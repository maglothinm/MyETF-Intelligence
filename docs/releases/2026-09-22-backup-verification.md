# Beast backup repair: activated and independently verified

Verified on September 22, 2026, through 11:27:15 UTC (7:27 a.m. Eastern).
Canonical repository ID 1349678672, maglothinm/MyETF-Intelligence; main application
revision f85a40f6b7b609ad8eec5c899c368d106fedd7c1 is checked out and configured.

Activation completed at 11:16:42 UTC. All three Windows services are Running and
Automatic under LocalService. Database/web PIDs remain 25732/23084; scheduler
PID is 13600. No unexpected service termination was recorded after activation
through this observation. Do not rerun either setup or repair activation.

The independent scheduler-launched backup ran 11:16:43 to 11:19:46 UTC, producing
27,197,505,861 bytes in routine-20260922T111643Z-e19aaa22.base. Its full
pg_verifybackup passed. An independent repeat check passed at 11:25:54 UTC with
exit 0, ignoring only the post-verification metadata file verified.json; database
checksums and WAL parsing were not skipped. The manifest SHA-256 matches:
de6f1ef5b813368a2222c739dd454ce03a0d3cadc5d08983ba1b307e030cdffe.

Legislative and AI jobs completed during the backup. A natural dashboard slot
started at 11:17:02 and completed at 11:17:22 while the backup was in progress.
Legislative ran again at 11:20:02 and exited 0 at 11:20:17. This verifies that
backup work no longer blocks the production scheduling loop. Root and readiness
HTTP endpoints returned 200. Main-source OCR CI run 35643473255 succeeded.

## Separate outstanding items

38 old local-*.partial files total 1,061,305,390,205 bytes. Their latest write was
before activation; no pg_dump was running. Free C: space was 182,076,276,736 bytes
at 11:27:15 UTC. None were deleted during this verification. Retain both verified
routine backups and all migration evidence when performing separately scoped
legacy-partial cleanup; never delete the live database or a current worker file.

The Executive collector failed independently: OGE API connection timeouts and
two bounded page-load attempts ended at 11:20:47 UTC. Executive OCR was skipped
because collection failed. This did not crash the repaired scheduler. No OGE
recovery or system-wide healthy status is claimed.

Windows has not rebooted since September 20. Reboot/start-before-sign-in and an
actual restore drill remain untested. A fresh live database continuity audit was
not completed; this verification does not claim a new payload/history rehash.
No production code, state, permissions, services, or schedules were changed here.

Exact observed metadata: 2026-09-22-backup-verification.json.
