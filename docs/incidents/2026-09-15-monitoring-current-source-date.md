# Monitoring current and the source timestamp — September 15, 2026

Read-only investigation at approximately 12:15 UTC / 08:15 America/Port-au-Prince.
The owner cancelled the tooltip change and requested continued diagnosis only.

## Conclusion

The current monitoring status is supported by successful recent production executions.
The older source timestamp is calculated separately. It is also affected by a
reporting defect: exported cloud collector histories identify their event and
trigger as `local`, so the production-only timestamp calculation excludes them.
The badge uses independent verified Runtime v2 execution evidence and remains valid.

## Live evidence

The published dashboard was generated at `2026-09-15T12:06:08Z`, with snapshot
`2161b47456295231fae0fc6d0f38c68551b7c9839ce33d4d594aba79688e7b4e`.
It reports source data through `2026-09-14T14:37:41Z`, corresponding to the latest
House record updates shown in its filing inventory.

| Branch | Published last successful check (UTC) | Freshness limit |
|---|---|---|
| Legislative | 2026-09-15 11:55:48 | 30 minutes |
| Executive | 2026-09-15 11:46:32 | 60 minutes |
| AI | 2026-09-15 11:48:17 | 75 minutes |

Each remains within its limit at the check time. Cloud Run independently confirms:

| Execution | Completion (UTC) | Result |
|---|---|---|
| `polititrack-legislative-s8qtf` | 12:10:45 | Success; 903 House and 89 Senate PTRs visible; zero new; complete-source validation passed |
| `polititrack-executive-gb4dd` | 11:46:36 | Success; 4,066 OGE 278-T listings discovered; zero new |
| `polititrack-ai-wl87q` | 11:48:20 | Success; 10,618 eligible, zero newly analyzed or deferred |

The Legislative execution is newer than the published dashboard. Its status is
additional live evidence, not a claim that the older publication already included it.
The Executive success confirms the previously diagnosed OGE timeout is not currently
blocking the checked run. No repair was performed by this investigation.

## Reporting defect

`append_run_history` in `scripts/government_trade_tracker_core.py` defaults its
exported event name to `local` outside GitHub Actions. The live `/data/runs.json`
contains recent successful Legislative and Executive rows with both `event_name`
and `trigger_source` equal to `local`.

`source_data_through` in `scripts/dashboard_insights.py` considers retained filing,
transaction, review and successful production-run timestamps. Its `production_run`
filter in `scripts/collector_freshness.py` rejects these incorrectly labelled rows.
Read-only evaluation against the actual served rows confirmed their exclusion.
This leaves the displayed timestamp at the newest retained record update, even
though verified source collection has occurred more recently.

Monitoring health instead uses verified Runtime v2 database execution evidence,
with last-success freshness limits and failure precedence. Therefore Current is a
statement about recent successful monitoring, not a guarantee of new filings,
fresh market prices, or the currency of every retained record.

## Scope, lineage and next action

Canonical repository ID `1349678672`, `maglothinm/MyETF-Intelligence`, default `main`
at `02dfe4126ed169f4366ac59aeb001d7954fce6a3` was verified. The served application
bundle matches its checked-in source assets exactly (SHA-256
`ab908bd3b523fa3b454b6b667fbc76508b3790e8a47ec9e6e52a5ffa8d691168`).
Diagnosis branch: `codex/monitoring-freshness-tooltip-20260915`.

No application or tooltip edits, tests, deployments, schedule changes, credentials,
collector dispatches, protected artifacts or production database writes were made.
Only this diagnosis and the local handoff are recorded. Existing release CI and
continuity evidence remain historical; no new release certification is claimed.
Future remediation should correct production provenance on newly exported run
history, preserve existing history, and explicitly define the source-date meaning
before changing its calculation. No remediation is included in this task.

Raw public responses and read-only Cloud Run evidence are retained locally at
`C:/Users/maglo/Documents/Codex/2026-09-10/polititrack-alerts-navigation/monitoring-tooltip-20260915`.
