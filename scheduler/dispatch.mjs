// Provider-neutral dispatch client. It contains no collector or state-writing logic.
export const REPOSITORY_ID = 1349678672;
export const TARGETS = Object.freeze({
  legislative: Object.freeze({file: "legislative_trade_tracker_v2.yml", name: "Legislative purchase tracker v2", cron: "5,20,35,50 * * * *"}),
  executive: Object.freeze({file: "executive_trade_tracker.yml", name: "Executive purchase tracker", cron: "11,41 * * * *"}),
});
const API = "https://api.github.com";
const ACTIVE = new Set(["queued", "in_progress", "waiting", "pending", "requested"]);
const repositoryName = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

export class DispatchError extends Error {
  constructor(code) { super(code); this.name = "DispatchError"; this.code = code; }
}

async function github(fetchImpl, path, token, body) {
  const headers = {
    "Accept": "application/vnd.github+json", "Authorization": `Bearer ${token}`,
    "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "PolitiTrack-Scheduler",
  };
  if (body) headers["Content-Type"] = "application/json";
  let url = API + path;
  // Follow only a same-origin GitHub repository rename redirect, never send a
  // credential to a response-supplied host. Do not retry a possibly accepted POST.
  for (let redirect = 0; redirect < 3; redirect++) {
    let response;
    try {
      response = await fetchImpl(url, {
        method: body ? "POST" : "GET", headers, redirect: "manual",
        signal: AbortSignal.timeout(20000), ...(body ? {body: JSON.stringify(body)} : {}),
      });
    } catch { throw new DispatchError("github_network_outcome_unknown"); }
    if ([301, 302, 307, 308].includes(response.status) && !body) {
      let destination;
      try { destination = new URL(response.headers.get("Location"), url); }
      catch { throw new DispatchError("invalid_repository_redirect"); }
      if (destination.origin !== API || !/^\/(repos|repositories)\//.test(destination.pathname)) {
        throw new DispatchError("unsafe_repository_redirect");
      }
      url = destination.href;
      continue;
    }
    if (!response.ok) throw new DispatchError(`github_http_${response.status}`);
    if (body) {
      if (![200, 204].includes(response.status)) throw new DispatchError("unexpected_dispatch_response");
      return null; // Acceptance is not evidence of execution or collector success.
    }
    try { return await response.json(); }
    catch { throw new DispatchError("invalid_github_response"); }
  }
  throw new DispatchError("repository_redirect_limit");
}

export async function dispatchCollector({branch, repository, token, enabled}, fetchImpl = fetch) {
  const target = TARGETS[branch];
  if (!target) throw new DispatchError("unknown_collector");
  if (enabled !== "true") return {branch, status: "disabled"};
  if (!token || typeof token !== "string") throw new DispatchError("missing_dispatch_secret");
  if (typeof repository !== "string" || !repositoryName.test(repository)) throw new DispatchError("invalid_repository");
  const repo = await github(fetchImpl, `/repos/${repository}`, token);
  if (repo?.id !== REPOSITORY_ID || repo.archived || repo.disabled) throw new DispatchError("canonical_repository_mismatch");
  if (!repositoryName.test(repo.full_name || "") || typeof repo.default_branch !== "string" || !repo.default_branch) {
    throw new DispatchError("invalid_repository_metadata");
  }
  const base = `/repos/${repo.full_name}/actions/workflows/${target.file}`;
  const workflow = await github(fetchImpl, base, token);
  if (workflow.name !== target.name || workflow.path !== `.github/workflows/${target.file}` || workflow.state !== "active") {
    throw new DispatchError("canonical_workflow_unavailable");
  }
  const recent = await github(fetchImpl, `${base}/runs?branch=${encodeURIComponent(repo.default_branch)}&per_page=20`, token);
  if (!Array.isArray(recent.workflow_runs)) throw new DispatchError("run_evidence_unavailable");
  const active = recent.workflow_runs.some(run => run.repository?.id === REPOSITORY_ID
    && run.name === target.name && String(run.path || "").split("@")[0] === `.github/workflows/${target.file}`
    && run.head_branch === repo.default_branch && ACTIVE.has(run.status));
  if (active) return {branch, status: "already_queued_or_running"};
  await github(fetchImpl, `${base}/dispatches`, token, {
    ref: repo.default_branch, inputs: {trigger_source: "external_scheduler"},
  });
  return {branch, status: "dispatch_accepted"};
}
