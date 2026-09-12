# PolitiTrack active handoff

Updated **2026-09-12T00:24:24.042666+00:00 — investor alerts, OGE health and navigation deployed**.
Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default `main`.

## Current task and remaining action

The owner authorized full release. PRs #169/#171 are merged and the application changes are live.
Gmail delivery remains incomplete: Owner-created Google app password has not yet been saved in the prepared Secret Manager form. No successful investor-alert email or inbox receipt is claimed.

The owner is signed into Google and created an app password named “PolitiTrack alerts.” A Google Cloud Secret Manager form named `polititrack-gmail-app-password` was prepared for their private entry. Do not ask for the password in chat or recreate account credentials. Complete this secure handoff, bind only the existing AI job's versioned Gmail secrets with narrow access, and verify provider acceptance/inbox receipt separately. The release tools and private evidence are in `C:/Users/maglo/Documents/Codex/2026-09-10/polititrack-alerts-navigation/release-20260911`. Refresh live configuration before any further mutation; schedules are already restored, so do not rerun the initial cutover.

## Current production

- Runtime source: `4deb31cb08fc38b0e38928aee609761f6c6579fd`; tested tree `db330aad8b7b1f1a72f13942d46a2e540d26d1ae`.
- Image on all six existing resources: `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6bd42784caff11fae8bcec4373331e58986a3bc79216782f682d2ca5107b87bf`.
- Build: `960864c8-87bc-4b77-a088-afbb87f85783`; web `polititrack-web-00040-c2l`, 100% traffic.
- Final Runtime CI `34659557574`: 530 passed, 2 skipped, real PostgreSQL integration passed. Investor main `34659136667` and Runtime main `34659244278` succeeded.
- Controlled Legislative, Executive, AI and Dashboard successors passed with exact prior-parent continuity. Natural scheduled Executive `polititrack-executive-md66c` succeeded.
- Full Signals JSON loads successfully; compact cells/popups and responsive scrolling passed live checks. Sound is enabled in the owner's existing browser.
- All four original producer schedules are ENABLED unchanged. Filing Vault remains PAUSED.

[Exact acceptance evidence](releases/2026-09-11-investor-alerts-navigation.md) and [machine-readable receipt](releases/2026-09-11-investor-alerts-navigation-receipt.json). Accepted heads in those receipts are historical observations and advance naturally.

## Preservation and release boundaries

All pre-release snapshots, original failure/side-effect evidence, three accounts, eight acknowledgement rows, and previous notification history were preserved. No schema migration, rebaseline, rewind or alternate writer was introduced. Personal review enablement, allowed origin and existing sign-in are intact. Prior recovery and Phase 5 certificates remain historical; this is bounded release acceptance.

Only recipient-aware, outbox-compatible images may follow this release. Keep the per-profile crossing journal and pending/held/uncertain/accepted delivery distinctions. Missing provider credentials must not stop collection. Do not clear holds, delete original failures, reset reviews, or populate production with a synthetic qualification test.

## Other work remains separate

Operations controls #164/#165 are present in source but their enablement remains off; their schema/IAM activation was not included. Current Opportunity #154 remains excluded. Preserve existing production ownership and coordinate any new release from fresh live evidence.

Historical references: [September 9 recovery](releases/2026-09-09-legislative-recovery.md), [personal acknowledgements](releases/2026-09-09-personal-review-acknowledgements.md), [Operations activation contract](operations-manual-runs.md), [feature contract](investor-alerts-navigation.md).
