# PolitiTrack active handoff

Updated **2026-09-08 15:33 UTC**. Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Active authorized task

Complete the owner's merge/deploy/go-live request for issue #155. PR #156 merged as `140944de3d0da9b76e6318714babad75212dab32`, but its first publication failed live acceptance: JSON classified two retained House paper/scanned PTRs as `other`, then insights reclassified them as `manual_exception` after identity enrichment. The corrective branch `fix/parser-review-category-stability` classifies from normalized exception fields on the first pass, keeping exported JSON, CSV and insights consistent. PR #154 remains excluded.

The correction preserves evidence IDs, source rows, timestamps, logical identities and strict acknowledgement validation. The manual inventory will correctly contain four entries: the two original Senate exceptions plus two retained House paper PTRs. Verify that legacy acknowledgements for only the Senate IDs remain recognized while House stays active.

## Verification and recovery evidence

- Regression assertions cover all four legacy message families and two complete-site cases (reason on review versus inherited from filing). They reproduced three failures before correction.
- Corrected canonical suite: **1,159 passed, 2 skipped**. Optional PostgreSQL cases require CI. A preliminary rerun lacked `jq` on PATH; after restoring the existing tool path the complete suite passed.
- Original build `4f8408c8-e543-4e7e-bc9f-4ca7c509e539`, image `sha256:574974380e800fc49a0074dc793a803ae3230465ec6b470ec5dfea9e4468686d`, failed live publication acceptance despite successful Executive/AI/Dashboard executions.
- Rejected snapshot `e1f43a632e28ba6ff4005cb079e4b713153ec12fff1071d5090e1722d992eca5` remains retained. No head was rewound and no history deleted.
- All six resources are restored to image `sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`, with producer source restored to `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`.
- Dashboard `polititrack-dashboard-jktkd` appended valid publication `8286a37ad8db2657fe11244098e708c3b4196f462296b7b5e21e721488974f5b`; served bundle matches retained source, and JSON/insights agree at manual 2 / other 2 / access-required 1501. The original four schedules resumed at 15:33 UTC. Vault remains paused, SQL private-only, legacy producers disabled.

## Separate Legislative incident

Runtime run `065d5330-abca-4eda-b683-64e85f2dcbe7`, execution `polititrack-legislative-gnkrk`, failed at 10:41 UTC on the old image after Senate HTTP 403 and incomplete-source validation. Its `side_effects_possible=true` guard remains intact; Legislative generation 232 remains accepted. See [the incident record](incidents/2026-09-08-legislative-retry-guard.md) and issue #8. Do not clear the flag, force a retry, delete evidence or replace a baseline.

## Next safe action

Merge the corrective PR after canonical checks, build exact merged source, and repeat the bounded existing-resource rollout. Validate the full served publication before resuming schedules. In isolated browser storage seed only the two real legacy Senate IDs, verify two House entries stay active, then acknowledge all four, refresh/reload and Restore. Replay missing/returning publications locally using served assets. Update final release evidence only after acceptance passes.
