# PolitiTrack project state

**Current as of:** 2026-09-05 14:43 UTC
**Canonical repository ID:** `1349678672`
**Current repository name:** `maglothinm/MyETF-Intelligence`
**Default branch:** `main`
**Current main:** `adefe3bad1cf52470bf8eb8e0a71937b70770eec`
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

The same candidate now contains the PR #125 correction. The Legislative workflow
is manual-only and requires an explicit validation acknowledgement. It receives no
Pushover or Healthchecks credentials, forces `--no-notify`, cannot trigger the AI
analyst or Pages publisher, isolates each official source transactionally, retains
restore/source/controlled receipts, preserves the canonical run-history schema,
and runs the new integration coverage in CI.

The controlled run has two acceptable evidence outcomes. With zero
notification-eligible records, one or two validated official sources may publish
a durable successor. With notification-eligible records, all six protected state,
ledger, and history files are restored byte-for-byte and only the unchanged
predecessor boundary is republished with a zero-outbound receipt. A total outage
may preserve continuity but cannot satisfy Phase 4.

Phase 4 also requires a later checked-in descriptor for the exact controlled run.
It verifies the predecessor and both successor artifacts against live GitHub
metadata and digests, validates all three receipts and archive contents, and proves
that collector implementation bytes and executable mode did not change before the
schedule-restoration revision. No placeholder descriptor is present.

PR #126 merged the reconciliation and controlled Legislative correction to
`main` as `4e0791f29e09831bfc399d528a8dd66604b1ebf7`. Its exact PR head passed the
required Python, Node, repository-contract, and observed-state checks. The first
controlled run, `33971479311` attempt 1, stopped in predecessor restore before
the tracker executed, before any state upload, and without any notification or
heartbeat credential. The live artifact was unexpired; the workflow's jq
expression used boolean-alternative semantics that converted an explicit
`expired: false` value to `true`.

PR #127 merged the exact-boolean correction as
`3737ae25d408a40ef67d1d82cd389c2e1a1123c0`. Controlled run `33971975967`
then restored the artifact metadata successfully but stopped before download when
the retry guard rejected the producer's `push` event. That producer is the
intentional recovery-only run `33966378019` attempt 1 at immutable revision
`23cc3b83cf468ed65d228b5208d30eff8798f5ff`; it restored a pinned earlier
artifact, sent no notifications, and uploaded the current continuity boundary.

PR #128 merged the pinned recovery-producer correction as
`adefe3bad1cf52470bf8eb8e0a71937b70770eec`. Controlled run `33972544005`
successfully completed the full predecessor restore and retry guard. It then
stopped at the offline-test gate before the tracker executed because its
orchestrator fixture inherited the workflow's production source-status path and
live restore-receipt requirement while reading a fixture-local path and
intentionally constructing no live receipt. The production implementation did
not fail, no protected artifact was published, and no outbound credential was
present.

The active correction branch is
`phase4/hermetic-legislative-offline-tests-20260905`. It makes the test fixture's
source-status destination explicit and clears the live-only receipt requirement
so the same tests are hermetic under both CI and the Legislative job environment.
No `phase4-ready.json` completion certificate exists yet.

## Exact blockers

1. Merge the hermetic offline-test correction only after the exact
   PR head is green.
2. Complete one controlled,
   no-notify main-branch validation. Pin its exact run, job, predecessor, artifacts,
   digests, and receipts in the Phase 4 prerequisite descriptor.
3. Restore the reviewed recurring schedule in a follow-up change. At the moment
   Phase 4 runs, the workflow must be API-active and its checked-in source must
   pass the rollback route contract.
4. Phase 4 must then replay both pinned Runtime artifacts and verify that live Runtime
   heads and latest receipts have not drifted. Only that successful run may issue
   the certificate.

If the Runtime heads and latest receipts remain unchanged, no new shadow producer
cycles are required. The earliest certificate is immediately after the controlled
Legislative run is pinned, the reviewed recurring route is restored and active,
and one Phase 4 reconciliation run succeeds. Any Runtime head or latest-receipt
drift reopens the evidence gate and requires a separately reviewed continuation;
it is not permission to rebaseline.

## Phase 5 boundary

Issue #100 authorizes Phase 5, not Phase 6. Phase 5 remains blocked until a
successful Phase 4 run emits the hash-verified certificate on the exact current
`main` revision. The Phase 5 workflow then rechecks the certificate, route source,
workflow states, current heads, and latest receipts before it may transfer
production authority. No Phase 5 production smoke, Runtime scheduler activation,
public Runtime web cutover, or legacy-writer disablement has been accepted as
complete.

## Next safe action

Review and merge the narrow expiration-field correction, perform the
alerts-suppressed main validation, and only then restore the recurring route and
allow Phase 4 certification to run.
