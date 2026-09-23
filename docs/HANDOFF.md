# PolitiTrack active handoff

## September 23 #225 — initial activation verified; CSV repair awaits Windows approval

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
The owner-requested retry successfully activated the original two-part fix
`c46dcef215e4872912ba2995b67cb117725b05e2` at **11:15:40 UTC**, using normal
Windows administrator approval and the existing web/scheduler controls. PostgreSQL
did not restart. The untracked source-status file hash matched across cutover.
The normal native scheduler's dashboard run at 11:17 succeeded on the new source.

Live publication exposed a CSV reader limit in the new evidence augmentation:
a retained **208,461-character** field exceeded the **131,072-character** default.
The AI run failed before committing a replacement snapshot; AI generation **852**
remains intact. The repair is now tested and merged in
[PR #229](https://github.com/maglothinm/MyETF-Intelligence/pull/229) as
**0c2ab975a837a1d2a28ca4e041019d0103413b54**, from tested head
`632f4343f54dad02a5347da342af31bf6074034b`. It temporarily sizes the reader to the
generated file, restores the prior limit, and does not truncate retained fields.

Local tests: **41 focused and 400 regression passes**. The new integration test
reproduced the original exact error and passed after repair. Offline finalization
of current immutable snapshot copies exported all **311** retained analysis rows
with discovery objects, unchanged history bytes and the original CSV limit restored;
no production/provider/notification writes occurred. All repair-head CI workflows
completed successfully on attempt **1**:
[Current Opportunity 35854077869](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077869),
[Runtime v2 safety 35854077842](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077842),
[Investor Edge regression 35854077909](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077909).
The original feature already passed four workflows, including PostgreSQL manual-OCR
outage/replay coverage, plus 547 local regression passes / 7 PostgreSQL skips and
10 interface/accessibility passes. The legacy analyst remains unchanged.

The repair's subsequent Windows prompt was canceled, as reported by Windows at
approximately **11:27 UTC**. Its elevated script did not run. No automatic retry
was made. Application/config remain **c46dcef**; only the initial release is active.
At **11:27:43 UTC**, readiness is HTTP 200, old AI generation 852 has no discovery
ledger, and dashboard generation **1617** serves the new export routes with **0**
persisted evidence objects. Its 311 AI rows have fallback evidence objects; that
does not establish the requested durable publication. Live acceptance remains false.

The September 22 continuity fingerprint and all **4,693** headers before
`2026-09-23T11:03:40.422575+00:00` remain unchanged, with the latter retaining digest
`8135b8a25206577231f3a8b3b9256b64`. There are zero broken snapshot parent links.
Database, web and scheduler are running. No rebaseline, legacy/cloud writer,
source re-upload, original-upload approval, or rollback across new snapshots occurred.
The original 30-page upload remains **needs_review** with its existing generation
693 extraction receipt. Its live pending-upload outage scenario was not recreated.

### Next safe action

The owner's Desktop shortcut **Activate PolitiTrack Discovery Update** now targets
the repaired merged release **0c2ab975a837a1d2a28ca4e041019d0103413b54**, with tested
head **632f4343f54dad02a5347da342af31bf6074034b**. It verifies the unchanged prepared
activation package's SHA-256, prevents overlapping launcher instances, requests
normal Windows elevation and reports its result. Do not bypass UAC. The owner has
been asked whether they are connected and ready for another prompt or prefer the
shortcut. The existing `releases/discovery225/Apply.ps1` supports these pinned args.

After approval, verify the activation receipt and continuity, then run the existing
locked AI and dashboard producers with trigger `deployment_validation` and check
persisted ledger, served JSON/CSV equality, revisions and hashes. No new schedule
is needed. Keep #225 open until acceptance. Current Opportunity remains OFF;
missing historical quote provenance must remain unknown. Do not alter the original
upload to manufacture outage evidence. See [DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md).
