# Lossless opportunity journal storage (#246)

`opportunity-state.json` retains its filename and logical schema. Its physical
representation now uses `polititrack-content-addressed-json-v1`: exact canonical
JSON subtrees are stored once and referenced by SHA-256. This is deduplication,
not deletion, compression, a new state owner or a larger archive allowance.

All production readers use `opportunity_common.read_json`; all writers still
pass through the existing `opportunity_state.save` integrity and predecessor
checks under the single Runtime v2 AI writer. The reader accepts old plain JSON
and new envelopes. Event IDs, sequences, parent hashes, historical payloads,
current projections, delivery receipts and investment gates do not change.
The object graph is hash-verified, acyclic, depth/count/byte bounded and complete.
Reserved reference-shaped user data is escaped. Mutable projections are detached
from shared historical objects, so updating a projection cannot alter its past.

A skipped review records its first loss of freshness, but repeated identical
missed-work states do not clone the same complete evaluation again. Queue
telemetry still updates. Genuine reviews and changed invalidation reasons remain
journaled. A skipped record's last attempted/successful review never advances.

## Recovery and rollback

Never manually decode or rewrite an authoritative database snapshot. The normal
AI owner converts a validated predecessor when publishing its next snapshot.
Retain private verified pre-change exports and compare the complete logical state.

An executable rollback MUST retain the compatible codec and readers after the
first encoded snapshot is committed. Reverting blindly to an old executable
would reject the new envelope; selecting an older database head is not a rollback
and remains forbidden. For a regression, pause the affected producer through the
normal service boundary, keep its current head, and deploy a compatible forward
repair or an old behavior build that retains the reader/writer compatibility.

Diagnostics that inspect this file should import `opportunity_state.load` or
`opportunity_common.read_json`, not assume its physical JSON has top-level events.
Public dashboard JSON/CSV remain the same logical projections.

Append-only research history continues to grow with actual work. This change
removes inventory-wide repeated no-work snapshots and deduplicates retained
payloads; it does not promise unlimited storage. All existing archive/path/hash
limits remain enforced. Future lifecycle storage changes require separate
continuity evidence; no history may be trimmed as an emergency workaround.

## Acceptance scope

The initial private real-state clone preserved all 8,596 events, 533 opportunities
and 1,607 other AI files byte-for-byte while reducing the full uncompressed AI
snapshot from 526,698,384 to 225,361,624 bytes under the unchanged 536,870,912-byte
limit. This offline proof is not a deployed snapshot or an investment-case
acceptance result. Native scheduled publication and continuity must be checked
separately. OpenAI quota recovery and renewed provider receipts are independent
requirements for model-backed investment acceptance.
