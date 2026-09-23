# PolitiTrack active handoff

## September 23 #225 — activated and discovery publication verified

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Beast application/config are **0c2ab975a837a1d2a28ca4e041019d0103413b54**, merged in
[PR #229](https://github.com/maglothinm/MyETF-Intelligence/pull/229) after exact-head
CI on `632f4343f54dad02a5347da342af31bf6074034b`. This includes the two-part fix
from [PR #226](https://github.com/maglothinm/MyETF-Intelligence/pull/226).
Both activations used normal Windows administrator approval and the existing
web/scheduler service controls. PostgreSQL remained on PID 25732. The repaired
release activated at **2026-09-23T11:29:40.0382451Z**. Source and local configuration
agree; no cloud/legacy producer or new schedule was enabled.

### Live acceptance

At **2026-09-23T11:32:31.129606+00:00**, the existing canonical AI and dashboard writers had
committed and served the discovery evidence. The initial publication used controlled invocations
tagged `deployment_validation`, using the ordinary namespace locks, restore,
validation, atomic commit and unchanged private Beast job configuration. They
were not new scheduled writers or manual database edits. The existing native
scheduler then independently republished the same evidence on the repaired source,
finishing at **2026-09-23 11:32:19.599653+00:00**, run `3c2d8b46-76ab-41f2-b979-86add4eb9c59`. The
dashboard generation below is that automatic scheduled publication.

- AI generation **853**, SHA-256 `5b06047efd7d010f00139b03ac808457a938990fa79bf95683b99773bf25f83f`.
- Dashboard generation **1619**, SHA-256 `46322226bd568b30cc0276a5c4a789c134961261521e1864c625f4fde560fb87`.
- **10,899** persisted transaction evidence objects;
  **10,899** published objects; statuses: **10,899 unknown**.
- All **311** published AI rows contain `information_value_at_discovery`.
- Dedicated JSON and CSV objects agree exactly and match the persisted AI ledger.
- Both new exports, existing AI JSON/CSV, and dashboard scripts return HTTP 200
  and match committed snapshot bytes. Readiness is 200. Authentication and Host
  rejection checks pass.
- Both immutable-history fingerprints remain intact: 4,511 headers from September
  22 and **4,693** before `2026-09-23T11:03:40.422575+00:00`, the latter retaining
  digest `8135b8a25206577231f3a8b3b9256b64`. The complete chain has **0** broken
  parent links. The activation script also verified all pre-existing untracked
  files before restarting writers. No state reset, rebaseline or user-data deletion.

Current Opportunity remains **OFF**. Legacy prices do not establish verified
first-discovery quote quality and comparable price basis; those records correctly
remain `unknown`, with retained inputs and explicit reasons. Do not invent missing
historical quotes or treat unknown as a measured comparison. No qualification or
notification rule was changed by this evidence feature.

### Repair and validation

The first live AI publication attempt exposed a generated CSV field longer than
Python's default reader limit. It failed before snapshot commit, preserving AI
generation 852. PR #229 temporarily sizes that reader to its own generated file
and restores the prior setting, preserving all retained cells and analysis history.
The regression reproduced the original failure, then passed. Local focused checks:
**41 passed**; broad regression: **400 passed**. Offline finalization of actual
snapshot copies exported all 311 rows, including a **208,461-character** cell,
with unchanged history and no production/provider/notification writes.

All three repair-head CI workflows succeeded on attempt **1**:
[Current Opportunity 35854077869](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077869),
[Runtime v2 safety 35854077842](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077842),
[Investor Edge regression 35854077909](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35854077909).
The original two-part change passed all four CI workflows, including real
PostgreSQL manual OCR outage/commit/replay coverage and browser tests. Its Windows
baseline was 547 regression passes / 7 local PostgreSQL skips plus 10 interface
passes. The preserved legacy analyst remains unchanged.

### Remaining boundary

The original 30-page upload still has status **needs_review**
and its original committed extraction receipt
`fe768ffad0909dbba9095b89615561a5fc3c259423f4a22b191737fbe5e50a3f`. It completed OCR before this release;
it was not re-uploaded, requeued or approved, and review-before-import remains.
Its completion is not proof of the new live outage-independent queue path.
Keep [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225) open for that
remaining live acceptance evidence or explicit owner acceptance of the isolated
proof. Do not manufacture it by changing the original upload. The implementation
passed injected-outage tests and an isolated replay of its committed receipt.

The Desktop activation shortcut is pinned to the repaired release and recognizes
an existing activation receipt. No further restart is required for this version.
Continue normal Beast operation; monitor future manual-upload processing through
the existing maintenance receipts and collector health. No new monitor or schedule
was created by this task. See [DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md).
