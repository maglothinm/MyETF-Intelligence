# PolitiTrack active handoff

Updated: **2026-09-05 13:20 UTC**
Canonical repository: **ID 1349678672 — `maglothinm/MyETF-Intelligence`**
Canonical main: **`706873d041f5dfc1c0cc384205ee385413f7a432`**
Active issue: **#99 — Phase 4 final live shadow validation gate**
Authorized successor: **#100 — Phase 5 production promotion**
Active branch: **`phase4/reconcile-failed-shadow-evidence-20260905`**
Certificate state: **not issued**
Production cutover state: **blocked**

## Current authority and immediate safety state

The GitHub Actions path remains production authority. Runtime v2 remains the
shadow candidate and has not been promoted.

PR #125 merged at `706873d041f5dfc1c0cc384205ee385413f7a432` with a
live Legislative cron before its degraded-state publication contract had been
validated on `main`. Because a one-source degraded result would be rejected by
the next validator and withheld from protected-state upload, workflow ID
`345003824` was reversibly set to `disabled_manually` before its next scheduled
start. Do not re-enable its schedule until the correction and controlled
alerts-suppressed validation described below are complete.

Newest protected Legislative authority at the pause boundary:

- artifact `9969550055` (`legislative-tracker-state`);
- run `33966378019`, attempt 1, conclusion `success`;
- source `23cc3b83cf468ed65d228b5208d30eff8798f5ff`;
- archive SHA-256
  `bd698df04dc12d04a119bd59bc45ba09876dea7cfc108b0c6583dc296d8b413d`.

Preserve it. Missing or rejected successor state is a blocker, not rebaseline
authority.

## Phase 4 facts

- The unavailable `gcloud run jobs executions describe-latest` call has already
  been replaced. The controller prefers the exact execute-command JSON receipt
  and uses `status.latestCreatedExecution.name` only as a bounded fallback.
- Run `33878297187` / artifact `9942568612` contains a valid six-success prefix
  and two AI failures with no snapshot mutation.
- Run `33887857023` / artifact `9945994606` begins at that exact final state and
  contains eight unique ordered shadow successes: two complete cycles.
- The old validator rejected the completed run because it compared the advanced
  live baseline directly to the earlier immutable anchor.
- No Phase 4 completion certificate was generated, and Phase 5 did not start.

The reconciliation implementation replays the two pinned artifacts without
executing a producer or changing the anchor. It validates GitHub run/job/artifact
metadata, archive hashes and contents, the complete chain, current Runtime heads,
current latest receipts, cleanup, and the source/API contract of the retained
rollback route. Phase 5 is hardened to recheck those bindings and to fail closed
on smoke or rollback-dispatch errors.

## Work still required

1. Correct PR #125's merged implementation in manual-only/no-notify mode:
   degraded-success validation and upload must agree; source-status evidence must
   be retained; canonical run-history schema and CLI compatibility must be
   preserved; and the new integration tests must actually run in CI.
2. Combine or sequence that correction with the Phase 4 reconciliation on a
   green, reviewable PR.
3. After merge, enable only the manual workflow path and perform one controlled
   no-notify main validation. Verify the exact run, attempt, state artifact,
   digest, predecessor, and source receipt.
4. Restore the recurring schedule in a follow-up reviewed change. Ensure the
   workflow API state is active.
5. Let Phase 4 replay the pinned evidence. It may issue `phase4-ready.json` only
   if current Runtime heads and latest receipts still match the evidence and the
   rollback route is operational.
6. Issue #100 may proceed automatically only from that successful certificate.
   Stop before Phase 6.

## Earliest certificate

If current Runtime heads and latest receipts have not changed, the certificate
can be issued on the first successful Phase 4 reconciliation run after the
corrected legacy route is validated, scheduled, and active. No additional shadow
producer cycle is needed. If those live receipts drift, stop and review a new
continuation record; do not change the immutable inventory.

## Prohibited shortcuts

Do not rebaseline the Runtime inventory, treat workflow state `active` as proof of
a working source route, accept a failed-run artifact without its pinned digest and
job metadata, allow a failed execute command to resolve a stale execution, enable
the unsafe merged schedule, initialize blank protected state, or describe Phase 5
as complete before its own completion artifact and terminal production checks
exist.
