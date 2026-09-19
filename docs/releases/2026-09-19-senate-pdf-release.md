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
