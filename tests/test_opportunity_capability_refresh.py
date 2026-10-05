"""TEST-only capability lifecycle and streaming regression checks."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace
import pytest
from opportunity_helpers import Clock, rules
from test_ai_filing_analyst_hardened import _config
from scripts.opportunity_common import DataUnavailable, OpportunityError, digest, utc
from scripts.opportunity_capability_refresh import refresh, parse_quote_contract, matching_metadata, validate_cache, NAME
from scripts.opportunity_document import stream_document, RAW_LIMIT, TEXT_LIMIT
from scripts.opportunity_providers import RequestBudget

DESCRIPTION='Get real-time quote data for US stocks. Constant polling is not recommended.'
DOC=json.dumps({'/quote':{'get':{'operationId':'quote','premium':None,'description':DESCRIPTION}}})


class Response:
    def __init__(self,body=b'',status=200,headers=None):
        self.body=body;self.status_code=status;self.headers=headers or {};self.closed=False
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def close(self): self.closed=True
    def json(self): return json.loads(self.body)
    def iter_content(self,n):
        for start in range(0,len(self.body),n): yield self.body[start:start+n]


class Session:
    def __init__(self,c): self.c=c;self.calls=[];self.quote_age=0;self.status=200
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if 'docs/api/' in url: return Response(DOC.encode())
        return Response(json.dumps({'t':self.c().timestamp()-self.quote_age,'c':100}).encode(),self.status)


def setup(tmp_path):
    c=Clock();cfg=_config(tmp_path);cfg.ai_dir.mkdir(parents=True,exist_ok=True)
    cfg=replace(cfg,finnhub_api_key='TEST-finnhub',sec_user_agent='TEST test@example.test')
    mapping={'security_id':'TEST-FIGI','share_class':'TEST-share','currency':'USD','exchange':'XNAS',
             'source_url':'https://api.massive.com/v3/reference/tickers/TEST','valid_from':'2026-01-01','valid_through':'2026-09-07','cik':'123'}
    seed={'version':1,'verified_at':utc(c()-timedelta(days=2)),'valid_until':utc(c()-timedelta(days=1)),
          'verification_reference':'TEST-independent-seed','finnhub_realtime_verified':True,'massive_basic_verified':True,
          'alphavantage_daily_adjusted_verified':False,'securities':{'TEST':mapping},'filers_by_report':{}}
    (cfg.ai_dir/'opportunity-provider-capabilities.json').write_text(json.dumps(seed))
    class History:
        def __init__(self): self.calls=[];self.conflict=False
        def metadata(self,ticker):
            self.calls.append('metadata')
            return {'ticker':ticker,'active':True,'type':'CS','primary_exchange':'XNAS','composite_figi':'WRONG' if self.conflict else 'TEST-FIGI',
                    'share_class_figi':'TEST-share','currency_name':'usd','cik':'123'}
        def history(self,row,now):
            self.calls.append('history');return {'bars':[{'close':100}],'history_coverage_end':'2026-09-04','source_pages':[{'payload_hash':'TEST'}]}
    return c,cfg,seed,Session(c),History(),{'OPPORTUNITY_REFRESH_CAPABILITIES':'true','MASSIVE_API_KEY':'TEST-massive'}


def test_contract_parser_rejects_changed_or_premium_endpoint():
    assert parse_quote_contract(DOC)['operation_id']=='quote'
    with pytest.raises(DataUnavailable): parse_quote_contract(DOC.replace('null','"Premium"'))
    with pytest.raises(DataUnavailable): parse_quote_contract(DOC.replace('real-time','delayed'))
    with pytest.raises(DataUnavailable): parse_quote_contract('no supported structured contract')


def test_genuine_observation_required_and_repeat_is_cached(tmp_path):
    c,cfg,seed,s,h,env=setup(tmp_path)
    report,caps,_=refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)
    assert report['status']=='verified' and caps['finnhub_realtime_verified']
    assert caps['securities']['TEST']['valid_through']==c().date().isoformat()
    before=(len(s.calls),len(h.calls));c.advance()
    report,caps,_=refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)
    assert report['status']=='current' and (len(s.calls),len(h.calls))==before
    assert json.loads((cfg.ai_dir/'opportunity-provider-capabilities.json').read_text())==seed
    validate_cache(json.loads((cfg.ai_dir/NAME).read_text()))


@pytest.mark.parametrize('age',[301,-1])
def test_stale_or_future_quote_never_renews(tmp_path,age):
    c,cfg,seed,s,h,env=setup(tmp_path);s.quote_age=age
    report,caps,_=refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)
    assert report['status']=='blocked' and caps=={}
    assert report['failures']['TEST']=='fresh_regular_session_quote_not_observed'


def test_new_identity_conflict_withdraws_previously_successful_observation(tmp_path):
    c,cfg,seed,s,h,env=setup(tmp_path)
    _,caps,_=refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h);assert caps
    # Advance to the next regular session while the 24-hour observation remains
    # valid. A new-day identity check fails and must withdraw current capability.
    c.value+=timedelta(hours=23,minutes=30);h.conflict=True
    report,caps,_=refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)
    assert caps=={} and report['failures']['TEST']=='refreshed_security_identity_conflict'


def test_closed_session_no_probe_and_off_or_live_no_auto_activation(tmp_path):
    c,cfg,seed,s,h,env=setup(tmp_path);c.value=c().replace(hour=12)
    report,caps,_=refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)
    assert report['status']=='awaiting_regular_session_verification' and not s.calls and not h.calls
    assert not (cfg.ai_dir/NAME).exists()
    for mode in ('off','live'):
        report,caps,_=refresh(cfg,rules(mode=mode),s,env,c,RequestBudget(80),history_client=h)
        assert report['status']=='disabled' and caps is None


def test_cache_tampering_is_fatal_not_a_success(tmp_path):
    c,cfg,seed,s,h,env=setup(tmp_path);refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)
    path=cfg.ai_dir/NAME;value=json.loads(path.read_text());value['securities']['TEST']['mapping']['security_id']='CHANGED';path.write_text(json.dumps(value))
    with pytest.raises(OpportunityError): refresh(cfg,rules(),s,env,c,RequestBudget(80),history_client=h)


def test_stream_large_markup_complete_text_without_raw_memory_copy():
    body=b'<html>'+b'<div data-padding="'+b'x'*3_100_000+b'">Revenue rose &amp; margins improved.</div><p>Material risk remains.</p></html>'
    response=Response(body)
    value=stream_document(SimpleNamespace(get=lambda *a,**k:response),'https://www.sec.gov/Archives/edgar/data/123/test.htm','TEST',1)
    assert value['raw_bytes']>3_000_000 and value['text']=='Revenue rose & margins improved. Material risk remains.'
    assert value['complete'] and response.closed and value['sha256']


def test_stream_network_chunks_preserve_words_and_multibyte_characters():
    text='Test café earnings &amp; risk.'
    response=Response(('<p>'+text+'</p>').encode())
    response.iter_content=lambda n:(response.body[i:i+1] for i in range(len(response.body)))
    result=stream_document(SimpleNamespace(get=lambda *a,**k:response),'https://www.sec.gov/Archives/edgar/data/123/test.htm','TEST',1)
    assert result['text']=='Test café earnings & risk.'


def test_stream_rejects_transport_text_and_encoding_limits():
    for response in (Response(b'x',headers={'Content-Length':str(RAW_LIMIT+1)}),Response(b'<p>'+b'x'*(TEXT_LIMIT+1)+b'</p>'),Response(b'abc',headers={'Content-Type':'text/html; charset=utf-16'})):
        with pytest.raises(DataUnavailable): stream_document(SimpleNamespace(get=lambda *a,**k:response),'https://www.sec.gov/Archives/edgar/data/123/test.htm','TEST',1)
        assert response.closed
