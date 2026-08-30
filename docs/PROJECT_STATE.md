# PolitiTrack project state

Last updated: **2026-08-30 UTC**
Status: **local cutover candidate under verification; push, rename, Pages, and
legacy archive are not yet complete**

This file is a point-in-time operational snapshot, not a substitute for checking
live GitHub state. See `AGENTS.md` for the mandatory verification procedure.

## Repository identity

| Role | Repository | Repository ID | Recorded head | Status |
|---|---|---:|---|---|
| Canonical | `maglothinm/MyETF-Intelligence` | `1349678672` | `5a132e1` | Private standalone repository; awaiting same-ID in-place rename to `maglothinm/PolitiTrack` |
| Final canonical name | `maglothinm/PolitiTrack` | `1349678672` | Same history | Planned cutover name; do not create a new repository |
| Legacy | `maglothinm/MyETF` | `1033519491` | `c16c37e` | Public historical fork; must not receive production work and is to be frozen/archived after cutover |

GitHub issue `#1`, **Consolidate repositories and cut over to PolitiTrack**, is the
active work record. The canonical repository's numeric ID is authoritative if an
old URL redirects after the rename.

## Durable state checkpoint

The state was migrated into the canonical private repository by successful run
`33179207530`. The following successful production runs and unexpired artifacts
are the pre-cutover checkpoint. Always query GitHub for newer valid artifacts
before a run; do not hard-code these IDs as permanent restore targets.

| Pipeline | Successful run | Protected artifact | Artifact ID | `state.json` SHA-256 | Validated record counts |
|---|---:|---|---:|---|---|
| Legislative tracker v2 | `33277494482` | `legislative-tracker-state` | `9721960970` | `cc26314b48608288f8646f444e58438fc98667fafc77c342087581891e0b3c39` | 983 filings; 65 transactions; 19 purchases; 21 runs |
| Executive tracker | `33276747269` | `executive-tracker-state` | `9721752302` | `264b0984155da06860e87315430dcd670361767163007198583db23a73897b56` | 4,109 filings; 1,495 pending-review records; 15 runs |
| AI analyst / paper portfolio | `33277540811` | `ai-analysis-state` | `9721970474` | `7b26e89cb9032e3d47a7caf29d0df7f5180f825459a8e8728001d646f585639d` | 12 analyses; 20 runs |

The 2026-08-30 validation found that filing, transaction, purchase, review, and
analysis contents match the earlier checkpoint. Only successful run lineage and
its run logs advanced. No approved task in the repository consolidation
authorizes a rebaseline. State absence, ambiguous rerun-attempt provenance, a
failed restore, or a later successful producer with no valid successor artifact is
a stop condition.

Production-state authority is the newest provenance-valid artifact, not a cache.
Selection must verify repository, branch, workflow identity, producer job and
commit, and the exact successful attempt whose time window contains the artifact.
A rerun's aggregate run conclusion is insufficient because all attempts share the
same run ID.

## Current design and evidence

- Commit `5a132e1` contains the Investor Edge production integration that landed
  while repository reconciliation was in progress. It is part of the canonical
  history and must not be overwritten by an older merge candidate.
- Candidate alerts support the existing Pushover channel and optional Gmail SMTP
  delivery when both `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are configured.
  The code and workflow wiring exist at `5a132e1`; live credential presence and a
  successful real Gmail delivery remain separately unverified.
- The cutover candidate has two separate simulation workflows:
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

## Known blocker

Legacy workflow runs `33219808359` and `33221027676` remain stale and queued.
They must be cancelled or otherwise proven incapable of running before the
duplicate-writer retirement and cutover can be called complete. Their queued state
is not evidence of successful work.

## Cutover gates still open

The following items were not yet operationally verified when this snapshot was
written:

1. Cancel stale queued legacy runs `33219808359` and `33221027676`, then verify no
   retired scheduler or duplicate writer can start.
2. Commit and push the final reconciliation without replacing the `5a132e1`
   Investor Edge integration, and run the full local test/static-check set. Record
   the resulting canonical SHA; local edits are not a pushed implementation.
3. Run the canonical production workflows and confirm successful conclusions plus
   continuous successor artifacts; do not initialize state.
4. Dispatch both simulations. Confirm Run Simulation produces only its one-day
   acceptance dashboard, and the $10K replay produces only provenance-valid
   `simulation-state` with an intact append-only predecessor.
5. Publish and inspect the canonical dashboard, including mobile and wallboard
   surfaces, from canonical data.
6. Rename repository ID `1349678672` in place to `maglothinm/PolitiTrack`, update
   URLs/settings/integrations, and verify the redirect and default branch.
7. Freeze the public legacy repository, disable its Actions/Pages, replace its
   README with a legacy notice, and archive it.
8. Re-check Gmail credential configuration and prove delivery only with a
   separately authorized live candidate-alert test. Until then, report Gmail as
   implemented but delivery-unverified.

When these gates change, update this file with the final commit, exact Actions run
and artifact IDs, deployment URL, and archive/settings results.
