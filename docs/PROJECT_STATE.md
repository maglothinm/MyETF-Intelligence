# PolitiTrack project state

**Current as of:** 2026-09-02 UTC  
**Canonical repository ID:** `1349678672`  
**Current repository name:** `maglothinm/MyETF-Intelligence`  
**Default branch:** `main`  
**Active controlled work:** issue #36 / PR #37  
**Active branch:** `codex/runtime-v2-shadow-integration`  
**Target endpoint:** ready for review, unmerged, undeployed

This file records current operational truth. Historical receipts remain in
`validation/`, incident records, the append-only decision log, and Git history.

## Operational authority

Canonical `main`, its existing GitHub Actions production writers, and its retained
protected-state contracts remain operational authority. The published dashboard
and production Legislative, Executive, AI, simulation, and Filing Vault behavior
on `main` were not redeployed or replaced by issue #36.

Runtime v2 is not production authority. It has not been merged, deployed,
initialized against a live database, populated through a state import, scheduled,
used for a live collector/AI/dashboard/simulation cycle, promoted to production
mode, or used to publish Pages.

Issue #36 did not inspect or change any external cloud project, account, billing,
credential, database, bucket, service, job, or scheduler. Legacy
`maglothinm/MyETF` remains excluded.

## Beast Runtime v2 Phases 1–2

### Verified source and base

| Evidence | Value |
|---|---|
| Intake `main` | `d603e9b40ffb78c51f635589bc886875f411299b` |
| Runtime v2 source branch | `codex/runtime-v2-cutover` |
| Runtime v2 source head | `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6` |
| Source merge base | `e6d7ba5f88ec5886ae4d4bf108a5edcc4e370515` |
| Intake divergence | 7 commits ahead, 2 commits behind `main` |
| Preserved source-tree checkpoint | `7cceb9694ef7b50f71494f7c5b6baabe57520aa5` |
| Review branch | `codex/runtime-v2-shadow-integration` |
| Review | PR #37 |

The source branch remains unchanged. Its 29 committed Runtime v2 paths were copied
by exact blob identity onto a fresh branch based on verified `main`, avoiding a
merge or rebase of divergent history.

The original ChatGPT Work filesystem is unavailable. Local-only worktrees,
stashes, reflogs, staged/unstaged patches, ignored files, and untracked files from
that session are **unverified**. That limitation is not permission to deploy,
initialize, or rebaseline. The complete remote inventory is in
`docs/CONSOLIDATION_INVENTORY.md`.

### Explicit mode contract

Producer execution requires:

```text
POLITITRACK_MODE=shadow|production
```

Missing, blank, unknown, or conflicting values fail closed. The CLI resolves mode
before constructing its PostgreSQL store, and `JobRunner` validates it again.

In shadow mode:

- Legislative and Executive commands always include `--no-notify`.
- AI commands always include `--suppress-alerts`.
- legacy suppression configuration cannot opt out.
- trigger evidence is `shadow`.
- notification, callback, Healthchecks, mail, webhook, Pushover, Slack, Discord,
  Twilio, SendGrid, Mailgun, SMTP, and GitHub Actions artifact credentials/context
  are removed from subprocess environments.
- read-only analysis credentials are retained unless independently absent.
- mode is recorded in run rows, status, workflow evidence, and snapshot provenance.
- failed shadow runs are not classified as possibly having emitted external
  effects.

Explicit production mode retains intended producer command behavior and existing
explicit suppression settings. No production-mode process ran during this task.

### Durable state

The Runtime v2 migration is additive. It adds and validates `runtime_mode`,
backfills any earlier Runtime v2 run rows as production, and does not drop,
recreate, initialize, import, replace, or advance a snapshot table or head.
Database behavior in this phase is tested with source inspection and test doubles,
not a live database.

### Infrastructure source

Terraform defaults producer environment to shadow and schedules to disabled. A
Terraform check rejects enabled schedules unless mode is explicitly production.
The mode is a non-secret control and cannot be supplied through the secret map.
No Terraform, image build, cloud API, runtime, scheduler, or import action was
executed.

### Filing Vault reconciliation

The preserved source imported `GoogleCloudObjectStore` but did not include that
class. This caused both focused Runtime v2 and standard repository CI to fail at
collection. PR #37 implements the missing adapter with lazy Google Cloud imports,
bounded object operations, content-addressed same-key verification, safe classified
errors, and required uniform bucket-level access plus enforced public-access
prevention. No external bucket was contacted.

## CI and review evidence

PR #37 adds a read-only `Runtime v2 safety tests` workflow. It installs
`requirements-runtime-v2.txt`, compiles the package, runs focused Runtime v2,
shadow-mode, and dashboard-insight tests, and runs `verify.sh`. It invokes no
producer and receives read-only repository permissions.

The normal `Investor Edge tests` workflow provides broader integration coverage.
The initial failure exposed the missing GCS adapter and was corrected rather than
retried unchanged.

Checkpoint `1de2298bf1fbb0afcc772c6aedd82a6d4f9f4398` passed both required workflows:

| Workflow | Run | Conclusion |
|---|---:|---|
| Runtime v2 safety tests | `33638954917` | success |
| Investor Edge tests | `33638955190` | success |

GitHub reported PR #37 mergeable against `main` at that checkpoint. It contains
all executable, infrastructure, test, inventory, cutover-guide, project-state, and
decision-log changes through D-041.

The final handoff and this state update are documentation-only successors. Their
exact final head must pass both workflows before the PR leaves draft. PR #37 checks
and metadata identify the exact final SHA because a tracked file cannot contain
its own future commit SHA.

## Protected-state continuity

Issue #36 did not read, download, upload, replace, or advance:

- `legislative-tracker-state`;
- `executive-tracker-state`;
- `ai-analysis-state`.

It did not change seen IDs, ledgers, analyses, paper positions, alerts, Investor
Edge history, health callbacks, or a production dashboard. Historical artifact
identifiers in the original source runbook were not revalidated and are not future
migration authority. A later import requires fresh canonical provenance and the
then-current one-writer/high-water-mark gates.

## Parallel work

| Work | State | Treatment in issue #36 |
|---|---|---|
| PR #3 / `codex/production-remediation` | Draft | No merge or cherry-pick |
| PR #33 / `codex/score-receipts-data-quality` | Draft | No merge or cherry-pick |
| PR #35 / `codex/chatgpt-codex-phase-1-2` | Open | Separate documentation task |
| `codex/runtime-v2-integration` | Temporary staging ref | Non-authoritative; preserved only |
| `codex/runtime-v2-cutover` | Original source | Preserved unchanged |

All other branches listed in `docs/CONSOLIDATION_INVENTORY.md` remain untouched.

## Completion gate

Phases 1–2 end only when both workflows succeed on the final documentation-only
PR head, GitHub still reports mergeable, and PR #37 is marked ready for review but
remains unmerged. No production/cloud/state/credential/schedule/settings/Pages
action may occur.

## Next safe action

Validate the final documentation-only head, record its SHA and run IDs in issue
#36 and PR #37 metadata, mark PR #37 ready for review, then stop.

Fresh state provenance, isolated or live shadow acceptance, runtime/browser
acceptance, production promotion, schedule activation, one-writer transfer,
rollback drills, and retirement of the current GitHub production path require a
later explicitly authorized release phase.
