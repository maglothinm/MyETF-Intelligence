# PolitiTrack active handoff

## September 23 activation retry for #225 — Windows approval canceled

The owner explicitly requested activation. Canonical repository ID 1349678672,
`maglothinm/MyETF-Intelligence`, main `52e75335a6643adcc2c0a43c90510e84a46114fe`.
The prepared release remains implementation merge
`c46dcef215e4872912ba2995b67cb117725b05e2`, tested at
`e5653120d4cd9d16303ec1ba3eda5488c1e2548e`. Main differs only in operational
documentation. Session branch: `codex/discovery225-live-activation` (documentation only).

One normal Windows elevation request was made at approximately 11:03:40 UTC.
Windows returned `The operation was canceled by the user`, observed at 11:06:25 UTC.
The elevated activation script did not start. No prompt remains active, no release
activation receipt exists, and no automatic retry was made after that cancellation.

Read-only acceptance at **11:06:58 UTC** confirms application/config still use
`dfb5c66ffc51b30b8afbdc283dbe10def4723f89`. Database/web/scheduler remain
Running/Automatic with unchanged PIDs **25732 / 24620 / 25956**. Readiness is HTTP
200. AI generation **851** has no discovery ledger; dashboard generation **1616**
still serves the previous release and discovery JSON/CSV routes are HTTP 404.
Existing assets match committed snapshots; upload authentication and invalid-Host
rejection pass. Activation and autonomous discovery reporting remain **unverified**.

All **4,693** snapshot headers before `2026-09-23T11:03:40.422575+00:00` retain
digest `8135b8a25206577231f3a8b3b9256b64`; the older September 22 checkpoint also
matches. The complete snapshot chain has zero broken parent links. This is a
read-only preservation fingerprint, not a state rebaseline. The latest recorded
routine physical backup completed 00:02:23 UTC with `pg_verifybackup` passed,
manifest SHA-256 `dfd22e31219f36342aa37c1bf0909ce98a0214a0442db134cdc5a6706d8c8062`.
No source changes, configuration changes, service restart, original upload change,
new producer, cloud activation or legacy restore was performed by this attempt.

The original 30-page upload remains **needs_review**, with its existing Executive
generation 693 receipt. Its earlier OCR completion does not prove this release's
outage-independent path. Do not re-upload or requeue it for a demonstration.

The four exact-head CI runs remain successful on attempt 1:
[Source OCR 35770240188](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240188),
[Runtime v2 35770240147](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240147),
[Current Opportunity 35770240223](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240223),
[Investor Edge regression 35770240357](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240357).
The prior source checks remain 547 regression passes / 7 local PostgreSQL skips,
10 interface/accessibility passes, and final focused 31 passes / 1 skip; real
PostgreSQL cases passed CI. No product source changed, so these suites were not
repeated for this operational retry. Local launch/verification helpers passed
PowerShell syntax/Python compilation checks; the launcher was not executed.

### Next safe action

The owner's Desktop now contains **Activate PolitiTrack Discovery Update**.
This shortcut opens the prepared pinned package via normal Windows administrator
approval, checks its SHA-256, prevents overlapping launcher instances, and reports
whether the existing services restarted. It was created but not launched. The
package remains `C:\ProgramData\PolitiTrack\releases\discovery225\Apply.ps1`.
Do not bypass UAC or repeatedly reopen a canceled prompt.

After the owner opens that shortcut and approves Windows elevation, verify the
activation receipt, current services/source, both immutable-history checkpoints,
then normal AI/dashboard publication and live JSON/CSV equality with the persisted
ledger. Keep [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225) open
until live acceptance. Current Opportunity is still OFF; incomplete historical
discovery provenance must remain unknown. Existing single-writer ownership and
review-before-import remain required. See [DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md).
