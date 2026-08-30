# PolitiTrack recovery overlay retirement report

Original recovery date: 2026-08-25

Overlay retirement date: 2026-08-29

## Result

The standalone `apply.sh` / `repo-files/` recovery overlay is retired. `apply.sh`
always stops without changing its target, and `repo-files/` contains only a retirement
notice. The overlay is no longer an alternative source tree.

This was required because the overlay contained an earlier two-collector snapshot. It
could overwrite newer runtime code and recreate the retired Legislative workflow beside
Legislative v2, producing two schedulers and two writers for the same state key.

## Canonical operational source

The checked-in repository root is the only operational source. Its active workflow set
is:

- `legislative_trade_tracker_v2.yml` — sole Legislative production writer
- `executive_trade_tracker.yml` — sole Executive production writer
- `ai_filing_analyst.yml` — sole AI analysis-state writer
- `publish_trade_dashboard.yml` — GitHub Pages publisher
- `investor_edge_tests.yml` — Investor Edge integration tests
- `manual_test.yml` — isolated Run Simulation
- `filing_simulation.yml` — isolated $10K portfolio simulator

The retired Legislative workflow and the one-time migration-import workflow must remain
absent. Production tracker dispatches do not expose initialization or bootstrap inputs;
they restore protected state and fail closed when it is unavailable.

## State continuity

This retirement changes source files only. It does not delete, reset, rewrite, or
initialize production data. The stable production artifact names remain:

- `legislative-tracker-state`
- `executive-tracker-state`
- `ai-analysis-state`

The corresponding `.trade-tracker/` paths and JSON/JSONL schemas remain compatible.
GitHub Actions artifacts are the sole production-state authority; the workflows do not
restore or save tracker/AI state through Actions caches.

Every state consumer validates the producer repository, workflow name and path, default
branch, successful workflow conclusion and authoritative job, artifact creation time
within the producing attempt, and producer-commit ancestry. The persistent simulator
paginates the complete matching-artifact set and applies a deterministic global
newest-first order before provenance filtering. A high-water check rejects an older
artifact whenever a later successful writer attempt exists but lacks an eligible
artifact. These guards prevent a missing or rerun artifact from silently rolling state
backward.

Simulator data is isolated under `simulation-*` artifact names and cannot be promoted
to a production state artifact. `manual_test.yml` creates a short-lived Investor Edge
acceptance dashboard, while `filing_simulation.yml` owns the persistent paper-only $10K
history. The dashboard publisher accepts `simulation-state` only from an exact,
successful $10K simulator attempt, validates its result/history and safety attestations,
and publishes it as the separate `data/simulation.json` dataset.

## Recovery rule

If a protected state artifact is missing, stop and restore the verified predecessor.
Do not create a replacement baseline and do not copy files from an older recovery ZIP.
Repository identity, current state, decisions, and handoff procedures are defined in
`AGENTS.md` and `docs/`.

## Verification

Run `bash verify.sh`. It checks that:

- the retired installer exits without mutating a target;
- `repo-files/` has no installable payload;
- the retired writer and migration importer are absent;
- the seven canonical workflows parse and have the expected names;
- protected state uses successful, provenance-validated artifacts rather than Actions
  caches;
- attempt-window and high-water checks prevent ambiguous or stale artifact restores;
- both isolated simulations remain in their own namespace;
- the dashboard publisher validates and consumes optional `simulation-state`; and
- `MANIFEST.sha256` matches the retained recovery records.
