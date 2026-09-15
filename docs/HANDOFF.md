# PolitiTrack active handoff

Updated **2026-09-15 — Inbox interruption delay implemented; release verification pending**.
Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default `main`.

## Current task — sustained Inbox interruption alerts (#179)

The owner requested a sensible delay for agent offline/online Inbox noise.
Implemented a 60-minute continuous published-evidence threshold, one warning per
branch episode, and recovery only after a reported interruption. Persisted timers
survive reloads and concurrent tabs; intermediate successful runs reset them.
Operations stays immediate, and external notifications and stored history remain
unchanged. Local notification checks: 41 passed. Generated dashboard, notification
wrapper and insight checks: 82 passed. Canonical CI and live release are pending.

Branch `codex/inbox-outage-delay-20260915`, based on canonical main `02dfe412`
plus the local diagnosis below. Next: verify PR CI, build an immutable image,
update only the existing Dashboard publisher, verify its successor and served
bundle, and preserve all other existing resource settings and state.

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

## September 14 current release — Investor Edge backfill progress accepted

PRs #173/#176/#177 are merged and deployed. Source `0483e8c1f66a9328ec6f46d1ba003594c9aa75fc`, build `b27a9df0-8c09-42df-a39b-01b1d0f985b8`, image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:14a8ec467ad9893048086349b8675de8967878c5610cad0071f1a6b1d6d24404` are verified on all six existing resources; web `polititrack-web-00043-29c` serves 100% traffic.

The corrected engine chain succeeded at source `4717b770`; the final CSS-only successor passed a new Dashboard run, preservation audit and vertical-scroll checks. Root and standalone progress views passed six live browser checks. Original history, all observation/profile identities, three accounts, eight acknowledgements and failed-run evidence are preserved. The first Python 3.11 incompatibility was corrected without advancing or resetting its failed AI snapshot. All original producer schedules are ENABLED unchanged; Vault remains PAUSED. No new migration, IAM, scoring/budget or unrelated feature enablement.

[Exact release evidence](releases/2026-09-14-investor-edge-backfill-progress.md) and [receipt](releases/2026-09-14-investor-edge-backfill-progress-receipt.json). Production heads advance naturally; this is bounded feature acceptance, not completion of all historical market outcomes. Gmail delivery configuration remains separate.

Issue #172 deployment is complete. No additional owner feedback is needed. Do not rerun the release; refresh live evidence before any future changes.

## Preserved concurrent release handoff

The owner authorized full release. PRs #169/#171 are merged and the application changes are live.
Gmail delivery remains incomplete: Owner-created Google app password has not yet been saved in the prepared Secret Manager form. No successful investor-alert email or inbox receipt is claimed.

The owner is signed into Google and created an app password named “PolitiTrack alerts.” A Google Cloud Secret Manager form named `polititrack-gmail-app-password` was prepared for their private entry. Do not ask for the password in chat or recreate account credentials. Complete this secure handoff, bind only the existing AI job's versioned Gmail secrets with narrow access, and verify provider acceptance/inbox receipt separately. The release tools and private evidence are in `C:/Users/maglo/Documents/Codex/2026-09-10/polititrack-alerts-navigation/release-20260911`. Refresh live configuration before any further mutation; schedules are already restored, so do not rerun the initial cutover.

## Current production

Source `0483e8c1f66a9328ec6f46d1ba003594c9aa75fc`; image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:14a8ec467ad9893048086349b8675de8967878c5610cad0071f1a6b1d6d24404`; build `b27a9df0-8c09-42df-a39b-01b1d0f985b8`; web `polititrack-web-00043-29c` at 100%. All four producer schedules are ENABLED, Vault remains PAUSED. The release receipt records exact controlled executions, snapshot hashes, live progress counts and preservation checks. Earlier September 11 tools and credentials handoff below remain historical/context only.

## Preservation and release boundaries

All pre-release snapshots, original failure/side-effect evidence, three accounts, eight acknowledgement rows, and previous notification history were preserved. No schema migration, rebaseline, rewind or alternate writer was introduced. Personal review enablement, allowed origin and existing sign-in are intact. Prior recovery and Phase 5 certificates remain historical; this is bounded release acceptance.

Only recipient-aware, outbox-compatible images may follow this release. Keep the per-profile crossing journal and pending/held/uncertain/accepted delivery distinctions. Missing provider credentials must not stop collection. Do not clear holds, delete original failures, reset reviews, or populate production with a synthetic qualification test.

## Other work remains separate

Operations controls #164/#165 are present in source but their enablement remains off; their schema/IAM activation was not included. Current Opportunity #154 remains excluded. Preserve existing production ownership and coordinate any new release from fresh live evidence.

Historical references: [September 9 recovery](releases/2026-09-09-legislative-recovery.md), [personal acknowledgements](releases/2026-09-09-personal-review-acknowledgements.md), [Operations activation contract](operations-manual-runs.md), [feature contract](investor-alerts-navigation.md).
