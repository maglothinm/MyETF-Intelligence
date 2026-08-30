# PolitiTrack

PolitiTrack is the canonical production system for monitoring public U.S. government financial disclosures, preserving the underlying evidence, ranking newly disclosed equity purchases, and evaluating those signals in a paper-only research portfolio.

The authoritative repository is [`maglothinm/PolitiTrack`](https://github.com/maglothinm/PolitiTrack). `MyETF` and `MyETF-Intelligence` are historical aliases for this program; the public `MyETF` fork is legacy-only and must not run production workflows.

## Production topology

| Layer | Production responsibility |
|---|---|
| `Legislative purchase tracker v2` | Polls House and Senate disclosure sources and updates Legislative state. |
| `Executive purchase tracker` | Discovers OGE Form 278-T filings and updates Executive state. |
| `AI filing analyst and paper portfolio` | Enriches parsed purchases, applies deterministic scoring and Investor Edge, delivers configured candidate alerts, and updates the paper portfolio. |
| `Publish government trade dashboard` | Builds and deploys the static review dashboard and CHG90 wallboard from successful state artifacts. |
| [`Run Simulation`](.github/workflows/manual_test.yml) | Runs an isolated Investor Edge acceptance check and publishes a one-day dashboard artifact. |
| [`Run $10K portfolio simulator`](.github/workflows/filing_simulation.yml) | Advances a separate persistent paper simulation with $10,000 starting capital and a $20,000 goal. |

The deployed dashboard is:

```text
https://maglothinm.github.io/PolitiTrack/
```

The portrait and ultrawide wallboard is:

```text
https://maglothinm.github.io/PolitiTrack/wallboard.html
```

GitHub Pages is a separate access boundary from repository privacy. Confirm that the dashboard's visibility is appropriate before treating a private repository as protection for published Pages data.

## Durable state contract

Production continuity is carried by these GitHub Actions artifacts:

- `legislative-tracker-state`
- `executive-tracker-state`
- `ai-analysis-state`

Their compatibility-sensitive paths remain under `.trade-tracker/`. Existing artifact names, cache keys, completed IDs, and ledgers are intentionally preserved.

Never create a new baseline during routine operation or repository maintenance. Legislative and Executive workflows hard-code state initialization and historical-alert bootstrapping off; those controls are not exposed to manual runs. A missing required state artifact fails closed. Recovery may proceed only through a separately approved procedure that identifies and verifies the known-good state; do not substitute an empty state. Simulations must never upload, cache, or overwrite any production state artifact.

Repository identity, operational state, decisions, and the current handoff are defined in [`AGENTS.md`](AGENTS.md), [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md), [`docs/DECISIONS.md`](docs/DECISIONS.md), and [`docs/HANDOFF.md`](docs/HANDOFF.md).

## Capabilities

- Fail-closed House, Senate, and OGE collection from official public sources.
- Filing inventory, normalized transaction ledger, purchase-only compatibility ledger, review queue, and retained run history.
- Pushover filing alerts and optional Pushover and Gmail candidate-alert delivery.
- Evidence-constrained OpenAI analysis with deterministic scoring and hard caps.
- Investor Edge historical-performance profiles and a bounded score modifier.
- Paper-only positions with no brokerage credentials or order-submission path.
- Searchable static dashboard, CSV exports, Investor Edge drilldown, and CHG90 wallboard.
- One-run Investor Edge acceptance testing and a distinct persistent $10K paper simulator, both isolated from production state.

Detailed operating guides:

- [`README_GOVERNMENT_TRADES.md`](README_GOVERNMENT_TRADES.md)
- [`README_AI_FILING_ANALYST.md`](README_AI_FILING_ANALYST.md)
- [`README_INVESTOR_EDGE.md`](README_INVESTOR_EDGE.md)
- [`README_REPORTING_DASHBOARD.md`](README_REPORTING_DASHBOARD.md)
- [`README_WALLBOARD_PRIVATE_REPO.md`](README_WALLBOARD_PRIVATE_REPO.md)
- [`BRANDING_MIGRATION.md`](BRANDING_MIGRATION.md)

## Required GitHub configuration

Review the official disclosure-site restrictions before setting:

```text
DISCLOSURE_TERMS_ACKNOWLEDGED=true
```

Production secrets and variables are documented in the component guides. The principal secrets are `OPENAI_API_KEY`, optional market-data keys, optional Pushover credentials, optional Gmail app credentials, and independent Healthchecks URLs. Do not commit secret values.

`AI_PAPER_TRADING_ONLY=true` is enforced by the workflow. PolitiTrack is for research and review; it does not place trades and is not investment advice.

## Safe manual operation

To run a collector without altering the established baseline:

1. Open the workflow in GitHub Actions.
2. Select `main`.
3. Select **Run workflow**.
4. Confirm in the log that the expected state artifact was restored before collection.

There are two separate simulation actions:

- **Actions → Run Simulation → Run workflow** is the isolated Investor Edge acceptance test. It clones production artifacts into temporary directories, uses deterministic local inputs, supplies no real notification credentials, and publishes only a one-day dashboard artifact.
- **Actions → Run $10K portfolio simulator → Run workflow** runs an isolated historical paper replay with $10,000 starting capital and a $20,000 goal. It retains only `simulation-state`, never receives live notification credentials, and cannot write production tracker, AI, or portfolio state.

## Local verification

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-tracker.txt -r requirements-ai.txt pytest==9.0.2
python -m pytest -q
git diff --check
```

Chromium and OCR dependencies are required for live OGE collection and image-only filings; see the collector guide for installation details.

## Coverage and use boundaries

“Fast” means detection after an official disclosure becomes public. It does not remove statutory reporting delays. OGE coverage is partial because many Executive-branch reports are held by employing agencies or require Form 201 requests. PolitiTrack records those limitations rather than claiming unavailable coverage.

House, Senate, and OGE systems publish statutory use restrictions. `DISCLOSURE_TERMS_ACKNOWLEDGED=true` records an operator acknowledgement; it is not a legal conclusion that a particular commercial, automated-investment, or redistribution use is permitted.
