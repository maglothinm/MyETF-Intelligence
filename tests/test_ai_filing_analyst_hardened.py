from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ai_filing_analyst as legacy
from scripts import ai_filing_analyst_hardened as hardened



def test_compatibility_entrypoint_routes_shared_module_namespace() -> None:
    assert legacy.run_analyst is hardened.run_analyst
    assert legacy.openai_analyze is hardened.openai_analyze
    assert legacy.notify_candidate.__globals__ is legacy.__dict__

def _payload() -> dict:
    return {
        "analysis_summary": "Public evidence supports only a conservative review.",
        "transaction_intent": "possibly_discretionary",
        "owner_significance": "direct_household",
        "filer_relevance_score": 10,
        "policy_contract_relevance_score": 5,
        "market_confirmation_score": 2,
        "confidence": 0.7,
        "positive_factors": ["Recent disclosure"],
        "negative_factors": ["Value is reported as a range"],
        "contradictory_evidence": [],
        "evidence_sources": [],
        "external_context_status": "not_found",
    }


def _response(
    output_text: str,
    *,
    status: str = "completed",
    reason: str = "",
    response_id: str = "resp_test",
):
    return SimpleNamespace(
        status=status,
        incomplete_details=(SimpleNamespace(reason=reason) if reason else None),
        output_text=output_text,
        id=response_id,
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
        _request_id="req_test",
    )


class _Responses:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        value = self.values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


class _Client:
    def __init__(self, values):
        self.responses = _Responses(values)


class _Factory:
    def __init__(self, values):
        self.client = _Client(values)

    def __call__(self, **_kwargs):
        return self.client


def _config(tmp_path: Path) -> legacy.AnalystConfig:
    root = Path(__file__).resolve().parents[1]
    return legacy.AnalystConfig(
        legislative_dir=tmp_path / "legislative",
        executive_dir=tmp_path / "executive",
        ai_dir=tmp_path / "ai",
        schema_path=root / "schemas/ai_filing_analysis.schema.json",
        rules_path=root / "config/signal_rules.yml",
        result_path=tmp_path / "ai-analysis-result.json",
        analyses_csv_path=tmp_path / "ai-latest-analyses.csv",
        portfolio_csv_path=tmp_path / "ai-paper-portfolio.csv",
        enabled=True,
        paper_trading_only=True,
        reanalyze_existing=False,
        suppress_alerts=True,
        max_analyses=20,
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        web_search_enabled=False,
        fetch_document_text=False,
        openai_api_key="test-openai-key",
        finnhub_api_key="",
        alphavantage_api_key="",
        alphavantage_entitlement="",
        sec_user_agent="",
        pushover_api_token="",
        pushover_user_key="",
        require_pushover=False,
        dashboard_url="https://example.test/",
        repository_url="https://github.com/example/PolitiTrack",
        max_download_bytes=1_000_000,
        max_ocr_pages=2,
        request_timeout=(1.0, 1.0),
    )


def _schema(cfg: legacy.AnalystConfig) -> dict:
    return legacy.load_schema(cfg.schema_path)


def test_incomplete_output_escalates_token_limit_then_validates(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    factory = _Factory(
        [
            _response("", status="incomplete", reason="max_output_tokens", response_id="r1"),
            _response(json.dumps(_payload()), response_id="r2"),
        ]
    )
    result = hardened.openai_analyze({}, cfg, _schema(cfg), client_factory=factory)
    assert result.payload["analysis_summary"]
    assert [call["max_output_tokens"] for call in factory.client.responses.calls] == [
        4000,
        8000,
    ]
    assert result.diagnostics[0]["terminal_status"] == "incomplete"
    assert result.diagnostics[0]["incomplete_reason"] == "max_output_tokens"
    assert result.diagnostics[-1]["terminal_status"] == "completed"


def test_malformed_json_retries_without_repair(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    factory = _Factory([_response('{"analysis_summary":"cut'), _response(json.dumps(_payload()))])
    result = hardened.openai_analyze({}, cfg, _schema(cfg), client_factory=factory)
    assert len(factory.client.responses.calls) == 2
    assert result.diagnostics[0]["error_type"] == "JSONDecodeError"


def test_repeated_malformed_json_defers_candidate(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    factory = _Factory([_response("{"), _response("{")])
    with pytest.raises(hardened.StructuredOutputDeferred) as caught:
        hardened.openai_analyze({}, cfg, _schema(cfg), client_factory=factory)
    assert len(caught.value.diagnostics) == 2
    assert all(item["error_type"] == "JSONDecodeError" for item in caught.value.diagnostics)


class _QuotaError(RuntimeError):
    status_code = 429
    body = {"error": {"code": "insufficient_quota"}}


def test_quota_is_classified_without_sdk_retry(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    factory = _Factory([_QuotaError("insufficient_quota")])
    with pytest.raises(legacy.OpenAIQuotaError) as caught:
        hardened.openai_analyze({}, cfg, _schema(cfg), client_factory=factory)
    assert len(factory.client.responses.calls) == 1
    assert caught.value.diagnostics[0]["error_type"] == "_QuotaError"


def test_authentication_failure_is_fatal_configuration(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    class AuthError(RuntimeError):
        status_code = 401
        body = {"error": {"code": "invalid_api_key"}}

    factory = _Factory([AuthError("invalid_api_key")])
    with pytest.raises(hardened.FatalAnalystConfigurationError):
        hardened.openai_analyze({}, cfg, _schema(cfg), client_factory=factory)
    assert len(factory.client.responses.calls) == 1


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _trade(index: int) -> dict:
    return {
        "trade_id": f"trade:{index}",
        "observed_at_utc": f"2026-09-0{index}T12:00:00Z",
        "branch": "legislative",
        "source": "house",
        "report_id": f"report-{index}",
        "filer": "Example Filer",
        "owner": "Self",
        "asset": f"Example {index} Common Stock",
        "ticker": f"EX{index}",
        "asset_type": "Stock",
        "transaction_type": "Purchase",
        "transaction_date": "2026-08-25",
        "filed_date": "2026-09-01",
        "amount": "$15,001 - $50,000",
        "source_url": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/{index}.pdf",
        "equity_like": True,
        "parse_confidence": "high",
    }


def _filing(index: int) -> dict:
    return {
        "filing_key": f"house|report-{index}",
        "source": "house",
        "report_id": f"report-{index}",
        "filer": "Example Filer",
        "filed_date": "2026-09-01",
        "source_url": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/{index}.pdf",
        "status": "processed",
    }


def _prepare(cfg: legacy.AnalystConfig, count: int = 1) -> None:
    trades = [_trade(index) for index in range(1, count + 1)]
    filings = [_filing(index) for index in range(1, count + 1)]
    _write_jsonl(cfg.legislative_dir / "transactions.jsonl", trades)
    _write_jsonl(cfg.legislative_dir / "filings.jsonl", filings)
    cfg.executive_dir.mkdir(parents=True, exist_ok=True)


def _isolate_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hardened.legacy.InvestorEdgeRuntime,
        "create",
        lambda *_args, **_kwargs: SimpleNamespace(enabled=False),
    )
    monkeypatch.setattr(hardened.legacy, "maintain_investor_edge", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(hardened.legacy, "load_sec_ticker_map", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        hardened.legacy,
        "market_context",
        lambda trade, *_args, **_kwargs: {
            "ticker": trade["ticker"],
            "current_price": 10.0,
            "transaction_date_close": None,
            "quote_timestamp_utc": "2026-09-04T20:00:00Z",
            "data_status": "partial",
            "providers": ["fixture"],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        hardened.legacy,
        "sec_context",
        lambda ticker, *_args, **_kwargs: {
            "ticker": ticker,
            "status": "unavailable",
            "company": "",
            "cik": None,
            "recent_filings": [],
            "form4_transactions": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        hardened.legacy,
        "document_text",
        lambda trade, filing, *_args, **_kwargs: {
            "status": "not_requested",
            "url": filing.get("source_url") or trade.get("source_url"),
            "text": "",
            "content_hash": "",
        },
    )
    monkeypatch.setattr(
        hardened.legacy,
        "update_paper_positions",
        lambda *_args, **_kwargs: ([], 0, 0),
    )


def test_candidate_failure_publishes_degraded_state_and_next_cycle_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _config(tmp_path)
    _prepare(cfg)
    _isolate_runtime(monkeypatch)
    forbidden_delivery = lambda *_args, **_kwargs: pytest.fail(
        "A deferred candidate must not enter alert delivery"
    )
    monkeypatch.setattr(hardened.legacy, "_notification_post", forbidden_delivery)
    monkeypatch.setattr(hardened.legacy, "_send_candidate_email", forbidden_delivery)

    malformed = _Factory([_response("{"), _response("{"), _response("{")])
    first = hardened.run_analyst(cfg, client_factory=malformed)
    assert first.run_status == "degraded"
    assert first.state_publishable and first.success
    assert first.completed_count == 0
    assert len(first.deferred_candidates) == 1
    assert not first.fatal_errors
    assert not first.delivery_phase_started
    state, _ = legacy.load_state(cfg.ai_dir / "state.json")
    assert state.last_success_utc == first.finished_utc
    assert not state.completed_analysis_ids

    valid = _Factory([_response(json.dumps(_payload()))])
    second = hardened.run_analyst(cfg, client_factory=valid)
    assert second.run_status == "success"
    assert second.state_publishable and second.success
    assert second.completed_count == 1
    assert not second.deferred_candidates
    state, _ = legacy.load_state(cfg.ai_dir / "state.json")
    assert len(state.completed_analysis_ids) == 1
    assert state.last_success_utc == second.finished_utc

    third = hardened.run_analyst(cfg, client_factory=_Factory([]))
    assert third.run_status == "success"
    assert third.completed_count == 0
    assert third.skipped_existing_count == 1


def test_quota_defers_remaining_batch_and_preserves_publishable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = _config(tmp_path)
    _prepare(cfg, count=2)
    _isolate_runtime(monkeypatch)
    result = hardened.run_analyst(cfg, client_factory=_Factory([_QuotaError("insufficient_quota")]))
    assert result.run_status == "degraded"
    assert result.state_publishable and result.success
    assert result.attempted_count == 1
    assert len(result.deferred_candidates) == 2
    assert {item["reason"] for item in result.deferred_candidates} == {
        "openai_quota_unavailable",
        "not_attempted_after_openai_quota",
    }


def test_delivery_checkpoint_marks_uncertainty_before_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = replace(
        _config(tmp_path),
        suppress_alerts=False,
        pushover_api_token="token",
        pushover_user_key="user",
        require_pushover=True,
    )
    state = legacy.AIState(
        candidate_alert_deliveries={
            "delivery": {
                "requested_channels": ["pushover"],
                "delivered_channels": {},
                "channel_errors": {},
                "alert": {"title": "test", "message": "test", "url": ""},
            }
        }
    )
    state_path = cfg.ai_dir / "state.json"
    state_path.parent.mkdir(parents=True)
    legacy.save_state(state_path, state)
    result = hardened.AnalystRunResult(started_utc=legacy.iso_utc())
    monkeypatch.setattr(
        hardened.legacy,
        "_notification_post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unknown send outcome")),
    )
    hardened._deliver_pending_candidate_alerts(cfg, result, state, state_path)
    assert result.delivery_phase_started
    assert result.delivery_attempt_count == 1
    assert result.delivery_uncertain_count == 1
    checkpoint = json.loads(cfg.result_path.read_text())
    assert checkpoint["delivery_phase_started"] is True
    assert checkpoint["delivery_uncertain_count"] == 1
    assert checkpoint["state_publishable"] is False
