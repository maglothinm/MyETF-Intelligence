# Collector freshness and scheduler reliability

Work record: [issue #19](https://github.com/maglothinm/MyETF-Intelligence/issues/19).
Repository ID **1349678672** is authoritative; its current name is
`maglothinm/MyETF-Intelligence`. This document separates implementation from
external activation and measured production cadence.

## Root cause recorded before behavior changes

The production path is the existing collector workflow, provenance-validated
protected artifact restore, collector, successful protected-state upload, then
the AI and read-only Pages workflows. Legislative was configured at
`7,22,37,52 * * * *`; Executive was configured at `13 * * * *` (hourly).
The AI analyst follows successful collector `workflow_run` events and also has
manual dispatch. It does not have an independent production cron.

`government_trade_tracker.py` writes `runs.jsonl` with collector `started_utc`
and `finished_utc`, success/errors, event and a run link. These are collector
timestamps, not workflow start. AI history follows the same distinction.
Only successful producers upload protected artifacts; a failed attempt may never
appear in that retained history. Legislative incomplete discovery deliberately
leaves its protected history unchanged. Previously Pages ran only on successful
upstream completion, so it could miss failures as well as missing executions.

`dashboard_insights._health` selected the latest retained conclusion and computed
age, but exposed no cadence or freshness threshold. Its overall aggregation only
understood failure, success and unknown. Tests explicitly accepted old successes.
The shared frontend already styled a `stale` state but had no policy that could
produce it. The header rendered **Latest runs successful** directly from this
historical conclusion. Open pages did not age health independently of publication.

The compact model derived its timestamp from retained evidence, including AI and
portfolio updates. The older summary also fell back to dashboard generation time
when source evidence was absent. Neither was a reliable definition of source
collector currency. Publication can succeed while collection is materially late.

A fresh read-only audit at **2026-08-31 17:03 UTC** verified newer protected
successors than the previous documentation checkpoint. Legislative starts were
07:43:30 and 15:31:59 UTC (**468.5 minutes apart**); Executive starts were
05:27:57 and 13:41:44 UTC (**493.8 minutes apart**). Latest successful producer
jobs completed at 15:32:59 and 13:44:00 respectively. These measured gaps support
independent scheduling; successful jobs do not prove timely cron delivery.

The audit validated exact producer attempts/jobs, repository identity, commit
ancestry, global producer high-water marks, expiry, ZIP digests, complete state
inventory and continuity. The approved historical bootstrap produced a new
`historical-backfill.jsonl`; it was validated against its published receipt schema,
not discarded as an unknown file or treated as a reason to reset state.

## Freshness contract

| Worker | Expected opportunity | Stale after successful completion |
|---|---|---|
| Legislative | 15 minutes | More than 30 minutes |
| Executive / OGE | 30 minutes | More than 60 minutes |
| AI analyst | Collector completion, nominally every 15 minutes | More than 75 minutes |

The central Python policy is `scripts/collector_freshness.py`. AI's conservative
75-minute bound is the 30-minute Legislative freshness window plus the analyst's
45-minute job limit. It is not an independent AI schedule and never overrides
stale collector inputs. Browser aging consumes this published policy; it does not
hard-code a second set of thresholds or dispatch jobs.

Health precedence is **failure > stale > unknown > success**. A latest failed
attempt outranks a previous recent success. Success requires explicit successful
execution evidence and a valid, sufficiently recent completion timestamp.
Missing or malformed evidence remains unknown. A successful but expired check is
stale. Synthetic, TEST, simulation and publication records cannot refresh a
production collector. No missed run records are invented.

The header uses **Monitoring current**, a branch-specific failure/overdue warning,
or **Monitoring status incomplete**. **Source data through** uses retained
production source observations and collector completion, never a page build,
AI analysis or portfolio refresh. Generation time is separate in Operations.
This timestamp is the newest represented source evidence, not a guarantee that
every branch is current; the health indicator and branch details supply that test.

Operations retains newest-first history and exposes attempt/success timestamps,
cadence, next expected check, age, overdue duration, estimated missed intervals,
latest conclusion, errors, run link and safe trigger source. Estimated missed
intervals describe absent successful checks; they do not assert whether GitHub
dropped a trigger, a queue delayed execution, or a collector ran unsuccessfully.

## Rollout and remaining activation

1. Implement and test the model, presentation, dispatch contract and Executive
   `13,43 * * * *` schedule on the canonical branch.
2. Require successful PR CI, merge and verify the actual Pages artifact/live
   content against current protected inputs. Do not use production dispatch as a
   fixture generator.
3. Provision the independent scheduler only with legitimate account access and a
   narrowly scoped Actions-write secret stored server-side. Follow
   [the scheduler deployment guide](EXTERNAL_SCHEDULER.md). Verify several actual
   dispatch cycles, exact producer attempts, continued state/alert deduplication,
   AI propagation and Pages source advancement.
4. Retain GitHub cron while external delivery is unverified. Any later decision to
   disable cron requires an explicit recorded activation decision and rollback.

External scheduling is **not activated by merely committing Worker code**. An
accepted dispatch is not proof that a collector started, completed or published
state. Collector freshness remains authoritative; there is no invented scheduler
alive indicator. Existing obsolete-writer clearance and production recovery gates
remain in force. A stale successful dashboard is evidence of an unresolved
operational problem even after the health presentation is fixed.

Rollback reverts reviewed code on current main while consuming the newest valid
artifacts. It never restores an older state snapshot, initializes a baseline,
revives the retired overlay or writes simulation state into production.
