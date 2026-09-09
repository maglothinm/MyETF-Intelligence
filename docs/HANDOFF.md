# PolitiTrack active handoff

Updated **2026-09-09 — Legislative recovery implementation**. Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Active owner request — Legislative recovery

The owner requests restoring Legislative collection. Official Senate access now succeeds from the production network. Immutable execution/image evidence shows the September 8 failed collector could not send Pushover notifications because both credentials were absent. Implemented an explicit, code-pinned case that checks generation 232 and the entire unchanged failed-run inventory under the writer lock, retains the original failure, and records adjudication in the new run and successor snapshot. Future credential-free tracker failures no longer falsely assert alert capability. Complete-source validation remains required.

Regression, immutable-state export and exact-image evidence checks precede Runtime CI and deployment. Production recovery is not yet accepted at this checkpoint. Next: build the merged tested source, fence/drain the four existing schedules, run one controlled complete-source Legislative successor, publish through the existing Dashboard writer, verify parent continuity and live producer status, then restore original schedules. Coordinate shared production ownership with the separate issue #159 personal acknowledgement task. [Incident and recovery details](incidents/2026-09-09-legislative-recovery.md).

## Previously completed owner request

Issue #155 is merged and live through PR #156 plus corrective PR #157. Runtime source `19e894ef1262a86d4e54e24a8a34f6b7f230f688`, build `cea78696-8521-45d4-98b8-bdea9e45fc09`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300` on all six resources. The final documentation commit is separate from runtime source. PR #154 remains unmerged and excluded.

See [the accepted release report](releases/2026-09-08-parser-acknowledgements.md) for exact CI, execution, asset and snapshot evidence. Canonical tests: 1,159 passed, 2 local PostgreSQL skips; Runtime CI passed. Live acceptance seeded only the two actual Senate legacy IDs and verified two Senate acknowledged / two House active. In the same isolated context, acknowledging all four, three refresh requests, reload and Restore passed. The user's storage was never modified. Missing/returning publication cycles passed 74 tests with served assets in isolated replay; they are not future-production-cycle claims.

## Current production boundary

The final fenced Dashboard run advanced one generation with exact parent continuity. Legislative, Executive and AI heads remained unchanged during this publication-only correction. Earlier Executive/AI controlled smokes passed on PR #156; those executable paths did not change in PR #157. Four schedules are enabled at original settings, Vault paused, SQL private-only and legacy producers disabled.

Live acceptance initially exposed a classification-order defect, which was reproduced, fixed and re-released. The rejected snapshot was retained; a valid old-image publication was appended before the corrected release. No state rewind, initialization, rebaseline, history deletion, guard bypass, IAM grant or alternate writer occurred.

## Remaining incident and next safe action

Legislative generation 232 remains accepted and its old-image failed run `065d5330-abca-4eda-b683-64e85f2dcbe7` remains retry-blocked after Senate HTTP 403 at 10:41 UTC. Do not report all pipelines healthy. [Incident record](incidents/2026-09-08-legislative-retry-guard.md), [issue #8](https://github.com/maglothinm/MyETF-Intelligence/issues/8). Next: audited source-access and side-effect-evidence recovery, preserving the failed run and accepted state, before one controlled complete-source retry. The current CLI has no reviewed production adjudication command; do not clear a flag or replace a baseline.

Historical certificate artifact 9997087643 (run 34059488724, attempt 1; SHA-256 `6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`) is retained. It is not a new certificate for this release. Runtime v2 PostgreSQL snapshots remain production authority.
