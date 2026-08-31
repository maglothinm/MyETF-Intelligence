from __future__ import annotations

import csv
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from scripts.build_trade_dashboard import (
    build_parser,
    build_payload,
    build_site,
    load_ai,
    load_branch,
    load_simulation,
)


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
                "run_url": "https://github.com/example/PolitiTrack/actions/runs/100",
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
        repository_url="https://github.com/example/PolitiTrack",
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
        "data/dashboard-insights.json",
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
        "data/simulation.json",
        "data/ai-analyses.csv",
        "data/paper-portfolio.csv",
        "data/ai-runs.csv",
    ):
        assert (output_dir / relative).exists(), relative

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    styles_css = (output_dir / "styles.css").read_text(encoding="utf-8")
    app_js = (output_dir / "app.js").read_text(encoding="utf-8")
    wallboard_html = (output_dir / "wallboard.html").read_text(encoding="utf-8")
    wallboard_css = (output_dir / "wallboard.css").read_text(encoding="utf-8")
    wallboard_js = (output_dir / "wallboard.js").read_text(encoding="utf-8")
    assert "PolitiTrack Government Trade Monitor" in index_html
    assert 'content="width=device-width, initial-scale=1, viewport-fit=cover"' in index_html
    assert 'id="run-simulation-link"' in index_html
    assert 'id="run-10k-agent-link"' in index_html
    assert 'href="wallboard.html"' in index_html
    assert "Content-Security-Policy" in index_html
    assert "PolitiTrack Intelligence Wallboard" in wallboard_html
    assert 'id="wall-run-simulation-link"' in wallboard_html
    assert 'id="wall-run-10k-agent-link"' in wallboard_html
    assert "Portrait wallboard" in wallboard_html
    assert "orientation: portrait" in wallboard_css
    assert "min-aspect-ratio:12/5" in wallboard_css
    assert "DEFAULT_REFRESH_SECONDS = 300" in wallboard_js
    assert "requestWakeLock" in wallboard_js
    assert "workflowUrl(summary.repository_url)" in app_js
    assert "workflowUrl(summary.repository_url)" in wallboard_js
    assert 'workflowFile="manual_test.yml"' in app_js
    assert 'workflowFile="manual_test.yml"' in wallboard_js
    assert 'workflowUrl(summary.repository_url, "filing_simulation.yml")' in app_js
    assert 'workflowUrl(summary.repository_url, "filing_simulation.yml")' in wallboard_js
    assert "Authorization" not in app_js
    assert "Authorization" not in wallboard_js
    assert "env(safe-area-inset-bottom)" in styles_css
    assert "min-height:44px" in styles_css
    assert json.loads((output_dir / "data/simulation.json").read_text(encoding="utf-8")) == {}
    with (output_dir / "data/transactions.csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert {row["ticker"] for row in csv_rows} == {"EXM", "SEC", "OLD"}


def test_published_review_inventory_matches_overview_without_preview_truncation(tmp_path: Path) -> None:
    """The dashboard count and full JSON/CSV use the same classified review rows."""
    payload = build_payload(load_branch(None, "legislative"), load_branch(None, "executive"),
                            repository_url="https://github.com/example/PolitiTrack")
    payload["filings"] = [
        {"filing_key": f"senate|retained:{index}", "source": "senate", "branch": "legislative",
         "report_id": f"retained:{index}", "status": "review_required", "filed_date": "2026-08-29",
         "filer": f"Fixture Official {index}", "review_reason": "PDF parser requires manual review"}
        for index in range(12)
    ] + [
        {"filing_key": "oge|request", "source": "oge", "branch": "executive", "report_id": "request",
         "status": "review_required", "access_mode": "request"},
        {"filing_key": "senate|test", "source": "senate", "branch": "legislative", "report_id": "test",
         "review_reason": "PDF parser requires manual review", "is_temporary": True},
    ]
    payload["reviews"] = [
        {"review_id": f"review|retained:{index}", "source": "senate", "report_id": f"retained:{index}",
         "observed_at_utc": "2026-08-30T10:01:00Z", "retained_extra": {"id": index}}
        for index in range(12)
    ] + [
        {"review_id": "review|request", "source": "oge", "report_id": "request", "reason": "Manual review"},
        {"review_id": "review|other", "reason": "Source clarification"},
        {"review_id": "review|test", "source": "senate", "report_id": "test"},
    ]
    before = copy.deepcopy(payload)
    output = tmp_path / "site"
    build_site(payload, output)
    assert payload == before
    rows = json.loads((output / "data/pending-reviews.json").read_text(encoding="utf-8"))
    model = json.loads((output / "data/dashboard-insights.json").read_text(encoding="utf-8"))
    assert len(rows) == 15
    assert [row["review_id"] for row in rows] == [row["review_id"] for row in payload["reviews"]]
    production = [row for row in rows if not row["is_synthetic_test"]]
    exceptions = [row for row in production if row["category"] == "manual_exception"]
    assert len(exceptions) == model["reviews"]["manual_exception"] == 12
    assert len(production) == model["reviews"]["total"] == 14
    assert len(model["reviews"]["latest"]) == 8
    assert model["reviews"]["access_required"] == model["reviews"]["other"] == 1
    assert model["synthetic"]["reviews"] == 1
    assert rows[-1]["is_synthetic_test"] is True
    assert rows[-1]["category"] == "manual_exception"
    assert rows[0]["filing_key"] == "senate|retained:0"
    assert rows[0]["filing_status"] == "review_required"
    assert rows[0]["branch"] == "legislative"
    assert rows[0]["reason"] == "PDF parser requires manual review"
    assert rows[0]["retained_extra"] == {"id": 0}
    with (output / "data/pending-reviews.csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == len(rows)
    assert [row["review_id"] for row in csv_rows] == [row["review_id"] for row in rows]
    assert sum(row["category"] == "manual_exception" and row["is_synthetic_test"] == "False" for row in csv_rows) == 12
    assert csv_rows[0]["filing_key"] == "senate|retained:0"
    assert csv_rows[0]["filing_status"] == "review_required"


def test_dashboard_handles_missing_branch_artifacts(tmp_path: Path) -> None:
    missing = load_branch(tmp_path / "does-not-exist", "executive")
    assert missing["filings"] == []
    assert missing["transactions"] == []
    assert missing["reviews"] == []
    assert missing["runs"] == []
    assert missing["state"] == {}


def test_dashboard_defaults_to_canonical_polititrack_repository(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    args = build_parser().parse_args([])

    assert args.repository_url == "https://github.com/maglothinm/PolitiTrack"


def test_dashboard_keeps_ten_k_agent_result_isolated(tmp_path: Path) -> None:
    simulation_dir = tmp_path / "simulation"
    simulation_dir.mkdir()
    result = {
        "schema_version": 1,
        "status": "success",
        "success": True,
        "simulation_id": "simulation:42",
        "mode": "offline_historical_replay",
        "as_of_utc": "2026-08-29T18:00:00Z",
        "run_url": "https://github.com/example/PolitiTrack/actions/runs/42",
        "message": "Selected TEST; priced paper portfolio value $10,250.00 toward the $20,000.00 goal.",
        "selection": {"method": "random", "candidate_count": 12},
        "objective": {
            "starting_capital_usd": 10000.0,
            "goal_value_usd": 20000.0,
            "goal_reached": False,
            "goal_progress_percent": 51.25,
            "remaining_to_goal_usd": 9750.0,
        },
        "filing": {
            "branch": "legislative",
            "source": "house",
            "report_id": "house:42",
            "filer": "Example Representative",
            "source_url": "https://example.test/filing-42.pdf",
        },
        "trade": {"trade_id": "trade:42", "ticker": "TEST"},
        "analysis": {"status": "available", "score": 81},
        "accounting": {
            "status": "priced",
            "starting_cash_usd": 10000.0,
            "shares": 100.0,
            "entry_price_usd": 100.0,
            "valuation_price_usd": 102.5,
            "portfolio_value_usd": 10250.0,
            "profit_loss_usd": 250.0,
            "return_percent": 2.5,
        },
        "notification": {"pushover": "not_requested", "email": "not_requested"},
        "notification_status": "Pushover: not_requested; email: not_requested",
        "safety": {
            "paper_only": True,
            "alerts_sent": False,
            "production_inputs_mutated": False,
        },
    }
    (simulation_dir / "simulation-result.json").write_text(
        json.dumps(result), encoding="utf-8"
    )

    simulation = load_simulation(simulation_dir)
    payload = build_payload(
        load_branch(None, "legislative"),
        load_branch(None, "executive"),
        repository_url="https://github.com/example/PolitiTrack",
        simulation=simulation,
    )

    assert payload["simulation"] == result
    assert payload["summary"]["filing_count"] == 0
    assert payload["summary"]["transaction_count"] == 0
    assert payload["summary"]["analysis_count"] == 0
    assert payload["summary"]["open_paper_position_count"] == 0

    output = tmp_path / "simulation-site"
    build_site(payload, output)
    assert json.loads((output / "data/simulation.json").read_text(encoding="utf-8")) == result

    index = (output / "index.html").read_text(encoding="utf-8")
    app = (output / "app.js").read_text(encoding="utf-8")
    wallboard = (output / "wallboard.html").read_text(encoding="utf-8")
    wallboard_js = (output / "wallboard.js").read_text(encoding="utf-8")
    assert "Latest $10K Agent simulation" in index
    assert "production counts excluded" in index.lower()
    assert "never changes production tracker, AI, or portfolio state" in index
    assert "wall-ten-k-simulation" in wallboard
    assert 'checkedJson("data/dashboard-insights.json")' in app
    assert 'checkedJson("data/dashboard-insights.json")' in wallboard_js
    insights = json.loads((output / "data/dashboard-insights.json").read_text(encoding="utf-8"))
    assert insights["simulation"]["current_value"] == 10250
    assert insights["simulation"]["change_usd"] == 250
    assert "goal_progress_percent" not in insights["simulation"]
    assert insights["simulation"]["persistent_history"] is False


def test_load_simulation_requires_exact_result_filename(tmp_path: Path) -> None:
    assert load_simulation(None) == {}
    assert load_simulation(tmp_path / "missing") == {}
    directory = tmp_path / "simulation"
    directory.mkdir()
    (directory / "simulation.json").write_text('{"status":"queued"}', encoding="utf-8")
    assert load_simulation(directory) == {}
    (directory / "simulation-result.json").write_text(
        '{"status":"success"}', encoding="utf-8"
    )
    assert load_simulation(directory) == {"status": "success"}


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
                "run_url": "https://github.com/example/PolitiTrack/actions/runs/200",
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
        repository_url="https://github.com/example/PolitiTrack",
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
    assert "AI-ranked directional signals" in index
    assert "Paper-research portfolio" in index
    assert 'file:"ai-analyses"' in app
    assert (output / "data/ai-analyses.csv").exists()
    assert (output / "data/paper-portfolio.csv").exists()


def test_public_build_preserves_input_bytes_and_excludes_private_payloads(tmp_path: Path) -> None:
    """Exercise the actual file builder, including the separately generated Edge page."""
    from scripts.build_trade_dashboard import main

    inputs = tmp_path / "copied-inputs"
    inputs.mkdir()
    secret = "fixture-private-" + "value"
    heartbeat = "https://hc-ping.com/" + "fixture-only-never-fetch"
    hostile = '<img src=x onerror="window.fixtureExecuted=true">'
    write_jsonl(inputs / "filings.jsonl", [{
        "filing_key": "house:fixture", "filer": hostile, "status": "cataloged",
        "source": "house", "source_url": "https://example.test/official",
        "filed_date": "2026-08-20", "credentials": {"token": secret},
        "heartbeat_url": heartbeat,
    }])
    (inputs / "state.json").write_text('{"seen_ids":["keep-this-id"]}', encoding="utf-8")
    (inputs / "investor-edge-leaderboard.json").write_text(json.dumps({
        "investors": [{"filer": hostile, "owner": "Self", "sample_count": 0,
                       "edge_score": 50, "recipient": "private@example.test",
                       "delivery_payload": {"secret": secret, "url": heartbeat}}]
    }), encoding="utf-8")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
    output = tmp_path / "public-site"
    assert main(["--legislative-dir", str(inputs), "--ai-dir", str(inputs),
                 "--output-dir", str(output)]) == 0
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir()}
    assert before == after
    assets = "\n".join(p.read_text(encoding="utf-8") for p in output.rglob("*") if p.is_file())
    for value in (secret, heartbeat, "private@example.test"):
        assert value not in assets
    edge = (output / "investor-edge.html").read_text(encoding="utf-8")
    assert hostile not in edge
    assert "&lt;img" in edge
    assert "Building history — insufficient completed observations (n = 0)" in edge
    insights = json.loads((output / "data/dashboard-insights.json").read_text(encoding="utf-8"))
    assert insights["coverage"]["filings"] == 1
    assert insights["health"]["status"] == "unknown"
    assert insights["paper"]["empty_note"] == "No open paper positions"


def test_dashboard_navigation_and_dialog_ids_remain_unique(tmp_path: Path) -> None:
    from bs4 import BeautifulSoup
    build_site(build_payload(load_branch(None, "legislative"), load_branch(None, "executive"),
                             repository_url="https://github.com/example/PolitiTrack"), tmp_path / "site")
    for page in ("index.html", "wallboard.html"):
        soup = BeautifulSoup((tmp_path / "site" / page).read_text(encoding="utf-8"), "html.parser")
        ids = [node["id"] for node in soup.select("[id]")]
        assert len(ids) == len(set(ids))
        for opener in soup.select("[data-dialog]"):
            assert soup.find("dialog", id=opener["data-dialog"])
        assert not soup.select("script:not([src]), style, [onclick]")
        assert all(node.get("aria-label") for node in soup.select("button.help, button.icon-button"))
        assert "connect-src 'self'" in str(soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"}))


def test_dashboard_release_checks(tmp_path: Path) -> None:
    """Keep additive UI regressions in the existing fixed-file CI test selection.

    Workflow configuration deliberately remains unchanged for this UI release.
    Linux CI also executes the repository's complete retired-overlay verifier;
    Windows development without Bash still exercises the fixture-only UI suites.
    """
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_dashboard_insights.py", "tests/test_dashboard_notifications.py",
         "tests/test_dashboard_dom.py", "--basetemp", str(tmp_path / "ui-checks")],
        cwd=repository, capture_output=True, text=True, check=False, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if os.name != "nt":
        bash = shutil.which("bash")
        assert bash, "Bash is required for the Linux repository verification gate"
        verification = subprocess.run(
            [bash, "verify.sh"], cwd=repository, capture_output=True,
            text=True, check=False, timeout=90,
        )
        assert verification.returncode == 0, verification.stdout + verification.stderr
        assert "VERIFICATION PASSED" in verification.stdout
