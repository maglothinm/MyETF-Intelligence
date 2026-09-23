# PolitiTrack active handoff

## September 23 #232 - complete filer directory merged; Windows activation canceled

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
[PR #233](https://github.com/maglothinm/MyETF-Intelligence/pull/233) merged as
**83501363c719aa14a46e141ef4c94cfb0532d23b**, matching tested head
**a37133f08d4e77b164e89d27bb4625ec31b89c40**. It removes the 40-profile admission
cap, publishes all retained known filers with explicit evidence/review status,
keeps background observation/provider limits, and adds filer-name/status filters
and complete CSV export on root and standalone profile views.

All exact-head workflows passed on attempt **1**:
- [Investor Edge 35857964119](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964119).
- [Runtime v2 safety 35857964150](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964150).
- [Source upload/OCR 35857964122](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964122).
- [Current Opportunity 35857964184](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964184).

Local regression: **412 passed**, using UTF-8 as the Beast launcher does. Root
and standalone real-browser search/status/clear/responsive checks passed at 1280
and 390 pixels, with zero JavaScript errors. Offline snapshot replay published
**1,028 owner profiles covering all 975 known filer names**, including Donald Trump,
while preserving 62 prior profiles, 1,519 observations and all history-ledger bytes,
with zero provider requests. Source classification and the original filing review
were not changed. These are source/offline checks, not live directory acceptance.

### Activation boundary

The normal administrator prompt was opened at approximately **12:04:36 UTC**.
Windows subsequently returned **The operation was canceled by the user** before
the elevated activation script started. No activation receipt or transcript was
created; no automatic retry was made. As verified at the end of this attempt,
Beast application/config remain **0c2ab975a837a1d2a28ca4e041019d0103413b54**.
Database PID **25732**, web PID **36060**, and scheduler PID **38268** remain running
with automatic startup. The directory change is **merged, not activated**.

The read-only continuity checkpoint at `2026-09-23T12:02:16.803496+00:00` covers
**4,706 immutable snapshot headers**, digest `7d77ad4fde7c22093e23f7424666093f`.
The after-attempt verification matched it. No rebaseline, review approval, filing
upload, new writer/schedule or cloud/legacy activation occurred.

### Next safe action

The Desktop shortcut **Activate PolitiTrack Profile Search** is ready. Its launcher
pins the merged revision and tested head above, verifies the prepared helper SHA-256
`6A8EAEFA223D8A19B4C0024BEBCBEABAC41289FB7545C81426CD89F72C8AEEA5`, prevents
overlapping launches and requests normal Windows approval. The package is
`C:\ProgramData\PolitiTrack\releases\profiles232\Apply.ps1`; it reuses the existing
idle check, web/scheduler stop/start, configuration revision and continuity checks.
Do not restart or replace PostgreSQL. User-visible launcher and verification
reports are retained in this task's outputs folder.

After owner-approved activation, use `work/publish_profiles232.py` with the merged
revision to run the existing AI/dashboard producers under their normal locks.
Run `work/verify_profiles232_live.py` with that revision to compare persisted AI,
served JSON/CSV and snapshot bytes, directory completeness, per-run budgets,
original review receipt and parent links. Recheck browser search against the live
site, repeat the continuity check and record an accepted completion receipt.
Keep [#232](https://github.com/maglothinm/MyETF-Intelligence/issues/232) open until
live verification. [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225)
retains its independent manual-upload outage acceptance boundary.
