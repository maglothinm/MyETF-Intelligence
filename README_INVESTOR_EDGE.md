# PolitiTrack Investor Edge

Investor Edge measures whether a government filer/owner's prior disclosed equity purchases have historically contained a repeatable, publicly followable signal. It is a deterministic modifier to the existing PolitiTrack score, not a replacement for the existing evidence-based scoring model.

Investor Edge is integrated but disabled by default. For a safe first run, manually dispatch **AI filing analyst and paper portfolio** with both **Enable Investor Edge** and **Suppress alerts** selected. Review the generated profiles before setting the repository variable `INVESTOR_EDGE_ENABLED` to `true`. It remains paper-research-only and has no brokerage or order-submission path.

## Identity

Performance is attributed to the normalized pair `filer + disclosed owner`. A member's Self trades, Spouse trades, Joint trades, and other disclosed ownership categories therefore do not automatically share a performance record.

## Historical measurement

For eligible prior equity purchases, Investor Edge compares the security with a sector ETF when industry data is available and otherwise with SPY. Abnormal return is measured at 5, 20, 60, and 120 trading-session horizons from two anchors:

- **Picker alpha:** from the underlying transaction date.
- **Followable alpha:** from the public filing date.

The default score weights followable alpha most heavily because PolitiTrack can only act on public information.

## Score

The raw Investor Edge score is 0-100 and combines:

- 45% followable benchmark-relative alpha
- 20% transaction-date benchmark-relative alpha
- 15% historical hit rate
- 10% consistency
- 10% sector-specific history for the current candidate

Small or incomplete samples are shrunk toward 50. The resulting PolitiTrack modifier is hard-capped at `-12` to `+12` points. Existing PolitiTrack hard caps still apply after the modifier, so Investor Edge cannot make an incomplete or otherwise capped signal qualify by itself.

## Market data

The engine first reuses PolitiTrack's cached daily history. When more history is needed, it makes a bounded number of requests using the already-configured Alpha Vantage and Finnhub credentials. Results are cached under `.trade-tracker/ai/investor-edge-market`. Provider errors are scrubbed before being written to durable state so query-string credentials are not persisted.

## Dashboard

The normal dashboard build now also generates `investor-edge.html`. The heat map shows:

- Investor Edge and current PolitiTrack modifier
- confidence and sample count
- 5/20/60/120-day followable alpha
- overall followable alpha
- picker alpha
- hit rate
- average disclosure lag

Low-confidence rows are faded so small samples are not visually comparable to established histories.

## Persistent artifacts

The analyst state adds:

- `investor-edge-profiles.json`
- `investor-edge-leaderboard.json`
- cached daily and profile market data under `investor-edge-market/`

New analyses and normal market-refresh revisions gain `base_score`, `base_raw_score`, `investor_edge_modifier`, `investor_edge`, and `score_method_version` fields when Investor Edge is enabled. Historical analyses are not retroactively rewritten, preventing look-ahead changes to prior paper-portfolio decisions.
