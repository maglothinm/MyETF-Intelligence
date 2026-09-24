"""Offline API usage accounting tests; reported usage is not an invoice."""
from dataclasses import replace
from types import SimpleNamespace
from decimal import Decimal
import json
import sqlite3
import pytest
from scripts import api_usage
from scripts.opportunity_common import ROOT,read_json
from test_ai_filing_analyst_hardened import _config


def response(**changes):
    value={'id':'resp_TEST','model':'gpt-5.6-terra','status':'completed','service_tier':'default',
      'usage':{'input_tokens':1000,'input_tokens_details':{'cached_tokens':200,'cache_write_tokens':100},
               'output_tokens':500,'output_tokens_details':{'reasoning_tokens':300}},'output':[]}
    value.update(changes);return value


def test_cached_input_and_reasoning_not_double_counted():
    data=api_usage.capture(response());assert data['status']=='reported'
    rates=read_json(ROOT/'config/api_usage_rates.json')
    cost=api_usage.estimate(data,'gpt-5.6-terra','default','2026-09-24T20:00:00Z',rates)
    assert Decimal(cost['estimated_token_cost_usd'])==Decimal('0.00769')
    assert data['reasoning_tokens']==300 and data['output_tokens']==500


def test_long_context_applies_to_entire_request():
    r=response();r['usage'].update(input_tokens=300000,input_tokens_details={'cached_tokens':0})
    cost=api_usage.estimate(api_usage.capture(r),'gpt-5.6-terra','default','2026-09-24T20:00:00Z',read_json(ROOT/'config/api_usage_rates.json'))
    assert Decimal(cost['estimated_token_cost_usd'])==Decimal('1.209')
    assert cost['rate_reference']['long_context_applied']


@pytest.mark.parametrize('usage',[None,{'input_tokens':False,'output_tokens':1}, {'input_tokens':1,'input_tokens_details':{'cached_tokens':2},'output_tokens':1}, {'input_tokens':1,'output_tokens':2}, {'input_tokens':2,'input_tokens_details':{'cached_tokens':0},'output_tokens':2,'output_tokens_details':{'reasoning_tokens':5}}])
def test_incomplete_or_impossible_usage_not_priced(usage):
    value=api_usage.capture(response(usage=usage))
    assert value['status']=='missing_or_inconsistent'
    assert api_usage.estimate(value,'gpt-5.6-terra','default','2026-09-24T20:00:00Z',read_json(ROOT/'config/api_usage_rates.json'))['estimated_token_cost_usd'] is None


@pytest.mark.parametrize('model,tier,at',[('unknown','default','2026-09-24T20:00:00Z'),('gpt-5.6-terra','priority','2026-09-24T20:00:00Z'),('gpt-5.6-terra','default','2025-01-01T00:00:00Z')])
def test_unknown_tariff_or_tier_is_not_zero(model,tier,at):
    result=api_usage.estimate(api_usage.capture(response()),model,tier,at,read_json(ROOT/'config/api_usage_rates.json'))
    assert result['estimated_token_cost_usd'] is None


def test_persisted_usage_dedupes_response_and_survives_instance(tmp_path,monkeypatch):
    journal=tmp_path/'operational'/'usage.sqlite3';monkeypatch.setenv('POLITITRACK_API_USAGE_PATH',str(journal))
    cfg=_config(tmp_path/'ai')
    raw=response(output=[{'type':'web_search_call','body':'DO NOT RETAIN MODEL OUTPUT'}]);raw['private']='DO NOT RETAIN KEY'
    api_usage.record_attempt(cfg,'a',raw)
    api_usage.record_attempt(cfg,'retry_same_response',raw)
    api_usage.record_attempt(cfg,'unknown',error_type='Timeout')
    out=api_usage.publish(cfg);m=out['months'][0]
    assert m['attempts']==2 and m['usage_reported_attempts']==1 and m['unpriced_attempts']==1
    assert m['input_tokens']==1000 and m['output_tokens']==500
    assert m['tool_call_count']==1 and m['estimated_observed_tokens_usd'] is None
    assert m['complete_account_bill_available'] is False
    with sqlite3.connect(journal) as db:serialized=' '.join(r[0] for r in db.execute('SELECT payload FROM usage_events'))
    assert 'DO NOT RETAIN' not in serialized
    assert read_json(cfg.ai_dir/api_usage.SUMMARY_NAME)==out


def test_missing_journal_shows_unmetered_not_free(tmp_path,monkeypatch):
    monkeypatch.delenv('POLITITRACK_API_USAGE_PATH',raising=False)
    result=api_usage.publish(_config(tmp_path))
    assert result['months']==[] and 'not zero' in result['notice']


def test_broken_journal_does_not_break_the_analyst(tmp_path,monkeypatch,caplog):
    path=tmp_path/'bad.sqlite3';path.write_text('not SQLite')
    monkeypatch.setenv('POLITITRACK_API_USAGE_PATH',str(path))
    cfg=_config(tmp_path);api_usage.record_attempt(cfg,'a',response())
    assert 'usage accounting unavailable' in caplog.text
    assert api_usage.publish(cfg)['accounting_status']=='unavailable'


def test_attribute_style_response_is_supported():
    usage=SimpleNamespace(input_tokens=10,output_tokens=4,input_tokens_details=SimpleNamespace(cached_tokens=0),output_tokens_details=SimpleNamespace(reasoning_tokens=2))
    result=api_usage.capture(SimpleNamespace(usage=usage));assert result['status']=='reported'
    assert result['cache_write_tokens']==0 and result['cache_write_detail_reported'] is False


def test_hardened_wrapper_records_every_response_including_incomplete(tmp_path,monkeypatch):
    from test_ai_filing_analyst_hardened import _Factory,_response,_payload,_schema,hardened
    cfg=_config(tmp_path);journal=tmp_path/'meter.sqlite3';monkeypatch.setenv('POLITITRACK_API_USAGE_PATH',str(journal))
    bad=_response('',status='incomplete',reason='max_output_tokens',response_id='resp_TEST_incomplete')
    good=_response(json.dumps(_payload()),response_id='resp_TEST_completed')
    for r in [bad,good]:r.usage=SimpleNamespace(input_tokens=10,output_tokens=20,input_tokens_details=SimpleNamespace(cached_tokens=0),output_tokens_details=SimpleNamespace(reasoning_tokens=15))
    result=hardened.openai_analyze({},cfg,_schema(cfg),client_factory=_Factory([bad,good]))
    assert result.payload['analysis_summary']
    summary=api_usage.publish(cfg);m=summary['months'][0]
    assert m['attempts']==2 and m['usage_reported_attempts']==2 and m['output_tokens']==40 and m['reasoning_tokens']==30
