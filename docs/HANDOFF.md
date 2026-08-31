# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: **issue #4 — dashboard UX; issue #6 — shared contextual help**

## Current task — published and verified

The owner's “Publish” request is complete. PR
[#10](https://github.com/maglothinm/MyETF-Intelligence/pull/10) merged tested head
`ca0152044bec58032acc3c7604398e844b2ba12f` as
`9d9e7bef326a0e24a5f846ea1310dec24a647019` on canonical `main`.
Repository ID **1349678672**, current name **maglothinm/MyETF-Intelligence**.
The tested and merged trees match. Existing Pages published the merge successfully;
this final documentation-only successor records its evidence.

[Live dashboard](https://maglothinm.github.io/MyETF-Intelligence/) ·
[Manual Parser Exceptions](https://maglothinm.github.io/MyETF-Intelligence/#records/reviews?category=manual_exception).

Delivered: consistent Overview/review classification and full exception drill-down,
exact retained-filing selection with honest unmatched-review details, source/branch
filter metadata and OGE formatting, shared Signals/Records/Operations help, and
refresh consistency. No workflow, collector, analyst scoring, state schema, alert,
simulator or hosting configuration changed. No review/retry writer was added.

Changed implementation files: `scripts/dashboard_insights.py`,
`scripts/build_trade_dashboard.py`,
`scripts/dashboard_assets/{app.js,common.js,index.html,styles.css}` and
`tests/{test_dashboard_insights.py,test_trade_dashboard.py,dashboard_dom.test.cjs}`.
Documentation: `docs/{PROJECT_STATE.md,DECISIONS.md,HANDOFF.md}`.

## Verification and continuity

- Full local integration rerun: **295 tests passed**. **34 DOM scenarios** and
  **32 native notification scenarios** passed. Syntax, Python compilation, static
  dashboard generation, unchanged source-input hashes and diff checks passed.
- PR CI [33384840936](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33384840936)
  / attempt 1 / job `99465044563`: success. Main CI
  [33385044349](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044349)
  / attempt 1 / job `99465680760`: success. Both exact logs show **213 selected
  tests passed** and Linux `verify.sh`: **VERIFICATION PASSED**.
- Pages [33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313)
  / attempt 1 succeeded; build `99465681041`, deploy `99465807219`.
  Artifact **9755242103**, ZIP SHA-256
  `ca3b63daecb7c4e6ce5e92e162cbb363e753c07d8983fddcc1306ca7ac7e4014`.
- At **11:04:50 UTC**, all **21** fixed live URLs returned HTTP 200 and matched
  the uploaded artifact. Published build SHA equals merge `9d9e7be`. Counts:
  **5,079 filings / 60 transactions / 1,496 reviews / 11 analyses**.
- Live in-app browser: card → **1** parser exception → exact RICHARD BLUMENTHAL
  filing → back; focus/visibility, source choices, help attributes and no document
  overflow passed at 1280×720. Local rendered checks also passed at 1440×1000 and
  390×844, including all five mouse-hover bubbles.

| Protected input | Artifact | Successful run / attempt | Job |
|---|---:|---|---:|
| Legislative | `9749549239` | `33369634244` / 1 | `99417536057` |
| Executive | `9746602231` | `33360633323` / 1 | `99391153447` |
| AI | `9749567326` | `33369677492` / 1 | `99417669143` |

Fresh GitHub authority, exact workflow/job/attempt windows, ancestry, high-water
marks, expiration, downloaded ZIP digests/full inventories and continuity passed
before and after deployment. Actual publisher logs prove it consumed the exact
three inputs above; they are unchanged. Only `github-pages` was uploaded.
`simulation-state` **9734790733**, run **33320677882 / 1**, job **99281977011**,
is unchanged with two replay rows and preserved predecessor bytes.

Pre-release rollback artifact **9749580990**, Pages **33369728437 / 1**, exported
ZIP hash `330d1e4e343d827d917eb3902ba289eed59f00554147a82c38469b86a05df427`.
Use a reviewed source revert with current valid input artifacts if rollback is
needed; never restore old production state. Ignored audit exports are in
`.remediation/dashboard-review-publish/`, especially `release-evidence.json`,
`deployment-verification.json` and both exact CI receipts. Detailed run links and
remaining history are in `docs/PROJECT_STATE.md`.

## Preserved work and remaining limits

Upstream approved Senate recovery evidence at `ac6342a` and
`docs/incidents/senate-efd-2026-08-30.md` are preserved unchanged. Local `main`
at `9e5de909` and untracked `.codex/` remain untouched. Another task switched
the shared checkout during final verification; this evidence was prepared in
isolated branch/worktree `codex/dashboard-review-release-evidence`, avoiding its
files and branch. Never implement, deploy or dispatch in legacy `maglothinm/MyETF`.

Keyboard focus/touch behavior passed DOM fixtures; native keyboard activation,
physical iPhone/Safari/touch, real audio and physical ultrawide acceptance remain
unverified. Axe fixture checks exclude layout and contrast. Keep issues #4 and #6
open for this acceptance, not because publication is pending.

Only obsolete queued runs **33219808359** and **33221027676** remained active at
the final audit. Their supported cancellation/deletion failed in the separate
recovery task. The owner-approved GitHub Support draft is still unsent because no
eligible Actions support route was available. Backend clearance or confirmation
that neither can execute remains required before the separate requested manual
Legislative run. See the preserved incident record; do not relax this gate.

No collector, AI, simulator, live alert or fake heartbeat was dispatched by this
UI release. No credentials/settings were changed or independently tested.
Held PR #3, same-ID rename/privacy, legacy settings and Gmail delivery proof remain
separate open work.

## Next safe action

Perform the remaining physical-device/keyboard/touch acceptance on the live
dashboard. Publication needs no further approval or dispatch. Keep the obsolete
writer cleanup and cutover work separate; requery current GitHub provenance
before any later production operation.
