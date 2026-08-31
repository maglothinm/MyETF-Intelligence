# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: [issue #11 — Investor Edge historical bootstrap](https://github.com/maglothinm/MyETF-Intelligence/issues/11).

## Current task — full deployment requested; production bootstrap gated

The owner requested **Fully deploy** after the Investor Edge release. The code is
already published, but this follow-up cannot establish full production bootstrap
while the existing manual Legislative gate remains unresolved.

Canonical repository **1349678672** is currently **maglothinm/MyETF-Intelligence**,
default **main**. This task uses clean isolated branch
`codex/investor-edge-bootstrap` in `.remediation/investor-edge-worktree`,
fast-forwarded to `642cebc45a489b7b3faf9b2840a716002828fafa`.
The shared checkout and unrelated work are preserved. The documentation commit
containing this handoff changes no executable source or production state.

## Verified current deployment and continuity

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

## Exact blocker and next safe action

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

## Separate retained limits

The newer Filing Vault catalog/viewer is published, but its private API/storage
runtime remains inactive. Its existing host, database, private bucket, credentials,
legitimate source acknowledgements and timer are separate issue #13 activation
prerequisites; this task did not create infrastructure or infer source consent.
See [FILING_VAULT.md](FILING_VAULT.md) for that distinct procedure.

Source-original access, parser/OCR limitations, actual market completion, Gmail
delivery proof, physical devices, held PR #3, the historical simulator-prefix
concern, same-ID rename/privacy and legacy retirement remain as documented.
