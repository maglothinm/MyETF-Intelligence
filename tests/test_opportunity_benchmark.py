"""TEST-only matched benchmark validation; no network calls or portfolio state."""
from copy import deepcopy
from datetime import timedelta
import pytest
from scripts.opportunity_common import DataUnavailable, utc, digest
from scripts.opportunity_benchmark import advance_benchmark
from scripts.opportunity_research import advance
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_significance import normalize
from opportunity_helpers import Clock, Market, trade, rules
from test_opportunity_providers import provider


def observation(c, *, price=100, benchmark_price=500):
    rows=normalize([trade()],c())[0]
    snap=Market(c,price).snapshot(rows,c())
    benchmark=deepcopy(snap)
    benchmark.update(status='available',symbol='TEST-BENCH',security_id='TEST-BENCH-ID',share_class='fund')
    benchmark['quote']['price']=benchmark_price
    for b in benchmark['bars']:
        b.update(open=benchmark_price,high=benchmark_price+2,low=benchmark_price-2,close=benchmark_price)
    snap['benchmark']=benchmark
    r={'opportunity_id':'TEST-opportunity','rule_hash':'a'*64,'mode':'shadow','ticker':'TEST',
       'security_id':'TEST-FIGI-1','share_class':'common','currency':'USD','lifecycle':'opportunity_available',
       'gates':{'meaningful_buying':True},'investment_dossier':{'status':'ready_for_human_review'},
       'market':{'quote':snap['quote'],'session':'regular'}}
    return r,snap


def anchored():
    c=Clock();cal=ExchangeCalendar();r,s=observation(c)
    research=advance(None,r,s,cal,c());c.advance()
    r,s=observation(c);research=advance(research,r,s,cal,c())
    assert all(v.get('benchmark_anchor') for v in research['cohorts'].values())
    return c,cal,research


def mature(c,cal):
    target=cal.sessions('2026-09-08','2026-10-01')[5]
    c.value=cal.session(target)[1]+timedelta(minutes=5)
    r,s=observation(c,price=110,benchmark_price=525)
    s['bars'][-1]['close']=110
    return r,s


def test_matched_benchmark_measures_excess_after_equal_cost_assumptions():
    c,cal,research=anchored();r,s=mature(c,cal)
    research=advance(research,r,s,cal,c())
    for v in research['cohorts'].values():
        own=v['outcomes']['5'];bench=v['benchmark_outcomes']['5']
        assert own['net_return_fraction']==pytest.approx(.099)
        assert bench['net_return_fraction']==pytest.approx(.049)
        assert bench['benchmark_relative_fraction']==pytest.approx(.05)
        assert own['benchmark_relative_fraction']==pytest.approx(.05)
        assert bench['source_asset_outcome_sha256']==digest(own)
        assert 'excludes dividends' in bench['notice']
    before=deepcopy(research);s['benchmark']['bars'][-1]['close']=999
    assert advance(research,r,s,cal,c())==before


def test_late_benchmark_appends_without_rewriting_original_result():
    c,cal,research=anchored();r,s=mature(c,cal);good=deepcopy(s['benchmark'])
    s['benchmark']={'status':'unavailable','reason':'TEST temporary gap'}
    research=advance(research,r,s,cal,c())
    originals=[deepcopy(v['outcomes']['5']) for v in research['cohorts'].values()]
    assert all(v['benchmark_relative_fraction'] is None for v in originals)
    s['benchmark']=good;research=advance(research,r,s,cal,c())
    assert [v['outcomes']['5'] for v in research['cohorts'].values()]==originals
    assert all(v['benchmark_outcomes']['5']['benchmark_relative_fraction']==pytest.approx(.05) for v in research['cohorts'].values())


@pytest.mark.parametrize('failure',['skew','currency','identity','observation'])
def test_bad_benchmark_never_fabricates_comparison_or_fails_primary(failure):
    c=Clock();cal=ExchangeCalendar();r,s=observation(c);research=advance(None,r,s,cal,c());c.advance()
    r,s=observation(c)
    if failure=='skew':s['benchmark']['quote']['at']=utc(c()-timedelta(seconds=121))
    if failure=='currency':s['benchmark']['currency']='EUR'
    if failure=='identity':s['benchmark']['security_id']=''
    if failure=='observation':s['benchmark']['quote']['observed_at']=utc(c()+timedelta(seconds=1))
    research=advance(research,r,s,cal,c())
    assert all(v['anchor'] and not v.get('benchmark_anchor') for v in research['cohorts'].values())
    assert all(not v.get('benchmark_outcomes') for v in research['cohorts'].values())
    assert r['lifecycle']=='opportunity_available'


def test_benchmark_split_normalization_and_identity_changes():
    c,cal,research=anchored();r,s=mature(c,cal)
    s['benchmark']['adjustment_events']=[{'kind':'split','date':'2026-09-10','ratio':2}]
    s['benchmark']['bars'][-1]['close']=262.5
    result=advance(research,r,s,cal,c())
    assert all(v['benchmark_outcomes']['5']['gross_return_fraction']==pytest.approx(.05) for v in result['cohorts'].values())
    s['benchmark']['security_id']='CHANGED'
    result=advance(research,r,s,cal,c())
    assert all(not v['benchmark_outcomes'] for v in result['cohorts'].values())


def test_provider_benchmark_shared_budget_and_arcx_only_in_research(tmp_path):
    p,rows,c=provider(tmp_path);p.rules['decision_contract_version']=2
    p.caps['securities']={'SPY':{'security_id':'TEST-SPY-ID','share_class':'fund','currency':'USD','exchange':'ARCX',
        'source_url':'https://example.test/TEST-security','valid_from':'2020-01-01','valid_through':'2027-01-01'}}
    original=deepcopy(p.session.values)
    p.session.values+=deepcopy(original)
    value=p.snapshot(rows,c())
    assert value['benchmark']['status']=='available' and value['benchmark']['symbol']=='SPY'
    assert len(p.session.calls)==4
    p.research_benchmark(c());p.snapshot(rows,c());assert len(p.session.calls)==4
    with pytest.raises(DataUnavailable,match='unsupported_exchange'):
        p.snapshot([{**rows[0],'exchange':'ARCX'}],c(),force=True)


def test_missing_benchmark_capability_is_explicit_and_primary_stays_usable(tmp_path):
    p,rows,c=provider(tmp_path);p.rules['decision_contract_version']=2
    value=p.snapshot(rows,c())
    assert value['quote']['price']==50 and not value['provider_conflict']
    assert value['benchmark']['status']=='unavailable'
    assert len(p.session.calls)==2


def test_missing_security_fields_defer_without_spending_provider_budget(tmp_path):
    p,rows,c=provider(tmp_path);p.rules['decision_contract_version']=2
    p.caps['securities']={'SPY':{'source_url':'https://example.test/TEST','valid_from':'2020-01-01','valid_through':'2027-01-01'}}
    assert p.research_benchmark(c())['status']=='unavailable'
    assert p.session.calls==[]
