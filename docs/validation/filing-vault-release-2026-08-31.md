# Filing Vault publication receipt â€” 2026-08-31

Work record: [issue #13](https://github.com/maglothinm/MyETF-Intelligence/issues/13).
The owner explicitly requested **Publish**. Canonical repository ID **1349678672**,
live name **maglothinm/MyETF-Intelligence**, default branch **main**. The existing
GitHub Pages deployment remains the only publication path; no new repository,
production writer, simulation run or external alert was created or dispatched.

## Source and scope

[PR #16](https://github.com/maglothinm/MyETF-Intelligence/pull/16) merged tested
head `755349945bf8fdd4389a8c6aa6d770370df487af` as
`104fc519d883c93153c639e85a2474d3d816a336`. Their trees match exactly.
The release preserves the approved Operations and Investor Edge changes and their
verified-release documentation through `b5169f3`.

Published source includes the optional private Flask/SQLAlchemy/Supabase runtime,
six additive tables, exact 30-day retention, immutable document hashes and versions,
source-specific access rules, acknowledgement receipts, lifecycle tooling and
integrated filing actions/catalog/viewer. PDF.js is self-hosted with original
licenses and a 201-file hash/size manifest. Conflicting retained filing IDs remain
reviewable but cannot become View Filing links through compact projections.

Publication does **not** establish active document retrieval. The private API,
PostgreSQL migration, private bucket, verified catalog delivery, daily timer,
HTTPS/CORS, government-source access and physical-device acceptance require the
runtime checks in [FILING_VAULT.md](../FILING_VAULT.md). No source acceptance,
credential, cached availability or successful retrieval is inferred from Publish.

## Verification

The complete local suite passed **524 tests with no skips**. Six additional
filing-link DOM cases passed. The suite includes mocked government providers,
cache expiry/hash/version/acknowledgement security and generated dashboard/DOM
checks. All 201 vendored asset hashes/sizes, Python/JavaScript syntax and workflow
YAML passed. Earlier desktop/mobile browser acceptance used a clearly TEST-marked
in-memory API and synthetic PDFs; it is not production runtime acceptance.

| Run | Attempt | Source | Result |
|---|---:|---|---|
| [PR CI 33392460770](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392460770) | 1 | `7553499` | Success; job `99489078881`, 441 pytest cases, 6 link DOM cases, Linux `VERIFICATION PASSED` |
| [Main CI 33392608687](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392608687) | 1 | `104fc51` | Success; job `99489550762`, 441 pytest cases, 6 link DOM cases, Linux `VERIFICATION PASSED` |
| [Pages 33392608680](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33392608680) | 1 | `104fc51` | Success; build job `99489550775`, deploy job `99489776345` |

## Protected-state continuity

The prepublication audit inspected **167 Actions runs**, including 82 producer
records, exact run attempts and successful producer jobs, artifact upload/attempt
windows, repository/workflow/default-branch identity, expiry, ancestry and producer
high-water marks. The final **12:45:06 UTC** audit checked **169 runs / 82
producer records**: protected/simulator high-water marks and metadata remained
unchanged, and Pages `33392608680` was the latest publisher. No cache was treated
as production authority. Protected ZIP and
every member hash/size matched the prior exported snapshot; JSON/JSONL inventories
parsed without changes. These are read-only evidence copies, never restored or
uploaded as production state by this publication task.

| Protected artifact | Artifact ID | Producing run / attempt | Successful job |
|---|---:|---|---:|
| legislative-tracker-state | 9749549239 | [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) / 1 | 99417536057 |
| executive-tracker-state | 9746602231 | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | 99391153447 |
| ai-analysis-state | 9749567326 | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | 99417669143 |

All three producer commits are `3902968d5d70cd00030248ae4a6bcea18aa2e6ea`,
an ancestor of the published source, with artifacts unexpired until 2026-11-29.

| Archive | Bytes | SHA-256 |
|---|---:|---|
| Legislative | 46,720 | `fcd8d2398fe1f6631e87023aa90b90e695fd64be21c5034df1c7196c2ded9479` |
| Executive | 509,704 | `997a0eaf63b4b3bd33bbda34bfc40a633802c04cfd891f6a2dca726d93a2b4be` |
| AI | 272,092 | `318e1892cc74505711dd362ba96255d060e5a099d174f36627af7f222c981aa9` |

Raw retained counts: Legislative 983 filings / 65 transactions / 19 purchases /
1 review / 31 runs; Executive 4,109 filings / 1,495 reviews / 23 runs; AI
12 analyses / 36 runs. Public counts are deduplicated projections and need not
equal these raw ledger counts.

Isolated simulator artifact **9734790733**, run **33320677882 / attempt 1**,
job **99281977011**, remains two history rows. This unchanged current snapshot
does not resolve the separately recorded historical simulator rewrite concern.

## Live publication and remaining activation

Pages artifact **9758066553**, **3,872,316 bytes**, has SHA-256
`28dd09b87b99f55636f9b47fe1be4254323c0ca10c33d1edeafd00151696ad4c`.
Exact build logs restore the three protected artifacts above and simulator
**9734790733**. The public API-origin variable is blank in the build log.

The [live Vault](https://maglothinm.github.io/MyETF-Intelligence/filing-vault.html)
shows **5,079** retained filings and honest unavailable retrieval. The House filter
shows **883** rows, and opening an exact filing preserves its ID and official URL
with disabled source refresh and an explicit no-document-retrieved explanation.
Live desktop (1280px) and mobile (390px) checks found no horizontal overflow or
console warnings/errors. No government source was opened, retrieved or accepted
in these checks. This does not establish physical iPhone/Safari acceptance.
At **12:43:45 UTC**, all **238 served content files** returned HTTP 200 and
matched artifact bytes/hash/size; the archive has 239 files, with only the empty
`.nojekyll` marker excluded from the HTTP check. All **201 pinned PDF assets**
matched their manifest; JavaScript modules and WebAssembly had valid MIME types.
Both the emitted and live configuration are exactly `{"api_origin":""}`. The
catalog contains 5,079 unique IDs with allowed scalar metadata. Public JSON
private-field checks passed; no government PDFs, database files, protected state
or raw ledgers were present in the Pages archive.

Local runtime configuration and Vault
environment variables were absent. A bounded attempt to use the configured Git
credential helper returned no usable credential; no alternate credential search
or configuration mutation was attempted. Remote secret metadata and runtime
environments remain unverified.

Issue #13 stays open for private runtime/source/device acceptance. The next safe
action after publication is to configure the existing private runtime, execute the
explicit additive migration, supply a verified catalog, test security and source
access, install the daily timer, and publish its public HTTPS API origin through
the canonical Pages configuration. Static publication alone cannot operate a
30-day cache. Never put raw documents or server secrets in Pages or Git.

The obsolete writer queues, held PR #3, repository rename/privacy and legacy
retirement, external delivery and physical-device gates remain separate.
Read-only release evidence is retained under the isolated worktree's ignored
`.remediation/publish-vault/` directory; raw state archives are not committed.
