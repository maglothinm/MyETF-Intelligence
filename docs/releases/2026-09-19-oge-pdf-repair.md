# OGE download classification and readable-PDF repair (#182)

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Implementation branch: `codex/oge-pdf-repair-20260919`, based on `8ca6c4b`.
Source implementation is complete; canonical CI and merge evidence will be
recorded below. **This repair has not been deployed.**

## Causes and changes

The [read-only diagnosis](2026-09-19-ocr-functionality-diagnosis.md) found 340
retained OGE PDF links incorrectly classified as request-only, and 217
Legislative `invalid_or_encrypted_pdf` outcomes. Representative public PDF
downloads reproduced both paths.

- Recognize official HTTPS PDF paths before the legacy broad-host request rule.
  PDF filenames in a Form 201 query, nonofficial hosts, credentials and nonstandard
  ports do not qualify for automatic reclassification. HTTP content and document
  bounds are still checked after download.
- Keep the **old URL-slot calculation solely for listing-ID hashing**. Corrected
  document/request fields do not change existing listing/filing keys or create
  newly observed filings. Existing listing exports retain their supplied IDs.
- Append corrected access metadata through the existing Executive producer for
  retained PDFs, including records absent from current discovery. Preserve source
  URL, first-seen time, collector outcome, counts, unknown metadata and original
  ledger rows. A repeat pass is a no-op.
- Retry affected old invalid-PDF/direct-OGE-access failures once under
  `source-document-policy-v2`, bypassing their obsolete delay/review timers. Keep
  `source-ocr-v2` extraction caches and pending confirmations intact; new failures
  and unrelated reviews keep normal backoff. Real gated OGE requests sort behind
  accessible documents, while owner uploads keep first priority.
- Open PDFs with an explicitly empty user password. Public, permission-encrypted
  PDFs are accepted when the decoder can read them normally. No supplied owner
  password, password guessing, rewritten decrypted document or permission removal
  is involved. Password-required/malformed PDFs remain rejected. Byte, page,
  pixel, native-text and isolated-process limits remain unchanged.

## Additional parsing finding

The old generic parser's 5/37 candidate outputs from the two OGE samples are not
validated trades. Inspection revealed that split `RECEIVED OVER` / `30 DAYS AGO`
column headings were being prepended to the first asset name; one sample also has
wrapped asset-name continuations. A narrow guard now rejects the whole parse when
this known header contaminates an asset, sending it to layout review rather than
publishing corrupted transactions after downloads become reachable.

The repair establishes download and extraction eligibility, **not complete OGE
transaction ingestion**. Those layouts need validated parsing/row-completeness
acceptance before automatic import. The owner's uploaded House rows still require
the existing document-specific review; no corrections were submitted.

## Verification

- Targeted source/worker/collector tests: **99 passed, 4 PostgreSQL-dependent
  skips** locally. Includes old-ID compatibility for PDF/request/landing-link
  combinations, old export normalization, actual HTTP-call eligibility, request
  gating, silent historical recovery, append-only metadata, repeat idempotence,
  old rejection retry, unrelated backoff and successful evidence preservation.
- Neighboring runtime/dashboard/preservation tests: **199 passed, 17
  environment-dependent skips** locally. Four Node OCR-health tests passed.
- A synthetic AES-256 PDF with an empty user password passes bounded inspection
  and actual Poppler/Tesseract extraction on both pages. The existing real
  password-required fixture still fails closed. Page-limit checks still reject
  the same readable encrypted document when its page count exceeds the limit.
- Both previously rejected public House samples pass bounded inspection. Actual
  OCR completed **2/2 pages** for `house:2025:20030307`, and **3/3 pages** for
  `oge:c7aa20fb7288756065000dbbacfa2d07`. Their original bytes/hashes are unchanged;
  derived text and downloaded documents are not committed as fixtures.
- On an isolated copy of the published ledger, exactly **340 access records**
  changed, **all 5,144 filing keys and every unrelated field** were preserved,
  the original ledger remained an unchanged prefix, and the second refresh wrote
  nothing. This is a diagnostic-copy check, not a production continuity audit.
- Compile and whitespace checks passed. The canonical Source OCR workflow now
  includes the OGE regression suite and synthetic fixture path; its existing
  PostgreSQL service supplies the database coverage unavailable locally.

## Release status and continuation

Canonical CI/merge: pending at source checkpoint.

Beast was **offline** when checked during this repair. The connected Cloud Shell
deployment path is therefore unavailable. No build, controller, migration,
production state write or manual producer dispatch was performed. No current
database/snapshot preservation audit is claimed. The existing sealed journals
remain untouched; last verified production remains the September 18 release
`a2a15edb30895ece37b690e50e0f95fb1eaa2649`, four original schedules enabled and
Filing Vault paused.

Next: finish canonical CI/merge, then use a new coordinated release with an
immutable tested image, fresh preservation baseline, the existing source writers,
independent identity/count/history checks and live OCR-health acceptance. Do not
reopen old release journals, rebaseline, replay historical alerts or claim all
Executive transactions recovered. Keep issue #182 open.
