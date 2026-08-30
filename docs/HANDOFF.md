# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Work record: **[issue #6 — Refine contextual help on the current PolitiTrack dashboard](https://github.com/maglothinm/MyETF-Intelligence/issues/6)**

## Current task and exact scope

Contextual-help implementation and local regression verification are complete.
Chrome responsive acceptance, Linux verification and publication remain pending.
This is a **local, unpushed candidate on `main`**, based on
`a5d67034044ca53fc861a51af6218e79f9899870`; the commit carrying this handoff contains
the implementation and documentation. Canonical repository is
`maglothinm/MyETF-Intelligence`, ID **1349678672**, default `main`, still public and
pre-rename. Do not use legacy `maglothinm/MyETF`.

No workflow, collector, score, modifier, confidence calculation, classification,
benchmark, identity, simulation, paper-position, alert or production-state change
is included. Held PR #3 remains untouched. Generated production Pages output was
not edited; no workflow was dispatched and no external alert was sent.

## Completed source and evidence

- `scripts/dashboard_assets/common.js` retains one shared `#tooltip` and refactors
  the existing `setupDialogsAndTooltips()`. It adds safe optional title/body/note,
  frozen shared definitions, 300ms hover, immediate focus/help, correct pointer
  exit/pinning, preserved ARIA tokens, Escape, caret/viewport positioning,
  layout-change handling and keyboard scrolling of overflowing copy.
- Source HTML/JS and `investor_edge.py::build_dashboard_addon()` provide contextual
  help for Investor Edge, TEST pipeline acceptance, single-run $10K replay,
  research terminology, selective Overview, local notifications and Monitor Mode.
  Workflow actions have adjacent 44px help buttons. Selected explanatory links
  use first-touch preview and second-touch navigation; ordinary navigation and
  desktop actions remain immediate.
- All material research/simulation/insufficient-history/local-browser warnings
  remain visible. Business functions and workflow files are unchanged.
- Full repository tests: **182 passed**, including **24 JSDOM scenarios** and
  **32 native Node notification scenarios**. Syntax, Python compilation and diff
  checks passed. Fixture builders, immutable-input/public-output sanitation and
  existing dashboard/research regressions passed. Axe found no serious/critical
  findings in tested fixture views; layout/color checks were excluded.
- Geometry/pointer checks use explicit stubs: 1920×1080, 1440×900, 1180×820,
  820×1180 and 390×844, plus visual-viewport offsets, detached anchors, layout
  changes and overflow reading. **No rendered screenshots or physical-device
  acceptance were performed.**
- Windows `verify.sh` could not resolve required `dirname`/`mktemp` utilities.
  Shell syntax and the script's unmodified embedded Python assertions passed
  separately. Canonical Git blobs match all four manifest hashes; working
  recovery files differ only by Windows line endings. Full Linux execution and
  its `VERIFICATION PASSED` output remain required before release.
- Detailed changed files, final copy, interaction design, tests and limits are in
  `docs/CONTEXTUAL_HELP.md`. Local ignored audit evidence is
  `.remediation/tooltip-audit.md`; it is an evidence record, never state authority.

## Fresh operational checkpoint — 16:56–17:03 UTC

All 114 canonical runs and 144 repository-global artifacts were inspected.
Protected IDs, reported ZIP digests, exact successful attempts/jobs, ancestry and
producer high-water marks are unchanged from the deployed redesign. No newer
eligible producer or active eligible writer was found.

| Pipeline | Artifact ID | Producing run / attempt | Successful job |
|---|---:|---|---:|
| Legislative | `9734211271` | `33318579174` / `1` | `99276401831` |
| Executive | `9732455687` | `33312565343` / `1` | `99260139758` |
| AI | `9734221839` | `33318614858` / `1` | `99276494661` |

Producer commit is `4a9135a`, an ancestor of the base and this candidate. This is
fresh **metadata/lineage** verification, not a new artifact download, production
restore, ZIP-content or ledger-count audit. Historical full continuity evidence
remains in `docs/PROJECT_STATE.md`.

Isolated replay artifact `9734790733`, run `33320677882` / attempt 1, successful
job `99281977011`, is unchanged. No simulation was run for this work.

## Existing deployment, unchanged by this candidate

- Main CI [33323430401](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430401),
  attempt 1: success at deployed UI commit `12d5896`.
- Pages [33323430450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430450),
  attempt 1: success; build `99289284456`, deploy `99289373251`, artifact
  `9735544864`. That run uploaded no protected state.
- Fresh live root, Wallboard, Edge and insights responses were HTTP 200; published
  `build_sha` remains `12d58964060885696ef4f5d3724ba5575de33fb2`.
- These runs verify the previous release, **not** the new tooltip candidate.

## Remaining limits and next safe action

1. Connect Chrome through Settings → Computer use. The Browser skill requires
   the requested Chrome connection; no other browser was substituted. Inspect
   desktop/tablet/390px generated fixtures, Actions dialog, touch help, focus,
   caret, overflow, console/CSP and real iPhone Safari. Keep issue #6 open until
   acceptance/release evidence is recorded; issue #4 retains its earlier device
   acceptance requirements.
2. Run full Linux `verify.sh` in the existing CI path. When publication is
   requested, reverify live canonical main, artifact high-water marks and this
   diff; use only the existing read-only Pages publisher and record new CI/Pages
   runs and live build SHA. Do not dispatch collectors/AI/simulations for UI QA.
3. Preserve pre-existing untracked `.codex/`; local generated tests/audit files
   remain ignored. Do not treat them as production authority.
4. Separate unchanged open work: issue #1, PR #3, obsolete queued runs
   `33219808359` and `33221027676` (zero jobs/artifacts), same-ID rename/privacy,
   legacy Actions/Pages/archive settings and actual Gmail delivery proof. Do not
   close those gates, rebaseline state or claim duplicate-writer retirement.
