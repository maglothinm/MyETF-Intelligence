"""Immutable-decision outcome accounting. No positions, orders or backdated fills."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from .opportunity_common import day, digest, number, timestamp, utc
from .opportunity_benchmark import advance_benchmark


def advance(previous,record,snapshot,calendar,now,*,deliveries=None,intents=None,cost_bps=10.0):
    research=deepcopy(previous or {'version':1,'cohorts':{}})
    if research.get('version')!=1 or not isinstance(research.get('cohorts'),dict):
        raise ValueError('invalid retained opportunity research')
    gates=record.get('gates') or {}; dossier=record.get('investment_dossier') or {}
    definitions={'buying_only':gates.get('meaningful_buying') is True,
                 'company_case_and_price':dossier.get('status')=='ready_for_human_review',
                 'full_method':record.get('lifecycle')=='opportunity_available'}
    for label,qualified in definitions.items():
        key=digest({'opportunity':record['opportunity_id'],'rule_hash':record['rule_hash'],'cohort':label})
        if qualified and key not in research['cohorts']:
            research['cohorts'][key]={'cohort':label,'rule_hash':record['rule_hash'],'mode':record['mode'],
                'first_decision_at':utc(now),'decision_usable_at':None if record['mode']=='live' and label=='full_method' else utc(now),
                'anchor':None,'outcomes':{},'cost_assumption_bps':cost_bps,
                'timing_basis':'after_accepted_alert' if record['mode']=='live' and label=='full_method' else 'after_evaluation',
                'notice':'Conditional on evaluated disclosure population; not an independent stock-universe benchmark. No actual investment or fill.'}
    q=(record.get('market') or {}).get('quote') or {}
    qt,observed,price=timestamp(q.get('at')),timestamp(q.get('observed_at')),number(q.get('price'))
    quote_ok=bool(qt and observed and qt<=observed<=now and (observed-qt).total_seconds()<=300 and price and price>0
        and q.get('kind')=='realtime' and q.get('feed_delay_seconds')==0 and (record.get('market') or {}).get('session')=='regular')
    today=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    for cohort in research['cohorts'].values():
        if cohort['timing_basis']=='after_accepted_alert' and not cohort['decision_usable_at']:
            candidates=[]
            for eid,intent in (intents or {}).items():
                if intent.get('opportunity_id')!=record['opportunity_id'] or (intent.get('snapshot') or {}).get('rule_hash')!=cohort['rule_hash']:
                    continue
                for delivery in (deliveries or {}).get(eid,{}).values():
                    accepted=timestamp(delivery.get('accepted_at'))
                    if delivery.get('status')=='accepted' and accepted and accepted>=timestamp(cohort['first_decision_at']):
                        candidates.append(accepted)
            if candidates:
                cohort['decision_usable_at']=utc(min(candidates))
        usable=timestamp(cohort.get('decision_usable_at'))
        if not cohort['anchor'] and quote_ok and usable and qt>usable:
            session_date=qt.astimezone(ZoneInfo('America/New_York')).date().isoformat()
            session=calendar.session(session_date)
            if session and session[0]<=qt<=session[1] and snapshot.get('basis')=='split_adjusted' and snapshot.get('actions_complete') is True:
                cohort['anchor']={'price':price,'at':q['at'],'observed_at':q['observed_at'],'provider':q.get('provider'),
                    'session_date':session_date,'basis_date':snapshot.get('basis_date'),'currency':record.get('currency'),
                    'security_id':record.get('security_id'),'share_class':record.get('share_class'),
                    'lag_seconds':(qt-usable).total_seconds(),'kind':'first_retained_regular_quote_after_usable_decision','not_a_fill':True}
        anchor=cohort.get('anchor')
        if not anchor:
            cohort['waiting_reason']='post_delivery_or_post_decision_quote_not_observed'; continue
        if not snapshot.get('actions_complete') or snapshot.get('provider_conflict') or snapshot.get('basis')!='split_adjusted':
            cohort['waiting_reason']='comparable_market_history_unavailable'; continue
        if any(not anchor.get(k) or anchor.get(k)!=snapshot.get(k) for k in ('security_id','share_class','currency')):
            cohort['waiting_reason']='research_security_identity_conflict'; continue
        history_observed=timestamp(snapshot.get('history_observed_at'))
        if not history_observed or history_observed>now or not day(snapshot.get('basis_date')) or str(snapshot['basis_date'])>today:
            cohort['waiting_reason']='research_history_observation_not_verified'; continue
        bars={b.get('date'):b for b in snapshot.get('bars',[]) if day(b.get('date')) and b['date']<=today}
        sessions=calendar.sessions(anchor['session_date'],today)
        if not sessions or sessions[0]!=anchor['session_date']:
            cohort['waiting_reason']='research_calendar_coverage_missing'; continue
        factor=Decimal(1)
        for action in snapshot.get('adjustment_events',[]):
            if action.get('kind')=='split' and anchor['session_date']<str(action.get('date',''))<=str(snapshot.get('basis_date','')):
                ratio=number(action.get('ratio'))
                if not ratio or ratio<=0:
                    factor=None; break
                factor*=Decimal(str(ratio))
        if factor is None:
            cohort['waiting_reason']='research_split_history_invalid'; continue
        comparable_anchor=float(Decimal(str(anchor['price']))/factor)
        prior_horizons=set(cohort['outcomes'])
        for horizon in (5,20,60,120):
            if str(horizon) in cohort['outcomes']:
                continue  # Original results remain immutable when later source revisions arrive.
            if len(sessions)<=horizon:
                continue
            target=sessions[horizon]; interval=calendar.session(target)
            if not interval or interval[1]>now or interval[1]>history_observed or target not in bars:
                continue
            close=number(bars[target].get('close')); cost=number(cohort.get('cost_assumption_bps'))
            if close is None or close<=0 or cost is None or not 0<=cost<=10000:
                continue
            cohort['outcomes'][str(horizon)]={'status':'measured_price_return','horizon_sessions':horizon,
                'target_session':target,'endpoint_at':utc(interval[1]),'endpoint_close':close,
                'gross_return_fraction':close/comparable_anchor-1,'net_return_fraction':close/comparable_anchor-1-cost/10000,
                'cost_assumption_bps':cost,'anchor_on_comparable_split_basis':comparable_anchor,
                'basis_date':snapshot.get('basis_date'),'provider':snapshot.get('history_provider'),
                'history_observed_at':snapshot.get('history_observed_at'),'calculated_at':utc(now),
                'benchmark_relative_fraction':None,'benchmark_status':'matching_benchmark_evidence_not_supplied',
                'dividend_treatment':'price return only; excludes dividends; not total return',
                'execution_note':'Hypothetical post-decision reference, not an executable-price guarantee or a trade.'}
        advance_benchmark(cohort,snapshot,calendar,now,new_horizons=set(cohort['outcomes'])-prior_horizons)
        cohort['waiting_reason']='remaining_horizons_or_matching_benchmark_unavailable'
    return research


def summarize(records):
    cohorts=[c for r in records for c in (r.get('research') or {}).get('cohorts',{}).values()]
    return {'schema_version':1,'cohort_count':len(cohorts),
        'anchored_count':sum(c.get('anchor') is not None for c in cohorts),
        'matched_benchmark_horizon_counts':{str(h):sum(str(h) in c.get('benchmark_outcomes',{}) for c in cohorts) for h in (5,20,60,120)},
        'measured_horizon_counts':{str(h):sum(str(h) in c.get('outcomes',{}) for c in cohorts) for h in (5,20,60,120)},
        'notice':'Overlapping cohorts are not independent experiments. Missing outcomes are not zero. No benchmark-adjusted edge is claimed without matched benchmark evidence.',
        'records':[{'opportunity_id':r['opportunity_id'],'ticker':r.get('ticker'),'research':r['research']} for r in records if r.get('research')]}
