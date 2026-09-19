# Operations manual runs — issue #164

Operations has a Run now button above the Legislative, Executive and AI analyst
history in each tile. Sign in with an explicitly authorized operator account.
Ordinary personal review accounts retain separate acknowledgements and cannot
start production work. Public dashboard reading remains available.

The button requests the same existing production job used by its schedule. It
shows starting, running, successful completion, failure, or an unconfirmed start.
Published history keeps its own timestamp and updates separately. A request being
accepted never establishes collection success. A scheduled run already in progress
disables manual dispatch. A rare race with a scheduled writer fails the manual
execution rather than reporting a coalesced/no-work process as successful.

## Identity, safety and audit

- Reuse the secure personal-account session, exact HTTPS origin and a dedicated
  request header. Validate the expected stable account UUID on every write.
- `RUNTIME_OPERATIONS_ACCOUNT_IDS` is an explicit server-side UUID allowlist. No
  account receives run privileges merely by signing up or choosing a username.
- Allow only `polititrack-legislative`, `polititrack-executive` and `polititrack-ai`.
  Verify their existing single-task, no-retry production entrypoints before start.
- Dispatch with the job's current etag and two fixed execution-only environment
  values: `POLITITRACK_TRIGGER_SOURCE=dashboard_manual` and a request UUID. The API
  accepts no command, environment, task-count, timeout or resource override from
  the browser. Job templates and schedules are unchanged.
- Commit an additive request receipt before dispatch. PostgreSQL row locks and a
  unique request UUID prevent duplicate starts across clicks, tabs and web workers.
  Keep the actor, timestamps and every prior request, independently of snapshots.
- Never automatically repeat a POST after a timeout. Reconcile its exact UUID
  against retained executions. If the start cannot be confirmed, further manual
  starts for that service remain blocked pending investigation; normal scheduled
  collection continues. Database and Cloud Run outages produce an unavailable
  status, not a fabricated successful run.
- Require completed execution evidence, all tasks successful and no failed or
  cancelled tasks before showing success. Preserve existing namespace locks,
  complete-source validation, atomic snapshots and durable notification outbox.
  No producer state, failed history, delivery hold or retry flag is rewritten.

The AI cadence label now reflects its existing `14,44 * * * *` schedule rather
than the retired workflow-run relationship. Its 75-minute freshness limit remains.

## Deployment

The feature defaults off. Install only its additive receipt tables with
`python -m runtime_v2 operations-init-db`, using the existing private database.
Configure these values on the existing web service:

| Setting | Value |
|---|---|
| `RUNTIME_OPERATIONS_ENABLED` | `true` after readiness verification |
| `RUNTIME_OPERATIONS_ACCOUNT_IDS` | Existing authorized account UUIDs, comma separated |
| `RUNTIME_OPERATIONS_PROJECT` | Existing production GCP project |
| `RUNTIME_OPERATIONS_REGION` | Existing production region |
| `RUNTIME_PERSONAL_REVIEWS_ENABLED` / `RUNTIME_REVIEW_ORIGIN` | Preserve existing personal-account configuration |

The optional Terraform role `polititrackManualRuns` grants the web service account
only `run.jobs.get`, `run.jobs.run`, `run.jobs.runWithOverrides`,
`run.executions.get` and `run.executions.list`, bound on the three named jobs.
It grants no job-edit, cancellation, scheduler, IAM, admin-job or dashboard-job
permission. Execution overrides require a distinct Cloud Run permission; this is
why the existing read-only web identity needs a narrowly scoped grant.
[Cloud Run run API](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run).

Coordinate the shared production release with the active Legislative recovery.
Fence and drain existing schedules for the image/schema cutover; preserve accounts,
acknowledgements, notification history, snapshots and original incident rows.
Use an outbox-compatible rollback image and leave additive receipt history intact.
Disable the web feature to withdraw controls without affecting scheduled jobs.

## Acceptance

`tests/test_operations.py` covers owner/ordinary/anonymous access, origin and
account-change protection, fixed resources/overrides, dispatch replay/restart,
scheduled overlap, failure retry, lost responses, full-page busy checks and real
PostgreSQL concurrency in Runtime CI. Generated DOM checks cover all three buttons,
sign-in, scheduled busy status, duplicate clicks, failures, uncertain responses and
success only after terminal execution evidence.

Local implementation is not production acceptance. Record exact CI heads and
attempts, image, publication and manual execution outcomes in the release receipt.
