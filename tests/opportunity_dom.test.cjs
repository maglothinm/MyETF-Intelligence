'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const deps=createRequire(path.resolve(process.env.POLITITRACK_TEST_NODE_MODULES||'node_modules','package.json'));
const {JSDOM}=deps('jsdom');
const axe=deps('axe-core');
const {render,effectiveStatus}=require('../scripts/dashboard_assets/current-opportunities.js');
const assets=path.resolve(__dirname,'../scripts/dashboard_assets');
const model=JSON.parse(fs.readFileSync(process.env.OPPORTUNITY_FIXTURE_JSON,'utf8'));
const now=Date.parse(model.telemetry.finished_at);
function page(){return new JSDOM(fs.readFileSync(path.join(assets,'current-opportunities.html'),'utf8'),{runScripts:'outside-only',url:'https://example.test/current-opportunities.html'});}
test('same persisted gates, semantic details, shadow label and exports',()=>{
  const dom=page(),doc=dom.window.document; render(doc,model,now);
  assert.match(doc.getElementById('mode').textContent,/SHADOW/);
  assert.equal(doc.querySelectorAll('article').length,model.records.length);
  assert.equal(doc.querySelectorAll('.available').length,model.records.filter(r=>r.lifecycle==='opportunity_available').length);
  assert.ok(doc.querySelector('summary')); assert.equal(doc.querySelectorAll('a[download]').length,2);
  const count=model.records.filter(r=>effectiveStatus(r,now)==='watching').length;
  render(doc,model,now,'watching'); assert.equal(doc.querySelectorAll('article').length,count);
});
test('stale or missing clock withdraws available badges',()=>{
  for(const at of [NaN,now+24*60*60*1000]){
    const dom=page();render(dom.window.document,model,at);
    assert.equal(dom.window.document.querySelectorAll('.available').length,0);
  }
});
test('untrusted values and source URLs remain inert',()=>{
  const copy=structuredClone(model);copy.records[0].issuer='<img src=x onerror=alert(1)>';
  copy.records[0].evidence.sources=[{url:'javascript:alert(1)',id:'TEST bad URL'}];
  const dom=page();render(dom.window.document,copy,now);
  assert.equal(dom.window.document.querySelectorAll('img,[onerror],a[href^="javascript:"]').length,0);
  assert.match(dom.window.document.body.textContent,/<img src=x/);
});
test('axe semantic accessibility has no violations',async()=>{
  const dom=page();render(dom.window.document,model,now);dom.window.eval(axe.source);
  const result=await dom.window.axe.run(dom.window.document,{rules:{'color-contrast':{enabled:false}}});
  assert.equal(result.violations.length,0,JSON.stringify(result.violations.map(v=>({id:v.id,impact:v.impact}))));
});
