# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: **issue #8 — Senate resilience and operational recovery**

## Current task

The owner authorized public evidence publication, clearing two obsolete queued
writers, then a fresh production run and continuity/deployment verification.
The historical draft and newly approved recovery evidence are published on
issue #8 and linked from PR #9. Scheduled recovery and deployment are now
independently verified. Queue clearance failed through every available supported
control, so the requested additional manual run remains **undispatched**.

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, default
`main`; audited runtime commit `3902968d5d70cd00030248ae4a6bcea18aa2e6ea`.
Implementation PR #9 merged source `125eac1aba5a5f5324040cbfac7f30b63a2f0347` as
`19f7044e8bd12fd4d693cf7f468623f318034717`, with matching trees. This handoff and
incident record are documentation-only successors. Preserve untracked `.codex/`,
held PR #3 and unrelated work. Never execute legacy `maglothinm/MyETF`.

**Publication authorization:** The owner explicitly approved the new recovery
evidence for issue #8, PR #9 and main, plus the prepared GitHub Support request.
The new evidence is published in
[issue comment 5477003406](https://github.com/maglothinm/MyETF-Intelligence/issues/8#issuecomment-5477003406)
and [PR comment 5477009236](https://github.com/maglothinm/MyETF-Intelligence/pull/9#issuecomment-5477009236).
These three documentation files record the same evidence without runtime changes.
Publication uses isolated branch `codex/senate-recovery-evidence`; the shared
checkout's concurrent `codex/dashboard-review-ux` edits are preserved.

## Completed and verified

The existing Senate client/complete-source processing/terminal heartbeat fix is
unchanged. Prior local full suite: **283 passed**; targeted client/monitor/tracker:
**117 passed**; heartbeat: **13 passed**. PR CI `33346339195` / attempt 1 / job
`99351095293` and main CI `33346456045` / attempt 1 / job `99351415370` succeeded
with 212 selected tests and Linux `verify.sh` reporting `VERIFICATION PASSED`.
No new runtime tests are claimed for this documentation-only update.

The owner explicitly approved the previously blocked public evidence. It is
published on [issue #8](https://github.com/maglothinm/MyETF-Intelligence/issues/8#issuecomment-5476609143)
and linked from [PR #9](https://github.com/maglothinm/MyETF-Intelligence/pull/9#issuecomment-5476612083).
That comment is the historical 01:09 UTC checkpoint; current evidence is in
[the incident record](incidents/senate-efd-2026-08-30.md).

Read-only audit completed at **09:51:27 UTC**; full publication preflight at
**10:24 UTC** reconfirmed all authorities, inventories, continuity and 21 live
files unchanged, with only the two obsolete queues active:

| Pipeline | Latest artifact | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` |

Exact producer identity/attempt windows, ancestry, high-water marks, ZIP digests,
full inventories and continuity passed. Legislative actual restore chain is
`9739239507 → 9742750536 → 9749549239`; the middle artifact came from successful
scheduled run `33348331610` / 1 / job `99356670792`. Run history advanced
29 → 30 → 31. Non-run ledgers are byte-identical; protected IDs and records are
retained. Always query newer live authority, never pin these IDs for restore.

Both scheduled Legislative recovery runs found House **883** / Senate **91**,
complete successful discovery, zero baseline changes/new filings/alerts, and
exactly one accepted Healthchecks success **HTTP 200** each. No audit ping was
sent. Provider-side UP/status history and notification delivery were not queried.

Pages `33369728437` / attempt 1 succeeded; build job `99417832272`, deploy
`99417945412`, artifact `9749580990`. Actual restore logs identify the three
latest inputs above. All **21** live files matched artifact bytes with HTTP 200;
published build `3902968`, 5,079 filings / 60 transactions / 1,496 reviews /
11 analyses. This is content/deployment acceptance, not device acceptance.

## Blocker and exact cleanup attempts

Obsolete canonical runs `33219808359` and `33221027676` remain queued, attempt 1,
SHA `b9cf0f3e3863de69d92ae01f35f1c154a082f56a`, zero jobs and zero artifacts.
Workflow ID `344663675`, `.github/workflows/legislative_trade_tracker.yml`, is
`deleted`, but existing records are not proven incapable of running.

Owner-authorized ordinary and force cancellation returned HTTP 409. Supported
REST deletion of only these exact empty records returned HTTP 403 after their
metadata exports were hash-verified. Signed-in UI `Cancel workflow` failed for
both; no delete option was available in the inspected run menu. Fresh API
readback at **09:52:29–30 UTC** still returned queued. See the incident record
for request IDs and hashes. No other runs/artifacts/settings were deleted or
changed. Do not relax the manual dispatch gate or recreate the retired workflow.

Local `.remediation/senate-recovery/` contains `scheduled-evidence.json`,
hash-verified ZIPs, queue exports/receipts, fresh readback and
`github-support-draft.md`. The support draft is authorized but **unsent**; it
requests backend cleanup and confirmation neither obsolete run can execute.
The signed-in support portal offered no applicable Actions ticket route. The
available repository-features form required Templates, Releases, Insights or
Branches, none of which describes this incident. No unrelated category was
submitted, no plan was changed and no ticket number exists.
These local exports are evidence, never alternate production-state authority.

## Next safe action

Use an eligible GitHub Actions technical-support route to submit the already
authorized draft. Owner publication/submission approval is no longer missing;
portal eligibility and backend queue clearance are the blockers. Once GitHub
clears the records or confirms they cannot
execute, recheck all writer runs, current main and newest provenance-valid
artifacts. Then dispatch exactly one new current-main Legislative run and verify
complete discovery, one accepted terminal heartbeat, exact producing attempt,
full protected-state continuity and downstream Pages artifact/live content.

Do not rerun the historical failed SHA, initialize, rebaseline, use a cache as
authority or introduce an alternate writer. No manual collector/AI/simulation
dispatch, fake heartbeat, live candidate-alert test or settings change was made
by this recovery session. Existing schedules were left intact. Device acceptance,
held PR #3, cutover/rename/privacy/legacy settings and Gmail delivery remain
separate work.
