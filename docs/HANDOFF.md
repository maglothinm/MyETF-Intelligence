# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work records: **issue #12 — Operations health-check history ordering** and
[issue #11 — Investor Edge historical bootstrap](https://github.com/maglothinm/MyETF-Intelligence/issues/11).

## Current task and completed releases

The owner requested “Merge and publish.” [PR #14](https://github.com/maglothinm/MyETF-Intelligence/pull/14)
is merged and the fix is published to [Operations](https://maglothinm.github.io/MyETF-Intelligence/#operations).
Issue #12 closed with the merge. Canonical repository ID **1349678672**, current
name **maglothinm/MyETF-Intelligence**, default branch **main**.

Tested implementation `39f7edc28eda1ce4a309a2069321ee27d2574f94` and final PR
head `d621257b28620b7559f41cd1698f7c281aa5fe98` merged as
`7a1108fb2e32c39f6af943395c1bb9b9a550d26f`; the merged tree equals the final
PR tree. The later Investor Edge release, PR #15, published `676701ac` with this
Operations implementation unchanged. This documentation-only successor builds on
`895bc5739d14524bb7d4a1d7b546cd4e105665a4`, preserving both releases and their
evidence; it does not require another Pages publication.

Work remains isolated in `.remediation/operations-history-worktree`, branch
`codex/operations-history-order`. The shared checkout is used by other tasks;
it currently uses `codex/persistent-dashboard-shell`. Preserve it, local `main`,
untracked `.codex/` and `.worktrees/`, and unrelated branches. The upstream
Investor Edge validation report, decision 026 and review UX/recovery
documentation remain intact. Operations release authorization/evidence is decision 027.

## Delivered behavior and scope

`healthCards()` previously reversed an already newest-first model timeline.
It now sorts a copied collection by parsed finish time, descending, with a valid
start fallback and deterministic descending ID/URL ties. Undated records follow
dated records. Each record keeps its status, counts, link and accessible timestamp;
labels use the same timestamp fallback. The Overview preview shares the renderer.

Native horizontal overflow retains left-to-right DOM order: newest on the left,
older runs to the right. Refresh rebuilds the strip at offset zero. There are no
custom chronology arrows or selected-index state. Ordinary run links and existing
run-table sorting/previous/next pagination remain intact. No extra UI explanation,
CSS reversal, backend chronology or stored timestamp change was introduced.

Implementation: `scripts/dashboard_assets/common.js`. Regression coverage:
`tests/dashboard_dom.test.cjs`, `tests/operations_history.test.cjs`,
`tests/test_trade_dashboard.py`. Documentation: PROJECT_STATE, DECISIONS, HANDOFF.
The Operations fix changed no workflow, schedule, collector, AI, alert, simulation
or hosting configuration. Its only manual dispatch was the existing read-only
Pages workflow; the later Investor Edge release is described separately below.

## Operations tests and original publication evidence

- Full active Python suite: **296 passed**, no skips (387.84 seconds).
- **47 DOM scenarios**, including 13 new chronology/interaction cases;
  **10 dependency-free Node history scenarios** and **32 notification scenarios**
  passed. The native history wrapper is in the existing CI-watched dashboard test
  file; its final-location rerun passed without changing workflow selection.
- Coverage includes ascending, descending, mixed, tied, offset-aware, invalid,
  singleton and empty timestamps; newest-first output; record/link/status identity;
  immutability; new-run refresh and existing table pagination.
- Final PR CI [33387446310](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33387446310),
  attempt 1, job `99473151241`: success on exact PR head `d621257`.
- Main CI [33390543725](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33390543725),
  attempt 1, job `99482912240`: success on `7a1108f`; **214 tests passed** and
  Linux `verify.sh` reported **VERIFICATION PASSED**.
- Pages [33390642511](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33390642511),
  attempt 1, `workflow_dispatch` on exact `main` `7a1108f`: success.
  Build `99483229101`; deploy `99483408539`; both successful.
- Pages artifact **9757309134**, created 12:13:35 UTC, expires 2026-09-01
  12:13:34 UTC; exact successful attempt/build window verified. ZIP SHA-256:
  `6c36174d26ebf1e8b6495c435150da8e3c4703a02b595f6fba297dedab8e683a`.
- At **12:14:31 UTC**, all **28 public content files** plus root checks returned
  HTTP 200 and matched the artifact bytes, including published build/source.
  Hosting marker `.nojekyll` is not a public content URL.

Local TEST-only browser previews at 1440x1000 and 390x844 confirmed latest run 09
first at offset zero, rightward scroll exposing oldest run 00, and refresh reset.
Desktop scroll reached 126.4px; mobile-width scroll reached 150.4px. DOM tests
verify native link activation is not intercepted. Physical keyboard, touch and
Safari acceptance remain unverified; native Tab automation did not establish
focus movement. Optional DOM/browser evidence is not inferred from CI.

## Current published build and Operations acceptance

The concurrent Investor Edge release, PR #15, subsequently published
`676701ac1521458aefd72e2329d4e87c8781e41f`. It includes `7a1108f` and keeps
the Operations `common.js` blob unchanged in all three generated JavaScript
bundles. Main CI [33391179298](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391179298)
/ attempt 1 / job `99484924620` passed **264 tests** and Linux `verify.sh`.
Automatic Pages [33391179240](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391179240)
/ attempt 1 succeeded, build `99484924587`, deploy `99485120700`.
Artifact **9757512563**, created 12:20:05 UTC, expires 2026-09-01 12:20:04 UTC;
ZIP SHA-256 `eb83f2101c9137bbaab71214da50b6e30eb576fee60ff35cec3510db9df108b8`.
The carry-forward audit completed at **12:22:10 UTC** and all **28 public content
files** matched this artifact at **12:22:11 UTC**. The separate Investor Edge
release audit checked 30 URLs, including its additional entry-point requests.
Exact protected producer attempts, high-water marks, ZIPs and inventories remain
unchanged from the Operations publication checkpoint below.

A fresh live browser tab on build `676701ac` verified all three Operations
histories newest first at scroll offset zero, with each first/last link and label
attached to its correct run. At 1440x1000, rightward scroll reached 126.4px and
showed older August 29 runs; Refresh returned to zero. At 390x844, scrolling
reached 150.4px and Refresh again returned to zero. An older tab had retained
the prior script under Pages' `max-age=600` cache; the fresh-tab verification
resolved that stale-view observation. Native external-tab opening was not
observable through the browser tool. DOM activation/target/status tests passed;
physical keyboard, touch and Safari acceptance remain unverified.

Current two-entry simulator history is unchanged by this UI publication, and the
verifier's immediate-predecessor prefix check passed. This is not an exhaustive
historical append-lineage audit. Preserve the separately recorded historical
rewrite concern and its gate before future manual simulator work.

Current receipts: `.remediation/operations-history-publish/audit/carryforward-evidence.json`
and `.remediation/operations-history-publish/browser/verification.json`, with
desktop/mobile screenshots. This documentation integration starts from canonical
`main` documentation successor `895bc5739d14524bb7d4a1d7b546cd4e105665a4`,
preserving the Investor Edge release report, validation report and decision 026.

Initial local setup failures (missing temp directory and an existing link-arrow
assertion) were corrected before the passing run. Historical `backend/tests`
requires a separate `api` setup and is outside active `pytest tests`. Linux CI
resolves the local Windows Bash limitation. A connector ready-for-review response
schema failure was handled through a narrowly scoped authenticated GraphQL request;
the PR state was re-read before merging. No credentials were logged or changed.

## Protected inputs and continuity

Fresh preflight at **12:11:02 UTC** and postflight at **12:14:31 UTC** verified
repository/default branch, expected workflow/name/job, exact successful producer
attempt/upload window, expiry, ancestry and global producer high-water marks.
The exact publisher build log confirms these consumed inputs:

| Protected artifact | ID | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` |

Fresh ZIP downloads, full inventories, retained IDs/counts, schemas and ledger
continuity match preflight and the previous review-UX checkpoint byte-for-byte.
The publisher uploaded only `github-pages`; no protected state advanced.
Protected ZIP SHA-256 values:

- Legislative: `fcd8d2398fe1f6631e87023aa90b90e695fd64be21c5034df1c7196c2ded9479`
- Executive: `997a0eaf63b4b3bd33bbda34bfc40a633802c04cfd891f6a2dca726d93a2b4be`
- AI: `318e1892cc74505711dd362ba96255d060e5a099d174f36627af7f222c981aa9`

Simulation **9734790733**, run **33320677882 / attempt 1**, job **99281977011**,
retains the same complete two-entry history across this UI publication, and the
immediate-predecessor prefix check passed. This does not resolve the separate
historical rewrite concern before future manual simulator work. ZIP SHA-256:
`1daa01b253894ea07007bdfbf59bdcf5cb2afe568e9d6feff1774488b294dc59`.
Published counts reconcile to **5,079 filings / 60 transactions / 1,496 reviews /
11 analyses**, including 1 manual parser exception and 1,495 access-required rows.

Rollback evidence: previous Pages **33385044313 / attempt 1**, artifact
**9755242103**, ZIP SHA-256
`ca3b63daecb7c4e6ce5e92e162cbb363e753c07d8983fddcc1306ca7ac7e4014`.
Rollback means a reviewed source revert through Pages with current valid inputs,
never replacing protected state with an older snapshot.

Ignored receipts, exact logs and exported ZIPs are under the shared workspace's
`.remediation/operations-history-publish/`, including `dispatch.json`,
`audit/preflight-evidence.json`, `audit/postflight-evidence.json`,
`audit/carryforward-evidence.json` and `browser/verification.json`.
These are audit evidence, never production restore authority.

## Preserved Investor Edge release and production acceptance

PR #15 released implementation `b4a9049abcca16c40b88c9c05489e93ddad71d8f`
and tested integrated head `c27e884a4981db4a84982bbf665962ec2e081daa` as
`676701ac1521458aefd72e2329d4e87c8781e41f`; their trees match. Its separate
worktree remains `.remediation/investor-edge-worktree`, branch
`codex/investor-edge-bootstrap`. Its already published documentation successor
`895bc57` is the base for this combined handoff.

Investor Edge now reconstructs bounded retained filing history inside existing
trackers, discovers historical profiles independently of new AI candidates, and
continues fair bounded observations across zero-candidate runs. Global maintenance
failures prevent successful state promotion and candidate alert delivery.
Historical reconstruction creates no new filing/candidate notification event.
Both dashboards expose the full profile inventory and honest progress telemetry.
Scoring, configuration, protected artifact names and writer ownership are unchanged.

The integrated local suite passed **347 tests**, including optional DOM checks,
without skips. Focused merged DOM and native Operations wrappers, JavaScript syntax
and diff checks passed. The first full-suite attempt encountered test setup errors;
the fresh isolated test-directory run completed successfully.

Integrated [PR CI 33391078330](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391078330)
and [main CI 33391179298](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391179298)
both succeeded on attempt 1. Each passed **264 tests** and Linux `verify.sh`
reported **VERIFICATION PASSED**. Initial PR CI also passed before integration.

Automatic [Pages 33391179240](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391179240)
succeeded on attempt 1. The exact-attempt restore and publication audit passed;
all **30** checked live public URLs matched its artifact bytes. The
[root Investor Edge view](https://maglothinm.github.io/MyETF-Intelligence/#investor-edge)
and standalone page rendered without console warnings/errors or document-width
overflow at 1280x720. Existing legacy population telemetry remains visibly
unavailable rather than falsely completed. Device, Safari, touch and audio tests
are not inferred from this desktop check.

Protected inputs and isolated simulator history remained unchanged. The Investor Edge release manually dispatched no production
writer, simulation, alert or heartbeat; no credentials or
repository settings changed. Source caches and acceptance copies remain local,
not production-state authority.

Earlier detailed acceptance and limitations are preserved in
[the validation report](validation/investor-edge-bootstrap-2026-08-31.md)
and [PROJECT_STATE](PROJECT_STATE.md). Operations implementation and test evidence
remain recorded there and in decision D-2026-08-31-025; the Investor Edge decision
is D-2026-08-31-026. Detailed release verification stays in the ignored local
`.remediation/investor-edge-bootstrap/` evidence directory, including
`release-preflight/`, `release-postflight/` and exact CI receipts.

## Remaining limits and next safe action

Both authorized code releases and live publication are complete. No further runtime
merge, deployment, production run or state repair is needed for Operations ordering.
The fresh live browser verification passed; existing cached tabs may need reloading.
Keep physical-device acceptance separate and do not imply that a resized viewport
proves touch, Safari or physical keyboard behavior. Native external-tab opening
remains unverified by the browser tool, despite passing DOM activation/target tests.

Issue #11 remains open for production acceptance. Code publication does not itself
populate production profiles. Verify future normal sole-writer artifact successors
and actual market backlog reduction separately. Never upload acceptance copies,
rebaseline, or dispatch an alternate writer. Missing source originals, parser/OCR
limitations and market coverage remain as documented in the preserved validation
report. The unchanged $10K simulator's historical predecessor-rewrite concern needs
its separate audit before future manual simulator work; the current immediate-
predecessor prefix check does not resolve that broader concern.

Issue #1 cutover, held PR #3, rename/privacy, legacy settings and Gmail delivery
proof remain separate. Obsolete queued runs `33219808359` and `33221027676`
persist; the separate manual Legislative run remains gated on their clearance.
The Senate recovery and Support context remains preserved in
`docs/incidents/senate-efd-2026-08-30.md`. No credentials or repository settings
were changed or independently tested by this release.
