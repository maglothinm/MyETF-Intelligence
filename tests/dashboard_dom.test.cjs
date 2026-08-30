'use strict';

// JSDOM checks DOM behavior, not browser rendering, touch, CSP, or audio policy.
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
  const dom = new JSDOM(fs.readFileSync(path.join(build, 'index.html'), 'utf8'), {url: 'https://dashboard.test/PolitiTrack/',
    runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole});
  const {window} = dom;
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
  return {dom, window, doc, byId, data, requests, errors, failures, navigate, refresh, close: () => window.close()};
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

test('tooltips support hover, focus, click, Escape and outside dismissal including dialogs', async t => {
  const env = await dashboard(); t.after(env.close);
  const tip = env.byId('tooltip'), help = env.doc.querySelector('[aria-label="Explain coverage status"]');
  help.dispatchEvent(new env.window.Event('pointerover', {bubbles: true})); assert.equal(tip.hidden, false);
  assert.equal(help.getAttribute('aria-describedby'), 'tooltip');
  help.dispatchEvent(new env.window.Event('pointerout', {bubbles: true})); assert.equal(tip.hidden, true);
  help.focus(); assert.equal(tip.hidden, false);
  env.doc.dispatchEvent(new env.window.KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true})); assert.equal(tip.hidden, true);
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
