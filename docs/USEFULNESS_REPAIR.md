# Usefulness repair — issue #255

Canonical repository 1349678672, `maglothinm/MyETF-Intelligence`.
Owner instruction October 5, 2026: repair the live usefulness audit findings.
This document describes implemented source, not proof of live investment utility.

## Preserved decision boundary

Current Opportunity remains SHADOW. Both AI delivery suppressions remain true.
No entry/significance/valuation threshold, model, portfolio, historical anchor,
original evaluation, source ledger, outbox or subscription is changed. There is no
new scheduler or cloud service. Only the existing Runtime v2 AI owner may persist
capability observations, review progress and new evaluations.

## Historical identity and current capability are different

An independently evidenced historical report-to-person link does not expire
merely because a feed-health receipt expires. Historical-only enrichment returns
no feed entitlement flags, maps only transactions within the original verified
security interval, and retains the existing common-stock/source-quality checks.
Newer transactions cannot inherit an unverified date interval. Current market
requests additionally require a currently verified matching security entry.

Optional `OPPORTUNITY_REFRESH_CAPABILITIES=true` in the existing SHADOW AI
invocation enables bounded **observed** renewal. It is not enabled by source
presence. It uses only the existing independently verified seed allowlist, the
configured free Massive account, Finnhub and the existing shared request budget
and pacing file. One seed security is considered per tick. No arbitrary ticker,
new filer, report identity or provider subscription is inferred.

Renewal checks the current public structured Finnhub US quote contract, actual
configured-key access, exact current Massive composite/share-class FIGI, CIK,
exchange/currency/type, validated daily history, and an actual quote no more than
five minutes old within a regular session. Closed sessions wait; failure cannot
extend an expiry. Scope changes cannot reuse another account's observations.
A later failed refresh withdraws that security's prior current observation.
The original pinned receipt is unchanged. Live alert activation is not supported
by this automatic shadow-refresh path and remains separately gated.

`opportunity-capability-refresh.json` is a validated derived cache in the same AI
snapshot. Changes append a capability-observation event in the existing immutable
journal. Old snapshots preserve earlier observations. Daily-date validity prevents
an overnight cached observation from pretending to be a new-day verification.

Official contracts inspected for this implementation:
- https://finnhub.io/docs/api/quote
- https://massive.com/docs/rest/stocks/tickers/ticker-overview
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## Incremental, complete-text issuer review

The reviewer processes available complete documents even when another required
document is unavailable, oversized or deferred by the per-run budget. Per-document
failure receipts and bounded cooldowns prevent repeatedly downloading the same
blocked response. All required missing documents remain explicit coverage gaps;
partial section progress never clears issuer or investment gates.

Issuer document extraction streams the entire response through a text parser,
retains the hash of every raw byte, and verifies decoding without replacement.
Limits are 24,000,000 transport bytes and 3,000,000 extracted text bytes; existing
31/32-MB evidence-cache admission/hard limits and model/request budgets remain.
Markup-heavy filings larger than the former 3-MB raw limit can now be processed
without storing their entire HTML response in memory. Truncation is never accepted
as complete evidence. Script/style bodies are excluded as previously; section
quotes come from complete normalized document text. Index pages retain their
separate existing 3-MB limit. Unsupported encodings or safety-limit documents
remain explicit review requirements, not empty successful documents.

Completed section reviews retain original limitations. When limitations exist,
a separate source-bound structured check may classify generic scope notices or
ordinary disclosed risks as nonblocking. Any material missing fact or inability
to decide remains a blocker. The original limitation and the separate assessment
are retained; no timer or confidence score clears uncertainty. A model check is
not a guarantee of factual truth or a substitute for human review.

## Useful dispositions, not inflated completion counts

Research dispositions separate blocked work, partial research, unsupported
valuation methods, completed watch cases, supported rejections and cases ready
for human review. Nonpositive reported annual EPS produces an explicit
unsupported-method screen with its SEC accession and source reference. It is
not an economic rejection or a completed investment review. Source research may
continue but no unsupported EPS-multiple case is manufactured.

`analysis_completed_at` is absent for incomplete evidence; last attempt is stored
separately. `usable_decision_at` is absent until the required data and completed
decision conditions hold. Telemetry labels attempted work separately from
completed investment reviews and actual section progress.

An old unresolved placeholder may link to one successor only when its exact
trade-ID set is contained in one verified case. It remains in history. Ambiguous
links and ticker-only similarities cannot merge cases or reset anchors.

## Smaller default dashboard work

The default page fetches `current-opportunities-index.json` and renders at most
25 cards per page. The original full JSON and CSV remain unchanged in coverage.
Detailed evidence loads only after an explicit click; the page verifies both
opportunity ID and evaluation ID before showing it. A changed snapshot requires
a refresh rather than mixing evaluations. Full details still use the existing
complete export, so a deliberate details request can be large; no per-case API
or removal of historical source data is claimed. Existing freshness and threshold
filters continue to withdraw stale badges.

## Acceptance and release

Offline tests cannot certify a real investment case. Before release, verify
canonical exact-head CI and take a NEW frozen four-head export after actual native
writers drain. Preserve all original event/ledger prefixes, IDs and snapshot
chains. Capture the collector-written status-file hash only at the final frozen
boundary, not before waiting. Use normal Windows administrator approval and the
existing Scheduler/Web services; never restart or rewind the database to pass.

The only intended production configuration additions are the reviewed source SHA
and `OPPORTUNITY_REFRESH_CAPABILITIES=true` for the existing AI invocation. Preserve
all other settings and both suppressions. Do not manufacture a fresh capability
file. Observe a genuine regular-session renewal, native persisted issuer progress,
new disposition counts, dashboard agreement and zero real AI deliveries.

Actual case completion, sustainable coverage beyond the seed allowlist, and
investment performance remain separate acceptance items. Do not call the repair
fully accepted merely because code, fixtures or an installation succeeds.
