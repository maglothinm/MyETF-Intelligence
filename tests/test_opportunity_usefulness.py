"""Offline regressions for #255. TEST fixtures only; no credentials or live calls."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
from types import SimpleNamespace
from scripts.opportunity_common import utc, DataUnavailable, digest
from scripts.opportunity_providers import capabilities, enrich_identities
from scripts.opportunity_review_v2 import InvestmentSourceReviewer
from scripts.opportunity_disposition import disposition
from scripts.opportunity_dashboard import compact_projection
from scripts.opportunity_significance import normalize
from opportunity_helpers import Clock, trade, rules
from test_ai_filing_analyst_hardened import _config
from test_opportunity_decision_v2 import FakeSourceMarket, case_fixture


def test_expired_feed_keeps_only_proven_historical_identity(tmp_path):
    c=Clock(); raw=trade(); tx=raw['transaction_date']
    cap={'version':1,'verified_at':utc(c()-timedelta(days=2)), 'valid_until':utc(c()-timedelta(days=1)),
         'verification_reference':'TEST independent receipt', 'finnhub_realtime_verified':True,
         'alphavantage_daily_adjusted_verified':False,'massive_basic_verified':True,
         'securities':{'TEST':{'security_id':'TEST-FIGI','share_class':'TEST-common','currency':'USD','exchange':'XNAS',
                              'source_url':'https://example.test/identity','valid_from':tx,'valid_through':(c()-timedelta(days=1)).date().isoformat(),'cik':'123'}},'filers_by_report':{}}
    (tmp_path/'opportunity-provider-capabilities.json').write_text(json.dumps(cap))
    assert capabilities(tmp_path,c())=={}
    ids=capabilities(tmp_path,c(),historical_identity_only=True)
    assert 'finnhub_realtime_verified' not in ids and 'massive_basic_verified' not in ids
    enriched=enrich_identities([raw],ids,c())[0]
    assert enriched['security_id']=='TEST-FIGI'
    fresh={**raw,'transaction_date':c().date().isoformat()};fresh.pop('security_id',None);fresh.pop('security_evidence',None)
    assert 'security_evidence' not in enrich_identities([fresh],ids,c())[0]
    bad={**raw,'equity_like':False};bad.pop('security_id',None);bad.pop('security_evidence',None)
    assert 'security_evidence' not in enrich_identities([bad],ids,c())[0]
    assert cap['valid_until']==utc(c()-timedelta(days=1))


def test_future_receipt_does_not_establish_historical_identity(tmp_path):
    c=Clock()
    cap={'version':1,'verified_at':utc(c()+timedelta(hours=1)),'valid_until':utc(c()+timedelta(days=1)),
         'verification_reference':'TEST','finnhub_realtime_verified':True,'alphavantage_daily_adjusted_verified':False,
         'securities':{},'filers_by_report':{}}
    (tmp_path/'opportunity-provider-capabilities.json').write_text(json.dumps(cap))
    assert capabilities(tmp_path,c(),historical_identity_only=True)=={}


def test_oversized_first_document_does_not_starve_other_sections(tmp_path):
    c=Clock();cfg=replace(_config(tmp_path),sec_user_agent='TEST test@example.test')
    market=FakeSourceMarket(c,filing_count=2);cache={'version':1,'issuers':{}}
    calls=[]; oversized=[]
    def model(context,config,schema,**kwargs):
        src=context['source'];calls.append(src['source_id'])
        return SimpleNamespace(payload={'reviewed':True,'limitations':[],
            'claims':[{'claim_id':src['source_id'],'kind':'fact','text':src['text'],
                       'references':[{'source_id':src['source_id'],'quote':src['text']}]}]})
    rows=normalize([trade()],c())[0]
    first=market.accessions[-1].replace('-','')
    for n in range(2):
        reviewer=InvestmentSourceReviewer(cfg,rules(evidence_document_budget=4),market,{'securities':{'TEST':{'cik':'123'}}},c,cache=cache,analyze=model)
        reviewer._pace=lambda:None
        original=reviewer._document
        def text(url):
            if first in url and url.endswith('test.htm'):
                oversized.append(url);raise DataUnavailable('issuer_document_byte_safety_limit')
            return original(url)
        reviewer._document=text
        result=reviewer(rows,'TEST-membership',c())
        assert result['status']=='incomplete' and result['coverage']['issuer'] is False
        assert result['coverage_detail']['sections_reviewed'] > 0
        assert result['coverage_detail']['pending_documents']
        assert result['coverage_detail']['last_substantive_progress_at']
        c.advance()
    assert len(oversized)==1  # durable cooldown, no download on every tick
    assert len(calls)==1  # completed source section not paid for twice


def test_one_document_budget_still_makes_section_progress_before_inventory_complete(tmp_path):
    c=Clock();cfg=replace(_config(tmp_path),sec_user_agent='TEST test@example.test')
    market=FakeSourceMarket(c,filing_count=6);cache={'version':1,'issuers':{}}
    def model(context,*args,**kwargs):
        src=context['source'];return SimpleNamespace(payload={'reviewed':True,'limitations':[],
            'claims':[{'claim_id':src['source_id'],'kind':'fact','text':src['text'],
                       'references':[{'source_id':src['source_id'],'quote':src['text']}]}]})
    rows=normalize([trade()],c())[0]
    results=[]
    for _ in range(2):
        reviewer=InvestmentSourceReviewer(cfg,rules(evidence_document_budget=1),market,{'securities':{'TEST':{'cik':'123'}}},c,cache=cache,analyze=model)
        reviewer._pace=lambda:None
        results.append(reviewer(rows,'TEST',c()));c.advance()
    assert results[-1]['coverage_detail']['sections_reviewed']>0
    assert results[-1]['coverage']['issuer'] is False
    assert results[-1]['coverage_detail']['documents_downloaded']<6


def test_unsupported_eps_is_not_investment_rejection_or_completed_review():
    c=Clock();e={'fundamentals':{'annual_eps':{'value':-0.06,'accession':'TEST-annual'},'source_url':'https://example.test/facts','observed_at':utc(c())}}
    d=disposition(e,{'status':'needs_evidence'},c())
    assert d['status']=='unsupported_valuation_method'
    assert d['method_screen_complete'] and not d['investment_review_complete']
    assert 'not a rejection' in d['next_action']
    assert disposition({}, {'status':'needs_evidence'},c())['status']=='blocked'


def test_index_preserves_ids_and_does_not_mutate_or_copy_large_evidence():
    original={'mode':'shadow','schema_version':1,'records':[{'opportunity_id':'TEST','evaluation_id':'TEST-evaluation',
        'lifecycle':'needs_review','transactions':[{'raw_row':'TEST '*10000}], 'reason_codes':['a']*20,
        'research_disposition':{'status':'blocked','investment_review_complete':False}}]}
    before=deepcopy(original);index=compact_projection(original)
    assert original==before
    assert index['records'][0]['opportunity_id']=='TEST' and index['records'][0]['evaluation_id']=='TEST-evaluation'
    assert index['records'][0]['reason_count']==20 and 'transactions' not in index['records'][0]
    assert len(json.dumps(index)) < len(json.dumps(original))/10


def test_native_current_capability_cannot_authorize_another_historical_security(tmp_path):
    from scripts.opportunity_providers import MarketProvider, RequestBudget
    c=Clock();p=MarketProvider(_config(tmp_path),rules(),None,{'version':1,'securities':{}},c,RequestBudget(80))
    import pytest
    with pytest.raises(DataUnavailable,match='current_security_identity_not_verified'):
        p.snapshot([trade()],c())


def test_limitation_adjudication_preserves_original_and_keeps_material_gaps(tmp_path):
    from test_opportunity_decision_v2 import case_fixture
    c=Clock();cfg=replace(_config(tmp_path),sec_user_agent='TEST test@example.test')
    market=FakeSourceMarket(c,filing_count=1);cache={'version':1,'issuers':{}}
    r=rules(evidence_model_budget=4)
    def model(context,*args,**kwargs):
        if 'original_limitations' in context:
            return SimpleNamespace(payload={'supported':False,'unsupported_claim_ids':[], 'limitations':['TEST material missing fact']})
        src=context['source']
        return SimpleNamespace(payload={'reviewed':True,'limitations':['TEST unresolved material customer commitment'],
            'claims':[{'claim_id':src['source_id'],'kind':'fact','text':src['text'],
                       'references':[{'source_id':src['source_id'],'quote':src['text']}]}]})
    reviewer=InvestmentSourceReviewer(cfg,r,market,{'securities':{'TEST':{'cik':'123'}}},c,cache=cache,analyze=model);reviewer._pace=lambda:None
    result=reviewer(normalize([trade()],c())[0],'TEST',c())
    assert result['status']=='incomplete'
    review=next(iter(next(iter(cache['issuers'].values()))['documents'].values()))['reviews']['0']
    assert review['limitations']==['TEST unresolved material customer commitment']
    assert len(review['limitation_reviews'])==1
    assert result['reason']=='issuer_section_review_has_unresolved_limits'
