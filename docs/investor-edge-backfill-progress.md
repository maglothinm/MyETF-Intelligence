# Investor Edge backfill progress — issue #172

## Scope and semantics

Backfill status is evidence about the bounded published investor population, not
all cataloged filings, the AI model's candidate queue, or all government records.
The existing scoring version, method hash, identity keys, horizons, no-lookahead
rules, retention limit and provider/run budgets are unchanged.

The producer classifies each distinct eligible observation into exactly one state:

| State | Evidence and meaning |
|---|---|
| Completed | All configured picker/followable outcomes exist by the as-of cutoff. |
| Ready | Existing cached prices can calculate at least one missing outcome using the existing production outcome function, and the current retry/date gates permit an attempt. |
| Queued | A first evaluation has not established market-data availability. It is not counted as cache-computable work. |
| Awaiting maturity | The remaining outcomes require future sessions, established from current retained price rows or a future entry anchor. |
| Awaiting retry | An existing provider backoff or once-per-UTC-date attempt gate is active. |
| Missing data | Prices are unavailable, incomplete or stale; maturity cannot safely be inferred. |
| Blocked | Market credentials are absent and available caches cannot finish the work. A zero configured processing budget is also called out as blocked at the summary level. |
| Unknown | Required dates, identity or current-profile evidence cannot be established. |

Maturity is conservative: an absent weekday price is not assumed to be an
exchange holiday, and no future trading calendar or finish date is fabricated.
An old transaction can have a recently observed disclosure and therefore an
immature followable outcome. Partial observations still contribute only their
existing eligible outcomes to the unchanged score.

The existing engine attempts an incomplete observation at most once per UTC
calendar date; a half-hour producer schedule does not mean the same observation
is attempted every half hour. Exponential provider backoff may defer it longer.
The panel exposes the actual earliest eligibility timestamp, not a promise of
execution at that timestamp.

## Durable journal and estimates

A versioned, additive `progress_journal` is retained inside the existing
`investor-edge-observations.json` backfill object. There is no new production
file, schema migration, state writer or scheduler. At most 24 maintenance events
are retained. The initial global maintenance pass records at most once per
runtime instance; its final refresh and dashboard builds cannot advance counts.
Only an accepted producer snapshot makes its journal authoritative.

The journal counts actual newly available outcome sets and resolved ready work,
not request attempts or a difference between changing population totals. A method
or observation-universe change invalidates the comparable throughput window;
pruning is never credited as completion. Out-of-order timestamps are ignored.
Prior durable observations and scores are never reset by telemetry migration.

A numeric ETA requires three recent positive measured throughput intervals for
cache-computable work. The range uses the observed slowest/fastest completion
rates, including elapsed intervals between successful maintenance passes. It
excludes unverified first evaluations, missing prices, backoff, and future
outcomes. Zero or insufficient progress, stale evidence, disabled processing,
or zero processing budget suppresses the estimate. It is a conditional processing
range, not an appointment or estimate of all historical coverage.

Three successful maintenance passes with the same ready work remaining and no
new outcomes produce a stalled-work warning. Ordinary maturity waiting and
provider retry delays do not. Last maintenance and last actual advancement are
shown separately. Telemetry exceptions fail open for scoring, preserve the prior
journal, and publish unknown progress rather than invented zeros.

## Presentation and safety

Root and standalone Investor Edge share one read-only component. Counts remain
mutually exclusive; pending details are limited to 200 items, prioritizing
blocked/missing data, with explicit truncation and existing profile drilldowns.
Keyboard/touch-accessible filtering, a contained scrollable table, and preserved
open/filter/focus state support review without growing the heat-map rows.

Only allowlisted progress fields reach the public JSON and inert standalone
payload. Untrusted text is escaped. No raw provider errors, tokens, recipient
configuration or internal run identifiers are published by this component.
Legacy aggregate-only snapshots keep their known counts but explicitly lack a
verified detailed status/ETA; zero pending alone cannot prove this feature current.

Publication evidence ages using the existing AI freshness policy. Re-rendering
the same snapshot cannot refresh it; backwards device clocks remain uncertain.
An exact next scheduled execution remains unavailable because a static snapshot
cannot verify Scheduler enablement or actual dispatch. Operations supplies the
existing execution evidence. There is no synthetic running indicator, browser
job dispatch, external notification, or percentage that counts immature returns
as a failed background task.

No additional owner rating, acknowledgement, password or input is required for
ordinary historical maintenance. Source parsing/access reviews remain separate.

## Acceptance and release boundary

Local focused acceptance: **87 passed, 1 optional Node/jsdom skip**. Repository
safety verification passed. Node, accessibility and responsive browser acceptance
run against isolated TEST fixtures in GitHub CI. Full local collection could not
run because Flask/application dependencies were not installed in the ChatGPT
container; this is not a claim that the full suite passed locally.

`tests/backfill_progress_preview.py` generates read-only TEST previews and can
capture Chromium evidence for root/standalone views at 1280, 700 and 390 pixels.
No live data, collectors, AI calls, market requests or notification credentials
are used. PR #173 carries the exact-head CI evidence.

This document records implementation, not production acceptance. Deployment
requires a fresh Runtime v2 baseline, the existing coordinated immutable-image
release path, unchanged configuration/schedules/personal data, and accepted AI
and Dashboard successors. Verify the live JSON/panels and their snapshot lineage.
Do not use an old Phase 5 certificate as acceptance of this change. Issue #172
remains open until production verification is recorded.
