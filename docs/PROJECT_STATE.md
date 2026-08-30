# PolitiTrack project state

Last updated: **2026-08-30 UTC**
Status: **UI release prepared in issue #4; merge/Pages evidence pending.
Reconciliation deployed; state-safety PR #3 and repository cutover remain open.**

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

Local active suite: 180 passed; final targeted suite: 9 passed including the
additive UI suites (61 model, 32 native Node notification and 12 DOM scenarios).
Axe found zero serious/critical fixture findings with contrast/layout unavailable.
Linux verify.sh, PR CI and new Pages evidence are pending. Chrome, iPhone Safari,
real audio, responsive screenshots and physical CHG90 are unverified. The owner
explicitly requested merge/deploy after disclosure; issue #4 remains open for
device acceptance. No collectors, AI, simulations or external alerts were
manually dispatched. See D-2026-08-30-019 and the active handoff.

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
