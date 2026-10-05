"""Research progress and actionable next steps, separate from investment gates."""
from .opportunity_common import number, timestamp, utc


def disposition(evidence, dossier, now):
    coverage = evidence.get('coverage_detail') or {}
    facts = evidence.get('fundamentals') or {}
    annual = facts.get('annual_eps') or {}
    eps = number(annual.get('value'))
    fact_at = timestamp(facts.get('observed_at'))
    status = dossier.get('status')
    result = {'status':'blocked', 'investment_review_complete':False,
              'method_screen_complete':False, 'as_of':utc(now),
              'sections_reviewed':coverage.get('sections_reviewed',0),
              'sections_total':coverage.get('sections_total',0),
              'last_substantive_progress_at':coverage.get('last_substantive_progress_at'),
              'next_action':'Resolve the stated source or identity requirement; no investment conclusion is available.'}
    if status == 'thesis_invalidated' and evidence.get('status') == 'contradicted' and coverage.get('complete') is True:
        result.update(status='rejected_thesis',investment_review_complete=True,
                      next_action='Review the cited contradictory facts; do not treat the original thesis as supported.')
    elif eps is not None and eps <= 0 and annual.get('accession') and facts.get('source_url') and fact_at and fact_at <= now:
        result.update(status='unsupported_valuation_method',method_screen_complete=True,
            reason='The reported annual EPS reference is nonpositive; the installed EPS-multiple model cannot value this case.',
            reference={'value':eps,'accession':annual['accession'],'source_url':facts['source_url'],'observed_at':facts['observed_at']},
            next_action='Use a separately reviewed valuation method or human analysis. This is not a rejection of the investment; source research may continue.')
    elif status in ('ready_for_human_review','watching') and evidence.get('status') == 'sufficient' and coverage.get('complete') is True:
        result.update(status='ready_for_human_review' if status=='ready_for_human_review' else 'watching_entry',
            investment_review_complete=True,method_screen_complete=True,
            next_action='Review the complete case and all current gates before deciding.' if status=='ready_for_human_review' else 'Watch the stated entry ceiling and invalidation conditions; obtain a fresh price before action.')
    elif coverage.get('pending_documents'):
        result.update(status='research_in_progress_with_coverage_gaps',
            next_action='Continue reviewing available sections; resolve the listed documents before claiming complete issuer coverage.',
            pending_documents=coverage['pending_documents'])
    elif result['sections_reviewed']:
        result.update(status='research_in_progress',next_action='Continue the remaining section reviews, then verify the company case and current entry.')
    elif evidence.get('reason'):
        result['reason'] = evidence['reason']
    return result
