'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const modules = process.env.POLITITRACK_TEST_NODE_MODULES || path.join(__dirname, '../.remediation/ui-test-tools/node_modules');
const {JSDOM} = require(path.join(modules, 'jsdom'));
const axe = require(path.join(modules, 'axe-core'));
const source = fs.readFileSync(path.join(__dirname, '../scripts/dashboard_assets/backfill-progress.js'), 'utf8');
const instant = '2026-09-11T20:00:00Z';
function payload(changes = {}) {
  return {
    schema_version: 1, status: 'queued',
    counts: {completed: 5, ready: 2, queued: 1, awaiting_maturity: 3, awaiting_retry: 1, missing_data: 1, blocked: 0, unknown: 0},
    total_observations: 13, last_successful_run_at: instant, last_advancement_at: instant,
    advanced_in_last_run: 3, completed_in_last_run: 2, stalled_successful_runs: 0,
    stale_after_minutes: 75, evidence_stale: false,
    next_retry_at: '2026-09-12T00:00:00Z', next_scheduled_run_at: null,
    eta: {lower_seconds: 1800, upper_seconds: 3600, measured_intervals: 3},
    detail_total: 8, details_truncated: true,
    details: [
      {category: 'ready', investor: 'TEST Investor', owner: 'Spouse', ticker: 'AAA', reason: 'Cached outcomes available.', profile_index: 0},
      {category: 'awaiting_maturity', investor: 'TEST Second', owner: 'Self', ticker: 'BBB', reason: 'More sessions are needed.', profile_index: 1},
      {category: 'missing_data', investor: 'TEST Third', owner: 'Joint', ticker: 'CCC', reason: 'Prices unavailable.', profile_index: 2}
    ], ...changes
  };
}
function setup(t, data, hash = '') {
  const errors = [];
  const dom = new JSDOM(`<!doctype html><html lang="en"><head><title>Backfill fixture</title></head><body><main><h1>Investor Edge</h1><span id="edge-bootstrap-status" role="status"></span><div id="edge-backfill-detail"></div><details id="investor-0-details"><summary>TEST profile</summary></details></main></body></html>`, {url: 'https://example.test/investor-edge.html'+hash, runScripts: 'outside-only', pretendToBeVisual: true});
  const w = dom.window;
  let wall = Date.parse(instant), mono = 0;
  w.Date.now = () => wall;
  Object.defineProperty(w.performance, 'now', {value: () => mono});
  w.fetch = () => {throw new Error('No network request is permitted');};
  w.addEventListener('error', e => errors.push(e.error));
  w.eval(source);
  const host = w.document.getElementById('edge-backfill-detail');
  const status = w.document.getElementById('edge-bootstrap-status');
  const result = {w, host, status, render: p => w.PTBackfill.render(host, p),
    tick: (minutes, wallMinutes = minutes) => {mono += minutes*60000; wall += wallMinutes*60000;}};
  if (data !== undefined) result.render(data);
  t.after(() => {dom.window.close(); assert.deepEqual(errors, []);});
  return result;
}

test('disjoint counts, bounded ETA and no invented next execution', t => {
  const e = setup(t, payload());
  assert.equal(e.status.textContent, 'Historical work queued');
  assert.equal(e.host.querySelectorAll('.edge-history-counts dd').length, 8);
  assert.match(e.host.textContent, /Estimated processing: 30 min–1.0 hours/);
  assert.match(e.host.textContent, /ready cached work only/);
  const next = [...e.host.querySelectorAll('dt')].find(n => n.textContent === 'Next scheduled execution');
  assert.equal(next.nextElementSibling.textContent, 'Unavailable');
  assert.match(e.host.textContent, /No rating or acknowledgement/);
  assert.match(e.host.textContent, /Showing 3 of 8/);
});

test('legacy or inconsistent counts never become a completion claim', t => {
  const e = setup(t, {backfill_pending_observation_count: 0});
  assert.equal(e.status.textContent, 'Historical backfill status unavailable');
  e.render(payload({total_observations: 12}));
  assert.equal(e.status.textContent, 'Historical backfill status unavailable');
  assert.doesNotMatch(e.host.textContent, /Estimated processing:/);
  assert.equal(e.host.querySelector('dd'), null);
});

test('escaping prevents HTML injection and profile links use validated indexes', t => {
  const e = setup(t, payload({details: [{category: 'missing_data', investor: '<img src=x onerror="bad()">', owner: '</td><script>bad()</script>', ticker: '<svg onload="bad()">', reason: '<a href="javascript:bad()">bad</a>', profile_index: '0\" onclick="bad()'}]}));
  assert.equal(e.host.querySelectorAll('img,svg,script').length, 0);
  assert.equal(e.host.querySelector('a[href^="javascript:"]'), null);
  assert.equal(e.host.querySelector('tbody a'), null);
  assert.match(e.host.textContent, /<img/);
});

test('pending work filters preserve open state, query and keyboard focus on refresh', t => {
  const data = payload(), e = setup(t, data);
  e.host.querySelector('details').open = true;
  let select = e.host.querySelector('select'), input = e.host.querySelector('input');
  select.value = 'missing_data'; select.dispatchEvent(new e.w.Event('change'));
  input.value = 'CCC'; input.dispatchEvent(new e.w.Event('input')); input.focus();
  assert.equal(e.host.querySelectorAll('tbody tr:not([hidden])').length, 1);
  assert.match(e.host.querySelector('#backfill-filter-result').textContent, /1 matching/);
  e.render(data);
  assert.equal(e.host.querySelector('details').open, true);
  assert.equal(e.host.querySelector('select').value, 'missing_data');
  assert.equal(e.host.querySelector('input').value, 'CCC');
  assert.equal(e.w.document.activeElement.id, 'backfill-text-filter');
  assert.equal(e.host.querySelector('tbody tr:not([hidden]) a').getAttribute('href'), 'investor-edge.html#investor-2-details');
});

test('stalled processing warns while future maturity alone does not', t => {
  const e = setup(t, payload({status: 'stalled', stalled_successful_runs: 3}));
  assert.equal(e.status.classList.contains('failure'), true);
  assert.match(e.host.querySelector('.edge-progress-warning').textContent, /3 successful maintenance passes/);
  assert.doesNotMatch(e.host.textContent, /Estimated processing:/);
  e.render(payload({status: 'awaiting_maturity', counts: {completed: 5,ready: 0,queued: 0,awaiting_maturity: 8,awaiting_retry: 0,missing_data: 0,blocked: 0,unknown: 0}}));
  assert.equal(e.status.textContent, 'Waiting for outcome maturity');
  assert.equal(e.host.querySelector('.edge-progress-warning'), null);
  assert.doesNotMatch(e.host.textContent, /Estimated processing:/);
});

test('same publication ages into stale state without producing progress or ETA', t => {
  const data = payload(), e = setup(t, data);
  const original = JSON.stringify(data);
  e.tick(76); e.render(data);
  assert.match(e.status.textContent, /stale/i);
  assert.doesNotMatch(e.host.textContent, /Estimated processing:/);
  e.render(data);
  assert.match(e.status.textContent, /stale/i);
  assert.equal(JSON.stringify(data), original);
});

test('a backwards device clock remains uncertain for the same evidence', t => {
  const data = payload(), e = setup(t, data);
  e.tick(1, -1); e.render(data);
  assert.match(e.status.textContent, /stale|unavailable/i);
  e.tick(1, 2); e.render(data);
  assert.match(e.status.textContent, /stale|unavailable/i);
  e.render(payload({last_successful_run_at: '2026-09-11T20:01:00Z'}));
  assert.equal(e.status.textContent, 'Historical work queued');
});

test('standalone uses inert producer data and opens an existing profile detail', t => {
  const e = setup(t, undefined, '#investor-0-details');
  const data = e.w.document.createElement('script');
  data.type = 'application/json'; data.id = 'edge-backfill-data'; data.textContent = JSON.stringify(payload());
  e.w.document.body.appendChild(data);
  e.w.PTBackfill.attachStandalone();
  assert.equal(e.status.textContent, 'Historical work queued');
  assert.equal(e.w.document.getElementById('investor-0-details').open, true);
});

test('component controls and open detail table pass accessibility checks', async t => {
  const e = setup(t, payload());
  e.host.querySelector('details').open = true;
  e.w.eval(axe.source);
  const result = await e.w.axe.run(e.w.document, {rules: {'color-contrast': {enabled: false}}});
  assert.equal(result.violations.length, 0, JSON.stringify(result.violations.map(v => ({id: v.id, nodes: v.nodes.map(n => n.target)}))));
});
