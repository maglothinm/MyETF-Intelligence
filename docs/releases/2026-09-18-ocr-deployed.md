# OCR deployed with warnings — September 18, 2026

Issue #182 remains open. Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, default branch `main`.

The corrected rollout finished at **2026-09-18T20:56:33.832832Z**, with result **DEPLOYED_WITH_OCR_WARNINGS**. Process `36964` exited 0. All six existing runtime resources use source `a2a15edb30895ece37b690e50e0f95fb1eaa2649` and image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`. Cloud Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded. OCR is enabled on Legislative, Executive and web with the retained owner allowlist.

The additive inbox migration, image/schema/account check, both controlled source cycles, AI and Dashboard publication succeeded. Independent acceptance `polititrack-admin-d4wp2` returned PASS at `2026-09-18T20:55:33.540395Z`: baseline preservation, source/AI history, published OCR-health values and live asset hashes agree. An unauthenticated OCR API request returned `401 SIGN_IN_REQUIRED`. Three accounts and nine acknowledgement records were preserved, as were previous snapshot metadata, append-only ledgers, durable observation identities and notification history. No rebaseline, rewind, account reset or history deletion occurred.

## Corrected defect and verification

The first rollout failed acceptance because the generic dashboard privacy projection removed the safe OCR heartbeat. [PR #186](https://github.com/maglothinm/MyETF-Intelligence/pull/186) passes only the exact OCR telemetry envelope through its bounded `safe_metrics` validator before the generic privacy filter. Invalid telemetry and unrelated private heartbeat/configuration fields remain filtered. The actual generated dashboard is covered by five added regression cases. Local checks: **207 passed, 1 PostgreSQL-dependent skip**. The merge tree equals the tested PR-head tree.

- Exact-head [OCR CI 35389493194](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35389493194): success, including canonical database coverage.
- Exact-head [Investor Edge CI 35389493190](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35389493190): success.
- [Repair procedure PR #187](https://github.com/maglothinm/MyETF-Intelligence/pull/187), merge `db7cd0fd2bb24223a744d219ea04009747a317d7`: 59 local safety checks passed; [controller CI 35390534977](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35390534977) succeeded.

The actual Cloud Shell controller `/home/maglothinm/ocrv2.py` is the reviewed v2.2 engine, SHA-256 `bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`. The installed explicit repair wrapper `/home/maglothinm/ocr_health_repair_release.py` is SHA-256 `c095e90551a1d96b853a08450af34f9abfedde80ef5504432306c7b8abf90319`. Its release summary identifies v2.3 verified health-publication repair. The unchanged original audit is checksum-pinned.

## Executions and preserved state

| Step | Successful execution |
|---|---|
| Frozen baseline | `polititrack-admin-vf2k7` |
| Additive migration | `polititrack-admin-4tl6k` |
| Image/schema/account smoke | `polititrack-admin-nvpbz` |
| Legislative 1 | `polititrack-legislative-9zzg9` |
| Executive 1 | `polititrack-executive-dmp2c` |
| Legislative 2 | `polititrack-legislative-f6tb4` |
| Executive 2 | `polititrack-executive-hktw5` |
| AI | `polititrack-ai-vfckf` |
| Dashboard | `polititrack-dashboard-j6pc8` |
| Independent acceptance | `polititrack-admin-d4wp2` |

| Namespace | Accepted generation | Snapshot |
|---|---:|---|
| Legislative | 1110 | `75399e5f-5523-48f6-a0f6-0fcd5e48aa1b` |
| Executive | 590 | `9f1abe4d-f29c-4617-a717-7ab378d7f601` |
| AI | 639 | `cf03ef63-4a90-4831-8e13-fa529254a106` |
| Dashboard | 1211 | `59924523-827c-4694-970b-ff0a4186d6d7` |

These are acceptance-time heads; restored scheduled writers advance them naturally. Runtime v2 database/snapshots remain production authority. Older GitHub artifacts are historical evidence.

The original no-submission journal is unchanged at SHA-256 `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`. The first deployed-image attempt remains closed as `recovered_new_image_ocr_disabled`, unchanged at `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`. Its failed acceptance and interrupted first recovery remain retained history.

The corrected journal at `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-health-repair-a2a15edb3089/ocr-deployment/journal.json` is complete, SHA-256 `f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d`. Adjacent baseline, acceptance and summary receipts remain intact. No controller is active; do not replay this release or reopen an old journal.

## Schedules and natural execution

At restoration all original schedule fields were verified, including target, retry configuration and deadline:

| Existing schedule | State | Original cadence | Time zone |
|---|---|---|---|
| Legislative | ENABLED | `5,20,35,50 * * * *` | Etc/UTC |
| Executive | ENABLED | `11,41 * * * *` | Etc/UTC |
| AI | ENABLED | `14,44 * * * *` | America/New_York |
| Dashboard | ENABLED | `2,17,32,47 * * * *` | Etc/UTC |
| Filing Vault | PAUSED | `17 3 * * *` | Etc/UTC |

Natural Legislative execution `polititrack-legislative-f5f7m` was created at `2026-09-18T21:05:00.804967Z` by `polititrack-scheduler-v2@project-38008d5f-4918-46e6-920.iam.gserviceaccount.com`. In project number `497412818801`, it used the exact corrected image, returned Completed=True and succeededCount=1, and finished at `2026-09-18T21:08:48.313546Z`. It was not manually dispatched. This independently verifies scheduling after this corrected restoration. The earlier recovery's `polititrack-legislative-sb4pf` is separate historical evidence.

## OCR outcomes and remaining acceptance

At acceptance Legislative showed **Failure / Degraded**, with two deferred Senate paper-viewer cases, 16 human-review cases and 993 ready/unobserved filings. The two paper URLs expose page images rather than a direct PDF; the existing downloader raises `PaperFilingError`, which is currently retained as deferred work. The warnings were not erased or relabeled healthy. Executive maintenance showed **Successful / Complete**, with 20 access-required OGE filings and zero technical retries. Access-required is not evidence of document extraction.

Both final controlled source passes attempted five documents but completed zero new OCR extractions, zero pages and zero appended transactions. Three real extraction evidence files from the first rollout remain retained and were verified. Live Operations displayed the repaired Legislative heartbeat `20:40:04.031636Z` and Executive heartbeat `20:43:22.002951Z`, matching accepted metrics. This proves truthful health publication; it is not all-green OCR-engine acceptance or completion of the historical backlog.

Secure owner sign-in succeeded in the live browser. The original `9116331.pdf` was prepared for `house|house:2026:9116331`, SHA-256 `58cefce89a3fe84a5d4893337e79b4bc9add769d02fac1869403456afd5a4343`, 33,662 bytes, two pages. The authenticated upload dialog initially reported no existing upload for this filing. The file-selection/upload call then became unresponsive; the following browser-state check and connection recovery also failed to return. No upload receipt was observed. Submission, extraction and raw-file cleanup are **unknown/unverified**, not successful and not proven absent. The attempt was not repeated. No corrections were submitted.

Next safe action is to recover the existing authenticated browser and use **Refresh processing status** before deciding whether any upload retry is necessary. Verify durable extraction and raw cleanup, then obtain document-specific interpretation of the three unclear asset labels before confirming all five physical rows. Blank ownership remains unknown; do not borrow Joint ownership from the form's example row or fabricate expanded asset names/tickers. Confirmed corrections must reconcile through the existing source producer. Resolve the two Senate warnings separately and keep issue #182 open until remaining acceptance is evidenced.

[Sanitized evidence receipt](2026-09-18-ocr-deployed-receipt.json) records these later checks separately. The completed controller summary retains its original `NOT_YET` fields for upload and scheduled-run acceptance; it was not rewritten to claim later work.
