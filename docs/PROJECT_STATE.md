# PolitiTrack project state

**Current as of:** 2026-09-02 UTC  
**Canonical repository ID:** `1349678672`  
**Current repository name:** `maglothinm/MyETF-Intelligence`  
**Default branch:** `main`  
**Active controlled work:** issue #36 / PR #38  
**Active branch:** `codex/runtime-v2-shadow-review`  
**Target endpoint:** open for review, unmerged, undeployed

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

## Active review transition

Draft PR #37 reached exact green, mergeable head
`8b16436e14862ad7abcdf94dc7272f437f88b091`. The GitHub connector's
ready-for-review mutation failed because its GraphQL response requested an
unsupported repository field. PR #37 was closed without merge.

PR #38 was opened non-draft from the same exact tree on
`codex/runtime-v2-shadow-review`. It is the active review. The transition did not
change executable source or operational state; the continuity updates following
the branch copy are documentation-only.

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
| Active review branch | `codex/runtime-v2-shadow-review` |
| Active review | PR #38, non-draft |

The source branch remains unchanged. Its 29 committed Runtime v2 paths were copied
by exact blob identity onto fresh verified `main` ancestry, avoiding a merge or
rebase of divergent history.

The original ChatGPT Work filesystem is unavailable. Local-only worktrees,
stashes, reflogs, staged/unstaged patches, ignored files, and untracked files from
that session are **unverified**. That limitation is not permission to deploy,
initialize, or rebaseline. The remote inventory is in
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
class. This caused focused Runtime v2 and standard repository CI to fail at
collection. The active review implements the missing adapter with lazy Google
Cloud imports, bounded object operations, content-addressed same-key verification,
safe classified errors, and required uniform bucket-level access plus enforced
public-access prevention. No external bucket was contacted.

## CI and review evidence

PR #38 contains the read-only `Runtime v2 safety tests` workflow. It installs
`requirements-runtime-v2.txt`, compiles the package, runs focused Runtime v2,
shadow-mode, and dashboard-insight tests, and runs `verify.sh`. It invokes no
producer and receives read-only repository permissions.

The standard `Investor Edge tests` workflow provides broader integration coverage.
The initial failure exposed the missing GCS adapter and was corrected rather than
retried unchanged.

Executable-tree checkpoint `8b16436e14862ad7abcdf94dc7272f437f88b091`
passed:

| Workflow | Run | Conclusion |
|---|---:|---|
| Runtime v2 safety tests | `33639231223` | success |
| Investor Edge tests | `33639231236` | success |

GitHub reported that exact tree mergeable against `main`. PR #37 retained those
results and was closed unmerged solely because the connector could not clear its
draft flag. PR #38 began from the identical head.

The active continuity updates are documentation-only successors and require both
workflows on the exact final PR #38 head. PR checks and metadata identify that
future final SHA because a tracked file cannot contain its own commit ID.

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

## Parallel and retained work

| Work | State | Treatment in issue #36 |
|---|---|---|
| PR #3 / `codex/production-remediation` | Draft | No merge or cherry-pick |
| PR #33 / `codex/score-receipts-data-quality` | Draft | No merge or cherry-pick |
| PR #35 / `codex/chatgpt-codex-phase-1-2` | Open | Separate continuity task |
| PR #37 / `codex/runtime-v2-shadow-integration` | Closed, unmerged | Green predecessor retained as evidence |
| PR #38 / `codex/runtime-v2-shadow-review` | Open, non-draft | Active review; do not merge in this phase |
| `codex/runtime-v2-integration` | Temporary staging ref | Non-authoritative; preserved only |
| `codex/runtime-v2-cutover` | Original source | Preserved unchanged |

All other branches listed in `docs/CONSOLIDATION_INVENTORY.md` remain untouched.

## Completion gate

Phases 1–2 end only when both workflows succeed on the final PR #38 head, GitHub
reports it mergeable, and PR #38 remains open, non-draft, unmerged, and undeployed.
No production, cloud, state, credential, schedule, settings, or Pages action may
occur.

## Next safe action

Validate the final documentation-only PR #38 head, record its exact SHA and run
IDs in issue/PR metadata, reconfirm mergeability, and stop.

Fresh state provenance, isolated or live shadow acceptance, runtime/browser
acceptance, production promotion, schedule activation, one-writer transfer,
rollback drills, and retirement of the current GitHub production path require a
later explicitly authorized release phase.
