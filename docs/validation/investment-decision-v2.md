# Investment Decision v2 validation — issue #236

Base: `deb18f6632017c8a762a8d9dec2799f82cc6a845` on canonical `main`.
Branch: `codex/investment-decision-v2-20260924`.
Installed Beast revision at inspection: `83501363c719aa14a46e141ef4c94cfb0532d23b`.
This document records source/test evidence, not production activation.

## Requirement mapping

| Requirement | Implementation | Executed validation |
|---|---|---|
| Source-row reliability | input_quality + significance.normalize | inverted bounds, concatenated rows, reinvestment, option, owner/date/ticker mismatches; no input mutations |
| Complete bounded review | review_v2 + AI-owned evidence cache | six filings larger than a segment, repeated cache restore, no duplicate document fetch, all segments reviewed |
| Claim provenance | decision.verify_claims + structured reviewer | invented/future/duplicate evidence rejected; exact quotations and source hashes |
| Risk classification | decision.classify_findings | ordinary risk retained; inferred breaker becomes uncertainty |
| Independent company case | validate_case/build_dossier | source-linked thesis, scenario math, current entry, missing thesis, unsupported units/splits and stale/nonfinite price checks |
| Model contract | hardened optional validator/instructions | custom strict schema fake-client test; existing wrapper regressions preserved |
| Continuing review | engine/runtime/provider cache | complete evidence inventory rechecked; incomplete review resumes; no-new-filing test and post-analysis fresh quote |
| State continuity | original owner and additive fields/cache | immutable evaluation prefix/old AI state preserved; existing checkpoint/restart/concurrency regression suite |
| Post-decision research | opportunity_research | no same-time/backdated anchor; accepted live receipt required; exact completed horizon, assumed costs, immutable results, unknown benchmark |
| Dashboard | persisted projection + dossier DOM | inert untrusted values, sources, risk/scenario labels, expired badge withdrawal, axe semantics |
| Safe modes and release | existing off/shadow/live contract | original no-send/receipt/restart tests, one simulated re-entry event, no real provider calls in fixtures |

The broad local regression command in the existing CI workflow completed with
**426 passed, 1 skipped** on September 24. The skipped check was the optional standalone Investor Edge DOM check because its
local jsdom environment was not configured; it was not a database test.
No live PostgreSQL verification is claimed. The standalone opportunity
suite previously completed **166 passes**; later broad results include the
additional strict-model-contract test. A shared Windows temporary-directory
permission error was resolved with a new isolated `--basetemp`, without changing
shared permissions or weakening assertions. The historical owner-delivery TEST
fixture explicitly retains its original v1 methodology; actual production rule
validation accepts contract v2 only. New v2 tests validate the new gate separately.

The corrected four-cycle TEST re-entry fixture produced:
`watching -> watching -> opportunity_available -> opportunity_available`, one
simulated intent, zero actual provider calls/notifications/trades, preserved AI
state bytes and six immutable events. An initial fixture used an out-of-discovery-
band return and correctly stayed watching; only the fixture price path was fixed.
No production price rules were relaxed.

Six Node/axe checks passed on the legacy projection and six on the generated v2
projection. Headless Edge checks at 1280x900 and 390x844 both passed, with no page
JavaScript errors or horizontal page overflow. Those use an explicitly labeled
TEST fixture clock. Exact-head CI results must be recorded in the PR/check receipts
rather than inferred from local results.
Axe color-contrast checking is disabled in the inherited jsdom harness; it is not
a full visual/accessibility or physical iPad certification.

## Live observations and blocked release proof

The read-only published transaction audit returned 12,765 records with 274 flagged
records. Counts overlap by reason: 78 inverted ranges, 79 multiple source rows,
103 multiple source symbols, 63 source security-type conflicts, 36 direction
conflicts, 25 ticker conflicts, five date conflicts, 29 non-common-stock records,
and six automatic/managed purchase flags. These are case-screening flags requiring
source review, not verified corrected transactions or a claim that all 274 are
parser errors. The projection is not authoritative snapshot proof.

A bounded existing-provider MSFT response probe returned HTTP 200 and a positive
Finnhub quote; zero-delay entitlement is not established. Alpha Vantage returned
HTTP 200, a premium-endpoint message, and no daily-adjusted bars. No upgrade or
capability record was written. The attempted read-only snapshot restoration was
blocked by the tool safety layer before execution. No production database command,
state reset, deployment, schedule change or portfolio mutation occurred.

Remaining operational proof: exact-head CI, authoritative snapshot/export
verification, working entitled split-aware history, exact identity/capability
receipts, approved deployed shadow cycles, actual issuer reviews, matched benchmark
observations and prospective outcomes. TEST success does not imply these occurred.

See `docs/INVESTMENT_DECISION_V2.md` for assumptions, limits and guarded rollout.
