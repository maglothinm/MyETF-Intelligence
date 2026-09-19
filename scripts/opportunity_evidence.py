"""Current SEC-source contradiction review through the existing bounded analyst API.

Issuer coverage is explicitly SEC material filings, not a claim of all news or
all investment risk. Incomplete/truncated source retrieval cannot clear a gate.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import re

from bs4 import BeautifulSoup

from .opportunity_common import DataUnavailable, day, timestamp, utc


class SourceReviewer:
    def __init__(self, config, rules, market, caps, clock, *, analyze=None):
        self.config,self.rules,self.market,self.caps,self.clock = config,rules,market,caps,clock
        self.analyze=analyze

    def __call__(self, rows, membership_hash, now):
        from . import ai_filing_analyst as analyst
        mapping=(self.caps.get('securities') or {}).get(rows[0].get('ticker')) or {}
        cik=str(mapping.get('cik') or '')
        if not cik.isdigit() or not self.config.sec_user_agent or not self.config.openai_api_key:
            raise DataUnavailable('SEC_identity_user_agent_or_evidence_model_unavailable')
        headers={'User-Agent':self.config.sec_user_agent,'Accept-Encoding':'gzip, deflate'}
        url=f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json'
        payload=self.market.get(url,headers=headers)
        recent=(payload.get('filings') or {}).get('recent') or {}
        dates=recent.get('filingDate') or []
        forms=recent.get('form') or []
        accessions=recent.get('accessionNumber') or []
        documents=recent.get('primaryDocument') or []
        if not dates or not (len(dates)==len(forms)==len(accessions)==len(documents)):
            raise DataUnavailable('SEC_recent_filings_coverage_incomplete')
        start=now.date()-timedelta(days=self.rules['context_days'])
        if any(not day(d) for d in dates):
            raise DataUnavailable('SEC_filing_dates_invalid')
        if min(day(d) for d in dates) > start and (payload.get('filings') or {}).get('files'):
            raise DataUnavailable('SEC_context_requires_additional_history')
        selected=[i for i,d in enumerate(dates) if day(d) and start <= day(d) <= now.date() and forms[i] in ('8-K','8-K/A','10-K','10-K/A','10-Q','10-Q/A','6-K','20-F')]
        if len(selected)>self.rules['evidence_document_budget']:
            raise DataUnavailable('issuer_document_review_budget_exhausted')
        sources=[{'url':url,'id':'SEC-submissions:'+cik,'observed_at':utc(self.clock()),'published_at':None,'coverage':'SEC recent material filings'}]
        texts=[]
        for i in selected:
            if not re.fullmatch(r'[0-9-]+',accessions[i]) or not re.fullmatch(r'[A-Za-z0-9_.-]+',documents[i]):
                raise DataUnavailable('unsafe_SEC_document_locator')
            doc=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accessions[i].replace("-","")}/{documents[i]}'
            self.market.budget.consume()
            try:
                response=self.market.session.get(doc,headers=headers,timeout=self.config.request_timeout)
                response.raise_for_status()
            except Exception as exc:
                raise DataUnavailable('issuer_document_unavailable:'+type(exc).__name__) from exc
            text=BeautifulSoup(response.text,'html.parser').get_text(' ',strip=True)
            if len(text)>self.rules['evidence_document_characters']:
                raise DataUnavailable('issuer_document_exceeds_complete_review_budget')
            sources.append({'url':doc,'id':accessions[i],'published_at':dates[i],'precision':'date',
                            'observed_at':utc(self.clock()),'sha256':hashlib.sha256(response.content).hexdigest()})
            texts.append({'url':doc,'form':forms[i],'text':text})
        parser_clear=True
        reports={r.get('report_id') for r in rows}
        for directory in (self.config.legislative_dir,self.config.executive_dir):
            if not directory:
                continue
            queue = directory/'pending-review.jsonl'
            try:
                reviews = [json.loads(line) for line in queue.read_text(encoding='utf-8').splitlines() if line.strip()] if queue.exists() else []
                if any(not isinstance(value, dict) for value in reviews):
                    raise ValueError('parser queue record is not an object')
            except (OSError, ValueError) as exc:
                raise DataUnavailable('parser_review_queue_unreadable') from exc
            for review in reviews:
                if review.get('report_id') in reports or review.get('ticker') == rows[0].get('ticker'):
                    parser_clear=False
        if not parser_clear:
            raise DataUnavailable('unresolved_parser_evidence')
        sources += [{'url':r['source_url'],'id':r['trade_id'],'observed_at':r['observed_at_utc'],'published_at':r.get('filed_date'),'precision':'date'} for r in rows]
        context={'task':'Review current contradictions to the disclosed buying thesis using only the supplied source evidence. Reassess a possible price return after a prior excursion. Report all unresolved contradictory evidence. No catalyst is required. Do not infer absence of risk beyond these checked sources. Scores will not be used for eligibility.',
                 'transaction':rows[0],'disclosed_activity':rows,'issuer_documents':texts,'checked_sources':sources,
                 'issuer_coverage_from':start.isoformat(),'issuer_coverage_through':utc(now)}
        try:
            response=(self.analyze or analyst.openai_analyze)(context,replace(self.config,web_search_enabled=False),analyst.load_schema(self.config.schema_path))
        except analyst.AnalystError as exc:
            raise DataUnavailable('evidence_review_deferred:'+type(exc).__name__) from exc
        value=response.payload
        cited=value.get('evidence_sources') or []
        allowed={s['url'] for s in sources}
        supported=bool(cited) and all(c.get('url') in allowed for c in cited)
        confidence=value.get('confidence')
        complete=supported and isinstance(confidence,(float,int)) and confidence>=self.rules['evidence_min_confidence'] and value.get('external_context_status') == 'found'
        contradictions=value.get('contradictory_evidence') or []
        checked=self.clock()
        return {'status':'contradicted' if complete and contradictions else 'sufficient' if complete else 'incomplete',
                'checked_at':utc(checked),'valid_until':utc(checked+timedelta(hours=self.rules['evidence_max_hours'])),
                'membership_hash':membership_hash,'coverage':{'disclosures':True,'issuer':complete,'parser':parser_clear},
                'sources':sources,'contradictions':contradictions,'summary':value.get('analysis_summary'),
                'return_review_cleared':bool(complete and not contradictions),
                'scope':'retained disclosures, relevant parser queue, complete bounded SEC material filings; no claim of all news coverage',
                'model_response_id':getattr(response,'response_id',None)}
