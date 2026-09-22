# PolitiTrack active handoff

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

Next safe action: verify exact-head PR checks, merge the reviewed source, and activate on Beast with normal Windows administrator approval. Preserve database services, all source/AI histories and untracked legislative-source-status.json. The manual-page policy does not clear automatic Executive retries or solve OGE collection outages.
