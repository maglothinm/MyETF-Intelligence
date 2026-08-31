'use strict';

// Native Node coverage runs in CI without optional JSDOM/axe packages. Load the
// actual presentation source; browser interaction remains in dashboard_dom tests.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sourcePath = path.resolve(__dirname, '../scripts/dashboard_assets/common.js');
const context = {window: {}, URL, location: {href: 'https://dashboard.test/PolitiTrack/'}};
vm.runInNewContext(fs.readFileSync(sourcePath, 'utf8'), context, {filename: sourcePath});
const PT = context.window.PT;
const run = (id, finished_utc, extra = {}) => ({id, finished_utc, status: 'success', error_count: 0,
  new_record_count: 1, run_url: 'https://example.test/TEST/runs/' + id, ...extra});
const chronological = ['06:00', '06:15', '06:30', '06:45'].map((time, index) => run('run-' + index, `2026-08-30T${time}:00Z`));
const latestFirst = ['run-3', 'run-2', 'run-1', 'run-0'];

function timelineLinks(runs, detailed) {
  const model = {health: {branches: [{branch: 'legislative', status: 'success', timeline: runs,
    last_run_utc: null, last_success_utc: null, new_record_count: 0, errors: [], run_url: null}]}};
  const html = PT.healthCards(model, detailed);
  // Read only the generated timeline fragment. No alternate sorting or rendering
  // algorithm is implemented in this harness.
  const timeline = html.match(/<div class="timeline"[^>]*>([\s\S]*?)<\/div>/)?.[1];
  assert.notEqual(timeline, undefined, 'Health card includes the existing history component');
  return {html: timeline, links: [...timeline.matchAll(/<a\b([^>]*)>/g)].map(match =>
    Object.fromEntries([...match[1].matchAll(/([\w-]+)="([^"]*)"/g)].map(attribute => [attribute[1], attribute[2]])))};
}

const cases = [
  ['ascending input', chronological, latestFirst],
  ['descending input', chronological.slice().reverse(), latestFirst],
  ['mixed input', [chronological[1], chronological[3], chronological[0], chronological[2]], latestFirst],
  ['equal instants with stable IDs', [run('tie-a', '2026-08-30T06:45:00Z'),
    run('tie-c', '2026-08-30T02:45:00-04:00'), run('tie-b', '2026-08-30T06:45:00.000Z')], ['tie-c', 'tie-b', 'tie-a']],
  ['offset-aware datetime values and finish precedence', [
    run('old', '2026-08-30T08:15:00+02:00', {started_utc: '2026-08-30T06:10:00Z'}),
    run('new', '2026-08-30T02:45:00-04:00', {started_utc: '2026-08-30T05:00:00Z'}),
    run('middle', '2026-08-30T06:30:00Z', {started_utc: '2026-08-30T06:20:00Z'}),
  ], ['new', 'middle', 'old']],
  ['valid start fallback and unknown times last', [run('unknown', 'invalid'),
    run('finished', '2026-08-30T06:45:00Z'), run('fallback', 'invalid', {started_utc: '2026-08-30T07:00:00Z'}),
    run('start-only', null, {started_utc: '2026-08-30T06:50:00Z'})], ['fallback', 'start-only', 'finished', 'unknown']],
  ['workflow-only starts and queued creation observations', [run('finished', '2026-08-30T06:45:00Z'),
    run('queued', null, {status: 'unknown', workflow_created_utc: '2026-08-30T07:00:00Z'}),
    run('job-start', null, {status: 'unknown', producer_job_started_utc: '2026-08-30T06:55:00Z', workflow_started_utc: '2026-08-30T06:30:00Z'}),
    run('running', null, {status: 'unknown', workflow_started_utc: '2026-08-30T06:50:00Z'})], ['queued', 'job-start', 'running', 'finished']],
  ['stable URL fallback without IDs', ['url-a', 'url-c', 'url-b'].map(id =>
    run(id, '2026-08-30T06:45:00Z', {id: null})), ['url-c', 'url-b', 'url-a']],
  ['a single run', [chronological[3]], ['run-3']],
  ['no runs', [], []],
];

for (const [name, input, expected] of cases) {
  test(`health history renders newest first for ${name} without mutating records`, () => {
    const before = JSON.stringify(input);
    input.forEach(Object.freeze); Object.freeze(input);
    for (const detailed of [true, false]) {
      for (const rows of [input, Object.freeze(input.slice().reverse())]) {
        const {html, links} = timelineLinks(rows, detailed);
        assert.deepEqual(links.map(link => new URL(link.href).pathname.split('/').at(-1)), expected);
        if (!input.length) assert.match(html, /No retained evidence/);
        for (const link of links) {
          const record = input.find(row => row.run_url === link.href);
          assert.ok(record, 'Every rendered action still refers to an original record');
          assert.equal(link.class, record.status);
          assert.equal(link.target, '_blank');
          assert.equal(link.tabindex, undefined, 'Sequential accessibility order follows the generated order');
        }
      }
    }
    assert.equal(JSON.stringify(input), before);
  });
}

test('history labels keep each sorted record status, counts and authoritative timestamp', () => {
  const rows = [run('old-success', '2026-08-30T06:00:00Z', {new_record_count: 12}),
    run('latest-failure', null, {started_utc: '2026-08-30T06:45:00Z', status: 'failure', error_count: 3})];
  const {links} = timelineLinks(rows, true);
  const newest = links[0], timestamp = PT.date(rows[1].started_utc);
  assert.equal(newest.href, rows[1].run_url);
  assert.equal(newest.class, 'failure');
  assert.equal(newest['aria-label'], PT.esc(`${PT.statusText('failure')} ${timestamp}; 3 errors; 1 new records`));
  assert.equal(newest.title, PT.esc(`${PT.statusText('failure')} · ${timestamp}`));
  assert.equal(links[1]['aria-label'], PT.esc(`${PT.statusText('success')} ${PT.date(rows[0].finished_utc)}; 0 errors; 12 new records`));
});

test('workflow-only observations label their actual timestamp kind without inventing collector completion', () => {
  const rows = [run('created', null, {status: 'unknown', workflow_created_utc: '2026-08-30T07:00:00Z'}),
    run('job-start', null, {status: 'unknown', producer_job_started_utc: '2026-08-30T06:55:00Z'}),
    run('started', null, {status: 'unknown', workflow_started_utc: '2026-08-30T06:50:00Z'}),
    run('job', '2026-08-30T06:45:00Z', {status: 'failure', evidence_source: 'github_actions'})];
  const {links} = timelineLinks(rows, true);
  assert.match(links[0]['aria-label'], /Workflow created/);
  assert.match(links[1]['aria-label'], /Producer job started/);
  assert.match(links[2]['aria-label'], /Workflow started/);
  assert.match(links[3]['aria-label'], /Workflow job finished/);
  assert.equal(rows[0].finished_utc, null);
  assert.equal(rows[1].finished_utc, null);
});

const asOf = Date.parse('2026-08-31T12:00:00Z');
const before = minutes => new Date(asOf - minutes * 60000).toISOString();
function freshnessModel(ages = {}) {
  return {generated_utc: before(0), data_through_utc: before(10), health: {as_of_utc: before(0),
    required_branches: ['legislative', 'executive', 'ai'],
    policy: {legislative: {expected_interval_minutes: 15, stale_after_minutes: 30},
      executive: {expected_interval_minutes: 30, stale_after_minutes: 60},
      ai: {expected_interval_minutes: 15, stale_after_minutes: 75}},
    branches: ['legislative', 'executive', 'ai'].map(branch => ({branch, status: 'success',
      last_attempt_utc: before((ages[branch] ?? 10) + 1), last_success_utc: before(ages[branch] ?? 10),
      latest_run_success: true, latest_conclusion: 'success', errors: [], error_count: 0,
      trigger_source: 'schedule', new_record_count: 0, timeline: []}))}};
}

for (const [branch, minutes, expected] of [
  ['legislative', 10, 'success'], ['legislative', 29, 'success'], ['legislative', 30, 'success'],
  ['legislative', 30.01, 'stale'], ['legislative', 70, 'stale'],
  ['executive', 45, 'success'], ['executive', 60, 'success'], ['executive', 60.01, 'stale'],
  ['ai', 75, 'success'], ['ai', 75.01, 'stale'],
]) test(`${branch} successful execution ${minutes}m old is ${expected} at a fixed instant`, () => {
  const model = PT.healthAt(freshnessModel({[branch]: minutes}), asOf);
  assert.equal(model.health.branches.find(row => row.branch === branch).status, expected);
  assert.equal(model.health.status, expected);
});

test('freshness calculations preserve attempt time, distinguish failed attempts and retain a recent prior success', () => {
  const model = freshnessModel();
  Object.assign(model.health.branches[0], {last_attempt_utc: before(5), latest_run_success: false, latest_conclusion: 'failure', error_count: 1, errors: ['Collector failed']});
  const health = PT.healthAt(model, asOf).health;
  assert.equal(health.status, 'failure');
  assert.equal(health.branches[0].status, 'failure');
  assert.equal(health.branches[0].fresh, true, 'Recency of prior success does not mask latest failure');
  assert.equal(health.branches[0].last_attempt_utc, before(5));
  assert.equal(health.branches[0].last_success_utc, before(10));
  assert.equal(health.branches[0].next_expected_utc, new Date(asOf + 5 * 60000).toISOString());
  assert.equal(health.branches[0].age_minutes, 10);
  assert.equal(health.branches[0].overdue_minutes, 0);
});

test('an aging page cannot remain green when publishers and collectors stop', () => {
  const input = freshnessModel({legislative: 29});
  const original = JSON.stringify(input);
  input.health.branches.forEach(Object.freeze); Object.freeze(input.health.branches); Object.freeze(input);
  assert.equal(PT.healthAt(input, asOf).health.status, 'success');
  const aged = PT.healthAt(input, asOf + 41 * 60000);
  assert.equal(aged.health.status, 'stale');
  assert.equal(aged.health.branches[0].age_minutes, 70);
  assert.equal(aged.health.branches[0].overdue_minutes, 55);
  assert.equal(aged.health.branches[0].estimated_missed_intervals, 3);
  assert.equal(aged.health.branches[0].next_expected_utc, new Date(Date.parse(before(29)) + 15 * 60000).toISOString());
  assert.equal(JSON.stringify(input), original, 'Aging is a view, not a production-state mutation');
});

test('a device clock behind the publisher cannot turn already stale production evidence green', () => {
  const input = freshnessModel({legislative: 70});
  input.health.status = input.health.branches[0].status = 'stale';
  const result = PT.healthAt(input, asOf - 60 * 60000);
  assert.equal(result.health.status, 'stale');
  assert.equal(result.health.branches[0].age_minutes, 70);
  assert.equal(result.health.as_of_utc, before(0));
  assert.equal(PT.healthAt(input, NaN).health.status, 'stale', 'An invalid clock cannot erase server-proven stale evidence');
  assert.equal(PT.healthAt(freshnessModel(), NaN).health.status, 'unknown', 'An invalid clock never proves current');
});

function displayClock(wall = asOf, elapsed = 0) {
  return {view: PT.createHealthClock({wallNow: () => wall, monotonicNow: () => elapsed}),
    advance(minutes, moveWall = true) { elapsed += minutes * 60000;if(moveWall)wall += minutes * 60000; },
    setWall(value) { wall=value; }, setElapsed(value) { elapsed=value; }};
}

test('a slow or frozen device clock cannot freeze fresh evidence at the publication time', () => {
  const model=freshnessModel(),clock=displayClock(asOf-120*60000);
  const first=clock.view(model);
  assert.equal(first.health.status,'unknown');
  assert.equal(first.health.clock_unreliable,true);
  assert.equal(first.health.branches[0].age_minutes,10);
  clock.advance(40,false);
  const aged=clock.view(model);
  assert.equal(aged.health.status,'stale');
  assert.equal(aged.health.branches[0].age_minutes,50);
  assert.equal(aged.health.branches[0].overdue_minutes,35);
});

test('same-publication refresh and clock catch-up cannot restart age or clear clock uncertainty', () => {
  const model=freshnessModel(),before=JSON.stringify(model),clock=displayClock(asOf-120*60000);
  assert.equal(clock.view(model).health.status,'unknown');
  clock.advance(10,false);
  const refetched=JSON.parse(before);
  refetched.generated_utc=new Date(asOf+10*60000).toISOString();
  assert.equal(clock.view(refetched).health.branches[0].age_minutes,20,'Unchanged server assessment is the same publication');
  clock.setWall(asOf);
  assert.equal(clock.view(model).health.status,'unknown','Catching up to the old publisher time is not new evidence');
  clock.advance(30,false);
  assert.equal(clock.view(JSON.parse(before)).health.status,'stale');
  assert.equal(clock.view(model).health.branches[0].age_minutes,50);
  assert.equal(JSON.stringify(model),before,'The elapsed anchor is browser-only metadata');
});

test('normal clocks age current evidence and a genuinely newer publication can establish fresh monitoring', () => {
  const clock=displayClock(),model=freshnessModel();
  assert.equal(clock.view(model).health.status,'success');
  clock.advance(40);
  assert.equal(clock.view(model).health.status,'stale');
  const next=freshnessModel();
  next.health.as_of_utc=next.generated_utc=new Date(asOf+40*60000).toISOString();
  next.health.branches.forEach(row=>{row.last_success_utc=new Date(asOf+30*60000).toISOString();});
  assert.equal(clock.view(next).health.status,'success');
  assert.equal(clock.view(next).health.branches[0].age_minutes,10);
});

for(const intermediateTick of [false,true]) test(`a delayed newer publication cannot regress accrued elapsed time (${intermediateTick?'with':'without'} an intervening clock tick)`, () => {
  const clock=displayClock(),model=freshnessModel();
  assert.equal(clock.view(model).health.status,'success');
  clock.advance(70,false);
  if(intermediateTick)assert.equal(clock.view(model).health.status,'stale');
  const delayed=freshnessModel();
  delayed.generated_utc=delayed.health.as_of_utc=new Date(asOf+10*60000).toISOString();
  delayed.health.branches.forEach(row=>{row.last_success_utc=new Date(asOf+5*60000).toISOString();});
  clock.setWall(asOf+10*60000);
  const assessment=clock.view(delayed);
  assert.equal(assessment.health.status,'stale');
  assert.equal(assessment.health.branches[0].age_minutes,65);
  assert.equal(assessment.health.as_of_utc,new Date(asOf+70*60000).toISOString());
});

test('failed and already stale evidence outrank unreliable or unavailable device clocks', () => {
  for(const clock of [displayClock(asOf-120*60000),displayClock(NaN),displayClock(asOf,NaN)]) {
    const model=freshnessModel({legislative:70});
    assert.equal(clock.view(model).health.status,'stale');
    Object.assign(model.health.branches[1],{status:'failure',latest_run_success:false,error_count:1});
    assert.equal(clock.view(model).health.status,'failure');
  }
  assert.equal(displayClock(asOf,NaN).view(freshnessModel()).health.status,'unknown');
});

test('elapsed-clock rollback does not regress the assessment or restore green', () => {
  const clock=displayClock(),model=freshnessModel();
  clock.view(model);clock.advance(10);
  const known=clock.view(model);
  clock.setElapsed(0);
  const uncertain=clock.view(model);
  assert.equal(uncertain.health.status,'unknown');
  assert.equal(uncertain.health.as_of_utc,known.health.as_of_utc);
  clock.advance(40);
  assert.equal(clock.view(model).health.status,'stale');
});

test('overall precedence is failure then stale then unknown then success', () => {
  const model = freshnessModel({executive: 70});
  assert.equal(PT.healthAt(model, asOf).health.status, 'stale');
  Object.assign(model.health.branches[2], {latest_run_success: null, last_success_utc: null});
  assert.equal(PT.healthAt(model, asOf).health.status, 'stale');
  model.health.branches[0].latest_run_success = false;
  assert.equal(PT.healthAt(model, asOf).health.status, 'failure');
  const fresh = freshnessModel();
  assert.equal(PT.healthAt(fresh, asOf).health.status, 'success');
  fresh.health.branches[2].evidence_incomplete = true;
  assert.equal(PT.healthAt(fresh, asOf).health.status, 'unknown');
  fresh.health.branches = [];
  assert.equal(PT.healthAt(fresh, asOf).health.status, 'unknown');
});

test('missing policy, missing or future success time, and unknown latest conclusion cannot claim current', () => {
  for (const change of [m => { m.health.policy = {}; },
    m => { m.health.branches[0].last_success_utc = null; },
    m => { m.health.branches[0].last_success_utc = before(-1); },
    m => { m.health.branches[0].latest_run_success = null; }]) {
    const model = freshnessModel(); change(model);
    assert.equal(PT.healthAt(model, asOf).health.status, 'unknown');
  }
});

test('new publications and synthetic simulation timeline records do not refresh admitted production evidence', () => {
  const model = freshnessModel({legislative: 70});
  model.generated_utc = before(0);
  model.health.branches[0].timeline = [run('simulation', before(0), {is_synthetic_test: true, trigger_source: 'manual_test'})];
  model.notifications = {runs: [{branch: 'publish', success: true, finished_utc: before(0)}]};
  const result = PT.healthAt(model, asOf);
  assert.equal(result.health.status, 'stale');
  assert.equal(result.health.branches[0].last_success_utc, before(70));
  assert.equal(result.data_through_utc, before(10));
});

test('public trigger display accepts coarse values only and never echoes authentication metadata', () => {
  assert.equal(PT.triggerLabel('external_scheduler'), 'External scheduler');
  assert.equal(PT.triggerLabel('workflow_dispatch'), 'Workflow dispatch', 'Dispatch alone does not prove a human or external scheduler initiated it');
  for (const value of ['token=private', 'https://private.test/key', '<script>bad</script>', 'constructor', '__proto__', ['external_scheduler'], null])
    assert.equal(PT.triggerLabel(value), 'Unavailable');
});
