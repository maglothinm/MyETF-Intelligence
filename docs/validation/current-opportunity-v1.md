# Current Opportunity v1 acceptance evidence

Status: implemented on `codex/current-opportunity-v1`; **not deployed or live**.
Canonical repository `1349678672`, `maglothinm/MyETF-Intelligence`; issue #153.
Base main verified as `061b8a4dda7f6c0940e8d3f92c6aed3dbb957f0f`.

## Baseline and boundaries

Read the repository contract, current project-state/handoff and recent decision
history. GitHub repository metadata and main ref were rechecked. Existing
recovery run `34059488724`, attempt 1, remains successful; its artifact
`9997087643` was unexpired when checked, with digest
`6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`.
That is evidence about the earlier recovered runtime, not current feature health.
No new GCP state interrogation, deployment, production invocation, schedule,
real notification, portfolio action or entitlement purchase occurred.

The incident reference `scripts/ai_filing_analyst_legacy.py` is unchanged.
The existing unrelated OneDrive checkout was not modified. Work was performed
in an isolated clone from canonical main. Legacy protected records and their
recovery manifest remain unchanged.

Before branch publication, inspect all workflow triggers. Feature-branch push
must match no production workflow; PR triggers must have no write credentials,
deployment commands, protected state writes or production dispatch. The new
`Current Opportunity offline tests` workflow is PR-only, `contents: read`, has
no secrets/schedules/dispatch, and uploads TEST evidence only. Existing
`workflow_run` consumers do not name this test workflow. Never infer deployment
from these CI results.

## Numbered specification mapping

| Brief section | Implementation / proof |
|---|---|
| 1. Objective and scope | Four independent gates in `opportunity_engine.evaluate`; delayed low/absent-Edge test; off default; no production changes |
| 2. Repository and baseline | Canonical metadata/main verification above; narrow Runtime authority clarification in AGENTS; unchanged incident reference |
| 3. Architecture/persistence | `opportunity_state`, `runtime_v2.runner/store/archive`; migration/archive/atomic-commit and corrupt-state tests in `test_opportunity_integration.py` |
| 4. Meaningful buying | `opportunity_significance`; `test_opportunity_significance.py` covers all routes, monetary boundaries, identities, copies, amendments, ordering and conservative net sales |
| 5. Timeline/market | `opportunity_market`/`opportunity_providers`; `test_opportunity_market.py` and provider tests cover anchors, returns, corporate actions, full paths, ATR and real session rules |
| 6. Evidence/lifecycle | `opportunity_evidence`, `evidence_status`, `evaluate`; lifecycle and provider tests cover incomplete/contradicted evidence, return clearance, archive/extension and model citation validation |
| 7. Continuing evaluation/budgets | `cycle`, `RequestBudget`, `EvidenceProvider`; zero-new-filing hardened integration; market/evidence budget rotation and stale-badge removal tests |
| 8. Delivery semantics | `opportunity_notifications`, hardened legacy routing, existing owner checkpoints; notification tests inject stale data, rejected/unknown sends and process death at each boundary |
| 9. Dashboard/alerts | `opportunity_dashboard`, owning `build_trade_dashboard`, source assets, DOM tests; desktop/mobile rendered checks with axe and overflow checks |
| 10. Modes/migration/rollback | `prepare`, explicit `authorize`, activation baseline and off rollback tests; runbook preserves old and additive state, no backward-head restore |
| 11. Acceptance fixtures | Six focused Python suites plus DOM tests and `opportunity_shadow_fixture.py`; full chained state restore and separate accepted/stale send branches |
| 12. Deliverables | Implemented branch/issue/PR, TEST shadow comparison JSON/Markdown, HTML preview and exports, validation receipts, feature/runbook and append-only decision entry |

## Thirteen acceptance groups

| Group | Concrete tests/evidence |
|---|---|
| Significance | Individual/relative/accumulation/collective thresholds; exact/open/missing bounds and insufficient history in significance suite |
| Identity | Household collapse, unresolved owner, classes/security, same-day locators, copies, amendments and permutation tests |
| Timing | June transaction evaluated in September; date-only/unknown/bounded public availability; later observations excluded by cutoff; transaction/observation concentration |
| Price anchors | Quiet return arithmetic, retained first discovery/ATR, split conversion, missing references and minor chased rescue rejection |
| Price path | Quiet, risen, rally-and-return, decline and conflicting evidence fixtures |
| Market quality | NaN/zero/stale/delayed/EOD/extended/conflict/gaps/ATR; splits versus dividends; holiday/DST/early close tests |
| Lifecycle | First qualification, watching, returned opportunity, contradiction invalidation, explicit administrative archive and supported extension |
| Continuing review | `test_hardened_zero_new_filing_run_still_reviews_and_preserves_paper`; both market-budget and smaller evidence-budget fairness tests |
| Edge separation | Missing, failed and changed Edge integration cases; failure restores prior Edge bytes; unrelated global corruption still fails |
| Legacy separation | Existing baseline suites; delayed score-zero fixture; no modification to legacy incident file, research capital configuration or paper functions |
| Notifications | Per-channel acceptance/restart, failed versus uncertain, stale send-time data, amendment/newer-event supersession, cooldown measured from delivery, baseline silence/later return |
| Persistence | Real deterministic archive round trip, manifest/checksum coverage, real `LockedNamespace.commit` validation with a transport fake, existing JobRunner checkpoints and restart; corruption blocks another commit |
| Isolation/UI | TEST-only providers and inputs, no real sends; inert injected HTML/URLs, semantic filters/details/exports, expiry withdrawal, desktop/mobile axe and overflow verification |

## Reproducible fixture

`python tests/opportunity_shadow_fixture.py --output /new/empty/TEST-output`
produces the comparison, hash inventory, full immutable state, dashboard and
exports. It refuses to overwrite existing content. The replay uses a labeled
2026-09-08 exchange-session clock, synthetic sources and in-memory providers.

1. At 15:00 UTC, June 1 buying at a $100 reference is chased at $104: watching.
2. At 15:30, price is $102.50 with the earlier excursion retained, no new filing,
   and a fresh evidence review: watching, one return observation.
3. At 16:00, a second distinct eligible observation and current evidence produce
   one `qualified_reentry` intent. Every cycle is saved and restored.
4. Separate branches start from that same retained intent. Accepted branch sends
   once through a fake provider and does not repeat on restart. Stale branch
   presents a ten-minute-old quote, appends failed validation/supersession, and
   makes zero fake sends. Both branches make zero real external calls.

Legacy comparison invokes the actual retained `deterministic_score` and
`build_entry_plan` functions for each TEST scenario. It does not reinterpret
old scores as probabilities or pretend to reconstruct historical production
alerts. No performance advantage, fill, shares or returns are asserted.

## Verification and practical limits

Local regression tests include existing analyst, Edge, dashboard, Runtime v2,
atomic commit, shadow, concurrency, provenance and publication checks alongside
the feature tests. The completion receipt records exact final totals, SHA,
CI run/attempt IDs and artifact digests. CI additionally tests Python 3.11 and
3.12; existing Runtime safety CI provides its PostgreSQL service tests.

DOM tests exercise the source-rendered data using jsdom and axe. Headless Edge
was also checked at 1440x1100 and 390x844, including expanded timeline, with no
page errors, horizontal page overflow or axe violations (including contrast).
The mobile timeline is a labeled, keyboard-focusable scroll region. Browser
instrumentation allows the local axe script; shipped CSP remains unchanged.
No physical touch-device, screen-reader or Safari/Firefox validation is claimed.

Provider account entitlement/latency, complete live identity mappings, current
source/parser coverage and actual issuer-document budget feasibility are
unverified. Absent capability evidence remains nonactionable. Review documents
larger than the conservative full-document budget remain incomplete. No real
PostgreSQL service or cloud deployment was run locally; transport fakes invoke
real archive/validation/commit code, and separately reported CI may exercise
its isolated PostgreSQL service. Passing tests does not authorize production
activation. See [activation/rollback runbook](../CURRENT_OPPORTUNITY.md).


## Recorded implementation validation

Implementation tree at `47c97455e12cbc5cb42934666e83ebbd3087d0c2`:
338 local regression cases passed, including 87 opportunity cases; four DOM
cases passed. All exact-head PR runs completed successfully at attempt 1:

- [Current Opportunity, Python 3.11/3.12](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34131567152): 329 Python cases and four DOM cases on each interpreter.
- [Runtime v2 safety](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34131567128): 436 cases; PostgreSQL service and repository verification passed.
- [Investor Edge integration](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34131567153): 628 Python cases plus six filing-resolution and eleven scheduler DOM cases; repository verification passed.

Downloaded TEST artifacts were verified against GitHub's archive digest and all
299 entries in each fixture checksum inventory. Python 3.12 artifact
`10022300647`: `92923d6c865e5454ef558f91dc5554904a9e38f41dfd74d84a36f4712c5522d0`.
Python 3.11 artifact `10022299097`:
`f1e8e8baea854132edd46626868df8338cf2b627b552d3f7924c8a90740fb2fc`.
The earlier artifact upload omitted `.nojekyll`; the corrected upload includes
all checksummed TEST files. This entry records the tested implementation tree,
not a production certificate or a claim about later commits.
