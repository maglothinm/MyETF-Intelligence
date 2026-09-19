# Legislative OCR and Executive zero-transaction diagnosis

Issue #182; canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
This is a read-only production investigation on September 19, 2026, using the
authenticated upload dialog, live Operations, public published ledgers and
bounded downloads of official documents. No application repair or deployment is
claimed. The inspected source files at documentation base `148ac7c` match deployed
application source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`.

## Observed inventory

The [published dashboard evidence](https://polititrack-web-s6icmprjvq-uc.a.run.app/data/dashboard-insights.json)
was generated at **2026-09-19T07:47:56Z**. The accompanying
[filings ledger](https://polititrack-web-s6icmprjvq-uc.a.run.app/data/filings.json)
contained these counts; scheduled publication can subsequently advance them.

| Measure | Legislative | Executive |
|---|---:|---:|
| Retained filings | 1,011 | 4,133 |
| Collector-processed filings | 882 | 0 |
| Retained transactions | 12,247 | 0 |
| OCR needs review | 220 | 0 |
| OCR access required | 0 | 36 |
| OCR retry delayed | 2 | 0 |
| No OCR receipt yet | 789 | 4,097 |

Latest published successful producer run IDs were
`legislative:66190826-8b5b-4d1a-bbd2-5d8d215bcec7` (finished 07:40:11Z) and
`executive:743af343-8120-4ebf-8aab-8673ea4aaf7e` (finished 07:45:51Z).
Each attempted five documents, completed zero new extractions and appended zero
OCR transactions. Legislative OCR remained degraded; Executive's successful
maintenance status does not establish successful document extraction.

## Legislative: extraction/review works, broad acceptance does not

The accepted upload for `house|house:2026:9116331`, created at
`2026-09-19T01:19:38.83546Z`, now displays **needs review** and
`upload_confirmation_required`. The authenticated review form contains all five
physical rows across both pages (four on page 1, one on page 2). Transaction types,
dates and amount ranges are populated; ownership remains blank. Three asset labels
remain flagged for document-specific review. No corrections or confirmations were
submitted, and the PDF was not uploaded again.

The filing receipt records the upload attempt at `2026-09-19T01:23:34.479670Z` and
retains the original extraction timestamp `2026-09-18T19:32:25.482961Z`. This is
consistent with reuse of preserved same-digest evidence, rather than a fourth new
extraction. The upload-to-review path is verified; correction/import acceptance is
still outstanding. `SourceUploadStore.acknowledge()` clears the raw payload in the
same database update that publishes this evidence-backed review status after the
canonical snapshot commit. Thus cleanup is supported by the observed status and
code path, but an independent database check was not available: Beast was offline.

Of 220 OCR review cases, **217 have `invalid_or_encrypted_pdf`**; the remaining
three are the sample's confirmation requirement, one `unsupported_scanned_layout`
and one `table_needs_review`. Two Senate image-viewer filings separately remain
`PaperFilingError` retries.

Two representative rejected House PDFs, `house:2025:20029105` and
`house:2025:20030307`, returned HTTP 200, opened with pdfplumber's default empty
password and exposed readable native text. Both contain an encryption dictionary.
The deployed `scripts/source_ocr.py:inspect_document()` rejects any such dictionary,
and reproduced `invalid_or_encrypted_pdf` on both unchanged downloads. The first
page also rendered normally in Poppler. This confirms overbroad rejection for the
sampled documents; it does not prove the same internal cause for every one of 217.
Of those 217, **215 already have collector status processed** and two are cataloged.
The OCR warnings therefore do not imply loss of 217 previously parsed filings.

The Operations "last document OCR completed" field is unavailable because its
recent run timeline has no new extraction timestamp. It is not proof that the
three retained extractions or the sample preview are absent.

## Executive: direct PDFs are incorrectly classified as request-only

Executive has **4,133 cataloged/retained filings, not zero filings**. The zero is
processed filings and transactions. All 4,133 records have `access_mode=request`:
3,793 source URLs are request-form links, while **340 source URLs end in `.pdf`**.
The Operations access/request count of 1,525 is from the pending-review population;
the OCR count of 36 is from attempted OCR receipts. Neither is the complete
inventory count, and neither validates access restrictions for every document.

Confirmed code path:

1. `scripts/oge_disclosures.py:_classify_links()` tests for `extapps2.oge.gov`
   before checking for PDF/download links, classifying even direct official PDF
   links as request-only. A local call with a real PDF URL and "Download PDF"
   anchor text reproduced that result.
2. `resolve_oge_pdf()` returns `None` immediately for `access_mode=request`.
3. `runtime_v2/source_ocr_worker.py:download()` likewise raises `access_required`
   for non-direct OGE records before issuing a document request.

Two affected records were independently downloaded without authentication or a
Form 201 submission:

| Filing ID | HTTP / document verification | Native parser reproduction |
|---|---|---:|
| `oge:c7aa20fb7288756065000dbbacfa2d07` | 200, PDF, 5,451 bytes, 3 pages, no encryption dictionary | 5 candidate transactions |
| `oge:14d1310fe8a29827f7dcf22a5d264cd5` | 200, PDF, 9,786 bytes, 5 pages, no encryption dictionary | 37 candidate transactions |

Both passed the deployed document inspection function. The first page of the
first document also rendered as an OGE 278-T form. Native parser outputs are
diagnostic candidates only: row completeness/accuracy, OCR agreement and live
import were not accepted or written. A third PDF link,
`oge:981cab70ca237b807917ef53173c8aa2`, returned HTTP 200/PDF but exceeded the
20 MiB bounded diagnostic read; its full contents/hash were not verified.
Correcting classification will not guarantee that every PDF satisfies size,
page, parsing or review requirements. Real request-form links remain gated.

## Next repairs and acceptance

- Correct OGE direct-document classification and refresh affected retained
  metadata through the canonical producer. Preserve existing filing IDs:
  `_stable_listing_id()` currently hashes both document and request URL slots,
  so merely moving a URL between them would create duplicate identities.
- Refine PDF inspection to distinguish documents readable without a supplied
  password from genuinely password-protected/invalid files while preserving
  byte, page, pixel, timeout and process bounds; retain all rejected history.
- Validate representative documents through parsing and a preserved-state live
  successor before claiming Executive transaction recovery or healthy OCR.
- Finish independent upload cleanup verification and owner review of the three
  unclear sample labels, then verify correction/import reconciliation. Resolve
  the two Senate image-viewer cases separately.

No new workflow was dispatched, no production state was written, and no schedules,
Filing Vault settings, account data or sealed deployment journals were changed by
this investigation. The last verified configuration remains four enabled original
schedules and Filing Vault paused. No fresh database/artifact continuity audit was
performed. Issue #182 stays open; no new design decision or release is asserted.
