"""Threshold research fixtures: no external services, credentials or production data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import json

import pytest

from scripts.opportunity_common import load_rules, OpportunityError, utc
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar, assess
from scripts.opportunity_significance import normalize
from scripts.opportunity_threshold import assess_thresholds, mark_unavailable
from scripts.opportunity_state import load, save
from opportunity_helpers import Clock, Evidence, Market, rules, state, trade

CLOSED = datetime(2026, 9, 19, 17, 0, tzinfo=timezone.utc)
CAL = ExchangeCalendar()


def setup(high=104, date='2026-06-01', now=CLOSED):
    clock = Clock(now)
    rows, _ = normalize([trade(transaction_date=date)], clock())
    snap = Market(clock).snapshot(rows, clock())
    for b in snap['bars']:
        if b['date'] > date:
            b.update(high=high, low=min(high, 98), open=min(high,100), close=min(high,100))
    anchors = assess(rows, {}, snap, clock(), rules(), CAL)['anchors']
    return rows, anchors, snap, clock


def evaluate(high=104, previous=None, fraction=.08, **kwargs):
    rows, anchors, snap, clock = setup(high, **kwargs)
    value=assess_thresholds(rows, anchors, previous or {}, snap, clock(), rules(never_crossed_fraction=fraction), CAL)
    return value, value['trades']['TEST-1']


@pytest.mark.parametrize('high,status', [(104,'not_crossed'),(119,'crossed'),(108,'crossed'),(107.99999,'not_crossed'),(101,'not_crossed'),(95,'not_crossed')])
def test_entire_path_not_endpoint_and_equality(high,status):
    value, result=evaluate(high)
    assert result['status']==status
    assert result['ever_crossed'] is (status=='crossed')
    assert result['coverage_complete']
    assert value['counts'][status]==1
    assert result['reference_kind']=='trade_date_close'
    assert result['purchase_day_ordering']=='unknown_excluded'
    assert result['coverage_through']=='2026-09-18T20:00:00Z'
    assert result['valid_until']=='2026-09-21T13:30:00Z'
    if status=='crossed':
        assert result['crossing']['precision']=='session'
        assert result['crossing']['at'] is None
        assert result['crossing']['first_observed_at']==utc(CLOSED)


def test_retracement_restart_missing_provider_and_removed_purchase_preserve_crossing(tmp_path):
    clock=Clock(CLOSED); s=state(tmp_path,clock); provider=Market(clock); provider.rally=119
    cycle(s,[trade()],rules(),clock,CAL,provider,Evidence(clock),channels=['simulation'])
    save(tmp_path,s); before=deepcopy(s['events']); s=load(tmp_path,clock())
    clock.advance(); provider.rally=None; provider.price=101
    cycle(s,[trade()],rules(),clock,CAL,provider,Evidence(clock),channels=['simulation'])
    r=next(iter(s['opportunities'].values()))['purchase_thresholds']['trades']['TEST-1']
    assert r['status']=='crossed' and r['peak_gain_fraction']==pytest.approx(.19)
    clock.advance(); provider.modify={'gap':'TEST provider outage'}
    cycle(s,[trade()],rules(),clock,CAL,provider,Evidence(clock),channels=['simulation']);save(tmp_path,s)
    r=next(iter(s['opportunities'].values()))['purchase_thresholds']['trades']['TEST-1']
    assert r['status']=='crossed' and not r['coverage_complete']
    assert 'TEST provider outage' in r['reason_codes']
    assert s['events'][:len(before)]==before
    clock.advance(); cycle(s,[],rules(),clock,CAL,provider,Evidence(clock),channels=['simulation'])
    r=next(iter(s['opportunities'].values()))['purchase_thresholds']['trades']['TEST-1']
    assert r['status']=='crossed' and r['active'] is False


@pytest.mark.parametrize('damage,reason', [
    ('missing','incomplete_price_history'),('duplicate','conflicting_history_bars'),
    ('invalid','invalid_price_history'),('no_provider','missing_history_provenance'),
    ('basis','unverified_split_only_basis'),('actions','unverified_split_only_basis'),
    ('conflict','unresolved_provider_conflict'),('future','missing_or_future_history_observation'),
    ('no_time','missing_or_future_history_observation'),('reference_revision','provider_reference_revision_requires_review')])
def test_bad_history_never_proves_no_crossing(damage,reason):
    rows,anchors,snap,c=setup()
    if damage=='missing':snap['bars'].pop(-3)
    if damage=='duplicate':snap['bars'].append(deepcopy(snap['bars'][-1]))
    if damage=='invalid':snap['bars'][-1]['high']=float('nan')
    if damage=='no_provider':snap.pop('history_provider')
    if damage=='basis':snap['basis']='total_return'
    if damage=='actions':snap['actions_complete']=False
    if damage=='conflict':snap['provider_conflict']=True
    if damage=='future':snap['history_observed_at']=utc(c()+timedelta(hours=1))
    if damage=='no_time':snap.pop('history_observed_at')
    if damage=='reference_revision':
        b=next(b for b in snap['bars'] if b['date']=='2026-06-01');b.update(close=101,high=102)
    r=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert r['status']=='unknown' and r['ever_crossed'] is None
    assert reason in r['reason_codes']


def test_gap_does_not_hide_supported_historical_crossing():
    rows,anchors,snap,c=setup(119);snap['bars'].pop(-3)
    r=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert r['status']=='crossed' and not r['coverage_complete']


def test_purchase_day_high_excluded_and_first_crossing_is_observed_not_exact_time():
    rows,anchors,snap,c=setup(104)
    next(b for b in snap['bars'] if b['date']=='2026-06-01')['high']=160
    r=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert r['status']=='not_crossed' and r['peak_gain_fraction']==pytest.approx(.04)
    assert r['purchase_day_ordering']=='unknown_excluded'


def test_newer_purchase_does_not_reset_earlier_purchase():
    rows,anchors,snap,c=setup(104)
    next(b for b in snap['bars'] if b['date']=='2026-06-10')['high']=120
    first=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)
    rows,_=normalize([trade(),trade('TEST-2',transaction_date='2026-09-01')],c())
    anchors=assess(rows,anchors,snap,c(),rules(),CAL)['anchors']
    result=assess_thresholds(rows,anchors,first,snap,c(),rules(),CAL)
    assert result['trades']['TEST-1']['status']=='crossed'
    assert result['trades']['TEST-2']['status']=='not_crossed'
    assert result['counts']=={'crossed':1,'not_crossed':1,'unknown':0}


def test_corrected_date_cannot_inherit_or_reset_original_reference():
    rows,anchors,snap,c=setup(119)
    first=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)
    rows[0]['transaction_date']='2026-09-01'
    result=assess_thresholds(rows,anchors,first,snap,c(),rules(),CAL)['trades']['TEST-1']
    assert result['status']=='unknown'
    assert result['original_identity']['transaction_date']=='2026-06-01'
    assert result['crossings'] and result['peak_gain_fraction']==pytest.approx(.19)
    again=assess_thresholds(rows,anchors,{'trades':{'TEST-1':result}},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert again['status']=='unknown'


def test_split_conversion_and_dividends_separate():
    rows,anchors,snap,c=setup(104)
    first=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)
    snap['basis_date']='2026-09-20';snap['adjustment_events']=[{'date':'2026-09-20','kind':'split','ratio':2},{'date':'2026-09-20','kind':'dividend','amount':10}]
    for b in snap['bars']:
        for key in ('open','high','low','close'):b[key]/=2
    c.advance(minutes=24*60)
    snap['history_observed_at']=utc(c())
    second=assess_thresholds(rows,anchors,first,snap,c(),rules(),CAL)['trades']['TEST-1']
    assert second['status']=='not_crossed'
    assert second['current_reference_price']==50
    assert second['reference']['price']==100
    assert second['peak_gain_fraction']==pytest.approx(.04)
    snap['adjustment_events'].append({'date':'2026-09-20','kind':'split','ratio':2})
    bad=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert bad['status']=='unknown' and 'duplicate_split_event' in bad['reason_codes']


def test_threshold_changes_reclassify_retained_peak_without_alert_method_change():
    old, _=evaluate(119)
    new,r=evaluate(104,previous=old,fraction=.25)
    assert r['status']=='not_crossed' and '0.08' in r['crossings']
    _,r=evaluate(104,previous=new,fraction=.15)
    assert r['status']=='crossed' and r['peak_gain_fraction']==pytest.approx(.19)
    assert load_rules()['method_hash']==rules(never_crossed_fraction=.25)['method_hash']


def test_open_session_needs_verified_high_coverage_and_action_basis():
    current=datetime(2026,9,18,15,0,tzinfo=timezone.utc)
    rows,anchors,snap,c=setup(104,now=current)
    first=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert first['status']=='unknown'
    q=snap['quote'];q.update(session_extremes_scope='regular',session_extremes_through=q['at'],
                            session_extremes_from=utc(CAL.session('2026-09-18')[0]),session_high=104)
    snap['adjustments_through']='2026-09-18'
    second=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert second['status']=='not_crossed' and second['coverage_through']==utc(c())
    q['session_high']=119
    r=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert r['status']=='crossed' and r['crossing']['precision']=='session_to_quote'
    # A stale quote with a supported ordinary-session price can prove crossing,
    # but never supplies complete current-session negative coverage.
    q.update(price=120,at=utc(c()-timedelta(minutes=20)))
    q.pop('session_extremes_scope')
    r=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert r['status']=='crossed' and not r['coverage_complete']
    snap['adjustments_through']='2026-09-17'
    r=assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']
    assert r['status']=='unknown'


def test_extended_hours_and_unknown_purchase_day_are_not_positive_proof():
    rows,anchors,snap,c=setup(104)
    snap['quote'].update(price=150,at='2026-09-18T23:00:00Z')
    snap['adjustments_through']='2026-09-19'
    assert assess_thresholds(rows,anchors,{},snap,c(),rules(),CAL)['trades']['TEST-1']['status']=='not_crossed'
    _,r=evaluate(104,date='2026-09-19')
    assert r['status']=='unknown'


def test_pending_review_withdraws_negative_flags_but_retains_crossed():
    quiet,_=evaluate(104); crossed,_=evaluate(119)
    assert mark_unavailable(quiet,CLOSED,'budget')['trades']['TEST-1']['status']=='unknown'
    assert mark_unavailable(crossed,CLOSED,'budget')['trades']['TEST-1']['status']=='crossed'


def test_flag_does_not_manufacture_opportunity_or_send_and_exports_are_per_purchase(tmp_path):
    from scripts.opportunity_dashboard import load_projection,write_exports
    c=Clock(CLOSED);s=state(tmp_path/'ai',c)
    cycle(s,[trade(amount='$1,001 - $15,000')],rules(),c,CAL,Market(c),Evidence(c),channels=['simulation'])
    r=next(iter(s['opportunities'].values()))
    assert r['purchase_thresholds']['trades']['TEST-1']['status']=='not_crossed'
    assert not r['gates']['meaningful_buying'] and r['lifecycle']!='opportunity_available'
    assert not s['intents']
    save(tmp_path/'ai',s)
    out=tmp_path/'site';(out/'data').mkdir(parents=True)
    write_exports(load_projection(tmp_path/'ai'),out,Path(__file__).resolve().parents[1]/'scripts/dashboard_assets')
    with (out/'data/purchase-thresholds.csv').open() as f: records=list(csv.DictReader(f))
    assert len(records)==1 and records[0]['status']=='not_crossed'
    assert json.loads(records[0]['provenance_json'])==r['purchase_thresholds']['trades']['TEST-1']


@pytest.mark.parametrize('value',[0,-.1,11,float('nan'),float('inf')])
def test_bad_threshold_config_rejected(tmp_path,value):
    import yaml
    base=load_rules();base.pop('method_hash');base['never_crossed_fraction']=value
    p=tmp_path/'rules.yml';p.write_text(yaml.safe_dump(base))
    with pytest.raises(OpportunityError):load_rules(p)


@pytest.mark.parametrize('high,status',[(104,'not_crossed'),(119,'crossed')])
def test_threshold_projection_validation_rejects_unproved_status(high,status):
    from scripts.opportunity_threshold import validate_thresholds
    value,r=evaluate(high)
    validate_thresholds(value)
    r['status']='crossed' if status=='not_crossed' else 'not_crossed'
    with pytest.raises(OpportunityError):validate_thresholds(value)


def test_budget_skip_and_change_of_threshold_cannot_send_an_alert(tmp_path):
    c=Clock(CLOSED);s=state(tmp_path,c);p=Market(c)
    cycle(s,[trade()],rules(),c,CAL,p,Evidence(c),channels=['simulation'])
    r=next(iter(s['opportunities'].values()));assert r['purchase_thresholds']['counts']['not_crossed']==1
    c.advance();cycle(s,[trade()],rules(security_budget=0),c,CAL,p,Evidence(c),channels=['simulation'])
    r=next(iter(s['opportunities'].values()));assert r['purchase_thresholds']['counts']['unknown']==1
    # A descriptive threshold change schedules reassessment without altering buying gates.
    cycle(s,[trade()],rules(never_crossed_fraction=.01),c,CAL,p,Evidence(c),channels=['simulation'])
    r=next(iter(s['opportunities'].values()));assert r['purchase_thresholds']['counts']['crossed']==1
    assert not s['intents']
    save(tmp_path,s)


def test_custom_quote_freshness_applies_to_negative_flag():
    current=datetime(2026,9,18,15,0,tzinfo=timezone.utc)
    rows,anchors,snap,c=setup(104,now=current)
    q=snap['quote'];q.update(session_extremes_scope='regular',session_extremes_through=q['at'],
                            session_extremes_from=utc(CAL.session('2026-09-18')[0]),session_high=104)
    snap['adjustments_through']='2026-09-18'
    short=rules(quote_max_seconds=15)
    first=assess_thresholds(rows,anchors,{},snap,c(),short,CAL)['trades']['TEST-1']
    assert first['status']=='not_crossed' and first['valid_until']==utc(c()+timedelta(seconds=15))
    c.advance(minutes=1)
    later=assess_thresholds(rows,anchors,{},snap,c(),short,CAL)['trades']['TEST-1']
    assert later['status']=='unknown'
