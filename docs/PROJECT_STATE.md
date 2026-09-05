# PolitiTrack project state

**Current as of:** 2026-09-05 15:05 UTC

**Canonical repository ID:** `1349678672`

**Current repository name:** `maglothinm/MyETF-Intelligence`

**Default branch:** `main`

**Current main:** `e160d1783ee93508761e0054b909e29d8b00ef3d`

**Phase 4 tracking issue:** #99

**Phase 5 authorization:** #100

**Phase 4 certificate:** not issued

**Phase 5 production cutover:** blocked

This file records current operational truth. Historical receipts remain in
GitHub Actions artifacts, the append-only decision log, and Git history.

## Current authority

GitHub Actions remains production authority. Runtime v2 remains in shadow mode;
its producer schedulers are paused, its web route is private, and production
authority has not transferred.

The Legislative workflow API is active, but the source at current `main` is the
temporary controlled-validation form: manual dispatch only, explicit
acknowledgement required, notifications and heartbeat credentials absent, and
downstream AI/Pages fan-out blocked. It is not yet an operational recurring
rollback route. The active follow-up branch is
`phase4/restore-legislative-route-and-pin-evidence-20260905`.

## Phase 4 execution lookup

The obsolete `gcloud run jobs executions describe-latest` lookup is absent from
`deploy/runtime-v2/runtime_promotion_control.sh`. The shared controller first
uses the exact JSON returned by `gcloud run jobs execute` and only then permits
the supported Cloud Run Job `status.latestCreatedExecution.name` field as a
bounded fallback. It verifies that every resolved execution belongs to the
expected job, so a failed command cannot fall through to a stale receipt.

## Completed two-cycle shadow evidence

The immutable evidence remains current and requires no additional producer run:

| Role | Run | Head revision | Artifact | Archive SHA-256 |
|---|---:|---|---:|---|
| Anchored prefix | `33878297187` | `58503dff1b5b944ba0ee9466c0450f8351499206` | `9942568612` | `9c843a10fe65c40cff2358dcb3557fcb688c282602061abf3e8a63669413a04f` |
| Completed two cycles | `33887857023` | `aedcb2c936a08947b1f38a062b0bee86bf75b0cb` | `9945994606` | `f91bb81e9cec45390064e686220e1262d2df70de9227f4263c595d1b8c5fdad8` |

The second artifact chains from the first artifact's final heads and contains
eight ordered, unique successful receipts across two complete cycles. The final
heads are:

| Namespace | Generation | Snapshot SHA-256 |
|---|---:|---|
| Legislative | 6 | `aa929115f31cd7cfb3ed2fc35a9a86e13b98750d4994d81148392081fcf446f7` |
| Executive | 6 | `a53d91ea377ba60a2a209be6f413b001019904993371f2cbde91b1af68c1090d` |
| AI | 5 | `39b6408c3922319bafcaf4380df9ac6a7d225eb4590a86937b884b8351cb4007` |
| Dashboard | 6 | `ee66d67e5f500e721dd2c805f091dc008b41fc12b91721a102691f13009a6f79` |

Those producer cycles succeeded. Their controller run ended in failure only
because the old validator compared the legitimately advanced live baseline to
the earlier immutable anchor. PR #126 replaced that comparison with pinned,
hash-verified replay and current-head/current-receipt reconciliation; it did not
rebaseline or execute another producer.

## Controlled Legislative validation

PRs #126 through #129 corrected the Legislative transactional orchestration,
restore metadata boolean handling, the exact recovery-only predecessor exception,
and hermetic offline tests. Current main is PR #129's merge revision.

The required controlled validation completed successfully:

| Evidence | Value |
|---|---|
| Workflow run | `33972938031`, attempt 1, run number 56 |
| Authoritative job | `101324554606` (`track`), success |
| Validated revision | `e160d1783ee93508761e0054b909e29d8b00ef3d` |
| Outcome | `zero_change_successor` |
| Sources | House `ok` (890 catalog records); Senate `ok` (86) |
| Notification evidence | 0 eligible, 0 attempted, 0 sent, 0 delivered |
| Protected successor | artifact `9971492043`, SHA-256 `61f2a22f9a06a12c01fb0f1933090ec86b5657122c16cced7080fc5d9a45e46a` |
| Diagnostic output | artifact `9971492201`, SHA-256 `21af1d80644294d918854f686636e26fe152ecb8891c3c25bee16ca3f1c01668` |

The protected successor restores from artifact `9969550055`, run
`33966378019` attempt 1, revision
`23cc3b83cf468ed65d228b5208d30eff8798f5ff`, and archive SHA-256
`bd698df04dc12d04a119bd59bc45ba09876dea7cfc108b0c6583dc296d8b413d`.
The restore, source-status, and controlled-validation receipts agree across both
successor archives. The protected ledger, transaction, filing, pending-review,
and alert-delivery state remained continuous; only the run history and state
success marker advanced.

## Schedule restoration candidate

The active follow-up pins the exact controlled evidence in
`deploy/runtime-v2/phase4-legislative-validation-evidence.json` and restores the
reviewed Legislative cadence (`7,22,37,52 * * * *`, America/New_York), manual
`trigger_source` dispatch, Pushover inputs, Healthchecks start/terminal signals,
and normal AI/Pages fan-out. It retains the strengthened exact-attempt restore,
artifact digest, compatible-ancestry, high-water, and retry guards.

The production tracker no longer uses `--no-notify`. A hard durable-result gate
and verified restore receipt are required before a protected successor uploads.
One successful official source may publish a truthful degraded successor; zero
sources, invalid state, missing restore evidence, or contradictory delivery
accounting cannot publish state. `REQUIRE_PUSHOVER` remains false, matching the
pre-incident availability contract; a secret reference is not proof that the
secret exists or delivery succeeds.

The legacy-route verifier now rejects cosmetic restoration: a Legislative file
with a cron still fails if it retains controlled-only acknowledgement,
notification suppression, protected-upload validation, or controlled mode.

## Exact blockers and earliest certificate

1. The schedule-restoration/evidence-pin branch must pass local verification and
   exact-head CI, then merge to `main`.
2. The automatically triggered Phase 4 v6 run must prove the descriptor,
   unchanged collector implementation bytes, operational legacy route, pinned
   two-cycle replay, unchanged Runtime heads/latest receipts, and cleanup.

If those live Runtime receipts remain unchanged, the Phase 4 completion
certificate can be issued by that first successful reconciliation run. No new
shadow producer cycle is needed. The certificate is a hash-checked
`phase4-ready.json` in the `phase4-readiness` Actions artifact; the workflow has
read-only contents permission and does not commit the certificate to Git.

## Phase 5 boundary

Issue #100 authorizes Phase 5, not Phase 6. A successful Phase 4 v6 run
automatically triggers Phase 5 v2. Phase 5 must bind the exact certificate and
certified main revision, recheck route source and Runtime heads/latest receipts,
then atomically transfer one-writer production authority and verify its terminal
evidence. Until that succeeds, Runtime schedulers, public Runtime web, and
legacy-writer retirement are not complete. Do not advance `main` while Phase 4
or Phase 5 is running; both workflows deliberately reject revision drift.

## Next safe action

Finish and merge the single restoration/evidence-pin PR from a green exact head,
then keep `main` fixed while Phase 4 and the authorized Phase 5 successor run.
Stop before Phase 6.
