# PolitiTrack project state

**Current as of:** 2026-09-09T12:52:47.404970+00:00 — personal reviews accepted; Legislative recovery pending.

**Canonical repository:** ID `1349678672`, `maglothinm/MyETF-Intelligence`; default branch `main`.

**Historical recovery control revision:** `db080d413b5e804a335f575071a62d48a9d4083b` (PR #151).

## September 9 durable personal acknowledgement release — issue #159

PR #160 is merged and accepted live. Runtime source `c0eaeb430aa7f665283f9ee560cf72fbe9c257cf`,
build `c84e6510-9825-4c84-b512-cf82d18ed627`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:5428e1333ceff18b7c2e1f7fd46f3e82652b6c2cb7b94d1fbee20b099fa19ec6` is on all six existing
resources. Web revision `polititrack-web-r159-persist-0909` serves the accepted dashboard.
See [the exact release evidence](releases/2026-09-09-personal-review-acknowledgements.md).

Each person's acknowledgement history is stored in the existing private
PostgreSQL database. Clearing browser data requires signing in again. The owner's
four original acknowledgements have been recovered with timestamps preserved;
the owner must choose their own password using the privately delivered setup link.
Two independent test accounts passed live cookie clearing, renewed sign-in,
Restore/import protections and a fresh web revision, then were disabled.

All original producer schedules are ENABLED and Filing Vault remains PAUSED.
Legislative generation 232 and its original failed-run/guard state are unchanged.
Executive and AI heads were unchanged through the fenced cutover; Dashboard
advanced 332 -> 333
with exact parent continuity. No protected state or personal history was deleted.
The separate Legislative repair may resume release ownership after receiving this
receipt. The September 8 records below are historical, not current image evidence.

## Production authority

**September 9 recovery in progress:** Official Senate access succeeds from the production network. The permanent repair separates collection from per-record delivery for Legislative, Executive and AI. Failed or ambiguous old attempts cannot latch later collection; individual uncertain alerts retain duplicate protection. The original Legislative failed row and generation 232 snapshot remain intact. [Recovery diagnosis and contract](incidents/2026-09-09-legislative-recovery.md). Deployment and a natural scheduled successor remain required; no live recovery is claimed here. Coordinate production ownership with issue #159 and preserve its merged source and data.

**September 8 accepted release:** Issue #155 is live after PR #156 and corrective PR #157. Runtime source `19e894ef1262a86d4e54e24a8a34f6b7f230f688`, Cloud Build `cea78696-8521-45d4-98b8-bdea9e45fc09`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300`. All six resources use that digest; producer configurations persist the corrected source. Dashboard `polititrack-dashboard-68f7j` committed generation 250 and passed real isolated-browser acceptance before schedules resumed. [Full release evidence](releases/2026-09-08-parser-acknowledgements.md).

The corrected inventory has four manual exceptions: two original Senate and two retained House paper PTRs. Seeding only the real Senate legacy IDs left Senate acknowledged and House active; acknowledge-all, three real refreshes, reload and Restore passed. The served bundle also passed 74 isolated publication-replay tests. The user's browser storage was not changed.

Legislative remains blocked at generation 232 after a pre-existing Senate HTTP 403 run at 10:41 UTC. Its guard and history remain intact; [incident evidence](incidents/2026-09-08-legislative-retry-guard.md). All four original producer schedules are enabled; Vault remains paused, SQL private-only, legacy producers disabled. PR #154 remains excluded. Historical certificates below are not certification of the new image or current all-pipeline health.

Runtime v2 is the production authority. The earlier shadow/blocked description in this file was stale. Phase 5 completed in canonical run `34005780266`, attempt 1, at `9f4303623cf21c3dff434fbb7240c07e6d255174`. Artifact `9981508660` has archive SHA-256 `c5094a1677712e413425e118f29dd0fc1f870c5bc712879fbc2223f2b9c2f7d0`. Its `phase5-complete.json` independently matches checksum `0006ed72a2a42308c21084bee236c45f4e9e17df4803c244caf03a520028dcb7` and result `phase5_complete`.

That certificate records the original production transfer. The subsequent concurrency repair and natural-schedule recovery have separate evidence; the original certificate is not a certificate for the repaired image.

## Runtime recovery

PR #142 repaired snapshot-reader/writer concurrency. The September 6 recovery used immutable image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`, with producer source revision `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`, verified as an ancestor of current main.

Scheduler reactivation run `34046362664` succeeded. All four producer schedulers are enabled. AI uses `14,44 * * * *` in America/New_York; Dashboard retains `2,17,32,47 * * * *` in Etc/UTC. Filing Vault lifecycle remains paused. Cloud SQL public IPv4 remains disabled and its private network remains `polititrack-runtime-v2`.

Natural-certification run `34047080001` failed in preflight because its Dashboard timezone assertion contradicted both Terraform and the live Scheduler. PR #151 corrects the assertion and selects logs from the recorded activation timestamp instead of a sliding four-hour window. It does not change production schedules or runtime code.

Corrected certification run `34059488724`, attempt 1, job `101557337973`, completed successfully at control revision `db080d413b5e804a335f575071a62d48a9d4083b`. Artifact `9997087643` independently matches archive SHA-256 `6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`. Its certificate reports `runtime_v2_natural_ai_schedule_certified`, cleanup pending false, and temporary execution/logging authority removed. Both internal evidence hashes were independently verified.

## Live functionality

**Historical September 6 verification:** Independent GCP reads showed successful Legislative, Executive, AI, and Dashboard executions. AI natural runs committed generations 63 and 64 at 17:17 and 17:48 UTC. Public `/readyz` returned ready and `/` returned HTTP 200 with the same snapshot hash at 20:56 UTC. The certified durable heads are Legislative 82, Executive 46, AI 70, and Dashboard 79, all bound to repaired source revision `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`. The served hash matches the certified Dashboard 79 head. AI executions `polititrack-ai-rss97` and `polititrack-ai-db5vt`, followed by `polititrack-dashboard-vl4p6`, were independently checked in GCP: all succeeded, used the approved digest, and were created by the existing Scheduler service account.

## Preserved boundaries

No replatform, state initialization, rewind, rebaseline, protected artifact replacement, legacy route activation, or Phase 6 decommissioning is authorized. The original Phase 5 evidence and all recovery predecessors remain retained. Runtime database/snapshot authority must not be confused with the pre-cutover GitHub artifact authority described in historical documents.
