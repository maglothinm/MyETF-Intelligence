# PolitiTrack Investor Edge

Investor Edge measures whether a government filer and disclosed owner have previously produced a repeatable, publicly followable signal. It is a deterministic modifier to the existing evidence-based PolitiTrack score, not a prediction engine or a replacement score. The normal and manually dispatched AI workflows enable it by default. It remains paper-research-only and has no brokerage or order-submission path.

## Identity and historical eligibility

Performance is attributed to a source-provided Bioguide/filer ID plus disclosed owner when available. `Trade` preserves `filer_id`, `filer_id_source`, and explicit `filer_aliases` without changing existing trade IDs. Name-only sources use an explicitly lower-confidence normalized-name fallback; no person ID is inferred from a filing ID. Explicit aliases may bridge name-only history to one stable ID, but a collision between multiple stable IDs blocks the bridge. The existing House/Senate listing payloads do not themselves guarantee a Bioguide ID, so this is propagation of available identity, not a claim of complete live ID enrichment.

Self, Spouse, Joint, Dependent, Trust, Managed, and Other ownership categories do not automatically share a record. The durable profile includes identity provenance and confidence, configuration version, and a method hash.

Only earlier, eligible equity purchases for that identity may contribute to a candidate. Synthetic tests, non-purchases, unresolved securities, future disclosures, and records that fail eligibility checks are excluded. Medium-quality or incomplete identity records can receive reduced effective weight rather than being treated as equally reliable. Each trade result records its status, eligibility or exclusion reasons, quality weight, and the observations actually available as of the scoring cutoff.

## Picker and followable alpha

Investor Edge compares the security with a sector ETF when a sufficiently confident industry mapping exists and otherwise uses SPY. It measures benchmark-relative return at 5, 20, 60, and 120 trading-session horizons from two anchors:

- **Picker alpha** starts at the underlying transaction date. It helps describe the official's historical security selection but was not publicly actionable at that time.
- **Followable alpha** starts at the first trading session after PolitiTrack first observed the public disclosure (falling back to the reported filing date when no observation timestamp exists). It is the more relevant measure for a PolitiTrack user because it uses a conservative, realistically actionable entry.

For every completed horizon, the durable observation retains entry and exit dates and prices, stock return, benchmark return, and alpha. Missing horizons remain unavailable; they are not filled with zero or a neutral value. The default horizon weights are 15% at 5 sessions, 30% at 20, 35% at 60, and 20% at 120, normalized across the outcomes that are actually available. Per-horizon alpha is clipped to ±25 percentage points before aggregation so one outlier cannot dominate a profile.

Both security and benchmark returns use the same `split_dividend_adjusted_total_return` basis from Alpha Vantage `TIME_SERIES_DAILY_ADJUSTED` / `5. adjusted close`. [Alpha Vantage documents the adjusted series](https://www.alphavantage.co/documentation/#dailyadj) and [explains its split/dividend treatment](https://www.alphavantage.co/stock-price-tracker-website-python-django/). Its adjusted daily endpoint requires provider entitlement; missing access leaves observations pending. Finnhub daily candles document split adjustment only, so they are not a total-return fallback. Fresh and cached outcomes must respect the cutoff for stock and benchmark entry/exit dates, and benchmark sessions must match the stock sessions exactly.

## Score, confidence, and caps

The unshrunk 0–100 Edge score uses these default component weights:

| Component | Weight |
|---|---:|
| Followable benchmark-relative alpha | 45% |
| Picker benchmark-relative alpha | 20% |
| Followable hit rate | 15% |
| Consistency | 10% |
| Skill in the candidate's mapped sector | 10% |

Hit rates are recorded separately for picker and followable outcomes at every horizon as well as in weighted form. Sector performance is separately shrunk and includes the strongest observed sector, its benchmark, alpha, hit rate, sample size, score, and confidence.

Small samples are deliberately pulled toward neutral Edge 50. Confidence incorporates effective sample weight, completed-horizon coverage, a prior of eight trades, the minimum completed-trade threshold, and identity confidence. Sector evidence has its own four-trade prior and mapping confidence. These choices keep a few weak or incomplete observations from appearing comparable to an established history.

The shrunk Edge score maps to a whole-number PolitiTrack modifier hard-capped at `-12` to `+12`. At least three completed and three effective observations are required by default; below this configurable minimum the status is `insufficient_data` and the modifier is exactly zero. The normal capped deterministic score is preserved as `base_score`; `final_score = clamp(base_score + modifier, 0, existing caps)`. Thus a negative modifier reduces an already capped score (64 with a −12 modifier becomes 52), while a positive modifier cannot exceed the cap. `base_raw_score` and the adjusted raw diagnostic remain separately visible. Reapplication does not compound the modifier. If Edge cannot run, the core analysis retains its base score and an explicit disabled, unavailable, or error status.

## Bounded backfill and caches

The engine reuses only validated adjusted history in `investor-edge-market/adjusted-v1/`. Each snapshot records schema version, ticker, price basis, provider, UTC fetch time, and a digest of its rows. Freshness uses the recorded fetch time, not a restored file's modification time. Raw/unversioned Edge and core market caches remain untouched but are ineligible. Snapshots are never spliced across adjustment revisions or providers. Last-good validated adjusted data remains usable during an outage for horizons it actually covers.

Adjusted daily history uses existing Alpha Vantage credentials; sector mapping still uses Finnhub. Both are bounded by the shared default 40-request budget. Daily-cache freshness defaults to 24 hours and sector-cache freshness to 168 hours. Errors are scrubbed before persistence. There is no live provider request in offline acceptance tests.

Historical outcomes are stored in `investor-edge-observations.json`. At most 30 missing observations are backfilled per run by default; deferred work remains eligible later. Unavailable histories retain exponential calendar-day retry backoff so one missing symbol does not monopolize every run. Each trade exposes pending horizons and a coverage reason, and profiles aggregate those reasons.

Profiles consider at most 40 recent eligible purchases and the leaderboard at most 40 identities. The active observation set is bounded to 2,000 entries by default, but overflow is copied into `investor-edge-observations-archive.json` **before** the active snapshot is replaced; durable history is not pruned. An existing malformed archive blocks loading rather than being replaced. Old-method observations remain audit evidence but cannot score under the new adjusted-price methodology. Existing analysis revisions are never rewritten to conceal the methodology change.

These limits are configured in `config/investor_edge.yml`. Changing scoring inputs changes the method hash, making the methodology visible rather than silently mixing incompatible observations.

## Dashboard and candidate surfaces

Every dashboard build generates `investor-edge.html` and `data/investor-edge.json`. The heat map shows Edge score and modifier, confidence and effective sample size, picker and followable alpha, 5/20/60/120-session followable alpha and hit rates, strongest-sector evidence, and average or median disclosure lag. Low-confidence rows are faded. Filtering is client-side.

Open an investor row for the detail view. It exposes normalized identity and methodology metadata, sector performance, eligibility and exclusion information, and the prior-trade outcome matrix. The matrix separates picker and followable entry points and shows stock return, benchmark return, and alpha for each completed horizon. An em dash means the observation is unavailable; it does not mean zero.

The normal **AI candidates** table and the CHG90 wallboard also show a compact Edge summary alongside the base and final PolitiTrack scores: modifier, confidence, observation count, the relevant available followable-alpha horizon, weighted followable hit rate, current-sector alpha, and disclosure lag. The downloadable AI CSV flattens those fields while retaining the nested profile in durable JSON.

Candidate notification formatting includes classification, amount, entry-review status and band, a concise AI summary, Edge fields, and a dashboard link. Gmail requires both `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`; code and configuration are not proof of delivery. The proposed external recovery journal is on hold: delivery remains governed by artifact-only state, and ambiguous delivery after a failed publication is not claimed resolved. The Run Simulation workflow supplies no real notification credentials and generates only a TEST-marked preview.

## Run Simulation

Use **Actions → Run Simulation → Run workflow** for an isolated end-to-end acceptance check. The workflow restores the latest Legislative, Executive, and AI artifacts, clones them into run-specific temporary directories, chooses a historical filing with an eligible equity purchase, and creates a TEST-prefixed copy dated at the selected `as_of` date. When retained mature history does not meet the minimum, the offline scoring adapter adds enough explicitly TEST-marked, fully matured fixtures to exercise the real minimum gate. Those supplemental records appear in the result evidence and are never written to production trackers. It exercises the production analysis-record, scoring, and Edge integration paths with deterministic local evidence and an explicitly adjusted-price fixture adapter.

The simulation does not call OpenAI or a market-data service and supplies no API or notification credentials. It does not call the real notification function; instead, `data/simulation-result.json` contains the exact alert preview and machine-checkable assertions. The generated dashboard is exposed only through the uniquely named `simulation-dashboard-<run-id>-<attempt>` artifact and expires after one day. The cloned AI state remains in runner-temporary storage and is discarded; neither it nor the dashboard is uploaded as production state or deployed to Pages.

## Persistent artifacts

The durable AI state contains:

- `investor-edge-profiles.json` — profiles keyed by normalized identity; old keys remain as aliases after a stable-ID upgrade;
- `investor-edge-leaderboard.json` — the bounded dashboard population and run metadata;
- `investor-edge-observations.json` — reusable per-trade, per-horizon outcomes and backfill progress;
- `investor-edge-observations-archive.json` — immutable inactive/old-method observations, including hash-keyed revisions where necessary; mandatory continuity data once created;
- `investor-edge-market/` — cached daily history and company-sector mappings.

Analyses created or market-refreshed while the runtime is available retain base and final scores, modifier, Edge status and any scrubbed error, flattened display fields, the nested profile, and the scoring-method version. Existing historical analysis revisions are not rewritten in place, preventing later data from changing an earlier paper decision.

## Limitations

- Historical alpha is descriptive and does not establish causation, private information, or future performance.
- Filing delays mean picker alpha was generally not followable. Followable alpha starts no earlier than the next trading session after first observation, but still does not model later notification latency, spread, slippage, fees, taxes, or position sizing.
- Public source retention, parser confidence, resolved tickers, price-history availability, and the bounded backfill determine the sample. Sparse or missing data lowers confidence and can leave horizons unavailable.
- Sector classification is approximate and can change. Low-confidence or absent mappings fall back to SPY, and sector-specific claims require comparable history.
- Results can be sensitive to a small number of filings despite clipping, weighting, and shrinkage. Inspect the drilldown rather than ranking investors by Edge alone.
- The system is for paper research and review. It is not investment advice and never submits an order.
