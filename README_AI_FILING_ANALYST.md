# PolitiTrack AI filing analyst and paper-research portfolio

This layer runs after the Legislative or Executive collector completes successfully. It reviews newly parsed public-equity purchases, enriches them with market and SEC information, requests a constrained structured analysis from the OpenAI Responses API, applies deterministic scoring and entry-review rules, and publishes the result on the GitHub Pages dashboard.

It does **not** connect to a brokerage, place an order, or represent a score as certainty. `AI_PAPER_TRADING_ONLY=true` is enforced by the code and workflow.

## Processing sequence

1. Restore the newest Legislative and Executive tracker-state artifacts.
2. Restore the durable AI-analysis artifact.
3. Select previously unanalyzed equity-like purchase rows with a resolved ticker.
4. Fetch the official filing document when directly accessible and extract text or OCR it.
5. Add current and historical price context when market-data keys are configured.
6. Add SEC issuer and insider-filing context when `SEC_USER_AGENT` is configured.
7. Send a fixed evidence package to the OpenAI Responses API using strict JSON-schema output.
8. Calculate the base score with deterministic rules in `config/signal_rules.yml`.
9. Build the candidate's Investor Edge profile from earlier public purchases and apply its bounded modifier without overriding the normal hard caps.
10. Calculate a volatility-aware entry-review band and maximum-chase rule from the final score.
11. Send configured candidate alerts at the threshold.
12. Open or update simulated paper positions and publish the dashboard.

The collector workflows are independent. An AI/API failure does not turn a successful House, Senate, or OGE collection into a failed collector run. The unprocessed transaction remains eligible for a later AI retry.

## Required GitHub configuration

### Actions secret

Create this under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Required | Purpose |
|---|---:|---|
| `OPENAI_API_KEY` | Yes | OpenAI Responses API access. |
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

## First activation

After committing the files and creating the secret/variables:

1. Open **Actions → AI filing analyst and paper portfolio**.
2. Select **Run workflow** on `main`.
3. Leave **Reanalyze the newest already-processed purchases** unchecked for the first run.
4. Leave **Enable Investor Edge** selected; it is the normal default.
5. Leave **Suppress alerts** checked only when you want an initial no-alert acceptance test.
6. Set the maximum analyses to `20` or less.
7. Run the workflow.

The first run creates `.trade-tracker/ai/state.json`, analyzes currently retained parsed purchases up to the run limit, creates `ai-analysis-state`, and triggers a dashboard publication. It does not parse the thousands of catalog-only baseline filings because those records do not yet contain transaction rows.

After activation, each successful scheduled or manual Legislative or Executive tracker run on the default branch automatically triggers the AI workflow. Pull-request collector runs are deliberately excluded from secret-bearing AI execution. Previously completed analysis IDs are skipped unless the model, rules, prompt version, or manual reanalysis setting changes.

## Dashboard output

The dashboard gains three research views:

- **AI candidates** — final and base scores, class, filer/owner, transaction timing, current price, price movement, entry status, review band, rationale, cautions, source links, and a compact Investor Edge summary. The summary includes modifier, confidence, observation count, relevant followable alpha, followable hit rate, sector alpha, and disclosure lag. Missing observations render as an em dash rather than a synthetic neutral value.
- **Paper portfolio** — simulated entry price, quantity, current/exit price, unrealized or realized P&L, return, and evaluation horizon.
- **Investor Edge** — a filterable historical-performance heat map with a per-investor drilldown for normalized identity, methodology, sector evidence, eligibility, and trade-by-trade picker/followable outcomes at 5/20/60/120 trading sessions.

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
- Investor Edge reuses the core market cache, bounds new provider requests per run, caches its observations, backs off durable unavailable-price retries so they cannot starve later trades, prunes old observation versions to a configured retention limit, and processes only the configured number of missing historical outcomes in each backfill pass.
- The full model receives only the current candidate, its filing, recent same-ticker disclosures, selected market/SEC context, and a bounded document extract.
- Direct document retrieval is restricted to HTTPS hosts under `house.gov`, `senate.gov`, or `oge.gov`; other URLs are retained as links but are not fetched into the runner.
- Set `AI_WEB_SEARCH_ENABLED=false` to avoid web-search tool calls.
- You may substitute another compatible lower-cost model available to your API account after validating that its structured rankings remain adequate.

## Failure semantics

A run fails visibly when an eligible candidate cannot be completed or a required candidate alert cannot be delivered. Completed analyses and their queued alert snapshots are saved incrementally before delivery begins. Analysis failures remain eligible for a later analysis retry; alert failures remain in the durable per-channel delivery queue and retry without another model call.

Missing optional market or SEC data produces a warning and a deterministic score cap rather than silently inventing context. Analyses with incomplete price history remain eligible for a market-only refresh on later runs; the stored AI evidence assessment is reused, so a temporary quote-provider limit does not require another model call. If refreshed data changes a candidate from weak/incomplete to an actionable paper-review class, the dashboard, alert, and simulated position are updated then.

Investor Edge is fail-open per candidate. Every new analysis persists the base and final scores plus an explicit scored, neutral, disabled, unavailable, or error status. An Edge startup, data, or profile failure leaves the normal deterministic score in place, records the fallback state (and a scrubbed per-candidate error when available), and does not invent alpha, hit rate, confidence, or lag. Candidate delivery counts only when at least one channel accepts the alert during that run. Each configured channel has durable pending/delivered state: accepted channels are recorded immediately and skipped later, while unfinished optional channels retry on later runs without re-analysis. Required Pushover is attempted first, remains pending on failure, and still makes the run fail visibly. Retries are bounded per run; completed ledger entries are bounded, but pending deliveries are retained.

## Isolated simulation

**Actions → Run Simulation** provides the safe end-to-end acceptance path. It clones the latest tracker and AI artifacts into runner-temporary directories, creates a TEST-prefixed filing, and exercises the production analysis-record, scoring, and Edge integration using deterministic local evidence and prices. Matching retained Investor Edge history is used when available; otherwise one explicitly marked prior-history fixture is added only to the isolated tree. The simulation never calls OpenAI or market-data services, supplies no real notification credentials, and renders the candidate notification as an alert preview instead of sending it. The dashboard artifact includes `data/simulation-result.json`, expires after one day, and is neither saved as production AI state nor deployed to Pages.

## Source and use restrictions

The House, Senate, and OGE disclosure portals state restrictions on obtaining or using financial-disclosure reports, including commercial-use restrictions. The tracker variable acknowledging those terms does not constitute a legal determination that a particular investment use is permitted. Retain the official filing URL and review the source record and applicable restrictions before relying on an analysis.
