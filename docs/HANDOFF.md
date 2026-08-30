# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Work record: **issue #4 — Deliver the read-only commercial PolitiTrack dashboard redesign**

## Current task

The approved UI is merged and deployed through the canonical Pages publisher.
Current task: retain the verified release record and finish device acceptance.
The owner explicitly requested deployment after disclosure of unavailable
Chrome/iPhone/CHG90 acceptance. Do not claim complete device acceptance.
Canonical repository: `maglothinm/MyETF-Intelligence`, ID **1349678672**,
default `main`; still public/pre-rename. Never use legacy `maglothinm/MyETF`.

The UI-only branch `codex/dashboard-redesign` is based on live main `4a9135a`.
Held `codex/production-remediation` / PR #3 remains untouched. This UI release has
no workflow, state-schema, collector, analyst-runtime, scoring, alert or
simulation-contract diff from main.

## Delivered source and local evidence

- Generator-owned assets implement Overview, Signals, Investor Edge, $10K Agent,
  Records and Operations. Root/wallboard/Edge URLs, CSVs, evidence and GitHub
  simulation links are preserved.
- Additive `dashboard-insights.json` drives Overview; full ledgers load on demand
  with bounded rendering, debounced search, sorting and explicit date bases.
- Coverage, parsed trades, access-required inventory and manual exceptions remain
  distinct. Missing evidence stays unavailable/unknown. Only High Priority and
  Watchlist signals qualify. Edge methodology is unchanged; insufficient history
  never appears as zero performance.
- Browser-local notifications/settings are bounded; hydration is silent; failed
  rendering does not advance the baseline. Sound defaults off and requires an
  explicit user gesture. No external alert behavior is changed.
- Passive wallboard retains five-minute refresh, countdown, fullscreen, wake lock,
  orientation logic and last-known-data preservation. Risk dialogs/tooltips pass
  DOM fixture checks, including focus restoration.
- $10K result remains SIMULATED, SINGLE-RUN HISTORICAL REPLAY; independent replay
  history is not persistent portfolio performance.
- Final local active suite: **181 passed**. Final targeted suite: **9 passed**, including
  additive model/notification/DOM suites. Included are **61 model cases**,
  **32 native Node notification scenarios**, and **12 JSDOM scenarios**. Axe found
  zero serious/critical findings in tested fixture views; DOM emulation cannot
  assess contrast/layout. Linux `verify.sh` is invoked by the existing CI test
  entry point, without workflow edits.
- Copied-input generation reconciles 5,079 filings, 60 transactions, 1,496 reviews,
  11 analyses, zero qualifying signals/open positions, 1 manual exception and
  1,495 access-required records. Local static HTTP smoke passed.
- Immutable input/copy manifest: **209 hash/size checks, zero differences**.
  No collectors, AI, simulations, external alerts or heartbeats were invoked.

## Release checkpoints

Fresh audit at 16:35 UTC verified global producer high-water marks, exact
attempts/jobs, ZIP digests, inventories and prior ledger continuity:

| Pipeline | Artifact ID | Producing run / attempt | Job ID |
|---|---:|---|---:|
| Legislative | `9734211271` | `33318579174` / `1` | `99276401831` |
| Executive | `9732455687` | `33312565343` / `1` | `99260139758` |
| AI | `9734221839` | `33318614858` / `1` | `99276494661` |

Latest isolated replay: artifact `9734790733`, run `33320677882` / attempt 1,
job `99281977011`; two independent rows with preserved predecessor prefix.
These IDs are checkpoints, never fixed future restore targets.

Rollback Pages: successful `33320697336` / attempt 1, artifact `9734796157`,
exported ZIP SHA-256
`e8dc54967255af1fca24ed0f16383b3b2fa145cca947a8ec1d133e3ab4c0bca2`.
The old live files matched that artifact.

## Verified deployed release

PR [#5](https://github.com/maglothinm/MyETF-Intelligence/pull/5) merged UI source
`e2f71cff8029871656ba2dbd8c4021e406ea2e9c` as
`12d58964060885696ef4f5d3724ba5575de33fb2` on canonical `main`. The merge tree
exactly matches the tested PR tree. This evidence update changes documentation
only and does not change the deployed application source.

| Evidence | Verified result |
|---|---|
| PR CI | [33323384450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323384450), attempt 1, job `99289162854`; success |
| Main CI | [33323430401](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430401), attempt 1, job `99289284185`; success |
| CI coverage | 77 selected tests in each run; included release gate executes additive UI suites and Linux `verify.sh`, requiring `VERIFICATION PASSED` |
| Pages | [33323430450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430450), attempt 1, `push`; success |
| Pages jobs | Build `99289284456`; deploy `99289373251`; both successful |
| Pages artifact | `9735544864`, exact build-attempt window and ZIP digest verified |
| Pages ZIP SHA-256 | `0edc98bfc0176f4b2407edfd15218ccb76451426a99380b7a39a6172f107c692` |
| Live acceptance | 2026-08-30 16:49:28 UTC: 21 fixed root/Wallboard/Investor Edge/assets/JSON URLs returned HTTP 200 and exactly matched the Pages artifact |
| Deployed build SHA | `dashboard-insights.json.build_sha` equals `12d58964060885696ef4f5d3724ba5575de33fb2` |
| Continuity | Actual restore logs, newest global authority and high-water checks passed; all three protected ZIPs and full inventories are unchanged from the release checkpoint |
| Simulation isolation | `9734790733` and its two replay rows unchanged; no new simulation run |
| Final active-run inventory | No active eligible production writer; only the two previously known obsolete queued runs remain |

Live [dashboard](https://maglothinm.github.io/MyETF-Intelligence/),
[Wallboard](https://maglothinm.github.io/MyETF-Intelligence/wallboard.html) and
[Investor Edge](https://maglothinm.github.io/MyETF-Intelligence/investor-edge.html)
are deployed. This is HTTP/content acceptance, not real-browser visual or device
acceptance. No production-state artifact was uploaded by the Pages run.


## Remaining limits and next safe action

1. Keep issue #4 open for real Chrome, current iPhone Safari touch/audio,
   responsive screenshots/console/CSP and rotated CHG90 physical acceptance.
   No browser was available for those checks. DOM emulation is not device proof.
2. Use the existing deployed UI; preserve the recorded rollback Pages artifact.
   Do not dispatch collectors, AI, simulations or external alerts for visual QA.
3. Before any later production work, requery canonical state and exact artifact
   provenance; the recorded IDs are checkpoints, not permanent restore targets.
4. The local tracked tree is clean after this documentation-only evidence commit.
   Pre-existing untracked `.codex/` is preserved; ignored audit exports/test
   fixtures remain local and must never be published as production authority.

Separate open work: obsolete queued runs `33219808359` and `33221027676`
remain uncontained (zero jobs/artifacts at audit); PR #3 and issue #1 stay held.
Same-ID rename/privacy, legacy Actions/Pages/archive settings and Gmail delivery
proof are unchanged/unverified. Do not close issue #1, rebaseline state, or claim
duplicate-writer retirement complete.
