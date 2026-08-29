# PolitiTrack branding migration

PolitiTrack is the product name. This change updates user-visible application, dashboard, alert, analyst, verification, and documentation text without changing compatibility-sensitive production identities.

## Preserved legacy identifiers

The following names remain intentionally unchanged until a separate, tested repository and state migration:

- GitHub repositories and URLs: `maglothinm/MyETF-Intelligence` and the rollback source `maglothinm/MyETF`.
- Durable state and artifact paths, including `.trade-tracker/`, tracker-state artifact names, cache keys, completed IDs, and paper-portfolio ledgers.
- Existing `MYETF_*` environment variables and secrets, including `MYETF_SOURCE_REPO` and any deployed SMTP secret names.
- GitHub Actions workflow filenames, workflow identities, concurrency groups, and the display name `Import migrated MyETF state`.
- Installer boundary markers such as `MYETF-GOVERNMENT-TRADE-TRACKER` and the matching `.gitignore` markers used for idempotent upgrades.
- Existing logger names, temporary state filenames, HTTP client identifiers, and migration inventory paths where renaming could disrupt monitoring, WAF behavior, diagnostics, or recovery procedures.
- Legacy distribution and provenance archive names, including `MyETF-government-trade-tracker-fast-track.zip` and `myetf-investor-edge-implementation.zip`.
- Historical recovery reports whose titles describe the legacy MyETF repository at the time of recovery.

## Later migration

Rename the authoritative GitHub repository and compatibility-sensitive identifiers only after the rebranded code is green, current production state has been exported, workflows are disabled for cutover, restoration is tested, and rollback remains available. The migration must not create a new silent baseline or share mutable state between production and simulations.
