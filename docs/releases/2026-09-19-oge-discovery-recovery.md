# OGE discovery recovery — issue #182

## Observed failure

The original Executive schedule ran `polititrack-executive-5qpd5` at
2026-09-19T11:41:00.952580Z. Its production run
`d32ffb7b-1e2a-452a-96eb-56d8fe93f438` failed at
11:46:09.848413Z while waiting 120,000 ms for OGE's rendered table.
OCR remained at `waiting_for_collection`, then `skipped`, with zero document
attempts. No replacement Executive snapshot was accepted from this failure.

The public collection's HTML returned HTTP 200 in 0.2 seconds from the existing
authenticated Cloud Shell. Its published page configuration uses server-side
DataTables and the official data service
`https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v2/rest`.
A read-only request with the table's normal first-page parameters timed out
after 45.13 seconds. The connected browser also retained its Loading row after
one reload and the ordinary 278-T search. There was no site-served bot challenge
or access-denial evidence. These observations establish unavailable table data
from the tested clients, not the cause inside OGE's infrastructure.

## Collector repair

The existing collector now retries initial loading once on a timeout, retaining
diagnostics for both attempts. It does not retry unknown acknowledgement or
source-validation failures. Failed official-host requests log the host, path,
resource type and network error without queries, credentials, headers or bodies.

OGE's server-side search and each page must complete the requested DataTables
draw, search term and offset before parsing. Fixed search sleeps and accepting
unchanged pages after a timeout are removed. Page totals and returned/rendered
row counts must agree. Repeated pages, changing totals, missing next controls,
changed headers and reaching the page limit before the end fail the whole
discovery; an accumulated prefix cannot be published as a complete collection.

The existing parser, ID calculation, direct-PDF classification and PDF validation
remain intact. There is no cached-source fallback, new writer, snapshot rewind,
history edit, schedule change or release-gate exception.

The source branch starts at tested repair source
`db4aa4da54be845a1e139dc354d9f59aa9006d8a`, preserving that repair's deployment
scope. Current Opportunity's separate source integration is not included in this
branch's application image.

## Verification and release boundary

Local application regression suite: 320 passed, 21 environment-dependent skips.
After adding the actual JavaScript draw-correlation regression, all 41 focused
OGE tests passed. They cover old responses/searches/offsets, missing draw counters,
loading placeholders, complete and incomplete pagination, bounded timeout retry,
non-retryable source failures, log redaction, and existing filing-ID preservation.
Canonical CI and live deployment are recorded in the later acceptance entry.

This change cannot repair an unavailable OGE-hosted service. Live recovery
requires a successful complete collection through the existing Executive writer.
Keep the successful-baseline release gate and all four closed journals intact.
The four original schedules remain enabled; Vault remains paused. The previous
release journal is closed as `recovered_original_configuration`, SHA-256
`5fd6a3462881fceece2e5665606789f2454a9ecadc28232213cc97eab61ca5b8`.
A later OCR deployment requires a fresh reviewed successor, fresh successful
baseline and independent acceptance, never replay of that journal.

## Canonical acceptance and current live boundary

[PR #190](https://github.com/maglothinm/MyETF-Intelligence/pull/190) merged at
`eb228bc18f242ecc71f368d50181126a746a052a` from isolated source head
`4b3c7db19f721816495f4213e132a9953dbd4149`.
[Canonical PR CI 35441670108](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35441670108)
passed **341 Python tests, one skip, four Node tests and the isolated desktop/mobile
correction checks**. Job `105893425394` tested GitHub's PR merge
`d68c44879641cc4a152f7a2d0f49e067e6dc3aa4`; its tree
`894f7a20ce07fcad15baa0542f40bdbebd313fd1` exactly matches the accepted main merge.
[Main CI 35441765858](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35441765858)
also passed on `eb228bc18f242ecc71f368d50181126a746a052a`.
The isolated pre-Current-Opportunity head is a separate tree and is not described
as that exact CI checkout. Browser acceptance artifact `10583349622` is a test
artifact, not protected production state.

Read-only live verification at **2026-09-19T12:04:41.573331Z** confirms the six OCR
release resources still use the accepted image
`sha256:31d09bce4ee2ca7e32343f6fa84a7c354afde245f64c52b8ff6c3c48a5ba3f7d`.
All four producer source revisions remain
`a2a15edb30895ece37b690e50e0f95fb1eaa2649`; OCR is enabled on Legislative,
Executive and web. The original schedule inventory/configurations were verified
again at 12:02 UTC: four enabled, Vault paused. All four closed journal hashes
still match their recorded values, including the failed/recovered fourth attempt.
No controller is active, and this recovery session made no production-resource,
schedule, account, state or journal mutations.

**Source repair merged; live OGE recovery and deployment remain blocked.**
The latest observed Executive attempt failed, and the public collection still did
not supply data in the observed browser session. Do not relabel a prior successful
snapshot as a successful latest attempt, serve a cached collection as fresh, or
relax the successful-baseline cutover gate. Original schedules continue their
normal attempts. A future successful complete Executive run, a reviewed new
continuation preserving all four journals, exact deployment-source CI/build
verification, fresh baseline and live acceptance remain required. Issue #182
stays open. No additional general maintenance authorization is needed.
