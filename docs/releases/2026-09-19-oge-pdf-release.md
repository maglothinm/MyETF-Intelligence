# Reviewed release of the OGE eligibility/PDF policy repair (#182)

Application source is the tested PR #188 merge `db4aa4da54be845a1e139dc354d9f59aa9006d8a`; [application verification](2026-09-19-oge-pdf-repair.md) records exact-head canonical CI and real OCR evidence. This procedure is prepared, not yet deployed.

Beast and the existing authenticated Cloud Shell connection are restored. The saved SSH host key matches the current server; the original controller and predecessor wrapper checksums still match. A fresh live read confirms all six resources use the accepted September 18 image, four original producer schedules are enabled, and Vault is paused.

`scripts/ocr_oge_pdf_repair_release.py` requires the unchanged checksum-pinned v2.2 engine and prior health-release wrapper. It verifies all three predecessor journals, including completed journal SHA-256 `f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d`, its acceptance/schedule evidence and every earlier sealed receipt. Old files remain immutable. This is a new specific release, not a replay of any prior attempt.

Read-only preparation compares all current resource specifications with the accepted completed release, original scheduler specifications/states, the exact-source successful build and registry digest, and private database/backup/PITR settings. One new workspace `ocr-oge-pdf-repair-db4aa4da54be` stores current preparation receipts. The copied old acceptance is explicitly predecessor evidence, never a new frozen baseline.

The existing engine holds both workspace locks and performs fresh preflight, original-schedule pause/drain, a new frozen independent baseline, image/schema smoke checks, bounded runs through existing producers, full identity/history/personal-review/notification preservation, published OCR-health and live asset acceptance, and original schedule restoration. Recovery remains journaled and fails closed on unknown submissions or changed configurations. No accounts, IAM, credentials, schedules, source IDs or alert history are replaced. Known OGE layout and owner-row interpretation reviews remain open.

Local safety verification: **81 passed**, covering all previous engine/wrapper checks plus three-attempt sealing, completed predecessor/acceptance requirements, wrong-source/incomplete builds, changed live specifications, fresh empty successor state, tampering and closed-attempt refusal. Canonical controller CI, immutable build and actual deployment results will be recorded separately.
