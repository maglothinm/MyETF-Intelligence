# Senate eFD HTTP 403 incident and recovery evidence

Verified **2026-08-31 09:51:27 UTC**. Work record:
[issue #8](https://github.com/maglothinm/MyETF-Intelligence/issues/8), implementation
[PR #9](https://github.com/maglothinm/MyETF-Intelligence/pull/9).

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, default
branch `main`. Runtime and audited producer commit:
`3902968d5d70cd00030248ae4a6bcea18aa2e6ea`. Later documentation-only commits do not
change this audited runtime. Artifact IDs below are checkpoints, never permanent
restore targets; always select the newest valid authority from live GitHub.

**Owner-approved publication:** The owner explicitly approved this new recovery
evidence for issue #8, PR #9 and main on August 31. It is published in
[issue comment 5477003406](https://github.com/maglothinm/MyETF-Intelligence/issues/8#issuecomment-5477003406)
and linked from [PR comment 5477009236](https://github.com/maglothinm/MyETF-Intelligence/pull/9#issuecomment-5477009236).
This documentation-only publication changes no runtime or production state.
A fresh preflight at **10:24 UTC** reconfirmed the three unchanged authorities,
full continuity and all 21 live files, with only the two obsolete queues active.

## Outcome and limits

The merged fix has succeeded in two scheduled production runs, including complete
House/Senate discovery, accepted Healthchecks success delivery, protected-state
continuity and downstream dashboard publication. These runs were scheduled by
the existing workflow, not manually dispatched by this recovery session.

The requested additional manual production run remains **blocked** by obsolete
queued runs `33219808359` and `33221027676`. Cancellation, force cancellation,
exact empty-record deletion and signed-in UI cancellation all failed. No queue
clearance, manual recovery dispatch or provider-side Healthchecks UP status is
claimed. The accepted HTTP 200 success pings are independently verified below.

The owner explicitly approved publication of the detailed evidence on August 31.
The earlier 01:09 UTC checkpoint is published at
[issue comment 5476609143](https://github.com/maglothinm/MyETF-Intelligence/issues/8#issuecomment-5476609143)
and cross-linked from
[PR comment 5476612083](https://github.com/maglothinm/MyETF-Intelligence/pull/9#issuecomment-5476612083).
Its then-pending production status is superseded by this audit.

## Incident and delivered change

Failed Legislative run
[33342768435](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33342768435),
attempt 1, job `99341272661`, failed on the initial Senate home GET with HTTP 403,
before CSRF/agreement processing. Its runner reported `mexicocentral`; the prior
successful run reported `eastus`. This is diagnostic context, not proof that
region caused the denial or a guarantee that all hosted runners now work.

PR #9 merged tested source `125eac1aba5a5f5324040cbfac7f30b63a2f0347` as
`19f7044e8bd12fd4d693cf7f468623f318034717`, with identical trees. It added bounded
official-source sessions and strict agreement/CSRF/search/report validation,
complete discovery before protected-state/scanner/alert effects, safe diagnostics,
and one classified terminal heartbeat. Existing IDs, artifacts, baselines,
deduplication, schedules and simulation isolation remain unchanged.

Local suite: **283 passed**. PR CI
[33346339195](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33346339195)
(attempt 1, job `99351095293`) and main CI
[33346456045](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33346456045)
(attempt 1, job `99351415370`) succeeded: 212 selected tests each, plus Linux
`verify.sh` reporting `VERIFICATION PASSED`. These are prior implementation
checks, not newly rerun tests for this documentation-only evidence update.

## Scheduled production acceptance

| Run / attempt | Producer job | Runner region | Protected output | Result |
|---|---:|---|---:|---|
| [33348331610 / 1](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33348331610) | `99356670792` | `westcentralus` | `9742750536` | Success at 01:41 UTC |
| [33369634244 / 1](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) | `99417536057` | `eastus` | `9749549239` | Success at 07:44 UTC |

Both ran `3902968d5d70cd00030248ae4a6bcea18aa2e6ea` on canonical `main`. Both
recorded House **883** / Senate **91**, both source statuses `ok`,
`discovery_complete=true` and `success=true`. Baseline changes, new filings,
transactions, purchases and alerts were zero. Each logged exactly one terminal
Healthchecks success request, classification `legislative_complete`, accepted
with **HTTP 200**. Neither logged a source retry. No extra ping was sent by the
audit. Provider status/history and notification delivery were not queried.

Actual restore logs prove Legislative lineage:
`9739239507` (run `33336684309` / 1) → `9742750536` (run `33348331610` / 1) →
`9749549239` (run `33369634244` / 1). Every edge passed full ledger-prefix and
seen-ID continuity. Run-history rows advanced **29 → 30 → 31**, exactly one per
successful scheduled run. No rebaseline, empty state or cache restore occurred.

## Latest protected authority at the audit checkpoint

All selections passed repository/default-branch/workflow/display-name/producer-job
identity, exact successful attempt windows, commit ancestry, producer high-water
checks, expiration, GitHub ZIP digests and complete extracted inventories.
Continuity also passed against the exported pre-incident checkpoints. No later
successful producer was silently skipped. The initial active-run inventory found
only the two obsolete queued records; final authority/high-water checks found no
newer successful producer.

| Pipeline | Artifact | Run / attempt | Job | Retained records |
|---|---:|---|---:|---|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` | 983 filings; 65 transactions; 19 purchases; 1 review; 31 runs |
| Executive | `9746602231` | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | `99391153447` | 4,109 filings; 1,495 reviews; 23 runs |
| AI | `9749567326` | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | `99417669143` | 12 analyses; 36 runs; no open positions |

All pre-incident non-run ledgers are byte-identical. Legislative retains 883 seen
House IDs, 93 seen Senate IDs and 60 seen trade IDs. The 91 reports in the current
Senate catalog do not replace or trim its 93 historical seen IDs. Review data,
analysis history, paper state, alert-delivery state and Investor Edge records
retain continuity.

| Artifact | ZIP SHA-256 | `state.json` SHA-256 |
|---|---|---|
| `9742750536` (intermediate Legislative) | `f50c0ede3b4dc5cee5f8c456333f91088048aa1264625999f994e848d67e4f64` | `64409ec0e05d436177b77e0afc0daf85147b99b189b2da6930299f2c80d390db` |
| `9749549239` | `fcd8d2398fe1f6631e87023aa90b90e695fd64be21c5034df1c7196c2ded9479` | `d20b2ed611ade74c5e491405aabebe4d79b43dfbeb4fb8120359945f1a522cee` |
| `9746602231` | `997a0eaf63b4b3bd33bbda34bfc40a633802c04cfd891f6a2dca726d93a2b4be` | `929c48d6b9ff08073a8d98d12456705643f8ff100d4902598b203e958669aad6` |
| `9749567326` | `318e1892cc74505711dd362ba96255d060e5a099d174f36627af7f222c981aa9` | `f9bfceb222caa24d8eea24f7507c672ec00804ca6d16d5c28ea1940805cf75ee` |

## Dashboard publication

Pages run
[33369728437](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369728437),
attempt 1, succeeded with build job `99417832272` and deploy job `99417945412`.
Artifact `9749580990` has verified ZIP SHA-256
`330d1e4e343d827d917eb3902ba289eed59f00554147a82c38469b86a05df427`.
Its source and published build are canonical `3902968d5d70cd00030248ae4a6bcea18aa2e6ea`.

Actual publisher logs restored precisely the three latest protected artifacts
above. All **21** tested live root/Wallboard/Investor Edge/assets/JSON URLs returned
HTTP 200 and matched the artifact bytes. Published counts reconcile to **5,079
filings, 60 transactions, 1,496 reviews and 11 analyses**. Protected ledger counts
are intentionally distinct from the dashboard's deduplicated display counts.

[Live dashboard](https://maglothinm.github.io/MyETF-Intelligence/),
[Wallboard](https://maglothinm.github.io/MyETF-Intelligence/wallboard.html),
[Investor Edge](https://maglothinm.github.io/MyETF-Intelligence/investor-edge.html).
This establishes deployment/content acceptance, not physical-device acceptance.
No simulation, alternate publisher or manual protected-state writer was run by
this audit/recovery session.

## Obsolete queue blocker and next safe action

Runs [33219808359](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33219808359)
and [33221027676](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33221027676)
are canonical historical runs, not runs in the legacy public repository. Both
remain queued at attempt 1, SHA `b9cf0f3e3863de69d92ae01f35f1c154a082f56a`, with
zero jobs and zero artifacts. Their workflow ID `344663675`, path
`.github/workflows/legislative_trade_tracker.yml`, is `deleted`.

Ordinary and force-cancel endpoints returned HTTP 409. Following explicit owner
authorization, their exact empty run records were exported and hash-verified;
supported REST deletion returned HTTP 403, `Could not delete the workflow run`,
at 09:50:11 / 09:50:12 UTC. Fresh GETs still returned queued. Signed-in UI
`Cancel workflow` also reported `Failed to cancel workflow` for each; the first
run's options offered only a status badge, no deletion control.

| Run | DELETE GitHub request ID | Export SHA-256 |
|---|---|---|
| `33219808359` | `D79A:3C8331:B43E471:25BFF586:6A954E52` | `e3db10cc5aacb01fc33ba3259558b51c693a217afcba42fbeaae4064bd83de5e` |
| `33221027676` | `D79A:3C8331:B43EE3F:25C01718:6A954E54` | `ca61e6139f4950c805d3854515013dcf67fa2af477fa7131d3491650a670a5ed` |

The historical queued code has an independent concurrency group and unsafe old
restore/upload behavior. Absence from today's default branch does not prove that
these existing records cannot execute. The manual dispatch gate is unchanged.
GitHub documents cancellation and force cancellation; its deletion guide only
offers deletion for completed or more-than-two-week-old runs. These runs are
younger. No stronger supported API was found. See
[GitHub run API](https://docs.github.com/en/rest/actions/workflow-runs),
[deletion eligibility](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/delete-a-workflow-run).

Next: have GitHub clear the server-side records and confirm they cannot execute.
A prepared support draft is local and submission is authorized. The signed-in
portal offered no applicable Actions ticket route; its repository-features form
required an unrelated Templates, Releases, Insights or Branches category. No
unrelated category was submitted, no plan was changed and no support ticket has
been created. An eligible Actions support route is still needed. After
clearance, re-query all writer runs and the latest valid artifacts, then dispatch
one fresh current-main Legislative run and repeat exact-attempt continuity,
terminal heartbeat and downstream deployment verification. Do not rerun an old
failed SHA, rebaseline, relax provenance or create an alternate writer.

Local recovery records are in `.remediation/senate-recovery/`, including
`scheduled-evidence.json`, `publication-preflight.json`, hash-verified ZIP exports,
deletion receipts and the support draft. They are audit/recovery evidence, never
production authority.
