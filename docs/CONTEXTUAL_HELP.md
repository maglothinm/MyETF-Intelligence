# Contextual-help implementation and acceptance record

Issue [#6](https://github.com/maglothinm/MyETF-Intelligence/issues/6), 2026-08-30.
Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`; local
`main` based on `a5d67034044ca53fc861a51af6218e79f9899870`. The implementation is
local, not pushed or deployed. The live dashboard remains the prior `12d5896`
release. This record accompanies the implementation commit.

## Owning source and reused code

| File | Change |
|---|---|
| `scripts/dashboard_assets/common.js` | Frozen `PT.HELP`, escaped help helpers and signal facts; refactored existing `setupDialogsAndTooltips()` |
| `scripts/dashboard_assets/index.html` | Source-owned help targets and adjacent workflow help buttons |
| `scripts/dashboard_assets/app.js` | Shared research-term help next to analysis-table sort controls |
| `scripts/dashboard_assets/styles.css` | Elevated navy bubble, subtle border/shadow, 340px cap, 12px text, 12–13px padding, directional caret and action-help layout |
| `scripts/investor_edge.py::build_dashboard_addon()` | Help markup in the standalone Edge view; calculations untouched |
| `tests/dashboard_dom.test.cjs` | Deterministic interaction, safety, accessibility and geometry regressions |
| `tests/test_investor_edge.py` | Shared framework, named help controls, retained labels/values and visible warnings |
| `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, this record | Local candidate, design decision, live checkpoint and release limits |

There is one shared `#tooltip` with `role="tooltip"`, using the existing
`data-tooltip` pattern. Static/generated targets may reference `data-tooltip-key`;
the shared object resolves their text. `data-tooltip-title` and
`data-tooltip-note` are optional. The bubble is built with `createElement` and
`textContent`; hostile markup remains inert text. No tooltip library, framework,
business logic or generated production HTML was introduced or edited.

## Added and refined targets

- Investor Edge navigation, transaction-date outcomes, post-disclosure outcomes,
  confidence/shrinkage and detailed heat-map navigation.
- Actions entry point; distinct TEST acceptance and $10K replay links; $10K Agent
  navigation and latest independent replay explanation.
- Final score, Edge confidence, base score/modifier, followable alpha and hit rate,
  sector edge, entry-review band, chase ceiling and signal expiration. Repeated
  definitions are shared with analysis-table headings and the standalone Edge
  heat map, horizon columns and transaction/disclosure entries.
- Selective Overview attention cards, Inbox, Sound, Refresh and Monitor Mode.
  Existing coverage, retained run-health and sound-mode explanations remain.

PAPER RESEARCH, SIMULATED, SINGLE-RUN HISTORICAL REPLAY, “No persistent portfolio
history yet”, delayed/cached prices, insufficient history, Methodology & Risk,
browser-local notices and source evidence links remain visibly present.

## Final primary copy

**Investor Edge navigation**

> Investor Edge measures how a filer or disclosed owner’s historical investments
> performed relative to relevant benchmarks. Completed transaction-date and
> post-disclosure outcomes are evaluated, while limited histories are de-emphasized.

**Run Simulation**

> Opens an isolated TEST workflow that exercises the PolitiTrack / Investor Edge
> pipeline without changing production state. It sends no live alerts and cannot
> publish to production Pages.

**$10K Agent navigation**

> Research lab for PolitiTrack’s simulated $10,000 historical replay and separately
> retained paper-position evidence. The replay is isolated from production and
> does not represent real money.

**Open Run $10K Agent**

> Opens an isolated $10,000 historical replay using retained PolitiTrack evidence.
> It does not place real trades, alter production state, or create persistent
> portfolio history.

**Latest replay**

> This is one independent historical replay, not a continuing investment account.
> Starting value, replay value and change apply only to this run.

## Interaction and accessibility

Desktop whole-control hover opens after 300ms. Child traversal does not restart
the delay. A 100ms exit grace allows the pointer to cross into the hoverable
bubble; help remains while the trigger has keyboard focus. Focus and explicit
help activation open immediately. Desktop links and buttons execute on the first
click.

Workflow links have separate adjacent 44px `?` controls, so reading their help
cannot open GitHub. Their action links remain one tap. Only explicitly marked
explanatory links (Investor Edge/$10K navigation, detailed Edge view and Monitor
Mode) use first touch to pin help and second touch to follow, with “Tap again to
open. Tap elsewhere to dismiss.” Ordinary navigation never requires two taps.
Actual mouse pointer events override a device's coarse-pointer capability.

Visible focus rings and named help buttons remain. `aria-describedby` gains only
the `tooltip` token, preserves other owners' tokens, and removes its own token on
dismissal. Escape cancels pending/open help; it dismisses help before the dialog.
Dialog close restores the opener's focus. Normal tab navigation is not trapped.
Arrow/Page/Home/End keys scroll overflowing copy while its trigger keeps focus.

The bubble uses a 12px viewport inset and chooses above/below using available
space; its caret tracks the anchor within constrained horizontal bounds. A
manual popover lifts the same element to the top layer in supported browsers;
dialog-local fixed placement remains the fallback. Layout mutations and resize
observation reposition it. Detached/hidden anchors, page scroll, resize and
visual-viewport changes dismiss stale help. Scrolling tooltip content is allowed.
Existing reduced-motion rules remain.

## Verification and limits

- `python -m pytest -q tests`: **182 passed**, one warning. This
  includes the requested dashboard/insights/notifications/trade-dashboard/Edge
  suites and their existing release gate.
- The nested native Node suites passed **24 JSDOM scenarios** and **32
  notification scenarios**. JSDOM/axe reported no serious/critical findings in
  tested views; layout/color-contrast analysis is excluded.
- JavaScript syntax, Python compilation and `git diff --check` passed.
- Fresh generated fixture sites are produced through the owning builders by the
  tests. Immutable-input and public-output sanitation regressions pass. No
  production artifacts or credentials were used as test input.
- Synthetic geometry checks cover **1920×1080, 1440×900, 1180×820, 820×1180 and
  390×844**, edge clamping/carets, visual-viewport offsets, layout mutations,
  detached anchors, keyboard overflow scrolling and scroll/resize dismissal.
- **No screenshots or rendered responsive acceptance:** Chrome is unavailable in
  the Browser connection. Its skill requires the requested Chrome connection;
  no other browser was substituted. Real Chrome layout/caret/CSP, page horizontal
  overflow, touch usability and iPhone Safari/physical-device acceptance remain
  unverified. Connect Chrome via Settings → Computer use, then perform these
  checks on a generated local fixture before release.
- **Full Linux verifier remains pending:** the Windows `verify.sh` attempt could
  not resolve required `dirname`/`mktemp` shell utilities. Its unchanged embedded
  Python workflow/state assertions and shell syntax passed separately. All four
  canonical Git blob SHA-256 values match `MANIFEST.sha256`; local raw recovery
  files differ only by Windows CRLF endings. The full Linux script must still run
  in CI; these supplemental checks are not a claimed `VERIFICATION PASSED` run.

## Operational checkpoint; no new deployment

The read-only 16:56–17:03 UTC audit inspected all 114 canonical runs and all 144
artifacts. Repository identity, main, exact producer attempts/jobs, ancestry and
high-water marks match the prior release. No newer eligible producer or active
eligible writer was found.

| Pipeline | Protected artifact | Successful producing run / attempt | Job |
|---|---:|---|---:|
| Legislative | `9734211271` | [33318579174](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33318579174) / 1 | `99276401831` |
| Executive | `9732455687` | [33312565343](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33312565343) / 1 | `99260139758` |
| AI | `9734221839` | [33318614858](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33318614858) / 1 | `99276494661` |

IDs, reported ZIP digests and attempt lineage are unchanged. Archive contents and
ledger counts were not independently reopened/recounted in this presentation-only
session. No production restore, state write, collector, analysis, simulation,
external alert or credential test occurred.

Prior main CI [33323430401](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430401)
and Pages [33323430450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430450)
remain successful, attempt 1, at `12d5896`. Pages artifact is `9735544864`.
Live root, Wallboard, Edge and insights return HTTP 200 and the published build
SHA remains `12d58964060885696ef4f5d3724ba5575de33fb2`. These runs do **not** verify
or publish the new contextual-help code.

Issue #1, held PR #3, same-ID rename/privacy, legacy retirement settings, two
obsolete queued runs and Gmail delivery proof remain separate open work.

## Later contextual-help candidates

“Counts toward Edge”, exclusion/quality notes, disclosure lag and valuation
timestamps may benefit from targeted help later. No new calculations or broad
tooltip coverage were added for those concepts in this pass.
