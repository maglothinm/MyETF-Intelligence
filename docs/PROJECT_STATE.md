# PolitiTrack project state

## Current Opportunity purchase threshold — production blocked (#197)

The owner authorized implementation followed by production activation. PR #199
carries the implemented per-purchase crossing history, configurable 8% default,
explicit incomplete-data states, compact filter and purchase CSV/JSON exports.
Existing buying/entry/evidence/data gates and paper trading remain unchanged.
Source/CI/merge receipts are retained in the PR; approval is already recorded.

A read-only check of the production AI credentials at September 19, 17:35:42 UTC
received a valid Finnhub quote but **no Alpha Vantage daily history**: the
required `TIME_SERIES_DAILY_ADJUSTED` endpoint returned a premium-access notice.
This blocks trustworthy price-path evaluation and live activation. Current
Opportunity remains off; no provider capability is fabricated and no paid
subscription is purchased. The Executive-only recovery journal separately
reported complete with schedules restored; this is not proof that the later
OCR continuation or this feature is deployed. Refresh its ownership before
any release. See [readiness evidence](releases/2026-09-19-purchase-threshold.md)
and [feature/runbook](PURCHASE_GAIN_THRESHOLD.md).

## Authorized PDF/Senate OCR release — September 19 (#182)

**Live activation checkpoint, 17:32 UTC:** the approved Executive-only repair
completed at 17:29:54 UTC. Executive `polititrack-executive-mldd4` collected all
4,068 listings and committed generation 620 on tested source `77aadf541b03…`
with OCR disabled. Independent `polititrack-admin-2bhnz` passed, proving baseline
preservation, unchanged Executive OCR evidence and unchanged other heads. All
four original schedules were restored. The completed incident is sealed at
SHA-256 `64b2cc0697a7ae2b061eda8941da522a765e56125fc2a63e9606167673f29836`.
[Recovery receipt](releases/2026-09-19-executive-recovery-receipt.json).

**Activation recovery checkpoint, 18:07 UTC:** the normal attempt installed the
same tested image on all six resources and enabled OCR. Its first Legislative
run `polititrack-legislative-7xnjg` committed generation 1191 (5 documents,
8/8 pages, zero retries); Executive `polititrack-executive-xmhxh` committed
generation 621 (5 documents, 17/17 pages, zero retries). Both producers succeeded.
The controller stopped on one `gcloud ... executions describe` status read:
`UNAUTHENTICATED`, reason `ACCESS_TOKEN_TYPE_UNSUPPORTED`. This is a cloud
observation failure, not a failed Executive collection or OCR run.

The unchanged controller is completing safe recovery in
`ocr-pdf-activation-77aadf541b03`; Beast process `32324` remains the only active
controller. Read-only preservation `polititrack-admin-wd7p9` is queued at Cloud
Run startup. Preserve the attempt and let recovery disable OCR and restore
schedules. Do not reopen its journal or resubmit either successful producer.
A new sealed normal continuation is being prepared in
`scripts/ocr_activation_read_recovery_release.py`; only the exact execution-status
read may retry the observed token-type rejection, at most three reads, with all
diagnostics retained. All full baseline/acceptance gates and mutations remain
unchanged. Local controller suite: 141 passed. Canonical CI and the completed
recovery SHA-256 are required before dispatch. Current Opportunity stays off;
Vault stays paused. Final OCR activation/acceptance is not yet complete.

The following records describe the preceding diagnosis and closed attempts.

The owner requested deployment of the tested PDF repair and correct review
classification for Senate image-only filings. PR #191 is merged at
`a9607c88e10959c0cd3844f008915aec12dd0935`, with the same tree as tested build
source `df5bb5a850942ff54f6b73a4936fc9ec18d8e548`. Canonical OCR, Runtime safety
and Current Opportunity checks passed. The new image is installed, but rollout
acceptance failed and recovery disabled OCR; see the current checkpoint below.
Unsupported Senate page viewers and paper
layouts become `needs_review`, without a retry timer. Matching retained Senate
retry receipts receive an append-only classification correction, preserving old
receipts, attempt counts, source dates, evidence and personal reviews. Transport
and access failures retain their existing backoff. Successful extraction caches
and the document policy version are unchanged.

The upstream OGE interruption recovered before the later troubleshooting:
scheduled `polititrack-executive-6jcw6` succeeded at 13:45:42 UTC, before the first
successful diagnostic at 13:53:04. Manual `polititrack-executive-cft5v` succeeded
at 14:00:48. Failed and successful executions had identical image/specifications.
The earlier TCP failure is established; its upstream internal cause and any claim
that our testing forced recovery are not established.

**Recovery completed at 15:27:16 UTC.** Build
`55696595-ff36-411f-922f-65a3657490ab` produced installed image
`sha256:ae9b21488499dd8e7f7bbbacac5ccaea5bea0e86a817b0f9ceeea8d79d2586eb`.
The fresh baseline and schema/image checks passed. Legislative
`polititrack-legislative-7bwpp` committed generation 1183 with five OCR documents,
11/11 pages, zero technical retries and five review outcomes. Executive
`polititrack-executive-thrvb` failed before OCR on two bounded OGE loading waits.
Independent preservation `polititrack-admin-hfd2g` passed. All six resources
retain the new image; OCR is disabled on Legislative, Executive and web. All four
original schedules are ENABLED unchanged; Vault stays PAUSED. No controller is active.

The fifth journal is closed as `recovered_new_image_ocr_disabled`, SHA-256
`ed2e9e56e3f770d66fa45bf69f47a2c3f20a34ff02db993ab9c130802d931f2d`.
Preserve all five attempts and committed history. Read-only production-browser
diagnostics prove the table can be fully ready while the collector wait times
out; this is an application readiness defect, not a proven current upstream outage.
Probe `polititrack-admin-jjzmt` isolated it: the polling argument
`{search: null, start: null}` arrives as `{}`, so both properties are undefined
and the initial optional-filter comparison rejects a ready table. Passing the
same values as a JSON scalar succeeds on that same page. A narrow source fix
preserves the values and all existing draw/search/offset/count checks, with a
real Playwright regression. PR #194 merged at `5acc472214ec1886d6556b5051b6b9379cd5a5de`;
exact-head CI `35453468818` passed 354 tests, one skip and browser/UI checks.
Read-only `polititrack-admin-r7svg` collected all 16,670 rows and 4,068 unique
278-T listings. Build `adba5676-b161-4b89-8336-0edc6c22795b` succeeded for tested
source `77aadf541b034072f58dba5e7107c2c8e8ba4bd1`, image digest
`sha256:6be7d1e5236746d02d872303fa6192c29a824d0f55178df33a51c343eb0f18de`.
That source fix is built, not deployed. Independent `polititrack-admin-c6wmp`
confirmed both Senate transitions, unchanged seven-attempt history, no retry
timers, preserved OCR ledger and the original House upload awaiting review.

The owner explicitly approved the one-time Executive-only repair with OCR disabled,
followed by normal activation and acceptance. The new reviewed procedure
`scripts/ocr_executive_recovery_release.py` binds that exception to the exact
built source/image and seals all five closed attempts. It changes only Executive,
requires independent incident preservation and genuine authoritative recovery,
then seals the successful incident before a separate ordinary OCR continuation.
That continuation retains the original successful-baseline and acceptance code.
Procedure tests and deployment are in progress. No source-recovery action has
yet been taken. Current Opportunity stays off; the original House
upload still requires owner review. [Evidence](releases/2026-09-19-senate-pdf-release.md).

## Historical OGE diagnosis — September 19, 12:23 UTC (#182)

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
maintenance authorization is needed. [Detailed evidence](releases/2026-09-19-oge-live-blocker-diagnosis.json).

## Current Opportunity source integration — PR #154, not deployed

The owner authorized merging PR #154 on September 19, 2026. Its source is
reconciled against main `75cb399ea870a77069911c80f3bfe0b788475fd9`, preserving the
newer OCR/OGE repairs, recipient-aware legacy outbox, and Edge backfill pass.
Current Opportunity remains **off**; this is not a production deployment, live
activation, or implementation of the newly proposed never-crossed-percentage flag.
See [the feature/runbook](CURRENT_OPPORTUNITY.md) and PR #154 for merge/check
receipts. Production configuration, histories, schedules, accounts, and live
notifications are outside this source-only merge. The separate OCR release and
owner-review work described below remains open and unchanged.

## Current repair — OGE downloads and readable PDFs (#182)

The repair is merged through [PR #188](https://github.com/maglothinm/MyETF-Intelligence/pull/188) into canonical `main` at `db4aa4da54be845a1e139dc354d9f59aa9006d8a`. The merge tree equals tested head `7c74a303c340928f114e99c25e09606c9a344958`. Official OGE PDF links now receive direct access metadata while the old URL-slot calculation preserves every listing ID. Existing producer passes append metadata corrections to retained PDFs, retry the affected old OCR failures once, and prioritize accessible documents over gated requests. Readable empty-password PDFs pass inspection; password-required/malformed files and all existing resource bounds remain enforced. Successful OCR caches and pending owner confirmations retain their version.

Local verification: **298 Python tests passed, 21 environment-dependent skips; 4 Node tests passed**. Actual OCR completed 2/2 pages of the previously rejected House sample and 3/3 pages of an OGE sample. A copy of the public ledger showed exactly 340 metadata corrections while preserving all 5,144 IDs and unrelated fields, with no writes on a repeat pass. Canonical exact-head CI passed: [OCR 35431787255](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35431787255) (318 passed, 1 skipped; PostgreSQL enabled), [Runtime safety 35431787249](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35431787249) (530 passed, 2 skipped), and [Investor Edge 35431787258](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35431787258) (778 passed).

**Reconnected; release stopped safely before deployment.** Beast and authenticated Cloud Shell work. Release procedure [PR #189](https://github.com/maglothinm/MyETF-Intelligence/pull/189) is merged at `a644c923a8ef5e8a2bdafde3223bd014b495b4cb`; exact-head controller CI [35440015522](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35440015522) passed 81 checks. Cloud Build `106763d5-5981-41fa-bc97-686c8bdfa3c1` succeeded for tested application source `db4aa4da54be845a1e139dc354d9f59aa9006d8a`, producing `sha256:b7e8c0a3cd771e0741abfb5e3bf7334e5f47d0b74807bfd48b991ce9154aecb6`. Current Opportunity #154 is outside that pinned image.

The fresh read-only baseline `polititrack-admin-fqgkw` verified snapshot hashes/lineage and recorded the existing account inventory, but the release gate refused cutover because the latest Executive production run was a failure. Cloud logs identify **OGE rendered-table discovery timing out after 120,000 ms before OCR** in `polititrack-executive-rhwfp`, `polititrack-executive-42tdc` and `polititrack-executive-vwjd8` (10:16, 10:46 and 11:14 UTC). That current collection problem is separate from repaired PDF classification/validation.

**Recovery completed at 2026-09-19T11:33:23.485002Z.** All six runtime resources retain the September 18 image `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`; its OCR flags remain enabled on Legislative, Executive and web. Four original schedules are enabled with unchanged specifications; Vault remains paused. No image update, migration or producer dispatch occurred in this attempt. The generic old engine recovery message about OCR being disabled does not describe these verified original flags. No controller remains active.

The new journal is closed as `recovered_original_configuration`, SHA-256 `5fd6a3462881fceece2e5665606789f2454a9ecadc28232213cc97eab61ca5b8`, at `ocr-oge-pdf-repair-db4aa4da54be/ocr-deployment/journal.json` under the original Cloud Shell workspace. All 863 sealed predecessor files still match. Snapshot heads at baseline: Legislative 1168, Executive 615, AI 668, Dashboard 1269; three accounts and nine acknowledgement rows are retained. [Release evidence and exact snapshot identities](releases/2026-09-19-oge-pdf-release.md).

Next: resolve/verify OGE discovery recovery, then review a new continuation retaining this fourth closed attempt and requiring fresh baseline success. Do not reopen/replay its journal, weaken the baseline gate or resubmit the owner upload. Independent read-only upload audit `polititrack-admin-hcvkt` passed at `2026-09-19T11:35:43.858829Z`: the accepted House upload has a null raw payload, its acknowledged snapshot hash and two-page extraction match, and all five rows remain `needs_review`. No resubmission or owner corrections occurred. OGE layout and owner row-correction/import acceptance remain open. No further general maintenance authorization is needed.

## September 18 rollout and earlier upload checkpoints (#182)

**The corrected rollout completed at 2026-09-18T20:56:33.832832Z. No release controller is active.** All six existing runtime resources use source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`, image `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`; OCR is enabled on Legislative, Executive and web with the existing owner allowlist. Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded. The additive migration, image/schema checks, controlled successors, independent preservation audit, published OCR-health comparison and live asset checks passed.

The four original schedules are **ENABLED with their original configurations**; Filing Vault remains **PAUSED and untouched**. Natural scheduled Legislative `polititrack-legislative-f5f7m`, created at `21:05:00.804967Z` by the existing scheduler service account, completed successfully at `21:08:48.313546Z` on the exact corrected image. This is post-restoration evidence for this release, not the earlier recovery's run.

The result is **DEPLOYED_WITH_OCR_WARNINGS**, not all-green OCR health. At acceptance, two Senate paper-viewer cases remained deferred, Legislative had 16 human-review cases, and Executive had 20 access-required OGE filings with zero technical retries. Three actual extraction evidence files from the earlier controlled work remain preserved; the final corrected maintenance passes themselves completed zero new document extractions. Operations now displays the validated OCR heartbeat and accurately distinguishes these outcomes.

Both older closed journals and their receipts remain immutable. Their SHA-256 values are `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`. The corrected journal is complete, SHA-256 `f2bb8676741af365319d4a0dea15ea829ee33f8f9fb818adba6cc8ee418ef43d`. All three accounts, nine acknowledgement rows, retained ledgers, snapshot lineage and notification history passed preservation checks. No rebaseline or account reset occurred.

**Upload accepted — September 19, 01:19 UTC (September 18, 9:19 PM Boston):** The source upload for `house|house:2026:9116331` returned HTTP 202 at `01:19:37.626758Z`, following two HTTP 503 attempts at `01:19:04.883890Z` and `01:19:10.183070Z`. The authenticated owner dialog now shows one two-page upload created at `01:19:38.83546Z`, status **pending**. Browser access has recovered. The existing Legislative execution `polititrack-legislative-5t8xv`, created at `01:20:14.062023Z`, was observed pending. Do not upload the file again. Extraction, raw cleanup and correction/import acceptance remain unverified; no corrections were submitted during this check. The earlier attempt/retry entries below remain historical evidence.

**Earlier owner-test checkpoint:** secure sign-in succeeded and the existing owner's source-upload form opened for `house|house:2026:9116331`. Before the attempt, the form reported no upload for this filing. The browser file-selection/upload call then stopped responding, and a subsequent browser-state check could not return. No upload receipt was observed; submission, extraction and raw cleanup remain unknown/unverified. The attempt was not repeated and no row corrections were submitted. Do not assume either successful upload or no submission. Three unclear asset labels still require document-specific owner interpretation; preserve all five physical rows and blank ownership.

**Retry check — September 18, 23:09 UTC:** The owner requested another upload attempt. The browser connection again failed to respond before a new submission could be made. An authorized read-only Cloud Logging query for the last day returned no recorded POST requests to this web service’s source-OCR API. This is log evidence only, not a database receipt or proof that the earlier attempt never submitted. No new upload or corrections were submitted by this retry; no production configuration or recovered journal was changed. Reconcile the existing upload status through the authenticated UI before retrying.

Next: monitor the accepted upload through **Refresh processing status** and the existing scheduled producer; finish extraction/cleanup verification, obtain owner review before confirming all rows, and verify reconciliation. Do not resubmit the accepted PDF. Resolve the two Senate OCR warnings separately. Keep issue #182 open. No additional feature, maintenance or Codex-permission authorization is needed. Do not replay the completed rollout or modify old journals. [Final release evidence](releases/2026-09-18-ocr-deployed.md) and its linked receipt contain exact executions, CI and snapshot identities. Earlier entries below are historical checkpoints.

## Historical checkpoint — corrected rollout active at September 18, 20:20 UTC (#182)

Application repair PR #186 merged at `a2a15edb30895ece37b690e50e0f95fb1eaa2649`; exact PR-head OCR CI `35389493194` and Investor Edge CI `35389493190` passed, and the merge tree matches the tested head. Cloud Build `db933dc7-5e85-483f-b7b0-655a0ddf7dc0` succeeded and produced `sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d` in the existing runtime-v2 image repository.

The explicit repair release procedure in PR #187 merged at `db7cd0fd2bb24223a744d219ea04009747a317d7`; all 59 local safety checks and canonical controller CI `35390534977` passed. Installed wrapper `/home/maglothinm/ocr_health_repair_release.py` is SHA-256 `c095e90551a1d96b853a08450af34f9abfedde80ef5504432306c7b8abf90319`. Its read-only preparation verified all live recovered resource/schedule specifications, the repaired build/registry digest and database protections. Both older closed attempts and their receipts are sealed.

**Maintenance is active.** Desktop Commander process `36964` on Beast is running the reviewed wrapper `--deploy`. The four original schedules are paused; Vault remains paused. The controller is draining the existing AI `polititrack-ai-8psnb` and Dashboard `polititrack-dashboard-tqb7f` before obtaining a fresh frozen baseline. Do not interrupt them or launch another controller. New journal: `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-health-repair-a2a15edb3089/ocr-deployment/journal.json`. No repaired-image deployment or final acceptance is claimed yet at this checkpoint.

The earlier recovery's natural scheduled Legislative `polititrack-legislative-sb4pf` completed successfully at `2026-09-18T20:12:39.923230Z`; its creator is the existing scheduler service account. This verifies that recovery's scheduling, not the still-pending repaired rollout. Preserve original journal SHA `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e` and recovered successor SHA `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`.

Next: observe the same process through fresh baseline, pinned-image activation, producer/AI/dashboard successors, independent preservation and published OCR-health acceptance, and original schedule restoration. Authenticate only through secure browser sign-in for the separate upload/correction/cleanup test. The existing sample is selected; its three unclear labels still need document-specific owner review. Keep issue #182 open. [Repair release procedure](releases/2026-09-18-ocr-health-repair-release.md).


## September 18, 20:02 UTC — OCR acceptance failed; recovery verified (#182)

All six runtime resources now retain pinned source `9402f6c9866e919c789845de96f4334058600cee`, image `sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`. The additive OCR inbox migration and read-only image/schema/account check succeeded. Two controlled Legislative runs, two Executive runs, AI and Dashboard succeeded; final acceptance `polititrack-admin-ht9mq` failed with `published_ocr_health_disagrees`.

**Recovery completed:** `polititrack-admin-424v8` verified frozen-baseline preservation. OCR is disabled on Legislative, Executive and web. At `2026-09-18T20:02:20.643694+00:00`, the four original schedules were ENABLED with original configurations; Vault remained PAUSED. No state rewind, history deletion or account change occurred. A Cloud Shell authentication error interrupted the first recovery's web wait; resuming that same recovery completed successfully without duplicate producer submissions. The failed audit and earlier error remain historical evidence.

The actual Cloud Shell controller `/home/maglothinm/ocrv2.py` is v2.2, SHA-256 `bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`; the prior copy remains in `ocrv2.before-recovery-continuation.py`. The original recovered journal still has SHA-256 `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`. Its successor at `/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-continuations/9de6a3cfc21a4ec9b51915301bdaa534/journal.json` is now closed as `recovered_new_image_ocr_disabled`; do not edit/delete/reopen either journal.

Root cause: the dashboard privacy projection stripped the validated OCR `heartbeat_at`. The narrow fix validates only `runtime_mode_evidence.source_ocr` through `safe_metrics`; all other private heartbeat/configuration fields remain filtered. Full dashboard regression coverage and neighboring tests passed locally: **207 passed, 1 PostgreSQL-dependent skip**. Canonical CI and deployment of the correction are still pending at this checkpoint. See [publication correction](releases/2026-09-18-ocr-health-publication.md).

Next: verify canonical CI, build the corrected immutable image, prepare a fresh reviewed release from this recovered configuration, and perform independent publication/OCR-health acceptance. Authenticated owner upload/correction/cleanup and a natural scheduled run remain unverified. The browser is signed out; preserve existing accounts and request secure sign-in when that test is ready. Three unclear sample labels still need document-specific owner review. Keep issue #182 open.


## September 18 repository cleanup — issue #184

Removed the obsolete August 29 `myetf-investor-edge-implementation.zip` installer after verifying the integrated application files remain present and no runtime/workflow consumes the ZIP. Current application code is unchanged. The owner's retention request is to remove obsolete update copies older than September 11 while keeping the two latest useful versions and their dependencies.

Inventory: 134 old merged branches are eligible (122 ancestry-verified and 12 exact-head merged PRs); 231 non-state output artifacts are candidates after retaining the newest two per family and excluding exact pinned evidence. Deletion of branches/artifacts is pending authenticated access; none is claimed complete. Open PRs, unique unmerged work, recent releases, ordinary Git ancestry, production state and pinned recovery/cutover evidence remain intact.

The concurrent OCR continuation at `ebf233ffdffbb7c91bbab90fd281436bd41ab086` is preserved. This cleanup does not deploy OCR, modify runtime/schedules, or certify live health. Existing OCR/runtime release evidence below remains the authority for that separate task. Verification for cleanup is the exact deletion/documentation diff and unchanged application tree; no new runtime run is claimed.

**Historical accepted checkpoint:** 2026-09-15T12:38:15.901975+00:00 — Inbox interruption delay accepted; history preserved.

**Canonical repository:** ID `1349678672`, `maglothinm/MyETF-Intelligence`; default branch `main`.

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

## September 14 accepted predecessor — Investor Edge backfill progress

PRs #173/#176/#177 are merged and deployed. Source `0483e8c1f66a9328ec6f46d1ba003594c9aa75fc`, build `b27a9df0-8c09-42df-a39b-01b1d0f985b8`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:14a8ec467ad9893048086349b8675de8967878c5610cad0071f1a6b1d6d24404` are verified on all six existing resources; web `polititrack-web-00043-29c` serves 100% traffic.

The corrected engine chain succeeded at source `4717b770`; the final CSS-only successor passed a new Dashboard run, preservation audit and vertical-scroll checks. Root and standalone progress views passed six live browser checks. Original history, all observation/profile identities, three accounts, eight acknowledgements and failed-run evidence are preserved. The first Python 3.11 incompatibility was corrected without advancing or resetting its failed AI snapshot. All original producer schedules are ENABLED unchanged; Vault remains PAUSED. No new migration, IAM, scoring/budget or unrelated feature enablement.

[Exact release evidence](releases/2026-09-14-investor-edge-backfill-progress.md) and [receipt](releases/2026-09-14-investor-edge-backfill-progress-receipt.json). Production heads advance naturally; this is bounded feature acceptance, not completion of all historical market outcomes. Gmail delivery configuration remains separate.

## September 14 backfill source completion — historical development evidence

Issue #172 / PR #173 is the isolated backfill-progress implementation. Its
verification is tracked in `docs/validation/investor-edge-backfill-progress-2026-09-14.md`.
The production image/schedules/state described below have not been changed by
source development or tests. Live release acceptance remains required.

## September 11 release — historical accepted predecessor

PRs #169/#171 are merged. All six resources use runtime source `4deb31cb08fc38b0e38928aee609761f6c6579fd`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6bd42784caff11fae8bcec4373331e58986a3bc79216782f682d2ca5107b87bf`, build `960864c8-87bc-4b77-a088-afbb87f85783`. Web `polititrack-web-00040-c2l` serves 100% traffic. Final Runtime CI `34659557574` passed (530 tests, 2 skips; real PostgreSQL), and Investor main CI `34659136667` passed.

Sound defaults on for new browsers; the owner's current browser was enabled. Investor Edge >60.0 and Watchlist/High Priority stage recipient-aware Gmail intent in the existing durable outbox. Operations shows OGE health and inventory; full Signals data loads with compact readable cells and reachable horizontal scrolling. Controlled successors, exact source assets, live narrow-window behavior and natural scheduled Executive `polititrack-executive-md66c` passed.

All prior snapshot metadata, the retained incident evidence, three account rows, eight acknowledgements and notification history match the baseline. All four original schedules are restored unchanged; Vault remains paused. No migration, rebaseline, rewind or unrelated feature activation occurred. Operations controls #164 remain disabled; Current Opportunity #154 remains excluded.

Gmail delivery remains incomplete: Owner-created Google app password has not yet been saved in the prepared Secret Manager form. No successful investor-alert email or inbox receipt is claimed.

[Exact release evidence](releases/2026-09-11-investor-alerts-navigation.md) and [receipt](releases/2026-09-11-investor-alerts-navigation-receipt.json). Runtime heads continue to advance; refresh live evidence for subsequent releases.

## September 9 permanent Legislative recovery — historical accepted release

Runtime source `9f1a59105f2ac7cfa6ed3f764d9ab4b3d5483301`, build `9ad52cb8-5875-4e08-a86c-ea90e512247c`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:916f23124c028467079b305f50681336fc0b1e6e553cdb4fefe491dc2d380ef1` is verified on
all six existing resources. Web revision `polititrack-web-00039-ps5` serves 100% traffic.
PRs #161/#162 passed final exact-head CI, including real PostgreSQL failure,
restart and concurrency scenarios, and were accepted through the live production path.

Legislative completed House 894 / Senate 85, passed complete-source validation
and appended generation 233 to the preserved generation 232 parent. Executive,
AI and Dashboard also published successfully. Natural scheduled Legislative
execution `polititrack-legislative-nmt57` succeeded afterward. The live dashboard reports success.
All four original schedules are ENABLED and Filing Vault remains PAUSED.

The original Legislative failed run, its side-effect flag and all pre-release snapshot metadata
remain unchanged. Current snapshot payloads/manifests verify. Personal account
identities and eight retained acknowledgement rows match their pre-release hashes.
No rebaseline, rewind, IAM expansion or unrelated feature activation occurred.
[Exact release evidence](releases/2026-09-09-legislative-recovery.md).

Collection is independent of per-record notification uncertainty. Pushover
credentials remain absent; successful external alert delivery is not claimed.
Only outbox-compatible images may follow this release. Prior certificates and
the following release records remain historical evidence.

## September 9 durable personal acknowledgement release — issue #159

PR #160 is merged and accepted live. Runtime source `c0eaeb430aa7f665283f9ee560cf72fbe9c257cf`,
build `c84e6510-9825-4c84-b512-cf82d18ed627`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:5428e1333ceff18b7c2e1f7fd46f3e82652b6c2cb7b94d1fbee20b099fa19ec6` was accepted on all six existing
resources. Its web revision was `polititrack-web-r159-persist-0909`; the current release is recorded above.
See [the exact release evidence](releases/2026-09-09-personal-review-acknowledgements.md).

Each person's acknowledgement history is stored in the existing private
PostgreSQL database. Clearing browser data requires signing in again. The owner's
four original acknowledgements have been recovered with timestamps preserved;
password setup was pending at that checkpoint. The owner has since completed sign-in; this recovery did not change credentials or sessions.
Two independent test accounts passed live cookie clearing, renewed sign-in,
Restore/import protections and a fresh web revision, then were disabled.

At the #159 acceptance checkpoint, all original producer schedules were ENABLED and Filing Vault remained PAUSED.
Legislative generation 232 and its original failed-run/guard state were unchanged.
Executive and AI heads were unchanged through the fenced cutover; Dashboard
advanced 332 -> 333
with exact parent continuity. No protected state or personal history was deleted.
That receipt returned ownership to the Legislative repair, now accepted above. The September 8 records below are historical, not current image evidence.

## Operations manual controls in preparation — issue #164

The owner requested Run now buttons in the Legislative, Executive and AI tiles.
Implementation adds owner-authorized dispatch of the existing jobs, durable
request receipts and truthful live completion status. The feature is default off.
Local full regression: 1,208 passed, 36 skipped; final focused checks and exact-head
CI remain required. No production control or permission is enabled by this entry.
The Legislative recovery is now accepted. Manual-control activation requires the explicit handoff and a fresh production baseline.
[Manual run contract](operations-manual-runs.md).

## Production authority

**September 9 recovery accepted:** The current production image and evidence are recorded above and in [the recovery release](releases/2026-09-09-legislative-recovery.md). Runtime v2 remains the sole production authority. Original failure evidence is retained; per-record delivery uncertainty no longer obstructs collection.

**September 8 accepted release:** Issue #155 is live after PR #156 and corrective PR #157. Runtime source `19e894ef1262a86d4e54e24a8a34f6b7f230f688`, Cloud Build `cea78696-8521-45d4-98b8-bdea9e45fc09`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300`. At that historical acceptance, all six resources used that digest and producer configurations persisted the corrected source. Dashboard `polititrack-dashboard-68f7j` committed generation 250 and passed real isolated-browser acceptance before schedules resumed. [Full release evidence](releases/2026-09-08-parser-acknowledgements.md).

The corrected inventory has four manual exceptions: two original Senate and two retained House paper PTRs. Seeding only the real Senate legacy IDs left Senate acknowledged and House active; acknowledge-all, three real refreshes, reload and Restore passed. The served bundle also passed 74 isolated publication-replay tests. The user's browser storage was not changed.

At the September 8 checkpoint, Legislative was blocked at generation 232 after the Senate HTTP 403 run at 10:41 UTC. Its original evidence remains intact; the September 9 release above restores collection; [incident evidence](incidents/2026-09-08-legislative-retry-guard.md). All four original producer schedules are enabled; Vault remains paused, SQL private-only, legacy producers disabled. PR #154 remains excluded. Historical certificates below are not certification of the new image or current all-pipeline health.

Runtime v2 is the production authority. The earlier shadow/blocked description in this file was stale. Phase 5 completed in canonical run `34005780266`, attempt 1, at `9f4303623cf21c3dff434fbb7240c07e6d255174`. Artifact `9981508660` has archive SHA-256 `c5094a1677712e413425e118f29dd0fc1f870c5bc712879fbc2223f2b9c2f7d0`. Its `phase5-complete.json` independently matches checksum `0006ed72a2a42308c21084bee236c45f4e9e17df4803c244caf03a520028dcb7` and result `phase5_complete`.

That certificate records the original production transfer. The subsequent concurrency repair and natural-schedule recovery have separate evidence; the original certificate is not a certificate for the repaired image.

## Runtime recovery

PR #142 repaired snapshot-reader/writer concurrency. The September 6 recovery used immutable image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`, with producer source revision `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`, verified as an ancestor of current main.

Scheduler reactivation run `34046362664` succeeded. All four producer schedulers are enabled. AI uses `14,44 * * * *` in America/New_York; Dashboard retains `2,17,32,47 * * * *` in Etc/UTC. Filing Vault lifecycle remains paused. Cloud SQL public IPv4 remains disabled and its private network remains `polititrack-runtime-v2`.

Natural-certification run `34047080001` failed in preflight because its Dashboard timezone assertion contradicted both Terraform and the live Scheduler. PR #151 corrects the assertion and selects logs from the recorded activation timestamp instead of a sliding four-hour window. It does not change production schedules or runtime code.

Corrected certification run `34059488724`, attempt 1, job `101557337973`, completed successfully at control revision `db080d413b5e804a335f575071a62d48a9d4083b`. Artifact `9997087643` independently matches archive SHA-256 `6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`. Its certificate reports `runtime_v2_natural_ai_schedule_certified`, cleanup pending false, and temporary execution/logging authority removed. Both internal evidence hashes were independently verified.

## Live functionality

**Historical September 6 verification:** Independent GCP reads showed successful Legislative, Executive, AI, and Dashboard executions. AI natural runs committed generations 63 and 64 at 17:17 and 17:48 UTC. Public `/readyz` returned ready and `/` returned HTTP 200 with the same snapshot hash at 20:56 UTC. The certified durable heads are Legislative 82, Executive 46, AI 70, and Dashboard 79, all bound to repaired source revision `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`. The served hash matches the certified Dashboard 79 head. AI executions `polititrack-ai-rss97` and `polititrack-ai-db5vt`, followed by `polititrack-dashboard-vl4p6`, were independently checked in GCP: all succeeded, used the approved digest, and were created by the existing Scheduler service account.

## Preserved boundaries

No replatform, state initialization, rewind, rebaseline, protected artifact replacement, legacy route activation, or Phase 6 decommissioning is authorized. The original Phase 5 evidence and all recovery predecessors remain retained. Runtime database/snapshot authority must not be confused with the pre-cutover GitHub artifact authority described in historical documents.
