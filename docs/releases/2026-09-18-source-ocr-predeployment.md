# Source OCR release checkpoint — September 18, 2026

**Status: merged and built; not deployed or enabled.**

Canonical repository: ID `1349678672`, `maglothinm/MyETF-Intelligence`.
PR #183 merged with expected head `3e11f9491bfa29d0935059202926ed2ec57ec987`.
Merge/source revision: `9402f6c9866e919c789845de96f4334058600cee`.
A fresh isolated checkout verified the merge tree is identical to that tested PR head.

## Verified source and build evidence

- Exact PR-head CI: OCR `35273397222`, Runtime v2 safety `35273397245`, Investor Edge `35273397187`; all successful.
- Post-merge main CI: OCR `35339190135`, Investor Edge `35339190177`; both successful. The Runtime safety workflow's previously verified PR-head result is not relabeled a main-push run.
- Cloud Build `d4a7f1e6-3437-4235-8e3b-13e4125f6a72` completed successfully, including pinned-source checkout, build and push.
- Built immutable image: `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`.
- Building the image does not deploy it or enable source uploads/OCR.

## Read-only production preflight

Beast is connected and authenticated GCP inspection succeeded. Existing six release-resource specifications were saved locally, without printing secrets. The live image split matches the September 15 release: Dashboard has the Inbox-delay image; the other five release resources retain the accepted September 14 image. All four producer schedules were ENABLED; Vault remained PAUSED. Cloud SQL public IPv4 is disabled, private networking is configured, and backups and point-in-time recovery are enabled.

Read-only admin execution `polititrack-admin-tbdj4` completed successfully at `2026-09-18T11:24:25.808041Z`. Its repeatable-read audit verified current snapshot payload hashes/manifests and retained metadata through these observed heads:

| Namespace | Generation | Snapshot ID |
|---|---:|---|
| Legislative | 1078 | `16e89c58-d243-4b02-811f-76233e1d8919` |
| Executive | 572 | `11cc1af9-4b22-4bff-abc4-5c5a3e726d70` |
| AI | 624 | `24970173-457d-4d6d-aebc-50b130375135` |
| Dashboard | 1182 | `0ef76aec-115c-47b7-a226-c91568eaf167` |

The audit also recorded three personal accounts and nine acknowledgements. These are observed preflight values, not frozen cutover heads; normal schedules continue advancing production. No state reset, account modification or original-history deletion was performed.

## Execution boundary and next step

A tool safety check blocked writing the temporary schedule-pause/cutover helper before execution, reporting that it could not determine the request's safety status. This was not a GCP permission or credential error. No schedule-pause command, database migration, live-image update or feature activation was executed. The blocked helper was not retried through another tool or access path.

Obtain the owner's explicit confirmation for the bounded maintenance window: pause only the four existing producer schedules, allow active runs to finish, capture a fresh frozen preservation baseline, add only the OCR inbox table, roll out the pinned tested image to existing resources, enable the authorized account and OCR flags, verify controlled upload/backfill/health/cleanup behavior, and restore the exact original schedules. Do not assume that confirmation guarantees the platform will allow a previously blocked tool request; report any continuing restriction. Do not request the original feature requirements again.

The original sample's three unclear asset labels still require document-specific review; no live import or corrected-label approval has occurred. OCR-specific health is in the merged image but has not been observed in production.

Private execution receipts and the fresh checkout are under `C:/Users/maglo/Documents/Codex/2026-09-18/polititrack-ocr-release-182`. Reuse neither historical baseline values nor old release scripts blindly. The existing production release, notification setup, Vault pause, and unrelated feature flags remain unchanged.
