# PolitiTrack active handoff

Updated: **2026-09-05 15:05 UTC**

Canonical repository: **ID 1349678672 — `maglothinm/MyETF-Intelligence`**

Canonical main: **`e160d1783ee93508761e0054b909e29d8b00ef3d`**

Active issue: **#99 — Phase 4 final live shadow validation gate**

Authorized successor: **#100 — Phase 5 production promotion**

Active branch: **`phase4/restore-legislative-route-and-pin-evidence-20260905`**

Certificate state: **not issued**

Production cutover state: **blocked**

## Completed evidence

- The unsupported `describe-latest` execution lookup is gone. Exact execute JSON
  is primary and `status.latestCreatedExecution.name` is only a bounded fallback.
- Run `33887857023` / artifact `9945994606` contains the required eight ordered
  successes across two complete shadow cycles and chains from run `33878297187`
  / artifact `9942568612`. No additional producer run is authorized or needed
  while current heads and latest receipts remain unchanged.
- The controlled Legislative run `33972938031` attempt 1, job `101324554606`,
  succeeded at `e160d1783ee93508761e0054b909e29d8b00ef3d` with both sources healthy,
  zero notification-eligible records, and zero outbound activity.
- Protected successor artifact `9971492043` has archive SHA-256
  `61f2a22f9a06a12c01fb0f1933090ec86b5657122c16cced7080fc5d9a45e46a`;
  diagnostic artifact `9971492201` has SHA-256
  `21af1d80644294d918854f686636e26fe152ecb8891c3c25bee16ca3f1c01668`.
- The exact predecessor is artifact `9969550055`, run `33966378019` attempt 1,
  revision `23cc3b83cf468ed65d228b5208d30eff8798f5ff`, archive SHA-256
  `bd698df04dc12d04a119bd59bc45ba09876dea7cfc108b0c6583dc296d8b413d`.

## Active reconciliation

The follow-up branch adds the real controlled-run descriptor and restores the
operational Legislative route: schedule `7,22,37,52 * * * *` in
America/New_York, manual/external trigger labels, notification and heartbeat
wiring, and successful-run fan-out to AI and Pages. It retains all exact-attempt,
digest, ancestry, high-water, and state-initialization protections.

The production durable gate accepts a validated one- or two-source successor,
but rejects zero sources, missing restore evidence, invalid state, or inconsistent
delivery evidence. The route verifier now fails a merely cosmetic cron if the
workflow remains controlled-only, no-notify, or upload-gated by a
suppression-specific validator.

No file in the controlled-evidence implementation set may change between
`e160d1783ee93508761e0054b909e29d8b00ef3d` and the restoration revision.

## Remaining sequence

1. Pass local verification and exact-head CI for the restoration/evidence PR.
2. Merge it and freeze `main`.
3. Let Phase 4 v6 replay the pinned artifacts, verify current Runtime heads and
   latest receipts, and issue the hash-checked `phase4-readiness` artifact.
4. Let the authorized Phase 5 v2 workflow bind that certificate and complete the
   one-writer production transfer.
5. Verify the Phase 5 artifact, Runtime scheduler/web state, legacy workflow
   retirement, and protected continuity. Stop before Phase 6.

## Certificate semantics

Phase 4 does not commit `phase4-ready.json`; it has read-only repository content
permission. A valid certificate is the `phase4-ready.json` plus its SHA-256 file
inside artifact `phase4-readiness` from a successful Phase 4 v6 run. Failed runs
may upload diagnostics under the same artifact name, so artifact presence alone
is not completion.

## Current blocker

The certificate can be issued at the first successful Phase 4 v6 run after the
restoration/evidence commit reaches `main`, provided the four Runtime heads and
latest receipts still match the pinned two-cycle evidence. Phase 5 remains
blocked until that exact run succeeds; Phase 6 is outside authorization.
