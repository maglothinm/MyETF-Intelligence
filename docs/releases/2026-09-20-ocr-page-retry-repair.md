# OCR page completion and overdue retries - issue #203

Status: deployed with remaining OCR warnings; normal and OCR-specific audits, natural scheduling and published-metric verification passed.
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

## Historical connection boundary before release

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

## Verified reconnection and release preparation (completed checkpoint)

The owner independently supplied Cloud Shell's public ED25519 fingerprint
`SHA256:owVHUvlU3NLcXIoKVQESUl/C3z8/kvzvuzfcMiwjuLM`. Pinning that exact key
restored SSH using the existing local private key; no key or IAM change occurred.
The earlier connection-blocker narrative is retained as history.

Final PR #204 head `a430ed1658efad0ca430a04a657b88f0d9b41ca0` passed OCR
`35510840684`, Runtime safety `35510840687`, and Current Opportunity offline
`35510840685`. Merge `aba0285689d649d94e3e11444b582c748927bbc4` has the identical
tested tree `1ed514667bbd40aed9413427c129192e4ad2590e` and is the pinned image source.
Build `7e079133-a433-4d1d-beba-e32bfd2bce83` was submitted at 12:50:17 UTC.
An earlier local CLI argument rejection submitted no build; an explicit empty
build inventory was verified before the corrected submission.

Read-only checks verified all six resources against their accepted configuration,
the four enabled original schedules, paused Vault, free controller lock, accepted
September 19 journal hash and all 2,096 preceding sealed files. A fresh wrapper
extends the seal to the eighth accepted release, preserving its full records.
It selects workspace `ocr-page-retry-aba0285689d6` under the original release root
and reuses the unchanged normal lifecycle and read-only audit. Current Opportunity
stays off. The existing additive schema initialization remains idempotent; this
application repair introduces no schema change.

Local controller and independent-verifier suite: **172 passed**. The verifier
requires unchanged old OCR ledger bytes and extraction evidence, actual due-retry
attempt progress, correct source/snapshot identity, and preservation of the
original owner upload. It reports remaining technical retries separately from
progress; a PASS does not mean that all documents are approved or every failure
has cleared. Procedure CI, completed build, fresh baseline and live acceptance
remain prerequisites; no production resource or state mutation is claimed yet.

## Production execution — September 20

PR #205 merged the separately reviewed release procedure at
`0befd4a60978cb15f4b65f2170870461170df85a`. Its exact head
`c59e16786e38036edc2f3a42d2a92e8643b9f03a` passed controller CI
[35512024741](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35512024741)
with 172 checks. Source merge OCR CI
[35511460884](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35511460884)
also passed. Build `7e079133-a433-4d1d-beba-e32bfd2bce83` completed successfully
at 12:56:42 UTC, producing image digest
`sha256:f0fc0a54029094043448da348f5e2c04889b1f4863d11fd35ee68ee9999c4c84`
from application source `aba0285689d649d94e3e11444b582c748927bbc4`.

Fresh frozen baseline `polititrack-admin-2pvks`, observed at 13:04:19 UTC,
passed with successful latest producers and verified immutable snapshots.
Generations were Legislative 1263, Executive 647, AI 715 and Dashboard 1362.
Idempotent schema compatibility `polititrack-admin-vzpfb` and image smoke
`polititrack-admin-f9cs9` passed. All six existing resources received the pinned
image, with OCR enabled on Legislative, Executive and web.

| Controlled pass | Execution | Generation | Completed documents | Pages | Remaining technical retries |
|---|---|---:|---:|---:|---:|
| Legislative 1 | `polititrack-legislative-xlsgn` | 1264 | 5 | 36/36 | 10 |
| Executive 1 | `polititrack-executive-xr8kv` | 648 | 4 | 18/18 | 1 |
| Legislative 2 | `polititrack-legislative-2nmjr` | 1265 | 4 | 46/46 | 6 |
| Executive 2 | `polititrack-executive-sf8h8` | 649 | 5 | 15/15 | 1 |

The four passes completed 18 documents and 115/115 pages from 19 attempts.
All 18 completed extractions required human review; no transaction was appended.
The second Legislative pass stopped within its existing batch time budget after
four large documents. Budgets were not increased to drain the queue.

One execution-status read returned `ACCESS_TOKEN_TYPE_UNSUPPORTED`; the existing
reviewed bounded read retry recovered without another producer submission.
Later SSH transport dropped after AI submission. Read-only checks confirmed the
controller process was gone, its lock was free, its journal had no failure, and
AI execution `polititrack-ai-22zcw` had succeeded at 13:38:07 UTC. The same open
journal resumed in a detached session, re-observing the recorded executions.
The transport interruption did not authorize replaying any closed journal or
changing an acceptance gate. The new dashboard execution is
`polititrack-dashboard-ng95b`.

Normal independent preservation `polititrack-admin-65ggm` passed. The release
finished at **13:55:37 UTC** with all four original schedules enabled, unchanged
configurations, Vault paused and Current Opportunity off. The live asset hashes
matched the accepted dashboard snapshot, and the enabled OCR API retained its
sign-in requirement. All 2,689 files in the eight sealed predecessor attempts
still match. Final release journal SHA-256:
`9980523ad75ce1f4993967cbc4dce8c296e486b0d21ffc0e7db745a02e94ddcd`.

Accepted generations: Legislative 1265, Executive 649, AI 716 and Dashboard 1363.
Prior snapshot metadata, ledger prefixes, filing/trade/review identities, account
inventory, acknowledgements, paper/analysis history and notification history
passed preservation. Exact snapshot IDs, payload hashes and producer run IDs are
recorded in [the acceptance receipt](2026-09-20-ocr-page-retry-acceptance.json).
This is `DEPLOYED_WITH_OCR_WARNINGS`: processing succeeded while retained retries
remain honestly visible. No state reset, automatic review approval or new schedule
was used.

Independent OCR audit `polititrack-admin-n2fdz` passed at **13:58:54 UTC**.
Against this release's frozen baseline it verified every prior OCR ledger byte
and all 481 prior extraction files (355 Legislative, 126 Executive). Each branch
added nine extraction files. Nine of 15 House retries and two of three Executive
retries were resolved; all three Executive cases had actually been retried.
Six House retries remained unattempted, and one Executive retry remained.

The original owner upload is unchanged: two pages, five review rows,
`needs_review`, raw payload NULL. No resubmission or approval occurred. The
remaining OGE retry is `oge|oge:29228ca69c134b357487711903d725be`, Katharine
MacGregor's 2020 PDF. Its official PDF and parent record returned HTTP 404 in
direct checks. Why the source is unavailable is not established. Its receipts
and bounded retry policy remain intact.

A proposed optional ordinary Legislative follow-up did not submit a job: the
full execution-inventory prerequisite timed out after 90 seconds, before its
intent or dispatch. The absence of that intent and the unchanged completed
release journal were verified. Work remains with the original schedules; an
incomplete inventory is not treated as proof that a writer is idle.

## Natural scheduled operation

The original scheduler created `polititrack-legislative-wl5tn` at
**14:05:00.881741 UTC** with the expected scheduler service account, pinned
image/source, canonical arguments and OCR enabled. It succeeded at
**14:10:39 UTC** and committed generation **1266**, snapshot SHA-256
`ddb95149b6ce8cbcba22ba7e0e353a43c0a895fb5304b3db767033de71eb6f42`.
This was a genuine new source commit, not a manual dispatch or skipped writer.

The bounded batch attempted four documents, completed three and **40/40 pages**,
and left **three** technical House retries. Intake succeeded, cleanup was not
needed and no transaction was appended. Its OCR duration was 180.229 seconds,
with one delayed retry during this batch. Combined with the controlled work,
21 documents and 155 pages completed. Retained review requirements and remaining
technical warnings are not converted into approval or hidden success.

One ordinary dashboard refresh, `polititrack-dashboard-tdnzh`, was then submitted
to publish this scheduled result. The existing checksum-pinned, fields-only
read path inspected all 1,073 dashboard executions and confirmed none active or
unconfirmed before submission. The completed release journal is unchanged;
original schedules and production limits are unchanged. The initial slow full
CLI inventory was not used as an idle assertion.


## Published outcome and remaining work

The follow-up dashboard succeeded at **14:15:53 UTC**, generation **1365**, snapshot
SHA-256 `92be19653163dacc8a29a004b426a844e6c0efc38b15dcdf6874b3f3acd5ce0e`.
Its public snapshot was generated at **14:15:05 UTC**. The 14:17:32 UTC check found
HTTP 200 for root, readiness, insights and filings; the Legislative heartbeat,
40 pages and three retries matched the genuine scheduled result. All 5,152 prior
filing IDs remain. The public Executive heartbeat also advanced to 14:14:45 UTC,
with four more documents, 15/15 pages and one retained retry; that public evidence
is recorded separately from the four controlled passes and the explicitly audited
Legislative execution.

Four of the original 18 technical retries remain in that published snapshot:

| Filing | Latest retained result | Next safe action |
|---|---|---|
| House 20034351 | Prior `incomplete_page_ocr`; not yet retried in production | Original bounded schedule; the earlier local repair check completed 3/3 pages |
| House 9115684 | Prior `incomplete_page_ocr`; not yet retried | Original bounded schedule |
| House 9115679 | `pdf_render_failed` at 14:10:07 UTC; retry due 14:30:34 UTC | Preserve backoff; allow an ordinary eligible retry |
| MacGregor OGE 2020 PDF | `MonitorError`; official PDF/parent HTTP 404 | Preserve source warning and retries; do not substitute an unverified document |

The actual 9115679 source PDF, SHA-256
`cacef2564e9c121c8cc9916060b6dffd592bea668c4e308fb066769c598d0bb2`, completed
**20/20 pages** locally with no no-text pages in **36.317 seconds**, using the
normal full 120-second document allowance. Its production attempt began near
the end of the 180-second batch and lasted about 27 seconds. This is consistent
with the remaining-time limit; the generic retained error does not separately
prove the renderer's internal cause. The successful local diagnostic does not
advance or clear the pending production receipt.

An initial public verification received one HTTP 503. Cloud request logs identify
`/data/dashboard-insights.json` at 14:16:42.378909 UTC (0.596 seconds). The subsequent
four endpoint checks all returned 200. Its internal cause is unestablished; no
configuration change, hidden warning or zero-error availability claim followed.
Monitor a recurrence as a separate availability symptom.

Keep #203 open for remaining live retry outcomes; #182's owner correction/import
acceptance remains separate. All scheduled processing, account/review protections,
backoff, sole-writer rules and feature flags remain in place. No controller or
release gate remains open. Continue ordinary scheduled work; never replay the
completed release journal or reset the retry ledger to improve displayed health.
