---
name: Codex implementation task
about: Create a bounded PolitiTrack task packet for ChatGPT → Codex execution
title: ""
labels: ""
assignees: ""
---

<!--
Before dispatching Codex, ChatGPT should validate current GitHub state and replace
all placeholders below. This template supplements AGENTS.md and
docs/CHATGPT_CODEX_WORKFLOW.md; it does not relax either contract.
-->

## Goal

Describe the user-visible or operational outcome.

## Repository identity / base

- Canonical repository ID: `1349678672`
- Repository: `maglothinm/MyETF-Intelligence` (use the current live name if renamed)
- Base branch: `main`
- Observed base SHA: `<sha>`
- Related issues/PRs: `<references>`

## Existing behavior / evidence

Summarize the live repository, runtime, dashboard, Actions, or artifact evidence that motivates this task. Distinguish verified facts from hypotheses.

## Scope

- `<allowed change>`
- `<allowed change>`

## Out of scope / hard boundaries

- Do not work in legacy `maglothinm/MyETF`.
- Preserve unrelated work.
- `<explicitly excluded behavior/file/system>`
- `<production/state/deployment boundary>`

## Implementation requirements

1. `<required behavior>`
2. `<required behavior>`
3. `<required behavior>`

Avoid prescribing implementation details unless they are necessary for safety, compatibility, or acceptance.

## State-safety requirements

State whether this task is read-only/presentation-only or may affect production state.

If production state is involved, enumerate the applicable protected artifacts, restore authority, writer/concurrency rules, simulation restrictions, rebaseline prohibition, alert/credential restrictions, and any active infrastructure gates from `AGENTS.md` / `docs/HANDOFF.md`.

## Acceptance criteria

- [ ] Canonical repository ID remains `1349678672`.
- [ ] Requested behavior is implemented within scope.
- [ ] Existing protected behavior/state remains unchanged unless explicitly authorized above.
- [ ] Applicable regressions/tests pass.
- [ ] No unrelated diff is introduced.
- [ ] Required continuity documentation is updated.
- [ ] Exact status is reported as proposed / implemented locally / committed / PR open / merged / deployed / operational.
- [ ] `<task-specific acceptance>`

## Verification required

- Local/unit/integration checks: `<commands or suites>`
- CI: `<required checks>`
- Rendered/browser/device checks: `<if applicable>`
- Actions/deployment checks: `<if applicable>`
- Artifact/provenance/continuity checks: `<if applicable>`

## Codex completion contract

Before reporting completion, Codex must:

1. Read `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, `docs/CHATGPT_CODEX_WORKFLOW.md`, and this issue.
2. Revalidate current canonical `main` and active gates before editing.
3. Use an isolated `codex/<issue-or-task>-<slug>` branch/worktree for material work.
4. Implement only this issue's scope and preserve unrelated changes/state.
5. Run the required checks and record exact results.
6. Update `PROJECT_STATE`, `DECISIONS`, and `HANDOFF` when required by `AGENTS.md`.
7. Commit the work and open/update a PR unless the issue explicitly authorizes another repository-safe path.
8. Report repository name/ID, branch, commit SHA, changed files, tests, CI, PR, deployment, protected-artifact evidence, blockers, and next safe action as applicable.

ChatGPT will independently verify the live GitHub evidence before treating the task as complete.
