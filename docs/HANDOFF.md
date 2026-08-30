# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Status: **safe branch revision verified; production completion blocked by stuck obsolete GitHub runs**
Work record: [issue #1](https://github.com/maglothinm/MyETF-Intelligence/issues/1), open.
Review: [draft PR #3](https://github.com/maglothinm/MyETF-Intelligence/pull/3), unmerged.

## Current task and exact scope

The owner said "Finish" after approving the public review-branch push. Complete
remaining safe revision checks, without reactivating deferred features or
bypassing production-state gates. Simulation Gmail, extra durable storage,
persistent Git-backed paper agent, AI recovery journal and dependent dispatch
Worker remain held. AGENTS.md is unchanged.

Canonical repository **1349678672** is public **maglothinm/MyETF-Intelligence**.
Remote: `https://github.com/maglothinm/MyETF-Intelligence.git`.
Branch: **codex/production-remediation**. Rechecked default main remains
**4a9135a8c12af6eebfce01cf33772ffa13e41951**.
Published branch head before this checkpoint-only follow-up:
**a7925448524014896d7624eccb1d50d6434a42e1**.
Implementation: **020351a86861020d1a0f579b8ccdd7f218be3994**.
Fresh-checkout CI setup fix: **4cb6d5677daa60fff507d86502e156b70200a8ff**.
This follow-up changes only the exact migration allowlist and operational docs.

Preserve unrelated untracked `.codex/` and ignored
`.remediation/held-feature-drafts/`. Neither is published.
No merge, production dispatch, protected upload, mail, Pages deployment, rename,
visibility change, legacy shutdown or archive was performed.

## Completed revision and verification

The compatible implementation includes artifact-only restore/seal validation,
exact attempt/job provenance and producer high-water checks, full inventories,
ledger-prefix and identity preservation, adjusted-price Investor Edge,
effective-sample gating, immutable Edge archives/aliases, and both simulations'
existing permitted outputs without live credentials. See [STATE_SAFETY.md](STATE_SAFETY.md).

- Latest local full suite: **244 passed in 16.67s**.
- Static checks: 49 Python files, 5 embedded Python blocks, 5 JSON, 11 YAML;
  three generated JavaScript files, recovery manifest and credential scan passed.
- Windows has no Bash; Linux provides the full 58 shell checks and verify.sh.
- CI [33313544655](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33313544655)
  passed at `4cb6d56`, attempt 1, job `99262749719`: 244 tests plus full
  verify.sh, 105 repeated state/workflow tests and all 58 shell checks.
- CI [33313630046](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33313630046)
  passed at `a792544`, attempt 1; no artifacts.
- This checkpoint-only follow-up's CI is attached to PR #3; inspect its exact
  head/run separately before promotion.
- Earlier CI `33313439413` failed because pytest's ignored parent was absent
  on a fresh checkout; corrected by `4cb6d56`, not suppressed.
- Prior actual-input dashboard and deterministic TEST scoring passed without
  model/market/notification calls and with original input hashes unchanged.

## Current protected-state evidence

All current artifacts below were unexpired and verified with the actual shared
helper: global artifact selection, repository/branch/workflow, exact successful
attempt/job, ancestor commit, producer high-water, GitHub ZIP digest, complete
schemas/inventories, original/prior ledger byte prefixes and retained IDs/Edge
outcomes. Actual read-only restoration also passed for all three.

| Pipeline | Run | Attempt | Job | Artifact | Counts |
|---|---:|---:|---:|---:|---|
| Legislative | 33306989441 | 1 | 99245167496 | 9730784030 | 983 filings; 65 transactions; 19 purchases; 1 review; 26 runs |
| Executive | 33312565343 | 1 | 99260139758 | 9732455687 | 4,109 filings; 1,495 reviews; 19 runs |
| AI | 33312663088 | 1 | 99260390680 | 9732466504 | 12 analyses; 27 runs |

All producer SHAs are main `4a9135a`.
New exact allowlist entries: **9732455687**, **9732466504**. Existing six entries
are unchanged. Comparisons included original artifacts **9723708154**,
**9723732691**, **9723743439**, and previous successors **9730784030**,
**9727833986**, **9730794047**. Full file/ZIP hashes are in
[protected-state-migration.json](protected-state-migration.json).
This is verified continuity, not a rebaseline or promotion.

Historical simulation read-only restore also passed: artifact **9723569827**,
run **33283104953**, attempt **1**, job **99181508496**, one complete history row.
No simulation or production successor was uploaded.
Ignored reproduction: `.remediation/verify_live_state.py`.
Ignored ZIP exports/candidate inventory/evidence: `.remediation/live-audit/`.
Re-query before promotion; these IDs are not permanent restore pins.

## Exact remaining blocker and next safe action

Both obsolete runs remain **queued**, each with **zero jobs and zero artifacts**:

- [33219808359](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33219808359)
- [33221027676](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33221027676)

This session reverified canonical ID, removed path
`.github/workflows/legislative_trade_tracker.yml`, and historical SHA
`b9cf0f3e3863de69d92ae01f35f1c154a082f56a` before retrying cancellation.
**Ordinary cancel and force-cancel returned HTTP 409 for both runs.**
GitHub workflow **344663675** reports **deleted**, but file/workflow deletion is
not proof that these already queued runs cannot execute.

**Owner action:** ask GitHub Support to terminally cancel those exact two stuck
runs, or provide authoritative confirmation that neither can execute or publish
protected state. Do not substitute a green PR, zero current jobs, or deleted
workflow for containment. No broad Actions disablement or run deletion was tried.

Keep PR #3 draft/unmerged and issue #1 open. After containment, re-query current
artifact lineage and allowlist, obtain any necessary explicit promotion authority,
then perform production acceptance. Do not dispatch production or perform the
rename/cutover before safety gates pass.

Other unchanged limits:

- Existing [Pages](https://maglothinm.github.io/MyETF-Intelligence/) is from
  successful main publisher
  [33312700469](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33312700469),
  not this revision.
- Live adjusted-price entitlement, sufficient historical samples, Gmail delivery
  and browser/Safari acceptance remain unverified. Held functionality is not
  implemented acceptance: historical replay is not a persistent paper agent.
- Same-ID rename/privacy and legacy repository **1033519491** Actions/Pages
  shutdown/archive remain incomplete.
- The earlier detailed public issue-comment update was rejected by host review as
  a separate disclosure outside branch-push approval. No comment was posted or
  retried through another route; separate approval is needed if desired.
