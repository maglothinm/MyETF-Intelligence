# PolitiTrack active handoff

Updated **2026-09-09 — Legislative recovery implementation**. Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Active owner request — Legislative recovery

The owner requires a permanent fix: failures, including ambiguous old alert
attempts, must not obstruct later collection. Runtime Legislative, Executive and AI
now stage alerts with the atomic successful snapshot; per-record delivery claims
and uncertainty survive restart independently. The pinned September 8 no-delivery
proof resolves only that exact legacy alert fence. No old flag or history is edited.
Complete-source validation and writer locks remain mandatory.

Finish exact-head CI including PostgreSQL regressions, integrate issue #159's
merged source and wait for its production ownership handback. Then fence/drain the
existing schedules, deploy the tested image, install the additive outbox schema,
and verify controlled producers plus a later natural Legislative run. Do not use
an old direct-send image after accepting queued-channel snapshots. Production
recovery is not yet accepted. [Contract and evidence](incidents/2026-09-09-legislative-recovery.md).

## Personal acknowledgement release in progress — issue #159


Issue [#159](https://github.com/maglothinm/MyETF-Intelligence/issues/159): browser
clearing must not erase acknowledgements; **each person has separate saved state**.
Branch `codex/durable-personal-review-acknowledgements` contains additive private
PostgreSQL account/review tables, authenticated APIs, sign-in UI, explicit legacy
import, stable-account password recovery, and database/DOM regression coverage.
The original four September 8 acknowledgement records were recovered read-only
and await migration into the owner's account. Do not ask the owner to acknowledge
them again or treat another browser-local restoration as the fix.

## Current implementation and remaining work

PR #160 merged as `c0eaeb430aa7f665283f9ee560cf72fbe9c257cf` after exact-head
Runtime and Investor Edge CI passed (runs 34351334909 and 34351334927). The #159
owner is building and releasing it; schema migration, original-timestamp recovery
and live two-account acceptance require that owner's final receipt.
Owner password setup is a final user action through a private single-use link;
never choose a real owner password or expose a credential in release evidence.
See [the implementation and administration contract](parser-review-acknowledgements.md).

The **Restore Legislative collection** task explicitly transferred the next
bounded shared release slot to #159 while continuing its larger durable
notification-isolation fix in isolation. Both tasks report no shared production
mutation yet. #159 may release after validation, preserving every Legislative
failed-run/guard record and excluding the incident-only unmerged commit. Return
the exact merged source, digest, schedule state, continuity and completion/rollback
receipt before transferring ownership back. Do not run historical release helpers
with old hardcoded source/image/scheduler receipts.

## Preserved production boundary

Last #159 read-only verification found source
`19e894ef1262a86d4e54e24a8a34f6b7f230f688`, image
`sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300`
on all six resources, web revision `polititrack-web-00035-v7h`. Refresh these facts
after the Legislative release. Existing SQL is private-only with backups and PITR
enabled. The September 8 [feature release](releases/2026-09-08-parser-acknowledgements.md)
and prior Phase 5 certificates remain immutable historical evidence.

No #159 production writes, schedule changes, new IAM grants, protected snapshot
changes, rebaseline, retry-guard bypass, alternate writer, or PR #154 activation
has occurred. Account/review rows remain outside producer snapshots. Disable test
accounts after acceptance while retaining audit/history. The browser-deletion
[investigation](incidents/2026-09-09-browser-acknowledgement-deletion.md) remains
valid historical evidence; its browser-only workaround is superseded by #159.
