# OCR controller takeover — September 18, 2026

## OGE go-live diagnosis — September 19, 12:23 UTC (#182)

**The current source failure is TCP connectivity to the disclosure host.** Cloud
Shell and Beast both resolve `extapps2.oge.gov`, but connections to port 443 time
out after 12 seconds with curl exit 28, no completed TCP/TLS connection and no
HTTP response. OGE's separate `www.oge.gov` frontend returns HTTP 200 from both
clients (0.175 seconds from Cloud Shell; 0.336 seconds from Beast). Beast resolves
the disclosure host to `169.62.159.153`. This narrows the failure to disclosure-host
availability/connectivity; it does not identify OGE's internal service, routing
or filtering cause. No site-served bot challenge, login or acknowledgement error
was returned. Existing RDC and authenticated Google Cloud access work.

The latest scheduled Executive execution `polititrack-executive-r5hq7`, created
at 12:11:08.590890Z, failed at 12:15 UTC. Run
`a160011a-8833-4031-8f24-bec4267efa95` timed out waiting 120,000 ms for the table.
OCR is enabled, but collection failed first: final OCR stage `skipped`, zero
documents attempted. This is separate from the PDF eligibility/validation repair.

**Three release facts must stay distinct:**

1. The source is currently unreachable from both tested clients. A collector
   retry can tolerate a transient failure but cannot restore the remote service.
2. The release controller requires every latest production run to be successful
   before changing images. The Executive failure blocks that gate. No gate or
   closed journal was changed, and a prior successful snapshot cannot stand in
   for the latest failed attempt.
3. PR #190 is merged and CI passed, but it has no new image or reviewed release
   continuation yet. Cloud Build's newest build is still
   `106763d5-5981-41fa-bc97-686c8bdfa3c1`, source `db4aa4da54be...` (PR #188).
   The existing wrapper pins that older source and its attempt is closed.
   Replaying it would not deploy the discovery fix. Choosing the isolated
   recovery head also requires exact-source CI; PR/main CI tested the merged
   tree, which includes the separate disabled Current Opportunity integration.

Live Executive still uses source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`, image
`sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`.
Four original schedules are enabled with unchanged specifications; Vault is
paused. This diagnosis used read-only cloud/network checks and changed docs only.

Next safe action: complete a successful official-source collection through the
existing Executive writer, select and verify the exact repair source/build,
prepare a new reviewed continuation retaining all four journals, then perform a
fresh baseline, deployment and independent acceptance. No further general
maintenance authorization is needed. [Detailed evidence](2026-09-19-oge-live-blocker-diagnosis.json).

## September 19 active OGE/PDF repair release

**Reconnected; release stopped safely before deployment.** Beast and authenticated Cloud Shell work. Release procedure [PR #189](https://github.com/maglothinm/MyETF-Intelligence/pull/189) is merged at `a644c923a8ef5e8a2bdafde3223bd014b495b4cb`; exact-head controller CI [35440015522](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35440015522) passed 81 checks. Cloud Build `106763d5-5981-41fa-bc97-686c8bdfa3c1` succeeded for tested application source `db4aa4da54be845a1e139dc354d9f59aa9006d8a`, producing `sha256:b7e8c0a3cd771e0741abfb5e3bf7334e5f47d0b74807bfd48b991ce9154aecb6`. Current Opportunity #154 is outside that pinned image.

The fresh read-only baseline `polititrack-admin-fqgkw` verified snapshot hashes/lineage and recorded the existing account inventory, but the release gate refused cutover because the latest Executive production run was a failure. Cloud logs identify **OGE rendered-table discovery timing out after 120,000 ms before OCR** in `polititrack-executive-rhwfp`, `polititrack-executive-42tdc` and `polititrack-executive-vwjd8` (10:16, 10:46 and 11:14 UTC). That current collection problem is separate from repaired PDF classification/validation.

**Recovery completed at 2026-09-19T11:33:23.485002Z.** All six runtime resources retain the September 18 image `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`; its OCR flags remain enabled on Legislative, Executive and web. Four original schedules are enabled with unchanged specifications; Vault remains paused. No image update, migration or producer dispatch occurred in this attempt. The generic old engine recovery message about OCR being disabled does not describe these verified original flags. No controller remains active.

The new journal is closed as `recovered_original_configuration`, SHA-256 `5fd6a3462881fceece2e5665606789f2454a9ecadc28232213cc97eab61ca5b8`, at `ocr-oge-pdf-repair-db4aa4da54be/ocr-deployment/journal.json` under the original Cloud Shell workspace. All 863 sealed predecessor files still match. Snapshot heads at baseline: Legislative 1168, Executive 615, AI 668, Dashboard 1269; three accounts and nine acknowledgement rows are retained. [Release evidence and exact snapshot identities](2026-09-19-oge-pdf-release.md).

Next: resolve/verify OGE discovery recovery, then review a new continuation retaining this fourth closed attempt and requiring fresh baseline success. Do not reopen/replay its journal, weaken the baseline gate or resubmit the owner upload. Independent read-only upload audit `polititrack-admin-hcvkt` passed at `2026-09-19T11:35:43.858829Z`: the accepted House upload has a null raw payload, its acknowledged snapshot hash and two-page extraction match, and all five rows remain `needs_review`. No resubmission or owner corrections occurred. OGE layout and owner row-correction/import acceptance remain open. No further general maintenance authorization is needed.


## Current repair — OGE downloads and readable PDFs (#182)

The repair is merged through [PR #188](https://github.com/maglothinm/MyETF-Intelligence/pull/188) into canonical `main` at `db4aa4da54be845a1e139dc354d9f59aa9006d8a`. The merge tree equals tested head `7c74a303c340928f114e99c25e09606c9a344958`. Official OGE PDF links now receive direct access metadata while the old URL-slot calculation preserves every listing ID. Existing producer passes append metadata corrections to retained PDFs, retry the affected old OCR failures once, and prioritize accessible documents over gated requests. Readable empty-password PDFs pass inspection; password-required/malformed files and all existing resource bounds remain enforced. Successful OCR caches and pending owner confirmations retain their version.

Local verification: **298 Python tests passed, 21 environment-dependent skips; 4 Node tests passed**. Actual OCR completed 2/2 pages of the previously rejected House sample and 3/3 pages of an OGE sample. A copy of the public ledger showed exactly 340 metadata corrections while preserving all 5,144 IDs and unrelated fields, with no writes on a repeat pass. Canonical exact-head CI passed: [OCR 35431787255](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35431787255) (318 passed, 1 skipped; PostgreSQL enabled), [Runtime safety 35431787249](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35431787249) (530 passed, 2 skipped), and [Investor Edge 35431787258](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35431787258) (778 passed).

**Not deployed.** Beast is offline, so the connected Cloud Shell release path is unavailable. No production settings/state or sealed journals were changed. The last verified configuration remains the September 18 image, four enabled original schedules and Filing Vault paused. Testing also exposed OGE wrapped headers contaminating asset names; a guard now routes those cases to layout review, so corrected access does not imply accepted transactions. The existing five-row House upload remains awaiting owner review, with no resubmission or corrections.

Next: restore the Beast/Cloud Shell connection, then perform a fresh coordinated release and independent live acceptance once deployment access is available. Preserve IDs, historical alerts, snapshots, personal review history and all closed journals. OGE layout acceptance and owner correction/import/independent cleanup verification remain open. [Repair details and evidence](2026-09-19-oge-pdf-repair.md).

## September 18 rollout and earlier upload checkpoints (#182)

**The corrected rollout completed at 2026-09-18T20:56:33.832832Z. No release controller is active.** All six existing runtime resources use source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`, image `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`; OCR is enabled on Legislative, Executive and web with the existing owner allowlist. Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded. The additive migration, image/schema checks, controlled successors, independent preservation audit, published OCR-health comparison and live asset checks passed.

The four original schedules are **ENABLED with their original configurations**; Filing Vault remains **PAUSED and untouched**. Natural scheduled Legislative `polititrack-legislative-f5f7m`, created at `21:05:00.804967Z` by the existing scheduler service account, completed successfully at `21:08:48.313546Z` on the exact corrected image. This is post-restoration evidence for this release, not the earlier recovery's run.

The result is **DEPLOYED_WITH_OCR_WARNINGS**, not all-green OCR health. At acceptance, two Senate paper-viewer cases remained deferred, Legislative had 16 human-review cases, and Executive had 20 access-required OGE filings with zero technical retries. Three actual extraction evidence files from the earlier controlled work remain preserved; the final corrected maintenance passes themselves completed zero new document extractions. Operations now displays the validated OCR heartbeat and accurately distinguishes these outcomes.

Both older closed journals and their receipts remain immutable. Their SHA-256 values are `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`. The corrected journal is complete, SHA-256 `f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d`. All three accounts, nine acknowledgement rows, retained ledgers, snapshot lineage and notification history passed preservation checks. No rebaseline or account reset occurred.

**Upload accepted — September 19, 01:19 UTC (September 18, 9:19 PM Boston):** The source upload for `house|house:2026:9116331` returned HTTP 202 at `01:19:37.626758Z`, following two HTTP 503 attempts at `01:19:04.883890Z` and `01:19:10.183070Z`. The authenticated owner dialog now shows one two-page upload created at `01:19:38.83546Z`, status **pending**. Browser access has recovered. The existing Legislative execution `polititrack-legislative-5t8xv`, created at `01:20:14.062023Z`, was observed pending. Do not upload the file again. Extraction, raw cleanup and correction/import acceptance remain unverified; no corrections were submitted during this check. The earlier attempt/retry entries below remain historical evidence.

**Earlier owner-test checkpoint:** secure sign-in succeeded and the existing owner's source-upload form opened for `house|house:2026:9116331`. Before the attempt, the form reported no upload for this filing. The browser file-selection/upload call then stopped responding, and a subsequent browser-state check could not return. No upload receipt was observed; submission, extraction and raw cleanup remain unknown/unverified. The attempt was not repeated and no row corrections were submitted. Do not assume either successful upload or no submission. Three unclear asset labels still require document-specific owner interpretation; preserve all five physical rows and blank ownership.

**Retry check — September 18, 23:09 UTC:** The owner requested another upload attempt. The browser connection again failed to respond before a new submission could be made. An authorized read-only Cloud Logging query for the last day returned no recorded POST requests to this web service’s source-OCR API. This is log evidence only, not a database receipt or proof that the earlier attempt never submitted. No new upload or corrections were submitted by this retry; no production configuration or recovered journal was changed. Reconcile the existing upload status through the authenticated UI before retrying.

Next: monitor the accepted upload through **Refresh processing status** and the existing scheduled producer; finish extraction/cleanup verification, obtain owner review before confirming all rows, and verify reconciliation. Do not resubmit the accepted PDF. Resolve the two Senate OCR warnings separately. Keep issue #182 open. No additional feature, maintenance or Codex-permission authorization is needed. Do not replay the completed rollout or modify old journals. [Final release evidence](2026-09-18-ocr-deployed.md) and its linked receipt contain exact executions, CI and snapshot identities. Earlier entries below are historical checkpoints.

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
