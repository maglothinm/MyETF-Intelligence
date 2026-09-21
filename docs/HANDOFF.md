# PolitiTrack active handoff

## September 21 backup engine verified; Windows activation pending (#214)

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`.
Repair PR #215 is merged at `f85a40f6b7b609ad8eec5c899c368d106fedd7c1`.
Beast still runs `42c6f27df5d9266decad3abc7aa6f794edda0f3a`: Windows reported the
administrator prompt canceled. Do not repeat the prompt without the owner
proceeding. The owner has an **Activate PolitiTrack Backup Repair** desktop
shortcut. It verifies the reviewed script hash and requests normal elevation to
restart only PolitiTrackScheduler. Do not rerun the full original setup.

All three services are installed, Running and Automatic, but the old scheduler
still suffers inline pg_dump/RLS failures and restarts. The repair source and CI
are complete; automatic activation and post-activation scheduling are NOT yet
verified. Keep #214 open. Actual reboot remains untested; keep #211 open.

Completed: dedicated replication-only backup login, unchanged application RLS,
manual full physical backup (25,956,737,137 bytes) with pg_verifybackup passed at
19:17:07 UTC, and removal of 10 confirmed failed partials (220,958,188,263 bytes).
Migration export/basebackup are retained. A current old pg_dump partial was left
untouched; additional old partials can accumulate until activation. Read-only
continuity preserved all 4,287 baseline snapshot headers and their successor
lineage. At 19:20 UTC heads: Legislative 1371, Executive 679, AI 772, Dashboard1470.
Local application config and authority receipt are unchanged. Dashboard HTTP200.

Next: owner opens the shortcut and approves UAC. Verify the saved activation
receipt, service/source revision, natural jobs, and backup health. The independent
backup engine records today's manual success; never edit it to fake a scheduled
backup. No production reset, migration replay, live-cloud recreation, permissions
relaxation, or reinstatement of retired writers is allowed.

[Backup repair evidence](releases/2026-09-21-backup-repair.md) and
[JSON receipt](releases/2026-09-21-backup-repair.json). Earlier cutover evidence:
[release record](releases/2026-09-21-beast-local-cutover.md).
