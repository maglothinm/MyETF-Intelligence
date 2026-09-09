# Legislative recovery and permanent notification liveness

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

## Permanent collection and delivery contract

Runtime v2 Legislative, Executive and AI collectors stage notification intents in
the forced `durable_outbox_v1` mode. They never send alerts during collection.
The existing snapshot, head and successful-run transaction also inserts those
intents into the additive PostgreSQL outbox. Complete House-and-Senate validation
and accepted-parent checks remain required; a failed collection publishes neither
state nor new alert intents. A failed run retains its original evidence. Later
scheduled collection does not consult a historical namespace-wide alert latch.

After a successful commit, the existing namespace lock remains held while a
bounded dispatcher processes pending deliveries. Each record/channel has a stable
identity: filing source/report or logical review for trackers; trade/analysis/
revision for AI. It commits a `sending` claim and event before contacting the
existing provider. Confirmed acceptance becomes `accepted`; explicit rejection
becomes `rejected`; a timeout or process death after claim becomes `uncertain`.
Uncertain or rejected submissions are never automatically resent. Those records
do not occupy the pending batch, so new eligible records continue to deliver.
No credentials are stored in intents, snapshots or delivery events.

AI queued channels remain distinct from accepted channels. A queued alert is not
reported as delivered. Missing credentials leave existing pending deliveries
unattempted and do not prevent collection. Existing explicit notification
suppression and shadow-mode boundaries remain enforced. No new scheduler,
provider, IAM grant or alternate writer is introduced.

### Legacy uncertainty

Before the first successor, old failed or abandoned production runs after the
accepted parent become retained legacy delivery fences. The original rows and
side-effect flags are unchanged. A failure already recording no possible side
effects is resolved as `no_delivery`. The immutable September 8 receipt also
resolves only its exact unchanged run as `no_delivery`; its pinned digest and
original evidence remain required for that exemption. Collection itself does
not depend on this receipt, exact incident, or parent generation.

Other old ambiguous runs remain `unresolved`. Their completion time bounds the
records they could have sent; abandoned runs use detection time under the writer
lock. An individual alert whose official filed date is on or before that UTC date,
or unavailable, is `legacy_held` with the failed-run reference. Same-day dates
cannot establish ordering and are held conservatively. Later official filing
dates remain eligible. These fences survive head advancement and process restart.
This retains duplicate protection without stopping later data collection or
globally disabling fresh alerts. Held records are neither erased nor falsely
marked delivered. A future record-level reconciliation must use affirmative
delivery evidence before changing any hold.

`python -m runtime_v2 notifications-status` is read-only and reports counts,
legacy findings and individual held identities without secret/message payloads.

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

The final permanent implementation requires local regressions and exact-head
Runtime CI, including real PostgreSQL tests for atomic queue publication, failures
followed by scheduled success, crash/restart with uncertain delivery, fresh-record
delivery, missing credentials, concurrent writer exclusion and original history
preservation. Production recovery is not claimed at this implementation checkpoint.

The issue #159 personal acknowledgement release owns the next production slot.
Integrate its merged source and wait for its completion receipt before shared
production mutations. Then pause/drain the four existing producer schedules,
deploy one tested immutable build to the existing resources, and run the additive
outbox migration through the existing admin job. Never run the new producers before
the migration succeeds. Verify a complete-source Legislative successor with the
accepted generation 232 parent, changed Executive/AI paths, Dashboard publication,
original failure preservation and the restored original schedules. Verify a later
natural scheduled Legislative successor as evidence of continued liveness.

### Rollback boundary

The additive outbox tables do not replace any protected history. After an outbox
snapshot has been accepted, rollback to the old direct-send AI image is unsafe:
it does not understand queued-channel metadata and could duplicate an alert.
Use an outbox-compatible corrected image. If a release must be stopped, fence
producer schedules and retain the accepted heads/queue; do not restore old heads
or start an incompatible direct sender. Before any new producer snapshot, the
previous image remains a valid configuration rollback with the original incident
guard and schedule state. Keep personal acknowledgement schema/data intact.
