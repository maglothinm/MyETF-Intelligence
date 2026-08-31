# Scheduler freshness release evidence — 2026-08-31

Work: [issue #19](https://github.com/maglothinm/MyETF-Intelligence/issues/19).
Canonical repository ID **1349678672**, current name
**maglothinm/MyETF-Intelligence**, default branch **main**.

## Delivery state

[PR #20](https://github.com/maglothinm/MyETF-Intelligence/pull/20) merged tested
head `c9dd3a5e129f41207ffbc7ce4278e9d0cf5d4692` as
`b9380f231d09eb8610a96c6d4c83399ace67b008`. Their trees match exactly.
The first freshness deployment passed full artifact and live-content verification.
A subsequent fixed-clock audit confirmed another edge case: a fresh publication
could stop aging when the device clock was far behind the server. A follow-up
clock fix passes 65 DOM and 42 native JS tests, including late publications after
page suspension; CI/deployment are pending. Its final receipt follows below when
deployed. External scheduling is **inactive**, not provisioned by this code.

## Root cause and capability

Historical successful conclusions had no freshness SLA. Open pages did not age
health; failed attempts could be absent from successful protected-state history;
AI/portfolio updates could advance an ambiguous source timestamp. Recorded latest
collector gaps were 468.5 minutes for Legislative and 493.8 for Executive.

Central policy: Legislative expected 15 / stale >30 minutes; Executive 30 / >60;
AI follows collector success with >75 minutes (30-minute collector window plus
45-minute analyst timeout). Failure > stale > unknown > success. A recent AI run
cannot make stale collector inputs healthy. No artificial missed-run rows exist.

Header, Operations and Monitor Mode distinguish current, stale, failure and
unknown. Operations exposes last attempt/success, cadence, next expected run,
age, overdue duration, estimated missing successful checks, errors, run links
and safe trigger labels. Source data through excludes build and AI refresh time.
Failed/pending Actions observations remain read-only and cannot advance source
currency or protected state. Exact job execution order handles queued reruns.

Legislative cron remains `7,22,37,52 * * * *`; Executive is now
`13,43 * * * *`, with the existing America/New_York schedule timezone retained.
The disabled external example targets minutes 5/20/35/50 and 11/41 UTC through
canonical authenticated workflow_dispatch. Manual dispatch remains available.
The three fixed noncancelling concurrency groups, restore/high-water checks and
filing/analysis/delivery deduplication remain. A new guard blocks a retry if an
unretained attempt may already have caused side effects. This stops ambiguous
retries; it does not promise transactional exactly-once external delivery.

## Local and CI verification

Full local pytest: **633 passed, no skips, 131.00 seconds**. This includes generated
dashboard, Vault and PDF fixtures. Independently, 63 dashboard DOM cases,
35 native UI cases and 11 Worker cases passed. Workflow YAML, JavaScript syntax,
diff checks and unchanged local preview input member hashes passed.

The first PR CI run `33420173749` failed because the Linux verifier still
required Executive's old hourly cron. Its expected schedule and deterministic
verifier checksum were updated; all artifact/simulation/retired-overlay safety
assertions remain in place. No test was weakened or waived.

| CI | Exact run / attempt | Job | Result |
|---|---|---|---|
| PR source | `33420373213` / 1 | `99580987977` | 550 Python; 6 filing DOM; 11 Worker; repository verifier passed |
| Merged main | `33420549112` / 1 | `99581556586` | 550 Python; 6 filing DOM; 11 Worker; repository verifier passed |

Read-only live observer/guard integration at 17:26 UTC made 53 API reads. All
three branches were available, exact attempts/jobs matched protected producers,
and the retry guard allowed each clean current authority. No dispatch occurred.

## First Pages deployment and live result

[Pages run 33420549071](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33420549071)
/ attempt 1 succeeded; build job `99581557155`, deploy job `99581861414`.
Pages artifact **9768730400**, SHA-256
`7b2e3a3c0a436a7f1efbb36d3b565e18cc57c6a76ceb936b3b3ea9a7b33b0d55`.
Source is merge `b9380f2`; deployment completed at 17:38:22 UTC.
All **250 served content files** matched the archived bytes in the 17:39:21 UTC
audit. The source repository and numeric identity were checked independently.

The published model generated at **17:38:02 UTC** is overall **stale**, with
all three workers stale. Last successful collector completion is **15:32:55 UTC**
for Legislative and **13:43:54 UTC** for Executive; AI completed **15:33:54 UTC**.
Source data through remains **15:32:55 UTC**, not the new build time. Workflow
evidence was available for all branches. The live header displays
**Legislative polling overdue** and **Source data through Aug 31, 11:32 AM**
in the checked America/New_York browser. This directly reproduces and corrects
the old green-success failure against unchanged retained production data.

Preview desktop and 320px/390px portrait checks passed: readable status/Operations,
no horizontal page overflow, preserved sticky header and seven Workspace links.
Monitor Mode also shows stale and the same source timestamp. Browser checks found
no warnings/errors. These are rendered checks, not physical-device acceptance.

## Protected-state continuity

Exact Pages build logs confirm the following restored inputs. Independently
validated repository/default branch, workflow name/path, successful producing
attempt/job, ancestry, high-water mark, unexpired archive digest, complete member
inventory and predecessor continuity all passed. Inputs are unchanged between
preflight and first postflight; no producer advanced during the rollout.

| Pipeline | Artifact | Producer run / attempt | Job | ZIP SHA-256 |
|---|---|---|---|---|
| Ai | `9764387095` | `33409079174` / 1 | `99543844689` | `4ce53ab46300fd53999c8c23539197a2bb916fed1f6c1101adb34c7c6713cc86` |
| Executive | `9760298853` | `33398375467` / 1 | `99508337018` | `e4c95a6829fef8c431bb7f574d6cda9af585f887157d6b2bd8dcefeccb18a4e0` |
| Legislative | `9764350004` | `33408974583` / 1 | `99543508327` | `666303ed7c1dc88d2404a9048b45a75276f927ef0c595713e981d393bc8cc228` |

Counts remain: Legislative 1,001 filings, 183 transactions, 73 purchases,
1 review, 32 run rows and 20 historical receipts; Executive 4,109 filings,
1,495 reviews and 24 runs; AI 12 analyses and 38 runs. The approved bootstrap
receipt schema was explicitly validated; it was not ignored or reset.

Simulator `9734790733`, producer `33320677882` / attempt 1, retains two rows
byte-for-byte. The older historical simulator concern remains separate. Neither
simulation workflow changed; neither receives a new production writer or real
alert credential. No production writer, simulation, alert test, rebaseline,
credential or repository setting was manually dispatched/changed.

## Outstanding infrastructure and acceptance limits

No post-release collector has yet established the intended 15/30-minute cadence.
At the 17:39 UTC audit, the latest collector runs were still `33408974583`
(Legislative), `33398375467` (Executive), and `33409079174` (AI), all attempt 1.
Hours-long GitHub schedule gaps persist. A fixture proves fresh success clears
stale, and failure outranks stale; no live failure or artificial production run
was created to demonstrate those cases. Real post-release source advancement,
several dispatch cycles and external delivery remain unverified.

Before external activation, obtain GitHub backend clearance for obsolete queued
runs **33219808359** and **33221027676**, select/configure the Cloudflare account,
and store a narrowly scoped Actions-write credential as a server-side secret.
Then verify multiple canonical collector/AI/Pages cycles and continued state and
alert continuity. Follow [EXTERNAL_SCHEDULER.md](../EXTERNAL_SCHEDULER.md).
GitHub cron stays enabled until an explicit documented redundancy decision.
Private Vault runtime, held PR #3, physical-device acceptance, cutover and legacy
recovery gates remain separate. This receipt does not claim those are resolved.

Rollback uses reviewed code on current main and the newest valid protected state;
it never restores older exports or initializes a new baseline. Exported artifacts
and API/proof reports live under ignored `.remediation/preflight`, `postflight`,
`scheduler-live-integration`, and `scheduler-release-check` in the isolated
scheduler worktree. Raw credentials and raw job logs are not published.
