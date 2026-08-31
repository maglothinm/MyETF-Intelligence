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

## D-2026-08-30-019 — Release the dashboard as a read-only presentation layer

**Decision:** Issue #4 delivers the commercial dashboard on a dedicated branch
from canonical `main`, independently of held state-safety PR #3. The owner
explicitly requested merge/deployment after the outstanding device acceptance and
cutover limitations were disclosed. Decisions 015–018 are reserved by that held
revision and are not incorporated or superseded here.

**Reason:** The dashboard can derive a compact public view from existing records
without changing collectors, scores, classifications, state schemas, portfolio
accounting, external alerts, workflow configuration, or simulation contracts.
The existing Pages publisher restores protected artifacts read-only and uploads
only `github-pages`; this release does not dispatch production writers.

**Consequence:** Only High Priority/Watchlist records enter the actionable board.
Catalog coverage, access-required inventory, parser exceptions, and branch health
remain distinct. Unknown values stay unavailable. The $10K result remains a
single-run historical replay; append-only replay history is not a persistent
portfolio. Browser notifications, acknowledgements and sound are local to a
device, establish a silent first baseline, and never alter external alerts.
Generated public outputs exclude sensitive delivery fields and heartbeat URLs.

The two stale queued runs, repository settings cutover, PR #3, and unverified
Gmail delivery remain separate open work. Automated DOM/accessibility fixtures
are not proof of Chrome, iPhone Safari, real audio, or physical CHG90 behavior;
issue #4 remains open until the remaining device acceptance is recorded.

## D-2026-08-30-020 — Contextual help extends one shared presentation layer

**Decision:** Issue #6 reuses `PT.setupDialogsAndTooltips()`, `data-tooltip` and
the single `#tooltip` on root, Wallboard and standalone Investor Edge. A frozen
`PT.HELP` object owns repeated product definitions; optional title/body/note
content is rendered with DOM APIs and `textContent`, never interpreted HTML.

**Reason:** First-time users need to distinguish historical evidence, isolated
TEST acceptance and single-run $10K replay without losing persistent warnings or
accidentally following workflow links while reading an explanation on touch.

**Consequence:** Workflow links have separate accessible 44px help buttons and
remain one-tap actions. Explicitly marked explanatory navigation uses first-touch
preview/second-touch navigation with a visible instruction. Other navigation and
desktop activation remain immediate. Pointer hover waits 300ms; keyboard focus
and explicit help are immediate. The existing bubble gains a navy surface, caret,
viewport-aware placement and native manual-popover enhancement where available.
It remains a supplemental tooltip, with no focus trap; keyboard scrolling from
the trigger can read overflow copy in short/zoomed viewports.

All retained scores, confidence calculations, identity handling, classifications,
prices, simulation isolation, paper positions, alerts, workflows and production
state remain unchanged. Visible PAPER RESEARCH, TEST/SIMULATED, single-run replay,
missing-history and browser-local limitations stay on-screen. Local DOM tests
and geometry stubs do not establish rendered browser or physical-device acceptance.

## D-2026-08-30-021 — Publish approved contextual help through existing Pages

**Decision:** Following the owner's explicit “I want it published” instruction,
release issue #6 through PR #7 and the existing canonical read-only Pages
publisher, after successful PR CI and a fresh artifact-continuity audit. No
additional confirmation or alternative hosting implementation is required.

**Reason:** The tested presentation change can ship without altering production
writers. The owner requested publication after the browser/device and Windows
verifier limits were disclosed; PR/main Linux CI subsequently passed the complete
verifier. Actual browser/device acceptance remains unverified.

**Consequence:** Merge `1aa87398b53689873de350155d33afdb993fb036` is published by
successful run `33325629663`; all 21 live files match artifact `9736138918`.
Scheduled Executive/AI successors were validated before release and remained
unchanged through publication. Keep issue #6 open for device acceptance. Do not
conflate publication with the separate cutover, PR #3, obsolete queues,
repository settings or Gmail delivery gates.

## D-2026-08-31-022 — Require complete discovery before Legislative processing

**Decision:** Use a dedicated truthful Senate client with strict agreement,
CSRF, search and report validation. Bound fresh-session recovery and keep masked
form tokens distinct from cookie tokens. Both required catalogs must validate
before filing processing, alerts, baselines or authoritative state changes.

**Reason:** An unavailable source must produce an explicit degraded failure,
not a partial-source success or an empty filing set.

**Consequence:** Preserve existing IDs, deduplication, artifacts, restore
authority, schedules and simulations. Produce safe classified diagnostics and
one terminal heartbeat after retries; require complete-source validation before
protected upload. Rollback means a reviewed code revert that continues from the
newest valid state. It never means replacing current state with an older copy.
Manual production verification remains subject to every existing writer-safety
gate. No proxy or unofficial data source is authorized by this decision.


## D-2026-08-31-023 — Share review classification and existing record navigation

**Decision:** Project every retained review through the existing Python category
classifier for both the Overview count and public JSON/CSV inventory. Publish
exact-match filing availability, retained metadata and synthetic ancestry as
additive presentation fields; never mutate the source ledgers. Use the existing
hash router for category and record selection and the existing tables for detail.
Source options carry their retained source/branch dimension. Workspace explanations
continue through `PT.HELP` and the single existing tooltip.

**Reason:** A count that opens an unfiltered, differently classified inventory
makes the underlying parser exception difficult to find. A shared projection
keeps the count and list consistent without a second browser classifier.

**Consequence:** Opening the card clears stale table filters, selects manual
exceptions, and brings the result into view. Synthetic reviews remain labeled in
full Records but are excluded from production exception counts. A contradictory
or missing filing match opens the original review instead of guessing a filing.
Refresh stages newly opened tables too and rejects mismatched review counts.
No new resolution action, production write, workflow or simulation behavior is
introduced. This local implementation is not authorization or proof of publication.


## D-2026-08-31-024 — Publish approved review UX through canonical Pages

**Decision:** The owner's explicit “Publish” instruction authorizes releasing
the tested review UX via a canonical pull request, successful CI and the existing
read-only Pages workflow. Preserve the separately approved recovery documentation
already on main and leave the local recovery branch/commit untouched.

**Reason:** The dashboard fixes are tested presentation changes. Publication
does not require a production writer or modification of protected state, and
does not resolve the separate obsolete queue or physical-device acceptance gates.

**Consequence:** Revalidate exact protected producer attempts, high-water marks,
ZIP hashes and inventories before and after publication, and verify the deployed
artifact/build and live content. Keep issues #4 and #6 open for outstanding device
acceptance. No collector, AI, simulation or external-alert dispatch is authorized
by this UI publication decision. PR #10 merged as `9d9e7be`; PR/main CI and
Pages run `33385044313` / attempt 1 succeeded. Post-deployment audit verified all
21 live files against artifact `9755242103`, exact consumed inputs, unchanged
protected inventories and simulator history. Physical-device acceptance remains
open. The final documentation-only evidence was prepared in an isolated worktree
because another task switched the shared checkout.

## D-2026-08-31-025 — Present Operations run history newest first

**Decision:** Issue #12 orders a copied health timeline by the actual retained
execution timestamp, descending, with stable descending run ID and URL ties.
Use a valid finish timestamp, falling back to a valid start timestamp when needed;
undated records follow dated records. The shared Overview preview uses the same
ordering as Operations.

**Reason:** The renderer reversed the model's already newest-first history.
Explicit datetime ordering also handles ascending or mixed API results without
reversing CSS, focus order, labels or record links.

**Consequence:** Native horizontal scrolling moves toward older runs on the right.
Each refresh starts at the latest item. Source arrays, stored chronology,
health status, schedules and state writers remain unchanged. No extra chronology
copy, slider controls or selection state is introduced. Native Node regression
checks complement optional DOM tests in the existing watched dashboard CI test file.
