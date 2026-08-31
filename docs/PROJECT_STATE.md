# PolitiTrack project state

Last updated: **2026-08-31 UTC**
Status: **Investor Edge release authorized and pushed in PR #15; integrating the
concurrent Operations ordering release from PR #14. Final integrated CI, merge
and Pages verification are pending. Existing production-state and cutover gates
remain unchanged.**

This file is a point-in-time operational snapshot, not a substitute for checking
live GitHub state. See `AGENTS.md` for the mandatory verification procedure.

## Investor Edge release — in progress 2026-08-31

The owner requested “Release the commit”. Implementation `b4a9049` is pushed in
[PR #15](https://github.com/maglothinm/MyETF-Intelligence/pull/15).
Its initial [CI run](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33390265467)
passed 263 tests and Linux `verify.sh`. Concurrent PR #14 merged to main at
`7a1108fb2e32c39f6af943395c1bb9b9a550d26f`; this integration preserves both
features and their tests. The integrated local suite passed **347 tests**, without
skips, including optional DOM checks. Integrated CI, merge and deployment remain pending.
The records below retain the earlier local-acceptance checkpoints; they are not
claims that the bootstrap has already advanced production data.

## Investor Edge historical bootstrap — pre-release acceptance 2026-08-31

[Issue #11](https://github.com/maglothinm/MyETF-Intelligence/issues/11) implements
combined normalized history, explicit zero-candidate global maintenance,
discovery-first building profiles, durable breadth-first market backfill, and a
separate 20-filing historical transaction reconstruction pass inside the existing
tracker writers. Full root/standalone inventories now expose actual population
and pending-work telemetry. Scoring, owner identity, no-lookahead protections,
40/40/30/40/2,200 limits, protected artifact names and writer ownership are
unchanged. Workflow edits add only test coverage/path filters.

The demonstrated production cause was missing parsed history, not candidate-only
input: main already combined both branches and globally refreshed Edge, but the
artifacts held only **60 unique transactions / 1 eligible purchase / 1 identity**
alongside **5,066 catalog-only filings**. Baseline-seen filings were never revisited
by normal unseen-filing processing. Historical rows now append idempotently with
original IDs/observation timestamps and no new-filing, AI-candidate, external-alert
or Notification Center events. Global Edge persistence failures stop successful
state promotion; live candidate delivery waits until final maintenance succeeds.

Actual artifact-copy acceptance: 40 bounded House filing attempts parsed 30
filings and added 299 unique transactions. Copies now contain **359 unique
transactions / 122 eligible purchases / 17 identities and profiles**. All 17
profiles are building; no completed market outcomes were fabricated. Each of two
Edge passes processed 30 attempts, but **122 observations remain pending** because
no provider credentials were supplied and cached benchmark/stock coverage was
insufficient. Deterministic available-price tests separately show 43 pending
observations falling to 13, then 0, without new filings. The actual acceptance is
not evidence of decreasing production market backlog.

Remaining catalog-only work: **5,036** (849 House, 90 Senate, 4,097 OGE/request).
Eight sampled scans need missing local Tesseract; two expose an existing House
multiline amount parser limitation. OGE Form 201 originals require legitimate
access; they were not automatically retrieved. Cache-only replay reproduced all
299 transactions and its repeated sample added none. Original input hashes,
seen IDs, ledger prefixes and immutable AI decision history remain unchanged.

Local verification: **346 tests passed**, including available DOM checks;
syntax/compilation, YAML contracts, static generation and actual-copy root and
standalone browser checks passed. No new remote CI/Linux workflow result is
claimed. Implementation is in the isolated same-repository worktree
`.remediation/investor-edge-worktree`, branch `codex/investor-edge-bootstrap`,
based on canonical main `f2df59740b095417e3883fd81ac0a16c1d16fdad`. Other tasks'
checkout, unpublished work and the approved Senate/UI release evidence are
preserved. This local implementation has not advanced main or production state.

Final read-only GitHub audit at **11:48:35 UTC** reconfirmed the unchanged
protected authorities: Legislative **9749549239 / 33369634244 / attempt 1**,
Executive **9746602231 / 33360633323 / attempt 1**, AI
**9749567326 / 33369677492 / attempt 1**. Exact producer jobs, workflow identity,
ancestry, high-water marks, expiry, ZIP hashes and full continuity passed.
Simulation **9734790733 / 33320677882 / attempt 1** remains two rows, unchanged.
Live Pages is still **33385044313 / attempt 1**, artifact **9755242103**, source
`9d9e7be`; four fixed live surfaces returned HTTP 200 and matched its bytes.
No collector, AI, simulator, alert or heartbeat was dispatched by this task.

See [the validation report](validation/investor-edge-bootstrap-2026-08-31.md)
for raw/deduplicated counts, exact run links/jobs/hashes, A–J test coverage,
source failures and remaining limits. Review/release through canonical CI when
authorized; then verify sole-writer successors and real pending reduction.
Do not upload acceptance copies, rebaseline, change held PR #3's allowlist, or
bypass the existing obsolete-run gate for a separate manual production run.

## Operations history ordering — pre-release record, 2026-08-31

Release update: [PR #14](https://github.com/maglothinm/MyETF-Intelligence/pull/14)
is now merged at `7a1108fb2e32c39f6af943395c1bb9b9a550d26f`.
The following paragraphs preserve its earlier implementation checkpoint.

Issue #12 uses isolated branch `codex/operations-history-order`, based on canonical
`main` `f2df59740b095417e3883fd81ac0a16c1d16fdad`, the documentation-only
successor of deployed `9d9e7be`. The shared health-card renderer
now sorts a copied timeline by parsed execution finish time (valid start fallback),
newest first, with deterministic ID/URL ties. Operations and its Overview preview
share DOM, link and timestamp order. Native horizontal scrolling remains unchanged;
refresh rebuilds the strip at its leftmost/latest item. No backend, stored state,
workflow, scheduling, alert, simulation or hosting configuration changed.

Local verification: **296 active Python tests passed**, **47 DOM scenarios**,
**10 native history scenarios** and **32 native notification scenarios** passed.
Generated TEST previews passed desktop/mobile-width native scrolling and refresh
checks. Physical keyboard/touch/Safari acceptance remains unverified.

Implementation `39f7edc28eda1ce4a309a2069321ee27d2574f94` is pushed in
[draft PR #14](https://github.com/maglothinm/MyETF-Intelligence/pull/14).
Canonical CI [33387285664](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33387285664)
succeeded with 214 tests and Linux `verify.sh` reporting `VERIFICATION PASSED`.
This documentation-only successor records that result. The fix is not merged
or deployed; its release must use the existing read-only publisher because the
Pages push-path filter does not include the changed frontend asset.

Fresh read-only GitHub audit found the earlier review UX publication complete:
PR #10 merged to `9d9e7be`; main CI
[33385044349](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044349)
and Pages
[33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313)
both succeeded on attempt 1. All 28 live public content files matched Pages
artifact `9755242103`, with build `9d9e7be`. These results verify the previous release; they do not publish issue #12.

Protected artifact metadata remains unchanged: Legislative `9749549239`
(`33369634244`/1), Executive `9746602231` (`33360633323`/1), AI `9749567326`
(`33369677492`/1). Exact workflow/job/attempt windows, expiry, ancestry and producer
high-water checks passed across all 158 audited runs. No protected payload was
restored or written; this is metadata/provenance continuity, not a new full ledger
audit. Evidence is in ignored `.remediation/operations-history-audit/` in the shared
workspace; local implementation/TEST preview are in its isolated worktree.
See the active handoff for final local test results and publication status.

## Dashboard review UX — published and verified 2026-08-31 11:04 UTC

The owner explicitly requested “Publish” after the local implementation and its
device limits were reported. PR [#10](https://github.com/maglothinm/MyETF-Intelligence/pull/10)
merged tested head `ca0152044bec58032acc3c7604398e844b2ba12f` as
`9d9e7bef326a0e24a5f846ea1310dec24a647019` on canonical `main`; their trees
match. This release preserved the separately approved recovery documentation
from `ac6342ac85e5a395f1b8bab251b8f608c47249e0`, including its unchanged
incident record. This final evidence update changes documentation only.

[Live dashboard](https://maglothinm.github.io/MyETF-Intelligence/) and
[Manual Parser Exceptions](https://maglothinm.github.io/MyETF-Intelligence/#records/reviews?category=manual_exception)
are published from repository ID **1349678672**, current name
**maglothinm/MyETF-Intelligence**. Local `main` at `9e5de909` remains preserved.

The Overview card opens the full exception inventory with stale filters cleared.
One shared Python projection/classifier drives counts and public JSON/CSV rows,
including synthetic-record exclusion from production totals. Clickable reviews
select an exact retained filing or show their original review when no exact match
exists. Source filters expose retained source/branch taxonomy and consistent OGE
capitalization. Signals, Records and Operations reuse the existing workspace
tooltip behavior. Refresh keeps newly opened tables consistent with the summary.
No workflow, collector, scoring, state schema, alert, simulation or hosting path
changed. The dashboard remains read-only, without retry or resolution actions.

| Release evidence | Verified result |
|---|---|
| PR CI | [33384840936](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33384840936), attempt 1, job `99465044563`; success |
| Main CI | [33385044349](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044349), attempt 1, job `99465680760`; success |
| CI coverage | Both exact-attempt logs show 213 selected tests passed and Linux `verify.sh` reporting `VERIFICATION PASSED` |
| Pages | [33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313), attempt 1, push; success |
| Pages jobs | Build `99465681041`; deploy `99465807219`; both successful |
| Pages artifact | `9755242103`; exact successful attempt/build window, expiration and ZIP digest verified |
| Pages ZIP SHA-256 | `ca3b63daecb7c4e6ce5e92e162cbb363e753c07d8983fddcc1306ca7ac7e4014` |
| Live content | 11:04:50 UTC: all 21 fixed dashboard/Wallboard/Edge/assets/JSON URLs returned HTTP 200 and matched the artifact bytes |
| Published build | `9d9e7bef326a0e24a5f846ea1310dec24a647019` in dashboard insights |

Full local suite rerun after integration: **295 passed**, including the nested
release checks. **34 DOM scenarios**, **32 native notification scenarios**, JS
syntax, Python compilation, static generation and diff checks passed. The Linux
CI results resolve the local Windows Bash limitation; they do not imply that CI
provisioned the optional JSDOM/browser dependencies.

Rendered preview checks passed at 1440×1000 and 390×844 for card/filter/detail
navigation, selected-record focus, mobile visibility and all five hover bubbles.
After deployment, the in-app browser at 1280×720 confirmed card → one exception →
exact filing → back, visible focused record, source choices, shared help attributes
and no horizontal document overflow. The retained record is RICHARD BLUMENTHAL,
filed 2026-08-21; the queue and card both show **1** manual parser exception.
Keyboard/touch behavior passed DOM fixtures; native keyboard activation, physical
touch/iPhone Safari, audio and physical ultrawide acceptance remain unverified.
Axe fixture checks exclude layout and color contrast. Issues #4 and #6 stay open
for those acceptance limits, not for deployment.

### Protected inputs and continuity

Fresh preflight completed at 11:00 UTC; post-deployment audit at 11:04:50 UTC
verified actual publisher restore logs, exact workflow/job/attempt identity,
ancestry, global producer high-water marks, expiration, downloaded ZIP digests,
full inventories and unchanged retained counts/IDs:

| Protected input | Artifact | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9749549239` | [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) / 1 | `99417536057` |
| Executive | `9746602231` | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | `99391153447` |
| AI | `9749567326` | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | `99417669143` |

The publisher consumed these exact inputs and uploaded only `github-pages`.
No protected state was replaced or advanced. Published counts reconcile to
**5,079 filings / 60 transactions / 1,496 reviews / 11 analyses**, including
1 manual exception and 1,495 access/request-required records. Isolated
`simulation-state` artifact `9734790733`, run `33320677882` / attempt 1 / job
`99281977011`, is unchanged with two replay rows and preserved predecessor bytes.
No collector, AI, simulator or external-alert workflow was manually dispatched.
No credentials or repository settings were changed or independently tested.

Known-good pre-release rollback Pages: `33369728437` / attempt 1, artifact
`9749580990`, exported ZIP SHA-256
`330d1e4e343d827d917eb3902ba289eed59f00554147a82c38469b86a05df427`.
Rollback is a reviewed source revert through Pages using current valid inputs;
it never replaces protected state with a historical snapshot. Ignored evidence:
`.remediation/dashboard-review-publish/`, including `release-evidence.json`,
`deployment-verification.json`, exact CI receipts/logs and exported artifacts.
These records are verification evidence, not production restore authority.

The two known obsolete queued runs were the only active runs at verification.
Their manual-dispatch gate, support-route blocker, held PR #3, rename/privacy,
legacy settings and Gmail delivery proof remain separate open work. The Senate
recovery checkpoint below is preserved from the approved upstream documentation.

## Senate recovery — verified 2026-08-31 09:51 UTC

Issue #8 adds strict official-source session validation, bounded retries and
complete Legislative discovery before processing. The code preserves existing
production artifacts, stable IDs, baselines and alert deduplication. Two later
scheduled runs used the merged fix and passed independent operational validation.
The owner explicitly approved the new recovery evidence for issue #8, PR #9 and
main. It is published in [issue comment 5477003406](https://github.com/maglothinm/MyETF-Intelligence/issues/8#issuecomment-5477003406)
and linked from [PR comment 5477009236](https://github.com/maglothinm/MyETF-Intelligence/pull/9#issuecomment-5477009236).
This documentation-only publication records the same checkpoint. A fresh audit
at **10:24 UTC** reconfirmed unchanged authority, full continuity, both obsolete
queues and all 21 live Pages files. See [the incident evidence](incidents/senate-efd-2026-08-30.md) for
exact run URLs, jobs, hashes, continuity and queue-cleanup receipts. Older tables
below remain historical checkpoints, not current artifact authority.

PR [#9](https://github.com/maglothinm/MyETF-Intelligence/pull/9) merged source
`125eac1aba5a5f5324040cbfac7f30b63a2f0347` as
`19f7044e8bd12fd4d693cf7f468623f318034717`; their trees match. Local full suite:
283 passed. PR CI [33346339195](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33346339195)
and main CI [33346456045](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33346456045)
both succeeded with 212 selected tests and `VERIFICATION PASSED` from Linux
`verify.sh`. The audited runtime commit is
`3902968d5d70cd00030248ae4a6bcea18aa2e6ea`; this evidence update changes no code.

Scheduled Legislative runs
[33348331610](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33348331610)
and [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244),
both attempt 1, succeeded with House **883** / Senate **91**, complete discovery,
zero baseline changes and zero alerts. Each delivered exactly one classified
Healthchecks success request accepted with **HTTP 200**. Provider-side UP/status
history was not separately queried. Neither run was manually dispatched by this
session. The additional requested manual run has **not** been dispatched.

| Current protected checkpoint | Artifact | Successful run / attempt | Job | Retained counts |
|---|---:|---|---:|---|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` | 983 filings; 65 transactions; 19 purchases; 1 review; 31 runs |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` | 4,109 filings; 1,495 reviews; 23 runs |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` | 12 analyses; 36 runs |

Exact workflow/job/attempt provenance, commit ancestry, producer high-water
marks, expiration, ZIP digests, complete inventories, ledger prefixes and
protected IDs passed. Legislative actual restore lineage is
`9739239507 → 9742750536 → 9749549239`; run-history counts advanced 29 → 30 → 31.
All pre-incident non-run ledgers remain byte-identical. No rebaseline occurred.

Pages [33369728437](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369728437)
/ attempt 1 succeeded, artifact `9749580990`. It restored exactly the three
checkpoints above. All **21** checked live files returned HTTP 200 and matched
the artifact; published build is `3902968`, with 5,079 filings, 60 transactions,
1,496 reviews and 11 analyses. Existing contextual help remains deployed. This
is content/deployment acceptance, not physical-device acceptance.

## Repository identity

| Role | Repository | Repository ID | Recorded head | Status |
|---|---|---:|---|---|
| Canonical | `maglothinm/MyETF-Intelligence` | `1349678672` | Verified UI / Pages `9d9e7be` plus documentation-only evidence successor | **Public** standalone repository with Pages enabled; awaiting same-ID rename and intended privacy correction |
| Final canonical name | `maglothinm/PolitiTrack` | `1349678672` | Same history | Approved target name; do not create a new repository |
| Legacy | `maglothinm/MyETF` | `1033519491` | `36447a2` | Code-frozen public history; all six workflows removed, but Pages and archive settings remain open |

GitHub issue `#1`, **Consolidate repositories and cut over to PolitiTrack**, remains the
cutover record; issue #4 tracks the UI release and remaining device acceptance. The canonical repository's numeric ID is authoritative if an
old URL redirects after the rename.

## UI release checkpoint — 2026-08-30

The UI-only branch `codex/dashboard-redesign` starts from live main
`4a9135a8c12af6eebfce01cf33772ffa13e41951` and excludes held PR #3. There is no
workflow, collector, analyst-runtime, scoring, schema, alert or simulation-contract
change. Existing read-only Pages publishing is the only deployment path.

Fresh audit at 16:35 UTC verified latest protected artifacts, exact successful
attempts/jobs, producer high-water marks, ZIP digests, inventories and continuity:

| Pipeline | Artifact | Producing run / attempt | Producer job | Retained counts |
|---|---:|---|---:|---|
| Legislative | `9734211271` | `33318579174` / `1` | `99276401831` | 983 filings; 65 transactions; 19 purchases; 1 review; 27 runs |
| Executive | `9732455687` | `33312565343` / `1` | `99260139758` | 4,109 filings; 1,495 reviews; 19 runs |
| AI | `9734221839` | `33318614858` / `1` | `99276494661` | 12 analyses; 28 runs |

Producer commits are `4a9135a`. No eligible canonical producer was pending.
The two obsolete queued runs remain unchanged cutover blockers. Latest isolated
`simulation-state` is `9734790733`, run `33320677882` / attempt 1, job
`99281977011`, with two replay rows and verified predecessor prefix.

Known-good Pages rollback: `33320697336` / attempt 1, artifact `9734796157`,
exported ZIP SHA-256
`e8dc54967255af1fca24ed0f16383b3b2fa145cca947a8ec1d133e3ab4c0bca2`.
Old live Pages matched this artifact. After development, 209 immutable input/copy
hash-size checks passed with zero differences. Copies are fixtures, not authority.

Published deduplicated counts: 5,079 filings, 60 transactions, 1,496 reviews,
11 analyses and zero open paper positions. Coverage separates 5,066 cataloged-only,
6 processed and 7 review-required filings; review inventory separates 1 manual
exception from 1,495 access-required records. No signal qualifies at this snapshot.

Final local active suite: 181 passed; final targeted suite: 9 passed including the
additive UI suites (61 model, 32 native Node notification and 12 DOM scenarios).
Axe found zero serious/critical fixture findings with contrast/layout unavailable.
Linux verify.sh and PR/main CI passed; Pages evidence follows. Chrome, iPhone Safari,
real audio, responsive screenshots and physical CHG90 are unverified. The owner
explicitly requested merge/deploy after disclosure; issue #4 remains open for
device acceptance. No collectors, AI, simulations or external alerts were
manually dispatched. See D-2026-08-30-019 and the active handoff.

## Verified deployed release

## Contextual-help publication — verified 2026-08-30 17:36 UTC

The owner explicitly requested publication after the Chrome/device gap was
disclosed. PR [#7](https://github.com/maglothinm/MyETF-Intelligence/pull/7) merged
tested source `2a955f571c2cd4cf26b033984daa39904c11d64c` as
`1aa87398b53689873de350155d33afdb993fb036` on canonical `main`. Their trees match.
Documentation-only successors do not change the deployed application source.

[Live dashboard](https://maglothinm.github.io/MyETF-Intelligence/),
[Investor Edge](https://maglothinm.github.io/MyETF-Intelligence/investor-edge.html)
and [Wallboard](https://maglothinm.github.io/MyETF-Intelligence/wallboard.html)
are published from repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.

| Release evidence | Verified result |
|---|---|
| PR CI | [33325538713](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325538713), attempt 1, job `99294887628`; success, 78 selected tests |
| Main CI | [33325629684](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629684), attempt 1, job `99295130888`; success, 78 selected tests |
| Linux verifier | Both CI runs passed the existing release gate, which executes full `verify.sh` and requires `VERIFICATION PASSED` |
| Pages | [33325629663](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629663), attempt 1; success; build `99295130679`, deploy `99295188583` |
| Pages artifact | `9736138918`; exact successful attempt/build window and ZIP digest verified |
| Pages ZIP SHA-256 | `f8d5a8e65fa26e34b06e425a6016100fd0e488b312a3aa2fae5731a378acf283` |
| Live verification | 17:36:13 UTC: 21 root/Wallboard/Edge/assets/JSON URLs returned HTTP 200 and exactly matched the Pages artifact |
| Published build | `1aa87398b53689873de350155d33afdb993fb036` |
| Source-content check | 27 additional checks passed across 11 fixed live URLs, including exact source asset/script comparisons, shared copy, help/touch attributes and persistent warnings |

The earlier Windows verifier limitation is resolved for this release by Linux CI.
Local verification remains **182 tests passed**, including **24 JSDOM scenarios**
and **32 native Node notification scenarios**. JSDOM is an optional dependency
not provisioned by CI; its local results are not inferred remote CI results.
Real Chrome/Safari/touch, responsive screenshots, rendered overflow/caret/CSP and
physical-device acceptance remain unverified under issue #6.

### Protected inputs and continuity

Scheduled Executive and downstream AI runs completed before publication. Their
newer artifacts passed exact workflow/job/attempt identity, ancestry, producer
high-water checks, ZIP digests, schema and full inventory/record continuity
against original, prior and last-deployed checkpoints. No eligible writer was
active before merging or at final verification.

| Pipeline | Newest protected artifact | Successful run / attempt | Job | Retained counts |
|---|---:|---|---:|---|
| Legislative | `9734211271` | `33318579174` / 1 | `99276401831` | 983 filings; 65 transactions; 19 purchases; 1 review; 27 runs |
| Executive | `9736054489` | `33325239324` / 1 | `99294089255` | 4,109 filings; 1,495 reviews; 20 runs |
| AI | `9736064296` | `33325343519` / 1 | `99294369216` | 12 analyses; 29 runs |

Actual publisher restore logs, fresh global authority checks and downloaded
protected ZIPs/full inventories prove these inputs were unchanged through
publication. Published counts reconcile to 5,079 filings, 60 transactions,
1,496 reviews and 11 analyses. The Pages run uploaded only `github-pages`.
No collectors, AI, simulations, external alerts or production-state writers were
dispatched by this release task, and no workflow rules were changed.

Isolated simulation artifact `9734790733`, run `33320677882` / attempt 1, remains
unchanged with two replay history rows and preserved predecessor bytes.
Known-good rollback Pages is `33325376676` / attempt 1, artifact `9736074454`,
exported ZIP SHA-256
`910f9e40171a11ea3f0ade63b6dae4386ca4979faaa48d31c7cc4e785739b371`.
Ignored local evidence: `.remediation/tooltip-publish-preflight`,
`.remediation/tooltip-published/deployment-verification.json`, and
`.remediation/tooltip-live-content.json`. These are recovery/verification records,
not alternate production authority.

Only the two known obsolete queued runs remained at final verification. Issue #1,
held PR #3, repository rename/privacy, legacy settings retirement and Gmail
delivery proof remain separate open work. Issue #6 remains open for device
acceptance, not because publication is pending.

## Earlier deployed redesign evidence

PR [#5](https://github.com/maglothinm/MyETF-Intelligence/pull/5) merged UI source
`e2f71cff8029871656ba2dbd8c4021e406ea2e9c` as
`12d58964060885696ef4f5d3724ba5575de33fb2` on canonical `main`. The merge tree
exactly matches the tested PR tree. This evidence update changes documentation
only and does not change the deployed application source.

| Evidence | Verified result |
|---|---|
| PR CI | [33323384450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323384450), attempt 1, job `99289162854`; success |
| Main CI | [33323430401](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430401), attempt 1, job `99289284185`; success |
| CI coverage | 77 selected tests in each run; included release gate executes additive UI suites and Linux `verify.sh`, requiring `VERIFICATION PASSED` |
| Pages | [33323430450](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33323430450), attempt 1, `push`; success |
| Pages jobs | Build `99289284456`; deploy `99289373251`; both successful |
| Pages artifact | `9735544864`, exact build-attempt window and ZIP digest verified |
| Pages ZIP SHA-256 | `0edc98bfc0176f4b2407edfd15218ccb76451426a99380b7a39a6172f107c692` |
| Live acceptance | 2026-08-30 16:49:28 UTC: 21 fixed root/Wallboard/Investor Edge/assets/JSON URLs returned HTTP 200 and exactly matched the Pages artifact |
| Deployed build SHA | `dashboard-insights.json.build_sha` equals `12d58964060885696ef4f5d3724ba5575de33fb2` |
| Continuity | Actual restore logs, newest global authority and high-water checks passed; all three protected ZIPs and full inventories are unchanged from the release checkpoint |
| Simulation isolation | `9734790733` and its two replay rows unchanged; no new simulation run |
| Final active-run inventory | No active eligible production writer; only the two previously known obsolete queued runs remain |

Live [dashboard](https://maglothinm.github.io/MyETF-Intelligence/),
[Wallboard](https://maglothinm.github.io/MyETF-Intelligence/wallboard.html) and
[Investor Edge](https://maglothinm.github.io/MyETF-Intelligence/investor-edge.html)
are deployed. This is HTTP/content acceptance, not real-browser visual or device
acceptance. No production-state artifact was uploaded by the Pages run.

## Historical post-reconciliation checkpoint

The state was migrated into the canonical repository by successful run
`33179207530`. The following successful production runs and unexpired artifacts
are the post-reconciliation checkpoint. Always query GitHub for newer valid artifacts
before a run; do not hard-code these IDs as permanent restore targets.

| Pipeline | Successful run | Protected artifact | Artifact ID | `state.json` SHA-256 | Validated record counts |
|---|---:|---|---:|---|---|
| Legislative tracker v2 | `33283553866` | `legislative-tracker-state` | `9723708154` | `045a3f8c5f5a9f096ef12290f7db84228e1a5f127cff56fb20960e851c25cf58` | 983 filings; 65 transactions; 19 purchases; 1 pending review; 24 runs |
| Executive tracker | `33283609603` | `executive-tracker-state` | `9723732691` | `7a70efafe057f2e9883bcb69d2ea312804d3431b7dabeff89c558a3cd6271d75` | 4,109 filings; 1,495 pending-review records; 17 runs |
| AI analyst / paper portfolio | `33283690942` | `ai-analysis-state` | `9723743439` | `65cfa452dcb78dd14843155218b65178fb6fea7030cfbee95ac655bd22e2df19` | 12 analyses; 23 runs |

The 2026-08-30 post-deployment validation found that every filing, transaction,
purchase, review, and analysis ledger is byte-identical to the pre-change
checkpoint. Only successful run lineage and state timestamps advanced. No
approved task in the repository consolidation
authorizes a rebaseline. State absence, ambiguous rerun-attempt provenance, a
failed restore, or a later successful producer with no valid successor artifact is
a stop condition.

Production-state authority is the newest provenance-valid artifact, not a cache.
Selection must verify repository, branch, workflow identity, producer job and
commit, and the exact successful attempt whose time window contains the artifact.
A rerun's aggregate run conclusion is insufficient because all attempts share the
same run ID.

## Current design and deployment evidence

- Commit `1af4696` deployed the reconciled PolitiTrack tree on top of `5a132e1`.
  Commit `fe6d180` fixed read-only permissions only in the isolated Run Simulation
  copy. Production acceptance commit `d5ef440` then exercised the canonical chain.
- Candidate alerts support the existing Pushover channel and optional Gmail SMTP
  delivery when both `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are configured.
  The code and workflow wiring exist at `5a132e1`; live credential presence and a
  successful real Gmail delivery remain separately unverified.
- The canonical repository has two separate simulation workflows:
  - **Run Simulation** (`.github/workflows/manual_test.yml`) is a one-day Investor
    Edge acceptance. It clones provenance-valid protected inputs into temporary
    directories, creates TEST-marked data, uses deterministic local evidence,
    emits an alert preview, and uploads only a one-day
    `simulation-dashboard-<run-id>-<attempt>` artifact.
  - **Run $10K portfolio simulator**
    (`.github/workflows/filing_simulation.yml`) performs isolated historical replay
    from $10,000 toward a $20,000 goal. Its only durable write is
    `simulation-state`, consisting of `simulation-result.json` plus append-only
    `simulation-runs.jsonl` history.
  Neither workflow receives live alert credentials or writes a protected
  production artifact. The simulation state is not production paper-portfolio
  state.
- Run Simulation acceptance `33283294140` succeeded and uploaded only
  `simulation-dashboard-33283294140-1` artifact `9723624975`. The $10K replay
  `33283104953` succeeded and uploaded only `simulation-state` artifact
  `9723569827`; its result is paper-only, used no network or alert delivery, and
  left production inputs unmodified.
- The one-time production controller `33283549659` succeeded. It verified, in
  order, Legislative `33283553866`, Executive `33283609603`, AI `33283690942`,
  and dashboard `33283725400` at commit `d5ef440`.
- GitHub Pages deployed successfully and returned HTTP 200 at
  `https://maglothinm.github.io/MyETF-Intelligence/` with PolitiTrack branding,
  both simulation actions, and current canonical data. The URL is expected to
  change after the repository rename.
- The seven public-repository simulator commits ending at `c16c37e` were audited
  but were not cherry-picked. Their workflow restored and then uploaded
  `ai-analysis-state`, so it violated simulation isolation. Run Simulation
  and the separately isolated $10K replay supersede that unsafe code path.
- Legislative v2, Executive, and AI are the only permitted scheduled writers for
  their respective protected state. Duplicate schedules and failed-run state
  uploads must remain disabled.
- Production state is restored only from provenance-validated Actions artifacts.
  Caches are not a state authority. Artifact selection maps rerun artifacts to the
  exact successful attempt and fails closed when attempt provenance or a producer
  high-water mark cannot be established.
- The former recovery overlay is retired: `apply.sh` exits fail-closed without
  modifying files, and `repo-files/` contains only `RETIRED.md`.

## Known blockers

Obsolete canonical workflow runs `33219808359` and `33221027676` remain stale and queued.
They must be cancelled or otherwise proven incapable of running before the
duplicate-writer retirement and cutover can be called complete. Their queued state
is not evidence of successful work. Exact-identity cancellation attempts with
both the ordinary and force-cancel Actions endpoints returned HTTP 409 because
GitHub reports the runs as queued while its cancellation service considers them
pre-queued. The retired workflow is absent from the default branch, but those two
pre-existing run records remain a stop condition. On August 31 the owner
authorized clearing both. Ordinary/force cancellation still returned HTTP 409;
supported exact deletion after hash-verified exports of their empty job/artifact
records returned HTTP 403. Signed-in UI cancellation also failed for both. Fresh
readback at 09:52 UTC still shows queued, attempt 1, zero jobs/artifacts and
workflow ID `344663675` in `deleted` state. No clearance is claimed. A concrete
GitHub Support draft is prepared locally and submission is authorized, but it
remains unsent: the signed-in portal offered no applicable Actions ticket route.
No ticket number exists and no unrelated category was submitted. GitHub must clear the
server-side records or confirm they cannot execute before the requested fresh
manual production run. Existing schedules were not changed.

GitHub settings still report the canonical repository as public and pre-rename,
and the legacy repository as public, unarchived, and Pages-enabled. The browser
settings runtime was unavailable, so privacy, same-ID rename, legacy Pages
unpublish, Actions setting disablement, and archive flag were not claimed.

## Cutover gates still open

The following settings-dependent items remain open:

1. Cancel stale queued legacy runs `33219808359` and `33221027676`, then verify no
   retired scheduler or duplicate writer can start.
2. Correct canonical visibility deliberately, then rename repository ID
   `1349678672` in place to `maglothinm/PolitiTrack`; update
   URLs/settings/integrations, and verify the redirect and default branch.
3. Disable legacy Actions and Pages at the repository-settings level and archive
   repository ID `1033519491`. Its README/workflow code freeze at `36447a2` is
   complete, but it is not a substitute for those settings.
4. Re-publish and inspect both Pages surfaces at the post-rename URL.
5. Re-check Gmail credential configuration and prove delivery only with a
   separately authorized live candidate-alert test. Until then, report Gmail as
   implemented but delivery-unverified.

When these gates change, update this file with the final commit, exact Actions run
and artifact IDs, deployment URL, and archive/settings results.
