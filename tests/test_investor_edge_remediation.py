"""Offline acceptance for price basis, chronology, identity, and score safeguards."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.government_trade_tracker import make_trade
from scripts.investor_edge import (
    OBSERVATION_ARCHIVE_FILE,
    PRICE_BASIS,
    InvestorEdgeRuntime,
    MarketHistoryProvider,
    _outcome_for_horizon,
    adjusted_price_history,
    apply_profile_to_analysis,
    load_config,
    matching_investor_records,
)


def series(values, ticker="AAA"):
    return adjusted_price_history(
        [{"date": f"2025-01-{index + 6:02d}", "close": value} for index, value in enumerate(values)],
        ticker=ticker,
        provider="alphavantage:TIME_SERIES_DAILY_ADJUSTED",
    )


class RecordedSession:
    def __init__(self, payload=None):
        self.payload = payload
        self.calls = []

    def get(self, url, *, params, **kwargs):
        self.calls.append(dict(params))
        if self.payload is None:
            raise RuntimeError("offline provider unavailable")
        return SimpleNamespace(json=lambda: self.payload, raise_for_status=lambda: None)


def provider(directory, session, **config):
    return MarketHistoryProvider(
        ai_dir=directory, session=session, alphavantage_api_key="offline-placeholder",
        config={"network_request_budget_per_run": 5, **config},
    )


@pytest.mark.parametrize("raw,adjusted", [([100, 50], [50, 50]), ([100, 1000], [1000, 1000]), ([100, 99], [99, 99])])
def test_forward_reverse_splits_and_dividends_do_not_create_fake_returns(tmp_path, raw, adjusted):
    payload = {"Meta Data": {"2. Symbol": "AAA"}, "Time Series (Daily)": {
        f"2025-01-{index + 6:02d}": {"4. close": str(raw[index]), "5. adjusted close": str(value)}
        for index, value in enumerate(adjusted)
    }}
    session = RecordedSession(payload)
    history = provider(tmp_path, session).daily("AAA")
    result = _outcome_for_horizon(history, series([100, 100], "SPY"), date(2025, 1, 6), 1, as_of=date(2025, 1, 7))
    assert result["stock_return_percent"] == result["alpha_percent"] == 0
    assert result["price_basis"] == PRICE_BASIS
    assert session.calls[0]["function"] == "TIME_SERIES_DAILY_ADJUSTED"
    assert session.calls[0]["outputsize"] == "full"
    assert result["price_provenance"]["stock"]["rows_sha256"]


@pytest.mark.parametrize("change", [
    {"price_basis": "raw"}, {"provider": "finnhub:split_only"},
    {"schema_version": 0}, {"fetched_utc": ""}, {"fetched_utc": "2025-01-01"},
    {"rows_sha256": "tampered"}, {"ticker": "OTHER"},
])
def test_mixed_unversioned_or_tampered_adjusted_cache_is_rejected_and_preserved(tmp_path, change):
    history = series([50, 50])
    cache = tmp_path / "investor-edge-market/adjusted-v1/AAA-daily.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({**history.metadata, "rows": list(history), **change}), encoding="utf-8")
    original = cache.read_bytes()
    result = provider(tmp_path, RecordedSession()).daily("AAA")
    assert result == []
    assert cache.read_bytes() == original


def test_adjusted_cache_validated_by_timestamp_not_filesystem_mtime(tmp_path):
    history = series([50, 50])
    history.metadata["fetched_utc"] = "2025-01-01T00:00:00Z"
    cache = tmp_path / "investor-edge-market/adjusted-v1/AAA-daily.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({**history.metadata, "rows": list(history)}), encoding="utf-8")
    session = RecordedSession()
    assert provider(tmp_path, session).daily("AAA") == history
    assert len(session.calls) == 1


def test_snapshots_are_never_spliced_across_adjustment_revisions(tmp_path):
    history = series([100, 100])
    cache = tmp_path / "investor-edge-market/adjusted-v1/AAA-daily.json"
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({**history.metadata, "rows": list(history)}), encoding="utf-8")
    session = RecordedSession({"Meta Data": {"2. Symbol": "AAA"}, "Time Series (Daily)": {
        "2025-01-07": {"4. close": "50", "5. adjusted close": "50"},
        "2025-01-08": {"4. close": "50", "5. adjusted close": "50"},
    }})
    result = provider(tmp_path, session, market_cache_hours=0).daily("AAA")
    assert [row["date"] for row in result] == ["2025-01-07", "2025-01-08"]
    assert all(row["close"] == 50 for row in result)


def test_raw_close_is_not_a_fallback_when_adjusted_field_is_unavailable(tmp_path):
    session = RecordedSession({"Meta Data": {"2. Symbol": "AAA"}, "Time Series (Daily)": {"2025-01-06": {"4. close": "100"}}})
    history = provider(tmp_path, session).daily("AAA")
    assert history == []
    assert len(session.calls) == 1


@pytest.mark.parametrize("metadata", [None, {"2. Symbol": "WRONG"}])
def test_provider_response_requires_matching_symbol_provenance(tmp_path, metadata):
    session = RecordedSession({"Meta Data": metadata, "Time Series (Daily)": {"2025-01-06": {"5. adjusted close": "100"}}})
    assert provider(tmp_path, session).daily("AAA") == []


def test_cached_future_benchmark_price_is_not_visible():
    detail = _outcome_for_horizon(series([50, 55]), series([100, 100], "SPY"), date(2025, 1, 6), 1)
    detail["benchmark_exit_date"] = "2025-01-08"
    assert InvestorEdgeRuntime._visible_outcomes({"1": detail}, [1], date(2025, 1, 7)) == {"1": None}


def test_stock_and_benchmark_must_share_verified_basis_and_exact_sessions():
    stock, benchmark = series([50, 55]), series([100, 100], "SPY")
    benchmark.metadata["price_basis"] = "split_only"
    assert _outcome_for_horizon(stock, benchmark, date(2025, 1, 6), 1) is None
    assert _outcome_for_horizon(list(stock), series([100, 100], "SPY"), date(2025, 1, 6), 1) is None


def test_negative_modifier_reduces_capped_base_and_reapplication_is_idempotent():
    original = {"score": 64, "raw_score": 100, "hard_caps": [{"maximum_score": 64}]}
    lowered = apply_profile_to_analysis(original, {"modifier": -12}, {})
    assert lowered["final_score"] == 52
    assert apply_profile_to_analysis(lowered, {"modifier": -12}, {}) == lowered
    assert apply_profile_to_analysis(original, {"modifier": 12}, {})["final_score"] == 64


def test_below_minimum_has_no_modifier_even_for_extreme_outperformance(tmp_path):
    class OfflineProvider:
        price_basis = PRICE_BASIS
        provider_name = "deterministic_fixture"
        errors = []
        network_requests = 0

        def sector(self, ticker):
            return {"benchmark": "SPY", "sector": "Broad market", "mapping_confidence": 1}

        def daily(self, ticker, **kwargs):
            return [{"date": (date(2024, 1, 1) + timedelta(days=i)).isoformat(), "close": 100 * (1.01 ** i if ticker == "AAA" else 1)} for i in range(800)]

    def trade(identifier, day):
        return {"trade_id": identifier, "filer": "Example", "filer_id": "E001", "owner": "Self", "ticker": "AAA", "transaction_type": "Purchase", "equity_like": True, "parse_confidence": "high", "transaction_date": day.isoformat(), "filed_date": (day + timedelta(days=2)).isoformat()}

    config = load_config(Path(__file__).resolve().parents[1] / "config/investor_edge.yml")
    runtime = InvestorEdgeRuntime(config, tmp_path, OfflineProvider(), {})
    history = [trade(str(i), date(2024, 1, 15) + timedelta(days=40 * i)) for i in range(2)]
    candidate = trade("candidate", date(2025, 6, 1))
    result = runtime.profile_for_trade(candidate, history + [candidate])
    assert result["sample_count"] == result["effective_sample_count"] == 2
    assert result["status"] == "insufficient_data"
    assert result["minimum_sample_met"] is False
    assert result["modifier"] == 0
    score = apply_profile_to_analysis({"score": 60, "raw_score": 60}, {**result, "modifier": 12}, {})
    assert score["score"] == 60
    reloaded = InvestorEdgeRuntime(config, tmp_path, OfflineProvider(), {}, runtime.observations)
    again = reloaded.profile_for_trade(candidate, history + [candidate])
    for field in ("edge_score", "modifier", "sample_count", "effective_sample_count", "followable_alpha", "status"):
        assert again[field] == result[field]


def test_source_identity_survives_trade_serialization_without_changing_trade_id():
    kwargs = dict(branch="legislative", source="house", owner="Self", asset="Example", ticker="AAA", asset_type="Stock", transaction_type="Purchase", transaction_date="2025-01-01", notification_date="", amount="$1,001 - $15,000", raw_row="purchase", confidence="high")
    report = {"report_id": "report1", "filer": "A. Example", "filed_date": "2025-01-03"}
    before = make_trade(report=report, **kwargs)
    after = make_trade(report={**report, "bioguide_id": "E000001", "filer_aliases": ["Alice Example"]}, **kwargs)
    serialized = asdict(after)
    assert serialized["filer_id"] == "E000001"
    assert serialized["filer_id_source"] == "bioguide_id"
    assert serialized["filer_aliases"] == ("Alice Example",)
    assert before.trade_id == after.trade_id


def test_explicit_alias_bridge_is_rejected_on_stable_id_collision():
    target = {"filer": "Alice Example", "filer_id": "E001", "owner": "Self", "filer_aliases": ["A. Example"]}
    name_only = {"filer": "A. Example", "owner": "Self"}
    assert name_only in matching_investor_records(target, [target, name_only])
    collision = {"filer": "A. Example", "filer_id": "OTHER", "owner": "Self"}
    assert name_only not in matching_investor_records(target, [target, name_only, collision])
    assert matching_investor_records(name_only, [target, name_only, collision]) == []


def test_malformed_archive_cannot_be_silently_replaced(tmp_path):
    archive = tmp_path / OBSERVATION_ARCHIVE_FILE
    archive.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="archive is malformed"):
        InvestorEdgeRuntime({}, tmp_path, SimpleNamespace(), {})
    assert archive.read_text(encoding="utf-8") == "{broken"
