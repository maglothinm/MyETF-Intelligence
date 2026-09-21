# Windows local runtime

The owner-authorized issue #211 migration replaces Google Cloud with native
Windows services on Beast. PostgreSQL remains the full Runtime v2 authority;
there is no state reset, alternate database format or second producer schedule.

* `PolitiTrackDatabase`: PostgreSQL 16, loopback port 54329.
* `PolitiTrackWeb`: Waitress dashboard at `http://127.0.0.1:8765`.
* `PolitiTrackScheduler`: existing Legislative, Executive, AI and Dashboard jobs
  at their original UTC minute offsets. Missed slots coalesce after shutdown.

All three services use LocalService, automatic startup and crash recovery.
Closing a browser or signing out does not stop them. Sleep and shutdown pause
processing; internet access is still required for source retrieval and paid APIs.
No change to Windows sleep preferences is made by the installer.

Private configuration, logs and data live under `C:\ProgramData\PolitiTrack`.
The root ACL grants only the owner, Administrators, SYSTEM and LocalService.
Never commit `config/runtime.json`, exported cloud configuration or SQL backups.
`requirements-local.txt` lists local runtime dependencies. The pinned WinSW
2.12.0 binary is checksum checked by `Install-Services.ps1` before registration.
PostgreSQL, Python, Chromium, Tesseract and Poppler must already be installed.

Prepare service XML with `Install-Services.ps1 -PrepareOnly`, review it, then
run the script as administrator. A private `config/local-authority.json` receipt
must explicitly attest repository ID 1349678672, `authority: beast_local`,
`cloud_writers_drained: true`, and `database_verified: true` before scheduling
can start. Service registration alone cannot activate unverified production.

The migration exports all PostgreSQL data after cloud schedules are paused and
public owner writes are blocked. `scripts/local_database_audit.py` fingerprints
every table with binary fields represented by SHA-256; it independently checks
every runtime snapshot's payload hash. Compare the full source and restored
audits before activating local authority. Preserve the source export and its
checksum permanently. The scheduler creates one consistent custom-format backup
per active day and retains the latest two separately from migration evidence.

Local HTTP is restricted to the exact loopback host and port. Owner sessions
retain HttpOnly/SameSite=Strict and origin checks with a dedicated local cookie;
remote deployment HTTPS behavior is unchanged. Vault, Current Opportunity and
manual cloud job controls retain their disabled state. Existing accounts,
acknowledgements, OCR evidence, ledgers and notification delivery state migrate.

Stop the scheduler before maintenance, then the web and database services. Start
the database first. Do not resume any cloud scheduler after local activation.
Recovery must restore the newest verified local backup, not the migration
baseline once newer local production state exists. Off-machine backup media are
recommended for protection against loss of Beast itself.
