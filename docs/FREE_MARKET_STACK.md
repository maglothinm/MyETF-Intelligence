# Free market-data stack — Massive, Finnhub and SEC

Implementation: issue #239, extending #236 / merged Investment Decision v2.
Repository ID 1349678672; source base b158d177b222d93bc785570e1c5e5ec8c5dc90f4.
This is the same PolitiTrack application and existing Runtime v2 AI state owner.
No new trading service, production scheduler or cloud hosting is introduced.

## Selected provider contract

- **Massive Stocks Basic:** free daily OHLC history plus explicit splits and cash
  dividends, bounded to the documented rolling two-year window. No current quote
  is sourced from the free EOD feed.
- **Finnhub:** existing current-quote interface and key, with existing freshness,
  identity and entitlement gates. An HTTP 200 alone never sets a capability flag.
- **SEC:** existing issuer filings, exhibits and company facts. The paid Massive
  financials product is not used.

Checked-in `history_provider: massive` selects the free source for Current
Opportunity and its matched-benchmark research. `mode: off` stays unchanged.
`history_provider: alphavantage` remains a deliberate compatibility option, not a
fallback taken when Massive fails. The free path never calls Alpha Vantage or
requires its premium entitlement/key. Existing historical Investor Edge records,
its legacy price methodology and paper accounting are not rewritten by this
provider change. The new provider serves the current-opportunity/decision path;
this is not a silent migration of every legacy history calculation.

## Exact API behavior

The adapter requests **raw, unadjusted** Massive daily bars (`adjusted=false`) and
computes the common split-only basis from explicit dated `split_from`/`split_to`
ratios. It includes splits effective today when converting prior prices to today's
share basis. Cash dividends remain separate metadata, never hidden price changes.
This avoids mixing dividend-adjusted closes and current raw quotes, or applying
splits twice. Future, duplicated/conflicting, invalid or wrong-security records
cannot clear a required-data gate.

Endpoints verified against current official documentation on September 24:

- `GET /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}`
- `GET /stocks/v1/splits`
- `GET /stocks/v1/dividends`
- `GET /v3/reference/tickers/{ticker}` for isolated setup verification

The current splits/dividends routes replace the older reference-route naming;
no deprecated endpoint is silently substituted. Authentication uses an HTTP
Authorization header, never a URL key. Redirects are disabled. Pagination is
restricted to the same approved endpoint/host, bounded to 16 pages, detects cycles,
strips credentials from returned continuation URLs, and resumes only complete,
checksum-validated prior pages. HTTP 429 honors shared backoff rather than retrying
behind the rate limiter. Provider errors are stable reason codes, not raw bodies.

The request starts two days inside the two-year limit and ends yesterday. Missing
older dates, missing sessions, insufficient ATR history and out-of-range original
references remain unknown. Newer cases can still be evaluated. No extra history
is manufactured by changing an old transaction date or resetting an anchor.

**Daily-bar scope matters:** the generic Massive aggregate contract uses qualifying
trades in ET windows and does not establish regular-hours-only daily coverage.
The adapter preserves that limitation. A daily aggregate boundary is not labeled
as a verified 4 p.m. execution or official closing-auction price. Original reference
dates are explicit, separate from the window-end timestamp. Threshold and research
exports carry the source scope; matched benchmark results require compatible scopes.
Regular-session live-quote requirements are not weakened. An incomplete current
session cannot certify that a stock never crossed a threshold.

## Free-tier resource controls and persistence

The shared per-key pacing database reserves actual requests at least 13 seconds
apart (at most five/minute), including across process restarts. It coordinates this
PolitiTrack client, not unrelated applications using the same key. No hidden HTTP
retry can bypass it. Default history budget is 12 requests per invocation, also
charged to the existing overall request budget. Pagination consumes that budget.
Benchmark history shares the limiter/cache; its first acquisition can require
three history/action calls plus a Finnhub quote, not the old two-call Alpha budget.

`opportunity-massive-cache.json` is a bounded derived response cache in the existing
AI snapshot. Same-day complete pages are reused; partial work resumes; prior-day
cache entries can expire without changing immutable opportunity events, original
anchors or old ledgers. Cache hashes are validated on restore/publication.
The operational SQLite pacing file is not a source-data or portfolio authority.
The native AI host supplies its shared path under PolitiTrack's local temp folder.

The adapter retrieves history and benchmark data before capturing the current
Finnhub quote so free-tier waiting does not manufacture a fresh-looking old quote.
The existing post-analysis refresh and delivery-time validation remain in force.

## Setup boundary

No Massive credential was present in the inspected runtime configuration. The
implementation does not create an account, accept paid terms, buy a subscription,
change plan, or send an investment alert. The owner creates a free Stocks Basic
account, then enters the key locally without echo using:

```powershell
& 'C:\ProgramData\PolitiTrack\venv\Scripts\python.exe' -X utf8 `
  'PATH-TO-REVIEWED-SOURCE\scripts\opportunity_massive_setup.py' `
  --key-file 'C:\ProgramData\PolitiTrack\config\massive-private.json' `
  --output 'NEW-EMPTY-PRIVATE-PROBE-DIRECTORY' `
  --pacing-path 'C:\ProgramData\PolitiTrack\temp\massive-pacing.sqlite3'
```

The setup helper first checks a real free-data response for one selected common
stock. It creates a new credential file only after successful provider checks;
Windows file ACLs restrict it to the current user, SYSTEM and Administrators.
Existing credential files are never overwritten. The probe receipt contains no
key and makes no claim of complete universe coverage, source-owner mappings,
Finnhub licensing, production activation or trading success.

A reviewed release subsequently configures `MASSIVE_API_KEY_FILE` in the existing
AI invocation. Its verified capability receipt must set `massive_basic_verified`
from real evidence; `finnhub_realtime_verified` and exact security/owner mappings
remain required. The retained Alpha boolean may be false. No receipt is fabricated.
Fresh authoritative snapshot checks, normal Windows service/elevation boundaries
and observed scheduled shadow cycles still precede operational acceptance. Live
investment delivery is a separate gate. This change does not authorize orders.

## API usage and costs

Free market data does **not** mean free AI calls. `api_usage.py` records every
response or handled request failure passing through the hardened OpenAI wrapper,
including incomplete/invalid responses that lead to another request. It retains
actual input/output/cached/reasoning token counts where reported, distinguishes
unknown usage, and deduplicates repeated response IDs. It never records prompts,
model text, keys or raw error bodies. Reasoning is an output subset, not a second
charge; cached inputs and reported cache writes are treated as input subsets.

On Beast the native AI host writes an operational usage journal under local logs,
so a failed analyst run does not erase observed API usage. Only the normal AI
writer publishes `api-usage-summary.json` into its snapshot. This journal cannot
replace or modify trading state. Non-native/test runs default to a journal in
that run's isolated AI directory. A process killed before response observation
may leave unobserved usage; accounting failure is explicitly reported, not free.

`config/api_usage_rates.json` contains dated official standard text-token tariffs
for the explicitly matched model. Unknown model IDs or nonstandard tiers remain
unpriced. Estimated token subtotals are not invoices: tool fees, taxes, credits,
other applications, unobserved requests and unreported cache-write charges are
not inferred. Historical unmetered charges cannot be reconstructed. The dashboard
shows recorded usage and known estimated subtotals separately from unknown costs.
No billing API/admin credential, paid account upgrade or fixed monthly AI price is
introduced. No more expensive model is selected.

The new **Operating costs** screen is available from the overview navigation even
when Current Opportunity is off. It reports the selected $0 new data-subscription
design separately from OpenAI usage and provides JSON export. It never calls an
empty usage history a zero-dollar bill. Current Opportunity exposes history-source
limitations in its persisted evidence detail.

## Official references

- https://massive.com/pricing
- https://massive.com/docs/rest/stocks/aggregates/custom-bars
- https://massive.com/docs/rest/stocks/corporate-actions/splits
- https://massive.com/docs/rest/stocks/corporate-actions/dividends
- https://massive.com/docs/rest/stocks/tickers/ticker-overview
- https://finnhub.io/docs/api/quote
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://developers.openai.com/api/docs/models/gpt-5.6-terra

## Rollback

Keep the compatible reader and set opportunity mode off through the normal owner.
Preserve new caches, usage evidence, dossiers, original histories and delivery
receipts. Do not rewind heads, reinitialize state, reactivate cloud/legacy writers,
or substitute an unverified paid/other provider to make a gate pass.
