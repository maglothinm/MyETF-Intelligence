'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {PolitiTrackNotifications, STORAGE_KEY, LIMITS, inQuietHours, safeLink} = require('../scripts/dashboard_assets/notifications.js');

class MemoryStorage {
  constructor() { this.values = new Map(); this.writes = 0; }
  getItem(key) { return this.values.get(key) || null; }
  setItem(key, value) { this.values.set(key, value); this.writes += 1; }
}
function locks() {
  let tail = Promise.resolve();
  return {request(_name, _options, work) {
    const next = tail.then(work); tail = next.catch(() => {}); return next;
  }};
}
function audio() {
  const context = {state: 'suspended', currentTime: 0, destination: {}, notes: [], resumes: 0,
    resume() { this.resumes += 1; this.state = 'running'; return Promise.resolve(); }, close() { this.state = 'closed'; },
    createOscillator() {
      return {frequency: {setValueAtTime: value => context.notes.push(value)}, connect() {}, disconnect() {}, start() {}, stop() {}};
    },
    createGain() { return {gain: {setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}}, connect() {}, disconnect() {}}; }};
  return context;
}
function setup(options = {}) {
  const storage = options.storage || new MemoryStorage();
  const context = audio();
  let now = Date.parse('2026-08-30T12:00:00Z'), created = 0;
  const listeners = {};
  const host = {document: {visibilityState: 'visible', hasFocus: () => true}, navigator: {userActivation: {isActive: false}},
    addEventListener(name, handler) { listeners[name] = handler; }, removeEventListener(name) { delete listeners[name]; }};
  const engine = new PolitiTrackNotifications({storage, now: () => now, locks: options.locks === undefined ? locks() : options.locks,
    host, audioFactory: () => { created += 1; return context; }, ...options});
  return {engine, storage, context, host, listeners, get created() { return created; }, advance: milliseconds => { now += milliseconds; }};
}
const gesture = {isTrusted: true, type: 'click'};
function model(update = {}) {
  return {generated_at: '2026-08-30T12:00:00Z', notifications: {filing_ids: ['filing-old'], trade_ids: ['trade-old'], qualifying_signals: [],
    runs: [{id: 'legislative:old', branch: 'legislative', status: 'success', conclusion: 'success', at: '2026-08-30T11:00:00Z', error_count: 0, url: 'https://github.com/example/run/1'}],
    simulation_results: [], current_incidents: [], ...update}};
}
const signal = (id, classification = 'high_priority') => ({analysis_id: id, classification, ticker: 'TEST', analyzed_at: '2026-08-30T12:00:00Z', link: '#signals'});
async function render(engine, data) { const pending = engine.prepare(data); await pending.commit(); return pending; }

test('first hydration establishes baseline only after render commit, without events or audio', async () => {
  const env = setup();
  const pending = env.engine.prepare(model({filing_ids: Array.from({length: 6000}, (_, i) => 'retained-' + i), qualifying_signals: [signal('retained')]}));
  assert.equal(pending.firstVisit, true);
  assert.deepEqual(pending.events, []);
  assert.equal(env.storage.writes, 0);
  assert.equal(env.engine.getState().settings.mode, 'off');
  await pending.commit();
  assert.equal(env.engine.getState().unread, 0);
  assert.equal(env.created, 0);
  assert.equal(env.context.notes.length, 0);
  assert.ok(JSON.parse(env.storage.getItem(STORAGE_KEY)).baseline);
});

test('failed render or incomplete input never commits the browser baseline', async () => {
  const env = setup();
  await render(env.engine, model());
  const saved = env.storage.getItem(STORAGE_KEY);
  const pending = env.engine.prepare(model({qualifying_signals: [signal('not-rendered')]}));
  assert.equal(pending.events.length, 1);
  assert.equal(env.storage.getItem(STORAGE_KEY), saved);
  assert.throws(() => env.engine.prepare({notifications: {}}), /Incomplete/);
  assert.equal(env.storage.getItem(STORAGE_KEY), saved);
});

test('new qualifying burst is one visual record and one two-note chime after gesture', async () => {
  const env = setup();
  await render(env.engine, model());
  await env.engine.setSettings({mode: 'all'});
  assert.equal(await env.engine.enableSound(), false);
  assert.equal(env.created, 0);
  assert.equal(await env.engine.enableSound(gesture), true);
  const pending = await render(env.engine, model({qualifying_signals: [signal('a'), signal('b', 'watchlist'), signal('c')]}));
  assert.equal(pending.changes.signals, 3);
  assert.equal(env.engine.getState().events.length, 1);
  assert.equal(env.engine.getState().events[0].count, 3);
  assert.equal(env.context.notes.length, 2);
  assert.equal(env.engine.getState().unread, 1);
});

test('weak/archive analyses and entry plans never become qualifying notifications', async () => {
  const env = setup();
  await render(env.engine, model());
  const pending = await render(env.engine, model({qualifying_signals: [signal('a', 'weak_signal'), {...signal('b', 'archive'), entry_plan: {status: 'review_now'}}]}));
  assert.equal(pending.changes.signals, 0);
  assert.equal(env.engine.getState().unread, 0);
});

test('ordinary filings and transactions are grouped and silent with all audio enabled', async () => {
  const env = setup();
  await render(env.engine, model());
  await env.engine.setSettings({mode: 'all'}); await env.engine.enableSound(gesture);
  const pending = await render(env.engine, model({filing_ids: ['filing-old', 'new-1', 'new-2'], trade_ids: ['trade-old', 'new-trade']}));
  assert.deepEqual(pending.changes, {filings: 2, transactions: 1, signals: 0, simulations: 0});
  assert.equal(env.engine.getState().events.length, 1);
  assert.match(env.engine.getState().events[0].summary, /2 new filings.*1 newly parsed/);
  assert.equal(env.context.notes.length, 0);
});

test('unchanged refresh, reload, storage sync and reconnect do not replay notification audio', async () => {
  const shared = new MemoryStorage(), sharedLocks = locks();
  const first = setup({storage: shared, locks: sharedLocks});
  await render(first.engine, model()); await first.engine.enableSound(gesture);
  const current = model({qualifying_signals: [signal('new')]});
  await render(first.engine, current); await render(first.engine, current);
  first.listeners.storage({key: STORAGE_KEY});
  await render(first.engine, current);
  assert.equal(first.context.notes.length, 2);
  const reloaded = setup({storage: shared, locks: sharedLocks});
  assert.equal(reloaded.engine.getState().sound.armed, false);
  await reloaded.engine.enableSound(gesture); await render(reloaded.engine, current);
  assert.equal(reloaded.context.notes.length, 0);
  assert.equal(reloaded.engine.getState().events.length, 1);
});

test('simultaneously prepared tabs acquire one durable sound claim', async () => {
  const shared = new MemoryStorage(), sharedLocks = locks();
  const a = setup({storage: shared, locks: sharedLocks}), b = setup({storage: shared, locks: sharedLocks});
  await render(a.engine, model()); await render(b.engine, model());
  await a.engine.enableSound(gesture); await b.engine.enableSound(gesture);
  const next = model({qualifying_signals: [signal('cross-tab')]});
  const ap = a.engine.prepare(next), bp = b.engine.prepare(next);
  await Promise.all([ap.commit(), bp.commit()]);
  assert.equal(a.context.notes.length + b.context.notes.length, 2);
  assert.equal(JSON.parse(shared.getItem(STORAGE_KEY)).events.length, 1);
});

test('without atomic cross-tab coordination automatic sound fails silent', async () => {
  const env = setup({locks: null});
  await render(env.engine, model()); await env.engine.enableSound(gesture);
  await render(env.engine, model({qualifying_signals: [signal('one')]}));
  assert.equal(env.engine.getState().events.length, 1);
  assert.equal(env.context.notes.length, 0);
  assert.equal(env.engine.getState().sound.coordinationAvailable, false);
});

test('overnight and daytime quiet hours suppress audio without hiding visual events', async () => {
  assert.equal(inQuietHours({enabled: true, start: '22:00', end: '07:00'}, new Date(2026, 7, 30, 23, 15)), true);
  assert.equal(inQuietHours({enabled: true, start: '22:00', end: '07:00'}, new Date(2026, 7, 30, 3, 15)), true);
  assert.equal(inQuietHours({enabled: true, start: '22:00', end: '07:00'}, new Date(2026, 7, 30, 7, 0)), false);
  assert.equal(inQuietHours({enabled: true, start: '09:00', end: '17:00'}, new Date(2026, 7, 30, 12)), true);
  const env = setup();
  await render(env.engine, model()); await env.engine.enableSound(gesture);
  await env.engine.setSettings({quietHours: {enabled: true, start: '00:00', end: '00:00'}});
  await render(env.engine, model({qualifying_signals: [signal('quiet')]}));
  assert.equal(env.engine.getState().unread, 1);
  assert.equal(env.context.notes.length, 0);
  await env.engine.setSettings({quietHours: {enabled: false}});
  await render(env.engine, model({qualifying_signals: [signal('quiet')]}));
  assert.equal(env.context.notes.length, 0);
});

test('high-priority mode excludes watchlist audio; ordinary mode changes do not unlock audio', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.setSettings({mode: 'all'});
  await render(env.engine, model({qualifying_signals: [signal('unarmed')]}));
  assert.equal(env.created, 0);
  await env.engine.setSettings({mode: 'high'}); await env.engine.enableSound(gesture);
  await render(env.engine, model({qualifying_signals: [signal('unarmed'), signal('watch', 'watchlist')]}));
  assert.equal(env.context.notes.length, 0);
  assert.equal(env.engine.getState().actionable, 2, 'Watchlist is an actionable classification even without a high-priority chime');
  await render(env.engine, model({qualifying_signals: [signal('unarmed'), signal('watch', 'watchlist'), signal('high')]}));
  assert.equal(env.context.notes.length, 2);
});

test('high-priority mode includes supported operation failures and stale incidents', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.enableSound(gesture);
  assert.equal(env.engine.getState().settings.mode, 'high');
  await render(env.engine, model({current_incidents: [{id: 'failure-high', branch: 'executive', kind: 'failure', since: '2026-08-30T12:00:00Z'}]}));
  assert.deepEqual(env.context.notes, [440, 329.63]);
  await render(env.engine, model({current_incidents: [{id: 'failure-high', branch: 'executive', kind: 'failure', since: '2026-08-30T12:00:00Z'}, {id: 'stale-high', branch: 'legislative', kind: 'stale', since: '2026-08-30T12:00:00Z'}]}));
  assert.deepEqual(env.context.notes, [440, 329.63, 440, 329.63]);
});

test('first visit failure is current status without historical unread entries; same branch later recovers', async () => {
  const env = setup();
  const failure = {id: 'legislative:bad', branch: 'legislative', kind: 'failure', since: '2026-08-30T10:00:00Z', url: '#operations'};
  await render(env.engine, model({current_incidents: [failure], runs: [{id: 'legislative:bad', branch: 'legislative', at: failure.since, status: 'failure', error_count: 1}]}));
  assert.equal(env.engine.getState().currentIncidents.length, 1);
  assert.equal(env.engine.getState().unread, 0);
  // Unknown evidence cannot manufacture a recovery or discard the incident.
  await render(env.engine, model({runs: []}));
  assert.equal(env.engine.getState().unread, 0);
  await render(env.engine, model());
  assert.equal(env.engine.getState().events.length, 1);
  assert.match(env.engine.getState().events[0].summary, /legislative recovered/);
  assert.equal(env.engine.getState().events[0].severity, 'success');
  assert.equal(env.engine.getState().events[0].pattern, null);
});

test('new failure sounds once; another branch success cannot resolve it', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.setSettings({mode: 'all'}); await env.engine.enableSound(gesture);
  const failure = {id: 'executive:bad', branch: 'executive', kind: 'failure', since: '2026-08-30T11:30:00Z'};
  await render(env.engine, model({current_incidents: [failure]}));
  assert.deepEqual(env.context.notes, [440, 329.63]);
  await render(env.engine, model());
  assert.equal(env.engine.getState().events.length, 1);
  assert.equal(env.context.notes.length, 2);
});

test('a successful run with errors cannot be labeled recovery', async () => {
  const env = setup();
  const incident = {id: 'legislative:bad', branch: 'legislative', kind: 'failure', since: '2026-08-30T10:00:00Z'};
  await render(env.engine, model({current_incidents: [incident]}));
  await render(env.engine, model({runs: [{id: 'legislative:warn', branch: 'legislative', status: 'success', conclusion: 'success', at: '2026-08-30T11:00:00Z', error_count: 2}]}));
  assert.equal(env.engine.getState().events.length, 0);
});

test('only explicit historical replay results produce simulated completion records', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.setSettings({mode: 'all'}); await env.engine.enableSound(gesture);
  const acceptance = {simulation_id: 'acceptance-1', kind: 'acceptance', status: 'success', timestamp: '2026-08-30T12:00:00Z'};
  await render(env.engine, model({simulation_results: [acceptance]}));
  assert.equal(env.engine.getState().unread, 0, 'Opening Actions is not evidence of a user dispatch');
  await render(env.engine, model({simulation_results: [acceptance, {simulation_id: 'replay-1', kind: 'historical_replay', status: 'success', timestamp: '2026-08-30T12:00:00Z', url: '#agent'}]}));
  assert.equal(env.engine.getState().events[0].simulation, true);
  assert.match(env.engine.getState().events[0].summary, /SIMULATED.*historical replay/);
  assert.deepEqual(env.context.notes, [523.25]);
});

test('failed replay result is visual with failure label and no completion chime', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.setSettings({mode: 'all'}); await env.engine.enableSound(gesture);
  await render(env.engine, model({simulation_results: [{simulation_id: 'replay-failed', kind: 'historical_replay', status: 'failure'}]}));
  assert.equal(env.engine.getState().events[0].severity, 'warning');
  assert.match(env.engine.getState().events[0].summary, /failure reported/);
  assert.equal(env.context.notes.length, 0);
});

test('acknowledge, snooze, mute and settings are browser-local and persist safely', async () => {
  const env = setup();
  await render(env.engine, model());
  await render(env.engine, model({qualifying_signals: [signal('event')]}));
  const id = env.engine.getState().events[0].id;
  await env.engine.snooze(id, 60); assert.equal(env.engine.getState().unread, 0);
  env.advance(61 * 60000); assert.equal(env.engine.getState().unread, 1);
  await env.engine.mute('signals'); assert.equal(env.engine.getState().unread, 0);
  await env.engine.mute('signals', false); assert.equal(env.engine.getState().unread, 1);
  await env.engine.acknowledge(id); assert.equal(env.engine.getState().unread, 0);
  await env.engine.setSettings({volume: 99, quietHours: {start: 'wrong', end: '25:00'}});
  assert.equal(env.engine.getState().settings.volume, 1);
  assert.equal(env.engine.getState().settings.quietHours.start, '22:00');
  assert.match(env.engine.getState().explanation, /do not change Gmail, Pushover or Healthchecks/);
  const reload = setup({storage: env.storage}); assert.equal(reload.engine.getState().events[0].acknowledged, true);
});

test('old snapshots cannot regress a later committed baseline', async () => {
  const env = setup();
  const newer = model({qualifying_signals: [signal('retained')]}); newer.generated_at = '2026-08-30T13:00:00Z';
  await render(env.engine, newer);
  const saved = env.storage.getItem(STORAGE_KEY);
  const pending = await render(env.engine, model());
  assert.equal(pending.olderSnapshot, true);
  assert.equal(env.storage.getItem(STORAGE_KEY), saved);
});

test('production generated_utc timestamp rejects older publication snapshots', async () => {
  const env = setup();
  const current = model(); delete current.generated_at; current.generated_utc = '2026-08-30T13:00:00Z';
  await render(env.engine, current);
  const old = model({qualifying_signals: [signal('older-publication')]}); delete old.generated_at; old.generated_utc = '2026-08-30T11:00:00Z';
  const pending = await render(env.engine, old);
  assert.equal(pending.olderSnapshot, true);
  assert.equal(env.engine.getState().events.length, 0);
});

test('hidden dashboard and browser storage errors remain silent without throwing', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.enableSound(gesture);
  env.host.document.visibilityState = 'hidden';
  await render(env.engine, model({qualifying_signals: [signal('hidden')]}));
  assert.equal(env.context.notes.length, 0);
  env.host.document.visibilityState = 'visible';
  env.storage.setItem = () => { throw new Error('Quota exceeded'); };
  await render(env.engine, model({qualifying_signals: [signal('hidden'), signal('storage')] }));
  assert.equal(env.engine.getState().storageAvailable, false);
  assert.equal(env.context.notes.length, 0);
});

test('unsupported or blocked audio is handled; explicit test never creates external work', async () => {
  const unsupported = setup({audioFactory: () => null});
  assert.equal(await unsupported.engine.enableSound(gesture), false);
  const blocked = setup({audioFactory: () => ({state: 'suspended', resume: () => Promise.reject(new Error('blocked'))})});
  assert.equal(await blocked.engine.enableSound(gesture), false);
  const working = setup();
  assert.equal(await working.engine.testSound({isTrusted: false, type: 'click'}), false);
  assert.equal(await working.engine.testSound(gesture), true);
  assert.equal(working.context.notes.length, 2);
  assert.equal(working.engine.getState().events.length, 0);
  assert.equal(working.engine.getState().settings.mode, 'off', 'Test sound must not enable automatic audio');
  assert.equal(working.engine.getState().sound.armed, false);
});

test('pre-armed first hydration and mixed-category burst produce no initial flood and at most one sound', async () => {
  const env = setup();
  await env.engine.enableSound(gesture); await env.engine.setSettings({mode: 'all'});
  await render(env.engine, model({qualifying_signals: [signal('retained')]}));
  assert.equal(env.context.notes.length, 0);
  await render(env.engine, model({qualifying_signals: [signal('retained'), signal('new')],
    current_incidents: [{id: 'executive:new', branch: 'executive', kind: 'failure', since: '2026-08-30T12:00:00Z'}],
    simulation_results: [{simulation_id: 'new-replay', kind: 'historical_replay', status: 'success'}]}));
  assert.equal(env.engine.getState().events.length, 3);
  assert.equal(env.context.notes.length, 2);
  assert.equal(JSON.parse(env.storage.getItem(STORAGE_KEY)).playedIds.length, 3);
});

test('bounded bloom memory prevents replay after exact event-ID list eviction', async () => {
  const env = setup();
  await render(env.engine, model()); await env.engine.enableSound(gesture);
  await render(env.engine, model({qualifying_signals: [signal('once')]}));
  const stored = JSON.parse(env.storage.getItem(STORAGE_KEY));
  stored.seenIds = []; stored.playedIds = []; stored.events = []; stored.baseline.signals = [];
  env.storage.setItem(STORAGE_KEY, JSON.stringify(stored));
  await render(env.engine, model({qualifying_signals: [signal('once')]}));
  assert.equal(env.context.notes.length, 2);
  assert.equal(env.engine.getState().events.length, 0);
});

test('zero volume stays silent and no synthetic gesture can initialize audio', async () => {
  const env = setup();
  assert.equal(await env.engine.enableSound({isTrusted: false, type: 'click'}), false);
  assert.equal(await env.engine.enableSound({isTrusted: true, type: 'load'}), false);
  assert.equal(env.created, 0);
  await env.engine.setSettings({volume: 0});
  assert.equal(await env.engine.testSound(gesture), false);
  assert.equal(env.context.notes.length, 0);
});

test('browser-local history and IDs stay bounded; overflow never creates retained-record flood', async () => {
  const env = setup();
  const oversized = model({filing_ids: Array.from({length: LIMITS.baseline + 20}, (_, i) => 'record-' + i)});
  await render(env.engine, oversized); await render(env.engine, oversized);
  assert.equal(env.engine.getState().unread, 0);
  assert.deepEqual(env.engine.getState().limitedCategories, ['filings']);
  const state = JSON.parse(env.storage.getItem(STORAGE_KEY));
  assert.equal(state.baseline.filings.length, LIMITS.baseline);
  state.events = Array.from({length: LIMITS.history + 20}, (_, i) => ({id: 'record-' + i, category: 'records'}));
  state.seenIds = Array.from({length: LIMITS.ids + 20}, (_, i) => 'id-' + i);
  env.storage.setItem(STORAGE_KEY, JSON.stringify(state));
  const reload = setup({storage: env.storage});
  assert.equal(reload.engine.getState().events.length, LIMITS.history);
  await render(reload.engine, oversized);
  assert.equal(JSON.parse(env.storage.getItem(STORAGE_KEY)).seenIds.length, LIMITS.ids);
});

test('hostile text stays data and unsafe supporting URLs are rejected', async () => {
  assert.equal(safeLink('javascript:alert(1)', '#signals'), '#signals');
  assert.equal(safeLink('data:text/html,evil', '#signals'), '#signals');
  assert.equal(safeLink('//evil.test/path', '#signals'), '#signals');
  assert.equal(safeLink('https://example.test/filing'), 'https://example.test/filing');
  const env = setup(); await render(env.engine, model());
  await render(env.engine, model({qualifying_signals: [{...signal('hostile'), ticker: '<img src=x onerror=alert(1)>', link: 'javascript:alert(1)'}]}));
  assert.match(env.engine.getState().events[0].summary, /<img/);
  assert.equal(env.engine.getState().events[0].link, '#signals');
  assert.equal(globalThis.alert, undefined);
});
