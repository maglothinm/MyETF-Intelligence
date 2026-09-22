# Investor Edge evidence-first release

## September 22 Investor Edge evidence-first update (#219) — merged, Windows activation pending

PR #220 merged as 7e33fc39aed897a2ae22b78f3ff73bece475a258. Its complete tree
matches tested head 6582171922f0def04ca9dcfd3bd650b13fc0611f. All four CI workflows
passed: Investor Edge 35726290251, Runtime v2 35726290276, Source OCR 35726290244,
and Current Opportunity 35726290341. Focused local tests: 194 passed. Root and
standalone responsive fixtures passed at 1280/700/390 pixels; keyboard, filters,
closed defaults, deep links and actual zero/adverse result preservation verified.

Windows returned user-canceled elevation (exit 1). Production remains at
f85a40f6b7b609ad8eec5c899c368d106fedd7c1; all three services remain Running/Automatic.
No activation receipt or live deployment claim. Do not retry elevation without
owner action and do not rerun Finish PolitiTrack Setup or backup provisioning.

A Desktop shortcut named **Activate Investor Edge Update** now opens the reviewed
package at C:\ProgramData\PolitiTrack\releases\edge219\Activate.ps1. It requests
normal Windows approval, activates only merged source with a scheduler-only restart,
uses the existing locked dashboard producer, then verifies live HTTP and snapshot
continuity. The updater refuses source downgrades. Completion is established only
by backups/edge219-complete.json plus its HTTP and continuity receipts.

Pre-release baseline: 4,436 snapshot headers; cutoff 2026-09-22T12:18:30.870429+00:00;
header digest b6065022e955b62f73c5a2b17b94aeae. Evidence is in
backups/edge219-snapshot-baseline.json. Keep #219 open until live verification.
Canonical repo ID 1349678672. Beast-local PostgreSQL remains sole authority.
Preserve all histories, untracked legislative-source-status.json and backup repair.
No cloud reactivation, scoring changes, state rebaseline or extra schedules.
OGE failures remain separate. Progress timestamps are population-wide, not per-profile.
