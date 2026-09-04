from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ai_filing_analyst import (
    AnalystConfig,
    AIState,
    OpenAIResult,
    OpenAIQuotaError,
    analysis_id_for_trade,
    analysis_needs_market_refresh,
    build_analysis_record,
    build_entry_plan,
    deterministic_score,
    eligible_trade,
    is_official_disclosure_url,
    historical_trade_id,
    load_complete_retained_transaction_history,
    load_tracker_data,
    load_state,
    load_rules,
    open_paper_position,
    openai_analyze,
    parse_form4_transactions,
    refresh_analysis_market,
    repeated_same_direction_count,
    run_analyst,
    save_state,
    select_new_analysis_candidates,
    signal_direction,
    update_paper_positions,
)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sample_trade() -> dict[str, object]:
    return {
        "trade_id": "trade:example",
        "observed_at_utc": "2026-08-26T12:00:00Z",
        "branch": "legislative",
        "source": "house",
        "report_id": "house:2026:100",
        "filer": "Example Representative",
        "chamber": "House",
        "title": "Representative",
        "agency": "",
        "owner": "Self",
        "asset": "Example Corporation Common Stock (EXM)",
        "ticker": "EXM",
        "asset_type": "Stock",
        "transaction_type": "Purchase",
        "transaction_date": "2026-08-24",
        "notification_date": "2026-08-25",
        "filed_date": "2026-08-25",
        "amount": "$100,001 - $250,000",
        "source_url": "https://example.test/house-100.pdf",
        "raw_row": "Example Corporation Purchase $100,001 - $250,000",
        "equity_like": True,
        "parse_confidence": "high",
    }


def sample_filing() -> dict[str, object]:
    return {
        "filing_key": "house|house:2026:100",
        "source": "house",
        "report_id": "house:2026:100",
        "filer": "Example Representative",
        "filed_date": "2026-08-25",
        "source_url": "https://example.test/house-100.pdf",
        "title": "Representative",
        "agency": "",
        "status": "processed",
    }


def sample_ai_payload() -> dict[str, object]:
    return {
        "analysis_summary": "A recent, relatively large direct-household purchase with limited price movement warrants review.",
        "transaction_intent": "likely_discretionary",
        "owner_significance": "direct_household",
        "filer_relevance_score": 18,
        "policy_contract_relevance_score": 13,
        "market_confirmation_score": 8,
        "confidence": 0.84,
        "positive_factors": ["Direct household ownership", "Recent filing"],
        "negative_factors": ["Disclosed value is a range"],
        "contradictory_evidence": [],
        "evidence_sources": [
            {
                "title": "Official filing",
                "url": "https://example.test/house-100.pdf",
                "published_date": "2026-08-25",
                "claim": "The filing reports the purchase.",
            },
            {
                "title": "Official committee jurisdiction",
                "url": "https://example.test/committee-jurisdiction",
                "published_date": "2026-08-25",
                "claim": "The filer has documented jurisdiction relevant to the issuer.",
            },
        ],
        "external_context_status": "found",
    }


def config_for(tmp_path: Path) -> AnalystConfig:
    root = Path(__file__).resolve().parents[1]
    return AnalystConfig(
        legislative_dir=tmp_path / "legislative",
        executive_dir=tmp_path / "executive",
        ai_dir=tmp_path / "ai",
        schema_path=root / "schemas/ai_filing_analysis.schema.json",
        rules_path=root / "config/signal_rules.yml",
        result_path=tmp_path / "ai-result.json",
        analyses_csv_path=tmp_path / "analyses.csv",
        portfolio_csv_path=tmp_path / "portfolio.csv",
        enabled=True,
        paper_trading_only=True,
        reanalyze_existing=False,
        suppress_alerts=True,
        max_analyses=20,
        model="gpt-5.6-terra",
        reasoning_effort="medium",
        web_search_enabled=True,
        fetch_document_text=False,
        openai_api_key="test-key",
        finnhub_api_key="",
        alphavantage_api_key="",
        alphavantage_entitlement="",
        sec_user_agent="",
        pushover_api_token="",
        pushover_user_key="",
        require_pushover=False,
        dashboard_url="https://example.test/dashboard/",
        repository_url="https://github.com/example/PolitiTrack",
        max_download_bytes=25 * 1024 * 1024,
        max_ocr_pages=75,
        request_timeout=(1.0, 1.0),
    )


def test_canonical_history_combines_both_branches_without_candidate_truncation(tmp_path: Path) -> None:
    cfg = replace(config_for(tmp_path), max_analyses=1)
    trades = [dict(sample_trade(), trade_id=f"trade:history-{index}", filer=f"Retained Filer {index}",
                   branch="legislative" if index < 2 else "executive",
                   source="house" if index < 2 else "oge") for index in range(4)]
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", trades[:2])
    write_jsonl(cfg.executive_dir / "transactions.jsonl", trades[2:])
    history, _ = load_complete_retained_transaction_history(cfg)
    candidates, skipped = select_new_analysis_candidates(history, cfg, AIState(), "rules")
    assert len(candidates) == 1 and skipped == 0
    assert len(history) == 4
    assert {trade["branch"] for trade in history} == {"legislative", "executive"}
    assert {trade["trade_id"] for trade in history} == {trade["trade_id"] for trade in trades}
    for original in trades:
        loaded = next(trade for trade in history if trade["trade_id"] == original["trade_id"])
        assert all(loaded[key] == value for key, value in original.items())


def test_history_deduplicates_overlap_and_prefers_normalized_ledger(tmp_path: Path) -> None:
    cfg = config_for(tmp_path)
    original = sample_trade()
    stale_purchase = dict(original, parse_confidence="low", equity_like=False)
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", [original, original])
    write_jsonl(cfg.legislative_dir / "purchases.jsonl", [stale_purchase])
    write_jsonl(cfg.executive_dir / "purchases.jsonl", [stale_purchase])
    history, _ = load_complete_retained_transaction_history(cfg)
    assert len(history) == 1
    assert history[0]["trade_id"] == original["trade_id"]
    assert history[0]["parse_confidence"] == "high"
    assert history[0]["equity_like"] is True
    assert {origin["ledger"] for origin in history[0]["history_provenance"]} == {
        "transactions.jsonl", "purchases.jsonl"
    }


def test_legacy_id_fallback_is_deterministic_and_owner_specific(tmp_path: Path) -> None:
    cfg = config_for(tmp_path)
    old = sample_trade()
    old.pop("trade_id")
    spouse = dict(old, owner="Spouse")
    joint = dict(old, owner="Joint")
    dependent = dict(old, owner="Dependent")
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", [old, spouse, joint, dependent, old])
    write_jsonl(cfg.executive_dir / "transactions.jsonl", [old])
    first, _ = load_complete_retained_transaction_history(cfg)
    second, _ = load_complete_retained_transaction_history(cfg)
    assert first == second and len(first) == 4
    assert len({trade["trade_id"] for trade in first}) == 4
    assert historical_trade_id(old) == historical_trade_id(dict(old, observed_at_utc="2026-08-30T00:00:00Z"))
    assert all(trade["trade_id"].startswith("historical-trade:") for trade in first)
    assert all(trade["trade_id_origin"] == "historical_fallback_v1" for trade in first)
    assert "trade_id" not in old


def test_history_retains_first_observation_and_purchase_only_compatibility(tmp_path: Path) -> None:
    old = sample_trade()
    later = dict(old, observed_at_utc="2026-08-31T11:00:00Z", comment="retained later parse")
    write_jsonl(tmp_path / "transactions.jsonl", [old, later])
    fallback = dict(old, trade_id="trade:pre-ledger", branch="")
    write_jsonl(tmp_path / "purchases.jsonl", [fallback])
    history, _ = load_tracker_data(tmp_path, branch="legislative")
    primary = next(row for row in history if row["trade_id"] == old["trade_id"])
    assert primary["observed_at_utc"] == old["observed_at_utc"]
    assert primary["comment"] == later["comment"]
    assert len(history) == 2 and all(row["branch"] == "legislative" for row in history)


def test_legacy_fallback_uses_available_report_provenance() -> None:
    old = sample_trade()
    old.pop("trade_id")
    old.pop("report_id")
    other_report = dict(old, source_url="https://example.test/other-retained-filing.pdf")
    assert historical_trade_id(old) != historical_trade_id(other_report)
    assert historical_trade_id(dict(old, filing_key="house|old-one")) != historical_trade_id(
        dict(old, filing_key="house|old-two")
    )


def test_zero_candidates_still_publishes_entire_historical_population(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = replace(config_for(tmp_path), suppress_alerts=False, reanalyze_existing=True,
                  pushover_api_token="test-only-token", pushover_user_key="test-only-user")
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "true")
    history = [dict(sample_trade(), trade_id=f"trade:bootstrap-{index}",
                    filer=f"Historical Filer {index}", historical_bootstrap=True,
                    source="house" if index < 2 else "oge",
                    branch="legislative" if index < 2 else "executive") for index in range(4)]
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", history[:2])
    write_jsonl(cfg.executive_dir / "transactions.jsonl", history[2:])

    def forbidden(*_args: object, **_kwargs: object) -> object:
        pytest.fail("A zero-candidate historical maintenance run must not use AI/SEC/alerts")

    for name in ("openai_analyze", "load_sec_ticker_map", "market_context", "notify_candidate"):
        monkeypatch.setattr(f"scripts.ai_filing_analyst.{name}", forbidden)
    monkeypatch.setattr("scripts.ai_filing_analyst.requests.post", forbidden)
    first = run_analyst(cfg)
    assert first.success and first.completed_count == first.attempted_count == first.alerted_count == 0
    assert first.historical_transaction_count == first.historical_bootstrap_transaction_count == 4
    profiles = json.loads((cfg.ai_dir / "investor-edge-profiles.json").read_text())["profiles"]
    leaderboard = json.loads((cfg.ai_dir / "investor-edge-leaderboard.json").read_text())
    assert len(profiles) == len(leaderboard["investors"]) == 4
    assert leaderboard["branch_transaction_counts"] == {"legislative": 2, "executive": 2}
    assert leaderboard["building_profile_count"] == 4
    assert not (cfg.ai_dir / "analyses.jsonl").exists()
    saved_state = json.loads((cfg.ai_dir / "state.json").read_text())
    assert saved_state["completed_analysis_ids"] == saved_state["candidate_alert_deliveries"] == {}
    second = run_analyst(cfg)
    assert second.success and second.completed_count == second.alerted_count == 0
    assert len(json.loads((cfg.ai_dir / "investor-edge-leaderboard.json").read_text())["investors"]) == 4


def test_historical_bootstrap_cannot_queue_candidate_alerts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.ai_filing_analyst import _queue_candidate_alert, notify_candidate
    cfg = replace(config_for(tmp_path), suppress_alerts=False,
                  pushover_api_token="test-only-token", pushover_user_key="test-only-user")
    state = AIState()
    historical = {"historical_bootstrap": True, "trade_id": "trade:old", "classification": "high_priority"}
    monkeypatch.setattr("scripts.ai_filing_analyst.requests.post", lambda *_a, **_k: pytest.fail("No old-history alerts"))
    assert _queue_candidate_alert(cfg, historical, state) is None
    assert notify_candidate(cfg, historical, state=state) is False
    assert state.candidate_alert_deliveries == {}


@pytest.mark.parametrize("failure", ["refresh", "save"])
@pytest.mark.parametrize("phase", ["initial", "final"])
def test_global_maintenance_failure_cannot_be_a_successful_state_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, phase: str
) -> None:
    from scripts.ai_filing_analyst import InvestorEdgeRuntime

    class BrokenRuntime:
        enabled = True
        refresh_count = 0
        save_count = 0

        def refresh_leaderboard(self, *_args: object, **_kwargs: object) -> list:
            self.refresh_count += 1
            if failure == "refresh" and self.refresh_count == (1 if phase == "initial" else 2):
                raise RuntimeError("global history refresh failed")
            return []

        def save(self, *_args: object) -> None:
            self.save_count += 1
            if failure == "save" and self.save_count == (1 if phase == "initial" else 2):
                raise OSError("durable history write failed")

    cfg = replace(config_for(tmp_path), suppress_alerts=False)
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", [
        dict(sample_trade(), historical_bootstrap=phase == "final")
    ])
    cfg.ai_dir.mkdir(parents=True)
    saved_success = "2026-08-20T00:00:00Z"
    save_state(cfg.ai_dir / "state.json", AIState(last_success_utc=saved_success))
    monkeypatch.setattr(InvestorEdgeRuntime, "create", lambda **_kwargs: BrokenRuntime())
    for name in ("_retry_pending_candidate_alerts", "notify_candidate", "requests.post"):
        monkeypatch.setattr(f"scripts.ai_filing_analyst.{name}",
                            lambda *_a, **_k: pytest.fail("No alerts in a failed maintenance run"))
    if phase == "initial":
        for name in ("openai_analyze", "load_sec_ticker_map", "market_context", "update_paper_positions"):
            monkeypatch.setattr(f"scripts.ai_filing_analyst.{name}",
                                lambda *_a, **_k: pytest.fail("Stop work after initial maintenance failure"))
    result = run_analyst(cfg)
    assert not result.success
    assert result.attempted_count == result.alerted_count == 0
    assert result.investor_edge_maintenance_status == "failed"
    assert any("must not be promoted" in error for error in result.errors)
    assert json.loads((cfg.ai_dir / "state.json").read_text())["last_success_utc"] == saved_success
    run = json.loads((cfg.ai_dir / "runs.jsonl").read_text().splitlines()[-1])
    assert run["investor_edge_maintenance_status"] == "failed" and not run["success"]


def test_zero_unanalyzed_candidates_refreshes_existing_normal_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from scripts.ai_filing_analyst import json_hash
    cfg = config_for(tmp_path)
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "true")
    history = [dict(sample_trade(), trade_id=f"trade:already-analyzed-{index}",
                    filer=f"Retained Filer {index}") for index in range(4)]
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", history)
    cfg.ai_dir.mkdir(parents=True)
    rules_hash = json_hash(load_rules(cfg.rules_path))
    save_state(cfg.ai_dir / "state.json", AIState(completed_analysis_ids={
        analysis_id_for_trade(trade, model=cfg.model, rules_hash=rules_hash): "2026-08-28T00:00:00Z"
        for trade in history
    }))
    for name in ("openai_analyze", "load_sec_ticker_map", "market_context"):
        monkeypatch.setattr(f"scripts.ai_filing_analyst.{name}", lambda *_a, **_k: pytest.fail("No candidate work expected"))
    result = run_analyst(cfg)
    assert result.success and result.investor_edge_maintenance_status == "complete"
    assert result.skipped_existing_count == 4 and result.attempted_count == 0
    assert result.historical_bootstrap_transaction_count == 0
    leaderboard = json.loads((cfg.ai_dir / "investor-edge-leaderboard.json").read_text())
    assert leaderboard["published_profile_count"] == 4


def test_deterministic_score_and_entry_plan_are_bounded() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    trade = sample_trade()
    market = {
        "current_price": 101.0,
        "transaction_date_close": 100.0,
        "atr_14": 2.0,
        "average_volume_20d": 2_000_000,
    }
    score = deterministic_score(
        trade,
        sample_ai_payload(),
        market,
        [trade],
        rules,
    )
    assert 80 <= score["score"] <= 100
    assert score["classification"] == "high_priority"
    assert score["components"]["transaction_quality"] <= 20
    plan = build_entry_plan(trade, market, score["score"], rules)
    assert plan["entry_status"] == "review_now"
    assert plan["review_band_low"] < plan["review_band_high"]
    assert plan["position_allocation_percent"] == 1.0
    assert plan["paper_only"] is True



def test_sale_is_bearish_signal_and_never_opens_paper_position() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    sale = sample_trade()
    sale.update(
        {
            "trade_id": "trade:sale",
            "transaction_type": "Sale (Partial)",
            "transaction_date": "2026-08-24",
        }
    )
    earlier_sale = dict(sale)
    earlier_sale.update(
        {
            "trade_id": "trade:sale-earlier",
            "transaction_date": "2026-08-20",
        }
    )
    market = {
        "current_price": 99.0,
        "transaction_date_close": 100.0,
        "atr_14": 2.0,
        "average_volume_20d": 2_000_000,
    }

    assert eligible_trade(sale, rules) is True
    assert signal_direction(sale) == "bearish"
    assert repeated_same_direction_count(sale, [earlier_sale, sale]) == 1

    scored = deterministic_score(
        sale,
        sample_ai_payload(),
        market,
        [earlier_sale, sale],
        rules,
    )
    assert scored["signal_direction"] == "bearish"
    assert scored["repeated_same_direction_count_90d"] == 1
    assert not any(
        item["reason"] == "Transaction is not a purchase"
        for item in scored["hard_caps"]
    )

    plan = build_entry_plan(sale, market, scored["score"], rules)
    assert plan["signal_direction"] == "bearish"
    assert plan["entry_status"] == "bearish_caution"
    assert plan["position_allocation_percent"] == 0.0

    analysis = {
        "trade_id": sale["trade_id"],
        "analysis_id": "analysis:sale",
        "ticker": sale["ticker"],
        "filer": sale["filer"],
        "owner": sale["owner"],
        "source_url": sale["source_url"],
        "score": scored["score"],
        "classification": scored["classification"],
        "transaction_type": sale["transaction_type"],
        "signal_direction": "bearish",
        "entry_plan": plan,
    }
    assert open_paper_position(analysis, AIState(), rules) is None


def test_contextual_score_requires_external_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    payload = sample_ai_payload()
    payload["evidence_sources"] = [payload["evidence_sources"][0]]
    score = deterministic_score(
        sample_trade(),
        payload,
        {
            "current_price": 101.0,
            "transaction_date_close": 100.0,
            "atr_14": 2.0,
            "average_volume_20d": 2_000_000,
        },
        [sample_trade()],
        rules,
    )
    assert score["score"] <= 64
    assert any(
        item["reason"] == "High contextual scores lack external supporting evidence"
        for item in score["hard_caps"]
    )


def test_missing_market_data_applies_hard_cap() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    score = deterministic_score(
        sample_trade(),
        sample_ai_payload(),
        {"current_price": None, "transaction_date_close": None},
        [sample_trade()],
        rules,
    )
    assert score["score"] <= 59
    assert any(item["reason"] == "Current market price unavailable" for item in score["hard_caps"])


def test_official_disclosure_url_allowlist() -> None:
    assert is_official_disclosure_url(
        "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/100.pdf"
    )
    assert is_official_disclosure_url(
        "https://efdsearch.senate.gov/search/view/ptr/abc/"
    )
    assert is_official_disclosure_url(
        "https://extapps2.oge.gov/201/Presiden.nsf/example.pdf"
    )
    assert not is_official_disclosure_url("http://disclosures-clerk.house.gov/file.pdf")
    assert not is_official_disclosure_url("https://house.gov.evil.example/file.pdf")
    assert not is_official_disclosure_url("https://example.test/filing.pdf")


def test_parse_form4_open_market_transactions() -> None:
    xml = b"""<?xml version='1.0'?>
    <ownershipDocument>
      <issuer><issuerName>Example Corporation</issuerName><issuerTradingSymbol>EXM</issuerTradingSymbol></issuer>
      <reportingOwner><reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId></reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-08-24</value></transactionDate>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>1000</value></transactionShares>
            <transactionPricePerShare><value>10.25</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
          <postTransactionAmounts><sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
          <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
        </nonDerivativeTransaction>
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-08-24</value></transactionDate>
          <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
    </ownershipDocument>"""
    rows = parse_form4_transactions(xml)
    assert len(rows) == 1
    assert rows[0]["transaction_code"] == "P"
    assert rows[0]["direction"] == "acquired"
    assert rows[0]["reporting_owners"] == ["DOE JANE"]
    assert rows[0]["ticker"] == "EXM"


def test_openai_call_uses_responses_structured_output() -> None:
    captured: dict[str, object] = {}

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_test",
                status="completed",
                output_text=json.dumps(sample_ai_payload()),
                usage=SimpleNamespace(input_tokens=123, output_tokens=45),
            )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs
            self.responses = FakeResponses()

    cfg = config_for(Path("/tmp"))
    schema = json.loads(cfg.schema_path.read_text(encoding="utf-8"))
    result = openai_analyze(
        {"candidate_transaction": sample_trade()},
        cfg,
        schema,
        client_factory=FakeClient,
    )
    assert result.response_id == "resp_test"
    assert result.payload["filer_relevance_score"] == 18
    assert captured["model"] == "gpt-5.6-terra"
    assert captured["reasoning"] == {"effort": "medium"}
    assert captured["tools"] == [{"type": "web_search"}]
    text = captured["text"]
    assert isinstance(text, dict)
    assert text["format"]["type"] == "json_schema"
    assert text["format"]["strict"] is True
    assert captured["store"] is False



def test_openai_insufficient_quota_is_not_retried() -> None:
    calls = {"count": 0}

    class FakeQuotaError(Exception):
        status_code = 429
        body = {
            "message": "You exceeded your current quota",
            "type": "insufficient_quota",
            "code": "insufficient_quota",
        }

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            calls["count"] += 1
            raise FakeQuotaError("429 insufficient_quota")

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["max_retries"] == 0
            self.responses = FakeResponses()

    cfg = config_for(Path("/tmp"))
    schema = json.loads(
        cfg.schema_path.read_text(encoding="utf-8")
    )

    with pytest.raises(OpenAIQuotaError, match="quota"):
        openai_analyze(
            {"candidate_transaction": sample_trade()},
            cfg,
            schema,
            client_factory=FakeClient,
        )

    assert calls["count"] == 1


def test_openai_transient_429_is_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    class FakeRateLimitError(Exception):
        status_code = 429
        body = {
            "message": "Requests per minute exceeded",
            "type": "rate_limit_exceeded",
            "code": "rate_limit_exceeded",
        }

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            calls["count"] += 1
            if calls["count"] < 3:
                raise FakeRateLimitError(
                    "429 rate_limit_exceeded"
                )
            return SimpleNamespace(
                id="resp_retry",
                status="completed",
                output_text=json.dumps(
                    sample_ai_payload()
                ),
                usage=SimpleNamespace(
                    input_tokens=10,
                    output_tokens=5,
                ),
            )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["max_retries"] == 0
            self.responses = FakeResponses()

    monkeypatch.setattr(
        "scripts.ai_filing_analyst.time.sleep",
        lambda seconds: sleeps.append(
            float(seconds)
        ),
    )

    cfg = config_for(Path("/tmp"))
    schema = json.loads(
        cfg.schema_path.read_text(encoding="utf-8")
    )

    result = openai_analyze(
        {"candidate_transaction": sample_trade()},
        cfg,
        schema,
        client_factory=FakeClient,
    )

    assert result.response_id == "resp_retry"
    assert calls["count"] == 3
    assert sleeps == [1.0, 2.0]


def test_ai_batch_stops_after_first_quota_failure(
    tmp_path: Path,
) -> None:
    cfg = config_for(tmp_path)

    first = sample_trade()
    second = dict(first)
    second.update(
        {
            "trade_id": "trade:second",
            "ticker": "EX2",
            "asset": (
                "Example Two Corporation "
                "Common Stock (EX2)"
            ),
        }
    )

    write_jsonl(
        cfg.legislative_dir / "transactions.jsonl",
        [first, second],
    )
    write_jsonl(
        cfg.legislative_dir / "filings.jsonl",
        [sample_filing()],
    )

    (
        cfg.legislative_dir / "state.json"
    ).write_text("{}", encoding="utf-8")

    cfg.executive_dir.mkdir(parents=True)

    (
        cfg.executive_dir / "state.json"
    ).write_text("{}", encoding="utf-8")

    calls = {"count": 0}

    class FakeQuotaError(Exception):
        status_code = 429
        body = {
            "message": "You exceeded your current quota",
            "type": "insufficient_quota",
            "code": "insufficient_quota",
        }

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            calls["count"] += 1
            raise FakeQuotaError(
                "429 insufficient_quota"
            )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.responses = FakeResponses()

    result = run_analyst(
        cfg,
        client_factory=FakeClient,
    )

    assert result.success is True
    assert result.run_status == "degraded"
    assert result.state_publishable is True
    assert result.attempted_count == 1
    assert calls["count"] == 1
    assert result.errors == []
    assert len(result.deferred_candidates) == 2
    assert result.deferred_candidates[0]["reason"] == "openai_quota_unavailable"
    assert result.deferred_candidates[1]["reason"] == "not_attempted_after_openai_quota"
    assert any(
        "remaining ai analyses were deferred"
        in item.casefold()
        for item in result.warnings
    )


@pytest.mark.parametrize("fail_final_publication", [False, True])
def test_full_run_is_incremental_and_opens_paper_position(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_final_publication: bool
) -> None:
    cfg = replace(config_for(tmp_path), suppress_alerts=False)
    if fail_final_publication:
        from scripts.ai_filing_analyst import maintain_investor_edge
        cfg = replace(cfg, pushover_api_token="test-token", pushover_user_key="test-user")

        def fail_final_maintenance(*args: object, **kwargs: object) -> bool | None:
            if kwargs.get("allow_backfill") is False:
                return False
            return maintain_investor_edge(*args, **kwargs)

        monkeypatch.setattr("scripts.ai_filing_analyst.maintain_investor_edge", fail_final_maintenance)
        monkeypatch.setattr("scripts.ai_filing_analyst.requests.post",
                            lambda *_a, **_k: pytest.fail("No candidate send before final publication"))
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "true")
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", [sample_trade()])
    write_jsonl(cfg.legislative_dir / "filings.jsonl", [sample_filing()])
    (cfg.legislative_dir / "state.json").write_text("{}", encoding="utf-8")
    cfg.executive_dir.mkdir(parents=True)
    (cfg.executive_dir / "state.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.ai_filing_analyst.market_context",
        lambda *args, **kwargs: {
            "ticker": "EXM",
            "providers": ["test"],
            "current_price": 101.0,
            "transaction_date_close": 100.0,
            "atr_14": 2.0,
            "average_volume_20d": 2_000_000,
            "data_status": "complete",
            "errors": [],
        },
    )
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.load_sec_ticker_map", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.sec_context",
        lambda *args, **kwargs: {
            "ticker": "EXM",
            "status": "complete",
            "company": "Example Corporation",
            "recent_filings": [],
            "form4_transactions": [],
            "errors": [],
        },
    )

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            return SimpleNamespace(
                id="resp_run",
                status="completed",
                output_text=json.dumps(sample_ai_payload()),
                usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.responses = FakeResponses()

    first = run_analyst(cfg, client_factory=FakeClient)
    if fail_final_publication:
        assert not first.success and first.investor_edge_maintenance_status == "failed"
        assert first.completed_count == 1 and first.alerted_count == 0
        state = json.loads((cfg.ai_dir / "state.json").read_text())
        assert state["last_success_utc"] is None
        assert len(state["candidate_alert_deliveries"]) == 1
        assert all(not row["delivered_channels"] for row in state["candidate_alert_deliveries"].values())
        return
    assert first.success is True
    assert first.completed_count == 1
    assert first.high_priority_count == 1
    assert first.alerted_count == 0
    assert first.paper_positions_opened == 1
    analyses = [json.loads(line) for line in (cfg.ai_dir / "analyses.jsonl").read_text().splitlines()]
    assert analyses[0]["ticker"] == "EXM"
    assert analyses[0]["investor_edge_modifier"] == 0
    assert analyses[0]["investor_edge"]["sample_count"] == 0
    assert (cfg.ai_dir / "investor-edge-profiles.json").exists()
    assert (cfg.ai_dir / "investor-edge-leaderboard.json").exists()
    state = json.loads((cfg.ai_dir / "state.json").read_text())
    assert len(state["positions"]) == 1
    assert cfg.analyses_csv_path.exists()
    assert cfg.portfolio_csv_path.exists()

    second = run_analyst(cfg, client_factory=FakeClient)
    assert second.success is True
    assert second.completed_count == 0
    assert second.skipped_existing_count == 1


def test_candidate_delivery_retries_only_failed_channel_without_reanalysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = replace(
        config_for(tmp_path),
        suppress_alerts=False,
        pushover_api_token="app-token",
        pushover_user_key="user-key",
        require_pushover=True,
        gmail_address="alerts@example.test",
        gmail_app_password="app-password",
    )
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "false")
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", [sample_trade()])
    write_jsonl(cfg.legislative_dir / "filings.jsonl", [sample_filing()])
    (cfg.legislative_dir / "state.json").write_text("{}", encoding="utf-8")
    cfg.executive_dir.mkdir(parents=True)
    (cfg.executive_dir / "state.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "scripts.ai_filing_analyst.market_context",
        lambda *args, **kwargs: {
            "ticker": "EXM",
            "providers": ["test"],
            "current_price": 101.0,
            "transaction_date_close": 100.0,
            "atr_14": 2.0,
            "average_volume_20d": 2_000_000,
            "data_status": "complete",
            "errors": [],
        },
    )
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.load_sec_ticker_map", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.sec_context",
        lambda *args, **kwargs: {
            "ticker": "EXM",
            "status": "complete",
            "company": "Example Corporation",
            "recent_filings": [],
            "form4_transactions": [],
            "errors": [],
        },
    )

    openai_calls = {"count": 0}
    pushover_calls = {"count": 0}
    smtp_attempts = {"count": 0}
    email_sends = {"count": 0}

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            openai_calls["count"] += 1
            return SimpleNamespace(
                id="resp_delivery_retry",
                status="completed",
                output_text=json.dumps(sample_ai_payload()),
                usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.responses = FakeResponses()

    def fake_pushover(*_args: object, **_kwargs: object) -> object:
        pushover_calls["count"] += 1
        return SimpleNamespace(status_code=200, text="ok")

    class FlakySMTP:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            smtp_attempts["count"] += 1
            if smtp_attempts["count"] == 1:
                raise OSError("temporary SMTP outage")

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def login(self, address: str, password: str) -> None:
            assert (address, password) == ("alerts@example.test", "app-password")

        def send_message(self, _message: object) -> None:
            email_sends["count"] += 1

    monkeypatch.setattr("scripts.ai_filing_analyst.requests.post", fake_pushover)
    monkeypatch.setattr("scripts.ai_filing_analyst.smtplib.SMTP_SSL", FlakySMTP)

    first = run_analyst(cfg, client_factory=FakeClient)
    assert first.success is True
    assert first.completed_count == 1
    assert first.alerted_count == 1
    assert openai_calls["count"] == 1
    assert pushover_calls["count"] == 1
    assert smtp_attempts["count"] == 1
    assert email_sends["count"] == 0

    first_state = json.loads((cfg.ai_dir / "state.json").read_text(encoding="utf-8"))
    assert len(first_state["candidate_alert_deliveries"]) == 1
    first_delivery = next(iter(first_state["candidate_alert_deliveries"].values()))
    assert set(first_delivery["delivered_channels"]) == {"pushover"}
    assert "gmail" in first_delivery["channel_errors"]

    second = run_analyst(cfg, client_factory=FakeClient)
    assert second.success is True
    assert second.completed_count == 0
    assert second.skipped_existing_count == 1
    assert second.alerted_count == 1
    assert openai_calls["count"] == 1
    assert pushover_calls["count"] == 1
    assert smtp_attempts["count"] == 2
    assert email_sends["count"] == 1

    second_state = json.loads((cfg.ai_dir / "state.json").read_text(encoding="utf-8"))
    second_delivery = next(iter(second_state["candidate_alert_deliveries"].values()))
    assert set(second_delivery["delivered_channels"]) == {"pushover", "gmail"}
    assert second_delivery["channel_errors"] == {}

    third = run_analyst(cfg, client_factory=FakeClient)
    assert third.success is True
    assert third.completed_count == 0
    assert third.alerted_count == 0
    assert openai_calls["count"] == 1
    assert pushover_calls["count"] == 1
    assert smtp_attempts["count"] == 2
    assert email_sends["count"] == 1


def test_ai_state_loads_without_alert_delivery_field(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "completed_analysis_ids": {"analysis:old": "2026-08-20T00:00:00Z"},
                "positions": {},
                "last_attempt_utc": None,
                "last_success_utc": None,
                "last_portfolio_refresh_utc": None,
            }
        ),
        encoding="utf-8",
    )

    state, loaded = load_state(state_path)
    assert loaded is True
    assert state.candidate_alert_deliveries == {}
    save_state(state_path, state)
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["candidate_alert_deliveries"] == {}


def test_market_refresh_reuses_ai_payload_and_can_upgrade_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = config_for(tmp_path)
    trade = sample_trade()
    write_jsonl(cfg.legislative_dir / "transactions.jsonl", [trade])
    write_jsonl(cfg.legislative_dir / "filings.jsonl", [sample_filing()])
    (cfg.legislative_dir / "state.json").write_text("{}", encoding="utf-8")
    cfg.executive_dir.mkdir(parents=True)
    (cfg.executive_dir / "state.json").write_text("{}", encoding="utf-8")

    market_calls = {"count": 0}

    def fake_market(*args: object, **kwargs: object) -> dict[str, object]:
        market_calls["count"] += 1
        if market_calls["count"] == 1:
            return {
                "ticker": "EXM",
                "providers": [],
                "current_price": None,
                "transaction_date_close": None,
                "atr_14": None,
                "average_volume_20d": None,
                "data_status": "unavailable",
                "errors": ["temporary market-data limit"],
            }
        return {
            "ticker": "EXM",
            "providers": ["test"],
            "current_price": 101.0,
            "transaction_date_close": 100.0,
            "atr_14": 2.0,
            "average_volume_20d": 2_000_000,
            "data_status": "complete",
            "errors": [],
        }

    monkeypatch.setattr("scripts.ai_filing_analyst.market_context", fake_market)
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.load_sec_ticker_map", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.sec_context",
        lambda *args, **kwargs: {
            "ticker": "EXM",
            "status": "complete",
            "company": "Example Corporation",
            "recent_filings": [],
            "form4_transactions": [],
            "errors": [],
        },
    )

    openai_calls = {"count": 0}

    class FakeResponses:
        def create(self, **kwargs: object) -> object:
            openai_calls["count"] += 1
            return SimpleNamespace(
                id="resp_refresh",
                status="completed",
                output_text=json.dumps(sample_ai_payload()),
                usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            )

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            self.responses = FakeResponses()

    first = run_analyst(cfg, client_factory=FakeClient)
    assert first.success is True
    assert first.completed_count == 1
    assert first.paper_positions_opened == 0
    first_analysis = json.loads(
        (cfg.ai_dir / "analyses.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert analysis_needs_market_refresh(first_analysis) is True
    assert first_analysis["score"] <= 59

    second = run_analyst(cfg, client_factory=FakeClient)
    assert second.success is True
    assert second.completed_count == 0
    assert second.skipped_existing_count == 1
    assert second.market_analyses_refreshed == 1
    assert second.market_signal_upgrades == 1
    assert second.paper_positions_opened == 1
    assert openai_calls["count"] == 1
    latest = json.loads(
        (cfg.ai_dir / "analyses.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert latest["classification"] == "high_priority"
    assert latest["entry_plan"]["entry_status"] == "review_now"
    assert latest["analysis_revision"] == 2


def test_refresh_analysis_market_preserves_ai_and_recomputes_rules() -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    trade = sample_trade()
    prior = {
        "analysis_id": "analysis:example",
        "trade_id": trade["trade_id"],
        "analysis_revision": 1,
        "ai": sample_ai_payload(),
        "market": {"current_price": None, "transaction_date_close": None},
        "score": 59,
        "classification": "weak_signal",
        "entry_plan": {"entry_status": "market_data_incomplete"},
    }
    refreshed = refresh_analysis_market(
        prior,
        trade,
        [trade],
        {
            "current_price": 101.0,
            "transaction_date_close": 100.0,
            "atr_14": 2.0,
            "average_volume_20d": 2_000_000,
        },
        rules,
    )
    assert refreshed["ai"] == prior["ai"]
    assert refreshed["analysis_revision"] == 2
    assert refreshed["classification"] == "high_priority"
    assert refreshed["entry_plan"]["entry_status"] == "review_now"


def test_native_analysis_record_applies_investor_edge_without_defeating_caps(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    trade = sample_trade()

    class FakeInvestorEdge:
        enabled = True

        def profile_for_trade(self, current, transactions):
            assert current is trade
            assert transactions == [trade]
            return {
                "modifier": 7,
                "edge_score": 79,
                "sample_count": 8,
                "confidence_label": "High",
            }

    record = build_analysis_record(
        trade=trade,
        filing=sample_filing(),
        ai_result=OpenAIResult(sample_ai_payload(), "resp_edge", 10, 5),
        market={
            "current_price": 101.0,
            "transaction_date_close": 100.0,
            "atr_14": 2.0,
            "average_volume_20d": 2_000_000,
        },
        sec={},
        document={"status": "not_requested", "content_hash": ""},
        all_transactions=[trade],
        rules=rules,
        rules_hash="edge-test-rules",
        config=config_for(tmp_path),
        investor_edge=FakeInvestorEdge(),
    )
    assert record["investor_edge_modifier"] == 7
    assert record["base_score"] <= record["score"]
    assert record["score"] <= 100
    assert record["entry_plan"]["paper_only"] is True


def test_paper_position_closes_at_evaluation_horizon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[1]
    rules = load_rules(root / "config/signal_rules.yml")
    cfg = replace(config_for(tmp_path), finnhub_api_key="test")
    state = AIState()
    analysis = {
        "trade_id": "trade:example",
        "analysis_id": "analysis:example",
        "ticker": "EXM",
        "filer": "Example Representative",
        "owner": "Self",
        "source_url": "https://example.test/filing",
        "score": 85,
        "classification": "high_priority",
        "entry_plan": {
            "position_allocation_percent": 1.0,
            "current_price": 100.0,
            "entry_status": "review_now",
        },
    }
    opened = open_paper_position(analysis, state, rules)
    assert opened is not None
    position = next(iter(state.positions.values()))
    position["evaluation_horizon_utc"] = "2020-01-01T00:00:00Z"
    monkeypatch.setattr(
        "scripts.ai_filing_analyst.fetch_finnhub_quote",
        lambda *args, **kwargs: {"current_price": 110.0},
    )
    events, updated, closed = update_paper_positions(
        state,
        cfg,
        rules,
        object(),  # fetch is mocked
        [],
    )
    assert updated == 0
    assert closed == 1
    assert events[0]["event_type"] == "close"
    assert events[0]["return_percent"] == 10.0
    assert events[0]["status"] == "closed"
