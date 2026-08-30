'use strict';

// Execute the actual integration scripts against a small DOM contract and a
// notification API double. Browser layout remains a separate acceptance gate.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function page(file, options = {}) {
  const nodes = new Map(), listeners = new Map(), calls = [];
  function element(id = '') {
    return {id, dataset: {}, value: '', checked: false, disabled: false, hidden: false, innerHTML: '', textContent: '', attributes: {},
      addEventListener(type, handler) { this[type] = handler; }, querySelectorAll() { return []; }, querySelector() { return null; },
      setAttribute(key, value) { this.attributes[key] = value; }, removeAttribute(key) { delete this.attributes[key]; },
      closest() { return null; }, focus() {}, close() { this.closed = true; }, getBoundingClientRect() { return {left: 0, top: 0, right: 20, bottom: 20, width: 20, height: 20}; }};
  }
  const document = {activeElement: element('body'), visibilityState: 'visible', documentElement: element('html'),
    getElementById(id) { if (!nodes.has(id)) nodes.set(id, element(id)); return nodes.get(id); },
    querySelectorAll() { return []; },
    addEventListener(name, handler) { const list = listeners.get(name) || []; list.push(handler); listeners.set(name, list); }};
  const saved = {events: options.events || [], unread: (options.events || []).length, actionable: 0,
    settings: {mode: options.mode || 'off', volume: .2, quietHours: {enabled: false, start: '22:00', end: '07:00'}, mutedCategories: {}},
    sound: {armed: Boolean(options.armed), status: 'Off'}, storageAvailable: true, limitedCategories: [], currentIncidents: []};
  class Notifications {
    constructor(config) { this.config = config; }
    getState() { return saved; }
    setSettings(value) {
      calls.push(['settings', value]);
      if (options.rejectSettings) return Promise.reject(new Error('Browser lock unavailable'));
      return Promise.resolve().then(() => { Object.assign(saved.settings, value); if (value.mode === 'off') saved.sound.armed = false; });
    }
    acknowledge(id) { calls.push(['acknowledge', id]); return options.rejectAcknowledge ? Promise.reject(new Error('Storage unavailable')) : Promise.resolve(); }
    snooze(id, minutes) { calls.push(['snooze', id, minutes]); return Promise.resolve(); }
    mute(category, muted) { calls.push(['mute', category, muted]); return Promise.resolve(); }
    enableSound(event) { calls.push(['enable', event]); return options.rejectEnable ? Promise.reject(new Error('Sound unavailable')) : Promise.resolve().then(() => { saved.sound.armed = true; if (saved.settings.mode === 'off') saved.settings.mode = 'high'; }); }
    testSound(event) { calls.push(['test', event]); return Promise.resolve(); }
  }
  const context = {document, location: {href: 'https://example.test/PolitiTrack/' + (file === 'wallboard.js' ? 'wallboard.html' : ''), hash: '', search: ''},
    navigator: {}, PolitiTrackNotifications: Notifications, Date, URL, URLSearchParams, console, Promise,
    innerWidth: 1440, innerHeight: 900, setInterval: () => 1, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), addEventListener() {}};
  context.window = context;
  vm.createContext(context);
  const folder = path.resolve(__dirname, '../scripts/dashboard_assets');
  vm.runInContext(fs.readFileSync(path.join(folder, 'common.js'), 'utf8'), context, {filename: 'common.js'});
  vm.runInContext(fs.readFileSync(path.join(folder, file), 'utf8'), context, {filename: file});
  return {nodes, calls, saved, listeners, context};
}

test('stored notifications render without requiring a successful first network load', () => {
  const env = page('app.js', {events: [{id: 'event-1', category: 'signals', severity: 'info', icon: '◆', timestamp: '2026-08-30T12:00:00Z', summary: 'Watchlist update', link: '#signals'}]});
  assert.equal(env.nodes.get('notification-count').textContent, '1');
  assert.match(env.nodes.get('notification-list').innerHTML, /Watchlist update/);
});

test('notification rendering escapes hostile text and keeps local evidence in the same page', () => {
  const env = page('app.js', {events: [{id: '" autofocus onfocus="bad', category: 'signals', severity: 'high', icon: '<bad>', timestamp: '2026-08-30T12:00:00Z', summary: '<img src=x onerror=alert(1)>', link: '#signals', snoozedUntil: '2000-01-01T00:00:00Z'}]});
  const html = env.nodes.get('notification-list').innerHTML;
  assert.ok(!html.includes('<img'));
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /data-ack="&quot; autofocus onfocus=&quot;bad"/);
  assert.match(html, /href="#signals" data-notification-link/);
  assert.ok(!html.includes('target="_blank"'));
  assert.match(html, /<small>Unread<\/small>/, 'Expired snooze is not displayed as still snoozed');
  assert.match(env.nodes.get('mute-categories').innerHTML, /<legend>/, 'Dynamic rendering keeps the fieldset accessible name');
});

test('acknowledge all is one atomic mutation and rejected UI mutations are handled', async () => {
  const env = page('app.js', {events: [{id: 'one', category: 'records'}, {id: 'two', category: 'records'}], rejectAcknowledge: true});
  assert.equal(await env.nodes.get('acknowledge-all').onclick(), false);
  assert.equal(env.calls.length, 1);
  assert.equal(env.calls[0][0], 'acknowledge');
  assert.equal(env.calls[0][1], 'all');
  assert.equal(env.nodes.get('notification-storage-note').hidden, false);
  assert.match(env.nodes.get('notification-storage-note').textContent, /could not be saved/);
});

test('dashboard sound enables immediately within the originating user gesture and catches errors', async () => {
  const env = page('app.js', {rejectEnable: true});
  const event = {isTrusted: true, type: 'click'};
  const result = env.nodes.get('enable-sound').onclick(event);
  assert.equal(env.calls[0][0], 'enable');
  assert.equal(env.calls[0][1], event);
  assert.equal(await result, false);
});

test('wallboard arms sound without awaiting another setting operation first', async () => {
  const env = page('wallboard.js');
  const event = {isTrusted: true, type: 'click'};
  const result = env.nodes.get('wall-sound').onclick(event);
  assert.equal(env.calls.length, 1);
  assert.equal(env.calls[0][0], 'enable');
  assert.equal(env.calls[0][1], event);
  await result;
  assert.equal(env.nodes.get('wall-sound').textContent, 'Sound armed');
});

test('wallboard waits for Off to persist and catches failed sound settings', async () => {
  const env = page('wallboard.js', {mode: 'high', armed: true});
  await env.nodes.get('wall-sound').onclick({isTrusted: true, type: 'click'});
  assert.equal(env.calls[0][0], 'settings');
  assert.equal(env.calls[0][1].mode, 'off');
  assert.equal(env.nodes.get('wall-sound').textContent, 'Sound off');
  const failed = page('wallboard.js', {mode: 'high', armed: true, rejectSettings: true});
  await failed.nodes.get('wall-sound').onclick({isTrusted: true, type: 'click'});
  assert.equal(failed.nodes.get('wall-sound').textContent, 'Sound unavailable');
});
