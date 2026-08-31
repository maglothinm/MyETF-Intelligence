# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: [issue #13 — 30-Day Filing Vault](https://github.com/maglothinm/MyETF-Intelligence/issues/13)

## Current task — publish the approved Filing Vault

Implement private 30-day filing storage, source-aware retrieval and an integrated
evidence viewer. Work is isolated in **codex/filing-vault**, worktree
**.worktrees/filing-vault**. Canonical ID **1349678672**, live name
**maglothinm/MyETF-Intelligence**, default **main**. Started from
`9d9e7bef326a0e24a5f846ea1310dec24a647019`; includes documentation-only main
successor `f2df59740b095417e3883fd81ac0a16c1d16fdad` and its release evidence.
The original shared checkout, its other branches and untracked `.codex/` are
preserved. Never implement or dispatch in legacy `maglothinm/MyETF`.

**The owner now explicitly requests Publish for this Vault implementation.**
Release commit `71b55ec3e35128f438c860ce01f4fb64b22100cc` is being integrated
with canonical main `676701ac1521458aefd72e2329d4e87c8781e41f` (Investor
Edge PR #15), preserving its parent Operations history PR #14 at `7a1108f`
and the verified Edge/Operations release receipts `895bc573` and `b5169f3`
on main. These last integrations change documentation only; tested application
code remains identical.
[PR #16](https://github.com/maglothinm/MyETF-Intelligence/pull/16) is open for this release. Push, canonical PR/CI, merge and existing Pages deployment are
authorized without another confirmation. No Vault release has completed yet.
Private runtime/storage/migration/timer activation remains separately unconfigured;
if absent, the released interface must retain honest catalog-only availability.

## Implementation

`backend/filing_vault/` provides the optional Flask API, six additive SQLAlchemy
tables, private Supabase storage, immutable SHA-256 evidence, known-ID catalog
admission, acknowledgement receipts, versioning and reconciliation. The existing
API can opt in; no tracker table/ledger is replaced. Development filesystem storage
must remain outside every Git checkout. TTL is exactly 2,592,000 seconds after
retrieval; metadata checks do not extend it. Missing/corrupt/expired bytes are not
served. An outage can fall back only to still-valid, verified and eligible bytes.

Separate House, Senate, OGE and executive-agency adapters use approved endpoints
and source-specific access classes. Existing Senate access logic is reused.
Form 201 and agency requests remain request-only; no submission or identity is
fabricated. Separate amendment records require exact source relationships from
the trusted catalog, not matching names or speculative endpoint inference.

The current static generator exports safe catalog metadata and adds View Filing /
Official Source across Records, transactions, reviews, signals/analysis, paper
positions, $10K results, Wallboard and Investor Edge detail. The dedicated Vault
inventory provides filters, search, provenance, original downloads, refresh,
version history and a responsive full-page viewer. PDF.js 6.3.289 renders locally;
original bytes are unchanged. HTML is displayed as a separate inert text preview.
201 vendor assets have a byte-size/SHA-256 manifest and retained licenses.

Configuration, six-table schema, all API routes, source boundaries, security,
acknowledgements and daily retention operations are in [FILING_VAULT.md](FILING_VAULT.md).
Runtime service/timer examples are under `config/filing-vault/`. Existing read-only
CI gains Vault tests; Pages gains a public API-origin variable and output checks.
No protected writer, schedule, concurrency group, alert credential, simulation
workflow or production state was changed or dispatched.

## Local verification

The original full run passed **463 tests** with no skips. Integration with
Operations passed **464 tests**, also without skips. The combined suite after
Investor Edge integration passed **524 tests**, with no skips. All **6 new
filing-link DOM cases** also passed; the existing CI now runs these cases. This includes **168
Vault cases** (62 backend, 72 provider, 34 UI), which run 22 generated Vault DOM
scenarios and 7 PDF-helper scenarios. Existing dashboard/notification/simulation
regressions and nested release checks pass. Python/JS syntax, all workflow YAML,
generated output, private-data/input-byte checks and 201 vendor hashes/sizes pass.
Government sources are mocked. PostgreSQL security SQL and transactional rollback
are tested with fixtures, not a live server. No local Bash run or new Vault remote CI is claimed yet. Vendor Git attributes preserve original bytes on Windows checkouts.

The in-app browser used a disposable in-memory TEST API and synthetic PDFs:
actual PDF.js rendering passed at 1440x1000 and 390x844 with no horizontal overflow.
Refresh retained retrieval/expiry while advancing validation time; cached reopening
did not repeat acknowledgement. The OGE request-only fixture kept Official Source
and its explicit access explanation. Browser warning/error logs were empty.
Screenshots in this worktree's ignored `.remediation/browser-evidence/`:
`vault-pdf-desktop.png`, `vault-pdf-mobile.png`, `vault-request-mobile.png`.
No real government, storage, source-access grant or alert service was used.
Physical iPhone/Safari and real PostgreSQL/Supabase runtime acceptance are unverified.

Latest pre-Vault audit: **166 Actions runs** checked, protected ZIP/member
hashes, inventories and simulation history unchanged. Pages **33391179240 /
attempt 1** at `676701ac`, artifact **9757512563**, succeeded with build job
**99484924587** and deploy job **99485120700**. Exact build logs consumed the
same three protected inputs below and simulator artifact **9734790733**.

## Existing production evidence — not Vault deployment

Read-only audit inspected all 158 Actions runs then available, exact successful
producer jobs/attempt windows, identity, ancestry, high-water marks, expiry,
existing ZIP hashes/sizes and retained JSON/JSONL inventories. Continuity passed;
no production state was restored or written by this task.

| Record | Artifact | Successful run / attempt | Job |
|---|---:|---|---:|
| Legislative | 9749549239 | [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) / 1 | 99417536057 |
| Executive | 9746602231 | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | 99391153447 |
| AI | 9749567326 | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | 99417669143 |

Prior PR #10 CI [33384840936](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33384840936),
main CI [33385044349](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044349)
and Pages [33385044313](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33385044313)
all succeeded on attempt 1. Pages artifact **9755242103**, build **9d9e7be**,
consumed those exact protected inputs. The prior 11:04:50 UTC receipt matched
21 live files; this task's fresh HTTP probes failed, so it does not independently
reassert those bytes. Recorded published counts: 5,079 filings / 60 transactions /
1,496 reviews / 11 analyses. Detailed upstream release evidence is preserved in
PROJECT_STATE/DECISIONS. Existing simulation history is unchanged. A final 12:01 UTC GitHub check found
160 runs, with only two unrelated CI additions and the same protected artifact
IDs, producing attempts, hashes and expiration.

## Remaining configuration and next safe action

Finish integration tests, push the integrated source to PR #16, require exact-source CI,
then merge and independently verify Pages and protected continuity. In parallel,
check whether the existing application runtime is configured; do not block safe
code/catalog publication merely because private retrieval is not activated.
To activate retrieval, provision the existing PostgreSQL database, private Supabase bucket,
server-only storage/signing credentials and HTTPS API host. Run the explicit additive
migration; configure exact origins/agency hosts and truthfully accepted government
source notices. Supply catalog metadata from verified canonical publisher output,
install the runtime daily timer, then set the public `FILING_VAULT_API_ORIGIN`
repository variable and release through canonical CI/Pages. Static publication
alone cannot activate cached viewing. No credentials or settings were changed. Source acknowledgements are not
implied by publication authorization. Local runtime environment/config files are
absent. A bounded configured Git credential-helper read returned no usable
credential, so remote API-origin variables, secret names and runtime environments
remain unverified; no alternative credential search was attempted.

Verify private storage/database isolation, HTTPS/CORS, aggregate proxy/egress rate
limits, exact source access, timer execution and physical mobile acceptance before
calling the feature operational. Request-only reports and arbitrary agency pages
without a known direct endpoint remain unavailable. Endpoint revalidation does not
claim exhaustive discovery of independently published amendments.

Preserve the separate Senate recovery incident/gate: obsolete queued writers
**33219808359** and **33221027676** require backend clearance before the separately
requested manual Legislative run. Its support draft remains unsent. Held PR #3,
same-ID rename/privacy, legacy retirement and external delivery/device acceptance
remain separate tasks. Preserve the Operations receipt
warning about a historical simulator-history rewrite before any future manual
simulator work; unchanged current history is not proof resolving that concern.
Never rebaseline or treat local cache as production-state
authority. Requery live GitHub provenance before any production operation.
