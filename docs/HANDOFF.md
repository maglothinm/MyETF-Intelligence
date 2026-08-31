# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: **issue #12 — Operations health-check history ordering**

## Current task and implementation

Present Operations health-check history newest to oldest from left to right,
including initial load and refreshed data. Canonical repository ID **1349678672**,
current name **maglothinm/MyETF-Intelligence**, default `main`. This work uses
isolated branch `codex/operations-history-order`, based on
`f2df59740b095417e3883fd81ac0a16c1d16fdad`, the documentation-only successor
of PR #10's review UX release `9d9e7bef326a0e24a5f846ea1310dec24a647019`.
The worktree is `.remediation/operations-history-worktree` under the shared
workspace. The shared checkout is concurrently used for Investor Edge work;
preserve it, local `main`, untracked `.codex/`, and all unrelated branches.

Root cause: `healthCards()` reversed an already newest-first model timeline.
It now sorts a copied presentation collection by parsed finish time, descending,
with a valid start fallback and deterministic descending ID/URL ties. Undated
records follow dated records. Each record retains its own status, counts, link
and accessible timestamp; labels use the same timestamp fallback as sorting.
The shared Overview preview follows the same order. Source arrays are unchanged.

The component uses native left-to-right horizontal overflow and ordinary run
links. It has no custom chronology arrows or selected-index/highlight state.
New timeline nodes on refresh start at scroll offset zero. Existing run-table
sorting and previous/next pagination are unchanged. No new explanatory UI copy,
CSS reversal or redundant navigation controls were added.

Changed implementation: `scripts/dashboard_assets/common.js`. Regression coverage:
`tests/dashboard_dom.test.cjs`, `tests/operations_history.test.cjs` and
`tests/test_trade_dashboard.py`. Documentation: this file, PROJECT_STATE and DECISIONS.
No workflows, schedules, execution, backend chronology, retained timestamps,
protected artifacts, collectors, alerts, simulations or hosting configuration changed.

## Verification

- 47 generated-dashboard DOM scenarios passed, including 13 new chronology,
  timestamp, record activation, refresh, immutability and pagination scenarios.
- 10 dependency-free Node history scenarios passed; the Python wrapper passed.
  The existing CI dashboard test selection invokes this wrapper without optional
  JSDOM/axe packages. Its final location rerun passed; no workflow changed.
- Final full active Python suite: **296 passed**, including generated-dashboard,
  native Node and nested release checks; no skips (387.84 seconds).
- JavaScript syntax and diff checks passed. Dashboard generation used empty inputs
  plus explicitly marked TEST fixtures, not production-state clones.
- Rendered in-app browser checks at 1440x1000 and 390x844 confirmed latest run 09
  first at offset zero, older runs to the right, ordinary horizontal scrolling,
  and refresh returning to offset zero. Desktop scroll advanced to 126.4px;
  mobile-width scroll advanced to 150.4px and exposed the oldest run 00.
- DOM tests verify native link activation is not intercepted and each target,
  status and accessible name remains attached to its record. Native Tab automation
  did not establish focus movement; physical keyboard, touch and Safari acceptance
  are unverified. Do not infer those from DOM fixtures or viewport resizing.
- TEST preview/helper and browser screenshots are ignored under this worktree's
  `.remediation/`. No production writer, external alert or simulation was dispatched.

Initial verification setup failures were corrected: missing temporary directory,
and a test assertion that omitted the existing external-link arrow. Running pytest
without the `tests` path also collected unrelated historical `backend/tests`, which
cannot import `api`; the active suite is explicitly `pytest tests`. Windows has no
available Bash, so local execution of Linux `verify.sh` is not claimed.

## Live baseline and continuity (read-only audit)

The previous review UX publication completed during this task. PR #10 merged as
`9d9e7be`; its tree equals the starting review branch `ca01520`.
PR CI [33384840936](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33384840936),
main CI [33385044349](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044349)
and Pages [33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313)
all succeeded on attempt 1. Main CI job: `99465680760`; Pages build/deploy:
`99465681041` / `99465807219`.

All 28 checked public files on the
[live dashboard](https://maglothinm.github.io/MyETF-Intelligence/) matched Pages
artifact `9755242103`; live build is `9d9e7be`, generated 11:02:05 UTC.
Pages ZIP SHA-256:
`ca3b63daecb7c4e6ce5e92e162cbb363e753c07d8983fddcc1306ca7ac7e4014`.
This is the prior release, **not deployment of issue #12**.

| Protected artifact | ID | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` |

Exact repository/default branch, expected workflow/name/job, successful attempt,
upload window, expiry and producer ancestry checks passed. All 158 Actions runs
(82 producers) were scanned; no later producer high-water mark superseded these.
Metadata is unchanged from the documented checkpoint. Protected payloads were not
restored or written, so this is metadata/provenance continuity, not a fresh full
ledger audit. Shared-workspace receipts are in
`.remediation/operations-history-audit/{metadata-evidence.json,pages-evidence.json}`.

## Remaining limits and next safe action

The ordering fix is locally verified and not merged or deployed. The exact scoped
diff is ready for the canonical PR/CI and existing read-only Pages path.
Confirm current main,
exact CI head, protected producer high-water marks and deployed build/content
before reporting the fix operational. Never dispatch a production writer to test
this presentation change and never restore state from a cached checkpoint.

Issue #1 cutover, held PR #3, repository rename/privacy, legacy settings,
physical-device acceptance and Gmail delivery proof remain separate. Obsolete
queued runs `33219808359` and `33221027676` persist; the separate manual Legislative
run remains gated on their clearance. The Senate recovery evidence and pending
Support context remain preserved in `docs/incidents/senate-efd-2026-08-30.md`.
No credentials or repository settings were changed or tested by this task.
