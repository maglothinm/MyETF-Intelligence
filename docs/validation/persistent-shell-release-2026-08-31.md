# Persistent dashboard shell publication receipt — 2026-08-31

Work record: [issue #4](https://github.com/maglothinm/MyETF-Intelligence/issues/4),
with shared help compatibility in [issue #6](https://github.com/maglothinm/MyETF-Intelligence/issues/6).
The owner explicitly requested **Deploy** after local validation and native-input
limits were reported. Canonical repository ID **1349678672**, live name
**maglothinm/MyETF-Intelligence**, default **main**.

**Release verified:** PR #17 merged, PR/main CI passed and the existing Pages
publisher succeeded. The **13:12:37 UTC** postpublication audit verified exact
source/provenance, unchanged protected state and all 238 served content files plus
the root URL against the Pages artifact. Physical-device acceptance remains separate.

## Source and scope

[PR #17](https://github.com/maglothinm/MyETF-Intelligence/pull/17) merged tested
head `6967a170d1925f06cccb7cb0ae2dbf637c7f22cc` as
`42351e2c8b462566b69a4d05b8ca256f3731fc8c`. Their trees match exactly.
The isolated worktree is `.remediation/persistent-shell/worktree`, branch
`codex/persistent-shell-layout`. The release preserves approved Operations,
Investor Edge and Filing Vault code/tests and all upstream records, including
Investor Edge production-activation prerequisites from `d6b1e41`.

The root dashboard has one sticky application header whose measured border-box
height drives the desktop Workspace offset, remaining viewport height and anchor
clearance. Workspace scrolls independently only when its content exceeds that
space. The document remains the content scroller; shell tables retain horizontal
access without an additional vertical height cap. Six dashboard hash routes use
this shell. All seven Workspace links remain, including the separate Filing Vault
page; standalone page layouts are unchanged.

The source delta changes only `scripts/dashboard_assets/{app.js,index.html,styles.css}`,
`tests/{dashboard_dom.test.cjs,dashboard_notification_integration.test.cjs}` and
project records. It adds no collector, scoring, state schema, alert, simulation,
workflow, schedule, runtime credential or hosting configuration change. This
publication uses only the existing read-only Pages workflow, not a production
writer, simulator or alert workflow.

## Local and canonical verification

The combined active suite passed **524 tests in 102.74 seconds**. One benign
pytest cache ACL warning did not affect results. An earlier attempt had 54 fixture
setup errors because its in-checkout `--basetemp` conflicted with safe-path guards;
rerunning with an external temporary directory resolved them without changing
those guards or executable source. JavaScript syntax, diff checks and canonical
static generation passed. Original shell validation additionally covered seven
new asynchronous route/focus/header regressions in the existing DOM suite.

Generated-preview checks confirmed all seven Workspace links at **320px and
390px**, without horizontal page overflow. At **1366×420**, the header's actual
height was **86.5px** at top zero; the sidebar height was **333.5px** with 710px of
content. Scrolling the sidebar to 190px left the document at zero. Scrolling the
document to 680px retained sidebar offset 190px and header top zero. The Operations
heading landed at 128px, below the 86.5px header, and the native Actions dialog
retained focus. Original rendered checks covered all six routes and widths from
320px through 3840px. These preview checks are distinct from live verification.

| Run | Attempt | Source | Result |
|---|---:|---|---|
| [PR CI 33395139807](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395139807) | 1 | `6967a17` | Success; job `99497756387`, 441 pytest cases, 6 filing-link DOM cases, Linux `VERIFICATION PASSED` |
| [Main CI 33395366037](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395366037) | 1 | `42351e2` | Success; job `99498489333`, same 441 pytest cases, 6 filing-link DOM cases and Linux verifier |
| [Pages 33395506967](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395506967) | 1 | `42351e2` | Success; build job `99498953297`, deploy job `99499100656`; dispatched 13:10:28 UTC |

## Protected-state preflight and postpublication continuity

The prepublication audit covered **169 Actions runs**, repository-global artifact
name enumeration, exact producer attempts/jobs, successful upload windows,
repository/workflow/default-branch identity, expiry, ancestry and producer
high-water marks. Its final fresh readback passed at **12:57:41 UTC**. Protected
ZIP/member hashes, sizes, parsed inventories and retained counts matched prior
verified exports. These read-only copies are evidence, never production authority.

The final **13:12:37 UTC** audit covered **172 runs**, fresh global artifact/high-water
checks, exact producing attempts/jobs, commit ancestry and newly downloaded
ZIP/member hashes and inventories. All protected inputs and simulator history
remain unchanged. The actual Pages build log consumed the exact protected IDs
and producing attempts below, and its only uploaded artifact was `github-pages`.
Only the two previously known obsolete queues remained active. Neither simulation
workflow receives external-alert secrets, deploys Pages or uploads protected state;
its existing isolated output contract remains unchanged.

| Protected artifact | Artifact ID | Producing run / attempt | Successful job |
|---|---:|---|---:|
| legislative-tracker-state | 9749549239 | [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) / 1 | 99417536057 |
| executive-tracker-state | 9746602231 | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | 99391153447 |
| ai-analysis-state | 9749567326 | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | 99417669143 |

All three producer commits are `3902968d5d70cd00030248ae4a6bcea18aa2e6ea`;
all three artifacts remain unexpired until 2026-11-29.

| Archive | Bytes | SHA-256 |
|---|---:|---|
| Legislative | 46,720 | `fcd8d2398fe1f6631e87023aa90b90e695fd64be21c5034df1c7196c2ded9479` |
| Executive | 509,704 | `997a0eaf63b4b3bd33bbda34bfc40a633802c04cfd891f6a2dca726d93a2b4be` |
| AI | 272,092 | `318e1892cc74505711dd362ba96255d060e5a099d174f36627af7f222c981aa9` |

Raw retained counts: Legislative 983 filings / 65 transactions / 19 purchases /
1 review / 31 runs; Executive 4,109 filings / 1,495 reviews / 23 runs; AI
12 analyses / 36 runs. Generated public counts are deduplicated projections:
5,079 filings / 60 transactions / 1,496 reviews / 11 analyses / zero paper positions.

Isolated simulator artifact **9734790733**, run **33320677882 / attempt 1**, job
**99281977011**, retains two history rows and unchanged result/history bytes.
Its ZIP SHA-256 is `1daa01b253894ea07007bdfbf59bdcf5cb2afe568e9d6feff1774488b294dc59`.
This does not resolve the separately recorded historical simulator rewrite concern.

## Pages publication and live verification

The owner-authorized dispatch used existing workflow **344663676**,
`.github/workflows/publish_trade_dashboard.yml`, on canonical `main` at
`42351e2`; no trigger or workflow file was changed. The asset-only diff does not
match that publisher's push-path filter, so the same workflow was dispatched
explicitly after successful canonical CI.

[Pages 33395506967](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395506967)
succeeded on attempt 1. Build job **99498953297** completed at **13:11:01 UTC**;
deploy job **99499100656** completed at **13:11:13 UTC**. Artifact **9759155643**
was created inside the exact successful build-attempt window at **13:10:59 UTC**
and expires **2026-09-01 13:10:58 UTC**. Its downloaded archive is **3,872,939 bytes**,
SHA-256 `6f1ecc514659cb0e488bb818172b66ad4c112a3610ec80744584c8e6cdeeea60`.
The GitHub digest matches the downloaded bytes.

At the **13:12:37 UTC** audit completion, all **238 served public content files**
returned HTTP 200 and matched artifact bytes; the root URL also matched. The archive
preserves all **239 file paths**, with only the empty `.nojekyll` marker excluded
from HTTP file verification. The published build is
`42351e2c8b462566b69a4d05b8ca256f3731fc8c`. All **204 PDF-related/vendor files**
remain byte-identical to the prior deployment; the published Vault configuration
is still exactly `{"api_origin":""}`. Protected tracker, AI and simulator source
inventories are unchanged. Public counts remain 5,079 filings / 60 transactions /
1,496 reviews / 11 analyses / zero paper positions.

The [live dashboard](https://maglothinm.github.io/MyETF-Intelligence/?release=42351e2)
was checked in a fresh in-app browser view of this release. At **1440×900**, all six
hash routes rendered with headings at 128px below the 86.5px sticky header, sidebar
top 86.5px and no horizontal page overflow. Signals loaded 11 records, Records 5,079
and Operations 90. The sidebar height was 813.5px and contents fit without scrolling.
After deep document scroll 789.6px, header top remained zero and the sidebar stayed
pinned.

At **1366×420**, the sidebar height was 333.5px with 710px of content. Scrolling it
to 190.4px left the document at zero; document scrolling to 680px preserved that
sidebar offset and header top zero. At **390×844** and **320×740**, the no-hash landing
kept all seven links visible in the static mobile Workspace. The measured header
heights were 137.45px and 187.45px respectively, with no horizontal overflow.
At **3840×1080**, header height 86.5px/top zero and sidebar height 993.5px matched the
available viewport; its contents needed no scrollbar.

At 320px, the native Actions dialog remained entirely within the viewport and its
Close Actions control retained focus in the native top layer. The shared coverage
help popover opened visibly at 3840px. Browser warning/error logs were empty.
These are rendered browser checks; synthetic-input and physical-device limitations
remain below. No Actions workflow link, government-source retrieval or source
acknowledgement was activated during these checks.

The last verified rollback reference is Pages **33392608680 / attempt 1**,
artifact **9758066553**, source `104fc519d883c93153c639e85a2474d3d816a336`,
ZIP SHA-256 `28dd09b87b99f55636f9b47fe1be4254323c0ca10c33d1edeafd00151696ad4c`.
Rollback means a reviewed source revert through existing Pages with current valid
inputs; it never replaces protected state with this historical snapshot.

## Remaining limits and evidence

Browser-control wheel/key events are synthetic (`isTrusted=false`). They do not
establish physical trackpad boundary containment, native keyboard traversal,
Page Up/Down/Home/End, touch/Safari, audio or physical CHG90 acceptance. The existing
DOM focus/navigation and rendered checks do not close these device gates in issues
#4/#6. The owner authorized deployment with those limits disclosed.

Filing Vault private retrieval remains inactive with published `{"api_origin":""}`;
this shell release does not activate its server, database, storage, source notices
or timer. Investor Edge's full production bootstrap still requires the existing
manual Legislative gate to be cleared; an AI-only run cannot reconstruct catalog-only
transactions. Obsolete queued runs **33219808359** and **33221027676**, the unsent
Support draft, held PR #3, same-ID rename/privacy, legacy retirement, historical
simulator concern and Gmail delivery proof remain separate work.

Ignored release evidence is under the parent workspace's
`.remediation/persistent-shell-publish/`, including `preflight-evidence.json`, `postpublication-pages.json`,
`postpublication-compatibility.json`, `simulation-workflow-isolation.json` and
`browser/` screenshots/measurements: `live-routes.json`, `live-short-scroll.json`,
`live-mobile.json`, `live-320.json` and `live-overlays-wide.json`, with corresponding
screenshots. Original local evidence remains under `.remediation/persistent-shell/`.
Raw protected exports and local fixtures are not committed or uploaded as state.
