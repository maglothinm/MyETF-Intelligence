# PolitiTrack active handoff

## Current continuation — September 18, 2026: Cloud Shell access unavailable (#182)

The continuation recovered [the controller takeover](releases/2026-09-18-ocr-controller-takeover.md) and its tested identity patch from canonical `main` at `108d5315938a48d3bd33c8448e8ce99f23407285`. Existing feature and bounded-maintenance authorizations remain recorded; another authorization is not the remedy for the access or tool restrictions.

Beast was online. Its release checkout was clean, detached at tested runtime source `9402f6c9866e919c789845de96f4334058600cee`, with the canonical GitHub remote. A fresh remote ref read confirmed the main commit above. No existing inventory diagnostic, production job, migration or release test was rerun.

**New access evidence:** the connected cloud browser had no existing Cloud Shell session. Opening Cloud Shell and one reload each returned **502 Bad Gateway / [Errno 111] Connection refused**. Beast's Cloud SDK reported no existing Cloud Shell SSH key; its key-generation prompt was declined and exited with `SSH key generation aborted by user`. No new SSH credentials or session authorization were created. This connection failure does not establish a GCP permissions problem.

**Still outstanding:** read and reconcile the actual Cloud Shell journal at the reported workspace `/home/maglothinm/polititrack-ocr-182-v68vldej`; install the tested controller correction; establish a permitted journal-preserving continuation; then complete the coordinated baseline, additive migration, pinned-image rollout, authenticated upload/correction/cleanup test and independent live OCR-health acceptance. The owner-reported `recovered_original_configuration` journal was not inspected, changed or reopened during this continuation.

No production resource, scheduler, database, account or controller file was changed. The previously verified state remains the latest available evidence: four production schedules enabled, Filing Vault paused, OCR undeployed. Those statuses were not re-certified by a new live inventory in this continuation. The earlier deployment-helper safety rejection was neither retried nor cleared; an accessible Cloud Shell session alone does not clear it.

Next safe action: restore access to the existing Cloud Shell workspace through a permitted connection, inspect the retained journal, and continue only with an operation permitted by the tool's safety controls. Preserve the recovered attempt and every receipt. Keep issue #182 open.

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
