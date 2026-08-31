from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

from scripts.ai_filing_analyst import (
    AnalystError,
    AnalystConfig,
    AIState,
    OpenAIResult,
    _notification_post,
    build_analysis_record,
    format_candidate_alert,
    load_rules,
    notify_candidate,
)
from scripts.build_trade_dashboard import (
    analysis_export_record,
    build_payload,
    build_site,
)
from scripts.create_manual_test_filing import generate_manual_test
from scripts.investor_edge import build_dashboard_addon
from scripts.run_investor_edge_simulation import simulate_analysis_record


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("pending, expected", [(7, "Historical backfill in progress"), (0, "Historical backfill current")])
def test_dashboard_exports_bootstrap_telemetry_and_all_building_profiles(tmp_path: Path, pending: int, expected: str) -> None:
    ai_dir = tmp_path / "ai"
    ai_dir.mkdir()
    profiles = [{"investor_key": f"test-{index}|self", "filer": f"TEST Filer {index}", "owner": "Self",
                 "sample_count": 0, "minimum_sample_met": False, "edge_score": 50,
                 "status": "insufficient_data", "confidence_label": "Low", "backfill_pending_trade_count": 2}
                for index in range(4)]
    metadata = {"historical_transaction_count": 20, "eligible_purchase_count": 8,
                "unique_investor_identity_count": 4, "published_profile_count": 4,
                "completed_profile_count": 0, "building_profile_count": 4,
                "backfill_processed_this_run": 1, "backfill_pending_observation_count": pending,
                "backfill_limit_per_run": 30, "network_requests_this_run": 2,
                "branch_transaction_counts": {"legislative": 15, "executive": 5},
                "excluded_reason_counts": {"not_purchase": 12}}
    (ai_dir / "investor-edge-leaderboard.json").write_text(
        json.dumps({"investors": profiles, **metadata, "api_key": "never-export", "private_details": "not-public"}), encoding="utf-8")
    output = tmp_path / "dashboard"
    build_dashboard_addon(ai_dir, output)
    exported = json.loads((output / "data/investor-edge.json").read_text(encoding="utf-8"))
    assert {key: exported[key] for key in metadata} == metadata
    assert exported["investors"] == profiles
    assert "api_key" not in exported and "private_details" not in exported
    soup = BeautifulSoup((output / "investor-edge.html").read_text(encoding="utf-8"), "html.parser")
    assert soup.select_one("#edge-bootstrap-status").get_text() == expected
    assert len(soup.select("tr.investor-row")) == 4
    for row in soup.select("tr.investor-row"):
        cells = row.select("td")
        assert cells[3].get_text(strip=True) == "—"
        assert "Building history — insufficient completed observations (n = 0)" in cells[5].get_text()
        assert "Historical observations pending: 2" in cells[5].get_text()
        assert all(cell.get_text(strip=True) == "—" for cell in cells[6:11])


@pytest.mark.parametrize("pending", [None, True, -1, "0", 1.5])
def test_dashboard_legacy_or_invalid_history_telemetry_is_unavailable(tmp_path: Path, pending: object) -> None:
    ai_dir = tmp_path / "ai"
    ai_dir.mkdir()
    data = {"investors": [{"filer": "TEST legacy", "owner": "Spouse", "sample_count": 0}]}
    if pending is not None:
        data["backfill_pending_observation_count"] = pending
    (ai_dir / "investor-edge-leaderboard.json").write_text(json.dumps(data), encoding="utf-8")
    output = tmp_path / "dashboard"
    build_dashboard_addon(ai_dir, output)
    exported = json.loads((output / "data/investor-edge.json").read_text(encoding="utf-8"))
    assert exported["backfill_pending_observation_count"] is None
    assert exported["historical_transaction_count"] is None
    assert exported["branch_transaction_counts"] == {"legislative": None, "executive": None}
    page = (output / "investor-edge.html").read_text(encoding="utf-8")
    assert "Historical backfill status unavailable" in page
    assert "Historical backfill current" not in page
    assert "TEST legacy" in page


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _config(tmp_path: Path) -> AnalystConfig:
    return AnalystConfig(
        legislative_dir=None,
        executive_dir=None,
        ai_dir=tmp_path / "ai",
        schema_path=ROOT / "schemas/ai_filing_analysis.schema.json",
        rules_path=ROOT / "config/signal_rules.yml",
        result_path=tmp_path / "result.json",
        analyses_csv_path=tmp_path / "analyses.csv",
        portfolio_csv_path=tmp_path / "portfolio.csv",
        enabled=True,
        paper_trading_only=True,
        reanalyze_existing=True,
        suppress_alerts=False,
        max_analyses=1,
        model="surface-test",
        reasoning_effort="none",
        web_search_enabled=False,
        fetch_document_text=False,
        openai_api_key="",
        finnhub_api_key="",
        alphavantage_api_key="",
        alphavantage_entitlement="",
        sec_user_agent="",
        pushover_api_token="",
        pushover_user_key="",
        require_pushover=False,
        dashboard_url="https://example.test/dashboard",
        repository_url="https://example.test/repository",
        max_download_bytes=0,
        max_ocr_pages=0,
        request_timeout=(1.0, 1.0),
    )


def _trade(
    trade_id: str = "trade:current",
    *,
    transaction_date: str = "2026-08-20",
    filed_date: str = "2026-08-25",
    report_id: str = "house:current",
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "observed_at_utc": f"{filed_date}T12:00:00Z",
        "branch": "legislative",
        "source": "house",
        "report_id": report_id,
        "filer": "Example Representative",
        "chamber": "House",
        "title": "Representative",
        "agency": "",
        "owner": "Self",
        "asset": "Example Corporation Common Stock",
        "ticker": "EXM",
        "asset_type": "Stock",
        "transaction_type": "Purchase",
        "transaction_date": transaction_date,
        "filed_date": filed_date,
        "amount": "$15,001 - $50,000",
        "source_url": "https://example.test/filing.pdf",
        "raw_row": "Example Corporation purchase",
        "equity_like": True,
        "parse_confidence": "high",
        "is_synthetic_test": True,
        "is_temporary": True,
        "test_metadata": {"kind": "surface_test"},
    }


def _filing(trade: dict[str, object]) -> dict[str, object]:
    return {
        "filing_key": f"house|{trade['report_id']}",
        "source": "house",
        "report_id": trade["report_id"],
        "filer": trade["filer"],
        "filed_date": trade["filed_date"],
        "source_url": trade["source_url"],
        "title": trade["title"],
        "status": "processed",
        "is_synthetic_test": trade.get("is_synthetic_test", False),
        "is_temporary": trade.get("is_temporary", False),
        "test_metadata": trade.get("test_metadata", {}),
    }


def _ai_result() -> OpenAIResult:
    return OpenAIResult(
        payload={
            "analysis_summary": "Synthetic candidate for surface verification.",
            "transaction_intent": "likely_discretionary",
            "owner_significance": "direct_household",
            "filer_relevance_score": 12,
            "policy_contract_relevance_score": 8,
            "market_confirmation_score": 5,
            "confidence": 0.75,
            "positive_factors": ["Test fixture"],
            "negative_factors": [],
            "contradictory_evidence": [],
            "evidence_sources": [],
            "external_context_status": "not_requested",
        },
        response_id="simulation",
        input_tokens=None,
        output_tokens=None,
    )


def _market() -> dict[str, object]:
    return {
        "current_price": 101.0,
        "transaction_date_close": 100.0,
        "average_volume_20d": 2_000_000,
        "atr_14": 2.0,
    }


def _profile() -> dict[str, object]:
    return {
        "investor_key": "example representative|self",
        "edge_score": 63.5,
        "modifier": 4,
        "sample_count": 6,
        "confidence": 0.62,
        "confidence_label": "Medium",
        "followable_alpha": 2.4,
        "followable_alpha_by_horizon": {
            "5": 1.1,
            "20": 3.25,
            "60": 2.7,
            "120": None,
        },
        "weighted_followable_hit_rate_percent": 66.7,
        "average_disclosure_lag_days": 8.5,
        "current_sector": {"sector": "Technology", "benchmark": "XLK"},
        "sector_performance": [
            {
                "sector": "Technology",
                "benchmark": "XLK",
                "followable_alpha": 4.2,
            }
        ],
        "strongest_sector": {"sector": "Technology"},
        "trade_results": [],
        "data_errors": [],
    }


def test_candidate_alert_is_pure_complete_and_mutes_unavailable_samples() -> None:
    analysis = {
        "ticker": "EXM",
        "filer": "Example Representative",
        "owner": "Self",
        "score": 82,
        "final_score": 82,
        "base_score": 78,
        "classification": "high_priority",
        "amount": "$15,001 - $50,000",
        "entry_plan": {
            "entry_status": "review_now",
            "review_band_low": 99.5,
            "review_band_high": 103.25,
        },
        "ai": {"analysis_summary": "Review this candidate while the filing is fresh."},
        "investor_edge_modifier": 4,
        "investor_edge_status": "scored",
        "investor_edge": _profile(),
    }
    original = json.loads(json.dumps(analysis))
    alert = format_candidate_alert(analysis, "https://example.test/dashboard")

    assert analysis == original
    assert "Final 82" in alert["message"]
    assert "Base 78" in alert["message"]
    assert "Edge 63.5" in alert["message"]
    assert "+4 modifier" in alert["message"]
    assert "Medium 62%" in alert["message"]
    assert "Observations 6" in alert["message"]
    assert "20D alpha +3.25%" in alert["message"]
    assert "Hit 66.7%" in alert["message"]
    assert "Disclosure lag 8.5d" in alert["message"]
    assert "Classification High Priority" in alert["message"]
    assert "Amount $15,001 - $50,000" in alert["message"]
    assert "Entry status Review Now" in alert["message"]
    assert "Review band $99.50–$103.25" in alert["message"]
    assert "AI summary: Review this candidate while the filing is fresh." in alert["message"]
    assert alert["url"] == "https://example.test/dashboard"

    verbose = format_candidate_alert(
        {**analysis, "ai": {"analysis_summary": "word " * 200}}
    )
    summary_line = next(
        line for line in verbose["message"].splitlines() if line.startswith("AI summary:")
    )
    assert summary_line.endswith("…")
    assert len(summary_line) <= len("AI summary: ") + 220

    neutral = format_candidate_alert(
        {
            **analysis,
            "investor_edge_observation_count": 0,
            "investor_edge_score": 50,
            "investor_edge": {"sample_count": 0, "edge_score": 50, "modifier": 0},
        }
    )
    assert "Edge —" in neutral["message"]
    assert "Confidence —" in neutral["message"]
    assert "Observations 0" in neutral["message"]


def test_candidate_email_uses_existing_gmail_credentials_and_keeps_pushover_optional(
    tmp_path: Path, monkeypatch
) -> None:
    deliveries: list[object] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, *, timeout: float) -> None:
            assert (host, port, timeout) == ("smtp.gmail.com", 465, 1.0)

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def login(self, address: str, password: str) -> None:
            assert (address, password) == ("alerts@example.test", "app-password")

        def send_message(self, message: object) -> None:
            deliveries.append(message)

    monkeypatch.setattr("scripts.ai_filing_analyst.smtplib.SMTP_SSL", FakeSMTP)
    config = replace(
        _config(tmp_path),
        gmail_address="alerts@example.test",
        gmail_app_password="app-password",
    )
    delivered = notify_candidate(
        config,
        {
            "ticker": "EXM",
            "filer": "Example Representative",
            "owner": "Self",
            "score": 82,
            "base_score": 78,
            "final_score": 82,
            "classification": "high_priority",
            "amount": "$15,001 - $50,000",
            "entry_plan": {
                "entry_status": "review_now",
                "review_band_low": 99.5,
                "review_band_high": 103.25,
            },
            "ai": {"analysis_summary": "Review this candidate."},
            "investor_edge_modifier": 4,
            "investor_edge_status": "scored",
            "investor_edge": _profile(),
        },
    )
    assert delivered is True
    assert len(deliveries) == 1
    body = deliveries[0].get_content()  # type: ignore[attr-defined]
    assert "Classification High Priority" in body
    assert "Amount $15,001 - $50,000" in body
    assert "Entry status Review Now" in body
    assert "AI summary: Review this candidate." in body
    assert "Edge 63.5" in body
    assert "Dashboard: https://example.test/dashboard" in body


def test_pushover_channel_reports_whether_it_delivered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kwargs = {
        "title": "Candidate",
        "message": "Review candidate",
        "url": "https://example.test/dashboard",
        "url_title": "Open dashboard",
    }
    assert _notification_post(_config(tmp_path), **kwargs) is False

    posts: list[object] = []

    def fake_post(*args: object, **post_kwargs: object) -> object:
        posts.append((args, post_kwargs))
        return SimpleNamespace(status_code=200, text="ok")

    monkeypatch.setattr("scripts.ai_filing_analyst.requests.post", fake_post)
    config = replace(
        _config(tmp_path),
        pushover_api_token="app-token",
        pushover_user_key="user-key",
    )
    assert _notification_post(config, **kwargs) is True
    assert len(posts) == 1


def test_notify_candidate_reports_no_channel_and_checks_required_pushover_before_email(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis = {
        "ticker": "EXM",
        "classification": "watchlist",
        "score": 70,
        "entry_plan": {},
        "ai": {},
    }
    state = AIState()
    state_path = tmp_path / "state.json"
    assert (
        notify_candidate(
            _config(tmp_path), analysis, state=state, state_path=state_path
        )
        is False
    )
    assert state.candidate_alert_deliveries == {}
    assert not state_path.exists()

    suppressed = replace(
        _config(tmp_path),
        suppress_alerts=True,
        pushover_api_token="app-token",
        pushover_user_key="user-key",
        gmail_address="alerts@example.test",
        gmail_app_password="app-password",
    )
    assert (
        notify_candidate(suppressed, analysis, state=state, state_path=state_path)
        is False
    )
    assert state.candidate_alert_deliveries == {}
    assert not state_path.exists()

    attempts: list[str] = []

    def failed_post(*_args: object, **_kwargs: object) -> object:
        attempts.append("pushover")
        return SimpleNamespace(status_code=503, text="temporarily unavailable")

    class FakeSMTP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            attempts.append("email")

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def login(self, *_args: object) -> None:
            return None

        def send_message(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("scripts.ai_filing_analyst.requests.post", failed_post)
    monkeypatch.setattr("scripts.ai_filing_analyst.smtplib.SMTP_SSL", FakeSMTP)
    config = replace(
        _config(tmp_path),
        pushover_api_token="app-token",
        pushover_user_key="user-key",
        require_pushover=True,
        gmail_address="alerts@example.test",
        gmail_app_password="app-password",
    )
    with pytest.raises(AnalystError, match="Pushover notification failed"):
        notify_candidate(config, analysis, state=state, state_path=state_path)
    assert attempts == ["pushover"]
    assert state_path.exists()
    assert len(state.candidate_alert_deliveries) == 1
    queued = next(iter(state.candidate_alert_deliveries.values()))
    assert queued["requested_channels"] == ["pushover", "gmail"]
    assert queued["delivered_channels"] == {}
    assert "pushover" in queued["channel_errors"]


def test_optional_gmail_failure_fails_open_with_actual_delivery_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    analysis = {
        "ticker": "EXM",
        "classification": "high_priority",
        "score": 82,
        "entry_plan": {},
        "ai": {"analysis_summary": "Review this candidate."},
    }
    attempts: list[str] = []

    def successful_post(*_args: object, **_kwargs: object) -> object:
        attempts.append("pushover")
        return SimpleNamespace(status_code=200, text="ok")

    class FailedSMTP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            attempts.append("email")
            raise OSError("SMTP unavailable")

    monkeypatch.setattr("scripts.ai_filing_analyst.requests.post", successful_post)
    monkeypatch.setattr("scripts.ai_filing_analyst.smtplib.SMTP_SSL", FailedSMTP)
    both_channels = replace(
        _config(tmp_path),
        pushover_api_token="app-token",
        pushover_user_key="user-key",
        require_pushover=True,
        gmail_address="alerts@example.test",
        gmail_app_password="app-password",
    )
    assert notify_candidate(both_channels, analysis) is True
    assert attempts == ["pushover", "email"]
    assert "Optional Gmail candidate alert failed" in caplog.text

    attempts.clear()
    caplog.clear()
    gmail_only = replace(
        _config(tmp_path),
        gmail_address="alerts@example.test",
        gmail_app_password="app-password",
    )
    assert notify_candidate(gmail_only, analysis) is False
    assert attempts == ["email"]
    assert "Optional Gmail candidate alert failed" in caplog.text


def test_build_analysis_record_persists_edge_and_fails_open_per_candidate(
    tmp_path: Path,
) -> None:
    trade = _trade()
    rules = load_rules(ROOT / "config/signal_rules.yml")

    class SuccessRuntime:
        enabled = True
        provider = SimpleNamespace(alphavantage_api_key="", finnhub_api_key="")

        def profile_for_trade(self, _trade, _transactions):
            return _profile()

    record = build_analysis_record(
        trade=trade,
        filing=_filing(trade),
        ai_result=_ai_result(),
        market=_market(),
        sec={},
        document={},
        all_transactions=[trade],
        rules=rules,
        rules_hash="rules",
        config=_config(tmp_path),
        investor_edge=SuccessRuntime(),  # type: ignore[arg-type]
    )
    assert record["investor_edge_status"] == "scored"
    assert record["base_score"] is not None
    assert record["final_score"] == record["score"]
    assert record["investor_edge_modifier"] == 4
    assert record["investor_edge_relevant_alpha_label"] == "20D"
    assert record["investor_edge_relevant_followable_alpha"] == 3.25
    assert record["is_synthetic_test"] is True
    assert record["test_metadata"]["kind"] == "surface_test"

    class FailedRuntime:
        enabled = True
        provider = SimpleNamespace(
            alphavantage_api_key="never-persist-this-secret",
            finnhub_api_key="",
        )

        def profile_for_trade(self, _trade, _transactions):
            raise RuntimeError("apikey=never-persist-this-secret provider failed")

    failed = build_analysis_record(
        trade=trade,
        filing=_filing(trade),
        ai_result=_ai_result(),
        market=_market(),
        sec={},
        document={},
        all_transactions=[trade],
        rules=rules,
        rules_hash="rules",
        config=_config(tmp_path),
        investor_edge=FailedRuntime(),  # type: ignore[arg-type]
    )
    assert failed["analysis_status"] == "complete"
    assert failed["investor_edge_status"] == "error"
    assert failed["investor_edge_modifier"] == 0
    assert failed["base_score"] == failed["final_score"] == failed["score"]
    assert "never-persist-this-secret" not in json.dumps(failed)

    unavailable = build_analysis_record(
        trade=trade,
        filing=_filing(trade),
        ai_result=_ai_result(),
        market=_market(),
        sec={},
        document={},
        all_transactions=[trade],
        rules=rules,
        rules_hash="rules",
        config=_config(tmp_path),
        investor_edge=None,
    )
    assert unavailable["investor_edge_status"] == "unavailable"
    assert unavailable["investor_edge"]["status"] == "unavailable"
    assert unavailable["base_score"] == unavailable["final_score"] == unavailable["score"]
    assert unavailable["investor_edge_score"] is None


def test_dashboard_flattens_edge_fields_and_renders_candidate_surfaces(
    tmp_path: Path,
) -> None:
    analysis = {
        "analysis_id": "analysis:1",
        "trade_id": "trade:1",
        "analyzed_at_utc": "2026-08-29T12:00:00Z",
        "ticker": "EXM",
        "asset": "Example Corporation",
        "filer": "Example Representative",
        "owner": "Self",
        "score": 82,
        "base_score": 78,
        "classification": "high_priority",
        "investor_edge": _profile(),
        "ai": {"analysis_summary": "Review the synthetic candidate."},
        "entry_plan": {},
        "market": {},
        "is_synthetic_test": True,
    }
    empty_branch = {
        "filings": [],
        "transactions": [],
        "reviews": [],
        "runs": [],
        "state": {},
    }
    payload = build_payload(
        dict(empty_branch),
        dict(empty_branch),
        repository_url="https://example.test/repository",
        ai={"analyses": [analysis], "portfolio": [], "runs": [], "state": {}},
    )
    exported = payload["analyses"][0]
    assert exported["final_score"] == 82
    assert exported["investor_edge_score"] == 63.5
    assert exported["investor_edge_relevant_alpha_label"] == "20D"
    assert exported["investor_edge_sector_alpha"] == 4.2

    neutral = analysis_export_record(
        {"score": 50, "investor_edge": {"sample_count": 0, "edge_score": 50}}
    )
    assert neutral["investor_edge_score"] is None

    output = tmp_path / "site"
    build_site(payload, output)
    with (output / "data" / "ai-analyses.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        row = next(csv.DictReader(handle))
    assert row["base_score"] == "78"
    assert row["final_score"] == "82"
    assert row["investor_edge_score"] == "63.5"
    assert row["investor_edge_relevant_followable_alpha"] == "3.25"
    assert row["investor_edge_hit_rate_percent"] == "66.7"
    assert row["investor_edge_sector_alpha"] == "4.2"
    assert row["investor_edge_average_disclosure_lag_days"] == "8.5"
    assert "Investor Edge" in (output / "index.html").read_text(encoding="utf-8")
    app = (output / "app.js").read_text(encoding="utf-8")
    wallboard = (output / "wallboard.js").read_text(encoding="utf-8")
    for label in ("Sector edge", "Observations", "Modifier", "Run Simulation"):
        assert label in app
    for label in ("signalCard", "Sector edge", "final_score"):
        assert label in wallboard


def _simulation_trade(
    trade_id: str, transaction_date: str, filed_date: str, report_id: str
) -> dict[str, object]:
    row = _trade(
        trade_id,
        transaction_date=transaction_date,
        filed_date=filed_date,
        report_id=report_id,
    )
    row.pop("is_synthetic_test", None)
    row.pop("is_temporary", None)
    row.pop("test_metadata", None)
    return row


def test_run_simulation_reuses_production_path_without_network_or_alerts(
    tmp_path: Path,
) -> None:
    restored = tmp_path / "restored"
    restored.mkdir()
    prior = _simulation_trade("trade:prior", "2025-01-02", "2025-01-10", "house:prior")
    current = _simulation_trade(
        "trade:current", "2025-07-01", "2025-07-10", "house:current"
    )
    filings = [_filing(prior), _filing(current)]
    for filing in filings:
        filing.update(
            {
                "filing_key": f"house|{filing['report_id']}",
                "first_seen_utc": f"{filing['filed_date']}T12:00:00Z",
                "updated_at_utc": f"{filing['filed_date']}T12:00:00Z",
                "transaction_count": 1,
                "purchase_count": 1,
                "sale_count": 0,
                "exchange_count": 0,
            }
        )
    _write_jsonl(restored / "filings.jsonl", filings)
    _write_jsonl(restored / "transactions.jsonl", [prior, current])
    _write_jsonl(restored / "purchases.jsonl", [prior, current])
    (restored / "state.json").write_text(
        json.dumps(
            {
                "version": 1,
                "seen_filings": {"house": {}, "senate": {}, "oge": {}},
                "seen_trades": {},
            }
        ),
        encoding="utf-8",
    )

    tracker = tmp_path / "tracker"
    manifest = generate_manual_test(
        legislative_dir=restored,
        executive_dir=None,
        output_dir=tracker,
        as_of=date(2026, 8, 29),
        chooser=lambda candidates: candidates[0],
        token_factory=lambda: "simulation",
        now=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        require_investor_edge_history=True,
    )
    assert manifest["investor_edge_history_count"] >= 1

    ai_dir = tmp_path / "isolated-ai"
    result_file = tmp_path / "simulation-result.json"
    result = simulate_analysis_record(
        legislative_dir=tracker / "legislative",
        executive_dir=None,
        ai_dir=ai_dir,
        result_file=result_file,
    )
    assert result["verification"]["passed"] is True
    assert result["network_requests"] == 0
    assert result["openai_requests"] == 0
    assert result["real_alerts_sent"] is False
    assert result["analysis"]["is_synthetic_test"] is True
    assert result["analysis"]["investor_edge_observation_count"] >= 1
    assert result["analysis"]["classification"] in {"high_priority", "watchlist"}
    assert result["analysis"]["ai"]["evidence_sources"]
    assert result["assertions"]["candidate_alert_eligible"] is True
    assert result["assertions"]["record_profile_edge_agree"] is True
    assert result["assertions"]["record_profile_sample_agree"] is True
    assert result["assertions"]["record_profile_as_of_agrees"] is True
    assert result["assertions"]["persisted_profile_agrees"] is True
    assert result["assertions"]["leaderboard_profile_agrees"] is True
    assert "SIMULATION" in result["alert_preview"]["title"]
    assert result_file.is_file()
    assert (ai_dir / "analyses.jsonl").is_file()
    assert (ai_dir / "investor-edge-leaderboard.json").is_file()

    analysis = result["analysis"]
    candidate_profile = analysis["investor_edge"]
    persisted_profiles = json.loads(
        (ai_dir / "investor-edge-profiles.json").read_text(encoding="utf-8")
    )["profiles"]
    persisted_profile = persisted_profiles[result["investor_key"]]
    leaderboard = json.loads(
        (ai_dir / "investor-edge-leaderboard.json").read_text(encoding="utf-8")
    )["investors"]
    assert len(leaderboard) == 1
    leaderboard_profile = leaderboard[0]

    assert (
        analysis["investor_edge_score"]
        == candidate_profile["edge_score"]
        == persisted_profile["edge_score"]
        == leaderboard_profile["edge_score"]
    )
    assert (
        analysis["investor_edge_observation_count"]
        == candidate_profile["sample_count"]
        == persisted_profile["sample_count"]
        == leaderboard_profile["sample_count"]
    )
    assert (
        analysis["analyzed_at_utc"][:10]
        == candidate_profile["as_of_date"]
        == persisted_profile["as_of_date"]
        == leaderboard_profile["as_of_date"]
    )
