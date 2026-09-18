# OCR controller takeover — September 18, 2026

## Current OCR rollout — deployed with warnings (#182)

**The corrected rollout completed at 2026-09-18T20:56:33.832832Z. No release controller is active.** All six existing runtime resources use source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`, image `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`; OCR is enabled on Legislative, Executive and web with the existing owner allowlist. Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded. The additive migration, image/schema checks, controlled successors, independent preservation audit, published OCR-health comparison and live asset checks passed.

The four original schedules are **ENABLED with their original configurations**; Filing Vault remains **PAUSED and untouched**. Natural scheduled Legislative `polititrack-legislative-f5f7m`, created at `21:05:00.804967Z` by the existing scheduler service account, completed successfully at `21:08:48.313546Z` on the exact corrected image. This is post-restoration evidence for this release, not the earlier recovery's run.

The result is **DEPLOYED_WITH_OCR_WARNINGS**, not all-green OCR health. At acceptance, two Senate paper-viewer cases remained deferred, Legislative had 16 human-review cases, and Executive had 20 access-required OGE filings with zero technical retries. Three actual extraction evidence files from the earlier controlled work remain preserved; the final corrected maintenance passes themselves completed zero new document extractions. Operations now displays the validated OCR heartbeat and accurately distinguishes these outcomes.

Both older closed journals and their receipts remain immutable. Their SHA-256 values are `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`. The corrected journal is complete, SHA-256 `f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d`. All three accounts, nine acknowledgement rows, retained ledgers, snapshot lineage and notification history passed preservation checks. No rebaseline or account reset occurred.

**Owner test remains incomplete:** secure sign-in succeeded and the existing owner's source-upload form opened for `house|house:2026:9116331`. Before the attempt, the form reported no upload for this filing. The browser file-selection/upload call then stopped responding, and a subsequent browser-state check could not return. No upload receipt was observed; submission, extraction and raw cleanup remain unknown/unverified. The attempt was not repeated and no row corrections were submitted. Do not assume either successful upload or no submission. Three unclear asset labels still require document-specific owner interpretation; preserve all five physical rows and blank ownership.

**Retry check — September 18, 23:09 UTC:** The owner requested another upload attempt. The browser connection again failed to respond before a new submission could be made. An authorized read-only Cloud Logging query for the last day returned no recorded POST requests to this web service’s source-OCR API. This is log evidence only, not a database receipt or proof that the earlier attempt never submitted. No new upload or corrections were submitted by this retry; no production configuration or recovered journal was changed. Reconcile the existing upload status through the authenticated UI before retrying.

Next: recover the authenticated browser and read **Refresh processing status** before any retry; finish upload/extraction/cleanup verification, obtain owner review before confirming all rows, and verify reconciliation by the existing producer. Resolve the two Senate OCR warnings separately. Keep issue #182 open. No additional feature, maintenance or Codex-permission authorization is needed. Do not replay the completed rollout or modify old journals. [Final release evidence](2026-09-18-ocr-deployed.md) and its linked receipt contain exact executions, CI and snapshot identities. Earlier entries below are historical checkpoints.

## Historical checkpoint — corrected rollout active at September 18, 20:20 UTC (#182)

Application repair PR #186 merged at `a2a15edb30895ece37b690e50e0f95fb1eaa2649`; exact PR-head OCR CI `35389493194` and Investor Edge CI `35389493190` passed, and the merge tree matches the tested head. Cloud Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded and produced `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d` in the existing runtime-v2 image repository.

The explicit repair release procedure in PR #187 merged at `db7cd0fd2bb24223a744d219ea04009747a317d7`; all 59 local safety checks and canonical controller CI `35390534977` passed. Installed wrapper `/home/maglothinm/ocr_health_repair_release.py` is SHA-256 `c095e90551a1d96b853a08450af34f9abfedde80ef5504432306c7b8abf90319`. Its read-only preparation verified all live recovered resource/schedule specifications, the repaired build/registry digest and database protections. Both older closed attempts and their receipts are sealed.

**Maintenance is active.** Desktop Commander process `36964` on Beast is running the reviewed wrapper `--deploy`. The four original schedules are paused; Vault remains paused. The controller is draining the existing AI `polititrack-ai-8psnb` and Dashboard `polititrack-dashboard-tqb7f` before obtaining a fresh frozen baseline. Do not interrupt them or launch another controller. New journal: `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-health-repair-a2a15edb3089/ocr-deployment/journal.json`. No repaired-image deployment or final acceptance is claimed yet at this checkpoint.

The earlier recovery's natural scheduled Legislative `polititrack-legislative-sb4pf` completed successfully at `2026-09-18T20:12:39.923230Z`; its creator is the existing scheduler service account. This verifies that recovery's scheduling, not the still-pending repaired rollout. Preserve original journal SHA `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and recovered successor SHA `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`.

Next: observe the same process through fresh baseline, pinned-image activation, producer/AI/dashboard successors, independent preservation and published OCR-health acceptance, and original schedule restoration. Authenticate only through secure browser sign-in for the separate upload/correction/cleanup test. The existing sample is selected; its three unclear labels still need document-specific owner review. Keep issue #182 open. [Repair release procedure](2026-09-18-ocr-health-repair-release.md).


## September 18, 20:02 UTC — OCR acceptance failed; recovery verified (#182)

All six runtime resources now retain pinned source `9402f6c9866e919c789845de96f4334058600cee`, image `sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`. The additive OCR inbox migration and read-only image/schema/account check succeeded. Two controlled Legislative runs, two Executive runs, AI and Dashboard succeeded; final acceptance `polititrack-admin-ht9mq` failed with `published_ocr_health_disagrees`.

**Recovery completed:** `polititrack-admin-424v8` verified frozen-baseline preservation. OCR is disabled on Legislative, Executive and web. At `2026-09-18T20:02:20.643694+00:00`, the four original schedules were ENABLED with original configurations; Vault remained PAUSED. No state rewind, history deletion or account change occurred. A Cloud Shell authentication error interrupted the first recovery's web wait; resuming that same recovery completed successfully without duplicate producer submissions. The failed audit and earlier error remain historical evidence.

The actual Cloud Shell controller `/home/maglothinm/ocrv2.py` is v2.2, SHA-256 `bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`; the prior copy remains in `ocrv2.before-recovery-continuation.py`. The original recovered journal still has SHA-256 `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`. Its successor at `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-continuations/9de6a3cfc21a4ec9b51915301bdaa534/journal.json` is now closed as `recovered_new_image_ocr_disabled`; do not edit/delete/reopen either journal.

Root cause: the dashboard privacy projection stripped the validated OCR `heartbeat_at`. The narrow fix validates only `runtime_mode_evidence.source_ocr` through `safe_metrics`; all other private heartbeat/configuration fields remain filtered. Full dashboard regression coverage and neighboring tests passed locally: **207 passed, 1 PostgreSQL-dependent skip**. Canonical CI and deployment of the correction are still pending at this checkpoint. See [publication correction](2026-09-18-ocr-health-publication.md).

Next: verify canonical CI, build the corrected immutable image, prepare a fresh reviewed release from this recovered configuration, and perform independent publication/OCR-health acceptance. Authenticated owner upload/correction/cleanup and a natural scheduled run remain unverified. The browser is signed out; preserve existing accounts and request secure sign-in when that test is ready. Three unclear sample labels still need document-specific owner review. Keep issue #182 open.

## Historical checkpoint — September 18, 2026: controller installed; recovered journal preserved (#182)

Beast's Desktop Commander connection is responsive again. The existing Cloud Shell workspace is reachable through Google's authenticated tunnel using the existing local SSH key and an explicitly pinned server fingerprint. No SSH key was created by this continuation and no production credential or permission was changed.

The actual controller at `/home/maglothinm/ocrv2.py` matched original SHA-256 `3c46b99a0e406b506c659e98d7f2bdc679f7a653a2a544e57a78c76241d1d795`. The [tested identity patch](2026-09-18-ocr-controller-parent-identity.patch) from canonical commit `108d5315938a48d3bd33c8448e8ce99f23407285` was applied to a staged copy. Python compilation passed. After verifying the unchanged original against its backup, the staged copy replaced the controller. Installed SHA-256 is **`effe53abf63a7adaae8e44673a255dfe17d21fb1f8d030d279c6f36a0bfa0222`**, exactly matching the previously tested controller. The original remains at `/home/maglothinm/ocrv2.before-parent-identity.py` with its original hash. This is a source-only controller correction, not a runtime deployment.

**Actual journal reviewed:** `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-deployment/journal.json`, release ID `9de6a3cfc21a4ec9b51915301bdaa534`. Its status is `recovered_original_configuration`, `steps` is empty, `producer_submission_started` is false, and `schedules_restored` is true. Recovery time is `2026-09-18T15:44:14.898239+00:00`; recorded reason is `execution_inventory_unavailable_before_any_deployment_submission`. The current journal and its predecessor were read, not rewritten. Journal SHA-256 before and after controller replacement was identical: **`cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`**.

A fresh read-only Scheduler query confirmed Legislative, Executive, AI and Dashboard ENABLED, and Filing Vault PAUSED. No production job was dispatched and no schedule, runtime image, database, account, upload or state snapshot was changed. The completed 3,357-record diagnostic was not repeated. No new CI or live OCR acceptance is claimed; the installed controller matches the already-tested bytes and passed compilation in Cloud Shell.

**Remaining boundary:** the earlier automatic tool safety rejection of the runtime deployment-helper preparation was not retried, cleared or routed through Cloud Shell. Source-only controller installation does not authorize bypassing that rejection. The controller still refuses `--deploy` on this closed recovered journal. Do not delete the journal or change its status to force a retry. Existing feature and maintenance authorizations remain recorded; another general authorization is not a remedy.

Next safe work is a permitted, explicitly reviewed continuation that retains the closed attempt and its receipts, followed by a fresh coordinated baseline, additive migration, pinned-image rollout, authenticated upload/correction/cleanup, bounded backfill and independent OCR-health acceptance. **OCR remains undeployed; keep issue #182 open.** Pinned runtime source/image remain `9402f6c9866e919c789845de96f4334058600cee` / `sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`.

## Earlier diagnostic checkpoint — before controller installation

**Status: exact controller defect reproduced and correction tested; OCR not deployed.**
Canonical repository ID `1349678672`, `maglothinm/MyETF-Intelligence`, branch `main`. Runtime image/source remain the existing pinned release; this change records diagnosis and a nonexecuted controller patch, not a runtime rollout.

## Owner request and execution scope

The owner requested direct takeover and Work mode rather than further terminal copy/paste. Existing feature and bounded-maintenance authorization remains in force. Beast was confirmed online. The assistant directly inspected GCP through the existing authorized connection, wrote only local read-only diagnostic files, and ran the live inventory verification without asking the owner to execute another command. No chat-mode selector was changed, and no additional permission was granted or requested.

The prior platform restriction on a deployment-helper operation is distinct from this newly diagnosed application-validation error. This session did not retry that restricted operation, change security settings, or route deployment through another execution path.

## Confirmed defect

The actual authenticated Cloud Run v2 response pairs:

- `name`: `projects/project-38008d5f-4918-46e6-920/locations/us-central1/jobs/polititrack-legislative/executions/polititrack-legislative-h49zg`
- `job`: `polititrack-legislative`

The v2 controller required `job` to equal the first six segments of `name`, a full resource path. Consequently it rejected valid same-project/same-job executions. This is not a Cloud Run execution failure and does not show that the API returned another project.

The correction accepts the exact requested short job name only after validating the entire execution path. It also accepts full parent paths with the independently verified project ID/number aliases; normalizes execution identity for duplicate detection; and reports separate execution-path, parent-job and duplicate errors. Wrong projects, regions, jobs, malformed names and missing parent identity still fail. Pagination, terminal-state semantics, deployment authorization, state preservation and the closed-recovered-journal guard are unchanged.

## Executed verification

**40 isolated tests passed**, using the actual locally patched v2 controller for pagination/duplicate/error/recovered-state tests plus pure validator cases. Cases include short/full parent forms, verified project-number aliases, foreign projects/regions/jobs, malformed/missing values, equivalent-identity duplicates across pages, repeated page tokens, unchanged terminal-state interpretation, and continued refusal to reopen a recovered journal. Python compilation passed.

The exact identity validator used in local tests was copied transparently to Beast. Its SHA-256 matched `5c7c0a7eecaad6809f97e63da200c1abe8b4b18efdad20ab55549c345fc80249` on both systems.

Live read-only verification ran from `2026-09-18T16:01:18.937489+00:00` to `2026-09-18T16:01:46.627212+00:00`, with process exit code 0:

| Existing job | Records checked | Pages read | Complete pagination |
|---|---:|---:|---|
| Legislative | 1,001 | 11 | Yes |
| Executive | 607 | 7 | Yes |
| AI | 634 | 7 | Yes |
| Dashboard | 1,004 | 11 | Yes |
| Admin | 111 | 2 | Yes |
| **Total** | **3,357** | **38** | **All returned pages** |

All 3,357 records returned the short parent job name and passed the corrected validation. No duplicate identities or invalid tokens were accepted. No active/unconfirmed executions were found in these individual scans. This was not a frozen, simultaneous cutover baseline: original schedules stayed enabled throughout.

Final scheduler read confirmed Legislative, Executive, AI and Dashboard ENABLED; Filing Vault PAUSED. No schedule change, execution dispatch, database migration, account change, source import or runtime rollout was performed in this session. The latest observed Legislative execution completed successfully after restoration at `2026-09-18T15:54:52.877198Z`; Dashboard at `2026-09-18T15:51:10.661262Z`. This does not establish a post-restoration Executive/AI success or any OCR success.

## Preserved correction and handoff

[Exact source patch](2026-09-18-ocr-controller-parent-identity.patch) applies to the original `ocrv2.py` SHA-256 `3c46b99a0e406b506c659e98d7f2bdc679f7a653a2a544e57a78c76241d1d795`.
Resulting review-controller SHA-256: `effe53abf63a7adaae8e44673a255dfe17d21fb1f8d030d279c6f36a0bfa0222`.
The patch has not been applied to the owner's Cloud Shell controller or deployment journal. It is not a new release command, and it deliberately does not reopen the recovered attempt.

Owner-reported Cloud Shell workspace: `/home/maglothinm/polititrack-ocr-182-v68vldej`; reported journal status `recovered_original_configuration`, zero recorded execution steps, original schedules restored. Preserve that journal and all receipts. Reconcile its actual contents before any permitted future cutover; never delete it to force a new attempt.

Private diagnostic evidence on Beast: `C:/Users/maglo/Documents/Codex/2026-09-18/polititrack-ocr-release-182/evidence/takeover-read-only/inventory-validation.json`. Helpers: `execution_identity_review.py` and `ocr_inventory_readonly.py` in that same release workspace. They perform read-only inventory checks, not deployment.

Pending: reviewed controller integration and recovered-attempt continuation under permitted tools, fresh coordinated baseline, additive inbox migration, pinned-image activation, live upload/correction/cleanup, bounded backfill and independent OCR-health acceptance. Owner document interpretation must not be fabricated. Keep issue #182 open. The chat's UI mode selector and tool permissions are separate from these code corrections.
