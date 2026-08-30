/* Browser-local presentation only. This module never dispatches or sends alerts. */
(function (root, factory) {
  'use strict';
  const exported = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = exported;
  else root.PolitiTrackNotifications = exported.PolitiTrackNotifications;
}(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';

  const STORAGE_KEY = 'polititrack.notifications.v1';
  const LIMITS = Object.freeze({history: 150, ids: 2048, baseline: 12000, bloomBytes: 8192});
  const CATEGORIES = ['signals', 'operations', 'simulation', 'records'];
  const DEFAULT_SETTINGS = Object.freeze({mode: 'off', volume: 0.2,
    quietHours: {enabled: false, start: '22:00', end: '07:00'}, mutedCategories: {}});
  const EXPLANATION = 'History, acknowledgement, snooze, mute and sound settings belong to this browser on this device. They do not change Gmail, Pushover or Healthchecks. In-page sound works only while this dashboard is open and active; existing external alerts remain the background channels.';

  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function list(value) { return Array.isArray(value) ? value : []; }
  function string(value, limit = 256) { return typeof value === 'string' ? value.slice(0, limit) : ''; }
  function stamp(value) { return value && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString() : null; }
  function safeLink(value, fallback = '#overview') {
    const link = string(value, 2048).trim();
    if (!link || /[\u0000-\u0020\\]/.test(link) || link.startsWith('//')) return fallback;
    if (/^https?:\/\//i.test(link) || /^#[\w-]*$/.test(link) || /^(?:\.\/)?[\w./-]+(?:#[\w-]*)?$/.test(link)) return link;
    return fallback;
  }
  function hashes(value) {
    let a = 2166136261, b = 2246822507;
    for (let i = 0; i < value.length; i += 1) {
      a = Math.imul(a ^ value.charCodeAt(i), 16777619) >>> 0;
      b = Math.imul(b ^ value.charCodeAt(i), 3266489909) >>> 0;
    }
    return [a, b, (a + Math.imul(b, 3)) >>> 0, (b + Math.imul(a, 5)) >>> 0];
  }
  function digest(value) { return hashes(value).slice(0, 2).map(n => n.toString(16).padStart(8, '0')).join(''); }
  function eventId(category, ids) { return category + ':' + digest(ids.slice().sort().join('\u001f')); }
  function bloomRead(encoded) {
    const bytes = new Uint8Array(LIMITS.bloomBytes);
    if (typeof encoded === 'string' && encoded.length === LIMITS.bloomBytes * 2 && /^[\da-f]+$/.test(encoded)) {
      for (let i = 0; i < bytes.length; i += 1) bytes[i] = parseInt(encoded.slice(i * 2, i * 2 + 2), 16);
    }
    return bytes;
  }
  function bloomWrite(bytes) { return Array.from(bytes, n => n.toString(16).padStart(2, '0')).join(''); }
  function bloomHas(bytes, id) {
    return hashes(id).every(hash => { const bit = hash % (bytes.length * 8); return Boolean(bytes[bit >>> 3] & (1 << (bit & 7))); });
  }
  function bloomAdd(bytes, id) {
    hashes(id).forEach(hash => { const bit = hash % (bytes.length * 8); bytes[bit >>> 3] |= 1 << (bit & 7); });
  }
  function settings(value) {
    const source = value && typeof value === 'object' ? value : {};
    const quiet = source.quietHours || {};
    const validTime = value => typeof value === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
    return {mode: ['off', 'high', 'all'].includes(source.mode) ? source.mode : 'off',
      volume: typeof source.volume === 'number' && Number.isFinite(source.volume) ? Math.max(0, Math.min(1, source.volume)) : 0.2,
      quietHours: {enabled: quiet.enabled === true, start: validTime(quiet.start) ? quiet.start : '22:00', end: validTime(quiet.end) ? quiet.end : '07:00'},
      mutedCategories: Object.fromEntries(CATEGORIES.map(category => [category, source.mutedCategories && source.mutedCategories[category] === true]))};
  }
  function inQuietHours(value, date) {
    if (!value || !value.enabled) return false;
    const minute = time => Number(time.slice(0, 2)) * 60 + Number(time.slice(3));
    const start = minute(value.start), end = minute(value.end), now = date.getHours() * 60 + date.getMinutes();
    if (start === end) return true;
    return start < end ? now >= start && now < end : now >= start || now < end;
  }
  function freshState() {
    return {version: 1, baseline: null, events: [], seenIds: [], playedIds: [],
      seenBits: '', playedBits: '', settings: settings(DEFAULT_SETTINGS)};
  }
  function normalizeState(raw) {
    if (!raw || raw.version !== 1) return freshState();
    const state = freshState();
    state.settings = settings(raw.settings);
    state.baseline = raw.baseline && typeof raw.baseline === 'object' ? raw.baseline : null;
    if (state.baseline) {
      ['filings', 'transactions', 'signals', 'runs', 'simulations'].forEach(key => { state.baseline[key] = list(state.baseline[key]).filter(id => typeof id === 'string').slice(-LIMITS.baseline); });
      state.baseline.incidents = list(state.baseline.incidents).slice(-50);
      state.baseline.limited = list(state.baseline.limited).filter(key => ['filings', 'transactions', 'signals', 'runs', 'simulations'].includes(key));
    }
    state.events = list(raw.events).filter(event => event && typeof event.id === 'string' && CATEGORIES.includes(event.category))
      .slice(0, LIMITS.history).map(event => ({id: string(event.id), category: event.category,
        severity: ['high', 'warning', 'info', 'success'].includes(event.severity) ? event.severity : 'info',
        icon: string(event.icon, 4), timestamp: stamp(event.timestamp), summary: string(event.summary, 300),
        link: safeLink(event.link), simulation: event.simulation === true, acknowledged: event.acknowledged === true,
        snoozedUntil: stamp(event.snoozedUntil), count: Number.isFinite(event.count) ? Math.max(1, event.count) : 1,
        pattern: ['opportunity', 'confirmation', 'failure'].includes(event.pattern) ? event.pattern : null}));
    ['seenIds', 'playedIds'].forEach(key => { state[key] = list(raw[key]).filter(id => typeof id === 'string').slice(-LIMITS.ids); });
    state.seenBits = bloomWrite(bloomRead(raw.seenBits));
    state.playedBits = bloomWrite(bloomRead(raw.playedBits));
    return state;
  }
  function boundedIds(values, category, limited) {
    const ids = Array.from(new Set(values.filter(value => typeof value === 'string' && value).map(value => digest(value))));
    if (ids.length > LIMITS.baseline) limited.push(category);
    return ids.slice(-LIMITS.baseline);
  }
  function snapshot(model, now) {
    const data = model && model.notifications;
    if (!data || !['filing_ids', 'trade_ids', 'qualifying_signals', 'runs', 'simulation_results', 'current_incidents'].every(key => Array.isArray(data[key]))) {
      throw new Error('Incomplete dashboard notification evidence; the previous browser baseline is preserved.');
    }
    const limited = [];
    const signalRows = data.qualifying_signals.filter(row => row && typeof row.analysis_id === 'string' && ['high_priority', 'watchlist'].includes(row.classification));
    const simulationRows = data.simulation_results.filter(row => row && typeof row.simulation_id === 'string');
    const runs = data.runs.filter(row => row && typeof row.id === 'string' && typeof row.branch === 'string');
    const incidents = data.current_incidents.filter(row => row && typeof row.id === 'string' && typeof row.branch === 'string' && ['failure', 'stale'].includes(row.kind))
      .slice(-50).map(row => ({id: string(row.id), branch: string(row.branch, 40), kind: row.kind, since: stamp(row.since),
        url: safeLink(row.url, '#operations'), summary: string(row.summary, 240)}));
    return {filings: boundedIds(data.filing_ids, 'filings', limited), transactions: boundedIds(data.trade_ids, 'transactions', limited),
      signals: boundedIds(signalRows.map(row => row.analysis_id + ':' + row.classification), 'signals', limited),
      simulations: boundedIds(simulationRows.map(row => row.simulation_id), 'simulations', limited),
      runs: boundedIds(runs.map(row => row.id), 'runs', limited), incidents, limited,
      at: stamp(model.generated_utc || model.generated_at || model.as_of || model.generated_at_utc) || new Date(now).toISOString(),
      signalRows, simulationRows, runRows: runs};
  }
  function persistedSnapshot(snap) {
    const result = {...snap};
    delete result.signalRows; delete result.simulationRows; delete result.runRows;
    return result;
  }
  function evaluate(snap, state, now) {
    const baseline = state.baseline;
    const firstVisit = !baseline;
    const changes = {filings: 0, transactions: 0, signals: 0, simulations: 0};
    const events = [];
    if (firstVisit || (stamp(baseline.at) && Date.parse(snap.at) < Date.parse(baseline.at))) {
      return {firstVisit, changes, events, currentIncidents: snap.incidents, unresolvedIncidents: snap.incidents, olderSnapshot: !firstVisit};
    }
    const newIds = key => {
      if (snap.limited.includes(key) || list(baseline.limited).includes(key)) return [];
      const previous = new Set(baseline[key]);
      return snap[key].filter(id => !previous.has(id));
    };
    const seen = bloomRead(state.seenBits);
    const add = event => {
      if (!bloomHas(seen, event.id) && !state.seenIds.includes(event.id)) {
        events.push({...event, acknowledged: false, snoozedUntil: null});
      }
    };
    const observedAt = new Date(now).toISOString();
    const signalIds = newIds('signals');
    const signalSet = new Set(signalIds);
    const signals = snap.signalRows.filter(row => signalSet.has(digest(row.analysis_id + ':' + row.classification)));
    if (signals.length) {
      const high = signals.filter(row => row.classification === 'high_priority').length;
      changes.signals = signals.length;
      add({id: eventId('signals', signalIds), category: 'signals', severity: high ? 'high' : 'info', icon: '◆',
        timestamp: observedAt, summary: signals.length === 1 ? 'New ' + (high ? 'High Priority' : 'Watchlist') + ' signal' + (signals[0].ticker ? ': ' + string(signals[0].ticker, 32) : '') : signals.length + ' new qualifying signals (' + high + ' High Priority, ' + (signals.length - high) + ' Watchlist)',
        link: safeLink(signals[0].link, '#signals'), simulation: false, count: signals.length, pattern: 'opportunity'});
    }
    const filingIds = newIds('filings'), tradeIds = newIds('transactions');
    changes.filings = filingIds.length; changes.transactions = tradeIds.length;
    if (filingIds.length || tradeIds.length) add({id: eventId('records', filingIds.concat(tradeIds)), category: 'records', severity: 'info', icon: '●',
      timestamp: observedAt, summary: [filingIds.length ? filingIds.length + ' new filings' : '', tradeIds.length ? tradeIds.length + ' newly parsed transactions' : ''].filter(Boolean).join(' · '),
      link: '#records', simulation: false, count: filingIds.length + tradeIds.length, pattern: null});
    const oldIncidents = list(baseline.incidents);
    snap.incidents.filter(incident => !oldIncidents.some(old => old.id === incident.id)).forEach(incident => {
      add({id: eventId('incident', [incident.branch, incident.kind, incident.id]), category: 'operations', severity: 'warning', icon: '⚠',
        timestamp: incident.since || observedAt, summary: incident.branch + (incident.kind === 'stale' ? ' is stale according to retained evidence' : ' run requires attention'),
        link: incident.url, simulation: false, count: 1, pattern: 'failure'});
    });
    const unresolvedIncidents = snap.incidents.slice();
    oldIncidents.filter(incident => !snap.incidents.some(current => current.id === incident.id || current.branch === incident.branch)).forEach(incident => {
      const current = snap.runRows.filter(row => row.branch === incident.branch).sort((a, b) => (Date.parse(b.at) || 0) - (Date.parse(a.at) || 0))[0];
      const successful = current && (current.conclusion === 'success' || current.status === 'success') && current.error_count === 0;
      if (successful && stamp(current.at) && stamp(incident.since) && Date.parse(current.at) > Date.parse(incident.since)) {
        add({id: eventId('recovery', [incident.branch, incident.id, current.id]), category: 'operations', severity: 'success', icon: '✓',
          timestamp: stamp(current.at), summary: incident.branch + ' recovered from the previously observed ' + incident.kind + ' incident',
          link: safeLink(current.url, '#operations'), simulation: false, count: 1, pattern: null});
      } else unresolvedIncidents.push(incident);
    });
    const simulationIds = newIds('simulations'), simulationSet = new Set(simulationIds);
    const simulations = snap.simulationRows.filter(row => simulationSet.has(digest(row.simulation_id)) && row.kind === 'historical_replay');
    if (simulations.length) {
      changes.simulations = simulations.length;
      const completed = simulations.filter(row => ['success', 'completed'].includes(row.status));
      const failed = simulations.filter(row => ['failure', 'failed', 'error'].includes(row.status));
      add({id: eventId('simulation', simulations.map(row => row.simulation_id)), category: 'simulation', severity: failed.length ? 'warning' : completed.length ? 'success' : 'info', icon: failed.length ? '⚠' : '✓',
        timestamp: stamp(simulations[0].timestamp) || observedAt, summary: 'SIMULATED — ' + (simulations.length === 1 ? 'new $10K historical replay result' : simulations.length + ' new $10K historical replay results') + (failed.length ? ' · failure reported' : ''),
        link: safeLink(simulations[0].url, '#agent'), simulation: true, count: simulations.length, pattern: completed.length && !failed.length ? 'confirmation' : null});
    }
    return {firstVisit, changes, events, currentIncidents: snap.incidents, unresolvedIncidents: unresolvedIncidents.slice(-50), olderSnapshot: false};
  }

  class PolitiTrackNotifications {
    constructor(options = {}) {
      this._now = options.now || (() => Date.now());
      this._onChange = typeof options.onChange === 'function' ? options.onChange : () => {};
      this._host = options.host || root;
      this._locks = options.locks !== undefined ? options.locks : this._host.navigator && this._host.navigator.locks;
      this._storage = options.storage;
      this._storageAvailable = true;
      if (this._storage === undefined) {
        try { this._storage = this._host.localStorage; } catch (_) { this._storage = null; }
      }
      this._storageAvailable = Boolean(this._storage);
      this._audioFactory = options.audioFactory || (() => { const Audio = this._host.AudioContext || this._host.webkitAudioContext; return Audio ? new Audio() : null; });
      this._context = null; this._armed = false; this._audioStatus = 'Off'; this._queue = Promise.resolve();
      this._state = this._read() || freshState();
      if (this._state.settings.mode !== 'off') this._audioStatus = 'Use Enable sound after reopening this page';
      this._currentIncidents = this._state.baseline ? list(this._state.baseline.incidents) : [];
      this._storageListener = event => {
        if (event.key === STORAGE_KEY) { this._sync(); this._onChange(this.getState()); }
      };
      if (this._host.addEventListener) this._host.addEventListener('storage', this._storageListener);
    }
    _read() {
      if (!this._storage) return null;
      try { const raw = this._storage.getItem(STORAGE_KEY); return raw ? normalizeState(JSON.parse(raw)) : null; }
      catch (_) { this._storageAvailable = false; return null; }
    }
    _sync() {
      const stored = this._read();
      if (stored) this._state = stored;
      if (this._state.settings.mode === 'off') this._armed = false;
    }
    _write() {
      if (!this._storage || !this._storageAvailable) return false;
      try { this._storage.setItem(STORAGE_KEY, JSON.stringify(this._state)); return true; }
      catch (_) { this._storageAvailable = false; this._armed = false; this._audioStatus = 'Browser storage unavailable; automatic sound is disabled'; return false; }
    }
    _exclusive(work) {
      const run = () => this._locks && this._locks.request ? this._locks.request(STORAGE_KEY, {mode: 'exclusive'}, work) : work();
      const result = this._queue.then(run, run);
      this._queue = result.catch(() => {});
      return result;
    }
    prepare(model) {
      this._sync();
      const snap = snapshot(model, this._now());
      const pending = evaluate(snap, this._state, this._now());
      let committed = false;
      return {...copy(pending), commit: () => {
        if (committed) return Promise.resolve(this.getState());
        committed = true;
        return this._exclusive(async () => {
          this._sync();
          const result = evaluate(snap, this._state, this._now());
          if (result.olderSnapshot) return this.getState();
          const seen = bloomRead(this._state.seenBits);
          result.events.forEach(event => { bloomAdd(seen, event.id); this._state.seenIds.push(event.id); });
          this._state.seenBits = bloomWrite(seen);
          this._state.seenIds = this._state.seenIds.slice(-LIMITS.ids);
          this._state.events = result.events.slice().reverse().concat(this._state.events).slice(0, LIMITS.history);
          this._state.baseline = persistedSnapshot(snap);
          this._state.baseline.incidents = result.unresolvedIncidents;
          this._currentIncidents = snap.incidents;
          const written = this._write();
          // A cross-tab lock and a durable claim are mandatory for automatic audio.
          if (written && this._locks && this._locks.request && !result.firstVisit) await this._soundFor(result.events);
          this._onChange(this.getState());
          return this.getState();
        });
      }};
    }
    getState() {
      const now = this._now();
      const visible = this._state.events.filter(event => !event.acknowledged && !this._state.settings.mutedCategories[event.category] && !(event.snoozedUntil && Date.parse(event.snoozedUntil) > now));
      const mode = this._state.settings.mode;
      return copy({events: this._state.events, unread: visible.length, actionable: visible.filter(event => event.category === 'signals' || ['high', 'warning'].includes(event.severity)).length,
        settings: this._state.settings, sound: {armed: this._armed && mode !== 'off' && this._storageAvailable && Boolean(this._locks && this._locks.request), status: mode === 'off' ? 'Off' : this._audioStatus,
          coordinationAvailable: Boolean(this._locks && this._locks.request)},
        currentIncidents: this._currentIncidents, storageAvailable: this._storageAvailable,
        limitedCategories: this._state.baseline ? list(this._state.baseline.limited) : [], explanation: EXPLANATION});
    }
    _mutate(change) {
      return this._exclusive(() => { this._sync(); change(this._state); this._write(); this._onChange(this.getState()); return this.getState(); });
    }
    acknowledge(id) { return this._mutate(state => { state.events.forEach(event => { if (event.id === id || id === 'all') event.acknowledged = true; }); }); }
    snooze(id, minutes = 60) {
      const duration = Number.isFinite(minutes) ? Math.max(1, Math.min(10080, minutes)) : 60;
      return this._mutate(state => { const event = state.events.find(item => item.id === id); if (event) event.snoozedUntil = new Date(this._now() + duration * 60000).toISOString(); });
    }
    mute(category, muted = true) {
      return this._mutate(state => { if (CATEGORIES.includes(category)) state.settings.mutedCategories[category] = Boolean(muted); });
    }
    setSettings(update) {
      return this._mutate(state => {
        state.settings = settings({...state.settings, ...update, quietHours: {...state.settings.quietHours, ...(update && update.quietHours)}, mutedCategories: {...state.settings.mutedCategories, ...(update && update.mutedCategories)}});
        if (state.settings.mode === 'off') { this._armed = false; this._audioStatus = 'Off'; }
      });
    }
    _gesture(event) {
      return Boolean(event && event.isTrusted && /^(?:click|pointerup|touchend|keydown)$/.test(event.type)) || Boolean(this._host.navigator && this._host.navigator.userActivation && this._host.navigator.userActivation.isActive);
    }
    async _unlockAudio(event) {
      if (!this._gesture(event)) { this._audioStatus = 'Use Enable sound to arm audio'; return false; }
      try {
        if (!this._context) this._context = this._audioFactory();
        if (!this._context) { this._audioStatus = 'Audio is unavailable in this browser'; return false; }
        if (this._context.state === 'suspended') await this._context.resume();
        if (this._context.state !== 'running') { this._audioStatus = 'Audio was blocked; try Enable sound again'; return false; }
        return true;
      } catch (_) { this._armed = false; this._audioStatus = 'Audio was blocked or is unavailable'; this._onChange(this.getState()); return false; }
    }
    async enableSound(event) {
      if (!await this._unlockAudio(event)) { this._onChange(this.getState()); return false; }
      if (this._state.settings.mode === 'off') await this.setSettings({mode: 'high'});
      this._armed = true;
      this._audioStatus = this._locks && this._locks.request && this._storageAvailable
        ? 'Armed while open and active' : 'Automatic sound unavailable; browser coordination or storage is missing';
      this._onChange(this.getState());
      return true;
    }
    async testSound(event) {
      if (!await this._unlockAudio(event)) return false;
      // The explicit test is local only and does not create a notification event.
      // Testing must not enable automatic sound or change the selected mode.
      const previouslyArmed = this._armed;
      this._armed = true;
      const played = this._play('opportunity');
      this._armed = previouslyArmed;
      this._onChange(this.getState());
      return played;
    }
    async _soundFor(events) {
      const prefs = this._state.settings;
      const active = !this._host.document || (this._host.document.visibilityState === 'visible' && (!this._host.document.hasFocus || this._host.document.hasFocus()));
      if (!this._armed || prefs.mode === 'off' || !active || !this._context || this._context.state !== 'running' || inQuietHours(prefs.quietHours, new Date(this._now()))) return;
      const played = bloomRead(this._state.playedBits);
      const candidates = events.filter(event => event.pattern && !prefs.mutedCategories[event.category] && (prefs.mode === 'all' || event.severity === 'high' || (event.category === 'operations' && event.pattern === 'failure')) && !bloomHas(played, event.id) && !this._state.playedIds.includes(event.id));
      if (!candidates.length) return;
      // One restrained sound for a refresh burst. Claim every eligible event first
      // so no later tab, reconnect or history eviction can replay this burst.
      candidates.forEach(event => { bloomAdd(played, event.id); this._state.playedIds.push(event.id); });
      this._state.playedBits = bloomWrite(played);
      this._state.playedIds = this._state.playedIds.slice(-LIMITS.ids);
      if (!this._write()) return;
      const chosen = candidates.find(event => event.severity === 'high') || candidates.find(event => event.pattern === 'failure') || candidates[0];
      this._play(chosen.pattern);
    }
    _play(pattern) {
      if (!this._context || this._context.state !== 'running' || !this._armed || this._state.settings.volume <= 0) return false;
      try {
        const notes = pattern === 'confirmation' ? [523.25] : pattern === 'failure' ? [440, 329.63] : [523.25, 659.25];
        const start = this._context.currentTime;
        notes.forEach((frequency, index) => {
          const oscillator = this._context.createOscillator(), gain = this._context.createGain();
          const at = start + index * 0.14;
          oscillator.type = 'sine'; oscillator.frequency.setValueAtTime(frequency, at);
          gain.gain.setValueAtTime(0, at); gain.gain.linearRampToValueAtTime(this._state.settings.volume * 0.15, at + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.16);
          oscillator.connect(gain); gain.connect(this._context.destination);
          oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
          oscillator.start(at); oscillator.stop(at + 0.18);
        });
        return true;
      } catch (_) { this._armed = false; this._audioStatus = 'Audio is unavailable; visual notifications remain active'; return false; }
    }
    destroy() {
      if (this._host.removeEventListener) this._host.removeEventListener('storage', this._storageListener);
      if (this._context && this._context.close) Promise.resolve(this._context.close()).catch(() => {});
      this._armed = false;
    }
  }
  return {PolitiTrackNotifications, STORAGE_KEY, LIMITS, inQuietHours, safeLink};
}));
