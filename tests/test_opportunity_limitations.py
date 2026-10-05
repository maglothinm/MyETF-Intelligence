"""Offline TEST regressions: companion exhibits resolve only evidenced gaps."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import pytest
from opportunity_helpers import Clock, rules, trade
from test_ai_filing_analyst_hardened import _config
from test_opportunity_decision_v2 import FakeSourceMarket, case_fixture
from scripts.opportunity_common import OpportunityError, DataUnavailable
from scripts.opportunity_limitations import item, resolve, check_result
from scripts.opportunity_review_v2 import InvestmentSourceReviewer
from scripts.opportunity_significance import normalize


def fixture():
    limitations=[item('TEST-main:0',0,'Companion exhibit missing from this segment.')]
    claims=[{'claim_id':'TEST-exhibit-claim','kind':'fact','text':'TEST sales were 50.',
             'references':[{'source_id':'TEST-exhibit:0','quote':'TEST sales were 50.'}]}]
    sources=[{'source_id':'TEST-main:0','document_sha256':'a'*64}, {'source_id':'TEST-exhibit:0','document_sha256':'b'*64}]
    result={'resolutions':[{'limitation_id':limitations[0]['limitation_id'],'classification':'resolved_by_evidence',
                          'explanation':'The companion exhibit supplies the exact missing sales figure.','claim_ids':['TEST-exhibit-claim']}], 'limitations':[]}
    return limitations,claims,sources,result


def test_companion_claim_can_resolve_scope_gap_and_cache_is_reused():
    c=Clock();limits,claims,sources,result=fixture();slot={};calls=[];before=deepcopy(limits)
    def model(context,schema):
        calls.append(context)
        assert len(context['reviewed_sources'])==2
        assert context['verified_claims'][0]['claim_id']=='TEST-exhibit-claim'
        return result
    report,errors=resolve(limits,claims,sources,slot,model,c)
    assert not errors and report['status']=='resolved_within_reviewed_scope'
    assert limits==before and report['original_limitations']==before
    assert resolve(limits,claims,sources,slot,model,c)==(report,errors) and len(calls)==1


@pytest.mark.parametrize('change,expected',[
    ('missing_reference','limitation_resolution_requires_evidence'),
    ('invented_reference','unsupported_limitation_claim_reference'),
    ('missing_resolution','limitation_resolution_incomplete'),
    ('duplicate_resolution','invalid_limitation_resolution'),
    ('material_gap','material_issuer_limitation_unresolved'),
    ('review_gap','limitation_review_has_unresolved_limits')])
def test_missing_and_unsupported_evidence_never_clears(change,expected):
    limits,claims,sources,result=fixture()
    if change=='missing_reference': result['resolutions'][0]['claim_ids']=[]
    if change=='invented_reference': result['resolutions'][0]['claim_ids']=['invented']
    if change=='missing_resolution': result['resolutions']=[]
    if change=='duplicate_resolution': result['resolutions']*=2
    if change=='material_gap': result['resolutions'][0]['classification']='unresolved'
    if change=='review_gap': result['limitations']=['Unresolved material economic fact']
    assert expected in check_result(result,limits,claims)


def test_cache_tampering_is_fatal_and_new_exhibit_requires_new_review():
    c=Clock();limits,claims,sources,result=fixture();slot={};calls=[]
    model=lambda *args: calls.append(args) or result
    resolve(limits,claims,sources,slot,model,c)
    sources[1]['document_sha256']='c'*64
    resolve(limits,claims,sources,slot,model,c);assert len(calls)==2
    last=list(slot['catalog_limitation_reviews'].values())[-1]
    last['result']['limitations']=['tampered']
    with pytest.raises(OpportunityError): resolve(limits,claims,sources,slot,model,c)


def test_three_cycle_companion_review_completion(tmp_path):
    c=Clock();cfg=replace(_config(tmp_path),sec_user_agent='TEST test@example.test')
    market=FakeSourceMarket(c,filing_count=2);cache={'version':1,'issuers':{}}
    reference,_=case_fixture(c);calls=[]
    def model(context,config,schema,**kwargs):
        calls.append(context)
        if 'source' in context:
            src=context['source'];lim=['TEST companion information absent from this segment'] if '-000002/' in src['source_id'] else []
            payload={'reviewed':True,'limitations':lim,'claims':[{'claim_id':src['source_id'],'kind':'fact','text':src['text'],
                'references':[{'source_id':src['source_id'],'quote':src['text']}]}]}
        elif 'original_limitations' in context:
            assert len(context['reviewed_sources'])==2
            companion=next(v['claim_id'] for v in context['verified_claims'] if '-000001/' in v['claim_id'])
            payload={'resolutions':[{'limitation_id':v['limitation_id'],'classification':'resolved_by_evidence',
                'explanation':'TEST companion source supplies the missing information.','claim_ids':[companion]} for v in context['original_limitations']],'limitations':[]}
        elif 'proposal' in context:
            payload={'supported':True,'unsupported_claim_ids':[],'limitations':[]}
        else:
            case=deepcopy(reference['investment_case']);cid=context['claims'][0]['claim_id']
            for field in ('thesis','why_now','shareholder_economics','invalidation','review_conditions'): case[field]['claim_ids']=[cid]
            for scenario in case['scenarios'].values(): scenario['claim_ids']=[cid]
            payload={'investment_case':case,'findings':[],'limitations':[]}
        return SimpleNamespace(payload=kwargs['payload_validator'](payload))
    results=[]
    for _ in range(3):
        reviewer=InvestmentSourceReviewer(cfg,rules(evidence_model_budget=2),market,{'securities':{'TEST':{'cik':'123'}}},c,cache=cache,analyze=model)
        reviewer._pace=lambda:None
        results.append(reviewer(normalize([trade()],c())[0],'TEST-case',c()));c.advance()
    assert results[0]['status']=='incomplete' and results[0]['coverage_detail']['sections_reviewed']==2
    assert results[1]['status']=='incomplete'
    assert results[2]['status']=='sufficient'
    assert results[2]['limitation_resolution']['status']=='resolved_within_reviewed_scope'
    originals=[r['limitations'] for slot in cache['issuers'].values() for d in slot['documents'].values() for r in d['reviews'].values()]
    assert ['TEST companion information absent from this segment'] in originals
    assert len(calls)==5  # two sections, one catalog check, case, semantic check
