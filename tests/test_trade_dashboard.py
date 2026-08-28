from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.build_trade_dashboard import build_payload, build_site, load_ai, load_branch


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_dashboard_merges_state_artifacts_and_builds_static_site(tmp_path: Path) -> None:
    legislative_dir = tmp_path / "legislative"
    executive_dir = tmp_path / "executive"

    write_jsonl(
        legislative_dir / "filings.jsonl",
        [
            {
                "filing_key": "house|house:2026:100",
                "first_seen_utc": "2026-08-25T17:00:00Z",
                "updated_at_utc": "2026-08-25T17:00:00Z",
                "branch": "legislative",
                "source": "house",
                "report_id": "house:2026:100",
                "filer": "Example Representative",
                "filed_date": "2026-08-25",
                "source_url": "https://example.test/house-100.pdf",
                "document_format": "pdf",
                "chamber": "House",
                "title": "Representative",
                "agency": "",
                "district": "MA-01",
                "report_type": "Periodic Transaction Report",
                "access_mode": "direct",
                "status": "cataloged",
                "transaction_count": 0,
                "purchase_count": 0,
                "sale_count": 0,
                "exchange_count": 0,
                "review_reason": "",
            },
            # A later outcome for the same filing must replace the catalog-only row.
            {
                "filing_key": "house|house:2026:100",
                "first_seen_utc": "2026-08-25T17:00:00Z",
                "updated_at_utc": "2026-08-25T17:05:00Z",
                "branch": "legislative",
                "source": "house",
                "report_id": "house:2026:100",
                "filer": "Example Representative",
                "filed_date": "2026-08-25",
                "source_url": "https://example.test/house-100.pdf",
                "document_format": "pdf",
                "chamber": "House",
                "title": "Representative",
                "agency": "",
                "district": "MA-01",
                "report_type": "Periodic Transaction Report",
                "access_mode": "direct",
                "status": "processed",
                "transaction_count": 2,
                "purchase_count": 1,
                "sale_count": 1,
                "exchange_count": 0,
                "review_reason": "",
            },
        ],
    )
    purchase = {
        "trade_id": "trade:house-buy",
        "observed_at_utc": "2026-08-25T17:05:00Z",
        "branch": "legislative",
        "source": "house",
        "report_id": "house:2026:100",
        "filer": "Example Representative",
        "chamber": "House",
        "title": "Representative",
        "agency": "",
        "owner": "Spouse",
        "asset": "Example Corporation",
        "ticker": "EXM",
        "asset_type": "Stock",
        "transaction_type": "Purchase",
        "transaction_date": "2026-08-20",
        "notification_date": "2026-08-25",
        "filed_date": "2026-08-25",
        "amount": "$1,001 - $15,000",
        "source_url": "https://example.test/house-100.pdf",
        "raw_row": "Example Corporation Purchase",
        "equity_like": True,
        "parse_confidence": "high",
    }
    sale = {
        **purchase,
        "trade_id": "trade:house-sale",
        "owner": "Self",
        "asset": "Second Corporation",
        "ticker": "SEC",
        "transaction_type": "Sale",
        "amount": "$15,001 - $50,000",
    }
    write_jsonl(legislative_dir / "transactions.jsonl", [purchase, sale])
    # A purchase collected before transactions.jsonl existed must remain visible,
    # without duplicating the purchase that is already in the new ledger.
    legacy_purchase = {
        **purchase,
        "trade_id": "trade:legacy-buy",
        "filer": "Legacy Senator",
        "source": "senate",
        "report_id": "senate:legacy",
        "ticker": "OLD",
        "asset": "Legacy Holdings",
        "source_url": "https://example.test/senate-legacy",
    }
    write_jsonl(
        legislative_dir / "purchases.jsonl",
        [purchase, legacy_purchase],
    )
    write_jsonl(
        legislative_dir / "pending-review.jsonl",
        [
            {
                "review_id": "review:1",
                "observed_at_utc": "2026-08-25T17:06:00Z",
                "branch": "legislative",
                "source": "senate",
                "report_id": "senate:paper",
                "filer": "Example Senator",
                "filed_date": "2026-08-25",
                "source_url": "https://example.test/senate-paper",
                "reason": "Paper filing requires manual review",
                "title": "Senator",
                "agency": "",
            }
        ],
    )
    write_jsonl(
        legislative_dir / "runs.jsonl",
        [
            {
                "run_key": "100:1",
                "branch": "legislative",
                "started_utc": "2026-08-25T17:00:00Z",
                "finished_utc": "2026-08-25T17:06:00Z",
                "success": True,
                "source_counts": {"house": 879, "senate": 200},
                "new_filing_counts": {"house": 1, "senate": 0},
                "cataloged_filing_counts": {"house": 879, "senate": 200},
                "baseline_counts": {"house": 0, "senate": 0},
                "transaction_counts": {"house": 2, "senate": 0},
                "purchase_counts": {"house": 1, "senate": 0},
                "pending_review_counts": {"house": 0, "senate": 1},
                "errors": [],
                "run_url": "https://github.com/example/MyETF/actions/runs/100",
                "event_name": "schedule",
                "run_attempt": "1",
            }
        ],
    )
    (legislative_dir / "state.json").write_text(
        json.dumps({"last_success_utc": "2026-08-25T17:06:00Z"}),
        encoding="utf-8",
    )

    write_jsonl(
        executive_dir / "filings.jsonl",
        [
            {
                "filing_key": "oge|oge:1",
                "first_seen_utc": "2026-08-25T18:00:00Z",
                "updated_at_utc": "2026-08-25T18:00:00Z",
                "branch": "executive",
                "source": "oge",
                "report_id": "oge:1",
                "filer": "Example Secretary",
                "filed_date": "2026-08-24",
                "source_url": "https://example.test/oge-1.pdf",
                "document_format": "pdf",
                "chamber": "",
                "title": "Secretary",
                "agency": "Example Department",
                "district": "",
                "report_type": "OGE Form 278-T",
                "access_mode": "direct",
                "status": "cataloged",
                "transaction_count": 0,
                "purchase_count": 0,
                "sale_count": 0,
                "exchange_count": 0,
                "review_reason": "",
            }
        ],
    )
    (executive_dir / "state.json").write_text(
        json.dumps({"last_success_utc": "2026-08-25T18:00:00Z"}),
        encoding="utf-8",
    )

    legislative = load_branch(legislative_dir, "legislative")
    executive = load_branch(executive_dir, "executive")
    assert len(legislative["filings"]) == 1
    assert legislative["filings"][0]["status"] == "processed"
    assert {row["trade_id"] for row in legislative["transactions"]} == {
        "trade:house-buy",
        "trade:house-sale",
        "trade:legacy-buy",
    }

    payload = build_payload(
        legislative,
        executive,
        repository_url="https://github.com/example/MyETF",
    )
    assert payload["summary"]["filing_count"] == 2
    assert payload["summary"]["transaction_count"] == 3
    assert payload["summary"]["purchase_count"] == 2
    assert payload["summary"]["review_count"] == 1
    assert payload["summary"]["sources"]["house"]["visible_count"] == 879
    assert payload["summary"]["sources"]["senate"]["visible_count"] == 200
    assert payload["summary"]["sources"]["oge"]["filing_count"] == 1

    output_dir = tmp_path / "site"
    build_site(payload, output_dir)
    for relative in (
        "index.html",
        "404.html",
        "styles.css",
        "app.js",
        "wallboard.html",
        "wallboard.css",
        "wallboard.js",
        ".nojekyll",
        "data/summary.json",
        "data/filings.json",
        "data/transactions.json",
        "data/pending-reviews.json",
        "data/runs.json",
        "data/filings.csv",
        "data/transactions.csv",
        "data/pending-reviews.csv",
        "data/runs.csv",
        "data/ai-analyses.json",
        "data/paper-portfolio.json",
        "data/ai-runs.json",
        "data/ai-analyses.csv",
        "data/paper-portfolio.csv",
        "data/ai-runs.csv",
    ):
        assert (output_dir / relative).exists(), relative

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    wallboard_html = (output_dir / "wallboard.html").read_text(encoding="utf-8")
    wallboard_css = (output_dir / "wallboard.css").read_text(encoding="utf-8")
    wallboard_js = (output_dir / "wallboard.js").read_text(encoding="utf-8")
    assert "MyETF Government Trade Monitor" in index_html
    assert 'href="wallboard.html"' in index_html
    assert "Content-Security-Policy" in index_html
    assert "MyETF Intelligence Wallboard" in wallboard_html
    assert "Portrait wallboard" in wallboard_html
    assert "orientation: portrait" in wallboard_css
    assert "min-aspect-ratio: 12/5" in wallboard_css
    assert "DEFAULT_REFRESH_SECONDS = 300" in wallboard_js
    assert "requestWakeLock" in wallboard_js
    with (output_dir / "data/transactions.csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert {row["ticker"] for row in csv_rows} == {"EXM", "SEC", "OLD"}


def test_dashboard_handles_missing_branch_artifacts(tmp_path: Path) -> None:
    missing = load_branch(tmp_path / "does-not-exist", "executive")
    assert missing["filings"] == []
    assert missing["transactions"] == []
    assert missing["reviews"] == []
    assert missing["runs"] == []
    assert missing["state"] == {}


def test_dashboard_includes_ai_candidates_and_paper_portfolio(tmp_path: Path) -> None:
    ai_dir = tmp_path / "ai"
    write_jsonl(
        ai_dir / "analyses.jsonl",
        [
            {
                "analysis_id": "analysis:one",
                "trade_id": "trade:one",
                "analyzed_at_utc": "2026-08-26T12:00:00Z",
                "model": "gpt-5.6-terra",
                "source": "house",
                "filer": "Example Representative",
                "owner": "Self",
                "ticker": "EXM",
                "asset": "Example Corporation",
                "transaction_date": "2026-08-24",
                "filed_date": "2026-08-25",
                "amount": "$100,001 - $250,000",
                "source_url": "https://example.test/filing.pdf",
                "score": 86,
                "raw_score": 86,
                "classification": "high_priority",
                "market": {"current_price": 101.0, "return_since_transaction_percent": 1.0},
                "entry_plan": {
                    "entry_status": "review_now",
                    "review_band_low": 100.3,
                    "review_band_high": 101.4,
                    "position_allocation_percent": 1.0,
                },
                "ai": {
                    "analysis_summary": "Evidence-supported candidate for immediate human review.",
                    "positive_factors": ["Recent direct purchase"],
                    "negative_factors": [],
                    "evidence_sources": [],
                },
                "paper_only": True,
            }
        ],
    )
    write_jsonl(
        ai_dir / "paper-portfolio.jsonl",
        [
            {
                "event_id": "event:open",
                "event_type": "open",
                "position_id": "paper:one",
                "trade_id": "trade:one",
                "analysis_id": "analysis:one",
                "ticker": "EXM",
                "filer": "Example Representative",
                "owner": "Self",
                "source_url": "https://example.test/filing.pdf",
                "score": 86,
                "classification": "high_priority",
                "status": "open",
                "opened_at_utc": "2026-08-26T12:00:00Z",
                "evaluation_horizon_utc": "2026-09-25T12:00:00Z",
                "entry_price": 101.0,
                "current_price": 103.0,
                "quantity": 9.90099,
                "initial_notional": 1000.0,
                "market_value": 1019.8,
                "unrealized_pnl": 19.8,
                "return_percent": 1.98,
                "last_updated_utc": "2026-08-26T13:00:00Z",
                "paper_only": True,
            }
        ],
    )
    write_jsonl(
        ai_dir / "runs.jsonl",
        [
            {
                "run_key": "200:1",
                "started_utc": "2026-08-26T12:00:00Z",
                "finished_utc": "2026-08-26T12:01:00Z",
                "success": True,
                "enabled": True,
                "eligible_transaction_count": 1,
                "completed_count": 1,
                "high_priority_count": 1,
                "watchlist_count": 0,
                "errors": [],
                "warnings": [],
                "run_url": "https://github.com/example/MyETF/actions/runs/200",
            }
        ],
    )
    (ai_dir / "state.json").write_text(
        json.dumps(
            {
                "version": 1,
                "completed_analysis_ids": {"analysis:one": "2026-08-26T12:00:00Z"},
                "positions": {},
                "last_success_utc": "2026-08-26T12:01:00Z",
            }
        ),
        encoding="utf-8",
    )

    ai = load_ai(ai_dir)
    payload = build_payload(
        load_branch(None, "legislative"),
        load_branch(None, "executive"),
        repository_url="https://github.com/example/MyETF",
        ai=ai,
    )
    assert payload["summary"]["analysis_count"] == 1
    assert payload["summary"]["high_priority_count"] == 1
    assert payload["summary"]["open_paper_position_count"] == 1
    assert payload["summary"]["open_paper_pnl"] == 19.8
    assert payload["analyses"][0]["ticker"] == "EXM"
    assert payload["portfolio"][0]["status"] == "open"

    output = tmp_path / "site-ai"
    build_site(payload, output)
    index = (output / "index.html").read_text(encoding="utf-8")
    app = (output / "app.js").read_text(encoding="utf-8")
    assert "AI-ranked purchase candidates" in index
    assert "Paper-research portfolio" in index
    assert "ai-analyses.json" in app
    assert (output / "data/ai-analyses.csv").exists()
    assert (output / "data/paper-portfolio.csv").exists()
