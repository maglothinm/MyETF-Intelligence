"""Funding observations are not invoices, entitlements, or investment evidence."""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from .opportunity_common import timestamp, utc

CATALOG = [
    ('openai_api', 'OpenAI API', 'prepaid', 'runtime', 'Funds the PolitiTrack model, not ChatGPT.', 'https://platform.openai.com/settings/organization/billing/overview'),
    ('chatgpt', 'ChatGPT / Codex credits', 'unknown', 'separate_account', 'Separate development account. These credits do not fund the configured API key.', 'https://chatgpt.com/'),
    ('massive', 'Massive market data', 'unknown', 'runtime', 'Stocks Basic free data is selected; account invoices are not connected.', 'https://massive.com/dashboard'),
    ('finnhub', 'Finnhub quotes', 'unknown', 'runtime', 'Existing quote access; subscription and invoice balance are not verified.', 'https://finnhub.io/dashboard'),
    ('sec', 'SEC public filings', 'free', 'runtime', 'Public-data source; no prepaid provider balance.', 'https://www.sec.gov/edgar'),
    ('alphavantage', 'Alpha Vantage', 'unknown', 'legacy_integration', 'Retained legacy/Investor Edge integration; not the selected opportunity history provider.', 'https://www.alphavantage.co/support/'),
    ('pushover', 'Pushover', 'unknown', 'notifications', 'Client licence and message allowance differ; investment delivery stays suppressed.', 'https://pushover.net/'),
    ('gmail', 'Gmail / email account', 'unknown', 'notifications', 'Existing account; a Workspace subscription, if any, is separate from message counts.', 'https://myaccount.google.com/payments-and-subscriptions'),
    ('healthchecks', 'Healthchecks', 'unknown', 'supporting', 'Historical monitoring integration; record a bill only if an account charge exists.', 'https://healthchecks.io/'),
    ('github', 'GitHub Actions / storage', 'unknown', 'development', 'CI and retained artifacts; no current account invoice or paid allowance has been verified.', 'https://github.com/settings/billing'),
    ('beast', 'Beast / internet / electricity', 'included', 'local_host', 'Native local runtime. Existing household/hardware costs are not measured here; no cloud runtime.', None),
    ('other', 'Other PolitiTrack service', 'unknown', 'owner_declared', 'Optional owner-reported service cost; no provider connection is implied.', None),
]
PROVIDERS = {row[0]: row for row in CATALOG}
TYPES = {'prepaid', 'subscription', 'one_time', 'free', 'included', 'unknown'}
UNITS = {'USD', 'credits', 'requests'}


def decimal_value(value, *, negative=False):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,9}(?:\.\d{1,6})?', value):
        raise ValueError('Use a decimal amount, not a currency symbol or exponent.')
    number = Decimal(value)
    if not number.is_finite() or (number < 0 and not negative):
        raise ValueError('Invalid amount.')
    return number


def api_scope(key, environment=None):
    if not key:
        return None
    env = environment or {}
    value = [key, env.get('OPENAI_BASE_URL', ''), env.get('OPENAI_ORG_ID', ''), env.get('OPENAI_PROJECT_ID', '')]
    return hashlib.sha256(('polititrack-billing-v1\0' + '\0'.join(value)).encode()).hexdigest()


def error_metadata(exc):
    body = getattr(exc, 'body', None)
    body = body if isinstance(body, dict) else {}
    error = body.get('error') if isinstance(body.get('error'), dict) else body
    safe = lambda x: x if isinstance(x, str) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}', x) else None
    status = getattr(exc, 'status_code', None)
    return {'http_status': status if type(status) is int and 100 <= status <= 599 else None,
            'code': safe(error.get('code')), 'type': safe(error.get('type'))}


def validate_observation(data, now):
    allowed = {'provider', 'funding_type', 'unit', 'remaining', 'observed_at', 'low_threshold', 'charge_usd', 'next_due', 'label'}
    if not isinstance(data, dict) or set(data) != allowed or not isinstance(data['provider'], str) or data['provider'] not in PROVIDERS:
        raise ValueError('Choose a listed service and complete the observation form.')
    if not isinstance(data['funding_type'], str) or not isinstance(data['unit'], str) or data['funding_type'] not in TYPES or data['unit'] not in UNITS:
        raise ValueError('Invalid billing type or balance unit.')
    at = timestamp(data['observed_at'])
    if not at or at > now or (now - at).days > 366:
        raise ValueError('Balance observation must be within the past year, not in the future.')
    result = dict(data)
    result['observed_at'] = utc(at)
    for field in ('remaining', 'low_threshold', 'charge_usd'):
        if data[field] is not None:
            result[field] = str(decimal_value(data[field], negative=field == 'remaining'))
    if data['provider'] == 'openai_api' and (data['unit'] != 'USD' or data['funding_type'] not in {'prepaid', 'unknown'}):
        raise ValueError('Record the OpenAI API dollar balance, not ChatGPT usage-credit units.')
    if data['funding_type'] in {'free', 'included'} and any(data[k] is not None for k in ('remaining', 'charge_usd')):
        raise ValueError('Free/included services must not contain a paid balance or charge.')
    if data['funding_type'] == 'prepaid' and data['remaining'] is None:
        raise ValueError('Enter the remaining balance, not the amount of a recent top-up.')
    if data['next_due'] is not None:
        due = timestamp(data['next_due'])
        if not due or abs((due - now).days) > 366:
            raise ValueError('Invalid renewal or credit-expiration date.')
        result['next_due'] = utc(due)
    label = data['label']
    if not isinstance(label, str) or len(label) > 80 or any(ord(c) < 32 for c in label):
        raise ValueError('Use a short non-sensitive service label; never enter a key or payment details.')
    if re.search(r'(?i)(sk-[a-z0-9]|api[_ -]?key|password|token\s*[:=])', label):
        raise ValueError('Do not enter credentials in a billing label.')
    return result


def read_usage(path: Path | None, since: datetime):
    """Read operational observations only; never issue a model/billing request."""
    if path is None or not path.is_file():
        return [], 'not_metered'
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=3)) as db:
            db.execute('PRAGMA query_only=ON')
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='usage_events' AND type='table'").fetchone():
                return [], 'not_metered'
            rows = db.execute('SELECT payload FROM usage_events WHERE observed_at>=? ORDER BY observed_at,id LIMIT 100001', (since.date().isoformat(),)).fetchall()
            if len(rows) > 100000:
                return [], 'coverage_limit_exceeded'
        events = [json.loads(row[0]) for row in rows]
        if any(not isinstance(e, dict) or not timestamp(e.get('observed_at')) for e in events):
            return [], 'unavailable'
        return events, 'observed_requests_only'
    except (OSError, sqlite3.Error, ValueError):
        return [], 'unavailable'


def request_health(events, scope, now):
    current = [e for e in events if scope and e.get('billing_scope') == scope and timestamp(e['observed_at']) <= now]
    current.sort(key=lambda e: (timestamp(e['observed_at']), e.get('id', '')))
    last = current[-1] if current else None
    result = {'status': 'unverified', 'observed_at': None, 'last_success_at': None,
              'error_code': None, 'balance_verified': False}
    if not last:
        return result
    newer_unknown = any(not e.get('billing_scope') and timestamp(last['observed_at']) < timestamp(e['observed_at']) <= now for e in events)
    if newer_unknown:
        result['status'] = 'newer_request_scope_unverified'
        return result
    successes = [e for e in current if e.get('response_id') and not e.get('request_error_type')]
    result['last_success_at'] = successes[-1]['observed_at'] if successes else None
    error = last.get('provider_error') or {}
    code = error.get('code')
    code = code if isinstance(code, str) and re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}', code) else None
    status = 'available' if last.get('response_id') and not last.get('request_error_type') else 'request_failed'
    if code in {'credit_balance_exhausted', 'insufficient_quota'} or error.get('type') == 'insufficient_quota':
        status = 'funding_or_spend_limit_blocked'
    elif error.get('http_status') == 429:
        status = 'rate_limited'
    elif error.get('http_status') in (401, 403):
        status = 'authorization_failed'
    age = (now - timestamp(last['observed_at'])).total_seconds()
    result.update(status=status, observed_at=last['observed_at'], error_code=code,
                  age_seconds=age, stale=age > 7200)
    return result


def _estimate(observation, events, scope, coverage, now):
    result = {'amount': None, 'status': 'not_available', 'deducted_tokens_usd': None,
              'notice': 'Local token-cost estimate only; not the provider balance. Other applications, tools, taxes, credit expiration and unobserved charges are excluded.'}
    if not observation or observation.get('scope') != scope or not scope:
        return result
    if coverage != 'observed_requests_only' or observation['remaining'] is None:
        return result
    since = timestamp(observation['observed_at'])
    if (now - since).total_seconds() > 86400:
        result['status'] = 'balance_observation_stale'
        return result
    after = [e for e in events if since <= timestamp(e['observed_at']) <= now]
    if any(e.get('billing_scope') != scope or (e.get('billing') or {}).get('estimated_token_cost_usd') is None
           or e.get('tools_configured') or e.get('tool_call_count') for e in after):
        result['status'] = 'incomplete_cost_coverage'
        return result
    try:
        costs = [Decimal(str(e['billing']['estimated_token_cost_usd'])) for e in after]
        if any(not c.is_finite() or c < 0 for c in costs):
            raise ValueError
        total = sum(costs, Decimal(0))
        result.update(amount=str(Decimal(observation['remaining']) - total),
                      status='estimated_local_tokens_only', deducted_tokens_usd=str(total))
    except (InvalidOperation, ValueError, KeyError):
        result['status'] = 'invalid_cost_evidence'
    return result


def compose(latest, events, coverage, scope, now):
    from .api_usage import summarize
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_events = [e for e in events if month_start <= timestamp(e['observed_at']) <= now]
    safe_events = []
    for original in month_events:
        item = dict(original)
        price = (item.get('billing') or {}).get('estimated_token_cost_usd')
        try:
            if price is not None and (not Decimal(str(price)).is_finite() or Decimal(str(price)) < 0):
                raise ValueError
        except (InvalidOperation, ValueError):
            item['billing'] = {'estimated_token_cost_usd': None}
        safe_events.append(item)
    usage = summarize(safe_events)
    health = request_health(events, scope, now)
    services = []
    for provider, name, default, role, note, link in CATALOG:
        value = latest.get(provider)
        current = value is not None and (provider != 'openai_api' or value.get('scope') == scope)
        observed = timestamp(value['observed_at']) if value else None
        stale = observed is not None and (now - observed).total_seconds() > 86400
        kind = value['funding_type'] if current else default
        alerts = []
        if not current and kind not in {'free', 'included'}:
            alerts.append('balance_or_plan_not_recorded' if value is None else 'api_configuration_changed')
        if stale:
            alerts.append('balance_observation_stale')
        amount = value['remaining'] if current else None
        if amount is not None:
            if Decimal(amount) <= 0:
                alerts.append('recorded_balance_exhausted')
            elif value.get('low_threshold') is not None and Decimal(amount) <= Decimal(value['low_threshold']):
                alerts.append('recorded_balance_low')
        due = timestamp(value.get('next_due')) if current else None
        if due and (due - now).total_seconds() <= 7 * 86400:
            alerts.append('renewal_or_expiration_due')
        estimate = _estimate(value if current else None, events, scope, coverage, now) if provider == 'openai_api' else None
        if estimate and estimate['amount'] is not None and value.get('low_threshold') is not None:
            if Decimal(estimate['amount']) <= Decimal(value['low_threshold']):
                alerts.append('estimated_balance_low')
        if provider == 'openai_api' and health['status'] not in {'available', 'unverified'}:
            alerts.append('latest_api_request_' + health['status'])
        services.append({'provider': provider, 'name': name, 'role': role, 'note': note,
                         'billing_url': link, 'funding_type': kind, 'observation': {k: v for k, v in value.items() if k != 'scope'} if value else None,
                         'observation_matches_api_configuration': current, 'stale': stale,
                         'remaining': amount, 'unit': value['unit'] if value else 'USD',
                         'source': 'owner_reported' if current else 'not_verified',
                         'estimate': estimate, 'alerts': alerts})
    counts = Counter(row['funding_type'] for row in services)
    return {'schema_version': 1, 'generated_utc': utc(now), 'services': services,
            'api_health': health, 'api_usage': usage, 'usage_coverage': coverage,
            'paid_services_recorded': sum(row['observation_matches_api_configuration'] and row['funding_type'] in {'prepaid', 'subscription', 'one_time'} for row in services),
            'services_needing_attention': sum(bool(row['alerts']) for row in services),
            'unverified_services': sum(not row['observation_matches_api_configuration'] and row['funding_type'] not in {'free', 'included'} for row in services),
            'account_separation': 'OpenAI API funding is separate from ChatGPT subscriptions, wallets and usage credits. Never add these balances together.',
            'balance_policy': 'Remaining amounts are owner-reported observations, not live provider balances. The official OpenAI Costs API reports costs, not a prepaid balance; this installation does not scrape private billing endpoints or browser session keys.',
            'checks_make_paid_requests': False, 'automatic_purchases': False,
            'investment_alert_settings_changed': False}
