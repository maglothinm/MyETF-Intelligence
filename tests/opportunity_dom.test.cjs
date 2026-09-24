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
  assert.ok(doc.querySelector('summary')); assert.equal(doc.querySelectorAll('a[download]').length,5);
  assert.ok(doc.querySelector('a[href="data/information-value-at-discovery.json"]'));
  assert.match(doc.body.textContent,/Information value at discovery/);
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

test('purchase threshold filter distinguishes crossed, quiet and unknown per purchase',()=>{
  const copy=structuredClone(model); const sample=copy.records[0];
  sample.purchase_thresholds={threshold_fraction:.08,trades:{quiet:{trade_id:'quiet',active:true,status:'not_crossed',threshold_fraction:.08,valid_until:new Date(now+60000).toISOString(),peak_gain_fraction:.04},crossed:{trade_id:'crossed',active:true,status:'crossed',threshold_fraction:.08,peak_gain_fraction:.19},unknown:{trade_id:'unknown',active:true,status:'unknown',threshold_fraction:.08}}};
  copy.records=[sample];const dom=page(),doc=dom.window.document;
  for(const status of ['not_crossed','crossed','unknown']){render(doc,copy,now,'all',status);assert.equal(doc.querySelectorAll('article').length,1);}
  render(doc,copy,now,'all','not_crossed');assert.match(doc.querySelector('.threshold-summary').textContent,/1 not crossed; 1 previously crossed; 1 unknown/);
  assert.match(doc.body.textContent,/Peak gain 19.00%/);
  assert.ok(doc.querySelector('label[for="threshold-filter"]'));
  render(doc,copy,now+120000,'all','not_crossed');assert.equal(doc.querySelectorAll('article').length,0);
  render(doc,copy,NaN,'all','crossed');assert.equal(doc.querySelectorAll('article').length,1);
});

test('v2 dossier keeps quotations inert, risks separate, and scenarios labeled',async()=>{
  const copy=structuredClone(model),r=copy.records[0];
  r.investment_dossier={status:'ready_for_human_review',evaluated_at:new Date(now).toISOString(),
    case:{thesis:{text:'TEST <img src=x onerror=alert(1)> economics',claim_ids:['TEST-claim']},scenarios:{bear:{annual_eps:6,multiple:15,assumption:'TEST assumption'}}},
    claims:[{claim_id:'TEST-claim',kind:'fact',text:'TEST reported evidence',references:[{quote:'TEST <script>alert(1)</script>',url:'javascript:alert(1)'}]}],
    findings:{risk:[{implication:'TEST customer concentration risk',claim_id:'TEST-claim'}]},scenario_prices:{bear:90},
    entry_max:113.33,base_upside_fraction:.6,bear_downside_fraction:.1,scenario_reward_risk:6,
    valuation_notice:'TEST assumptions, not forecasts.',risk_notice:'TEST scenario loss is not a maximum.',capital_authorization:'No trade authorization.'};
  const dom=page(),doc=dom.window.document;render(doc,copy,now);
  assert.ok(doc.querySelector('.investment-dossier'));
  assert.match(doc.body.textContent,/Scenario valuation — assumptions, not forecasts/);
  assert.match(doc.body.textContent,/Known investment risks/);
  assert.match(doc.body.textContent,/Scenario entry ceiling: \$113\.33/);
  assert.match(doc.body.textContent,/TEST customer concentration risk/);
  assert.equal(doc.querySelectorAll('img,[onerror],a[href^="javascript:"]').length,0);
  dom.window.eval(axe.source);const result=await dom.window.axe.run(doc,{rules:{'color-contrast':{enabled:false}}});
  assert.equal(result.violations.length,0,JSON.stringify(result.violations.map(v=>v.id)));
});

test('matched benchmark comparison is displayed separately from unavailable evidence',()=>{
  const copy=structuredClone(model),r=copy.records[0];
  r.investment_dossier={status:'ready_for_human_review',case:{},findings:{},claims:[]};
  r.research={cohorts:{test:{cohort:'full_method',outcomes:{'5':{net_return_fraction:.099,cost_assumption_bps:10}},
    benchmark_outcomes:{'5':{symbol:'TEST-BENCH',benchmark_relative_fraction:.05}}}}};
  const doc=page().window.document;render(doc,copy,now);
  assert.match(doc.body.textContent,/excess over TEST-BENCH: 5\.00%/);
  assert.match(doc.body.textContent,/not risk-adjusted alpha/);
  r.research.cohorts.test.benchmark_outcomes={};render(doc,copy,now);
  assert.match(doc.body.textContent,/benchmark-relative result unavailable/);
  assert.doesNotMatch(doc.body.textContent,/excess over TEST-BENCH/);
});


test('operating costs distinguishes no observations from free market data and keeps text inert',async()=>{
  const {render:renderCosts}=require('../scripts/dashboard_assets/operating-costs.js');
  const html=fs.readFileSync(path.join(assets,'operating-costs.html'),'utf8');
  const dom=new JSDOM(html,{runScripts:'outside-only',url:'https://example.test/operating-costs.html'}),doc=dom.window.document;
  renderCosts(doc,{months:[],notice:'Unmetered historical usage is unknown.'});
  assert.match(doc.body.textContent,/unknown, not \$0/i);
  renderCosts(doc,{months:[{month_utc:'TEST',attempts:2,usage_reported_attempts:1,input_tokens:1000,cached_input_tokens:200,output_tokens:500,estimated_token_subtotal_usd:'0.00769',unpriced_attempts:1,tool_call_count:1,models:['<img src=x onerror=alert(1)>']}],notice:'Not an invoice.'});
  assert.match(doc.body.textContent,/\$0\.0077/);assert.match(doc.body.textContent,/Unpriced attempts/);
  assert.equal(doc.querySelectorAll('img,[onerror]').length,0);
  dom.window.eval(axe.source);
  const results=await dom.window.axe.run(doc,{rules:{'color-contrast':{enabled:false}}});
  assert.equal(results.violations.length,0,JSON.stringify(results.violations));
});
