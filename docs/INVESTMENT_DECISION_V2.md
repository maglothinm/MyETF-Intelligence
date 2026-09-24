# Investment Decision v2 — evidence-backed, human-reviewed cases

Implementation issue: #236. Canonical repository ID: 1349678672.

This extends the existing Current Opportunity engine, Runtime v2 owner, immutable
AI snapshot and dashboard. It is not a second scheduler, portfolio or brokerage
integration. Checked-in mode remains `off`. Source changes and TEST acceptance do
not imply deployed shadow observation or investment performance.

## Decision contract

A current opportunity requires the existing meaningful-buying, current-price,
source-evidence and market-quality gates **and** a supported company investment
case. Investor Edge remains supplementary and does not qualify or veto the case.
`ready_for_human_review` means an auditable proposed case, not permission to trade.
Original source documents, interpretation of quotations and capital/risk limits
still require a human decision.

### Transaction integrity

`opportunity_input_quality.issues` identifies inverted disclosed ranges,
concatenated transaction rows, source direction/date/ticker/owner mismatches,
non-common-stock conflicts and automatic/managed/reinvestment purchase evidence.
These reasons exclude the affected contribution from qualification. They never
rewrite the original ledger, infer corrected transactions or approve parser items.
A consistency check is not proof of source authenticity or complete extraction.

### Resumable issuer review

`InvestmentSourceReviewer` checks SEC recent material filings over the existing
context interval and the latest available annual report, with explicit incomplete
status when the submissions API requires additional historical pages. It retrieves
primary text and EX-10/EX-99 textual exhibits through the filing's document index.
It divides complete normalized text into contiguous bounded segments, not an
unacknowledged first-N-character truncation. Exact segment locations, SHA-256,
observation timestamps, quotations and review progress are retained.

The existing per-run document/model/request limits remain. Exceeding those work
budgets defers the remaining sections; completed sections resume on a later cycle.
A private `opportunity-evidence-cache.json` resides in the **same AI snapshot**.
Only the existing owner persists it. It is derived evidence, never state authority.
It is validated during restore/publication. Source ledgers and prior evaluations
are not rewritten. Cache limits are 32 MB hard / 31 MB admission threshold and
3 MB per retrieved document; non-text exhibits, incomplete inventories, oversized
claim catalogs or safety-limit documents require explicit review.

Completed evidence is reused only while its membership, expiry and a newly
checked SEC inventory hash still agree. Incomplete reviews cannot be cached as
clearance for a day. A new issuer filing therefore prompts reassessment even
without a new disclosed transaction.

Coverage means the checked SEC filing text/exhibits and retained disclosure/parser
context; it does **not** mean all company news, all contracts or all investment risk.
A relationship-only discovery route remains separate future research and cannot
silently bypass meaningful buying.

### Claims, risks and cases

Structured extraction requires exact source excerpts and actual observation times.
Claim IDs distinguish facts, inferences and assumptions. A separate structured
semantic review checks entity, period, units, interpretation and shareholder
attribution. Matching quotations and a second model review are not a human truth
guarantee. Self-reported model confidence does not clear these gates.

Findings are `support`, `risk`, `uncertainty` or `thesis_breaker`. Ordinary risks
remain visible and do not invalidate a case automatically. An inference presented
as a breaker becomes uncertainty. A supported factual breaker can invalidate the
case without requiring a workable valuation, so a canceled contract or similar
fact is not held up by missing scenario inputs. Unsupported critical findings hold
review rather than create a confident verdict.

The company-case synthesis receives issuer claims and financial facts, not the
political transaction rows. Disclosed buying remains a separate qualification
gate rather than evidence that the company economics are attractive.

Each dossier has a source-linked business thesis, why-now assessment, attributable
shareholder economics, review/invalidation conditions and a 20/60/120-session
review horizon. Initial valuation support is **positive reported annual GAAP EPS
with explicitly assumed forward EPS and price/earnings scenarios**. The SEC
companyfacts reference uses USD/share annual diluted EPS, a genuine annual period,
filed-by-cutoff observations and the exact accession. It is not annualized
quarterly earnings, adjusted EPS, or an automatic forecast. Unsupported business
models and unreconciled splits remain data/valuation-limited.

Bear/base/bull scenario values are computed deterministically as assumed EPS times
assumed multiple. The entry ceiling is the smaller of:

- base value / (1 + required upside)
- (base value + required reward/risk * bear value) / (1 + required reward/risk)

The provisional defaults are 15% base-scenario upside and 2:1 base reward versus
bear-scenario decline. These are review assumptions for shadow evaluation, **not**
validated predictors, success probabilities or a guarantee against loss. A price
below the proposed bear value requires reassessment rather than an artificial
infinite reward/risk ratio. The original trade/discovery and volatility price
gates remain independently required; no threshold was relaxed to generate alerts.

## Timing, lifecycle and display

A fresh market snapshot is requested after a successful lengthy evidence review.
Existing quote age/session checks still apply. Delivery retains the normal
last-moment source/price revalidation and durable receipts. Case evidence and a
current price must both be usable; an old analysis quote is not a current entry.

`thesis_status` and `assessment_status` are separate. Missing fresh data withdraws
the actionable badge but does not rewrite the last supported thesis as disproven.
All prior decisions and notification records remain immutable. Dossier fields,
source quotes, assumption tables, risks, blockers and research outcomes are
published from that same persisted decision. UI content uses text nodes and
validated HTTPS links, not model-generated HTML.

No capital limit, position size or order is inferred. Downside scenarios are not
maximum loss guarantees; total loss, gaps and non-guaranteed stops are stated.

## Prospective research

The same evaluation journal stores conditional cohorts for buying-only,
company-case-plus-price and the full method. Cohorts start once per opportunity,
method hash and comparison route; rule changes do not rewrite an old experiment.
These are comparisons within the evaluated disclosure population, not an
independently screened whole-market baseline or independent observations.

For shadow/comparison cases, the anchor is the first retained regular-session
quote **strictly after the usable evaluation**. A live full-method cohort requires
an accepted alert receipt first. The actual quote lag is retained. None is an
actual fill or a politician-date return. Outcome evaluation uses completed
exchange sessions at 5/20/60/120 horizons, matching security identity and supported
split adjustments. Measured outcomes are not overwritten by later data revisions.
The documented 10-basis-point round-trip cost is a configurable research
assumption, not a claimed broker cost. These are price returns excluding dividends.

`opportunity-research.json` and the decision CSV/JSON expose the records. A missing
benchmark is `null`, explicitly unavailable, never zero or a claim of alpha.
Matched benchmark feeds and out-of-sample live evidence remain necessary before
claiming investment advantage. Buying-only and company-only cohort overlaps must
not be counted as independent successes.

## Verification and rollout

Run the existing Current Opportunity regression workflow. It now also generates
`tests/opportunity_decision_fixture.py` and runs the existing DOM/axe checks against
the new model. Fixtures use explicit TEST data and fake providers; they cannot
send real notifications or open portfolios. The four-cycle fixture shows chased
price, first return, confirmed return, unchanged follow-up: exactly one simulated
intent, restore between cycles, no previous AI state change.

Before deployed shadow activation:

1. Verify canonical exact-head CI and preserve existing runtime identity. Export
   and hash-verify authoritative AI/Legislative/Executive snapshots and the current
   deployment/configuration through the approved read-only restore path. Do not
   substitute the public dashboard, caches or a blank state for this evidence.
2. Verify provider entitlement, exact security/share-class/owner mappings and
   achievable quote age. Store genuine current capability receipts through the
   existing owner; never manufacture flags or purchase an account upgrade silently.
3. Use the existing Beast release/service process and required Windows elevation
   to deploy the reviewed revision. Set only `OPPORTUNITY_MODE=shadow` in the
   existing AI invocation. Preserve all live notification/portfolio configuration.
4. Verify normal scheduled and zero-new-filing cycles, persisted section progress,
   old ledger fingerprints, case/gate/dashboard agreement, actual source coverage,
   resource budgets and no real new sends. Record source heads, rule hash and
   actual job evidence. A successful heartbeat alone is not acceptance.
5. Live opportunity notifications require the existing separately approved live
   activation receipt/channels and all market/evidence gates. Brokerage execution
   is not implemented or authorized by this feature.

Rollback uses the compatible new reader with opportunity mode `off`, preserving
all additive case/cache/research/receipt records. Do not rewind database heads or
restore an old reader without compatibility testing. Existing legacy behavior is
unchanged while off or shadow. No cloud service or legacy workflow is re-enabled.

The September 24 response preflight returned an Alpha Vantage premium-endpoint
message and zero required daily-adjusted bars. Finnhub returned a positive quote,
but this does not attest zero-delay licensing. The snapshot-read preflight was
blocked by the tool safety check, and no database command was executed. Thus this
implementation is not presently certified for deployed shadow or live alerts.
An authorized compatible historical-data capability and verified runtime snapshots
are concrete activation prerequisites, not deficiencies to hide with fallback data.

Official API contracts used:
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://www.sec.gov/about/developer-resources
- https://platform.openai.com/docs/guides/structured-outputs
