'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {PolitiTrackNotifications, STORAGE_KEY} = require('../scripts/dashboard_assets/notifications.js');
const base = Date.parse('2026-09-15T12:00:00Z');
const time = minutes => new Date(base + minutes * 60000).toISOString();
const failure = (minute, branch = 'executive', kind = 'failure') => ({id: branch + ':' + minute, branch, kind, since: time(minute)});
const success = (minute, branch = 'executive', extra = {}) => ({id: branch + ':success:' + minute, branch, at: time(minute), status: 'success', conclusion: 'success', error_count: 0, ...extra});
function fixture() {
  let now = base;
  const values = new Map();
  const storage = {getItem: key => values.get(key), setItem: (key, value) => values.set(key, value)};
  let tail = Promise.resolve();
  const locks = {request: (_key, _options, work) => { const next = tail.then(work); tail = next.catch(() => {}); return next; }};
  const create = () => new PolitiTrackNotifications({storage, locks, now: () => now, host: {}});
  const engine = create();
  const model = (minute, incidents = [], runs = []) => ({generated_utc: time(minute), notifications: {
    filing_ids: [], trade_ids: [], qualifying_signals: [], simulation_results: [], runs, current_incidents: incidents}});
  const commit = async (minute, incidents = [], runs = [], target = engine) => {
    now = base + minute * 60000;
    await target.prepare(model(minute, incidents, runs)).commit();
    return target.getState().events;
  };
  return {engine, create, commit, model, storage, wall: minute => { now = base + minute * 60000; }};
}

test('59-minute interruption and its recovery generate no Inbox notifications', async () => {
  const f = fixture();
  await f.commit(0);
  await f.commit(1, [failure(1)]);
  assert.deepEqual(await f.commit(60, [failure(31)]), []);
  assert.deepEqual(await f.commit(61, [], [success(60.5)]), []);
  assert.equal(f.engine.getState().currentIncidents.length, 0);
});

test('one alert at 60 minutes across changing run IDs and kinds, then one verified recovery', async () => {
  const f = fixture();
  await f.commit(0);
  await f.commit(1, [failure(1)]);
  await f.commit(31, [failure(31)]);
  let events = await f.commit(61, [failure(61, 'executive', 'stale')]);
  assert.equal(events.length, 1);
  assert.match(events[0].summary, /at least 60 minutes/);
  assert.equal(events[0].pattern, 'failure');
  assert.equal((await f.commit(91, [failure(91)])).length, 1);
  events = await f.commit(96, [], [success(95)]);
  assert.equal(events.length, 2);
  assert.equal(events[0].severity, 'success');
  assert.equal(events[0].pattern, null);
  assert.equal((await f.commit(101, [], [success(100)])).length, 2);
});

test('reload and concurrent tabs preserve the timer and deliver one alert', async () => {
  const f = fixture();
  await f.commit(0, [failure(0)]);
  const other = f.create();
  await f.commit(59, [failure(30)], [], other);
  assert.equal(other.getState().events.length, 0);
  f.wall(60);
  const payload = f.model(60, [failure(60)]);
  await Promise.all([f.engine.prepare(payload).commit(), other.prepare(payload).commit()]);
  assert.equal(f.create().getState().events.length, 1);
});

test('refreshing old data, clock jumps, and older publications cannot earn outage time', async () => {
  const f = fixture();
  await f.commit(0, [failure(0)]);
  f.wall(180);
  await f.engine.prepare(f.model(0, [failure(0)])).commit();
  await f.engine.prepare(f.model(-10, [failure(-10)])).commit();
  assert.equal(f.engine.getState().events.length, 0);
  assert.equal((await f.commit(59, [failure(30)])).length, 0);
  assert.equal((await f.commit(60, [failure(60)])).length, 1);
});

test('a success between failed observations resets the continuous interruption timer', async () => {
  const f = fixture();
  await f.commit(0, [failure(0)]);
  await f.commit(50, [failure(50)], [success(30)]);
  assert.equal((await f.commit(60, [failure(60)], [success(30)])).length, 0);
  assert.equal((await f.commit(109, [failure(100)])).length, 0);
  assert.equal((await f.commit(110, [failure(110)])).length, 1);
});

test('unknown evidence and another branch cannot announce a recovery', async () => {
  const f = fixture();
  await f.commit(0, [failure(0)]);
  await f.commit(60, [failure(60)]);
  assert.equal((await f.commit(65, [], [success(64, 'legislative')])).length, 1);
  assert.equal((await f.commit(70, [], [success(69, 'executive', {error_count: 1})])).length, 1);
  assert.equal((await f.commit(75, [], [success(74, 'executive', {conclusion: 'failure'})])).length, 1);
  assert.equal((await f.commit(80, [], [success(79)])).length, 2);
});

test('quiet recovery resets an episode and leaves existing signal history and preferences intact', async () => {
  const f = fixture();
  await f.engine.setSettings({mode: 'off', volume: .6});
  await f.commit(0);
  const signalModel = f.model(1, [failure(1)]);
  signalModel.notifications.qualifying_signals = [{analysis_id: 'new', classification: 'high_priority'}];
  await f.engine.prepare(signalModel).commit();
  await f.commit(30, [], [success(29)]);
  await f.commit(45, [failure(45)]);
  assert.equal((await f.commit(104, [failure(100)])).length, 1);
  assert.equal((await f.commit(105, [failure(105)])).length, 2);
  assert.equal(f.engine.getState().settings.mode, 'off');
  assert.equal(f.engine.getState().settings.volume, .6);
  assert.equal(f.engine.getState().events.filter(e => e.category === 'signals').length, 1);
});

test('upgrade starts pending legacy incidents quietly and retains prior notification history', async () => {
  const f = fixture();
  await f.commit(0, [failure(0)]);
  const legacy = JSON.parse(f.storage.getItem(STORAGE_KEY));
  delete legacy.baseline.incidents[0].observedSince;
  delete legacy.baseline.incidents[0].notified;
  f.storage.setItem(STORAGE_KEY, JSON.stringify(legacy));
  const upgraded = f.create();
  assert.equal((await f.commit(120, [failure(120)], [], upgraded)).length, 0);
  assert.equal((await f.commit(180, [failure(180)], [], upgraded)).length, 1);
});
