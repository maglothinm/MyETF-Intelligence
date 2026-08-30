# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Status: **published as draft PR #3; fresh-checkout CI setup correction pending verification**
Work record: [canonical issue #1](https://github.com/maglothinm/MyETF-Intelligence/issues/1), open.

## Task, identity, and branch

Continue the approved remediation while holding simulation Gmail, extra durable
storage, persistent Git-backed paper agent, AI recovery journal, and dependent
dispatch Worker. The owner explicitly deferred these features; do not ask the
same contract question again or silently reactivate the drafts. AGENTS.md is unchanged.

- Canonical ID **1349678672**, public `maglothinm/MyETF-Intelligence`.
- Remote `https://github.com/maglothinm/MyETF-Intelligence.git`.
- Revision branch **codex/production-remediation**, based on rechecked main
  **4a9135a8c12af6eebfce01cf33772ffa13e41951**.
- Implementation commit: **020351a86861020d1a0f579b8ccdd7f218be3994**.
  Documentation follow-up `6ffb1639aff2db13890b855acecefb90e6ac87ec` was pushed
  after the owner's explicit "Yes push" resolved the prior publication blocker.
- [Draft PR #3](https://github.com/maglothinm/MyETF-Intelligence/pull/3) is open
  against unchanged main. This authorizes review publication and offline CI only.
- No default-branch merge, production dispatch, mail, deployment, rename or archive.
- Preserve unrelated `.codex/`. Held feature drafts, including snapshots of their
  prior analyst/workflow wiring, are recoverable under ignored
  `.remediation/held-feature-drafts/`, not active source or committed code.

## Revision delivered for review

See [STATE_SAFETY.md](STATE_SAFETY.md) for the complete design and known limitations.

- Shared artifact-only restore/seal helpers: full schema/hash/inventory validation,
  exact run/attempt/job provenance, global newest/high-water checks, immutable
  ledger prefixes/IDs, and final pre-upload authority recheck.
- Exact pre-manifest migration inventory for six independently verified exports.
- Optional historical simulator restoration fails closed after any previous
  production; missing/expired/corrupt state never silently disappears.
- Investor Edge adjusted stock/benchmark prices, versioned cache provenance,
  cutoff guards, minimum effective-sample neutral status, capped-base negative
  modifiers, source-provided IDs, retained profile aliases and immutable archives.
- Both simulations have only permitted outputs and no real notification/provider
  credentials. TEST input hashes are compared immediately before artifact upload.
- Existing analyst delivery behavior retained; external journal removed.
- Behavioral state tests, parsed workflow contract guards, full active CI suite,
  static/generated-JS checks, credential-pattern checks, recovery verification.

## Evidence

| Pipeline | Successful run | Attempt | Job | Artifact |
|---|---:|---:|---:|---:|
| Legislative | [33306989441](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33306989441) | 1 | 99245167496 | 9730784030 |
| Executive | [33297296482](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33297296482) | 1 | 99219056330 | 9727833986 |
| AI | [33307012616](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33307012616) | 1 | 99245230528 | 9730794047 |

These are the previously byte-verified checkpoints. Original artifacts 9723708154, 9723732691,
9723743439 and these successors pass the revised schema validator, exact ZIP/file
hashes, old JSONL prefix preservation and ID continuity. Full evidence lives in
`protected-state-migration.json`; none is a permanent restore pin.

**244 active pytest tests passed in 13.82s**. Static checks passed for 49 Python
files, five embedded Python blocks, five JSON files, 11 YAML files, three generated
JavaScript files, recovery manifest and credential-pattern scan. Bash is absent
and WSL not installed: 58 Bash checks and full verify.sh require Linux CI.
First Linux run [33313439413](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33313439413),
attempt 1, failed with 61 passed and 183 setup errors: the ignored parent of
pytest's temporary base was absent on a fresh checkout. `pytest.ini` now points
to ignored `.test-tmp-pytest` directly under the checkout; follow-up CI is required.

New scheduled main producers observed during publication, all successful attempt 1:
Executive run `33312565343`, job `99260139758`, artifact `9732455687`;
AI run `33312663088`, job `99260390680`, artifact `9732466504`.
Both are unexpired and have checked attempt/job metadata, but their bytes and
continuity were not validated in this publication session. Legislative remains
run `33306989441`, attempt 1, artifact `9730784030`. No artifact was written by
this review revision.

Actual-input preview built at ignored `.remediation/revision-preview/`.
Isolated TEST scoring from verified copied inputs passed, with zero network/model
requests/emails and source hashes unchanged. Scratch reproduction:
`.remediation/check_current_revision.py`. Live provider entitlement, sufficient
sample coverage, and browser/Safari behavior remain unverified.

## Remaining blockers and next safe action

1. Push the fresh-checkout test configuration correction and verify PR Linux CI
   (including full verify.sh). Keep PR #3 draft; do not merge or dispatch production.
   Leave `.codex/` and held drafts untouched. Record final CI evidence in issue #1.
2. Runs [33219808359](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33219808359)
   and [33221027676](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33221027676)
   remain queued at removed `legislative_trade_tracker.yml`, SHA
   `b9cf0f3e3863de69d92ae01f35f1c154a082f56a`, canonical ID. Ordinary and
   force-cancel returned HTTP 409 previously. No production dispatch or cutover
   until these writers are cancelled or proven incapable of execution.
3. Before promotion, re-query current protected producers/attempts/artifacts.
   A newer unmanifested producer requires a newly exported, hash-verified
   allowlist update, not fallback or a blank baseline.
4. Existing [Pages](https://maglothinm.github.io/MyETF-Intelligence/) and successful
   publisher [33312700469](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33312700469)
   are prior-deployment evidence only. This revision has not been deployed.
5. Gmail secrets were absent at the authenticated check; no delivery proof exists.
   Notification recovery is deferred, historical replay is not a persistent agent,
   and the dashboard still links to Actions rather than dispatching directly.
6. Same-ID rename/privacy and legacy ID 1033519491 Actions/Pages shutdown/archive
   are not completed. Keep issue #1 open and report exact CI/review state there.

Do not equate a tested branch with production acceptance.
