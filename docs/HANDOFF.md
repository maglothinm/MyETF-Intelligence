# PolitiTrack active handoff

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
