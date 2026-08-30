# PolitiTrack decision log

This append-only log records durable project decisions. Corrections should add a
new superseding entry rather than silently rewriting history.

## D-2026-08-29-001 — One canonical repository

**Decision:** GitHub repository ID `1349678672`, currently named
`maglothinm/MyETF-Intelligence` and to be renamed in place to
`maglothinm/PolitiTrack`, is the program's only canonical repository.

**Reason:** ChatGPT conversations, Codex sessions, and local workspaces do not form
one guaranteed transcript. A single repository provides a durable, independently
verifiable source for code, issues, decisions, handoffs, Actions, and state
lineage.

**Consequence:** `MyETF`, `MyETF-Intelligence`, and `PolitiTrack` are aliases for
one program, not separate development targets. The public `maglothinm/MyETF`
repository is legacy only.

## D-2026-08-29-002 — Preserve imported production baselines

**Decision:** Continue from the Legislative, Executive, and AI state imported by
successful migration run `33179207530`. Missing or invalid state is a recovery
incident, never implicit permission to initialize or bootstrap.

**Reason:** Seen IDs, reviews, analyses, paper positions, alerts, and Investor Edge
history prevent duplicate processing and preserve longitudinal results.

**Consequence:** `initialize_state=true` and `bootstrap_alerts=true` require a
separate, explicitly approved rebaseline procedure with verified snapshots and a
rollback plan. The consolidation itself does not authorize rebaselining.

## D-2026-08-29-003 — Selective reconciliation, not a history merge

**Decision:** Audit the seven simulator commits on the public legacy repository,
but do not cherry-pick or merge them into the canonical repository.

Audited public commits:

| Commit | Historical change |
|---|---|
| `a5e21a5` | Add Simulator context rules |
| `16c86dd` | Add exit-risk and 60-day news context enrichment |
| `bd78f86` | Complete context-enrichment implementation |
| `ed31004` | Finalize compact enricher |
| `2d342f2` | Run enrichment |
| `1e138a8` | Test enrichment logic |
| `c16c37e` | Validate enrichment on implementation changes |

**Reason:** The legacy workflow restored the live `ai-analysis-state`, mutated its
contents, and uploaded that protected production artifact again. That is not an
isolated simulation and could contaminate operational state. The repositories had
also diverged, so an indiscriminate merge could overwrite canonical work.

**Consequence:** `.github/workflows/manual_test.yml` (**Run Simulation**) in the
canonical repository supersedes the legacy simulator. Useful behavior must be
reimplemented under the isolation contract, never recovered by reviving the
legacy state-writing workflow.

## D-2026-08-29-004 — Preserve concurrently landed Investor Edge work

**Decision:** Treat canonical commit `5a132e1` (Investor Edge production
integration #2) as an immutable reconciliation base, not an incidental change.

**Reason:** It landed in the canonical repository while the split-repository audit
was running and includes production scoring, dashboard surfaces, simulation, and
candidate-alert work that is newer than the earlier reconciliation checkout.

**Consequence:** Any final tree must be based on the current canonical head and
retain its Investor Edge files, tests, workflow, and state compatibility.

## D-2026-08-29-005 — Rename in place

**Decision:** Rename repository ID `1349678672` from `MyETF-Intelligence` to
`PolitiTrack` after reconciliation and verification. Do not create a third
repository.

**Reason:** An in-place rename preserves history, issues, secrets, variables,
Actions, artifacts, permissions, and the repository's stable numeric identity.

**Consequence:** Update explicit repository URLs, dashboard deployment, remote
configuration, integrations, and environment entry points after the rename. Keep
old names only where required by history or stable compatibility keys.

## D-2026-08-29-006 — Freeze and archive public MyETF

**Decision:** After the canonical cutover is verified, replace the public
repository README with a legacy notice, disable its Actions and Pages, and archive
it as a rollback/history record.

**Reason:** Leaving the public fork runnable created the code and workflow split
that this cutover is correcting.

**Consequence:** No production work, workflow dispatch, deployment, or state
restore may occur in `maglothinm/MyETF` even before the archive setting is applied.

## D-2026-08-29-007 — Repository files are the continuity contract

**Decision:** Use `AGENTS.md` for operating rules, `docs/PROJECT_STATE.md` for
current operational truth, `docs/DECISIONS.md` for durable decisions, and
`docs/HANDOFF.md` for the active task and next action. Use issues for work and
commits/Actions/artifacts for evidence.

**Reason:** Conversation memory is useful context but is neither complete nor a
reliable deployment record.

**Consequence:** Every repository session reads these files at start and updates
the applicable records before ending. Completion reports include repository,
branch, SHA, tests, Actions, artifact lineage, deployment, and blockers.

## D-2026-08-29-008 — One writer per production state

**Decision:** Legislative v2, Executive, and AI each have one scheduled workflow
that may write their protected artifact, and state publication occurs only after a
successful validated producer step.

**Reason:** Duplicate schedules and uploads after failed runs create races and can
promote a partial or stale directory as the newest restore point.

**Consequence:** Tests, dashboard builders, simulations, migration helpers, failed
runs, and legacy workflows may not publish protected production artifacts.

## D-2026-08-29-009 — Simulation is read-only with respect to production

**Decision:** Run Simulation may clone current artifacts into run-specific
temporary storage, but may output only TEST-marked previews and short-lived
simulation artifacts. It sends no live notifications and deploys no production
dashboard.

**Reason:** Acceptance testing must exercise realistic input without advancing seen
IDs, analysis state, paper positions, alert delivery, or Investor Edge history.

**Consequence:** Any simulation workflow that writes a protected artifact fails
the acceptance contract regardless of whether the test itself passes.

## D-2026-08-29-010 — Capability is not delivery proof

**Decision:** Record Gmail candidate alerts as implemented at `5a132e1`, but do not
claim them operational until secret configuration and an actual accepted delivery
are verified.

**Reason:** Source references to `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` prove code
paths, not secret existence, authentication, inbox receipt, or retry behavior in
the live repository.

**Consequence:** Reports distinguish implemented, configured, dispatched,
accepted, and received states. Live notification testing requires separate
authorization and must not use Run Simulation credentials.

## D-2026-08-30-011 — Maintain two distinct isolated simulations

**Decision:** The canonical repository has two separately named simulation
workflows with different acceptance contracts:

- `.github/workflows/manual_test.yml` (**Run Simulation**) performs the one-day
  Investor Edge acceptance and may upload only the one-day
  `simulation-dashboard-<run-id>-<attempt>` artifact.
- `.github/workflows/filing_simulation.yml` (**Run $10K portfolio simulator**)
  performs an isolated historical replay with $10,000 starting capital and a
  $20,000 goal. Its only durable output is `simulation-state`, containing the
  latest `simulation-result.json` and append-only `simulation-runs.jsonl` history.

**Reason:** Investor Edge path acceptance and a persistent historical portfolio
replay answer different questions. Combining them would blur test artifacts with
simulator history or tempt a simulation to mutate the live AI paper portfolio.

**Consequence:** The one-day acceptance never advances `simulation-state`; the
$10K replay never writes a protected production artifact or its own acceptance
dashboard artifact. Both consume protected inputs read-only, receive no live alert
credentials, and remain subject to D-2026-08-29-009. In `simulation-state`, every
successful replay preserves the exact prior JSONL prefix and appends one result.

## D-2026-08-30-012 — Artifacts, not caches, are production-state authority

**Decision:** Legislative, Executive, and AI restores use only the newest
provenance-valid GitHub Actions artifact. A cache is never authoritative
production state and may not be used as a restore fallback.

**Reason:** Cache keys and recency do not prove which workflow, branch, commit,
job, or rerun attempt produced the files. GitHub reruns also reuse a run ID, so the
aggregate run conclusion can describe a later attempt than the artifact being
considered.

**Consequence:** Candidate selection verifies the canonical repository ID,
default branch, expected workflow path/name and authoritative job, successful
attempt conclusion, producer commit ancestry, and artifact creation within the
exact attempt window. It also enforces the workflow's producer high-water mark.
If an artifact cannot be uniquely mapped to the successful attempt that created
it—or a later successful attempt has no eligible successor state—the restore
fails closed instead of selecting an older artifact.

## D-2026-08-30-013 — Retire the recovery overlay permanently

**Decision:** `apply.sh` is a fail-closed tombstone and `repo-files/` contains only
`RETIRED.md`. The old recovery overlay must not be regenerated or executed.

**Reason:** Its payload predates the canonical workflow set and could reintroduce
old branding, obsolete code, or a duplicate Legislative state writer.

**Consequence:** Repository changes are made directly to the canonical checked-in
files. State recovery uses provenance-valid protected artifacts; neither the
overlay nor its retired payload is a recovery authority.

## D-2026-08-30-014 — Settings evidence is required for identity cutover

**Decision:** Repository ID `1349678672` remains canonical even while GitHub
reports its live name as `MyETF-Intelligence` and visibility as public. The target
is still an in-place rename to `PolitiTrack` with the intended privacy setting;
no replacement repository may be created to bypass unavailable settings access.

**Reason:** Source branding, README text, a redirect assumption, or a successful
Pages deployment cannot prove repository name, visibility, Actions policy, Pages
policy, or archive state. The authenticated settings runtime was unavailable
during the 2026-08-30 cutover, while the numeric repository identity and deployed
code remained independently verifiable.

**Consequence:** Operational records use the current live name and Pages URL until
GitHub confirms the rename. Public legacy `MyETF` is code-frozen at `36447a2`, but
removing workflow files is not a substitute for disabling Actions/Pages and
setting the archive flag. The cutover remains open until those settings and the
two stale queued runs are verified.

## D-2026-08-30-015 — Pause conflicting remediation proposals before promotion

**Decision:** Preserve the uncommitted `codex/production-remediation` worktree and
pause implementation pending explicit owner resolution of the newly supplied
contract versus the earlier approved remediation directive. Do not silently
amend `AGENTS.md`, merge, dispatch, or deploy the conflicting draft.

**Reason:** The draft adds same-repository fast-forward Git namespaces for an
isolated persistent paper agent, simulation results/receipts, and an AI delivery
recovery journal; a dedicated simulation notification job references Gmail
secrets. The restated contract forbids simulation alert credentials, restricts
simulation durable outputs, and makes provenance-valid artifacts the sole
production-state authority. Local tests cannot resolve that authorization or
design conflict.

**Consequence:** These are local proposals, not adopted operational designs.
Retain all existing production continuity constraints and protected checkpoints.
Ask whether to authorize explicit, narrowly documented exceptions or revise the
draft to remain within the unchanged contract. The persistent paper experiment
remains separate from historical replay and no $20,000 return is promised.

## D-2026-08-30-016 — Continue the unchanged-contract revision; hold added authorities

**Decision:** The owner's "Hold on those features. Continue the revision"
supersedes the pause in D-015 without authorizing contract exceptions. Keep
`AGENTS.md` unchanged. Remove simulation Gmail, extra durable-result state,
persistent Git-backed paper-agent execution, Git-backed AI recovery integration,
and the dependent Worker from active code/workflows. Preserve their local drafts
outside the commit under ignored `.remediation/held-feature-drafts/`.

**Consequence:** Finish artifact-only state integrity and Investor Edge corrections.
Both simulation workflows retain only their existing permitted outputs and receive
no real alert/provider credentials. Production alert durability, direct dashboard
dispatch, and persistent paper-agent operation remain explicitly unresolved.

Shared restore/seal helpers replace duplicated inline restore implementations.
Exact pre-manifest hash allowlisting bridges verified checkpoints without a
rebaseline. Completed IDs are never silently pruned; Edge archives are immutable,
pending horizons can mature, and identity upgrades retain prior profile aliases.

CI now runs the entire active `tests/` suite and mandatory Linux `verify.sh`.
Historical `backend/tests` imports a retired absent `api` package and is preserved
but outside active CI collection. Windows checks explicitly report unavailable
Bash. Shell/recovery text uses canonical LF via `.gitattributes`; protected
production checkpoint verification remains byte-exact with no normalization.

No new external state authority, paid/provider call, live notification, protected
writer, production dispatch, default-branch merge, rename, or legacy cutover is
authorized by this reduced-scope revision.
