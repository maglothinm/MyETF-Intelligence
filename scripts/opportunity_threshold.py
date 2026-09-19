"""Per-purchase historical threshold observations, never a qualification gate.

A negative result needs complete coverage. A positive observation is retained
across gaps/restarts. References are immutable trade-date closes, not fills;
purchase-day ordering and extended-hours prices are explicitly outside scope.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Mapping
from zoneinfo import ZoneInfo

from .opportunity_common import DataUnavailable, day, digest, number, timestamp, utc
from .opportunity_market import completed_bars, effective

VERSION = 1
DEFAULT_FRACTION = 0.08
NOTICE = ('Split-only price change after the purchase-date closing reference, not '
          'the filer\'s execution price. Purchase-day ordering and extended hours '
          'are not covered. No crossing is not a forecast or a buy recommendation.')


def _identity(row: Mapping) -> dict:
    return {k: row.get(k) for k in ('trade_id', 'transaction_date', 'security_id', 'share_class', 'currency')}


def _next_open(now: datetime, calendar) -> str | None:
    today = now.astimezone(ZoneInfo('America/New_York')).date()
    for date_value in calendar.sessions(today.isoformat(), (today + timedelta(days=14)).isoformat()):
        interval = calendar.session(date_value)
        if interval[0] > now:
            return utc(interval[0])
    return None


def _point(gain: float, price: float, date_value: str, *, at: str | None,
           source: str, precision: str, observed_at: str, basis_date: str) -> dict:
    return {'gain_fraction': gain, 'price': price, 'session_date': date_value,
            'at': at, 'precision': precision, 'provider': source,
            'first_observed_at': observed_at, 'basis_date': basis_date}


def _crosses(gain: float | None, fraction: float) -> bool:
    return gain is not None and gain + 1e-12 >= fraction


def _point_order(point: Mapping) -> tuple:
    # Session-only evidence cannot establish a first intraday crossing time.
    return (point.get('session_date') or '', point.get('at') or '', point.get('first_observed_at') or '')


def assess_purchase(row: Mapping, reference: Mapping | None, previous: Mapping,
                    snapshot: Mapping, now: datetime, fraction: float, calendar, *, quote_max_seconds: int = 300) -> dict:
    """Return an additive record; never rewrite the anchor or prior observations."""
    now_text = utc(now)
    identity = _identity(row)
    old = deepcopy(dict(previous))
    result = {**old, 'trade_id': row['trade_id'], 'identity': identity, 'active': True,
              'threshold_fraction': fraction, 'evaluated_at': now_text, 'status': 'unknown',
              'reason_codes': [], 'coverage_complete': False, 'valid_until': now_text,
              'coverage_through': None, 'completed_sessions_through': None,
              'expected_sessions': 0, 'observed_sessions': 0, 'missing_sessions': [],
              'purchase_day_ordering': 'unknown_excluded', 'session_scope': 'regular',
              'reference_kind': 'trade_date_close', 'current_session_coverage': 'not_required',
              'current_reference_price': None, 'peak_gain_fraction': old.get('peak_gain_fraction'),
              'peak_observation': old.get('peak_observation'), 'crossings': old.get('crossings', {}),
              'crossing': None, 'ever_crossed': None}
    # A date/security correction is review work, not permission to reset a purchase.
    if old and old.get('identity') != identity:
        result['original_identity'] = old.get('original_identity') or old['identity']
        result['identity'] = old['identity']
        result['requested_identity'] = identity
        result['reason_codes'] = ['purchase_reference_correction_requires_review']
        return result
    result.pop('requested_identity', None)
    ref = deepcopy(dict(reference or old.get('reference') or {}))
    if not ref or ref.get('kind') != 'trade_date_close' or not timestamp(ref.get('at')):
        result['reason_codes'] = ['missing_purchase_reference']
        return result
    if (ref['at'][:10] != row.get('transaction_date') or
            any(ref.get(k) != row.get(k) for k in ('security_id', 'share_class', 'currency'))):
        result['reason_codes'] = ['purchase_reference_correction_requires_review']
        return result
    reference_key = digest({'identity': identity, 'reference': ref})
    if old.get('reference_key') and old['reference_key'] != reference_key:
        result['reason_codes'] = ['purchase_reference_correction_requires_review']
        return result
    result.update(reference=ref, reference_key=reference_key)
    observations = []
    reasons = []
    txdate = row['transaction_date']
    date_today = now.astimezone(ZoneInfo('America/New_York')).date().isoformat()
    try:
        if snapshot.get('gap'):
            raise DataUnavailable(str(snapshot['gap']))
        if snapshot.get('basis') != 'split_adjusted' or snapshot.get('actions_complete') is not True:
            raise DataUnavailable('unverified_split_only_basis')
        if snapshot.get('provider_conflict') is not False:
            raise DataUnavailable('unresolved_provider_conflict')
        if not snapshot.get('history_provider'):
            raise DataUnavailable('missing_history_provenance')
        history_seen = timestamp(snapshot.get('history_observed_at'))
        if not history_seen or history_seen > now:
            raise DataUnavailable('missing_or_future_history_observation')
        basis = day(snapshot.get('basis_date'))
        if not basis or basis.isoformat() > date_today:
            raise DataUnavailable('invalid_history_basis_date')
        action_keys = []
        for action in snapshot.get('adjustment_events') or []:
            if not isinstance(action, Mapping) or not day(action.get('date')):
                raise DataUnavailable('invalid_corporate_action')
            if action.get('kind') == 'split':
                action_keys.append(action['date'])
        if len(action_keys) != len(set(action_keys)):
            raise DataUnavailable('duplicate_split_event')
        value, _ = effective(ref, snapshot)
        if not calendar.session(txdate) or txdate > date_today:
            raise DataUnavailable('invalid_transaction_session')
        bars = completed_bars(snapshot, history_seen, calendar)
        path = [b for b in bars if txdate < b['date'] <= date_today]
        expected = [d for d in calendar.sessions(txdate, date_today)
                    if d > txdate and calendar.session(d)[1] <= now]
        present = {b['date'] for b in path}
        missing = [d for d in expected if d not in present]
        if missing:
            reasons.append('incomplete_price_history')
        if any(b['date'] not in expected for b in path):
            raise DataUnavailable('unexpected_price_history_session')
        # A revised provider close cannot silently reprice the frozen purchase anchor.
        original = next((b for b in bars if b['date'] == txdate), None)
        if original is not None and abs(original['close'] / value - 1) > 1e-8:
            raise DataUnavailable('provider_reference_revision_requires_review')
        result.update(current_reference_price=value, expected_sessions=len(expected),
                      observed_sessions=len(path), missing_sessions=missing,
                      completed_sessions_through=utc(calendar.session(expected[-1])[1]) if expected else None)
        for bar in path:
            observations.append(_point(bar['high']/value-1, bar['high'], bar['date'], at=None,
                source=snapshot['history_provider'], precision='session', observed_at=utc(history_seen),
                basis_date=snapshot['basis_date']))
        through = result['completed_sessions_through']
        quote = snapshot.get('quote') or {}
        quote_at, quote_seen = timestamp(quote.get('at')), timestamp(quote.get('observed_at'))
        quote_price = number(quote.get('price'))
        quote_good = bool(quote_at and quote_seen and quote_at <= quote_seen <= now and
            calendar.regular(quote_at) and quote_at > timestamp(ref['at']) and
            quote.get('provider') and quote.get('precision') in ('second', 'millisecond') and
            quote.get('kind') == 'realtime' and quote.get('feed_delay_seconds') == 0 and
            quote_at.astimezone(ZoneInfo('America/New_York')).date() == basis and
            quote_price is not None and quote_price > 0 and
            # A daily feed cannot certify splits not yet covered by its history.
            day(snapshot.get('adjustments_through')) and
            day(snapshot['adjustments_through']) >= quote_at.astimezone(ZoneInfo('America/New_York')).date())
        if quote_good:
            observations.append(_point(quote_price/value-1, quote_price,
                quote_at.astimezone(ZoneInfo('America/New_York')).date().isoformat(), at=utc(quote_at),
                source=quote['provider'], precision=quote['precision'], observed_at=utc(quote_seen),
                basis_date=snapshot['basis_date']))
        current_interval = calendar.session(date_today)
        # During trading, sporadic quotes do not prove that an earlier spike was absent.
        if current_interval and current_interval[0] <= now < current_interval[1]:
            high = number(quote.get('session_high'))
            current_complete = bool(quote_good and quote_at.date() == now.date() and
                (now-quote_at).total_seconds() <= quote_max_seconds and
                quote.get('session_extremes_scope') == 'regular' and
                quote.get('session_extremes_through') == quote.get('at') and
                quote.get('session_extremes_from') == utc(current_interval[0]) and
                high is not None and high >= quote_price and date_today > txdate)
            if current_complete:
                observations.append(_point(high/value-1, high, date_today, at=None,
                    source=quote['provider'], precision='session_to_quote', observed_at=utc(quote_seen),
                    basis_date=snapshot['basis_date']))
                through = utc(quote_at)
                result['current_session_coverage'] = 'verified_through_quote'
                result['valid_until'] = utc(min(quote_at+timedelta(seconds=quote_max_seconds), current_interval[1]))
            else:
                result['current_session_coverage'] = 'unverified'
                reasons.append('current_session_high_coverage_unverified')
        else:
            result['valid_until'] = _next_open(now, calendar) or now_text
        if not path and through is None:
            reasons.append('no_completed_post_reference_observation')
        result['coverage_through'] = through
        result['coverage_complete'] = bool(through and not reasons)
    except (DataUnavailable, ValueError, TypeError, KeyError, AttributeError) as exc:
        # Invalid transport data is a visible gap, never a manufactured negative.
        reasons.append(str(exc) if isinstance(exc, DataUnavailable) else 'malformed_threshold_history')
    # Historical highs and the largest supported gain survive price-cache eviction.
    prior_peak = number(old.get('peak_gain_fraction'))
    candidates = observations + ([old['peak_observation']] if old.get('peak_observation') else [])
    if candidates:
        peak = max(candidates, key=lambda p: (p['gain_fraction'], -int(p['session_date'].replace('-', ''))))
        if prior_peak is None or peak['gain_fraction'] > prior_peak:
            result['peak_observation'] = deepcopy(peak)
            result['peak_gain_fraction'] = max(0.0, peak['gain_fraction'])
    threshold_key = format(fraction, '.12g')
    crossed = [p for p in candidates if _crosses(p['gain_fraction'], fraction)]
    existing_crossing = result['crossings'].get(threshold_key)
    if existing_crossing:
        crossed.append(existing_crossing)
    if crossed:
        point = min(crossed, key=_point_order)
        result['crossings'][threshold_key] = deepcopy(point)
        result['crossing'] = deepcopy(point)
    result['reason_codes'] = sorted(set(reasons))
    if _crosses(number(result.get('peak_gain_fraction')), fraction):
        result['status'], result['ever_crossed'] = 'crossed', True
    elif result['coverage_complete']:
        result['status'], result['ever_crossed'] = 'not_crossed', False
    else:
        result['status'], result['ever_crossed'] = 'unknown', None
    return result


def assess_thresholds(rows: list[dict], anchors: Mapping, prior: Mapping,
                      snapshot: Mapping, now: datetime, rules: Mapping, calendar) -> dict:
    fraction = float(rules.get('never_crossed_fraction', DEFAULT_FRACTION))
    trades = deepcopy(dict(prior.get('trades') or {}))
    for old in trades.values():
        old['active'] = False
    for row in rows:
        tid = row['trade_id']
        trades[tid] = assess_purchase(row, (anchors.get('trades') or {}).get(tid), trades.get(tid) or {},
                                     snapshot, now, fraction, calendar, quote_max_seconds=rules['quote_max_seconds'])
    counts = Counter(t['status'] for t in trades.values() if t['active'])
    return {'version': VERSION, 'threshold_fraction': fraction, 'evaluated_at': utc(now),
            'notice': NOTICE, 'trades': trades,
            'counts': {k: counts[k] for k in ('crossed', 'not_crossed', 'unknown')}}


def mark_unavailable(value: Mapping, now: datetime, reason: str, *, removed: bool = False) -> dict:
    """Withdraw negative flags when a due review is skipped; keep positive evidence."""
    result = deepcopy(dict(value))
    if not result:
        return result
    for trade in result['trades'].values():
        if not trade.get('active'):
            continue
        if removed:
            trade['active'] = False
        if trade['status'] != 'crossed':
            trade.update(status='unknown', ever_crossed=None)
        trade.update(coverage_complete=False, valid_until=utc(now))
        trade['reason_codes'] = sorted(set(trade.get('reason_codes', []) + [reason]))
    counts = Counter(t['status'] for t in result['trades'].values() if t.get('active'))
    result['counts'] = {k: counts[k] for k in ('crossed', 'not_crossed', 'unknown')}
    return result


def validate_thresholds(value: Mapping) -> None:
    """Validate new projections while allowing pre-feature journals unchanged."""
    from .opportunity_common import OpportunityError
    if not isinstance(value, dict) or value.get('version') != VERSION:
        raise OpportunityError('invalid purchase threshold version')
    fraction = number(value.get('threshold_fraction'))
    if fraction is None or not 0 < fraction <= 10 or not timestamp(value.get('evaluated_at')):
        raise OpportunityError('invalid purchase threshold metadata')
    if not isinstance(value.get('trades'), dict):
        raise OpportunityError('invalid purchase threshold trades')
    for tid, result in value['trades'].items():
        if not isinstance(result, dict) or result.get('trade_id') != tid or type(result.get('active')) is not bool:
            raise OpportunityError('invalid purchase threshold identity')
        status = result.get('status')
        if status not in ('crossed', 'not_crossed', 'unknown'):
            raise OpportunityError('invalid purchase threshold status')
        if not timestamp(result.get('evaluated_at')) or not timestamp(result.get('valid_until')):
            raise OpportunityError('invalid purchase threshold time')
        gain = number(result.get('peak_gain_fraction'))
        threshold = number(result.get('threshold_fraction'))
        if threshold is None or not 0 < threshold <= 10:
            raise OpportunityError('invalid purchase threshold value')
        if result['active'] and threshold != fraction:
            raise OpportunityError('active purchase threshold differs from method')
        if status == 'crossed' and (not _crosses(gain, threshold) or result.get('ever_crossed') is not True or not result.get('crossing')):
            raise OpportunityError('crossed purchase lacks retained positive evidence')
        if status == 'not_crossed' and (gain is None or _crosses(gain, threshold) or
                result.get('coverage_complete') is not True or result.get('ever_crossed') is not False or
                not timestamp(result.get('coverage_through')) or result.get('reason_codes')):
            raise OpportunityError('negative purchase flag lacks complete coverage')
        if status == 'unknown' and result.get('ever_crossed') is not None:
            raise OpportunityError('unknown purchase flag cannot claim a negative')
    counts = Counter(t['status'] for t in value['trades'].values() if t['active'])
    if value.get('counts') != {k: counts[k] for k in ('crossed', 'not_crossed', 'unknown')}:
        raise OpportunityError('purchase threshold counts differ from records')
