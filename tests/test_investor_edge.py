from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.investor_edge import (
    MAX_MODIFIER_LIMIT,
    InvestorEdgeRuntime,
    MarketHistoryProvider,
    apply_profile_to_analysis,
    build_dashboard_addon,
    investor_key,
    load_config,
)
from scripts.build_trade_dashboard import main as build_dashboard


def rows(start: date, returns: list[float]) -> list[dict[str, object]]:
    price = 100.0
    out = []
    current = start
    for change in returns:
        out.append({"date": current.isoformat(), "close": price})
        price *= 1.0 + change
        current += timedelta(days=1)
    out.append({"date": current.isoformat(), "close": price})
    return out


class FakeProvider:
    def __init__(self, stock_rows, benchmark_rows):
        self.stock_rows = stock_rows
        self.benchmark_rows = benchmark_rows
        self.errors = []
        self.network_requests = 0

    def sector(self, ticker: str):
        return {"industry": "Technology", "benchmark": "SPY", "sector": "Technology"}

    def daily(self, ticker: str, *, minimum_date=None):
        return self.benchmark_rows if ticker == "SPY" else self.stock_rows


def trade(day: date, *, trade_id: str, owner: str = "Self"):
    return {
        "trade_id": trade_id,
        "filer": "Example Representative",
        "owner": owner,
        "ticker": "AAA",
        "transaction_type": "Purchase",
        "equity_like": True,
        "transaction_date": day.isoformat(),
        "filed_date": (day + timedelta(days=2)).isoformat(),
        "amount": "$15,001 - $50,000",
    }


def test_investor_identity_separates_spouse() -> None:
    assert investor_key(trade(date(2025, 1, 1), trade_id="a", owner="Self")) != investor_key(
        trade(date(2025, 1, 1), trade_id="b", owner="Spouse")
    )


def test_consistent_outperformance_produces_positive_edge(tmp_path: Path) -> None:
    start = date(2024, 1, 1)
    # Stock rises roughly 0.35% per session while benchmark rises 0.05%.
    stock_rows = rows(start, [0.0035] * 800)
    benchmark_rows = rows(start, [0.0005] * 800)
    cfg = {
        "enabled": True,
        "max_modifier": 12,
        "minimum_completed_trades": 3,
        "confidence_prior_trades": 3,
        "max_history_trades": 20,
        "alpha_clip_percent": 25.0,
        "alpha_score_points_per_percent": 2.5,
        "horizons": [5, 20, 60, 120],
        "horizon_weights": {"5": .15, "20": .30, "60": .35, "120": .20},
        "edge_weights": {"followable_alpha": .45, "picker_alpha": .20, "hit_rate": .15, "consistency": .10, "sector_skill": .10},
    }
    runtime = InvestorEdgeRuntime(cfg, tmp_path, FakeProvider(stock_rows, benchmark_rows), {})
    history = [trade(start + timedelta(days=20 + i * 40), trade_id=f"h{i}") for i in range(8)]
    candidate = trade(start + timedelta(days=500), trade_id="candidate")
    profile = runtime.profile_for_trade(candidate, [*history, candidate])
    assert profile["sample_count"] >= 6
    assert profile["edge_score"] > 60
    assert profile["modifier"] > 0
    assert profile["followable_alpha_by_horizon"]["20"] > 0


def test_small_sample_is_shrunk_toward_neutral(tmp_path: Path) -> None:
    start = date(2024, 1, 1)
    stock_rows = rows(start, [0.01] * 400)
    benchmark_rows = rows(start, [0.0] * 400)
    cfg = {
        "enabled": True,
        "max_modifier": 12,
        "minimum_completed_trades": 3,
        "confidence_prior_trades": 8,
        "max_history_trades": 20,
        "alpha_clip_percent": 25.0,
        "alpha_score_points_per_percent": 2.5,
        "horizons": [5, 20, 60, 120],
        "horizon_weights": {"5": .15, "20": .30, "60": .35, "120": .20},
        "edge_weights": {"followable_alpha": .45, "picker_alpha": .20, "hit_rate": .15, "consistency": .10, "sector_skill": .10},
    }
    runtime = InvestorEdgeRuntime(cfg, tmp_path, FakeProvider(stock_rows, benchmark_rows), {})
    one = trade(start + timedelta(days=10), trade_id="one")
    candidate = trade(start + timedelta(days=250), trade_id="candidate")
    profile = runtime.profile_for_trade(candidate, [one, candidate])
    assert profile["raw_edge_score"] > profile["edge_score"]
    assert profile["confidence_label"] == "Low"
    assert profile["modifier"] <= 3


def test_hard_cap_still_wins_after_positive_modifier() -> None:
    analysis = {
        "score": 59,
        "raw_score": 86,
        "classification": "weak_signal",
        "score_components": {},
        "hard_caps": [{"reason": "Current market price unavailable", "maximum_score": 59}],
    }
    profile = {"modifier": 12, "edge_score": 100}
    rules = {"thresholds": {"high_priority": 80, "watchlist": 65, "weak_signal": 50}}
    updated = apply_profile_to_analysis(analysis, profile, rules)
    assert updated["score"] == 59
    assert updated["raw_score"] == 98
    assert updated["investor_edge_modifier"] == 12


def test_modifier_has_an_absolute_safety_cap() -> None:
    analysis = {
        "score": 50,
        "raw_score": 50,
        "classification": "weak_signal",
        "score_components": {},
        "hard_caps": [],
    }
    rules = {"thresholds": {"high_priority": 80, "watchlist": 65, "weak_signal": 50}}
    updated = apply_profile_to_analysis(analysis, {"modifier": 999}, rules)
    assert updated["investor_edge_modifier"] == MAX_MODIFIER_LIMIT
    assert updated["score"] == 50 + MAX_MODIFIER_LIMIT


def test_future_public_disclosure_is_not_used_as_prior_history(tmp_path: Path) -> None:
    start = date(2024, 1, 1)
    stock_rows = rows(start, [0.003] * 500)
    benchmark_rows = rows(start, [0.0005] * 500)
    cfg = {
        "enabled": True,
        "max_modifier": 12,
        "minimum_completed_trades": 1,
        "confidence_prior_trades": 1,
        "max_history_trades": 20,
        "alpha_clip_percent": 25.0,
        "alpha_score_points_per_percent": 2.5,
        "horizons": [5, 20, 60, 120],
        "horizon_weights": {"5": .15, "20": .30, "60": .35, "120": .20},
        "edge_weights": {"followable_alpha": .45, "picker_alpha": .20, "hit_rate": .15, "consistency": .10, "sector_skill": .10},
    }
    runtime = InvestorEdgeRuntime(cfg, tmp_path, FakeProvider(stock_rows, benchmark_rows), {})
    candidate = trade(start + timedelta(days=250), trade_id="candidate")
    future_public = trade(start + timedelta(days=20), trade_id="future-public")
    future_public["filed_date"] = (start + timedelta(days=260)).isoformat()
    profile = runtime.profile_for_trade(candidate, [future_public, candidate])
    assert profile["sample_count"] == 0
    assert profile["modifier"] == 0


def test_provider_errors_never_persist_query_credentials(tmp_path: Path) -> None:
    alpha_key = "alpha-secret-value"
    finnhub_key = "finnhub-secret-value"

    class ErrorResponse:
        def raise_for_status(self) -> None:
            raise RuntimeError(
                f"401 https://provider.invalid/query?apikey={alpha_key}&token={finnhub_key}"
            )

    class ErrorSession:
        def get(self, *args, **kwargs):
            return ErrorResponse()

    provider = MarketHistoryProvider(
        ai_dir=tmp_path,
        session=ErrorSession(),
        alphavantage_api_key=alpha_key,
        finnhub_api_key=finnhub_key,
        request_timeout=(1.0, 1.0),
        config={"network_request_budget_per_run": 4},
    )
    assert provider.daily("AAA") == []
    persisted = " ".join(provider.errors)
    assert alpha_key not in persisted
    assert finnhub_key not in persisted
    assert "[redacted]" in persisted


def test_invalid_ticker_cannot_escape_market_cache(tmp_path: Path) -> None:
    class FailIfCalledSession:
        def get(self, *args, **kwargs):
            raise AssertionError("invalid tickers must not reach a provider")

    provider = MarketHistoryProvider(
        ai_dir=tmp_path,
        session=FailIfCalledSession(),
        alphavantage_api_key="configured",
        request_timeout=(1.0, 1.0),
        config={"network_request_budget_per_run": 4},
    )
    assert provider.daily("../../outside") == []
    assert not (tmp_path.parent / "outside-daily.json").exists()


def test_feature_is_disabled_by_default_but_supports_valid_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.yml"
    monkeypatch.delenv("INVESTOR_EDGE_ENABLED", raising=False)
    assert load_config(missing)["enabled"] is False
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "true")
    assert load_config(missing)["enabled"] is True
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "sometimes")
    with pytest.raises(ValueError, match="boolean"):
        load_config(missing)


def test_dashboard_addon_writes_heatmap_and_native_link(tmp_path: Path) -> None:
    ai_dir = tmp_path / "ai"
    ai_dir.mkdir()
    (ai_dir / "investor-edge-leaderboard.json").write_text(
        '{"generated_utc":"2026-08-29T10:00:00Z","investors":[{"filer":"A","owner":"Self","edge_score":80,"modifier":7,"confidence":0.8,"confidence_label":"High","sample_count":12,"considered_trade_count":14,"followable_alpha_by_horizon":{"5":1,"20":3,"60":7,"120":10},"followable_alpha":5,"picker_alpha":6,"hit_rate_percent":70,"average_disclosure_lag_days":14}]}',
        encoding="utf-8",
    )
    out = tmp_path / "site"
    out.mkdir()
    (out / "index.html").write_text('<div class="header-actions"></div>', encoding="utf-8")
    build_dashboard_addon(ai_dir, out)
    assert (out / "investor-edge.html").exists()
    assert (out / "investor-edge.css").exists()
    assert (out / "data/investor-edge.json").exists()
    assert "Investor Edge" in (out / "index.html").read_text(encoding="utf-8")


def test_native_dashboard_build_always_publishes_investor_edge_page(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert build_dashboard(["--output-dir", str(out)]) == 0
    assert (out / "investor-edge.html").exists()
    assert (out / "investor-edge.css").exists()
    assert (out / "investor-edge.js").exists()
    assert (out / "data" / "investor-edge.json").exists()
    assert 'href="investor-edge.html"' in (out / "index.html").read_text(encoding="utf-8")
