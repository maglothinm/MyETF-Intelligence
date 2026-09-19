from copy import deepcopy
from datetime import timedelta
import pytest

from scripts.opportunity_significance import normalize, significance, amount_range, net_interval
from opportunity_helpers import NOW, rules, trade


def result(rows, **kwargs):
    normalized,_=normalize(rows,NOW)
    return significance(normalized,normalized,rules(),**kwargs)


@pytest.mark.parametrize('minimum,qualified', [('99999',False),('100000',True),('100001',True)])
def test_individual_lower_bound(minimum,qualified):
    assert result([trade(amount_lower=minimum,amount_upper='1000000')])['meaningful'] is qualified


@pytest.mark.parametrize('amount,low,high', [('$100,000 - $250,000','100000','250000'),('Over $100,000','100000',None),('unknown',None,None),('$500',None,None),('Up to $50,000',None,'50000')])
def test_ranges(amount,low,high):
    assert amount_range({'amount':amount}) == {'lower':low,'upper':high,'disclosed':amount}


def test_accumulation_and_same_day_distinct_transactions():
    rows=[trade('TEST-a',amount='$25,000 - $50,000'),trade('TEST-b',amount='$25,000 - $50,000')]
    assert {r['route'] for r in result(rows)['routes']} == {'repeated_accumulation'}
    ambiguous=[{k:v for k,v in r.items() if k!='source_transaction_id'} for r in rows]
    assert not result(ambiguous)['meaningful']
    assert not result(rows,eligible_ids={'TEST-b'})['meaningful']


def test_household_collapsing_and_unresolved_ownership():
    rows=[trade(str(i),owner=owner,amount='$40,000 - $50,000') for i,owner in enumerate(['Self','Spouse','Dependent'])]
    assert not result(rows)['meaningful']
    for i,r in enumerate(rows): r['filer_id']='TEST-'+str(i)
    assert 'collective_buying' in {r['route'] for r in result(rows)['routes']}
    rows[2]['owner']='Unknown'
    assert not result(rows)['meaningful']


@pytest.mark.parametrize('count,expected', [(9,False),(10,True)])
def test_relative_size_conservative_upper_history(count,expected):
    rows=[trade('prior-'+str(i),transaction_date='2026-05-'+str(i+1).zfill(2),amount='$1,000 - $12,500') for i in range(count)]
    rows.append(trade(amount='$25,000 - $50,000'))
    routes=result(rows)['routes']
    assert any(r['route']=='relative_size' for r in routes) is expected


def test_transaction_cluster_is_not_age_window():
    rows=[trade('a',amount='$25,000 - $50,000',transaction_date='2026-06-01'),trade('b',amount='$25,000 - $50,000',transaction_date='2026-07-01')]
    value=result(rows)
    assert value['meaningful'] and value['transaction_span_days']==30 and value['observation_span_days']==0
    rows[1]['transaction_date']='2026-07-02'
    assert not result(rows)['meaningful']


def test_copies_amendments_cutoff_and_order():
    old=trade('old')
    copy=trade('copy',duplicate_of='old')
    amended=trade('new',amends_trade_id='old',amount='$1,000 - $15,000')
    normalized,excluded=normalize([old,copy,amended],NOW)
    assert [r['trade_id'] for r in normalized]==['new']
    assert not significance(normalized,normalized,rules())['meaningful']
    assert normalize([amended,copy,old],NOW)==(normalized,excluded)
    amended['observed_at_utc']=(NOW+timedelta(days=1)).isoformat()
    assert result([old,amended])['meaningful']


def test_sell_dominated_activity_and_open_net_bounds():
    rows=[trade(str(i),filer_id='TEST-'+str(i),amount='$40,000 - $50,000') for i in range(3)]
    rows.append(trade('sale',transaction_type='Sale',amount='$200,000 - $250,000'))
    value=result(rows)
    assert not value['meaningful'] and value['net_interval']['sell_dominated']
    assert value['net_interval']['lower']=='-130000'
    rows[-1]['amount']='Over $200,000'
    assert result(rows)['net_interval']['lower'] is None


def test_security_share_class_and_identity_are_explicit():
    a=trade('a',amount='$25,000 - $50,000')
    b=trade('b',amount='$25,000 - $50,000',share_class='preferred')
    normalized,_=normalize([a,b],NOW)
    assert len({r['security_key'] for r in normalized})==2
    for field in ('filer_id','security_evidence'):
        raw=trade(); raw.pop(field)
        assert not result([raw])['meaningful']


@pytest.mark.parametrize('updates', [{'parse_confidence':'low'},{'equity_like':False},{'amount_lower':'NaN','amount_upper':'Infinity'},{'source_url':None},{'transaction_date':'bad'}])
def test_required_quality_never_manufactures_qualification(updates):
    assert not result([trade(**updates)])['meaningful']
