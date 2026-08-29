#!/usr/bin/env python3
"""Build a static, searchable review dashboard from PolitiTrack state artifacts."""

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

try:  # Support both package and direct-script execution.
    from .investor_edge import build_dashboard_addon
except ImportError:  # pragma: no cover - direct execution path
    from investor_edge import build_dashboard_addon  # type: ignore

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
    "is_synthetic_test",
    "is_temporary",
    "test_metadata",
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
    "signal_direction",
    "transaction_date",
    "notification_date",
    "filed_date",
    "amount",
    "source_url",
    "raw_row",
    "equity_like",
    "parse_confidence",
    "is_synthetic_test",
    "is_temporary",
    "test_metadata",
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

ANALYSIS_FIELDS = (
    "analysis_id",
    "trade_id",
    "analyzed_at_utc",
    "analysis_status",
    "model",
    "branch",
    "source",
    "report_id",
    "filer",
    "title",
    "agency",
    "chamber",
    "owner",
    "ticker",
    "asset",
    "asset_type",
    "transaction_type",
    "transaction_date",
    "filed_date",
    "observed_at_utc",
    "amount",
    "source_url",
    "score",
    "raw_score",
    "classification",
    "score_components",
    "hard_caps",
    "transaction_age_days",
    "repeated_purchase_count_90d",
    "market",
    "sec",
    "ai",
    "entry_plan",
    "paper_only",
)

PORTFOLIO_FIELDS = (
    "position_id",
    "trade_id",
    "analysis_id",
    "ticker",
    "filer",
    "owner",
    "source_url",
    "score",
    "classification",
    "status",
    "opened_at_utc",
    "evaluation_horizon_utc",
    "closed_at_utc",
    "exit_reason",
    "allocation_percent",
    "entry_price",
    "exit_price",
    "quantity",
    "initial_notional",
    "current_price",
    "market_value",
    "unrealized_pnl",
    "realized_pnl",
    "return_percent",
    "last_updated_utc",
    "paper_only",
)

AI_RUN_FIELDS = (
    "run_key",
    "started_utc",
    "finished_utc",
    "success",
    "enabled",
    "eligible_transaction_count",
    "skipped_existing_count",
    "attempted_count",
    "completed_count",
    "high_priority_count",
    "watchlist_count",
    "weak_signal_count",
    "archive_count",
    "alerted_count",
    "paper_positions_opened",
    "paper_positions_updated",
    "paper_positions_closed",
    "errors",
    "warnings",
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


def load_ai(directory: Path | None) -> dict[str, Any]:
    if directory is None or not directory.exists():
        return {"analyses": [], "portfolio": [], "runs": [], "state": {}}

    analyses = latest_by(read_jsonl(directory / "analyses.jsonl"), "trade_id")
    portfolio_records = latest_by(read_jsonl(directory / "paper-portfolio.jsonl"), "position_id")
    portfolio = {str(item.get("position_id") or ""): dict(item) for item in portfolio_records if item.get("position_id")}
    runs = latest_by(read_jsonl(directory / "runs.jsonl"), "run_key")
    state = read_json_object(directory / "state.json")
    state_positions = state.get("positions") or {}
    if isinstance(state_positions, dict):
        for position_id, position in state_positions.items():
            if isinstance(position, dict):
                portfolio[str(position_id)] = dict(position)
    return {
        "analyses": analyses,
        "portfolio": list(portfolio.values()),
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
    ai: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filings = legislative["filings"] + executive["filings"]
    transactions = legislative["transactions"] + executive["transactions"]
    reviews = legislative["reviews"] + executive["reviews"]
    runs = legislative["runs"] + executive["runs"]
    ai = ai or {"analyses": [], "portfolio": [], "runs": [], "state": {}}
    analyses = latest_by(ai.get("analyses", []), "trade_id")
    portfolio = latest_by(ai.get("portfolio", []), "position_id")
    ai_runs = latest_by(ai.get("runs", []), "run_key")

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
    analyses.sort(key=lambda item: date_sort_value(item, "analyzed_at_utc", "analysis_id"), reverse=True)
    portfolio.sort(key=lambda item: date_sort_value(item, "opened_at_utc", "position_id"), reverse=True)
    ai_runs.sort(key=lambda item: date_sort_value(item, "finished_utc", "run_key"), reverse=True)

    status_counts = Counter(str(item.get("status") or "unknown") for item in filings)
    transaction_type_counts = Counter(
        str(item.get("transaction_type") or "Unknown") for item in transactions
    )
    purchase_count = sum(
        str(item.get("transaction_type") or "") == "Purchase" for item in transactions
    )
    manual_test_filing_count = sum(bool(item.get("is_synthetic_test")) for item in filings)
    manual_test_transaction_count = sum(
        bool(item.get("is_synthetic_test")) for item in transactions
    )
    classification_counts = Counter(
        str(item.get("classification") or "unknown") for item in analyses
    )
    direction_counts = Counter(
        str(item.get("signal_direction") or "unknown") for item in analyses
    )
    high_priority_bullish_count = sum(
        str(item.get("classification") or "") == "high_priority"
        and str(item.get("signal_direction") or "") == "bullish"
        for item in analyses
    )
    high_priority_bearish_count = sum(
        str(item.get("classification") or "") == "high_priority"
        and str(item.get("signal_direction") or "") == "bearish"
        for item in analyses
    )
    open_positions = [item for item in portfolio if str(item.get("status") or "") == "open"]
    closed_positions = [item for item in portfolio if str(item.get("status") or "") == "closed"]
    open_paper_pnl = sum(float(item.get("unrealized_pnl") or 0) for item in open_positions)
    realized_paper_pnl = sum(float(item.get("realized_pnl") or 0) for item in closed_positions)
    generated_utc = utc_now_iso()
    latest_timestamp = max_timestamp(
        [
            *(str(item.get("updated_at_utc") or "") for item in filings),
            *(str(item.get("observed_at_utc") or "") for item in transactions),
            *(str(item.get("observed_at_utc") or "") for item in reviews),
            *(str(item.get("finished_utc") or "") for item in runs),
            *(str(item.get("analyzed_at_utc") or "") for item in analyses),
            *(str(item.get("last_updated_utc") or item.get("opened_at_utc") or "") for item in portfolio),
            *(str(item.get("finished_utc") or "") for item in ai_runs),
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
        "manual_test_filing_count": manual_test_filing_count,
        "manual_test_transaction_count": manual_test_transaction_count,
        "review_count": len(reviews),
        "run_count": len(runs),
        "analysis_count": len(analyses),
        "high_priority_count": classification_counts.get("high_priority", 0),
        "high_priority_bullish_count": high_priority_bullish_count,
        "high_priority_bearish_count": high_priority_bearish_count,
        "watchlist_count": classification_counts.get("watchlist", 0),
        "direction_counts": dict(sorted(direction_counts.items())),
        "open_paper_position_count": len(open_positions),
        "closed_paper_position_count": len(closed_positions),
        "open_paper_pnl": round(open_paper_pnl, 2),
        "realized_paper_pnl": round(realized_paper_pnl, 2),
        "classification_counts": dict(sorted(classification_counts.items())),
        "ai_last_success_utc": str((ai.get("state") or {}).get("last_success_utc") or ""),
        "status_counts": dict(sorted(status_counts.items())),
        "transaction_type_counts": dict(sorted(transaction_type_counts.items())),
        "sources": sources,
        "coverage_note": (
            "Cataloged filings show what the tracker can currently see. A 'Cataloged only' "
            "record predates transaction backfill and has not necessarily been parsed. "
            "AI scores are evidence-constrained research rankings and all positions are simulated."
        ),
    }
    return {
        "summary": summary,
        "filings": filings,
        "transactions": transactions,
        "reviews": reviews,
        "runs": runs,
        "analyses": analyses,
        "portfolio": portfolio,
        "ai_runs": ai_runs,
    }


INDEX_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark light">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
  <meta name="description" content="PolitiTrack official government financial disclosure filing review dashboard">
  <title>PolitiTrack Government Trade Monitor</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <div>
      <p class="eyebrow">Official-source disclosure monitor</p>
      <h1>PolitiTrack Government Trade Monitor</h1>
      <p class="subtitle">House, Senate, and Executive-branch filing inventory, transactions, review items, and tracker health.</p>
    </div>
    <div class="header-actions">
      <a class="button secondary" href="wallboard.html">Wallboard</a>
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

    <section id="manual-test-notice" class="notice" aria-label="Manual Test notice" hidden>
      <strong>Manual Test preview:</strong>
      <span id="manual-test-note">This temporary dashboard contains synthetic test data.</span>
    </section>

    <section class="summary-grid" aria-label="Summary">
      <article class="metric-card"><span>Cataloged filings</span><strong id="filing-count">—</strong></article>
      <article class="metric-card"><span>Parsed transactions</span><strong id="transaction-count">—</strong></article>
      <article class="metric-card"><span>Purchases</span><strong id="purchase-count">—</strong></article>
      <article class="metric-card"><span>Review queue</span><strong id="review-count">—</strong></article>
      <article class="metric-card"><span>AI analyses</span><strong id="analysis-count">—</strong></article>
      <article class="metric-card"><span>High-priority signals</span><strong id="high-priority-count">—</strong></article>
      <article class="metric-card"><span>Open paper positions</span><strong id="open-position-count">—</strong></article>
      <article class="metric-card"><span>Open paper P&amp;L</span><strong id="paper-pnl">—</strong></article>
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
      <button class="tab active" data-panel="ai" type="button">AI signals</button>
      <button class="tab" data-panel="portfolio" type="button">Paper portfolio</button>
      <button class="tab" data-panel="filings" type="button">Filings</button>
      <button class="tab" data-panel="transactions" type="button">Transactions</button>
      <button class="tab" data-panel="reviews" type="button">Review queue</button>
      <button class="tab" data-panel="runs" type="button">Run history</button>
    </nav>

    <section id="panel-ai" class="panel active">
      <div class="panel-header">
        <div><h2>AI-ranked directional signals</h2><p>Purchases are bullish candidates; sales are bearish/caution signals. Scores measure signal strength using deterministic rules, market data, SEC context, and structured AI analysis.</p></div>
        <a class="download-link" href="data/ai-analyses.csv">Download CSV</a>
      </div>
      <div class="notice compact"><strong>Paper research only:</strong><span>No brokerage orders are created. Open the official filing and supporting evidence before acting.</span></div>
      <div class="controls">
        <label>Search<input id="ai-search" type="search" placeholder="Ticker, filer, owner, rationale…"></label>
        <label>Class<select id="ai-classification"><option value="">All classes</option></select></label>
        <label>Source<select id="ai-source"><option value="">All sources</option></select></label>
      </div>
      <p id="ai-count-label" class="result-count"></p>
      <div class="table-wrap"><table><thead><tr><th>Analyzed</th><th>Signal</th><th>Direction</th><th>Score</th><th>Filer / owner</th><th>Disclosure</th><th>Market / entry review</th><th>Analysis</th><th>Evidence</th></tr></thead><tbody id="ai-body"></tbody></table></div>
      <button id="ai-more" class="more-button" type="button">Show more</button>
    </section>

    <section id="panel-portfolio" class="panel">
      <div class="panel-header">
        <div><h2>Paper-research portfolio</h2><p>Simulated positions opened only when deterministic score and entry rules qualify. Performance is measured from the first investable quote seen by PolitiTrack.</p></div>
        <a class="download-link" href="data/paper-portfolio.csv">Download CSV</a>
      </div>
      <div class="controls">
        <label>Search<input id="portfolio-search" type="search" placeholder="Ticker, filer, owner…"></label>
        <label>Status<select id="portfolio-status"><option value="">All statuses</option></select></label>
      </div>
      <p id="portfolio-count-label" class="result-count"></p>
      <div class="table-wrap"><table><thead><tr><th>Opened</th><th>Ticker</th><th>Status</th><th>Score</th><th>Filer / owner</th><th>Entry</th><th>Current / exit</th><th>Quantity</th><th>P&amp;L</th><th>Evaluation horizon</th><th>Filing</th></tr></thead><tbody id="portfolio-body"></tbody></table></div>
      <button id="portfolio-more" class="more-button" type="button">Show more</button>
    </section>

    <section id="panel-filings" class="panel">
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

WALLBOARD_HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="dark">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
  <meta name="description" content="PolitiTrack portrait and ultrawide government trade intelligence wallboard">
  <title>PolitiTrack Intelligence Wallboard</title>
  <link rel="stylesheet" href="wallboard.css">
</head>
<body>
  <header class="wall-header">
    <div class="identity">
      <p class="eyebrow">Official-source monitoring · AI research queue</p>
      <h1>PolitiTrack Intelligence Wallboard</h1>
      <p class="subtitle">New filings, ranked purchase candidates, simulated positions, and agent health.</p>
    </div>
    <div id="overall-state" class="overall-state unknown" aria-live="polite">
      <span class="pulse-dot"></span>
      <span id="overall-state-label">Loading systems</span>
    </div>
    <div class="clock-block" aria-label="Current time and dashboard freshness">
      <strong id="clock">--:--</strong>
      <span id="clock-date">—</span>
      <span id="freshness">Loading data…</span>
      <span id="refresh-countdown">Refresh pending</span>
    </div>
    <div class="wall-actions">
      <a class="wall-button secondary" href="index.html">Review dashboard</a>
      <button id="fullscreen-button" class="wall-button" type="button">Full screen</button>
    </div>
  </header>

  <section id="error-banner" class="error-banner" hidden aria-live="assertive"></section>

  <main class="wall-layout">
    <section class="wall-panel overview-panel" aria-labelledby="overview-title">
      <div class="panel-heading compact-heading">
        <div>
          <p class="eyebrow">Collector and analyst status</p>
          <h2 id="overview-title">Operations</h2>
        </div>
        <span id="data-through" class="quiet">—</span>
      </div>
      <div id="source-strip" class="source-strip"></div>
      <div class="metric-grid" aria-label="Key metrics">
        <article class="metric-card priority"><span>High priority</span><strong id="metric-high">—</strong></article>
        <article class="metric-card watch"><span>Watchlist</span><strong id="metric-watch">—</strong></article>
        <article class="metric-card"><span>New filings · 24h</span><strong id="metric-new-filings">—</strong></article>
        <article class="metric-card"><span>Review queue</span><strong id="metric-review">—</strong></article>
        <article class="metric-card"><span>Open paper positions</span><strong id="metric-open-positions">—</strong></article>
        <article class="metric-card"><span>Open paper P&amp;L</span><strong id="metric-pnl">—</strong></article>
      </div>
    </section>

    <section class="wall-panel candidates-panel" aria-labelledby="candidates-title">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Primary decision queue</p>
          <h2 id="candidates-title">AI-ranked signals</h2>
        </div>
        <span id="candidate-count" class="section-count">—</span>
      </div>
      <div id="candidate-list" class="candidate-list"></div>
    </section>

    <section class="wall-panel portfolio-panel" aria-labelledby="portfolio-title">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Prospective validation</p>
          <h2 id="portfolio-title">Paper positions</h2>
        </div>
        <span id="portfolio-count" class="section-count">—</span>
      </div>
      <div id="portfolio-list" class="compact-list"></div>
    </section>

    <section class="wall-panel filings-panel" aria-labelledby="filings-title">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Newest official records</p>
          <h2 id="filings-title">Recent filings</h2>
        </div>
        <span id="filing-count" class="section-count">—</span>
      </div>
      <div id="filing-list" class="compact-list"></div>
    </section>

    <section class="wall-panel operations-panel" aria-labelledby="activity-title">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Automation and exceptions</p>
          <h2 id="activity-title">Agent activity</h2>
        </div>
      </div>
      <div class="operations-columns">
        <div>
          <h3>Latest runs</h3>
          <div id="run-list" class="micro-list"></div>
        </div>
        <div>
          <h3>Needs review</h3>
          <div id="review-list" class="micro-list"></div>
        </div>
      </div>
    </section>
  </main>

  <footer class="wall-footer">
    <span>Research wallboard only. Open the official filing before relying on an extracted transaction or AI ranking.</span>
    <span id="orientation-label">Portrait wallboard · 1080 × 3840 target</span>
  </footer>

  <script src="wallboard.js" defer></script>
</body>
</html>
'''

WALLBOARD_CSS = r''':root {
  --bg: #030914;
  --surface: #0a1624;
  --surface-2: #102238;
  --surface-3: #142a43;
  --border: #294866;
  --text: #f3f8fc;
  --muted: #94a9bc;
  --blue: #68bcff;
  --blue-soft: #b3ddff;
  --green: #65e3a0;
  --amber: #ffd072;
  --red: #ff7c7c;
  --shadow: 0 18px 55px rgba(0, 0, 0, .32);
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: clamp(16px, 1.7vw, 21px);
}

* { box-sizing: border-box; }
html { min-height: 100%; background: var(--bg); color: var(--text); }
body {
  margin: 0;
  min-height: 100vh;
  background:
    radial-gradient(circle at 88% 4%, rgba(44, 111, 166, .34), transparent 25rem),
    radial-gradient(circle at 10% 78%, rgba(32, 101, 83, .18), transparent 32rem),
    var(--bg);
}
a { color: var(--blue-soft); }
button, a { -webkit-tap-highlight-color: transparent; }

.wall-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    "identity clock"
    "state actions";
  align-items: center;
  gap: .85rem 1.1rem;
  padding: max(1rem, env(safe-area-inset-top)) max(1.15rem, env(safe-area-inset-right)) .85rem max(1.15rem, env(safe-area-inset-left));
  border-bottom: 1px solid rgba(79, 117, 151, .48);
  background: rgba(4, 12, 23, .92);
  backdrop-filter: blur(16px);
}
.identity { grid-area: identity; min-width: 0; }
.identity h1 { margin: 0; font-size: clamp(1.65rem, 4.6vw, 3rem); line-height: 1; letter-spacing: -.035em; }
.subtitle { margin: .35rem 0 0; color: var(--muted); font-size: .9rem; }
.eyebrow { margin: 0 0 .28rem; color: var(--blue); font-size: .66rem; font-weight: 850; letter-spacing: .14em; text-transform: uppercase; }

.overall-state {
  grid-area: state;
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: .55rem;
  min-height: 2.3rem;
  padding: .52rem .8rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  font-weight: 800;
}
.overall-state.up { color: var(--green); border-color: rgba(101, 227, 160, .55); }
.overall-state.down { color: var(--red); border-color: rgba(255, 124, 124, .55); }
.overall-state.unknown { color: var(--amber); border-color: rgba(255, 208, 114, .55); }
.pulse-dot { width: .72rem; height: .72rem; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 .28rem rgba(255,255,255,.06); }
.overall-state.up .pulse-dot { animation: pulse 2.4s infinite; }
@keyframes pulse { 50% { box-shadow: 0 0 0 .5rem rgba(101, 227, 160, 0); } }

.clock-block {
  grid-area: clock;
  display: grid;
  justify-items: end;
  align-content: center;
  white-space: nowrap;
}
.clock-block strong { font-size: clamp(1.8rem, 4.8vw, 3rem); line-height: .95; letter-spacing: -.04em; }
.clock-block span { color: var(--muted); font-size: .7rem; line-height: 1.45; }
#freshness.fresh { color: var(--green); }
#freshness.stale { color: var(--amber); }
#freshness.old { color: var(--red); }

.wall-actions { grid-area: actions; display: flex; justify-content: flex-end; gap: .55rem; }
.wall-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.4rem;
  padding: .58rem .85rem;
  border: 1px solid var(--blue);
  border-radius: .6rem;
  background: var(--blue);
  color: #06111d;
  font: inherit;
  font-size: .75rem;
  font-weight: 850;
  text-decoration: none;
  cursor: pointer;
}
.wall-button.secondary { border-color: var(--border); background: var(--surface-2); color: var(--text); }

.error-banner {
  margin: .7rem 1rem 0;
  padding: .7rem .9rem;
  border: 1px solid rgba(255, 124, 124, .58);
  border-radius: .65rem;
  background: rgba(91, 23, 31, .82);
  color: #ffd6d6;
  font-weight: 750;
}

.wall-layout {
  display: grid;
  grid-template-areas:
    "overview"
    "candidates"
    "portfolio"
    "filings"
    "operations";
  gap: .8rem;
  padding: .8rem 1rem;
}
.wall-panel {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  padding: .9rem;
  border: 1px solid var(--border);
  border-radius: .85rem;
  background: linear-gradient(145deg, rgba(14, 30, 48, .97), rgba(7, 19, 32, .97));
  box-shadow: var(--shadow);
}
.overview-panel { grid-area: overview; }
.candidates-panel { grid-area: candidates; }
.portfolio-panel { grid-area: portfolio; }
.filings-panel { grid-area: filings; }
.operations-panel { grid-area: operations; }

.panel-heading { display: flex; align-items: end; justify-content: space-between; gap: 1rem; margin-bottom: .65rem; }
.panel-heading h2 { margin: 0; font-size: clamp(1.2rem, 3.1vw, 1.9rem); line-height: 1; letter-spacing: -.025em; }
.compact-heading { margin-bottom: .5rem; }
.section-count, .quiet { color: var(--muted); font-size: .74rem; text-align: right; }

.source-strip { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; margin-bottom: .62rem; }
.source-chip {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: .48rem;
  min-width: 0;
  padding: .55rem .62rem;
  border: 1px solid var(--border);
  border-radius: .58rem;
  background: var(--surface-2);
}
.source-chip > div { min-width: 0; }
.source-chip .status-dot { width: .65rem; height: .65rem; border-radius: 50%; background: var(--amber); }
.source-chip.up .status-dot { background: var(--green); }
.source-chip.down .status-dot { background: var(--red); }
.source-chip strong { font-size: .78rem; }
.source-chip small { display: block; width: 100%; overflow: hidden; color: var(--muted); font-size: .61rem; text-overflow: ellipsis; white-space: nowrap; }
.source-chip b { color: var(--blue-soft); font-size: .72rem; }

.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .5rem; }
.metric-card {
  min-height: 4.25rem;
  padding: .6rem .68rem;
  border: 1px solid rgba(66, 104, 139, .75);
  border-radius: .58rem;
  background: rgba(16, 34, 56, .82);
}
.metric-card span { display: block; color: var(--muted); font-size: .65rem; font-weight: 760; letter-spacing: .045em; text-transform: uppercase; }
.metric-card strong { display: block; margin-top: .28rem; font-size: clamp(1.45rem, 4.2vw, 2.35rem); line-height: .95; }
.metric-card.priority strong { color: var(--green); }
.metric-card.watch strong { color: var(--blue); }
.money-positive { color: var(--green); }
.money-negative { color: var(--red); }
.money-neutral { color: var(--muted); }

.candidate-list { display: grid; grid-template-columns: 1fr; gap: .55rem; min-height: 0; }
.candidate-card {
  display: grid;
  grid-template-columns: 5rem minmax(0, 1fr) auto;
  align-items: center;
  gap: .68rem;
  min-width: 0;
  padding: .68rem;
  border: 1px solid rgba(72, 111, 146, .82);
  border-left-width: .28rem;
  border-radius: .7rem;
  background: rgba(12, 27, 44, .9);
}
.candidate-card.high_priority { border-left-color: var(--green); }
.candidate-card.watchlist { border-left-color: var(--blue); }
.candidate-card.weak_signal { border-left-color: var(--amber); }
.candidate-card.archive { border-left-color: var(--muted); opacity: .82; }
.candidate-score {
  display: grid;
  place-items: center;
  align-content: center;
  width: 4.7rem;
  height: 4.7rem;
  border: .14rem solid var(--border);
  border-radius: 50%;
  background: var(--surface-3);
}
.candidate-score strong { font-size: 1.55rem; line-height: 1; }
.candidate-score span { color: var(--muted); font-size: .58rem; text-transform: uppercase; }
.candidate-card.high_priority .candidate-score { border-color: rgba(101, 227, 160, .72); color: var(--green); }
.candidate-card.watchlist .candidate-score { border-color: rgba(104, 188, 255, .72); color: var(--blue); }
.candidate-body { min-width: 0; }
.candidate-title { display: flex; align-items: baseline; gap: .55rem; min-width: 0; }
.candidate-title strong { font-size: 1.35rem; color: var(--text); }
.candidate-title span { overflow: hidden; color: var(--muted); font-size: .74rem; text-overflow: ellipsis; white-space: nowrap; }
.candidate-meta { margin-top: .15rem; color: var(--blue-soft); font-size: .69rem; }
.candidate-summary {
  display: -webkit-box;
  margin: .28rem 0 0;
  overflow: hidden;
  color: #dbe8f2;
  font-size: .73rem;
  line-height: 1.32;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.candidate-entry { display: grid; justify-items: end; gap: .22rem; min-width: 7.5rem; text-align: right; }
.candidate-entry strong { color: var(--amber); font-size: .76rem; }
.candidate-entry span { color: var(--muted); font-size: .62rem; }
.candidate-entry a { font-size: .66rem; font-weight: 800; }

.compact-list, .micro-list { display: grid; gap: .44rem; min-height: 0; }
.compact-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: .7rem;
  min-width: 0;
  padding: .58rem .65rem;
  border: 1px solid rgba(57, 89, 119, .75);
  border-radius: .58rem;
  background: rgba(11, 26, 42, .78);
  text-decoration: none;
}
.compact-row:hover { background: rgba(25, 53, 82, .86); }
.row-primary { min-width: 0; }
.row-primary strong { display: block; overflow: hidden; color: var(--text); font-size: .82rem; text-overflow: ellipsis; white-space: nowrap; }
.row-primary span { display: block; overflow: hidden; margin-top: .12rem; color: var(--muted); font-size: .66rem; text-overflow: ellipsis; white-space: nowrap; }
.row-secondary { display: grid; justify-items: end; gap: .12rem; white-space: nowrap; }
.row-secondary strong { font-size: .76rem; }
.row-secondary span { color: var(--muted); font-size: .61rem; }

.operations-columns { display: grid; grid-template-columns: 1fr 1fr; gap: .65rem; min-height: 0; }
.operations-columns h3 { margin: 0 0 .45rem; color: var(--blue-soft); font-size: .74rem; letter-spacing: .06em; text-transform: uppercase; }
.micro-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: .45rem;
  min-width: 0;
  padding: .46rem .5rem;
  border: 1px solid rgba(57, 89, 119, .7);
  border-radius: .5rem;
  background: rgba(10, 24, 39, .76);
  font-size: .66rem;
}
.micro-row .micro-status { width: .6rem; height: .6rem; border-radius: 50%; background: var(--amber); }
.micro-row .micro-status.up { background: var(--green); }
.micro-row .micro-status.down { background: var(--red); }
.micro-row strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.micro-row span:last-child { color: var(--muted); white-space: nowrap; }

.empty-state {
  display: grid;
  place-items: center;
  min-height: 7rem;
  padding: 1rem;
  border: 1px dashed var(--border);
  border-radius: .65rem;
  color: var(--muted);
  text-align: center;
}

.wall-footer {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: .55rem max(1rem, env(safe-area-inset-right)) max(.65rem, env(safe-area-inset-bottom)) max(1rem, env(safe-area-inset-left));
  border-top: 1px solid rgba(79, 117, 151, .4);
  color: var(--muted);
  font-size: .59rem;
}

/* Samsung CHG90 rotated on the MI-12009: effective 1080 × 3840 portrait canvas. */
@media (orientation: portrait) and (min-height: 1400px) {
  body { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; height: 100dvh; min-height: 0; overflow: hidden; }
  .wall-layout {
    grid-template-rows: 1.1fr 2.35fr 1fr 1.2fr 1.15fr;
    min-height: 0;
    overflow: hidden;
  }
  .wall-panel { height: 100%; }
  .candidate-list, .compact-list, .operations-columns { overflow: hidden; }
}

/* Native 3840 × 1080 landscape fallback when the arm is rotated back. */
@media (orientation: landscape) and (min-aspect-ratio: 12/5) {
  :root { font-size: clamp(15px, .58vw, 21px); }
  body { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; height: 100dvh; min-height: 0; overflow: hidden; }
  .wall-header {
    grid-template-columns: minmax(30rem, 1.3fr) auto auto auto;
    grid-template-areas: "identity state clock actions";
    padding-top: .72rem;
    padding-bottom: .62rem;
  }
  .identity h1 { font-size: 2.25rem; }
  .subtitle { font-size: .75rem; }
  .wall-layout {
    grid-template-columns: 1.02fr 1.9fr 1.18fr;
    grid-template-rows: 1fr 1fr;
    grid-template-areas:
      "overview candidates portfolio"
      "filings candidates operations";
    min-height: 0;
    overflow: hidden;
  }
  .wall-panel { height: 100%; }
  .candidate-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .candidate-card { grid-template-columns: 4.25rem minmax(0, 1fr); }
  .candidate-score { width: 4rem; height: 4rem; }
  .candidate-entry { grid-column: 2; grid-row: 2; display: flex; justify-content: space-between; justify-items: initial; min-width: 0; text-align: left; }
  .candidate-summary { -webkit-line-clamp: 1; }
  .source-strip { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .metric-card { min-height: 3.45rem; padding: .45rem .55rem; }
  .metric-card strong { margin-top: .16rem; font-size: 1.65rem; }
  .compact-row { padding: .43rem .55rem; }
}

@media (max-width: 760px) {
  .wall-header { grid-template-columns: 1fr; grid-template-areas: "identity" "state" "clock" "actions"; }
  .clock-block { justify-items: start; }
  .wall-actions { justify-content: flex-start; }
  .candidate-card { grid-template-columns: 4.2rem minmax(0, 1fr); }
  .candidate-score { width: 4rem; height: 4rem; }
  .candidate-entry { grid-column: 2; justify-items: start; text-align: left; }
  .operations-columns { grid-template-columns: 1fr; }
  .wall-footer { flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  .overall-state.up .pulse-dot { animation: none; }
}
'''

WALLBOARD_JS = r'''const DEFAULT_REFRESH_SECONDS = 300;
const params = new URLSearchParams(window.location.search);
const requestedRefresh = Number(params.get("refresh") || DEFAULT_REFRESH_SECONDS);
const refreshSeconds = Math.min(1800, Math.max(60, Number.isFinite(requestedRefresh) ? requestedRefresh : DEFAULT_REFRESH_SECONDS));

const state = {
  data: null,
  lastLoadAt: null,
  nextRefreshAt: Date.now() + refreshSeconds * 1000,
  wakeLock: null,
};

const el = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const safeUrl = value => {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
};
const titleCase = value => String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase());
const number = value => Number(value || 0).toLocaleString();
const currency = value => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString([], { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 2 });
};
const price = value => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString([], { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });
};
const percent = value => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(2)}%`;
};
const parseDate = value => {
  if (!value) return null;
  const raw = String(value);
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  const date = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date;
};
const formatDate = value => {
  const date = parseDate(value);
  if (!date) return String(value || "—");
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
};
const relativeAge = value => {
  const date = parseDate(value);
  if (!date) return "no timestamp";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
};
const pnlClass = value => Number(value || 0) > 0 ? "money-positive" : Number(value || 0) < 0 ? "money-negative" : "money-neutral";
const classificationRank = value => ({ high_priority: 0, watchlist: 1, weak_signal: 2, archive: 3 }[String(value || "archive")] ?? 4);
const isSuperUltrawide = () => window.innerWidth / Math.max(1, window.innerHeight) >= 2.4;

async function checkedJson(path) {
  const response = await fetch(`${path}?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}

async function loadData() {
  const [summary, filings, transactions, reviews, trackerRuns, analyses, portfolio, aiRuns] = await Promise.all([
    checkedJson("data/summary.json"),
    checkedJson("data/filings.json"),
    checkedJson("data/transactions.json"),
    checkedJson("data/pending-reviews.json"),
    checkedJson("data/runs.json"),
    checkedJson("data/ai-analyses.json"),
    checkedJson("data/paper-portfolio.json"),
    checkedJson("data/ai-runs.json"),
  ]);

  const normalizedAiRuns = aiRuns.map(row => ({ ...row, branch: "ai analyst" }));
  const runs = [...trackerRuns, ...normalizedAiRuns].sort((a, b) => String(b.finished_utc || "").localeCompare(String(a.finished_utc || "")));
  state.data = { summary, filings, transactions, reviews, analyses, portfolio, runs, aiRuns };
  state.lastLoadAt = new Date();
  state.nextRefreshAt = Date.now() + refreshSeconds * 1000;
  el("error-banner").hidden = true;
  renderAll();
}

function sourceStatus(source) {
  if (source?.latest_success === true) return "up";
  if (source?.latest_success === false) return "down";
  return "unknown";
}

function renderHeader() {
  const summary = state.data.summary;
  const latestAiRun = state.data.aiRuns[0] || null;
  const statuses = Object.values(summary.sources || {}).map(sourceStatus);
  statuses.push(latestAiRun ? (latestAiRun.success ? "up" : "down") : (summary.ai_last_success_utc ? "up" : "unknown"));

  const generated = parseDate(summary.generated_utc);
  const ageMinutes = generated ? (Date.now() - generated.getTime()) / 60000 : Infinity;
  let overall = "up";
  let label = "All systems operational";
  if (statuses.includes("down")) {
    overall = "down";
    label = "Attention required";
  } else if (statuses.includes("unknown") || ageMinutes > 90) {
    overall = "unknown";
    label = ageMinutes > 90 ? "Dashboard data is stale" : "Partial status available";
  }
  const badge = el("overall-state");
  badge.className = `overall-state ${overall}`;
  el("overall-state-label").textContent = label;

  const freshness = el("freshness");
  freshness.textContent = `Dashboard ${relativeAge(summary.generated_utc)}`;
  freshness.className = ageMinutes <= 25 ? "fresh" : ageMinutes <= 90 ? "stale" : "old";
  el("data-through").textContent = `Data through ${formatDate(summary.data_through_utc)}`;
}

function renderSources() {
  const summary = state.data.summary;
  const sources = Object.values(summary.sources || {});
  const latestAiRun = state.data.aiRuns[0] || null;
  sources.push({
    source: "ai",
    filing_count: summary.analysis_count,
    visible_count: latestAiRun?.completed_count || 0,
    last_success_utc: summary.ai_last_success_utc,
    last_run_utc: latestAiRun?.finished_utc || "",
    latest_success: latestAiRun ? Boolean(latestAiRun.success) : (summary.ai_last_success_utc ? true : null),
    latest_error: Array.isArray(latestAiRun?.errors) ? latestAiRun.errors.join("; ") : "",
  });

  el("source-strip").innerHTML = sources.map(source => {
    const status = sourceStatus(source);
    const label = String(source.source || "").toLowerCase() === "ai" ? "AI analyst" : titleCase(source.source);
    const count = String(source.source || "").toLowerCase() === "ai" ? source.filing_count : source.visible_count;
    const detail = source.latest_error || `Last success ${relativeAge(source.last_success_utc)}`;
    return `<article class="source-chip ${status}" title="${escapeHtml(detail)}">
      <span class="status-dot"></span>
      <div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(detail)}</small></div>
      <b>${number(count)}</b>
    </article>`;
  }).join("");
}

function renderMetrics() {
  const summary = state.data.summary;
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  const newFilings = state.data.filings.filter(row => {
    const date = parseDate(row.first_seen_utc || row.updated_at_utc);
    return date && date.getTime() >= cutoff && String(row.status || "") !== "cataloged";
  }).length;
  el("metric-high").textContent = number(summary.high_priority_count);
  el("metric-watch").textContent = number(summary.watchlist_count);
  el("metric-new-filings").textContent = number(newFilings);
  el("metric-review").textContent = number(summary.review_count);
  el("metric-open-positions").textContent = number(summary.open_paper_position_count);
  const pnl = Number(summary.open_paper_pnl || 0);
  const pnlNode = el("metric-pnl");
  pnlNode.textContent = currency(pnl);
  pnlNode.className = pnlClass(pnl);
}

function renderCandidates() {
  const analyses = [...state.data.analyses]
    .filter(row => ["high_priority", "watchlist", "weak_signal"].includes(String(row.classification || "")))
    .sort((a, b) => classificationRank(a.classification) - classificationRank(b.classification) || Number(b.score || 0) - Number(a.score || 0) || String(b.analyzed_at_utc || "").localeCompare(String(a.analyzed_at_utc || "")));
  const rows = analyses.slice(0, 6);
  el("candidate-count").textContent = `${number(state.data.summary.high_priority_bullish_count)} bullish high · ${number(state.data.summary.high_priority_bearish_count)} bearish high · ${number(state.data.summary.watchlist_count)} watch`;
  if (!rows.length) {
    el("candidate-list").innerHTML = `<div class="empty-state">No AI-ranked directional signals are available yet. This panel will populate after a qualifying purchase or sale is parsed and analyzed.</div>`;
    return;
  }
  el("candidate-list").innerHTML = rows.map(row => {
    const entry = row.entry_plan || {};
    const market = row.market || {};
    const filingUrl = safeUrl(row.source_url);
    const band = entry.review_band_low && entry.review_band_high ? `${price(entry.review_band_low)}–${price(entry.review_band_high)}` : "No review band";
    const entryStatus = titleCase(entry.entry_status || "review pending");
    const meta = [row.filer, row.owner, row.amount, row.source ? titleCase(row.source) : ""].filter(Boolean).join(" · ");
    const summary = row.ai?.analysis_summary || "Analysis summary pending.";
    return `<article class="candidate-card ${escapeHtml(row.classification || "archive")}">
      <div class="candidate-score"><strong>${number(row.score)}</strong><span>${escapeHtml(titleCase(row.classification || "archive"))}</span></div>
      <div class="candidate-body">
        <div class="candidate-title"><strong>${escapeHtml(row.ticker || "?")}</strong><span>${escapeHtml(row.asset || "Unresolved asset")}</span></div>
        <div class="candidate-meta">${escapeHtml(meta || "Unknown filer")}</div>
        <p class="candidate-summary">${escapeHtml(summary)}</p>
      </div>
      <div class="candidate-entry">
        <strong>${escapeHtml(entryStatus)}</strong>
        <span>${price(market.current_price)} current</span>
        <span>${escapeHtml(band)}</span>
        <span>${formatDate(row.transaction_date)} trade</span>
        ${filingUrl ? `<a href="${escapeHtml(filingUrl)}" target="_blank" rel="noopener">Official filing</a>` : ""}
      </div>
    </article>`;
  }).join("");
}

function renderPortfolio() {
  const rows = [...state.data.portfolio]
    .filter(row => String(row.status || "") === "open")
    .sort((a, b) => Number(b.score || 0) - Number(a.score || 0) || Number(b.unrealized_pnl || 0) - Number(a.unrealized_pnl || 0))
    .slice(0, 6);
  el("portfolio-count").textContent = `${number(state.data.summary.open_paper_position_count)} open`;
  if (!rows.length) {
    el("portfolio-list").innerHTML = `<div class="empty-state">No simulated positions are open.</div>`;
    return;
  }
  el("portfolio-list").innerHTML = rows.map(row => {
    const url = safeUrl(row.source_url);
    const pnl = Number(row.unrealized_pnl || 0);
    const content = `<div class="row-primary"><strong>${escapeHtml(row.ticker || "?")} · ${escapeHtml(row.filer || "Unknown filer")}</strong><span>${escapeHtml(row.owner || "Unknown owner")} · score ${number(row.score)} · entry ${price(row.entry_price)}</span></div><div class="row-secondary"><strong class="${pnlClass(pnl)}">${currency(pnl)}</strong><span>${percent(row.return_percent)} · ${price(row.current_price)}</span></div>`;
    return url ? `<a class="compact-row" href="${escapeHtml(url)}" target="_blank" rel="noopener">${content}</a>` : `<div class="compact-row">${content}</div>`;
  }).join("");
}

function renderFilings() {
  const rows = [...state.data.filings]
    .sort((a, b) => String(b.updated_at_utc || b.first_seen_utc || b.filed_date || "").localeCompare(String(a.updated_at_utc || a.first_seen_utc || a.filed_date || "")))
    .slice(0, isSuperUltrawide() ? 4 : 7);
  el("filing-count").textContent = `${number(state.data.summary.filing_count)} cataloged`;
  if (!rows.length) {
    el("filing-list").innerHTML = `<div class="empty-state">No filing inventory is available.</div>`;
    return;
  }
  el("filing-list").innerHTML = rows.map(row => {
    const url = safeUrl(row.source_url);
    const counts = `${number(row.purchase_count)} buys · ${number(row.sale_count)} sales`;
    const role = [row.title, row.agency, row.district].filter(Boolean).join(" · ");
    const content = `<div class="row-primary"><strong>${escapeHtml(titleCase(row.source))} · ${escapeHtml(row.filer || "Unknown filer")}</strong><span>${escapeHtml(role || row.report_type || "Official disclosure")} · ${escapeHtml(titleCase(row.status || "unknown"))}</span></div><div class="row-secondary"><strong>${formatDate(row.filed_date)}</strong><span>${escapeHtml(counts)}</span></div>`;
    return url ? `<a class="compact-row" href="${escapeHtml(url)}" target="_blank" rel="noopener">${content}</a>` : `<div class="compact-row">${content}</div>`;
  }).join("");
}

function renderOperations() {
  const runs = state.data.runs.slice(0, 6);
  el("run-list").innerHTML = runs.length ? runs.map(row => {
    const status = row.success ? "up" : "down";
    const branch = titleCase(row.branch || "tracker");
    return `<div class="micro-row" title="${escapeHtml((row.errors || []).join("; "))}"><span class="micro-status ${status}"></span><strong>${escapeHtml(branch)}</strong><span>${relativeAge(row.finished_utc)}</span></div>`;
  }).join("") : `<div class="empty-state">No retained runs.</div>`;

  const reviews = state.data.reviews.slice(0, 5);
  el("review-list").innerHTML = reviews.length ? reviews.map(row => {
    const url = safeUrl(row.source_url);
    const content = `<span class="micro-status down"></span><strong>${escapeHtml(`${titleCase(row.source)} · ${row.filer || "Unknown"}`)}</strong><span>${formatDate(row.filed_date)}</span>`;
    return url ? `<a class="micro-row" href="${escapeHtml(url)}" target="_blank" rel="noopener">${content}</a>` : `<div class="micro-row">${content}</div>`;
  }).join("") : `<div class="empty-state">No manual-review items.</div>`;
}

function renderAll() {
  renderHeader();
  renderSources();
  renderMetrics();
  renderCandidates();
  renderPortfolio();
  renderFilings();
  renderOperations();
}

function updateClock() {
  const now = new Date();
  el("clock").textContent = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
  el("clock-date").textContent = now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  const remaining = Math.max(0, Math.ceil((state.nextRefreshAt - Date.now()) / 1000));
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  el("refresh-countdown").textContent = `Data refresh in ${minutes}:${String(seconds).padStart(2, "0")}`;
  if (state.data) renderHeader();
}

function updateOrientationLabel() {
  const portrait = window.innerHeight > window.innerWidth;
  const mode = portrait ? "Portrait wallboard" : window.innerWidth / window.innerHeight >= 2.4 ? "Super-ultrawide wallboard" : "Responsive wallboard";
  el("orientation-label").textContent = `${mode} · ${window.innerWidth} × ${window.innerHeight} viewport · CHG90 target 1080 × 3840 portrait`;
}

async function requestWakeLock() {
  if (!("wakeLock" in navigator)) return;
  try {
    state.wakeLock = await navigator.wakeLock.request("screen");
  } catch {
    state.wakeLock = null;
  }
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement && document.documentElement.requestFullscreen) {
      await document.documentElement.requestFullscreen();
      el("fullscreen-button").textContent = "Exit full screen";
    } else if (document.fullscreenElement && document.exitFullscreen) {
      await document.exitFullscreen();
      el("fullscreen-button").textContent = "Full screen";
    }
  } finally {
    await requestWakeLock();
  }
}

function showError(error) {
  const banner = el("error-banner");
  banner.textContent = `Wallboard refresh failed: ${error?.message || error}. Existing data remains on screen.`;
  banner.hidden = false;
  state.nextRefreshAt = Date.now() + refreshSeconds * 1000;
}

el("fullscreen-button").addEventListener("click", () => toggleFullscreen().catch(showError));
document.addEventListener("fullscreenchange", () => {
  el("fullscreen-button").textContent = document.fullscreenElement ? "Exit full screen" : "Full screen";
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && document.fullscreenElement) requestWakeLock();
});
window.addEventListener("resize", () => {
  updateOrientationLabel();
  if (state.data) renderAll();
});

setInterval(updateClock, 1000);
setInterval(() => loadData().catch(showError), refreshSeconds * 1000);
updateClock();
updateOrientationLabel();
loadData().catch(showError);
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
.notice.compact { margin-top: 8px; margin-bottom: 12px; padding: 10px 12px; font-size: .86rem; }
.score { display: inline-grid; place-items: center; min-width: 46px; height: 46px; border: 2px solid var(--border); border-radius: 50%; background: var(--surface-2); font-size: 1rem; font-weight: 850; }
.score.high_priority { color: var(--success); border-color: rgba(112, 214, 161, .7); }
.score.watchlist { color: var(--accent-2); border-color: rgba(105, 183, 255, .7); }
.score.weak_signal { color: var(--warning); border-color: rgba(242, 200, 121, .7); }
.score.archive { color: var(--muted); }
.badge.high_priority { color: var(--success); border-color: rgba(112, 214, 161, .5); }
.badge.watchlist { color: var(--accent-2); border-color: rgba(105, 183, 255, .5); }
.badge.weak_signal { color: var(--warning); border-color: rgba(242, 200, 121, .5); }
.badge.bullish { color: var(--success); border-color: rgba(112, 214, 161, .6); }
.badge.bearish { color: var(--danger); border-color: rgba(255, 140, 140, .6); }
.badge.neutral { color: var(--muted); }
.analysis-summary { min-width: 310px; max-width: 520px; line-height: 1.45; }
.analysis-summary small { display: block; margin-top: 6px; color: var(--muted); }
.evidence-links { min-width: 150px; }
.evidence-links a { display: block; margin-bottom: 5px; }
.money-positive { color: var(--success); font-weight: 750; }
.money-negative { color: var(--danger); font-weight: 750; }
.money-neutral { color: var(--muted); font-weight: 750; }
.entry-cell strong { display: block; }
.entry-cell small { display: block; margin-top: 4px; color: var(--muted); }
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
const state = {
  data: null,
  shown: {
    ai: PAGE_SIZE,
    portfolio: PAGE_SIZE,
    filings: PAGE_SIZE,
    transactions: PAGE_SIZE,
    reviews: PAGE_SIZE,
    runs: PAGE_SIZE,
  },
};

const el = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
const safeUrl = value => { try { const url = new URL(String(value)); return ["http:", "https:"].includes(url.protocol) ? url.href : ""; } catch { return ""; } };
const titleCase = value => String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const number = value => Number(value || 0).toLocaleString();
const currency = value => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString([], { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
};
const price = value => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return Number(value).toLocaleString([], { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });
};
const percent = value => {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "—";
  return `${Number(value).toFixed(2)}%`;
};
const formatDate = value => {
  if (!value) return "—";
  const raw = String(value);
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
  const d = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(raw);
  return Number.isNaN(d.getTime()) ? escapeHtml(raw) : d.toLocaleString([], { dateStyle: "medium", timeStyle: raw.includes("T") ? "short" : undefined });
};
const dictTotal = value => Object.values(value || {}).reduce((sum, item) => sum + Number(item || 0), 0);
const link = (url, text="Open") => { const clean = safeUrl(url); return clean ? `<a href="${escapeHtml(clean)}" target="_blank" rel="noopener">${escapeHtml(text)}</a>` : "—"; };
const haystack = row => Object.values(row || {}).map(value => typeof value === "object" ? JSON.stringify(value) : String(value ?? "")).join(" ").toLowerCase();
const pnlClass = value => Number(value || 0) > 0 ? "money-positive" : Number(value || 0) < 0 ? "money-negative" : "money-neutral";

async function checkedJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}

async function loadData() {
  const [summary, filings, transactions, reviews, trackerRuns, analyses, portfolio, aiRuns] = await Promise.all([
    checkedJson("data/summary.json"),
    checkedJson("data/filings.json"),
    checkedJson("data/transactions.json"),
    checkedJson("data/pending-reviews.json"),
    checkedJson("data/runs.json"),
    checkedJson("data/ai-analyses.json"),
    checkedJson("data/paper-portfolio.json"),
    checkedJson("data/ai-runs.json"),
  ]);
  const normalizedAiRuns = aiRuns.map(row => ({
    ...row,
    branch: "ai analyst",
    source_counts: {},
    new_filing_counts: {},
    transaction_counts: {},
    ai_completed_count: Number(row.completed_count || 0),
  }));
  const runs = [...trackerRuns, ...normalizedAiRuns].sort((a, b) => String(b.finished_utc || "").localeCompare(String(a.finished_utc || "")));
  state.data = { summary, filings, transactions, reviews, runs, analyses, portfolio };
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
  el("analysis-count").textContent = number(summary.analysis_count);
  el("high-priority-count").textContent = number(summary.high_priority_count);
  el("open-position-count").textContent = number(summary.open_paper_position_count);
  const pnl = Number(summary.open_paper_pnl || 0);
  const pnlElement = el("paper-pnl");
  pnlElement.textContent = currency(pnl);
  pnlElement.className = pnlClass(pnl);
  el("coverage-note").textContent = `${summary.coverage_note} `;
  const manualTestNotice = el("manual-test-notice");
  const manualTestFilings = Number(summary.manual_test_filing_count || 0);
  const manualTestTransactions = Number(summary.manual_test_transaction_count || 0);
  manualTestNotice.hidden = manualTestFilings === 0;
  el("manual-test-note").textContent = `${number(manualTestFilings)} synthetic filing(s) and ${number(manualTestTransactions)} cloned transaction(s) are included for this isolated test only. Production state and alerts are unchanged.`;
  el("updated-at").textContent = `Dashboard generated ${formatDate(summary.generated_utc)}${summary.ai_last_success_utc ? ` • AI last succeeded ${formatDate(summary.ai_last_success_utc)}` : ""}`;
  el("repository-link").href = safeUrl(summary.repository_url) || "#";
  el("source-cards").innerHTML = Object.values(summary.sources || {}).map(source => {
    const statusClass = source.latest_success === true ? "up" : source.latest_success === false ? "down" : "unknown";
    const statusText = source.latest_success === true ? "Last run succeeded" : source.latest_success === false ? "Last run failed" : "No retained run status";
    return `<article class="source-card"><header><strong>${escapeHtml(titleCase(source.source))}</strong><span class="status-dot ${statusClass}" title="${escapeHtml(statusText)}"></span></header><dl><dt>Cataloged filings</dt><dd>${number(source.filing_count)}</dd><dt>Visible in last run</dt><dd>${number(source.visible_count)}</dd><dt>Last run</dt><dd>${formatDate(source.last_run_utc)}</dd><dt>Last success</dt><dd>${formatDate(source.last_success_utc)}</dd></dl>${source.latest_error ? `<p class="muted">${escapeHtml(source.latest_error)}</p>` : ""}</article>`;
  }).join("");
}

function setTable(id, rows, renderer, shownKey) {
  const shown = state.shown[shownKey];
  el(id).innerHTML = rows.length ? rows.slice(0, shown).map(renderer).join("") : `<tr><td class="empty-row" colspan="14">No matching records.</td></tr>`;
  const button = el(`${shownKey}-more`);
  button.hidden = rows.length <= shown;
  button.onclick = () => { state.shown[shownKey] += PAGE_SIZE; renderAllTables(); };
  el(`${shownKey}-count-label`).textContent = `Showing ${number(Math.min(rows.length, shown))} of ${number(rows.length)} matching record(s).`;
}

function filteredAnalyses() {
  const query = el("ai-search").value.trim().toLowerCase();
  const classification = el("ai-classification").value;
  const source = el("ai-source").value;
  return state.data.analyses.filter(row =>
    (!query || haystack(row).includes(query)) &&
    (!classification || row.classification === classification) &&
    (!source || row.source === source)
  );
}

function evidenceLinks(row) {
  const sources = Array.isArray(row.ai?.evidence_sources) ? row.ai.evidence_sources : [];
  const links = [];
  if (row.source_url) links.push(link(row.source_url, "Official filing"));
  for (const source of sources.slice(0, 3)) {
    if (source?.url && source.url !== row.source_url) links.push(link(source.url, source.title || "Evidence"));
  }
  return links.length ? links.join("") : "—";
}

function renderAnalyses() {
  const rows = filteredAnalyses();
  setTable("ai-body", rows, row => {
    const entry = row.entry_plan || {};
    const market = row.market || {};
    const band = entry.review_band_low && entry.review_band_high ? `${price(entry.review_band_low)}–${price(entry.review_band_high)}` : "No calculated band";
    const marketText = `${price(market.current_price)} current${market.return_since_transaction_percent !== null && market.return_since_transaction_percent !== undefined ? ` • ${percent(market.return_since_transaction_percent)} since trade` : ""}`;
    const factors = [...(row.ai?.positive_factors || []).slice(0, 2), ...(row.ai?.negative_factors || []).slice(0, 1).map(item => `Caution: ${item}`)];
    return `<tr>
      <td>${formatDate(row.analyzed_at_utc)}</td>
      <td class="asset-cell"><strong>${escapeHtml(row.ticker || "Unknown")}</strong><small>${escapeHtml(row.asset || "")}</small></td>
      <td><span class="badge ${escapeHtml(row.signal_direction || "neutral")}">${escapeHtml(titleCase(row.signal_direction || "neutral"))}</span><small>${escapeHtml(row.transaction_type || "Unknown")}</small></td>
      <td><span class="score ${escapeHtml(row.classification || "archive")}">${number(row.score)}</span><small><span class="badge ${escapeHtml(row.classification || "archive")}">${escapeHtml(titleCase(row.classification || "archive"))}</span></small></td>
      <td class="filer-cell"><strong>${escapeHtml(row.filer || "Unknown")}</strong><small>${escapeHtml([row.owner,row.title,row.agency,row.chamber].filter(Boolean).join(" • "))}</small></td>
      <td>${formatDate(row.transaction_date)}<small>${escapeHtml(row.amount || "—")} • filed ${formatDate(row.filed_date)}</small></td>
      <td class="entry-cell"><strong>${escapeHtml(titleCase(entry.entry_status || "unknown"))}</strong><small>${escapeHtml(marketText)}</small><small>${escapeHtml(band)}</small><small>Chase: ${escapeHtml(percent(entry.chase_percent))}</small></td>
      <td class="analysis-summary">${escapeHtml(row.ai?.analysis_summary || "—")}<small>${escapeHtml(factors.join(" • "))}</small></td>
      <td class="evidence-links">${evidenceLinks(row)}</td>
    </tr>`;
  }, "ai");
}

function filteredPortfolio() {
  const query = el("portfolio-search").value.trim().toLowerCase();
  const status = el("portfolio-status").value;
  return state.data.portfolio.filter(row => (!query || haystack(row).includes(query)) && (!status || row.status === status));
}

function renderPortfolio() {
  const rows = filteredPortfolio();
  setTable("portfolio-body", rows, row => {
    const pnl = row.status === "closed" ? Number(row.realized_pnl || 0) : Number(row.unrealized_pnl || 0);
    const currentOrExit = row.status === "closed" ? row.exit_price : row.current_price;
    return `<tr>
      <td>${formatDate(row.opened_at_utc)}</td>
      <td class="asset-cell"><strong>${escapeHtml(row.ticker || "Unknown")}</strong><small>${escapeHtml(titleCase(row.classification || ""))}</small></td>
      <td><span class="badge ${escapeHtml(row.status || "")}">${escapeHtml(titleCase(row.status || "unknown"))}</span>${row.exit_reason ? `<small>${escapeHtml(titleCase(row.exit_reason))}</small>` : ""}</td>
      <td>${number(row.score)}</td>
      <td class="filer-cell"><strong>${escapeHtml(row.filer || "Unknown")}</strong><small>${escapeHtml(row.owner || "Unknown")}</small></td>
      <td>${price(row.entry_price)}<small>${currency(row.initial_notional)} simulated</small></td>
      <td>${price(currentOrExit)}<small>${row.status === "closed" ? `closed ${formatDate(row.closed_at_utc)}` : `updated ${formatDate(row.last_updated_utc)}`}</small></td>
      <td>${Number(row.quantity || 0).toLocaleString([], { maximumFractionDigits: 6 })}</td>
      <td class="${pnlClass(pnl)}">${currency(pnl)}<small>${percent(row.return_percent)}</small></td>
      <td>${formatDate(row.evaluation_horizon_utc)}</td>
      <td>${link(row.source_url)}</td>
    </tr>`;
  }, "portfolio");
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
    const testLabel = row.is_synthetic_test ? `<small>Temporary Manual Test • ${escapeHtml(row.report_id || "TEST")}</small>` : "";
    return `<tr><td>${formatDate(row.filed_date)}</td><td>${escapeHtml(titleCase(row.source))}</td><td class="filer-cell"><strong>${escapeHtml(row.filer || "Unknown")}</strong><small>${escapeHtml(row.report_type || "")}</small></td><td>${escapeHtml(role.join(" • ") || "—")}</td><td><span class="badge ${escapeHtml(row.status || "")}">${escapeHtml(titleCase(row.status || "unknown"))}</span>${testLabel}${row.review_reason ? `<small>${escapeHtml(row.review_reason)}</small>` : ""}</td><td>${escapeHtml(counts)}</td><td>${link(row.source_url)}</td></tr>`;
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
  setTable("transactions-body", rows, row => `<tr><td>${formatDate(row.transaction_date)}</td><td>${formatDate(row.filed_date)}</td><td>${escapeHtml(titleCase(row.source))}</td><td class="filer-cell"><strong>${escapeHtml(row.filer || "Unknown")}</strong><small>${escapeHtml([row.title,row.agency,row.chamber].filter(Boolean).join(" • "))}</small>${row.is_synthetic_test ? `<small>Temporary Manual Test</small>` : ""}</td><td>${escapeHtml(row.owner || "Unknown")}</td><td><span class="badge">${escapeHtml(row.transaction_type || "Unknown")}</span></td><td class="asset-cell"><strong>${escapeHtml(row.ticker || row.asset || "Unknown")}</strong>${row.ticker ? `<small>${escapeHtml(row.asset || "")}</small>` : ""}</td><td>${escapeHtml(row.amount || "—")}</td><td>${link(row.source_url)}</td></tr>`, "transactions");
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
  setTable("runs-body", rows, row => {
    const isAi = String(row.branch || "").startsWith("ai");
    const visible = isAi ? "—" : number(dictTotal(row.source_counts));
    const newItems = isAi ? number(row.completed_count) : number(dictTotal(row.new_filing_counts));
    const transactions = isAi ? number(row.eligible_transaction_count) : number(dictTotal(row.transaction_counts));
    return `<tr><td>${formatDate(row.finished_utc)}</td><td>${escapeHtml(titleCase(row.branch))}</td><td><span class="badge ${row.success ? "success" : "failure"}">${row.success ? "Success" : "Failed"}</span></td><td>${visible}</td><td>${newItems}</td><td>${transactions}</td><td>${escapeHtml((row.errors || []).join("; ") || "—")}</td><td>${link(row.run_url, "Open run")}</td></tr>`;
  }, "runs");
}

function renderAllTables() { renderAnalyses(); renderPortfolio(); renderFilings(); renderTransactions(); renderReviews(); renderRuns(); }
function renderAll() {
  renderSummary();
  populateSelect("ai-classification", state.data.analyses.map(row => row.classification));
  populateSelect("ai-source", state.data.analyses.map(row => row.source));
  populateSelect("portfolio-status", state.data.portfolio.map(row => row.status));
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
for (const id of ["ai-search","ai-classification","ai-source","portfolio-search","portfolio-status","filings-search","filings-source","filings-status","transactions-search","transactions-source","transactions-type","reviews-search","reviews-source"]) el(id).addEventListener("input", () => { const key = id.split("-")[0]; state.shown[key] = PAGE_SIZE; renderAllTables(); });
el("refresh-button").addEventListener("click", () => {
  state.shown = { ai: PAGE_SIZE, portfolio: PAGE_SIZE, filings: PAGE_SIZE, transactions: PAGE_SIZE, reviews: PAGE_SIZE, runs: PAGE_SIZE };
  loadData().catch(showError);
});
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
        write_json(data_dir / "ai-analyses.json", payload["analyses"])
        write_json(data_dir / "paper-portfolio.json", payload["portfolio"])
        write_json(data_dir / "ai-runs.json", payload["ai_runs"])
        write_csv(data_dir / "filings.csv", payload["filings"], FILING_FIELDS)
        write_csv(data_dir / "transactions.csv", payload["transactions"], TRANSACTION_FIELDS)
        write_csv(data_dir / "pending-reviews.csv", payload["reviews"], REVIEW_FIELDS)
        write_csv(data_dir / "runs.csv", payload["runs"], RUN_FIELDS)
        write_csv(data_dir / "ai-analyses.csv", payload["analyses"], ANALYSIS_FIELDS)
        write_csv(data_dir / "paper-portfolio.csv", payload["portfolio"], PORTFOLIO_FIELDS)
        write_csv(data_dir / "ai-runs.csv", payload["ai_runs"], AI_RUN_FIELDS)
        (temp_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
        (temp_dir / "404.html").write_text(INDEX_HTML, encoding="utf-8")
        (temp_dir / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
        (temp_dir / "app.js").write_text(APP_JS, encoding="utf-8")
        (temp_dir / "wallboard.html").write_text(WALLBOARD_HTML, encoding="utf-8")
        (temp_dir / "wallboard.css").write_text(WALLBOARD_CSS, encoding="utf-8")
        (temp_dir / "wallboard.js").write_text(WALLBOARD_JS, encoding="utf-8")
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
    parser.add_argument("--ai-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--repository-url",
        default=(
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', 'maglothinm/MyETF-Intelligence').strip('/')}"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    legislative = load_branch(args.legislative_dir, "legislative")
    executive = load_branch(args.executive_dir, "executive")
    ai = load_ai(args.ai_dir)
    payload = build_payload(legislative, executive, repository_url=args.repository_url, ai=ai)
    build_site(payload, args.output_dir)
    build_dashboard_addon(args.ai_dir, args.output_dir)
    print(
        f"Dashboard built at {args.output_dir}: "
        f"{len(payload['filings'])} filings, {len(payload['transactions'])} transactions, "
        f"{len(payload['reviews'])} review items, {len(payload['analyses'])} AI analyses, "
        f"{len(payload['portfolio'])} paper positions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
