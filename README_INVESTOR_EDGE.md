# PolitiTrack Investor Edge

Investor Edge measures whether a government filer and disclosed owner have previously produced a repeatable, publicly followable signal. It is a deterministic modifier to the existing evidence-based PolitiTrack score, not a prediction engine or a replacement score. The normal and manually dispatched AI workflows enable it by default. It remains paper-research-only and has no brokerage or order-submission path.

## Identity and historical eligibility

Performance is attributed to the normalized pair `filer + disclosed owner`. Self, Spouse, Joint, Dependent, Trust, Managed, and Other ownership categories do not automatically share a record. The durable profile includes the normalized identity, its confidence, the configuration version, and a method hash so a result can be traced to the rules that produced it.

Only earlier, eligible equity purchases for that identity may contribute to a candidate. Synthetic tests, non-purchases, unresolved securities, future disclosures, and records that fail eligibility checks are excluded. Medium-quality or incomplete identity records can receive reduced effective weight rather than being treated as equally reliable. Each trade result records its status, eligibility or exclusion reasons, quality weight, and the observations actually available as of the scoring cutoff.

## Complete retained history and profile discovery

`load_complete_retained_transaction_history()` combines both restored tracker
branches before any candidate selection:

- `.trade-tracker/legislative/transactions.jsonl`
- `.trade-tracker/executive/transactions.jsonl`

These normalized all-transactions ledgers are primary. Each branch's
`purchases.jsonl` supplies older records absent from the primary ledger; an
overlapping purchase copy cannot override primary normalized fields or turn a
historical bootstrap record into a new candidate. Deduplication uses `trade_id`.
For old rows without one, a deterministic SHA-256 fallback includes source,
report identity, filer, disclosed owner, asset, ticker, transaction type/date and
amount. Report identity can fall back to a retained filing key or source URL.
`history_provenance` records branch, source and contributing ledger; duplicate
copies preserve the earliest valid `observed_at_utc`. Original filing and
transaction dates, parse confidence, equity flags and ownership remain available.

The resulting `historical_transactions` collection is independent of
`new_analysis_candidates`, already-analyzed IDs and the model's batch limit.
Candidate profiles and global maintenance receive the full history. A future
filing is not required before an existing eligible filer-owner identity can appear.

Every enabled AI execution performs global Edge maintenance, including executions
with zero new candidates and no OpenAI request. First it discovers the eligible
population within the configured leaderboard limit and persists every selected
profile, including profiles with no completed observations. It then advances
bounded historical work and saves the updated observations, profiles and
leaderboard. A final refresh persists current inventory after candidate work
without starting a second backfill budget. New normal disclosures enter this same
durable history on subsequent runs; historical and prospective profiles are not
separate systems.

This describes implemented behavior, not a claim that the change is deployed.
The [artifact-copy validation report](docs/validation/investor-edge-bootstrap-2026-08-31.md)
records actual before/after counts and outstanding source limitations.

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

Historical outcomes are stored in `investor-edge-observations.json`. At most 30 missing observations are processed in one run by default; this is a trade-observation processing budget, not a 30-day window or a promise of 30 completed outcomes. Deferred work remains eligible on later successful runs even without new disclosures. Unavailable histories persist a bounded retry marker with exponential calendar-day backoff, so the same missing symbols cannot consume every run and starve later trades. Profiles consider at most the 40 most recent eligible historical purchases per identity, the leaderboard is bounded to 40 identities, and durable observations are pruned deterministically to 2,000 entries by default while prioritizing the current method and recent trades. Cached observations are keyed by the method and trade inputs, and each profile reports the current backfill limit, processed count, and pending count.

Historical processing is deterministic and breadth-first: each identity gets a
turn before the next round of observations. A durable last-investor cursor rotates
the starting point across runs; untouched work precedes partial or unavailable
retries. One prolific filer therefore cannot monopolize the initial population.
Exhausting the network budget, or configuring it to zero, does not stop later
cache-computable observations. Work requiring unavailable prices stays pending.

The existing defaults remain `max_history_trades: 40`,
`leaderboard_max_investors: 40`, `backfill_analysis_limit_per_run: 30`,
`network_request_budget_per_run: 40` and `history_lookback_days: 2200`.
No 30-day filing cutoff is introduced. Candidate-time censoring and the distinction
between picker and followable outcomes are unchanged; current profile maintenance
does not rewrite immutable historical candidate decisions.

These limits are configured in `config/investor_edge.yml`. Changing scoring inputs changes the method hash, making the methodology visible rather than silently mixing incompatible observations.

## Cataloged-filing transaction bootstrap

A cataloged filing is not necessarily parsed transaction history. The existing
Legislative and Executive tracker writers now have a separate bounded maintenance
pass for already-seen, catalog-only filings that lack normalized transactions.
`HISTORICAL_FILING_BACKFILL_LIMIT_PER_RUN` defaults to `20`; the CLI override is
`--historical-filing-backfill-limit-per-run`, and `0` disables this pass. This
filing-parsing limit is independent of Edge's 30-observation market backfill limit.
No workflow or additional production-state writer is introduced.

The pass uses the existing official House, Senate and OGE scanners and their
validation/review behavior. Disclosure terms must be acknowledged. An OGE
Form 201 request-only listing is classified as access-required and is not
automatically retrieved or submitted for access. Paper-checkbox and unsupported
document layouts are not converted into invented transactions. Classified
outcomes in the tracker directory's append-only `historical-backfill.jsonl`
distinguish completed, review/validation-blocked and retryable work. Unattempted
filings precede previously attempted retries.

Original cached or legitimately vaulted source bytes are checked before another
request. The optional `--historical-source-documents-manifest` or
`HISTORICAL_SOURCE_DOCUMENTS_MANIFEST` selects the manifest; its default is
`historical-source-documents.json` inside the restored tracker-state directory:

```json
{
  "documents": [
    {
      "filing_key": "house|house:2026:EXAMPLE",
      "source_url": "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/EXAMPLE.pdf",
      "path": "source-documents/EXAMPLE.pdf",
      "sha256": "FULL_SHA256_OF_ORIGINAL_BYTES",
      "format": "pdf"
    }
  ]
}
```

The source URL and filing key must match the retained filing; the contained
relative path, byte limit and SHA-256 must validate. PDF originals and original
Senate HTML are supported through the same scanners, with cached Senate pages
subject to the normal report validation. Flattened or truncated AI document-text
caches are not raw transaction-parser inputs. Invalid cache entries do not cause
an unchecked network fallback. Supplying a document never waives access or use
restrictions.

Only files inside the existing uploaded tracker-state directory are retained
with that protected artifact. A manifest or raw sources configured elsewhere are
not automatically copied or uploaded; they must be available explicitly on a
later run. This source-document bridge is not a substitute for provenance-valid
tracker-state restoration.

Normalized rows retain the existing parser-generated IDs and original public
observation semantics: filing `first_seen_utc`, then a retained seen timestamp,
then a valid filing-date fallback, never the bootstrap clock. Transactions and
purchase projections append idempotently, and existing seen IDs, baseline state,
reviews and ledger prefixes are preserved. Filing outcomes, transactions and
receipts carry `historical_bootstrap: true`. These records do not enter normal
new-filing notifications, AI candidate/reanalysis selection or candidate-alert
delivery, and do not create new Notification Center events. The normal path for
genuinely new disclosures remains active. A missing production-state artifact
still blocks the run; historical reconstruction is not a rebaseline mechanism.

## Dashboard and candidate surfaces

Every dashboard build generates `investor-edge.html` and `data/investor-edge.json`. The heat map shows Edge score and modifier, confidence and effective sample size, picker and followable alpha, 5/20/60/120-session followable alpha and hit rates, strongest-sector evidence, and average or median disclosure lag. Low-confidence rows are faded. Filtering is client-side.

Investor Edge is now a first-class root navigation destination at
`#investor-edge`. Its summary reads the published profile inventory independently
of qualifying signal cards, so an empty signal board does not imply that profile
history is empty. The existing `investor-edge.html` URL retains the full heat map
and drilldowns. The Overview does not turn a sparse heat map into a dominant
chart or download the complete record ledgers.

The compact **Investor Edge History** status appears in the root and standalone
views. It reports profile counts, retained historical trades, processed work and
pending observations from machine-readable leaderboard metadata:

| Metadata | Meaning |
|---|---|
| `historical_transaction_count` | Deduplicated combined retained input, not only AI candidates. |
| `eligible_purchase_count` | Eligible purchases in that input. |
| `unique_investor_identity_count` | Eligible filer-owner identities before the leaderboard population cap. |
| `published_profile_count` | Profiles in the bounded published inventory. |
| `completed_profile_count` | Published profiles with no pending observations and at least the configured minimum completed sample. |
| `building_profile_count` | Remaining published profiles, including zero-observation and insufficient-sample profiles. |
| `backfill_processed_this_run` | Historical trade observations processed this run, not necessarily completed outcomes. |
| `backfill_pending_observation_count` | Pending trade observations across the published population, including immature or unavailable history. |
| `backfill_limit_per_run` | Observation-processing budget, separate from filing parsing. |
| `network_requests_this_run` | Actual Edge provider requests. |
| `branch_transaction_counts` | Retained Legislative and Executive transaction counts. |
| `excluded_reason_counts` | Aggregated eligibility reasons; a record can have multiple reasons. |

Pending observations are not counts of individual horizons, source filings or
network requests. **Historical backfill in progress** means pending work exists;
**Historical backfill current** means none remains for the bounded published
history, not that every cataloged source filing has been parsed. A profile can
still be building because its completed sample is too small. Older artifacts
without population metadata show unavailable counts/unknown history status;
missing metadata is never inferred to mean zero or current.

Open an investor row for the detail view. It exposes normalized identity and methodology metadata, sector performance, eligibility and exclusion information, and the prior-trade outcome matrix. The matrix separates picker and followable entry points and shows stock return, benchmark return, and alpha for each completed horizon. An em dash means the observation is unavailable; it does not mean zero.

The **Signals** destination preserves base/final scores, modifier, confidence,
observation count, relevant available followable-alpha horizon, hit rate,
current-sector alpha, and disclosure lag in candidate cards and the all-analysis
table. The wallboard uses a condensed history/confidence summary and links back
to the detailed views. The downloadable AI CSV retains flattened fields; durable
profiles are unchanged.

Insufficient histories are visibly de-emphasized and labeled **Building history —
insufficient completed observations (n = X)**. Missing or insufficient alpha and
return values remain unavailable, including when a profile contains some
observations. A retained neutral placeholder is not displayed as demonstrated
performance or a recommendation. A horizon label is attached only to the
existing value it describes; the UI does not calculate a new alpha, score,
benchmark, minimum-sample rule, or portfolio return.

The presentation view model is generated by `scripts/dashboard_insights.py`,
and root/wallboard assets are owned by `scripts/build_trade_dashboard.py` and
`scripts/dashboard_assets/`. The existing
`scripts/investor_edge.py::build_dashboard_addon()` still generates the standalone
Edge view. Update generator sources rather than hand-editing published HTML.

Context help explains Edge, confidence, scores, review bands, chase ceilings,
and expiration through hover, focus, and tap/click. **Methodology & Risk** opens
the complete disclosure; insufficient-history and delayed/cached-price labels
stay visible. These presentation changes do not change eligibility, scoring,
classification, identity handling, benchmarks, or alert delivery.

The Notification Center tracks newly qualifying signals only after a successful
browser-local baseline. It does not mark retained history as new on first load.
Acknowledgement, snooze, mute, quiet hours, and gesture-enabled audio affect only
that browser; existing external notifications described below are unchanged.

Candidate notifications include classification, amount, entry-review status and band, a concise AI summary, the same Edge fields, and a dashboard link. Existing Pushover delivery remains supported. As an optional second channel, set both `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`; the analyst sends the candidate message from that Gmail account to the same address over Gmail SMTP. Leaving either integration unconfigured does not fabricate a delivery. The completed analysis and immutable alert snapshot are persisted before sending, and each configured channel has its own durable pending/delivered state. Both pending retries and newly queued candidates use the existing bounded, channel-deduplicated delivery path only after final global maintenance succeeds and no prior run errors remain. Accepted channels are recorded immediately and are not resent; unfinished optional channels retry on later runs without re-analysis. Required Pushover is attempted first and still fails the run when it cannot deliver. Alert suppression covers candidate delivery and the Run Simulation workflow supplies no real notification credentials. Normal new-filing tracker alerts are unchanged; historical reconstruction never sends them.

Candidate-specific Edge failures remain fail-open as described above. Failure to
initialize, refresh or persist the enabled global Edge population instead fails
the AI run, so its protected state is not promoted. An initial maintenance failure
aborts candidate/market work; a final maintenance failure prevents candidate
delivery. Retaining per-candidate fallback scores does not justify publishing an
incomplete or stale global inventory as successful.

## Run Simulation

Use **Actions → Run Simulation → Run workflow** for an isolated end-to-end acceptance check. The workflow restores the latest Legislative, Executive, and AI artifacts, clones them into run-specific temporary directories, chooses a historical filing with an eligible equity purchase, and creates a TEST-prefixed copy dated at the selected `as_of` date. It uses matching retained history when present; otherwise it adds one explicitly marked prior-history fixture only to the isolated tree. It then exercises the production analysis-record, deterministic scoring, and Investor Edge integration path with deterministic local evidence and market data.

The simulation does not call OpenAI or a market-data service and supplies no API or notification credentials. It does not call the real notification function; instead, `data/simulation-result.json` contains the exact alert preview and machine-checkable assertions. The generated dashboard is exposed only through the uniquely named `simulation-dashboard-<run-id>-<attempt>` artifact and expires after one day. The cloned AI state remains in runner-temporary storage and is discarded; neither it nor the dashboard is uploaded as production state or deployed to Pages.

This acceptance preview is separate from the **$10K Agent** historical replay.
The latter is labeled **SIMULATED — SINGLE-RUN HISTORICAL REPLAY**, with starting
value, replay value, actual change, remaining objective, and retained timestamps.
Independent replay history is not a persistent cash/holdings/valuation ledger:
the UI states **No persistent portfolio history yet** and does not invent an
equity curve or benchmark comparison.

## Persistent artifacts

The durable AI state contains:

- `investor-edge-profiles.json` — latest profiles keyed by normalized investor identity;
- `investor-edge-leaderboard.json` — the bounded dashboard population and run metadata;
- `investor-edge-observations.json` — reusable per-trade, per-horizon outcomes, retry progress and the persistent fairness cursor;
- `investor-edge-market/` — cached daily history and company-sector mappings.

Analyses created or market-refreshed while the runtime is available retain base and final scores, modifier, Edge status and any scrubbed error, flattened display fields, the nested profile, and the scoring-method version. Existing historical analysis revisions are not rewritten in place, preventing later data from changing an earlier paper decision.

## Limitations

- Historical alpha is descriptive and does not establish causation, private information, or future performance.
- Filing delays mean picker alpha was generally not followable. Followable alpha starts no earlier than the next trading session after first observation, but still does not model later notification latency, spread, slippage, fees, taxes, or position sizing.
- Public source retention, parser confidence, resolved tickers, price-history availability, and the bounded backfill determine the sample. Sparse or missing data lowers confidence and can leave horizons unavailable.
- Sector classification is approximate and can change. Low-confidence or absent mappings fall back to SPY, and sector-specific claims require comparable history.
- Results can be sensitive to a small number of filings despite clipping, weighting, and shrinkage. Inspect the drilldown rather than ranking investors by Edge alone.
- The system is for paper research and review. It is not investment advice and never submits an order.
- The redesign's actual Chrome desktop, current iPhone Safari, and physical CHG90 acceptance remain unverified. Local tests or emulated viewport checks do not establish those device results; deployment and device evidence belong in `docs/HANDOFF.md`.
