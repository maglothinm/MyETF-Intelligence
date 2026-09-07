"""Exchange-session-aware price references and independently enforced entry gates."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Mapping
from zoneinfo import ZoneInfo

from .opportunity_common import DataUnavailable, day, digest, number, timestamp, utc


class ExchangeCalendar:
    """Official-session calendar, including DST, early closes and exchange holidays."""
    def __init__(self, name: str = 'XNYS'):
        import exchange_calendars as calendars
        self.calendar = calendars.get_calendar(name)
        self.name = name

    def session(self, date_value: str) -> tuple[datetime, datetime] | None:
        try:
            if not self.calendar.is_session(date_value):
                return None
            return (self.calendar.session_open(date_value).to_pydatetime(), self.calendar.session_close(date_value).to_pydatetime())
        except (ValueError, KeyError) as exc:
            raise DataUnavailable('calendar_out_of_range') from exc

    def regular(self, now: datetime) -> bool:
        interval = self.session(now.astimezone(ZoneInfo('America/New_York')).date().isoformat())
        return bool(interval and interval[0] <= now < interval[1])

    def sessions(self, start: str, end: str) -> list[str]:
        try:
            return [v.date().isoformat() for v in self.calendar.sessions_in_range(start, end)]
        except ValueError as exc:
            raise DataUnavailable('calendar_out_of_range') from exc


def quote_quality(snapshot: Mapping, now: datetime, rules: Mapping, calendar: ExchangeCalendar) -> list[str]:
    quote = snapshot.get('quote') or {}
    reasons = []
    price = number(quote.get('price'))
    at, seen = timestamp(quote.get('at')), timestamp(quote.get('observed_at'))
    if price is None or price <= 0:
        reasons.append('invalid_quote_price')
    if not at or not seen or at > now or seen > now or at > seen:
        reasons.append('missing_or_future_quote_timestamp')
    elif (now-at).total_seconds() > rules['quote_max_seconds']:
        reasons.append('stale_quote')
    if quote.get('kind') != 'realtime' or quote.get('feed_delay_seconds') != 0:
        reasons.append('unverified_live_feed')
    if not calendar.regular(now):
        reasons.append('market_closed')
    elif at and not calendar.regular(at):
        reasons.append('extended_or_previous_session_quote')
    if not quote.get('provider') or quote.get('precision') not in ('second', 'millisecond'):
        reasons.append('unsupported_quote_provenance')
    if snapshot.get('basis') != 'split_adjusted' or snapshot.get('actions_complete') is not True:
        reasons.append('unsupported_corporate_actions')
    if snapshot.get('provider_conflict') is not False:
        reasons.append('unresolved_provider_conflict')
    return reasons


def completed_bars(snapshot: Mapping, now: datetime, calendar: ExchangeCalendar) -> list[dict]:
    bars = []
    for raw in snapshot.get('bars') or []:
        interval = calendar.session(str(raw.get('date')))
        values = {k: number(raw.get(k)) for k in ('open', 'high', 'low', 'close')}
        if not interval or interval[1] > now:
            continue
        if any(v is None or v <= 0 for v in values.values()) or values['low'] > min(values['open'], values['close']) or values['high'] < max(values['open'], values['close']):
            raise DataUnavailable('invalid_price_history')
        if raw.get('observed_at') and (not timestamp(raw['observed_at']) or timestamp(raw['observed_at']) > now):
            continue
        bars.append({**raw, **values, 'at': utc(interval[1])})
    bars.sort(key=lambda b: b['date'])
    if len({b['date'] for b in bars}) != len(bars):
        raise DataUnavailable('conflicting_history_bars')
    return bars


def measured_atr(bars: list[dict], at: datetime, periods: int, calendar: ExchangeCalendar) -> dict | None:
    prior = [b for b in bars if timestamp(b['at']) <= at]
    if len(prior) < periods + 1:
        return None
    sample = prior[-periods-1:]
    if [b['date'] for b in sample] != calendar.sessions(sample[0]['date'], sample[-1]['date']):
        return None
    ranges = [max(b['high']-b['low'], abs(b['high']-p['close']), abs(b['low']-p['close'])) for p, b in zip(sample, sample[1:])]
    value = sum(ranges)/periods
    if value <= 0:
        return None
    return {'value':value, 'sessions':periods, 'through':sample[-1]['at'], 'source_hash':digest(sample),
            'method':'mean of completed session true ranges; no fallback'}


def anchor(price: float, at: str, snapshot: Mapping, *, kind: str, atr: dict | None, observed_at: str) -> dict:
    return {'price':price, 'at':at, 'observed_at':observed_at, 'provider':snapshot.get('history_provider') if kind == 'trade_date_close' else (snapshot.get('quote') or {}).get('provider'),
            'precision':'session_close' if kind == 'trade_date_close' else 'second',
            'status':'reconstructed' if kind == 'trade_date_close' else 'observed', 'kind':kind,
            'confidence':'supported_market_reference', 'basis':'split_adjusted', 'basis_date':snapshot.get('basis_date'),
            'currency':snapshot.get('currency'), 'security_id':snapshot.get('security_id'), 'share_class':snapshot.get('share_class'), 'atr':atr}


def effective(anchor_value: Mapping, snapshot: Mapping) -> tuple[float, float | None]:
    if any(anchor_value.get(k) != snapshot.get(k) for k in ('currency','security_id','share_class','basis')):
        raise DataUnavailable('incompatible_price_basis_or_security')
    base = day(anchor_value.get('basis_date'))
    current_base = day(snapshot.get('basis_date'))
    if not base or not current_base or current_base < base:
        raise DataUnavailable('unsupported_adjustment_basis_date')
    factor = 1.0
    for event in snapshot.get('adjustment_events') or []:
        ex_date = day(event.get('date'))
        if not ex_date:
            raise DataUnavailable('invalid_adjustment_event')
        if base < ex_date <= current_base and event.get('kind') == 'split':
            ratio = number(event.get('ratio'))
            if ratio is None or ratio <= 0:
                raise DataUnavailable('unsupported_split')
            factor *= ratio
        elif event.get('kind') not in ('split', 'dividend'):
            raise DataUnavailable('unsupported_corporate_action')
    value = number(anchor_value.get('price'))
    atr = number((anchor_value.get('atr') or {}).get('value'))
    if value is None or value <= 0:
        raise DataUnavailable('invalid_reference_price')
    return value/factor, atr/factor if atr is not None else None


def timeline(row: Mapping, discovery: Mapping | None, now: datetime) -> dict:
    def date_anchor(value, kind):
        return {'value':value if day(value) else None, 'precision':'date' if day(value) else 'unknown',
                'provider':row.get('source'), 'source_url':row.get('source_url'), 'kind':kind,
                'status':'disclosed' if day(value) else 'unknown', 'confidence':'source_reported' if day(value) else 'unknown'}
    release = {'value':None, 'precision':'unknown', 'status':'unknown', 'confidence':'unknown'}
    public = row.get('public_availability') or {}
    if timestamp(public.get('at')) and timestamp(public['at']) <= now and public.get('source_url'):
        release = {**public, 'value':public['at'], 'precision':public.get('precision', 'second'), 'status':'observed', 'confidence':'verified_source'}
    elif day(public.get('date')) and day(public['date']) <= now.date() and public.get('source_url'):
        release = {**public, 'value':public['date'], 'precision':'date', 'status':'disclosed', 'confidence':'source_reported'}
    else:
        negative, positive = timestamp(public.get('last_complete_negative_at')), timestamp(public.get('first_positive_at'))
        if negative and positive and negative < positive <= now and public.get('same_complete_source_coverage') is True and public.get('source_url'):
            release = {**public, 'value':[utc(negative), utc(positive)], 'precision':'bounded_interval', 'status':'bounded', 'confidence':'coverage_supported'}
    first = row['first_observed_at_utc']
    return {'transaction':date_anchor(row.get('transaction_date'), 'transaction_date'),
            'submission':date_anchor(row.get('filed_date'), 'submission_date'), 'public_availability':release,
            'first_observation':{'value':first, 'precision':'second', 'provider':'PolitiTrack', 'status':'observed', 'confidence':'retained_source_observation'},
            'discovery_quote':deepcopy(discovery),
            'discovery_quote_lag_seconds':(timestamp(discovery['at'])-timestamp(first)).total_seconds() if discovery else None,
            'confidence':'limited_public_availability' if release['value'] is None else 'supported_with_reported_precision'}


def assess(rows: list[dict], prior_anchors: Mapping, snapshot: Mapping, now: datetime, rules: Mapping, calendar: ExchangeCalendar) -> dict:
    anchors = deepcopy(dict(prior_anchors))
    anchors.setdefault('trades', {})
    reasons = quote_quality(snapshot, now, rules, calendar)
    if snapshot.get('gap'):
        reasons.append(str(snapshot['gap']))
    if any(r.get('security_id') != snapshot.get('security_id') or r.get('share_class') != snapshot.get('share_class') or r.get('currency') != snapshot.get('currency') for r in rows):
        reasons.append('incompatible_price_basis_or_security')
    bars = completed_bars(snapshot, now, calendar)
    quote = dict(snapshot.get('quote') or {})
    # Preserve the invalid-data reason while keeping the durable JSON finite.
    for field in ('price', 'session_high', 'session_low'):
        if field in quote:
            quote[field] = number(quote[field])
    price, quote_at = number(quote.get('price')), timestamp(quote.get('at'))
    first = min((timestamp(r['first_observed_at_utc']) for r in rows), default=now)
    if not anchors.get('discovery') and not reasons and quote_at >= first:
        atr = measured_atr(bars, quote_at, rules['atr_sessions'], calendar)
        if atr:
            anchors['discovery'] = anchor(price, quote['at'], snapshot, kind='first_usable_quote_after_discovery', atr=atr, observed_at=quote['observed_at'])
    if not anchors.get('discovery'):
        reasons.append('missing_discovery_reference')
    metrics, eligible = {}, []
    for row in rows:
        tid = row['trade_id']
        txdate = row.get('transaction_date')
        ref = anchors['trades'].get(tid)
        if not ref:
            bar = next((b for b in bars if b['date'] == txdate), None)
            if bar:
                at = timestamp(bar['at'])
                ref = anchor(bar['close'], bar['at'], snapshot, kind='trade_date_close',
                             atr=measured_atr(bars, at, rules['atr_sessions'], calendar), observed_at=utc(now))
                anchors['trades'][tid] = ref
        missing = []
        if ref and ref.get('kind') == 'trade_date_close' and ref.get('at', '')[:10] != txdate:
            missing.append('corrected_trade_date_requires_reference_review')
        if not ref:
            missing.append('missing_trade_reference')
        if not price or not ref:
            metrics[tid] = {'path':'insufficient_data', 'reason_codes':missing or reasons}
            continue
        reference, atr = effective(ref, snapshot)
        if atr is None:
            missing.append('missing_reference_atr')
        path_bars = [b for b in bars if b['date'] > txdate]
        expected = [d for d in calendar.sessions(txdate, now.astimezone(ZoneInfo('America/New_York')).date().isoformat()) if calendar.session(d)[1] <= now and d > txdate]
        if [b['date'] for b in path_bars] != expected:
            missing.append('incomplete_price_path')
        highs = [reference, price] + [b['high'] for b in path_bars]
        lows = [reference, price] + [b['low'] for b in path_bars]
        # Provider session extremes expose excursions missed by periodic observations.
        if quote_at and calendar.regular(quote_at):
            for field, target in (('session_high', highs), ('session_low', lows)):
                val = number(quote.get(field))
                if val and val > 0:
                    target.append(val)
        up, down = max(highs)/reference-1, min(lows)/reference-1
        move = price/reference-1
        near = abs(move) <= rules['trade_fraction'] + 1e-12 and atr is not None and abs(price-reference) <= rules['trade_atr_multiple']*atr + 1e-12
        threshold = min(reference*rules['trade_fraction'], rules['trade_atr_multiple']*atr) if atr is not None else 0
        excursion = max(highs)-reference > threshold + 1e-12 or reference-min(lows) > threshold + 1e-12
        path = 'returned_to_range' if near and excursion else 'never_materially_moved' if near else 'material_decline' if move < 0 else 'already_moved'
        if not missing and near:
            eligible.append(tid)
        metrics[tid] = {'transaction_to_current':move, 'transaction_to_release':None, 'release_to_discovery':None,
                        'max_up_fraction':up, 'max_down_fraction':down, 'drawdown_from_high':price/max(highs)-1,
                        'path':path if not missing else 'insufficient_data', 'near':near, 'reason_codes':missing,
                        'reference_price':reference, 'reference_atr':atr,
                        'price_band':[reference-threshold, reference+threshold], 'resolution':'completed_daily_OHLC_and_observed_quotes'}
        # Only an explicit compatible release price supports the two optional segments.
        release_price = row.get('public_price_reference')
        if release_price and timestamp(release_price.get('at')) and timestamp(release_price['at']) <= now:
            rel, _ = effective(release_price, snapshot)
            metrics[tid]['transaction_to_release'] = rel/reference-1
            if anchors.get('discovery'):
                disc, _ = effective(anchors['discovery'], snapshot)
                metrics[tid]['release_to_discovery'] = disc/rel-1
    discovery_near = False
    discovery_return = None
    if anchors.get('discovery') and price:
        ref, atr = effective(anchors['discovery'], snapshot)
        discovery_return = price/ref-1
        discovery_near = atr is not None and abs(discovery_return) <= rules['discovery_fraction'] + 1e-12 and abs(price-ref) <= rules['discovery_atr_multiple']*atr + 1e-12
        if not atr:
            reasons.append('missing_discovery_atr')
    paths = {v['path'] for v in metrics.values()}
    path = next((p for p in ('insufficient_data','material_decline','already_moved','returned_to_range','never_materially_moved') if p in paths), 'insufficient_data')
    return {'anchors':anchors, 'metrics':metrics, 'eligible_trade_ids':eligible, 'discovery_near':discovery_near,
            'discovery_to_current':discovery_return, 'reason_codes':sorted(set(reasons)), 'path':path,
            'quote':dict(quote), 'session':'regular' if calendar.regular(now) else 'market_closed',
            'adjustment_events':snapshot.get('adjustment_events', []), 'basis':snapshot.get('basis'),
            'timeline':{r['trade_id']:timeline(r, anchors.get('discovery'), now) for r in rows}}
