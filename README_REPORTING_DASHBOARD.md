# PolitiTrack filing-review dashboard

## Purpose

The tracker originally proved that government sources were being checked, but it did not provide a practical place to review what had been filed. This reporting layer converts the durable tracker state into a browser-accessible filing and transaction feed.

## Existing reporting data

The collectors already supply the following reporting layer. The dashboard
redesign is presentation-only: it does not change collection, parsing, scoring,
portfolio accounting, alert delivery, or production-state continuity.

- Catalogs every House, Senate, and OGE filing visible to a tracker run, including already-seen baseline records.
- Preserves purchases, sales, and exchanges in an all-transaction ledger while retaining the purchase-only ledger for compatibility.
- Retains a compact run history with source counts and errors.
- Adds latest-filings and latest-transactions CSV artifacts to every tracker run.
- Adds human-readable tables and official filing links to the GitHub Actions run summary.
- Sends a Pushover alert for each newly processed filing rather than only equity-like purchases.
- Publishes a searchable GitHub Pages dashboard after each Legislative or Executive run.

## Dashboard views

The optional [30-Day Filing Vault](docs/FILING_VAULT.md) adds consistent
**View Filing** and **Official Source** actions to evidence-bearing records.
`filing-vault.html` provides a searchable inventory, acknowledgement, original
document viewer and provenance. Its private Flask/PostgreSQL/Supabase runtime
must be configured separately; static Pages alone does not cache documents.
The publisher reads the public repository variable `FILING_VAULT_API_ORIGIN`.
Never put Vault storage credentials in GitHub Pages or its build variables.

The static root dashboard has six directly linkable destinations:

| Destination | Contents |
|---|---|
| **Overview** (`#overview`) | Deterministic Situation Brief, qualifying signals, device-local changes, manual exceptions, coverage counts, parsed-transaction composition, and retained run health |
| **Signals** (`#signals`) | High Priority and Watchlist cards, followed by the searchable table of all AI classifications and evidence |
| **Investor Edge** (`#investor-edge`) | Published profile summary and links to the preserved heat map, methodology, and trade-level drilldowns at `investor-edge.html` |
| **$10K Agent** (`#agent`) | Latest isolated historical replay and the separate production paper-position table |
| **Records** (`#records/filings`, `#records/transactions`, `#records/reviews`) | Retained filings, parsed transactions, and review inventory with official disclosure links |
| **Operations** (`#operations`) | Legislative, Executive, and AI run evidence, coverage totals, and publication details |

Signal cards preserve final/base scores, classification, direction, entry-review
status, and Investor Edge evidence. Transaction, filing, observation, analysis,
and quote times stay distinct. Only valid numeric prices produce a price-band
graphic; missing values display **Unavailable**. Weak signals and archives never
fill an empty actionable board. The board shows at most 48 cards; the complete
retained analyses remain available in the table and CSV.

Record tables retain CSV downloads and add debounced search, explicit date-basis
filters, column sorting, sticky headers, and 50-row pagination. Large ledgers
load only when their destination is opened. `data/ai-analyses.csv` retains
flattened Investor Edge fields; full profiles and outcomes remain in JSON.
Missing or insufficient outcomes are unavailable, not zero or neutral returns.

The compact **Actions** drawer contains **Open Run Simulation** and **Open Run
$10K Agent**. These are GitHub Actions links: the page does not dispatch jobs or
show invented queued/running progress. **Methodology & Risk** opens the complete
disclosure in a dialog. Context help supports hover, keyboard focus, tap/click,
Escape, and outside dismissal; essential simulation and price-delay labels stay
visible without opening a tooltip.

## Generated sources and local builds

`scripts/build_trade_dashboard.py` remains the build entry point. It reads the
checked-in HTML/CSS/JavaScript in `scripts/dashboard_assets/` and combines the
shared utilities and notification engine into the generated scripts. The
presentation-only `scripts/dashboard_insights.py` produces versioned
`data/dashboard-insights.json` from existing records. Overview initially fetches
this compact model rather than the full filing and review ledgers. Existing
JSON/CSV filenames remain available. Do not edit generated Pages files or the
inactive `frontend/trades_dashboard` application.

Build from read-only fixture copies, never by running collectors to populate a
preview:

```text
python scripts/build_trade_dashboard.py --legislative-dir <copied-legislative> --executive-dir <copied-executive> --ai-dir <copied-ai> --simulation-dir <copied-simulation> --output-dir <temporary-site> --repository-url https://github.com/maglothinm/MyETF-Intelligence
python -m http.server 8765 --directory <temporary-site>
```

The simulation input is optional. Input-state hashes must remain unchanged after
generation. Public output removes credentials, recipient information, heartbeat
URLs, and internal notification payloads. The frontend has a self-only CSP and
no CDN, analytics, charting framework, live market request, or heartbeat probe.

## Browser-local changes and sound

The first complete successful render silently establishes the browser baseline.
Later successful refreshes compare stable record IDs, group routine filing and
transaction changes, and retain a bounded Notification Center. A failed refresh
preserves the last rendered data and does not advance that baseline. This is
per-browser/per-device state, not an account or production ledger.

The center supports acknowledgement, one-hour snooze, category mute, volume,
quiet hours, and **Off / High Priority Only / All eligible events** sound modes.
Sound defaults off and requires an explicit user gesture. High Priority Only
also permits supported failure incidents; ordinary filings and refreshes stay
silent. Quiet hours suppress audio, not visual history. Reloads and unchanged
refreshes do not replay events. History is capped at 150 entries; record-membership
snapshots and deduplication storage are also bounded. If a membership category
exceeds its bound, its delta is suppressed rather than labeling old records new.

Sound is dependable only while the page is open and active. Browser storage or
audio restrictions can leave it unavailable. Local settings never alter Gmail,
Pushover, or Healthchecks, which remain the background channels. Test sound does
not run a workflow or send a notification. No Web Push or service worker is added.

## Coverage status

A filing marked **Cataloged only** was visible to the source collector but was already part of the silent baseline before this reporting upgrade. It has an official link, but its transaction rows have not necessarily been parsed. New filings are marked **Processed** or **Review required**.

This upgrade does not silently claim historical transaction coverage. A separate, controlled backfill is required to parse all pre-upgrade documents.

Coverage graphics show absolute counts of separate populations, not a conversion
funnel. Transaction composition describes the parsed post-upgrade ledger plus
retained earlier purchases, not complete historical government trading or exact
dollar exposure. Review inventory distinguishes **Access/request required**,
**Manual/parser exception**, and **Other/uncategorized**; OGE access requests are
informational inventory rather than thousands of system failures.

Run health distinguishes successful execution from current monitoring. The central
Python freshness policy requires Legislative success within 30 minutes (15-minute
cadence), Executive success within 60 minutes (30-minute cadence), and downstream
AI success within 75 minutes (collector-triggered, allowing its 45-minute runtime).
Overall precedence is **failure > stale > unknown > success**. A latest failure
outranks a recent earlier success; zero new filings is not a failure.

**Monitoring current** appears only when all required workers meet the policy.
Open pages age the retained evidence even if publishing stops. **Source data
through** comes from production source observations/collector completion; page
generation and AI/portfolio refresh do not advance it. Operations separately shows
generation time and each worker's attempt, success, cadence, next expected check,
age, overdue duration, estimated missed intervals, conclusion/errors and trigger.
Unknown timestamps stay unavailable. See [freshness semantics and root cause](docs/SCHEDULER_FRESHNESS.md)
and [external scheduler activation](docs/EXTERNAL_SCHEDULER.md).

## GitHub Pages deployment

The canonical repository publishes from GitHub Actions:

1. Open **Settings** in the PolitiTrack repository.
2. Open **Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Verify eligible, unexpired protected artifacts and preserve the previous Pages artifact for rollback.
5. Use the existing `Publish government trade dashboard` workflow for a UI-only release. It also runs after the existing tracker workflows.
6. Verify the root, `wallboard.html`, and `investor-edge.html`, the tested build SHA, published counts, and unchanged production-state evidence.

Do not dispatch collectors, AI analysis, simulations, or external alerts merely
to populate or deploy this presentation. Repository checks and the operating
contract remain release gates.

Production Pages URL:

```text
https://maglothinm.github.io/MyETF-Intelligence/
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

The $10K display is labeled **SIMULATED — SINGLE-RUN HISTORICAL REPLAY**. It shows
starting/current replay value, actual dollar/percentage change, remaining amount
to the $20,000 objective, and retained entry/valuation times and evidence links.
Starting capital is not goal progress. Independent replay records are not joined
into an equity curve: **No persistent portfolio history yet.** An unpriced replay
does not claim investment performance; a portfolio without open positions says
**No open paper positions**.

## Acceptance limits

Automated checks and emulated viewport reviews do not establish real-device
acceptance. Actual Chrome desktop, current iPhone Safari touch behavior, and the
physical rotated CHG90 display have not yet been validated for this redesign.
Record live deployment and device results separately in `docs/HANDOFF.md`; do not
infer them from a successful local build.
