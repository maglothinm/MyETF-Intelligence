# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work: [issue #19](https://github.com/maglothinm/MyETF-Intelligence/issues/19).

## Current task — external scheduler activation remains gated

Canonical ID **1349678672**, live repository **maglothinm/MyETF-Intelligence**,
default **main**. PR #20 and its clock follow-up PR #21 are merged.
Final deployed source **5932a49950384fb9cb2bdab93c4093ea596789a1** has a tree identical
to tested source `2a13b6c6d2d3d51cf7a4ec5ac05a45e2451ad46c`. Work is isolated
in `.worktrees/scheduler-freshness`: implementation branch
`codex/freshness-clock-audit`, final receipt branch `codex/scheduler-release-receipt`.
Original checkout `9d9e7be`, local main and unrelated work remain preserved.
Never implement or dispatch from legacy `maglothinm/MyETF`.

## Completed work and proof

Central freshness policy, truthful source timestamps, header/Operations/Monitor
aging, read-only exact Actions observations, Executive half-hour cron, safe
canonical external dispatch contract and uncertain-retry guard are deployed.
The external Worker is inert. GitHub cron remains enabled.

Local **633 tests, no skips**, plus **11 Worker cases** passed. PR CI
**33420373213 / 1** and main CI **33420549112 / 1** each passed 550 Python,
6 filing DOM, 11 Worker and Linux verification. The old schedule expectation in
verify.sh and its checksum were corrected; safety assertions remain intact.

Initial Pages **33420549071 / 1** succeeded, source `b9380f2`, artifact **9768730400**.
All **250 live files** matched at that checkpoint. Exact logs and full authority audit confirm:
Legislative **9764350004 -> 33408974583 / 1**;
Executive **9760298853 -> 33398375467 / 1**;
AI **9764387095 -> 33409079174 / 1**. Provenance/high-water/expiry/hashes and
continuity passed at 17:39 UTC; protected inputs and simulator 9734790733's two
rows are unchanged. Header correctly shows overdue with source **15:32:55 UTC**,
despite generation at **17:38:02 UTC**. Desktop/portrait Operations and Monitor
checks pass with no browser warnings/errors. Full jobs/hashes/counts and limits
are in [the release receipt](validation/scheduler-freshness-2026-08-31.md).
Ignored proof is under this worktree's `.remediation/preflight`, `postflight`,
`scheduler-live-integration` and `scheduler-release-check`.

## Final verified result and next safe action

Clock follow-up deployed from PR #21, source `5932a49950384fb9cb2bdab93c4093ea596789a1`.
PR CI **33421833418 / 1** and main CI **33421979782 / 1**
succeeded. Final Pages **33421979811 / 1**, artifact **9769279578**, succeeded;
all 250 live files match. Fresh exact-attempt provenance/high-water/hashes and
continuity passed at **2026-08-31T17:57:09Z**. Protected/simulator inputs remain
unchanged. The live header is correctly overdue; source time remains 15:32:55 UTC.
Full regression again passed **633 tests, no skips**; clock coverage passed
**65 DOM + 42 native cases** and independent review. No known code blocker remains.

Repository/UI rollout is verified. Next safe action is to resolve the GitHub
clearance gate and provision the external scheduler, then observe several actual
cycles before claiming cadence or choosing cron redundancy. No production writer
was manually dispatched. Issue #19 remains open for infrastructure acceptance.
Final proof: `.remediation/final-postflight` and
`.remediation/scheduler-release-check/33421979811-1`; committed release receipt
contains exact jobs, hashes, input counts and remaining limitations.

## Infrastructure blockers

External scheduler activation remains blocked by GitHub backend clearance for
obsolete queued writers **33219808359** and **33221027676**. No diagnostic writer
or external scheduler may bypass that gate. Cloudflare account/Worker/scoped
secret configuration and multiple real 15/30-minute cycles are still required.
At 17:57 no new collector had arrived; latest measured gaps were 468.5/493.8m.
Actual post-release source advancement and external delivery remain unverified.
Keep GitHub cron until a separately recorded redundancy decision. No producer,
simulation, alert test, rebaseline, credential or repository setting was manually
dispatched/changed. Vault, held PR #3, physical-device, simulator-history and
cutover gates remain separate below.

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
