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
