'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const context={window:{},URL,location:{href:'https://TEST.example/'},console};
vm.runInNewContext(fs.readFileSync('scripts/dashboard_assets/common.js','utf8'),context);
const PT=context.window.PT;
const now=Date.parse('2026-09-17T20:00:00Z');
function model(ocr={}) {
  const source={required:true,enabled:true,status:'failure',activity:'degraded',stage:'complete',
    finished_at:'2026-09-17T19:59:00Z',heartbeat_at:'2026-09-17T19:59:00Z',stale_after_minutes:90,
    cleanup_status:'deferred',detail:'OCR cleanup requires attention.',...ocr};
  const branches=['legislative','executive','ai'].map(branch=>({branch,status:'success',errors:[],timeline:[],
    expected_interval_minutes:30,stale_after_minutes:90,last_success_utc:'2026-09-17T19:59:00Z',
    latest_run_success:true,latest_conclusion:'success',...(branch==='legislative'?{source_ocr:source}:{})}));
  return {health:{status:'failure',as_of_utc:new Date(now).toISOString(),branches,required_branches:['legislative','executive','ai']}};
}
test('a successful collector cannot hide failed OCR in browser rollup',()=>{
  const result=PT.healthAt(model(),now);assert.equal(result.health.status,'failure');
  assert.equal(result.health.branches[0].status,'success');
  assert.match(PT.monitoringSummary(result).label,/Legislative OCR/);
  assert.doesNotMatch(PT.monitoringSummary(result).label,/collector failed/);
});
test('OCR becomes stale without a new publication and cannot be refreshed green',()=>{
  const m=model({status:'success',activity:'idle',cleanup_status:'complete'});
  assert.equal(PT.healthAt(m,now).health.status,'success');
  assert.equal(PT.healthAt(m,now+91*60000).health.branches[0].source_ocr.status,'stale');
  assert.equal(PT.healthAt(m,now,{clockUnreliable:true}).health.branches[0].source_ocr.status,'unknown');
});
test('Operations shows stage, actual OCR counts, queue and cleanup separately',()=>{
  const html=PT.healthCards(model(),true);
  for(const label of ['Source OCR','Last OCR heartbeat','Documents OCR-completed','Ready work remaining','Needs human review','File cleanup'])assert.ok(html.includes(label),label);
  assert.match(PT.ocrRunLabel({source_ocr_metrics:{stage:'complete',cleanup_status:'deferred',documents_completed:2,retry_delayed_count:1}}),/cleanup Deferred/);
});
test('untrusted health text is escaped and never inserted as HTML',()=>{
  const html=PT.healthCards(model({detail:'<script>bad()</script>',error_code:'<img src=x>'}),true);
  assert.ok(!html.includes('<script>bad()'));
  assert.ok(!html.includes('<img src=x>'));
});
test('compact and detailed cards keep collection and OCR history in separate sections',()=>{
  const m=model({activity:'blocked_by_collection',status:'unknown',
    last_completed_pass_at:'2026-09-17T18:00:00Z',last_success_at:'2026-09-17T17:00:00Z'});
  for(const detailed of [false,true]) {
    const html=PT.healthCards(m,detailed);
    const collector=html.match(/<section class="collector-run-health"[^>]*>(.*?)<\/section>/s)[1];
    const ocr=html.match(/<section class="ocr-run-health"[^>]*>(.*?)<\/section>/s)[1];
    assert.match(collector,/Legislative collector/);
    assert.match(collector,/Last successful collection/);
    assert.doesNotMatch(collector,/Last healthy OCR pass/);
    assert.match(ocr,/Legislative Source OCR/);
    assert.match(ocr,/Blocked by collection/);
    assert.match(ocr,/Last completed OCR pass/);
    assert.match(ocr,/Last healthy OCR pass/);
    assert.doesNotMatch(ocr,/Last successful collection|Last success /);
    assert.match(html,/Last successful analysis/);
  }
});

test('request-only backlog and unchanged-content checks are separate from runnable work',()=>{
  const html=PT.healthCards(model({ready_remaining:0,request_only_remaining:3832,
    unobserved_remaining:2441,unobserved_access_remaining:2441,unchanged_documents:5}),true);
  for(const label of ['OGE document requests required','Of these, awaiting document access',
    'Unchanged documents checked','Ready work remaining']) assert.ok(html.includes(label),label);
  assert.ok(PT.healthCards(model(),true).includes('Not reported'));
});



test('Overview and Operations show committed cached imports and preserve last import on later zero runs',()=>{
  const m=model({committed_pass:true,transactions_appended:0,extractions_reused:5,documents_completed:0,
    last_transaction_import_at:'2026-09-17T19:40:00Z',last_transaction_import_count:10,
    source_unavailable_remaining:9,retry_remaining:0});
  for(const detailed of [false,true]) {
    const html=PT.healthCards(m,detailed);
    assert.match(html,/Latest committed pass: <strong>0 transactions appended/);
    assert.match(html,/5 cached extractions reused/);
    assert.match(html,/0 new extractions/);
    assert.match(html,/Last transaction import/);
    assert.match(html,/10 transactions/);
    assert.match(html,/9 source documents unavailable/);
    assert.match(html,/Needs attention/); // Progress must never override an independent failure.
  }
  const uncommitted=PT.healthCards(model({committed_pass:false,transactions_appended:999}),false);
  assert.doesNotMatch(uncommitted,/Latest committed pass|999 transactions/);
});
test('run tooltip separates imports, fresh extractions, and outstanding technical retries',()=>{
  const label=PT.ocrRunLabel({source_ocr_metrics:{stage:'complete',cleanup_status:'not_needed',
    transactions_appended:10,documents_completed:0,extractions_reused:5,retry_delayed_count:0,retry_remaining:10}});
  assert.match(label,/10 transactions appended/);
  assert.match(label,/5 cached extractions reused/);
  assert.match(label,/0 retries this pass; 10 technical retries outstanding/);
});
