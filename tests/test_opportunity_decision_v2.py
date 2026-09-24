"""TEST-only investment cases. No production source, credentials or provider calls."""
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace
import pytest
from scripts.opportunity_common import utc, digest, DataUnavailable, OpportunityError, load_rules
from scripts.opportunity_decision import verify_claims, classify_findings, annual_eps, validate_case, build_dossier
from scripts.opportunity_input_quality import issues
from scripts.opportunity_review_v2 import InvestmentSourceReviewer, validate_cache, chunks
from scripts.opportunity_providers import EvidenceProvider, RequestBudget
from scripts.opportunity_engine import cycle
from scripts.opportunity_market import ExchangeCalendar
from scripts.opportunity_state import save, load
from opportunity_helpers import Clock, Market, Evidence, trade, rules, state


def case_fixture(clock):
    src={'source_id':'TEST-section','url':'https://example.test/TEST-source','text':'TEST net revenue grew and customer concentration remains a material risk.',
         'observed_at':utc(clock()),'published_at':'2026-09-01','document_sha256':'a'*64}
    claim={'claim_id':'TEST-claim','kind':'fact','text':'TEST revenue grew; customer concentration is a risk.',
           'references':[{'source_id':src['source_id'],'quote':src['text']}]}
    claims,errors=verify_claims([claim],[src],clock()); assert not errors
    statement={'text':'TEST company economics and conditions supported by the source; assumptions require human review.','claim_ids':['TEST-claim']}
    case={k:deepcopy(statement) for k in ('thesis','why_now','shareholder_economics','invalidation','review_conditions')}
    case.update(method='annual_eps_multiple',reference_accession='0001-26-000001',horizon_sessions=60,
        scenarios={k:{'annual_eps':eps,'multiple':mult,'assumption':'TEST forward assumption, not reported result.','claim_ids':['TEST-claim']}
                   for k,eps,mult in [('bear',6,15),('base',8,20),('bull',10,22)]})
    facts={'annual_eps':{'value':8,'accession':'0001-26-000001','filed_date':'2026-02-01'}}
    e=Evidence(clock).review([], 'TEST-membership',clock())
    e.update(decision_contract_version=2,investment_case=case,verified_claims=claims,fundamentals=facts,
             findings={'risk':[{'kind':'risk','claim_id':'TEST-claim','implication':'TEST concentration risk'}]},case_errors=[],
             coverage_detail={'documents_downloaded':1,'sections_total':1,'sections_reviewed':1,'complete':True,'scope':'TEST fixture evidence only'})
    return e,src


@pytest.mark.parametrize('row,reason',[
    (trade(amount='$250,001 - $50,000'),'inverted_disclosed_amount_range'),
    (trade(raw_row='TEST municipal bond [GS] P 08/19/2026 $250,001 - TEST Nike (NKE) [ST] S 08/27/2026 $15,001 - $50,000'),'multiple_source_transaction_rows'),
    (trade(raw_row='TEST dividend reinvestment'),'automatic_or_managed_purchase_not_discretionary_evidence'),
    (trade(asset_type='Stock Option'),'not_verified_common_stock'),
    (trade(raw_row='SP TEST (TEST) [ST] P 06/01/2026 09/01/2026 $100,000 - $250,000'),'source_owner_conflict'),
    (trade(raw_row='TEST (TEST) [ST] P 06/02/2026 09/01/2026 $100,000 - $250,000'),'source_transaction_date_conflict'),
    (trade(raw_row='TEST (OTHER) [ST] P 06/01/2026 09/01/2026 $100,000 - $250,000'),'source_ticker_conflict')])
def test_source_guards_preserve_input(row,reason):
    before=deepcopy(row); assert reason in issues(row); assert row==before


def test_valid_raw_purchase():
    assert issues(trade(raw_row='TEST Corporation (TEST) [ST] P 06/01/2026 09/01/2026 $100,000 - $250,000'))==[]


def test_forged_quote_future_source_and_duplicate_claims_fail():
    c=Clock(); e,s=case_fixture(c); claim=deepcopy(e['verified_claims'][0])
    claim['references'][0]['quote']='Invented supporting quotation'
    assert verify_claims([claim],[s],c())[1]
    claim=deepcopy(e['verified_claims'][0]); s['observed_at']=utc(c()+timedelta(seconds=1))
    assert verify_claims([claim],[s],c())[1]
    s['observed_at']=utc(c()); assert verify_claims([claim,claim],[s],c())[1]


def test_risk_is_not_invalidation_and_inference_cannot_be_fact_breaker():
    c=Clock(); e,_=case_fixture(c)
    groups,errors=classify_findings([{'kind':'risk','claim_id':'TEST-claim','implication':'concentration'}],e['verified_claims'])
    assert groups['risk'] and not groups['thesis_breaker'] and not errors
    e['verified_claims'][0]['kind']='inference'
    groups,_=classify_findings([{'kind':'thesis_breaker','claim_id':'TEST-claim','implication':'Inference only'}],e['verified_claims'])
    assert groups['uncertainty'] and not groups['thesis_breaker']


def test_eps_annual_units_dates_and_restatements():
    c=Clock(); value={'start':'2025-01-01','end':'2025-12-31','filed':'2026-02-01','form':'10-K','accn':'TEST-1','val':8}
    data={'facts':{'us-gaap':{'EarningsPerShareDiluted':{'units':{'USD/shares':[value,{**value,'filed':'2026-12-01','val':99},{**value,'start':'2025-10-01','val':2}]}}}}}
    assert annual_eps(data,c())['value']==8
    data['facts']['us-gaap']['EarningsPerShareDiluted']['units']={'USD':[value]}
    assert annual_eps(data,c()) is None


def test_scenarios_are_deterministic_and_no_size_or_order():
    c=Clock(); e,_=case_fixture(c); q={'at':utc(c()),'price':100}
    d=build_dossier(e,q,c(),rules(decision_contract_version=2))
    assert d['status']=='ready_for_human_review'
    assert d['scenario_prices']=={'bear':90,'base':160,'bull':220}
    assert d['entry_max']==pytest.approx(340/3)
    assert d['scenario_reward_risk']==pytest.approx(6)
    assert d['human_review_required'] and 'no position size' in d['capital_authorization']
    assert build_dossier(e,{**q,'price':120},c(),rules())['status']=='watching'
    assert build_dossier(e,{**q,'price':80},c(),rules())['status']=='needs_evidence'


def test_stale_price_missing_thesis_split_and_nonfinite_fail():
    c=Clock(); e,_=case_fixture(c); q={'at':utc(c()-timedelta(minutes=6)),'price':100}
    assert build_dossier(e,q,c(),rules())['status']=='needs_evidence'
    q={'at':utc(c()),'price':float('nan')}
    assert build_dossier(e,q,c(),rules())['status']=='needs_evidence'
    q={'at':utc(c()),'price':100}
    assert build_dossier(e,q,c(),rules(),{'adjustment_events':[{'kind':'split','date':'2026-08-01'}]})['status']=='needs_evidence'
    del e['investment_case']['thesis']
    assert build_dossier(e,q,c(),rules())['status']=='needs_evidence'


def test_low_model_confidence_does_not_make_facts_missing():
    c=Clock(); e,_=case_fixture(c); e['confidence']=0.01
    assert build_dossier(e,{'at':utc(c()),'price':100},c(),rules())['status']=='ready_for_human_review'


def test_incomplete_review_cache_is_resumed_not_cached_as_clear():
    c=Clock(); e=Evidence(c).review([],'x',c()); e['status']='incomplete'
    calls=[]; provider=EvidenceProvider([e],rules(),reviewer=lambda *a:calls.append(a) or e,model_budget=1)
    provider.review([],'x',c()); assert len(calls)==1


def test_production_config_cannot_select_legacy_decision_contract(tmp_path):
    import yaml
    r=load_rules(); r.pop('method_hash'); r['decision_contract_version']=1
    path=tmp_path/'rules.yml'; path.write_text(yaml.safe_dump(r))
    with pytest.raises(OpportunityError): load_rules(path)


def test_v2_requires_company_case_and_fresh_post_review_quote(tmp_path):
    c=Clock(); s=state(tmp_path/'ai',c); market=Market(c)
    class Review:
        def review(self,rows,membership_hash,now,force=False):
            c.advance(minutes=6)
            e,_=case_fixture(c); e['membership_hash']=membership_hash; return e
    r=rules(decision_contract_version=2)
    cycle(s,[trade()],r,c,ExchangeCalendar(),market,Review(),channels=['simulation'])
    item=next(iter(s['opportunities'].values()))
    assert item['lifecycle']=='opportunity_available' and item['gates']['investment_case']
    assert market.calls[-1][1] is True
    old=deepcopy(s['events']); save(tmp_path/'ai',s)
    c.advance(); s=load(tmp_path/'ai',c())
    e=Evidence(c)
    cycle(s,[trade()],r,c,ExchangeCalendar(),market,e,channels=['simulation'])
    item=next(iter(s['opportunities'].values()))
    assert item['lifecycle']=='needs_review' and not item['gates']['investment_case']
    assert s['events'][:len(old)]==old
    assert item['thesis_status']=='supported' and item['assessment_status']=='incomplete_or_stale'
    save(tmp_path/'ai',s)


class FakeSourceMarket:
    def __init__(self,clock,filing_count=6):
        self.clock=clock; self.budget=RequestBudget(1000); self.session=self; self.calls=[]
        self.accessions=[f'0000000123-26-{i:06d}' for i in range(1,filing_count+1)]
    def get(self,url,**kwargs):
        self.calls.append(url)
        if '/submissions/' in url:
            return {'filings':{'recent':{'filingDate':['2026-09-01']*len(self.accessions),'form':['8-K']*len(self.accessions),
                'accessionNumber':self.accessions,'primaryDocument':['test.htm']*len(self.accessions)}}}
        if '/companyfacts/' in url:
            return {'cik':123,'facts':{'us-gaap':{'EarningsPerShareDiluted':{'units':{'USD/shares':[
                {'start':'2025-01-01','end':'2025-12-31','filed':'2026-02-01','form':'10-K','accn':'0001-26-000001','val':8}]}}}}}
        if url.endswith('-index.html'):
            data=b'<table summary="Document Format Files"><tr><td>1</td><td>TEST</td><td><a href="test.htm">test.htm</a></td><td>8-K</td></tr></table>'
        else:
            data=('<p>TEST net revenue grew and customer concentration remains a material risk.</p>'*8).encode()
        return SimpleNamespace(status_code=200,raise_for_status=lambda:None,iter_content=lambda n:[data],close=lambda:None)


def test_resumable_review_exceeds_four_documents_and_character_limit(tmp_path):
    from dataclasses import replace
    from test_ai_filing_analyst_hardened import _config
    c=Clock(); cfg=replace(_config(tmp_path),sec_user_agent='TEST test@example.test')
    e,_=case_fixture(c); market=FakeSourceMarket(c); cache={'version':1,'issuers':{}}
    calls=[]
    def model(context,config,schema,**kwargs):
        calls.append(context['task'])
        if 'source' in context:
            src=context['source']; result={'reviewed':True,'limitations':[],
                'claims':[{'claim_id':src['source_id'],'kind':'fact','text':src['text'],
                           'references':[{'source_id':src['source_id'],'quote':src['text']}]}]}
        elif 'proposal' in context:
            result={'supported':True,'unsupported_claim_ids':[],'limitations':[]}
        else:
            assert 'disclosed_activity' not in context
            assert context['case_scope'].startswith('Company economics only')
            case=deepcopy(e['investment_case']); cid=context['claims'][0]['claim_id']
            for k in ('thesis','why_now','shareholder_economics','invalidation','review_conditions'): case[k]['claim_ids']=[cid]
            for sc in case['scenarios'].values(): sc['claim_ids']=[cid]
            result={'investment_case':case,'findings':[{'kind':'risk','claim_id':cid,'implication':'TEST ordinary risk'}],'limitations':[]}
        return SimpleNamespace(payload=kwargs['payload_validator'](result))
    r=rules(decision_contract_version=2,evidence_document_characters=200)
    from scripts.opportunity_significance import normalize
    rows=normalize([trade()],c())[0]
    incomplete=0
    for step in range(40):
        reviewer=InvestmentSourceReviewer(cfg,r,market,{'securities':{'TEST':{'cik':'123'}}},c,cache=cache,analyze=model)
        reviewer._pace=lambda:None
        result=reviewer(rows,'TEST-membership',c())
        cache=json.loads(json.dumps(cache)); validate_cache(cache)
        if result['status']=='sufficient': break
        incomplete+=1; c.advance()
    assert result['status']=='sufficient',result
    assert incomplete>2 and result['coverage_detail']['documents_downloaded']==6
    assert result['coverage_detail']['sections_total']>6
    assert result['findings']['risk'] and not result['contradictions']
    assert all(market.calls.count(u)==1 for u in set(market.calls) if u.endswith('test.htm'))
    assert len(calls)==result['coverage_detail']['sections_total']+2
    assert not (cfg.ai_dir/'opportunity-evidence-cache.json').exists()  # only owner persists cache


def test_cache_tampering_fails_and_chunks_cover_full_text():
    parts=chunks('TEST words '*100,100)
    assert ' '.join(parts)==' '.join(('TEST words '*100).split())
    cache={'version':1,'issuers':{'x':{'documents':{'d':{'chunks':['TEST'],'text_digest':'bad','reviews':{}}}}}}
    with pytest.raises(OpportunityError): validate_cache(cache)


def test_research_anchor_is_after_decision_not_old_transaction_quote():
    from scripts.opportunity_research import advance
    from scripts.opportunity_significance import normalize
    c=Clock(); cal=ExchangeCalendar(); market=Market(c); rows=normalize([trade()],c())[0]
    def record():
        snap=market.snapshot(rows,c())
        r={'opportunity_id':'TEST-opportunity','rule_hash':'a'*64,'mode':'shadow','ticker':'TEST',
           'security_id':'TEST-FIGI-1','share_class':'common','currency':'USD','lifecycle':'opportunity_available',
           'gates':{'meaningful_buying':True},'investment_dossier':{'status':'ready_for_human_review'},
           'market':{'quote':snap['quote'],'session':'regular'}}
        return r,snap
    r,snap=record(); research=advance(None,r,snap,cal,c())
    assert all(v['anchor'] is None for v in research['cohorts'].values())
    c.advance(minutes=30);r,snap=record();research=advance(research,r,snap,cal,c())
    anchors=[v['anchor'] for v in research['cohorts'].values()]
    assert all(v['lag_seconds']==1800 for v in anchors)
    c.value=c().replace(day=15,hour=21,minute=0)
    r,snap=record();research=advance(research,r,snap,cal,c())
    assert [v['anchor'] for v in research['cohorts'].values()]==anchors
    for v in research['cohorts'].values():
        assert v['outcomes']['5']['net_return_fraction']==pytest.approx(-0.001)
        assert v['outcomes']['5']['benchmark_relative_fraction'] is None
        assert '20' not in v['outcomes']
    before=deepcopy(research);snap['bars'][-1]['close']=200
    assert advance(research,r,snap,cal,c())==before  # Retained outcomes are not retrospectively rewritten.


def test_live_full_method_needs_accepted_delivery_before_anchor():
    from scripts.opportunity_research import advance
    from scripts.opportunity_significance import normalize
    c=Clock();cal=ExchangeCalendar();market=Market(c);rows=normalize([trade()],c())[0]
    snap=market.snapshot(rows,c())
    r={'opportunity_id':'TEST-opportunity','rule_hash':'a'*64,'mode':'live','security_id':'TEST-FIGI-1',
       'share_class':'common','currency':'USD','lifecycle':'opportunity_available','gates':{'meaningful_buying':True},
       'investment_dossier':{'status':'ready_for_human_review'},'market':{'quote':snap['quote'],'session':'regular'}}
    research=advance(None,r,snap,cal,c());c.advance()
    snap=market.snapshot(rows,c());r['market']['quote']=snap['quote'];research=advance(research,r,snap,cal,c())
    full=next(v for v in research['cohorts'].values() if v['cohort']=='full_method')
    assert full['anchor'] is None and full['decision_usable_at'] is None
    accepted=utc(c()); c.advance();snap=market.snapshot(rows,c());r['market']['quote']=snap['quote']
    research=advance(research,r,snap,cal,c(),intents={'TEST-event':{'opportunity_id':'TEST-opportunity','snapshot':{'rule_hash':'a'*64}}},
        deliveries={'TEST-event':{'simulation':{'status':'accepted','accepted_at':accepted}}})
    full=next(v for v in research['cohorts'].values() if v['cohort']=='full_method')
    assert full['decision_usable_at']==accepted and full['anchor']['at']>accepted


def test_cached_review_rechecks_issuer_changes():
    c=Clock();e=Evidence(c).review([],'x',c());calls=[]
    class Reviewer:
        def cache_is_current(self,*a): return False
        def __call__(self,*a): calls.append(a);return e
    p=EvidenceProvider([e],rules(),reviewer=Reviewer(),model_budget=1)
    p.review([],'x',c());assert len(calls)==1


def test_custom_structured_model_contract_is_validated(monkeypatch,tmp_path):
    from test_ai_filing_analyst_hardened import _config
    from scripts import ai_filing_analyst_hardened as h
    from scripts.opportunity_review_v2 import SECTION_SCHEMA
    from jsonschema import Draft202012Validator
    monkeypatch.setattr(h.legacy,'pace_openai_request',lambda:None)
    captured=[]
    def create(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(status='completed',incomplete_details=None,id='TEST-response',usage=None,
            output_text=json.dumps({'reviewed':True,'claims':[],'limitations':[]}))
    def validator(value):
        if list(Draft202012Validator(SECTION_SCHEMA).iter_errors(value)): raise ValueError('TEST schema error')
        return value
    result=h.openai_analyze({'TEST':True},_config(tmp_path),SECTION_SCHEMA,
        client_factory=lambda **kwargs:SimpleNamespace(responses=SimpleNamespace(create=create)),
        payload_validator=validator,instructions='TEST source evidence instructions')
    assert result.payload['reviewed'] is True
    assert captured[0]['instructions']=='TEST source evidence instructions'
    assert captured[0]['text']['format']['strict'] is True
