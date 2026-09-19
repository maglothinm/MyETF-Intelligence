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
