# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Owner: next ChatGPT/Codex repository session
Work record: canonical issue `#1`, **Consolidate repositories and cut over to
PolitiTrack**

## Objective

Finish the controlled consolidation into repository ID `1349678672`, verify the
production-state lineage and isolated simulation, rename that same repository to
`maglothinm/PolitiTrack`, and freeze/archive public legacy `maglothinm/MyETF`
without rebaselining Legislative, Executive, or AI state.

## Current position

- Canonical pre-rename repository: `maglothinm/MyETF-Intelligence` (private,
  standalone), repository ID `1349678672`.
- Current canonical head to preserve: `5a132e1`, which already contains Investor
  Edge production integration #2.
- The reconciliation candidate is local/unverified until a new SHA is pushed to
  the canonical default branch. Repository rename, Pages cutover, and public
  archive have not been completed.
- Legacy public repository: `maglothinm/MyETF`, head `c16c37e`.
- The seven legacy simulator commits were audited and intentionally were not
  cherry-picked. Their workflow could overwrite `ai-analysis-state`.
- The candidate contains two isolated simulations:
  - `.github/workflows/manual_test.yml` (**Run Simulation**) is the one-day
    Investor Edge acceptance. It uses runner-temporary clones, TEST-marked input,
    deterministic analysis, and a one-day simulation dashboard artifact.
  - `.github/workflows/filing_simulation.yml` (**Run $10K portfolio simulator**)
    replays historical filings with $10,000 starting capital and a $20,000 goal.
    Its only durable output is `simulation-state`: `simulation-result.json` and
    append-only `simulation-runs.jsonl`.
  Neither simulation receives live alert credentials or writes protected
  production state.
- Production restores now treat provenance-validated Actions artifacts as the only
  authority. Caches do not qualify. Candidate artifacts must map to the exact
  successful rerun attempt that created them and pass the producer high-water
  check.
- The old overlay is retired. `apply.sh` fails closed without changing files and
  `repo-files/` contains only `RETIRED.md`.
- Gmail candidate-alert code and workflow inputs exist at `5a132e1`. Whether the
  live repository has working Gmail secrets and can deliver successfully remains
  unverified.
- Stale queued legacy runs `33219808359` and `33221027676` remain a cutover
  blocker. Do not report duplicate-writer retirement complete until they are
  cancelled or otherwise proven unable to execute.

## Protected pre-cutover checkpoint

| Pipeline | Successful run | Artifact ID | `state.json` SHA-256 | Validated counts |
|---|---:|---:|---|---|
| Legislative tracker v2 | `33277494482` | `9721960970` | `cc26314b48608288f8646f444e58438fc98667fafc77c342087581891e0b3c39` | 983 filings; 65 transactions; 19 purchases; 21 runs |
| Executive tracker | `33276747269` | `9721752302` | `264b0984155da06860e87315430dcd670361767163007198583db23a73897b56` | 4,109 filings; 1,495 review records; 15 runs |
| AI analyst | `33277540811` | `9721970474` | `7b26e89cb9032e3d47a7caf29d0df7f5180f825459a8e8728001d646f585639d` | 12 analyses; 20 runs |

Migration run `33179207530` is the successful import record. The business ledgers
and analyses match the earlier checkpoint; only successful run lineage and run
logs advanced. These IDs are comparison evidence, not fixed restore targets. Use
the newest provenance-valid successor from the canonical repository, mapped to
its exact successful attempt. If protected state cannot be restored or provenance
is ambiguous, stop. Do not use a cache, `initialize_state`, `bootstrap_alerts`, or
a blank state directory.

## Completed in the reconciliation audit

- Established repository ID `1349678672` as the single canonical identity and
  opened issue `#1` for the cutover.
- Compared the canonical and public histories from their common base and audited
  all seven public simulator commits.
- Identified the legacy simulator's production-state write as unsafe and selected
  canonical Run Simulation as the replacement.
- Captured the last known successful production run and artifact IDs for all three
  protected pipelines.
- Revalidated the protected checkpoint at runs `33277494482`, `33276747269`, and
  `33277540811`; business ledgers/analyses remained continuous while run lineage
  advanced.
- Detected the concurrently landed `5a132e1` Investor Edge work so the final
  reconciliation can be rebased on it rather than overwriting it.
- Defined separate acceptance contracts for the one-day Investor Edge simulation
  and the append-only $10K historical portfolio replay.
- Made provenance-valid artifacts—not caches—the production-state authority, with
  exact attempt mapping for reruns.
- Retired the old overlay with a fail-closed `apply.sh` and a lone
  `repo-files/RETIRED.md` tombstone.
- Installed the repository continuity contract in `AGENTS.md` and `docs/`.

## Next safe actions

1. Re-read `AGENTS.md`, verify live repository ID/name/head, and ensure the final
   reconciliation starts from `5a132e1` or its descendant.
2. Cancel stale queued legacy runs `33219808359` and `33221027676`; verify no
   retired workflow can start or write state.
3. Review the complete diff for duplicate schedules, old dashboard triggers,
   failed-run state uploads, stale brand URLs, and any legacy migration workflow
   that can still write protected artifacts.
4. Run the complete relevant unit/static/dashboard test set and record exact
   commands and results.
5. Commit/push to the canonical default branch, then verify the intended commit is
   live before dispatching workflows. Replace the `PENDING` final SHA below only
   after GitHub confirms it.
6. Run or observe the canonical Legislative v2, Executive, and AI workflows.
   Confirm successful conclusions and successor artifacts that preserve continuity
   with the checkpoint above.
7. Dispatch both simulations. Confirm Run Simulation produces only its one-day
   dashboard artifact. Confirm the $10K replay produces only `simulation-state`,
   appends exactly one history record, and preserves its predecessor prefix. Verify
   neither receives live alert credentials or updates protected state.
8. Publish and visually inspect the canonical dashboard and wallboard, including
   mobile behavior and canonical repository links.
9. Rename repository ID `1349678672` in place to `maglothinm/PolitiTrack`; update
   explicit URLs, variables, integrations, Pages, and environment remotes, then
   verify the stable ID and redirect.
10. Replace the legacy public README with a frozen notice, disable public Actions
   and Pages, archive the repository, and verify no scheduler remains active.
11. Update `PROJECT_STATE.md` and this handoff with final SHA, run URLs/IDs,
    successor artifact IDs and continuity comparison, deployment URL, repository
    settings, archive result, and any blocker. Add a decision entry only if a
    durable decision changes.

## Pending cutover evidence

| Evidence | Current value |
|---|---|
| Final pushed canonical SHA | `PENDING` |
| Run Simulation acceptance run/artifact | `PENDING` |
| $10K simulator run / `simulation-state` artifact | `PENDING` |
| Canonical Pages URL and live inspection | `PENDING` |
| Same-ID rename to `maglothinm/PolitiTrack` | `PENDING` |
| Legacy Actions/Pages disabled and repository archived | `PENDING` |

## Completion report required

Do not close issue `#1` or tell the user the cutover is complete until the report
contains all of the following:

- canonical repository ID, final name, branch, and commit SHA;
- files/capabilities delivered and any deliberately retained compatibility name;
- local test/static/dashboard results;
- production and simulation Actions run IDs/URLs and conclusions;
- newest Legislative, Executive, and AI artifact IDs plus continuity result;
- dashboard/Pages URL and live verification result;
- public legacy Actions/Pages/archive status;
- Gmail configured/delivery status stated with evidence, or explicitly marked
  unverified; and
- remaining blockers and the next safe action.

Queued work is not successful work. A commit is not a deployment. Configured code
is not proven delivery. Use exact status words.
