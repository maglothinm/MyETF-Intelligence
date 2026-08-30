# PolitiTrack Investor Edge

Investor Edge measures whether a government filer and disclosed owner have previously produced a repeatable, publicly followable signal. It is a deterministic modifier to the existing evidence-based PolitiTrack score, not a prediction engine or a replacement score. The normal and manually dispatched AI workflows enable it by default. It remains paper-research-only and has no brokerage or order-submission path.

## Identity and historical eligibility

Performance is attributed to the normalized pair `filer + disclosed owner`. Self, Spouse, Joint, Dependent, Trust, Managed, and Other ownership categories do not automatically share a record. The durable profile includes the normalized identity, its confidence, the configuration version, and a method hash so a result can be traced to the rules that produced it.

Only earlier, eligible equity purchases for that identity may contribute to a candidate. Synthetic tests, non-purchases, unresolved securities, future disclosures, and records that fail eligibility checks are excluded. Medium-quality or incomplete identity records can receive reduced effective weight rather than being treated as equally reliable. Each trade result records its status, eligibility or exclusion reasons, quality weight, and the observations actually available as of the scoring cutoff.

## Picker and followable alpha

Investor Edge compares the security with a sector ETF when a sufficiently confident industry mapping exists and otherwise uses SPY. It measures benchmark-relative return at 5, 20, 60, and 120 trading-session horizons from two anchors:

- **Picker alpha** starts at the underlying transaction date. It helps describe the official's historical security selection but was not publicly actionable at that time.
- **Followable alpha** starts at the first trading session after PolitiTrack first observed the public disclosure (falling back to the reported filing date when no observation timestamp exists). It is the more relevant measure for a PolitiTrack user because it uses a conservative, realistically actionable entry.

For every completed horizon, the durable observation retains entry and exit dates and prices, stock return, benchmark return, and alpha. Missing horizons remain unavailable; they are not filled with zero or a neutral value. The default horizon weights are 15% at 5 sessions, 30% at 20, 35% at 60, and 20% at 120, normalized across the outcomes that are actually available. Per-horizon alpha is clipped to ±25 percentage points before aggregation so one outlier cannot dominate a profile.

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

The shrunk Edge score maps to a whole-number PolitiTrack modifier hard-capped at `-12` to `+12`. The normal deterministic score is preserved as `base_score`; `final_score` applies the modifier and then the existing PolitiTrack hard caps. Investor Edge therefore cannot make an ambiguous, incomplete, untradeable, or otherwise capped signal qualify by itself. If Edge cannot run for a candidate, analysis continues fail-open with the base score and records a neutral, disabled, unavailable, or error status instead of inventing performance values.

## Bounded backfill and caches

The engine reuses PolitiTrack's cached daily history before requesting anything new. Additional market history and sector mappings use the already-configured Alpha Vantage and Finnhub credentials and are bounded by the per-run network-request budget. The defaults are 40 network requests per run, 24 hours for daily-market cache freshness, and 168 hours for company-profile cache freshness. Provider errors are scrubbed before durable persistence so query-string credentials are not written to state.

Historical outcomes are stored in `investor-edge-observations.json`. At most 30 missing observations are backfilled in one run by default; deferred work remains eligible for later runs. Unavailable histories persist a bounded retry marker with exponential calendar-day backoff, so the same missing symbols cannot consume every run and starve later trades. Profiles consider at most the 40 most recent eligible historical purchases per identity, the leaderboard is bounded to 40 identities, and durable observations are pruned deterministically to 2,000 entries by default while prioritizing the current method and recent trades. Cached observations are keyed by the method and trade inputs, and each profile reports the current backfill limit, processed count, and pending count.

These limits are configured in `config/investor_edge.yml`. Changing scoring inputs changes the method hash, making the methodology visible rather than silently mixing incompatible observations.

## Dashboard and candidate surfaces

Every dashboard build generates `investor-edge.html` and `data/investor-edge.json`. The heat map shows Edge score and modifier, confidence and effective sample size, picker and followable alpha, 5/20/60/120-session followable alpha and hit rates, strongest-sector evidence, and average or median disclosure lag. Low-confidence rows are faded. Filtering is client-side.

Open an investor row for the detail view. It exposes normalized identity and methodology metadata, sector performance, eligibility and exclusion information, and the prior-trade outcome matrix. The matrix separates picker and followable entry points and shows stock return, benchmark return, and alpha for each completed horizon. An em dash means the observation is unavailable; it does not mean zero.

The normal **AI candidates** table and the CHG90 wallboard also show a compact Edge summary alongside the base and final PolitiTrack scores: modifier, confidence, observation count, the relevant available followable-alpha horizon, weighted followable hit rate, current-sector alpha, and disclosure lag. The downloadable AI CSV flattens those fields while retaining the nested profile in durable JSON.

Candidate notifications include classification, amount, entry-review status and band, a concise AI summary, the same Edge fields, and a dashboard link. Existing Pushover delivery remains supported. As an optional second channel, set both `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`; the analyst sends the candidate message from that Gmail account to the same address over Gmail SMTP. Leaving either integration unconfigured does not fabricate a delivery. The completed analysis and immutable alert snapshot are persisted before sending, and each configured channel has its own durable pending/delivered state. Accepted channels are recorded immediately and are not resent; unfinished optional channels retry on later runs without re-analysis. Required Pushover is attempted first and still fails the run when it cannot deliver. Alert suppression covers candidate delivery and the Run Simulation workflow supplies no real notification credentials. Tracker filing alerts are unchanged.

## Run Simulation

Use **Actions → Run Simulation → Run workflow** for an isolated end-to-end acceptance check. The workflow restores the latest Legislative, Executive, and AI artifacts, clones them into run-specific temporary directories, chooses a historical filing with an eligible equity purchase, and creates a TEST-prefixed copy dated at the selected `as_of` date. It uses matching retained history when present; otherwise it adds one explicitly marked prior-history fixture only to the isolated tree. It then exercises the production analysis-record, deterministic scoring, and Investor Edge integration path with deterministic local evidence and market data.

The simulation does not call OpenAI or a market-data service and supplies no API or notification credentials. It does not call the real notification function; instead, `data/simulation-result.json` contains the exact alert preview and machine-checkable assertions. The generated dashboard is exposed only through the uniquely named `simulation-dashboard-<run-id>-<attempt>` artifact and expires after one day. The cloned AI state remains in runner-temporary storage and is discarded; neither it nor the dashboard is uploaded as production state or deployed to Pages.

## Persistent artifacts

The durable AI state contains:

- `investor-edge-profiles.json` — latest profiles keyed by normalized investor identity;
- `investor-edge-leaderboard.json` — the bounded dashboard population and run metadata;
- `investor-edge-observations.json` — reusable per-trade, per-horizon outcomes and backfill progress;
- `investor-edge-market/` — cached daily history and company-sector mappings.

Analyses created or market-refreshed while the runtime is available retain base and final scores, modifier, Edge status and any scrubbed error, flattened display fields, the nested profile, and the scoring-method version. Existing historical analysis revisions are not rewritten in place, preventing later data from changing an earlier paper decision.

## Limitations

- Historical alpha is descriptive and does not establish causation, private information, or future performance.
- Filing delays mean picker alpha was generally not followable. Followable alpha starts no earlier than the next trading session after first observation, but still does not model later notification latency, spread, slippage, fees, taxes, or position sizing.
- Public source retention, parser confidence, resolved tickers, price-history availability, and the bounded backfill determine the sample. Sparse or missing data lowers confidence and can leave horizons unavailable.
- Sector classification is approximate and can change. Low-confidence or absent mappings fall back to SPY, and sector-specific claims require comparable history.
- Results can be sensitive to a small number of filings despite clipping, weighting, and shrinkage. Inspect the drilldown rather than ranking investors by Edge alone.
- The system is for paper research and review. It is not investment advice and never submits an order.
