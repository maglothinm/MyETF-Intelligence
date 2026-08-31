# 30-Day Filing Vault

Work record: [issue #13](https://github.com/maglothinm/MyETF-Intelligence/issues/13).
The implementation is prepared for authorized publication in PR #16. Database
migration, private bucket configuration and an operating daily timer require the application runtime
described below. Publishing static Pages alone cannot provide document caching.

## Architecture and storage

The existing generated dashboard remains the presentation layer. Its shared
`View Filing` / `Official Source` actions open `filing-vault.html`, which uses the
existing design system and a responsive full-page document viewer. Root Records,
transactions, reviews, signals/analyses, paper positions, $10K results, Wallboard
and Investor Edge trade detail use this route. Browser notifications continue to
open their existing evidence surface, where the filing actions are available.

`backend/filing_vault` extends the repository's Flask, SQLAlchemy/PostgreSQL and
Supabase conventions without importing its legacy eager database connection.
`create_vault_app()` is an independently deployable Flask application;
`init_app(app)` registers the same blueprint on the existing API when
`VAULT_ENABLED=true`.
No second tracker, analysis ledger or production artifact authority is created.

The six additive tables are `vault_filings`, `vault_filing_documents`,
`vault_filing_versions`, `vault_filing_source_metadata`,
`vault_filing_acknowledgements` and `vault_catalog_checkpoints`.
They separate identity, source snapshots, retrieval events and immutable objects.
Run the explicit `init-db` migration; application startup does not initialize
production tracker state. Existing SQLAlchemy tracker tables are unchanged.
On PostgreSQL, this migration creates and secures the six Vault tables in one
transaction: row-level security is enabled without browser policies, and table
privileges are revoked from PUBLIC and any existing `anon` / `authenticated`
roles. This prevents Supabase's exposed schema from bypassing the Flask API.
Use the table owner or a dedicated server-only role with suitable grants and
BYPASSRLS; never use browser database credentials. A failed security step rolls
back the migration. Unrelated tables and role defaults remain unchanged.

Production documents reside in a **private Supabase Storage bucket** in the
existing application project. The adapter verifies bucket privacy and refuses a
public bucket. It does not create buckets or change permissions. Keys follow
`filings/{source}/{opaque-filer-id}/{opaque-filing-id}/{sha256}.pdf` (or `.html`).
Hashes make unsafe IDs and filenames unsuitable for traversal; object keys never
appear in public API metadata. SQL records retain exact filing IDs and URLs.
Explicit development/test filesystem storage is supported only outside **all**
Git checkouts. Never commit source PDFs, put them in Pages, upload them to Actions
artifacts, or reuse any protected tracker artifact for this cache.

## Identity, catalog import and provenance

The generator exports `data/filing-resources.json`: schema version, canonical
repository ID, generation time and existing filing metadata. `filing_id` retains
the original `filing_key`; no tracker ID is changed. Transactions resolve only to
one consistent retained filing using exact IDs/source/report/URL evidence.
Contradictory or ambiguous records never select another filing. Failed resolution
remains explicit across compact dashboard projections; original keys and URLs stay
visible, but View Filing cannot fall back to a conflicting retained ID. The API accepts
registered IDs only; there is no public URL-fetch or document-upload endpoint.

Import is a trusted server administration operation:

```sh
python -m backend.filing_vault init-db
python -m backend.filing_vault import-catalog /srv/polititrack/catalog/filing-resources.json
```

Supply the catalog from the existing canonical publisher's verified output, after
its protected-input provenance validation. A JSON `repository_id` field is a
format check, not cryptographic proof of origin. Do not accept user uploads or
unverified copies as administrative catalog input. Import never downloads reports
or mutates Legislative, Executive, AI or simulation data. Missing source filer
identifiers remain unavailable; names are not treated as proof of identity.

Each retrieval preserves the official URL, actual request/document URL, response
metadata, unmodified bytes, SHA-256, MIME type, byte count, retrieval/expiry times
and version snapshot. OCR, extraction and analysis are separate from raw evidence.
HTML is downloaded unchanged but displayed as a separate text projection. Its
scripts, forms and embedded resources never run inside the application.

## Retention and versions

Expiry is exactly **2,592,000 seconds (30 × 24 hours)** after a successful document
retrieval. Cache hits require an existing object, matching size/hash, a strictly
future expiry and a filing still eligible to be current. Missing/corrupt/expired
objects require authoritative retrieval. Expired bytes are never served merely
because the source is unavailable.

Refresh Source contacts the exact official endpoint and compares content, even
when the URL and HTTP headers are unchanged. If valid cached bytes are unchanged,
their object, `retrieved_at` and `expires_at` remain unchanged; only validation
evidence advances. Changed bytes create a new version. Retrieval after expiration
creates a fresh retrieval/expiry record even if the content hash is identical.
Historical version metadata is retained after physical objects expire.

Explicit source amendment/supersession relationships are linked in both directions.
Superseded, withdrawn or invalid filings are not served as current. The UI shows
Current, Amended, Superseded, Archived or Not cached as applicable. Similar names,
dates and tickers do not justify linking different filings. Separately published
amendments must arrive through the trusted ingestion catalog with their exact
relationship; a document HEAD response alone cannot discover them. The adapters
record `validation_scope` to distinguish endpoint headers from full content checks.
This implementation does not claim exhaustive automatic amendment discovery from
government search catalogs that do not publish a reliable relationship.

On a transient source outage, a still-valid, hash-verified cached copy can be
shown with its retrieval timestamp and an explicit warning. A changed endpoint,
identity mismatch, withdrawal, access denial or security rejection cannot trigger
that fallback. The viewer retains Official Source and a useful Retry state.

## Source adapters and access classes

| Provider | Supported retrieval | Boundary |
|---|---|---|
| House | Known official PTR/financial-report PDF paths | Preserves report year/document ID; rejects mismatched IDs and substituted redirects |
| Senate | Known eFD report endpoints using the existing validated Senate session; PDF or HTML | Separate truthful operator source acknowledgement required; no browser automation or access-page caching |
| OGE | Explicit direct PDF resources on approved OGE hosts | Request-only resources remain `REQUEST_REQUIRED` / `OGE_FORM_201`; no manufactured submissions |
| Executive agency | Direct PDF or configured structured endpoint returning PDF on explicitly approved `.gov` hosts | Agency pages without a known direct document remain unavailable; request-required records remain request-required |

Each record has `access_class`: `DIRECT_PUBLIC`, `ACKNOWLEDGEMENT_REQUIRED`,
`REQUEST_REQUIRED`, or `UNAVAILABLE`, plus its source-specific access method.
OGE distinguishes directly downloadable senior-official reports from reports
requiring requests; the application does not reinterpret a request listing as a
download permission. See [OGE's disclosure request page](https://extapps2.oge.gov/201/Presiden.nsf/201%20Request)
and [OGE's description of request-only inventory](https://www.oge.gov/web/oge.nsf/Resources/Increased%2BVisibility%2Binto%2Bthe%2BReports%2BAvailable%2Bfrom%2BOGE%2Bby%2BRequest).
House access is described on the [official financial disclosure page](https://disclosures-clerk.house.gov/FinancialDisclosure).

The technical acknowledgement and access boundaries are not a legal opinion or
permission for otherwise restricted uses. Raw retrieval is isolated from AI,
commercial research and investment functionality. No AI or market service is
called by the Vault.

## Acknowledgements and API

Before document access, the viewer displays the versioned Federal Financial
Disclosure Notice. Acceptance records a hashed random session identifier,
timestamp, notice version and source-policy version. A signed opaque receipt is
kept on that browser for up to 30 days; ordinary cached openings do not repeatedly
interrupt it. No account name, address or requester information is collected.
If browser storage is unavailable, the receipt lasts only for the current page.
No acceptance is inferred from visiting a page. Government acknowledgements and
OGE/agency forms remain separate.

| Method / route | Result |
|---|---|
| `GET /api/filings` | Filtered, sorted inventory; `limit`/`offset` pagination |
| `GET /api/filings/{id}` | Metadata, status, provenance and version history |
| `GET /api/filings/{id}/document` | Original bytes after acknowledgement and integrity validation |
| `POST /api/filings/{id}/refresh` | Deliberate source check, content comparison and version update |
| `GET /api/filings/{id}/official-source` | Exact stored authoritative URL |
| `GET /api/filing-acknowledgements` | Current notice and receipt status |
| `POST /api/filing-acknowledgements` | Record explicit acceptance and return signed receipt |

Encode IDs as URL components; existing Senate IDs containing URLs remain valid.
The browser sends the receipt as an Authorization bearer header, never a URL or
ambient cookie. POSTs require JSON and a permitted Origin. Cross-origin requests
use an exact CORS origin allowlist. Responses use no-store/nosniff and restrictive
CSP headers. PDF.js renders pages locally on responsive canvases with cancellable,
bounded lazy loading. PDF scripting, XFA and annotation actions are disabled;
original bytes remain a separate download. There is no dependency on native PDF
embedding, which can render blank in sandboxed browsers. Unsupported browsers,
protected/corrupt PDFs and documents above the viewer page limit retain an
explicit error and the original download action.

PDF.js 6.3.289 is pinned and self-hosted, including worker, fonts, CMaps and image decoders.
Its version, upstream origin, integrity manifest and licenses are under
`scripts/dashboard_assets/vendor/pdfjs/`. No public CDN, external viewer or
government request is needed to render a cached document. The restrictive CSP
permits local workers and WebAssembly decoding, but not JavaScript `unsafe-eval`.
Git attributes disable line-ending conversion for this vendor directory so its
recorded hashes survive Windows checkouts.
The legacy build targets recent browsers; Mozilla lists Safari 18+ as mostly
supported and Chrome 125+ as supported. Local Chromium viewport checks do not
establish physical iPhone/Safari acceptance. Rendering is limited to 300 pages,
32 MiB, four retained canvases and 4 megapixels per canvas; original downloads
remain available when rendering fails. PDF decoding is not a hard memory sandbox.

## Configuration and deployment

See `.env.filing-vault.example` and `requirements-vault.txt`. Use the existing
PostgreSQL/Supabase project, server-only credentials, a private dedicated bucket,
and an HTTPS WSGI deployment. Never place the storage service key or signing key
in Pages variables or browser code. The static build receives only
`FILING_VAULT_API_ORIGIN`, an HTTPS origin with no path, credentials or query.
The existing Pages build maps the same-named repository variable into this
setting; it contains no secret. Set it only after the private runtime is ready.
Without a reachable API the page explicitly shows catalog-only availability.

```sh
python -m pip install -r requirements-vault.txt
gunicorn --workers 2 --bind 127.0.0.1:8000 'backend.filing_vault:create_vault_app()'
```

Use a reverse proxy with HTTPS, bounded request sizes, connection timeouts and
shared per-client rate limits. Built-in guards are process-local, not a distributed
quota system. Source requests have host-specific pacing; multiple workers need an
aggregate egress limit appropriate to the official service. Database row/advisory
locks serialize retrieval and prevent lifecycle cleanup from racing uploads.

## Daily lifecycle

Install the example runtime service/timer in `config/filing-vault/` after adapting
its paths and environment. This is an application-host timer, **not** another
GitHub Actions writer. Run at least daily, after the existing ingestion/publisher
schedule has supplied a verified fresh catalog. Reconciliation imports the
configured catalog, revalidates due tracked metadata/content, removes expired
objects and orphan files, retains provenance and logs counts/failures. Do not
delete transaction or analysis records when document bytes expire. Failed deletion
remains retryable. `--no-revalidate` performs cleanup without upstream retrieval.
The checked-in timer is not installed or operational merely because it exists.

## Security and testing

Government retrieval requires an approved HTTPS host, standard port, no userinfo,
safe path and public DNS addresses. Connections pin the validated IP and verify
TLS against the government hostname. Every redirect is revalidated; credentials
are stripped across hosts. Requests bypass environment proxies, enforce bounded
timeouts/retries/redirects/streamed size and reject unsupported MIME, incomplete
PDFs and access/login HTML. Server code never executes embedded PDF content.
Storage is private; paths and credentials are never returned to clients.

Structured events cover attempts/success/failure, cache hits/misses/expiry,
changed content/amendments, integrity mismatch, acknowledgement and request-only
states. Logs avoid document content, tokens and raw acknowledgement identifiers.

```sh
python -m pytest tests/test_filing_vault.py tests/test_filing_vault_providers.py tests/test_filing_vault_ui.py -q
python -m pytest tests -q
node --check scripts/dashboard_assets/filing-vault.js
node --test tests/filing_pdf_dom.test.cjs
```

DOM tests use the repository's optional JSDOM/axe harness. Set
`POLITITRACK_TEST_NODE` and `POLITITRACK_TEST_NODE_MODULES` when Node/modules are not
on the default path. Windows tests may require writable `TEMP`/`TMP` and an
explicit `--basetemp`. All source tests mock government endpoints. Simulations
must not import synthetic records into production Vault storage; existing
simulation workflows receive no Vault credentials and remain unchanged.

## Implementation inventory and validation

Runtime: `backend/filing_vault/{__init__,__main__,api,schema,service,storage,providers}.py`
and opt-in integration in `backend/api/__init__.py`. Dashboard: `scripts/filing_resources.py`,
`build_trade_dashboard.py`, `investor_edge.py`, shared `dashboard_assets/{app,common,wallboard}.js`,
`index.html`, `styles.css`, new `filing-vault.{html,js,css}`, `filing-pdf.{js,css}` and
`vendor/pdfjs/`. Operations: `.gitattributes`, both environment examples,
`requirements-vault.txt`, `config/filing-vault/`, the existing read-only CI and Pages
workflows, this guide and project-state/decision/handoff/dashboard documentation.

Tests: `tests/test_filing_vault.py`, `test_filing_vault_providers.py`,
`test_filing_vault_ui.py`, `filing_vault_dom.test.cjs`, `filing_pdf_dom.test.cjs`,
`filing_resolution_dom.test.cjs`, and updated existing dashboard/Investor Edge assertions. Original local validation on
2026-08-31: **463 pytest cases passed with no skips**, including **168 Vault cases**,
**22 generated Vault DOM scenarios** and **7 PDF-helper scenarios**. Source input
bytes, private-data exclusions, vendor integrity, Python/JS syntax and workflow
YAML passed. Actual PDF rendering, refresh timestamps, notice reuse and request-only
errors passed against a disposable in-memory TEST API at desktop/mobile sizes.

Publication integration with the released Operations and Investor Edge changes
passed **524 tests with no skips**, plus **6 filing-link DOM cases**. GitHub CI
and Pages publication remain pending at this checkpoint. The configured PostgreSQL/Supabase
project, real government-source access, distributed limits, HTTPS/CORS, daily timer
and physical iPhone/Safari still need runtime acceptance. No production artifact,
real alert or simulation was written or dispatched for these tests.
