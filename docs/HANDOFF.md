# PolitiTrack active handoff

Updated: **2026-09-08**

Canonical repository: **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Active task

Implement [issue #155](https://github.com/maglothinm/MyETF-Intelligence/issues/155):
Manual Parser Exception acknowledgements returning after refresh/publication.
Work is isolated on `fix/parser-acknowledgement-persistence`, based on
`061b8a4dda7f6c0940e8d3f92c6aed3dbb957f0f`. PR #154's unrelated Current Opportunity
feature branch was not used or changed.

## Implementation and local evidence

- Publication absence no longer clears browser acknowledgement history.
- Structured exception codes and logical identities exclude mutable reason text.
- Retained evidence IDs and JSONL remain intact; reprocessing avoids duplicate
  review rows/notifications by logical identity.
- Legacy v1 browser storage learns stable identities; Restore removes matching
  aliases, and a materially changed logical identity remains active.
- Full identity inventory is published with the JSON/CSV/model. Existing count,
  category and evidence-ID validation remains; identity validation is additive.
- The 500-entry retention policy, acknowledged inventory and retained evidence
  semantics are documented in `docs/parser-review-acknowledgements.md`.
- CI now runs dashboard DOM regressions and watches the shared identity module.

`python -m pytest -q tests`: **1,157 passed, 2 skipped**, including all three
required tracker/dashboard Python suites and 74 generated-dashboard DOM tests.
`bash verify.sh`: **passed**. `git diff --check`: **passed**.
Four AI scoring test failures reproduced on untouched main were corrected with
a test-only fixed scoring clock; production scoring rules are unchanged.

Unrestricted root `pytest -q` also collects four historical `backend/tests` files
that fail to import `api`. Their legacy database module opens an external database
at import and their tests delete database rows. They were not redirected to live
data or altered for this parser fix. Canonical offline/CI suites are under `tests/`.
The two skipped optional integration cases require environment support beyond
this Windows test run; canonical Actions supplies its configured environment.

## Production evidence and boundary

Read-only public `/readyz` returned ready with snapshot
`a3b9ac81339d558f751f0a35d864c6218d1d2926648bba4ac5a2fe1c3db247ff` during this task.
The two live review IDs were `review:26d3a33b8b6c3b4b0018eabd672efcda` and
`review:69bba9ad5c91225a4ba4ed56fd7e30d4`; both use the old Senate image-viewer
message covered by the compatibility classifier. These reads establish the old
publication's shape, not deployment of this fix.

Existing recovery certificate artifact `9997087643`, run `34059488724` attempt 1,
remains unexpired with API digest
`6b35663482221d972f0967f0d2fba5eb68865609541c5693d29c093d4369c58f`.
Its historical production certificate remains separate from this code change;
no new protected artifact was written and no production continuity mutation occurred.

## Next safe action

Review the implementation PR and its canonical Actions checks. After merge,
release through the existing Runtime v2 procedure, then exercise the two-exception
acknowledge / refresh / zero-publication / return / restore sequence against the
deployed build. No merge, deployment, state reset, rebaseline, scheduler change,
or live acknowledgement mutation is represented as complete by this handoff.
