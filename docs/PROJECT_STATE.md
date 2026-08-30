# PolitiTrack project state

Last updated: **2026-08-30 UTC**
Status: **contract-compatible revision published in draft PR #3; Linux CI found
a fresh-checkout pytest setup error, corrected in the pending follow-up.
Production acceptance remains pending. No merge or cutover.**

## Current revision and owner-held scope

The owner instructed: "Hold on those features. Continue the revision."
`AGENTS.md` is unchanged. Simulation Gmail, extra durable storage, the persistent
Git-backed paper agent, Git-backed AI recovery, and dependent dispatch Worker
are excluded from active source/workflows. Local drafts are preserved under
ignored `.remediation/held-feature-drafts/`; they are not deployed or committed.

Canonical repository ID `1349678672` remains public
`maglothinm/MyETF-Intelligence`; rechecked default `main` is
`4a9135a8c12af6eebfce01cf33772ffa13e41951`. Revision branch:
`codex/production-remediation`. Implementation commit: `020351a86861020d1a0f579b8ccdd7f218be3994`.
The owner explicitly approved public publication with "Yes push" after the earlier
safety-review rejection. Branch head `6ffb1639aff2db13890b855acecefb90e6ac87ec`
was pushed and [draft PR #3](https://github.com/maglothinm/MyETF-Intelligence/pull/3)
opened against unchanged main. Linux CI run `33313439413`, attempt 1, failed
because pytest's configured temporary-directory parent was absent in a fresh
checkout (61 passed, 183 setup errors). The follow-up moves the disposable test
base to ignored `.test-tmp-pytest` directly under the checkout; CI must verify it.
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
Bash/WSL is unavailable locally: **58 Bash syntax checks and verify.sh execution
remain a Linux CI gate**, not a local pass.

Existing schedules advanced independently during revision. Current unexpired
protected artifacts observed on 2026-08-30, all successful attempt 1 on main `4a9135a`:

| Pipeline | Run | Producer job | Artifact |
|---|---:|---:|---:|
| Legislative | `33306989441` | `99245167496` | `9730784030` |
| Executive | `33312565343` | `99260139758` | `9732455687` |
| AI | `33312663088` | `99260390680` | `9732466504` |

The two newer Executive/AI artifacts have verified run/attempt/job metadata, but
were not exported or byte-continuity-checked in this publication session. Before
promotion, export and validate them against the prior checkpoints and refresh the
exact pre-manifest allowlist; do not fall back to an older allowed artifact.

No revised code was deployed. Existing pre-rename Pages and successful main
publisher run `33312700469` remain the deployment evidence. Live adjusted-price
entitlement, sufficient samples, Gmail delivery, and Safari acceptance are not
proven by offline results. The existing Actions-link dashboard control remains.

Issue #1 stays open. Obsolete runs `33219808359` and `33221027676` still report
queued at removed `legislative_trade_tracker.yml`, SHA
`b9cf0f3e3863de69d92ae01f35f1c154a082f56a`. Prior ordinary/force-cancel attempts
returned HTTP 409. No production dispatch or cutover until contained.

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
