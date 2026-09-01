# Contextual-help implementation and acceptance record

Issue [#6](https://github.com/maglothinm/MyETF-Intelligence/issues/6). The implementation
and publication are complete; browser/device acceptance remains open.

## Contextual-help publication — verified 2026-08-30 17:36 UTC

The owner explicitly requested publication after the Chrome/device gap was
disclosed. PR [#7](https://github.com/maglothinm/MyETF-Intelligence/pull/7) merged
tested source `2a955f571c2cd4cf26b033984daa39904c11d64c` as
`1aa87398b53689873de350155d33afdb993fb036` on canonical `main`. Their trees match.
Documentation-only successors do not change the deployed application source.

[Live dashboard](https://maglothinm.github.io/MyETF-Intelligence/),
[Investor Edge](https://maglothinm.github.io/MyETF-Intelligence/investor-edge.html)
and [Wallboard](https://maglothinm.github.io/MyETF-Intelligence/wallboard.html)
are published from repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.

| Release evidence | Verified result |
|---|---|
| PR CI | [33325538713](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325538713), attempt 1, job `99294887628`; success, 78 selected tests |
| Main CI | [33325629684](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629684), attempt 1, job `99295130888`; success, 78 selected tests |
| Linux verifier | Both CI runs passed the existing release gate, which executes full `verify.sh` and requires `VERIFICATION PASSED` |
| Pages | [33325629663](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629663), attempt 1; success; build `99295130679`, deploy `99295188583` |
| Pages artifact | `9736138918`; exact successful attempt/build window and ZIP digest verified |
| Pages ZIP SHA-256 | `f8d5a8e65fa26e34b06e425a6016100fd0e488b312a3aa2fae5731a378acf283` |
| Live verification | 17:36:13 UTC: 21 root/Wallboard/Edge/assets/JSON URLs returned HTTP 200 and exactly matched the Pages artifact |
| Published build | `1aa87398b53689873de350155d33afdb993fb036` |
| Source-content check | 27 additional checks passed across 11 fixed live URLs, including exact source asset/script comparisons, shared copy, help/touch attributes and persistent warnings |

The earlier Windows verifier limitation is resolved for this release by Linux CI.
Local verification remains **182 tests passed**, including **24 JSDOM scenarios**
and **32 native Node notification scenarios**. JSDOM is an optional dependency
not provisioned by CI; its local results are not inferred remote CI results.
Real Chrome/Safari/touch, responsive screenshots, rendered overflow/caret/CSP and
physical-device acceptance remain unverified under issue #6.

### Protected inputs and continuity

Scheduled Executive and downstream AI runs completed before publication. Their
newer artifacts passed exact workflow/job/attempt identity, ancestry, producer
high-water checks, ZIP digests, schema and full inventory/record continuity
against original, prior and last-deployed checkpoints. No eligible writer was
active before merging or at final verification.

| Pipeline | Newest protected artifact | Successful run / attempt | Job | Retained counts |
|---|---:|---|---:|---|
| Legislative | `9734211271` | `33318579174` / 1 | `99276401831` | 983 filings; 65 transactions; 19 purchases; 1 review; 27 runs |
| Executive | `9736054489` | `33325239324` / 1 | `99294089255` | 4,109 filings; 1,495 reviews; 20 runs |
| AI | `9736064296` | `33325343519` / 1 | `99294369216` | 12 analyses; 29 runs |

Actual publisher restore logs, fresh global authority checks and downloaded
protected ZIPs/full inventories prove these inputs were unchanged through
publication. Published counts reconcile to 5,079 filings, 60 transactions,
1,496 reviews and 11 analyses. The Pages run uploaded only `github-pages`.
No collectors, AI, simulations, external alerts or production-state writers were
dispatched by this release task, and no workflow rules were changed.

Isolated simulation artifact `9734790733`, run `33320677882` / attempt 1, remains
unchanged with two replay history rows and preserved predecessor bytes.
Known-good rollback Pages is `33325376676` / attempt 1, artifact `9736074454`,
exported ZIP SHA-256
`910f9e40171a11ea3f0ade63b6dae4386ca4979faaa48d31c7cc4e785739b371`.
Ignored local evidence: `.remediation/tooltip-publish-preflight`,
`.remediation/tooltip-published/deployment-verification.json`, and
`.remediation/tooltip-live-content.json`. These are recovery/verification records,
not alternate production authority.

Only the two known obsolete queued runs remained at final verification. Issue #1,
held PR #3, repository rename/privacy, legacy settings retirement and Gmail
delivery proof remain separate open work. Issue #6 remains open for device
acceptance, not because publication is pending.

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
| `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, this record | Implementation, design decisions, verified publication and remaining acceptance limits |

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
  checks on a generated local fixture or the published site to finish acceptance.
- **Earlier Windows verifier limitation (now resolved by release CI):** the Windows `verify.sh` attempt could
  not resolve required `dirname`/`mktemp` shell utilities. Its unchanged embedded
  Python workflow/state assertions and shell syntax passed separately. All four
  canonical Git blob SHA-256 values match `MANIFEST.sha256`; local raw recovery
  files differ only by Windows CRLF endings. The later PR/main Linux CI passed the full script through the existing release
  gate. The supplemental Windows checks alone were not a complete verifier run.

## Earlier implementation-session checkpoint — before publication

The read-only 16:56–17:03 UTC audit inspected all 114 canonical runs and all 144
artifacts. Repository identity, main, exact producer attempts/jobs, ancestry and
high-water marks match the prior release. No newer eligible producer or active
eligible writer was found.

| Pipeline | Protected artifact | Successful producing run / attempt | Job |
|---|---:|---|---:|
| Legislative | `9734211271` | [33318579174](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33318579174) / 1 | `99276401831` |
| Executive | `9732455687` | [33312565343](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33312565343) / 1 | `99260139758` |
| AI | `9734221839` | [33318614858](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33318614858) / 1 | `99276494661` |

At that earlier checkpoint, IDs, reported ZIP digests and attempt lineage were
unchanged. Archive contents and ledger counts were not reopened in that
implementation session; full publication continuity was later verified above.
No production restore, state write, collector, analysis, simulation,
external alert or credential test occurred.

Prior main CI [33323430401](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430401)
and Pages [33323430450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430450)
were successful, attempt 1, at `12d5896`. Pages artifact was `9735544864`.
Live root, Wallboard, Edge and insights returned HTTP 200 and the published build
SHA was `12d58964060885696ef4f5d3724ba5575de33fb2`. Those older runs did not verify or publish this tooltip release; the later
publication evidence is recorded above.

Issue #1, held PR #3, same-ID rename/privacy, legacy retirement settings, two
obsolete queued runs and Gmail delivery proof remain separate open work.

## Later contextual-help candidates

“Counts toward Edge”, exclusion/quality notes, disclosure lag and valuation
timestamps may benefit from targeted help later. No new calculations or broad
tooltip coverage were added for those concepts in this pass.
