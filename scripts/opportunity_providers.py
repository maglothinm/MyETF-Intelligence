"""Permitted-provider adapters with explicit entitlement and security evidence.

Use Alpha Vantage raw OHLC plus split coefficients, never dividend-adjusted
close against a raw Finnhub quote. No fallback endpoint or invented timestamp.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .opportunity_common import DataUnavailable, OpportunityError, ROOT, day, number, read_json, timestamp, utc
from .opportunity_notifications import DeliveryRejected


class RequestBudget:
    def __init__(self, limit: int):
        self.remaining = limit

    def consume(self):
        if self.remaining <= 0:
            raise DataUnavailable('provider_request_budget_exhausted')
        self.remaining -= 1


def capabilities(ai_dir: Path, now: datetime) -> dict:
    path = ai_dir / 'opportunity-provider-capabilities.json'
    if not path.exists():
        return {}
    value = read_json(path)
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(read_json(ROOT/'schemas/opportunity_provider_capabilities.schema.json')).iter_errors(value))
    if errors:
        raise OpportunityError('invalid provider capability record: '+errors[0].message)
    if value.get('version') != 1 or not timestamp(value.get('verified_at')) or not timestamp(value.get('valid_until')) or not timestamp(value['verified_at']) <= now <= timestamp(value['valid_until']) or not value.get('verification_reference'):
        return {}
    return value


def enrich_identities(rows: list[dict], caps: dict, now: datetime) -> list[dict]:
    """Exact evidenced source/security mappings; no similar-name or ticker merges."""
    result = []
    for raw in rows:
        row = dict(raw)
        match = (caps.get('securities') or {}).get(str(row.get('ticker')))
        if match and match.get('source_url') and day(match.get('valid_from')) and day(match.get('valid_through')) and day(row.get('transaction_date')) and day(match['valid_from']) <= day(row['transaction_date']) <= day(match['valid_through']) and now.date() <= day(match['valid_through']):
            row.update({k:match[k] for k in ('security_id','currency','share_class','exchange') if k in match})
            row['security_evidence'] = match['source_url']
        filer = (caps.get('filers_by_report') or {}).get(str(row.get('source'))+'|'+str(row.get('report_id')))
        if filer and filer.get('source_url') and filer.get('filer_id'):
            row['filer_id'] = filer['filer_id']
        result.append(row)
    return result


class MarketProvider:
    def __init__(self, config, rules, session, caps, clock, budget: RequestBudget):
        self.config, self.rules, self.session, self.caps, self.clock, self.budget = config, rules, session, caps, clock, budget
        self.cache = {}

    def get(self, url, params=None, headers=None):
        self.budget.consume()
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.config.request_timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise DataUnavailable('provider_request_failed:'+type(exc).__name__) from exc

    def snapshot(self, rows, now, force=False):
        row = rows[0]
        ticker, sid = row.get('ticker'), row.get('security_id')
        if not sid or not row.get('security_evidence'):
            raise DataUnavailable('security_mapping_not_verified')
        if row.get('exchange') not in ('XNYS', 'XNAS') or row.get('currency') != 'USD':
            raise DataUnavailable('unsupported_exchange_or_currency')
        if not self.caps.get('finnhub_realtime_verified') or not self.caps.get('alphavantage_daily_adjusted_verified'):
            raise DataUnavailable('realtime_and_split_history_entitlements_not_verified')
        if not self.config.finnhub_api_key or not self.config.alphavantage_api_key:
            raise DataUnavailable('required_market_credentials_unavailable')
        key = (sid, row.get('share_class'), row.get('currency'))
        if not force and key in self.cache:
            return deepcopy(self.cache[key])
        quote = self.get('https://finnhub.io/api/v1/quote', params={'symbol':ticker,'token':self.config.finnhub_api_key})
        observed = self.clock()
        at_number = number(quote.get('t'))
        if not at_number or at_number <= 0:
            raise DataUnavailable('provider_quote_timestamp_missing')
        at = utc(datetime.fromtimestamp(at_number, timezone.utc))
        history = self.get('https://www.alphavantage.co/query', params={'function':'TIME_SERIES_DAILY_ADJUSTED','symbol':ticker,'outputsize':'full','apikey':self.config.alphavantage_api_key})
        series = history.get('Time Series (Daily)')
        if not isinstance(series, dict) or any(history.get(k) for k in ('Information','Note','Error Message')):
            raise DataUnavailable('split_history_entitlement_or_coverage_unavailable')
        bars, actions, factor = [], [], 1.0
        today = observed.astimezone(ZoneInfo('America/New_York')).date().isoformat()
        for date_value, values in sorted(series.items(), reverse=True):
            if not day(date_value) or date_value > today:
                continue
            split = number(values.get('8. split coefficient'))
            dividend = number(values.get('7. dividend amount'))
            if split is None or split <= 0 or dividend is None or dividend < 0:
                raise DataUnavailable('missing_corporate_action_data')
            raw = {field:number(values.get(str(i)+'. '+field)) for i,field in enumerate(('open','high','low','close'), 1)}
            if any(v is None or v <= 0 for v in raw.values()):
                raise DataUnavailable('invalid_provider_history')
            bars.append({'date':date_value, **{k:v/factor for k,v in raw.items()}})
            if split != 1:
                actions.append({'date':date_value,'kind':'split','ratio':split,'provider':'alphavantage'})
            if dividend:
                actions.append({'date':date_value,'kind':'dividend','amount':dividend,'entry_price_adjusted':False,'provider':'alphavantage'})
            factor *= split
        result = {'security_id':sid,'share_class':row['share_class'],'currency':row['currency'],
                  'basis':'split_adjusted','basis_date':today,'actions_complete':True,'provider_conflict':False,
                  'history_provider':'alphavantage_daily_adjusted_raw_ohlc_and_splits','bars':bars,'adjustment_events':actions,
                  'quote':{'price':number(quote.get('c')),'at':at,'observed_at':utc(observed),'provider':'finnhub',
                           'precision':'second','kind':'realtime','feed_delay_seconds':0,
                           'session_high':number(quote.get('h')),'session_low':number(quote.get('l'))}}
        previous_bars = [b for b in bars if b['date'] < today]
        previous_close = number(quote.get('pc'))
        if previous_bars and previous_close and abs(previous_close/previous_bars[0]['close']-1) > 0.01:
            result['provider_conflict'] = True
        self.cache[key] = result
        return deepcopy(result)


class EvidenceProvider:
    """Reuse explicit current reviews; absent coverage never implies clearance."""
    def __init__(self, reviews: list[dict], rules: dict, *, reviewer=None, model_budget=2):
        self.reviews, self.rules, self.reviewer, self.remaining = reviews, rules, reviewer, model_budget

    def review(self, rows, membership_hash, now, force=False):
        matches = [r for r in self.reviews if r.get('membership_hash') == membership_hash and timestamp(r.get('checked_at')) and timestamp(r['checked_at']) <= now and timestamp(r.get('valid_until')) and now <= timestamp(r['valid_until'])]
        if matches and (not force or not self.reviewer):
            return deepcopy(max(matches, key=lambda r:r['checked_at']))
        if self.reviewer and self.remaining > 0:
            self.remaining -= 1
            result = self.reviewer(rows, membership_hash, now)
            self.reviews.append(deepcopy(result))
            return result
        raise DataUnavailable('current_source_backed_contradiction_review_unavailable')


class NotificationProvider:
    """Use exactly the analyst's existing recipient and priority configuration."""
    def __init__(self, config):
        self.config = config

    def send(self, channel, alert, event_id):
        from . import ai_filing_analyst as analyst
        from . import ai_filing_analyst_hardened as hardened
        try:
            if channel == 'pushover':
                import requests
                response = requests.post(analyst.PUSHOVER_MESSAGES_URL,
                    data={'token':self.config.pushover_api_token,'user':self.config.pushover_user_key,
                          'title':alert['title'],'message':alert['message'],'url':alert['url'],'priority':0},
                    timeout=self.config.request_timeout)
                if response.status_code in (400,401,403,413,429):
                    raise DeliveryRejected('pushover rejected request')
                response.raise_for_status()
                result = response.json()
                if result.get('status') != 1:
                    raise DeliveryRejected('pushover did not accept request')
                return {'accepted':True,'provider':'pushover','request_id':result.get('request'),'event_id':event_id}
            if channel == 'gmail':
                accepted = hardened._send_candidate_email_with_evidence(self.config, alert)
                return {'accepted':accepted,'provider':'gmail','event_id':event_id}
            raise DeliveryRejected('unsupported configured channel')
        except hardened.CandidateDeliveryRejected as exc:
            raise DeliveryRejected('email rejected before acceptance') from exc
