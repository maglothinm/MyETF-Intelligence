# Durable personal parser acknowledgements — accepted September 9, 2026

Issue [#159](https://github.com/maglothinm/MyETF-Intelligence/issues/159),
PR [#160](https://github.com/maglothinm/MyETF-Intelligence/pull/160), canonical
repository **1349678672 — maglothinm/MyETF-Intelligence**.

## Result

Acknowledgements now belong to each person's stable account in private PostgreSQL.
Clearing browser data signs the person out; signing in restores their history.
The owner's four original acknowledgements were recovered with their September 8
timestamps unchanged. The owner must set their own password using the private,
single-use setup link delivered separately. No owner password was selected by the
agent. Other people have independent queues and require their own invitations.

The acknowledgement history is outside public exports and producer snapshots.
Restore retains a tombstone, so importing an old browser backup cannot undo it.
Failed saves do not appear successful, and signed-out/unavailable personal state
is shown explicitly. See [the contract](../parser-review-acknowledgements.md).

## Exact accepted release

- Release branch: `main`; implementation branch: `codex/durable-personal-review-acknowledgements`.
- Merged runtime source: `c0eaeb430aa7f665283f9ee560cf72fbe9c257cf`.
- Tested PR head: `5db166d7d0c11700ed10a45724ee48e148f05d39`; the merge tree matched it exactly.
- Cloud Build: `c84e6510-9825-4c84-b512-cf82d18ed627`, successful exact-source build.
- Image on all six existing resources: `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:5428e1333ceff18b7c2e1f7fd46f3e82652b6c2cb7b94d1fbee20b099fa19ec6`.
- Web revision: `polititrack-web-r159-persist-0909`, 100% traffic at acceptance.
- Dashboard execution: `polititrack-dashboard-j2hjn`.
- Served dashboard snapshot: `3dc7853a8e616d008891ba9f26e8d22ad3391ae2a4ceec0302562885d6ce4c60`.
- Accepted at: `2026-09-09T12:52:47.404970+00:00`.

`RUNTIME_PERSONAL_REVIEWS_ENABLED=true` and the exact production HTTPS review
origin are set on the existing web service. Only additive `runtime_review_*`
tables were created. Existing private SQL networking, credentials, enabled
backups/PITR, service accounts and permissions were reused. No IAM grant or
public database access was added.

## Verification

- Local canonical suite: **1,173 passed, 18 optional/local integration skips**.
- Runtime v2 CI [34351334927](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34351334927),
  attempt 1, exact PR head: **success; 471 passed, 1 SQLite concurrency skip**.
  Real PostgreSQL account isolation, atomic rollback and concurrent saves passed.
- Investor Edge CI [34351334909](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34351334909),
  attempt 1, exact PR head: **success**.
- Compilation, JavaScript syntax, Terraform formatting/validation and `verify.sh`
  passed. The deployed application bundle matched the merged source byte-for-byte
  and passed all **77 generated dashboard DOM checks**.
- Live JSON/CSV/insights agreed on four parser exceptions and
  1,509 access/request-required records.
- Two real test accounts passed sign-in, cookie clearing, renewed sign-in,
  account separation, cross-account/stale-write rejection, Restore, and replayed
  legacy import without resurrection. Unauthenticated and cross-origin writes
  were rejected; private responses were no-store.
- A fresh web revision running the same image/configuration preserved the same
  separate account histories after renewed sign-in. Both test accounts were then
  disabled and login rejection verified; their audit/history was retained.
- The owner account was re-read after testing: exactly four acknowledgements with
  the original identities and timestamps. Owner password setup remains pending.

## Protected continuity and schedules

The release held the existing four producer schedules, drained active executions,
captured accepted heads, and used the existing Dashboard writer. The fenced
cutover changed only the Dashboard head, with exact parent continuity:

| Namespace | Before | After | Accepted after snapshot SHA-256 |
|---|---:|---:|---|
| legislative | 232 | 232 | `7fda615a19c31165fefa91b2501ffab8f2c677325aeffdc35b7ff444c2d609df` |
| executive | 169 | 169 | `a3c5f584b77000c07b4dbcd427d0d22e1203e5c43cb0848115290870868df752` |
| ai | 196 | 196 | `651f332c8375ddcf01686ae59e2cd075b23e0b4d4238c88e7e0b1f4343ccd908` |
| dashboard | 332 | 333 | `3dc7853a8e616d008891ba9f26e8d22ad3391ae2a4ceec0302562885d6ce4c60` |

Dashboard parent: `58b246f3bd17a4f591e7f5efa488c521499bb55986cedc470f6529f600e6ee94`.
The Legislative failed run `065d5330-abca-4eda-b683-64e85f2dcbe7`, generation 232
and `side_effects_possible=true` guard were preserved exactly. No Legislative
retry or collector/AI smoke run was used for this acknowledgement release. The
separate Legislative repair continues under its own task and issue.

All four original schedules were restored and verified ENABLED with their
original definitions; Filing Vault remains PAUSED. Natural runs can advance
heads after this fenced acceptance snapshot. No state initialization, rebaseline,
rewind, evidence deletion, alternate writer, or PR #154 activation occurred.
Previous Phase 5 certificates remain immutable historical evidence; this report
is bounded feature acceptance, not new all-pipeline certification.

## Rollback and private delivery

The retained rollback image is `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300` at source `19e894ef1262a86d4e54e24a8a34f6b7f230f688`.
The prepared rollback disables personal access and appends a valid old-source
Dashboard publication through the existing writer. It never deletes account
history or rewinds a head. No rollback was needed during this release.

Raw provisioning tokens, test passwords, owner account identifiers and detailed
private recovery receipts remain in the local task evidence. They are not part
of this public report. The separately delivered owner setup link expires seven
days after provisioning and can be used once. Password recovery uses the same
account identity and preserves review history.
