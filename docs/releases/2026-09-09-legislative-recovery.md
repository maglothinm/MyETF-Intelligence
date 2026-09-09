# Legislative recovery accepted

Accepted at 2026-09-09T13:41:35.684561+00:00. The database audit used a read-only snapshot at 2026-09-09T13:40:08.823666+00:00. Collection resumed with an exact successor to the preserved generation 232 snapshot, followed by a successful natural scheduled run.

## Release identity

- Runtime source: `9f1a59105f2ac7cfa6ed3f764d9ab4b3d5483301` (PRs #161 and #162).
- Image: `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:916f23124c028467079b305f50681336fc0b1e6e553cdb4fefe491dc2d380ef1`.
- Cloud Build: `9ad52cb8-5875-4e08-a86c-ea90e512247c`.
- Web revision: `polititrack-web-00039-ps5`; 100% traffic.
- All six existing resources use the same image; producer source settings match.

## Live acceptance

| Producer | Baseline generation | Controlled generation | Verified generation | Controlled execution |
| --- | ---: | ---: | ---: | --- |
| Legislative | 232 | 233 | 234 | `polititrack-legislative-6whgv` |
| Executive | 169 | 170 | 170 | `polititrack-executive-gw6n4` |
| AI | 196 | 197 | 197 | `polititrack-ai-s5s7p` |
| Dashboard | 333 | 334 | 335 | `polititrack-dashboard-gl989` |

Natural Legislative execution: `polititrack-legislative-nmt57`. The saved receipt includes each new run ID, parent hash, generation, source and snapshot hash.

Complete House-and-Senate validation passed. Executive, AI and Dashboard also published successfully through the existing writer locks and atomic snapshot path. The live Operations page and `/readyz` were checked against the new publication.

## Preserved evidence and data

- Original failed run `065d5330-abca-4eda-b683-64e85f2dcbe7` is unchanged, including `side_effects_possible=true`.
- Original generation 232 ZIP remains byte-for-byte verified at SHA-256 `7fda615a19c31165fefa91b2501ffab8f2c677325aeffdc35b7ff444c2d609df`.
- All pre-release snapshot metadata hashes match. Current ZIPs and every manifest file verify. Every controlled successor has the exact pre-release parent.
- All five personal-review tables remain present. Account identities and all eight retained acknowledgement rows are unchanged, including the owner’s four original records and disabled test-account history. Personal feature/origin settings and the owner account setup/recovery process are preserved. The live browser showed the owner account signed in; this release did not modify credentials or sessions.
- Four original producer schedules are enabled with identical timing, time zones, targets and retry settings. Filing Vault remains paused. Database networking, backup/PITR and IAM were not changed.

## Permanent behavior and validation

Legislative, Executive and AI stage alert intents and commit them with successful state. Delivery claims and uncertainty are durable per record; ambiguous old alerts cannot block later collection or unrelated new alerts. The pinned proof resolves only the original incident’s delivery uncertainty. Failed collections retain their evidence and publish neither state nor alert intents.

Final Runtime CI: 506 passed, one SQLite-only concurrency skip, with real PostgreSQL integration. Investor Edge: 712 passed. Local full suite: 1,195 passed, 31 environment/optional skips. Tested head/tree match the deployed runtime source tree. Tests cover failure-to-success liveness, crash/restart uncertainty, no automatic resend, missing credentials, atomic publication and concurrent writers.

Pushover credentials remain absent from the inherited live configuration. This release proves collection and publication liveness; it does not certify external alert delivery. Queued, held, uncertain and accepted records remain distinct in the delivery status receipt.

## Rollback boundary

After an outbox snapshot is accepted, use only an outbox-compatible corrected image. An old direct-send AI image can ignore queued-channel metadata and duplicate alerts. If intervention is required, pause producers and retain heads, outbox and history; never rewind or rebaseline.

This is bounded recovery acceptance. Prior Phase 5 certificates remain immutable historical evidence; no new all-system certification or unrelated PR #154 activation is claimed.

[Live dashboard](https://polititrack-web-s6icmprjvq-uc.a.run.app/#operations).

[Machine-readable release receipt](2026-09-09-legislative-recovery-receipt.json).
