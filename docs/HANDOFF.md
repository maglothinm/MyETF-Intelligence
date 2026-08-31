# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: [issue #13 — 30-Day Filing Vault](https://github.com/maglothinm/MyETF-Intelligence/issues/13).

## Current task — publication delivered; private runtime activation remains

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

## Delivered source and verification

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

## Protected continuity and retained evidence

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
is in this worktree's `.remediation/publish-vault/` and `.remediation/browser-evidence/`.
Raw state copies are read-only evidence, never production restore authority.

## Remaining configuration and next safe action

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
