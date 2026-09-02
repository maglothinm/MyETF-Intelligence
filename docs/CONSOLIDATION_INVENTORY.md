# PolitiTrack consolidation inventory

Captured: **2026-09-02**  
Canonical repository: **`maglothinm/MyETF-Intelligence`**, ID **`1349678672`**  
Canonical default branch: **`main`**  
Phase 1 starting main: **`d603e9b40ffb78c51f635589bc886875f411299b`**

This inventory records the Phase 1 rescue and the inputs authorized for the
Phase 2 Runtime v2 integration candidate. It does not authorize deployment,
cutover, schedule changes, protected-state writes, or merging another pull
request.

## Phase 2 final safety disposition

The integration at `3bdf187dce472fab0843b9ca0524d0bdbcfbb217` was preserved as
the immutable review base. Final work moved to the new branch
`codex/runtime-v2-handoff-final-20260902`; the earlier
`codex/runtime-v2-integration` branch was not rewritten.

- **KEEP:** the integrated Runtime v2 implementation, frozen provenance receipts,
  verified external rescue bundle, and ignored local migration inputs.
- **FIXED:** stale `verify.sh` manifest digest; missing additive database CHECK
  constraint; omitted CI shell continuation; mutating bootstrap validation path;
  and incomplete Terraform shadow-secret exclusion.
- **UNCHANGED:** all Runtime v1 producer workflows and protected artifact names;
  PR #3 and PR #33 remain independent; no local artifact became source authority.
- **NOT AUTHORIZED:** cloud apply, schedule activation, production mode, external
  notification, Runtime v1 retirement, protected-state publication, rebaseline,
  force-push, or merge.

## Rescue record

The external rescue root is:

`C:\Users\maglo\OneDrive\Documents\ChatGPT\PolitiTrack-Rescue-20260902-075657`

It is outside the repository and every registered worktree. It contains a
repository topology report, one report for each worktree, exclusion manifests,
and a verified all-refs Git bundle:

`bundles/polititrack-all-refs-20260902-075657.bundle`

The bundle contains 53 refs, records complete history, verifies successfully,
and has SHA-256
`c4a8002b877675f69c56644c64828e6a38945d2caca311501ae5296f32e8a91e`.

| Rescue measure | Result |
|---|---:|
| Registered worktrees inspected | 4 |
| Dirty worktrees | 0 |
| Binary-capable patch files required/created | 0 |
| Relevant untracked files rescued | 0 |
| Rescue branches required/created | 0 |
| Stashes preserved | 0 |
| Unresolved local-only dirty work | None |

The inspected worktrees were the Runtime v2 checkout, PR #3 production
remediation checkout, detached current-main secret-transfer cleanup checkout,
and PR #33 score-receipts checkout. All were clean and conflict-free.

Ignored material was examined by path and category. Reconstructable dependency,
provider, and test caches were excluded. Downloaded protected-state archives,
their extracted state, and production-remediation gate artifacts were excluded
because they are protected local evidence, not source. The actual Runtime v2
environment mapping and secret mapping remain in place as **SECRET/LOCAL**; only
their paths, sizes, and hashes are recorded in the external manifest, never
their contents.

## Classification definitions

- **MAIN** — safely represented on current canonical main.
- **KEEP** — unique work that must survive, but may remain independent of this
  Phase 2 branch.
- **ADAPT** — useful behavior whose implementation or authority boundary must
  change for Runtime v2.
- **SUPERSEDED** — replaced by newer main or Runtime v2 behavior; retained only
  as history/evidence.
- **REVIEW** — insufficient evidence for a safe implementation decision.
- **LOCAL-ONLY** — useful work found only locally and rescued.
- **SECRET/LOCAL** — material that must remain outside Git.

## Branch and feature inventory

### MAIN

The following remote branch heads are ancestors of `origin/main` and therefore
already represented on canonical main:

- `codex/acknowledgement-brief-consistency`
- `codex/brief-cache-compatibility`
- `codex/contextual-help`
- `codex/dashboard-redesign`
- `codex/dashboard-review-ux`
- `codex/filing-vault`
- `codex/fix-freshness-redaction`
- `codex/freshness-clock-audit`
- `codex/investor-edge-bootstrap`
- `codex/investor-edge-integration`
- `codex/manual-review-acknowledgement`
- `codex/neutral-zero-attention`
- `codex/operations-history-order`
- `codex/persistent-shell-layout`
- `codex/polititrack-icon-assets`
- `codex/polititrack-rebrand`
- `codex/record-brief-consistency-release`
- `codex/record-freshness-release`
- `codex/record-manual-review-release`
- `codex/record-neutral-zero-release`
- `codex/scheduler-freshness`
- `codex/scheduler-release-receipt`
- `codex/senate-efd-resilience`

Their deployed UI, Filing Vault catalog, Investor Edge bootstrap, scheduler
freshness, source resilience, branding, and release evidence remain preserved by
the Phase 2 base.

### KEEP

| Source | Commit/files | Capability and reason | Runtime v2 interaction / later work |
|---|---|---|---|
| `codex/runtime-v2-cutover` | `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6`; 29 changed files from its merge base | Cloud Run jobs/service, Cloud Scheduler definitions, PostgreSQL immutable generations and advisory locks, private GCS storage, migration/bootstrap tooling, dashboard runtime, Filing Vault GCS backend, tests and runbook | Integrate onto current main, add a fail-closed shadow boundary, broaden tests, and keep schedules paused. |
| PR #33 / `codex/score-receipts-data-quality` | `399cdd96f22c6edf458ec7d0cb86c73f952f8530`; dashboard JS/CSS and DOM tests | Read-only score receipts and data-quality drilldown are useful independent product work | Keep independent. Rebase after Runtime v2 Phase 2; do not merge or solve its UI work here. |
| PR #35 / `codex/chatgpt-codex-phase-1-2` | `0ef5d6b8f471bc24a911222dc73eb12a29dc3a6d`; issue template and `docs/CHATGPT_CODEX_WORKFLOW.md` | Useful repository collaboration documentation created after the rescue fetch | Keep independent from Runtime v2; no Phase 2 dependency. |

### ADAPT

The following PR #3 capabilities are valuable but must be separated from its
GitHub-artifact orchestration before use with Runtime v2:

| PR #3 source | Files | Capability retained | Required adaptation |
|---|---|---|---|
| Investor Edge scoring/history | `scripts/investor_edge.py`, `config/investor_edge.yml`, `tests/test_investor_edge_remediation.py`, related core/surface tests | Split/dividend-adjusted total-return provenance, matched benchmark sessions, effective sample weighting, pending-horizon visibility, durable/bounded history cursor behavior, score-cap preservation, and negative-modifier behavior | Port only behavior not already on main, with focused equivalence tests against the current Investor Edge implementation. State must persist through Runtime v2 generations rather than GitHub artifact restore/seal. This is classification-only in Phase 2 unless a Runtime v2 dependency is found. |
| Simulation isolation | `scripts/run_filing_simulation.py`, `scripts/run_investor_edge_simulation.py`, `tests/test_filing_simulation.py`, workflow contract tests | Read-only production inputs, append-only isolated simulator history, no live provider/alert credentials, and no protected production writes | Preserve as generic invariants. Do not import PR #3 workflow rewrites wholesale; Runtime v2 shadow tests must independently prove no notification or Runtime v1 publication leakage. |
| State validation concepts | `scripts/protected_state.py`, `tests/test_protected_state.py`, `scripts/verify_repository.py` | Schema/inventory validation, archive traversal/tamper rejection, exact-attempt provenance, high-water checks, continuity assertions, and structural repository guards | Reuse validation ideas where they strengthen Runtime v2 migration and generation checks. Do not make GitHub artifacts Runtime v2's ongoing authority. |
| Alert safety | `scripts/ai_filing_analyst.py`, workflow tests, simulation runners | Delivery deduplication and explicit no-production-alert boundaries | Map to the central Runtime v2 operating mode so shadow suppression is enforced at the runner boundary and is regression-tested. |

### SUPERSEDED

| Source | Reason |
|---|---|
| PR #3 GitHub-specific restore/seal/upload orchestration in production workflow rewrites | Runtime v2 replaces ongoing GitHub protected-artifact coordination with PostgreSQL immutable accepted heads and GCS evidence. Existing main workflows remain unchanged during Phase 2; no PR #3 wholesale merge occurs. |
| PR #3 migration allowlist as an ongoing Runtime v2 authority | Runtime v2 migration uses frozen exact receipts bound to repository, workflow, run attempt, producer job, commit, archive digest, imported digest and inventory. Arbitrary/local fallback remains forbidden. |
| `origin/codex/investor-edge-current-architecture` | Three old unique commits would restore the retired overlay, delete current governance/UI/Vault/scheduler assets, and recreate obsolete workflows. Current main and the accepted Investor Edge implementation supersede it. Historical evidence only. |
| Stale local implementation/release branches not equal to their remote head | `codex/fix-freshness-redaction`, `codex/manual-review-acknowledgement`, and `codex/record-freshness-release` contain older local documentation or implementation shapes. Current main contains the accepted remote implementations and later release records. The local commits remain recoverable in the all-refs bundle but must not be reintegrated. |
| Other local branches whose patch is already represented on main | Local acknowledgement, cache-compatibility, neutral-zero, and release-record branches are patch-equivalent to accepted main changes. Historical evidence only. |

### REVIEW

No dirty or untracked source remains unclassified. PR #3 documentation-only
history, support-escalation notes, and broad workflow rewrites remain review-only
for any later selective remediation because they mix historical evidence with
GitHub-specific authority changes. They are not Runtime v2 Phase 2 dependencies.

### LOCAL-ONLY

No useful work existed only as dirty/untracked local content. Local-only commits
on stale branches were captured by the verified all-refs bundle and classified
as superseded historical evidence above; no rescue commit was necessary.

### SECRET/LOCAL

- `.remediation/runtime-v2-environment.json` — actual local deployment mapping;
  excluded from Git and the rescue copy.
- `.remediation/runtime-v2-secrets.json` — secret-name mapping/local sensitive
  configuration; excluded from Git and the rescue copy.
- `.remediation/runtime-v2-imports/` — frozen/downloaded protected artifacts,
  receipts, and extracted state; retained locally but excluded from Git/rescue.
- `.remediation/production-remediation/.remediation/gate-artifacts/` — downloaded
  protected verification artifacts; retained locally but excluded.

## PR #3 selective analysis appendix

PR #3 is open at commit
`ccfac9ea3032bd06acfa95f9ec79d1ccfaba09ac`, trails current main by two
net-zero secret-transfer history commits, and has 21 branch-only commits. It is
not merged wholesale.

- **KEEP/ADAPT:** Investor Edge adjusted-total-return provenance, effective
  samples, pending-horizon handling, score-cap correctness, bounded history and
  cursor behavior; simulation isolation; no-production-alert boundaries; generic
  state validation; and useful repository verification tooling.
- **SUPERSEDED:** GitHub Actions protected-artifact selection, restore, sealing,
  migration allowlist, and protected upload orchestration as Runtime v2's future
  operational state authority.
- **REVIEW:** broad changes to all production workflows, historical escalation
  documentation, and any current-main overlap not covered by a narrowly scoped
  Runtime v2 dependency.

Existing Runtime v1 workflow behavior is left untouched in this phase.

## PR #33 independence and probable conflicts

PR #33 remains open and independent at
`399cdd96f22c6edf458ec7d0cb86c73f952f8530`. Its implementation files
(`scripts/dashboard_assets/app.js`, `common.js`, `styles.css`, and
`tests/dashboard_dom.test.cjs`) do not overlap the Runtime v2 cutover branch's
runtime implementation. Both branches edit `docs/PROJECT_STATE.md`,
`docs/DECISIONS.md`, and `docs/HANDOFF.md`, so a later rebase is likely to require
manual documentation conflict resolution.

Recommended future order: complete and land the Runtime v2 integration first,
then rebase PR #33 onto the resulting main, preserve its UI/test changes, and
rewrite its active project-state/handoff sections to current truth. Do not merge
PR #33 into this Phase 2 candidate.
