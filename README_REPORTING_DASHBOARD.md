# PolitiTrack filing-review dashboard

## Purpose

The tracker originally proved that government sources were being checked, but it did not provide a practical place to review what had been filed. This reporting layer converts the durable tracker state into a browser-accessible filing and transaction feed.

## What changes

- Catalogs every House, Senate, and OGE filing visible to a tracker run, including already-seen baseline records.
- Preserves purchases, sales, and exchanges in an all-transaction ledger while retaining the purchase-only ledger for compatibility.
- Retains a compact run history with source counts and errors.
- Adds latest-filings and latest-transactions CSV artifacts to every tracker run.
- Adds human-readable tables and official filing links to the GitHub Actions run summary.
- Sends a Pushover alert for each newly processed filing rather than only equity-like purchases.
- Publishes a searchable GitHub Pages dashboard after each Legislative or Executive run.

## Dashboard views

The static site contains:

- **Filings** — every cataloged record, filer, role or jurisdiction, status, transaction counts, and official link.
- **Transactions** — purchases, sales, and exchanges with owner, ticker or asset, amount range, dates, and official link.
- **Review queue** — paper reports, request-only OGE records, and parser exceptions that require human review.
- **Run history** — retained tracker successes, source counts, new-record counts, and errors.
- **AI candidates** — final/base score, class, evidence, review band, source links, and the candidate's Investor Edge score, modifier, confidence, observation count, relevant followable alpha, followable hit rate, sector alpha, and disclosure lag.
- **Investor Edge** — a heat map of normalized filer/owner histories with 5/20/60/120-session outcomes and a per-investor drilldown into identity, sector evidence, eligibility, and prior-trade picker/followable return details.
- **Paper portfolio** — simulated entries and exits used only for prospective research evaluation.

The principal views are searchable and exportable to CSV. `data/ai-analyses.csv` contains flattened Investor Edge display fields; full profiles and trade outcomes remain in JSON. Missing historical observations display as an em dash and export blank rather than being represented as zero.

## Coverage status

A filing marked **Cataloged only** was visible to the source collector but was already part of the silent baseline before this reporting upgrade. It has an official link, but its transaction rows have not necessarily been parsed. New filings are marked **Processed** or **Review required**.

This upgrade does not silently claim historical transaction coverage. A separate, controlled backfill is required to parse all pre-upgrade documents.

## GitHub Pages deployment

The canonical repository publishes from GitHub Actions:

1. Open **Settings** in the PolitiTrack repository.
2. Open **Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Open **Actions → Legislative purchase tracker v2 → Run workflow** and start the manual run.
5. Do the same for **Executive purchase tracker**.
6. The `Publish government trade dashboard` workflow will run after each tracker. It can also be run manually.

Production Pages URL:

```text
https://maglothinm.github.io/PolitiTrack/
```

No tracker reinitialization is permitted. The collector workflows expose no initialization or historical-alert bootstrap inputs and hard-code both behaviors off. Existing durable state is restored from production artifacts. A missing artifact fails closed; recovery requires a separately approved procedure.

## Durable files

For each branch, the tracker state artifact now contains:

```text
state.json
filings.jsonl
transactions.jsonl
purchases.jsonl
pending-review.jsonl
runs.jsonl
```

The dashboard workflow downloads the newest unexpired Legislative and Executive state artifacts, builds the site in memory, and deploys only the generated static files. Tracker data is not committed to the Git branch.

## AI candidate and paper-portfolio layer

When `AI_ANALYSIS_ENABLED=true`, the dashboard also publishes evidence-constrained candidate rankings and a simulated paper portfolio. Every build includes `investor-edge.html` and `data/investor-edge.json`; the view populates as eligible profiles and completed horizons become available. Normal AI runs enable Investor Edge by default. Low-confidence histories are visually de-emphasized, and the drilldown should be reviewed before treating leaderboard differences as meaningful. See [`README_AI_FILING_ANALYST.md`](README_AI_FILING_ANALYST.md) for the analyst and [`README_INVESTOR_EDGE.md`](README_INVESTOR_EDGE.md) for the bounded historical-performance modifier, backfill limits, and interpretation caveats.

## Simulation boundary

PolitiTrack exposes two distinct simulation actions:

- [`Run Simulation`](.github/workflows/manual_test.yml) is an isolated Investor Edge acceptance check. It builds a one-day dashboard artifact from temporary state copies, includes an alert preview, and does not deploy to production Pages.
- [`Run $10K portfolio simulator`](.github/workflows/filing_simulation.yml) runs an isolated historical replay with $10,000 starting capital and a $20,000 goal. Its replay history persists only in the simulation-named `simulation-state` artifact and remains separate from the production paper portfolio.

Neither action can upload a production tracker or AI state artifact. Use their outputs for simulation review; use production workflow runs and deployed URLs to verify live operation.
