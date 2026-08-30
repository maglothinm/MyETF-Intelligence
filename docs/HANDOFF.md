# PolitiTrack active handoff

Updated: **2026-08-30 UTC**
Status: **revision committed locally; public publication blocked pending approval**
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
  A subsequent documentation-only commit records the publication blocker.
- Branch push was rejected before execution by the host safety review: the full
  payload would be published to a public GitHub repository without sufficiently
  explicit current-turn approval. No push, remote branch, PR, or new CI run.
  Do not bypass the rejection with another tool, token, or upload route.
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

All were rechecked unexpired. Original artifacts 9723708154, 9723732691,
9723743439 and these successors pass the revised schema validator, exact ZIP/file
hashes, old JSONL prefix preservation and ID continuity. Full evidence lives in
`protected-state-migration.json`; none is a permanent restore pin.

**244 active pytest tests passed in 13.82s**. Static checks passed for 49 Python
files, five embedded Python blocks, five JSON files, 11 YAML files, three generated
JavaScript files, recovery manifest and credential-pattern scan. Bash is absent
and WSL not installed: 58 Bash checks and full verify.sh require Linux CI.

Actual-input preview built at ignored `.remediation/revision-preview/`.
Isolated TEST scoring from verified copied inputs passed, with zero network/model
requests/emails and source hashes unchanged. Scratch reproduction:
`.remediation/check_current_revision.py`. Live provider entitlement, sufficient
sample coverage, and browser/Safari behavior remain unverified.

## Remaining blockers and next safe action

1. Request explicit owner approval to publish implementation commit `020351a`
   plus this documentation follow-up to public canonical GitHub. Until approved,
   keep both local. After approval, push only the reviewed revision, open a draft
   PR, and verify the read-only offline CI (including Linux verify.sh). Do not
   merge or dispatch production. Leave `.codex/` and held drafts untouched.
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
   publisher [33307049036](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33307049036)
   are prior-deployment evidence only. This revision has not been deployed.
5. Gmail secrets were absent at the authenticated check; no delivery proof exists.
   Notification recovery is deferred, historical replay is not a persistent agent,
   and the dashboard still links to Actions rather than dispatching directly.
6. Same-ID rename/privacy and legacy ID 1033519491 Actions/Pages shutdown/archive
   are not completed. Keep issue #1 open and report exact CI/review state there.

Do not equate a tested branch with production acceptance.
