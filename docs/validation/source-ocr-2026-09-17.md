# Source OCR development validation — September 17, 2026

Issue #182; canonical repository ID 1349678672. Branch `codex/source-upload-ocr-20260917`.
This is source-development evidence, **not** a production release or activation certificate.

## Executed locally

- Combined focused regression: **236 passed, 20 skipped**, 22.65 seconds. The skips include PostgreSQL-dependent tests; no local PostgreSQL success is claimed.
- Suites: source OCR, source OCR runtime/intake, government trade tracker, historical transaction bootstrap, trade dashboard, dashboard insights, Runtime v2 core/atomic commit/shadow/bootstrap safety, personal reviews and legislative resilient orchestration/integration.
- Real Tesseract: generated synthetic image fixture passed. Owner-provided two-page document was also actually rendered/OCR-processed, independently of mocked tests: all five physical rows recovered; checked Purchase/Sale and column B selections correct; three low-confidence asset labels correctly remain for review. Raw owner document is not in this repository or any public artifact.
- Isolated Chromium desktop/mobile review: 1280- and 390-pixel widths; five retained rows, one corrected/confirmed submission, expected account header, zero browser JavaScript errors. Fetch is replaced by in-memory TEST responses; no live endpoint, data or credentials are used.
- Python compilation, JavaScript syntax and `git diff --check` passed at the development checkpoint.
- Failed-commit tests prove the runner does not acknowledge/delete uploaded bytes after canonical commit failure. Committed-outcome replay avoids repeated import. Evidence disk failure aborts instead of returning a false processing receipt. Expired resubmission honors queue limits and preserves initial upload time.

## Historical pre-health release gate

Exact-head canonical CI (including the real PostgreSQL service), independent code/security review, approved additive schema migration, bounded live backfill, one full upload/confirmation/import/publication, cleanup/replay checks, and pre/post production-state preservation must be verified separately. No production image, schedule, database, canonical snapshot, account, alert or Vault flag has been modified by this development session.

The read-only source acquisition and dependency acquisition workflows used during development are removed from the final feature tree. Their successful artifacts are development inputs, not protected production-state authority. The initial dependency workflow had a YAML error, corrected before its successful run. None of those runs validate the application feature.


## OCR health and bounded-decoder checkpoint (same day, not live)

The owner authorized continuing through release and added independent OCR run
health. Verified input source archive: canonical branch revision
`6588f5350f5a8817694d81b6eb73aefb96372f11`, read-only source-bundle run
`35270146787`, artifact `10517974097`, archive SHA-256
`ae9e1b5c2b74e360e92474532c3fc23c6465fc85e6f7b52a24502b1bb5eb7af9`.
This artifact contains tracked source only and is not production-state authority.

Executed locally after the health/decoder changes:

- Focused OCR/intake/runtime/health suite: **47 passed, 5 skipped**. The skips are
  real-PostgreSQL cases; they must pass separately in canonical CI.
- Corrected dashboard/health subset: **39 passed, 1 skipped** at the preceding
  local checkpoint. A legacy history-label compatibility regression and a test
  fixture mistakenly marked synthetic were fixed before that pass.
- Node OCR health tests: **4 passed** (collector/OCR separation, stale evidence,
  Operations/history details and HTML escaping).
- Chromium desktop/mobile upload correction and Operations health checks passed
  at 1280/390-pixel widths: one five-row correction submission, collector success
  displayed alongside OCR failure, no horizontal clipping, no JavaScript errors.
  All fetch responses are in-memory TEST fixtures, not live APIs.
- Actual owner sample using `source-ocr-v2`: both pages OCR-completed, five rows,
  no page-layout problem, correct transaction/range selections; three degraded
  asset labels remain review-required. No owner document or derived private OCR
  text is included in the source tree or public test artifacts.
- Python compilation, JavaScript syntax and whitespace checks passed locally.
- Two larger combined local suite attempts reached test completion output but
  exceeded the command time limit before a final summary/exit was captured; they
  are not counted as successful completed regression runs.

Added real-PostgreSQL coverage proves health writes are scoped to the matching
source run, preserved through atomic snapshot attestation and independent of
post-commit cleanup failure. Exact-head CI and its precise outcome are recorded
in PR #183 after publication; a previous source head's green checks do not certify
these additions. New tests also cover encrypted files, decoder timeout/secret
isolation, mixed/unvalidated continuation layout, missing binaries, missing health
evidence, retry persistence, failed collection and cleanup/commit boundaries.

Deployment is blocked by the offline authorized Beast release connection, not by
missing feature approval. The owner has been prompted to reconnect it. Production
schema, current images, feature flags, scheduler state, source snapshots and live
health are unmodified/unverified by this development checkpoint. The next live
step is a fresh authenticated GCP read and preservation baseline, not replaying an
old recovery/cutover workflow. No runtime completeness or live OCR claim is made.
