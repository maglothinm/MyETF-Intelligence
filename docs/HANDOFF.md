# PolitiTrack active handoff

## Current OCR rollout — deployed with warnings (#182)

**The corrected rollout completed at 2026-09-18T20:56:33.832832Z. No release controller is active.** All six existing runtime resources use source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`, image `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`; OCR is enabled on Legislative, Executive and web with the existing owner allowlist. Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded. The additive migration, image/schema checks, controlled successors, independent preservation audit, published OCR-health comparison and live asset checks passed.

The four original schedules are **ENABLED with their original configurations**; Filing Vault remains **PAUSED and untouched**. Natural scheduled Legislative `polititrack-legislative-f5f7m`, created at `21:05:00.804967Z` by the existing scheduler service account, completed successfully at `21:08:48.313546Z` on the exact corrected image. This is post-restoration evidence for this release, not the earlier recovery's run.

The result is **DEPLOYED_WITH_OCR_WARNINGS**, not all-green OCR health. At acceptance, two Senate paper-viewer cases remained deferred, Legislative had 16 human-review cases, and Executive had 20 access-required OGE filings with zero technical retries. Three actual extraction evidence files from the earlier controlled work remain preserved; the final corrected maintenance passes themselves completed zero new document extractions. Operations now displays the validated OCR heartbeat and accurately distinguishes these outcomes.

Both older closed journals and their receipts remain immutable. Their SHA-256 values are `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`. The corrected journal is complete, SHA-256 `f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d`. All three accounts, nine acknowledgement rows, retained ledgers, snapshot lineage and notification history passed preservation checks. No rebaseline or account reset occurred.

**Owner test remains incomplete:** secure sign-in succeeded and the existing owner's source-upload form opened for `house|house:2026:9116331`. Before the attempt, the form reported no upload for this filing. The browser file-selection/upload call then stopped responding, and a subsequent browser-state check could not return. No upload receipt was observed; submission, extraction and raw cleanup remain unknown/unverified. The attempt was not repeated and no row corrections were submitted. Do not assume either successful upload or no submission. Three unclear asset labels still require document-specific owner interpretation; preserve all five physical rows and blank ownership.

Next: recover the authenticated browser and read **Refresh processing status** before any retry; finish upload/extraction/cleanup verification, obtain owner review before confirming all rows, and verify reconciliation by the existing producer. Resolve the two Senate OCR warnings separately. Keep issue #182 open. No additional feature, maintenance or Codex-permission authorization is needed. Do not replay the completed rollout or modify old journals. [Final release evidence](releases/2026-09-18-ocr-deployed.md) and its linked receipt contain exact executions, CI and snapshot identities. Earlier entries below are historical checkpoints.

## Historical checkpoint — corrected rollout active at September 18, 20:20 UTC (#182)

Application repair PR #186 merged at `a2a15edb30895ece37b690e50e0f95fb1eaa2649`; exact PR-head OCR CI `35389493194` and Investor Edge CI `35389493190` passed, and the merge tree matches the tested head. Cloud Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded and produced `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d` in the existing runtime-v2 image repository.

The explicit repair release procedure in PR #187 merged at `db7cd0fd2bb24223a744d219ea04009747a317d7`; all 59 local safety checks and canonical controller CI `35390534977` passed. Installed wrapper `/home/maglothinm/ocr_health_repair_release.py` is SHA-256 `c095e90551a1d96b853a08450af34f9abfedde80ef5504432306c7b8abf90319`. Its read-only preparation verified all live recovered resource/schedule specifications, the repaired build/registry digest and database protections. Both older closed attempts and their receipts are sealed.

**Maintenance is active.** Desktop Commander process `36964` on Beast is running the reviewed wrapper `--deploy`. The four original schedules are paused; Vault remains paused. The controller is draining the existing AI `polititrack-ai-8psnb` and Dashboard `polititrack-dashboard-tqb7f` before obtaining a fresh frozen baseline. Do not interrupt them or launch another controller. New journal: `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-health-repair-a2a15edb3089/ocr-deployment/journal.json`. No repaired-image deployment or final acceptance is claimed yet at this checkpoint.

The earlier recovery's natural scheduled Legislative `polititrack-legislative-sb4pf` completed successfully at `2026-09-18T20:12:39.923230Z`; its creator is the existing scheduler service account. This verifies that recovery's scheduling, not the still-pending repaired rollout. Preserve original journal SHA `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and recovered successor SHA `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`.

Next: observe the same process through fresh baseline, pinned-image activation, producer/AI/dashboard successors, independent preservation and published OCR-health acceptance, and original schedule restoration. Authenticate only through secure browser sign-in for the separate upload/correction/cleanup test. The existing sample is selected; its three unclear labels still need document-specific owner review. Keep issue #182 open. [Repair release procedure](releases/2026-09-18-ocr-health-repair-release.md).


## September 18 repository cleanup — issue #184

Removed the obsolete August 29 `myetf-investor-edge-implementation.zip` installer after verifying the integrated application files remain present and no runtime/workflow consumes the ZIP. Current application code is unchanged. The owner's retention request is to remove obsolete update copies older than September 11 while keeping the two latest useful versions and their dependencies.

Inventory: 134 old merged branches are eligible (122 ancestry-verified and 12 exact-head merged PRs); 231 non-state output artifacts are candidates after retaining the newest two per family and excluding exact pinned evidence. Deletion of branches/artifacts is pending authenticated access; none is claimed complete. Open PRs, unique unmerged work, recent releases, ordinary Git ancestry, production state and pinned recovery/cutover evidence remain intact.

The concurrent OCR continuation at `ebf233ffdffbb7c91bbab90fd281436bd41ab086` is preserved. This cleanup does not deploy OCR, modify runtime/schedules, or certify live health. Existing OCR/runtime release evidence below remains the authority for that separate task. Verification for cleanup is the exact deletion/documentation diff and unchanged application tree; no new runtime run is claimed.

## September 18, 20:02 UTC — OCR acceptance failed; recovery verified (#182)

All six runtime resources now retain pinned source `9402f6c9866e919c789845de96f4334058600cee`, image `sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`. The additive OCR inbox migration and read-only image/schema/account check succeeded. Two controlled Legislative runs, two Executive runs, AI and Dashboard succeeded; final acceptance `polititrack-admin-ht9mq` failed with `published_ocr_health_disagrees`.

**Recovery completed:** `polititrack-admin-424v8` verified frozen-baseline preservation. OCR is disabled on Legislative, Executive and web. At `2026-09-18T20:02:20.643694+00:00`, the four original schedules were ENABLED with original configurations; Vault remained PAUSED. No state rewind, history deletion or account change occurred. A Cloud Shell authentication error interrupted the first recovery's web wait; resuming that same recovery completed successfully without duplicate producer submissions. The failed audit and earlier error remain historical evidence.

The actual Cloud Shell controller `/home/maglothinm/ocrv2.py` is v2.2, SHA-256 `bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`; the prior copy remains in `ocrv2.before-recovery-continuation.py`. The original recovered journal still has SHA-256 `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`. Its successor at `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-continuations/9de6a3cfc21a4ec9b51915301bdaa534/journal.json` is now closed as `recovered_new_image_ocr_disabled`; do not edit/delete/reopen either journal.

Root cause: the dashboard privacy projection stripped the validated OCR `heartbeat_at`. The narrow fix validates only `runtime_mode_evidence.source_ocr` through `safe_metrics`; all other private heartbeat/configuration fields remain filtered. Full dashboard regression coverage and neighboring tests passed locally: **207 passed, 1 PostgreSQL-dependent skip**. Canonical CI and deployment of the correction are still pending at this checkpoint. See [publication correction](releases/2026-09-18-ocr-health-publication.md).

Next: verify canonical CI, build the corrected immutable image, prepare a fresh reviewed release from this recovered configuration, and perform independent publication/OCR-health acceptance. Authenticated owner upload/correction/cleanup and a natural scheduled run remain unverified. The browser is signed out; preserve existing accounts and request secure sign-in when that test is ready. Three unclear sample labels still need document-specific owner review. Keep issue #182 open.

## Historical checkpoint — September 18, 2026: controller installed; recovered journal preserved (#182)

Beast's Desktop Commander connection is responsive again. The existing Cloud Shell workspace is reachable through Google's authenticated tunnel using the existing local SSH key and an explicitly pinned server fingerprint. No SSH key was created by this continuation and no production credential or permission was changed.

The actual controller at `/home/maglothinm/ocrv2.py` matched original SHA-256 `3c46b99a0e406b506c659e98d7f2bdc679f7a653a2a544e57a78c76241d1d795`. The [tested identity patch](releases/2026-09-18-ocr-controller-parent-identity.patch) from canonical commit `108d5315938a48d3bd33c8448e8ce99f23407285` was applied to a staged copy. Python compilation passed. After verifying the unchanged original against its backup, the staged copy replaced the controller. Installed SHA-256 is **`effe53abf63a7adaae8e44673a255dfe17d21fb1f8d030d279c6f36a0bfa0222`**, exactly matching the previously tested controller. The original remains at `/home/maglothinm/ocrv2.before-parent-identity.py` with its original hash. This is a source-only controller correction, not a runtime deployment.

**Actual journal reviewed:** `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-deployment/journal.json`, release ID `9de6a3cfc21a4ec9b51915301bdaa534`. Its status is `recovered_original_configuration`, `steps` is empty, `producer_submission_started` is false, and `schedules_restored` is true. Recovery time is `2026-09-18T15:44:14.898239+00:00`; recorded reason is `execution_inventory_unavailable_before_any_deployment_submission`. The current journal and its predecessor were read, not rewritten. Journal SHA-256 before and after controller replacement was identical: **`cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`**.

A fresh read-only Scheduler query confirmed Legislative, Executive, AI and Dashboard ENABLED, and Filing Vault PAUSED. No production job was dispatched and no schedule, runtime image, database, account, upload or state snapshot was changed. The completed 3,357-record diagnostic was not repeated. No new CI or live OCR acceptance is claimed; the installed controller matches the already-tested bytes and passed compilation in Cloud Shell.

**Remaining boundary:** the earlier automatic tool safety rejection of the runtime deployment-helper preparation was not retried, cleared or routed through Cloud Shell. Source-only controller installation does not authorize bypassing that rejection. The controller still refuses `--deploy` on this closed recovered journal. Do not delete the journal or change its status to force a retry. Existing feature and maintenance authorizations remain recorded; another general authorization is not a remedy.

Next safe work is a permitted, explicitly reviewed continuation that retains the closed attempt and its receipts, followed by a fresh coordinated baseline, additive migration, pinned-image rollout, authenticated upload/correction/cleanup, bounded backfill and independent OCR-health acceptance. **OCR remains undeployed; keep issue #182 open.** Pinned runtime source/image remain `9402f6c9866e919c789845de96f4334058600cee` / `sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`.

## Active task — September 18, 2026: source OCR activation blocked; schedules restored (#182 / PR #183)

**The owner explicitly authorized the bounded maintenance window. No further
feature or maintenance approval is outstanding.** Beast is online and GCP
inspection succeeds. The remote tool nevertheless blocked preparation of the
runtime deployment helper because it could not determine the request's safety
status. This is not a GCP credential/permission error. Do not circumvent the tool
restriction, change security settings, or ask for another authorization as a cure.

The four existing producer schedules were paused at the recorded checkpoint
`2026-09-18T11:33:08.050652+00:00`. Drain found existing Dashboard execution
`polititrack-dashboard-k6cp4`, which was not cancelled. After the tool block,
all four original schedules were resumed and verified against their original
cadences, time zones, HTTP targets, retry settings and attempt deadlines. Vault
remained PAUSED and untouched. All six runtime resource specifications were also
verified unchanged. Recovery receipt: `2026-09-18T11:35:04.096136+00:00`.

**Not deployed or enabled.** No frozen cutover baseline, migration, live-image
update, OCR/account activation, or live upload/import was executed. No rebaseline,
account/acknowledgement reset or history deletion occurred. Existing scheduled
jobs can advance normally; no post-restoration successful run is claimed merely
from restoring the schedules. Application source was not changed in this attempt.

PR #183 remains merged at pinned runtime source
`9402f6c9866e919c789845de96f4334058600cee` in canonical repository ID 1349678672,
`maglothinm/MyETF-Intelligence`, branch `main`. The merge tree matches tested PR
head `3e11f9491bfa29d0935059202926ed2ec57ec987`. Post-merge OCR CI `35339190135`
and Investor Edge CI `35339190177` passed; PR-head Runtime safety `35273397245`
passed. Cloud Build `d4a7f1e6-3437-4235-8e3b-13e4125f6a72` succeeded. Built image:
`us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`.

OCR-specific run health is in that merged/built version, not verified live.
The original sample's three unclear labels remain held for document-specific
owner review. Keep issue #182 open. Once deployment execution is permitted,
refresh live specifications, coordinate the same bounded window, capture a fresh
frozen preservation baseline, perform only the additive OCR migration/activation,
and verify real processing, cleanup, history continuity and independent health.
Do not treat the earlier read-only preflight as a frozen or post-release audit.

[Latest maintenance-stop and restoration evidence](releases/2026-09-18-source-ocr-maintenance-stopped.md).
[Earlier merge, build and read-only preflight](releases/2026-09-18-source-ocr-predeployment.md).
Private receipts and clean pinned checkout:
`C:/Users/maglo/Documents/Codex/2026-09-18/polititrack-ocr-release-182`.
Preserve all source/AI history, personal accounts, acknowledgements, outbox,
original schedules, Vault pause and unrelated feature settings.


Updated **2026-09-15T12:38:15.901975+00:00 — Inbox interruption delay deployed and verified**.
Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default `main`.

## September 15 current release — Inbox interruption delay accepted

PR #180 / issue #179 is deployed and verified. Inbox waits for a continuous
60-minute interruption before one alert, and emits recovery only for a reported
episode. Operations stays immediate. Local checks, canonical PR/main CI, exact
served bundles and real Chromium boundary/recovery checks passed.

Dashboard publisher source `2629c05be5a7478c1fdd8695536f618b25d4d78f`, build `0acd4adc-7a40-4a1b-b142-3f163b987723`,
image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:aa5b79b468c6f02d3925bc8758b77fa68db922cbdafa383df37258574aeb9cae`. Publication `polititrack-dashboard-kvtfv`
succeeded at generation 900. Other production resource specifications
are unchanged. All original schedules are restored; Vault remains paused.
Snapshot lineage, original history, three accounts and eight acknowledgements
passed preservation checks. No task blocker remains; existing Gmail setup and
source-date reporting are separate. Refresh the page to load the new browser code.

[Release evidence](releases/2026-09-15-inbox-interruption-delay.md) and
[receipt](releases/2026-09-15-inbox-interruption-delay-receipt.json).
Do not replay this release; refresh live evidence before any future change.

## Prior diagnosis — Current despite an older source date

The owner cancelled the tooltip change and requested diagnosis. At 12:15 UTC on
September 15, published monitoring evidence and independent Cloud Run logs show
recent successful Legislative, Executive and AI execution. House, Senate and OGE
reported zero new filings. The displayed September 14 source timestamp uses
retained record/run timestamps separately from monitoring health.

A reporting defect is confirmed: recent collector history rows are incorrectly
labelled `local`, so the production-only source-date calculation excludes them.
Verified Runtime v2 execution records still support the Current badge. Application,
tooltip, schedules, credentials and production state were not changed. No repair or
new release is claimed. [Diagnosis and exact evidence](incidents/2026-09-15-monitoring-current-source-date.md).

Next remediation, if undertaken, should correct new run-history provenance without
rewriting retained history and clarify the source-date contract. The prior release
and outstanding Gmail handoff below remain intact.

## September 14 accepted predecessor — Investor Edge backfill progress

PRs #173/#176/#177 are merged and deployed. Source `0483e8c1f66a9328ec6f46d1ba003594c9aa75fc`, build `b27a9df0-8c09-42df-a39b-01b1d0f985b8`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:14a8ec467ad9893048086349b8675de8967878c5610cad0071f1a6b1d6d24404` are verified on all six existing resources; web `polititrack-web-00043-29c` serves 100% traffic.

The corrected engine chain succeeded at source `4717b770`; the final CSS-only successor passed a new Dashboard run, preservation audit and vertical-scroll checks. Root and standalone progress views passed six live browser checks. Original history, all observation/profile identities, three accounts, eight acknowledgements and failed-run evidence are preserved. The first Python 3.11 incompatibility was corrected without advancing or resetting its failed AI snapshot. All original producer schedules are ENABLED unchanged; Vault remains PAUSED. No new migration, IAM, scoring/budget or unrelated feature enablement.

[Exact release evidence](releases/2026-09-14-investor-edge-backfill-progress.md) and [receipt](releases/2026-09-14-investor-edge-backfill-progress-receipt.json). Production heads advance naturally; this is bounded feature acceptance, not completion of all historical market outcomes. Gmail delivery configuration remains separate.

Issue #172 deployment is complete. No additional owner feedback is needed. Do not rerun the release; refresh live evidence before any future changes.

## Preserved concurrent release handoff

The owner authorized full release. PRs #169/#171 are merged and the application changes are live.
Gmail delivery remains incomplete: Owner-created Google app password has not yet been saved in the prepared Secret Manager form. No successful investor-alert email or inbox receipt is claimed.

The owner is signed into Google and created an app password named “PolitiTrack alerts.” A Google Cloud Secret Manager form named `polititrack-gmail-app-password` was prepared for their private entry. Do not ask for the password in chat or recreate account credentials. Complete this secure handoff, bind only the existing AI job's versioned Gmail secrets with narrow access, and verify provider acceptance/inbox receipt separately. The release tools and private evidence are in `C:/Users/maglo/Documents/Codex/2026-09-10/polititrack-alerts-navigation/release-20260911`. Refresh live configuration before any further mutation; schedules are already restored, so do not rerun the initial cutover.

## September 14 production predecessor

Source `0483e8c1f66a9328ec6f46d1ba003594c9aa75fc`; image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:14a8ec467ad9893048086349b8675de8967878c5610cad0071f1a6b1d6d24404`; build `b27a9df0-8c09-42df-a39b-01b1d0f985b8`; web `polititrack-web-00043-29c` at 100%. All four producer schedules are ENABLED, Vault remains PAUSED. The release receipt records exact controlled executions, snapshot hashes, live progress counts and preservation checks. Earlier September 11 tools and credentials handoff below remain historical/context only.

## Preservation and release boundaries

All pre-release snapshots, original failure/side-effect evidence, three accounts, eight acknowledgement rows, and previous notification history were preserved. No schema migration, rebaseline, rewind or alternate writer was introduced. Personal review enablement, allowed origin and existing sign-in are intact. Prior recovery and Phase 5 certificates remain historical; this is bounded release acceptance.

Only recipient-aware, outbox-compatible images may follow this release. Keep the per-profile crossing journal and pending/held/uncertain/accepted delivery distinctions. Missing provider credentials must not stop collection. Do not clear holds, delete original failures, reset reviews, or populate production with a synthetic qualification test.

## Other work remains separate

Operations controls #164/#165 are present in source but their enablement remains off; their schema/IAM activation was not included. Current Opportunity #154 remains excluded. Preserve existing production ownership and coordinate any new release from fresh live evidence.

Historical references: [September 9 recovery](releases/2026-09-09-legislative-recovery.md), [personal acknowledgements](releases/2026-09-09-personal-review-acknowledgements.md), [Operations activation contract](operations-manual-runs.md), [feature contract](investor-alerts-navigation.md).
