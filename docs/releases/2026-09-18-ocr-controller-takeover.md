# OCR controller takeover — September 18, 2026

## Active rollout checkpoint — September 18, 2026, 19:25 UTC

The source-only closed-journal repair and explicit successor design in [PR #185](https://github.com/maglothinm/MyETF-Intelligence/pull/185) are merged at `58ac647d55f6952174966776304efe6fbd43c11b`. All 42 offline checks and GitHub controller safety run `35384375512` passed. See [continuation design](2026-09-18-ocr-recovered-continuation.md).

The exact new controller is staged at `/home/maglothinm/ocrv2.continuation-review.py`, SHA-256 `bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`. Its read-only review matched the actual recovered journal and every original receipt. The reviewed continuation was then submitted through the existing connected tool without a safety rejection. The old rejected helper was not replayed and no security setting was weakened.

**Maintenance is active.** The four production schedules are paused; Vault remains paused. Existing Executive `polititrack-executive-prmt9` completed successfully. Fresh frozen baseline `polititrack-admin-hfszq` passed. The existing Admin job now uses the pinned OCR image, and additive migration `polititrack-admin-jhl44` succeeded. Read-only image/schema/account/role verification is running as `polititrack-admin-k6mkt`. Remaining-resource rollout, producer acceptance, schedule restoration, upload/correction/cleanup and natural-run acceptance are not yet claimed.

Observe the existing Desktop Commander process `44328` on Beast and the successor journal `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-continuations/9de6a3cfc21a4ec9b51915301bdaa534/journal.json`. Do not start another controller or edit/delete either journal. The original recovered journal remains closed at SHA-256 `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`.

## Current continuation — September 18, 2026: controller installed; recovered journal preserved (#182)

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
