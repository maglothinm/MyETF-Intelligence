"""Local API usage observations, never an invoice or a trading-state authority.

No prompts, completions, keys, response bodies or raw exceptions are retained.
The optional native-host journal survives failed analyst runs; snapshots publish
summaries through the existing AI writer. Missing billing evidence stays unknown.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from contextlib import closing
from typing import Mapping
import json
import logging
import os
import re
import sqlite3
from .opportunity_common import ROOT, read_json, write_json, digest, timestamp, utc

LOG=logging.getLogger(__name__)
SUMMARY_NAME='api-usage-summary.json'


def _get(value,key,default=None):
    return value.get(key,default) if isinstance(value,Mapping) else getattr(value,key,default)


def _count(value):
    return value if type(value) is int and value>=0 else None


def capture(response):
    value=_get(response,'usage')
    inputs,outputs=_count(_get(value,'input_tokens')),_count(_get(value,'output_tokens'))
    details=_get(value,'input_tokens_details')
    cached=_count(_get(details,'cached_tokens'))
    writes=_count(_get(details,'cache_write_tokens',0))
    reasoning=_count(_get(_get(value,'output_tokens_details'),'reasoning_tokens'))
    valid=inputs is not None and outputs is not None and cached is not None and writes is not None and cached+writes<=inputs and (reasoning is None or reasoning<=outputs)
    return {'status':'reported' if valid else 'missing_or_inconsistent','input_tokens':inputs,'output_tokens':outputs,
            'cached_input_tokens':cached,'cache_write_tokens':writes,'reasoning_tokens':reasoning,
            'cache_write_detail_reported':_get(details,'cache_write_tokens') is not None,
            'note':'Cached/write tokens are input subsets; reasoning tokens are already included in output tokens.'}


def estimate(usage,model,service_tier,at,tariffs):
    result={'status':'unknown','estimated_token_cost_usd':None,'rate_reference':None}
    rate=(tariffs.get('models') or {}).get(model)
    if usage.get('status')!='reported' or not rate or service_tier not in ('default','standard',None):
        return result
    if not timestamp(at) or not timestamp(tariffs.get('verified_at')) or timestamp(at)<timestamp(tariffs['verified_at']):
        return result
    try:
        inputs=usage['input_tokens']; cached=usage['cached_input_tokens'];writes=usage['cache_write_tokens'];outputs=usage['output_tokens']
        long=inputs>rate['long_context_threshold']
        im=Decimal(str(rate['long_input_multiplier'])) if long else Decimal(1)
        om=Decimal(str(rate['long_output_multiplier'])) if long else Decimal(1)
        uncached_rate=Decimal(str(rate['input_per_million']))
        cached_rate=Decimal(str(rate['cached_input_per_million']))
        output_rate=Decimal(str(rate['output_per_million']))
        cost=((inputs-cached-writes)*uncached_rate+cached*cached_rate+writes*uncached_rate*Decimal(str(rate['cache_write_multiplier'])))*im+outputs*output_rate*om
        cost=cost/Decimal(1000000)
        if not cost.is_finite() or cost<0:
            return result
        result.update(status='estimated_tokens_only',estimated_token_cost_usd=str(cost),
            rate_reference={'version':tariffs['version'],'verified_at':tariffs['verified_at'],'source_url':rate['source_url'],'model':model,'long_context_applied':long})
    except (ValueError,TypeError,KeyError,ArithmeticError):
        pass
    return result


def journal_path(config):
    selected=os.environ.get('POLITITRACK_API_USAGE_PATH')
    return Path(selected) if selected else config.ai_dir/'api-usage.sqlite3'


def record_attempt(config,attempt_id,response=None,*,error_type=None):
    """Accounting failure must not turn a retry into a duplicated investment action."""
    try:
        at=utc(datetime.now(timezone.utc)); usage=capture(response)
        model=str(_get(response,'model') or config.model)
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',model):
            model='unrecognized'
        rid=str(_get(response,'id') or '')
        rid=rid if re.fullmatch(r'[A-Za-z0-9_-]{1,200}',rid) else None
        outputs=_get(response,'output') or []
        tools=sum(_get(item,'type') in ('web_search_call','file_search_call','code_interpreter_call','image_generation_call') for item in outputs)
        tariffs=read_json(ROOT/'config/api_usage_rates.json')
        billing=estimate(usage,model,_get(response,'service_tier'),at,tariffs)
        event={'schema_version':1,'id':str(attempt_id),'response_id':rid,'observed_at':at,'model':model,
            'response_status':str(_get(response,'status') or 'request_error')[:40],
            'request_error_type':str(error_type)[:100] if error_type else None,'usage':usage,
            'tool_call_count':tools,'tools_configured':bool(config.web_search_enabled),
            'billing':billing,'cost_scope':'text-token estimate only; excludes tools, tax, discounts, unreported cache-write charges and unobserved requests'}
        path=journal_path(config); path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(path,timeout=5)) as db:
            with db:
                db.execute('CREATE TABLE IF NOT EXISTS usage_events (id TEXT PRIMARY KEY,response_id TEXT UNIQUE,observed_at TEXT NOT NULL,payload TEXT NOT NULL)')
                db.execute('INSERT OR IGNORE INTO usage_events VALUES (?,?,?,?)',(event['id'],rid,at,json.dumps(event,sort_keys=True,allow_nan=False)))
    except Exception:
        LOG.warning('API usage accounting unavailable; the displayed cost may be incomplete.')


def summarize(events):
    months={}
    for event in events:
        at=timestamp(event.get('observed_at'))
        if at is None:
            continue
        key=at.strftime('%Y-%m')
        group=months.setdefault(key,{'month_utc':key,'attempts':0,'usage_reported_attempts':0,'unpriced_attempts':0,
            'input_tokens':0,'output_tokens':0,'cached_input_tokens':0,'reasoning_tokens':0,'tool_call_count':0,
            'estimated_token_subtotal_usd':'0','models':set(),'first_observed_at':event['observed_at'],'last_observed_at':event['observed_at']})
        group['attempts']+=1;group['models'].add(event.get('model','unknown'))
        group['first_observed_at']=min(group['first_observed_at'],event['observed_at']);group['last_observed_at']=max(group['last_observed_at'],event['observed_at'])
        usage=event.get('usage') or {}; cost=(event.get('billing') or {}).get('estimated_token_cost_usd')
        if usage.get('status')=='reported':
            group['usage_reported_attempts']+=1
            for k in ('input_tokens','output_tokens','cached_input_tokens','reasoning_tokens'):
                group[k]+=usage.get(k) or 0
        group['tool_call_count']+=event.get('tool_call_count',0)
        if cost is None:
            group['unpriced_attempts']+=1
        else:
            group['estimated_token_subtotal_usd']=str(Decimal(group['estimated_token_subtotal_usd'])+Decimal(cost))
    for group in months.values():
        group['models']=sorted(group['models'])
        group['coverage']='observed_requests_only'
        group['complete_account_bill_available']=False
        group['estimated_observed_tokens_usd']=group['estimated_token_subtotal_usd'] if not group['unpriced_attempts'] else None
    return {'schema_version':1,'generated_utc':utc(datetime.now(timezone.utc)),'months':sorted(months.values(),key=lambda g:g['month_utc'],reverse=True),
        'notice':'Observed API requests, not the total account bill. Historic unmetered calls cannot be reconstructed. Token estimates use dated public rates; tool charges, taxes, credits and other applications are excluded. Missing usage is not zero.',
        'data_stack':{'massive_basic_subscription_usd':0,'sec_subscription_usd':0,'new_finnhub_subscription_usd':0,'cloud_hosting_usd':0,'note':'Selected free data design, not verification of account invoices. Existing OpenAI API use is paid separately.'}}


def publish(config):
    path=journal_path(config)
    try:
        events=[]
        if path.exists():
            with closing(sqlite3.connect(path,timeout=5)) as db:
                db.execute('PRAGMA query_only=ON')
                events=[json.loads(row[0]) for row in db.execute('SELECT payload FROM usage_events ORDER BY observed_at,id')]
        summary=summarize(events)
    except Exception:
        summary=summarize([]);summary['accounting_status']='unavailable';summary['notice']='Usage journal could not be read; no zero-cost claim is made.'
    write_json(config.ai_dir/SUMMARY_NAME,summary)
    return summary
