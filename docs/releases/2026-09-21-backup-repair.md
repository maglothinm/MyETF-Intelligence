# Beast backup repair: verified engine, activation pending

Repair PR #215 is merged at `f85a40f6b7b609ad8eec5c899c368d106fedd7c1` in canonical
repository ID 1349678672. Issue #214 remains open: Windows reported the normal
administrator prompt canceled, and the scheduler has not been restarted onto the
repair. The application remains at `42c6f27df5d9266decad3abc7aa6f794edda0f3a`.
Do not describe the automatic scheduler fault as fixed in the running service.

## Completed verification

The new engine, invoked manually from the reviewed source, produced a full
25,956,737,137-byte PostgreSQL physical backup. Full pg_verifybackup passed at
2026-09-21 19:17:07 UTC (3:17 p.m. Eastern). Its directory is
`routine-20260921T191455Z-6db61a99.base`; the SHA-256 of its manifest is
`8b37a8f5f3fad0fc5157a7b0192f12e4fc88b98809439736afa997a29b383b3f`.
The receipt correctly identifies the old producer revision being backed up.

The dedicated backup login has REPLICATION but neither superuser nor BYPASSRLS.
The application login remains non-superuser, non-replication, non-BYPASSRLS.
Private credentials are stored only inside Beast's existing private config ACLs.
The independent backup child, exclusive locking, persisted retry delay, atomic
verified publication and two-routine-backup retention passed Windows tests.
Windows focused tests: 66 passed, 1 skipped. All three PR CI suites passed on
`dbdd72a5ada959881adeaf12c9130558938bd431`; exact runs are in the JSON receipt.

After verification, 10 exact legacy partial filenames from failed pg_dump
tracebacks were removed after exclusive-open checks, reclaiming 220,958,188,263
bytes. The removal summary was reconciled from the saved plan after a PowerShell
summary-calculation error. All 10 removals were confirmed. The migration export,
cutover physical backup and new verified backup remain. An active old pg_dump
attempt was deliberately excluded; the old scheduler can still accumulate more
partials until the repair is activated.

The read-only audit preserved all 4,287 baseline snapshot header records and
validated successor lineage. At 19:20 UTC the store held 4,292 snapshot records;
heads were Legislative 1371, Executive 679, AI 772, Dashboard 1470. Application
configuration and local-authority receipt were unchanged. No independent full
live-payload rehash was performed. The database and web service PIDs were
unchanged, and the dashboard returned HTTP 200. No reboot or restore drill ran.

## Remaining activation

The owner must open **Activate PolitiTrack Backup Repair** on Beast's desktop and
approve its Windows administrator prompt. The shortcut verifies the reviewed
installer hash and activates the exact merged revision. It restarts only the
scheduler, not the database or dashboard. Do not trigger repeated UAC prompts or
bypass Windows approval. Do not rerun the full setup installer for this repair.

After approval, verify `backups/backup-repair-activation.json`, the deployed and
configured revision, live service PIDs, natural producer jobs, and backup health.
A successful manual backup is not proof of automatic activation. Existing
`config/backup-status.json` records today's successful backup, so a second daily
backup should not be falsely manufactured by editing the success record. Keep
#214 and migration issue #211 open until their respective acceptance checks pass.

[Machine-readable evidence](2026-09-21-backup-repair.json)
