"""Observed capability renewal within the existing SHADOW AI owner.

No time-only renewal, new entitlement, ticker guessing or subscription upgrade.
Only the independently verified seed securities may be refreshed. Live delivery
continues to require its separate activation/capability path.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from .opportunity_common import DataUnavailable, OpportunityError, digest, number, timestamp, utc, read_json, write_json
from .opportunity_market import ExchangeCalendar
from .opportunity_massive import MassiveHistory, load_key

NAME='opportunity-capability-refresh.json'
POLICY_URL='https://finnhub.io/docs/api/quote'


def validate_cache(value):
    if not isinstance(value,dict) or value.get('version')!=1 or not isinstance(value.get('securities'),dict) or len(value['securities'])>32:
        raise OpportunityError('invalid capability observation cache')
    if len(json.dumps(value,allow_nan=False).encode())>2_000_000:
        raise OpportunityError('capability observation cache too large')
    for row in value['securities'].values():
        if not isinstance(row,dict) or row.get('receipt_hash')!=digest({k:v for k,v in row.items() if k!='receipt_hash'}):
            raise OpportunityError('capability observation integrity failure')
        if not timestamp(row.get('checked_at')) or not timestamp(row.get('valid_until')) or not isinstance(row.get('mapping'),dict):
            raise OpportunityError('invalid capability observation dates')


def parse_quote_contract(html):
    """Read the public structured documentation as data, never execute scripts."""
    match=re.search(r'"/quote"\s*:\s*(\{)',html)
    if not match:
        raise DataUnavailable('finnhub_quote_contract_unavailable')
    try:
        endpoint=json.JSONDecoder().raw_decode(html[match.start(1):])[0]['get']
    except (ValueError,KeyError,TypeError):
        raise DataUnavailable('finnhub_quote_contract_invalid') from None
    description=BeautifulSoup(endpoint.get('description',''),'html.parser').get_text(' ',strip=True)
    if endpoint.get('operationId')!='quote' or endpoint.get('premium') is not None or 'Get real-time quote data for US stocks.' not in description:
        raise DataUnavailable('finnhub_quote_contract_changed_requires_review')
    return {'source_url':POLICY_URL,'description':description,'operation_id':'quote',
            'premium_marker':None,'contract_sha256':digest(endpoint)}


def matching_metadata(metadata, seed, ticker):
    fields={'composite_figi':'security_id','share_class_figi':'share_class','primary_exchange':'exchange'}
    if metadata.get('ticker')!=ticker or metadata.get('active') is not True or metadata.get('type') not in ('CS','ETF'):
        raise DataUnavailable('refreshed_security_not_active_supported_type')
    if seed.get('exchange')=='ARCX' and metadata.get('type')!='ETF':
        raise DataUnavailable('benchmark_type_changed')
    if seed.get('exchange')!='ARCX' and metadata.get('type')!='CS':
        raise DataUnavailable('company_share_type_changed')
    if any(metadata.get(k)!=seed.get(v) for k,v in fields.items()) or str(metadata.get('currency_name','')).upper()!=seed.get('currency') or str(metadata.get('cik','')).lstrip('0')!=str(seed.get('cik','')).lstrip('0'):
        raise DataUnavailable('refreshed_security_identity_conflict')


def current_capabilities(cache, seed, now, scope):
    if cache.get('scope')!=scope or cache.get('seed_hash')!=digest(seed):
        return {}
    selected={ticker:row for ticker,row in cache['securities'].items()
              if timestamp(row['checked_at'])<=now<timestamp(row['valid_until'])
              and not (timestamp((cache.get('attempts',{}).get(ticker) or {}).get('at')) and timestamp(cache['attempts'][ticker]['at'])>=timestamp(row['checked_at']))
              and row['mapping'].get('valid_through','')>=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()}
    if not selected:
        return {}
    return {'version':1,'verified_at':min(row['checked_at'] for row in selected.values()),
            'valid_until':min(row['valid_until'] for row in selected.values()),
            'verification_reference':'native_readonly_provider_observations:'+digest(selected),
            'finnhub_realtime_verified':True,'massive_basic_verified':True,
            'alphavantage_daily_adjusted_verified':False,
            'securities':{k:deepcopy(v['mapping']) for k,v in selected.items()},
            'filers_by_report':deepcopy(seed.get('filers_by_report',{}))}


def refresh(config,rules,session,environment,clock,budget,*,history_client=None,calendar=None):
    if environment.get('OPPORTUNITY_REFRESH_CAPABILITIES')!='true' or rules['mode']!='shadow':
        return {'status':'disabled'},None,history_client
    seed_path=config.ai_dir/'opportunity-provider-capabilities.json'
    if not seed_path.exists():
        return {'status':'blocked','reason':'independently_verified_seed_required'},None,history_client
    # Validate seed schema/observed time through the existing reader before use.
    from .opportunity_providers import capabilities
    if not capabilities(config.ai_dir,clock(),historical_identity_only=True):
        return {'status':'blocked','reason':'valid_historical_identity_seed_required'},None,history_client
    seed=read_json(seed_path)
    try:
        key=load_key(environment)
        if not config.finnhub_api_key:
            raise DataUnavailable('finnhub_key_required')
    except DataUnavailable as exc:
        return {'status':'blocked','reason':str(exc)},None,history_client
    scope=hashlib.sha256((key+'\x00'+config.finnhub_api_key).encode()).hexdigest()
    path=config.ai_dir/NAME
    cache=read_json(path) if path.exists() else {'version':1,'securities':{},'attempts':{}}
    validate_cache(cache)
    if cache.get('scope')!=scope or cache.get('seed_hash')!=digest(seed):
        cache={'version':1,'securities':{},'attempts':{},'scope':scope,'seed_hash':digest(seed)}
    before=digest(cache);now=clock();cal=calendar or ExchangeCalendar()
    session_window=cal.session(now.astimezone(ZoneInfo('America/New_York')).date().isoformat())
    if not session_window or not session_window[0]<=now<session_window[1]:
        return {'status':'awaiting_regular_session_verification'},current_capabilities(cache,seed,now,scope),history_client
    today=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    due=[s for s in sorted(seed['securities']) if not cache['securities'].get(s) or not timestamp(cache['securities'][s].get('valid_until')) or timestamp(cache['securities'][s]['valid_until'])<=now+timedelta(hours=2) or cache['securities'][s]['mapping']['valid_through']<today]
    due=[s for s in due if not timestamp(cache.get('attempts',{}).get(s,{}).get('retry_after')) or timestamp(cache['attempts'][s]['retry_after'])<=now]
    cursor=cache.get('cursor','');due.sort(key=lambda s:(s<=cursor,s))
    report={'status':'current' if not due else 'verifying','verified_symbols':[],'failures':{}}
    # One security per tick, at most four Massive requests, using the SAME budgets/pacer.
    for symbol in due[:1]:
        cache['cursor']=symbol
        try:
            policy=cache.get('quote_contract') or {}
            if policy.get('checked_day')!=today:
                budget.consume()
                with session.get(POLICY_URL,timeout=config.request_timeout,allow_redirects=False,stream=True) as response:
                    if response.status_code!=200:
                        raise DataUnavailable('finnhub_quote_contract_http_unavailable')
                    content=bytearray()
                    for chunk in response.iter_content(65536):
                        content.extend(chunk)
                        if len(content)>2_000_000:
                            raise DataUnavailable('finnhub_quote_contract_size_limit')
                policy={**parse_quote_contract(bytes(content).decode('utf-8')), 'checked_day':today,'observed_at':utc(clock()),'page_sha256':hashlib.sha256(content).hexdigest()}
                cache['quote_contract']=policy
            if history_client is None:
                history_client=MassiveHistory(config,rules,clock,budget,environment=environment)
            expected=seed['securities'][symbol]
            metadata=history_client.metadata(symbol)
            matching_metadata(metadata,expected,symbol)
            row={**expected,'ticker':symbol,'security_evidence':expected['source_url']}
            history=history_client.history(row,clock())
            budget.consume()
            with session.get('https://finnhub.io/api/v1/quote',params={'symbol':symbol,'token':config.finnhub_api_key},timeout=config.request_timeout,allow_redirects=False) as response:
                if response.status_code!=200:
                    raise DataUnavailable('finnhub_quote_access_failed')
                quote=response.json()
            at=number(quote.get('t'));price=number(quote.get('c'));checked=clock()
            if not at or not price or price<=0 or not 0<=checked.timestamp()-at<=rules['quote_max_seconds']:
                raise DataUnavailable('fresh_regular_session_quote_not_observed')
            quote_at=datetime.fromtimestamp(at,timezone.utc)
            if not session_window[0]<=quote_at<=checked<session_window[1]:
                raise DataUnavailable('quote_not_in_verified_regular_session')
            observation={'checked_at':utc(checked),'valid_until':utc(checked+timedelta(hours=24)),
                'mapping':{**expected,'valid_through':today},'metadata_sha256':digest(metadata),
                'policy_reference':deepcopy(policy),'quote_observation':{'price':price,'at':utc(quote_at),'observed_at':utc(checked),'response_sha256':digest(quote)},
                'history_reference':{'bar_count':len(history['bars']),'through':history['history_coverage_end'],'source_pages':history.get('source_pages',[])}}
            observation['receipt_hash']=digest(observation)
            cache['securities'][symbol]=observation
            cache.setdefault('attempts',{}).pop(symbol,None)
            report['verified_symbols'].append(symbol)
        except OpportunityError:
            raise
        except (DataUnavailable, ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
            reason=str(exc) if isinstance(exc,DataUnavailable) else 'capability_probe_invalid:'+type(exc).__name__
            cache.setdefault('attempts',{})[symbol]={'reason':reason,'at':utc(clock()),'retry_after':utc(clock()+timedelta(minutes=60))}
            report['failures'][symbol]=reason
        except Exception as exc:
            cache.setdefault('attempts',{})[symbol]={'reason':'capability_probe_unavailable:'+type(exc).__name__,'at':utc(clock()),'retry_after':utc(clock()+timedelta(minutes=60))}
            report['failures'][symbol]='capability_probe_unavailable:'+type(exc).__name__
    validate_cache(cache)
    if digest(cache)!=before:
        write_json(path,cache)
        report['observation_changed']=True
        report['observation_hash']=digest(cache)
    report['status']='verified' if report['verified_symbols'] else 'blocked' if report['failures'] else 'current'
    return report,current_capabilities(cache,seed,clock(),scope),history_client
