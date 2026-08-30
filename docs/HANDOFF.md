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

- Canonical pre-rename repository: `maglothinm/MyETF-Intelligence`, repository ID
  `1349678672`. GitHub currently reports it **public**, not private.
- Reconciliation commit `1af4696` and isolated-copy fix `fe6d180` are deployed.
  Production acceptance commit `d5ef440` succeeded; this handoff is committed in
  a cleanup successor that removes the one-time controller.
- Legacy public repository `maglothinm/MyETF` is code-frozen at `36447a2`: its
  README is a legacy notice and all six workflow files are absent from `main`.
  GitHub still reports it unarchived and Pages-enabled.
- The seven legacy simulator commits were audited and intentionally were not
  cherry-picked. Their workflow could overwrite `ai-analysis-state`.
- The canonical repository contains two isolated simulations:
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
- Gmail candidate-alert code and workflow inputs exist. Whether the
  live repository has working Gmail secrets and can deliver successfully remains
  unverified.
- Stale queued legacy runs `33219808359` and `33221027676` remain a cutover
  blocker. Do not report duplicate-writer retirement complete until they are
  cancelled or otherwise proven unable to execute. Ordinary and force-cancel API
  attempts both returned HTTP 409 because GitHub's API reports `queued` while its
  cancellation service reports them not yet queued.
- The authenticated settings runtime was unavailable. Same-ID rename, canonical
  privacy, legacy Actions/Pages settings, and legacy archive are still open.

## Protected post-reconciliation checkpoint

| Pipeline | Successful run | Artifact ID | `state.json` SHA-256 | Validated counts |
|---|---:|---:|---|---|
| Legislative tracker v2 | `33283553866` | `9723708154` | `045a3f8c5f5a9f096ef12290f7db84228e1a5f127cff56fb20960e851c25cf58` | 983 filings; 65 transactions; 19 purchases; 1 review; 24 runs |
| Executive tracker | `33283609603` | `9723732691` | `7a70efafe057f2e9883bcb69d2ea312804d3431b7dabeff89c558a3cd6271d75` | 4,109 filings; 1,495 review records; 17 runs |
| AI analyst | `33283690942` | `9723743439` | `65cfa452dcb78dd14843155218b65178fb6fea7030cfbee95ac655bd22e2df19` | 12 analyses; 23 runs |

Migration run `33179207530` is the successful import record. All filing,
transaction, purchase, review, and analysis ledgers above are byte-identical to
the pre-change checkpoint; only successful run lineage and state timestamps
advanced. These IDs are comparison evidence, not fixed restore targets. Use
the newest provenance-valid successor from the canonical repository, mapped to
its exact successful attempt. If protected state cannot be restored or provenance
is ambiguous, stop. Do not use a cache, `initialize_state`, `bootstrap_alerts`, or
a blank state directory.

## Completed and verified

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
- Deployed the reconciliation without replacing `5a132e1`; local verification is
  115 tests, 8 temporary-cutover workflow YAML files, 54 Bash blocks, Python
  compilation, recovery verification, and all four manifest checks.
- Verified Investor Edge tests in runs `33283104938`, `33283294128`, and
  `33283549744`.
- Verified Run Simulation `33283294140`; it uploaded only
  `simulation-dashboard-33283294140-1` artifact `9723624975`.
- Verified the $10K simulator `33283104953`; it uploaded only `simulation-state`
  artifact `9723569827`, used $10,000 toward a $20,000 goal, sent no alerts, made
  no network calls, and did not mutate production input.
- Verified the canonical production chain through controller `33283549659`:
  Legislative `33283553866`, Executive `33283609603`, AI `33283690942`, and
  dashboard `33283725400` all succeeded at `d5ef440`.
- Verified the current Pages deployment returns HTTP 200 at
  `https://maglothinm.github.io/MyETF-Intelligence/` with PolitiTrack branding and
  both simulation controls.
- Code-froze the legacy repository at `36447a2` without deleting history.

## Next safe actions

1. Re-read `AGENTS.md` and verify live repository IDs/names/heads and settings.
2. Use authenticated GitHub settings access to cancel stale queued runs
   `33219808359` and `33221027676`; verify no
   retired workflow can start or write state.
3. Correct canonical visibility deliberately and rename repository ID
   `1349678672` in place to `maglothinm/PolitiTrack`; update
   explicit URLs, variables, integrations, Pages, and environment remotes, then
   verify the stable ID and redirect.
4. Disable public legacy Actions and Pages in settings, archive repository ID
   `1033519491`, and verify no scheduler remains active.
5. Rebuild/inspect Pages at the post-rename URL and update this handoff with the
   final names, settings, redirect, and archive evidence.

## Pending cutover evidence

| Evidence | Current value |
|---|---|
| Reconciliation / production acceptance | `1af4696` / `d5ef440`; verified |
| Run Simulation acceptance run/artifact | `33283294140` / `9723624975`; success |
| $10K simulator run / `simulation-state` artifact | `33283104953` / `9723569827`; success |
| Canonical production chain | `33283553866` → `33283609603` → `33283690942` → `33283725400`; success |
| Canonical Pages URL and live inspection | `https://maglothinm.github.io/MyETF-Intelligence/`; HTTP 200, current pre-rename URL |
| Legacy code freeze | `36447a2`; README replaced and all workflow files removed |
| Same-ID rename / canonical privacy | `BLOCKED — authenticated settings runtime unavailable` |
| Legacy Actions/Pages settings and archive | `BLOCKED — authenticated settings runtime unavailable` |

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
