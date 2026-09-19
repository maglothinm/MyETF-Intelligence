"""Deterministic ticker-level lifecycle. Optional context cannot influence gates."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Mapping

from .opportunity_common import DataUnavailable, day, digest, money, timestamp, utc
from .opportunity_market import assess
from .opportunity_significance import normalize, significance
from .opportunity_state import event


def evidence_status(evidence: Mapping, now: datetime, rules: Mapping, membership_hash: str) -> tuple[str, list[str]]:
    checked, valid = timestamp(evidence.get('checked_at')), timestamp(evidence.get('valid_until'))
    reasons = []
    if not checked or not valid or checked > now or now > valid or (now-checked).total_seconds() > rules['evidence_max_hours']*3600:
        reasons.append('stale_or_missing_evidence_review')
    coverage = evidence.get('coverage') or {}
    if not all(coverage.get(k) is True for k in ('disclosures','issuer','parser')):
        reasons.append('incomplete_contradiction_checks')
    if evidence.get('membership_hash') != membership_hash:
        reasons.append('evidence_predates_membership_change')
    sources = evidence.get('sources') or []
    if not sources or any(not (s.get('url') or s.get('id')) or not timestamp(s.get('observed_at')) or timestamp(s['observed_at']) > now for s in sources):
        reasons.append('missing_evidence_provenance')
    if evidence.get('status') == 'contradicted' and evidence.get('contradictions') and not reasons:
        return 'contradicted', ['identified_contradictory_evidence']
    if evidence.get('status') != 'sufficient' or evidence.get('contradictions'):
        reasons.append('unresolved_contradictory_evidence')
    return ('incomplete', sorted(set(reasons))) if reasons else ('sufficient', [])


def membership(rows: list[dict]) -> str:
    fields = ('trade_id','transaction_type','transaction_date','amount_range','owner_key','group_key','security_key','identity_reasons','supersedes_trade_ids')
    return digest([{k:r.get(k) for k in fields} for r in sorted(rows, key=lambda r:r['trade_id'])])


def _intent(state: dict, record: dict, transition: str, channels: list[str], now: datetime) -> None:
    serial = sum(i['opportunity_id'] == record['opportunity_id'] for i in state['intents'].values())+1
    eid = digest({'opportunity_id':record['opportunity_id'], 'transition':transition, 'serial':serial})
    payload = {'event_id':eid, 'opportunity_id':record['opportunity_id'], 'transition':transition,
               'evaluation_id':record['evaluation_id'], 'queued_at':utc(now), 'mode':state['mode'],
               'notification_type':'current_opportunity', 'channels':sorted(set(channels)), 'snapshot':deepcopy(record)}
    state['intents'][eid] = payload
    state['deliveries'][eid] = {c:{'status':'pending', 'attempts':0} for c in payload['channels']}
    event(state, 'notification_intent', payload, now)


def evaluate(state: dict, rows: list[dict], history: list[dict], snapshot: Mapping, evidence: Mapping,
             rules: Mapping, now: datetime, calendar, *, channels: list[str], input_cutoff: datetime) -> dict:
    security = rows[0]['security_key']
    oid = 'opportunity-' + digest({'security':security, 'direction':'long'})[:32]
    previous = state['opportunities'].get(oid) or {}
    mh = membership(rows)
    full = significance(rows, history, rules)
    buys = [r for r in rows if r.get('transaction_type') == 'Purchase']
    try:
        market = assess(buys, previous.get('anchors') or {}, snapshot, now, rules, calendar)
    except DataUnavailable as exc:
        market = {'anchors':deepcopy(previous.get('anchors') or {}), 'metrics':{}, 'eligible_trade_ids':[],
                  'discovery_near':False, 'reason_codes':[str(exc)], 'path':'insufficient_data', 'quote':{}, 'session':'unknown', 'timeline':{}}
    # Preserve observed excursions across evaluations; a later cache cannot erase them.
    for tid, metric in market['metrics'].items():
        old = ((previous.get('market') or {}).get('metrics') or {}).get(tid) or {}
        if 'max_up_fraction' in metric:
            metric['max_up_fraction'] = max(metric['max_up_fraction'], old.get('max_up_fraction', metric['max_up_fraction']))
            metric['max_down_fraction'] = min(metric['max_down_fraction'], old.get('max_down_fraction', metric['max_down_fraction']))
            if metric['near'] and old.get('path') in ('already_moved','material_decline','returned_to_range'):
                metric['path'] = 'returned_to_range'
    filtered = significance(rows, history, rules, eligible_ids=set(market['eligible_trade_ids']))
    contributors = sorted({t for route in filtered['routes'] for t in route['trade_ids']})
    contributing_paths = {(market['metrics'].get(t) or {}).get('path') for t in contributors}
    path = 'returned_to_range' if 'returned_to_range' in contributing_paths else market['path']
    market['path'] = path
    evstatus, evreasons = evidence_status(evidence, now, rules, mh)
    data_ids = {tid for tid,m in market['metrics'].items() if not m.get('reason_codes') and m.get('path') != 'insufficient_data'}
    data_ok = not market['reason_codes'] and significance(rows, history, rules, eligible_ids=data_ids)['meaningful']
    entry = filtered['meaningful'] and market['discovery_near']
    reasons = full['reason_codes'] + market['reason_codes'] + evreasons
    if not full['meaningful']:
        reasons.append('meaningful_buying_not_established')
    if not filtered['meaningful']:
        reasons.append('insufficient_buying_at_acceptable_entry')
    if not market['discovery_near']:
        reasons.append('discovery_movement_gate_failed')
    returned_at = previous.get('return_started_at')
    confirmations = list(previous.get('return_observations') or [])
    was_out = previous.get('was_out_of_range', False)
    last_out_at = previous.get('last_out_of_range_at')
    if not entry and data_ok and market['path'] in ('already_moved','material_decline'):
        last_out_at = utc(now)
    quote = market.get('quote') or {}
    qid = digest({k:quote.get(k) for k in ('at','provider','price')}) if quote.get('at') else None
    returned = path == 'returned_to_range' or (was_out and entry)
    if entry and returned:
        returned_at = returned_at or utc(now)
        if data_ok and evstatus == 'sufficient' and timestamp(evidence['checked_at']) >= timestamp(returned_at) and evidence.get('return_review_cleared') is True:
            if qid and qid not in confirmations:
                confirmations.append(qid)
        else:
            reasons.append('returned_price_requires_fresh_evidence_review')
        if len(confirmations) < rules['reentry_observations']:
            reasons.append('reentry_confirmation_pending')
            entry = False
    elif not entry:
        returned_at, confirmations = None, []
        was_out = was_out or (full['meaningful'] and market['path'] in ('already_moved','material_decline'))
    if market['path'] == 'material_decline':
        reasons.append('material_decline_requires_review')
    if evstatus == 'contradicted':
        lifecycle = 'invalidated'
    elif not full['meaningful'] or evstatus != 'sufficient' or (not data_ok and market['reason_codes'] != ['market_closed']) or 'sell_dominated_collective_activity' in reasons or market['path'] == 'material_decline':
        lifecycle = 'needs_review'
    elif not entry or market['session'] != 'regular':
        lifecycle = 'watching'
    else:
        lifecycle = 'opportunity_available'
    observed = {r['trade_id']:r['first_observed_at_utc'] for r in buys}
    qualifying_discoveries = [max(observed[tid] for tid in route['trade_ids']) for route in full['routes']]
    first_discovery = previous.get('first_qualifying_discovery') or (min(qualifying_discoveries) if qualifying_discoveries else None)
    horizon = timestamp(previous.get('monitoring_until')) or (timestamp(first_discovery)+timedelta(days=rules['monitoring_days']) if first_discovery else None)
    administration = None
    if horizon and now >= horizon:
        extension = timestamp(evidence.get('monitoring_extension_until'))
        if extension and extension > now and evstatus == 'sufficient':
            horizon, administration = extension, 'monitoring_extended'
        else:
            lifecycle, administration = 'archived', 'administrative_monitoring_horizon'
            reasons.append(administration)
    if previous.get('lifecycle') == 'archived' and mh == previous.get('membership_hash') and not administration == 'monitoring_extended':
        lifecycle = 'archived'
        reasons.append('administrative_archive_retained')
    activation = state.get('activation')
    baseline = previous.get('activation_baseline', False)
    if activation and (not previous.get('activation_id') or previous.get('activation_id') != activation['activation_id']):
        baseline = all(timestamp(r['first_observed_at_utc']) <= timestamp(activation['cutoff']) for r in buys)
    available = lifecycle == 'opportunity_available'
    previous_available = previous.get('lifecycle') == 'opportunity_available'
    method_changed = previous and previous.get('rule_hash') != rules['method_hash']
    new_material = bool(previous) and any(r['trade_id'] in contributors and r['trade_id'] not in previous.get('trade_ids', []) and not r.get('supersedes_trade_ids') and money(r['amount_range']['lower']) is not None and money(r['amount_range']['lower']) >= money(rules['relative_minimum']) and (not activation or timestamp(r['first_observed_at_utc']) > timestamp(activation['cutoff'])) for r in buys)
    supported_sources = {str(source.get('url') or source.get('id')) for source in evidence.get('sources', [])}
    strengthening_sources = evidence.get('strengthening_sources') or []
    evidence_strengthened = bool(evidence.get('strengthening_id') and evidence.get('strengthening_id') != (previous.get('evidence') or {}).get('strengthening_id') and strengthening_sources and all(isinstance(source,str) and source in supported_sources for source in strengthening_sources))
    transition = None
    accepted_times = [timestamp(d.get('accepted_at') or d.get('attempted_at'))
                      for eid in previous.get('notification_event_ids', [])
                      for d in state['deliveries'].get(eid, {}).values()
                      if d.get('status') in ('accepted', 'uncertain')]
    # Cooldown starts at actual (or possibly accepted) submission, not queue time.
    last_alert = max((t for t in accepted_times if t), default=None)
    cooldown = not last_alert or (now-last_alert).total_seconds() >= rules['reentry_cooldown_minutes']*60
    previously_alerted = bool(previous.get('notification_event_ids'))
    return_announced = any(i['opportunity_id'] == oid and i['transition'] == 'qualified_reentry'
                           and i['snapshot'].get('return_started_at') == returned_at for i in state['intents'].values())
    post_activation_return = bool(activation and returned and timestamp(returned_at) and timestamp(last_out_at)
                                  and timestamp(last_out_at) >= timestamp(activation['cutoff'])
                                  and timestamp(returned_at) > timestamp(activation['cutoff']))
    if available and not method_changed and (not baseline or new_material or evidence_strengthened or post_activation_return):
        if not previously_alerted:
            transition = 'qualified_reentry' if returned else 'first_qualification'
        elif returned and cooldown and not return_announced:
            transition = 'qualified_reentry'
        elif new_material or evidence_strengthened:
            transition = 'material_strengthening'
    elif lifecycle == 'invalidated' and previous.get('lifecycle') != 'invalidated' and any(d.get('status') == 'accepted' for eid in previous.get('notification_event_ids', []) for d in state['deliveries'].get(eid, {}).values()):
        transition = 'invalidation'
    if transition == 'qualified_reentry' and not cooldown:
        transition = None
    ids = list(previous.get('notification_event_ids') or [])
    if transition:
        serial = sum(i['opportunity_id'] == oid for i in state['intents'].values())+1
        ids.append(digest({'opportunity_id':oid, 'transition':transition, 'serial':serial}))
    record = {'opportunity_id':oid, 'security_key':security, 'security_id':rows[0].get('security_id'),
              'ticker':rows[0].get('ticker'), 'issuer':rows[0].get('asset'), 'currency':rows[0].get('currency'), 'share_class':rows[0].get('share_class'),
              'symbol_history':sorted(set(previous.get('symbol_history', [])+[r['ticker'] for r in rows if r.get('ticker')])),
              'direction':'long', 'trade_ids':sorted(r['trade_id'] for r in rows), 'membership_hash':mh,
              'membership_history':previous.get('membership_history', []) + ([{'at':utc(now), 'hash':mh, 'trade_ids':sorted(r['trade_id'] for r in rows)}] if mh != previous.get('membership_hash') else []),
              'transactions':deepcopy(rows), 'significance':full, 'entry_significance':filtered,
              'transaction_age_days':{r['trade_id']:(now.date()-day(r['transaction_date'])).days if day(r.get('transaction_date')) else None for r in rows},
              'evidence_age_seconds':(now-timestamp(evidence['checked_at'])).total_seconds() if timestamp(evidence.get('checked_at')) else None,
              'anchors':market['anchors'], 'market':market, 'evidence':dict(evidence), 'evidence_status':evstatus,
              'lifecycle':lifecycle, 'reason_codes':sorted(set(reasons)),
              'gates':{'meaningful_buying':full['meaningful'], 'acceptable_current_entry':bool(entry), 'sufficient_current_evidence':evstatus == 'sufficient', 'trustworthy_required_data':data_ok},
              'evaluation_cutoff':utc(now), 'input_cutoff':utc(input_cutoff), 'last_attempted_review':utc(now),
              'last_successful_review':utc(now) if data_ok and evstatus == 'sufficient' else previous.get('last_successful_review'),
              'next_review':utc(now+timedelta(minutes=rules['review_minutes'])), 'rule_hash':rules['method_hash'],
              'first_qualifying_discovery':first_discovery, 'monitoring_until':utc(horizon) if horizon else None,
              'administrative_decision':administration, 'activation_id':activation['activation_id'] if activation else None,
              'activation_baseline':baseline, 'was_out_of_range':was_out, 'last_out_of_range_at':last_out_at, 'return_started_at':returned_at,
              'return_observations':confirmations[-rules['reentry_observations']:], 'notification_event_ids':ids,
              'last_alert_at':utc(last_alert) if last_alert else None,
              'mode':state['mode'], 'context_only_investor_edge':True}
    quote_time = timestamp(quote.get('at'))
    valid_times = [quote_time+timedelta(seconds=rules['quote_max_seconds'])] if quote_time else []
    if timestamp(evidence.get('valid_until')):
        valid_times.append(timestamp(evidence['valid_until']))
    interval = calendar.session(now.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat())
    if interval:
        valid_times.append(interval[1])
    record['display_valid_until'] = utc(min(valid_times)) if valid_times else utc(now)
    record['evaluation_id'] = event(state, 'evaluation', record, now)
    state['opportunities'][oid] = record
    if transition:
        _intent(state, record, transition, channels, now)
    return record


def cycle(state: dict, raw_rows: list[dict], rules: Mapping, clock, calendar, market_provider, evidence_provider,
          *, channels: list[str], activation: dict | None = None) -> dict:
    input_cutoff = clock()
    if rules['mode'] == 'off':
        return state
    state['mode'] = rules['mode']
    if activation and state['activation'] != activation:
        event(state, 'activation_baseline', activation, input_cutoff)
        state['activation'] = deepcopy(activation)
    history, excluded = normalize(raw_rows, input_cutoff)
    grouped = defaultdict(list)
    for row in history:
        grouped[row['security_key']].append(row)
    due = []
    for key, rows in grouped.items():
        if not any(r.get('transaction_type') == 'Purchase' for r in rows):
            continue
        oid = 'opportunity-'+digest({'security':key, 'direction':'long'})[:32]
        prior = state['opportunities'].get(oid) or {}
        if not prior or membership(rows) != prior.get('membership_hash') or not timestamp(prior.get('next_review')) or timestamp(prior['next_review']) <= input_cutoff or prior.get('rule_hash') != rules['method_hash'] or (activation and prior.get('activation_id') != activation['activation_id']):
            due.append((prior.get('last_attempted_review') or '', key, rows))
    # Oldest-attempt first plus durable cyclic tie-break prevents repeated budget starvation.
    cursor = state.get('cursor') or ''
    archived_keys = {p['security_key'] for p in state['opportunities'].values() if p['lifecycle'] == 'archived'}
    due.sort(key=lambda item:(item[1] in archived_keys, item[0], item[1] <= cursor, item[1]))
    attempted = 0
    for _, key, rows in due[:rules['security_budget']]:
        try:
            snapshot = market_provider.snapshot(rows, input_cutoff)
        except DataUnavailable as exc:
            snapshot = {'gap':str(exc)}
        review_time = clock()
        mh = membership(rows)
        try:
            oid = 'opportunity-'+digest({'security':key, 'direction':'long'})[:32]
            evidence = evidence_provider.review(rows, mh, review_time, force=bool((state['opportunities'].get(oid) or {}).get('was_out_of_range')))
        except DataUnavailable as exc:
            evidence = {'status':'incomplete', 'reason':str(exc)}
        evaluate(state, rows, history, snapshot, evidence, rules, clock(), calendar, channels=channels, input_cutoff=input_cutoff)
        # Advance even when the whole due set fits: otherwise a smaller model
        # budget would repeatedly service the same first securities forever.
        if attempted == 0:
            state['cursor'] = key
        attempted += 1
    now = clock()
    missed = {key for _,key,_ in due[attempted:]}
    # A failed or budget-skipped refresh must not preserve a current badge.
    for oid, prior in list(state['opportunities'].items()):
        removed = prior['security_key'] not in grouped
        if removed or prior['security_key'] in missed or (prior.get('lifecycle') == 'opportunity_available' and timestamp(prior.get('display_valid_until')) and now > timestamp(prior['display_valid_until'])):
            record = deepcopy(prior)
            record.pop('evaluation_id')
            record['lifecycle'] = 'needs_review'
            record['gates']['trustworthy_required_data'] = False
            record['reason_codes'] = sorted(set(record['reason_codes']+['membership_removed_or_superseded' if removed else 'review_budget_exhausted' if prior['security_key'] in missed else 'stale_quote_or_evidence']))
            record['evaluation_cutoff'] = utc(now)
            record['evaluation_id'] = event(state, 'evaluation', record, now)
            state['opportunities'][oid] = record
    overdue_times = [timestamp(p.get('last_successful_review') or p.get('first_qualifying_discovery') or p['evaluation_cutoff'])
                     for p in state['opportunities'].values() if p['security_key'] in missed or p.get('last_successful_review') != p.get('evaluation_cutoff')]
    overdue_times += [min(timestamp(r['first_observed_at_utc']) for r in rows) for _, key, rows in due[attempted:]]
    oldest = min(overdue_times, default=now)
    state['telemetry'] = {'input_cutoff':utc(input_cutoff), 'finished_at':utc(now), 'due_count':len(due), 'attempted_count':attempted,
                          'overdue_count':len(missed), 'budget_exhausted':bool(missed), 'oldest_unreviewed_hours':max(0,(now-oldest).total_seconds()/3600),
                          'starvation_warning':(now-oldest).total_seconds() >= rules['starvation_hours']*3600,
                          'excluded_transactions':excluded, 'reason_counts':dict(Counter(r for p in state['opportunities'].values() for r in p['reason_codes']))}
    return state
