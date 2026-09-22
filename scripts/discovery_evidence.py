"""AI-owned, factual transaction-to-discovery evidence; no signal or person score.

References are market prices, not execution prices. Missing provenance never
becomes an inferred historical quote. The append-only ledger shares the existing
AI restore/validate/commit boundary and makes the report independent of LLM output.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import json
from pathlib import Path
import math

from .opportunity_common import day, number, timestamp, utc, canonical, digest
from .opportunity_market import effective

FIELD = "information_value_at_discovery"
LEDGER = "information-value-at-discovery.jsonl"
VERSION = 1


def finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    return value


def positive(value):
    result = number(value)
    return result if result is not None and result > 0 else None


def derive(row, reference=None, discovery=None, *, previous=None, basis=None):
    """Pure evidence calculation. Retain the first usable quote for THIS trade."""
    first = row.get('first_observed_at_utc') or row.get('observed_at_utc')
    observed, tx = timestamp(first), day(row.get('transaction_date'))
    identity = {k: row.get(k) for k in ('trade_id', 'ticker', 'transaction_date', 'security_id', 'share_class', 'currency')}
    identity['first_observation_at'] = utc(observed) if observed else None
    previous = previous or {}
    same = previous.get('identity') == identity
    if same and previous.get('discovery_quote'):
        discovery = previous['discovery_quote']
    if same and previous.get('transaction_reference'):
        reference = previous['transaction_reference']
    reference, discovery = finite_json(deepcopy(reference)), finite_json(deepcopy(discovery))
    reasons = []
    if not tx:
        reasons.append('missing_transaction_date')
    if not observed:
        reasons.append('missing_first_observation')
    elif tx and tx > observed.date():
        reasons.append('transaction_after_first_observation')
    if row.get('equity_like') is not True and not row.get('security_evidence'):
        reasons.append('exchange_traded_security_not_verified')
    if basis and any(row.get(k) and row[k] != basis.get(k) for k in ('security_id','share_class','currency')):
        reasons.append('transaction_security_or_currency_mismatch')
    rp = positive((reference or {}).get('price'))
    dp = positive((discovery or {}).get('price'))
    if not rp:
        reasons.append('missing_transaction_reference')
    elif (not timestamp(reference.get('at')) or timestamp(reference['at']).date() != tx
          or reference.get('kind') != 'trade_date_close' or not reference.get('provider')):
        reasons.append('transaction_reference_provenance_incomplete')
    quote_at = timestamp((discovery or {}).get('at'))
    seen_at = timestamp((discovery or {}).get('observed_at'))
    if not dp:
        reasons.append('missing_first_usable_discovery_quote')
    elif (not observed or not quote_at or not seen_at or quote_at < observed or seen_at < quote_at
          or discovery.get('kind') != 'first_usable_quote_after_discovery'
          or not discovery.get('provider') or discovery.get('quality') != 'usable'):
        reasons.append('discovery_quote_provenance_incomplete')
    atr = None
    comparison = None
    if rp and dp:
        if basis and basis.get('actions_complete') is True and basis.get('provider_conflict') is False:
            try:
                rp, atr = effective(reference, basis)
                dp, _ = effective(discovery, basis)
                atr = positive(atr)
                comparison = {k: basis.get(k) for k in ('security_id','share_class','currency','basis','basis_date')}
            except Exception:
                reasons.append('incompatible_reference_and_quote_basis')
        elif same and previous.get('status') == 'measured' and not reasons:
            # The historical comparison is already attested. Current conditions
            # cannot replace it or invalidate an earlier supported observation.
            return deepcopy(previous)
        else:
            reasons.append('price_basis_or_corporate_actions_unverified')
    status = 'unknown' if reasons else 'measured'
    delta = dp - rp if status == 'measured' else None
    percent = number(delta / rp * 100) if delta is not None else None
    atr_move = number(delta / atr) if delta is not None and atr else None
    if status == 'measured' and percent is None:
        status = 'unknown'
        reasons.append('nonfinite_movement')
    return {'schema_version': VERSION, 'identity': identity, 'status': status,
            'reason': reasons[0] if reasons else 'supported_transaction_and_discovery_references',
            'reason_codes': sorted(set(reasons)),
            'transaction_reference': reference, 'discovery_quote': discovery,
            'comparison_basis': comparison,
            'disclosure_lag_days': (observed.date()-tx).days if tx and observed and tx <= observed.date() else None,
            'disclosure_lag_basis': 'transaction_date_to_first_observation_UTC_calendar_days',
            'discovery_quote_lag_seconds': (quote_at-observed).total_seconds() if quote_at and observed and quote_at >= observed else None,
            'transaction_to_discovery_percent': percent if status == 'measured' else None,
            'transaction_to_discovery_atr': atr_move if status == 'measured' else None,
            'atr': deepcopy((reference or {}).get('atr')),
            'atr_status': 'available' if atr else 'unknown',
            'atr_reason': 'transaction_reference_atr' if atr else 'missing_comparable_transaction_atr',
            'notice': 'Market reference, not execution price; observation lag does not establish filing timeliness. No investment recommendation.'}


def opportunity_values(rows, prior, market, snapshot, now, rules, calendar):
    from .opportunity_market import anchor, quote_quality, completed_bars, measured_atr
    from .opportunity_common import DataUnavailable
    values = {}
    quote = snapshot.get('quote') or {}
    quality = quote_quality(snapshot, now, rules, calendar)
    for row in rows:
        tid = row['trade_id']
        old = (prior or {}).get(tid) or {}
        discovery = old.get('discovery_quote')
        if not discovery:
            retained = (market.get('anchors') or {}).get('discovery') or {}
            first, at = timestamp(row.get('first_observed_at_utc')), timestamp(retained.get('at'))
            if (first and at and at >= first and retained.get('kind') == 'first_usable_quote_after_discovery'
                    and retained.get('status') == 'observed' and retained.get('provider')):
                # Original Current Opportunity anchors were admitted only after
                # quote_quality passed; retain them during this additive upgrade.
                discovery = {**deepcopy(retained), 'quality':'usable', 'quote_kind':'realtime', 'feed_delay_seconds':0}
        if not discovery:
            first, at = timestamp(row.get('first_observed_at_utc')), timestamp(quote.get('at'))
            if not quality and first and at and at >= first:
                discovery = anchor(quote['price'], quote['at'], snapshot,
                    kind='first_usable_quote_after_discovery', atr=None, observed_at=quote['observed_at'])
                discovery.update(quality='usable', quote_kind=quote.get('kind'),
                                 feed_delay_seconds=quote.get('feed_delay_seconds'))
        reference = ((market.get('anchors') or {}).get('trades') or {}).get(tid)
        # Sales have factual disclosure evidence too; they are not entry signals.
        if not reference:
            try:
                bars = completed_bars(snapshot, now, calendar)
            except DataUnavailable:
                bars = []
            bar = next((b for b in bars if b['date'] == row.get('transaction_date')), None)
            if bar:
                reference = anchor(bar['close'], bar['at'], snapshot, kind='trade_date_close',
                    atr=measured_atr(bars, timestamp(bar['at']), rules['atr_sessions'], calendar), observed_at=utc(now))
        values[tid] = derive(row, reference, discovery, previous=old, basis=snapshot)
    return values


def load(directory):
    path = Path(directory) / LEDGER
    values = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                record = json.loads(line)
                value = record[FIELD]
                if value.get('schema_version') != VERSION or value.get('status') not in ('unknown','measured'):
                    raise ValueError('invalid_discovery_evidence_ledger')
                if record.get('evidence_sha256') != digest(value) or value.get('identity',{}).get('trade_id') != record['trade_id']:
                    raise ValueError('discovery_evidence_integrity_failure')
                values[record['trade_id']] = value
    return values


def persist(directory, transactions, analyses, *, opportunities=None):
    """Reuse retained evidence with no API calls and no changes to analysis history."""
    prior = load(directory)
    rows = {}
    for row in transactions:
        tid = row.get('trade_id')
        if tid and (row.get('equity_like') is True or row.get('security_evidence') or tid in prior):
            old = rows.get(tid)
            if old is None or (timestamp(row.get('observed_at_utc')) and
                    (not timestamp(old.get('observed_at_utc')) or timestamp(row['observed_at_utc']) < timestamp(old['observed_at_utc']))):
                rows[tid] = row
    retained = {}
    for analysis in sorted(analyses, key=lambda a: a.get('analyzed_at_utc') or ''):
        retained.setdefault(analysis.get('trade_id'), []).append(analysis)
    from_opportunity = {}
    for record in (opportunities or {}).values():
        from_opportunity.update(record.get(FIELD) or {})
    changes = []
    for tid, row in sorted(rows.items()):
        value = prior.get(tid)
        candidate = from_opportunity.get(tid)
        if candidate and (not value or value.get('status') != 'measured'):
            value = candidate
        identity_changed = bool(value and any(value.get('identity',{}).get(k) != row.get(k)
                                for k in ('ticker','transaction_date','security_id','share_class','currency')))
        if value is None or value.get('status') != 'measured' or identity_changed or not (row.get('equity_like') is True or row.get('security_evidence')):
            value = derive(row, previous=value)
            # Retain original evidence, including incomplete provenance. Legacy
            # provider aggregates do not prove quote quality or split basis.
            evidence = retained.get(tid) or []
            first_market = next((a for a in evidence if positive((a.get('market') or {}).get('current_price'))), None)
            if first_market:
                m = first_market['market']
                value['retained_market_evidence'] = {
                    'analysis_id': first_market.get('analysis_id'), 'analyzed_at_utc': first_market.get('analyzed_at_utc'),
                    'ticker': first_market.get('ticker') or m.get('ticker'),
                    **{k:finite_json(m.get(k)) for k in ('transaction_date_close','current_price','quote_timestamp_utc','providers','data_status','atr_14')}}
                value['reason_codes'] = sorted(set(value['reason_codes'] + ['legacy_market_quote_quality_and_basis_unverified']))
        if value != prior.get(tid):
            changes.append({'trade_id':tid, FIELD:value, 'evidence_sha256':digest(value)})
            prior[tid] = value
    if changes:
        with (Path(directory)/LEDGER).open('a', encoding='utf-8', newline='\n') as stream:
            for value in changes:
                stream.write(canonical(value)+'\n')
    return prior


def attach(analyses, values):
    return [{**row, FIELD:deepcopy(values.get(row.get('trade_id')) or derive(row))} for row in analyses]


def write_exports(values, output):
    output = Path(output)
    rows = [{'trade_id':tid, FIELD:value} for tid,value in sorted(values.items())]
    (output/'information-value-at-discovery.json').write_text(canonical({'schema_version':VERSION,'records':rows})+'\n', encoding='utf-8')
    fields = ['trade_id','ticker','transaction_date','first_observation_at','status','reason',
              'disclosure_lag_days','discovery_quote_lag_seconds','transaction_to_discovery_percent',
              'transaction_to_discovery_atr','atr_status',FIELD]
    with (output/'information-value-at-discovery.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for item in rows:
            value=item[FIELD]
            row={key:value.get(key) for key in fields}
            row.update(value['identity']); row['trade_id']=item['trade_id']; row[FIELD]=canonical(value)
            writer.writerow({k:("'"+v if isinstance(v,str) and v[:1] in ('=','+','-','@','\t','\r') else v) for k,v in row.items() if k in fields})
