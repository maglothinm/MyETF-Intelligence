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

Each view is searchable and exportable to CSV.

## Coverage status

A filing marked **Cataloged only** was visible to the source collector but was already part of the silent baseline before this reporting upgrade. It has an official link, but its transaction rows have not necessarily been parsed. New filings are marked **Processed** or **Review required**.

This upgrade does not silently claim historical transaction coverage. A separate, controlled backfill is required to parse all pre-upgrade documents.

## One-time GitHub Pages activation

After committing the reporting files:

1. Open **Settings** in the PolitiTrack repository.
2. Open **Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Open **Actions → Legislative purchase tracker → Run workflow** and run it with both boxes unchecked.
5. Do the same for **Executive purchase tracker**.
6. The `Publish government trade dashboard` workflow will run after each tracker. It can also be run manually.

Legacy Pages URL, retained until the GitHub repository rename and private-wallboard cutover:

```text
https://maglothinm.github.io/MyETF-Intelligence/
```

No tracker reinitialization is required. Existing durable state is preserved.

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

When `AI_ANALYSIS_ENABLED=true`, the dashboard also publishes evidence-constrained candidate rankings and a simulated paper portfolio. The build always includes an `investor-edge.html` heat-map shell, which populates after the optional feature is enabled and profiles exist. See [`README_AI_FILING_ANALYST.md`](README_AI_FILING_ANALYST.md) for the analyst and [`README_INVESTOR_EDGE.md`](README_INVESTOR_EDGE.md) for the bounded historical-performance modifier.
