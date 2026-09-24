"""Free-stack TEST fixtures. No credentials, real HTTP calls or notifications."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import json
import pytest
from scripts.opportunity_common import DataUnavailable, OpportunityError, read_json, utc
from scripts.opportunity_massive import MassiveHistory, SharedPacer, validate_cache, CACHE_NAME, SCOPE
from scripts.opportunity_providers import MarketProvider, RequestBudget
from opportunity_helpers import Clock, rules, trade
from test_ai_filing_analyst_hardened import _config


class Response:
    def __init__(self,payload,code=200,headers=None):self.payload=payload;self.status_code=code;self.headers=headers or {};self.closed=False
    def iter_content(self,chunk_size):yield json.dumps(self.payload).encode()
    def close(self):self.closed=True
    def raise_for_status(self):assert self.status_code==200
    def json(self):return self.payload


class Session:
    def __init__(self,pages):self.pages=list(pages);self.calls=[]
    def get(self,url,**kw):
        self.calls.append((url,kw))
        value=self.pages.pop(0)
        if isinstance(value,Exception):raise value
        return value if isinstance(value,Response) else Response(value)


class Pacer:
    def __init__(self):self.calls=0;self.backoffs=[]
    def acquire(self):self.calls+=1
    def backoff(self,v):self.backoffs.append(v)


def daily(date,price=100):
    at=datetime.fromisoformat(date).replace(tzinfo=ZoneInfo('America/New_York'))
    return {'t':int(at.timestamp()*1000),'o':price,'h':price+2,'l':price-2,'c':price,'v':1000}


def payloads():
    return [{'status':'OK','ticker':'TEST','adjusted':False,'resultsCount':2,'results':[daily('2026-06-01',100),daily('2026-09-04',50)]},
            {'status':'OK','results':[{'id':'TEST-split','ticker':'TEST','execution_date':'2026-08-03','split_from':1,'split_to':2}]},
            {'status':'OK','results':[{'id':'TEST-dividend','ticker':'TEST','ex_dividend_date':'2026-08-10','currency':'USD','cash_amount':1.25}]}]


def client(tmp_path,pages=None,**kw):
    cfg=SimpleNamespace(ai_dir=tmp_path,request_timeout=(1,1))
    return MassiveHistory(cfg,rules(history_provider='massive'),Clock(),RequestBudget(80),
        environment={'MASSIVE_API_KEY':'TEST-NOT-A-REAL-KEY'},session=Session(payloads() if pages is None else pages),pacer=Pacer(),**kw)


def test_split_basis_dividends_and_current_day_not_in_history(tmp_path):
    p=client(tmp_path);v=p.history(trade(),Clock()())
    assert [b['close'] for b in v['bars']]==[50,50]
    assert v['basis']=='split_adjusted' and v['actions_complete']
    assert v['adjustment_events'][1]['entry_price_adjusted'] is False
    assert v['history_session_scope']==SCOPE and 'quote' not in v
    assert v['bars'][0]['window_start_at']=='2026-06-01T04:00:00Z'
    assert all('apiKey' not in url and 'TEST-NOT-A-REAL-KEY' not in url for url,_ in p.session.calls)
    assert all(k['allow_redirects'] is False for _,k in p.session.calls)
    assert all(k['headers']['Authorization'].startswith('Bearer ') for _,k in p.session.calls)
    assert p.requests==3 and p.pacer.calls==3


def test_cache_survives_new_instance_without_more_requests(tmp_path):
    p=client(tmp_path);first=p.history(trade(),Clock()())
    second=client(tmp_path,[]);assert second.history(trade(),Clock()())==first
    assert second.requests==0 and second.hits==3
    body=(tmp_path/CACHE_NAME).read_text();assert 'TEST-NOT-A-REAL-KEY' not in body


def test_cache_tampering_cannot_clear_history(tmp_path):
    p=client(tmp_path);p.history(trade(),Clock()())
    value=read_json(tmp_path/CACHE_NAME);next(iter(value['entries'].values()))['complete']=False
    (tmp_path/CACHE_NAME).write_text(json.dumps(value))
    with pytest.raises(OpportunityError,match='integrity'):client(tmp_path)


def test_rolling_two_year_request_does_not_follow_old_trade_outside_free_plan(tmp_path):
    p=client(tmp_path);v=p.history(trade(transaction_date='2015-01-01'),Clock()())
    url=p.session.calls[0][0]
    assert '/2024-09-10/2026-09-07' in url
    assert v['history_coverage_start']=='2024-09-10'
    assert not any(b['date']=='2015-01-01' for b in v['bars'])


def test_partial_pagination_resumes_without_claiming_complete(tmp_path):
    first={'status':'OK','results':[{'id':'a'}],'next_url':'https://api.massive.com/stocks/v1/splits?cursor=two'}
    p=client(tmp_path,[first]);p.rules['massive_requests_per_run']=1
    with pytest.raises(DataUnavailable,match='budget'):p.pages('/stocks/v1/splits',{'ticker':'TEST'},'/stocks/v1/splits')
    entry=next(iter(p.cache['entries'].values()));assert not entry['complete'] and len(entry['pages'])==1
    q=client(tmp_path,[{'status':'OK','results':[{'id':'b'}]}])
    pages=q.pages('/stocks/v1/splits',{'ticker':'TEST'},'/stocks/v1/splits')
    assert len(pages)==2 and len(q.session.calls)==1 and 'cursor=two' in q.session.calls[0][0]


@pytest.mark.parametrize('url',['http://api.massive.com/stocks/v1/splits','https://evil.test/stocks/v1/splits','https://api.massive.com:443/stocks/v1/splits','https://me:secret@api.massive.com/stocks/v1/splits','https://api.massive.com/v3/reference/tickers/TEST','https://api.massive.com/stocks/v1/splits#key'])
def test_unsafe_pagination_is_not_followed(tmp_path,url):
    p=client(tmp_path,[{'status':'OK','results':[],'next_url':url}])
    with pytest.raises(DataUnavailable,match='pagination'):p.pages('/stocks/v1/splits',{},'/stocks/v1/splits')
    assert len(p.session.calls)==1


def test_next_url_key_not_persisted_or_forwarded(tmp_path):
    p=client(tmp_path,[{'status':'OK','results':[],'next_url':'https://api.massive.com/stocks/v1/splits?cursor=x&apiKey=LEAK'}, {'status':'OK','results':[]}])
    p.pages('/stocks/v1/splits',{},'/stocks/v1/splits')
    assert 'LEAK' not in (tmp_path/CACHE_NAME).read_text()
    assert 'LEAK' not in p.session.calls[1][0]


def test_rate_limit_is_shared_and_survives_restart(tmp_path):
    now=[100.0];sleep=lambda seconds:now.__setitem__(0,now[0]+seconds)
    p=SharedPacer(tmp_path/'rate.sqlite','TEST-key',clock=lambda:now[0],sleep=sleep)
    calls=[]
    for i in range(7):
        q=p if i%2 else SharedPacer(tmp_path/'rate.sqlite','TEST-key',clock=lambda:now[0],sleep=sleep)
        q.acquire();calls.append(now[0])
    assert calls==[100,113,126,139,152,165,178]
    p.backoff(600)
    with pytest.raises(DataUnavailable,match='backoff'):p.acquire()


def test_429_records_backoff_no_retry_or_paid_fallback(tmp_path):
    p=client(tmp_path,[Response({},429,{'Retry-After':'90'})])
    with pytest.raises(DataUnavailable,match='429'):p.history(trade(),Clock()())
    assert p.pacer.backoffs==[90] and len(p.session.calls)==1


@pytest.mark.parametrize('code',[301,401,403,500])
def test_http_errors_do_not_become_empty_success(tmp_path,code):
    p=client(tmp_path,[Response({'error':'TEST-secret'},code)])
    with pytest.raises(DataUnavailable) as err:p.history(trade(),Clock()())
    assert 'TEST-secret' not in str(err.value)


@pytest.mark.parametrize('change',[{'adjusted':True},{'ticker':'OTHER'},{'resultsCount':500},{'results':[daily('2026-06-01'),daily('2026-06-01')]},{'results':[daily('2026-09-08')]},{'results':[dict(daily('2026-06-01'),h=1)]}])
def test_invalid_history_is_rejected(tmp_path,change):
    pages=payloads();pages[0].update(change);p=client(tmp_path,pages)
    with pytest.raises(DataUnavailable):p.history(trade(),Clock()())


def test_corporate_action_currency_and_ratio_are_checked(tmp_path):
    pages=payloads();pages[1]['results'][0]['split_from']=0
    with pytest.raises(DataUnavailable,match='split_ratio'):client(tmp_path,pages).history(trade(),Clock()())


def test_key_is_required_without_network_or_account_creation(tmp_path):
    with pytest.raises(DataUnavailable,match='key_required'):
        MassiveHistory(SimpleNamespace(ai_dir=tmp_path),rules(),Clock(),RequestBudget(10),environment={},session=Session([]),pacer=Pacer())


def test_missing_split_page_never_uses_unadjusted_bars_as_comparable(tmp_path):
    pages=payloads();pages[1]={'status':'ERROR','results':[]}
    with pytest.raises(DataUnavailable):client(tmp_path,pages).history(trade(),Clock()())


def test_provider_massive_route_does_not_require_alpha_key(tmp_path):
    c=Clock();cfg=replace(_config(tmp_path),finnhub_api_key='TEST',alphavantage_api_key='')
    q={'t':c().timestamp(),'c':50,'pc':50,'h':51,'l':49}
    provider=MarketProvider(cfg,rules(history_provider='massive'),Session([q]),{'massive_basic_verified':True,'finnhub_realtime_verified':True},c,RequestBudget(80))
    provider.massive_history=client(tmp_path/'history')
    value=provider.snapshot([trade()],c())
    assert value['quote']['provider']=='finnhub' and value['bars'][0]['close']==50
    assert all('alphavantage' not in u for u,_ in provider.session.calls)


def test_massive_basic_capability_missing_keeps_entry_unavailable(tmp_path):
    c=Clock();provider=MarketProvider(_config(tmp_path),rules(history_provider='massive'),Session([]),{},c,RequestBudget(10))
    with pytest.raises(DataUnavailable,match='capabilities'):provider.snapshot([trade()],c())


def test_daily_aggregate_boundary_is_not_fabricated_regular_close(tmp_path):
    from scripts.opportunity_market import completed_bars,ExchangeCalendar
    p=client(tmp_path);v=p.history(trade(),Clock()())
    bars=completed_bars(v,Clock()(),ExchangeCalendar())
    assert bars[0]['at']=='2026-06-02T04:00:00Z'
    assert bars[0]['session_scope']==SCOPE


def test_daily_reference_date_is_retained_for_threshold(tmp_path):
    from scripts.opportunity_market import assess,ExchangeCalendar
    from scripts.opportunity_significance import normalize
    from scripts.opportunity_threshold import assess_purchase
    c=Clock();row=trade();rows=normalize([row],c())[0]
    snap=client(tmp_path).history(row,c())
    snap['quote']={'price':50,'at':utc(c()),'observed_at':utc(c()),'provider':'TEST-finnhub','kind':'realtime','precision':'second','feed_delay_seconds':0}
    market=assess(rows,{},snap,c(),rules(),ExchangeCalendar())
    reference=market['anchors']['trades'][row['trade_id']]
    assert reference['reference_date']==row['transaction_date']
    result=assess_purchase(row,reference,{},snap,c(),.08,ExchangeCalendar())
    assert 'purchase_reference_correction_requires_review' not in result['reason_codes']
    assert result['session_scope']==SCOPE


def test_setup_private_key_does_not_overwrite_existing(tmp_path):
    from scripts.opportunity_massive_setup import private_key_file
    p=tmp_path/'private.json';p.write_text('existing')
    with pytest.raises(ValueError,match='overwritten'):private_key_file(p,'TEST-key')
    assert p.read_text()=='existing'


def test_setup_key_file_is_readable_only_after_explicit_creation(tmp_path):
    from scripts.opportunity_massive_setup import private_key_file
    from scripts.opportunity_massive import load_key
    p=tmp_path/'private'/'massive.json';private_key_file(p,'TEST-ONLY')
    assert load_key({'MASSIVE_API_KEY_FILE':str(p)})=='TEST-ONLY'


def test_actual_defaults_select_free_source_but_never_activate():
    from scripts.opportunity_common import load_rules
    config=load_rules()
    assert config['history_provider']=='massive' and config['mode']=='off'


def test_free_history_runs_existing_decision_cycle_and_preserves_state(tmp_path):
    from scripts.opportunity_engine import cycle
    from scripts.opportunity_market import ExchangeCalendar
    from scripts.opportunity_state import save,load
    from opportunity_helpers import state
    from test_opportunity_decision_v2 import case_fixture
    c=Clock();cal=ExchangeCalendar();cfg=replace(_config(tmp_path),finnhub_api_key='TEST',alphavantage_api_key='')
    s=state(cfg.ai_dir,c);before=(cfg.ai_dir/'state.json').read_bytes()
    dates=cal.sessions('2024-09-10','2026-09-04')
    history_pages=[{'status':'OK','ticker':'TEST','adjusted':False,'resultsCount':len(dates),'results':[daily(d,100) for d in dates]}, {'status':'OK','results':[]}, {'status':'OK','results':[]}]
    quote={'t':c().timestamp(),'c':100,'pc':100,'h':102,'l':98}
    r=rules(history_provider='massive',decision_contract_version=2)
    market=MarketProvider(cfg,r,Session([quote,quote,quote,quote]),{'massive_basic_verified':True,'finnhub_realtime_verified':True},c,RequestBudget(80))
    market.massive_history=MassiveHistory(cfg,r,c,market.budget,environment={'MASSIVE_API_KEY':'TEST-ONLY'},session=Session(history_pages),pacer=Pacer())
    class CaseEvidence:
        def review(self,rows,mh,now,force=False):
            evidence,_=case_fixture(c);evidence['membership_hash']=mh;return evidence
    cycle(s,[trade()],r,c,cal,market,CaseEvidence(),channels=['simulation'])
    record=next(iter(s['opportunities'].values()))
    assert record['lifecycle']=='opportunity_available',record['reason_codes']
    assert record['investment_dossier']['status']=='ready_for_human_review'
    assert record['market']['history_session_scope']==SCOPE
    assert all('alphavantage' not in u for u,_ in market.session.calls)
    save(cfg.ai_dir,s);again=load(cfg.ai_dir,c())
    assert again['events']==s['events'] and len(again['intents'])==1
    assert (cfg.ai_dir/'state.json').read_bytes()==before
    assert market.massive_history.requests==3
