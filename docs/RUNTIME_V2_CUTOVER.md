# PolitiTrack Runtime v2 — staged consolidation and later cutover

Runtime v2 is a proposed replacement for GitHub Actions scheduling and protected
artifact delivery in the operational path. It reuses the existing collectors,
AI analyst, dashboard builder, and Filing Vault service while adding independent
scheduling, PostgreSQL immutable snapshots, advisory locks, and private Google
Cloud Storage.

**Current status:** source integration only. Issue #36 / PR #37 implements Beast
Phases 1–2. Runtime v2 is not merged, deployed, initialized, imported, scheduled,
or production-authoritative. Canonical `main` and its existing GitHub Actions
contracts remain authoritative.

## Current architecture proposal

| Concern | Proposed Runtime v2 authority |
|---|---|
| Scheduling | Cloud Scheduler invokes dedicated Cloud Run jobs |
| Single-writer coordination | PostgreSQL advisory lock per namespace |
| Collector/AI state | Immutable hashed PostgreSQL generations |
| Publication guard | Compare-and-swap against the restored parent hash |
| Dashboard serving | Cloud Run service restores the latest accepted dashboard snapshot |
| Filing Vault objects | Private GCS bucket with uniform access and public-access prevention |
| Migration evidence | Fresh canonical provenance receipt plus retained immutable input |

The proposed producer order is Legislative, Executive, AI, then dashboard. A
successful job advances one immutable generation. Failed or overlapping jobs do
not replace an accepted head.

## Mandatory operational mode

Every Runtime v2 producer requires one explicit mode:

```text
POLITITRACK_MODE=shadow
POLITITRACK_MODE=production
```

Missing, blank, unknown, or conflicting values fail closed before producer
execution. Mode is recorded in run rows, status output, workflow evidence, and
snapshot provenance.

### Shadow mode

Shadow mode is the only mode permitted for pre-release acceptance work. It forces:

- `--no-notify` on Legislative and Executive tracker commands;
- `--suppress-alerts` on AI analyst commands;
- a `shadow` trigger source in retained evidence;
- removal of external-delivery, Healthchecks, callback, webhook, mail, Pushover,
  and GitHub Actions artifact credentials/context from subprocess environments;
- `side_effects_possible=false` for failed shadow runs.

Shadow mode does **not** by itself authorize a live run. Phase 1–2 validation uses
synthetic tests and source inspection only. A later release must identify a
disposable or explicitly approved live database/storage boundary before invoking
any producer.

### Production mode

Production mode preserves intended producer behavior. Existing explicit
notification and alert suppression remains available. Changing a deployed runtime
to production, importing canonical state, enabling schedules, or transferring the
single-writer role requires a separate release authorization and acceptance
receipt.

## Infrastructure defaults

Terraform defaults producer containers to:

```hcl
runtime_environment = {
  POLITITRACK_MODE = "shadow"
}

schedules_enabled = false
```

Terraform rejects enabled schedules unless mode is explicitly `production`. The
mode is a non-secret control and cannot be supplied through the secret map.

These definitions are reviewable source. They are not evidence that a project,
image, database, bucket, secret, job, service, or scheduler exists.

## State migration policy

Do not reuse artifact identifiers or local receipts copied into the original
Runtime v2 source branch as future authority. They describe an earlier snapshot
of production and were not revalidated during Phases 1–2.

A later migration must create a fresh receipt for each protected namespace and
bind all of the following:

1. canonical repository ID `1349678672` and then-current repository name;
2. expected workflow path and authoritative producer job;
3. exact successful run and attempt;
4. exact artifact ID, size, digest, and archive SHA-256;
5. default branch and producer head SHA;
6. producer ancestry and high-water-mark checks;
7. artifact creation within the successful attempt window;
8. retained successful-state marker and complete required inventory.

The import path accepts only Legislative, Executive, and AI canonical artifacts.
It cannot replace an existing Runtime v2 head. Initial import is explicit; a
missing head never grants permission to initialize blank state.

The Runtime v2 SQL migration is additive. It must be applied without dropping or
recreating existing snapshot/head tables. Historical Runtime v2 run rows are
classified as production when the new mode column is introduced.

## Staged release plan

### Phase 1 — recovery and inventory

Completed in PR #37 source history:

- identify canonical base and all discoverable remote refs;
- preserve the 29 committed source paths from `codex/runtime-v2-cutover` without
  changing that branch;
- record exact source/base/head SHAs and divergence;
- classify parallel PRs and branches;
- explicitly identify original Work-only state as unverified when the filesystem
  is unavailable;
- perform no production or cloud action.

See `docs/CONSOLIDATION_INVENTORY.md`.

### Phase 2 — shadow-safe source integration

Implemented for review in PR #37:

- fail-closed mode contract;
- central shadow command/environment enforcement;
- durable mode evidence;
- additive schema changes;
- missing private GCS Vault adapter;
- Terraform shadow defaults and schedule gate;
- focused read-only pull-request CI and synthetic tests;
- no merge, deployment, import, or live producer invocation.

The required endpoint is a green, mergeable, ready-for-review PR that remains
unmerged.

### Phase 3 — isolated runtime provisioning and state acceptance

Not authorized by issue #36. A future release should, at minimum:

1. identify the approved cloud project and access boundary;
2. review the Terraform plan with schedules disabled and shadow mode explicit;
3. build an immutable image and record its digest;
4. provision private database/storage with least-privilege identities;
5. verify the GCS Vault bucket's uniform access and enforced public-access
   prevention;
6. apply the additive schema without initializing protected state;
7. create fresh canonical migration receipts;
8. import Legislative, Executive, and AI as generation 1 exactly once;
9. confirm each imported inventory/hash against its receipt;
10. build a first dashboard snapshot without external publication;
11. record readiness and rollback evidence.

No schedule or production mode belongs in this phase.

### Phase 4 — controlled shadow acceptance

Not authorized by issue #36. A future release must define whether shadow jobs use
an isolated disposable database copied from accepted inputs or an approved
parallel Runtime v2 database. It must prove:

- no external alert, email, Pushover, webhook, callback, or Healthchecks delivery;
- no protected GitHub Actions artifact operation;
- no GitHub Pages publication;
- expected generation transitions only;
- correct Legislative, Executive, AI, and dashboard ordering;
- no overlap or lock violation;
- retained IDs, ledgers, analyses, positions, and history remain internally
  consistent;
- dashboard/browser behavior is accepted against the shadow outputs;
- all failures are classified without advancing an invalid head.

### Phase 5 — production promotion

Not authorized by issue #36. Promotion requires a separate written decision and
release receipt. At minimum:

1. resolve every existing production-writer and obsolete-run gate;
2. verify the final canonical GitHub artifacts and Runtime v2 shadow heads;
3. choose one authoritative cutover instant;
4. explicitly set `POLITITRACK_MODE=production`;
5. enable Runtime v2 schedules only after the mode change is reviewed;
6. prevent simultaneous production writes from GitHub Actions and Runtime v2;
7. observe several successful real intervals across all producers;
8. validate alert delivery separately from state publication;
9. validate dashboard freshness and physical/browser acceptance;
10. record the exact rollback trigger and retained prior-runtime window;
11. disable the former GitHub producer schedules only after acceptance.

## Rollback policy

Rollback pauses Runtime v2 schedules and preserves its PostgreSQL database,
immutable snapshots, private buckets, image digest, logs, and receipts for
diagnosis. It does not:

- replace a newer accepted state with an older artifact;
- initialize blank state;
- revive a retired or obsolete writer;
- run GitHub and Runtime v2 as simultaneous production authorities;
- delete evidence merely to make a later attempt appear clean.

The prior GitHub production path remains available until a later release records
that Runtime v2 has passed the complete production observation window.

## Current prohibition

For PR #37, do not run the bootstrap script, Terraform, Cloud Build, Cloud Run,
Cloud Scheduler, database initialization, state import, collectors, AI analyst,
dashboard publisher, simulation, alert delivery, Healthchecks, Pages, secret
changes, repository-setting changes, or protected-artifact operations. Finish
exact-head CI and review preparation, then stop with the PR unmerged.
