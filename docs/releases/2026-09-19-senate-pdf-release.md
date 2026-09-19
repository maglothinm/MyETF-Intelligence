# PDF/Senate OCR and complete OGE discovery release (#182)

The owner explicitly requested deployment. Application PR #191 merged as
`a9607c88e10959c0cd3844f008915aec12dd0935`; its tested head and selected immutable
build source is `df5bb5a850942ff54f6b73a4936fc9ec18d8e548`. The tree includes
the previously tested PDF policy (#188), complete OGE collection (#190), and
Senate image-viewer review classification. Current Opportunity stays off.

Application verification: local OCR suite **333 passed, 21 environment skips**.
Canonical exact-head checks succeeded: [Source OCR 35450023850](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35450023850),
[Runtime safety 35450023851](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35450023851),
and [Current Opportunity 35450023853](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35450023853).
The OCR workflow includes real PostgreSQL and desktop/mobile preview checks.

The new `ocr_senate_pdf_release.py` explicitly reuses the checksum-pinned prior
release procedure, engine and independent audit. It adds the fourth journal
(`5fd6a3462881fceece2e5665606789f2454a9ecadc28232213cc97eab61ca5b8`), its
verified no-producer recovery, read-only baseline and restored schedule evidence
to the immutable predecessor seal. The prior unsuccessful baseline cannot be
used for acceptance. No previous journal is rewritten or reopened.

One workspace `ocr-senate-pdf-repair-df5bb5a85094` receives fresh preparation.
The exact successful build and registry digest, original resource/scheduler
configuration, private database and recovery settings must match. The unchanged
engine then requires pause/drain, a fresh successful frozen baseline, image/schema
checks, two bounded passes per source, AI/dashboard successors, independent
history/account/acknowledgement/outbox preservation and public OCR-health
acceptance, followed by original schedule restoration. Filing Vault stays paused.

Known unsupported layouts remain reviewable; no transaction rows are invented or
auto-confirmed. Matching retained Senate retry receipts are corrected append-only
without another download or new attempt. The accepted House upload and owner row
review are preserved. Password-required/malformed PDFs remain blocked. This
document records the procedure; deployment acceptance is still pending.

## Active execution checkpoint — September 19, 15:01 UTC

Procedure PR #192 merged at `295c77f1a1ac4907de99a07db281ba052c045eae` after
[controller CI 35450279679](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35450279679)
passed all 96 tests. Installed wrapper SHA-256 is
`a7230d4012a28b344919f8fc881c718c5d6ac93676699b02120215063fe7898b`.
Application OCR CI passed **353 tests, 1 skip**, plus Node and both browser sizes.

Cloud Build `55696595-ff36-411f-922f-65a3657490ab` succeeded at 14:57:28 UTC,
producing immutable image
`us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:ae9b21488499dd8e7f7bbbacac5ccaea5bea0e86a817b0f9ceeea8d79d2586eb`.
Read-only preparation passed all live specifications, build, registry and database
checks. The verified wrapper is running through Beast process `10120`, using the
new workspace under `/home/maglothinm/polititrack-ocr-182-v68vldej`.

The four existing producer schedules are paused and inventory/drain completed.
Fresh frozen baseline `polititrack-admin-lvnpb` is running. Do not start another
controller or modify any journal. The same process must finish acceptance and
restore schedules, or finish its existing recovery. No final deployment acceptance
is claimed at this checkpoint.

The supplemental `verify_senate_pdf_release.py` is an independent read-only SQL
check, to be run through the existing admin job after acceptance. It compares the
new source snapshots to this release's frozen baseline, requires append-only OCR
receipts, unchanged old extraction evidence, both Senate classifications with
unchanged attempt history and no retry timer, new actual extraction files, and
the original two-page/five-row House upload still awaiting owner review with raw
bytes cleared. It neither changes production nor overrides the original audit.

## Recovery checkpoint — September 19, 15:27 UTC

The image was installed on all six resources, and schema/image checks passed.
Legislative `polititrack-legislative-7bwpp` succeeded at 15:15:05 UTC. Its OCR
pass completed five documents and all 11 pages, with zero technical retries and
five review outcomes. It committed generation 1183, snapshot
`2d6cc7a9-49bd-46f6-902e-5523293e9686`, payload SHA-256
`ad6b9b3dd079d59ce0bfd7be8d599663c5bc885c292247688be13fc78a212c76`.

Executive `polititrack-executive-thrvb` failed before OCR after two 120-second
OGE loading waits. No Executive successor was committed. The controller stopped
acceptance and completed recovery at `2026-09-19T15:27:16.200595Z`.
Independent read-only preservation `polititrack-admin-hfd2g` passed, including
original snapshot metadata, ledger prefixes, identities, personal reviews and
notification history. The new image and committed Legislative results are
retained; OCR is disabled on Legislative, Executive and web. All four original
schedules are restored unchanged; Vault remains paused.

The fifth closed journal has SHA-256
`ed2e9e56e3f770d66fa45bf69f47a2c3f20a34ff02db993ab9c130802d931f2d`.
Do not reopen it. Final release acceptance and the supplemental complete-release
check remain unfulfilled.

Read-only reproduction `polititrack-admin-s8mxn` established a collector readiness
defect: the same image's browser had 100 rendered/API rows, matching integer
request/response draw 1, total 16,670, server-side mode, no Loading placeholder
and no page errors, but the current readiness predicate still timed out. A
fresh direct official API request also returned HTTP 200 and consistent metadata.
This reproduction must not be attributed to a currently unavailable OGE service.
The exact failing predicate condition is under investigation.
