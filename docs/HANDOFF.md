# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Work record: **issue #4 — Deliver the read-only commercial PolitiTrack dashboard redesign**

## Current task

Merge and deploy the approved UI through the existing canonical Pages publisher.
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
- Local active suite: **180 passed**. Final targeted suite: **9 passed**, including
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

UI PR, merge SHA, CI and new Pages evidence: **pending**. Deployment URL remains
`https://maglothinm.github.io/MyETF-Intelligence/`.

## Remaining limits and next safe action

1. Commit/push the UI branch and open one PR. Wait for successful CI, including
   Linux `verify.sh`, and honor repository review rules.
2. Merge the checked SHA under explicit owner authorization; allow the existing
   main-push publisher to deploy. Do not dispatch production workflows.
3. Verify exact build/deploy attempt, consumed artifact IDs, unchanged protected
   snapshots and live root/wallboard/Edge/JSON/asset bytes, including build SHA.
4. Record the final SHA, runs and live results here and in PROJECT_STATE.
5. Keep issue #4 open for real Chrome, current iPhone Safari touch/audio,
   responsive screenshots/console/CSP and rotated CHG90 physical acceptance.
   No browser was available for these checks. DOM emulation is not device proof.

Separate open work: obsolete queued runs `33219808359` and `33221027676`
remain uncontained (zero jobs/artifacts at audit); PR #3 and issue #1 stay held.
Same-ID rename/privacy, legacy Actions/Pages/archive settings and Gmail delivery
proof are unchanged/unverified. Do not close issue #1, rebaseline state, or claim
duplicate-writer retirement complete.
