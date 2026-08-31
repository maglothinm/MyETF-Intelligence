# Investor Edge historical bootstrap — local acceptance, 2026-08-31

Work record: [issue #11](https://github.com/maglothinm/MyETF-Intelligence/issues/11).
Canonical repository: **1349678672**, currently
**maglothinm/MyETF-Intelligence**, default branch **main**.
Implementation branch: **codex/investor-edge-bootstrap**, based on
`f2df59740b095417e3883fd81ac0a16c1d16fdad`. The implementation commit containing
this report is local; it has not been pushed, merged, dispatched or deployed.

## Proven root cause

The current main code already combined Legislative and Executive transactions
and already called global `refresh_leaderboard()` even with no new AI candidates.
Candidate selection was **not** the demonstrated cause of the one-profile
production result. Both `profile_for_trade()` and `refresh_leaderboard()` received
the combined retained ledger, not just the model's current batch.

The verified artifacts contained only **60 unique normalized transactions**, all
Legislative, of which **one** was an eligible historical equity purchase. Only one
eligible filer-owner identity could be discovered from those rows. Meanwhile,
**5,066 cataloged filings lacked any normalized transactions**. Baseline catalog
discovery recorded them as seen, and ordinary tracking processed only unseen
filings; subsequent runs never reconstructed the already-cataloged history.
Executive catalog rows were principally access-request listings, not parsed
transactions. Loading both branches alone could not manufacture missing history.

Additional demonstrated weaknesses were a loader that discarded legacy rows
without `trade_id`, sequential high-volume-first market backfill that could spend
all 30 slots before another identity's turn, and dashboard presentation without
explicit population/backfill counts. The root view also showed only the first
eight profile cards rather than a complete bounded inventory.

## Implemented behavior

- One canonical normalized history combines both branch `transactions.jsonl`
  ledgers. Older purchases supplement missing rows without overriding primary
  normalized fields. Stable IDs deduplicate; missing IDs use full SHA-256 over
  source/report (or filing key/source URL), filer, disclosed owner, asset, ticker,
  type, transaction date and amount. Original dates, earliest valid observation,
  eligibility fields and contributing branch/source/ledger provenance survive.
- AI candidate selection is separate. Every enabled AI run discovers and saves
  the full configured Edge population before bounded market work, even with zero
  candidates. Missing outcomes produce visible building profiles, not fabricated
  performance. Current candidates use cache-only, time-censored profiles after
  global maintenance; final publication grants no second processing budget.
- Deterministic breadth-first scheduling uses a durable investor cursor and puts
  untouched work ahead of retries. Cached prices can still be used at zero or
  exhausted network budget; cache misses do not create artificial failed attempts
  or retry backoff merely because no request could be made.
- Existing tracker writers silently reconstruct up to **20** already-seen
  catalog-only filings per run after complete required discovery. Official
  scanners, disclosure terms and access restrictions remain authoritative. A
  hash-, path- and identity-validated original-source manifest is checked first.
  Form 201 request-only records without legitimately supplied originals are
  counted as access-required and never requested automatically.
- Historical rows retain parser IDs and original observation timestamps, carry
  `historical_bootstrap: true`, and append idempotently. No baseline reset, new
  filing event, model candidate, candidate upgrade, external alert or new
  Notification Center event is created solely by reconstruction.
- Root and standalone Edge views show the complete bounded profile inventory
  independently of qualifying signal cards, plus actual profile, trade,
  eligibility, processed/pending, request and branch counts. Legacy missing
  telemetry stays unknown, not falsely current.
- Candidate-specific Edge scoring remains fail-open. Global initialization,
  refresh or persistence failure instead fails the AI run so incomplete state
  cannot be promoted. Initial failure stops candidate/market work. Existing and
  newly queued candidate deliveries wait until final maintenance succeeds and
  there are no earlier run errors; the existing bounded per-channel deduplication
  path is reused.

No scoring formula, confidence shrinkage, identity categories, alpha horizon,
modifier or hard cap changed. `config/investor_edge.yml` is unchanged: 40 recent
eligible purchases per identity, 40 published identities, 30 observation attempts,
40 provider requests, and 2,200-day lookback. **30 is not a 30-day filing window.**
New disclosures continue through the same durable observation/profile system.

## Actual production inputs and isolated results

Counts below use the latest unique filing/transaction identities unless marked
as raw append-only rows. “After” is a disposable local copy, **not production**.

| Measure | Verified production input | Isolated acceptance after two filing passes and two Edge passes |
|---|---:|---:|
| Legislative filings | 976 unique / 983 raw rows | 976 unique / 1,013 raw rows |
| Executive filings | 4,103 unique / 4,109 raw rows | Unchanged |
| Legislative normalized transactions | 60 unique / 65 raw rows | 359 unique / 364 raw rows |
| Executive normalized transactions | 0 | 0 |
| Combined normalized transactions | 60 | 359 |
| Eligible historical equity purchases | 1 | 122 |
| Unique eligible filer-owner identities | 1 | 17 |
| Published Investor Edge profiles | 1 | 17 |
| Completed profiles | 0 | 0 |
| Building-history profiles | 1 | 17 |
| Cached observation records, including unavailable results | 1 | 61 |
| Completed market observations | 0 | 0 |
| Pending trade observations | 1 | 122 |
| Cataloged filings lacking transaction backfill | 5,066 | 5,036 |

Filing pass 1 attempted 20 retained House filings: 16 parsed, 80 unique
transactions appended. Pass 2 attempted 20: 14 parsed, 219 appended. The final
population therefore contains **299 additional unique transactions from 30
historical filings**, with no new filing identities. Each source GET was limited
to the exact retained official House PDF URL, redirects disabled; original bytes
were retained with SHA-256 and identity-bound manifest entries. The existing
repository `DISCLOSURE_TERMS_ACKNOWLEDGED` variable was read-only verified true
at 11:26:48 UTC. That configuration receipt is not a legal-use determination.

A separate replay using only those 40 cached originals reproduced all 299
transactions with **zero network requests**. Repeating the same sample added
**zero transactions**, with transaction, purchase and filing ledgers byte-identical
to the preceding replay. Existing seen filing/trade/review IDs, original
observation timestamps and original ledger prefixes were preserved.

Each Edge pass processed **30 observation attempts** with zero new filings,
zero model analyses and zero provider requests. The acceptance deliberately
supplied no market-provider credentials; cached stock/benchmark coverage was
insufficient. Thus all 17 profiles remained building and **122 observations
remained pending**. Processing an unavailable observation is not a completed
return. No alpha, hit rate, price, high-confidence status or performance was
invented. Current observations/profiles were the only AI-copy outputs changed;
`state.json`, `analyses.jsonl` and `runs.jsonl` remained byte-identical.

The final code repeated this Edge acceptance in another new copy with the same
17/122 result. All **47** originally verified input files and the first acceptance
copy remained hash-identical. Those copies and raw-document caches are test
evidence, never alternate production-state authority.

Pending reduction is demonstrated separately with deterministic available-price
fixtures: 43 pending trade observations become **13 after the first 30-slot pass,
then 0 after the second 13-slot pass on the same day**, with no new filing.
This is algorithmic continuation proof, **not proof of live market completion**.

Eligibility diagnostics in the actual expanded input: `not_purchase: 206`,
`unresolved_ticker: 78`, `not_confidently_equity: 66`. Reasons can overlap and
must not be summed as an exclusive partition. Both-branch eligibility is proven
by tests; the real Executive input contains no parsed transactions.

## Remaining source work and limitations

The 5,036 remaining catalog-only filings comprise:

| Source/access | Remaining | Explanation |
|---|---:|---|
| House/direct | 849 | 839 outside this bounded sample; 8 local OCR failures and 2 existing parser-layout failures |
| Senate/direct | 90 | Not attempted in this House-only acceptance; normal execution requires the existing validated Senate session |
| OGE/request | 4,097 | Form 201 access-required inventory; no automatically retrievable original was available |

The eight scanned House originals have no text layer, and local parsing failed
with `MonitorError` caused by `TesseractNotFoundError`: report IDs
`house:2026:9116256`, `9116257`, `9116258`, `9116267`, `9116290`, `9116292`,
`9116308`, and `9116311` (the same `house:2026:` prefix applies to each).
Poppler is present. The existing Linux tracker workflows install Tesseract,
but these exact documents have **not** been verified on that runner; OCR or
paper-checkbox review may still prevent automatic parsing.

Reports `house:2026:20035175` and `house:2026:20035209` expose an existing
House scanner limitation: the upper amount bound occurs on the first
continuation line, followed by more asset-description lines, while the prepass
checks only the final continuation line. The scanner rejects the incomplete
amount range. Original-page inspection shows `[GS]` securities, not eligible
equity purchases. This task records the defect rather than silently modifying
the official parser's interpretation. All ten remain explicit pending work.

The accepted source manifest is a read-only bridge. Default manifests and raw
documents inside the existing tracker-state upload directory are retained by
that artifact; externally configured files are **not automatically copied or
uploaded**. Flattened AI document-text caches are not original parser inputs.

## Tests and dashboard verification

Final full local suite: **346 passed**, no skips, in 62.17 seconds, with existing
Node/JSDOM/axe dependencies explicitly configured. Command:

```text
python -m pytest tests -q -rs --basetemp .remediation/test-full-edge-final -p no:cacheprovider
```

| Requested coverage | Evidence |
|---|---|
| A, C: multiple identities/both branches | Canonical loader and real zero-candidate runtime fixtures publish four identities across both branches |
| B: zero candidates | Historical-bootstrap and already-analyzed normal histories refresh without OpenAI, SEC candidate work or alerts |
| D: deduplication | Stable IDs, overlapping purchases, deterministic legacy IDs, distinct source URLs and owner categories |
| E: bounded continuation | 43 observations, 30 then 13 processed, pending 13 then 0, same day/no new filings |
| F: discovery before completion | Profiles persisted before the first provider operation; zero-budget and unavailable-price profiles remain visible |
| G: fairness | Prolific/low-volume identities, persisted cursor, deterministic ordering and retry-vs-untouched scheduling |
| H: filing bootstrap | Bounded/cache-first official parser use, idempotence, timestamps, seen IDs, original ledger prefixes and complete-discovery gating |
| I: no duplicate alerts | Bootstrap selection/queue/notification exclusions, projected event exclusions, initial/final maintenance failure gates, existing per-channel retries |
| J: no scoring regression | Existing Edge suite plus future-cutoff/partial-horizon, owner separation, last-good-profile, benchmark and hard-cap regressions |
| Cache edge cases | Real provider cache at zero/exhausted request budgets, miss-before-hit ordering and preserved partial benchmark/observation identity |
| New disclosures | Cache-only publication and later normal trades enrich the same profile inventory |

Additional focused results: **67 Edge tests**, **30 AI analyst tests**, **36 DOM
scenarios**, and **32 native notification scenarios** passed. Python compilation,
JavaScript syntax, YAML contract checks and `git diff --check` passed. Four
workflow diffs add only test selections/path filters (nine lines); schedules,
concurrency, secrets, restore selection, artifact names and uploads are unchanged.
The full Linux `verify.sh` was not executed locally; no new remote CI result is
claimed for this unpushed implementation.

The actual-copy dashboard build produced **5,079 unique filings / 359
transactions / 1,496 review items / 11 analyses / 0 paper positions**.
The root and standalone browser views both displayed 17 profiles, 0 complete,
17 building, 359 trades, 30 processed attempts and 122 pending observations.
All 17 root table rows were present, Edge values unavailable, no console
warnings/errors, and no horizontal document overflow at the ordinary 1280×720
browser viewport. Physical-device, touch/audio and Safari acceptance are not
inferred from those checks.

## Fresh GitHub authority and deployment boundary

Read-only final audit: **2026-08-31 11:48:15–11:48:35 UTC**. Exact repository,
default branch, workflow/display name, successful producer job, attempt window,
consumer ancestry, global producer high-water marks, expiration, downloaded ZIP
digest, full inventory and continuity checks passed. All three remain unchanged
from the inputs inspected before implementation. Their producer commit is
`3902968d5d70cd00030248ae4a6bcea18aa2e6ea`, ancestor of the audited main.

| Protected artifact | Artifact ID | Successful run / attempt | Producer job | ZIP SHA-256 |
|---|---:|---|---:|---|
| `legislative-tracker-state` | 9749549239 | [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) / 1 | 99417536057 | `fcd8d2398fe1f6631e87023aa90b90e695fd64be21c5034df1c7196c2ded9479` |
| `executive-tracker-state` | 9746602231 | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | 99391153447 | `997a0eaf63b4b3bd33bbda34bfc40a633802c04cfd891f6a2dca726d93a2b4be` |
| `ai-analysis-state` | 9749567326 | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | 99417669143 | `318e1892cc74505711dd362ba96255d060e5a099d174f36627af7f222c981aa9` |

Isolated `simulation-state` is unchanged: artifact **9734790733**, successful
run **33320677882 / 1**, job **99281977011**, two retained replay rows. Neither
simulation workflow changed or ran. No protected writes, production deployment,
live AI/market requests, Pushover/Gmail/Healthchecks delivery or credential/settings
changes were performed in this acceptance. Only bounded official House source
retrieval and read-only GitHub/Pages checks used external services.

An unrelated existing simulator review concern is retained in HANDOFF: its
notification-isolation step reserializes predecessor JSONL after prefix
validation. No simulator execution or universal future-prefix guarantee is
inferred from the unchanged artifact verified here.

Live [Pages](https://maglothinm.github.io/MyETF-Intelligence/) remains the earlier
review-UX release: successful [33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313)
/ attempt 1, build job **99465681041**, deploy job **99465807219**, artifact
**9755242103**, source `9d9e7bef326a0e24a5f846ea1310dec24a647019`.
Root, Wallboard, standalone Edge and summary returned HTTP 200 and matched that
artifact. These are existing successful runs, **not runs of this fix**.

The auditor also evaluated held PR #3's additional pre-manifest migration
allowlist and reported that these newer artifacts are not listed. That is an
existing held-PR migration gate, not evidence that deployed main's provenance
checks failed. No held allowlist or restore policy was modified or bypassed.
Obsolete runs **33219808359** and **33221027676** remain queued at attempt 1 with
zero jobs/artifacts; their existing manual-production-dispatch gate remains.

## Changed files and next safe action

Implementation: `scripts/{ai_filing_analyst,investor_edge,government_trade_tracker,
historical_transaction_bootstrap,dashboard_insights}.py`,
`scripts/dashboard_assets/{app.js,index.html,styles.css}`.
Tests: `tests/{test_ai_filing_analyst,test_historical_transaction_bootstrap,
test_investor_edge_core,test_investor_edge_surfaces,test_dashboard_insights}.py`
and `tests/dashboard_dom.test.cjs`. Coverage-only workflow changes:
`ai_filing_analyst.yml`, `legislative_trade_tracker_v2.yml`,
`executive_trade_tracker.yml`, `investor_edge_tests.yml`. Documentation:
both Investor Edge/AI READMEs, PROJECT_STATE, DECISIONS, HANDOFF and this report.

Review and release the local commit through canonical CI when authorized. Then
verify actual sole-writer artifact successors, stable IDs and profile/pending
counts over normal runs with configured market access. Do not claim pending
market work is decreasing in production until that evidence exists. Respect the
obsolete-writer gate before any separate manual production run; do not rebaseline
or upload these acceptance copies. Source parser follow-up, physical-device
acceptance, Gmail delivery, held PR #3 and repository cutover remain separate.

Ignored local evidence is under `.remediation/investor-edge-bootstrap/`:
`initial-audit/`, `final-audit/`, `before-population.json`,
`actual-bootstrap-passes.json`, `actual-edge-passes.json`,
`bootstrap-document-diagnostics.json`, original source-document hashes,
`final-code-acceptance/`, and `dashboard-preview/`. None is production authority.
