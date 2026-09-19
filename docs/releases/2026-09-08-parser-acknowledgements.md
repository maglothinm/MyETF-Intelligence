# PolitiTrack issue #155 — accepted production release

Recorded 2026-09-08T16:03:23.170520+00:00. Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, branch **main**.

**The acknowledgement fix is merged and live.** [Open the dashboard](https://polititrack-web-s6icmprjvq-uc.a.run.app). A separate, pre-existing Legislative collection blocker remains; this report does not certify all pipelines healthy.

[PR #156](https://github.com/maglothinm/MyETF-Intelligence/pull/156) delivered persistence and stable exception identity. [Corrective PR #157](https://github.com/maglothinm/MyETF-Intelligence/pull/157) fixed classification order discovered during live acceptance. Final runtime source: `19e894ef1262a86d4e54e24a8a34f6b7f230f688`. Corrective implementation head: `44969e74a04b413c693d2048053cb824f5ce0a52`. PR #154 remains unmerged and excluded.

## Actual legacy acknowledgement acceptance

The corrected inventory contains **four manual exceptions**: the user's two known Senate records plus two retained House paper/scanned PTRs previously categorized as `other`. They are newly recognized manual inventory, not duplicate or reactivated Senate evidence.

A fresh isolated Edge context was seeded with **only these two real legacy v1 IDs**:

- `review:26d3a33b8b6c3b4b0018eabd672efcda`
- `review:69bba9ad5c91225a4ba4ed56fd7e30d4`

Against the corrected live publication, both Senate records remained acknowledged and both House records stayed active: **2 acknowledged / 2 active**. The UI exposed Restore for the Senate rows and Acknowledge for the House rows. Legacy timestamps were preserved while stable identities were learned.

In that same context, acknowledging the remaining House records produced **4 acknowledged / 0 active**. This persisted through **three actual refresh requests and a reload**. Restore on all four returned **4 active / 0 stored acknowledgements**. The user's browser profile/storage was never used or modified. All observed browser network requests were GET/HEAD, with no page errors.

Live publication snapshot: `3b607037a0d2f7f79ef2cecec026cdab2c0b5eb99d4b624c6373c35e37781c39`. JSON, CSV, and insights counts/IDs/logical identity maps agree at **4 manual exceptions and 1,501 access requests**. Served `app.js` SHA-256 `c102ebdfa382e89548a66386f4978fd82733378d92f475ee10b141ffca6757b2` exactly matches the merged source's generated bundle (notifications + common + app). `/readyz` returned ready. Refresh snapshots in the legacy-seeded context: `["3b607037a0d2f7f79ef2cecec026cdab2c0b5eb99d4b624c6373c35e37781c39", "3b607037a0d2f7f79ef2cecec026cdab2c0b5eb99d4b624c6373c35e37781c39", "3b607037a0d2f7f79ef2cecec026cdab2c0b5eb99d4b624c6373c35e37781c39"]`. Repeated requests do not by themselves prove a future scheduled publication.

## Immutable build and runtime verification

- Cloud Build `cea78696-8521-45d4-98b8-bdea9e45fc09`: **SUCCESS**, exact-source checkout of `19e894ef1262a86d4e54e24a8a34f6b7f230f688`.
- All six Runtime v2 resources use `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300`.
- All four producer job configurations persist that source revision for future runs. Existing accepted snapshot provenance remains unchanged until each producer next commits.
- Web revision `polititrack-web-00035-v7h` is ready with **100% traffic**.
- Corrected Dashboard execution `polititrack-dashboard-68f7j` succeeded in production mode through the existing writer lock, validation/archive, and atomic commit path.
- The final correction changes only dashboard classification. Executive `polititrack-executive-2px6g` and AI `polititrack-ai-rf46c` previously passed controlled production smokes on PR #156 source `140944de3d0da9b76e6318714babad75212dab32`; their executable collector/analyst code is unchanged by PR #157. They were not rerun manually on the corrected image.

The final fence preserved Legislative, Executive and AI heads exactly. Dashboard advanced one generation with its preceding hash as parent:

| Namespace | Before generation | After generation | After SHA-256 |
| --- | --- | --- | --- |
| legislative | 232 | 232 | `7fda615a19c31165fefa91b2501ffab8f2c677325aeffdc35b7ff444c2d609df` |
| executive | 129 | 129 | `6a7cd3d645ebe5213da8e8e56f0d3e0414dbdb403c945b82e09896904ef6d78b` |
| ai | 155 | 155 | `eb3df546224539d2c0751f1ff9e65dcbb74b1db6837640e64f6b51adb31738fe` |
| dashboard | 249 | 250 | `3b607037a0d2f7f79ef2cecec026cdab2c0b5eb99d4b624c6373c35e37781c39` |

Live acceptance and the 74-test served-bundle replay passed **before** schedules resumed. All four original producer schedules are enabled with unchanged cron, timezones, targets and retry configuration. Filing Vault lifecycle remains paused. Cloud SQL has public IPv4 disabled and remains on its private network. Legacy producer workflows remain disabled. No IAM grant, alternate writer, state initialization/import, rebaseline, guard edit or evidence deletion was used.

## Regression and CI evidence

Canonical Python suite: **1,159 passed, 2 local skips** (optional PostgreSQL integration, supplied and passed in Runtime CI). `verify.sh`, compilation and diff checks passed. Three regression failures reproduced the category defect before the correction. Local replay of the captured 1,505-row restored publication proved consistent JSON/CSV/insights, preserved review IDs and stable repeated enrichment.

The exact served JavaScript bundle passed **74 DOM tests, zero failures**, using deterministic local fixtures. Coverage includes absent/zero publication, reload and returning exceptions, repeated 2 → 0 → 1 → 2 cycles, changed reason/evidence IDs, new logical exceptions, legacy migration, Restore across aliases, cross-tab updates and the 500-record retention boundary. These missing-publication cycles are **isolated replay**, not edited or fabricated live publications.

| CI | Attempt | Conclusion | Source head |
| --- | --- | --- | --- |
| [Run 34240149284](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34240149284) | 1 | success | `f94fb1677486` |
| [Run 34240149292](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34240149292) | 1 | success | `f94fb1677486` |
| [Run 34241120681](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34241120681) | 1 | success | `140944de3d0d` |
| [Run 34245743277](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34245743277) | 1 | success | `44969e74a04b` |
| [Run 34245743334](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34245743334) | 1 | success | `44969e74a04b` |
| [Run 34246070619](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34246070619) | 1 | success | `19e894ef1262` |

The initial implementation suite had 1,157 passes. Two additional hotfix regression cases raise the final count to 1,159. One preliminary local rerun lacked `jq` on PATH; the complete suite passed after restoring the existing tool path. Unrestricted root pytest's historical `backend/tests` import/external-database issues remain unchanged; canonical tests are under `tests/`.

## Retained release history and remaining incident

The first strict rollout stopped at the pre-existing Legislative retry guard and restored the old image. A subsequent Dashboard publication revealed the House category mismatch. That rejected snapshot, `e1f43a632e28ba6ff4005cb079e4b713153ec12fff1071d5090e1722d992eca5`, remains retained. Existing Dashboard execution `polititrack-dashboard-jktkd` appended valid retained-image publication `8286a37ad8db2657fe11244098e708c3b4196f462296b7b5e21e721488974f5b` and original schedules resumed at 15:33 UTC. No head or history was rewound or deleted. PR #157 was then tested, merged, rebuilt and accepted as described above.

Legislative run `065d5330-abca-4eda-b683-64e85f2dcbe7`, execution `polititrack-legislative-gnkrk`, failed on the old image at `2026-09-08T10:41:24.714055Z` after three Senate landing HTTP 403 responses and complete-source validation failure. Its `side_effects_possible=true` retry guard and accepted generation 232 remain intact. House logged zero newly processed records, purchases and pending reviews, but these counts are not an adjudication of external delivery. See [issue #8](https://github.com/maglothinm/MyETF-Intelligence/issues/8) and `docs/incidents/2026-09-08-legislative-retry-guard.md`. Next safe action: audited source-access and side-effect-evidence recovery before one controlled complete-source Legislative retry.

Historical recovery artifact `9997087643`, run `34059488724` attempt 1, remained unexpired with SHA-256 `6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`. It certifies the prior recovery, not this feature image. No protected artifact was replaced and no new Phase 5 certificate is claimed. The retained rollback image is `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`. Restoring an image alone does not replace a served dashboard snapshot; use the existing Dashboard writer to append any required rollback publication.
