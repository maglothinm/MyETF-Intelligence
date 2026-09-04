# Phase 5 Runtime v2 production promotion

Phase 5 transfers PolitiTrack's automatic production authority from the retained GitHub Actions collectors and Pages publisher to Runtime v2. It is a gated cutover, not a decommissioning phase.

## Authoritative controls

The live control path is versioned and fail-closed:

- `.github/workflows/phase4_live_shadow_validation_v6.yml` creates the Phase 4 readiness certificate.
- `.github/workflows/phase5_production_promotion_v2.yml` is the only workflow authorized to consume that certificate and transfer production authority.
- `deploy/runtime-v2/runtime_promotion_control.sh` implements the shared runtime, scheduler, IAM, database, web, and legacy-route controls.
- `deploy/runtime-v2/runtime_promotion_observed_state.sh` captures the exact observed legacy workflow state, persists the certified Runtime source revision on producer jobs, and restores the observed state during rollback.
- `deploy/runtime-v2/validate_runtime_promotion.py` validates both certificates from execution evidence rather than workflow success alone.

Both live workflows serialize through the `runtime-v2-live-controller` concurrency group. A failed, stale, non-canonical, or superseded Phase 4 run cannot trigger promotion.

## Entry gate

The production workflow may start only after the canonical `main` revision produces an independently checksummed `phase4_ready_for_phase5` certificate. That certificate must bind:

- two complete, serialized Legislative → Executive → AI → dashboard shadow cycles;
- eight unique successful Runtime v2 run receipts and eight unique Cloud Run execution names;
- the recovered append-only baseline and every one-generation parent transition;
- verified `shadow` mode, suppressed external effects, exact control and Runtime source revisions, and current AI/dashboard input hashes;
- paused Runtime v2 producer schedulers, a private Runtime v2 web service, private-only Cloud SQL, an active legacy collector route, and complete temporary-authority cleanup;
- the exact observed state of each retained legacy workflow.

The Legislative and Executive legacy collectors must be active at the entry gate. AI and dashboard workflow states are preserved exactly as observed rather than being assumed active.

## Authority transfer

The promotion controller performs the following sequence:

1. Verify the Phase 4 certificate checksum and bind its control revision, Runtime source revision, immutable image, final heads, execution evidence, and observed legacy workflow-state map.
2. Require canonical `main` to remain at the certified control revision.
3. Reconfirm the repository and project boundaries, private-only Cloud SQL, private Runtime v2 web service, paused Runtime v2 producer schedulers, paused Filing Vault lifecycle scheduler, exact Phase 4 heads, and unchanged observed legacy state.
4. Persist explicit `production` mode, the immutable image, database boundary, and certified `SOURCE_REVISION` on all Runtime v2 producer jobs while keeping their schedulers paused.
5. Disable the four retained legacy production workflows through the GitHub Actions workflow-state API, then drain and reject any overlapping legacy run.
6. Execute one serialized production smoke cycle in Legislative → Executive → AI → dashboard order with the dedicated `phase5_smoke` trigger source.
7. Validate four unique successful receipts, exact one-generation parent continuity, no overlapping protected writers, no unexpected namespace mutation, source-revision equality, and current AI/dashboard input hashes.
8. Remove all temporary execution, logging, and service-account impersonation authority.
9. Grant public invocation to the Runtime v2 web service and require `/healthz`, `/readyz`, and `/` to bind to the accepted dashboard snapshot.
10. Enable exactly the four Runtime v2 producer schedulers. The Filing Vault lifecycle scheduler remains outside this phase and must remain paused.
11. Emit and checksum a `phase5_complete` certificate, then independently verify the terminal production state.

## Automatic rollback

Any failure after the route is touched pauses the Runtime v2 producer schedulers, removes public web invocation, removes temporary authority, returns Runtime v2 to `shadow` mode, restores every retained legacy workflow to its exact pre-cutover observed state, and dispatches a Legislative and Executive recovery pulse. Rollback never deletes or rewinds Runtime v2 snapshots.

A failure before the route is touched performs safety cleanup but does not manufacture a recovery event or mutate the still-active legacy route.

The completion certificate records `rollback_restores_exact_observed_state: true` and includes the pre-cutover legacy workflow-state map.

## Completion evidence

Phase 5 is complete only when the live workflow succeeds and its checksum-verified certificate records:

- `result: phase5_complete`;
- `production_route: runtime_v2` and `production_authority_transferred: true`;
- four unique successful production-smoke receipts;
- all four Runtime v2 producer schedulers enabled;
- all four legacy automatic workflows disabled but retained;
- the public Runtime v2 URL and served dashboard snapshot hash;
- private-only Cloud SQL and the Filing Vault lifecycle scheduler still paused;
- complete removal of temporary control-plane authority;
- the exact control revision, Runtime source revision, and immutable image digest;
- `rollback_restores_exact_observed_state: true`;
- `phase6_started: false`.

The canonical live run IDs, certificate checksums, final heads, served dashboard digest, and closure record are appended only after the terminal production-state verification succeeds.

## Non-goals

Phase 5 does not delete legacy workflows, Pages history, artifacts, Cloud Run jobs, database snapshots, migration evidence, tags, or recovery material. Those decisions belong to a separately authorized Phase 6.
