# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: [issue #11 — Investor Edge historical bootstrap](https://github.com/maglothinm/MyETF-Intelligence/issues/11).

## Current task — implemented and locally verified, not deployed

The user's attached bootstrap request is implemented in canonical repository
**1349678672**, current name **maglothinm/MyETF-Intelligence**, default **main**.
Work branch **codex/investor-edge-bootstrap** is in the isolated same-repository
worktree `.remediation/investor-edge-worktree`, based on main
`f2df59740b095417e3883fd81ac0a16c1d16fdad`. The commit containing this handoff
includes the implementation and evidence. It is local: no push, PR merge,
production dispatch or deployment is claimed.

Other tasks switched the shared checkout during the audit, so this task moved its
work into the isolated worktree. Preserve the root checkout, its current branch,
untracked `.codex/`, held PR #3, and the approved Senate/UI release evidence.
Never implement or dispatch from legacy `maglothinm/MyETF`.

## Completed work and actual result

Root cause: main already combined both restored branch histories and refreshed
Edge without candidates. The authoritative artifacts contained only 60 unique
transactions, one eligible purchase and one eligible identity, while 5,066
catalog-only filings lacked transactions. Normal baseline/unseen-only discovery
never reconstructed old cataloged filings. Legacy missing-ID rows and sequential
market scheduling were additional weaknesses.

Implemented canonical normalized history with stable/fallback deduplication,
retained dates/provenance and separate AI candidate selection; discovery-first
profiles; durable breadth-first observation scheduling; zero-candidate maintenance
and cache-only work at exhausted request budgets. Existing trackers now silently
reconstruct at most 20 catalog-only filings per run using official scanners,
existing access rules and an optional identity/hash-validated original-document
cache. No baseline reset, historical filing alert, AI candidate upgrade or new
Notification Center event occurs solely from reconstruction.

Global Edge maintenance must persist successfully before AI state can be promoted.
Initial failure stops candidate/market work. Existing pending and new candidate
deliveries wait for final successful maintenance and no earlier run errors, then
use the existing bounded channel-deduplicated queue. Candidate-specific Edge
fallback, formulas, alpha horizons, owner separation, modifier/hard caps,
time-censoring and the 40/40/30/40/2,200 limits are unchanged.

Root and standalone dashboards show the full bounded profile inventory plus
population, completeness, processed/pending and branch counts independently of
qualifying signal cards. Unknown legacy telemetry is not falsely labeled current.

In real artifact copies, two 20-filing House passes parsed 30 filings and added
299 unique transactions. Result: **359 transactions / 122 eligible purchases /
17 identities and profiles**, all **17 building / 0 complete**. No model analyses,
external alerts or new filing identities were created. Each of two Edge passes
processed 30 attempts; **122 observations remain pending** because local
acceptance supplied no provider credentials and cached price coverage was
insufficient. Deterministic price fixtures separately show pending 43 → 13 → 0
across two same-day passes with no new filings. Do not confuse that test with
live market completion.

Cache-only replay reproduced the 299 additions with zero requests; repeating the
same sample appended zero transactions and left output ledgers byte-identical.
All 47 original verified input files, original seen IDs/timestamps/prefixes, and
immutable AI state/analysis/run history remained unchanged. A final-code repeat
in new copies reproduced the 17-profile/122-pending result.

## Verification

**346 local tests passed**, no skips, with existing Node/JSDOM/axe dependencies
configured. Focused Edge suite: 67 passed; analyst suite: 30 passed. Included
36 DOM and 32 native notification scenarios. Python compilation, JS syntax,
YAML contracts, static generation and diff checks passed. Four workflow edits
add only test coverage/path filters; no schedule, credential, restore, artifact
upload, concurrency or writer change.

Actual-copy dashboard: **5,079 unique filings / 359 transactions / 1,496 review
items / 11 analyses / 0 paper positions**. In-app browser root and standalone
views both showed 17 profiles and accurate history counts, unavailable
performance, no console warnings/errors, and no horizontal document overflow at
the ordinary 1280×720 viewport. Physical devices, Safari, touch/audio and full
Linux `verify.sh` are not claimed for this task; no new remote CI ran.

[Detailed validation report](validation/investor-edge-bootstrap-2026-08-31.md)
contains A–J coverage, all source counts/failures, changed-file groups, run links,
hashes and limitations. Ignored evidence is in
`.remediation/investor-edge-bootstrap/`, especially `before-population.json`,
`actual-bootstrap-passes.json`, `actual-edge-passes.json`,
`bootstrap-document-diagnostics.json`, `final-code-acceptance/`,
`final-audit/` and `dashboard-preview/`. Copies are never production authority.

## Unchanged production authority

Final read-only audit completed **2026-08-31 11:48:35 UTC**. Exact canonical
workflow/display-name/job/attempt windows, ancestry, global producer high-water
marks, expiration, ZIP digests, complete inventories and continuity passed.

| Protected state | Artifact | Successful run / attempt | Producer job |
|---|---:|---|---:|
| Legislative | 9749549239 | [33369634244](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369634244) / 1 | 99417536057 |
| Executive | 9746602231 | [33360633323](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33360633323) / 1 | 99391153447 |
| AI | 9749567326 | [33369677492](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33369677492) / 1 | 99417669143 |

All three producer commits are `3902968d5d70cd00030248ae4a6bcea18aa2e6ea`.
Their original production populations remain unchanged (60 transactions, one
eligible identity/profile). Isolated simulator artifact **9734790733**, run
**33320677882 / 1**, job **99281977011**, remains two retained rows, unchanged.
Neither simulation changed or ran; no protected state or live alert credentials
were added to simulation workflows.

Live [dashboard](https://maglothinm.github.io/MyETF-Intelligence/) remains the
prior approved review-UX release: successful Pages **33385044313 / 1**, build
**99465681041**, deploy **99465807219**, artifact **9755242103**, source
`9d9e7bef326a0e24a5f846ea1310dec24a647019`. Four fixed live Pages URLs returned
HTTP 200 and matched the artifact. This is not deployment of the bootstrap fix.
The previous publication and Senate incident evidence remain in PROJECT_STATE
and `docs/incidents/senate-efd-2026-08-30.md`.

## Remaining limits and next safe action

- **122 pending market observations** in the acceptance copy; no real
  provider-backed pending reduction or completed market return is proven.
- **5,036 catalog-only filings** remain: 849 House (839 outside the sample,
  eight local missing-Tesseract failures, two existing multiline-amount scanner
  failures), 90 Senate unattempted in this House-only acceptance, and 4,097 OGE
  Form 201 access-request listings. Exact report IDs are in the validation report.
  Linux already installs OCR but these exact documents remain unverified there.
- Externally configured source manifests/documents are not automatically retained
  in a state artifact. Only files within its existing uploaded state directory
  persist through that path; never treat document caches as state authority.
- Obsolete runs **33219808359** and **33221027676** still show queued / attempt 1 /
  zero jobs and artifacts. Preserve the existing gate on any separate manual
  production dispatch. The separate authorized Support draft remains unsent;
  no backend clearance is claimed.
- Held PR #3's additional pre-manifest allowlist does not include these newer
  artifacts. That held migration gate is unchanged; this work neither adopts nor
  modifies its allowlist or production restore policy.
- Same-ID rename/privacy, legacy settings retirement, Gmail delivery proof and
  physical-device acceptance remain separate open work. No credentials/settings
  were changed, and no production, alert or heartbeat endpoint was exercised.
- Separate read-only review note: the unchanged `filing_simulation.yml`
  notification-isolation step reserializes the full JSONL history after its
  predecessor-prefix check. Noncanonical predecessor formatting could change.
  This existing simulator path was not executed or modified; audit it before
  future simulator work rather than inferring byte-preservation from this task.

Next: review/release the local commit through canonical CI when authorized, then
verify the actual sole-writer artifact successors and profile/pending counts over
normal runs with configured market data. Freshly recheck provenance before those
operations. Do not upload acceptance copies, rebaseline, clear safety gates,
dispatch an alternate writer or claim the live one-profile symptom is already
resolved by a local commit.
