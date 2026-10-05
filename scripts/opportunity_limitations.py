"""Resolve section limitations against the verified complete issuer claim catalog.

A reference missing from one segment may be present in a reviewed companion
exhibit. No missing source or material uncertainty is cleared by omission.
"""
from copy import deepcopy
from .opportunity_common import DataUnavailable, OpportunityError, digest, timestamp, utc

KINDS = ['generic_scope_notice','ordinary_disclosed_risk','resolved_by_evidence','unresolved']
ITEM = {'type':'object','additionalProperties':False,'required':['limitation_id','classification','explanation','claim_ids'],
        'properties':{'limitation_id':{'type':'string'},'classification':{'type':'string','enum':KINDS},
                      'explanation':{'type':'string'},'claim_ids':{'type':'array','items':{'type':'string'}}}}
SCHEMA = {'type':'object','additionalProperties':False,'required':['resolutions','limitations'],
          'properties':{'resolutions':{'type':'array','items':ITEM},
                        'limitations':{'type':'array','items':{'type':'string'}}}}


def item(source_id, index, text):
    value={'source_id':source_id,'index':index,'text':text}
    return {'limitation_id':digest(value),**value}


def check_result(result, limitations, claims):
    expected={v['limitation_id'] for v in limitations}
    allowed={v['claim_id'] for v in claims}
    seen=set();reasons=[]
    for row in result.get('resolutions',[]):
        lid=row.get('limitation_id');refs=row.get('claim_ids') or []
        kind=row.get('classification')
        if lid not in expected or lid in seen or kind not in KINDS or not str(row.get('explanation','')).strip():
            reasons.append('invalid_limitation_resolution');continue
        seen.add(lid)
        if any(ref not in allowed for ref in refs):
            reasons.append('unsupported_limitation_claim_reference')
        if kind in ('resolved_by_evidence','ordinary_disclosed_risk') and not refs:
            reasons.append('limitation_resolution_requires_evidence')
        if kind=='unresolved':
            reasons.append('material_issuer_limitation_unresolved')
    if seen!=expected:
        reasons.append('limitation_resolution_incomplete')
    if result.get('limitations'):
        reasons.append('limitation_review_has_unresolved_limits')
    return sorted(set(reasons))


def resolve(limitations, claims, sources, slot, model, clock):
    if not limitations:
        return {'status':'not_required','original_limitations':[],'resolutions':[]},[]
    source_refs=[{k:s.get(k) for k in ('source_id','url','document_sha256','observed_at')} for s in sources]
    key=digest({'version':1,'limitations':limitations,'claims':claims,'sources':source_refs})
    reviews=slot.setdefault('catalog_limitation_reviews',{})
    if not isinstance(reviews,dict):
        raise OpportunityError('invalid issuer limitation review catalog')
    if key not in reviews:
        if len(reviews)>=256:
            raise DataUnavailable('limitation_review_catalog_capacity_requires_review')
        context={'task':('Resolve every listed section limitation against the supplied complete reviewed issuer claim catalog. '
            'A companion exhibit or another segment may supply information absent from the original segment. '
            'Use only exact supplied claim IDs and their quotations. Every limitation must receive exactly one resolution. '
            'resolved_by_evidence requires cited claims that actually resolve the specific missing information; merely '
            'mentioning an exhibit is not evidence of its contents. ordinary_disclosed_risk requires supporting claims. '
            'generic_scope_notice is only a statement of a segment or method scope, never a substitute for a missing '
            'material fact or risk. Unavailable required metrics, exhibits, facts, conflicting interpretations or inability '
            'to decide must remain unresolved. Do not invent facts or infer complete risk coverage from silence. '
            'The original limitations remain immutable. This check does not authorize investment or replace the company case.'),
            'original_limitations':limitations,'verified_claims':claims,'reviewed_sources':source_refs}
        result=model(context,SCHEMA)
        reviews[key]={'review_key':key,'completed_at':utc(clock()),'result':result,'result_hash':digest(result)}
    record=reviews[key]
    if record.get('review_key')!=key or not timestamp(record.get('completed_at')) or timestamp(record['completed_at'])>clock() or record.get('result_hash')!=digest(record.get('result')):
        raise OpportunityError('issuer limitation review integrity failure')
    reasons=check_result(record['result'],limitations,claims)
    report={'status':'unresolved' if reasons else 'resolved_within_reviewed_scope',
            'original_limitations':deepcopy(limitations),'review':deepcopy(record),
            'notice':'Source-bound model interpretation; human verification remains required.'}
    return report,reasons
