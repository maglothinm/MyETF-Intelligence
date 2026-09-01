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

## D-2026-08-31-026 — Bootstrap retained history without creating new events

**Decision:** Issue #11 uses the combined normalized Legislative/Executive
transaction universe independently of AI candidate selection. Discover and
persist all configured historical profiles before bounded breadth-first market
work; retain a deterministic investor cursor and cache-only continuation when
network capacity is exhausted. Keep scoring, time censoring and all existing
40/40/30/40/2,200 defaults unchanged.

**Reason:** Provenance-verified production artifacts held only one eligible
purchase/identity, while 5,066 cataloged filings had no normalized transactions.
Main already refreshed globally from both branches; ordinary baseline/unseen-only
tracking never reconstructed the cataloged history. Sequential market processing
and missing population telemetry made the sparse result harder to diagnose.

**Consequence:** Existing tracker writers get a separate 20-filing bounded
historical pass using official scanners and original-document caches validated
by source identity, contained path and SHA-256. Access-request listings remain
blocked without legitimately available originals. Preserve parser IDs, original
observation timestamps, baselines and all prior ledger/seen state. Append silent
`historical_bootstrap` records and receipts; exclude them from new filing alerts,
model candidate/reanalysis selection, candidate upgrades/delivery and new local
Notification Center events. Partial parsing and missing prices remain explicitly
pending or blocked; no fabricated returns or completed-history claim is allowed.

Candidate-specific Edge failure remains fail-open, but global population
initialization/refresh/persistence is required for a successful AI state writer.
Initial maintenance failure stops candidate/market work. Pending and newly queued
candidate alerts use the existing bounded channel-deduplicated path only after
final maintenance succeeds and no earlier errors remain. This prevents the new
fatal maintenance gate from knowingly sending alerts in an unpublishable run;
it does not claim an atomic transaction across GitHub artifacts and external
delivery services.

The root and standalone dashboards publish full bounded profiles and actual
population/backfill metadata independently of qualifying signals. Unknown legacy
counts stay unknown. Workflow changes are coverage-only; no extra schedule,
writer, protected artifact or hosting path is introduced. Local acceptance
produced 17 building profiles and 122 pending observations from real artifact
copies. That local checkpoint did not establish deployment or live pending
reduction; the existing manual-production, held-PR and cutover gates are not relaxed.


Release authorization: the owner requested “Release the commit”. Integrate the
already-approved Operations ordering change from canonical main, retain both
regression suites, and publish through the existing PR/CI/Pages path. This does
not authorize a new manual production or simulation run or relax existing gates.

Release verification: PR #15 merged as `676701a`; integrated PR/main CI and the
automatic Pages publication succeeded. The deployed tree matches the tested head
and both dashboard surfaces were verified live. Production population progress
still requires subsequent normal writer evidence; local acceptance is not live state.

## D-2026-08-31-027 — Publish approved Operations ordering through canonical Pages

**Decision:** The owner's explicit “Merge and publish” instruction authorizes
merging tested PR #14 and dispatching the existing read-only Pages workflow on
canonical `main`, without a production writer or workflow/configuration change.

**Reason:** The narrow presentation fix has local regression coverage and exact
PR/main CI evidence. The existing publisher's push paths do not include its
frontend asset, so publication needs an explicit dispatch of that same workflow.

**Consequence:** PR #14 merged as `7a1108f`; main CI `33390543725` and Pages
`33390642511` succeeded on attempt 1. Artifact `9757309134` matches all 28 live
public files. Pre/postflight checks verified exact consumed producer attempts,
global high-water marks and unchanged protected payloads. The current two-entry
simulator history stayed unchanged; its immediate-predecessor prefix check passed.
The separately recorded historical rewrite concern remains unresolved before
future manual simulator work. Publication does not close physical-device acceptance, obsolete queue,
cutover, repository rename/privacy or external-delivery work. Release evidence is
recorded in a documentation-only successor after deployment, preserving the
concurrently used shared checkout and unrelated branches.

The concurrent approved Investor Edge release subsequently published `676701ac`
through Pages `33391179240` / attempt 1, artifact `9757512563`. It contains the
unchanged Operations implementation, verified in all generated script bundles and
in a fresh live browser at desktop/mobile widths. Current protected inputs remain
unchanged. This documentation successor integrates both releases on top of
`895bc57`, preserving decision 026 and all production-acceptance gates; neither
publication establishes live Investor Edge population or market backlog progress.

## D-2026-08-31-028 — Keep raw Filing Vault evidence in private runtime storage

**Decision:** Issue #13 adds the Vault to the existing Flask/SQLAlchemy/Supabase
architecture and links it from the existing generated dashboard. Private runtime
objects and additive vault tables are separate from all protected tracker artifacts.
GitHub/Pages contain code and safe metadata only, never cached government documents.

**Reason:** Static Pages cannot safely implement persistent server retrieval,
acknowledgement enforcement, hash validation, expiration and source access gates.
An optional runtime preserves the existing deployment and ingestion contracts.

**Consequence:** Absolute retention is 30 days from actual retrieval; metadata checks
do not renew it. Exact IDs and immutable version/source snapshots survive expiration.
Government requirements remain distinct from the versioned PolitiTrack notice.
Synthetic records are rejected by server admission, and no simulation gets Vault
credentials. Known request-only disclosures remain request-only. Source endpoint
checks never pretend to discover separate amendments without authoritative catalog
relationships. Local PDF.js rendering preserves original bytes and avoids blank
native embeds; its code assets and licenses are pinned locally. API/storage
configuration, verified catalog delivery, runtime timer installation and publication
must be verified separately before the feature can be described as operational.

## D-2026-08-31-029 — Publish the approved Filing Vault through canonical Pages

**Decision:** The owner's explicit Publish instruction authorizes pushing the
Vault branch, canonical PR/CI, merge and the existing read-only Pages publisher.
Preserve current main's Operations-history and Investor Edge fixes and all previous
release evidence.

**Reason:** The implemented source-aware runtime and integrated interface can be
released without changing protected state. Deployment status must still distinguish
published code/catalog UI from configured, operational cached-document retrieval.

**Consequence:** Require successful CI on the exact integrated source, validated
protected producer attempts/high-water marks, and verified Pages artifact/live
content. With no runtime configuration, publish the honest catalog-only state;
never invent API/storage credentials, source acknowledgements or cached availability.
No production writer, simulation or real alert dispatch is authorized. Keep issue
#13 open until private runtime and source/device acceptance are verified.

Release verification: PR #16 merged as `104fc51` with a tree identical to tested
`7553499`. PR/main CI and Pages `33392608680` / attempt 1 succeeded. The live
catalog/viewer is published while private retrieval remains inactive; build
configuration contains no API origin. Protected producer attempts, artifacts and
retained simulator history remain unchanged. Runtime/source/device acceptance
stays open in issue #13; this publication cannot be described as an operating cache.

## D-2026-08-31-030 — Keep one measured dashboard shell and the document scroller

**Decision:** Implement persistent navigation in the existing shared dashboard
shell. Observe the header's actual border-box height and share that measurement
with the desktop sidebar position, remaining viewport height and document anchor
offset. Keep the document as the main content scroller. Only the persistent
Workspace panel receives independent vertical overflow, and only while its
desktop layout applies; preserve the existing narrow-screen navigation.

**Reason:** Header wrapping, viewport changes and zoom make a guessed fixed offset
unreliable. A shared shell keeps all six dashboard hash routes consistent without
route copies or an additional scrolling page wrapper. Removing the shell's table
height cap avoids a third vertical scroll context while preserving horizontal
access to wide records. Native dialog/popover layering and the existing shared
tooltip remain above the pinned header and sidebar.

**Consequence:** Preserve branding, controls, navigation semantics, focus order
and breakpoints, including current main's seven-link Workspace and separate
Filing Vault page. Scope the shell class to the root dashboard. Change only
presentation assets, related frontend fixtures and project records; preserve
upstream workflows, collectors, scores, state, alerts, simulations and hosting.
Report local, integrated, deployed and physical-device validation separately.
This shell decision was locally numbered 025 before integration; published
Operations decision 025 and subsequent decisions 026–029 retain their identities.

## D-2026-08-31-031 — Deploy the approved persistent shell through canonical Pages

**Decision:** The owner's explicit **Deploy** instruction authorizes publishing
the tested shell through a canonical pull request, successful CI, merge and the
existing read-only Pages publisher. Integrate the already-approved Operations,
Investor Edge and Filing Vault releases from main without reverting their changes
or discarding their release and continuity evidence.

**Reason:** The shell can be deployed without a production writer or changed
workflow configuration. Asset-only changes require explicit dispatch of the
existing publisher when its unchanged push-path filter does not trigger a run.
The owner authorized deployment after native-input/device limitations were reported.

**Consequence:** Validate the exact combined source, protected producer attempts,
ancestry and high-water marks; require successful canonical CI and independently
verify the Pages artifact, consumed inputs and live content. Record exact release
IDs after verification. This checkpoint records authorization and integration,
not a completed deployment. No production writer, simulation, external alert,
private Vault runtime activation, repository setting or rebaseline is authorized.
Device acceptance, obsolete queues, historical simulator concerns, held PR #3,
cutover and external-delivery proof remain separate open work.

Release verification: PR #17 merged as `42351e2` with a tree identical to tested
`6967a17`. Combined local 524 tests and exact PR/main CI passed. Existing Pages
`33395506967` / attempt 1 succeeded, artifact `9759155643`. The 13:12:37 UTC audit
verified all 238 served content files plus root, exact consumed protected attempts,
fresh producer high-water marks and unchanged protected/simulator inventories.
All six live dashboard routes and 320px–3840px rendered layouts passed shell/anchor,
independent scrolling and overlay checks with no console warnings/errors. The seven-link
Workspace, separate Vault page, prior releases and honest inactive Vault runtime
are preserved. No production writer, simulation or external alert was dispatched.
Issues #4/#6 device acceptance and all existing production/runtime/cutover gates
remain open. Full evidence is in
[the release receipt](validation/persistent-shell-release-2026-08-31.md).

## D-2026-08-31-032 — Preserve approved icon sources and publish web copies

**Decision:** Keep the 22 unchanged files from the owner-supplied
`PolitiTrack_Icon_Assets.zip` in `assets/branding/polititrack/`, with source/archive
SHA-256 provenance. Publish only the required web variants through the existing
dashboard generators and the retained React frontend. Store the Windows ICO for
packaging/shortcut use without inventing a Windows installer configuration.

**Reason:** The approved artwork must remain recoverable at original resolution,
and adding images beside templates alone does not put them into generated Pages
output. Both the main and standalone Investor Edge generators need complete
favicon/manifest assets even when invoked independently.

**Consequence:** One small copying helper stages the runtime icons and manifest.
Relative URLs preserve repository-subpath hosting. Existing header dimensions,
wording, navigation and responsive layout remain unchanged; the large portrait
Wallboard keeps its 54px icon. The main manifest uses browser display mode and
does not add a service worker or alter application behavior. No collector, score,
state, workflow, alert, simulation, credential or hosting setting changes.

**Release:** [PR #18](https://github.com/maglothinm/MyETF-Intelligence/pull/18)
merged `aa8201a` as `6bd76843` with an identical tree. Local Python/React checks,
both CI runs and automatic Pages publication passed. All 250 served files plus
root match the published archive; live desktop/mobile geometry is preserved.
See [the release receipt](validation/icon-assets-2026-08-31.md) for full evidence
and unchanged protected input provenance.

## D-2026-08-31-033 — Separate execution success from monitoring freshness

**Decision:** Issue #19 defines one Python freshness policy: Legislative 15-minute
cadence / 30-minute stale threshold; Executive 30 / 60; collector-triggered AI
15-minute nominal input opportunity / 75-minute completion threshold. Overall
health uses failure > stale > unknown > success. A latest failure outranks an
earlier recent success. Browser aging uses the published policy and immutable
successful collector timestamps even when publication stops.

**Reason:** Historical run conclusions concealed materially overdue collection.
Protected state is uploaded only by successful producers, so it cannot alone
describe a later failed attempt. Dashboard generation, AI analysis and portfolio
refresh are also different from source collection.

**Consequence:** Add sanitized, exact-attempt Actions observations to the read-only
publisher without making them production-state authority. Failed collectors can
trigger a new health publication; skipped/cancelled publication is never a collector
failure. Source data through reflects production source observations and collector
completion; generation is separate. Operations exposes last attempt/success,
cadence, age, next expected check, overdue duration and trigger. Missing or
malformed evidence is unavailable; no synthetic or missing run is invented.

## D-2026-08-31-034 — Prepare external dispatch without switching authority

**Decision:** External scheduling uses authenticated workflow_dispatch into the
same two canonical collectors, with an allowlisted trigger_source input. The
provider-neutral client and inert Cloudflare Worker validate repository ID
1349678672, workflow identity and live default branch. Legislative GitHub cron
stays 7,22,37,52; Executive becomes 13,43. Proposed external times are 5,20,35,50
and 11,41, respectively. Preserve existing fixed concurrency groups with
cancel-in-progress false and validated latest-state restore.

**Reason:** Measured multi-hour cron gaps require independent delivery, but adding
a dispatch client alone does not establish provisioning or cadence. Concurrent
successful triggers must continue through one writer and retained deduplication.
A failed attempt can have sent an external alert before saving durable state.

**Consequence:** Block automatic replay when a later unretained producer attempt
may have entered the collector/analyst side-effect step; demonstrably unstarted or
skipped steps can recover normally. Review/recover ambiguous delivery rather than
silently resending. This does not claim atomic exactly-once delivery across GitHub
artifacts and external providers. The Worker has no public trigger endpoint and
ships with scheduling disabled and no secrets. Require legitimate infrastructure
configuration, existing obsolete-writer clearance, several real dispatch cycles
and continuity verification before activation or any later GitHub-cron removal.
The current task authorizes staged PR/CI/merge/Pages deployment; it does not approve
rebaselining, revival of retired writers, or bypass of existing recovery gates.

## D-2026-08-31-035 — Age published evidence independently of the device clock

**Decision:** Dashboard and Monitor share one injectable elapsed-time clock per
open page. Anchor it to the accepted publication and monotonic elapsed time.
Retain that anchor across repeat fetches of the same publication; never allow
device-clock catch-up or rollback to make already aged evidence green again.
Clock uncertainty makes otherwise current evidence unknown, with failure/stale
still taking precedence. A newer publication can establish a fresh anchor but
cannot lower the elapsed-time assessment already reached by the page.

**Reason:** Clamping device time to the server timestamp preserved server-proven
stale status, but a newly published fresh snapshot could stop aging while the
device clock was behind. A fixed-time audit after PR #20 reproduced this case.

**Consequence:** Health continues aging without publication or wall-clock
progress. Missing/invalid clock evidence has contextual help and cannot assert
current monitoring. This changes no cadence policy, source timestamp, state,
writer, alert, scheduler activation or protected artifact authority.

**Release verification for D-035:** PR #21 merged as `5932a49950384fb9cb2bdab93c4093ea596789a1`;
final Pages `33421979811` / 1, artifact `9769279578`, both final CI runs,
633 local tests and exact protected-state/live-content verification passed.
External activation remains gated; GitHub cron stays enabled. See the
[final release receipt](validation/scheduler-freshness-2026-08-31.md).

## D-2026-09-01-036 — Preserve nonproduction identity across public redaction

**Decision:** The public dashboard projection retains a coarse boolean exclusion
for every record with explicit test or simulation evidence. The projection never
retains the private environment value or test metadata that caused the exclusion.

**Reason:** The publisher sanitizes retained input before building health. Direct
model tests rejected `environment=simulation` and private-only `test_metadata`,
but the sanitizer removed those values before the production build called the
health model. A recent excluded row could consequently refresh collector health
and source currency after redaction.

**Consequence:** One shared predicate defines the existing nonproduction rules.
The sanitized JSON and CSV copies remain safe and idempotent while the coarse
marker prevents production admission, source ancestry and Operations history from
consuming test or simulation evidence. Open contextual help also rehydrates when elapsed-time
aging changes status, so its visible explanation cannot retain earlier green
wording. This changes no collector, schedule, state artifact, trigger, alert,
simulation writer, external scheduler activation or production credential.

**Release verification:** [PR #23](https://github.com/maglothinm/MyETF-Intelligence/pull/23)
tested `5aa8cef3127beba9c5a8fef002d1228710fb0b26` in CI `33498107710` and merged as
`2c1be6040e2e6d8cda18991dbb2db38fe56a011a`. Main CI `33498254970` and Pages
`33498255010` succeeded; Pages artifact `9796632425` is tied to that merge SHA.
The live model remained conservatively stale because Executive evidence was
228.833 minutes old even though the latest retained run succeeded. Legislative
and AI were current; source data through remained the Legislative collector
completion rather than the later dashboard build. Desktop, portrait, Wallboard,
newest-first history and stale help were verified. External activation remains
gated and GitHub cron remains enabled.
