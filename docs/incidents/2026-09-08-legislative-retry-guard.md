# Legislative retry guard after Senate access failure

**Resolved on September 9:** The permanent collection/outbox release passed
controlled and natural scheduled Legislative acceptance, preserving the exact
failed row, side-effect flag and generation 232 parent. See the
[accepted recovery](../releases/2026-09-09-legislative-recovery.md) and
[new contract](2026-09-09-legislative-recovery.md). The account below, including
its next-action guidance, is the retained September 8 incident record.

Observed during the 2026-09-08 release of [issue #155](https://github.com/maglothinm/MyETF-Intelligence/issues/155), in canonical repository ID **1349678672**. Related source-access incident: [issue #8](https://github.com/maglothinm/MyETF-Intelligence/issues/8).

## Verified sequence

- The last accepted Legislative snapshot is generation **232**, created at `2026-09-08T10:25:04Z`, SHA-256 `7fda615a19c31165fefa91b2501ffab8f2c677325aeffdc35b7ff444c2d609df`.
- Cloud Run execution `polititrack-legislative-gnkrk` produced Runtime v2 run `065d5330-abca-4eda-b683-64e85f2dcbe7`, started `2026-09-08T10:37:33.311733Z` and failed `2026-09-08T10:41:24.714055Z`.
- Its source revision was `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`, before the issue #155 merge or deployment. The old image digest was `sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`.
- The Senate landing GET to `https://efdsearch.senate.gov/search/home/` returned HTTP **403** on all three bounded bootstrap attempts, before CSRF/terms. Logged response fingerprint: `b926b117fd181a2b1da1ced3319c28f18400e9de111aca84b817eebcdb135aac`.
- House processing subsequently logged `visible={'house': 894}`, `new={'house': 0}`, `purchases={'house': 0}`, and `pending={'house': 0}`. The complete-source healthcheck failed. Runtime v2 recorded `CalledProcessError`, `side_effects_possible=true`, and no committed snapshot for that run.
- Later old-image executions, including `polititrack-legislative-ldzgd`, failed at `LockedNamespace.assert_retry_safe()` with `legislative retry is blocked because the last unretained run may have sent an alert`.
- The first issue #155 rollout's Legislative smoke, `polititrack-legislative-rstl7`, hit the same guard before starting a new durable producer run. That rollout restored the old image on all six resources and verified the original scheduler settings.

## Preserved state and interpretation

The guard remains in force. No failed-run row, side-effect flag, alert ledger, snapshot, head, or protected artifact was edited or deleted. No retry was forced and no baseline was replaced. The source rejection predates this feature release; its exact network/WAF cause is not established by the HTTP status alone.

Zero newly processed House records and Senate failure before discovery are evidence for later incident review, **not** an operator adjudication that no external side effects occurred. Do not clear `side_effects_possible` from these counts alone. The current Runtime v2 CLI has no reviewed production adjudication command.

The existing Dashboard producer can render the latest accepted inputs and publish the additive issue #155 identity map without advancing Legislative state. A successful dashboard release does not establish restored Legislative discovery or all-pipeline health.

## Next safe action

Recover this incident under issue #8 with an audited plan: preserve the original failed-run evidence and accepted snapshot; establish alert-delivery facts; determine the supported Senate access path; and implement/review any required retry adjudication through the single-writer contract. Only then run one controlled Legislative attempt and verify complete-source collection and a new snapshot with the retained generation 232 hash as its parent. A rebaseline, deletion, blind flag update, proxy workaround, or forced retry is not authorized by the acknowledgement release.
