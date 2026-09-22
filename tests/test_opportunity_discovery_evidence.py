"""Factual securities evidence only, using synthetic transactions and prices."""
from copy import deepcopy
import csv
import json
import pytest

from scripts import discovery_evidence as de
from scripts.opportunity_market import assess, ExchangeCalendar
from scripts.opportunity_common import utc
from opportunity_helpers import Clock, Market, trade, rules


def evidence(price=102):
    clock=Clock(); row=trade(first_observed_at_utc=trade()['observed_at_utc'],security_key='TEST')
    snapshot=Market(clock,price).snapshot([row],clock())
    market=assess([row],{},snapshot,clock(),rules(),ExchangeCalendar())
    values=de.opportunity_values([row],{},market,snapshot,clock(),rules(),ExchangeCalendar())
    return row,snapshot,market,values[row['trade_id']]


def test_percent_atr_lag_and_quote_provenance():
    row,snapshot,market,value=evidence()
    assert value['status']=='measured'
    assert value['transaction_to_discovery_percent']==pytest.approx(2)
    assert value['transaction_to_discovery_atr']==pytest.approx(.5)
    assert value['disclosure_lag_days']==99
    assert value['discovery_quote']['provider']=='TEST-market'
    assert value['discovery_quote_lag_seconds']==3600
    json.dumps(value,allow_nan=False)


def test_first_quote_is_frozen_across_later_prices_and_restart(tmp_path):
    row,snapshot,market,value=evidence()
    values=de.persist(tmp_path,[row],[],opportunities={'TEST':{de.FIELD:{row['trade_id']:value}}})
    prefix=(tmp_path/de.LEDGER).read_bytes()
    changed=deepcopy(value['discovery_quote']);changed['price']=120
    got=de.derive(row,value['transaction_reference'],changed,previous=de.load(tmp_path)[row['trade_id']],basis=snapshot)
    assert got==value
    de.persist(tmp_path,[row],[],opportunities={'TEST':{de.FIELD:{row['trade_id']:got}}})
    assert (tmp_path/de.LEDGER).read_bytes()==prefix


def test_later_transaction_never_reuses_ticker_first_discovery():
    row,snapshot,market,value=evidence()
    second={**row,'trade_id':'TEST-2','first_observed_at_utc':'2026-09-08T15:01:00Z'}
    got=de.opportunity_values([second],{},market,snapshot,Clock()(),rules(),ExchangeCalendar())['TEST-2']
    assert got['status']=='unknown' and got['discovery_quote'] is None


@pytest.mark.parametrize('change,reason',[
    ({'price':float('nan')},'missing_first_usable_discovery_quote'),
    ({'price':float('inf')},'missing_first_usable_discovery_quote'),
    ({'price':True},'missing_first_usable_discovery_quote'),
    ({'at':'2020-01-01T00:00:00Z'},'discovery_quote_provenance_incomplete'),
    ({'provider':None},'discovery_quote_provenance_incomplete'),
    ({'quality':'unknown'},'discovery_quote_provenance_incomplete'),
])
def test_invalid_quotes_remain_unknown(change,reason):
    row,snapshot,market,value=evidence()
    got=de.derive(row,value['transaction_reference'],{**value['discovery_quote'],**change},basis=snapshot)
    assert got['status']=='unknown' and reason in got['reason_codes']
    assert got['transaction_to_discovery_percent'] is None
    json.dumps(got,allow_nan=False)


def test_missing_atr_does_not_invent_it_or_erase_supported_percent():
    row,snapshot,market,value=evidence()
    reference={**value['transaction_reference'],'atr':None}
    got=de.derive(row,reference,value['discovery_quote'],basis=snapshot)
    assert got['status']=='measured' and got['transaction_to_discovery_percent']==pytest.approx(2)
    assert got['transaction_to_discovery_atr'] is None and got['atr_status']=='unknown'


def test_corrected_date_currency_and_missing_basis_do_not_reuse_measurements():
    row,snapshot,market,value=evidence()
    for modified,basis in [({**row,'transaction_date':'2026-06-02'},snapshot),
                           (row,{**snapshot,'currency':'EUR'}),(row,{})]:
        got=de.derive(modified,value['transaction_reference'],value['discovery_quote'],basis=basis)
        assert got['status']=='unknown'


def test_legacy_evidence_preserved_with_unknown_quality_no_current_quote_backfill(tmp_path):
    row=trade()
    old={'trade_id':row['trade_id'],'analysis_id':'TEST-analysis','analyzed_at_utc':'2026-09-08T15:00:00Z',
         'market':{'current_price':102,'transaction_date_close':100,'providers':['TEST-market'],
                   'quote_timestamp_utc':'2026-09-08T15:00:00Z','atr_14':4,'data_status':'complete'}}
    values=de.persist(tmp_path,[row],[old])
    got=values[row['trade_id']]
    assert got['status']=='unknown'
    assert got['retained_market_evidence']['current_price']==102
    later={**old,'analyzed_at_utc':'2026-09-09T15:00:00Z','market':{**old['market'],'current_price':140}}
    got=de.persist(tmp_path,[row],[later,old])[row['trade_id']]
    assert got['retained_market_evidence']['current_price']==102
    assert got['transaction_to_discovery_percent'] is None
    de.write_exports(values,tmp_path)
    exported=json.loads((tmp_path/'information-value-at-discovery.json').read_text())
    assert exported['records'][0][de.FIELD]==got
    with (tmp_path/'information-value-at-discovery.csv').open(newline='') as f:
        assert json.loads(next(csv.DictReader(f))[de.FIELD])==got


def test_sales_supported_but_non_exchange_assets_excluded(tmp_path):
    row,snapshot,market,value=evidence(price=98)
    sale={**row,'transaction_type':'Sale'}
    assert de.derive(sale,value['transaction_reference'],value['discovery_quote'],basis=snapshot)['transaction_to_discovery_percent']==pytest.approx(-2)
    bond={**row,'trade_id':'TEST-bond','ticker':'','equity_like':False,'security_evidence':None}
    assert 'TEST-bond' not in de.persist(tmp_path,[bond],[])
