# Current Opportunity v1

Implementation for issue #153. Production default: **off**. This change is a reviewable implementation, not a deployment, live certification, or investment-performance result.

## Decision and scope

`meaningful_buying AND acceptable_current_entry AND sufficient_current_evidence AND trustworthy_required_data` is required for `opportunity_available`. A legacy score, missing catalyst, Edge history, or transaction age cannot replace any gate. Existing paper portfolios and historical scores retain their existing code paths.

The compatibility entrypoint `scripts/ai_filing_analyst.py` routes to the hardened analyst. That analyst evaluates Current Opportunity before optional Edge work, even when its new-candidate list is empty. `OpportunityRuntime` reads both retained transaction and purchase ledgers, with an observed-input cutoff; it does not consume an Edge leaderboard or only AI cards. Source state must be successful and within the configured evidence freshness interval. Missing/corrupt required state remains fatal. Explicit TEST/nonproduction inputs are excluded by the production reader.

Runtime v2 remains the sole state owner: `JobRunner._run_ai` restores the existing AI namespace under its advisory writer lock. `LockedNamespace` validates opportunity state before packing or after restoring. The existing deterministic archive manifest and SHA-256 cover every new file. No database migration, additional writer, schedule, daemon, or producer workflow is introduced.

## Rules and identities

All provisional values are in `config/opportunity_rules.yml`, validated against `schemas/opportunity_rules.schema.json`. The method hash includes all rules except mode. These thresholds, including 1.5%/0.5 ATR since discovery, are engineering defaults for shadow study, not validated predictors.

| Route | Conservative requirement |
|---|---|
| Individual | Disclosed lower bound at least $100,000 |
| Accumulation | At least two distinct same-owner/security purchases within 30 transaction calendar days, lower-bound sum at least $50,000 |
| Collective | At least three supported household groups in a 30-day transaction interval, lower-bound sum at least $100,000; confidently sell-dominated disclosed activity blocks this route |
| Relative size | Current lower bound at least $25,000 and twice the median finite prior upper bounds; at least ten comparable prior purchases in the previous 24 months |

Unknown/open range bounds remain unknown/open. Decimal arithmetic is used for money. Sales and purchases are reported separately, with a signed disclosed-activity interval; it is not an estimate of actual holdings or complete portfolio flows. Seven-day acceleration and 90-day context are separate from qualification.

Exact filer IDs plus disclosed ownership establish household grouping; explicit household IDs require evidence. Names alone never establish identity. Unknown/shared-management relationships block automatic independent-group counting. Security ID, share class and currency define a stable opportunity ID. Ticker changes are symbol history, not new opportunities. Known copies and amendment chains are reconciled; conflicting copies, ambiguous lookalikes and branching amendments cannot manufacture qualification. Individual source row/transaction locators preserve genuinely distinct same-day trades.

The price-supported subset must independently satisfy a buying route. A later $1,000 purchase cannot reset the discovery reference or rescue chased $100,000 buying. Initial anchors and all earlier evaluations remain retained. A correction to an anchored trade date requires reference review instead of silently reusing a mismatched date.

## Market and evidence contracts

Transaction date, filed date, verified/bounded public availability, first observed time and first usable discovery quote are separate. Unknown public time stays unknown. Date-only inputs do not acquire midnight precision. A trade-date close is a reconstructed market reference, never the official's fill. Discovery quote lag is explicit.

Entry requires absolute trade-reference movement within both 3% and 1 reference ATR, plus discovery movement within both 1.5% and 0.5 reference ATR. ATR is the mean of 14 completed-session true ranges from 15 contiguous bars, frozen with each anchor. Later volatility cannot widen it. Stored anchors are converted only by documented later splits; dividends remain separate from price entry calculations.

The adapter uses Finnhub's actual quote timestamp and Alpha Vantage daily raw OHLC plus split coefficients. It never compares dividend-adjusted close with a raw current quote. Official references: [Alpha Vantage daily adjusted documentation](https://www.alphavantage.co/documentation/#dailyadj), [Finnhub quote API](https://finnhub.io/docs/api/quote), and the [exchange_calendars implementation](https://github.com/gerrymanoim/exchange_calendars). The calendar supplies actual US equity sessions, DST, holidays and early closes; it does not use a fixed UTC closing time. Initial adapter coverage is verified USD XNYS/XNAS securities on the US equity session calendar.

`opportunity-provider-capabilities.json`, under the AI owner, must conform to `schemas/opportunity_provider_capabilities.schema.json`. It records timestamped entitlement verification, expiry, supporting reference, exact security mappings with validity dates/CIK and optional exact source/report-to-filer mappings. No capability file is shipped enabled. No account entitlement, paid endpoint response, production identity mapping or achievable production latency was verified in this task. Missing/expired capability evidence produces visible data gaps and cannot clear live actionability. No fallback feed or subscription upgrade is attempted.

An eligible quote must be realtime, declare zero feed delay, have provider/actual observation times, and be at most five minutes old during a regular session. Missing, nonfinite, nonpositive, delayed, end-of-day, incompatible or conflicting observations fail the data gate. Closed sessions carry explicit market-closed status and cannot send an entry alert. Missing history/ATR remains data-limited. Daily OHLC plus observed session extremes can reveal excursions; it cannot prove absence of all intraday movement.

Evidence has checked/valid-until times, membership hash, source provenance, and separate disclosure/issuer/parser coverage. Unchanged price or absence of a catalyst cannot clear evidence. The built-in bounded reviewer checks retained disclosures and the relevant parser queue plus SEC material issuer filings over 90 days. It retrieves complete documents, provides only those sources to the existing structured analyst call, and rejects invented citations. This is explicitly SEC filing coverage, not all company news. Missing CIK/user agent/model credentials, incomplete older SEC coverage, oversized documents, unresolved parsing or budgets produce `incomplete`; supported contradictions produce `contradicted`.

Current structured evidence is reused between reviews. Default limits per phase are 20 securities, 80 HTTP requests, two structured reviews, four complete issuer documents per review and 12,000 text characters per document. The existing model wrapper permits at most three attempts per review. Optional web search is disabled for these source reviews. Large filings commonly exceed the conservative document limit: that is visible incomplete coverage, not a truncated document claimed complete. The injected evidence-provider interface also supports deterministic source reviews meeting the same contract.

## Lifecycle and continued review

`watching` means buying established but entry/session is unsuitable; `needs_review` means unresolved required data/evidence; `invalidated` requires identified contradictory evidence. A 60-day monitoring horizon starts when a route first becomes observable, not at the oldest constituent transaction. Archival is an explicit administrative decision; a current supported extension can reopen monitoring without changing initial anchors.

Due work uses a durable rotating cursor and oldest-attempt ordering, independent of Edge. Rotation advances even when every security fits the market budget so a smaller evidence budget cannot always favor the same securities. Failed, removed, stale and budget-skipped opportunities lose the current badge. Telemetry records attempted/successful review, next review, overdue work, provider capability, request budget, oldest unreviewed age, starvation warning and reason counts. A successful tick does not imply all records were reviewed. Default reviews are due after 30 minutes, but only the existing invocation cadence runs them; this is not streaming or guaranteed instantaneous detection.

Rally/decline history persists. Returned-price qualification requires a fresh source-backed return review and two distinct eligible quote observations across evaluations. A cached timestamp/provider/price triple is one observation. Re-entry alerts wait 60 minutes after the last actual or possibly accepted delivery; the badge may qualify earlier. A pending cooldown can release on a later due evaluation without requiring another out-of-range excursion.

## Persistence and delivery

`opportunity-state.json` is an additive version-1 namespace containing a hash-chained immutable event journal, latest evaluations, immutable per-channel intents and delivery receipts. Migration records the validated existing AI state hash and hashes of old JSON/JSONL files. Old positions, ledgers, Edge records and receipt structures are not rebuilt. Rewrites of earlier events/intents and malformed latest projections fail validation. Namespace size inherits the existing archive limits; immutable history is not pruned by this feature.

The opportunity ID is based on security identity and long direction. Notification IDs combine that ID with transition kind and event serial, not quote or rule hash. Material strengthening requires a newly contributing non-amendment purchase with a conservative lower bound at least the configured relative minimum, or a supported changed evidence-strengthening reference. Quote/Edge/score/rule changes alone do not send again. Invalidation updates are only for previously accepted opportunities.

In live mode the hardened analyst suppresses legacy primary bullish candidate messages and labels preserved bearish/neutral messages as filing information. Off/shadow keep existing notification qualification. No new subsystem opens or closes paper positions. Opportunity work reserves its own bounded budget before Edge; Edge failures restore prior bytes and surface warnings. Global state/source failures still prevent publication.

Only `JobRunner` calls live opportunity delivery, under the existing AI lock after the analyst succeeds. Each channel obtains a fresh quote, evidence and current membership/method/supersession check. Original queued evidence stays immutable; validation appends a new decision. The existing owner commits an `uncertain` receipt before the external submission, then records accepted, definitely rejected, deferred or unknown status. It rechecks expiry after checkpoints. A crash/ambiguous acceptance is not blindly retried; definite rejection may retry only after revalidation. No exactly-once provider guarantee is claimed. Intermediate delivery checkpoints preserve accounting and do not certify the running job; the normal final commit atomically marks success. Existing failed-run quarantine remains in force.

## Approved rollout and rollback procedure

This section specifies future work requiring separate production approval. Do not execute it as part of the implementation task.

1. Review the PR, passing exact-head CI and TEST artifacts; export current authoritative AI/collector heads with manifests, hashes, run identities and current image. Confirm no unresolved retry quarantine and preserve the existing writer/scheduler ownership.
2. Approve a deployment explicitly in `OPPORTUNITY_MODE=shadow`, with production notification/portfolio settings unchanged. Verify a migrated AI snapshot through the normal restore/commit path and byte/prefix preservation of old accounting. Never restore a blank state or re-enable legacy producers.
3. Under the approved owner, record verified provider capability/identity evidence, schema version 1, `verified_at`, `valid_until`, `verification_reference`, boolean `finnhub_realtime_verified`/`alphavantage_daily_adjusted_verified`, `securities`, and `filers_by_report`. Check actual quote age/feed entitlement, split history, complete parser/source coverage and bounded SEC review feasibility. Do not set verification flags without evidence or buy an upgrade implicitly.
4. Observe shadow through ordinary existing ticks, including zero-new-filing cycles, a regular-session return and a closed session. Require fresh-quote coverage, no unexplained data/provider conflicts, no starvation, bounded requests/model usage, consistent exported decisions and zero new external sends. Retain actual execution IDs, image, head generation/SHA, schema/rule hash and would-alert counts. Tune only through reviewed rule changes; research outcomes remain separate from portfolios.
5. Obtain explicit live approval identifying the reviewed method/image and existing recipient channels. Record `opportunity-activation.json` under the AI owner: `version: 1`, `repository_id: 1349678672`, `runtime_job: "polititrack-ai"`, real `approved_by`, `approval_reference`, UTC `approved_at`, UTC `cutoff`, and authorized subset of `channels: ["pushover", "gmail"]`. Set `OPPORTUNITY_MODE=live` only in the approved existing runtime. Code also requires `POLITITRACK_MODE=production`, matching `CLOUD_RUN_JOB`, and the owner marker supplied by `JobRunner`. Old observations are silently baselined; only later material changes/re-entry qualify for new delivery.
6. Verify actual baseline, submission/receipt checkpoints and restart behavior before declaring live acceptance. Reconcile `uncertain` provider outcomes with immutable evidence; do not change them to pending or reset intent IDs to force retries.

Rollback uses the compatible new reader with `OPPORTUNITY_MODE=off`, via separately approved configuration change. The next invocation records a durable mode change, stops new evaluation/delivery and hides the active opportunity projection while preserving the namespace, journal, accepted/uncertain receipts and all old accounting. Never rewind heads, delete the namespace, or deploy an older reader without round-trip compatibility verification. Existing legacy behavior resumes according to its unchanged settings; records explicitly superseded during live activation remain superseded to prevent replay of old primary alerts.

## Review commands and UI

The owning dashboard generator writes `current-opportunities.html`, its assets and CSV/JSON from the same persisted projection. The browser can withdraw an expired badge but cannot qualify one. Filters, semantic statuses, expandable details, source links, timeline/lag/price-path data and provenance exports are included. The view is labeled **SHADOW / NOT LIVE ALERTS** in shadow. Unrelated overview, Edge, filing, paper and simulation views remain available.

Run from an isolated checkout with Python 3.11/3.12 and Node 24:

```sh
python -m pip install -r requirements-runtime-v2.txt
python -m pytest -q tests/test_opportunity_*.py
python tests/opportunity_shadow_fixture.py --output /new/empty/TEST-output
npm install --prefix /isolated/ui-tools --ignore-scripts jsdom@26.1.0 axe-core@4.10.3
POLITITRACK_TEST_NODE_MODULES=/isolated/ui-tools/node_modules OPPORTUNITY_FIXTURE_JSON=/new/empty/TEST-output/dashboard/data/current-opportunities.json node --test tests/opportunity_dom.test.cjs
```

The harness refuses a nonempty output directory and uses injected TEST clocks/providers only. Its comparison executes the existing deterministic legacy scoring/entry functions; it is not a historical production alert or performance backtest. See [acceptance mapping](validation/current-opportunity-v1.md) for evidence and limitations.
