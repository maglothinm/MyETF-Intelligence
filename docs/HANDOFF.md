# PolitiTrack active handoff

Updated: **2026-09-02 UTC**  
Active issue: **#36 — Consolidate Runtime v2 safely in shadow mode (Beast Phases 1–2)**  
Active pull request: **#37 — Consolidate Runtime v2 safely in shadow mode**  
Active branch: **`codex/runtime-v2-shadow-integration`**  
Required state: **draft/unmerged/undeployed until every gate below is recorded**

## Current authority

GitHub repository ID **1349678672**, currently named
`maglothinm/MyETF-Intelligence`, is canonical. The default branch is `main`.
Legacy `maglothinm/MyETF` is not an implementation or runtime target.

GitHub Actions and the state/artifacts already governed by canonical `main` remain
the production authority. Runtime v2 has not been promoted, deployed, initialized,
imported, scheduled, or used for a live producer cycle by this task.

## Phase 1 result — remotely committed work preserved

The integration started from verified `main`
`d603e9b40ffb78c51f635589bc886875f411299b`.

The original Runtime v2 source branch remains unchanged:

- branch: `codex/runtime-v2-cutover`
- head: `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6`
- merge base: `e6d7ba5f88ec5886ae4d4bf108a5edcc4e370515`
- intake divergence: seven commits ahead and two commits behind `main`

Its 29 committed paths were copied by exact blob identity onto fresh `main`
ancestry. Preservation checkpoint
`7cceb9694ef7b50f71494f7c5b6baabe57520aa5` exists on the current branch.
The source branch was not merged, rebased, rewritten, or deleted.

The original ChatGPT Work filesystem is unavailable in the current execution
environment. Local-only worktrees, stashes, reflogs, staged/unstaged patches,
ignored files, and untracked files from that session are therefore **unverified**,
not represented as recovered. Complete remote evidence and branch classification
are in `docs/CONSOLIDATION_INVENTORY.md`.

## Phase 2 result — shadow-safe integration

Runtime v2 now requires an explicit operational mode:

```text
POLITITRACK_MODE=shadow|production
```

A missing, blank, unknown, or conflicting mode fails closed before the CLI creates
the PostgreSQL store or starts a producer. `JobRunner` independently validates the
contract.

In `shadow` mode:

- Legislative and Executive tracker commands always receive `--no-notify`.
- AI analyst commands always receive `--suppress-alerts`.
- trigger evidence is recorded as `shadow`.
- notification, callback, webhook, Healthchecks, mail, Pushover, Slack, Discord,
  Twilio, SendGrid, Mailgun, SMTP, and GitHub Actions artifact credentials/context
  are removed from producer subprocess environments.
- read-only analysis credentials are not removed merely because the mode is
  shadow.
- runtime mode is written to run rows, status output, workflow evidence, and
  immutable snapshot provenance.
- failed shadow runs are not marked as possibly having emitted external side
  effects.

In `production` mode, existing producer command behavior remains available and
explicit suppression settings still work. No production-mode execution occurred.

The Runtime v2 database migration is additive. It introduces `runtime_mode`,
backfills historical Runtime v2 rows as `production`, and does not drop, recreate,
initialize, or replace snapshot tables or heads.

Terraform producer configuration defaults to `POLITITRACK_MODE=shadow` and
`schedules_enabled=false`. A Terraform check rejects enabled schedules unless the
mode is explicitly `production`.

The source branch referenced a private GCS Vault adapter that it did not commit.
Phase 2 added that missing adapter with lazy Google Cloud imports and fail-closed
checks for uniform bucket-level access and enforced public-access prevention.
No bucket was contacted or changed by this task.

## Test and review gate

PR #37 adds a read-only `Runtime v2 safety tests` workflow. It installs the
Runtime v2 dependency set, compiles `runtime_v2`, runs focused synthetic tests,
and executes `verify.sh`. It does not invoke a producer or receive write
permissions.

The standard `Investor Edge tests` workflow also runs on the PR to detect
integration regressions. The first exact-head attempt exposed the missing GCS
adapter and failed before tests could execute; that defect was corrected rather
than retried unchanged.

Before ending Phases 1–2, record successful checks for the exact final PR head,
confirm the PR is mergeable, and move it from draft to ready-for-review only when
those checks pass. **Do not merge it.**

## Parallel work held separately

- PR #3 / `codex/production-remediation` — draft; separate state-safety gates.
- PR #33 / `codex/score-receipts-data-quality` — draft; separate data-quality work.
- PR #35 / `codex/chatgpt-codex-phase-1-2` — separate continuity-documentation task.
- `codex/runtime-v2-integration` — temporary non-authoritative staging ref retained
  to avoid rewriting/deleting recovery evidence; do not continue from it.

No commit from those branches was merged or cherry-picked into PR #37.

## Prohibited actions at this handoff

Do not merge PR #37, deploy, run Terraform, build or push a cloud image, invoke
Cloud Run, enable a scheduler, change `POLITITRACK_MODE` to production, initialize
or import Runtime v2 state, dispatch a collector/AI/dashboard/simulation, publish
Pages, change credentials/settings, or read/write/replace/advance the protected
`legislative-tracker-state`, `executive-tracker-state`, or `ai-analysis-state`
artifacts.

## Next safe action

Finish the exact-head PR #37 CI/review record. If both workflows pass and GitHub
reports the PR mergeable, mark it ready for review and stop with it unmerged and
undeployed. State import, disposable or live shadow cycles, browser/runtime
acceptance, production promotion, schedule activation, rollback drills, and
retirement of the prior production path belong to a later explicitly authorized
release phase.
