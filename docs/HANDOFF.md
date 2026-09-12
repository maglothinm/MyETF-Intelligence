# PolitiTrack active handoff

Updated **2026-09-11 — issue #172 branch implementation; production not changed by this work**.
Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Active task — Investor Edge backfill progress (#172 / PR #173)

Branch `work/investor-edge-backfill-progress-172`, based on canonical main
`258b7e16f51485fb9ba92971f4c05964eaab09aa` (PR #169 merged). Adds truthful
observation categories, persisted advancement/cadence evidence, bounded measured
ETA, retry explanations, stalled-work detection and accessible root/standalone
pending-work details. Scoring, schedules, production state and personal history
are unchanged. [Implementation/acceptance contract](investor-edge-backfill-progress.md).

Local focused tests: **87 passed, 1 optional Node/jsdom skip**. Repository safety
verification passed. Canonical CI, responsive browser evidence, merge and runtime
acceptance must be reported separately on PR #173 / issue #172. Temporary source
export/application tooling is development-only and must be absent from the final
merge tree. It cannot access production data or cloud/notification credentials.

**Next safe action:** finish exact-head code/DOM/full regression acceptance, remove
temporary tooling, then coordinate deployment from a fresh live baseline. Do not
close #172 as production-complete until AI/Dashboard successors and the served
status are verified. No rebaseline, historical snapshot replacement, IAM expansion,
new production writer or unrelated activation is authorized by this change.

## Prior task — investor alerts, OGE health and table navigation

**Source update:** PR #169 merged as `258b7e16f51485fb9ba92971f4c05964eaab09aa`
on September 11. Its previous implementation checkpoint follows for context;
its then-pending merge statement is historical, not current source status.
No newer live image was verified during the #172 implementation session.


Branch `codex/alerts-oge-navigation`, based on main
`86cb05cdcb248e3308dce52eca9a0ab7859d61e6`. The owner's request is implemented:
new-browser sound defaults on and activates on a real interaction; configured
Gmail recipient `maglothinm@gmail.com` receives queued Investor Edge crossings
strictly above 60.0 plus existing Watchlist/High Priority analysis alerts;
Operations exposes OGE check evidence and inventories; compact Signals cells
retain full hover/focus/tap text; wide tables have reachable top navigation.
Existing saved Off preferences remain Off.

Local canonical suite: **1,226 passed, 37 environment-dependent skips**; shared
sound/integration checks passed again after the final audio status wording fix
(**33 tests**). Repository safety verification passed. Real browser checks used
read-only copies of published data at 1280, 700 and 390 pixel widths. Main
Signals rows measured about 93 px instead of 946–1032 px. See
[implementation and activation checklist](investor-alerts-navigation.md).
Canonical exact-head CI evidence belongs to the linked PR for issue #168.

**Not activated:** no merge, image deployment, schema migration, producer
execution, scheduler/IAM modification or external message delivery occurred.
Gmail sender credentials are absent from the live AI job, Secret Manager and
repository secrets. Configure them securely on the existing AI job before
claiming accepted delivery. Never put the app password in chat or Git.

**Next safe action:** finish exact-head PR checks, coordinate one production
release with the still-pending Operations #164 activation, obtain secure Gmail
sender configuration, preserve current state/personal history and verify a real
outbox acceptance separately from collection success. Do not activate #154 or
change schedules. The accepted production baseline below remains unchanged.

## Current production release

PRs #161 and #162 are merged, built, deployed and accepted. Legislative completed
House 894 / Senate 85 in its normal 180-day window, passed complete-source
validation and appended generation 233 to the exact preserved generation 232
parent. Executive, AI and Dashboard also published valid successors. A later
natural scheduled Legislative execution `polititrack-legislative-nmt57` succeeded.

- Runtime source: `9f1a59105f2ac7cfa6ed3f764d9ab4b3d5483301`.
- Image on all six existing resources: `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:916f23124c028467079b305f50681336fc0b1e6e553cdb4fefe491dc2d380ef1`.
- Build: `9ad52cb8-5875-4e08-a86c-ea90e512247c`; web: `polititrack-web-00039-ps5`, 100% traffic.
- Final Runtime CI `34353185272`: 506 passed, one SQLite-only skip; real PostgreSQL integration passed.
- Investor Edge CI `34353185434`: 712 passed. Local full suite: 1,195 passed, 31 optional/environment skips.

[Exact release evidence](releases/2026-09-09-legislative-recovery.md) and
[permanent contract](incidents/2026-09-09-legislative-recovery.md).
Prior Phase 5 certificates remain historical; this is bounded recovery acceptance.

## State, notification and scheduling boundaries

All four original schedules are ENABLED with unchanged timing, time zones,
targets and retry settings. Filing Vault remains PAUSED. Accepted heads advance
naturally; refresh live state before any subsequent release. Original failed run
`065d5330-abca-4eda-b683-64e85f2dcbe7` and `side_effects_possible=true` remain
unchanged, as does its generation 232 parent. The historical flag no longer
latches collection. Its delivery fence is resolved only by the exact pinned
no-delivery evidence. Other uncertain alerts retain per-record duplicate protection.

Runtime Legislative, Executive and AI atomically commit alert intents with
successful snapshots. Missing credentials do not block collection. Pushover
credentials remain absent; external provider delivery is not certified by this
release. Queued, held, uncertain and accepted states must remain distinct.

After accepting outbox snapshots, use only an outbox-compatible corrected image.
Do not roll back to the old direct-send AI image, rewind heads, rebaseline,
delete old runs, clear alert holds or introduce an alternate writer. Keep writer
locks and complete-source validation. No IAM, private database networking,
backup/PITR, legacy-route or unrelated PR #154 activation change occurred.

## Personal acknowledgement continuity

Issue #159 / PR #160 remains accepted and included in this image. All five
personal-review tables, account identities and eight retained acknowledgement
rows are unchanged. The owner's four original acknowledgements retain their
timestamps; disabled test-account history and the Restore tombstone remain.
Personal review enablement and the exact configured origin are preserved.

The live browser showed the owner account signed in during recovery acceptance;
this release did not modify credentials or sessions. Any password setup or
recovery remains the owner's action. Never replace the owner identity, choose a
password for them, ask them to re-acknowledge, or publish setup tokens or recovery data.
See [the personal review release](releases/2026-09-09-personal-review-acknowledgements.md)
and [account administration](parser-review-acknowledgements.md).

## Additional active owner request — Operations Run now controls

Issue #164 / PR #165 is merged as `4948b3bb6683b826ca6647495ed6d6a32ff24be6`;
its coordinated production activation remains pending after this recovery handoff. The owner can start
the three existing jobs using the existing signed-in account; public/ordinary
review accounts cannot dispatch. Additive receipts survive refresh and browser
clearing. Production images, schedules, IAM and schemas have not changed for #164.
See [the implementation and activation contract](operations-manual-runs.md).
Preserve the owner's user-completed sign-in; never reset their password or session.

## Next coordinated work

The separate personal-review task is implementing the owner's Operations
**Run now** controls. It must use the existing jobs, execution-scoped trigger
labels, writer locks, completeness checks and durable notification contract.
Dispatch acceptance is not collection success. Preserve authentication,
same-origin protections and actor authorization. Keep schedules unchanged.
This recovery task returns production ownership with its exact acceptance
receipt; subsequent deployment must establish a fresh baseline and use its own
tested image. No overlapping production release is permitted.
