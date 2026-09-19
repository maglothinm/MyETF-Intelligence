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
The exact failing predicate condition was subsequently isolated below.

## Polling argument defect — September 19, 15:53 UTC

Read-only admin `polititrack-admin-jjzmt` succeeded at 15:53:44 UTC and reproduced
both failure and correction on the same loaded production-image browser page:

| Input/path | Observed value/result |
| --- | --- |
| Direct evaluation, `{search: null, start: null}` | Valid complete 100-row page |
| Polling, same object | `{}`; both fields `undefined`, strict null checks false |
| Polling, `{search: "278-T", start: 0}` | Both non-null fields preserved |
| Polling, serialized JSON parsed inside predicate | Valid complete 100-row page |
| Original helper | Timeout despite matching draw 1 and total 16,670 |

The optional initial-filter comparison rejects undefined against the source's
empty search. That explains both 120-second waits in the failed Executive pass.
The correction serializes only the wait argument; no draw/count/pagination gate
is removed, no partial collection is accepted, and no timeout is extended.
Add a real Playwright regression for initial nulls and stale search/page draws.
Local focused validation: 41 passed, one missing-local-Chromium skip; canonical
CI must run that browser test. Complete live candidate collection remains pending.

PR #194 is merged at `5acc472214ec1886d6556b5051b6b9379cd5a5de`.
Tested head `77aadf541b034072f58dba5e7107c2c8e8ba4bd1`, its PR CI checkout
`d69f7a1401fb38889b0a795048a778656d5c6ec5`, and the merge all have tree
`bc9f28aa15c1fb07a8485a0be9234d8ec086017a`. Canonical
[CI 35453468818](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35453468818)
passed 354 Python tests (including the real polling regression), one unrelated
skip, four Node checks and desktop/mobile UI checks. Main CI `35453651966` also
passed. Test artifact `10587626600` (attempt 1, repository 1349678672) expires
September 22; digest `0b863bc18255cd10bee68f3aa27cf9fbedcfb3194a45dda3a0aee2b0c9ea2727`.

The exact library cause is Playwright 1.57's `_impl._page.Page.wait_for_function`
forwarding its arguments through `_helper.locals_to_params`, which recursively
removes dictionary entries whose value is `None`. Direct `evaluate` does not
use that forwarding path. The JSON scalar prevents this loss before the frame
serializes the argument; it is not a source/network retry workaround.

Complete read-only candidate `polititrack-admin-xzrsl` advanced to 5,900 of
16,670 source rows, then timed out on the next page. It accepted no incomplete
collection and wrote no production state. Instrumented reproduction
`polititrack-admin-r7svg` then passed at 16:07:54 UTC: 168 readiness checks
(initial table plus 167 data pages), all 16,670 rows, and 4,068 unique 278-T
listing IDs. The last page contained 70 rows, ending exactly at 16,670. The
earlier mid-collection timeout's internal/upstream cause remains unproven; the
second test did not reproduce it, and neither test wrote production state.

Cloud Build `adba5676-b161-4b89-8336-0edc6c22795b` succeeded at
`2026-09-19T16:08:14.952095Z`, targeting tested source
`77aadf541b034072f58dba5e7107c2c8e8ba4bd1` and producing
`us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6be7d1e5236746d02d872303fa6192c29a824d0f55178df33a51c343eb0f18de`.
This includes the PDF and Senate repairs plus the nullable-wait correction.
No additional production image change has been made.

## Independent Legislative preservation — September 19, 16:06 UTC

Read-only `polititrack-admin-c6wmp` passed at 16:06:42 UTC, comparing the original
generation 1182 ledger with current generation 1185, snapshot
`80f9d315-cb3d-4ece-9636-2f3bcd139aa9`. Both specified Senate paper filings are
now `needs_review`, with no retry timer. Their seven prior attempts, original
attempt timestamp, source URL, error code and extraction version are unchanged.
The old OCR ledger is an exact byte prefix of the current ledger. This confirms
the append-only classification correction independently of the producer summary.

The original House upload still has its exact SHA-256, two pages and five rows
awaiting owner review, with raw upload bytes cleared. Latest Legislative, AI and
Dashboard runs were successful; Executive still failed on deployed source
`df5bb5a850942ff54f6b73a4936fc9ec18d8e548`. This is partial preservation evidence,
not full release acceptance or OCR reactivation.

## Concrete source-recovery proposal; not executed

The existing OCR release controller (`ocr_release_controller.py`, both frozen
baseline checks) and decisions D-2026-09-19-003/005 require every latest production
run to succeed before cutover. Executive cannot meet that requirement while its
deployed collector drops the initial wait parameters. A diagnostic collection
is not an authoritative producer and cannot replace that failed production run.
The new image is built and verified, but the ordinary OCR cutover remains blocked.

Proposed one-time incident recovery, requiring specific owner approval of this
exception before execution:

1. Seal the five closed journals and save a new incident receipt. Pause and drain
   the four existing schedules under the original controller lock. Audit current
   snapshot hashes/chains, prior history, accounts, reviews, upload and outbox.
   Preserve the latest Executive failure as the incident baseline; do not relabel
   it successful or substitute an older run. Reject any unrelated failure or
   configuration/state mismatch.
2. Change only the existing `polititrack-executive` job to the built digest above,
   with `SOURCE_REVISION=77aadf541b034072f58dba5e7107c2c8e8ba4bd1` and OCR still
   disabled. Use its existing canonical command, service account, configuration,
   writer lock, validated restore and atomic commit path. No new writer, schedule,
   permission, data import, blank state or journal reopening is permitted.
3. Execute one complete authoritative Executive recovery run and independently
   verify its exact source/image, successful snapshot successor, complete source
   collection and preservation against the incident receipt. An ambiguous
   submission is observed, never resubmitted. A failure cannot certify recovery;
   retain every record and keep OCR disabled during bounded restoration.
4. After genuine Executive recovery, use a new reviewed OCR continuation with a
   fresh successful frozen baseline and the unchanged full acceptance checks.
   Restore original schedules; keep Vault paused and Current Opportunity off.

The requested exception is limited to installing the proven collector correction
on the failed Executive component while OCR is off. It does not waive snapshot
validity, preservation or subsequent OCR activation/acceptance. General deployment
authorization has not been treated as authorization to override this recorded
successful-baseline rule.

## Owner-approved recovery implementation

The owner subsequently approved: "I approve a one-time Executive-only repair with
OCR disabled, followed by the normal activation and acceptance checks."
`scripts/ocr_executive_recovery_release.py` implements that exact scope with the
unchanged pinned controller, preparation and audit. Its first phase records a
fresh incident baseline, verifies only the reviewed Executive failure is present,
changes only Executive with OCR off, runs its canonical producer and audits the
successful successor and unchanged OCR evidence. Other namespace heads must not
advance during this phase. All original schedules are restored after verification.

Its separate `--activation --incident-sha SHA256` phase requires the completed
incident's exact journal hash, approval marker, original preservation receipt and
genuine successful Executive successor. It seals all six earlier attempts before
fresh normal preparation. The original full release `run` and audit remain
unchanged, including both successful-latest-run checks and full OCR acceptance.
The actual action still requires source CI, pinned procedure installation and
fresh live verification; this entry records implementation, not completion.
