#!/usr/bin/env python3
"""Build a static, searchable review dashboard from MyETF tracker state artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DEFAULT_OUTPUT = Path("trade-dashboard-site")

FILING_FIELDS = (
    "filing_key",
    "first_seen_utc",
    "updated_at_utc",
    "branch",
    "source",
    "report_id",
    "filer",
    "filed_date",
    "source_url",
    "document_format",
    "chamber",
    "title",
    "agency",
    "district",
    "report_type",
    "access_mode",
    "status",
    "transaction_count",
    "purchase_count",
    "sale_count",
    "exchange_count",
    "review_reason",
)

TRANSACTION_FIELDS = (
    "trade_id",
    "observed_at_utc",
    "branch",
    "source",
    "report_id",
    "filer",
    "chamber",
    "title",
    "agency",
    "owner",
    "asset",
    "ticker",
    "asset_type",
    "transaction_type",
    "transaction_date",
    "notification_date",
    "filed_date",
    "amount",
    "source_url",
    "raw_row",
    "equity_like",
    "parse_confidence",
)

REVIEW_FIELDS = (
    "review_id",
    "observed_at_utc",
    "branch",
    "source",
    "report_id",
    "filer",
    "filed_date",
    "source_url",
    "reason",
    "title",
    "agency",
)

RUN_FIELDS = (
    "run_key",
    "branch",
    "started_utc",
    "finished_utc",
    "success",
    "source_counts",
    "new_filing_counts",
    "cataloged_filing_counts",
    "baseline_counts",
    "transaction_counts",
    "purchase_counts",
    "pending_review_counts",
    "errors",
    "run_url",
    "event_name",
    "run_attempt",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL in {path} at line {number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected an object in {path} at line {number}")
        records.append(value)
    return records


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    return value if isinstance(value, dict) else {}


def latest_by(records: Iterable[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        record_key = str(record.get(key) or "")
        if record_key:
            latest[record_key] = dict(record)
    return list(latest.values())


def date_sort_value(record: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    return tuple(str(record.get(field) or "") for field in fields)


def load_branch(directory: Path | None, branch: str) -> dict[str, Any]:
    if directory is None or not directory.exists():
        return {
            "branch": branch,
            "filings": [],
            "transactions": [],
            "reviews": [],
            "runs": [],
            "state": {},
        }

    filings = latest_by(read_jsonl(directory / "filings.jsonl"), "filing_key")
    transactions = latest_by(read_jsonl(directory / "transactions.jsonl"), "trade_id")
    # Preserve purchases collected before the all-transaction ledger was introduced.
    transaction_index = {str(item.get("trade_id")): item for item in transactions}
    for purchase in read_jsonl(directory / "purchases.jsonl"):
        trade_id = str(purchase.get("trade_id") or "")
        if trade_id and trade_id not in transaction_index:
            transaction_index[trade_id] = dict(purchase)
    transactions = list(transaction_index.values())
    reviews = latest_by(read_jsonl(directory / "pending-review.jsonl"), "review_id")
    runs = latest_by(read_jsonl(directory / "runs.jsonl"), "run_key")
    state = read_json_object(directory / "state.json")

    for item in filings:
        item.setdefault("branch", branch)
    for item in transactions:
        item.setdefault("branch", branch)
    for item in reviews:
        item.setdefault("branch", branch)
    for item in runs:
        item.setdefault("branch", branch)

    return {
        "branch": branch,
        "filings": filings,
        "transactions": transactions,
        "reviews": reviews,
        "runs": runs,
        "state": state,
    }


def _flatten_for_csv(record: Mapping[str, Any], fieldnames: Sequence[str]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for field in fieldnames:
        value = record.get(field, "")
        if isinstance(value, (dict, list)):
            flattened[field] = json.dumps(value, sort_keys=True)
        else:
            flattened[field] = value
    return flattened


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_flatten_for_csv(row, fieldnames))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def max_timestamp(values: Iterable[str]) -> str:
    cleaned = [value for value in values if value]
    return max(cleaned) if cleaned else ""


def source_summary(
    filings: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, Any]],
    states: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    sources = ("house", "senate", "oge")
    counts = Counter(str(item.get("source") or "") for item in filings)
    summary: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_runs = [
            run
            for run in runs
            if source in (run.get("source_counts") or {})
        ]
        source_runs.sort(key=lambda run: str(run.get("finished_utc") or ""), reverse=True)
        latest_run = source_runs[0] if source_runs else {}
        last_success = ""
        for run in source_runs:
            if bool(run.get("success")):
                last_success = str(run.get("finished_utc") or "")
                break
        if not last_success:
            last_success = max_timestamp(
                str(state.get("last_success_utc") or "") for state in states
            )
        summary[source] = {
            "source": source,
            "filing_count": counts.get(source, 0),
            "last_run_utc": str(latest_run.get("finished_utc") or ""),
            "last_success_utc": last_success,
            "latest_success": latest_run.get("success") if latest_run else None,
            "latest_error": "; ".join(str(item) for item in (latest_run.get("errors") or [])),
            "visible_count": int((latest_run.get("source_counts") or {}).get(source, 0) or 0),
        }
    return summary


def build_payload(
    legislative: dict[str, Any],
    executive: dict[str, Any],
    *,
    repository_url: str,
) -> dict[str, Any]:
    filings = legislative["filings"] + executive["filings"]
    transactions = legislative["transactions"] + executive["transactions"]
    reviews = legislative["reviews"] + executive["reviews"]
    runs = legislative["runs"] + executive["runs"]

    filings = latest_by(filings, "filing_key")
    transactions = latest_by(transactions, "trade_id")
    reviews = latest_by(reviews, "review_id")
    runs = latest_by(runs, "run_key")

    filings.sort(key=lambda item: date_sort_value(item, "filed_date", "updated_at_utc", "filing_key"), reverse=True)
    transactions.sort(
        key=lambda item: date_sort_value(
            item, "filed_date", "transaction_date", "observed_at_utc", "trade_id"
        ),
        reverse=True,
    )
    reviews.sort(key=lambda item: date_sort_value(item, "filed_date", "observed_at_utc", "review_id"), reverse=True)
    runs.sort(key=lambda item: date_sort_value(item, "finished_utc", "run_key"), reverse=True)

    status_counts = Counter(str(item.get("status") or "unknown") for item in filings)
    transaction_type_counts = Counter(
        str(item.get("transaction_type") or "Unknown") for item in transactions
    )
    purchase_count = sum(
        str(item.get("transaction_type") or "") == "Purchase" for item in transactions
    )
    generated_utc = utc_now_iso()
    latest_timestamp = max_timestamp(
        [
            *(str(item.get("updated_at_utc") or "") for item in filings),
            *(str(item.get("observed_at_utc") or "") for item in transactions),
            *(str(item.get("observed_at_utc") or "") for item in reviews),
            *(str(item.get("finished_utc") or "") for item in runs),
        ]
    ) or generated_utc
    states = [legislative.get("state", {}), executive.get("state", {})]
    sources = source_summary(filings, runs, states)

    summary = {
        "generated_utc": generated_utc,
        "data_through_utc": latest_timestamp,
        "repository_url": repository_url,
        "filing_count": len(filings),
        "transaction_count": len(transactions),
        "purchase_count": purchase_count,
        "review_count": len(reviews),
        "run_count": len(runs),
        "status_counts": dict(sorted(status_counts.items())),
        "transaction_type_counts": dict(sorted(transaction_type_counts.items())),
        "sources": sources,
        "coverage_note": (
            "Cataloged filings show what the tracker can currently see. A 'Cataloged only' "
            "record predates transaction backfill and has not necessarily been parsed."
        ),
    }
    return {
        "summary": summary,
        "filings": filings,
        "transactions": transactions,
        "reviews": reviews,
        "runs": runs,
    }


INDEX_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
  <meta name="description" content="MyETF official government financial disclosure filing review dashboard">
  <title>MyETF Government Trade Monitor</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <div>
      <p class="eyebrow">Official-source disclosure monitor</p>
      <h1>MyETF Government Trade Monitor</h1>
      <p class="subtitle">House, Senate, and Executive-branch filing inventory, transactions, review items, and tracker health.</p>
    </div>
    <div class="header-actions">
      <a id="repository-link" class="button secondary" href="#" target="_blank" rel="noopener">Repository</a>
      <button id="refresh-button" class="button" type="button">Refresh data</button>
    </div>
  </header>

  <main>
    <section class="notice" aria-label="Coverage notice">
      <strong>Coverage note:</strong>
      <span id="coverage-note">Loading…</span>
      <span>Government disclosures may be published weeks after the underlying transaction.</span>
    </section>

    <section class="summary-grid" aria-label="Summary">
      <article class="metric-card"><span>Cataloged filings</span><strong id="filing-count">—</strong></article>
      <article class="metric-card"><span>Parsed transactions</span><strong id="transaction-count">—</strong></article>
      <article class="metric-card"><span>Purchases</span><strong id="purchase-count">—</strong></article>
      <article class="metric-card"><span>Review queue</span><strong id="review-count">—</strong></article>
    </section>

    <section>
      <div class="section-heading">
        <div>
          <p class="eyebrow">Collector status</p>
          <h2>Sources</h2>
        </div>
        <p id="updated-at" class="muted">Loading…</p>
      </div>
      <div id="source-cards" class="source-grid"></div>
    </section>

    <nav class="tabs" aria-label="Dashboard sections">
      <button class="tab active" data-panel="filings" type="button">Filings</button>
      <button class="tab" data-panel="transactions" type="button">Transactions</button>
      <button class="tab" data-panel="reviews" type="button">Review queue</button>
      <button class="tab" data-panel="runs" type="button">Run history</button>
    </nav>

    <section id="panel-filings" class="panel active">
      <div class="panel-header">
        <div><h2>Filing inventory</h2><p>Every filing currently cataloged by the trackers, including records that predate transaction parsing.</p></div>
        <a class="download-link" href="data/filings.csv">Download CSV</a>
      </div>
      <div class="controls">
        <label>Search<input id="filings-search" type="search" placeholder="Filer, agency, district, report…"></label>
        <label>Source<select id="filings-source"><option value="">All sources</option></select></label>
        <label>Status<select id="filings-status"><option value="">All statuses</option></select></label>
      </div>
      <p id="filings-count-label" class="result-count"></p>
      <div class="table-wrap"><table><thead><tr><th>Filed</th><th>Source</th><th>Filer</th><th>Role / jurisdiction</th><th>Status</th><th>Transactions</th><th>Official filing</th></tr></thead><tbody id="filings-body"></tbody></table></div>
      <button id="filings-more" class="more-button" type="button">Show more</button>
    </section>

    <section id="panel-transactions" class="panel">
      <div class="panel-header">
        <div><h2>Parsed transactions</h2><p>Purchases, sales, and exchanges parsed after the reporting upgrade, plus any earlier retained purchases.</p></div>
        <a class="download-link" href="data/transactions.csv">Download CSV</a>
      </div>
      <div class="controls">
        <label>Search<input id="transactions-search" type="search" placeholder="Ticker, company, filer, owner…"></label>
        <label>Source<select id="transactions-source"><option value="">All sources</option></select></label>
        <label>Type<select id="transactions-type"><option value="">All transaction types</option></select></label>
      </div>
      <p id="transactions-count-label" class="result-count"></p>
      <div class="table-wrap"><table><thead><tr><th>Transaction</th><th>Filed</th><th>Source</th><th>Filer</th><th>Owner</th><th>Type</th><th>Ticker / asset</th><th>Amount</th><th>Filing</th></tr></thead><tbody id="transactions-body"></tbody></table></div>
      <button id="transactions-more" class="more-button" type="button">Show more</button>
    </section>

    <section id="panel-reviews" class="panel">
      <div class="panel-header">
        <div><h2>Manual review queue</h2><p>Paper forms, request-only OGE records, and disclosures whose row structure could not be safely parsed.</p></div>
        <a class="download-link" href="data/pending-reviews.csv">Download CSV</a>
      </div>
      <div class="controls">
        <label>Search<input id="reviews-search" type="search" placeholder="Filer, agency, reason…"></label>
        <label>Source<select id="reviews-source"><option value="">All sources</option></select></label>
      </div>
      <p id="reviews-count-label" class="result-count"></p>
      <div class="table-wrap"><table><thead><tr><th>Filed</th><th>Source</th><th>Filer</th><th>Agency / title</th><th>Reason</th><th>Official page</th></tr></thead><tbody id="reviews-body"></tbody></table></div>
      <button id="reviews-more" class="more-button" type="button">Show more</button>
    </section>

    <section id="panel-runs" class="panel">
      <div class="panel-header">
        <div><h2>Tracker run history</h2><p>Recent successful and failed collector runs retained with the durable tracker state.</p></div>
        <a class="download-link" href="data/runs.csv">Download CSV</a>
      </div>
      <p id="runs-count-label" class="result-count"></p>
      <div class="table-wrap"><table><thead><tr><th>Finished</th><th>Branch</th><th>Status</th><th>Visible</th><th>New filings</th><th>Transactions</th><th>Errors</th><th>GitHub run</th></tr></thead><tbody id="runs-body"></tbody></table></div>
      <button id="runs-more" class="more-button" type="button">Show more</button>
    </section>
  </main>

  <footer>
    <p>Data is derived from official public disclosure sources. Open the linked source record before relying on a parsed row.</p>
  </footer>
  <script src="app.js" defer></script>
</body>
</html>
'''

STYLES_CSS = r''':root {
  --bg: #08111f;
  --surface: #101d2e;
  --surface-2: #15263a;
  --border: #294057;
  --text: #edf4fb;
  --muted: #9db0c3;
  --accent: #69b7ff;
  --accent-2: #a8d7ff;
  --success: #70d6a1;
  --warning: #f2c879;
  --danger: #ff8c8c;
  --shadow: 0 14px 40px rgba(0, 0, 0, .24);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
html { background: var(--bg); color: var(--text); }
body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top right, #173252 0, transparent 34rem), var(--bg); }
a { color: var(--accent-2); }
.site-header, main, footer { width: min(1500px, calc(100% - 32px)); margin-inline: auto; }
.site-header { display: flex; justify-content: space-between; gap: 24px; align-items: end; padding: 44px 0 24px; }
h1, h2, p { margin-top: 0; }
h1 { margin-bottom: 10px; font-size: clamp(2rem, 5vw, 3.5rem); line-height: 1.02; letter-spacing: -.035em; }
h2 { margin-bottom: 6px; font-size: 1.3rem; }
.subtitle { max-width: 850px; color: var(--muted); font-size: 1.05rem; }
.eyebrow { margin-bottom: 8px; color: var(--accent); font-size: .76rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.header-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.button, .more-button, .tab { border: 1px solid var(--border); border-radius: 10px; background: var(--accent); color: #07111d; font: inherit; font-weight: 750; padding: 10px 14px; cursor: pointer; text-decoration: none; }
.button.secondary, .more-button, .tab { background: var(--surface); color: var(--text); }
.notice { display: flex; flex-wrap: wrap; gap: 8px 12px; margin: 0 0 20px; padding: 14px 16px; border: 1px solid #6b5528; border-radius: 12px; background: rgba(101, 75, 20, .22); color: #f3dfb4; }
.summary-grid, .source-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.metric-card, .source-card { border: 1px solid var(--border); border-radius: 14px; background: linear-gradient(145deg, rgba(21, 38, 58, .96), rgba(13, 26, 42, .96)); box-shadow: var(--shadow); }
.metric-card { padding: 19px; }
.metric-card span { display: block; color: var(--muted); font-size: .86rem; }
.metric-card strong { display: block; margin-top: 8px; font-size: 2rem; }
.section-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-top: 34px; }
.source-card { padding: 16px; }
.source-card header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.source-card dl { display: grid; grid-template-columns: 1fr auto; gap: 7px 14px; margin: 14px 0 0; }
.source-card dt { color: var(--muted); }
.source-card dd { margin: 0; text-align: right; }
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: var(--muted); }
.status-dot.up { background: var(--success); }
.status-dot.down { background: var(--danger); }
.status-dot.unknown { background: var(--warning); }
.muted { color: var(--muted); }
.tabs { display: flex; gap: 8px; margin: 36px 0 14px; overflow-x: auto; padding-bottom: 4px; }
.tab { white-space: nowrap; }
.tab.active { background: var(--accent); color: #07111d; }
.panel { display: none; padding: 22px; border: 1px solid var(--border); border-radius: 16px; background: rgba(12, 25, 41, .94); box-shadow: var(--shadow); }
.panel.active { display: block; }
.panel-header { display: flex; justify-content: space-between; gap: 24px; align-items: start; }
.panel-header p { color: var(--muted); }
.download-link { white-space: nowrap; }
.controls { display: grid; grid-template-columns: minmax(220px, 2fr) repeat(2, minmax(150px, 1fr)); gap: 12px; margin: 18px 0 8px; }
.controls label { display: grid; gap: 6px; color: var(--muted); font-size: .78rem; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
input, select { width: 100%; border: 1px solid var(--border); border-radius: 9px; background: var(--surface-2); color: var(--text); padding: 10px 11px; font: inherit; }
.result-count { color: var(--muted); margin: 12px 0; }
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 11px; }
table { width: 100%; border-collapse: collapse; min-width: 960px; font-size: .88rem; }
th, td { padding: 11px 12px; text-align: left; vertical-align: top; border-bottom: 1px solid rgba(41, 64, 87, .68); }
th { position: sticky; top: 0; z-index: 1; background: #132337; color: var(--accent-2); font-size: .74rem; text-transform: uppercase; letter-spacing: .055em; }
tbody tr:hover { background: rgba(105, 183, 255, .055); }
.badge { display: inline-block; border: 1px solid var(--border); border-radius: 999px; padding: 3px 8px; background: var(--surface-2); font-size: .75rem; white-space: nowrap; }
.badge.processed, .badge.success { color: var(--success); border-color: rgba(112, 214, 161, .5); }
.badge.review_required, .badge.failure { color: var(--danger); border-color: rgba(255, 140, 140, .5); }
.badge.cataloged { color: var(--warning); border-color: rgba(242, 200, 121, .5); }
.badge.detected { color: var(--accent-2); }
.asset-cell strong, .filer-cell strong { display: block; }
.asset-cell small, .filer-cell small { display: block; margin-top: 3px; color: var(--muted); }
.more-button { margin-top: 14px; }
.more-button[hidden] { display: none; }
.empty-row { text-align: center; color: var(--muted); padding: 30px; }
footer { padding: 30px 0 48px; color: var(--muted); font-size: .85rem; }
@media (max-width: 950px) {
  .site-header { align-items: start; flex-direction: column; }
  .summary-grid, .source-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .controls { grid-template-columns: 1fr; }
}
@media (max-width: 560px) {
  .site-header, main, footer { width: min(100% - 20px, 1500px); }
  .site-header { padding-top: 28px; }
  .summary-grid, .source-grid { grid-template-columns: 1fr; }
  .panel { padding: 14px; }
  .panel-header { flex-direction: column; gap: 4px; }
}
@media (prefers-color-scheme: light) {
  :root { --bg: #eff4f8; --surface: #ffffff; --surface-2: #f4f7fa; --border: #cbd8e4; --text: #132235; --muted: #536a7f; --shadow: 0 12px 32px rgba(29, 54, 79, .12); }
  body { background: radial-gradient(circle at top right, #d9ebfb 0, transparent 34rem), var(--bg); }
  th { background: #e8f1f8; }
  .panel { background: rgba(255,255,255,.96); }
}
'''

APP_JS = r'''const PAGE_SIZE = 200;
const state = { data: null, shown: { filings: PAGE_SIZE, transactions: PAGE_SIZE, reviews: PAGE_SIZE, runs: PAGE_SIZE } };

const el = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const safeUrl = value => { try { const url = new URL(String(value)); return ["http:", "https:"].includes(url.protocol) ? url.href : ""; } catch { return ""; } };
const titleCase = value => String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const number = value => Number(value || 0).toLocaleString();
const formatDate = value => { if (!value) return "—"; const d = new Date(value); return Number.isNaN(d.getTime()) ? escapeHtml(value) : d.toLocaleString([], { dateStyle: "medium", timeStyle: value.includes("T") ? "short" : undefined }); };
const dictTotal = value => Object.values(value || {}).reduce((sum, item) => sum + Number(item || 0), 0);
const link = (url, text="Open") => { const clean = safeUrl(url); return clean ? `<a href="${escapeHtml(clean)}" target="_blank" rel="noopener">${escapeHtml(text)}</a>` : "—"; };
const haystack = row => Object.values(row || {}).map(value => typeof value === "object" ? JSON.stringify(value) : String(value ?? "")).join(" ").toLowerCase();

async function loadData() {
  const [summary, filings, transactions, reviews, runs] = await Promise.all([
    fetch("data/summary.json", {cache:"no-store"}).then(r => r.json()),
    fetch("data/filings.json", {cache:"no-store"}).then(r => r.json()),
    fetch("data/transactions.json", {cache:"no-store"}).then(r => r.json()),
    fetch("data/pending-reviews.json", {cache:"no-store"}).then(r => r.json()),
    fetch("data/runs.json", {cache:"no-store"}).then(r => r.json()),
  ]);
  state.data = { summary, filings, transactions, reviews, runs };
  renderAll();
}

function populateSelect(id, values, labeler=titleCase) {
  const select = el(id);
  const current = select.value;
  [...new Set(values.filter(Boolean))].sort().forEach(value => {
    if (![...select.options].some(option => option.value === value)) {
      const option = document.createElement("option"); option.value = value; option.textContent = labeler(value); select.append(option);
    }
  });
  select.value = current;
}

function renderSummary() {
  const summary = state.data.summary;
  el("filing-count").textContent = number(summary.filing_count);
  el("transaction-count").textContent = number(summary.transaction_count);
  el("purchase-count").textContent = number(summary.purchase_count);
  el("review-count").textContent = number(summary.review_count);
  el("coverage-note").textContent = `${summary.coverage_note} `;
  el("updated-at").textContent = `Dashboard generated ${formatDate(summary.generated_utc)}`;
  el("repository-link").href = safeUrl(summary.repository_url) || "#";
  el("source-cards").innerHTML = Object.values(summary.sources || {}).map(source => {
    const statusClass = source.latest_success === true ? "up" : source.latest_success === false ? "down" : "unknown";
    const statusText = source.latest_success === true ? "Last run succeeded" : source.latest_success === false ? "Last run failed" : "No retained run status";
    return `<article class="source-card"><header><strong>${escapeHtml(titleCase(source.source))}</strong><span class="status-dot ${statusClass}" title="${escapeHtml(statusText)}"></span></header><dl><dt>Cataloged filings</dt><dd>${number(source.filing_count)}</dd><dt>Visible in last run</dt><dd>${number(source.visible_count)}</dd><dt>Last run</dt><dd>${formatDate(source.last_run_utc)}</dd><dt>Last success</dt><dd>${formatDate(source.last_success_utc)}</dd></dl>${source.latest_error ? `<p class="muted">${escapeHtml(source.latest_error)}</p>` : ""}</article>`;
  }).join("");
}

function setTable(id, rows, renderer, shownKey) {
  const shown = state.shown[shownKey];
  el(id).innerHTML = rows.length ? rows.slice(0, shown).map(renderer).join("") : `<tr><td class="empty-row" colspan="12">No matching records.</td></tr>`;
  const button = el(`${shownKey}-more`);
  button.hidden = rows.length <= shown;
  button.onclick = () => { state.shown[shownKey] += PAGE_SIZE; renderAllTables(); };
  el(`${shownKey}-count-label`).textContent = `Showing ${number(Math.min(rows.length, shown))} of ${number(rows.length)} matching record(s).`;
}

function filteredFilings() {
  const query = el("filings-search").value.trim().toLowerCase();
  const source = el("filings-source").value;
  const status = el("filings-status").value;
  return state.data.filings.filter(row => (!query || haystack(row).includes(query)) && (!source || row.source === source) && (!status || row.status === status));
}
function renderFilings() {
  const rows = filteredFilings();
  setTable("filings-body", rows, row => {
    const role = [row.title, row.agency, row.district].filter(Boolean);
    const counts = `${number(row.transaction_count)} total / ${number(row.purchase_count)} buys / ${number(row.sale_count)} sales`;
    return `<tr><td>${formatDate(row.filed_date)}</td><td>${escapeHtml(titleCase(row.source))}</td><td class="filer-cell"><strong>${escapeHtml(row.filer || "Unknown")}</strong><small>${escapeHtml(row.report_type || "")}</small></td><td>${escapeHtml(role.join(" • ") || "—")}</td><td><span class="badge ${escapeHtml(row.status || "")}">${escapeHtml(titleCase(row.status || "unknown"))}</span>${row.review_reason ? `<small>${escapeHtml(row.review_reason)}</small>` : ""}</td><td>${escapeHtml(counts)}</td><td>${link(row.source_url)}</td></tr>`;
  }, "filings");
}

function filteredTransactions() {
  const query = el("transactions-search").value.trim().toLowerCase();
  const source = el("transactions-source").value;
  const type = el("transactions-type").value;
  return state.data.transactions.filter(row => (!query || haystack(row).includes(query)) && (!source || row.source === source) && (!type || row.transaction_type === type));
}
function renderTransactions() {
  const rows = filteredTransactions();
  setTable("transactions-body", rows, row => `<tr><td>${formatDate(row.transaction_date)}</td><td>${formatDate(row.filed_date)}</td><td>${escapeHtml(titleCase(row.source))}</td><td class="filer-cell"><strong>${escapeHtml(row.filer || "Unknown")}</strong><small>${escapeHtml([row.title,row.agency,row.chamber].filter(Boolean).join(" • "))}</small></td><td>${escapeHtml(row.owner || "Unknown")}</td><td><span class="badge">${escapeHtml(row.transaction_type || "Unknown")}</span></td><td class="asset-cell"><strong>${escapeHtml(row.ticker || row.asset || "Unknown")}</strong>${row.ticker ? `<small>${escapeHtml(row.asset || "")}</small>` : ""}</td><td>${escapeHtml(row.amount || "—")}</td><td>${link(row.source_url)}</td></tr>`, "transactions");
}

function filteredReviews() {
  const query = el("reviews-search").value.trim().toLowerCase();
  const source = el("reviews-source").value;
  return state.data.reviews.filter(row => (!query || haystack(row).includes(query)) && (!source || row.source === source));
}
function renderReviews() {
  const rows = filteredReviews();
  setTable("reviews-body", rows, row => `<tr><td>${formatDate(row.filed_date)}</td><td>${escapeHtml(titleCase(row.source))}</td><td>${escapeHtml(row.filer || "Unknown")}</td><td>${escapeHtml([row.title,row.agency].filter(Boolean).join(" • ") || "—")}</td><td>${escapeHtml(row.reason || "—")}</td><td>${link(row.source_url)}</td></tr>`, "reviews");
}

function renderRuns() {
  const rows = state.data.runs;
  setTable("runs-body", rows, row => `<tr><td>${formatDate(row.finished_utc)}</td><td>${escapeHtml(titleCase(row.branch))}</td><td><span class="badge ${row.success ? "success" : "failure"}">${row.success ? "Success" : "Failed"}</span></td><td>${number(dictTotal(row.source_counts))}</td><td>${number(dictTotal(row.new_filing_counts))}</td><td>${number(dictTotal(row.transaction_counts))}</td><td>${escapeHtml((row.errors || []).join("; ") || "—")}</td><td>${link(row.run_url, "Open run")}</td></tr>`, "runs");
}

function renderAllTables() { renderFilings(); renderTransactions(); renderReviews(); renderRuns(); }
function renderAll() {
  renderSummary();
  populateSelect("filings-source", state.data.filings.map(row => row.source));
  populateSelect("filings-status", state.data.filings.map(row => row.status));
  populateSelect("transactions-source", state.data.transactions.map(row => row.source));
  populateSelect("transactions-type", state.data.transactions.map(row => row.transaction_type), value => value);
  populateSelect("reviews-source", state.data.reviews.map(row => row.source));
  renderAllTables();
}

for (const button of document.querySelectorAll(".tab")) button.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item === button));
  document.querySelectorAll(".panel").forEach(panel => panel.classList.toggle("active", panel.id === `panel-${button.dataset.panel}`));
});
for (const id of ["filings-search","filings-source","filings-status","transactions-search","transactions-source","transactions-type","reviews-search","reviews-source"]) el(id).addEventListener("input", () => { const key = id.split("-")[0]; state.shown[key] = PAGE_SIZE; renderAllTables(); });
el("refresh-button").addEventListener("click", () => { state.shown = { filings: PAGE_SIZE, transactions: PAGE_SIZE, reviews: PAGE_SIZE, runs: PAGE_SIZE }; loadData().catch(showError); });
function showError(error) { document.querySelector("main").insertAdjacentHTML("afterbegin", `<section class="notice"><strong>Dashboard load failed:</strong> ${escapeHtml(error.message || error)}</section>`); }
loadData().catch(showError);
'''


def build_site(payload: Mapping[str, Any], output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=parent))
    try:
        data_dir = temp_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        write_json(data_dir / "summary.json", payload["summary"])
        write_json(data_dir / "filings.json", payload["filings"])
        write_json(data_dir / "transactions.json", payload["transactions"])
        write_json(data_dir / "pending-reviews.json", payload["reviews"])
        write_json(data_dir / "runs.json", payload["runs"])
        write_csv(data_dir / "filings.csv", payload["filings"], FILING_FIELDS)
        write_csv(data_dir / "transactions.csv", payload["transactions"], TRANSACTION_FIELDS)
        write_csv(data_dir / "pending-reviews.csv", payload["reviews"], REVIEW_FIELDS)
        write_csv(data_dir / "runs.csv", payload["runs"], RUN_FIELDS)
        (temp_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
        (temp_dir / "404.html").write_text(INDEX_HTML, encoding="utf-8")
        (temp_dir / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
        (temp_dir / "app.js").write_text(APP_JS, encoding="utf-8")
        (temp_dir / ".nojekyll").write_text("", encoding="utf-8")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        temp_dir.replace(output_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislative-dir", type=Path)
    parser.add_argument("--executive-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--repository-url",
        default=(
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', 'maglothinm/MyETF').strip('/')}"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    legislative = load_branch(args.legislative_dir, "legislative")
    executive = load_branch(args.executive_dir, "executive")
    payload = build_payload(legislative, executive, repository_url=args.repository_url)
    build_site(payload, args.output_dir)
    print(
        f"Dashboard built at {args.output_dir}: "
        f"{len(payload['filings'])} filings, {len(payload['transactions'])} transactions, "
        f"{len(payload['reviews'])} review items"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
