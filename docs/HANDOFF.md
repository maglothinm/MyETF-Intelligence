# PolitiTrack active handoff

Updated: **2026-09-02 UTC**  
Active issue: **#36 — Consolidate Runtime v2 safely in shadow mode (Beast Phases 1–2)**  
Active review: **PR #38 — Consolidate Runtime v2 safely in shadow mode**  
Active branch: **`codex/runtime-v2-shadow-review`**  
Required endpoint: **open for review, unmerged, and undeployed**

## Current authority

GitHub repository ID **1349678672**, currently named
`maglothinm/MyETF-Intelligence`, is canonical. Canonical `main`, its existing
GitHub Actions writers, and its protected-state contracts remain production
authority. Legacy `maglothinm/MyETF` is not an implementation or runtime target.

Runtime v2 has not been merged, deployed, initialized, imported, scheduled, or
used for a live producer cycle by issue #36.

## Review-PR transition

Draft PR #37 reached green, mergeable head
`8b16436e14862ad7abcdf94dc7272f437f88b091`. The GitHub connector then failed to
clear its draft flag because its ready-for-review GraphQL response requested an
unsupported repository field. PR #37 was closed **without merge** and retained as
recovery evidence.

PR #38 was opened non-draft from the same exact head on
`codex/runtime-v2-shadow-review`. This transition changed no executable tree,
production state, runtime, or cloud resource. PR #38 is the sole active review for
this work.

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
`7cceb9694ef7b50f71494f7c5b6baabe57520aa5` remains in the review history. The
source branch was not merged, rebased, rewritten, or deleted.

The original ChatGPT Work filesystem is unavailable in the current execution
environment. Local-only worktrees, stashes, reflogs, staged/unstaged patches,
ignored files, and untracked files from that session are **unverified**, not
represented as recovered. The remote-ref inventory is in
`docs/CONSOLIDATION_INVENTORY.md`.

## Phase 2 — completed review implementation

Runtime v2 requires:

```text
POLITITRACK_MODE=shadow|production
```

Missing, blank, unknown, or conflicting values fail closed before the CLI creates
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

The SQL migration is additive and does not drop, recreate, initialize, import,
replace, or advance a snapshot table or head. Terraform defaults producers to
shadow, leaves schedules disabled, and rejects an enabled schedule unless mode is
explicitly production.

The recovered source referenced `GoogleCloudObjectStore` but omitted the class.
The review implements the missing lazy-loaded adapter with bounded object
operations and fail-closed private-bucket policy checks. No bucket was contacted.

## Verified executable-tree checkpoint

Head `8b16436e14862ad7abcdf94dc7272f437f88b091` passed:

| Workflow | Run | Result |
|---|---:|---|
| Runtime v2 safety tests | `33639231223` | success |
| Investor Edge tests | `33639231236` | success |

GitHub reported that tree mergeable against `main`.

The PR #38 continuity updates are documentation-only successors. Both workflows
must pass on the exact final PR #38 head before the handoff is closed. PR checks
and metadata are the authority for that future SHA because a tracked file cannot
contain its own commit ID.

## Parallel work held separately

- PR #3 / `codex/production-remediation` — draft; separate state-safety gates.
- PR #33 / `codex/score-receipts-data-quality` — draft; separate data-quality work.
- PR #35 / `codex/chatgpt-codex-phase-1-2` — separate continuity task.
- PR #37 / `codex/runtime-v2-shadow-integration` — closed, unmerged predecessor.
- `codex/runtime-v2-integration` — temporary non-authoritative staging ref.
- `codex/runtime-v2-cutover` — original preserved source.

No commit from the separately gated branches was merged or cherry-picked into the
active review.

## Prohibited actions

Do not merge PR #38, deploy, run Terraform, build/push a cloud image, invoke Cloud
Run, enable a scheduler, change mode to production, initialize/import Runtime v2
state, dispatch a collector/AI/dashboard/simulation, publish Pages, change
credentials/settings, contact Healthchecks, or read/write/replace/advance the
protected `legislative-tracker-state`, `executive-tracker-state`, or
`ai-analysis-state` artifacts.

## Next safe action

Require both workflows to pass on the final PR #38 head, reconfirm mergeability,
record the exact SHA and run IDs in issue/PR metadata, and stop with PR #38 open,
non-draft, unmerged, and undeployed.

State import, disposable/live shadow cycles, browser/runtime acceptance, production
promotion, schedule activation, one-writer transfer, rollback drills, and prior
runtime retirement require a later explicitly authorized release phase.
