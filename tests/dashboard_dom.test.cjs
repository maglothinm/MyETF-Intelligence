'use strict';

// JSDOM checks DOM behavior, not browser rendering, physical touch, CSP, or audio policy.
// Pointer capabilities, clocks and geometry below are explicit deterministic stubs.
// All resources are fixture files and fetch is an in-memory same-origin adapter.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const toolModules = process.env.POLITITRACK_TEST_NODE_MODULES || path.resolve(__dirname, '../.remediation/ui-test-tools/node_modules');
const {JSDOM, VirtualConsole} = require(path.join(toolModules, 'jsdom'));
const axe = require(path.join(toolModules, 'axe-core'));
const build = process.env.POLITITRACK_TEST_BUILD || path.resolve(__dirname, '../.remediation/ui-preview');
const builtModel = JSON.parse(fs.readFileSync(path.join(build, 'data/dashboard-insights.json'), 'utf8'));
const KEY = 'polititrack.notifications.v1';
const copy = value => JSON.parse(JSON.stringify(value));
const tick = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

function pointer(env, node, type, options = {}) {
  const event = new env.window.MouseEvent(type, {bubbles: true, cancelable: true, ...options});
  Object.defineProperty(event, 'pointerType', {value: options.pointerType || 'mouse'});
  node.dispatchEvent(event);
  return event;
}

function tooltipClock(window) {
  const originalSet = window.setTimeout, originalClear = window.clearTimeout;
  let now = 0, sequence = 0;
  const pending = new Map();
  window.setTimeout = (callback, delay = 0, ...args) => {
    const id = ++sequence;
    pending.set(id, {at: now + Number(delay), callback: () => callback(...args)});
    return id;
  };
  window.clearTimeout = id => pending.delete(id);
  return {
    advance(milliseconds) {
      const until = now + milliseconds;
      for (;;) {
        const next = [...pending].filter(([, item]) => item.at <= until).sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
        if (!next) break;
        pending.delete(next[0]); now = next[1].at; next[1].callback();
      }
      now = until;
    },
    restore() { pending.clear(); window.setTimeout = originalSet; window.clearTimeout = originalClear; }
  };
}

function animationFrames(window) {
  const originalRequest = window.requestAnimationFrame, originalCancel = window.cancelAnimationFrame;
  let sequence = 0;
  const pending = new Map();
  window.requestAnimationFrame = callback => { const id = ++sequence; pending.set(id, callback); return id; };
  window.cancelAnimationFrame = id => pending.delete(id);
  return {
    flush() { const callbacks = [...pending.values()]; pending.clear(); callbacks.forEach(callback => callback(0)); },
    restore() { pending.clear(); window.requestAnimationFrame = originalRequest; window.cancelAnimationFrame = originalCancel; }
  };
}

// Observe whether the application blocked activation, then prevent only JSDOM's
// navigation default. A missing navigation implementation is not a passing result.
function activationWasBlocked(env, node, pointerType = 'mouse') {
  let blocked;
  const observe = event => { blocked = event.defaultPrevented; event.preventDefault(); };
  env.doc.addEventListener('click', observe, {once: true});
  const event = pointer(env, node, 'click', {pointerType});
  env.doc.removeEventListener('click', observe);
  // A help-preview handler can intentionally stop propagation before observation.
  return blocked ?? event.defaultPrevented;
}

function rect(left, top, width, height) {
  return {left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON() { return this; }};
}

function fixtures() {
  const filings = Array.from({length: 65}, (_, index) => ({filing_key: 'fixture-' + index, report_id: 'fixture-' + index,
    source: index % 2 ? 'house' : 'senate', branch: 'legislative', filer: index === 7 ? 'Unique Needle Filer' : 'Fixture Filer ' + String(index).padStart(2, '0'),
    title: 'Fixture official', status: index % 3 ? 'processed' : 'cataloged', transaction_count: index % 3 ? 1 : 0,
    filed_date: `2026-08-${String(index % 28 + 1).padStart(2, '0')}`, first_seen_utc: `2026-08-${String(index % 28 + 1).padStart(2, '0')}T12:00:00Z`,
    source_url: 'https://example.test/filing/' + index}));
  const runs = ['legislative', 'executive', 'ai'].map(branch => ({id: branch + ':fixture', run_key: branch + ':fixture', branch,
    success: true, status: 'success', conclusion: 'success', error_count: 0, errors: [], finished_utc: '2026-08-30T11:00:00Z',
    at: '2026-08-30T11:00:00Z', run_url: 'https://example.test/runs/' + branch, url: 'https://example.test/runs/' + branch, new_record_count: 0}));
  const transactions = [{trade_id: 'trade-fixture', transaction_date: '2026-08-01', filed_date: '2026-08-10', observed_at_utc: '2026-08-11T12:00:00Z',
    source: 'house', filer: 'Fixture Filer', owner: 'Spouse', ticker: 'TEST', asset: 'Fixture company', amount: '$1,001–$15,000', transaction_type: 'purchase', source_url: 'https://example.test/filing/1'}];
  const model = {...copy(builtModel), generated_utc: '2026-08-30T12:00:00Z', data_through_utc: '2026-08-30T11:00:00Z', signals: [], signals_truncated: false,
    coverage: {cataloged_only: 22, processed: 43, review_required: 0, other_filings: 0, filings: 65, transactions: 1, analyses: 0, qualifying_signals: 0, note: 'Separate retained populations. Cataloged does not mean parsed.'},
    composition: {population: 1, purchases: 1, sales: 0, other: 0, note: 'Parsed post-upgrade fixture ledger.'},
    reviews: {access_required: 0, manual_exception: 0, other: 0, total: 0, latest: []},
    simulation: {available: false, status: 'unavailable'}, paper: {open_positions: 0}, latest_filings: filings.slice(0, 5),
    synthetic: {filings: 0, transactions: 0, analyses: 0},
    health: {status: 'success', branches: runs.map(row => ({branch: row.branch, status: 'success', last_run_utc: row.at, last_success_utc: row.at,
      errors: [], new_record_count: 0, run_url: row.run_url, expected_cadence_seconds: null, timeline: [row]}))},
    notifications: {filing_ids: filings.map(row => row.filing_key), trade_ids: transactions.map(row => row.trade_id), qualifying_signals: [], runs, simulation_results: [], current_incidents: []}};
  return {'dashboard-insights': model, filings, transactions, 'pending-reviews': [], 'ai-analyses': [], 'paper-portfolio': [],
    runs: runs.filter(row => row.branch !== 'ai'), 'ai-runs': runs.filter(row => row.branch === 'ai')};
}

async function waitFor(predicate, description, timeout = 3000) {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeout) throw new Error('Timed out: ' + description);
    await tick(10);
  }
}

async function dashboard(options = {}) {
  const data = fixtures();
  if (options.change) options.change(data);
  const requests = [], errors = [], failures = new Set(), virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(fs.readFileSync(path.join(build, 'index.html'), 'utf8'), {url: 'https://dashboard.test/PolitiTrack/' + (options.hash || ''),
    runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole});
  const {window} = dom;
  window.matchMedia = query => ({matches: Boolean(options.coarse && /pointer:\s*coarse|hover:\s*none/.test(query)), media: query,
    addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}});
  if (options.visualViewport) window.visualViewport = Object.assign(new window.EventTarget(), options.visualViewport);
  window.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  window.HTMLDialogElement.prototype.close = function () { this.open = false; this.dispatchEvent(new window.Event('close')); };
  window.addEventListener('error', event => errors.push(event.error?.message || event.message));
  window.addEventListener('unhandledrejection', event => errors.push(String(event.reason)));
  window.fetch = async value => {
    const url = new URL(value, window.location.href);
    assert.equal(url.origin, window.location.origin, 'No external browser requests permitted');
    const match = url.pathname.match(/\/data\/([\w-]+)\.json$/);
    assert.ok(match, 'Only published JSON fixtures may be fetched');
    const name = match[1]; requests.push(name);
    if (failures.has(name)) return {ok: false, status: 503};
    if (!(name in data)) return {ok: false, status: 404};
    return {ok: true, status: 200, json: async () => copy(data[name])};
  };
  // Audio is intentionally unavailable; the page must never initialize it on load.
  window.AudioContext = function () { errors.push('Audio initialized without gesture'); throw new Error('Unexpected audio'); };
  if (options.beforeScript) options.beforeScript(window);
  window.eval(fs.readFileSync(path.join(build, 'app.js'), 'utf8'));
  const doc = window.document, byId = id => doc.getElementById(id);
  await waitFor(() => !byId('refresh-button').disabled, 'initial dashboard render');
  async function navigate(hash, predicate) {
    window.location.hash = hash;
    await waitFor(predicate || (() => true), 'navigation ' + hash);
    await tick(15);
  }
  async function refresh() {
    byId('refresh-button').click();
    await waitFor(() => !byId('refresh-button').disabled, 'refresh completion');
    await tick(5);
  }
  return {dom, window, doc, byId, data, requests, errors, failures, navigate, refresh, close: () => {
    // Disconnect any active tooltip layout observers before destroying the DOM.
    doc.dispatchEvent(new window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
    window.close();
  }};
}

test('Overview loads only compact insights; sections fetch their ledgers lazily', async t => {
  const env = await dashboard(); t.after(env.close);
  assert.deepEqual(env.requests, ['dashboard-insights']);
  assert.equal(env.byId('error-banner').hidden, true);
  assert.equal(env.byId('notification-count').textContent, '0');
  assert.equal(env.byId('attention-signals').textContent, '0');
  assert.ok(env.window.localStorage.getItem(KEY));
  await env.navigate('#records', () => env.byId('filings-body').children.length === 50);
  assert.deepEqual(env.requests, ['dashboard-insights', 'filings']);
  await env.navigate('#records/transactions', () => env.byId('transactions-body').textContent.includes('TEST'));
  assert.equal(env.requests.at(-1), 'transactions');
  assert.ok(!env.requests.includes('pending-reviews'));
  await env.navigate('#signals', () => env.requests.includes('ai-analyses'));
  assert.equal(env.byId('signals').hidden, false);
  await env.navigate('#agent', () => env.requests.includes('paper-portfolio'));
  assert.match(env.byId('paper-position-status').textContent, /No open paper positions/);
  await env.navigate('#operations', () => env.requests.includes('ai-runs'));
  assert.ok(env.requests.includes('runs'));
  assert.deepEqual(env.errors, []);
});

test('record pagination, debounced search, explicit date basis and sortable columns work', async t => {
  const env = await dashboard(); t.after(env.close);
  await env.navigate('#records', () => env.byId('filings-body').children.length === 50);
  assert.match(env.byId('filings-count-label').textContent, /1–50 of 65/);
  env.byId('filings-more').click();
  assert.equal(env.byId('filings-body').children.length, 15);
  assert.equal(env.byId('filings-more').disabled, true);
  const search = env.byId('filings-search'); search.value = 'Unique Needle'; search.dispatchEvent(new env.window.Event('input', {bubbles: true}));
  await waitFor(() => env.byId('filings-count-label').textContent.includes('of 1 matching'), 'debounced filter');
  assert.match(env.byId('filings-body').textContent, /Unique Needle/);
  env.byId('filings-clear').click();
  env.byId('filings-date-basis').value = 'filed_date'; env.byId('filings-date-basis').dispatchEvent(new env.window.Event('change', {bubbles: true}));
  env.byId('filings-date-from').value = '2026-08-20'; env.byId('filings-date-from').dispatchEvent(new env.window.Event('change', {bubbles: true}));
  assert.match(env.byId('filings-count-label').textContent, /date basis: Filing date/);
  const expected = env.data.filings.filter(row => row.filed_date >= '2026-08-20').length;
  assert.equal(env.byId('filings-body').children.length, expected);
  env.byId('filings-clear').click();
  env.doc.querySelector('[data-table="filings"][data-sort="filer"]').click();
  assert.equal(env.doc.querySelector('#panel-filings th[data-sort-field="filer"]').getAttribute('aria-sort'), 'ascending');
  assert.match(env.byId('filings-body').firstElementChild.textContent, /Fixture Filer 00/);
  assert.equal(env.doc.querySelector('#panel-filings a[download]').getAttribute('href'), 'data/filings.csv');
  assert.deepEqual(env.errors, []);
});

test('transaction, filing and observation dates remain separate DOM columns', async t => {
  const env = await dashboard(); t.after(env.close);
  await env.navigate('#records/transactions', () => env.byId('transactions-body').textContent.includes('TEST'));
  const cells = [...env.byId('transactions-body').firstElementChild.children];
  assert.match(cells[0].textContent, /Aug 1/);
  assert.match(cells[1].textContent, /Aug 10/);
  assert.match(cells[2].textContent, /Aug 11/);
  assert.equal(env.byId('transactions-date-basis').value, 'transaction_date');
});

test('hostile values are inert text in tables and signal cards', async t => {
  const hostile = '<img src=x onerror="window.hostileExecuted=1"><script>window.hostileExecuted=2</script>';
  const env = await dashboard({change(data) {
    data.filings[0].filer = hostile; data.filings[0].filed_date = '2026-08-31'; data.filings[0].source_url = 'javascript:window.hostileExecuted=3';
    data['dashboard-insights'].signals = [{analysis_id: 'malformed-optional', classification: 'watchlist', ticker: hostile, filer: hostile, asset: hostile,
      amount: null, current_price: null, final_score: null, review_band_low: 'bad', review_band_high: null, edge_observation_count: null, edge_confidence: null,
      direction: 'bullish', why: hostile, evidence: [{url: 'javascript:window.hostileExecuted=4', title: hostile}]}];
    data['dashboard-insights'].coverage.qualifying_signals = 1;
  }}); t.after(env.close);
  assert.equal(env.byId('error-banner').hidden, true);
  assert.equal(env.byId('overview-signals').querySelectorAll('img,script,[onerror]').length, 0);
  assert.match(env.byId('overview-signals').textContent, /<img src=x/);
  assert.ok(!env.byId('overview-signals').textContent.includes('NaN'));
  assert.match(env.byId('overview-signals').textContent, /Unavailable/);
  await env.navigate('#records', () => env.byId('filings-body').children.length === 50);
  assert.equal(env.byId('filings-body').querySelectorAll('img,script,[onerror],a[href^="javascript:"]').length, 0);
  assert.equal(env.window.hostileExecuted, undefined);
  assert.deepEqual(env.errors, []);
});

test('empty evidence stays Unknown with deliberate no-signal and no-position states', async t => {
  const env = await dashboard({change(data) {
    const model = data['dashboard-insights']; model.health.status = 'unknown';
    model.health.branches.forEach(row => { row.status = 'unknown'; row.timeline = []; row.last_run_utc = null; row.last_success_utc = null; row.new_record_count = null; });
    Object.keys(model.coverage).forEach(key => { if (typeof model.coverage[key] === 'number') model.coverage[key] = 0; });
    model.composition = {population: 0, purchases: 0, sales: 0, other: 0}; model.data_through_utc = null; model.latest_filings = [];
    model.notifications = {filing_ids: [], trade_ids: [], qualifying_signals: [], runs: [], simulation_results: [], current_incidents: []};
    data.filings = []; data.transactions = [];
  }}); t.after(env.close);
  assert.equal(env.byId('error-banner').hidden, true);
  assert.equal(env.byId('attention-health').textContent, 'Unknown');
  assert.match(env.byId('overview-signals').textContent, /No qualifying signals/);
  assert.match(env.byId('health-chart').textContent, /No retained evidence/);
  assert.ok(!env.byId('main').textContent.includes('NaN'));
  assert.match(env.byId('paper-position-status').textContent, /No open paper positions/);
  assert.match(env.byId('ten-k-simulation-result').textContent, /No persistent portfolio history yet/);
});

test('failed refresh preserves visible data and never commits the local baseline', async t => {
  const env = await dashboard(); t.after(env.close);
  const baseline = env.window.localStorage.getItem(KEY), previousSignals = env.byId('overview-signals').innerHTML;
  env.failures.add('dashboard-insights'); await env.refresh();
  assert.equal(env.window.localStorage.getItem(KEY), baseline);
  assert.equal(env.byId('overview-signals').innerHTML, previousSignals);
  assert.equal(env.byId('error-banner').hidden, false);
  assert.match(env.byId('error-banner').textContent, /Last successfully rendered data remains visible/);
  assert.match(env.byId('overall-state').textContent, /Refresh unavailable/);
  env.failures.clear(); await env.refresh();
  assert.equal(env.byId('error-banner').hidden, true);
  assert.equal(env.byId('notification-count').textContent, '0');
  assert.deepEqual(env.errors, []);
});

test('partial lazy-ledger refresh failure does not advance notification baseline', async t => {
  const env = await dashboard(); t.after(env.close);
  await env.navigate('#records', () => env.byId('filings-body').children.length === 50);
  const baseline = env.window.localStorage.getItem(KEY), table = env.byId('filings-body').innerHTML;
  env.data['dashboard-insights'].generated_utc = '2026-08-30T13:00:00Z';
  env.data['dashboard-insights'].notifications.filing_ids.push('new-after-failure');
  env.failures.add('filings'); await env.refresh();
  assert.equal(env.window.localStorage.getItem(KEY), baseline);
  assert.equal(env.byId('filings-body').innerHTML, table);
  assert.equal(env.byId('notification-count').textContent, '0');
});

test('one new qualifying signal renders one local event and unchanged refresh stays silent', async t => {
  const env = await dashboard(); t.after(env.close);
  const model = env.data['dashboard-insights'];
  model.generated_utc = '2026-08-30T13:00:00Z';
  model.signals = [{analysis_id: 'new-watch', classification: 'watchlist', ticker: 'DOMTEST', asset: 'Fixture company', filer: 'Fixture official',
    owner: 'Spouse', direction: 'bullish', final_score: 72, edge_status: 'insufficient_data', edge_observation_count: 1,
    transaction_date: '2026-08-01', filed_date: '2026-08-10', observed_at_utc: '2026-08-11T12:00:00Z', source_url: 'https://example.test/filing/new', evidence: []}];
  model.coverage.qualifying_signals = 1;
  model.notifications.qualifying_signals = [{analysis_id: 'new-watch', classification: 'watchlist', ticker: 'DOMTEST', link: '#signals'}];
  await env.refresh();
  assert.equal(env.byId('notification-count').textContent, '1');
  assert.equal(env.byId('notification-list').querySelectorAll('.notification-item').length, 1);
  assert.match(env.byId('notification-summary').textContent, /1 actionable/);
  assert.match(env.byId('overview-signals').textContent, /DOMTEST/);
  assert.match(env.byId('overview-signals').textContent, /insufficient completed observations \(n = 1\)/);
  await env.refresh();
  assert.equal(env.byId('notification-list').querySelectorAll('.notification-item').length, 1);
  assert.equal(env.byId('sound-button').textContent, 'Sound off');
  assert.deepEqual(env.errors, []);
});

test('new historical replay success/failure is visibly simulated without invented dispatch progress', async t => {
  const env = await dashboard(); t.after(env.close);
  const model = env.data['dashboard-insights'];
  model.generated_utc = '2026-08-30T13:00:00Z';
  model.simulation = {available: true, status: 'success', ticker: 'REPLAY', starting_value: 10000, current_value: 10100, change_usd: 100,
    change_percent: 1, remaining_to_goal: 9900, score: 74, classification: 'watchlist', entry_utc: '2026-08-11T12:00:00Z',
    valuation_utc: '2026-08-20T12:00:00Z', as_of_utc: '2026-08-20T12:00:00Z', run_url: 'https://example.test/run/replay', source_url: 'https://example.test/filing/replay'};
  model.notifications.simulation_results = [{simulation_id: 'dom-replay', kind: 'historical_replay', status: 'success', timestamp: model.generated_utc, url: '#agent'}];
  await env.refresh();
  assert.match(env.byId('notification-list').textContent, /SIMULATED/);
  assert.match(env.byId('ten-k-simulation-result').textContent, /10,100/);
  assert.ok(!env.byId('ten-k-simulation-panel').textContent.includes('50% goal'));
  assert.ok(!/Queued|Running/.test(env.byId('ten-k-simulation-result').textContent));
  model.generated_utc = '2026-08-30T14:00:00Z'; model.simulation.status = 'failure';
  model.notifications.simulation_results.push({simulation_id: 'dom-replay-failure', kind: 'historical_replay', status: 'failure', timestamp: model.generated_utc, url: '#agent'});
  await env.refresh();
  assert.match(env.byId('notification-list').textContent, /failure reported/);
  assert.equal(env.byId('ten-k-simulation-status').textContent, 'Failure');
  assert.deepEqual(env.errors, []);
});

test('tooltips delay mouse hover, cancel departed targets and preserve child traversal', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  const clock = tooltipClock(env.window); t.after(clock.restore);
  const first = env.doc.createElement('span'), second = env.doc.createElement('span');
  first.textContent = 'First'; second.textContent = 'Second'; help.replaceChildren(first, second);
  pointer(env, first, 'pointerover');
  clock.advance(249); assert.equal(tip.hidden, true, 'Incidental hover remains quiet');
  pointer(env, first, 'pointerout', {relatedTarget: second});
  pointer(env, second, 'pointerover', {relatedTarget: first});
  clock.advance(101); assert.equal(tip.hidden, false, 'Traversal within one control does not restart its delay');
  pointer(env, second, 'pointerout', {relatedTarget: first});
  pointer(env, first, 'pointerover', {relatedTarget: second});
  assert.equal(tip.hidden, false, 'Open help does not flicker across nested content');
  pointer(env, first, 'pointerout', {relatedTarget: env.doc.body});
  clock.advance(150);
  assert.equal(tip.hidden, true);
  pointer(env, help, 'pointerover'); clock.advance(100);
  pointer(env, help, 'pointerout', {relatedTarget: env.doc.body}); clock.advance(1000);
  assert.equal(tip.hidden, true, 'A departed target never opens later');
  assert.equal(help.hasAttribute('aria-describedby'), false);
  assert.deepEqual(env.errors, []);
});

test('a pointer can cross into the bubble to read it without losing the explanation', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  const clock = tooltipClock(env.window); t.after(clock.restore);
  pointer(env, help, 'pointerover'); clock.advance(350);
  pointer(env, help, 'pointerout', {relatedTarget: env.doc.body}); clock.advance(30);
  pointer(env, tip, 'pointerover', {relatedTarget: env.doc.body}); clock.advance(300);
  assert.equal(tip.hidden, false, 'Briefly crossing the visual gap does not dismiss readable help');
  pointer(env, tip, 'pointerout', {relatedTarget: env.doc.body}); clock.advance(150);
  assert.equal(tip.hidden, true);
});

test('core navigation, Actions and signal concepts resolve authoritative contextual help', async t => {
  const env = await dashboard({change(data) {
    data['dashboard-insights'].signals = [{analysis_id: 'help-signal', classification: 'watchlist', ticker: 'HELP',
      edge_status: 'insufficient_data', edge_observation_count: 1, source_url: 'https://example.test/filing/help', evidence: []}];
  }}); t.after(env.close);
  assert.equal(Object.isFrozen(env.window.PT.HELP), true, 'Core definitions share a frozen source');
  const checks = [
    ['nav a[href="#signals"]', 'signalsWorkspace', /qualifying trading signals/],
    ['nav a[href="#records"]', 'recordsWorkspace', /manual parser exceptions/],
    ['nav a[href="#operations"]', 'operationsWorkspace', /retained pipeline run evidence/],
    ['.nav-links a[href="#investor-edge"], nav a[href="#investor-edge"]', 'investorEdge', /historical investments performed relative to relevant benchmarks/],
    ['nav a[href="#agent"]', 'agentWorkspace', /simulated \$10,000 historical replay/],
    ['.header-actions [data-dialog="actions-dialog"]', 'actions', /Opens controls/],
    ['#run-simulation-link', 'runSimulation', /isolated TEST workflow/],
    ['#run-10k-agent-link', 'historicalReplay', /does not place real trades/],
    ['[aria-label="Explain final score"]', 'finalScore', /not a probability of profit or a recommendation/],
    ['[aria-label="Explain Investor Edge confidence"]', 'edgeConfidence', /completed observations, identity quality and sample-size adjustment/]
  ];
  const tip = env.byId('tooltip');
  for (const [selector, key, copyPattern] of checks) {
    const target = env.doc.querySelector(selector);
    assert.ok(target, `Missing contextual-help target: ${selector}`);
    assert.equal(target.dataset.tooltipKey, key);
    const dialog = target.closest('dialog');
    if (dialog) dialog.showModal();
    target.focus();
    assert.equal(tip.hidden, false, `Focus opens ${selector}`);
    assert.match(tip.textContent, copyPattern);
    assert.equal(target.getAttribute('aria-describedby'), 'tooltip');
    target.blur();
    if (dialog) dialog.close();
  }
  await env.navigate('#signals', () => env.requests.includes('ai-analyses'));
  for (const [label, key, copyPattern] of [
    ['Base score / Modifier', 'baseScoreModifier', /bounded Investor Edge adjustment/],
    ['Entry-review band', 'entryReviewBand', /not an order, target price, guaranteed fill or recommendation/],
    ['Chase ceiling', 'chaseCeiling', /not an instruction to buy/],
    ['Signal expiration', 'signalExpiration', /Missing expiration data remains unavailable/],
    ['Followable alpha', 'followableAlpha', /post-disclosure observation point/],
    ['Followable hit rate', 'followableHitRate', /completed post-disclosure observations/],
    ['Sector edge', 'sectorEdge', /Limited samples remain unavailable/]
  ]) {
    const target = env.doc.querySelector(`#signals [aria-label="Explain ${label}"]`);
    assert.ok(target, `Missing signal help: ${label}`);
    assert.equal(target.dataset.tooltipKey, key);
    target.focus(); assert.match(tip.textContent, copyPattern); target.blur();
  }
  for (const key of ['transactionOutcomes', 'disclosureOutcomes', 'confidenceShrinkage']) {
    const help = env.doc.querySelector(`#investor-edge button.help[data-tooltip-key="${key}"]`);
    assert.ok(help, `Investor Edge concept help: ${key}`);
    assert.ok(help.getAttribute('aria-label')?.startsWith('Explain '));
    assert.ok(!help.closest('article').hasAttribute('data-tooltip'), 'Whole explanatory cards are not hover targets');
  }
  assert.match(env.byId('ten-k-simulation-panel').textContent, /SIMULATED — SINGLE-RUN HISTORICAL REPLAY/);
  assert.match(env.byId('ten-k-simulation-panel').textContent, /No persistent portfolio history yet/);
  assert.match(env.byId('notifications-dialog').textContent, /this page, never external alerts/);
  assert.deepEqual(env.errors, []);
});

test('desktop tooltip-enabled links and Actions retain immediate normal activation', async t => {
  const env = await dashboard(); t.after(env.close);
  for (const selector of ['nav a[href="#investor-edge"]', 'nav a[href="#agent"]', '#run-simulation-link', '#run-10k-agent-link']) {
    const link = env.doc.querySelector(selector);
    pointer(env, link, 'pointerdown'); link.focus();
    assert.equal(activationWasBlocked(env, link), false, selector + ' must work on its first desktop click');
  }
  env.doc.querySelector('.header-actions [data-dialog="actions-dialog"]').click();
  assert.equal(env.byId('actions-dialog').open, true);
  assert.deepEqual(env.errors, []);
});

test('touch workflow help uses separate controls and never launches an action while reading', async t => {
  const env = await dashboard({coarse: true}); t.after(env.close);
  env.doc.querySelector('.header-actions [data-dialog="actions-dialog"]').click();
  const tip = env.byId('tooltip');
  for (const id of ['run-simulation-link', 'run-10k-agent-link']) {
    const link = env.byId(id), help = link.parentElement.querySelector('button.help');
    assert.ok(help, `${id} has a separate accessible explanation control`);
    assert.equal(help.dataset.tooltipKey, link.dataset.tooltipKey);
    assert.equal(help.closest('a'), null, 'A help button cannot be nested inside the workflow link');
    assert.ok(help.getAttribute('aria-label')?.startsWith('Explain '));
    let linkActivations = 0;
    link.addEventListener('click', () => linkActivations++);
    pointer(env, help, 'pointerdown', {pointerType: 'touch'}); help.focus();
    pointer(env, help, 'click', {pointerType: 'touch'});
    assert.equal(tip.hidden, false);
    assert.equal(linkActivations, 0, 'Reading help does not activate the workflow link');
    pointer(env, help, 'pointerout', {pointerType: 'touch', relatedTarget: env.doc.body});
    assert.equal(tip.hidden, false, 'Touch explanation remains pinned for reading');
    pointer(env, link, 'pointerdown', {pointerType: 'touch'});
    assert.equal(activationWasBlocked(env, link, 'touch'), false, 'The adjacent action still needs just one tap');
    assert.equal(tip.hidden, true, 'Activating the action does not flash an unreadable tooltip');
    assert.equal(linkActivations, 1);
  }
  assert.deepEqual(env.errors, []);
});

test('only explanatory touch navigation previews on first tap; second tap and ordinary navigation work', async t => {
  const env = await dashboard({coarse: true}); t.after(env.close);
  const tip = env.byId('tooltip');
  for (const selector of ['nav a[href="#investor-edge"]', 'nav a[href="#agent"]', 'nav a[href="#signals"]', 'nav a[href="#records"]', 'nav a[href="#operations"]']) {
    const link = env.doc.querySelector(selector);
    pointer(env, link, 'pointerdown', {pointerType: 'touch'});
    assert.equal(activationWasBlocked(env, link, 'touch'), true, 'First explanatory tap stays on the current page');
    assert.equal(tip.hidden, false);
    assert.match(tip.textContent, /Tap again to open/);
    pointer(env, link, 'pointerout', {pointerType: 'touch', relatedTarget: env.doc.body});
    assert.equal(tip.hidden, false);
    pointer(env, link, 'pointerdown', {pointerType: 'touch'});
    assert.equal(activationWasBlocked(env, link, 'touch'), false, 'Second intentional tap executes navigation');
    assert.equal(tip.hidden, true);
  }
  const ordinary = env.doc.querySelector('nav a[href="#overview"]');
  pointer(env, ordinary, 'pointerdown', {pointerType: 'touch'});
  assert.equal(activationWasBlocked(env, ordinary, 'touch'), false, 'Ordinary navigation never needs a second tap');
  assert.equal(env.window.PT.isCoarsePointer({pointerType: 'mouse'}), false, 'Actual mouse input overrides coarse device capability');
  assert.equal(env.window.PT.isCoarsePointer({pointerType: 'touch'}), true);
  assert.equal(env.window.PT.isCoarsePointer({}), true, 'Capability fallback is deterministic');
  assert.deepEqual(env.errors, []);
});

test('keyboard help is immediate, preserves descriptions, and Escape cancels pending hover', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  const clock = tooltipClock(env.window); t.after(clock.restore);
  help.setAttribute('aria-describedby', 'coverage-description retained-description');
  help.focus(); assert.equal(tip.hidden, false);
  assert.deepEqual(help.getAttribute('aria-describedby').split(/\s+/), ['coverage-description', 'retained-description', 'tooltip']);
  // A separate owner may add a description while a tooltip is visible.
  help.setAttribute('aria-describedby', help.getAttribute('aria-describedby') + ' later-description');
  env.doc.dispatchEvent(new env.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true})); assert.equal(tip.hidden, true);
  assert.equal(help.getAttribute('aria-describedby'), 'coverage-description retained-description later-description');
  help.blur(); pointer(env, help, 'pointerover'); clock.advance(100);
  env.doc.dispatchEvent(new env.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
  clock.advance(1000); assert.equal(tip.hidden, true, 'Escape also cancels a pending tooltip');
  help.focus(); assert.equal(tip.hidden, false);
  pointer(env, help, 'pointerout', {relatedTarget: env.doc.body}); clock.advance(200);
  assert.equal(tip.hidden, false, 'A keyboard-focused trigger retains help when the mouse moves away');
  help.blur(); assert.equal(tip.hidden, true, 'Moving keyboard focus away closes unpinned help');
  assert.deepEqual(env.errors, []);
});

test('explicit help pins immediately and supports toggle, outside and dialog dismissal', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  help.click(); assert.equal(tip.hidden, false);
  pointer(env, help, 'pointerout', {relatedTarget: env.doc.body}); assert.equal(tip.hidden, false);
  help.click(); assert.equal(tip.hidden, true, 'A second explicit help activation unpins');
  help.click(); assert.equal(tip.hidden, false);
  env.byId('situation-title').click(); assert.equal(tip.hidden, true);
  env.byId('notification-button').click();
  const modalHelp = env.doc.querySelector('#notifications-dialog [aria-label="Explain sound modes"]');
  modalHelp.click(); assert.equal(tip.hidden, false);
  assert.equal(tip.closest('dialog').id, 'notifications-dialog', 'Tooltip must render inside the active dialog layer');
  env.doc.dispatchEvent(new env.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));
  assert.equal(tip.hidden, true);
  assert.equal(tip.parentElement, env.doc.body);
  assert.equal(env.byId('notifications-dialog').open, true, 'Tooltip Escape does not close the containing dialog');
  modalHelp.click(); assert.equal(tip.hidden, false);
  env.byId('notifications-dialog').close(); assert.equal(tip.hidden, true);
  assert.equal(modalHelp.hasAttribute('aria-describedby'), false);
  assert.deepEqual(env.errors, []);
});

test('tooltip title, body and optional note render as inert text', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  const hostile = '<img src=x onerror="window.tooltipInjection=1"><script>window.tooltipInjection=2</script>';
  help.dataset.tooltipTitle = 'Title ' + hostile;
  help.dataset.tooltip = 'Body ' + hostile;
  help.dataset.tooltipNote = 'Note ' + hostile;
  help.focus();
  for (const part of ['Title ', 'Body ', 'Note ']) assert.ok(tip.textContent.includes(part + hostile));
  assert.equal(tip.querySelectorAll('img,script,[onerror]').length, 0);
  assert.equal(env.window.tooltipInjection, undefined);
  const plain = env.doc.querySelector('[aria-label="Explain run health"]');
  plain.focus();
  assert.ok(!tip.textContent.includes(hostile), 'Changing anchors removes prior rich content');
  assert.deepEqual(env.errors, []);
});

test('tooltip positions and caret remain in the viewport under deterministic geometry', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  for (const [width, height] of [[1920, 1080], [1440, 900], [1180, 820], [820, 1180], [390, 844]]) {
    Object.defineProperty(env.window, 'innerWidth', {configurable: true, value: width});
    Object.defineProperty(env.window, 'innerHeight', {configurable: true, value: height});
    const bubbleWidth = Math.min(340, width - 24), bubbleHeight = 110;
    tip.getBoundingClientRect = () => rect(parseFloat(tip.style.left) || 0, parseFloat(tip.style.top) || 0, bubbleWidth, bubbleHeight);
    for (const [left, top, placement] of [[0, 12, 'below'], [width - 44, height - 56, 'above'], [width / 2, height / 2, 'below']]) {
      help.getBoundingClientRect = () => rect(left, top, 44, 44);
      help.focus();
      assert.equal(tip.hidden, false);
      assert.equal(tip.dataset.placement, placement, `${width}×${height}: placement`);
      const x = parseFloat(tip.style.left), y = parseFloat(tip.style.top);
      assert.ok(x >= 12 && x + bubbleWidth <= width - 12, `${width}×${height}: horizontal bounds`);
      assert.ok(y >= 12 && y + bubbleHeight <= height - 12, `${width}×${height}: vertical bounds`);
      const caret = parseFloat(tip.style.getPropertyValue('--tooltip-arrow-x'));
      assert.ok(caret >= 10 && caret <= bubbleWidth - 10, 'Caret remains on bubble edge');
      assert.ok(Math.abs(x + caret - (left + 22)) <= 24, 'Caret remains near its trigger under edge clamping');
      help.blur();
    }
  }
  help.focus(); env.window.dispatchEvent(new env.window.Event('resize')); assert.equal(tip.hidden, true);
  help.blur(); help.focus(); env.doc.dispatchEvent(new env.window.Event('scroll')); assert.equal(tip.hidden, true);
  assert.deepEqual(env.errors, []);
});

test('tooltip geometry responds to layout mutations and dismisses detached anchors', async t => {
  const env = await dashboard(); t.after(env.close);
  const frames = animationFrames(env.window); t.after(frames.restore);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  let anchorRect = rect(300, 100, 44, 44);
  help.getBoundingClientRect = () => anchorRect;
  tip.getBoundingClientRect = () => rect(parseFloat(tip.style.left) || 0, parseFloat(tip.style.top) || 0, 340, 110);
  help.focus();
  const previousTop = parseFloat(tip.style.top);
  anchorRect = rect(300, 240, 44, 44);
  help.parentElement.style.paddingTop = '140px';
  await Promise.resolve(); frames.flush();
  assert.equal(parseFloat(tip.style.top) - previousTop, 140, 'A layout change repositions the existing bubble');
  help.remove(); await Promise.resolve(); frames.flush();
  assert.equal(tip.hidden, true, 'A rerendered-away anchor cannot leave stale floating help');
  assert.equal(help.hasAttribute('aria-describedby'), false);
  assert.deepEqual(env.errors, []);
});

test('visual viewport offsets constrain zoomed tooltip placement and viewport events dismiss it', async t => {
  const env = await dashboard({visualViewport: {offsetLeft: 60, offsetTop: 40, width: 390, height: 400}}); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  help.getBoundingClientRect = () => rect(404, 368, 44, 44);
  tip.getBoundingClientRect = () => rect(parseFloat(tip.style.left) || 0, parseFloat(tip.style.top) || 0, 340, 110);
  help.focus();
  const x = parseFloat(tip.style.left), y = parseFloat(tip.style.top);
  assert.ok(x >= 72 && x + 340 <= 438, 'Bubble fits the visible viewport horizontally');
  assert.ok(y >= 52 && y + 110 <= 428, 'Bubble fits the visible viewport vertically');
  assert.equal(tip.dataset.placement, 'above');
  env.window.visualViewport.dispatchEvent(new env.window.Event('resize'));
  assert.equal(tip.hidden, true);
  help.blur(); help.focus();
  env.window.visualViewport.dispatchEvent(new env.window.Event('scroll'));
  assert.equal(tip.hidden, true);
  assert.deepEqual(env.errors, []);
});

test('keyboard users can read overflowing help without moving focus or trapping it', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  help.focus();
  const content = tip.querySelector('.tooltip-content');
  Object.defineProperty(content, 'clientHeight', {value: 24});
  Object.defineProperty(content, 'scrollHeight', {value: 400});
  const key = name => {
    const event = new env.window.KeyboardEvent('keydown', {key: name, bubbles: true, cancelable: true});
    help.dispatchEvent(event); return event;
  };
  assert.equal(key('ArrowDown').defaultPrevented, true);
  assert.equal(content.scrollTop, 40);
  assert.equal(key('End').defaultPrevented, true);
  assert.equal(content.scrollTop, 376);
  content.dispatchEvent(new env.window.Event('scroll', {bubbles: true}));
  assert.equal(tip.hidden, false, 'Scrolling the explanation retains it');
  assert.equal(env.doc.activeElement, help, 'Reading never steals trigger focus');
  assert.equal(key('Tab').defaultPrevented, false, 'Normal tab navigation remains available');
  key('Escape'); assert.equal(tip.hidden, true);
  assert.deepEqual(env.errors, []);
});

test('complete Methodology & Risk opens compactly and restores trigger focus', async t => {
  const env = await dashboard(); t.after(env.close);
  const trigger = env.doc.querySelector('.sidebar-footer [data-dialog="risk-dialog"]');
  trigger.focus(); trigger.click();
  const dialog = env.byId('risk-dialog');
  assert.equal(dialog.open, true);
  assert.equal(env.doc.activeElement, dialog.querySelector('[data-close-dialog]'));
  for (const text of ['not investment advice', 'Disclosed amount ranges', 'Sample-size shrinkage', 'No $20,000 return is promised', 'Gmail, Pushover or Healthchecks']) assert.ok(dialog.textContent.includes(text), text);
  dialog.querySelector('[data-close-dialog]').click();
  assert.equal(dialog.open, false);
  assert.equal(env.doc.activeElement, trigger);
});

test('axe reports no serious/critical DOM accessibility violations (layout/color excluded)', async t => {
  const env = await dashboard(); t.after(env.close);
  env.window.eval(axe.source);
  async function check(label) {
    const result = await env.window.axe.run(env.doc, {rules: {'color-contrast': {enabled: false}}});
    const serious = result.violations.filter(row => ['serious', 'critical'].includes(row.impact));
    assert.equal(serious.length, 0, label + ': ' + JSON.stringify(serious.map(row => ({id: row.id, impact: row.impact, nodes: row.nodes.map(node => node.target)}))));
  }
  await check('Overview');
  env.byId('notification-button').click(); await check('Notification dialog');
  env.byId('notifications-dialog').close();
  await env.navigate('#records', () => env.byId('filings-body').children.length === 50); await check('Records table');
  env.doc.querySelector('.sidebar-footer [data-dialog="risk-dialog"]').click(); await check('Methodology dialog');
});


function reviewFixture(data, count = 1) {
  const review = {review_id: 'review:paper/&?=', filing_key: data.filings[0].filing_key, filing_available: true,
    source: 'senate', branch: 'legislative', report_id: data.filings[0].report_id, filer: 'Paper Filing Official',
    category: 'manual_exception', is_synthetic_test: false, filed_date: '2026-08-01',
    observed_at_utc: '2026-08-28T17:46:35Z', reason: 'Paper images need manual parser review',
    filing_status: 'review_required', source_url: 'https://example.test/paper'};
  data.filings[0] = {...data.filings[0], filer: review.filer, status: review.filing_status, review_reason: review.reason};
  data['pending-reviews'] = Array.from({length: count}, (_, i) => ({...review, review_id: review.review_id + i, report_id: i ? 'paper-' + i : review.report_id}));
  data['pending-reviews'].push(
    {...review, review_id: 'request', source: 'oge', branch: 'executive', filer: 'Access Required Official', category: 'access_required'},
    {...review, review_id: 'house', source: 'house', branch: 'legislative', filer: 'House Review Official', category: 'other'},
    {...review, review_id: 'custom', source: 'ethics-office', branch: 'executive', filer: 'Custom Source Official', category: 'other'},
    {...review, review_id: 'TEST:synthetic', filer: 'TEST ONLY', is_synthetic_test: true});
  Object.assign(data['dashboard-insights'].reviews, {manual_exception: count, access_required: 1, other: 2, total: count + 3, latest: data['pending-reviews'].slice(0, 8)});
  data['dashboard-insights'].source_filters.push({value: 'ethics-office', label: 'Ethics Office', field: 'source'});
}

function choose(env, id, value) {
  const control = env.byId(id); control.value = value;
  control.dispatchEvent(new env.window.Event('change', {bubbles: true}));
}

test('dashboard parser card clears stale filters and opens the actual exception and retained filing', async t => {
  const env = await dashboard({change: reviewFixture}); t.after(env.close);
  assert.equal(env.byId('attention-exceptions').textContent, '1');
  await env.navigate('#records/reviews', () => env.byId('reviews-body').children.length === 5);
  choose(env, 'reviews-source', 'oge'); choose(env, 'reviews-date-from', '2026-08-30');
  env.byId('reviews-search').value = 'no match';
  env.byId('reviews-search').dispatchEvent(new env.window.Event('input', {bubbles: true}));
  await env.navigate('#overview');
  env.byId('attention-exceptions').closest('a').click();
  await waitFor(() => env.byId('reviews-category').value === 'manual_exception' && env.byId('reviews-body').children.length === 1, 'parser card routing');
  await tick(220); // A pending debounced search must not overwrite the deep link.
  assert.equal(env.byId('records').hidden, false);
  assert.equal(env.byId('reviews-source').value, '');
  assert.equal(env.byId('reviews-date-from').value, '');
  assert.equal(env.byId('reviews-search').value, '');
  assert.match(env.byId('review-categories').textContent, /Manual Parser Exceptions: 1/);
  assert.match(env.byId('reviews-body').textContent, /Paper Filing Official/);
  assert.ok(!env.byId('reviews-body').textContent.includes('TEST ONLY'));
  assert.match(env.byId('reviews-body').textContent, /Paper images need manual parser review/);
  const row = env.byId('reviews-body').firstElementChild;
  assert.ok(row.querySelector('a.record-link'));
  row.querySelectorAll('td')[2].click();
  await waitFor(() => env.byId('selected-filings-title'), 'underlying source record selection');
  assert.equal(env.byId('panel-filings').hidden, false);
  assert.match(env.byId('filings-body').textContent, /fixture-0/);
  assert.match(env.byId('filings-body').textContent, /Paper images need manual parser review/);
  assert.equal(env.doc.activeElement.id, 'selected-filings-title');
  env.byId('filings-clear').click();
  assert.equal(env.byId('filings-body').children.length, 50);
  assert.equal(env.window.location.hash, '#records/filings');
  assert.deepEqual(env.errors, []);
});

test('parser links survive reload and history; chip and clear filters restore normal records', async t => {
  const env = await dashboard({change: reviewFixture, hash: '#records/reviews?category=manual_exception'}); t.after(env.close);
  await waitFor(() => env.byId('reviews-body').children.length === 1, 'initial deep link');
  assert.equal(env.byId('reviews-category').value, 'manual_exception');
  env.byId('clear-review-category').click();
  assert.equal(env.byId('reviews-category').value, '');
  assert.equal(env.byId('reviews-body').children.length, 5);
  assert.equal(env.window.location.hash, '#records/reviews');
  choose(env, 'reviews-category', 'manual_exception');
  assert.match(env.window.location.hash, /category=manual_exception/);
  await env.navigate('#signals');
  env.window.history.back();
  await waitFor(() => !env.byId('records').hidden, 'back to exceptions');
  assert.equal(env.byId('reviews-body').children.length, 1);
  env.byId('reviews-clear').click();
  assert.equal(env.byId('reviews-body').children.length, 5);
  assert.equal(env.window.location.hash, '#records/reviews');
});

test('complete parser collection is paginated beyond the compact eight-row overview', async t => {
  const env = await dashboard({change: data => reviewFixture(data, 53), hash: '#records/reviews?category=manual_exception'}); t.after(env.close);
  await waitFor(() => env.byId('reviews-body').children.length === 50, 'full exceptions');
  assert.equal(env.byId('attention-exceptions').textContent, '53');
  assert.match(env.byId('reviews-count-label').textContent, /1–50 of 53/);
  env.byId('reviews-more').click();
  assert.equal(env.byId('reviews-body').children.length, 3);
  assert.equal(env.byId('reviews-more').disabled, true);
  assert.ok([...env.byId('reviews-body').children].every(row => row.querySelector('.record-link')));
});

test('no parser exceptions has a positive empty state without an empty table', async t => {
  const env = await dashboard({hash: '#records/reviews?category=manual_exception'}); t.after(env.close);
  await waitFor(() => env.requests.includes('pending-reviews'), 'empty review ledger');
  assert.equal(env.byId('attention-exceptions').textContent, '0');
  assert.equal(env.byId('reviews-count-label').textContent, 'No records currently require manual parser review.');
  assert.equal(env.doc.querySelector('#panel-reviews .table-wrap').hidden, true);
  assert.equal(env.doc.querySelector('#panel-reviews .pagination').hidden, true);
});

test('Review Source uses canonical branch fields plus all narrow sources and uppercase OGE', async t => {
  const env = await dashboard({change: reviewFixture, hash: '#records/reviews'}); t.after(env.close);
  await waitFor(() => env.byId('reviews-body').children.length === 5, 'review taxonomy');
  const options = [...env.byId('reviews-source').options].map(option => option.textContent);
  for (const label of ['All Sources', 'Executive', 'Legislative', 'OGE', 'Senate', 'House', 'Ethics Office']) assert.ok(options.includes(label), label);
  assert.ok(!options.includes('Oge'));
  for (const [source, count] of [['branch:executive', 2], ['branch:legislative', 3], ['senate', 2], ['house', 1], ['oge', 1], ['ethics-office', 1], ['', 5]]) {
    choose(env, 'reviews-source', source);
    assert.equal(env.byId('reviews-body').children.length, count, source);
  }
  assert.equal(env.window.PT.title('Oge Form 278-T'), 'OGE Form 278-T');
  choose(env, 'reviews-source', 'oge');
  assert.match(env.byId('reviews-body').textContent, /OGE/);
  choose(env, 'reviews-category', 'manual_exception');
  assert.match(env.byId('reviews-body').textContent, /No parser exceptions match these additional filters/);
});

test('orphan and hostile review records remain inspectable without inventing filings or markup', async t => {
  const hostile = '<img src=x onerror="window.hostileExecuted=1">';
  const env = await dashboard({change(data) {
    reviewFixture(data); const row = data['pending-reviews'][0];
    delete row.filing_key; row.filing_available = false; row.filer = hostile; row.reason = hostile;
    row.review_id = 'review:/?&=%'; row.source_url = 'javascript:window.hostileExecuted=2';
  }, hash: '#records/reviews?category=manual_exception'}); t.after(env.close);
  await waitFor(() => env.byId('reviews-body').querySelector('.record-link'), 'orphan review');
  env.byId('reviews-body').querySelector('.record-link').click();
  await waitFor(() => env.byId('selected-reviews-title'), 'orphan review selected');
  assert.equal(env.byId('panel-reviews').hidden, false);
  assert.match(env.byId('reviews-body').textContent, /No matching filing is retained/);
  assert.match(env.byId('reviews-body').textContent, /review:\/\?&=%/);
  assert.equal(env.byId('reviews-body').querySelectorAll('img,[onerror],script,a[href^="javascript:"]').length, 0);
  assert.equal(env.window.hostileExecuted, undefined);
});

test('review refresh advances card and list together, and rejects a partial publication', async t => {
  const env = await dashboard({change: reviewFixture, hash: '#records/reviews?category=manual_exception'}); t.after(env.close);
  await waitFor(() => env.byId('reviews-body').children.length === 1, 'initial exception');
  const before = env.window.localStorage.getItem(KEY);
  env.data['dashboard-insights'].reviews.manual_exception = 2;
  env.data['dashboard-insights'].reviews.total = 5;
  await env.refresh();
  assert.equal(env.byId('error-banner').hidden, false);
  assert.match(env.byId('error-banner').textContent, /different publications/);
  assert.equal(env.byId('attention-exceptions').textContent, '1');
  assert.equal(env.byId('reviews-body').children.length, 1);
  assert.equal(env.window.localStorage.getItem(KEY), before);
  env.data['pending-reviews'].push({...env.data['pending-reviews'][0], review_id: 'second'});
  await env.refresh();
  assert.equal(env.byId('error-banner').hidden, true);
  assert.equal(env.byId('attention-exceptions').textContent, '2');
  assert.equal(env.byId('reviews-body').children.length, 2);
  assert.match(env.byId('review-categories').textContent, /Manual Parser Exceptions: 2/);
});

test('opening reviews during an in-flight refresh commits the card and newly loaded list together', async t => {
  const env = await dashboard({change: reviewFixture}); t.after(env.close);
  await env.navigate('#records/filings', () => env.byId('filings-body').children.length === 50);
  env.data['dashboard-insights'].generated_utc = '2026-08-31T12:00:00Z';
  Object.assign(env.data['dashboard-insights'].reviews, {manual_exception: 2, total: 5});

  // Hold an already-open table while the user opens Reviews for the first time.
  // That lazy load legitimately sees the old model; the refresh must restage it.
  const originalFetch = env.window.fetch;
  let releaseFilings;
  env.window.fetch = async value => {
    if (new URL(value, env.window.location.href).pathname.endsWith('/filings.json')) {
      return new Promise(resolve => {
        releaseFilings = () => resolve({ok: true, status: 200, json: async () => copy(env.data.filings)});
      });
    }
    return originalFetch(value);
  };
  t.after(() => releaseFilings?.());
  env.byId('refresh-button').click();
  await waitFor(() => releaseFilings, 'refresh waiting on existing filing table');
  await env.navigate('#records/reviews?category=manual_exception', () => env.byId('reviews-body').children.length === 1);
  assert.equal(env.byId('attention-exceptions').textContent, '1');
  assert.match(env.byId('reviews-body').textContent, /Paper Filing Official/);

  env.data['pending-reviews'].push({...env.data['pending-reviews'][0], review_id: 'arrived-during-refresh'});
  releaseFilings();
  await waitFor(() => !env.byId('refresh-button').disabled, 'refresh includes newly opened reviews');
  assert.equal(env.byId('error-banner').hidden, true);
  assert.equal(env.byId('attention-exceptions').textContent, '2');
  assert.equal(env.byId('reviews-body').children.length, 2);
  assert.match(env.byId('reviews-count-label').textContent, /1–2 of 2 matching records/);
  assert.match(env.byId('review-categories').textContent, /Manual Parser Exceptions: 2/);
  assert.equal(env.requests.filter(name => name === 'pending-reviews').length, 2, 'Refresh fetches the newly opened review ledger again');
  assert.deepEqual(env.errors, []);
});

test('switching from a filing detail to an orphan review focuses the visible selected record', async t => {
  const env = await dashboard({change(data) {
    reviewFixture(data);
    data['pending-reviews'].push({...data['pending-reviews'][0], review_id: 'orphan-after-filing',
      filing_key: 'missing-filing', filing_available: false, filer: 'Orphan Review Official'});
    Object.assign(data['dashboard-insights'].reviews, {manual_exception: 2, total: 5});
  }}); t.after(env.close);
  await env.navigate('#records/reviews?category=manual_exception', () => env.byId('reviews-body').children.length === 2);
  const filingLink = [...env.byId('reviews-body').querySelectorAll('.record-link')].find(link => link.textContent.includes('Paper Filing Official'));
  filingLink.click();
  await waitFor(() => env.byId('selected-filings-title'), 'retained filing detail');
  assert.equal(env.doc.activeElement.id, 'selected-filings-title');

  await env.navigate('#records/reviews?category=manual_exception', () => env.byId('panel-reviews').hidden === false);
  const orphanLink = [...env.byId('reviews-body').querySelectorAll('.record-link')].find(link => link.textContent.includes('Orphan Review Official'));
  assert.match(orphanLink.getAttribute('href'), /#records\/reviews\?review=/, 'An unverified retained filing key must use the review fallback');
  orphanLink.click();
  await waitFor(() => env.byId('selected-reviews-title'), 'original orphan review detail');
  assert.equal(env.byId('panel-filings').hidden, true);
  assert.equal(env.byId('panel-reviews').hidden, false);
  assert.equal(env.doc.activeElement, env.byId('selected-reviews-title'));
  assert.equal(env.doc.activeElement.closest('.record-panel').id, 'panel-reviews');
  assert.match(env.byId('reviews-body').textContent, /No matching filing is retained/);
  const ids = [...env.doc.querySelectorAll('[id]')].map(node => node.id);
  assert.equal(new Set(ids).size, ids.length, 'Retained details in inactive panels must not duplicate element IDs');
  assert.deepEqual(env.errors, []);
});

test('new workspace tooltips share mouse delay, immediate focus and immediate desktop activation', async t => {
  const env = await dashboard(); t.after(env.close);
  const clock = tooltipClock(env.window); t.after(clock.restore);
  for (const section of ['signals', 'records', 'operations', 'investor-edge', 'agent']) {
    const target = env.doc.querySelector(`nav a[href="#${section}"]`);
    pointer(env, target, 'pointerover'); clock.advance(299);
    assert.equal(env.byId('tooltip').hidden, true);
    clock.advance(1); assert.equal(env.byId('tooltip').hidden, false);
    pointer(env, target, 'pointerout', {relatedTarget: env.doc.body}); clock.advance(150);
    target.focus(); assert.equal(env.byId('tooltip').hidden, false);
    assert.equal(target.getAttribute('aria-describedby'), 'tooltip');
    assert.equal(activationWasBlocked(env, target), false);
    target.blur(); clock.advance(150);
  }
});

// These spies verify route/focus intent. Header/sidebar geometry and actual
// wheel, touch and keyboard scrolling still require a rendered browser.
function recordScrollRequests(env) {
  const requests = [];
  env.window.HTMLElement.prototype.scrollIntoView = function (options) {
    requests.push({target: this, block: options?.block, hidden: Boolean(this.closest('[hidden]'))});
  };
  return requests;
}

function deferLedger(env, name) {
  const originalFetch = env.window.fetch;
  let release;
  env.window.fetch = async value => {
    if (new URL(value, env.window.location.href).pathname.endsWith(`/${name}.json`)) {
      return new Promise(resolve => { release = () => resolve(originalFetch(value)); });
    }
    return originalFetch(value);
  };
  return {get waiting() { return Boolean(release); }, release() { const pending = release; release = undefined; pending?.(); },
    restore() { env.window.fetch = originalFetch; }};
}

test('initial landing keeps wrapped Workspace navigation in view while returning to an empty route positions Overview', async t => {
  const scrolls = [];
  const env = await dashboard({beforeScript(window) {
    window.HTMLElement.prototype.scrollIntoView = function () { scrolls.push(this); };
  }}); t.after(env.close);
  await tick(15);
  assert.equal(env.window.location.hash, '');
  assert.equal(scrolls.length, 0, 'Initial no-hash landing must not scroll past the mobile Workspace rows');
  await env.navigate('#signals', () => scrolls.length === 1);
  assert.equal(scrolls[0], env.byId('signals'));
  await env.navigate('', () => scrolls.length === 2);
  assert.equal(env.window.location.hash, '');
  assert.equal(scrolls[1], env.byId('overview'), 'Later navigation to an empty hash still returns to Overview');
  assert.equal(env.byId('overview').hidden, false);
  assert.deepEqual(env.errors, []);
});

test('ordinary routes reveal their destination after lazy loading without resetting keyboard focus or refresh position', async t => {
  const env = await dashboard(); t.after(env.close);
  const scrolls = recordScrollRequests(env), ledger = deferLedger(env, 'filings'); t.after(ledger.release);
  env.data['investor-edge'] = {investors: []};
  const workspaceLink = env.doc.querySelector('[data-section="records"]');
  workspaceLink.focus();
  await env.navigate('#records/filings', () => ledger.waiting);
  assert.equal(scrolls.length, 0, 'Do not choose a final position before the lazy table exists');
  ledger.release();
  await waitFor(() => scrolls.length === 1, 'filing route scroll after loading');
  assert.equal(env.byId('filings-body').children.length, 50);
  assert.equal(scrolls[0].target, env.byId('records'));
  assert.equal(scrolls[0].block, 'start');
  assert.equal(scrolls[0].hidden, false);
  assert.equal(env.doc.activeElement, workspaceLink, 'Workspace keyboard navigation keeps its normal tab order');

  for (const route of ['signals', 'investor-edge', 'agent', 'operations', 'overview']) {
    const before = scrolls.length;
    await env.navigate(`#${route}`, () => scrolls.length > before);
    assert.equal(scrolls.length, before + 1, `One position request for ${route}`);
    assert.equal(scrolls.at(-1).target, env.byId(route));
    assert.equal(scrolls.at(-1).hidden, false);
    assert.equal(scrolls.at(-1).block, 'start');
  }
  // Refreshing a page is not navigation and must not pull a reader to its top.
  ledger.restore();
  const beforeRefresh = scrolls.length;
  await env.refresh();
  assert.equal(scrolls.length, beforeRefresh);
  assert.deepEqual(env.errors, []);
});

test('a slow old route cannot scroll the newer visible destination', async t => {
  const env = await dashboard(); t.after(env.close);
  const scrolls = recordScrollRequests(env), ledger = deferLedger(env, 'filings'); t.after(ledger.release);
  await env.navigate('#records/filings', () => ledger.waiting);
  await env.navigate('#signals', () => scrolls.length === 1);
  assert.equal(scrolls[0].target, env.byId('signals'));
  const focused = env.doc.querySelector('[data-section="signals"]'); focused.focus();
  ledger.release();
  await waitFor(() => env.byId('filings-body').children.length === 50, 'old filing request completed');
  await tick(15);
  assert.equal(env.byId('records').hidden, true);
  assert.equal(env.byId('signals').hidden, false);
  assert.equal(scrolls.length, 1, 'Settling a stale route must not reposition the current page');
  assert.equal(env.doc.activeElement, focused);
  assert.deepEqual(env.errors, []);
});

test('notification hash opens its overlay without moving the underlying document or its dialog focus', async t => {
  const env = await dashboard(); t.after(env.close);
  const scrolls = recordScrollRequests(env);
  await env.navigate('#notifications', () => env.byId('notifications-dialog').open);
  const dialog = env.byId('notifications-dialog');
  assert.equal(scrolls.length, 0);
  assert.equal(env.doc.activeElement, dialog.querySelector('[data-close-dialog]'));
  dialog.querySelector('[data-close-dialog]').click();
  assert.equal(env.doc.activeElement, env.byId('changes-card'));
  assert.equal(scrolls.length, 0);
  assert.deepEqual(env.errors, []);
});

test('an awaited selected record does not scroll or steal focus from an Actions dialog opened meanwhile', async t => {
  const env = await dashboard(); t.after(env.close);
  const scrolls = recordScrollRequests(env), ledger = deferLedger(env, 'filings'); t.after(ledger.release);
  await env.navigate('#records/filings?filing=fixture-0', () => ledger.waiting);
  const opener = env.doc.querySelector('.header-actions [data-dialog="actions-dialog"]');
  opener.focus(); opener.click();
  const dialog = env.byId('actions-dialog'), close = dialog.querySelector('[data-close-dialog]');
  assert.equal(dialog.open, true);
  assert.equal(env.doc.activeElement, close);
  ledger.release();
  await waitFor(() => env.byId('selected-filings-title'), 'selected record loaded behind dialog');
  await tick(15);
  assert.equal(scrolls.length, 0);
  assert.equal(env.doc.activeElement, close);
  close.click();
  assert.equal(env.doc.activeElement, opener);
  assert.deepEqual(env.errors, []);
});

test('shell header measurement tracks its rendered height when controls resize without a window resize', async t => {
  let height = 84, headerObserver;
  const env = await dashboard({beforeScript(window) {
    const header = window.document.querySelector('.app-header');
    header.getBoundingClientRect = () => rect(0, 0, 390, height);
    window.ResizeObserver = class {
      constructor(callback) { this.callback = callback; }
      observe(target) { if (target === header) headerObserver = this; }
      disconnect() {}
    };
  }}); t.after(env.close);
  const measuredHeight = () => env.doc.documentElement.style.getPropertyValue('--header-height');
  assert.equal(measuredHeight(), '84px');
  assert.ok(headerObserver, 'Header content changes must be observed independently from viewport resizing');
  height = 137.5; headerObserver.callback();
  assert.equal(measuredHeight(), '137.5px');
  height = 84; headerObserver.callback();
  assert.equal(measuredHeight(), '84px', 'Returning to a single row must release unused sidebar/anchor offset');
  assert.deepEqual(env.errors, []);
});

test('shell header measurement follows viewport resizing when ResizeObserver is unavailable', async t => {
  let height = 132;
  const env = await dashboard({beforeScript(window) {
    window.ResizeObserver = undefined;
    window.document.querySelector('.app-header').getBoundingClientRect = () => rect(0, 0, 390, height);
  }}); t.after(env.close);
  const measuredHeight = () => env.doc.documentElement.style.getPropertyValue('--header-height');
  assert.equal(measuredHeight(), '132px');
  height = 84; env.window.dispatchEvent(new env.window.Event('resize'));
  assert.equal(measuredHeight(), '84px');
  assert.deepEqual(env.errors, []);
});
