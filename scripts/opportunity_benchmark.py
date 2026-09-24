"""Matched benchmark measurements; no backdated anchors or revised original outcomes."""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from .opportunity_common import day,digest,number,timestamp,utc


def advance_benchmark(cohort,snapshot,calendar,now,*,new_horizons=()):
    results=cohort.setdefault('benchmark_outcomes',{})
    b=snapshot.get('benchmark') or {};anchor=cohort.get('anchor');usable=timestamp(cohort.get('decision_usable_at'))
    if b.get('status')!='available' or not anchor or not usable:
        cohort['benchmark_waiting_reason']=b.get('reason','matching_benchmark_evidence_not_supplied');return
    if b.get('basis')!='split_adjusted' or b.get('actions_complete') is not True or b.get('provider_conflict') or b.get('currency')!=anchor.get('currency'):
        cohort['benchmark_waiting_reason']='benchmark_price_basis_or_currency_unverified';return
    if not all(b.get(k) for k in ('symbol','security_id','share_class','currency')):
        cohort['benchmark_waiting_reason']='benchmark_identity_unverified';return
    q=b.get('quote') or {};qt=timestamp(q.get('at'));observed=timestamp(q.get('observed_at'));price=number(q.get('price'))
    own_at=timestamp(anchor['at']);session=calendar.session(anchor['session_date'])
    if not cohort.get('benchmark_anchor'):
        eligible=bool(qt and observed and own_at and session and qt>usable and qt<=observed<=now
            and (now-observed).total_seconds()<=300 and (observed-qt).total_seconds()<=300
            and abs((qt-own_at).total_seconds())<=120 and session[0]<=qt<=session[1]
            and q.get('kind')=='realtime' and q.get('feed_delay_seconds')==0 and price and price>0)
        if not eligible:
            cohort['benchmark_waiting_reason']='matched_post_decision_benchmark_quote_not_observed';return
        cohort['benchmark_anchor']={k:b[k] for k in ('symbol','security_id','share_class','currency')}
        cohort['benchmark_anchor'].update(price=price,at=q['at'],observed_at=q['observed_at'],provider=q.get('provider'),
            basis_date=b.get('basis_date'),session_date=anchor['session_date'],
            timestamp_difference_seconds=(qt-own_at).total_seconds(),maximum_matching_skew_seconds=120,
            kind='retained_quote_matched_to_asset_anchor; not a fill')
    ba=cohort['benchmark_anchor']
    if any(ba[k]!=b.get(k) for k in ('symbol','security_id','share_class','currency')):
        cohort['benchmark_waiting_reason']='benchmark_identity_changed';return
    today=now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    history_at=timestamp(b.get('history_observed_at'))
    if not history_at or history_at>now or not day(b.get('basis_date')) or b['basis_date']>today:
        cohort['benchmark_waiting_reason']='benchmark_history_observation_unverified';return
    factor=Decimal(1)
    for action in b.get('adjustment_events',[]):
        if action.get('kind')=='split' and ba['session_date']<str(action.get('date',''))<=b['basis_date']:
            ratio=number(action.get('ratio'))
            if not ratio or ratio<=0:
                cohort['benchmark_waiting_reason']='benchmark_split_history_invalid';return
            factor*=Decimal(str(ratio))
    comparable=float(Decimal(str(ba['price']))/factor)
    bars={v.get('date'):v for v in b.get('bars',[]) if day(v.get('date'))}
    for horizon,own in cohort['outcomes'].items():
        if horizon in results:continue
        target=own['target_session'];end=calendar.session(target)
        history_scope=b.get('history_session_scope','regular')
        if own.get('history_session_scope','regular') != history_scope:
            cohort['benchmark_waiting_reason']='benchmark_session_scope_mismatch';continue
        endpoint=end[1] if end else None
        if history_scope == 'provider_daily_aggregate_not_verified_regular_only':
            endpoint=datetime.combine(day(target)+timedelta(days=1),datetime.min.time(),ZoneInfo('America/New_York'))
        close=number((bars.get(target) or {}).get('close'));cost=number(cohort.get('cost_assumption_bps'))
        if not endpoint or endpoint>now or endpoint>history_at or not close or close<=0 or cost is None or not 0<=cost<=10000:continue
        gross=close/comparable-1;net=gross-cost/10000
        results[horizon]={'status':'measured_matched_price_excess','symbol':ba['symbol'],
            'target_session':target,'endpoint_at':utc(endpoint),'endpoint_close':close,'history_session_scope':history_scope,'gross_return_fraction':gross,
            'net_return_fraction':net,'benchmark_relative_fraction':own['net_return_fraction']-net,
            'cost_assumption_bps':cost,'source_asset_outcome_sha256':digest(own),
            'calculated_at':utc(now),'history_observed_at':b['history_observed_at'],'provider':b.get('history_provider'),
            'basis_date':b['basis_date'],'anchor_on_comparable_split_basis':comparable,
            'notice':'Matched-session price-return comparison; excludes dividends on both legs, uses the same assumed cost, and is not risk-adjusted alpha or proof of an investment edge.'}
        # Only fill the primary result while it is being created in this evaluation.
        # Later benchmark evidence appends a linked measurement without rewriting it.
        if horizon in new_horizons:
            own['benchmark_relative_fraction']=results[horizon]['benchmark_relative_fraction']
            own['benchmark_status']='measured_in_linked_benchmark_outcome'
            results[horizon]['source_asset_outcome_sha256']=digest(own)
    cohort['benchmark_waiting_reason']='remaining_horizons_or_matching_history_unavailable'
