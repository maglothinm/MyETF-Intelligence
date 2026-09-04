# Phase 5 Runtime v2 production promotion

Phase 5 transfers PolitiTrack's automatic production authority from the retained GitHub Actions collectors and Pages publisher to Runtime v2. It is a gated cutover, not a decommissioning phase.

## Entry gate

The production workflow may start only after the canonical `main` revision produces an independently checksummed `phase4_ready_for_phase5` certificate. That certificate must bind:

- two complete, serialized Legislative → Executive → AI → dashboard shadow cycles;
- eight unique successful Runtime v2 run receipts and eight unique Cloud Run execution names;
- the recovered append-only baseline and every one-generation parent transition;
- verified `shadow` mode, suppressed external effects, exact source revision, and current AI/dashboard input hashes;
- paused Runtime v2 producer schedulers, a private Runtime v2 web service, private-only Cloud SQL, an active legacy production route, and complete temporary-authority cleanup.

A failed, stale, non-canonical, or superseded Phase 4 run cannot trigger promotion.

## Authority transfer

The promotion controller serializes all live work under `runtime-v2-live-controller` and performs the following sequence:

1. Reconfirm the certified Runtime v2 heads, immutable image, canonical repository, canonical `main`, project number, private Cloud SQL, private web service, paused Runtime v2 schedulers, and paused Filing Vault lifecycle scheduler.
2. Disable the four legacy production workflows through the GitHub Actions workflow-state API while retaining their files, artifacts, schedules, and rollback history.
3. Drain any legacy run that was already queued or executing and reject the cutover if any legacy run remains active.
4. Set all four Runtime v2 producer jobs to explicit `production` mode while keeping their schedulers paused.
5. Execute one serialized production smoke cycle in Legislative → Executive → AI → dashboard order, using the dedicated `phase5_smoke` trigger source.
6. Validate four unique successful receipts, exact one-generation parent continuity, no overlapping protected writers, no unexpected namespace mutation, source-revision equality, and current AI/dashboard input hashes.
7. Remove all temporary execution, logging, and service-account impersonation authority.
8. Grant public invocation to the Runtime v2 web service and require `/healthz`, `/readyz`, and `/` to bind to the accepted dashboard snapshot.
9. Enable exactly the four Runtime v2 producer schedulers. The Filing Vault lifecycle scheduler remains outside this phase and must remain paused.
10. Emit and checksum a `phase5_complete` certificate.

## Automatic rollback

Any failure after the route is touched pauses the Runtime v2 producer schedulers, removes public web invocation, removes temporary authority, returns Runtime v2 to `shadow` mode, re-enables the four legacy workflows, and dispatches a Legislative and Executive recovery pulse. Rollback never deletes or rewinds Runtime v2 snapshots.

A failure before the route is touched performs safety cleanup but does not manufacture a recovery event or mutate the still-active legacy route.

## Completion evidence

Phase 5 is complete only when the live workflow succeeds and its checksum-verified certificate records:

- `production_route: runtime_v2` and `production_authority_transferred: true`;
- four unique successful production-smoke receipts;
- all four Runtime v2 producer schedulers enabled;
- all four legacy automatic workflows disabled but retained;
- the public Runtime v2 URL and served dashboard snapshot hash;
- private-only Cloud SQL and unchanged Filing Vault scheduler state;
- complete removal of temporary control-plane authority;
- `phase6_started: false`.

## Non-goals

Phase 5 does not delete legacy workflows, Pages history, artifacts, Cloud Run jobs, database snapshots, migration evidence, tags, or recovery material. Those decisions belong to a separately authorized Phase 6.
