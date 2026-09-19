# Purchase gain threshold — issue #197

## Meaning and limits

The default `never_crossed_fraction: 0.08` is a configurable **descriptive** 8%
threshold, not a calibrated investment rule. Each retained purchase gets its own
immutable transaction-date closing reference. Its largest supported subsequent
regular-session gain is compared with the threshold; equality crosses. A stock
can contain both crossed and not-crossed purchases. A later purchase never resets
an earlier purchase, and a pullback does not erase its observed crossing.

This is not an actual execution-price or execution-time claim. The purchase-day
high is excluded because it can precede the purchase and also precedes the
closing-price reference. Every record explicitly labels that unknown ordering.
Extended hours, options, private assets, unmatched securities and currencies
outside the supported adapter are not silently inferred.

The classes are `crossed`, `not_crossed`, and `unknown`. A positive observation
survives later gaps, lower cached highs, changed thresholds and restarts. A
negative requires complete post-reference sessions through its stated cutoff.
During an open session, only explicitly verified regular-session running highs
can establish negative coverage through a quote. Ordinary intermittent quotes
cannot. The current Finnhub adapter does not assert unverified running-high
scope, so a quiet stock can correctly be **unknown during trading**, while its
last completed-session coverage remains displayed. Its historical daily highs
can still prove an earlier crossing.

Daily highs identify an observed breach **session**, not the first intraday
crossing time. `first_observed_at` records discovery of the price evidence and is
never backdated to a transaction. The earliest supported breach can move earlier
when previously missing historical evidence is obtained; older evaluations remain
immutable. Unknown or stale coverage never becomes a negative by default.

## Price basis and provenance

Use the existing Alpha Vantage `TIME_SERIES_DAILY_ADJUSTED` adapter's **raw OHLC
plus split coefficients**, not its dividend-adjusted close. Convert both old
references and subsequent highs to a compatible split-only basis. Dividend
amounts are separate. Preserve original reference/basis and peak-observation
basis in exports. The provider records actual history-observation time and the
latest supported corporate-action date; a quote with later unverified actions
cannot manufacture a threshold crossing.

Official API documentation: https://www.alphavantage.co/documentation/#dailyadj
and https://finnhub.io/docs/api/quote . Provider naming does not establish account
entitlement. Existing entitlement/security/currency gates remain mandatory.

Reject invalid/duplicate bars, unverified action bases, provider conflicts,
missing/future history observation, and revised reference closes. Missing daily
sessions prevent a negative but do not erase compatible positive evidence.
Transaction-date/security/reference corrections require explicit reference
review; they do not silently transfer or reset the original purchase history.

## Integration and persistence

`scripts/opportunity_threshold.py` creates `purchase_thresholds` within each
immutable opportunity evaluation. Prior events/intents are not rewritten; older
states without the additive field remain valid. Removed purchases stay retained
but inactive. A skipped due review withdraws negative flags; proved historical
crossings remain. The same AI writer lock, snapshot packing and atomic commits
own the data. No new scheduler, database, portfolio, provider or live feed exists.

The threshold does not alter the four opportunity gates, the entry bands,
significance calculations, or paper trading. It is excluded from the opportunity
qualification method hash; its own change requests a bounded new review without
manufacturing a new alert. Historical backfill and initial activation create no
retroactive simulated fills or duplicate alerts.

The Current Opportunity page adds a purchase-history filter, compact counts and
expandable per-purchase peak/crossing/coverage detail. Mixed histories are not
collapsed into one stock-level assertion. The browser withdraws expired negative
flags but cannot create a positive or requalify an opportunity. Complete JSON
includes the additive provenance. `data/purchase-thresholds.csv` exports one row
per purchase, neutralizing spreadsheet formula prefixes.

## Owner approval and release gates

On September 19, 2026 the owner authorized implementation, followed by production
activation. This approval covers the feature and Current Opportunity release;
it does not waive data validity, coordination or preserved-history requirements.
The checked-in mode remains off. Issue #197 stays open until live acceptance.

The Executive/OCR recovery under #182/#196 has the production release lock.
Do not start a competing release, alter its resource configuration, or edit its
closed journals. Once it is complete, use the existing coordinated release
process with a fresh exact-head/image/manifest audit. First verify the real AI
snapshot's provider capability file, supported identities, required credentials,
recipient channels and coverage. No manufactured capability flags, subscription
purchase, legacy producer activation or production rebaseline is permitted.

Observe this exact feature in production shadow without external sends. Validate
closed/open-session coverage, returned-price handling, the ordinary AI/dashboard
path and preserved snapshots/outbox/accounts. Only then apply the authorized live
activation record under the existing AI owner and establish a silent historical
baseline. Saturday-only observation cannot prove regular-session quote latency
or a live returned-price cycle. All missing evidence must be reported explicitly.

Rollback keeps the compatible new reader and sets mode off through the same
coordinated process, retaining the additive namespace, immutable history and
accepted/uncertain receipts. Never rewind state or replace closed recovery records.

## Acceptance commands

```sh
python -m pytest -q tests/test_opportunity_*.py
python tests/opportunity_shadow_fixture.py --output /new/empty/threshold-TEST
OPPORTUNITY_FIXTURE_JSON=/new/empty/threshold-TEST/dashboard/data/current-opportunities.json \
  POLITITRACK_TEST_NODE_MODULES=/isolated/test-tools/node_modules \
  node --test tests/opportunity_dom.test.cjs
```

Run the existing Current Opportunity Python 3.11/3.12, Runtime safety, Investor
Edge and OCR regression workflows on the final PR head. Source implementation,
CI acceptance, image installation and live operational acceptance are distinct.
