# Source uploads and durable OCR — issue #182

**Development feature, default disabled. Not a production activation receipt.**
Canonical repository: `maglothinm/MyETF-Intelligence`, numeric ID `1349678672`.

## What is implemented

The Records filing/detail and retained parser-exception detail offer **Upload source / OCR**. An authorized, signed-in account can associate one existing official filing with a PDF, PNG, JPEG or TIFF. Input is signature/decoder checked, bounded to 20 MiB and 20 million rendered pixels per page. Authorized manual uploads have no fixed page-count cap at intake or OCR; automatic downloads retain their 30-page cap. File names are not identities or server paths. Uploads are private, deduplicated by account/filing/content hash and limited to ten new uploads per account per hour and twenty raw documents globally.

The private SQL inbox is shared by the web service and the existing source producer. No browser-local upload path, new scheduled writer or Filing Vault activation is involved. Each successful producer run performs a bounded OCR-maintenance pass before committing its canonical snapshot. Defaults are five documents and a 180-second admission budget per source run; an in-flight bounded render/OCR operation may finish after that admission budget. Uploads are prioritized, followed by newly observed filings, existing parser failures, and untouched historical records. Already-seen and acknowledged filings remain eligible. A retry/backoff record is independent of seen filing/trade/review IDs.

Every newly encountered PDF/image content version goes through optical recognition, including files with a native text layer. Native text is retained for comparison, not silently replaced with OCR. The extractor invokes Tesseract separately for each rendered page under one document-wide OCR deadline for automatic downloads, or a per-page engine watchdog for manual uploads, with cumulative output safeguards retained. Successful per-page execution and valid output bind coordinates to physical pages, without relying on the multi-image TSV's incomplete page markers. Missing output or failed execution rejects the document; a completed page with no recognized words remains explicit review evidence, never proof of a blank page or permission for partial import. Durable extraction evidence is keyed by SHA-256 and extractor version under `ocr-evidence/`; attempts/statuses are retained in `source-ocr.jsonl`. Successful unchanged versions reuse their extraction rather than running OCR at every poll. Seven-day revalidation can detect changed bytes at a retained URL. HTML filings without page images are explicitly not applicable, not mislabeled as OCR-complete.

Due technical retries are prioritized after uploads/new filings and before parser-failure or untouched-history work, oldest attempt first. Existing backoff remains mandatory. This prevents historical inventory from indefinitely delaying recovery. Request-only OGE sources remain in the last access tier. Retained successful extraction versions and pending owner confirmations are not invalidated by this repair; live activation is separately required (issue #203).

The House paper-PTR decoder uses the four transaction-type and eleven amount-column checkbox layout. It separates printed examples, empty rows and actual transactions; preserves page/physical-row identity, unknown ownership and disclosed dollar ranges; and never invents stock tickers. This is a form-family parser, not a claim that arbitrary scanned tables are reliably understood. In particular, the third type is **Partial Sale**, amount J is **Over $50,000,000**, and K is the special spouse/dependent-child asset category, not an invented $100-million band.

## Owner review and canonical updates

An uploaded document is not presumed authentic from its name, selected record or matching text. Uploads require confirmation before canonical transaction import. The owner can review a complete extracted House table and correct asset text, selections and dates. The API checks account, expected document hash, unchanged physical row count/order, supported ranges and dates. Missing rows/pages, unsupported layouts and mismatched filers are not approved through this editor. Conflicts with an existing trusted transaction set remain review-required; this feature does not silently replace those rows.

The sole source writer reconciles accepted rows append-only inside its normal snapshot transaction. Prior first-observed times, filing dates, seen-filing timestamps, pending-review history, and personal acknowledgement events are preserved. A filing is resolved only with durably accepted transactions. Recovered rows use the existing historical-bootstrap marker: Investor Edge can consume historical evidence, but the change does not resend old filing alerts or backdate paper trades. Normal existing electronic-filing notification behavior is unchanged.

Automatic downloads use official-source transports. Senate keeps the existing validated access/terms handshake; OGE request-only access is reported as requiring access, not bypassed. Senate image-viewer layouts without a supported PDF remain review-required. A source-file upload is the manual bridge for legitimately retrieved documents.

## Temporary bytes and recovery

OCR files are created only in a scoped temporary directory. Upload bytes stay in the private inbox until extraction evidence/outcome is committed in the canonical source snapshot. Only then does the runner acknowledge the result and clear bytes. Failed OCR keeps bytes for retry; failed canonical commit cannot acknowledge or delete them. A crash after commit but before acknowledgement replays the committed upload receipt without duplicate extraction/import. Raw uploads expire after seven days; expiry is enforced on the next intake/status/producer maintenance transaction. Hashes, extraction evidence, source identity, corrections and status history remain. Neither raw uploads nor private OCR previews are published as dashboard/Actions assets or checked into git.

## OCR run health (owner requirement, September 17)

OCR has a separate stage outcome; a successful collector or successful snapshot is
not by itself an OCR success. The existing production run record stores an
allowlisted `runtime_mode_evidence.source_ocr` object. Recording telemetry does
not change run success, snapshot lineage, personal reviews or outbox state. The
atomic source commit preserves this field while replacing the runner provenance
with its normal snapshot attestation. Health is finalized after upload cleanup.
No additional health table, scheduled writer, external service or secret is added.

Stages distinguish waiting for collection, processing, awaiting canonical commit,
completed maintenance, failure, and skipped work after a collector failure. A
missing engine is a failure even on an otherwise idle pass. Upload-intake failure,
document retry backlog and post-commit cleanup failure are degraded health, not
hidden behind collector success. Human interpretation and official-access
requirements are separate counts, not engine failures. A completed idle pass is
healthy only when the commit and cleanup are confirmed.

Operations reports start/heartbeat/last healthy pass, last document actually
OCR-processed, document/page counts, reused extractions, appended transactions,
ready/unobserved work, oldest ready observation, review/access/retry counts,
intake and cleanup results. Run-history tooltips include the OCR stage where
available. The overall monitoring banner and brief include required OCR health;
collector status remains separately truthful. Once retained OCR inventory exists,
missing later telemetry cannot silently remove OCR from the required rollup.
Browser time advances the age of published evidence, never creates a new run.

A processing/commit heartbeat older than ten minutes is stale; collection-wait
uses thirty minutes. Completed passes use the source's existing freshness window.
Three distinct completed passes with ready work but no attempt or acknowledgement
progress are stalled. These are reported as published evidence, not continuous
live worker probes. Dashboard publication delays still apply. This change adds no
notification provider and does not change the existing sixty-minute Inbox
interruption policy or create a second alert schedule.

The extractor version is now `source-ocr-v2`. PDF/image inspection is isolated in a
child process with timeout and Linux CPU/address-space limits. Intake checks
capacity before decoder admission; decoder/render/OCR subprocesses receive no
application secrets or proxy configuration. A rotated or unreadable continuation
with no validated form layout prevents automatic partial-table import. Unsupported
layouts remain review-required rather than being described as successfully parsed.

## Activation gates — not executed by this change

1. Review and pass exact-head CI, real PostgreSQL and isolated browser evidence, plus the owner-provided two-page regression document. Test failed commit/acknowledgement recovery and malformed/encrypted/oversized documents before production release.
2. Use the established approved Runtime v2 release process. Create only the additive inbox table using `python -m runtime_v2.cli source-ocr-init-db` against the existing private runtime database. Do not initialize source state or personal accounts.
3. Configure `RUNTIME_SOURCE_OCR_ENABLED=true` consistently on the web service and existing legislative/executive producers. Configure `RUNTIME_SOURCE_OCR_ACCOUNT_IDS` to the authorized stable personal-account UUID(s), preserve the existing HTTPS `RUNTIME_REVIEW_ORIGIN`, and keep `DISCLOSURE_TERMS_ACKNOWLEDGED` accurate. Optional bounds are `RUNTIME_SOURCE_OCR_FILES_PER_RUN` and `RUNTIME_SOURCE_OCR_SECONDS_PER_RUN`. No schedule or unrelated feature flag changes are required. Vault remains paused.
4. Verify independent OCR health in the existing Operations panels and overall monitoring rollup. Confirm that the committed source run contains stage evidence, actual document/page counts and a finalized cleanup outcome. Use isolated tests, not destructive production fault injection, to prove stale/failed/intake/cleanup paths.
5. Verify one upload through committed import/publication, original-file cleanup, a subsequent idempotent run, bounded historical advancement, and unchanged protected-history/alert state. Explicitly record source revision, image digest, schema migration, producer runs and publication. Do not label a merged PR or green unit tests as live deployment.

The maintenance pass currently follows successful normal source collection. An upstream collector outage can therefore delay OCR/import work. OCR coverage in the interface is a last-published snapshot, not a live progress estimate, and is separate from Investor Edge market-outcome backfill.

## Regression material

Owner attachment `9116331.pdf`, SHA-256 `58cefce89a3fe84a5d4893337e79b4bc9add769d02fac1869403456afd5a4343`, is **not** committed or exported publicly by this change. Native text is absent on both pages. Real local extraction recovered five transaction rows (four on page one, one on page two), correct Purchase/Sale marks, column B for all five, transaction dates July 30/August 6, 2026, and notification date August 19, 2026. Three asset labels remain low-confidence and correctly require owner review. Preserve the September 11 filing/receipt date separately. Two repeated-looking school-asset rows are not silently collapsed; the preprinted 2020 example and its JT ownership are not transactions.

Public automated tests generate synthetic source images. `tests/source_ocr_browser_preview.py` exercises the actual upload/review JavaScript at desktop and mobile widths against in-memory TEST responses with all fetch calls replaced, not live APIs.
