# Collector scheduling and external dispatch

Status: repository implementation prepared; **no Cloudflare scheduler is activated
or verified by this change**. The checked-in Worker has no public route, no cron
triggers, and `SCHEDULER_ENABLED = "false"`. GitHub cron remains enabled. Material
work is tracked in canonical issue #19; repository identity is **1349678672**.

## Why successful runs were insufficient

Before this change, Legislative ran on `7,22,37,52 * * * *`, while Executive ran
only on `13 * * * *`. Both retained Python collector start/completion timestamps
in `runs.jsonl`; AI appended its own processing history after successful collector
workflow completions. These are not workflow-start timestamps. Protected artifacts
are uploaded only on successful producer paths, so a failed workflow may have no
new retained row. Pages was triggered only by successful upstream completions.
The old dashboard computed age without enforcing cadence; successful history could
therefore remain green indefinitely. A successful Pages build establishes neither
collector execution nor source currency.

The publisher now takes an additional read-only snapshot of canonical Actions run
attempts. It verifies numeric repository identity, default branch, workflow
name/path, exact run attempt, authoritative job and ancestor commit. Failed
collector/AI completions also trigger this same publisher; failed simulator runs
do not. Successful Actions jobs cannot replace a retained collector completion or
refresh source currency. Queued time, workflow start, job finish and collector
completion remain distinct; unavailable evidence is reported as unavailable.
Cancelled/skipped publication is never a collector failure.

## Cadence and dispatch contract

| Worker | Expected cadence | Stale after | GitHub fallback | Prepared external cron (UTC) |
|---|---|---|---|---|
| Legislative | 15 minutes | 30 minutes | `7,22,37,52 * * * *` | `5,20,35,50 * * * *` |
| Executive / OGE | 30 minutes | 60 minutes | `13,43 * * * *` | `11,41 * * * *` |

AI remains downstream of successful collector completions, with its SLA in the
shared Python freshness policy. It has no new schedule. Existing collector timeout
budgets are 40/45 minutes; a slow run can exceed the expected interval. A redundant
trigger never cancels an active collector. Overdue work stays visibly overdue
rather than extending its freshness threshold merely because a job is running.

Any trusted scheduler can invoke the same authenticated GitHub REST endpoint:
`POST /repos/{owner}/{repo}/actions/workflows/{workflow-file}/dispatches`, with
`{"ref":"<live-default-branch>","inputs":{"trigger_source":"external_scheduler"}}`.
Only `legislative_trade_tracker_v2.yml` and `executive_trade_tracker.yml` are
allowlisted in `scheduler/dispatch.mjs`. There is no external collector, state
writer, browser scheduling code, or alternate artifact authority.

The client resolves the live repository/default branch, checks ID **1349678672**,
validates the expected active workflow, and coalesces a dispatch when a recent
canonical run is already queued/running. Repository rename redirects are accepted
only on `api.github.com`; mismatched IDs, disabled workflows, malformed responses
and credential failures stop dispatch. POST outcomes are not automatically retried:
a network timeout could occur after GitHub accepted the dispatch. The next scheduled
cycle checks again. A dispatch acceptance log is not an execution-success heartbeat.

The non-secret `trigger_source` label is retained in collector/AI run history. It
is observability metadata, **not proof of caller identity or an authorization
bypass**. Actions observations alone label an external call `workflow_dispatch`
until its actual retained run supplies `external_scheduler`. No credentials or
authentication metadata enter dashboard assets.

## Concurrency, deduplication, and failed attempts

The existing three fixed concurrency groups remain unchanged, each with
`cancel-in-progress: false`. All trigger sources use one canonical writer per
pipeline. GitHub may replace a pending redundant run; it must not cancel the active
state producer. Each next run restores the newest provenance-valid unexpired
artifact and enforces the existing successful-producer high-water mark. Restored
seen filing/trade IDs, analysis IDs and delivery state prevent repeated successful
triggers from duplicating filings, alerts or AI work. Explicit manual AI reanalysis
retains its existing intentional behavior.

External delivery and artifact publication are not one transaction. An alert might
be accepted before a collector fails or its final artifact upload fails. A new
pre-collection guard therefore checks exact attempts since the restored producer,
including reruns with older run IDs. If a later collector/analyst step possibly
executed without retained authoritative state, the next writer stops before
collection or candidate notifications. Proven skipped/unstarted collector steps
can retry; missing/ambiguous job/step evidence fails closed. The guard changes no
protected artifact and has no bypass input. Existing Healthchecks/failure reporting
is preserved; the guard protects filing/candidate delivery, not repeated incident
notifications.

A blocked attempt requires incident review of delivery and artifact continuity,
then recovery using the repository contract. Do not clear IDs, initialize a fresh
baseline, suppress all future alerts, or upload failed-run state to get past it.
This deliberately stops uncertain retries; it does **not** claim mathematically
exactly-once delivery, recover lost state, or solve an external service's ambiguous
acceptance by guessing. Retention-expired/ambiguous Actions history also blocks
unsafe replay. Observation scans have a 100-page bound; exceeding it is unavailable
evidence, never success. API errors never become fabricated run records.

## Staged activation and evidence required

1. Merge tested repository changes and publish through the existing Pages path.
   Verify stale/failure/current behavior against provenance-valid retained state
   and real Actions history; keep both GitHub cron schedules enabled.
2. Resolve the retained production gate for obsolete queued runs **33219808359**
   and **33221027676**. Do not activate an automatic external dispatch as a way
   around the separately required GitHub clearance and continuity review.
3. Choose the Cloudflare account and a repository-scoped GitHub credential. A
   fine-grained token needs **Actions: write** plus repository metadata access,
   restricted to canonical ID 1349678672, with expiry/rotation ownership recorded.
   A managed GitHub App installation token is also possible, but this example does
   not mint or renew expiring installation tokens. Actions write permits more than
   these two workflows; the Worker allowlist is an additional application safeguard.
4. Copy `scheduler/cloudflare/wrangler.toml` to the ignored
   `scheduler/cloudflare/wrangler.production.toml`. Keep it disabled while selecting
   the account and storing `GITHUB_DISPATCH_TOKEN` with Wrangler's interactive
   `secret put` command (or Cloudflare's secret UI). Never put the token in TOML,
   a public asset, a command argument, logs, a committed `.env`, or an issue.
5. After approval/clearance, set the production copy's enabled flag to `"true"`
   and configure its two documented cron expressions; deploy that explicit config.
   Do not add an HTTP route, `fetch` handler or public trigger endpoint. Cloudflare
   cron configuration can take time to propagate; verification must observe actual
   executions rather than a successful deployment command alone.
6. Verify several real cycles for both workers, including GitHub run IDs/attempts,
   non-secret retained trigger labels, ~15/~30-minute completions, artifact lineage,
   deduplication, downstream AI/Pages and advancing source timestamps. Verify
   credentials/rotation and alert delivery separately. Missing dispatches naturally
   become stale; do not add an unverified green “scheduler alive” badge.
7. Document the fallback decision only after those cycles succeed. Initially keep
   GitHub cron as redundancy. Disabling it is a separate recorded authority change.
   Roll back external scheduling by setting production `crons = []` and enabled
   false, deploying, then confirming no external cycles remain; preserve GitHub
   schedules and all production artifacts.

## References and local verification

The implementation follows GitHub's [workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
and [concurrency behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
and Cloudflare's [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
and [Wrangler configuration](https://developers.cloudflare.com/workers/wrangler/configuration/).
Documentation was checked on 2026-08-31. The client accepts both the documented
200 dispatch response and the older 204 response, without publishing response data.

Deterministic offline checks: `python -m pytest -q tests/test_scheduler_evidence.py`
and `node --test tests/scheduler_dispatch.test.mjs`. Tests stub all GitHub requests;
they cannot prove external activation or observed production cadence.
