# PolitiTrack project state

## September 23 #232 - complete filer directory and search, source validation

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, branch
`codex/all-filer-profiles` from `main` at `85b13ca52feb4346a0581561333f755d6ca3cf7c`.
Beast is still running `0c2ab975a837a1d2a28ca4e041019d0103413b54`; this checkpoint
does not claim the directory change is deployed.

The Investor Edge publisher now includes every named retained filer, including
filing-only/review-required entries and transactions with no eligible equity
purchases. Existing disclosed-owner identities remain separate. The old 40-profile
selection no longer limits visibility or admission to the fair historical queue.
The existing 30-observation and 40-market-request per-run budgets, 40-trade history
window, retention policy, scoring methodology/hash and single writer are unchanged.
Known catalog entries do not manufacture trades, prices, observations or reviews.
Missing evidence is explicitly unknown; source-review counts and reasons are
published in complete JSON and CSV. All prior profiles and observations remain
retained through the existing snapshot path.

Both root and standalone views have name/owner search, history-status filters,
match counts, clear controls and complete CSV download. Name terms match in either
order, case-insensitively; matching incomplete profiles are revealed in Building
history. Root filters and focus survive refresh. Existing assessment eligibility,
zero/negative measured values and notification rules are preserved.

Validation: **412 local regression passes**, including Node/jsdom/axe checks;
the run used UTF-8, matching Beast's launcher (one default-Windows-codepage test
read failed before rerunning under that configuration). Four real Edge browser
checks passed: root/standalone at 1280 and 390 pixels, with no JavaScript errors.
An offline replay of AI generation 854, Legislative 1517 and Executive 715 produced
**1,028 owner profiles covering all 975 known filer names**, including Donald Trump.
It preserved all 62 prior profile identities, 1,519 observations and all history
ledger bytes, made zero provider calls, and took about 7.2 seconds to refresh.
This offline result is not live acceptance. Trump remains building history with
his original source review pending; the suspected municipal-bond/CI classification
is not silently rewritten or accepted by directory publication.

Next: exact-head canonical CI and merge; activate through existing Beast service
boundaries with normal Windows administrator approval, then use the existing
locked AI/dashboard producers. Verify complete directory/export agreement, live
search, per-run budgets, prior snapshot fingerprints, untracked files and the
unchanged original manual-upload review receipt. Keep #232 open until live checks.
Issue #225 retains its separate pending-upload outage acceptance boundary; do not
re-upload, requeue, approve, rebaseline or revive cloud/legacy writers for this work.


## September 23 #225 — activated and discovery publication verified

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Beast application/config are **0c2ab975a837a1d2a28ca4e041019d0103413b54**, merged in
[PR #229](https://github.com/maglothinm/MyETF-Intelligence/pull/229) after exact-head
CI on `632f4343f54dad02a5347da342af31bf6074034b`. This includes the two-part fix
from [PR #226](https://github.com/maglothinm/MyETF-Intelligence/pull/226).
Both activations used normal Windows administrator approval and the existing
web/scheduler service controls. PostgreSQL remained on PID 25732. The repaired
release activated at **2026-09-23T11:29:40.0382451Z**. Source and local configuration
agree; no cloud/legacy producer or new schedule was enabled.

### Live acceptance

At **2026-09-23T11:32:31.129606+00:00**, the existing canonical AI and dashboard writers had
committed and served the discovery evidence. The initial publication used controlled invocations
tagged `deployment_validation`, using the ordinary namespace locks, restore,
validation, atomic commit and unchanged private Beast job configuration. They
were not new scheduled writers or manual database edits. The existing native
scheduler then independently republished the same evidence on the repaired source,
finishing at **2026-09-23 11:32:19.599653+00:00**, run `3c2d8b46-76ab-41f2-b979-86add4eb9c59`. The
dashboard generation below is that automatic scheduled publication.

- AI generation **853**, SHA-256 `5b06047efd7d010f00139b03ac808457a938990fa79bf95683b99773bf25f83f`.
- Dashboard generation **1619**, SHA-256 `46322226bd568b30cc0276a5c4a789c134961261521e1864c625f4fde560fb87`.
- **10,899** persisted transaction evidence objects;
  **10,899** published objects; statuses: **10,899 unknown**.
- All **311** published AI rows contain `information_value_at_discovery`.
- Dedicated JSON and CSV objects agree exactly and match the persisted AI ledger.
- Both new exports, existing AI JSON/CSV, and dashboard scripts return HTTP 200
  and match committed snapshot bytes. Readiness is 200. Authentication and Host
  rejection checks pass.
- Both immutable-history fingerprints remain intact: 4,511 headers from September
  22 and **4,693** before `2026-09-23T11:03:40.422575+00:00`, the latter retaining
  digest `8135b8a25206577231f3a8b3b9256b64`. The complete chain has **0** broken
  parent links. The activation script also verified all pre-existing untracked
  files before restarting writers. No state reset, rebaseline or user-data deletion.

Current Opportunity remains **OFF**. Legacy prices do not establish verified
first-discovery quote quality and comparable price basis; those records correctly
remain `unknown`, with retained inputs and explicit reasons. Do not invent missing
historical quotes or treat unknown as a measured comparison. No qualification or
notification rule was changed by this evidence feature.

### Repair and validation

The first live AI publication attempt exposed a generated CSV field longer than
Python's default reader limit. It failed before snapshot commit, preserving AI
generation 852. PR #229 temporarily sizes that reader to its own generated file
and restores the prior setting, preserving all retained cells and analysis history.
The regression reproduced the original failure, then passed. Local focused checks:
**41 passed**; broad regression: **400 passed**. Offline finalization of actual
snapshot copies exported all 311 rows, including a **208,461-character** cell,
with unchanged history and no production/provider/notification writes.

All three repair-head CI workflows succeeded on attempt **1**:
[Current Opportunity 35854077869](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077869),
[Runtime v2 safety 35854077842](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077842),
[Investor Edge regression 35854077909](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077909).
The original two-part change passed all four CI workflows, including real
PostgreSQL manual OCR outage/commit/replay coverage and browser tests. Its Windows
baseline was 547 regression passes / 7 local PostgreSQL skips plus 10 interface
passes. The preserved legacy analyst remains unchanged.

### Remaining boundary

The original 30-page upload still has status **needs_review**
and its original committed extraction receipt
`fe768ffad0909dbba9095b89615561a5fc3c259423f4a22b191737fbe5e50a3f`. It completed OCR before this release;
it was not re-uploaded, requeued or approved, and review-before-import remains.
Its completion is not proof of the new live outage-independent queue path.
Keep [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225) open for that
remaining live acceptance evidence or explicit owner acceptance of the isolated
proof. Do not manufacture it by changing the original upload. The implementation
passed injected-outage tests and an isolated replay of its committed receipt.

The Desktop activation shortcut is pinned to the repaired release and recognizes
an existing activation receipt. No further restart is required for this version.
Continue normal Beast operation; monitor future manual-upload processing through
the existing maintenance receipts and collector health. No new monitor or schedule
was created by this task. See [DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md).

## Prior operational checkpoints

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

## Earlier operational checkpoints

## September 23 #225 — activated; large CSV field repair awaiting release

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`.
Beast successfully activated `c46dcef215e4872912ba2995b67cb117725b05e2` at
11:15:40 UTC after normal Windows administrator approval. Web and scheduler
restarted; PostgreSQL PID 25732 did not restart. Both pre-change history fingerprints
remain intact, including 4,693 headers before 11:03:40 UTC, with zero broken links.
The preserved untracked source-status file matched SHA-256
`126f9de9239dc5140c5885b71593b7e38391a0d60d522fa0a306cf53bc386aa7` after cutover.

A controlled invocation of the existing locked AI writer at 11:16:29 UTC failed
before snapshot commit: the new discovery CSV augmentation read a retained field
larger than Python's default 131,072-character CSV limit. The prior AI generation
852 remains authoritative. The normal scheduled dashboard run at 11:17 succeeded
on the activated source. Activation is proven; persisted discovery publication is
not yet accepted. No rollback across its new snapshots was attempted.

Branch `codex/discovery225-large-csv` fixes only that generated-export read: raise
the temporary reader limit to the actual file size and restore the previous
process-wide limit in `finally`. Do not truncate retained cells or rewrite analysis
history. The integration regression reproduced the original exact CSV error and
passes after the repair. Focused tests: 41 passed. Broader regression: 400 passed.
Offline finalization of actual retained snapshot copies exported all 311 analysis
rows, including a 208,461-character field, with every discovery object present,
unchanged analysis-history bytes and the original reader limit restored. No
provider, notification or production-state writes occurred in that offline check.

Next: wait for exact-head canonical CI, merge tested repair source, activate it
through the existing Beast service controls and normal Windows elevation, then
run the canonical AI/dashboard writers and verify their persisted evidence against
served JSON and CSV. Do not close #225 or claim live evidence publication yet.
The original 30-page upload is still needs_review with its original committed
receipt; do not re-upload, requeue or approve it for a demonstration. Its live
outage scenario was not recreated. Cloud/legacy producers remain retired.

## Earlier operational checkpoints

## September 23 activation retry for #225 — Windows approval canceled

The owner explicitly requested activation. Canonical repository ID 1349678672,
`maglothinm/MyETF-Intelligence`, main `52e75335a6643adcc2c0a43c90510e84a46114fe`.
The prepared release remains implementation merge
`c46dcef215e4872912ba2995b67cb117725b05e2`, tested at
`e5653120d4cd9d16303ec1ba3eda5488c1e2548e`. Main differs only in operational
documentation. Session branch: `codex/discovery225-live-activation` (documentation only).

One normal Windows elevation request was made at approximately 11:03:40 UTC.
Windows returned `The operation was canceled by the user`, observed at 11:06:25 UTC.
The elevated activation script did not start. No prompt remains active, no release
activation receipt exists, and no automatic retry was made after that cancellation.

Read-only acceptance at **11:06:58 UTC** confirms application/config still use
`dfb5c66ffc51b30b8afbdc283dbe10def4723f89`. Database/web/scheduler remain
Running/Automatic with unchanged PIDs **25732 / 24620 / 25956**. Readiness is HTTP
200. AI generation **851** has no discovery ledger; dashboard generation **1616**
still serves the previous release and discovery JSON/CSV routes are HTTP 404.
Existing assets match committed snapshots; upload authentication and invalid-Host
rejection pass. Activation and autonomous discovery reporting remain **unverified**.

All **4,693** snapshot headers before `2026-09-23T11:03:40.422575+00:00` retain
digest `8135b8a25206577231f3a8b3b9256b64`; the older September 22 checkpoint also
matches. The complete snapshot chain has zero broken parent links. This is a
read-only preservation fingerprint, not a state rebaseline. The latest recorded
routine physical backup completed 00:02:23 UTC with `pg_verifybackup` passed,
manifest SHA-256 `dfd22e31219f36342aa37c1bf0909ce98a0214a0442db134cdc5a6706d8c8062`.
No source changes, configuration changes, service restart, original upload change,
new producer, cloud activation or legacy restore was performed by this attempt.

The original 30-page upload remains **needs_review**, with its existing Executive
generation 693 receipt. Its earlier OCR completion does not prove this release's
outage-independent path. Do not re-upload or requeue it for a demonstration.

The four exact-head CI runs remain successful on attempt 1:
[Source OCR 35770240188](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240188),
[Runtime v2 35770240147](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240147),
[Current Opportunity 35770240223](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240223),
[Investor Edge regression 35770240357](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240357).
The prior source checks remain 547 regression passes / 7 local PostgreSQL skips,
10 interface/accessibility passes, and final focused 31 passes / 1 skip; real
PostgreSQL cases passed CI. No product source changed, so these suites were not
repeated for this operational retry. Local launch/verification helpers passed
PowerShell syntax/Python compilation checks; the launcher was not executed.

### Next safe action

The owner's Desktop now contains **Activate PolitiTrack Discovery Update**.
This shortcut opens the prepared pinned package via normal Windows administrator
approval, checks its SHA-256, prevents overlapping launcher instances, and reports
whether the existing services restarted. It was created but not launched. The
package remains `C:\ProgramData\PolitiTrack\releases\discovery225\Apply.ps1`.
Do not bypass UAC or repeatedly reopen a canceled prompt.

After the owner opens that shortcut and approves Windows elevation, verify the
activation receipt, current services/source, both immutable-history checkpoints,
then normal AI/dashboard publication and live JSON/CSV equality with the persisted
ledger. Keep [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225) open
until live acceptance. Current Opportunity is still OFF; incomplete historical
discovery provenance must remain unknown. Existing single-writer ownership and
review-before-import remain required. See [DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md).

## Previous operational checkpoints

## September 22 independent manual OCR and discovery evidence (#225) — merged; activation blocked

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Implementation branch `codex/manual-ocr-discovery-evidence`; PR [#226](https://github.com/maglothinm/MyETF-Intelligence/pull/226)
merged to main as `c46dcef215e4872912ba2995b67cb117725b05e2`.
Its source tree matches tested head `e5653120d4cd9d16303ec1ba3eda5488c1e2548e`.
The follow-up `codex/discovery225-activation-handoff` contains operational documentation only.

### Delivered source

Authenticated, allowlisted manual uploads for known Executive filings receive a
separate maintenance snapshot before fresh OGE collection, inside the existing
Executive lease. Collector failure cannot erase that committed extraction. The
maintenance receipt cannot advance collector freshness. Automatic-source limits,
review before import, post-commit acknowledgement and the single writer remain.

AI and Current Opportunity now retain per-transaction `information_value_at_discovery`
evidence with JSON/CSV/dashboard reporting. A first usable quote is immutable;
missing required evidence is `unknown`. Legacy prices retain their limitations.
The evidence describes securities and does not score public officials. See
[DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md). The legacy analyst is unchanged.

### Tests and merge evidence

Local regression: **547 passed, 7 skipped** (PostgreSQL cases); interface and
accessibility: **10 passed**. Final focused check: **31 passed, 1 skipped**.
The real PostgreSQL cases passed in canonical CI, including replay without duplicate
extraction/import, independent maintenance commits, and separate collector health.
All four exact-head runs completed successfully on attempt **1**:

| Workflow | Run |
|---|---|
| Source upload and OCR | [35770240188](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240188) |
| Runtime v2 safety | [35770240147](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240147) |
| Current Opportunity | [35770240223](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240223) |
| Investor Edge regression | [35770240357](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240357) |

### Live truth at 2026-09-22 19:01 UTC

Windows reported that the normal administrator prompt was canceled. Activation
did **not** start; there is no activation receipt for this release. Installed
application/config remain `dfb5c66ffc51b30b8afbdc283dbe10def4723f89`.
Database, web and scheduler remain Running/Automatic, with unchanged PIDs 25732,
24620 and 25956 respectively. Readiness is HTTP 200. The new discovery JSON/CSV
routes are still HTTP 404; AI generation 819 has no discovery ledger, and dashboard
generation 1551 is still on the previous source. Autonomous live reporting is
**not yet verified**. Existing AI/dashboard assets match their committed snapshot.
Upload authentication and invalid-Host rejection remain effective.

The originally pending 30-page upload changed during this session, before this
release: a normal successful Executive collection reached OCR at 18:41 UTC and
completed all 30 pages at 18:43 UTC. It is now **needs_review**, with reason
`upload_confirmation_required`, committed in Executive generation **693**, SHA-256
`fe768ffad0909dbba9095b89615561a5fc3c259423f4a22b191737fbe5e50a3f`.
The raw inbox payload was removed by normal post-commit cleanup. No owner approval
or import was performed. Do not re-upload, requeue, clear, or approve it to create
a demonstration. Its completion is not evidence of the new outage-independent path.

An isolated replay of the original committed receipt under an injected OGE outage
produced a maintenance commit with zero re-extractions and preserved review.
Real PostgreSQL CI also passed the outage/commit/replay cases. A live outage with
the original pending upload was **not recreated** because it had already completed.

An offline copy of retained source/AI snapshots produced **10,899** evidence
objects, all `unknown`; **311** retain legacy market evidence. Current Opportunity
is OFF and retained legacy records lack required verified first-discovery quote
quality/price-basis evidence. No discovery quote or historical provenance was
invented; configuration was not changed to manufacture a measured result.

All **4,511** snapshot headers created before
`2026-09-22T18:50:20.529501+00:00` retain digest
`7afd51f9c5019460fd9773d69396a10a`. The complete snapshot chain has **0** broken
parent links. PostgreSQL snapshots remain authoritative; no new protected GitHub
state artifact was produced by this source/test work. Legacy recovery artifact IDs
are not a replacement for these current heads. No rebaseline or cloud/legacy writer
activation occurred. Unrelated user files were not edited; normal running producers
may continue updating their own untracked status evidence.

### Next safe action

Keep [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225) open.
The prepared local package is
`C:\ProgramData\PolitiTrack\releases\discovery225\Apply.ps1`, pinned by arguments
to merged revision `c46dcef215e4872912ba2995b67cb117725b05e2` and tested head
`e5653120d4cd9d16303ec1ba3eda5488c1e2548e`. It checks canonical identity, tested
source, an idle producer window, snapshot continuity and untracked-file hashes;
restarts only the existing web/scheduler; and leaves PostgreSQL running.
No prompt remains active. Do not reopen a canceled prompt without owner action.

After owner-approved elevation, verify the activation receipt and unchanged old
snapshot headers, then the normal AI and dashboard producer revisions, persisted
ledger, JSON/CSV objects and live file hashes. Preserve the original upload's review
state. Source/CI success is not installation or live acceptance. No live outage proof
can be claimed for the original pending upload after its earlier completion.

## Earlier checkpoints

## September 22 manual-upload page exemption (#222) - merged; Windows approval pending

PR #223 merged as `dfb5c66ffc51b30b8afbdc283dbe10def4723f89` in canonical
repository ID 1349678672, `maglothinm/MyETF-Intelligence`, main branch.
The exact tested head `6fb612765cb5ff95b2712f9c8dd1d5b40a21c506` passed all four
CI workflows: Source OCR 35765600794, Runtime v2 35765600821, Investor Edge
35765600761 and Current Opportunity 35765600832. The Source OCR job
106874219819 also passed real PostgreSQL and isolated desktop/mobile UI checks.
Exact-head Windows repeat: 111 passed, 6 PostgreSQL tests skipped locally.

Manual uploads have no page-count cap in the new source. Automatic OCR remains
30 pages. The 20-MiB file-size cap, other resource safeguards, owner authorization,
source identity, confirmation, cache and commit/cleanup rules remain unchanged.
Real OCR completed all 37 synthetic PDF pages; manual admission covered 31, 37,
51 and 75-page PDF/TIFF cases with unchanged automatic rejection.

Windows reported user-canceled administrator approval at
`2026-09-22T18:19:40.4043961Z`. Activation did not start. Live application and
config both remain `7e33fc39aed897a2ae22b78f3ff73bece475a258`; all three services
remain Running/Automatic and loopback readiness is HTTP 200. The 4,502 existing
snapshot headers before `2026-09-22T18:13:42.082934+00:00` retain digest
`b2e86cdd8d19d794e1f8dd1a7173eed3`. No history was reset and no original file was
resubmitted, cleared or automatically approved.

The owner's Desktop shortcut **Activate Manual Upload Update** opens the pinned
release package at `C:\ProgramData\PolitiTrack\releases\manual222\Activate.ps1`.
Normal administrator approval is required. The installer waits for idle producers,
restarts only web/scheduler, leaves PostgreSQL running, preserves local configuration
and untracked source evidence, publishes via the existing locked dashboard writer,
then verifies HTTP and immutable snapshot headers. Do not run a second instance
while activation is in progress or retry a canceled prompt without owner action.

Keep #222 open until `backups/manual222-complete.json`, the HTTP verification and
snapshot-continuity receipts prove activation. `manual222-activation-blocked.json`
records the canceled attempt. Do not confuse source merge or synthetic tests with
a live upload, or claim this fixes separate OGE collection failures/automatic retries.
Do not rerun general setup, backups, cloud hosting or change schedules.

## Prior source checkpoint (superseded above)

## September 22 manual-upload page exemption (#222) â€” source tested, activation pending

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`.
Branch `codex/manual-upload-pages-222`, based on main
`d1f9c976030f86fe4fcc350ae01cc1a782acca2a`.
Only allowlisted manual uploads bypass the page-count admission check. Automatic
OCR remains limited to 30 pages, with no configuration/global maximum change.
Both private intake and worker extraction use the explicit manual policy. Manual
OCR uses a per-page engine watchdog; automatic document deadlines are unchanged.
Byte/pixel/output/decoder safety controls, authorization, original source identity,
confirmation-before-import, cached extraction identity and snapshot ownership remain.

Windows focused verification: 111 passed, 6 skipped (PostgreSQL integration cases
reserved for CI). Real OCR processed all 37 pages of a synthetic PDF. Admission
accepted synthetic PDF/TIFF documents of 31, 37, 51 and 75 pages in manual mode and
rejected them in automatic mode. Authenticated API intake retained all 37 pages;
private SQL inbox retained all 75 pages, deduplication and post-commit cleanup.
No original user document was resubmitted, auto-approved or published.

Live application remains `7e33fc39aed897a2ae22b78f3ff73bece475a258` until the new
release is explicitly verified. The previous Investor Edge activation did complete:
`backups/edge219-complete.json` at `2026-09-22T12:47:48.4582391Z` reports verified
HTTP, preserved snapshot headers and that exact source revision. This supersedes
the earlier canceled-activation handoff below; do not rerun its setup.

Current work: complete exact-head CI, merge, then use normal owner-approved Windows
service controls to activate the new source and verify web/worker state and
immutable history. Do not claim this change is live from tests or source merge.
No state reset, cloud reactivation, new schedules or unrelated feature changes.

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

## September 22 failed-backup cleanup completed (#214)

Owner-authorized cleanup removed all 38 confirmed pre-activation local-*.partial files at 11:34:27 UTC, totaling 1,061,305,390,205 bytes. No legacy partial files remain. C: now has 1,243,171,434,496 bytes free (about 1.24 TB). Both verified routine backups and all migration/other backup evidence remain; both routine manifest hashes are unchanged.

Post-cleanup at 11:35:07 UTC: all three services Running/Automatic with unchanged PIDs; dashboard readiness HTTP 200. Application revision stays f85a40f6b7b609ad8eec5c899c368d106fedd7c1. No production data, configuration, application code, or untracked user file was deleted or modified; no services restarted.

Do not rerun setup or activation. The backup repair and legacy cleanup are complete. OGE collection failures remain a separate issue; actual reboot and restore-drill acceptance are still untested.

[Cleanup evidence](releases/2026-09-22-legacy-backup-cleanup.md) and [exact receipts](releases/2026-09-22-legacy-backup-cleanup.json).

## Historical checkpoints (current cleanup status above supersedes storage figures below)

## September 22 backup repair activated and verified (#214)

Beast is running merged main source f85a40f6b7b609ad8eec5c899c368d106fedd7c1.
Activation passed at 11:16:42 UTC. All three services are Running/Automatic;
no unexpected service terminations through 11:27:15 UTC. The scheduler-created
27,197,505,861-byte physical backup passed at 11:19:46 UTC, with an independent
full integrity recheck at 11:25:54 UTC. Scheduled dashboard/Legislative/AI work
continued during backup; database and dashboard were not restarted.

Do not rerun setup or activation. Separate remaining work: 38 pre-activation
legacy partials consume 1,061,305,390,205 bytes (not deleted this verification);
Executive collection failed on OGE connection/page-load timeouts. Actual reboot
and restore-drill acceptance remain untested. No broad all-healthy claim.
[Current verification](releases/2026-09-22-backup-verification.md) and
[exact receipts](releases/2026-09-22-backup-verification.json).

## Prior checkpoints (historical; superseded above)

## September 21 backup repair: verified engine, owner activation pending (#214)

PR #215 merged at f85a40f6b7b609ad8eec5c899c368d106fedd7c1; the deployed application
is still 42c6f27df5d9266decad3abc7aa6f794edda0f3a because the Windows elevation
prompt was canceled. All three services are Running/Automatic, but the old
scheduler's backup/restart fault remains until the owner uses **Activate
PolitiTrack Backup Repair** and approves normal Windows elevation.

The new engine passed a full physical-backup integrity check at 19:17:07 UTC:
25,956,737,137 bytes. Removed 10 confirmed failed legacy partials totaling
220,958,188,263 bytes; migration backups and the active old attempt were preserved.
The dedicated backup login does not change application RLS or privileges.
Read-only audit: all 4,287 baseline snapshot headers preserved, successor lineage
valid, local config/authority unchanged. CI: Runtime safety 35643239002, OCR
35643238940, Opportunity 35643238956 all succeeded. Windows tests 66 passed,
1 skipped. Do not equate manual backup success with service activation.
See the [repair release](releases/2026-09-21-backup-repair.md) and JSON receipt.

## Earlier checkpoints (historical; current status above supersedes them)


## September 21 backup repair source (#214) - live acceptance pending

Windows service setup was completed by the owner: all three services were
verified Running/Automatic and real scheduled jobs succeeded. The first inline
pg_dump design is defective: the runtime role cannot bypass Vault RLS, causing
backup failures, scheduler restarts and accumulation of incomplete dumps.
Branch `codex/beast-backup-repair-214` isolates verified physical backups in a
separate child using a dedicated replication-only login. It preserves existing
application role restrictions, all production state and migration evidence.
Deployment, a full verified backup, natural scheduling and partial cleanup need
explicit live evidence before #214 can be closed. Reboot remains untested.

## September 21 Beast cutover — local authority live; Windows service approval pending (#211)

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Implementation PR **#212** is merged. Beast runs main application source
**42c6f27df5d9266decad3abc7aa6f794edda0f3a**. The follow-up evidence branch is
`codex/beast-local-cutover-evidence-20260921`.

The full Cloud SQL export restored successfully to native Windows PostgreSQL.
All **18 tables**, all **4,256 immutable snapshot payloads**, and all four
manifest-verified heads matched the frozen source. Authority moved to Beast at
**15:44:47 UTC** after five cloud schedules were paused and no cloud job remained
active. This is a host migration, not a rebaseline.

The first local Legislative, Executive, AI and Dashboard production cycle passed
at **15:47:43 UTC**. Heads advanced exactly once: Legislative **1360 → 1361**,
Executive **672 → 673**, AI **764 → 765**, Dashboard **1460 → 1461**. A subsequent
audit proved every frozen row fingerprint in the other 17 tables was preserved
and each new snapshot's parent matched its source head. Dashboard 1461 contains
5,152 filings, 12,737 transactions, 1,538 review items and 308 AI analyses.
Loopback readiness, 18 HTTP asset/data hashes, account-session API and the
existing desktop launcher's `--check-live` passed. PostgreSQL and the dashboard
listen only on `127.0.0.1`, ports 54329 and 8765.

Google Cloud hosting has been retired. The **15:53:35 UTC** inventory found zero
SQL instances/backups, Cloud Run services/jobs, schedules, active buckets,
artifact repositories, secrets, Compute instances/disks/routers. Two internal
reserved network ranges remain. Four deleted bucket records are retained by
Google until **September 28** despite their disabled soft-delete policy; retained
object bytes/final charges are not established. Do not claim all retained cloud
storage has already been permanently purged. All three legacy GitHub state
writers remain `disabled_manually`. Never resume cloud or legacy writers.

**Remaining blocker:** the Windows administrator prompt was canceled. The three
service configurations are prepared, but **no services are registered and no
recurring local scheduler is running yet**. The database, web server and desktop
tray currently run under the signed-in owner. The tray's existing startup entry
is enabled for sign-in; it does not replace the core service installer. The
owner must double-click **Finish PolitiTrack Setup** on Beast's Desktop and
approve Windows elevation. The installer transfers the existing database/web
processes to LocalService, registers automatic startup and verifies readiness.
Do not claim startup/reboot acceptance until `backups/installed-services.json`
and the three live Running service states have been checked.

Recovery: the 26,331,632,841-byte frozen SQL export and its SHA-256 are preserved
locally, plus a 25,760,825,499-byte post-cycle physical backup independently
verified by `pg_verifybackup`. Private data/configuration/backups are under
`C:\ProgramData\PolitiTrack`. Native OCR, Chromium, process cleanup and the enabled
Vault API's private file backend passed. Vault lifecycle remains paused; Current
Opportunity and manual cloud controls remain off. Existing OCR access/retry
backlogs are preserved. Closing the UI will not stop installed services; sleep
or power-off pauses processing, and missed intervals coalesce on return.

[Cutover, validation and next action](releases/2026-09-21-beast-local-cutover.md) ·
[Exact hashes, runs, counts and receipts](releases/2026-09-21-beast-local-cutover.json).

## September 21 dashboard history repair — deployed and verified (#208)

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, main
application source **50e3e0d6d0a09475cae694a74bfaf501416892f2** (PR #209).
The existing dashboard producer alone now uses image digest
`sha256:7003b8e37fdd2e949de6fb49f47e8544cc69bc4fb49a3ff11372240e9d71cd9b`.
The other five resources retain `aba0285689d649d94e3e11444b582c748927bbc4`
and their prior normalized configuration. All four original schedules are enabled;
Vault lifecycle remains paused and Current Opportunity off.

The seven-attempt cutoff no longer controls last-success dates. Snapshot-verified
production success history now supplies independent collection, completed OCR,
healthy OCR and document-completion dates. Overview, Operations and monitor cards
separate collector and Source OCR sections; blocked OCR is labeled explicitly.
The live Executive collection and completed OCR dates are **September 21 04:18
UTC**, replacing the misleading September 1 collection date. The last healthy OCR
pass is separately **September 20 00:45 UTC**. Current OGE collection failure stays
visible and OCR is **Blocked by collection**; no upstream recovery is claimed.

Publication `polititrack-dashboard-rm6cd` succeeded at **11:29:11 UTC**; Dashboard
**1451** is the direct immutable successor of **1450**. Baseline
`polititrack-admin-vmb4c` and acceptance `polititrack-admin-qcwpb` passed. Prior
snapshots, ledgers, identities, accounts, acknowledgements, completed runs and
notification history were preserved. Acceptance source generations: Legislative
**1350**, Executive **671**, AI **759**. Live readiness matches the accepted
snapshot; root/data/assets returned 200 and all changed asset hashes matched.
Overview and Operations were inspected in the browser.

Local focused validation: 218 Python and five Node health tests passed. Final
Runtime safety CI **35592427023** passed (including real PostgreSQL); PR source CI
**35592426780**, Investor Edge **35592426651**, Current Opportunity **35592426885**,
and merged-main source **35592689411** / Investor Edge **35592689390** all passed.

No #208 release blocker remains. Next safe action: normal scheduled publication
and separate diagnosis of the OGE incident / existing availability concerns.
Reload the page to load new labels. Do not replay the closed OCR release journal.

[Release and limitations](releases/2026-09-21-dashboard-health.md) ·
[Exact snapshot, CI, HTTP and integrity receipts](releases/2026-09-21-dashboard-health.json).

## September 20 OCR follow-up — live processing and continuity verified (#203)

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`. Evidence
branch `codex/ocr-live-continuity-20260920` is based on main
`6c9edb5b5759050764985a1f5c0d7bea355588b7`. The accepted application source
`aba0285689d649d94e3e11444b582c748927bbc4` remains deployed to all six resources,
image digest `sha256:f0fc0a54029094043448da348f5e2c04889b1f4863d11fd35ee68ee9999c4c84`.
At 19:13 UTC, normalized configs matched the accepted release; all four original
schedules were enabled and unchanged. No redeployment or manual producer dispatch
was needed. Vault remains paused and Current Opportunity off.

**Fresh read-only continuity and OCR audits passed** in `polititrack-admin-zgs5z`,
completed **19:22:27 UTC**. Audited generations: Legislative **1286**, Executive
**659**, AI **727**, Dashboard **1386**. Snapshot/ledger prefixes, stable IDs,
accounts, reviews, acknowledgements, completed runs and notification history are
retained. All 481 original extraction files and prior OCR receipts are intact;
163 new extraction files exist. The original upload remains two pages/five review
rows, `needs_review`, raw payload NULL. All 5,152 public filing IDs and first-seen
timestamps remain. All 512 accepted-workspace and 2,689 predecessor files match.
Closed journal hash remains
`9980523ad75ce1f4993967cbc4dce8c296e486b0d21ffc0e7db745a02e94ddcd`; release lock free.

**All 15 original House technical retries have cleared to review.** The final
20-page House 9115679 live retry completed at 14:38:53 UTC. Published Legislative
success at 19:09 UTC completed five documents/9 pages with zero technical retries.
Executive collection timed out on OGE's rendered table at 18:45 UTC before OCR,
then its next original scheduled run `polititrack-executive-h5qwl` recovered and
completed four documents/**17/17 pages** at 19:16:33 UTC. No transaction was
appended. Two OGE retries remain: the 2020 DeVos and MacGregor PDF URLs both
returned **404** in fresh 19:22 UTC checks. Do not hide those source warnings.

**Availability remains imperfect.** Root and insights returned 200, but readiness
and filings returned brief 503s at 19:22:20 UTC. Sequential rechecks returned 200;
readiness hash matched Dashboard 1386. Code shows web refresh takes the dashboard
writer lock, making contention plausible; logs do not prove the exact exception.
The 19:17:58 publication captured AI running and reports overall health failure;
the audit proves that same AI run succeeded at 19:18:13 UTC. Preserve this timing
difference and do not claim zero-error availability or all-green public health.

Next safe action: keep original source schedules and #203 open for the two 404
documents and a focused web-refresh contention diagnosis. Keep #182 for separate
owner correction/import acceptance. Do not replay the closed release, reset
receipts, rebaseline, resubmit the upload or auto-approve rows. Private read-only
audit receipts are in Cloud Shell release root
`/home/maglothinm/polititrack-ocr-182-v68vldej/ocr-live-continuity-20260920-1915`.
Source CI 35510840684 and controller CI 35512024741 were rechecked: success.

[Fresh evidence and limitations](releases/2026-09-20-ocr-live-continuity.md)
· [Exact audit, snapshot, HTTP and retry receipts](releases/2026-09-20-ocr-live-continuity.json)
· [Original release](releases/2026-09-20-ocr-page-retry-repair.md).

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

## PDF/Senate OCR release accepted — September 19 (#182)

Normal activation completed at **19:07:35 UTC**, with both OCR branches reporting
success. All six resources run tested application source
`77aadf541b034072f58dba5e7107c2c8e8ba4bd1`, build
`adba5676-b161-4b89-8336-0edc6c22795b`, image digest
`sha256:6be7d1e5236746d02d872303fa6192c29a824d0f55178df33a51c343eb0f18de`.
Two passes per source processed **20 documents and 56/56 pages, with zero
technical retries**. AI and dashboard succeeded. Independent acceptance
`polititrack-admin-ls8gh` verified prior histories, identities, snapshots,
acknowledgements, outbox and published OCR health; live asset hashes and the
enabled OCR API sign-in boundary passed. Accepted generations: Legislative 1193,
Executive 624, AI 679 and Dashboard 1291.

All four original schedules are ENABLED with unchanged configurations; Vault
remains PAUSED and Current Opportunity remains OFF. Historical OCR continues in
bounded scheduled batches. Unsupported Senate layouts require review with no
retry timer. The original House upload must not be resubmitted or auto-approved.

The owner-approved Executive-only recovery completed at 17:29:54 UTC, with OCR
disabled, genuine generation 620 and independent preservation. A subsequent
normal attempt had successful source runs but entered recovery after one status
read returned `ACCESS_TOKEN_TYPE_UNSUPPORTED`. Both closed records remain
immutable. Reviewed PR #201 adds bounded retries only to that exact read/error,
preserving full gates and diagnostics; the successful continuation needed no
such retry. Final journal SHA-256:
`54014b843890d0f845fe72e5c85c6750b444adaa21baa781fae210a491e34613`.

App CI `35453468818` passed 354 Python tests (one skip), four Node checks and
real PostgreSQL/browser checks. Controller CI `35460257042` passed 141 tests.
The application repair addresses a reproducible Playwright argument bug:
null-valued optional polling arguments were dropped, rejecting a ready table.
JSON transport preserves them; complete production collection repeatedly
verified all 4,068 listings. The earlier TCP outage recovered on a scheduled run
before later diagnostics; its provider-side internal cause is not established.

Independent Senate/PDF verification `polititrack-admin-87ghk` passed at
19:12:15 UTC against the original pre-repair baseline. Both unsupported Senate
filings are `needs_review`, with no retry timer and all seven prior attempts
preserved. Prior OCR receipts and extraction bytes are intact; new extraction
files total Legislative +20 and Executive +15 since that baseline. The original
House upload retains two pages and five review rows, with raw payload NULL.

The original Executive scheduler created `polititrack-executive-q525v` at
19:11:01 UTC using the expected scheduler identity, exact source/image and OCR
enabled. It completed successfully at **19:16:32 UTC**, collected all 4,068
listings and committed generation **625** with five documents, 16/16 pages and
zero technical retries. Intake succeeded and cleanup was not needed. This proves
post-restoration scheduled operation without a manual producer dispatch.

No release controller remains active or deployment gate remains open. Next safe
action: let the original schedules continue bounded history processing; review
unresolved document rows through the existing owner workflow. Keep #182 open
for the separate owner correction/import acceptance. Do not resubmit the House
upload or reopen any closed release journal.
[Release narrative](releases/2026-09-19-senate-pdf-release.md) ·
[Final acceptance receipt](releases/2026-09-19-ocr-final-acceptance.json).

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
