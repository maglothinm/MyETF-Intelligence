# PolitiTrack project state

**Current as of:** 2026-09-02 UTC  
**Canonical repository ID:** `1349678672`  
**Current repository name:** `maglothinm/MyETF-Intelligence`  
**Default branch:** `main`  
**Active controlled work:** issue #36 / draft PR #37  
**Active branch:** `codex/runtime-v2-shadow-integration`

This file records current operational truth. Historical release receipts remain in
`validation/`, incident records, the append-only decision log, and Git history.

## Operational authority

Canonical `main` and its existing GitHub Actions production-state contracts remain
the operational authority. The currently published dashboard and existing
Legislative, Executive, AI, simulation, and Filing Vault presentation behavior on
`main` were not changed or redeployed by issue #36.

Runtime v2 is **not** production authority. Under the current task it has not been:

- merged to `main`;
- deployed to a cloud runtime;
- initialized against a live PostgreSQL database;
- populated through a protected-state import;
- used for a live collector, AI, dashboard, or simulation cycle;
- configured with an active schedule;
- promoted to `POLITITRACK_MODE=production`;
- used to publish GitHub Pages or replace any existing production state.

No claim is made here about the current availability of an external cloud project,
credentials, billing, database, bucket, or scheduler. Issue #36 did not inspect or
change those resources.

Legacy `maglothinm/MyETF` remains excluded from implementation and runtime work.

## Active objective — Beast Runtime v2 Phases 1–2

The current objective is limited to safe source consolidation and a reviewable
shadow-mode implementation. Production cutover is outside this phase.

### Verified starting evidence

| Evidence | Value |
|---|---|
| Intake `main` | `d603e9b40ffb78c51f635589bc886875f411299b` |
| Runtime v2 source branch | `codex/runtime-v2-cutover` |
| Runtime v2 source head | `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6` |
| Source merge base | `e6d7ba5f88ec5886ae4d4bf108a5edcc4e370515` |
| Intake divergence | 7 commits ahead, 2 commits behind `main` |
| Preserved source-tree checkpoint | `7cceb9694ef7b50f71494f7c5b6baabe57520aa5` |
| Active review | draft PR #37 |

The source branch remains unchanged. Its 29 committed Runtime v2 paths were copied
by exact blob identity to a fresh branch based on verified `main`, avoiding an
implicit merge or rebase of divergent history.

The original ChatGPT Work filesystem is unavailable in the current environment.
Local-only worktrees, stashes, reflogs, staged or unstaged patches, ignored files,
and untracked files from that session are therefore **unverified**. This limitation
does not authorize deployment, state initialization, or rebaselining. The complete
remote-ref inventory and classifications are in
`docs/CONSOLIDATION_INVENTORY.md`.

## Phase 2 implementation state

### Explicit operating mode

Producer execution now requires:

```text
POLITITRACK_MODE=shadow|production
```

Missing, blank, unknown, or conflicting values fail closed. The CLI resolves the
mode before constructing its PostgreSQL store, and `JobRunner` validates the mode
again before producer command construction.

### Shadow-mode controls

In `shadow` mode:

- Legislative and Executive commands always include `--no-notify`.
- AI commands always include `--suppress-alerts`.
- legacy suppression flags cannot opt out of those controls.
- trigger evidence is normalized to `shadow`.
- external notification/callback/Healthchecks/mail/webhook credentials and GitHub
  Actions artifact credentials/context are removed from subprocess environments.
- read-only analysis credentials are not removed solely because the mode is
  shadow.
- the mode is recorded in durable run rows, status output, workflow evidence, and
  immutable snapshot provenance.
- a failed run is not marked as possibly having emitted external side effects.

This is defense in depth around the existing producer flags; it does not make a
live shadow cycle part of Phase 2 acceptance.

### Production compatibility

Explicit `production` mode retains the intended producer command behavior.
Existing explicit notification or AI-alert suppression remains effective. Tests
must prove that production command construction is not accidentally forced into
shadow suppression. No production-mode process was run by this task.

### Durable-state schema

The Runtime v2 migration is additive:

- adds `runtime_mode` to `runtime_job_runs`;
- restricts it to `shadow` or `production`;
- backfills any pre-existing Runtime v2 run rows as `production`;
- does not drop/recreate state tables or heads;
- does not initialize, import, replace, or advance a snapshot.

All database behavior in this phase is validated through source inspection and
test doubles, not a live database.

### Infrastructure declarations

Terraform producer environment defaults to:

```hcl
POLITITRACK_MODE = "shadow"
```

Schedules remain disabled by default. A Terraform check rejects
`schedules_enabled=true` unless the mode is explicitly `production`. Running
Terraform, building/pushing the image, creating resources, importing state, or
enabling schedules is prohibited in this phase.

### Filing Vault runtime reconciliation

The preserved source referenced a `GoogleCloudObjectStore` but did not include the
class in `backend/filing_vault/storage.py`. This made both focused Runtime v2 and
existing repository tests fail during import. Phase 2 added the missing adapter
with:

- lazy Google Cloud imports, so non-cloud Vault tests retain their existing
  dependency boundary;
- maximum-object-size enforcement;
- content-addressed same-key verification;
- bounded get/list/delete behavior;
- required uniform bucket-level access;
- required enforced public-access prevention;
- safe classified errors without leaking provider response details.

No bucket or external storage service was contacted.

## Test and CI state

PR #37 includes a new read-only workflow, `Runtime v2 safety tests`, which:

1. checks out the PR merge ref with read-only repository permissions;
2. installs `requirements-runtime-v2.txt`;
3. compiles `runtime_v2`;
4. runs focused Runtime v2, shadow-mode, and dashboard-insight tests;
5. runs the canonical `verify.sh` safety verifier;
6. never invokes a producer, imports state, or receives a write token.

The standard `Investor Edge tests` workflow also runs for integration coverage.
The first exact-head attempt failed at test collection because the original source
omitted the GCS adapter. That defect was implemented and a succeeding Runtime v2
workflow was observed on code checkpoint
`8e842fee952f6442066a8143ceb0b4c05e5c582e`. Final completion still requires both
workflows to pass on the exact final PR head after documentation is complete.

Do not treat an earlier green run as evidence for a later head.

## Protected-state continuity

Issue #36 has not read, downloaded, uploaded, replaced, or advanced:

- `legislative-tracker-state`;
- `executive-tracker-state`;
- `ai-analysis-state`.

It has not initialized or imported Runtime v2 state, changed seen IDs, altered
transaction/filing ledgers, changed AI analyses or paper positions, changed
Investor Edge history, delivered an alert, called a heartbeat, or changed a
production dashboard.

Historical artifact identifiers copied into the old source-branch runbook are not
revalidated by this phase and are not authority for a future import. Any later
migration must obtain fresh canonical provenance and satisfy the then-current
one-writer and high-water-mark gates.

## Parallel work and exclusions

The following remain separate:

| Work | State | Treatment in issue #36 |
|---|---|---|
| PR #3 / `codex/production-remediation` | Draft | No merge or cherry-pick |
| PR #33 / `codex/score-receipts-data-quality` | Draft | No merge or cherry-pick |
| PR #35 / `codex/chatgpt-codex-phase-1-2` | Open | Separate continuity-documentation task |
| `codex/runtime-v2-integration` | Temporary staging ref | Non-authoritative; preserved, not continued |
| `codex/runtime-v2-cutover` | Original source | Preserved unchanged |

All other remote branches listed in `docs/CONSOLIDATION_INVENTORY.md` remain
untouched.

## Current gates

Phase 1–2 is complete only when all of the following are true on the exact final
PR #37 head:

- focused Runtime v2 CI passes;
- standard integration CI passes;
- GitHub reports the PR mergeable;
- project records identify the exact head and checks;
- PR #37 is ready for review but remains unmerged;
- no production, cloud, protected-state, credential, schedule, repository-setting,
  or Pages action occurred.

## Next safe action

Complete exact-head CI and review preparation for PR #37. Mark it ready for review
only after all checks pass, then stop. Do not merge or deploy.

A later explicitly authorized release phase must separately define fresh state
provenance, import acceptance, disposable and/or live shadow validation, runtime
readiness, dashboard/browser acceptance, production promotion, scheduler
activation, one-writer transfer, rollback criteria, and retention of the prior
runtime during observation.
