# Legislative credential-free retry recovery

Work record: [issue #8](https://github.com/maglothinm/MyETF-Intelligence/issues/8).
Canonical repository **1349678672**, `maglothinm/MyETF-Intelligence`, branch `main`.
This extends the [September 8 incident](2026-09-08-legislative-retry-guard.md).

## Diagnosis and delivery adjudication

The September 8 Senate landing HTTP 403 was a real, bounded source rejection.
The same official client successfully read the Senate catalog from the existing
production network on September 9: read-only execution
`polititrack-legislative-kg4tb` at `2026-09-09T12:08:35Z` returned 57 PTRs in its
120-day diagnostic window. It called no tracker/notification function and wrote
no producer state. This proves current access; it does not establish the exact
cause of the earlier rejection or guarantee that it cannot recur. No alternate
source, proxy, user-agent impersonation, or completeness relaxation was used.

The persistent outage is the retry guard after run
`065d5330-abca-4eda-b683-64e85f2dcbe7`, execution
`polititrack-legislative-gnkrk`. The old runner marked every production tracker
invocation `side_effects_possible=true`, including invocations unable to deliver
any notification. The retained run and flag are preserved as original evidence.

Delivery impossibility is established independently of zero-result counts:

- The immutable execution has neither `PUSHOVER_API_TOKEN` nor
  `PUSHOVER_USER_KEY`, no volume/secret-file mounts, and directly invokes
  `python -m runtime_v2 run legislative`.
- Its exact image is `sha256:2902dc72b23bccfdcff95f71e2ea79d699c96352d9ae3195e8d2940f02bfb4bd`.
  The SHA-verified OCI configuration
  `sha256:2667b57a0d00bca2a041b626d1170d62403d08c0da3c5ed999c3c672fdaef522`
  also has no Pushover credentials or startup entrypoint supplying them.
- The original collector obtains both credentials only from its supplied
  environment. Its sole notification HTTP call is after the early return for
  either missing credential. The runner and source orchestrator preserve this
  absence; the complete-source healthcheck runs in validation-only mode.
- Original code is checked against the immutable image and source revision
  `72c1ca8c74a7af4b11f2e677c7a296d5e2358578`. The checked-in recovery receipt binds
  the execution, image/configuration, source hashes, failed run and accepted parent.

This finding applies to this exact run. It makes no claim that notification
credentials are configured or that external alert delivery works generally.

## Recovery contract

`runtime_v2.legislative_recovery` admits only the checked-in case
`legislative-20260908-no-delivery`, with a code-pinned evidence digest. An explicit
controlled execution uses:

```text
python -m runtime_v2 run legislative --retry-adjudication legislative-20260908-no-delivery
```

Under the existing Legislative advisory lock, the case requires the exact
accepted generation 232 snapshot ID/hash and the entire unchanged post-parent
run inventory. Any changed run field, additional run, different namespace/mode,
or moved head rejects it. The case is consumed as soon as the controlled run
starts. Its evidence is stored in the new run's mode evidence before collection
and in the successful snapshot provenance. No old row, flag, head, payload,
baseline, review, alert ledger or history is rewritten or removed.

Ordinary scheduled invocations keep the existing retry guard. Future tracker
failures mark possible alert delivery only when notifications are unsuppressed
and both Pushover credentials are present. With delivery capability present,
the guard remains conservative regardless of source/result counts. AI delivery
classification is unchanged. Legislative still must pass the same complete
House-and-Senate validation before the atomic snapshot/head/run commit.

## Release and acceptance

The accepted parent export is independently verified: snapshot
`13d95d99-94bc-4e12-be9c-e08f0b9254b5`, generation 232, ZIP SHA-256
`7fda615a19c31165fefa91b2501ffab8f2c677325aeffdc35b7ff444c2d609df`,
1,435,125 archive bytes, eight manifest-verified files. Read-only admin execution
`polititrack-admin-frw5s` also verified that the original failed run is the only
post-parent Legislative run. All original execution/source proof and the parent
are bound by case receipt SHA-256
`778865518665e1447907b2d51b643b80cc89afed00c955a4c2f30f3e44583fb0`.
The original image's final layer was independently hashed and the actual seven
collector/runner files matched the audited original Git revision byte-for-byte.

Local existing-suite regression: 1,156 passed, five optional skips (two
PostgreSQL service tests and three DOM suites whose optional packages are absent).
Final focused recovery/runtime verification: 72 passed, one PostgreSQL skip;
the new PostgreSQL recovery integration runs in Runtime CI. `verify.sh`, Python
compilation and diff checks passed. No production recovery,
new accepted Legislative generation, or deployed fix is claimed at this checkpoint.
Before deployment, require regression/Runtime CI, verify the accepted export and
original image hashes, pause/drain the original producer schedules, and deploy
one immutable build through the existing resources. Verify one complete-source
Legislative successor with generation 232 as its parent, then publish with the
existing Dashboard producer and restore the original schedules. Preserve all
parser acknowledgement fixes and sequence shared changes with issue #159.
