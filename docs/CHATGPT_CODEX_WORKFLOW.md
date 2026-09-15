# ChatGPT → Codex continuity workflow

Status: Phase 1 foundation exists; Phase 2 execution protocol defined here.
Tracking issue: #34.

This document makes the existing PolitiTrack continuity contract usable for normal owner-driven work. It supplements `AGENTS.md`; it does not replace it. If this document conflicts with `AGENTS.md`, `AGENTS.md` controls.

## Roles

### Owner

The owner supplies the product intent, priorities, constraints and release decision.

### ChatGPT

ChatGPT is the product/technical control plane. It translates the owner's intent into a bounded repository task, checks live GitHub state before relying on conversation memory, defines acceptance criteria, and independently verifies Codex results against repository evidence.

ChatGPT may inspect or change GitHub directly when the requested work and available tools permit it, but repository state—not the chat transcript—is the durable record.

### Codex

Codex is the implementation agent. It reads the repository contract and task issue, works only in the canonical repository, changes code/docs, runs tests, records evidence, and returns a precise implementation status. Codex must not treat a prior chat summary as authority over live repository state.

### GitHub

Canonical repository ID `1349678672` is the durable source of truth for code, issues, decisions, handoffs, commits, pull requests, Actions and protected-state lineage. The mutable repository name does not override the numeric identity requirement in `AGENTS.md`.

Legacy `maglothinm/MyETF` is not an implementation target.

## Phase 1 — canonical project memory

Phase 1 uses the continuity files that already exist. Do not create parallel replacements.

| Purpose | Canonical record |
|---|---|
| Repository/agent rules | `AGENTS.md` |
| Current operational truth | `docs/PROJECT_STATE.md` |
| Durable decisions | `docs/DECISIONS.md` |
| Active task / next safe action | `docs/HANDOFF.md` |
| Work definition | GitHub issue |
| Implementation evidence | commit / PR |
| Automated verification | GitHub Actions |
| Production continuity | provenance-valid protected artifacts per `AGENTS.md` |

Conversation memory is context only. When it conflicts with live GitHub evidence, investigate the discrepancy and use the repository contract to resolve it.

## Phase 2 — one request, one bounded execution loop

### 1. ChatGPT intake

For a material PolitiTrack request, ChatGPT should first determine whether the request is:

- explanation/review only;
- a documentation/process change;
- a code change;
- a deployment/operations action; or
- a state-affecting production action.

For repository-state or implementation work, perform the `AGENTS.md` session-start checks before writing implementation instructions.

### 2. Live-state preflight

Before dispatching Codex, establish at minimum:

- canonical repository ID and current name;
- base branch and current base commit SHA;
- relevant open issue(s), PR(s), recent commits and Actions evidence;
- applicable protected-state or deployment gates;
- whether unrelated work is already in progress;
- the canonical continuity files relevant to the task.

Do not create a new repository or use legacy `maglothinm/MyETF` to bypass a blocker.

### 3. Create the task issue

Every material implementation gets a GitHub issue containing the task packet below. Reuse an existing issue only when the new request is genuinely the same scope and acceptance contract.

The issue is the durable statement of intent. ChatGPT conversation text may elaborate on it, but Codex should be able to execute safely from the issue plus repository contract.

### 4. Task packet contract

A Codex task packet must contain:

1. **Goal** — the user-visible or operational outcome.
2. **Repository identity** — canonical repository ID, repository name, base branch and observed base SHA.
3. **Scope** — files/surfaces/behaviors that may change.
4. **Out of scope / hard boundaries** — things Codex must not change.
5. **Existing behavior/evidence** — the live facts that motivated the task.
6. **Implementation requirements** — required behavior without over-prescribing internals unless necessary.
7. **State-safety requirements** — protected artifacts, writer/simulation restrictions and any active gates.
8. **Acceptance criteria** — objective conditions that define success.
9. **Verification** — local tests, CI, rendered/browser checks, artifact lineage or deployment checks as applicable.
10. **Completion contract** — exact files/commit/PR/evidence/docs Codex must report and update.

When the task has no production-state implications, say so explicitly rather than omitting the boundary.

### 5. Codex execution

For material work, Codex should:

1. Read `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, this workflow, and the task issue.
2. Reconfirm repository ID `1349678672` before changes.
3. Start from the task's verified base, refreshing from canonical `main` if the base has moved and documenting any resulting scope conflict.
4. Use one isolated branch/worktree named `codex/<issue-or-task>-<slug>`.
5. Preserve unrelated work and production state.
6. Implement only the approved scope.
7. Run the applicable tests/checks.
8. Update continuity documentation when required by `AGENTS.md`.
9. Commit the implementation and open/update a PR for material work unless the task explicitly calls for a different repository-safe path.
10. Report status using the vocabulary below.

### 6. Status vocabulary

Use these terms precisely:

- **Proposed** — instructions/design only; no repository change.
- **Implemented locally** — changed in a worktree but not committed.
- **Committed** — present in a Git commit on a branch.
- **PR open** — proposed for merge; not on canonical `main`.
- **Merged** — present on canonical `main`.
- **Deployed** — publication/deployment completed successfully.
- **Operational** — live runtime behavior and required dependencies/credentials/state have been verified.

Never compress these into a generic "done" when the distinction matters.

### 7. ChatGPT verification after Codex

When Codex reports completion, ChatGPT should not rely on the prose report alone. Re-read live GitHub evidence and verify, as applicable:

- branch/commit/PR identity;
- changed files and diff scope;
- CI/test conclusions;
- main-branch merge SHA;
- Pages or other deployment run;
- protected artifact lineage and continuity;
- dashboard/runtime behavior;
- required updates to `PROJECT_STATE`, `DECISIONS` and `HANDOFF`;
- remaining blockers or unverified claims.

If the evidence does not support Codex's status label, downgrade the status and identify the missing proof.

## Default owner workflow

For normal PolitiTrack development, the preferred sequence is:

**Owner request in ChatGPT → ChatGPT live-state check → GitHub issue/task packet → Codex implementation branch → PR/CI → ChatGPT verification → merge/deploy decision → repository continuity update.**

The owner should not have to manually reconstruct project history for each new chat. The repository contract carries the durable facts; ChatGPT uses those facts to recover context before dispatching Codex.

## Short Codex dispatch form

When an issue already contains the full task packet, ChatGPT can give Codex a short dispatch instead of pasting a long duplicate specification:

> Implement GitHub issue #<N> in canonical repository ID 1349678672. Read `AGENTS.md`, `docs/PROJECT_STATE.md`, `docs/DECISIONS.md`, `docs/HANDOFF.md`, and `docs/CHATGPT_CODEX_WORKFLOW.md` first. Revalidate current `main` and all active gates before editing. Work on an isolated `codex/...` branch, preserve unrelated work and production state, satisfy the issue acceptance criteria, run required verification, update continuity records as required, commit, open/update the PR, and report exact evidence. Do not treat chat memory as authority over live GitHub state.

This form is intentionally short: the GitHub issue, not repeated chat prose, is the durable implementation specification.
