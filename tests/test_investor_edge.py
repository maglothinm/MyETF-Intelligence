from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scripts.investor_edge import (
    PRICE_BASIS,
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
    price_basis = PRICE_BASIS
    provider_name = "deterministic_fixture"
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
    assert profile["modifier"] == 0
    assert profile["status"] == "insufficient_data"


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


def test_feature_is_enabled_by_default_but_supports_valid_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.yml"
    monkeypatch.delenv("INVESTOR_EDGE_ENABLED", raising=False)
    assert load_config(missing)["enabled"] is True
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "true")
    assert load_config(missing)["enabled"] is True
    monkeypatch.setenv("INVESTOR_EDGE_ENABLED", "false")
    assert load_config(missing)["enabled"] is False
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


def test_dashboard_addon_renders_grouped_accessible_drilldown_and_safe_links(
    tmp_path: Path,
) -> None:
    ai_dir = tmp_path / "ai"
    ai_dir.mkdir()
    profile = {
        "investor_key": "bioguide-id-x1|self",
        "identity": {"investor_key": "bioguide-id-x1|self"},
        "filer": "A <script>alert('unsafe')</script>",
        "owner": "Self & Joint",
        "owner_raw": "Brokerage <One>",
        "edge_score": 71.5,
        "modifier": 5,
        "confidence": 0.6,
        "confidence_label": "Medium",
        "sample_count": 2,
        "followable_alpha_by_horizon": {
            "5": 2.25,
            "20": -1.5,
            "60": 0.0,
            "120": None,
        },
        "weighted_followable_hit_rate_percent": 62.5,
        "average_disclosure_lag_days": 9.5,
        "strongest_sector": {
            "sector": "Technology & services",
            "followable_alpha": 4.5,
            "sample_count": 2,
        },
        "trade_results": [
            {
                "trade_id": "trade:scored",
                "ticker": "AAA",
                "asset": "Alpha <em>Holdings</em>",
                "transaction_date": "2025-01-02",
                "filed_date": "2025-01-10",
                "disclosure_lag_days": 8,
                "owner": "Self",
                "amount": "$15,001 - $50,000",
                "benchmark": "XLK",
                "source_url": "https://example.test/filing?id=1&view=public",
                "status": "scored",
                "eligible": True,
                "excluded_reasons": [],
                "quality_warnings": ["medium_parse_confidence"],
                "picker_outcomes": {
                    "5": {
                        "stock_entry_price": 100.0,
                        "stock_return_percent": 5.0,
                        "benchmark_return_percent": 1.0,
                        "alpha_percent": 4.0,
                    }
                },
                "followable_outcomes": {
                    "5": {
                        "stock_entry_price": 105.0,
                        "stock_return_percent": 2.0,
                        "benchmark_return_percent": -1.0,
                        "alpha_percent": 3.0,
                    }
                },
                "picker_stock_return_by_horizon": {"20": 7.0},
                "picker_benchmark_return_by_horizon": {"20": 2.0},
                "picker_alpha_by_horizon": {"20": 5.0},
                "followable_stock_return_by_horizon": {"20": 4.0},
                "followable_benchmark_return_by_horizon": {"20": 1.5},
                "followable_alpha_by_horizon": {"20": 2.5},
            },
            {
                "trade_id": "trade:excluded",
                "ticker": "BBB",
                "transaction_date": "2024-01-02",
                "filed_date": "2024-01-05",
                "status": "excluded",
                "eligible": False,
                "excluded_reasons": ["likely_routine", "<unsafe reason>"],
                "source_url": "javascript:alert('unsafe')",
            },
        ],
    }
    (ai_dir / "investor-edge-leaderboard.json").write_text(
        json.dumps(
            {
                "generated_utc": "2026-08-29T10:00:00Z",
                "investors": [profile],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "site"
    build_dashboard_addon(ai_dir, output)

    page = (output / "investor-edge.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(page, "html.parser")
    headers = [item.get_text(" ", strip=True) for item in soup.select("#edge-table > thead th")]
    assert headers == [
        "Investor identity / key",
        "Filer",
        "Owner / account",
        "Edge",
        "Confidence",
        "Observations",
        "5D followable α",
        "20D followable α",
        "60D followable α",
        "120D followable α",
        "Hit rate",
        "Avg disclosure lag",
        "Strongest sector",
    ]
    main = soup.select_one("tr.investor-row[data-edge-group='investor-0']")
    detail = soup.select_one("tr.detail-row[data-edge-group='investor-0']")
    assert main is not None and detail is not None
    assert "low-sample" in (main.get("class") or [])
    cells = main.find_all("td", recursive=False)
    assert len(cells) == 13
    assert cells[0].get_text(" ", strip=True) == "bioguide-id-x1|self"
    assert cells[1].get_text(" ", strip=True) == "A <script>alert('unsafe')</script>"
    assert "Self & Joint" in cells[2].get_text(" ", strip=True)
    assert "Brokerage <One>" in cells[2].get_text(" ", strip=True)
    assert cells[3].get_text(" ", strip=True) == "71.5 +5 modifier"
    assert "heat-pos-3" in (cells[3].get("class") or [])
    assert cells[4].get_text(" ", strip=True) == "60.0% Medium"
    assert cells[5].get_text(" ", strip=True) == "2"
    assert [cells[index].get_text(" ", strip=True) for index in range(6, 10)] == [
        "+2.25%",
        "-1.50%",
        "+0.00%",
        "—",
    ]
    assert "heat-pos-1" in (cells[6].get("class") or [])
    assert "heat-neg-1" in (cells[7].get("class") or [])
    assert "heat-neutral" in (cells[8].get("class") or [])
    assert cells[10].get_text(" ", strip=True) == "62.5%"
    assert "heat-pos-3" in (cells[10].get("class") or [])
    assert cells[11].get_text(" ", strip=True) == "9.5d"
    assert cells[12].get_text(" ", strip=True) == "Technology & services +4.50% · n=2"

    disclosure = detail.find("details")
    assert disclosure is not None
    assert disclosure.find("summary") is not None
    cards = detail.select("article.trade-card")
    assert len(cards) == 2
    first_card_text = cards[0].get_text(" ", strip=True)
    assert "Actual public disclosure 2025-01-10" in first_card_text
    assert "Transaction entry $100" in first_card_text
    assert "Disclosure entry $105" in first_card_text
    assert "Benchmark XLK" in first_card_text
    assert "Counts toward Edge Yes" in first_card_text
    assert "Exclusions None recorded" in first_card_text
    safe_link = cards[0].find("a", string="Official filing")
    assert safe_link is not None
    assert safe_link["href"] == "https://example.test/filing?id=1&view=public"
    assert safe_link["rel"] == ["noopener", "noreferrer"]

    outcome_rows = cards[0].select("table.outcome-table tbody tr")
    assert len(outcome_rows) == 8
    assert [value.get_text(" ", strip=True) for value in outcome_rows[0].find_all(["th", "td"])] == [
        "5D",
        "Transaction",
        "+5.00%",
        "+1.00%",
        "+4.00%",
    ]
    assert [value.get_text(" ", strip=True) for value in outcome_rows[3].find_all(["th", "td"])] == [
        "20D",
        "Disclosure",
        "+4.00%",
        "+1.50%",
        "+2.50%",
    ]
    excluded_text = cards[1].get_text(" ", strip=True)
    assert "Counts toward Edge No" in excluded_text
    assert "likely_routine; <unsafe reason>" in excluded_text
    assert cards[1].find("a") is None

    assert "<script>alert('unsafe')</script>" not in page
    assert "javascript:alert" not in page
    assert "default-src 'self'" in page
    script = (output / "investor-edge.js").read_text(encoding="utf-8")
    assert "const groupedRows = new Map()" in script
    assert "row.dataset.edgeGroup" in script
    assert "for (const row of rows) row.hidden = !visible" in script


def test_dashboard_addon_uses_em_dash_for_unavailable_neutral_metrics(
    tmp_path: Path,
) -> None:
    ai_dir = tmp_path / "ai"
    ai_dir.mkdir()
    (ai_dir / "investor-edge-leaderboard.json").write_text(
        json.dumps(
            {
                "investors": [
                    {
                        "investor_key": "example|self",
                        "filer": "Example",
                        "owner": "Self",
                        "edge_score": 50,
                        "modifier": 0,
                        "sample_count": 0,
                        "hit_rate_percent": 50,
                        "followable_alpha_by_horizon": {},
                        "trade_results": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "site"
    build_dashboard_addon(ai_dir, output)

    soup = BeautifulSoup(
        (output / "investor-edge.html").read_text(encoding="utf-8"), "html.parser"
    )
    main = soup.select_one("tr.investor-row")
    assert main is not None
    cells = main.find_all("td", recursive=False)
    assert cells[3].get_text(" ", strip=True) == "—"
    assert cells[4].get_text(" ", strip=True) == "—"
    assert cells[5].get_text(" ", strip=True) == "0"
    assert all(cells[index].get_text(" ", strip=True) == "—" for index in range(6, 10))
    assert cells[10].get_text(" ", strip=True) == "—"
    assert cells[11].get_text(" ", strip=True) == "—"
    assert cells[12].get_text(" ", strip=True) == "—"
    assert "low-sample" in (main.get("class") or [])


def test_native_dashboard_build_always_publishes_investor_edge_page(tmp_path: Path) -> None:
    out = tmp_path / "site"
    assert build_dashboard(["--output-dir", str(out)]) == 0
    assert (out / "investor-edge.html").exists()
    assert (out / "investor-edge.css").exists()
    assert (out / "investor-edge.js").exists()
    assert (out / "data" / "investor-edge.json").exists()
    assert 'href="investor-edge.html"' in (out / "index.html").read_text(encoding="utf-8")
