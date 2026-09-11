# PolitiTrack active handoff

Updated **2026-09-11 — owner-authorized issue #168 release in progress**.
Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**.

## Active task — complete investor alerts and responsive dashboard release

The owner explicitly authorized full implementation on September 11. PR #169 is
merged at `258b7e16f51485fb9ba92971f4c05964eaab09aa`; its tree exactly matches the
previously tested head. Investor Edge main CI `34659136667` succeeded. Initial
build `5001986c-b0c4-4cfc-88f0-cd8789bea30d` succeeded but was not deployed.

Live preflight found a new acceptance blocker, issue #170: Signals data requests
return HTTP 500 with Cloud Run's “Response size was too large” log. Branch
`codex/alerts-release-20260911` adds negotiated streaming gzip for public text
assets and unbuffered streaming for large identity-only responses. Exact content,
conditional requests, HEAD, range handling and snapshot headers are retained.
Local focused Runtime/personal/Operations checks: **43 passed, 25 optional
PostgreSQL skips**; three cases exercise a full 33 MiB ledger. Exact-head CI and
the corrected build must succeed before the controlled image cutover.

All six live resources still match source
`9f1a59105f2ac7cfa6ed3f764d9ab4b3d5483301` and image
`sha256:916f23124c028467079b305f50681336fc0b1e6e553cdb4fefe491dc2d380ef1`.
Original schedules are enabled; Vault remains paused. Earlier release tasks are
inactive. Personal data, snapshots, notification history, scheduler configuration
and Operations control enablement are unchanged. There is no schema migration
for this feature. Current Opportunity #154 remains excluded.

Gmail sender secrets are absent. Google requires the owner's account verification
and app-password creation; that secure page is open for them. Complete independent
deployment work while awaiting that credential step. Do not request passwords in
chat. After credentials are available, use the existing AI outbox and verify
provider acceptance/inbox receipt separately from successful collection.

Next: merge the tested #170 correction, build the exact source, pause/drain existing
schedules, capture a read-only baseline, update the existing resources, verify
controlled successors and live complete Signals data, restore identical schedules
and verify natural runs. Keep all histories and recipient-aware rollback semantics.
See [feature contract](investor-alerts-navigation.md).

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
