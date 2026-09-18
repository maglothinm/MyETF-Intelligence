# OCR controller takeover — September 18, 2026

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
