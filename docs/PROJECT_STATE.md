# PolitiTrack project state

Last updated: **2026-08-30 UTC**
Status: **state-safety PR #3 remains draft/unmerged and now conflicts with the
newly deployed UI on main. Obsolete queued writers remain a GitHub-service
blocker; no support response or containment. Newer protected state must be
revalidated against the reconciled release commit before promotion. Hourly
follow-up active; no PR #3 production acceptance or repository cutover.**

## Hourly release checkpoint — 2026-08-30 17:41 UTC

Canonical ID **1349678672** remains `maglothinm/MyETF-Intelligence`. Main advanced
to **92f5c449a6b69bf081d5ec6c70a5d63aa701e2ae**, the documentation successor of
deployed dashboard/contextual-help commit **1aa87398b53689873de350155d33afdb993fb036**.
The independent UI releases did not merge state-safety PR #3.

At release head **884a344bcb6e7fef650a52cdb0fb5f3e177319e4**, PR #3 is open/draft
and GitHub reports **mergeable=false**, **mergeable_state=dirty**. Its
[CI 33320353688](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33320353688)
passed attempt 1, job `99281111335`, with no artifacts, but does not validate
integration with newer main. Reconcile without dropping the deployed view-model,
dashboard assets, public-output sanitation, contextual help, shared tooltip/risk
UI, or their tests. Overlaps include `.gitignore`, `README_INVESTOR_EDGE.md`, the
three operational docs, `scripts/investor_edge.py`, `tests/test_investor_edge.py`,
and `tests/test_investor_edge_surfaces.py`. Do not resolve these wholesale by
choosing one side. Retain main decisions D-019/D-020 and this branch's D-015–D-018.

The unchanged support comment remains present with zero replies and no newer
discussion comments/replies; pagination was complete. Both obsolete run IDs are
still queued, attempt 1, null conclusion, zero jobs/artifacts, with their exact
historical SHA/path/workflow identity unchanged. No cancellation retry or new
support post was made.

All 121 runs and 151 global artifacts were inspected. Latest unexpired metadata:

| Pipeline | Artifact | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | `9734211271` | `33318579174` / 1 | `99276401831` |
| Executive | `9736054489` | `33325239324` / 1 | `99294089255` |
| AI | `9736064296` | `33325343519` / 1 | `99294369216` |

Executive advanced through its schedule, and AI through `workflow_run`, on main
**a5d67034044ca53fc861a51af6218e79f9899870**. Legislative remains at producer
`4a9135a`. No later producer records or active eligible writers were found.
Artifact timestamps map to the exact successful attempts/jobs. New reported ZIP
digests: Executive `86dfc3be0ef9d3e46e8663f6dc057657606177fe682b834c406cf3b7e2fb28f5`;
AI `b1e17abd43c54174a9c2cf2945a78460b475c7ef527aa41647f8f0c024674042`.
This heartbeat did not download ZIPs or independently repeat content continuity.
Main's publication record at `92f5c44` records its full restore/inventory/continuity
checks; refresh those checks before PR #3 promotion. In particular, the newer
producer commit is not an ancestor of old release head `884a344`; integrate main
before testing revised consumer ancestry. Do not select older artifacts to evade
this requirement. No exact migration allowlist entries were changed.

Isolated replay metadata remains artifact `9734790733`, run `33320677882`,
attempt 1, job `99281977011`. Its recorded two-row history is not a persistent
paper portfolio. This heartbeat ran neither simulation.

The UI's [main CI 33325629684](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629684)
and [Pages 33325629663](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629663)
succeeded, attempt 1. Pages build `99295130679`, deploy `99295188583`, sole
artifact `9736138918` (`github-pages`). Main records live content acceptance at
17:36 UTC; this heartbeat verified run/artifact metadata, not browser/device
acceptance or a fresh content download. It performed no deployment.

This documentation-only update uses the same repository's release worktree at
`.remediation/production-remediation-monitor`. The active main checkout and its
untracked `.codex/` were left untouched. Continue hourly support/status reads.
After containment, reconcile and retest PR #3 against current main, refresh state
authority/continuity and exact allowlisting, then perform the authorized gates.

## Earlier revision evidence (historical)

## Current revision and owner-held scope

The owner instructed: "Hold on those features. Continue the revision."
`AGENTS.md` is unchanged. Simulation Gmail, extra durable storage, the persistent
Git-backed paper agent, Git-backed AI recovery, and dependent dispatch Worker
are excluded from active source/workflows. Local drafts are preserved under
ignored `.remediation/held-feature-drafts/`; they are not deployed or committed.

Canonical repository ID `1349678672` remains public
`maglothinm/MyETF-Intelligence`; the earlier checked default `main` was
`4a9135a8c12af6eebfce01cf33772ffa13e41951`. Revision branch:
`codex/production-remediation`. Implementation commit: `020351a86861020d1a0f579b8ccdd7f218be3994`.
The owner explicitly approved public publication with "Yes push" after the earlier
safety-review rejection. Branch head `6ffb1639aff2db13890b855acecefb90e6ac87ec`
was pushed and [draft PR #3](https://github.com/maglothinm/MyETF-Intelligence/pull/3)
opened against unchanged main. Linux CI run `33313439413`, attempt 1, failed
because pytest's configured temporary-directory parent was absent in a fresh
checkout (61 passed, 183 setup errors). The follow-up moves the disposable test
base to ignored `.test-tmp-pytest` directly under the checkout. Correction commit
`4cb6d5677daa60fff507d86502e156b70200a8ff` passed
[Linux CI 33313544655](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33313544655),
attempt 1, job `99262749719`: 244 tests passed; full verify.sh passed, including
105 state/workflow checks, 58 Bash syntax checks, recovery tombstone/inventory,
credential-pattern scan and generated assets. The run uploaded no artifacts.
The documentation successor `a7925448524014896d7624eccb1d50d6434a42e1` also
passed Linux CI `33313630046`, attempt 1, with no artifacts. The current
checkpoint-only follow-up `06fae22b3a46049dce5b32f73072e1138c43970d` adds two
newly verified entries and passed
[Linux CI 33314178604](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33314178604),
attempt 1, job `99264428646`, with no artifacts. Support-record commit
`54ccae751a020597b8a4e1167c6528dbc0b590e5` passed
[Linux CI 33315075463](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33315075463),
attempt 1, job `99266876236`: all 244 tests and verify.sh passed, no artifacts.
The current follow-up records the approved schedule only; its CI is attached to
PR #3 and must pass independently before promotion.
The owner subsequently authorized contacting GitHub and completing this revision
into production. This supersedes the earlier lack of promotion authority, not
the held-feature scope or any safety gate (D-2026-08-30-017).
No merge, production dispatch, mail, deployment, rename, or archive is claimed.
Unrelated pre-existing `.codex/` remains preserved.

The active revision consolidates artifact-only restore/seal validation, preserves
all IDs/ledger prefixes/Edge history, corrects adjusted-price and minimum-sample
scoring, and keeps both simulations credential-free with their existing permitted
outputs. See `docs/STATE_SAFETY.md` for design and intentionally unresolved scope.

Previously hash-verified successor checkpoints, all attempt 1:

| Pipeline | Successful run | Job | Artifact |
|---|---:|---:|---:|
| Legislative | `33306989441` | `99245167496` | `9730784030` |
| Executive | `33297296482` | `99219056330` | `9727833986` |
| AI | `33307012616` | `99245230528` | `9730794047` |

All six original/successor ZIPs pass the revised validator, exact inventory hashes,
prior-ledger byte-prefix preservation, and seen-ID retention. Exact evidence is in
`docs/protected-state-migration.json`. These are comparison checkpoints, not fixed
restore targets; always query for newer producers and attempts.

Local verification: **244 active tests passed**, 49 Python files and 5 embedded
Python blocks parsed, 5 JSON and 11 YAML files parsed, three generated JavaScript
files syntax-checked, recovery manifest and credential-pattern scan passed.
An actual-input dashboard built successfully, and an isolated TEST scoring run
completed with zero network/model requests/emails and unchanged source hashes.
Bash/WSL is unavailable locally. **All 58 Bash checks and full verify.sh passed
on Linux CI 33313544655**; they are not represented as local Windows passes.

Existing schedules advanced independently during revision. Last fully verified
protected checkpoint on 2026-08-30, all successful attempt 1 on main `4a9135a`:

| Pipeline | Run | Producer job | Artifact |
|---|---:|---:|---:|
| Legislative | `33306989441` | `99245167496` | `9730784030` |
| Executive | `33312565343` | `99260139758` | `9732455687` |
| AI | `33312663088` | `99260390680` | `9732466504` |

On the owner's "Finish" follow-up, all three current artifacts were selected with
the actual repository-global helper, including exact successful attempts/jobs,
producer commit ancestry and producer high-water checks. Downloads matched GitHub
ZIP digests. Complete inventories and original/prior checkpoint ledger prefixes,
protected IDs and completed Edge outcomes passed. Current counts: Legislative
983 filings / 65 transactions / 19 purchases / 1 review / 26 runs; Executive
4,109 filings / 1,495 reviews / 19 runs; AI 12 analyses / 27 runs.

Entries `9732455687` and `9732466504` were added to the exact pre-manifest
allowlist; every existing entry remains unchanged. No state bytes or production
artifacts were rewritten. Actual read-only restores succeeded for all three
protected pipelines. Historical `simulation-state` artifact `9723569827` also
restored successfully: run `33283104953`, attempt 1, job `99181508496`, one history
record. These checks used GitHub reads only, not live AI/market data/notifications.
Local full suite passed again: 244 tests in 16.67s, plus static/generated-asset and
credential-pattern checks. Ignored reproduction/evidence: `.remediation/live-audit/`
and `.remediation/verify_live_state.py`.

Before eventual promotion, re-query for newer producers and refresh only newly
exported, hash-verified successors if necessary. Never fall back to older allowed
state or initialize a new baseline.

At **2026-08-30 15:39 UTC**, the hourly-follow-up setup session observed newer
Legislative and AI artifacts from the existing main schedules:

| Pipeline | Newest observed artifact | Run / attempt | Successful producer job |
|---|---:|---|---:|
| Legislative | `9734211271` | `33318579174` / 1 | `99276401831` |
| Executive | `9732455687` (unchanged) | `33312565343` / 1 | `99260139758` |
| AI | `9734221839` | `33318614858` / 1 | `99276494661` |

All were unexpired with canonical main `4a9135a` and expected workflow identities.
This was a **metadata check only** for the new artifacts: ZIP contents, inventories,
ledger continuity and exact allowlist eligibility have **not** been verified.
The earlier table is the last fully verified checkpoint, not the current restore
selection. Do not fall back to it; export/verify newer state and refresh exact
allowlist entries before promotion. The setup session wrote no production state.

No PR #3 code was deployed. Main publisher `33312700469` was the earlier Pages
evidence; the latest independent UI deployment is recorded above. Live adjusted-price
entitlement, sufficient samples, Gmail delivery, and Safari acceptance are not
proven by offline results. The existing Actions-link dashboard control remains.

Issue #1 stays open. The attempted detailed issue-comment update was rejected by
the host publication review as a separate public disclosure outside the explicit
branch-push approval. It was not posted or retried by another route. The public
review PR and committed handoff contain the revision status; a detailed issue
comment was not retried. The owner's subsequent explicit GitHub-contact request
was fulfilled through the existing official Actions support discussion below.

Obsolete runs `33219808359` and `33221027676` still report
queued at removed `legislative_trade_tracker.yml`, SHA
`b9cf0f3e3863de69d92ae01f35f1c154a082f56a`. This session reverified each exact
identity and retried both ordinary and force-cancel endpoints: **all four returned
HTTP 409**. Both runs still have zero jobs and zero artifacts. GitHub reports their
workflow ID `344663675` as `deleted`, which does not establish cancellation of
already queued runs. No production dispatch or cutover until contained; PR #3
remains draft/unmerged. Latest retries at **2026-08-30 13:33:44-45 UTC** returned
the same four HTTP 409 responses: "Cannot cancel a workflow run that has not been
queued yet." Sanitized request IDs and exact run identities were sent to GitHub.

At **13:37:17 UTC**, authenticated as `maglothinm`, the agent posted the
[escalation](https://github.com/community/community/discussions/205874#discussioncomment-18207352)
to the matching existing official Community Actions discussion. This is a public
support escalation, not a private ticket or verified staff resolution. See
[SUPPORT_ESCALATION.md](SUPPORT_ESCALATION.md) for receipt and submitted message.
The request asks GitHub staff to terminally cancel the two runs or confirm that
neither can execute/upload, while preserving all artifacts and unrelated runs.
No broad Actions shutdown, run deletion, or new account subscription was tried.

The initial hourly follow-up was rejected because recurring authority was not
explicit. The owner then answered **"Yes"** to hourly checks and automatic rollout
resumption once containment is proven. On **2026-08-30**, task follow-up
**polititrack-production-unblock** was created successfully and its saved
configuration verified: **ACTIVE**, every hour, attached to this current task.
It checks the existing report and exact stale runs without duplicate posts or
repeated unchanged cancel requests. It may resume only the existing approved
revision after every safety gate passes, and pauses after verified completion or
an owner stop request. Deferred features remain held. See D-2026-08-30-018.
The local task requires the computer and app to remain running. Browser Support
sign-in is optional for a private ticket, not a prerequisite for the submitted
public escalation.

An independent read-only release review found no new concrete code blocker.
Containment and a fresh checkpoint review must occur **before merge**, because
the merge can immediately trigger Pages. Drain older producer runs, refresh the
newest exact-attempt artifact inventories/allowlist, then merge a green review
head. Verify revised collectors and their automatic AI/Pages successors before
dispatching redundant jobs. Complete exact-attempt continuity, both isolated
simulations and live deployment acceptance before eligible rename/legacy gates.

## Earlier operational evidence (historical)

This file is a point-in-time operational snapshot, not a substitute for checking
live GitHub state. See `AGENTS.md` for the mandatory verification procedure.

## Repository identity

| Role | Repository | Repository ID | Recorded head | Status |
|---|---|---:|---|---|
| Canonical | `maglothinm/MyETF-Intelligence` | `1349678672` | Production acceptance `d5ef440` plus this cleanup/docs successor | **Public** standalone repository with Pages enabled; awaiting same-ID rename and intended privacy correction |
| Final canonical name | `maglothinm/PolitiTrack` | `1349678672` | Same history | Approved target name; do not create a new repository |
| Legacy | `maglothinm/MyETF` | `1033519491` | `36447a2` | Code-frozen public history; all six workflows removed, but Pages and archive settings remain open |

GitHub issue `#1`, **Consolidate repositories and cut over to PolitiTrack**, is the
active work record. The canonical repository's numeric ID is authoritative if an
old URL redirects after the rename.

## Durable state checkpoint

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

Legacy workflow runs `33219808359` and `33221027676` remain stale and queued.
They must be cancelled or otherwise proven incapable of running before the
duplicate-writer retirement and cutover can be called complete. Their queued state
is not evidence of successful work. Exact-identity cancellation attempts with
both the ordinary and force-cancel Actions endpoints returned HTTP 409 because
GitHub reports the runs as queued while its cancellation service considers them
pre-queued. The retired workflow is absent from the default branch, but those two
pre-existing run records remain a stop condition.

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
