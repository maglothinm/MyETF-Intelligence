# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: **issue #4 — dashboard UX; issue #6 — shared contextual help**

## Current task and delivered state

Implement the attached parser-exception, Review Source and Workspace-help UX
request within the existing static dashboard. The implementation is local on
`codex/dashboard-review-ux`, based on canonical remote `main`
`3902968d5d70cd00030248ae4a6bcea18aa2e6ea`. Repository ID **1349678672**, current
name **maglothinm/MyETF-Intelligence**. The delivery commit contains this handoff.
**Not pushed, merged or deployed. No new Actions run or external publication.**

Local `main` still preserves the prior unpublished recovery-document commit
`9e5de909d7f939c0088914511cca72852e95508e`. This branch does not include that
previously blocked payload. Preserve untracked `.codex/`, held PR #3 and unrelated
work; never implement or dispatch in legacy `maglothinm/MyETF`.

## Implementation

Root cause: Overview called the Python review classifier, while the lazy Review
Queue exported raw rows and had no category filter. Its card linked only to the
unfiltered queue. Generic title formatting also rendered `oge` as `Oge` and source
options omitted the retained branch dimension.

The card now opens `#records/reviews?category=manual_exception`, resets stale
search/source/date filters and brings the exception result into view. The full
review JSON/CSV and Overview use the same public projection/classifier, with
synthetic ancestry excluded from production counts and labeled in the full queue.
The latest-eight preview never limits the full list. Explicit category controls,
a removable active indicator and a positive zero state reuse existing controls.

Clickable reviews show retained filer, record ID, reason, source/branch, filing
date, observation time/age and review category. Exact matched filing keys select
and highlight the original filing and its details in the existing table. Missing
or contradictory matches select the original review; no ID/status/time is invented.
The dashboard remains read-only: no second retry or resolution action was added.

Source choices include All Sources, OGE, Executive, Legislative, House, Senate and
other published taxonomy. Branch filters match retained branch fields, not client
source-name guesses. OGE capitalization is presentation-only. Signals, Records
and Operations share the existing PT.HELP, tooltip bubble, hover delay, keyboard
focus and two-tap touch preview used by Investor Edge and $10K Agent.

Refresh stages tables opened during its awaits and rejects mismatched review
counts before advancing the model or local notification baseline. Deep links,
selected detail IDs and focus remain safe for hostile text and unmatched records.

Changed files: `scripts/dashboard_insights.py`, `scripts/build_trade_dashboard.py`,
`scripts/dashboard_assets/{app.js,common.js,index.html,styles.css}`,
`tests/{test_dashboard_insights.py,test_trade_dashboard.py,dashboard_dom.test.cjs}`,
and `docs/{PROJECT_STATE.md,DECISIONS.md,HANDOFF.md}`. No workflows, production-state
schemas, collectors, scoring, alerts, simulators or hosting configuration changed.

## Verification

- Full active Python suite: **295 passed**. Includes existing simulation, tracker,
  signal/Edge, notification, dashboard generation and nested release checks.
- **34 DOM scenarios passed**, including card/filter/detail routing, reload/back,
  stale filters, 53 exceptions/pagination, zero state, synthetic exclusion, exact
  taxonomy, hostile/orphan records, refresh interleaving, unique focus IDs, all five
  workspace tooltips and existing axe checks. Final focused rerun passed after the
  mobile focus/layout change. Axe excludes layout and color-contrast checks.
- **32 native Node notification scenarios passed**. Python compilation, JS syntax
  and diff checks passed. There is no configured separate dashboard lint/build
  framework; the existing Python static generator built successfully.
- Generated verified-copy preview reconciles **5,079 filings / 60 transactions /
  1,496 reviews / 11 analyses**, with exactly **1** manual parser exception and an
  exact filing match. All input file hashes/sizes remain unchanged after generation.
- In-app rendered checks at **1440×1000** and **390×844**: card to one exception to
  matched filing, selected-record focus, filter reset, expected source counts,
  visible mobile exception and full-width status control, no horizontal page
  overflow, and all five mouse-hover bubbles with `aria-describedby`. Screenshots
  and hover evidence are in `.remediation/dashboard-review-ux/browser/`.
- Keyboard focus/touch are verified in deterministic DOM tests. Native Enter/Tab
  browser-control calls did not establish activation, so real keyboard/touch,
  physical iPhone/Safari, audio and physical ultrawide acceptance remain unverified.
- Windows has no available Bash: local `verify.sh` is not claimed. No new remote
  CI or Pages verification applies to this unpublished implementation.

## Production baseline evidence — read-only audit at 10:27 UTC

| Protected input | Artifact | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` |

Canonical run URLs are
https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244,
https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323 and
https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492.
Workflow/job identity, exact attempt windows, ancestor commits, all-run producer
high-water marks, expiry, ZIP hashes, inventories and record continuity passed.
These were verified before copying fixture inputs; copies are not production
restore authority. No protected artifact or simulation history was written.

Existing Pages **33369728437 / attempt 1**, artifact **9749580990**, succeeded:
https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369728437.
All **21** live URLs matched that artifact at build **3902968**. This proves the
existing deployment only. Fresh audit receipts, copied-input integrity and preview
files are in ignored `.remediation/dashboard-review-ux/`.

## Remaining limitations and next safe action

Review this local implementation, then obtain publication authorization before
pushing/merging/deploying. On publication, use the canonical existing PR/CI and
read-only Pages path, refresh exact artifact provenance/continuity and verify the
new deployed build. Do not reuse an old checkpoint as production restore input.
Do not publish the separately blocked recovery payload as part of this UI change.

No credentials were tested or changed. Obsolete queued runs `33219808359` and
`33221027676`, held PR #3, same-ID rename/privacy, legacy settings, physical-device
acceptance and Gmail delivery proof remain separate open work. They must not be
conflated with local dashboard implementation or relaxed to dispatch a writer.
