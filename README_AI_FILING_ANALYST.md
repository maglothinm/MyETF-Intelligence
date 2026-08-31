# PolitiTrack AI filing analyst and paper-research portfolio

This layer runs after the Legislative or Executive collector completes successfully. It reviews newly parsed public-equity purchases, enriches them with market and SEC information, requests a constrained structured analysis from the OpenAI Responses API, applies deterministic scoring and entry-review rules, and publishes the result on the GitHub Pages dashboard.

It does **not** connect to a brokerage, place an order, or represent a score as certainty. `AI_PAPER_TRADING_ONLY=true` is enforced by the code and workflow.

## Processing sequence

1. Restore the newest provenance-valid Legislative, Executive and AI state artifacts, including exact successful producer-attempt and continuity checks.
2. Load the canonical combined retained transaction history from both branches; select new AI candidates separately without truncating Edge input.
3. When Edge is enabled, discover and persist every eligible profile within the configured population limit, then perform bounded global historical maintenance. This runs even with zero new AI candidates; an initial global failure stops candidate/market work.
4. For selected candidates, fetch the official filing document when directly accessible and extract text or OCR it.
5. Add current and historical price context when market-data keys are configured, and SEC issuer/insider context when `SEC_USER_AGENT` is configured.
6. Send the candidate's fixed evidence package to the OpenAI Responses API using strict JSON-schema output.
7. Calculate the base score with deterministic rules in `config/signal_rules.yml`.
8. Build the candidate's time-censored Investor Edge profile from the complete retained universe and apply its bounded modifier without overriding normal hard caps.
9. Calculate the volatility-aware entry-review band and maximum-chase rule; persist completed analyses and any immutable candidate-alert snapshots.
10. Perform applicable market-only refreshes and update simulated paper positions through their existing paths.
11. Refresh and persist the final global Edge inventory without starting a second historical-processing budget. Failure prevents candidate delivery and successful protected-state promotion.
12. Only with no prior run errors, deliver existing pending and newly queued candidate alerts through the same bounded, per-channel deduplicated path.
13. Finalize the run and persist its result. Only successful validated state is eligible for protected-artifact publication; the existing dashboard builder reads that inventory independently of qualifying cards.

The collector workflows are independent. An AI/API failure does not turn a successful House, Senate, or OGE collection into a failed collector run. The unprocessed transaction remains eligible for a later AI retry.

## Historical universe and bootstrap

The normalized `transactions.jsonl` files under
`.trade-tracker/legislative/` and `.trade-tracker/executive/` are the primary
historical inputs. `purchases.jsonl` provides compatibility for otherwise absent
older records, not a competing primary source. Stable `trade_id` deduplicates
overlaps. Pre-ID rows receive a deterministic full SHA-256 identifier based on
source/report identity, filer, disclosed owner, asset, ticker, transaction type,
transaction date and amount; observation time and input path do not affect it.
Branch/source/ledger provenance is retained, primary normalized fields take
precedence, and duplicate copies preserve the earliest valid observation timestamp.
Self, Spouse, Joint and other disclosed owners are not collapsed into one investor.

The analyst passes this complete `historical_transactions` universe to both
candidate Edge profiles and global maintenance. Its separate
`new_analysis_candidates` collection applies eligibility, already-analyzed IDs
and `AI_MAX_ANALYSES_PER_RUN`. A zero-candidate execution can therefore publish
building-history profiles and advance cached or provider-backed observations
without a model call or a new disclosure from any investor.

Profile discovery precedes market work. Backfill proceeds deterministically
breadth-first across identities, with a persistent last-investor cursor and
unattempted observations ahead of partial/unavailable retries. Later cached work
can still advance after the network budget is exhausted or set to zero. Existing
defaults remain 40 most-recent eligible purchases per identity, 40 published
identities, 30 observation attempts per run, 40 provider requests and a 2,200-day
historical lookback. The 30-observation limit is not a 30-day filing window.
Existing confidence, alpha horizons, modifier/hard caps and candidate-time
censoring are unchanged; current profiles do not rewrite old analysis decisions.

Catalog-only filings can still lack normalized transactions. Their reconstruction
belongs to the existing tracker writers, not the AI writer, using a separate
20-filing default budget (`HISTORICAL_FILING_BACKFILL_LIMIT_PER_RUN` or
`--historical-filing-backfill-limit-per-run`; `0` disables it). The same official
House, Senate and OGE scanners are used under the existing disclosure terms.
OGE Form 201 request-only records are not automatically retrieved. A validated
raw-source manifest permits cached-first PDF/Senate HTML parsing; exact schema,
path/hash checks and retention rules are documented in
[Cataloged-filing transaction bootstrap](README_INVESTOR_EDGE.md#cataloged-filing-transaction-bootstrap).
The manifest defaults inside restored tracker state. External manifests and
sources are not automatically uploaded, and flattened AI document-text caches
are not substitutes for original source documents.

Historical rows preserve normal IDs and the original filing's public-observation
semantics. They carry `historical_bootstrap: true` and are excluded from new AI
analysis selection, market-refresh upgrades and candidate alerts, including
manual reanalysis selection. Their filing/transaction records are also excluded
from new Notification Center events. Tracker baseline state and seen IDs are not
reset; ordinary new disclosures continue normally. This is additive reconstruction
from retained filings, never permission to initialize missing production state.

The [2026-08-31 validation report](docs/validation/investor-edge-bootstrap-2026-08-31.md)
records actual artifact-copy population counts, pending history and inaccessible
filings. Those local acceptance results do not establish production deployment.

## Required GitHub configuration

### Actions secret

Create this under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Required | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` | For new model analyses | OpenAI Responses API access; zero-candidate Edge maintenance makes no model request. |
| `PUSHOVER_API_TOKEN` | Already used | Candidate and workflow-failure alerts. |
| `PUSHOVER_USER_KEY` | Already used | Candidate and workflow-failure alerts. |
| `GMAIL_ADDRESS` | Optional | Enables Gmail SMTP as a second candidate-alert channel when paired with `GMAIL_APP_PASSWORD`; the account is also the recipient. |
| `GMAIL_APP_PASSWORD` | Optional | Gmail app-specific password—not the normal account password—used only when `GMAIL_ADDRESS` is also configured. |
| `FINNHUB_API_KEY` | Strongly recommended | Current U.S. equity quote for timely entry review and paper-position marking. |
| `ALPHAVANTAGE_API_KEY` | Recommended | Daily price/volume history, transaction-date close, and ATR calculation. |
| `AI_HEALTHCHECKS_PING_URL` | Optional | Independent dead-man monitoring for the AI workflow. |

The market-data secrets are optional at runtime. Without a current market price, deterministic rules cap a candidate at 59/100, so it cannot become a high-priority or watchlist paper entry. Pushover remains supported and can be made required with `AI_REQUIRE_PUSHOVER=true`; it is not required by default. Gmail is additive and optional; leave both Gmail values blank to disable it. **Suppress alerts** suppresses all candidate-delivery channels, while collector filing alerts remain independent.

### Actions variables

Create these under **Settings → Secrets and variables → Actions → Variables**:

| Variable | Recommended value | Purpose |
|---|---|---|
| `AI_ANALYSIS_ENABLED` | `true` | Enables automatic runs after successful collectors. |
| `OPENAI_MODEL` | `gpt-5.6-terra` | Balances analysis quality and API cost. |
| `OPENAI_REASONING_EFFORT` | `medium` | Analysis effort. |
| `AI_WEB_SEARCH_ENABLED` | `true` | Lets the model find current public policy, contracting, regulatory, and issuer context. |
| `AI_FETCH_DOCUMENT_TEXT` | `true` | Reads the official filing document rather than relying only on parsed rows. |
| `AI_MAX_ANALYSES_PER_RUN` | `20` | Cost and runtime limit. |
| `AI_REQUIRE_PUSHOVER` | `false` | Optionally treat Pushover candidate-alert delivery as required. Gmail alerts work without Pushover. |
| `INVESTOR_EDGE_ENABLED` | `true` | Enables the bounded historical-performance modifier. Set to `false` only for a controlled comparison or rollback. |
| `SEC_USER_AGENT` | `PolitiTrack research contact your-email@example.com` | SEC fair-access identification. Replace with an actual monitored contact address. |
| `ALPHAVANTAGE_ENTITLEMENT` | blank unless supplied | Optional Alpha Vantage entitlement. |

`AI_PAPER_TRADING_ONLY` is hard-coded to `true` in the workflow. There is no brokerage credential or order endpoint in this implementation.

## Production operation

The production AI history already exists in `ai-analysis-state`; routine runs must restore it rather than create an empty state. Missing, expired, invalid or ambiguous state is a continuity blocker. Recover the newest provenance-valid state with exact successful-attempt and producer high-water checks; do not silently fall back to an older artifact, cache or new baseline. See `AGENTS.md` and `docs/PROJECT_STATE.md` for the current operational gates.

When a manual production run is separately authorized and current safety gates are satisfied:

1. Open **Actions → AI filing analyst and paper portfolio**.
2. Select **Run workflow** on `main`.
3. Leave **Reanalyze the newest already-processed purchases** unchecked unless a controlled reanalysis is intentional.
4. Leave **Enable Investor Edge** selected; it is the normal default.
5. Select **Suppress alerts** for a no-delivery acceptance run, or clear it for normal configured delivery.
6. Set the maximum analyses to `20` or less.
7. Run the workflow and verify that the log restored `ai-analysis-state` before analysis.

Each successful scheduled or manual Legislative or Executive tracker run on the default branch automatically triggers the AI workflow. Pull-request collector runs are deliberately excluded from secret-bearing AI execution. Previously completed analysis IDs are skipped unless the model, rules, prompt version, or manual reanalysis setting changes.

The verified pre-rename dashboard URL is
`https://maglothinm.github.io/MyETF-Intelligence/`; the workflow derives the
repository path at runtime and will follow the in-place rename. Set
`DASHBOARD_URL` only for a deliberate custom or authenticated address.

## Dashboard output

The dashboard gains three research views:

- **AI candidates** — final and base scores, class, filer/owner, transaction timing, current price, price movement, entry status, review band, rationale, cautions, source links, and a compact Investor Edge summary. The summary includes modifier, confidence, observation count, relevant followable alpha, followable hit rate, sector alpha, and disclosure lag. Missing observations render as an em dash rather than a synthetic neutral value.
- **Paper portfolio** — simulated entry price, quantity, current/exit price, unrealized or realized P&L, return, and evaluation horizon.
- **Investor Edge** — a filterable historical-performance heat map with a per-investor drilldown for normalized identity, methodology, sector evidence, eligibility, and trade-by-trade picker/followable outcomes at 5/20/60/120 trading sessions.

Root and standalone Investor Edge views load the full published profile inventory
independently of qualifying signal cards. **Investor Edge History** reports
profiles, completed/building profiles, historical transactions, processed work and
pending observations. Leaderboard metadata also contains eligible-purchase and
unique-identity counts, Legislative/Executive transaction counts, actual provider
requests, the processing limit and aggregate exclusion reasons. See the
[metadata definitions](README_INVESTOR_EDGE.md#dashboard-and-candidate-surfaces).

A completed profile has no pending trade observations and meets the configured
minimum completed sample; other published profiles remain building, including
zero-observation profiles. Pending counts are trade-level work within the bounded
published population, not individual horizons or all cataloged source filings.
**Historical backfill current** means zero pending work in that population; it
does not certify complete source coverage or a sufficient sample for every
profile. Legacy artifacts without the metadata display unavailable counts and
unknown status rather than implying zero or current. Performance values are not
fabricated while history builds.

Downloads include:

- `data/ai-analyses.csv`
- `data/paper-portfolio.csv`
- `data/ai-runs.csv`

The analysis CSV flattens the display-oriented Investor Edge fields for downstream review. The durable JSON keeps the full nested profile and per-horizon observations.

The durable AI artifact contains:

- `state.json`
- `analyses.jsonl`
- `paper-portfolio.jsonl`
- `runs.jsonl`
- cached official-document text
- market and SEC caches
- Investor Edge profiles, leaderboard, observations, and bounded market/profile caches

## Score construction

The maximum score is 100:

| Component | Maximum |
|---|---:|
| Filer authority and subject-matter relevance | 20 |
| Transaction quality and likely intentionality | 20 |
| Amount, novelty, and repeated accumulation | 15 |
| Policy, regulatory, contract, grant, or budget relevance | 15 |
| Transaction recency | 15 |
| Public market and SEC corroboration | 10 |
| Liquidity | 5 |

Classes:

- `80–100`: high priority
- `65–79`: watchlist
- `50–64`: weak signal
- below `50`: archive

Hard caps prevent an ambiguous or untradeable record from becoming a high-scoring candidate. Examples include a missing ticker, low parser confidence, a broad fund, missing current price, or low AI confidence.

The model supplies only three bounded evidence-assessment components. Transaction arithmetic, amount parsing, recency, repetition, liquidity, hard caps, class thresholds, price-chase limits, paper allocation, and review bands are calculated in code.

## Entry-review rules

The dashboard's entry band is not a valuation target. It is a mechanical review range based on:

- current quote;
- transaction-date close;
- 14-period average true range when available;
- an 8% maximum move above the official's transaction-date close;
- a 10-calendar-day signal expiration.

Possible statuses:

- `review_now` — current quote is inside the maximum-chase limit;
- `do_not_chase` — current quote is above the maximum-chase ceiling;
- `market_data_incomplete` — current or historical price information is insufficient.

All formulas and thresholds are editable in `config/signal_rules.yml`. Changing the rules changes the analysis hash, allowing the same trade to be reevaluated under the new version.

## Paper portfolio

A simulated position opens only when:

- the final score meets the watchlist or high-priority threshold;
- a current market price exists;
- entry status is `review_now`.

Default simulated portfolio values:

- portfolio notional: `$100,000`;
- high-priority position: `1.0%`;
- watchlist position: `0.5%`;
- evaluation horizon: `30` calendar days;
- quote refresh: no more than once per hour.

Positions close at the evaluation horizon using the next available quote. This creates a prospective dataset based on the first price observable after PolitiTrack detection—not the official's earlier transaction price.

## Cost controls

- A transaction is analyzed once per model, prompt version, and rules hash.
- The default maximum is 20 new analyses per run.
- Official documents, market history, SEC maps, and SEC context are cached.
- Investor Edge reuses the core market cache, bounds new provider requests per run, caches its observations, rotates a durable breadth-first cursor, backs off unavailable-price retries, prunes old observation versions to a configured retention limit, and applies one shared historical-observation budget per run. Exhausted network capacity does not prevent later cache-only work.
- The full model receives only the current candidate, its filing, recent same-ticker disclosures, selected market/SEC context, and a bounded document extract.
- Direct document retrieval is restricted to HTTPS hosts under `house.gov`, `senate.gov`, or `oge.gov`; other URLs are retained as links but are not fetched into the runner.
- Set `AI_WEB_SEARCH_ENABLED=false` to avoid web-search tool calls.
- You may substitute another compatible lower-cost model available to your API account after validating that its structured rankings remain adequate.

## Failure semantics

A run fails visibly when an eligible candidate cannot be completed, enabled global Edge maintenance cannot be persisted, or a required candidate alert cannot be delivered. Completed analyses and queued alert snapshots are saved incrementally before delivery begins. All existing pending and newly queued alerts wait until final global maintenance succeeds and no earlier run errors remain. They then share the existing bounded per-channel delivery queue; alert retries do not require another model call. Incremental local persistence is not authorization to promote a failed run's protected artifact.

Missing optional market or SEC data produces a warning and a deterministic score cap rather than silently inventing context. Analyses with incomplete price history remain eligible for a market-only refresh on later runs; the stored AI evidence assessment is reused, so a temporary quote-provider limit does not require another model call. If refreshed data changes a candidate from weak/incomplete to an actionable paper-review class, the dashboard, alert, and simulated position are updated then.

Investor Edge is fail-open **per candidate**. Every new analysis persists the base and final scores plus an explicit scored, neutral, disabled, unavailable, or error status. A candidate-specific profile/scoring failure leaves the normal deterministic score in place, records the fallback state and a scrubbed error when available, and does not invent alpha, hit rate, confidence, or lag.

Enabled global inventory maintenance is a separate fail-closed requirement.
Initialization, refresh or persistence failure makes the AI run unsuccessful so
protected state is not promoted. Initial maintenance failure aborts candidate
analysis, market-refresh work and alert delivery. Final maintenance failure
prevents delivery of both pending retries and newly queued candidates. A stale
leaderboard is not silently described as successfully maintained.

Candidate delivery counts only when at least one channel accepts the alert during that run. Each configured channel has durable pending/delivered state: accepted channels are recorded immediately and skipped later, while unfinished optional channels retry on later runs without re-analysis. Required Pushover is attempted first, remains pending on failure, and still makes the run fail visibly. Retries are bounded per run; completed ledger entries are bounded, but pending deliveries are retained. Historical-bootstrap transactions never enter this delivery path.

## Isolated simulation

**Actions → Run Simulation** provides the safe end-to-end acceptance path. It clones the latest tracker and AI artifacts into runner-temporary directories, creates a TEST-prefixed filing, and exercises the production analysis-record, scoring, and Edge integration using deterministic local evidence and prices. Matching retained Investor Edge history is used when available; otherwise one explicitly marked prior-history fixture is added only to the isolated tree. The simulation never calls OpenAI or market-data services, supplies no real notification credentials, and renders the candidate notification as an alert preview instead of sending it. The dashboard artifact includes `data/simulation-result.json`, expires after one day, and is neither saved as production AI state nor deployed to Pages.

## Source and use restrictions

The House, Senate, and OGE disclosure portals state restrictions on obtaining or using financial-disclosure reports, including commercial-use restrictions. The tracker variable acknowledging those terms does not constitute a legal determination that a particular investment use is permitted. Retain the official filing URL and review the source record and applicable restrictions before relying on an analysis.
