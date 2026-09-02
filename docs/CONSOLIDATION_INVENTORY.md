# Runtime v2 Consolidation Inventory

**Recorded:** 2026-09-02  
**Issue:** #36  
**Pull request:** #37  
**Canonical repository ID:** `1349678672`  
**Canonical repository at intake:** `maglothinm/MyETF-Intelligence`  
**Default branch:** `main`

## Recovery boundary

This inventory is based on live GitHub evidence from the canonical repository. The original ChatGPT Work filesystem was not available in the current execution environment. Consequently, local-only worktrees, stashes, reflogs, staged or unstaged patches, ignored files, and untracked files from that Work session are **not verified** and are not represented as recovered.

That uncertainty does not authorize a production action. All remotely committed refs were left intact, no branch was deleted or rewritten, and the consolidation uses only GitHub-addressable commits and blobs.

## Verified source and base

| Item | Verified value | Classification |
|---|---|---|
| Intake `main` | `d603e9b40ffb78c51f635589bc886875f411299b` | Fresh integration base |
| Runtime v2 source branch | `codex/runtime-v2-cutover` | Preserved source; unchanged |
| Runtime v2 source head | `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6` | Committed recovery authority |
| Source merge base | `e6d7ba5f88ec5886ae4d4bf108a5edcc4e370515` | Divergence anchor |
| Source divergence at intake | 7 commits ahead, 2 commits behind `main` | Do not merge/rebase source branch |
| Preserved source-tree checkpoint | `7cceb9694ef7b50f71494f7c5b6baabe57520aa5` | Squash-style content preservation on fresh ancestry |
| Working branch | `codex/runtime-v2-shadow-integration` | Phase 1-2 implementation branch |
| Dedicated PR | #37 | Draft, unmerged, undeployed |
| Temporary staging ref | `codex/runtime-v2-integration` | Non-authoritative; retained only to avoid deleting evidence |

The working branch was created from the verified intake `main`, not from the divergent source branch. The committed Runtime v2 file content was copied by exact blob identity, preserving the source branch and avoiding an implicit merge of its history.

## Exact committed Runtime v2 source set

The following 29 paths were preserved from source head `62a13eaa8ae5ac46046c992aedd42bc4816e2ce6`:

```text
.gcloudignore
backend/filing_vault/__init__.py
backend/filing_vault/__main__.py
deploy/runtime-v2/Dockerfile
deploy/runtime-v2/bootstrap.ps1
deploy/runtime-v2/cloudbuild.yaml
deploy/runtime-v2/terraform/.terraform.lock.hcl
deploy/runtime-v2/terraform/main.tf
deploy/runtime-v2/terraform/outputs.tf
deploy/runtime-v2/terraform/terraform.tfvars.example
deploy/runtime-v2/terraform/variables.tf
deploy/runtime-v2/terraform/versions.tf
docs/DECISIONS.md
docs/HANDOFF.md
docs/PROJECT_STATE.md
docs/RUNTIME_V2_CUTOVER.md
migrations/20260901_runtime_v2.sql
requirements-runtime-v2.txt
runtime_v2/__init__.py
runtime_v2/__main__.py
runtime_v2/archive.py
runtime_v2/cli.py
runtime_v2/database.py
runtime_v2/runner.py
runtime_v2/store.py
runtime_v2/web.py
scripts/dashboard_insights.py
tests/test_dashboard_insights.py
tests/test_runtime_v2.py
```

Phase 2 then added the mode contract, shadow-mode tests, Terraform schedule gate, focused CI, and this inventory as new integration work.

## Complete remote branch inventory

GitHub returned 31 remote branches at inventory time.

### Canonical and Runtime v2 branches

| Branch | Classification | Action |
|---|---|---|
| `main` | Canonical deployed authority | Read-only base for this task |
| `codex/runtime-v2-cutover` | Original committed Runtime v2 source | Preserved; do not merge/rebase/delete |
| `codex/runtime-v2-shadow-integration` | Current Phase 1-2 implementation | PR #37; keep unmerged pending gates |
| `codex/runtime-v2-integration` | Temporary staging ref | Non-authoritative; no PR; do not continue from it |

### Parallel branches with separate open PR gates

| Branch | PR | State at inventory | Consolidation treatment |
|---|---:|---|---|
| `codex/production-remediation` | #3 | Draft, unmerged | Held separately; no merge/cherry-pick |
| `codex/score-receipts-data-quality` | #33 | Draft, unmerged | Held separately; no merge/cherry-pick |
| `codex/chatgpt-codex-phase-1-2` | #35 | Open, unmerged | Separate continuity-documentation task |

### Other preserved remote branches

```text
codex/acknowledgement-brief-consistency
codex/brief-cache-compatibility
codex/contextual-help
codex/dashboard-redesign
codex/dashboard-review-ux
codex/filing-vault
codex/fix-freshness-redaction
codex/freshness-clock-audit
codex/investor-edge-bootstrap
codex/investor-edge-current-architecture
codex/investor-edge-integration
codex/manual-review-acknowledgement
codex/neutral-zero-attention
codex/operations-history-order
codex/persistent-shell-layout
codex/polititrack-icon-assets
codex/polititrack-rebrand
codex/record-brief-consistency-release
codex/record-freshness-release
codex/record-manual-review-release
codex/record-neutral-zero-release
codex/scheduler-freshness
codex/scheduler-release-receipt
codex/senate-efd-resilience
```

No branch outside #37 was modified by the implementation.

## Phase 2 safety controls

The integration branch introduces these centrally enforced controls:

- `POLITITRACK_MODE` is mandatory for producer execution and accepts only `shadow` or `production`.
- Mode resolution occurs before construction of the PostgreSQL store, so a missing or invalid value fails before producer or durable-state initialization.
- `JobRunner` independently validates the mode and rejects a conflicting explicit/environment declaration.
- Shadow tracker commands always include `--no-notify` for both Legislative and Executive jobs.
- Shadow AI commands always include `--suppress-alerts`, even if legacy suppression configuration is absent or false.
- Shadow subprocess environments remove GitHub Actions artifact credentials/context and external-delivery variables associated with Healthchecks, callbacks, webhooks, Pushover, Gmail/SMTP, SendGrid, Mailgun, Twilio, Slack, and Discord.
- Read-only analysis credentials such as OpenAI and market-data keys are not removed merely because the runtime is shadowed.
- Shadow trigger evidence is normalized to `shadow`.
- Runtime mode is recorded in `runtime_job_runs`, snapshot provenance, status output, and workflow evidence.
- The database migration is additive and backfills any pre-existing Runtime v2 run rows as `production`; it does not drop or recreate state tables or heads.
- Terraform producer environment defaults to `POLITITRACK_MODE=shadow`.
- Terraform rejects enabled schedules unless mode is explicitly `production`; schedules remain disabled by default.
- Dedicated Runtime v2 pull-request CI compiles the package, runs synthetic focused tests, and runs `verify.sh` without producer invocation.

## Protected-state and production boundary

During Phases 1-2, none of the following occurred:

- no read, download, upload, replacement, or advancement of `legislative-tracker-state`, `executive-tracker-state`, or `ai-analysis-state`;
- no database initialization, state import, rebaseline, or live PostgreSQL snapshot write;
- no collector, AI analyst, dashboard builder, simulation, or alert dispatch against live services;
- no Healthchecks callback or notification test;
- no Terraform apply, cloud image build/push, Cloud Run invocation, scheduler activation, or GitHub Pages publication;
- no secret, credential, repository setting, or access-control change;
- no merge to `main` and no use of legacy `maglothinm/MyETF`.

## Required next action

Complete PR #37 CI and review only. When the exact current head is green and the PR is review-ready, stop with the PR unmerged. A later, separately authorized release must define and verify state import, disposable/live shadow acceptance, dashboard/access validation, production-mode promotion, schedule activation, and rollback criteria.
