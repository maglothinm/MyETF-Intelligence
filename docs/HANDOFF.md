# PolitiTrack active handoff

## September 21 backup repair (#214) - source acceptance; live verification pending

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`.
Branch `codex/beast-backup-repair-214`. The owner completed the Windows installer;
all three services are installed, Running and Automatic. The earlier pending-UAC
note is historical. Natural production jobs advanced the local immutable heads.

The inline runtime-role pg_dump failed on protected Vault tables, blocked the
producer loop and crashed the scheduler. Windows repeatedly restarted it.
Replace it with a separate physical-backup child using a dedicated non-superuser
REPLICATION login; verify the full manifest before atomic publication; retain two
verified routine backups and preserve all migration recovery evidence. Failure
backoff and backup health are separate from producer scheduling. Application RLS,
producer schedules, snapshot contracts and local authority remain unchanged.

Source tests are not live acceptance. Activate only merged/tested source using
`deploy/local-windows/Apply-Backup-Repair.ps1`, with normal Windows administrator
approval. Restart only PolitiTrackScheduler. Do not restart the database/web,
reinitialize data, restore the migration export, reactivate cloud writers or
remove backups until actual verification and safe cleanup evidence are recorded.
Check `config/backup-status.json`, `logs/routine-backup.log`, natural production
runs and services. Actual reboot behavior remains untested. Keep #211 open.

## September 21 Beast cutover — finish Windows administrator approval (#211)

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`. Application
PR #212 is merged; Beast runs main source
`42c6f27df5d9266decad3abc7aa6f794edda0f3a`. Follow-up evidence branch:
`codex/beast-local-cutover-evidence-20260921`.

Production authority is now **Beast local PostgreSQL**, not Google Cloud. All 18
source tables and 4,256 snapshot payloads matched before activation. All four
local production jobs succeeded. Current heads are Legislative 1361, Executive
673, AI 765 and Dashboard 1461, each the direct immutable successor of the frozen
cloud head. Post-cycle baseline fingerprints and new payload hashes passed.
Local HTTP/data/assets, review session API, desktop parser, OCR, Chromium and
private Vault storage were verified. Full export and a verified post-cycle
physical recovery backup are retained under `C:\ProgramData\PolitiTrack\backups`.

Cloud database, jobs, service, schedules, artifact repository, secrets and active
buckets are deleted; SQL backup list is empty. Two internal network reservations
and provider-retained deleted bucket records remain. Bucket hard-delete dates
are September 28; do not promise a zero final bill or immediate permanent purge.
All three retired GitHub state workflows remain disabled. Never resume them or
restore the old cloud database as authority after these new local writes.

**Only startup activation remains blocked:** the owner canceled the administrator
prompt. No core Windows services exist yet, and no recurring local scheduler is
running. PostgreSQL/web are temporarily running under the owner; the existing
tray runs and its sign-in startup entry is enabled. Do not conflate tray startup
with automatic background services.

Next safe action: the owner double-clicks **Finish PolitiTrack Setup** on Beast's
Desktop and approves the Windows UAC prompt. Do not trigger another prompt
without the owner proceeding. The reviewed installer is
`C:\ProgramData\PolitiTrack\app\deploy\local-windows\Install-Services.ps1`.
It stops the dedicated manual web/database cleanly, installs
PolitiTrackDatabase/PolitiTrackWeb/PolitiTrackScheduler under LocalService with
automatic startup/recovery, and saves `backups/installed-services.json` after
readiness passes. Verify those live services and a natural scheduled cycle;
verify reboot behavior when the owner is ready. Keep #211 open until then.

If installation fails, inspect `logs/service-install.log`. Repair the existing
installation; do not initialize a new database, replay the migration export,
rebaseline state, or recreate Google Cloud. Vault API remains enabled with local
storage; lifecycle stays paused. Current Opportunity/manual cloud controls stay
off. Preserve the existing OCR access/retry backlog and upload/review records.

[Release record](releases/2026-09-21-beast-local-cutover.md) ·
[Exact receipts](releases/2026-09-21-beast-local-cutover.json).
