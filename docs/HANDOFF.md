# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: [issue #4 — dashboard shell](https://github.com/maglothinm/MyETF-Intelligence/issues/4),
with shared help compatibility in [issue #6](https://github.com/maglothinm/MyETF-Intelligence/issues/6).

## Current task — deploy the persistent dashboard shell

The owner explicitly requested **Deploy** after the local shell result and
native-input/device limits were disclosed. Complete canonical push/PR/CI/merge,
then the existing read-only Pages publisher and independent live verification.
No additional publication confirmation is pending. Do not dispatch a production
writer, simulation, external alert or private Vault runtime activation.

Repository ID **1349678672**, live name **maglothinm/MyETF-Intelligence**,
default **main**. Work uses isolated branch **codex/persistent-shell-layout** at
`.remediation/persistent-shell/worktree`. Original shell commit
**73193d91088efecbecf228220c0580f986039832** is being integrated with canonical
main **642cebc45a489b7b3faf9b2840a716002828fafa**. Preserve all concurrent approved
Operations, Investor Edge and Filing Vault code/tests/evidence, shared checkout
user files and unrelated worktrees. Never implement or dispatch in legacy
`maglothinm/MyETF`.

**Delivery state at this checkpoint:** shell implementation is committed locally;
current-main integration, its validation and publication remain in progress.
No new shell PR/CI/Pages or live deployment result is claimed here. The last
verified published source is Filing Vault release **104fc51**, with full receipts
retained below and in [the release record](validation/filing-vault-release-2026-08-31.md).

## Shell scope and completed local evidence

- The existing header stays at the viewport top. `ResizeObserver` measures its
  actual border box, with a resize fallback; the shared offset keeps the desktop
  sidebar and anchored content clear when the header wraps.
- Workspace fits the remaining desktop viewport and scrolls vertically only when
  necessary. The document remains the page scroller; tables retain horizontal
  access without a third vertical height-limited scrolling context. Preserve the
  seven current Workspace links and separate Filing Vault page unchanged.
- The root-only shell covers Overview, Signals, Investor Edge, Records,
  Operations and the $10K Agent hash routes. Existing narrow-screen navigation,
  tooltip, native dialogs/popovers and focus behavior remain intact.
- The shell delta is limited to `scripts/dashboard_assets/{app.js,index.html,styles.css}`,
  `tests/{dashboard_dom.test.cjs,dashboard_notification_integration.test.cjs}` and
  `docs/{PROJECT_STATE.md,DECISIONS.md,HANDOFF.md}`. It adds no workflow, collector,
  scoring, state, alert, simulation or hosting configuration change to current main.

The original shell commit passed **295 active Python tests in 398.82 seconds**,
including **41 DOM scenarios** (seven new shell/route/focus regressions) and
**32 notification scenarios** through existing wrappers. Syntax and diff checks
passed. The canonical generator produced **5,079 filings / 60 transactions /
1,496 reviews / 11 analyses / zero paper positions** from read-only fixtures;
all fixture hashes/sizes remained unchanged.

Rendered checks covered all six hash routes, record/exception focus, Source
filtering, Actions and Notification dialogs, help overlays, deep document scroll,
independent sidebar movement and widths **320px through 3840px**, with no horizontal
page overflow. Mobile wrapping and initial no-hash navigation remained visible.
These results predate integration with current main; rerun the combined tree before
publication. New remote Linux CI and Pages verification are still pending.

**Native-input limit:** browser-control wheel/key events were synthetic
(`isTrusted=false`). At the sidebar boundary, tool scroll commands moved the
document despite computed `overscroll-behavior-y: contain`; this does not establish
native wheel containment. Tool Tab presses did not establish native traversal.
DOM focus/navigation checks passed, but physical mouse/trackpad boundary behavior,
Page Up/Down/Home/End, touch/Safari, audio and physical CHG90 acceptance remain
unverified. Deployment authorization does not close those device gates.

Original evidence in the parent checkout: `.remediation/persistent-shell/validation-summary.json`,
`input-integrity-final.json`, `preview/`, `browser/` and `shell-dom-final/`.
Original test output is under the isolated worktree's `.remediation/full-shell-tests/`.
The local preview is http://127.0.0.1:8766/. New publication evidence belongs under
`.remediation/persistent-shell-publish/`; pending receipts are not results.
Raw state copies and local previews are evidence, never production authority.

## Next safe publication actions and separate gates

Finish current-main integration, review the exact delta and rerun combined tests
and generated-dashboard checks. Refresh full GitHub artifact-name enumeration,
exact producer attempts/jobs, expiry, ancestry and high-water marks. Push the
isolated branch, create the canonical PR, require successful CI on its exact head,
merge without discarding concurrent changes, and use the existing Pages workflow
on canonical main. Verify its exact successful attempt, consumed artifact IDs,
Pages artifact/live content and protected continuity before recording deployment
as complete. Do not modify workflow triggers or production state as a shortcut.

The Vault private API/cache remains inactive with published `{"api_origin":""}`;
this shell publication must preserve that honest configuration. The prior runtime
activation procedure below remains a separate task, not part of Deploy.
Obsolete queued writers **33219808359** and **33221027676** still require backend
clearance before the separately requested manual Legislative run; the support
draft remains unsent. The historical simulator rewrite concern remains unresolved
before future manual simulator work. Held PR #3, same-ID rename/privacy, legacy
retirement, Gmail delivery proof and physical-device acceptance remain separate.

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
