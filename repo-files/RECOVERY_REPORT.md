# MyETF government trade tracker recovery report

Assessment and implementation date: 2026-08-25

## Executive result

A stand-alone monitoring path has been implemented for newly published government purchase disclosures. It replaces the repository's non-operational House/Senate alert scripts and avoids making the older dashboard a prerequisite for collection.

The delivered overlay has two independent GitHub Actions workflows:

1. **Legislative purchase tracker** — official House and Senate PTR discovery, purchase-row normalization, persistent deduplication, CSV/JSONL output, and Pushover alerts.
2. **Executive purchase tracker** — browser-based OGE Form 278-T listing discovery, direct-document parsing when available, and a durable request/manual-review queue when a Form 201 request is required.

Offline verification passes 23 tests. A synthetic end-to-end request-queue smoke test is included in `verify.sh`.

## Original repository defects addressed

### P0 — scheduled monitoring was stopped or falsely green

The prior House and Senate workflows had been disabled. The Senate job never executed its parser, so a green run represented dependency installation rather than successful monitoring.

**Resolution:** both obsolete workflows are removed and replaced with workflows that execute tests, restore state, run the tracker, upload results, and send independent failure/heartbeat signals.

### P0 — House annual index was consumed incorrectly

The prior House script treated the annual ZIP as though it directly contained current PTR PDFs and hard-coded a single year.

**Resolution:** the tracker reads the annual index, filters Periodic Transaction Reports, derives each PDF URL from `Year` and `DocID`, and reads both the current and prior year to avoid year-boundary loss.

### P0 — Senate parser was a placeholder

The prior Senate script referenced a test PDF and an undefined notification function.

**Resolution:** the tracker performs the Senate public-use/CSRF flow, searches report type 11, paginates results, parses electronic tables, follows paper-report links, and creates review records where row semantics cannot be recovered reliably.

### P0 — single-company keyword monitoring

The old recovery target detected only configured text keywords.

**Resolution:** the new parser records every normalized purchase transaction. `WATCHLIST` is now an optional notification filter and never a data-loss filter.

### P1 — no durable purchase ledger

The prior scripts did not produce a reusable transaction dataset.

**Resolution:** each branch has an append-only JSONL ledger, a pending-review JSONL queue, a versioned state file, and a latest-purchases CSV. Stable trade/review IDs prevent duplicate records and alerts.

### P1 — state loss and scheduler death could remain silent

**Resolution:** scheduled runs fail closed if state cannot be restored. State is saved through both Actions cache and retained artifacts. Optional Healthchecks start/success/failure pings provide an external dead-man signal.

### P1 — paper and request-required filings could be silently skipped

**Resolution:** recognized paper House/Senate forms and OGE Form 201 listings create one-time review records with official links. They are not represented as successfully parsed trades.

## Current coverage limits

### Legislative

Coverage is the official House and Senate PTR filing universe returned by their public systems. Those systems can include candidates, officers, or covered employees as well as sitting Members. The first implementation does not enrich filers against a current-member roster.

### Executive

No centralized public endpoint exposes every Executive-branch public financial disclosure. OGE reviews a relatively small subset; many reports are maintained by employing agencies. OGE directly posts some documents and exposes/request-routes others.

The delivered workflow therefore provides:

- direct parsing where OGE publishes the 278-T document;
- a review/request alert where Form 201 is required;
- no claim of full coverage for agency-held reports.

Agency-specific connectors and a managed Form 201 intake process are separate workstreams.

## Operational acceptance still required

The code can be tested offline, but two actions require repository access:

1. Commit/push the overlay and re-enable the scheduled workflows on the default branch.
2. Run each workflow once with `initialize_state=true` and `bootstrap_alerts=false`.

The first live OGE workflow run is also the acceptance test for its current browser selectors. OGE can change its client-rendered table without a versioned API contract; diagnostics are uploaded when that happens.

## Security and compliance controls

- Secrets are scoped to notification/heartbeat steps rather than stored in source.
- State and output files are ignored by Git.
- Source requests have timeouts, size limits, retries, schema checks, and OCR page limits.
- The tracker requires explicit `DISCLOSURE_TERMS_ACKNOWLEDGED=true` before source access.
- The OGE collector does not bypass Form 201 or synthesize inaccessible records.

Review the statutory restrictions before commercial, automated-investment, or redistribution use.

## Verification status

- Python compilation: passed.
- Workflow YAML parsing and structural assertions: passed by `verify.sh`.
- Parser/state tests: 23 passed.
- Synthetic Executive request-queue integration: passed by `verify.sh`.
- Clean mock-repository install and idempotency: passed by `verify.sh`.
- Live House/Senate network run: not executed in this isolated build environment.
- Live OGE browser run: not executed in this isolated build environment.
- Commit/push to GitHub: not performed because GitHub account connection failed.
