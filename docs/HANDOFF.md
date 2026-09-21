# PolitiTrack active handoff

## September 21 Windows migration — preparation in progress (#211)

The owner explicitly requested all production processing on Beast, with Windows
startup services and no Google Cloud hosting. Canonical repository ID 1349678672
remains unchanged. Branch `codex/beast-local-runtime-20260921` adds a native
Windows host for the existing Runtime v2 jobs and a loopback-only dashboard.

All four cloud schedules were paused and public web ingress restricted to
internal before the final full SQL export. Cloud resources have not yet been
retired. Export operation `f9a96409-4593-449e-b8af-95f900000032` and source audits
are being checked. No local authority receipt has been activated. PostgreSQL 16,
Python, Chromium and OCR tools are installed on Beast; local services have not
yet been registered. Final continuity, Windows service and cloud retirement
receipts must supersede this preparation checkpoint before completion is claimed.

Focused validation: 86 tests passed and 30 PostgreSQL variants skipped locally.
Existing states, identifiers, account data, OCR evidence and delivery history
must migrate in full. Current Opportunity remains off and Vault lifecycle stays paused; the enabled
Vault API is preserved with private local file storage.

Next safe action: finish the frozen SQL export; restore and compare all-table
fingerprints; validate native Windows services; activate local authority only
after continuity passes; preserve recoverable backups before retiring cloud.

Earlier release evidence remains in PROJECT_STATE and docs/releases.
