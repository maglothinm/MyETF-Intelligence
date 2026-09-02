# PolitiTrack active handoff

Updated: **2026-09-02 UTC**  
Active issue: **#36 — Consolidate Runtime v2 safely in shadow mode (Beast Phases 1–2)**  
Active pull request: **#37 — Consolidate Runtime v2 safely in shadow mode**  
Active branch: **`codex/runtime-v2-shadow-integration`**  
Required endpoint: **ready for review, unmerged, and undeployed**

## Current authority

GitHub repository ID **1349678672**, currently named
`maglothinm/MyETF-Intelligence`, is canonical. The default branch is `main`.
Legacy `maglothinm/MyETF` is not an implementation or runtime target.

Canonical `main`, its existing GitHub Actions writers, and its protected-state
contracts remain production authority. Runtime v2 has not been merged, deployed,
initialized, imported, scheduled, or used for a live producer cycle by issue #36.

## Phase 1 — completed source recovery boundary

The integration started from verified `main`
`d603e9b40ffb78c51f635589bc886875f411299b`.

The original Runtime v2 source branch remains unchanged:

- branch: `codex/runtime-v2-cutover`
- head: `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6`
- merge base: `e6d7ba5f88ec5886ae4d4bf108a5edcc4e370515`
- intake divergence: seven commits ahead and two commits behind `main`

Its 29 committed paths were copied by exact blob identity onto fresh `main`
ancestry. Preservation checkpoint
`7cceb9694ef7b50f71494f7c5b6baabe57520aa5` is retained in PR #37 history. The
source branch was not merged, rebased, rewritten, or deleted.

The original ChatGPT Work filesystem is unavailable in the current execution
environment. Local-only worktrees, stashes, reflogs, staged/unstaged patches,
ignored files, and untracked files from that session are **unverified**, not
represented as recovered. The complete remote-ref inventory is in
`docs/CONSOLIDATION_INVENTORY.md`.

## Phase 2 — completed review implementation

Runtime v2 now requires:

```text
POLITITRACK_MODE=shadow|production
```

A missing, blank, unknown, or conflicting value fails closed before the CLI creates
the PostgreSQL store or starts a producer. `JobRunner` validates the contract
again.

In `shadow` mode:

- Legislative and Executive commands always receive `--no-notify`.
- AI commands always receive `--suppress-alerts`.
- trigger evidence is recorded as `shadow`.
- external notification, callback, webhook, Healthchecks, mail, Pushover, Slack,
  Discord, Twilio, SendGrid, Mailgun, SMTP, and GitHub Actions artifact
  credentials/context are removed from producer subprocess environments.
- read-only analysis credentials are not removed merely because the mode is
  shadow.
- runtime mode is retained in run rows, status, workflow evidence, and immutable
  snapshot provenance.
- failed shadow runs are not marked as possibly having emitted external effects.

Explicit production mode preserves intended producer command behavior and existing
explicit suppression settings. No production-mode execution occurred.

The SQL migration is additive; it records `runtime_mode`, backfills any historical
Runtime v2 run rows as production, and does not drop/recreate/initialize/replace a
snapshot table or head.

Terraform defaults producers to shadow and schedules to disabled. It rejects an
enabled schedule unless mode is explicitly production.

The recovered branch referenced `GoogleCloudObjectStore` but omitted the class.
PR #37 adds the missing lazy-loaded adapter with bounded object operations and
fail-closed private-bucket policy checks. No bucket was contacted or changed.

## Verified CI checkpoint

Checkpoint `1de2298bf1fbb0afcc772c6aedd82a6d4f9f4398` passed both required workflows:

| Workflow | Run | Result |
|---|---:|---|
| Runtime v2 safety tests | `33638954917` | success |
| Investor Edge tests | `33638955190` | success |

That checkpoint includes all executable, infrastructure, test, inventory,
cutover-guide, project-state, and decision-log changes through D-041. GitHub also
reported PR #37 mergeable against `main`.

This handoff update and the final project-state evidence are documentation-only
successors. They must still pass exact-head CI before PR #37 is marked ready for
review. The PR checks and PR body are the authority for the exact final head because
a file cannot contain its own future commit SHA.

## Parallel work held separately

- PR #3 / `codex/production-remediation` — draft; separate state-safety gates.
- PR #33 / `codex/score-receipts-data-quality` — draft; separate data-quality work.
- PR #35 / `codex/chatgpt-codex-phase-1-2` — separate continuity-documentation task.
- `codex/runtime-v2-integration` — temporary non-authoritative staging ref; do not
  continue from it.
- `codex/runtime-v2-cutover` — original preserved source; do not rewrite it.

No commit from those branches was merged or cherry-picked into PR #37.

## Prohibited actions

Do not merge PR #37, deploy, run Terraform, build/push a cloud image, invoke Cloud
Run, enable a scheduler, change mode to production, initialize/import Runtime v2
state, dispatch a collector/AI/dashboard/simulation, publish Pages, change
credentials/settings, contact Healthchecks, or read/write/replace/advance the
protected `legislative-tracker-state`, `executive-tracker-state`, or
`ai-analysis-state` artifacts.

## Next safe action

Require success from both workflows on the final documentation-only PR head,
reconfirm mergeability, mark PR #37 ready for review, update issue/PR metadata with
the exact final SHA and run IDs, then stop with the PR unmerged and undeployed.

State import, disposable/live shadow cycles, browser/runtime acceptance, production
promotion, schedule activation, one-writer transfer, rollback drills, and prior
runtime retirement belong to a later explicitly authorized release phase.
