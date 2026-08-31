# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: **issue #4 — dashboard UX; issue #6 — shared contextual help**

## Current task and delivered state

Implement the requested persistent dashboard header and Workspace navigation in
one shared application shell. The header stays at the viewport top, the desktop
sidebar remains below its measured height, and Workspace gains its own vertical
scrolling only when its contents exceed the available height. Preserve mobile
navigation, overlays, focus order, record/filter widths and the document scroller.

Canonical repository ID **1349678672**, current name
**maglothinm/MyETF-Intelligence**, default `main`. Work is isolated on
`codex/persistent-shell-layout`, based on live main
`9d9e7bef326a0e24a5f846ea1310dec24a647019`, under the parent checkout's
`.remediation/persistent-shell/worktree`. The original checkout's user files, untracked `.codex/`, held PR #3 and unrelated
work are preserved; concurrent task branches remain separate. Never implement or dispatch in legacy `maglothinm/MyETF`.

**Current delivery state: local implementation and validation complete, recorded
in the commit containing this handoff. No push, pull request, merge or deployment
for this shell payload.**
The earlier review UX payload was explicitly authorized and is already published;
that scoped approval is not publication authorization for this new layout change.

## Implementation scope

- Reuse the existing header's height and styling, measuring its actual border box
  with `ResizeObserver` and a resize fallback. The shared height token controls
  sidebar positioning and document anchor clearance when the header wraps.
- Pin the header across dashboard routes. At the existing persistent-sidebar
  breakpoint, limit Workspace to the remaining viewport height and enable
  `overflow-y: auto`; retain accessible links and their existing focus behavior.
- Preserve the document as the content scroller. Remove the shell's table vertical
  height cap, retaining horizontal table access, and reserve scrollbar space to
  avoid page-width shifts. Preserve the current narrow-screen navigation layout.
- Keep the existing tooltip, native dialogs and popovers above the shell; do not
  duplicate positioning across Overview, Signals, Investor Edge, Records,
  Operations and the $10K Agent routes.

Changed implementation files:
`scripts/dashboard_assets/{app.js,index.html,styles.css}` and
`tests/{dashboard_dom.test.cjs,dashboard_notification_integration.test.cjs}`.
Project records are `docs/{PROJECT_STATE.md,DECISIONS.md,HANDOFF.md}`.
No collectors, scoring, state schemas, alerts, simulations, workflow files or
hosting configuration are changed. No production state is written or restored,
and no production writer, simulation or external alert has been dispatched.

## Local verification

- Full active suite: **295 passed in 398.82 seconds**. Existing wrappers include
  **41 DOM scenarios** (seven new shell/route/focus regressions) and **32 native
  Node notification scenarios**, including six dashboard integration cases.
- JavaScript syntax and `git diff --check` passed. The canonical Python static
  generator built **5,079 filings / 60 transactions / 1,496 reviews / 11 analyses /
  zero paper positions** from read-only local fixtures. Every fixture file's
  hash/size still matches its original audited inventory; see the integrity receipt.
- Rendered browser checks: 1440x1000/900, 1366x520/420, 3840x1080, 1920x1080,
  1024x768, 902x600 (requested 901px rounded by browser), 900x600, 768x1024,
  390x844 and 320x740. Header remains at top zero; desktop sidebar stays below
  it within the viewport. No horizontal page overflow. Mobile keeps wrapped
  navigation and initial no-hash landing does not scroll it away. At 320px,
  header controls wrap instead of overflowing; the measured offset follows.
- All six routes checked, including deep page scrolling, route titles, parser
  exception and selected filing focus, Records Source filtering, full-height
  tables with horizontal access, and independent sidebar/main scroll movement.
  Actions and Notification dialogs remain in the native top layer. Run Simulation
  help popover and Workspace hover help render without sidebar/header clipping.
  No workflow link was dispatched. No new custom dropdown/popover/toast exists;
  existing native select controls, notices, help and dialogs were checked.
- **Native input limit:** browser-control diagnostics show synthetic wheel/key
  events (`isTrusted=false`). At the sidebar boundary those scroll commands moved
  the document despite computed `overscroll-behavior-y: contain`; this does not
  establish native wheel containment. Tab automation did not establish native
  traversal. DOM focus/navigation tests pass, but physical mouse/trackpad boundary
  behavior, Page Up/Down/Home/End, touch/Safari, audio and physical CHG90 acceptance
  remain unverified. No claim that these physical-device tests passed.
- Windows has no configured Bash runtime; local `verify.sh` is not claimed.
  New remote Linux CI and Pages have not run for this local shell commit.

Evidence in the parent checkout: `.remediation/persistent-shell/validation-summary.json`,
`input-integrity-final.json`, generated `preview/`, and `browser/` screenshots plus
`responsive-checks.jsonl`. The implementation worktree's `.remediation/full-shell-tests/`
contains test outputs; focused DOM fixture evidence is in the parent's
`.remediation/persistent-shell/shell-dom-final/`. Temporary browser viewport
settings were reset. Local preview: http://127.0.0.1:8766/.

## Existing published release — fresh read-only verification at 11:14 UTC

The earlier review UX PR
[#10](https://github.com/maglothinm/MyETF-Intelligence/pull/10) merged at 11:01:36
UTC as `9d9e7bef326a0e24a5f846ea1310dec24a647019`. This corrects the stale
publication-pending checkpoint previously recorded in these documents.

| Evidence | Result |
|---|---|
| PR CI | [33384840936](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33384840936), attempt 1, job `99465044563`; success |
| Main CI | [33385044349](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044349), attempt 1, job `99465680760`; success |
| Pages | [33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313), attempt 1; build `99465681041` and deploy `99465807219` successful |
| Pages artifact | `9755242103`, SHA-256 `ca3b63daecb7c4e6ce5e92e162cbb363e753c07d8983fddcc1306ca7ac7e4014`; fresh GitHub digest matches retained ZIP |
| Live result | All 21 checked URLs returned HTTP 200 and exactly matched the digest-verified Pages artifact, build `9d9e7bef326a0e24a5f846ea1310dec24a647019` |

Live [dashboard](https://maglothinm.github.io/MyETF-Intelligence/) remains this
previous release. No new shell deployment is claimed.

| Protected input | Artifact | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` |

Fresh exact repository/workflow/attempt/job bindings, expiry and commit ancestry
match the prior release evidence. Fresh metadata digests match all three retained
ZIP exports and their ledger counts are unchanged. All 158 run records were
inspected; no later eligible producer was found. Only the two obsolete queued
runs remain. The PR and main CI runs uploaded no artifacts; Pages uploaded only
`github-pages`. This verification did not restore or mutate production state.

**Audit limitation:** fresh repository-global artifact-name enumeration could not
be performed because public REST was rate-limited, the connector disallows that
endpoint, and local Git credential lookup was unavailable. Do not claim a new
complete restore-authority audit or use this checkpoint as automatic authority
for a future production restore. That requires a fresh complete selection audit.

Evidence in the parent checkout:

- `.remediation/persistent-shell/live-github-metadata.json`: fresh exact GitHub
  metadata, attempts, jobs, ancestor comparison and all 158 run records.
- `.remediation/persistent-shell/live-byte-verification.json`: all three retained
  protected ZIP digests, retained counts and 21 current live byte matches.
- `.remediation/dashboard-review-publish/deployment-verification.json`: preserved
  full prior publication acceptance at 11:04:50 UTC, including actual publisher
  restore IDs, protected continuity and two-row isolated simulation history.
- `.remediation/persistent-shell/`: completed local preview and validation
  receipts described above; these are not production authority.

## Remaining blockers and next safe action

Review the local shell commit and complete native-input/device acceptance when
available. A future publication must follow the canonical PR/CI/Pages path and
receive authorization for this new payload; refresh the complete artifact audit
for that release. Do not dispatch production writers or alerts as a layout test.

The obsolete queued runs `33219808359` and `33221027676`, held PR #3, same-ID
rename/privacy, legacy settings, physical-device acceptance and Gmail delivery
proof remain separate open work. No credentials or settings were tested or changed.

The Senate recovery evidence and incident record are unchanged. Supported
cancellation/deletion and signed-in UI attempts did not clear the two obsolete
queues. The authorized GitHub Support draft remains unsent because an applicable
Actions route was unavailable. Backend clearance or confirmation that neither run
can execute remains required before the separately requested manual Legislative
run. Do not relax that gate or conflate it with read-only dashboard implementation.
