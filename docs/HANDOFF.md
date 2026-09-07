# PolitiTrack active handoff

Updated: **2026-09-06 21:03 UTC**

Canonical repository: **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Current Opportunity implementation branch — not deployed

Issue #153 / branch `codex/current-opportunity-v1` implements Current Opportunity
v1 from main `061b8a4dda7f6c0940e8d3f92c6aed3dbb957f0f`. Defaults remain **off**.
The feature uses the hardened analyst and existing Runtime v2 AI snapshot owner;
no scheduler, production job, notification, paper-trading contract or live head
was changed in this task. The recovery receipt below remains historical evidence,
not certification of this feature. See [feature/runbook](CURRENT_OPPORTUNITY.md)
and [requirement-to-test mapping](validation/current-opportunity-v1.md).

The branch includes offline regression/fixture validation and gated live delivery
tested with fakes. Production provider entitlement, mapping/coverage and latency
verification, deployed shadow observation, and live activation each require the
separate approval and evidence gates in that runbook. Preserve the additive
namespace on rollback; do not reset state or re-enable legacy producers.

## Completed task

Runtime v2 / AI Analyst production recovery is certified. PR #151 corrected the natural-certification Dashboard timezone assertion and delayed-log window, merging as `db080d413b5e804a335f575071a62d48a9d4083b`. The existing controller passed on canonical main: run `34059488724`, attempt 1, job `101557337973`, all steps successful including temporary-authority cleanup.

Recovery artifact: `9997087643`; archive SHA-256 `6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`. Result: `runtime_v2_natural_ai_schedule_certified`. Both internal evidence hashes match. The certificate binds AI executions `polititrack-ai-rss97` and `polititrack-ai-db5vt`, followed by Dashboard execution `polititrack-dashboard-vl4p6`; independent GCP reads confirmed their Scheduler identity and approved immutable image.

Runtime source: `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`.
Image digest: `sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`.
Certified heads: Legislative 82, Executive 46, AI 70, Dashboard 79.

The original Phase 5 transfer is separately proven by successful run `34005780266`, artifact `9981508660`, archive SHA-256 `c5094a1677712e413425e118f29dd0fc1f870c5bc712879fbc2223f2b9c2f7d0`, and the verified `phase5-complete.json` checksum. Do not mistake that original-image certificate for the recovery certificate.

## Terminal boundary

Four producer schedulers enabled; Filing Vault paused; private-only Cloud SQL; legacy producer workflows retained and disabled; repaired immutable runtime; public `/readyz` ready and `/` HTTP 200 with the certified Dashboard snapshot. Temporary observation execution/logging permissions were removed. Pre-existing permanent deployer roles were preserved.

No state reset, rewind, rebaseline, alternate writer, replatform, or Phase 6 action was performed. Existing legacy artifacts and recovery evidence remain retained.

## Verification and remaining scope

Workflow YAML, all four embedded Bash scripts, embedded Python syntax, 14 Phase 5 tests, and repository `verify.sh` passed locally. One POSIX-specific test was skipped on Windows; the canonical live certification then passed all steps. No credential or external approval was needed.

Older status-mirror/recoverywatch runs predate this task and watch the obsolete initial recovery workflow/event. They are not certification authority. No new monitor or retry was created. Phase 5 issue #100 and historical issue administration were not changed by this task.

Next safe action: use the successful recovery run and artifact as the current receipt; retain the existing production schedules. Phase 6 decommissioning, rebaseline, and new notification guarantees require separately scoped work.
