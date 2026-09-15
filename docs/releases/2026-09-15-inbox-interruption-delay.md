# Inbox interruption delay — accepted September 15, 2026

Issue #179 / PR #180, canonical repository `1349678672` (`maglothinm/MyETF-Intelligence`).
Accepted at 2026-09-15T12:38:15.901975+00:00.

## Behavior

Inbox waits for 60 minutes of continuing published interruption evidence per agent.
Changing failed run IDs or failure/stale states remains one episode. A verified
intervening success resets the timer. Only a previously reported interruption
generates a recovery notice. First visits, brief interruptions and their recoveries
remain quiet. Operations health is immediate. Existing Inbox history, preferences,
sound coordination and external notification channels are preserved.

Cached refreshes and device-clock changes do not earn outage duration. This is
browser-local Inbox behavior; it requires later published evidence and does not
create a new background notification service or diagnose the root cause of an outage.

## Source and validation

- Implementation source: `2629c05be5a7478c1fdd8695536f618b25d4d78f`; main merge `d9e3d54bb5b695af9c1d7f7e1b277aa492a383ae`.
- Branch: `codex/inbox-outage-delay-20260915`.
- Local: 41 notification checks, 82 generated-dashboard/DOM/insight checks, syntax/diff checks and `verify.sh` passed.
- Canonical PR CI [34968737544](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34968737544): succeeded, 761 Python tests including notification and DOM wrappers, plus browser and repository-safety steps.
- Main CI [34968971627](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34968971627): succeeded.
- Build `0acd4adc-7a40-4a1b-b142-3f163b987723`: succeeded; image `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:aa5b79b468c6f02d3925bc8758b77fa68db922cbdafa383df37258574aeb9cae`.
- Only the existing Dashboard publisher uses this image. Other jobs and the web service retain their verified prior specifications. No collector/backend code changed.

## Live acceptance and preservation

- Dashboard execution `polititrack-dashboard-kvtfv` succeeded.
- Published generation `900`, snapshot `02577bd4-6b1f-40a1-bdf6-12431bd40550`, SHA-256 `8b4d02f1791e4f50bab9adb7c2cf826f3247d926ef496c715ea99a15127c7b37`.
- Exact app and Monitor Mode bundle bytes verified; website readiness returned ready.
- Isolated real Chromium opened the live Inbox and exercised its delivered engine: brief recovery = 0 events; before 60 minutes = 0; threshold = 1; verified recovery = 2 total.
- Baseline audit `polititrack-admin-gs5zz` and acceptance audit `polititrack-admin-l69mq` succeeded with read-only database transactions.
- All baseline snapshot metadata, existing failure rows, prior notification history, three accounts and eight acknowledgement rows matched their hashes. Every descendant parent link and current head payload hash was verified.
- Only Dashboard publication was briefly paused. Its exact original schedule was restored; other schedules stayed unchanged. Filing Vault remains paused.

Runtime v2 snapshots remain production authority. Historical GitHub state artifacts
were not restored or written. No migration, rebaseline, state rewind, alternate writer,
Gmail activation, source-date repair or unrelated feature enablement occurred.
The previously diagnosed source-date reporting defect remains a separate task.

Private evidence: `C:/Users/maglo/Documents/Codex/2026-09-10/polititrack-alerts-navigation/inbox-delay-20260915`.
