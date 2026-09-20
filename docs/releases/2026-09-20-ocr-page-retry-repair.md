# OCR page completion and overdue retries - issue #203

Status: source and canonical CI verified; PR #204 unmerged and not deployed.
Repository: `maglothinm/MyETF-Intelligence`, ID `1349678672`.
Baseline main: `2404ca2347e703b5699b31efbbcc56027d44fb37`.

## Observed production evidence

Read-only public snapshot generated `2026-09-20T12:04:33Z`:

| Source | Collector | Last successful run (UTC) | Latest OCR pages | Retained technical retries |
|---|---|---|---|---|
| Legislative | success | 11:53:51.651812 | 5/5 | 15 |
| Executive | success | 11:47:20.195769 | 20/20 | 3 |
| AI | success | 11:49:51.360556 | not applicable | not applicable |

The 5,152-filing public ledger contained 15 House `incomplete_page_ocr`
receipts, plus Executive `Error`, `ReadTimeout` and `MonitorError`. Their retry
times had passed. Current queue sorting put unattempted history (empty attempt
timestamp) before retained retries within the same priority class.

362 `invalid_or_encrypted_pdf` records are historical, all attempted before the
September 19 accepted release (newest 14:52:09 UTC); they are not evidence that
the released empty-password-PDF repair newly failed. Do not bulk reset them.

## Reproduction and source repair

Official House filing 8220754, four pages, SHA-256
`3e3736f784e4cb8148913c8b195f3a8fd5268cebbecc976960fa5a273f1746ba`,
reproduced `incomplete_page_ocr` with the original source. All four input names
appeared in Tesseract's process log, but only three page headers appeared in its
combined TSV. Visual inspection showed sideways scanned tables. This observation
does not identify Tesseract's internal cause or permit dropping any source page.

The repaired extractor binds successful single-page processes and valid outputs
to exact physical pages. One OCR deadline and cumulative document output limits
remain enforced. Missing files/headers with content, foreign/duplicate page
headers, malformed outputs and failed processes remain errors. Header-only
no-text output after a successful explicit page invocation is retained as
`empty_ocr_pages`; it blocks import, including approved partial rows. Unsupported
layouts and native/OCR disagreement remain human review, not invented trades.

Post-repair local results:

| Official sample | Actual pages completed | Parser outcome |
|---|---|---|
| 8220754 | 4/4 | `unsupported_scanned_layout` |
| 20034351 | 3/3 | `native_ocr_disagreement` |

20034351 SHA-256:
`1b58481cecdd446a5cf507c19b7e48e5ba8a04d06a6f71ae131e961f6b76c711`.
Documents were temporary local diagnostic inputs, not committed fixtures or
production imports. The remaining 16 retry documents were not individually
reproduced; no claim is made that all their underlying failures are fixed.

The queue now places due technical retries ahead of parser failures/history,
after uploads/new filings, using oldest prior attempt first. Backoff, budgets,
restricted-source access, sole-writer ownership and append-only receipts remain
unchanged. Health remains degraded while actual technical retries exist.

## Verification

- Focused OCR/extraction/runtime/health: 83 passed, 5 integration skips.
- Broader existing OCR CI Python selection: 346 passed, 22 environment-dependent
  skips (including PostgreSQL/browser checks not available locally).
- Existing Node OCR-health suite: four passed.
- Real Tesseract synthetic no-text middle page retains page 3 coordinates and
  flags review; missing/malformed/failed output, shared deadline, cumulative size,
  retry ordering/backoff and no-partial-import tests pass.
- `git diff --check` passed. Exact source head
  `ce63ba37c7bfaf4ce54c60ef0695e6fc694552b3` passed canonical OCR
  [35510220534](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35510220534),
  Runtime safety [35510220533](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35510220533),
  and Current Opportunity offline [35510220529](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35510220529).

The local environment's initial NumPy install failed on import; reinstalling the
same pinned version repaired the test environment. No application requirement
or production dependency was changed for that incidental failure.

## Deployment boundary and next safe action

The original source-repair session was blocked by an offline deployment device.
On reconnect, Beast and its existing Google Cloud sign-in were verified. A
read-only service description confirmed revision `polititrack-web-00055-ktr`
still uses accepted image
`sha256:6be7d1e5236746d02d872303fa6192c29a824d0f55178df33a51c343eb0f18de`.
The source PR is still open, and no production image, schedule, database, upload,
account, acknowledgement, snapshot, alert or OCR receipt was changed.

Cloud Shell was started through the normal Google CLI. SSH using the existing
local key stopped at an uncached host-key confirmation, which batch mode refused.
No key was accepted and no remote command executed. The CLI's three automatic
attempts ended with exit 1. Do not suppress this check or blindly trust a key
seen on the network. Ask the owner to obtain the public ED25519 fingerprint
inside the trusted Google Cloud Console Cloud Shell with
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`, then compare it before pinning
the connection. The September 19 release remains the deployed authority; its
immutable journals must stay closed. Current private heads, release ownership,
schedules and retry outcomes have not yet been revalidated in this continuation.

After reconnecting the existing authenticated deployment environment:

1. Verify exact-head CI (real PostgreSQL/browser checks), live release ownership,
   image/source/configuration, current immutable heads and original schedules.
2. Prepare a reviewed successor bound to the accepted September 19 release,
   retaining its complete sealed journal/receipt chain; do not replay it.
3. Build the tested immutable application source, preserve the original runtime
   controls and use the normal fresh baseline, pause/drain, activation and
   independent acceptance. No database migration is needed for this source repair.
4. Observe the existing source writers append real retry outcomes; verify the
   original retry receipts and document histories remain intact. Recovered
   extraction may legitimately end in review rather than automatic import.
5. Verify published OCR metrics against committed evidence, preserved account/
   acknowledgement/outbox/snapshot history and natural scheduled successors.
   Restore original schedules; keep Vault paused and Current Opportunity off.

Keep #203 open until live recovery is verified. The original uploaded House
document and separate owner correction/import acceptance in #182 are unchanged.
