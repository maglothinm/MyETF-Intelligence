# Live OCR and state continuity follow-up — September 20, 2026

**The accepted repair remains deployed and live OCR is progressing. Both fresh
read-only audits passed.** All 15 original House technical retries are resolved
to `needs_review`; review/import approval is still required. Two OGE document
downloads remain in retry and both official PDF URLs return HTTP 404. Public
readiness and filings intermittently returned 503 and then recovered to 200.
This is not an all-green availability certification.

## Deployment and verification scope

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Evidence branch `codex/ocr-live-continuity-20260920`, based on main
`6c9edb5b5759050764985a1f5c0d7bea355588b7` (PR #206).
At **19:13:19 UTC**, all six normalized resource configurations matched the
accepted release. Application source remains
`aba0285689d649d94e3e11444b582c748927bbc4`, image digest
`sha256:f0fc0a54029094043448da348f5e2c04889b1f4863d11fd35ee68ee9999c4c84`.
Web revision `polititrack-web-00057-8m5` is ready and receives 100% traffic.
The deployment already completed at 13:55:37 UTC; no redeployment was necessary.

All four original schedules are enabled with unchanged specifications. AI uses
`America/New_York`; the other active schedules use `Etc/UTC`. Vault remains paused
and Current Opportunity off. No source producer or dashboard was manually
dispatched during this follow-up, and no schedule or production state was changed.

## Fresh continuity evidence

One read-only admin execution, **`polititrack-admin-zgs5z`**, completed successfully
at **19:22:27 UTC**. The unchanged full continuity audit ran before the unchanged
OCR-specific verifier; a failure in the first stops the second. The full audit
compared against accepted execution `polititrack-admin-65ggm`, while OCR retry
outcomes were compared against original frozen baseline `polititrack-admin-2pvks`.
No baseline was manufactured and no closed deployment journal was resumed.

At **19:22:17 UTC**, the audit verified these immutable heads and all their files:

| Namespace | Generation | Snapshot ID | Successful producer run ID |
|---|---:|---|---|
| ai | 727 | `ce2ec215-954f-4043-bff7-2c0cca5fec39` | `d7f96773-f350-40a8-b568-410b154552af` |
| dashboard | 1386 | `0d1c65de-edd7-4977-83e7-0bcf6bc855cc` | `df9d4b58-832e-430c-989d-dea84d5d99ee` |
| executive | 659 | `9c431f2d-8002-4b37-90b1-6314d1406b28` | `0dd051da-a82a-44fc-bae4-620906f9be12` |
| legislative | 1286 | `363d7789-a6e1-42c0-8a0a-c11fa8bbe5f9` | `76f59715-2386-45a9-af9e-8d41c4bfb3c7` |

Snapshot hashes and parent-history hashes are in the [JSON receipt](2026-09-20-ocr-live-continuity.json).
All ledger prefixes, durable keys, prior files, account identities, nine
acknowledgements and ten review events are retained. Completed run history contains
4,125 rows; prior rows are unchanged. Notification/outbox history is retained.
Both latest source runs, AI and Dashboard were successful at the audit observation.

The OCR verifier retained all prior receipt bytes and **481 prior extraction
files** (355 Legislative, 126 Executive). It found **163 new extraction files**
(112 Legislative, 51 Executive) since the original baseline. All 15 original House
retries were actually attempted and resolved; two of three original Executive
retries resolved. Current technical retry totals are House zero, Executive two.
The additional Executive retry is DeVos, discovered after the baseline.

The original owner upload remains `needs_review`, two pages, five review rows,
and raw payload NULL. The fresh public ledger retains all **5,152** filing keys
and every prior first-observation timestamp. No pending row was auto-approved.

At **19:25:03 UTC**, all **512** sealed files in the accepted workspace and all
**2,689** predecessor files still matched their hashes. The release lock was free.
Closed journal SHA-256 remains
`9980523ad75ce1f4993967cbc4dce8c296e486b0d21ffc0e7db745a02e94ddcd`.
Private baseline/account rows remain only in the existing private audit workspace.

## Actual scheduled OCR

Published Legislative run `76f59715-2386-45a9-af9e-8d41c4bfb3c7` succeeded at
**19:09:04 UTC**, completing five documents and **9/9 pages**, with no technical
retries. The final originally blocked 20-page House document, 9115679, was processed
live at 14:38:53 UTC and now requires review; it is no longer waiting for retry.

Executive `polititrack-executive-xxm2l` failed at 18:45 UTC before OCR because the
OGE rendered listings table exceeded its 120-second wait. This was not a partial
OCR state commit. The next original scheduled execution,
**`polititrack-executive-h5qwl`**, recovered without intervention: it discovered
4,065 listings and succeeded at **19:16:33 UTC**, generation 659, completing
four documents and **17/17 pages** from five attempts. Intake was OK, cleanup
not needed, and no transaction was appended. The retained source-download failure
is reported rather than counted as a completed document.

The official 2020 DeVos and MacGregor PDF URLs both returned **HTTP 404** in the
19:22 UTC source checks. Exact URLs, filing keys, last attempts and backoff
timestamps are preserved in the JSON receipt. Why those files are unavailable is
unknown. Their retry warnings must remain visible.

## Public availability and publication timing

At 19:22 UTC, root and dashboard insights returned 200, while readiness and filings
returned 503. Cloud Run request logs confirm the two 503s at **19:22:20 UTC**,
each about 0.041 seconds. Sequential readiness and filings rechecks started at
19:22:51 and 19:22:59 UTC and both returned 200. Readiness served snapshot hash
`1afdbfde207a3abfbac4e5412ba7fe00da1e18a739f3ad23554f2d2008e423d4`, matching the
audited Dashboard generation 1386. This reproduces the earlier isolated 503 and
must remain an open availability finding.

Code inspection shows web refresh takes the dashboard writer lock and fails
immediately on contention; routes suppress the exception detail. Concurrent
refreshes or a publisher are a plausible cause, **not proven by these logs**.
Next safe web action is a focused contention reproduction and non-sensitive error
diagnostic before a separately reviewed fix. Do not mask verification failures.

The 19:17:58 publication contains successful OCR health for both sources but
captures AI while running, leaving overall published health `failure`. The audit
proves that same AI run succeeded at 19:18:13; Dashboard completed at 19:18:42.
The report preserves this publication timing difference instead of rewriting the
public health result.

## Checks and remaining work

Previously accepted source CI [35510840684](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35510840684)
and controller CI [35512024741](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35512024741)
were rechecked and remain successful. No application source changed in this
follow-up. Verification consists of live configuration reads, completed read-only
audits, source HTTP checks, public snapshot/ledger comparison and receipt checks.

Keep #203 open for the two unavailable OGE documents and intermittent web 503s.
Continue original bounded source schedules. Keep #182 for separate owner
correction/import acceptance; Current Opportunity #197 remains off and Vault
paused. No rebaseline, receipt reset, upload resubmission or closed-journal replay.
The [earlier release record](2026-09-20-ocr-page-retry-repair.md) and
[original acceptance receipt](2026-09-20-ocr-page-retry-acceptance.json) remain unchanged.
