# Dashboard success history and separate OCR status — September 21, 2026

Issue [#208](https://github.com/maglothinm/MyETF-Intelligence/issues/208), implementation
[PR #209](https://github.com/maglothinm/MyETF-Intelligence/pull/209), canonical repository
ID **1349678672**. Application source on main:
`50e3e0d6d0a09475cae694a74bfaf501416892f2`.

## What changed

The Runtime evidence reader selected only seven recent attempts. After seven
Executive failures, the September 21 success disappeared from that window and
an old September 1 artifact date appeared as the last success. OCR history was
also derived from the short display timeline, and the collector's success footer
was rendered underneath the Source OCR section.

The dashboard now retrieves successful production receipts independently of its
recent-attempt timeline. It verifies the matching immutable snapshot's namespace,
digest, source revision, chronology and production provenance. Up to four distinct
receipts retain the latest collection, completed OCR pass, healthy OCR pass and
completed document. A completed pass with technical retries advances completion,
but does not become a healthy pass. Malformed, future, shadow, unverified and
mismatched evidence cannot advance the historical anchors. No qualifying Runtime
success means unavailable, without silently substituting a legacy date.

Compact, Operations and monitor cards put collector timestamps and status in a
collector section. Source OCR has its own badge and explicitly named history.
“Blocked by collection” identifies an upstream attempt that never completed OCR.
Current failures remain failures even when an earlier success is recent.

## Validation

- Local focused suites: 218 Python passed; two PostgreSQL tests deferred to CI.
  Five Node health regression tests passed.
- Runtime v2 safety: [35592427023](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35592427023), success (658 passed, two unrelated skips). Includes real PostgreSQL history selection after 20 failures and rejection of invalid snapshot receipts.
- Source/OCR: [35592426780](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35592426780), success, including desktop/mobile browser checks (373 Python and five Node health tests passed; one unrelated skip).
- Investor Edge/dashboard DOM: [35592426651](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35592426651), success (802 Python tests, including the dashboard DOM harness).
- Current Opportunity: [35592426885](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35592426885), success.
- Merged-main source/OCR [35592689411](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35592689411) and Investor Edge [35592689390](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35592689390): success.

## Release scope and continuity

Only the existing `polititrack-dashboard` producer changes image and
`SOURCE_REVISION`. Its original scheduler is temporarily paused while existing
executions drain; the original producer publishes through its namespace lock and
immutable successor commit. The other five resources retain application source
`aba0285689d649d94e3e11444b582c748927bbc4` and their existing configuration.
No migration, source reprocessing, account change, OCR reset or rebaseline occurs.

Build `f84de217-c765-4733-a051-f93aef8afb05` produces image digest
`sha256:7003b8e37fdd2e949de6fb49f47e8544cc69bc4fb49a3ff11372240e9d71cd9b`.
The release uses a fresh journal and read-only repeatable-read baseline/acceptance
audits. The closed OCR release journal remains hash-pinned and untouched.

Baseline audit `polititrack-admin-vmb4c` passed at 11:23 UTC. Publication
`polititrack-dashboard-rm6cd` completed successfully at **11:29:11 UTC**.
Post-release audit `polititrack-admin-qcwpb` passed at **11:32:51 UTC**. The original
four schedules are enabled with their original cadence; Vault lifecycle is paused.

Dashboard generation **1451**, snapshot `28affef1-a1c9-494f-9993-878022801192`,
is the direct successor of generation **1450**. Its producer receipt is
`879f6414-a7dd-4f45-ad20-bb60ba6bdd21`. The live readiness digest matches the
accepted snapshot: `a5c609653b7f356bbe5e62a2240cece3bae9eb8ac721264102513c364e2cf5e6`.
All current snapshot file hashes and parent chains passed. Prior metadata,
completed-run history, account/review acknowledgements, notification history,
source ledger prefixes, retained files and durable identities are preserved.
Source heads at acceptance: Legislative **1350**, Executive **671**, AI **759**.
Legislative advanced normally during the release; Executive and AI were unchanged.
Exact snapshot IDs, producing receipts, digests and audit results are in the
[release evidence](2026-09-21-dashboard-health.json).

## Live result and remaining incident

At **11:30:48 UTC**, root, readiness, insights, app.js, wallboard.js and styles.css
returned HTTP 200. All three asset hashes matched the canonical release. Browser
inspection confirmed the separate sections in Overview and Operations.

| Executive evidence | Verified timestamp (UTC) |
| --- | --- |
| Last successful collection | September 21, 04:18:35.366019 |
| Last completed OCR pass | September 21, 04:18:35.456369 |
| Last document OCR completed | September 21, 04:18:34.900261 |
| Last healthy OCR pass | September 20, 00:45:59.993867 |

The latest Executive attempt still reports a collection failure, with Source OCR
**Blocked by collection**. Overall status remains failure. The September 21 OCR
pass completed work with technical retries outstanding, so its completion does
not replace the older healthy-pass timestamp. The ongoing OGE source errors and
previous intermittent web/operations availability concerns remain separate work;
this release does not claim an upstream recovery. No blocker remains for #208.

Next safe action: normal scheduled publication; investigate the OGE incident using
retained failure evidence. Reload the dashboard once to load the new labels.
Private operational receipts remain in the task-specific Cloud Shell folder
`/home/maglothinm/polititrack-ocr-182-v68vldej/dashboard-health-208-20260921`.
The closed OCR release journal hash remains
`9980523ad75ce1f4993967cbc4dce8c296e486b0d21ffc0e7db745a02e94ddcd`.

