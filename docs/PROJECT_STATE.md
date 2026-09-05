# PolitiTrack project state

**Current as of:** 2026-09-05 13:20 UTC
**Canonical repository ID:** `1349678672`
**Current repository name:** `maglothinm/MyETF-Intelligence`
**Default branch:** `main`
**Current main:** `706873d041f5dfc1c0cc384205ee385413f7a432`
**Phase 4 tracking issue:** #99
**Phase 5 authorization:** #100
**Phase 4 certificate:** not issued
**Phase 5 production cutover:** blocked

This file records current operational truth. Historical receipts remain in
GitHub Actions artifacts, the append-only decision log, and Git history.

## Current production authority and incident state

The retained GitHub Actions workflows remain production authority. Runtime v2
has completed shadow evidence but has not received production authority.

PR #125 merged to `main` as `706873d041f5dfc1c0cc384205ee385413f7a432`
and restored the Legislative schedule before a safe main-branch production
validation. Review after merge found that its exactly-one-source degraded result
is rejected by the next workflow validation step, so a degraded run cannot
publish a successor `legislative-tracker-state`. The new orchestrator's source
receipt is also omitted from uploaded artifacts, its run-history record is not in
the dashboard's canonical schema, and the new integration test was omitted from
the required CI commands.

To prevent the next schedule from recreating the unretained-side-effect
continuity incident, workflow ID `345003824` (`Legislative purchase tracker v2`)
was set to `disabled_manually` at approximately 2026-09-05 13:15 UTC. This is a
reversible safety pause. Executive tracking remains separate and was not changed.

The newest verified Legislative continuity artifact at the pause boundary is:

| Evidence | Value |
|---|---|
| Artifact | `9969550055` (`legislative-tracker-state`) |
| Producing run | `33966378019`, attempt 1 |
| Producing revision | `23cc3b83cf468ed65d228b5208d30eff8798f5ff` |
| Run conclusion | success |
| Archive SHA-256 | `bd698df04dc12d04a119bd59bc45ba09876dea7cfc108b0c6583dc296d8b413d` |
| Continuity treatment | preserve; do not rebaseline |

## Phase 4 execution lookup

The obsolete `gcloud run jobs executions describe-latest` lookup is no longer in
`deploy/runtime-v2/runtime_promotion_control.sh`. The shared controller first
reads the completed `gcloud run jobs execute --format=json` receipt and uses the
supported Cloud Run Job `status.latestCreatedExecution.name` field only as a
bounded fallback. Cross-job receipts fail closed.

## Phase 4 two-cycle evidence

The immutable recovered anchor remains unchanged. Two failed controller runs
contain the complete chained shadow history:

| Role | Run | Head revision | Artifact | Archive SHA-256 | Result used |
|---|---:|---|---:|---|---|
| Anchored prefix | `33878297187` | `58503dff1b5b944ba0ee9466c0450f8351499206` | `9942568612` | `9c843a10fe65c40cff2358dcb3557fcb688c282602061abf3e8a63669413a04f` | six successful receipts plus two AI failures that wrote no snapshot |
| Completed history | `33887857023` | `aedcb2c936a08947b1f38a062b0bee86bf75b0cb` | `9945994606` | `f91bb81e9cec45390064e686220e1262d2df70de9227f4263c595d1b8c5fdad8` | eight ordered, unique, successful receipts across two complete cycles |

The second artifact starts from the exact final heads of the first artifact. Its
final protected heads are:

| Namespace | Generation | Snapshot SHA-256 |
|---|---:|---|
| Legislative | 6 | `aa929115f31cd7cfb3ed2fc35a9a86e13b98750d4994d81148392081fcf446f7` |
| Executive | 6 | `a53d91ea377ba60a2a209be6f413b001019904993371f2cbde91b1af68c1090d` |
| AI | 5 | `39b6408c3922319bafcaf4380df9ac6a7d225eb4590a86937b884b8351cb4007` |
| Dashboard | 6 | `ee66d67e5f500e721dd2c805f091dc008b41fc12b91721a102691f13009a6f79` |

The producer portion of the required two-cycle shadow acceptance therefore
completed successfully. The original workflow still concluded `failure` because
its validator required the later live baseline to equal the immutable recovered
anchor even after the preceding failed run had legitimately advanced that
baseline. That failure did not issue a certificate and did not start Phase 5.

## Reconciliation implementation

The active reconciliation branch is
`phase4/reconcile-failed-shadow-evidence-20260905`. It preserves the anchor and
performs no additional producer execution. Its replay validator pins the two run
IDs, attempts, jobs, revisions, artifact IDs, sizes, digests, and expiration;
checks safe ZIP/JSON handling; proves the cross-artifact chain and two ordered
cycles; and requires the current Runtime heads and latest receipts to remain
identical to the replayed result.

Certification additionally requires the retained rollback workflows' current API
states and checked-in source contract, including a schedule-capable Legislative
and Executive collector. The resulting route receipt is included in the Phase 4
certificate and must match current source again before Phase 5. Failed Phase 5
smoke commands and failed legacy recovery dispatches cannot fall through to stale
execution receipts or produce a false rollback-complete marker.

No reconciliation commit is on `main`, no reconciliation Actions run has
succeeded, and no `phase4-ready.json` completion certificate exists yet.

## Exact blockers

1. Correct the merged PR #125 workflow/orchestrator contract while keeping the
   Legislative workflow manual-only and alerts suppressed.
2. Merge the reconciliation and corrective code only after the exact PR head is
   green.
3. Re-enable the manual-only Legislative workflow and complete one controlled,
   no-notify main-branch validation that restores the protected artifact, retains
   the source receipt, and preserves canonical run history.
4. Restore the reviewed recurring schedule in a follow-up change. At the moment
   Phase 4 runs, the workflow must be API-active and its checked-in source must
   pass the rollback route contract.
5. Phase 4 must then replay both pinned artifacts and verify that live Runtime
   heads and latest receipts have not drifted. Only that successful run may issue
   the certificate.

If the Runtime heads and latest receipts remain unchanged, no new shadow producer
cycles are required. The earliest certificate is immediately after the corrected
legacy-route validation and schedule restoration, plus one successful Phase 4
reconciliation run. Any Runtime head or latest-receipt drift reopens the evidence
gate and requires a separately reviewed continuation; it is not permission to
rebaseline.

## Phase 5 boundary

Issue #100 authorizes Phase 5, not Phase 6. Phase 5 remains blocked until a
successful Phase 4 run emits the hash-verified certificate on the exact current
`main` revision. The Phase 5 workflow then rechecks the certificate, route source,
workflow states, current heads, and latest receipts before it may transfer
production authority. No Phase 5 production smoke, Runtime scheduler activation,
public Runtime web cutover, or legacy-writer disablement has been accepted as
complete.

## Next safe action

Finish and review the manual-only Legislative correction and Phase 4
reconciliation, run the full required test set on their exact PR head, merge,
perform the alerts-suppressed main validation, and only then restore the recurring
route and allow Phase 4 certification to run.
