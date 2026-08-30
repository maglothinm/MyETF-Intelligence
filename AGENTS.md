# PolitiTrack repository contract

This file is the mandatory operating contract for every human, ChatGPT, Codex,
automation, and coding agent working on this program. Read it before inspecting or
changing code. More-specific instructions may add constraints, but they may not
relax the state-safety rules below.

## Canonical identity

- The one canonical repository is GitHub repository ID **1349678672**.
- During the 2026-08-29 cutover its pre-rename name is
  `maglothinm/MyETF-Intelligence`; its final name is
  `maglothinm/PolitiTrack`. The numeric repository ID, not the mutable name, is
  the identity check.
- `MyETF`, `MyETF-Intelligence`, and `PolitiTrack` are historical aliases for one
  program. They are not permission to create or maintain parallel implementations.
- `maglothinm/MyETF` is the legacy public repository. It is a historical/rollback
  record only. Do not implement, dispatch, schedule, deploy, or restore production
  state from it.
- Never create a third repository to complete a rename or migration. Rename the
  canonical repository in place so its history, issues, secrets, variables,
  artifacts, and repository ID remain attached.

If the checked-out repository cannot be proven to have ID `1349678672`, stop
before making changes and report the mismatch.

## Required session start

Before answering a repository-state question or changing code:

1. Read `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, and
   `docs/HANDOFF.md`.
2. Verify the repository identity, remote, default branch, current commit, and
   working-tree status. Preserve user changes and unrelated work.
3. Inspect the relevant GitHub issue, recent commits, Actions runs, and unexpired
   state artifacts. A chat transcript, local checkout, cache, or README alone is
   not operational truth. A cache is never production-state authority.
4. Compare the live state with `docs/PROJECT_STATE.md`. If they differ, treat the
   live GitHub state as evidence, investigate the difference, and update the
   documentation when the cause is known.
5. State which repository and branch are being used. Refuse implementation work
   in the legacy public repository.

## Production-state invariants

The following artifact names are protected continuity records:

| Pipeline | Protected artifact |
|---|---|
| Legislative tracker | `legislative-tracker-state` |
| Executive tracker | `executive-tracker-state` |
| AI analyst / paper portfolio / Investor Edge | `ai-analysis-state` |

These rules are non-negotiable:

- Provenance-validated GitHub Actions artifacts are the only production-state
  authority. Caches may accelerate dependencies, but they must never select,
  restore, replace, or advance Legislative, Executive, or AI state.
- Restore the newest provenance-valid, unexpired artifact before a stateful
  production run. `created_at` ordering alone is not sufficient.
- Validate every candidate against repository ID `1349678672`, the canonical
  default branch, the expected workflow file and display name, the expected
  authoritative producer job, a successful conclusion, and a producer commit
  that is an ancestor of the consuming commit.
- Map the artifact to the exact successful run **attempt** that created it. A
  rerun retains its run ID, so an aggregate run conclusion does not establish the
  provenance of an artifact from an earlier attempt. Check attempt boundaries,
  conclusion, and job result; reject the candidate if the mapping is ambiguous.
- Enforce the producer high-water mark. A later successful producer attempt with
  missing, invalid, or ineligible state is a continuity blocker; do not fall back
  silently to an older artifact.
- Missing, expired, malformed, incomplete, or ambiguous state is a blocker. Stop
  and recover it; do not silently create a new baseline.
- Never use `initialize_state=true`, `bootstrap_alerts=true`, a blank state
  directory, or a newly constructed `state.json` as a workaround for a failed
  restore.
- A deliberate rebaseline requires a dedicated GitHub issue, an exported and
  hash-verified snapshot of every affected artifact, an explicit rollback plan,
  and the owner's contemporaneous approval. A general request to fix or run the
  system is not rebaseline approval.
- Preserve seen filing IDs, seen trade IDs, pending review data, analysis history,
  paper positions, alert-delivery state, Investor Edge observations/profiles, and
  run history.
- Upload production state only after its authoritative producer job succeeds and
  the output is validated. Do not cache production state. A failed, skipped,
  cancelled, or superseded attempt must not become the newest state writer.
- Legislative, Executive, and AI state each have one scheduled writer. Do not
  introduce duplicate schedules, concurrency groups, or alternate workflows that
  write the same artifact.
- Do not copy production artifacts to another repository as a routine execution
  path. Migration artifacts are recovery evidence, not an alternate authority.

## Simulation isolation

There are two distinct simulation products. They are not interchangeable:

| Workflow | Purpose | Only permitted durable output |
|---|---|---|
| `.github/workflows/manual_test.yml` — **Run Simulation** | One-day Investor Edge acceptance using a TEST-marked synthetic filing and deterministic evidence | `simulation-dashboard-<run-id>-<attempt>`, retained for one day |
| `.github/workflows/filing_simulation.yml` — **Run $10K portfolio simulator** | Isolated historical filing replay with $10,000 starting capital and a $20,000 goal | `simulation-state`, containing `simulation-result.json` and append-only `simulation-runs.jsonl` history |

Both workflows may read provenance-valid clones of protected production artifacts.
Those clones remain read-only. The two simulations have separate purposes and
outputs: the one-day Investor Edge acceptance does not advance the portfolio
history, and the $10K replay does not publish an acceptance dashboard artifact.

Neither simulation may:

- write, upload, cache, or replace any protected production artifact;
- deploy its generated dashboard to production GitHub Pages;
- receive or send with real Pushover, Gmail, Healthchecks, brokerage, or other
  external-alert credentials;
- call a live AI or market-data service when the deterministic acceptance path is
  expected; or
- omit an unmistakable TEST/simulation marker from synthetic records and previews.

`simulation-state` is isolated simulator history, not production AI or paper-
portfolio state. Its JSONL predecessor must be preserved byte-for-byte and each
successful run may append exactly one result. It must never be used as a source
for a Legislative, Executive, or AI restore.

The seven simulator commits that ended at legacy commit `c16c37e` are historical
input only. They were audited and intentionally were not cherry-picked because
their workflow could write `ai-analysis-state`. Do not revive that implementation.

## Retired recovery overlay

`apply.sh` is deliberately fail-closed and must exit without changing files.
`repo-files/` contains only `RETIRED.md`. Do not reconstitute, execute, or copy an
older overlay payload: it predates the canonical workflow set and could recreate a
duplicate Legislative state writer. Recover state from provenance-valid artifacts
and change the checked-in canonical files directly.

## Change and verification rules

- Track material work in a GitHub issue. The consolidation/cutover record is issue
  `#1` in the canonical repository.
- Keep terminology and user-facing links on the PolitiTrack brand, while retaining
  old names only where required for historical explanation or compatibility.
- Do not change protected artifact names, state directories, stable record IDs, or
  migration tags as part of branding work.
- Treat secrets as configuration, not proof. A workflow reference to a secret does
  not prove that the secret exists or that a delivery succeeded.
- Tests passing locally do not prove a deployed workflow or restored state. Verify
  the relevant Actions run and artifact lineage separately.
- Never describe proposed, edited, committed, dispatched, deployed, or operational
  work as the same thing. Use the most precise completed state.

Before declaring repository work complete, verify as applicable:

1. the intended diff and commit on the canonical default branch;
2. relevant local tests, static checks, and dashboard generation;
3. successful canonical Actions runs and their exact run URLs/IDs;
4. the newest protected artifact IDs, their exact producing attempts, and, for a
   cutover, hashes/counts against the pre-change snapshot;
5. the live dashboard/deployment and its source repository;
6. repository settings, schedules, integrations, and legacy-repository status; and
7. absence of production-state writes or live alert credentials in either
   simulation.

## Required session end

Before ending any code or operations session:

1. Update `docs/PROJECT_STATE.md` when operational truth changed.
2. Add an entry to `docs/DECISIONS.md` when a durable design, ownership, naming,
   migration, state, or workflow decision changed.
3. Replace the active entry in `docs/HANDOFF.md` with the exact current task,
   completed work, evidence, blockers, and next safe action.
4. Commit documentation with the implementation it describes when practical.
5. Report to the user:
   - repository ID/name, branch, and commit SHA;
   - changed files or delivered capability;
   - tests/checks and their results;
   - Actions run IDs/URLs and conclusions;
   - protected artifact IDs, producing attempts, and continuity result;
   - dashboard/deployment result;
   - remaining blockers, credentials, or unverified claims; and
   - the next safe action.

Uncommitted work, queued/running workflows, unverified credentials, and pending
settings changes must be labeled that way. Never report them as complete.
