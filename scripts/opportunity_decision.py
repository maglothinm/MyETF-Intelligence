"""Evidence-addressable investment cases; scenarios are assumptions, not predictions."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import re
from typing import Mapping
from .opportunity_common import digest, number, timestamp, utc


def _text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def verify_claims(claims, sources, cutoff):
    catalog = {s.get('source_id'): s for s in sources if isinstance(s, dict)}
    verified, errors, seen = [], [], set()
    for claim in claims:
        cid = claim.get('claim_id')
        if not isinstance(cid, str) or not cid or cid in seen or claim.get('kind') not in ('fact','inference','assumption') or not _text(claim.get('text')):
            errors.append('invalid_or_duplicate_claim'); continue
        seen.add(cid)
        refs = claim.get('references') or []
        if not refs:
            errors.append('claim_without_source:' + cid); continue
        matches = []
        for ref in refs:
            src = catalog.get(ref.get('source_id')) or {}
            observed = timestamp(src.get('observed_at'))
            quote, body = _text(ref.get('quote')), _text(src.get('text'))
            if not observed or observed > cutoff or not src.get('url') or len(quote) < 12 or quote not in body:
                errors.append('unmatched_claim_excerpt:' + cid); continue
            start = body.find(quote)
            matches.append({'source_id':src['source_id'],'url':src['url'],'quote':quote,
                'start':start,'end':start+len(quote),'document_sha256':src.get('document_sha256'),
                'text_sha256':digest(body),'published_at':src.get('published_at'),'observed_at':src['observed_at']})
        if len(matches) == len(refs):
            verified.append({**deepcopy(claim),'references':matches,'verification':'exact_excerpt_match; semantic review required'})
    return verified, sorted(set(errors))


def classify_findings(findings, claims):
    byid = {c['claim_id']:c for c in claims}
    groups = {k:[] for k in ('thesis_breaker','uncertainty','risk','support')}
    errors = []
    for f in findings:
        kind, cid = f.get('kind'), f.get('claim_id')
        if kind not in groups or cid not in byid or not _text(f.get('implication')):
            errors.append('unsupported_finding'); continue
        if kind == 'thesis_breaker' and byid[cid]['kind'] != 'fact':
            groups['uncertainty'].append({**f,'kind':'uncertainty'})
        else:
            groups[kind].append(deepcopy(f))
    return groups, errors


def annual_eps(payload: Mapping, cutoff: datetime):
    tag = ((payload.get('facts') or {}).get('us-gaap') or {}).get('EarningsPerShareDiluted') or {}
    eligible = []
    for v in (tag.get('units') or {}).get('USD/shares', []):
        try:
            start, end, filed = [datetime.fromisoformat(v[k]).date() for k in ('start','end','filed')]
        except (ValueError,KeyError,TypeError):
            continue
        n = number(v.get('val'))
        if n is None or not 330 <= (end-start).days <= 385 or filed > cutoff.date() or end > cutoff.date():
            continue
        if v.get('form') not in ('10-K','10-K/A','20-F','20-F/A') or not v.get('accn'):
            continue
        eligible.append((end,filed,str(v['accn']),n,v))
    if not eligible:
        return None
    end, filed, accn, value, raw = max(eligible,key=lambda t:(t[0],t[1],t[2]))
    if (cutoff.date()-end).days > 550:
        return None
    return {'tag':'us-gaap:EarningsPerShareDiluted','unit':'USD/shares','period_start':raw['start'],
        'period_end':raw['end'],'filed_date':raw['filed'],'accession':accn,'value':value,
        'kind':'reported_full_year_GAAP_reference_not_forecast'}


def validate_case(case, claims, fundamentals):
    errors, ids = [], {c['claim_id'] for c in claims}
    for key in ('thesis','why_now','shareholder_economics','invalidation','review_conditions'):
        item = case.get(key) or {}; refs = item.get('claim_ids') or []
        if not _text(item.get('text')) or not refs or any(cid not in ids for cid in refs):
            errors.append('missing_supported_' + key)
    if case.get('method') != 'annual_eps_multiple':
        errors.append('valuation_method_not_supported')
    ref = fundamentals.get('annual_eps') or {}; n = number(ref.get('value'))
    if n is None or n <= 0:
        errors.append('positive_annual_eps_reference_unavailable')
    if case.get('reference_accession') != ref.get('accession'):
        errors.append('valuation_reference_mismatch')
    values = []
    for label in ('bear','base','bull'):
        s = (case.get('scenarios') or {}).get(label) or {}
        eps, mult = number(s.get('annual_eps')), number(s.get('multiple'))
        if eps is None or mult is None or eps < 0 or not 0 < mult <= 100:
            errors.append('invalid_' + label + '_scenario'); continue
        if not _text(s.get('assumption')) or not s.get('claim_ids') or any(cid not in ids for cid in s['claim_ids']):
            errors.append('unsupported_' + label + '_assumptions')
        values.append(eps*mult)
    if len(values) == 3 and not values[0] < values[1] < values[2]:
        errors.append('unordered_scenario_values')
    h = case.get('horizon_sessions')
    if isinstance(h,bool) or not isinstance(h,int) or h not in (20,60,120):
        errors.append('unsupported_review_horizon')
    return sorted(set(errors))


def build_dossier(evidence, quote, now, rules, snapshot=None):
    case, claims = evidence.get('investment_case') or {}, evidence.get('verified_claims') or []
    findings = evidence.get('findings') or {}
    reasons = list(evidence.get('case_errors') or [])
    if evidence.get('decision_contract_version') != 2:
        reasons.append('investment_case_contract_missing')
    reasons += validate_case(case,claims,evidence.get('fundamentals') or {})
    ref = (evidence.get('fundamentals') or {}).get('annual_eps') or {}
    for action in (snapshot or {}).get('adjustment_events', []):
        if action.get('kind') == 'split' and str(action.get('date','')) > str(ref.get('filed_date','')):
            reasons.append('split_after_reported_eps_requires_reconciled_valuation')
    price, at = number(quote.get('price')), timestamp(quote.get('at'))
    if not at or at > now or (now-at).total_seconds() > rules['quote_max_seconds'] or price is None or price <= 0:
        reasons.append('decision_quote_unavailable_or_stale')
    values = {}; entry_max = rr = upside = downside = None
    if not reasons:
        values = {k:float(Decimal(str(v['annual_eps']))*Decimal(str(v['multiple']))) for k,v in case['scenarios'].items()}
        bear, base = values['bear'], values['base']
        minimum_rr, minimum_upside = rules.get('decision_min_reward_risk',2.0), rules.get('decision_min_upside',0.15)
        entry_max = min(base/(1+minimum_upside),(base+minimum_rr*bear)/(1+minimum_rr))
        upside, downside = base/price-1, (price-bear)/price
        if price <= bear:
            reasons.append('bear_case_not_below_entry_requires_reassessment')
        else:
            rr = (base-price)/(price-bear)
        if price > entry_max:
            reasons.append('scenario_entry_not_attractive')
    if findings.get('thesis_breaker'):
        status = 'thesis_invalidated'
    elif findings.get('uncertainty') or reasons or evidence.get('status') != 'sufficient':
        status = 'watching' if reasons == ['scenario_entry_not_attractive'] else 'needs_evidence'
    else:
        status = 'ready_for_human_review'
    return {'schema_version':2,'status':status,'case':deepcopy(case),'claims':deepcopy(claims),
        'findings':deepcopy(findings),'source_coverage':deepcopy(evidence.get('coverage_detail') or {}),
        'fundamentals':deepcopy(evidence.get('fundamentals') or {}),'scenario_prices':values,
        'entry_max':entry_max,'base_upside_fraction':upside,'bear_downside_fraction':downside,
        'scenario_reward_risk':rr,'price':price,'quote_at':quote.get('at'),'evaluated_at':utc(now),
        'analysis_completed_at':evidence.get('checked_at'),'reason_codes':sorted(set(reasons)),
        'human_review_required':True,'transaction_verification':'row consistency checked; confirm original document before investment',
        'capital_authorization':'not provided; no position size or trade authorization',
        'risk_notice':'Scenario loss is not a maximum loss. Total loss and gap risk remain possible. Stops are not guaranteed.',
        'valuation_notice':'Illustrative source-anchored assumptions, not target probabilities or proven investment advantage.'}
