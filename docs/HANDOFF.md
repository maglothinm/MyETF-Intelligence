# PolitiTrack active handoff

## September 24 #239 — Free stack merged; owner API key is the next setup input

PR **#240** merged as **0b70118fc8911e54e427d0011a43672a7029f8ab**;
the tree exactly matches tested head **41eb60b90d65e49ed9578d60c41810884ba62318**.
Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
All four exact-head CI workflows succeeded: Current Opportunity 36035728639,
Investor Edge 36035728339, Runtime safety 36035728272, source OCR 36035728574.
Local verification: 518 Python passes / one optional PostgreSQL-service skip,
eight Node/axe passes, and headless Edge cost-page checks at 1280/390 pixels.

Massive free EOD history, explicit splits, rate limiting and restart caching are
implemented for the Current Opportunity/research path with Finnhub/SEC retained.
The test-only free adapter cycle passed the investment case gates and preserved
old state. API usage/cost estimates and the separate cost screen are implemented;
no invoice or historical unmetered charge is fabricated.

The **PolitiTrack Free Data Setup** launcher is on Beast's Desktop, pinned to the
tested clean source. It requests a free Massive key locally with hidden input,
performs a read-only provider probe and creates a restricted credential file after
success. It does not create an account, purchase a plan, activate a capability,
change production settings, enable an alert or place a trade. No Massive key was
present at closeout. Do not ask the owner to paste credentials into chat.

Installed application remains 83501363c719aa14a46e141ef4c94cfb0532d23b with Current
Opportunity OFF; no services, production settings, histories or portfolios changed.
No new scheduler or cloud writer was created. Retired GitHub writers remain disabled.
After local key setup, verify actual free-tier responses, precise capability/source
identities and a fresh authoritative snapshot baseline; then use normal Windows
release approval and observed shadow cycles. Keep #239/#236 open for live acceptance.
See `docs/releases/2026-09-24-free-stack-source.json` and `docs/FREE_MARKET_STACK.md`.


## September 24 #239 — Free market stack implementation; activation awaits owner key

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Branch `codex/free-market-stack-20260924`, based on main
`b158d177b222d93bc785570e1c5e5ec8c5dc90f4`. The owner approved Massive Basic free
history + existing Finnhub quotes + SEC, not a paid Alpha Vantage subscription.

Implemented explicit Massive history selection, raw OHLC/dated split reconciliation,
separate dividend provenance, two-year coverage limits, safe resumable pagination,
shared five/minute pacing, snapshot-owned derived caching, truthful daily-window
scope and matched research. Added API request/token accounting and a separate
Operating costs screen; missing usage is not a zero bill and token estimates are
not invoices. No model upgrade or additional paid call is made by a test.

A local hidden-input setup/probe helper accepts the owner's free API key without
putting it in Git, logs or command arguments. Current runtime has no Massive key;
no real Massive response, account creation or capability activation is claimed.
The data adapter is not a silent migration of legacy Investor Edge prices or old
paper accounting. Current Opportunity remains OFF on installed source
`83501363c719aa14a46e141ef4c94cfb0532d23b`; production configuration and services
are unchanged. See `docs/FREE_MARKET_STACK.md` for exact scope and setup.

Local verification: **518 Python passes / one optional PostgreSQL-service skip**;
**eight Node/axe checks passed**. The free adapter executed the existing decision
cycle with TEST provider responses and no Alpha key, preserved original AI state,
and generated one simulated intent. No actual market/model/notification call was
made by the tests. See `docs/validation/free-market-stack-local.json`.

Next: exact-head CI/review, owner free key and actual response tests, genuine
provider/security/owner receipts, fresh authoritative snapshot preflight, then
the existing Windows release boundary and scheduled shadow acceptance. No live
investment alerts, subscriptions, orders, new writers or cloud reactivation.


## September 24 #236 — PR #237 merged; state preflight passed, data activation blocked

Owner reviewed the implementation and instructed “Reviewed. Proceed.” Canonical
repository ID **1349678672**, `maglothinm/MyETF-Intelligence`. PR #237 merged at
15:00:10 UTC as **268e6e5fca4895300192028f869c1d6f38fb9d13**. Its tree exactly
matches reviewed/tested head **ee7564863f205e2066c41c89cb605478521d238c**.
All four exact-head CI workflows passed attempt 1: Current Opportunity 36003133613,
Runtime safety 36003133764, source OCR 36003133456, Investor Edge 36003133466.

The previous snapshot-read tool blocker is cleared. A read-only repeatable-read
transaction exported authoritative AI 908, Dashboard 1728, Executive 757 and
Legislative 1625. Every archive unpack/repack hash matched, the new AI reader
validated the existing state, and all **5,018** retained snapshot headers form
unbroken parent chains matching those heads. Private raw exports remain outside
Git on Beast. This is verified read-only preflight, not a production restore or
permission to reuse an old baseline at a later deployment.

The exact configured Alpha Vantage daily-adjusted endpoint still returned zero
bars and a premium-only message. The published entry monthly tier is $49.99 for
75 requests/minute; no subscription was purchased or cost approved. This proposed
tier is for historical data, not a substitute delayed quote. Finnhub returned a
positive regular-session quote 19.44 seconds old; full entitlement/identity
capability receipts are not yet established. No capability file was fabricated.

Beast remains on **83501363c719aa14a46e141ef4c94cfb0532d23b**; Current Opportunity
is **OFF**. Database/web/scheduler remain Running/Automatic, without a restart,
configuration change, new alert, order, source approval, or cloud/legacy activation.
The remote token is not elevated; normal Windows approval remains necessary at
actual release time. Issue #236 stays open for operational acceptance.

Next: obtain the owner's decision on historical-data access; verify real provider
responses and exact security/owner capability evidence; then take a fresh baseline
and use the existing Beast service boundary for shadow deployment and scheduled
acceptance. Live investment notifications and brokerage orders remain out of scope.
See `docs/releases/2026-09-24-investment-decision-preflight.json` for exact receipts.

## September 24 #236 — Investment Decision v2 source implementation, not deployed

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Branch `codex/investment-decision-v2-20260924` from `main`
`deb18f6632017c8a762a8d9dec2799f82cc6a845`. Installed Beast source inspected at
`83501363c719aa14a46e141ef4c94cfb0532d23b`; Current Opportunity remains OFF.

Implemented case-level source guards, resumable SEC document/exhibit reviews,
exact claim passages, distinct risks/uncertainties/thesis breakers, company
scenario dossiers, post-analysis quotes, conditional post-decision research,
and dashboard/CSV/JSON under the existing AI snapshot writer. Mode, channels,
old ledgers/reviews/portfolios and cloud retirement remain unchanged.

Local final broad regression: 437 passed / 0 skipped. TEST return/restart fixture:
one simulated opportunity intent, no real calls/messages/trades. Provider probe:
Alpha Vantage returned a premium-endpoint response with no required bars;
Finnhub responded but zero-delay entitlement remains unverified. Authoritative
snapshot preflight was tool-blocked, not executed. Do not activate shadow/live
until documented state/provider gates pass. No production deployment is claimed.
See `docs/INVESTMENT_DECISION_V2.md` and `docs/validation/investment-decision-v2.md`.
Issue #236 remains open for operational acceptance; PR #237 records exact-head CI.


## September 23 #232 - activated on Beast; complete directory and search verified live

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Session branch `codex/profiles232-live-receipt`, based on main
`a5904b0af624c3f2b40daf10912e24c7b01e26d8`; this receipt changes documentation only.
[PR #233](https://github.com/maglothinm/MyETF-Intelligence/pull/233) release
**83501363c719aa14a46e141ef4c94cfb0532d23b** is installed and configured on Beast, matching tested source
**a37133f08d4e77b164e89d27bb4625ec31b89c40**. The earlier canceled approval attempt is superseded by the
owner-authorized retry and successful normal Windows approval.

### Activation and autonomous publication

The existing release helper completed at **2026-09-23T12:13:56.9228612Z**, using
the existing scheduler/web stop-start boundaries. Database PID **25732** remained
running; web PID **37084** and scheduler PID **39472** are running with automatic
startup. The readiness endpoint returned HTTP 200. No manual AI/dashboard producer
run was invoked: the existing native scheduler published both new heads successfully
with `trigger_source=external_scheduler`, through the existing writer locks:

| Namespace | Generation | Committed UTC | Snapshot SHA-256 |
|---|---:|---|---|
| AI | 855 | 2026-09-23 12:14:35.889504 | `2f5a4a08f6efaadfaac5a2f715c1af22b4bd870e060d42a5978507dc9b0c2448` |
| Dashboard | 1622 | 2026-09-23 12:17:22.266089 | `ac85360a1b473201b913b3c963c17bdcd3437c25cd58345625be88c0efd20cb1` |

Both heads record source revision `83501363c719aa14a46e141ef4c94cfb0532d23b`. Read-only verification at
**2026-09-23T12:17:52.587355+00:00** found **1,028 distinct owner profiles covering all
975 known filer names**, including Donald Trump. All published filing names are
represented. Persisted AI, served JSON and CSV agree exactly; seven served data/UI
routes match the committed dashboard snapshot bytes. The existing per-run budgets
remain 30 historical observations and 40 provider requests; the accepted AI run used
30 and 40 respectively. These are background limits, not directory admission limits.

At **2026-09-23T12:18:08.803926+00:00**, real Edge checks against the deployed site passed
on both root/standalone views at 1280 and 390 pixels: name-order/case-independent
Donald Trump lookup, pending-review filter, automatic matching Building history
expansion, clear and responsive layout. No JavaScript errors occurred and the browser
was restricted to read-only local requests.

### Tests and continuity

Previously completed source validation: **412 local regression passes** under the
same UTF-8 configuration as Beast, plus offline browser/replay checks. Offline replay
retained all 62 prior profile identities, 1,519 observations and history-ledger bytes
with zero provider calls. All four exact-tested-head CI runs passed:

- [Investor Edge tests 35857964119](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964119): attempt 1 success.
- [Runtime v2 safety tests 35857964150](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964150): attempt 1 success.
- [Source upload and OCR tests 35857964122](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964122): attempt 1 success.
- [Current Opportunity offline tests 35857964184](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964184): attempt 1 success.

The after-activation and after-publication read-only fingerprints match all **4,706**
immutable snapshot headers at cutoff `2026-09-23T12:02:16.803496+00:00`, digest
`7d77ad4fde7c22093e23f7424666093f`. There are **zero broken snapshot parent links**.
Installed untracked `legislative-source-status.json` still matches SHA-256
`E5C1B22AB61D88DB8FA75B228DBF3A499734C37DDD26B22DB445C8B3F7226BF2`. PostgreSQL immutable heads remain the
authority; no protected GitHub recovery artifact was restored or replaced. No
rebaseline, new writer/schedule, filing upload or cloud/legacy activation occurred.

### Review boundary and next safe action

Donald Trump's Self profile is visible with 519 retained transactions, one pending
source review, and `building / insufficient_completed_observations`. His original
30-page manual upload `a816c4f5-3327-4cdd-9930-a94b53927a64` remains `needs_review`,
with receipt `fe768ffad0909dbba9095b89615561a5fc3c259423f4a22b191737fbe5e50a3f`.
Directory publication does not approve it or resolve the suspected municipal-bond
ticker classification. [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225)
retains the independent original pending-upload outage acceptance boundary.

Activation and live acceptance for [#232](https://github.com/maglothinm/MyETF-Intelligence/issues/232)
are complete. Completion receipt is
`C:\ProgramData\PolitiTrack\backups\profiles232-complete.json`, with `accepted=true`
and the expected installed revision. It supersedes the installer-time
`live_publication_verified=false` checkpoint and makes the prepared Desktop launcher
a no-op for this completed release. User-facing reports and verification JSON are
retained in the task outputs folder. Use the live name/status controls; no further
activation is needed. Leave the existing scheduler to continue bounded evidence
collection. Handle original source review and #225 separately without re-uploading,
requeueing, approving, or manufacturing evidence as part of this directory fix.
