"""Free Massive EOD history with explicit coverage, safe pagination and pacing.

Derived cache belongs to the existing AI snapshot. The shared SQLite file only
coordinates API pacing; it is never a filing, portfolio or snapshot authority.
"""
from __future__ import annotations
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
from zoneinfo import ZoneInfo
import hashlib
import json
import os
import re
import sqlite3
import time
from dateutil.relativedelta import relativedelta
from .opportunity_common import DataUnavailable, OpportunityError, day, digest, number, read_json, timestamp, utc, write_json

BASE = 'https://api.massive.com'
CACHE_NAME = 'opportunity-massive-cache.json'
SCOPE = 'provider_daily_aggregate_not_verified_regular_only'
MAX_CACHE_BYTES = 24 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def validate_cache(value):
    if not isinstance(value, dict) or value.get('version') != 1 or not isinstance(value.get('entries'), dict):
        raise OpportunityError('invalid Massive derived cache')
    if len(json.dumps(value, allow_nan=False).encode('utf-8')) > MAX_CACHE_BYTES or len(value['entries']) > 128:
        raise OpportunityError('Massive cache size limit')
    for key, entry in value['entries'].items():
        if not isinstance(entry, dict) or entry.get('content_hash') != digest({k:v for k,v in entry.items() if k != 'content_hash'}):
            raise OpportunityError('Massive cache integrity failure')
        if not timestamp(entry.get('observed_at')) or not isinstance(entry.get('pages'), list):
            raise OpportunityError('invalid Massive cache provenance')


def load_key(environment):
    """Only explicit configured credentials; never a key embedded in source data."""
    key = str(environment.get('MASSIVE_API_KEY') or '').strip()
    file = environment.get('MASSIVE_API_KEY_FILE')
    if not key and file:
        path = Path(file)
        if not path.is_file() or path.stat().st_size > 8192:
            raise DataUnavailable('massive_key_file_unavailable')
        value = read_json(path)
        if value.get('provider') != 'massive' or value.get('plan') != 'stocks_basic_free':
            raise DataUnavailable('massive_free_key_configuration_invalid')
        key = str(value.get('api_key') or '').strip()
    if not key or any(c.isspace() for c in key) or len(key) > 512:
        raise DataUnavailable('massive_free_api_key_required')
    return key


class SharedPacer:
    """Serialize reservations for this key across processes and restarts (<=5/min)."""
    def __init__(self, path, key, *, clock=time.time, sleep=time.sleep):
        self.path, self.clock, self.sleep = Path(path), clock, sleep
        self.identity = hashlib.sha256(key.encode()).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pacing (identity TEXT PRIMARY KEY, next_at REAL NOT NULL)')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def acquire(self):
        started = self.clock()
        while True:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT next_at FROM pacing WHERE identity=?', (self.identity,)).fetchone()
                now = self.clock()
                wait = max(0.0, row[0]-now) if row else 0.0
                if not wait:
                    db.execute('INSERT INTO pacing VALUES (?,?) ON CONFLICT(identity) DO UPDATE SET next_at=excluded.next_at', (self.identity, now+13.0))
                    return
            if now < started or now-started+wait > 75:
                raise DataUnavailable('massive_rate_limit_backoff_pending')
            self.sleep(wait)

    def backoff(self, seconds):
        until = self.clock() + max(65.0, min(float(seconds), 86400.0))
        with self._db() as db:
            db.execute('INSERT INTO pacing VALUES (?,?) ON CONFLICT(identity) DO UPDATE SET next_at=max(next_at,excluded.next_at)', (self.identity, until))


class MassiveHistory:
    def __init__(self, config, rules, clock, budget, *, environment=None, session=None, pacer=None):
        self.config, self.rules, self.clock, self.budget = config, rules, clock, budget
        self.environment = os.environ if environment is None else environment
        self.key = load_key(self.environment)
        pacing = self.environment.get('MASSIVE_RATE_LIMIT_PATH')
        if pacer is None and not pacing:
            raise DataUnavailable('massive_shared_rate_limit_path_required')
        self.pacer = pacer or SharedPacer(pacing, self.key)
        if session is None:
            import requests
            session = requests.Session()
            # No transport-level retries may bypass pacing or consume invisible requests.
            session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
        self.session = session
        path = config.ai_dir / CACHE_NAME
        self.cache = read_json(path) if path.exists() else {'version':1, 'entries':{}}
        validate_cache(self.cache)
        self.requests, self.hits = 0, 0
        self.account = hashlib.sha256(self.key.encode()).hexdigest()

    def _save(self):
        validate_cache(self.cache)
        write_json(self.config.ai_dir / CACHE_NAME, self.cache)

    def _safe_url(self, url, prefix):
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.netloc != 'api.massive.com' or parts.username or parts.password or parts.fragment or (not parts.path.startswith(prefix) if prefix.endswith('/') else parts.path != prefix) or '..' in parts.path or '%' in parts.path:
            raise DataUnavailable('massive_unsafe_pagination_url')
        query = [(k,v) for k,v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in ('apikey','api_key','token')]
        return urlunsplit(('https','api.massive.com',parts.path,urlencode(query),''))

    def _get(self, url, params=None):
        if self.requests >= self.rules.get('massive_requests_per_run', 12):
            raise DataUnavailable('massive_per_run_budget_exhausted')
        self.budget.consume()
        self.pacer.acquire()
        self.requests += 1
        try:
            response = self.session.get(url, params=params, headers={'Authorization':'Bearer '+self.key},
                timeout=self.config.request_timeout, allow_redirects=False, stream=True)
            if response.status_code == 429:
                retry = number(response.headers.get('Retry-After')) or 65
                self.pacer.backoff(retry)
                raise DataUnavailable('massive_http_429_backoff')
            if response.status_code in (401,403):
                raise DataUnavailable('massive_key_or_free_tier_access_denied')
            if response.status_code != 200:
                raise DataUnavailable('massive_http_'+str(response.status_code))
            data = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                data.extend(chunk)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise DataUnavailable('massive_response_too_large')
            result = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
            if not isinstance(result, dict) or result.get('status') not in ('OK','DELAYED') or 'error' in result:
                raise DataUnavailable('massive_unusable_response')
            json.dumps(result, allow_nan=False)  # Also reject non-finite exponent values.
            return result
        except DataUnavailable:
            raise
        except Exception as exc:
            # Never expose provider response bodies, request headers or keys in errors.
            raise DataUnavailable('massive_request_failed:'+type(exc).__name__) from None
        finally:
            if 'response' in locals():
                response.close()

    def pages(self, path, params, prefix, *, aggregate=False):
        now = self.clock()
        today = now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
        key = digest({'provider':'massive','path':path,'params':params,'day':today,'account':self.account})
        entry = self.cache['entries'].get(key)
        if entry and timestamp(entry['observed_at']) > now:
            raise DataUnavailable('massive_future_cache')
        if entry is None:
            # Derived request cache only; historical decisions/anchors are not removed.
            entries = self.cache['entries']
            for old in list(entries):
                if entries[old].get('day') != today:
                    del entries[old]
            if len(entries) >= 128:
                oldest = min(entries, key=lambda k: entries[k]['observed_at'])
                del entries[oldest]
            entry = {'day':today,'observed_at':utc(now),'pages':[],'complete':False,
                     'next_url':BASE+path,'first_params':params,'seen_urls':[]}
        elif entry['complete']:
            self.hits += 1
            return deepcopy(entry['pages'])
        for _ in range(16-len(entry['pages'])):
            url = self._safe_url(entry['next_url'], prefix)
            if url in entry['seen_urls']:
                raise DataUnavailable('massive_pagination_cycle')
            payload = self._get(url, entry['first_params'] if not entry['pages'] else None)
            if not isinstance(payload.get('results'), list):
                if aggregate and payload.get('resultsCount') == 0 and 'results' not in payload:
                    payload['results'] = []
                else:
                    raise DataUnavailable('massive_missing_results')
            next_url = payload.get('next_url')
            if next_url:
                next_url = self._safe_url(next_url, prefix)
            payload = {k:payload[k] for k in ('results','status','ticker','adjusted','resultsCount','request_id') if k in payload}
            payload['observed_at'] = utc(self.clock())
            entry['pages'].append(payload)
            entry['seen_urls'].append(url)
            entry.update(next_url=next_url, complete=not next_url, observed_at=utc(self.clock()))
            entry['content_hash'] = digest({k:v for k,v in entry.items() if k != 'content_hash'})
            self.cache['entries'][key] = entry
            try:
                self._save()
            except OpportunityError:
                self.cache['entries'].pop(key, None)
                raise DataUnavailable('massive_cache_admission_limit') from None
            if not next_url:
                return deepcopy(entry['pages'])
        raise DataUnavailable('massive_pagination_limit')

    def history(self, row, now):
        ticker = str(row.get('ticker') or '')
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}', ticker):
            raise DataUnavailable('massive_unsupported_ticker')
        today = now.astimezone(ZoneInfo('America/New_York')).date()
        # Two-day cushion avoids requesting beyond the free plan's rolling boundary.
        start = (today-relativedelta(years=2)+timedelta(days=2)).isoformat()
        end = (today-timedelta(days=1)).isoformat()
        prefix = '/v2/aggs/ticker/'+quote(ticker,safe='')+'/range/1/day/'
        pages = self.pages(prefix+start+'/'+end, {'adjusted':'false','sort':'asc','limit':50000}, prefix, aggregate=True)
        splits = self.pages('/stocks/v1/splits', {'ticker':ticker,'execution_date.gte':start,
            'execution_date.lte':today.isoformat(),'limit':5000,'sort':'execution_date.asc'}, '/stocks/v1/splits')
        dividends = self.pages('/stocks/v1/dividends', {'ticker':ticker,'ex_dividend_date.gte':start,
            'ex_dividend_date.lte':today.isoformat(),'limit':5000,'sort':'ex_dividend_date.asc'}, '/stocks/v1/dividends')
        bars, actions, events = [], [], {}
        for kind, source_pages, date_key in [('split',splits,'execution_date'),('dividend',dividends,'ex_dividend_date')]:
            for page in source_pages:
                for item in page['results']:
                    if not isinstance(item,dict) or item.get('ticker') != ticker or not day(item.get(date_key)):
                        raise DataUnavailable('massive_corporate_action_identity_or_date')
                    date = item[date_key]
                    if not start <= date <= today.isoformat():
                        raise DataUnavailable('massive_corporate_action_outside_window')
                    eid = item.get('id')
                    if not isinstance(eid,str) or not eid:
                        raise DataUnavailable('massive_corporate_action_id_missing')
                    event_key = kind+'|'+eid
                    if event_key in events:
                        if events[event_key] != item:
                            raise DataUnavailable('massive_conflicting_corporate_action')
                        continue
                    events[event_key] = item
                    result = {'date':date,'kind':kind,'provider':'massive','source_id':eid,
                              'observed_at':page['observed_at'],'entry_price_adjusted':kind=='split'}
                    if kind == 'split':
                        old, new = number(item.get('split_from')), number(item.get('split_to'))
                        if old is None or new is None or old <= 0 or new <= 0:
                            raise DataUnavailable('massive_invalid_split_ratio')
                        ratio = new/old
                        if number(ratio) is None or ratio <= 0:
                            raise DataUnavailable('massive_invalid_split_ratio')
                        result['ratio'] = ratio
                    else:
                        amount = number(item.get('cash_amount'))
                        if amount is None or amount < 0 or str(item.get('currency','')).upper() != row['currency']:
                            raise DataUnavailable('massive_dividend_currency_or_amount')
                        result.update(amount=amount,currency=row['currency'])
                    actions.append(result)
        dates = set()
        for page in pages:
            if page.get('ticker') != ticker or page.get('adjusted') is not False:
                raise DataUnavailable('massive_history_identity_or_adjustment_conflict')
            if page.get('resultsCount') is not None and page['resultsCount'] != len(page['results']):
                raise DataUnavailable('massive_incomplete_aggregate_page')
            for item in page['results']:
                ms = item.get('t') if isinstance(item,dict) else None
                if isinstance(ms,bool) or not isinstance(ms,(int,float)) or number(ms) is None or ms <= 0:
                    raise DataUnavailable('massive_invalid_bar_timestamp')
                try:
                    at = datetime.fromtimestamp(ms/1000,timezone.utc).astimezone(ZoneInfo('America/New_York'))
                except (ValueError,OverflowError,OSError):
                    raise DataUnavailable('massive_invalid_bar_timestamp') from None
                date = at.date().isoformat()
                if at.hour or at.minute or at.second or not start <= date <= end or date in dates or item.get('otc') is True:
                    raise DataUnavailable('massive_bar_date_scope_or_duplicate')
                values = {name:number(item.get(short)) for name,short in [('open','o'),('high','h'),('low','l'),('close','c')]}
                if any(v is None or v <= 0 for v in values.values()) or values['low'] > min(values['open'],values['close']) or values['high'] < max(values['open'],values['close']):
                    raise DataUnavailable('massive_invalid_ohlc')
                factor = Decimal(1)
                for action in actions:
                    if action['kind']=='split' and date < action['date'] <= today.isoformat():
                        factor *= Decimal(str(action['ratio']))
                values = {k:float(Decimal(str(v))/factor) for k,v in values.items()}
                if any(number(v) is None or v<=0 for v in values.values()):
                    raise DataUnavailable('massive_split_adjustment_invalid')
                bars.append({'date':date,**values,'window_start_at':utc(at),'observed_at':page['observed_at'],
                             'session_scope':SCOPE,'raw_ohlc':{k:item[k] for k in ('o','h','l','c')},
                             'volume':number(item.get('v'))})
                dates.add(date)
        if not bars:
            raise DataUnavailable('massive_no_historical_bars')
        bars.sort(key=lambda b:b['date'])
        actions.sort(key=lambda a:(a['date'],a['kind'],a['source_id']))
        all_pages = pages+splits+dividends
        if self.clock().astimezone(ZoneInfo('America/New_York')).date() != today:
            raise DataUnavailable('massive_day_boundary_requires_new_snapshot')
        return {'security_id':row['security_id'],'share_class':row['share_class'],'currency':row['currency'],
                'basis':'split_adjusted','basis_date':today.isoformat(),'actions_complete':True,
                'adjustments_through':today.isoformat(),'provider_conflict':False,'bars':bars,
                'adjustment_events':actions,'history_provider':'massive_basic_raw_daily_ohlc_explicit_splits',
                'history_observed_at':max(p['observed_at'] for p in all_pages),
                'history_session_scope':SCOPE,'history_coverage_start':start,
                'history_coverage_end':bars[-1]['date'],'free_plan_history_years':2,
                'source_pages':[{'request_id':p.get('request_id'),'observed_at':p['observed_at'],
                    'payload_hash':digest(p)} for p in all_pages],
                'history_notice':'Free EOD history, not a current quote. Provider daily aggregates use eligible-trade rules; regular-hours-only coverage is not asserted. Dividends are retained separately, not added to price returns.'}

    def metadata(self, ticker, date):
        if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,14}',ticker) or not day(date):
            raise DataUnavailable('massive_metadata_input_invalid')
        payload = self._get(BASE+'/v3/reference/tickers/'+quote(ticker,safe=''), {'date':date})
        value = payload.get('results')
        if not isinstance(value,dict) or value.get('ticker') != ticker or value.get('market')!='stocks' or value.get('locale')!='us' or not value.get('composite_figi') or not value.get('share_class_figi') or str(value.get('currency_name','')).upper()!='USD':
            raise DataUnavailable('massive_security_identity_unresolved')
        return {k:value.get(k) for k in ('ticker','name','type','active','primary_exchange','composite_figi','share_class_figi','cik','currency_name')}
