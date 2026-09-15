# PolitiTrack active handoff

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
