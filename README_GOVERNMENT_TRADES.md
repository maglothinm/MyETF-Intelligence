# Government disclosure tracker and review dashboard

## Operational objective

This component detects newly published financial-disclosure filings from official U.S. government sources, preserves a complete filing inventory and normalized transaction records, sends prompt alerts, and publishes a searchable static review dashboard. It remains independent of the repository's older Flask/PostgreSQL/dbt/React stack so collection and reporting do not depend on that incomplete deployment.

## Coverage

### Legislative branch

The `Legislative purchase tracker` workflow polls:

- House annual financial-disclosure indexes, then downloads new Periodic Transaction Report PDFs by document ID;
- Senate eFD Periodic Transaction Report search results, including electronic transaction tables and paper-report links.

Every newly visible filing is processed once. Electronic rows are normalized. Recognized paper or structurally unreadable forms are preserved in a review queue with the official filing link rather than silently ignored.

The source systems include public PTR filers beyond only sitting Members in some circumstances, including candidates, officers, or covered employees. The ledger identifies the filer and source; no unsupported inference about current office status is added.

### Executive branch

The `Executive purchase tracker` workflow opens OGE's client-rendered individual-disclosure collection in Chromium, accepts the public-use banner only after explicit operator acknowledgement, discovers Form 278-T listings, and then:

- directly downloads and parses reports for which OGE publishes a document;
- creates a review/request item when the listing requires OGE Form 201 or has no direct document;
- never attempts to bypass the request process.

This is not complete coverage of every Executive-branch public filer. OGE directly handles and publishes only part of that universe; many public reports remain with employing agencies. Additional agency-specific connectors are a later expansion.

## What is recorded

The tracker now retains three complementary datasets for each branch:

1. **Filing inventory** — every filing currently visible to the source collector, including previously baselined filings.
2. **All parsed transactions** — purchases, sales, sale subtypes, and exchanges.
3. **Purchase ledger** — a backward-compatible purchase-only subset used by existing integrations.

Each parsed transaction contains:

- branch, source, report ID, filer, chamber/title/agency where available;
- owner (`Self`, `Spouse`, `Joint`, or `Dependent Child` where disclosed);
- asset, ticker, asset type, and an `equity_like` classification;
- transaction type, transaction date, notification date where available, filing date, and disclosed value range;
- official source URL, raw row text, parser confidence, stable trade ID, and UTC observation timestamp.

Each filing record contains the filer, filing date, official link, source, role or jurisdiction, access method, processing status, transaction counts, and any review reason. A status of `cataloged` means that the filing is visible and linked but predates transaction backfill; it must not be interpreted as fully parsed.

Durable files:

| Data | Legislative | Executive |
|---|---|---|
| Filing inventory | `.trade-tracker/legislative/filings.jsonl` | `.trade-tracker/executive/filings.jsonl` |
| All transactions | `.trade-tracker/legislative/transactions.jsonl` | `.trade-tracker/executive/transactions.jsonl` |
| Purchase-only compatibility ledger | `.trade-tracker/legislative/purchases.jsonl` | `.trade-tracker/executive/purchases.jsonl` |
| Review queue | `.trade-tracker/legislative/pending-review.jsonl` | `.trade-tracker/executive/pending-review.jsonl` |
| Run history | `.trade-tracker/legislative/runs.jsonl` | `.trade-tracker/executive/runs.jsonl` |

The state directories are uploaded as retained GitHub Actions artifacts and restored on later runs. Each run also publishes latest-filings, latest-transactions, and latest-purchases CSV files.

## Searchable review dashboard

The `Publish government trade dashboard` workflow restores the newest Legislative and Executive state artifacts, combines them, and deploys a static GitHub Pages site. The dashboard provides:

- current House, Senate, and OGE collector status;
- a searchable inventory of all cataloged filings with direct official links;
- all retained purchases, sales, and exchanges;
- a manual-review queue;
- retained run history and errors;
- downloadable CSV exports for each view.

For this repository, the expected URL is:

```text
https://maglothinm.github.io/MyETF/
```

GitHub Pages must be enabled once under **Settings → Pages → Build and deployment → Source → GitHub Actions**. The dashboard workflow then runs automatically after either tracker finishes and can also be started manually.

## GitHub configuration

### 1. Review and acknowledge disclosure restrictions

Review the access/use language displayed by:

- House financial disclosures: `https://disclosures-clerk.house.gov/FinancialDisclosure`
- Senate eFD: `https://efdsearch.senate.gov/search/`
- OGE individual disclosures: `https://www.oge.gov/web/oge.nsf/Officials%20Individual%20Disclosures%20Search%20Collection?OpenForm=`

After review, create this **Actions variable** under **Settings → Secrets and variables → Actions → Variables**:

```text
DISCLOSURE_TERMS_ACKNOWLEDGED=true
```

The guard is intentional. Do not set the variable merely to make a failed workflow green.

### 2. Configure alert delivery

Create these **Actions secrets**:

```text
PUSHOVER_API_TOKEN
PUSHOVER_USER_KEY
```

Both workflows set `REQUIRE_PUSHOVER=true`. Missing credentials therefore fail immediately rather than allowing a tracker that cannot alert when a purchase appears.

Optional independent dead-man monitoring:

```text
LEGISLATIVE_HEALTHCHECKS_PING_URL
EXECUTIVE_HEALTHCHECKS_PING_URL
```

Use separate heartbeat endpoints. The legislative workflow normally runs four times per hour; the Executive workflow normally runs hourly.

### 3. Commit and push

```bash
git diff --check
git status --short
git add .
git commit -m "Add government purchase disclosure tracker"
git push
```

Scheduled workflows execute only from the default branch.

### 4. Initialize the durable baselines

For **each** workflow in the Actions tab:

1. Enable the workflow if GitHub shows it as disabled.
2. Select **Run workflow**.
3. Set `initialize_state` to `true`.
4. Leave `bootstrap_alerts` set to `false`.
5. Run it once.

That first run silently marks all currently visible filings as the baseline. It prevents a flood of historical alerts. It should still report nonzero source counts and create state/output artifacts.

Do not select `bootstrap_alerts=true` unless a historical scan and potentially many alerts are intentional.

### 5. Acceptance checks

For the Legislative workflow, confirm:

- offline tests pass;
- both House and Senate source counts are nonzero;
- `legislative-result.json` contains `"success": true`;
- a `legislative-tracker-state` artifact exists;
- the heartbeat receives start and success pings, when configured.

For the Executive workflow, confirm:

- `oge-listings.json` contains one or more Form 278-T listings;
- `executive-result.json` contains `"success": true`;
- an `executive-tracker-state` artifact exists;
- no OGE diagnostic failure screenshot was produced.

The first live Executive run is an acceptance test for the current OGE browser selectors. Offline fixtures validate table parsing, but the OGE page itself can change without notice.

## Alert controls

Repository/workflow environment variables:

| Variable | Default | Effect |
|---|---:|---|
| `NOTIFY_EQUITY_ONLY` | `true` | Applies to legacy purchase-only alert mode. |
| `NOTIFY_ALL_FILINGS` | `true` in the workflows | Sends one alert for every newly parsed filing, including sales and exchanges. |
| `NOTIFY_PENDING_REVIEWS` | `true` | Alerts when a paper form or Form 201 request needs review. |
| `WATCHLIST` | empty | Optional comma-separated ticker/company filter for alerts only. |
| `SENATE_LOOKBACK_DAYS` | `180` | Search horizon used to rebuild the visible Senate filing set. |
| `OCR_MAX_PAGES` | inherited default | Maximum pages permitted for OCR before the tracker fails rather than partially scans. |
| `ALLOW_EMPTY_SOURCES` | `false` | Zero-source results are treated as a source/parser failure. |

Example watchlist added to the tracker step's `env` block:

```yaml
WATCHLIST: "NVDA,AMD,Palantir"
```

The watchlist does not discard other purchases from the ledger.

## Local verification

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils tesseract-ocr
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-tracker.txt pytest==9.0.2
python -m pytest -q \
  tests/test_monitor_disclosures.py \
  tests/test_government_trade_tracker.py \
  tests/test_oge_disclosures.py \
  tests/test_trade_dashboard.py
```

A local Legislative source check without notifications requires an explicit terms acknowledgement and explicit state initialization:

```bash
DISCLOSURE_TERMS_ACKNOWLEDGED=true \
ALLOW_STATE_INITIALIZATION=true \
REQUIRE_PUSHOVER=false \
python scripts/government_trade_tracker.py \
  --branch legislative \
  --source all \
  --no-notify \
  --verbose
```

For Executive discovery, install Chromium first:

```bash
python -m playwright install --with-deps chromium
DISCLOSURE_TERMS_ACKNOWLEDGED=true \
python scripts/oge_disclosures.py --output oge-listings.json --verbose
```

## Scheduling and latency

The Legislative workflow polls at minutes 7, 22, 37, and 52 in `America/New_York`. The Executive browser workflow polls at minute 13 each hour. Both avoid the top of the hour, when hosted scheduling is more prone to delay.

These schedules control detection latency after publication, not trade-to-disclosure latency. Covered filers can generally report a transaction up to 45 days after it occurs. A five-minute polling schedule cannot reveal a transaction before the responsible office publishes it.

GitHub may delay or drop scheduled runs during high load. Public-repository schedules may also be disabled after prolonged repository inactivity. The optional heartbeat endpoints are the independent check that a scheduler is still alive.

## Failure model

The tracker exits nonzero when:

- disclosure-use terms have not been acknowledged;
- durable state is unexpectedly absent;
- a required source is empty or unavailable;
- an electronic source no longer matches its expected schema;
- a report cannot be downloaded or read within configured limits;
- required Pushover credentials are absent or delivery fails.

Known paper forms and request-required Executive listings are different: they are recorded in `pending-review.jsonl`, alerted once, marked seen, and left for human follow-through.

## Historical coverage boundary

The reporting upgrade catalogs all filings visible during the first post-upgrade run, including those that were silently baselined during initial activation. It does not retroactively download and parse every baselined document. Those records are displayed as `Cataloged only` with their official links. New filings are fully processed and retained. A separate historical backfill remains appropriate if transaction-level analysis of the baseline period is required.

The historical Flask/PostgreSQL/dbt/React path remains deferred because it contains separate deployment and API defects. The static dashboard deliberately avoids that dependency while providing a usable review interface now.

## AI analysis after collection

The optional AI workflow is isolated from collection. It restores successful tracker artifacts, analyzes newly parsed public-equity purchases, and publishes paper-research candidates without placing orders. See [`README_AI_FILING_ANALYST.md`](README_AI_FILING_ANALYST.md).
