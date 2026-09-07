from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest

from scripts.opportunity_common import DataUnavailable, utc
from scripts.opportunity_market import ExchangeCalendar, assess, effective, measured_atr, completed_bars, timeline
from scripts.opportunity_significance import normalize
from opportunity_helpers import NOW, Clock, Market, rules, trade


def evaluate(market=None, anchors=None, row=None, clock=None):
    clock=clock or Clock()
    market=market or Market(clock)
    rows,_=normalize([row or trade()],clock())
    return assess(rows,anchors or {},market.snapshot(rows,clock()),clock(),rules(),ExchangeCalendar())


def test_quiet_and_returns_and_immutable_anchors():
    clock=Clock(); provider=Market(clock)
    first=evaluate(provider,clock=clock)
    assert first['path']=='never_materially_moved'
    assert first['metrics']['TEST-1']['transaction_to_current']==0
    original=deepcopy(first['anchors'])
    clock.advance(); provider.price=101
    latest=evaluate(provider,first['anchors'],clock=clock)
    assert latest['anchors']==original
    assert latest['discovery_to_current']==pytest.approx(.01)
    assert latest['metrics']['TEST-1']['transaction_to_release'] is None


@pytest.mark.parametrize('price,rally,path', [(105,None,'already_moved'),(100,110,'returned_to_range'),(90,None,'material_decline')])
def test_price_paths_are_distinct(price,rally,path):
    c=Clock(); p=Market(c,price); p.rally=rally
    assert evaluate(p,clock=c)['path']==path


@pytest.mark.parametrize('change,reason', [({'price':0},'invalid_quote_price'),({'price':float('nan')},'invalid_quote_price'),({'at':None},'missing_or_future_quote_timestamp'),({'at':utc(NOW-timedelta(minutes=6))},'stale_quote'),({'feed_delay_seconds':900},'unverified_live_feed'),({'kind':'end_of_day'},'unverified_live_feed'),({'at':utc(NOW.replace(hour=12))},'extended_or_previous_session_quote')])
def test_quote_quality(change,reason):
    c=Clock(); p=Market(c); p.quote_modify=change
    result=evaluate(p,clock=c)
    assert reason in result['reason_codes']


def test_conflict_missing_atr_and_history_gap():
    c=Clock(); p=Market(c); p.modify={'provider_conflict':True}
    assert 'unresolved_provider_conflict' in evaluate(p,clock=c)['reason_codes']
    rows,_=normalize([trade()],c()); snap=Market(c).snapshot(rows,c())
    snap['bars']=[b for b in snap['bars'] if b['date'] >= '2026-06-01']
    value=assess(rows,{},snap,c(),rules(),ExchangeCalendar())
    assert 'missing_reference_atr' in value['metrics']['TEST-1']['reason_codes']
    snap=Market(c).snapshot(rows,c()); snap['bars'].pop(-3)
    assert 'incomplete_price_path' in assess(rows,{},snap,c(),rules(),ExchangeCalendar())['metrics']['TEST-1']['reason_codes']


def test_split_and_dividend_basis():
    c=Clock(); initial=evaluate(clock=c)['anchors']['trades']['TEST-1']
    snap={'security_id':'TEST-FIGI-1','currency':'USD','share_class':'common','basis':'split_adjusted',
          'basis_date':'2026-09-10','adjustment_events':[{'date':'2026-09-09','kind':'split','ratio':2},{'date':'2026-09-10','kind':'dividend','amount':1}]}
    assert effective(initial,snap)==(50,2)
    snap['basis']='total_return'
    with pytest.raises(DataUnavailable): effective(initial,snap)


def test_calendar_holidays_dst_early_close_extended_hours():
    cal=ExchangeCalendar()
    assert cal.session('2026-09-07') is None
    assert cal.session('2026-03-06')[0].hour==14
    assert cal.session('2026-03-09')[0].hour==13
    assert cal.session('2026-11-27')[1].hour==18
    assert not cal.regular(datetime(2026,11,27,18,0,tzinfo=timezone.utc))
    assert not cal.regular(datetime(2026,9,8,12,0,tzinfo=timezone.utc))


def test_publication_unknown_date_and_bounded_interval():
    row=normalize([trade()],NOW)[0][0]
    assert timeline(row,None,NOW)['public_availability']['value'] is None
    row['public_availability']={'date':'2026-09-08','source_url':'https://example.test'}
    assert timeline(row,None,NOW)['public_availability']['precision']=='date'
    row['public_availability']={'last_complete_negative_at':utc(NOW-timedelta(hours=2)),'first_positive_at':utc(NOW-timedelta(hours=1)),'same_complete_source_coverage':True,'source_url':'https://example.test'}
    assert timeline(row,None,NOW)['public_availability']['precision']=='bounded_interval'
    row['public_availability']['same_complete_source_coverage']=False
    assert timeline(row,None,NOW)['public_availability']['value'] is None


def test_missing_trade_date_never_uses_a_nearby_session():
    value=evaluate(row=trade(transaction_date='2026-05-31'))
    assert value['metrics']['TEST-1']['reason_codes']==['missing_trade_reference']


def test_reference_atr_does_not_widen_after_volatility_spike():
    c=Clock(); p=Market(c)
    initial=evaluate(p,clock=c)
    c.advance(); p.price=103.1; p.rally=140
    value=evaluate(p,initial['anchors'],clock=c)
    assert value['anchors']==initial['anchors']
    assert value['metrics']['TEST-1']['near'] is False
