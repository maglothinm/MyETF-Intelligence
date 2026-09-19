# Investor Edge backfill progress — live release accepted

Accepted **2026-09-14T15:05:00.702173+00:00** in canonical repository **1349678672**, `maglothinm/MyETF-Intelligence`.
Owner explicitly authorized deployment. PR #173 supplies the feature; corrective PR #176 resolves the production-interpreter mismatch, and PR #177 corrects the expanded root list scroll containment. Issue #172 is accepted by this record, not by the earlier source merge.

## Production identity

Source `0483e8c1f66a9328ec6f46d1ba003594c9aa75fc`. Cloud Build `b27a9df0-8c09-42df-a39b-01b1d0f985b8` succeeded, including compilation with the deployed Python 3.11 interpreter.
Image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:14a8ec467ad9893048086349b8675de8967878c5610cad0071f1a6b1d6d24404` is verified on all six existing resources. Web revision `polititrack-web-00043-29c` serves 100% traffic.
[Live Investor Edge](https://polititrack-web-s6icmprjvq-uc.a.run.app/#investor-edge).
[Machine-readable acceptance receipt](2026-09-14-investor-edge-backfill-progress-receipt.json).

## Verified live behavior

Root and standalone Investor Edge passed actual Chromium checks at 1280, 700 and 390 pixels, including pending-reason filters, contained scrolling and no browser errors. Both served JavaScript bundles contain the exact shared component from the accepted source. Readiness, full Investor Edge JSON, full Signals JSON and dashboard-insights JSON returned HTTP 200 and parsed successfully. The served snapshot matched the accepted Dashboard head.

The final presentation acceptance publication reports **unknown** across **1305** distinct eligible observations:

| State | Observations |
|---|---:|
| awaiting maturity | 0 |
| awaiting retry | 1148 |
| blocked | 0 |
| completed | 0 |
| missing data | 77 |
| queued | 0 |
| ready | 0 |
| unknown | 80 |

ETA availability: `no_currently_computable_work`. A numerical ETA is not fabricated from the configured maximum; it requires sufficient comparable measured progress. The journal begins with genuine successful maintenance and future sessions remain separate from computable work. This release does not claim all historical filing coverage is complete.

## Controlled production acceptance

The following complete producer chain was accepted at engine source `4717b770b943c6afa36eab1182fe7d2b8285f563`. Final presentation source adds only CSS and its browser regression; it does not alter engine behavior.

| Execution | Exact Cloud Run execution | Result |
|---|---|---|
| legislative | `polititrack-legislative-95kdc` | Succeeded |
| executive | `polititrack-executive-mv8wx` | Succeeded |
| ai | `polititrack-ai-6wsjc` | Succeeded |
| dashboard | `polititrack-dashboard-8ndjg` | Succeeded |
| acceptance | `polititrack-admin-fh4mk` | Succeeded |

| Namespace | Accepted generation | Snapshot SHA-256 |
|---|---:|---|
| ai | 439 | `75b7b3238980411fae8ab7a7231078904e7e4505341f1996bc273ebcc61b636a` |
| dashboard | 814 | `87e2da66b5649fd222c4288272743663cf9edde810360c28fe7379089356ac70` |
| executive | 391 | `e6fafed969006bac8a4509651b41edf7407bb42fa13df242c3e0da597305f383` |
| legislative | 714 | `85deb157763c7fa1b95113965b2672d3d7c66b18b7859569ce6e336040efb6f0` |

All descendant generations and parent hashes were verified from the original release baseline: AI 437, Dashboard 810, Executive 388 and Legislative 708. Every pre-release snapshot metadata hash is unchanged; all latest head payloads/manifests passed the production archive verifier. All 1,501 prior observation keys and 62 prior profile keys remain present. Method hash remains `c124c63e05a9ed3fc4d8`.

The three personal accounts, eight acknowledgement rows, full account-row hashes, prior notification history and original incident evidence match the baseline. No state reset, snapshot rewind, schema migration, IAM expansion, new writer or scoring/budget change occurred.

## Failure found during deployment and corrected

Initial image `sha256:5b5b1f05ac06031d6b8c0309781ad3c7afb1bda556f758c220e016ac93cea51a` failed AI execution `polititrack-ai-t79hh` at module import: a backslash inside an f-string expression is invalid in Python 3.11. Previous CI used Python 3.12. The failed runtime record `ea97fdcf-6cbe-46d8-a73d-beffaccc568c` remains intact with no snapshot and side-effects flag false; independent audit confirmed AI stayed at generation 437.

PR #176 preserves identical inert-JSON escaping outside the f-string, moves Investor Edge CI to production Python 3.11, and adds actual-image entry-point compilation. Exact-head CI `34852747585` (Investor Edge/Python 3.11) and `34852747430` (Runtime safety) succeeded. Earlier full isolated acceptance remains 1,296 passed / 2 skipped; its 3.12 success alone was not sufficient production compatibility evidence. The corrected image and live successes above supersede the failed candidate without deleting its history.

## Final presentation correction and verification

Visual review of the real-data root pending list exposed a CSS specificity conflict: the main shell removed the intended maximum height. PR #177 adds a root-scoped selector without changing other record tables. Final-head CI `34856903296` passed on Python 3.11, including Chromium assertions of the existing standalone 75vh bound and root 24rem bound.

This CSS/test-only successor was explicitly checked against engine source `4717b770b943c6afa36eab1182fe7d2b8285f563`. The final immutable image is uniform across the six resources; its Dashboard execution `polititrack-dashboard-9cmhb` and read-only audit `polititrack-admin-kwzgx` succeeded. All six real-data browser views passed finite maximum-height and actual table-height checks as well as filtering and horizontal containment. The latest Dashboard snapshot matches the served responses; earlier producer snapshots remain valid predecessors because their engine source is unchanged. Every descendant parent link and original preservation hash was rechecked.

The post-merge main check `34857488327` also succeeded. Natural AI execution `polititrack-ai-2chrw`, created by the existing Scheduler service account, completed successfully at `2026-09-14T14:55:16.839643Z` using the accepted unchanged engine source. This independently verifies scheduled engine operation after the controlled release.

## Restored operation and boundaries

All four original producer schedules are ENABLED with their exact prior configuration. Filing Vault remains PAUSED. Cloud SQL stays private-only with backups and point-in-time recovery enabled. Existing Gmail, Operations controls and Current Opportunity enablement were not changed. Gmail delivery is a separate outstanding configuration matter; this release does not claim an email was delivered.

Private execution, configuration, archive verification, JSON and screenshot evidence is retained on Beast at `C:/Users/maglo/Documents/Codex/2026-09-14/polititrack-backfill-release-172/evidence`. Only this summary and receipt are published; account rows, source payloads and credentials are not exported to the repository.
