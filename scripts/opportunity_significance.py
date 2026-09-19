"""Conservative disclosed-activity qualification over the complete eligible history."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable, Mapping

from dateutil.relativedelta import relativedelta

from .opportunity_common import day, digest, money, timestamp, utc


def amount_range(row: Mapping) -> dict:
    raw = str(row.get('amount') or '')
    if 'amount_lower' in row or 'amount_upper' in row:
        low, high = money(row.get('amount_lower')), money(row.get('amount_upper'))
    else:
        parts = re.findall(r'\d[\d,]*(?:\.\d+)?', raw)
        low = high = None
        if len(parts) == 2 and re.search(r'[-–—]|\bto\b', raw, re.I):
            low, high = map(money, parts)
        elif len(parts) == 1 and re.search(r'over|more than|greater than|\+', raw, re.I):
            low = money(parts[0])
        elif len(parts) == 1 and re.search(r'up to|less than|under', raw, re.I):
            high = money(parts[0])
    if low is not None and high is not None and high < low:
        low = high = None
    return {'lower': str(low) if low is not None else None,
            'upper': str(high) if high is not None else None, 'disclosed': raw}


def aggregate(rows: Iterable[Mapping]) -> dict:
    ranges = [row['amount_range'] for row in rows]
    def total(key):
        values = [money(value[key]) for value in ranges]
        return str(sum(values, Decimal(0))) if all(v is not None for v in values) else None
    return {'lower': total('lower'), 'upper': total('upper')}


def net_interval(buys: list, sales: list) -> dict:
    b, s = aggregate(buys), aggregate(sales)
    def difference(a, z):
        return str(money(a) - money(z)) if a is not None and z is not None else None
    lo, hi = difference(b['lower'], s['upper']), difference(b['upper'], s['lower'])
    # Negative net bounds are signed values, not input monetary amounts.
    return {'lower': lo, 'upper': hi, 'sell_dominated': hi is not None and Decimal(hi) < 0,
            'sign_uncertain': lo is None or hi is None or Decimal(lo) <= 0 <= Decimal(hi),
            'meaning': 'disclosed_activity_only; coverage may be incomplete'}


def identities(row: Mapping) -> tuple[str | None, str | None, list[str]]:
    reasons = []
    filer = next((str(row[k]) for k in ('filer_id', 'bioguide_id', 'reporting_person_id', 'person_id', 'member_id') if row.get(k)), None)
    owner = str(row.get('owner') or '').casefold()
    categories = {'self':'self', 'spouse':'spouse', 'dependent':'dependent', 'dependent child':'dependent', 'joint':'joint'}
    owner_id = str(row.get('owner_id') or '') or (f'{filer}:{categories[owner]}' if filer and owner in categories else None)
    # No name-only household merges or independence claims. Explicit group IDs require evidence.
    group = str(row.get('household_id') or '') if row.get('household_evidence') else None
    if not group and filer and owner in categories:
        group = 'disclosed-household:' + filer
    if not owner_id:
        reasons.append('unresolved_owner_identity')
    if not group:
        reasons.append('unresolved_household_identity')
    if row.get('shared_management_uncertain'):
        reasons.append('shared_management_uncertain')
    return owner_id, group, reasons


def normalize(rows: Iterable[Mapping], cutoff: datetime) -> tuple[list[dict], list[dict]]:
    """Select observed revisions first; never deduplicate by amount/date alone."""
    versions = defaultdict(list)
    excluded = []
    for original in rows:
        row = dict(original)
        observed = timestamp(row.get('observed_at_utc'))
        if observed is None or observed > cutoff:
            excluded.append({'trade_id': row.get('trade_id'), 'reason': 'unobserved_at_cutoff'})
            continue
        tid = str(row.get('canonical_trade_id') or row.get('duplicate_of') or row.get('trade_id') or '')
        if not tid:
            excluded.append({'trade_id': None, 'reason': 'missing_trade_identity'})
            continue
        row['trade_id'] = tid
        versions[tid].append(row)
    selected = {}
    for tid, copies in versions.items():
        copies.sort(key=lambda r: (r['observed_at_utc'], str(r.get('revision', '')), digest(r)))
        row = dict(copies[-1])
        # Two incompatible records at the same revision/time are unresolved, not arbitrary winners.
        semantic = lambda r: {k: r.get(k) for k in ('transaction_date','transaction_type','owner','ticker','amount','amount_lower','amount_upper')}
        peers = [r for r in copies if r['observed_at_utc'] == row['observed_at_utc']]
        row['identity_reasons'] = ['conflicting_trade_copies'] if len({digest(semantic(r)) for r in peers}) > 1 else []
        row['first_observed_at_utc'] = min(r.get('first_observed_at_utc') or r['observed_at_utc'] for r in copies)
        selected[tid] = row
    superseded = set()
    children = defaultdict(list)
    for tid, row in selected.items():
        parents = row.get('supersedes_trade_ids') or ([row['amends_trade_id']] if row.get('amends_trade_id') else [])
        row['supersedes_trade_ids'] = list(parents)
        for parent in parents:
            if parent == tid or parent not in selected or tid in (selected[parent].get('supersedes_trade_ids') or []):
                row['identity_reasons'].append('unresolved_amendment')
            else:
                superseded.add(parent)
                children[parent].append(tid)
    for parent, descendants in children.items():
        if len(descendants) > 1:
            for child in descendants:
                selected[child]['identity_reasons'].append('branching_amendment_chain')
    def visit(tid, path):
        if tid in path:
            for member in path:
                selected[member]['identity_reasons'].append('cyclic_amendment_chain')
                superseded.discard(member)
            return
        for parent in selected[tid].get('supersedes_trade_ids') or []:
            if parent in selected:
                visit(parent, path | {tid})
    for tid in selected:
        visit(tid, set())
    result = []
    for tid, row in sorted(selected.items()):
        if tid in superseded:
            excluded.append({'trade_id': tid, 'reason': 'superseded_amendment'})
            continue
        owner, group, limitations = identities(row)
        security = row.get('security_id')
        security_supported = bool(security and row.get('security_evidence') and row.get('currency') and row.get('share_class'))
        row.update(owner_key=owner, group_key=group, amount_range=amount_range(row))
        row['identity_confidence'] = {'owner':'source_supported' if owner else 'unresolved',
                                      'group':'disclosed_household_link' if group else 'unresolved',
                                      'economic_independence':'not_established'}
        row['security_key'] = str(security) + '|' + str(row.get('share_class')) + '|' + str(row.get('currency')) if security_supported else 'unresolved:' + str(row.get('ticker')) + '|' + str(row.get('share_class'))
        row['identity_reasons'] += limitations
        if not security_supported:
            row['identity_reasons'].append('unresolved_security_identity')
        if not day(row.get('transaction_date')) or day(row['transaction_date']) > cutoff.date():
            row['identity_reasons'].append('invalid_transaction_date')
        if row.get('parse_confidence') not in ('high', 'verified') or row.get('equity_like') is not True:
            row['identity_reasons'].append('required_source_quality')
        if not row.get('source_url'):
            row['identity_reasons'].append('missing_source_evidence')
        result.append(row)
    # Same-looking rows require distinct source line/transaction IDs to count separately.
    lookalikes = defaultdict(list)
    for row in result:
        key = (row['owner_key'], row['security_key'], row.get('transaction_date'), row.get('transaction_type'), digest(row['amount_range']))
        lookalikes[key].append(row)
    for group in lookalikes.values():
        if len(group) < 2:
            continue
        locators = [r.get('source_transaction_id') or (str(r.get('report_id')) + ':' + str(r['source_row']) if r.get('source_row') is not None else None) for r in group]
        if None in locators or len(set(locators)) != len(locators):
            for row in group:
                row['identity_reasons'].append('ambiguous_lookalike_transactions')
    return result, excluded


def significance(rows: list[dict], history: list[dict], rules: Mapping, *, eligible_ids: set[str] | None = None) -> dict:
    reasons, routes = [], []
    buys = [r for r in rows if r.get('transaction_type') == 'Purchase']
    sales = [r for r in rows if str(r.get('transaction_type')).startswith('Sale')]
    supported = [r for r in buys if not r['identity_reasons'] and money(r['amount_range']['lower']) is not None and (eligible_ids is None or r['trade_id'] in eligible_ids)]
    def add(route, group, **detail):
        routes.append({'route': route, 'trade_ids': sorted(r['trade_id'] for r in group),
                       'groups': sorted({r['group_key'] for r in group if r['group_key']}),
                       'amount_range': aggregate(group), **detail})
    for row in supported:
        minimum = money(row['amount_range']['lower'])
        if minimum >= money(rules['material_minimum']):
            add('material_individual', [row])
        txday = day(row['transaction_date'])
        prior = [r for r in history if r.get('transaction_type') == 'Purchase' and r['owner_key'] == row['owner_key'] and r['trade_id'] != row['trade_id'] and not r['identity_reasons'] and day(r.get('transaction_date')) and txday - relativedelta(months=rules['relative_history_months']) <= day(r['transaction_date']) < txday and money(r['amount_range']['upper']) is not None and r.get('currency') == row.get('currency')]
        upper_median = median([money(r['amount_range']['upper']) for r in prior]) if prior else None
        if len(prior) >= rules['relative_history_count'] and minimum >= money(rules['relative_minimum']) and minimum >= money(rules['relative_multiple']) * upper_median:
            add('relative_size', [row], prior_count=len(prior), median_prior_upper=str(upper_median), prior_trade_ids=sorted(r['trade_id'] for r in prior))
    supported.sort(key=lambda r: (r['transaction_date'], r['trade_id']))
    for end in sorted({r['transaction_date'] for r in supported}):
        endday = day(end)
        cluster = [r for r in supported if 0 <= (endday - day(r['transaction_date'])).days <= rules['cluster_days']]
        byowner = defaultdict(list)
        for row in cluster:
            byowner[row['owner_key']].append(row)
        for group in byowner.values():
            if len(group) >= rules['accumulation_count'] and money(aggregate(group)['lower']) >= money(rules['accumulation_minimum']):
                add('repeated_accumulation', group)
        contextual_sales = [r for r in sales if day(r.get('transaction_date')) and 0 <= (endday-day(r['transaction_date'])).days <= rules['context_days']]
        net = net_interval(cluster, contextual_sales)
        if len({r['group_key'] for r in cluster}) >= rules['collective_groups'] and money(aggregate(cluster)['lower']) >= money(rules['collective_minimum']):
            if net['sell_dominated']:
                reasons.append('sell_dominated_collective_activity')
            else:
                add('collective_buying', cluster, net_interval=net)
    routes = sorted({digest(r): r for r in routes}.values(), key=lambda r: (r['route'], r['trade_ids']))
    dates = [day(r.get('transaction_date')) for r in buys if day(r.get('transaction_date'))]
    observed = [timestamp(r['first_observed_at_utc']) for r in buys]
    latest = max(dates) if dates else None
    return {'meaningful': bool(routes), 'routes': routes, 'buy_range': aggregate(buys), 'sale_range': aggregate(sales),
            'net_interval': net_interval(buys, sales), 'opposing_sales': sales,
            'excluded_contributions': [{'trade_id':r['trade_id'], 'reasons':r['identity_reasons'] or ['entry_not_supported' if eligible_ids is not None and r['trade_id'] not in eligible_ids else 'missing_amount']} for r in buys if r not in supported],
            'reason_codes': sorted(set(reasons)), 'transaction_count':len(buys),
            'distinct_supported_groups':len({r['group_key'] for r in supported}),
            'transaction_span_days':(max(dates)-min(dates)).days if dates else None,
            'observation_span_days':(max(observed)-min(observed)).total_seconds()/86400 if observed else None,
            'acceleration_count':sum((latest-d).days <= rules['acceleration_days'] for d in dates) if latest else 0,
            'context_count':sum((latest-d).days <= rules['context_days'] for d in dates) if latest else 0,
            'independence_note':'Distinct disclosed groups; economic independence and complete holdings are not established.'}
