import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import test from "node:test";
import {dispatchCollector, REPOSITORY_ID, TARGETS} from "../scheduler/dispatch.mjs";

const token = "TEST-ONLY-dispatch-secret";
const options = {branch: "legislative", repository: "maglothinm/MyETF-Intelligence", token, enabled: "true"};
const metadata = {id: REPOSITORY_ID, full_name: "maglothinm/PolitiTrack", default_branch: "main"};
const workflow = {name: TARGETS.legislative.name, path: ".github/workflows/legislative_trade_tracker_v2.yml", state: "active"};

function fakeFetch(responses) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({url, ...init});
    const response = responses.shift();
    assert.ok(response, "unexpected network request");
    if (response instanceof Error) throw response;
    if (response instanceof Response) return response;
    return new Response(JSON.stringify(response), {status: 200});
  };
  return {calls, fetchImpl};
}

test("checked-in Worker configuration cannot activate a timer or public trigger", () => {
  const config = readFileSync(new URL("../scheduler/cloudflare/wrangler.toml", import.meta.url), "utf8");
  assert.match(config, /SCHEDULER_ENABLED = "false"/);
  assert.match(config, /^crons = \[\]$/m);
  assert.match(config, /workers_dev = false/);
  assert.match(config, /preview_urls = false/);
  assert.doesNotMatch(config, /^GITHUB_DISPATCH_TOKEN\s*=/m);
});

test("disabled client does not retrieve metadata or dispatch", async () => {
  const result = await dispatchCollector({...options, enabled: "false"}, () => assert.fail("network request"));
  assert.equal(result.status, "disabled");
});

test("dispatch resolves canonical rename/default branch and uses only safe input", async () => {
  const {calls, fetchImpl} = fakeFetch([{...metadata, default_branch: "production"}, workflow, {workflow_runs: []}, new Response(null, {status: 204})]);
  const result = await dispatchCollector(options, fetchImpl);
  assert.equal(result.status, "dispatch_accepted");
  assert.equal(calls.length, 4);
  assert.match(calls[3].url, /^https:\/\/api\.github\.com\/repos\/maglothinm\/PolitiTrack\/actions\/workflows\/legislative_trade_tracker_v2\.yml\/dispatches$/);
  assert.equal(calls[3].method, "POST");
  assert.deepEqual(JSON.parse(calls[3].body), {ref: "production", inputs: {trigger_source: "external_scheduler"}});
  assert.equal(calls[3].headers.Authorization, `Bearer ${token}`);
  assert.equal(JSON.stringify(result).includes(token), false);
});

test("new GitHub dispatch response 200 is acceptance, not collector success", async () => {
  const {fetchImpl} = fakeFetch([metadata, workflow, {workflow_runs: []}, {workflow_run_id: 123, private_metadata: token}]);
  assert.deepEqual(await dispatchCollector(options, fetchImpl), {branch: "legislative", status: "dispatch_accepted"});
});

test("wrong numeric repository identity prevents workflow access and dispatch", async () => {
  const {calls, fetchImpl} = fakeFetch([{...metadata, id: 12}]);
  await assert.rejects(dispatchCollector(options, fetchImpl), /canonical_repository_mismatch/);
  assert.equal(calls.length, 1);
});

test("disabled or mismatched workflow is never enabled or dispatched", async () => {
  for (const alter of [{state: "disabled_manually"}, {name: "Legacy tracker"}, {path: ".github/workflows/manual_test.yml"}]) {
    const {calls, fetchImpl} = fakeFetch([metadata, {...workflow, ...alter}]);
    await assert.rejects(dispatchCollector(options, fetchImpl), /canonical_workflow_unavailable/);
    assert.equal(calls.length, 2);
  }
});

test("already running canonical collector coalesces redundant scheduler request", async () => {
  const {calls, fetchImpl} = fakeFetch([metadata, workflow, {workflow_runs: [{
    repository: {id: REPOSITORY_ID}, name: workflow.name, path: workflow.path,
    head_branch: "main", status: "in_progress",
  }]}]);
  assert.equal((await dispatchCollector(options, fetchImpl)).status, "already_queued_or_running");
  assert.equal(calls.length, 3);
});

test("failed dispatch is sanitized and never automatically retried", async () => {
  const {calls, fetchImpl} = fakeFetch([metadata, workflow, {workflow_runs: []}, new Error(`response body ${token}`)]);
  await assert.rejects(dispatchCollector(options, fetchImpl), error => {
    assert.equal(error.message, "github_network_outcome_unknown");
    assert.equal(error.message.includes(token), false);
    return true;
  });
  assert.equal(calls.length, 4);
});

test("GitHub token cannot follow a redirect to another host", async () => {
  const {calls, fetchImpl} = fakeFetch([new Response(null, {status: 301, headers: {Location: "https://attacker.invalid/repos/repo"}})]);
  await assert.rejects(dispatchCollector(options, fetchImpl), /unsafe_repository_redirect/);
  assert.equal(calls.length, 1);
});

test("safe same-origin rename redirects still require repository ID validation", async () => {
  const {calls, fetchImpl} = fakeFetch([
    new Response(null, {status: 301, headers: {Location: `https://api.github.com/repositories/${REPOSITORY_ID}`}}),
    metadata, workflow, {workflow_runs: []}, new Response(null, {status: 204}),
  ]);
  assert.equal((await dispatchCollector(options, fetchImpl)).status, "dispatch_accepted");
  assert.equal(calls[1].url, `https://api.github.com/repositories/${REPOSITORY_ID}`);
});

test("unknown branch cannot target a simulation, publisher or arbitrary workflow", async () => {
  await assert.rejects(dispatchCollector({...options, branch: "manual_test"}, () => assert.fail("network request")), /unknown_collector/);
  assert.deepEqual(Object.keys(TARGETS), ["legislative", "executive"]);
  assert.equal(TARGETS.legislative.cron, "5,20,35,50 * * * *");
  assert.equal(TARGETS.executive.cron, "11,41 * * * *");
});
