"""TEST provider contracts; responses are in-memory fixtures, never HTTP calls."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from scripts.opportunity_common import DataUnavailable, OpportunityError, utc, write_json
from scripts.opportunity_providers import MarketProvider, RequestBudget, EvidenceProvider, capabilities, enrich_identities
from scripts.opportunity_evidence import SourceReviewer
from scripts.opportunity_significance import normalize
from opportunity_helpers import Clock, Evidence, rules, trade
from test_ai_filing_analyst_hardened import _config


class Session:
    def __init__(self,values): self.values=list(values); self.calls=[]
    def get(self,*a,**kw):
        self.calls.append((a,kw)); value=self.values.pop(0)
        if isinstance(value,Exception): raise value
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:value)


def provider(tmp_path,quote=None):
    c=Clock(); cfg=replace(_config(tmp_path),finnhub_api_key='TEST',alphavantage_api_key='TEST')
    raw=lambda price,split,div:{'1. open':str(price),'2. high':str(price+1),'3. low':str(price-1),'4. close':str(price),'7. dividend amount':str(div),'8. split coefficient':str(split)}
    session=Session([quote or {'t':c().timestamp(),'c':50,'pc':50,'h':51,'l':49}, {'Time Series (Daily)':{'2026-09-04':raw(50,2,1),'2026-09-03':raw(100,1,0)}}])
    caps={'finnhub_realtime_verified':True,'alphavantage_daily_adjusted_verified':True}
    return MarketProvider(cfg,rules(),session,caps,c,RequestBudget(10)),normalize([trade()],c())[0],c


def test_provider_split_basis_dividend_separation_actual_time_and_cache(tmp_path):
    p,rows,c=provider(tmp_path); value=p.snapshot(rows,c())
    assert value['bars'][1]['close']==50 and value['bars'][0]['close']==50
    assert value['adjustment_events'][1]['entry_price_adjusted'] is False
    assert value['quote']['at']==utc(c()) and not value['provider_conflict']
    assert p.snapshot(rows,c())==value and len(p.session.calls)==2


def test_provider_conflicts_and_missing_entitlements_never_fallback(tmp_path):
    p,rows,c=provider(tmp_path,{'t':Clock()().timestamp(),'c':50,'pc':90})
    assert p.snapshot(rows,c())['provider_conflict']
    p.caps={}
    with pytest.raises(DataUnavailable,match='entitlements'): p.snapshot(rows,c(),force=True)
    assert len(p.session.calls)==2


def test_provider_missing_time_and_request_budget(tmp_path):
    p,rows,c=provider(tmp_path,{'c':50})
    with pytest.raises(DataUnavailable,match='timestamp'): p.snapshot(rows,c())
    assert len(p.session.calls)==1
    p.budget=RequestBudget(0)
    with pytest.raises(DataUnavailable,match='budget'): p.snapshot(rows,c())


def test_capability_record_strict_boolean_expiry_and_exact_mapping(tmp_path):
    c=Clock(); path=tmp_path/'opportunity-provider-capabilities.json'
    value={'version':1,'verified_at':utc(c()),'valid_until':utc(c()+timedelta(days=1)),
           'verification_reference':'TEST-only','finnhub_realtime_verified':False,'alphavantage_daily_adjusted_verified':False,
           'securities':{},'filers_by_report':{}}
    write_json(path,value); assert capabilities(tmp_path,c())==value
    c.advance(minutes=24*60+1); assert capabilities(tmp_path,c())=={}
    value['finnhub_realtime_verified']='true'; write_json(path,value)
    with pytest.raises(OpportunityError): capabilities(tmp_path,c())
    raw=trade(security_id=None,security_evidence=None)
    assert enrich_identities([raw],{'securities':{'OTHER':{}}},c())[0]==raw


def test_evidence_cache_current_membership_and_bounded_review():
    c=Clock(); rows=normalize([trade()],c())[0]; e=Evidence(c); cached=e.review(rows,'one',c())
    calls=[]
    p=EvidenceProvider([cached],rules(),reviewer=lambda *a:calls.append(a) or cached,model_budget=1)
    assert p.review(rows,'one',c())==cached and not calls
    p.review(rows,'one',c(),force=True); assert len(calls)==1
    with pytest.raises(DataUnavailable): p.review(rows,'changed',c())


def test_sec_source_review_requires_current_complete_supported_evidence(tmp_path):
    c=Clock(); cfg=replace(_config(tmp_path),sec_user_agent='TEST example@example.test')
    rows=normalize([trade()],c())[0]
    payload={'filings':{'recent':{'filingDate':['2026-01-01'],'form':['10-K'],'accessionNumber':['1-2'],'primaryDocument':['test.htm']}}}
    market=SimpleNamespace(get=lambda *a,**kw:payload)
    def analyze(context,config,schema):
        assert not config.web_search_enabled
        return SimpleNamespace(payload={'confidence':0.9,'external_context_status':'found','evidence_sources':[{'url':context['checked_sources'][0]['url']}],
              'contradictory_evidence':[],'analysis_summary':'TEST checked sources only'},response_id='TEST-model')
    reviewer=SourceReviewer(cfg,rules(),market,{'securities':{'TEST':{'cik':'123'}}},c,analyze=analyze)
    result=reviewer(rows,'membership',c())
    assert result['status']=='sufficient' and all(result['coverage'].values())
    cfg.legislative_dir.mkdir(); (cfg.legislative_dir/'pending-review.jsonl').write_text('bad JSON')
    with pytest.raises(DataUnavailable,match='parser'): reviewer(rows,'membership',c())
    (cfg.legislative_dir/'pending-review.jsonl').write_text('')
    payload['filings']['recent']['filingDate']=['invalid']
    with pytest.raises(DataUnavailable,match='dates'): reviewer(rows,'membership',c())


def test_model_invented_sources_and_truncated_coverage_cannot_clear(tmp_path):
    c=Clock(); cfg=replace(_config(tmp_path),sec_user_agent='TEST')
    rows=normalize([trade()],c())[0]
    payload={'filings':{'recent':{'filingDate':['2026-09-01'],'form':['4'],'accessionNumber':['1-2'],'primaryDocument':['test.htm']}}}
    analyze=lambda *a:SimpleNamespace(payload={'confidence':1,'external_context_status':'found','evidence_sources':[{'url':'https://invented.test'}]})
    reviewer=SourceReviewer(cfg,rules(),SimpleNamespace(get=lambda *a,**kw:payload),{'securities':{'TEST':{'cik':'123'}}},c,analyze=analyze)
    assert reviewer(rows,'mh',c())['status']=='incomplete'
    payload['filings']['files']=[{'name':'older.json'}]
    with pytest.raises(DataUnavailable,match='additional_history'): reviewer(rows,'mh',c())
