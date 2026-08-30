# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Work record: **[issue #6 — contextual help](https://github.com/maglothinm/MyETF-Intelligence/issues/6)**

## Current task

The owner-requested tooltip publication is complete and live-content/state
continuity verification passed. Remaining task: browser/device acceptance under
issue #6. No publication approval is pending. Use the existing deployed UI.

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, default
`main`, remains public/pre-rename. Never use legacy `maglothinm/MyETF`. Source
`2a955f5` was merged by PR #7 as `1aa8739`; the exact full SHA and run evidence
follow. This handoff belongs to a documentation-only successor on `main`.

The implementation reuses `setupDialogsAndTooltips`, `data-tooltip` and one
shared `#tooltip`, adding consistent help, delayed hover, safe structured copy,
viewport/caret behavior and touch-safe workflow help. All material warnings
remain visible. See `docs/CONTEXTUAL_HELP.md` for changed files, exact copy,
interactions and tests. No business logic, workflow or production-state change
was included; held PR #3 remains untouched.

## Contextual-help publication — verified 2026-08-30 17:36 UTC

The owner explicitly requested publication after the Chrome/device gap was
disclosed. PR [#7](https://github.com/maglothinm/MyETF-Intelligence/pull/7) merged
tested source `2a955f571c2cd4cf26b033984daa39904c11d64c` as
`1aa87398b53689873de350155d33afdb993fb036` on canonical `main`. Their trees match.
Documentation-only successors do not change the deployed application source.

[Live dashboard](https://maglothinm.github.io/MyETF-Intelligence/),
[Investor Edge](https://maglothinm.github.io/MyETF-Intelligence/investor-edge.html)
and [Wallboard](https://maglothinm.github.io/MyETF-Intelligence/wallboard.html)
are published from repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.

| Release evidence | Verified result |
|---|---|
| PR CI | [33325538713](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325538713), attempt 1, job `99294887628`; success, 78 selected tests |
| Main CI | [33325629684](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629684), attempt 1, job `99295130888`; success, 78 selected tests |
| Linux verifier | Both CI runs passed the existing release gate, which executes full `verify.sh` and requires `VERIFICATION PASSED` |
| Pages | [33325629663](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33325629663), attempt 1; success; build `99295130679`, deploy `99295188583` |
| Pages artifact | `9736138918`; exact successful attempt/build window and ZIP digest verified |
| Pages ZIP SHA-256 | `f8d5a8e65fa26e34b06e425a6016100fd0e488b312a3aa2fae5731a378acf283` |
| Live verification | 17:36:13 UTC: 21 root/Wallboard/Edge/assets/JSON URLs returned HTTP 200 and exactly matched the Pages artifact |
| Published build | `1aa87398b53689873de350155d33afdb993fb036` |
| Source-content check | 27 additional checks passed across 11 fixed live URLs, including exact source asset/script comparisons, shared copy, help/touch attributes and persistent warnings |

The earlier Windows verifier limitation is resolved for this release by Linux CI.
Local verification remains **182 tests passed**, including **24 JSDOM scenarios**
and **32 native Node notification scenarios**. JSDOM is an optional dependency
not provisioned by CI; its local results are not inferred remote CI results.
Real Chrome/Safari/touch, responsive screenshots, rendered overflow/caret/CSP and
physical-device acceptance remain unverified under issue #6.

### Protected inputs and continuity

Scheduled Executive and downstream AI runs completed before publication. Their
newer artifacts passed exact workflow/job/attempt identity, ancestry, producer
high-water checks, ZIP digests, schema and full inventory/record continuity
against original, prior and last-deployed checkpoints. No eligible writer was
active before merging or at final verification.

| Pipeline | Newest protected artifact | Successful run / attempt | Job | Retained counts |
|---|---:|---|---:|---|
| Legislative | `9734211271` | `33318579174` / 1 | `99276401831` | 983 filings; 65 transactions; 19 purchases; 1 review; 27 runs |
| Executive | `9736054489` | `33325239324` / 1 | `99294089255` | 4,109 filings; 1,495 reviews; 20 runs |
| AI | `9736064296` | `33325343519` / 1 | `99294369216` | 12 analyses; 29 runs |

Actual publisher restore logs, fresh global authority checks and downloaded
protected ZIPs/full inventories prove these inputs were unchanged through
publication. Published counts reconcile to 5,079 filings, 60 transactions,
1,496 reviews and 11 analyses. The Pages run uploaded only `github-pages`.
No collectors, AI, simulations, external alerts or production-state writers were
dispatched by this release task, and no workflow rules were changed.

Isolated simulation artifact `9734790733`, run `33320677882` / attempt 1, remains
unchanged with two replay history rows and preserved predecessor bytes.
Known-good rollback Pages is `33325376676` / attempt 1, artifact `9736074454`,
exported ZIP SHA-256
`910f9e40171a11ea3f0ade63b6dae4386ca4979faaa48d31c7cc4e785739b371`.
Ignored local evidence: `.remediation/tooltip-publish-preflight`,
`.remediation/tooltip-published/deployment-verification.json`, and
`.remediation/tooltip-live-content.json`. These are recovery/verification records,
not alternate production authority.

Only the two known obsolete queued runs remained at final verification. Issue #1,
held PR #3, repository rename/privacy, legacy settings retirement and Gmail
delivery proof remain separate open work. Issue #6 remains open for device
acceptance, not because publication is pending.

## Next safe action and remaining gates

1. Open the live dashboard. Connect Chrome via Settings → Computer use when
   ready to perform desktop/tablet/390px rendered and touch acceptance, followed
   by actual iPhone Safari/device checks. The Browser skill requires the
   requested Chrome connection; no other browser was substituted for acceptance.
   Do not claim screenshots, physical-device, real audio or complete CSP/overflow
   acceptance from HTTP/JSDOM checks. Keep issues #6 and #4 open for these limits.
2. Before later production work, freshly requery repository and artifact
   authority. Recorded IDs are checkpoints, not permanent restore targets. Do
   not dispatch collectors, AI or simulations solely for visual QA.
3. Preserve pre-existing untracked `.codex/`. Audit exports and generated test
   outputs remain ignored. The final implementation tree is clean after the
   documentation-only evidence commit; verify with `git status` before edits.
4. Separate unchanged gates: issue #1, held PR #3, obsolete queued
   `33219808359` and `33221027676` (zero jobs/artifacts), same-ID rename/privacy,
   legacy Actions/Pages/archive settings and actual Gmail delivery proof. No
   state rebaseline, settings change or external-alert test was authorized here.
