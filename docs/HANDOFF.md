# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
## Current task — approved icon integration ready for release checks

The owner requested deployment of the newly created PolitiTrack icon package,
favicon/header wiring, applicable Windows icon references, checks and a commit.
The previously missing ZIP was supplied and inspected. Canonical repository ID
**1349678672**, current name **maglothinm/MyETF-Intelligence**, default **main**,
was reverified at `ecc031dad297f6878e086dbe0b62861cbb4a6441` before implementation.
Work is isolated on `codex/polititrack-icon-assets` in the task's `polititrack-icons`
clone. Shared checkout files and unrelated worktrees remain untouched.

The complete 22-file source package is preserved unchanged under
`assets/branding/polititrack/`, including the 1254px original and seven-frame
Windows ICO. Its README and manifest document provenance and usage. Source ZIP
SHA-256: `0fbc21472cce75ee3d1f47040683dfe8e4a1b1044cd892f12e75c599b40cf65a`.
No Windows packaging configuration or existing app-icon reference was found.

Production web variants live under `scripts/dashboard_assets/icons/`.
`scripts/dashboard_branding.py` copies those 11 assets plus `site.webmanifest`
from both `build_trade_dashboard.py` and the standalone Investor Edge generator.
Root, 404, Wallboard, Filing Vault and Investor Edge receive relative favicon,
Apple touch and manifest links. Root/Vault/Wallboard replace only the old header
mark; surrounding text, spacing and navigation remain unchanged. Header sizes
stay 35px desktop, 32px mobile and 54px for the existing large portrait Wallboard.
The React frontend uses the same approved icon bytes and retains its 50px header
footprint and existing manifest display/theme settings. Only its circular icon
crop and obsolete React sample install name were corrected.

Local checks so far: all 22 source files and both sets of generated web copies
match the ZIP exactly; all 30 favicon/touch/manifest links resolve in full-site
and standalone output. PNG dimensions, seven Windows ICO frames and source
manifest hashes passed. Browser comparisons at 1440px, 390px and 320px show
identical root header/brand/sidebar rectangles and no horizontal overflow.
Filing Vault desktop/mobile and Wallboard desktop/1440x2560 portrait comparisons
also match, with loaded icons. Investor Edge retains its text-only heading;
browser warning/error logs are empty. The full existing Python suite passed
**524 tests without skips in 258.80 seconds**, including nested dashboard release
and DOM checks. Isolated declared dependencies and an external test directory
were used; Windows dependency ACL access required a reviewed escalated run.
No source/test safety guards or ACLs were changed. Linux `verify.sh` remains a
remote CI check. The separate retained React test/build checks are still running;
record their result before merging this change.

Read-only preflight examined issue #4, 180 runs and 198 global artifacts.
Current protected inputs are Legislative `9764350004` (run `33408974583` / 1,
job `99543508327`), Executive `9760298853` (`33398375467` / 1, job `99508337018`),
and AI `9764387095` (`33409079174` / 1, job `99543844689`). Their successful
producer attempts/upload windows, expiry, ancestry and high-water marks passed.
The two-row simulator remains `9734790733` (`33320677882` / 1, job `99281977011`).
Existing Pages `33409174140` / 1 succeeded for `ecc031d`, artifact `9764416987`,
and its logs consumed those exact inputs. All five ZIP exports passed CRC and
independent SHA-256 checks, with inventories of 7 Legislative, 4 Executive,
45 AI, 2 simulator and 239 Pages files. Evidence is outside Git in the task's
`icon-release-evidence/`. This is pre-release evidence only.

**Delivery state:** tested implementation prepared for a commit referencing issue
#4 and canonical PR/CI review; no icon deployment yet. Finish the React checks,
require successful CI, then verify the existing Pages publisher and live icon
bytes. Generator changes already match its push trigger; do not add a workflow.
No production writer, simulation, alert, state, schedule, credential or setting
was changed or dispatched. Existing manual-writer/cutover/device gates remain
separate. The prior release and runtime evidence below is retained unchanged.

## Prior persistent-shell release — retained evidence

Prior work record: [issue #4 — dashboard shell](https://github.com/maglothinm/MyETF-Intelligence/issues/4),
with shared help compatibility in [issue #6](https://github.com/maglothinm/MyETF-Intelligence/issues/6).

### Persistent-shell deployment verified

The owner's explicit **Deploy** instruction authorized canonical PR/CI/merge and
the existing read-only Pages publisher. Repository ID **1349678672**, live name
**maglothinm/MyETF-Intelligence**, default **main**. Work remains isolated on
`codex/persistent-shell-layout` in `.remediation/persistent-shell/worktree`;
shared checkout user files and unrelated worktrees remain preserved. Never
implement or dispatch in legacy `maglothinm/MyETF`.

[PR #17](https://github.com/maglothinm/MyETF-Intelligence/pull/17) merged tested
**6967a170d1925f06cccb7cb0ae2dbf637c7f22cc** as
**42351e2c8b462566b69a4d05b8ca256f3731fc8c**; their trees match exactly.
The source retains approved Operations, Investor Edge and Filing Vault code/tests,
all release evidence, and main `d6b1e41` production-activation prerequisites.

**Delivery state:** deployed and independently verified. Existing Pages
**33395506967 / attempt 1** succeeded for `42351e2`, with build **99498953297**
and deploy **99499100656**. Artifact **9759155643** is **3,872,939 bytes**, SHA-256
`6f1ecc514659cb0e488bb818172b66ad4c112a3610ec80744584c8e6cdeeea60`.
At **13:12:37 UTC**, all **238 served content files plus the root URL** matched
that verified archive; the current published source is **42351e2**.

## Completed scope and validation

The shared root header stays at the viewport top. Its actual measured height
sets desktop Workspace offset/height and anchor clearance; Workspace scrolls
independently only when needed. The document remains the content scroller and
wide tables retain horizontal access without a third vertical scroll context.
Six hash routes share this shell. All seven Workspace links, the separate Vault
page, existing mobile navigation, native dialog/popover layers and focus/help
behavior remain intact. No new workflow, collector, score, state/schema, alert,
simulation, credential, schedule or hosting configuration change was introduced.

Combined local tests: **524 passed in 102.74 seconds**, one benign pytest cache
ACL warning. Earlier in-checkout temporary-directory fixture errors were resolved
with external TEMP; no source safety guard changed. Syntax, diff and generation
passed. At 320px/390px all seven links were visible without document overflow.
At 1366×420, header top was zero/height 86.5px, sidebar height 333.5px with 710px of
content. Sidebar scroll 190px left document zero; document scroll 680px preserved
sidebar 190px and header zero. Operations heading 128px cleared the header and the
native Actions dialog retained focus. Original rendered checks covered all six
routes from 320px through 3840px; these are preview checks, not live verification.

| Canonical run | Attempt | Result |
|---|---:|---|
| [PR CI 33395139807](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395139807) | 1 | Success; job `99497756387`, 441 tests, 6 filing-link DOM cases, Linux verifier |
| [Main CI 33395366037](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395366037) | 1 | Success; job `99498489333`, same tests/DOM/verifier |
| [Pages 33395506967](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33395506967) | 1 | Success; build `99498953297`, deploy `99499100656`, artifact `9759155643` |

The full preflight's final **12:57:41 UTC** readback checked 169 runs, repository-global
artifact enumeration, exact producer attempts/jobs, expiry, ancestry/high-water
marks and unchanged ZIP/member inventories. Legislative `9749549239`, Executive `9746602231`,
AI `9749567326` and two-row isolated simulator `9734790733` were unchanged. The final **13:12:37 UTC** postflight checked **172 runs**, fresh global
high-water/attempt provenance, downloaded ZIP/member inventories and exact Pages
restore logs; these same inputs were consumed and remained unchanged. Pages
uploaded only `github-pages`. Both simulation workflows retain their isolated
outputs with no external-alert secrets or Pages deployment.

## Live verification, next safe action and remaining limits

The [live dashboard](https://maglothinm.github.io/MyETF-Intelligence/?release=42351e2)
passed all six routes at 1440×900, heading clearance (128px below the 86.5px header),
sticky header/sidebar alignment and no horizontal overflow. At 1366×420, sidebar
scroll 190.4px left the document at zero; document scroll 680px preserved that
sidebar offset and header top zero. At 390×844 and 320×740, all seven links remained
visible on no-hash landing in the static mobile Workspace, with measured header
heights 137.45px and 187.45px and no horizontal overflow. At 3840×1080, sidebar
height 993.5px matched the available viewport and did not need a scrollbar.

The 320px native Actions dialog fit within the viewport and retained Close Actions
focus. Shared coverage help opened visibly at 3840px. Warning/error logs were empty.
The 239-path public inventory, all 204 PDF-related/vendor files and
`{"api_origin":""}` are preserved. Full source/run/job/hash/count, screenshot and
rollback evidence is in the
[release receipt](validation/persistent-shell-release-2026-08-31.md).

This documentation-only successor records the verified release without changing
executable source or advancing production state. No further deployment action is
needed for the shell. The next safe work is outstanding native/device acceptance
or the separately authorized producer/runtime/cutover tasks under their existing
gates; do not dispatch a writer, simulation or alert as a layout test.

Native wheel/key automation is synthetic (`isTrusted=false`), so physical
trackpad boundary containment, native keyboard traversal/Page Up/Down/Home/End,
touch/Safari, audio and physical CHG90 remain unverified. The owner authorized
publication after those limits were disclosed; issues #4/#6 remain open.

Ignored evidence: parent workspace `.remediation/persistent-shell-publish/`,
including `preflight-evidence.json`, `postpublication-pages.json`,
`postpublication-compatibility.json`, `simulation-workflow-isolation.json` and
`browser/` screenshots/measurements; original preview/fixture evidence remains
under `.remediation/persistent-shell/`. Raw exported state is read-only evidence,
not production authority. Last verified rollback: Pages `33392608680` / 1, artifact `9758066553`,
source `104fc51`, with hash and reviewed-source-revert procedure in the receipt.

Filing Vault private retrieval remains inactive with `{"api_origin":""}`.
Its runtime procedure and Investor Edge's separate production gate remain below.
Obsolete queued writers `33219808359` / `33221027676`, unsent Support draft, historical
simulator rewrite concern, held PR #3, rename/privacy/legacy retirement, device
acceptance and Gmail delivery proof are separate work. No configuration or
credential change is part of this shell deployment.

## Separate Investor Edge production activation — prerequisites retained

The following checkpoint is preserved from canonical main's documentation-only
commit `d6b1e41` for [issue #11](https://github.com/maglothinm/MyETF-Intelligence/issues/11).
Its **Fully deploy** request and producer gate belong to that separate task; they
do not change the current shell publication scope. References to that task's
branch, worktree and documentation commit describe its recorded checkpoint.

The owner requested **Fully deploy** after the Investor Edge release. The code is
already published, but this follow-up cannot establish full production bootstrap
while the existing manual Legislative gate remains unresolved.

Canonical repository **1349678672** is currently **maglothinm/MyETF-Intelligence**,
default **main**. This task uses clean isolated branch
`codex/investor-edge-bootstrap` in `.remediation/investor-edge-worktree`,
fast-forwarded to `642cebc45a489b7b3faf9b2840a716002828fafa`.
The shared checkout and unrelated work are preserved. The documentation commit
containing this handoff changes no executable source or production state.

### Verified current deployment and continuity

Current published source is `104fc519d883c93153c639e85a2474d3d816a336`, which
preserves Investor Edge release `676701a` and Operations ordering. Canonical
[main CI 33392608687](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392608687)
and [Pages 33392608680](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392608680)
are successful on attempt 1. The new read-only audit verified Pages build/deploy,
archive digest, and four live dashboard/Wallboard/Edge/summary surfaces against
that publication. Earlier full-release tests and file/browser acceptance remain
recorded in [PROJECT_STATE](PROJECT_STATE.md) and the
[Filing Vault release receipt](validation/filing-vault-release-2026-08-31.md);
no new source test suite was necessary for this documentation-only follow-up.

Fresh exact-attempt provenance, producer high-water, expiration, ZIP/member
inventory and continuity checks passed for the unchanged Legislative, Executive
and AI authorities. Isolated simulator history remains unchanged. Both production
trackers, the AI workflow and the existing Pages publisher report active.
Tracker/analyst/bootstrap source, configuration and schedules are unchanged from
the tested Investor Edge release. Their historical pass defaults to 20 filings;
existing observation and network budgets remain unchanged.

Private audit exports are in the shared workspace's ignored
`.remediation/investor-edge-bootstrap/full-deployment-audit-20260831/`.
They are verification evidence, never production restore authority. The helper's
held-PR migration-allowlist findings belong to PR #3; they do not invalidate the
independently verified deployed-main artifact provenance.

### Exact blocker and next safe action

Both obsolete runs **33219808359** and **33221027676** still report queued,
attempt 1, zero jobs and zero artifacts. Their workflow is deleted, but this does
not prove that their retained historical state-writing code cannot execute.
Issues #8 and #1 contain no GitHub clearance; the latest recovery comment retains
the gate and reports the Support submission unresolved. Prior unsuccessful
cancellation/deletion attempts are documented in the
[Senate incident record](incidents/senate-efd-2026-08-30.md).
No cancellation retry, deletion, writer dispatch, rebaseline, simulation, alert,
credential change or schedule change was performed by this task.

The gate specifically prevents the additional manual Legislative run. It is not
a newly invented blanket ban on all AI operations. An AI-only run cannot repair
catalog-only filings: it consumes retained transaction/purchase ledgers, whereas
historical reconstruction runs inside the tracker. Dispatching AI alone would
therefore not satisfy the requested population bootstrap.

**Next:** obtain GitHub backend clearance or an authoritative confirmation that
both obsolete runs cannot execute. The user has been asked for any Support/ticket
update. Then recheck live main and authoritative state, run the existing bounded
Legislative producer without initialization, verify its exact successful artifact
and preserved ledger/seen history, and verify the normal downstream AI/Pages
successors plus actual profile and pending-observation progress. Keep issue #11
open until that operational evidence exists. Never upload local acceptance
copies or bypass the gate to make the dashboard appear populated.

### Separate retained limits

The newer Filing Vault catalog/viewer is published, but its private API/storage
runtime remains inactive. Its existing host, database, private bucket, credentials,
legitimate source acknowledgements and timer are separate issue #13 activation
prerequisites; this task did not create infrastructure or infer source consent.
See [FILING_VAULT.md](FILING_VAULT.md) for that distinct procedure.

Source-original access, parser/OCR limitations, actual market completion, Gmail
delivery proof, physical devices, held PR #3, the historical simulator-prefix
concern, same-ID rename/privacy and legacy retirement remain as documented.

## Prior Filing Vault release and runtime handoff — retained evidence

The following is the completed Filing Vault publication checkpoint carried forward
from main `642cebc4`. Its run/test/state results describe that prior release and
do not establish the pending shell deployment. Ignored Vault evidence paths refer
to its `.worktrees/filing-vault` worktree, not the active shell worktree.

The owner's explicit **Publish** instruction was carried through canonical PR,
CI, merge and existing Pages. Repository ID **1349678672**, current live name
**maglothinm/MyETF-Intelligence**, default **main**. Never implement or dispatch
in legacy `maglothinm/MyETF`. The shared root checkout and unrelated worktrees
remain untouched. Work used branch **codex/filing-vault**, isolated worktree
**.worktrees/filing-vault**.

[PR #16](https://github.com/maglothinm/MyETF-Intelligence/pull/16) merged tested
head `755349945bf8fdd4389a8c6aa6d770370df487af` as
`104fc519d883c93153c639e85a2474d3d816a336`; the trees match exactly. This includes
the final exact-ID safeguard and preserves Operations/Investor Edge releases and
verified receipts through `b5169f3`. This documentation-only successor records
the release; it does not advance production state or change deployed source.

The [live Filing Vault](https://maglothinm.github.io/MyETF-Intelligence/filing-vault.html)
has **5,079** cataloged filings, filters, exact-ID details and official links.
**Private cached-document retrieval is inactive.** The generated public API origin
is blank and the live page explicitly reports unavailable retrieval; no document
was retrieved and no government acknowledgement was submitted by this publication.

### Filing Vault delivered source and verification

The optional Flask/SQLAlchemy/Supabase Vault includes six additive tables, private
storage, immutable SHA-256 evidence, exact 2,592,000-second expiry, acknowledgements,
version history, known-ID catalog admission, source adapters and daily lifecycle
commands/timer examples. Shared dashboard links and the responsive full-page
viewer reuse existing surfaces; PDF.js assets/licenses are pinned locally.
Rejected filing matches retain original provenance and cannot fall back to
conflicting IDs after compact projection. No protected writer or ledger changed.

The full local suite passed **524 tests with no skips**; **6 additional filing-link
DOM cases** passed. Syntax, all workflow YAML and **201 vendor hashes/sizes** pass.
Government-source tests are mocked. PostgreSQL isolation SQL is fixture-tested,
not verified against a live database. Earlier real PDF rendering used a disposable
TEST API; it is not evidence of production storage access.

| Canonical run | Attempt | Result |
|---|---:|---|
| [PR CI 33392460770](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392460770) | 1 | Success; 441 tests, 6 DOM cases, Linux VERIFICATION PASSED |
| [Main CI 33392608687](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392608687) | 1 | Success; same 441 tests, 6 DOM cases and verifier |
| [Pages 33392608680](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392608680) | 1 | Success; build `104fc51`, artifact `9758066553` |

Pages build/deploy jobs **99489550775 / 99489776345** succeeded. Archive size
**3,872,316 bytes**, SHA-256
`28dd09b87b99f55636f9b47fe1be4254323c0ca10c33d1edeafd00151696ad4c`.
All **238 served public content files** matched the exact Pages archive at
**12:43:45 UTC**, including all **201** pinned PDF assets. Only the empty
`.nojekyll` marker was not HTTP-checked. Emitted and live configuration both contain
exactly `{"api_origin":""}`; private-field/raw-document archive checks passed.
Desktop/mobile-width live checks passed source filtering and exact filing details
without horizontal overflow or console warnings/errors. Physical Safari/iPhone
and live runtime acceptance remain unverified.

### Filing Vault protected continuity and retained evidence

Exact producer repository/workflow/default branch, successful run attempts/jobs,
artifact upload windows, expiry, commit ancestry and global producer high-water
marks are checked independently of CI. Pages logs consume these exact inputs:

| Protected artifact | ID | Producing run / attempt | Successful job |
|---|---:|---|---:|
| legislative-tracker-state | 9749549239 | 33369634244 / 1 | 99417536057 |
| executive-tracker-state | 9746602231 | 33360633323 / 1 | 99391153447 |
| ai-analysis-state | 9749567326 | 33369677492 / 1 | 99417669143 |

The final **12:45:06 UTC** audit checked **169 runs / 82 producer records**.
Protected ZIP/member hashes, sizes, inventories and high-water marks remain unchanged. All producers
are at `3902968`, an ancestor of this release; artifacts expire on 2026-11-29.
Isolated simulator artifact **9734790733**, run **33320677882 / attempt 1**,
job **99281977011**, remains two rows. No writer, simulation, rebaseline, alert,
repository setting or credential was dispatched/changed by this publication.

See [the release receipt](validation/filing-vault-release-2026-08-31.md) for exact
run/job URLs, digests, counts, live file checks and limitations. Ignored evidence
is in the Vault worktree's `.remediation/publish-vault/` and `.remediation/browser-evidence/`.
Raw state copies are read-only evidence, never production restore authority.

### Separate Filing Vault configuration and next safe action

Issue #13 stays open. Activate the existing private application runtime only with
its real PostgreSQL connection, private Supabase bucket, server-only storage and
signing credentials and HTTPS API host. Run the explicit additive migration,
verify private table/bucket isolation, supply catalog metadata from the verified
canonical publisher, configure exact origins/agency hosts and legitimately accepted
source notices, install the daily timer and verify its execution. Then set the
public `FILING_VAULT_API_ORIGIN` repository variable and release through existing
CI/Pages. Do not put documents or secrets in Git/Pages, create another repository,
or use protected tracker artifacts as the document cache.

Local Vault configuration/environment variables were absent. A bounded configured
Git credential-helper read returned no usable credential; it did not retrieve
remote secret metadata or runtime environments, and no alternative credential
search was attempted. Published config proves only that this build has no API
origin; credentials and externally provisioned infrastructure remain unverified.
Static publication cannot activate the cache or imply government-source consent.
Request-only reports remain request-only. Endpoint validation does not establish
exhaustive discovery of separately published amendments.

Verify real HTTPS/CORS, aggregate proxy/egress rate limits, storage/database isolation,
source access, scheduled retention and physical devices before describing the
cache as operational. Detailed architecture/configuration is in
[FILING_VAULT.md](FILING_VAULT.md).

Preserve the separate Senate recovery gate: obsolete queued writers **33219808359**
and **33221027676** require backend clearance before the separately requested
manual Legislative run; its support draft remains unsent. The historical simulator
rewrite concern remains unresolved before future manual simulator work. Current
unchanged history does not resolve that older concern. Held PR #3, same-ID
rename/privacy, legacy retirement and external delivery/device acceptance remain
separate tasks. Requery live GitHub provenance before any production operation.
