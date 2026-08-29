from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.investor_edge import (
    OBSERVATION_FILE,
    InvestorEdgeRuntime,
    MarketHistoryProvider,
    _rows_cover,
    apply_profile_to_analysis,
    history_trade_eligibility,
    investor_identity,
    investor_key,
)


def price_rows(start: date, changes: list[float]) -> list[dict[str, object]]:
    price = 100.0
    rows: list[dict[str, object]] = []
    for offset, change in enumerate(changes):
        rows.append({"date": (start + timedelta(days=offset)).isoformat(), "close": price})
        price *= 1.0 + change
    rows.append({"date": (start + timedelta(days=len(changes))).isoformat(), "close": price})
    return rows


def core_config(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "version": 1,
        "enabled": True,
        "max_modifier": 12,
        "minimum_completed_trades": 3,
        "confidence_prior_trades": 3,
        "sector_confidence_prior_trades": 3,
        "max_history_trades": 40,
        "backfill_analysis_limit_per_run": 40,
        "alpha_clip_percent": 25.0,
        "alpha_score_points_per_percent": 2.5,
        "benchmark_default": "SPY",
        "horizons": [5, 20, 60, 120],
        "horizon_weights": {"5": 0.15, "20": 0.30, "60": 0.35, "120": 0.20},
        "edge_weights": {
            "followable_alpha": 0.45,
            "picker_alpha": 0.20,
            "hit_rate": 0.15,
            "consistency": 0.10,
            "sector_skill": 0.10,
        },
    }
    result.update(overrides)
    return result


def purchase(
    day: date,
    *,
    trade_id: str,
    ticker: str = "AAA",
    owner: str = "Self",
    **overrides: object,
) -> dict[str, object]:
    result: dict[str, object] = {
        "trade_id": trade_id,
        "filer": "Example Representative",
        "owner": owner,
        "ticker": ticker,
        "asset": f"Example Corp ({ticker})",
        "asset_type": "Stock",
        "transaction_type": "Purchase",
        "equity_like": True,
        "parse_confidence": "high",
        "transaction_date": day.isoformat(),
        "filed_date": (day + timedelta(days=2)).isoformat(),
        "amount": "$15,001 - $50,000",
        "raw_row": "Open market purchase",
    }
    result.update(overrides)
    return result


class DeterministicProvider:
    def __init__(self, stock_rows: list[dict[str, object]], benchmark_rows: list[dict[str, object]]):
        self.stock_rows = stock_rows
        self.benchmark_rows = benchmark_rows
        self.errors: list[str] = []
        self.network_requests = 0
        self.daily_calls: list[str] = []

    def sector(self, ticker: str) -> dict[str, object]:
        return {
            "industry": "Technology",
            "benchmark": "XLK",
            "sector": "Technology",
            "mapping_confidence": 0.9,
            "mapping_source": "test",
        }

    def daily(
        self,
        ticker: str,
        *,
        minimum_date: date | None = None,
        required_through: date | None = None,
    ) -> list[dict[str, object]]:
        self.daily_calls.append(ticker)
        return self.benchmark_rows if ticker in {"SPY", "XLK"} else self.stock_rows


def test_as_of_cutoff_prevents_future_outcomes_and_preserves_partial_horizons(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.01] * 250),
        price_rows(start, [0.0] * 250),
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    candidate = purchase(start + timedelta(days=20), trade_id="candidate")

    profile = runtime.profile_for_trade(candidate, [prior, candidate])

    assert profile["as_of_date"] == candidate["filed_date"]
    assert profile["followable_alpha_by_horizon"]["5"] > 0
    assert profile["followable_alpha_by_horizon"]["20"] is None
    assert profile["followable_alpha_by_horizon"]["60"] is None
    assert profile["followable_alpha_by_horizon"]["120"] is None
    assert profile["followable_hit_rate_by_horizon"]["5"] == 100.0
    assert profile["followable_hit_rate_by_horizon"]["20"] is None
    assert profile["weighted_followable_hit_rate_percent"] == 100.0
    assert 0 < profile["effective_sample_count"] < 1
    result = next(item for item in profile["trade_results"] if item["trade_id"] == "prior")
    assert profile["profile_status"] == "partial"
    assert profile["backfill_pending_trade_count"] == 1
    assert result["status"] == "partial_scored"
    assert result["observation_status"] == "partial_cached"
    detail = result["followable_outcomes"]["5"]
    assert detail["exit_date"] <= profile["as_of_date"]
    assert detail["stock_entry_price"] > 0
    assert detail["stock_exit_price"] > detail["stock_entry_price"]
    assert detail["stock_return_percent"] > detail["benchmark_return_percent"]


def test_large_consistently_poor_sample_produces_negative_edge(tmp_path: Path) -> None:
    start = date(2023, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [-0.0025] * 900),
        price_rows(start, [0.0005] * 900),
    )
    runtime = InvestorEdgeRuntime(
        core_config(confidence_prior_trades=1, minimum_completed_trades=3),
        tmp_path,
        provider,
        {},
    )
    history = [
        purchase(start + timedelta(days=10 + index * 25), trade_id=f"poor-{index}")
        for index in range(20)
    ]
    candidate = purchase(start + timedelta(days=700), trade_id="candidate")

    profile = runtime.profile_for_trade(candidate, [*history, candidate])

    assert profile["sample_count"] == 20
    assert profile["weighted_followable_hit_rate_percent"] == 0.0
    assert profile["followable_alpha"] < 0
    assert profile["edge_score"] < 40
    assert profile["modifier"] < 0


def test_sector_skill_is_confidence_shrunk_and_profile_is_reproducible(tmp_path: Path) -> None:
    start = date(2024, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 700),
        price_rows(start, [0.0005] * 700),
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    history = []
    for index, lag in enumerate((1, 2, 3, 4, 5, 20)):
        day = start + timedelta(days=10 + index * 40)
        history.append(
            purchase(
                day,
                trade_id=f"sector-{index}",
                filed_date=(day + timedelta(days=lag)).isoformat(),
            )
        )
    candidate = purchase(start + timedelta(days=500), trade_id="candidate")

    profile = runtime.profile_for_trade(candidate, [*history, candidate])

    assert len(profile["method_hash"]) == 20
    assert profile["methodology"]["method_hash"] == profile["method_hash"]
    assert profile["current_sector"]["mapping_confidence"] == 0.9
    assert profile["sector_skill_score"] > 50
    assert 0 < profile["sector_skill_confidence"] < 1
    assert profile["strongest_sector"]["sector"] == "Technology"
    assert profile["strongest_sector"]["score"] == profile["sector_skill_score"]
    assert profile["average_disclosure_lag_days"] == pytest.approx(35 / 6, abs=0.1)
    assert profile["median_disclosure_lag_days"] == 3.5


def test_identity_categories_are_stable_and_missing_owner_is_low_confidence() -> None:
    spouse_code = purchase(date(2025, 1, 1), trade_id="a", owner="SP")
    spouse_word = purchase(date(2025, 1, 2), trade_id="b", owner="Spouse")
    assert investor_key(spouse_code) == investor_key(spouse_word)
    assert investor_identity(spouse_code)["owner_category"] == "Spouse"

    trust = investor_identity(
        purchase(date(2025, 1, 3), trade_id="c", owner="Family Trust #1")
    )
    assert trust["owner_category"] == "Trust"
    assert trust["owner_fallback"] is True

    missing = investor_identity(purchase(date(2025, 1, 4), trade_id="d", owner=""))
    assert missing["owner_category"] == "Other"
    assert missing["owner_confidence_label"] == "Low"
    assert missing["owner_fallback"] is True

    renamed_a = purchase(
        date(2025, 1, 5), trade_id="e", filer="Representative A", bioguide_id="X001"
    )
    renamed_b = purchase(
        date(2025, 1, 6), trade_id="f", filer="Representative A. Jr.", bioguide_id="X001"
    )
    assert investor_key(renamed_a) == investor_key(renamed_b)

    alternate_namespace = purchase(
        date(2025, 1, 7), trade_id="g", filer="Representative A", filer_id="X001"
    )
    assert investor_key(renamed_a) == investor_key(alternate_namespace)

    assert investor_key(
        purchase(date(2025, 1, 8), trade_id="h", owner="Account Alpha")
    ) != investor_key(
        purchase(date(2025, 1, 9), trade_id="i", owner="Account Beta")
    )


def test_eligibility_explains_etf_low_confidence_and_nondiscretionary_exclusions() -> None:
    etf = history_trade_eligibility(
        purchase(date(2025, 1, 1), trade_id="etf", ticker="SPY", asset_type="ETF")
    )
    assert etf["eligible"] is False
    assert "fund_or_etf" in etf["excluded_reasons"]

    low = history_trade_eligibility(
        purchase(date(2025, 1, 1), trade_id="low", parse_confidence="low")
    )
    assert low["eligible"] is False
    assert "low_parse_confidence" in low["excluded_reasons"]

    routine = history_trade_eligibility(
        purchase(
            date(2025, 1, 1),
            trade_id="routine",
            raw_row="Acquired through automatic dividend reinvestment plan",
        )
    )
    assert routine["eligible"] is False
    assert "nondiscretionary_or_managed" in routine["excluded_reasons"]

    ambiguous = history_trade_eligibility(
        purchase(date(2025, 1, 1), trade_id="ambiguous", owner="Unlabeled account")
    )
    assert ambiguous["eligible"] is True
    assert ambiguous["quality_weight"] < 1
    assert "low_identity_confidence" in ambiguous["quality_warnings"]

    synthetic = history_trade_eligibility(
        purchase(date(2025, 1, 1), trade_id="synthetic", is_synthetic_test=True)
    )
    assert synthetic["eligible"] is False
    assert "synthetic_or_temporary" in synthetic["excluded_reasons"]

    impossible = history_trade_eligibility(
        purchase(
            date(2025, 1, 10),
            trade_id="negative-lag",
            filed_date="2025-01-09",
        )
    )
    assert impossible["eligible"] is False
    assert "public_date_before_transaction" in impossible["excluded_reasons"]

    contradictory_filing = history_trade_eligibility(
        purchase(
            date(2025, 1, 10),
            trade_id="contradictory-filing",
            filed_date="2025-01-09",
            observed_at_utc="2025-01-12T12:00:00Z",
        )
    )
    assert contradictory_filing["eligible"] is False
    assert "filed_date_before_transaction" in contradictory_filing["excluded_reasons"]


def test_observed_date_wins_and_followable_anchor_is_next_session(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.002] * 300), price_rows(start, [0.0] * 300)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(
        start,
        trade_id="prior",
        filed_date="2025-01-10",
        observed_at_utc="2025-01-05T21:30:00Z",
    )
    candidate = purchase(start + timedelta(days=200), trade_id="candidate")

    profile = runtime.profile_for_trade(candidate, [prior, candidate])
    result = next(item for item in profile["trade_results"] if item["trade_id"] == "prior")

    assert result["public_disclosure_date"] == "2025-01-05"
    assert result["filed_date"] == "2025-01-10"
    assert result["followable_anchor_date"] == "2025-01-06"
    assert result["followable_outcomes"]["5"]["anchor_date"] == "2025-01-06"
    assert result["disclosure_lag_days"] == 4
    assert profile["current_disclosure_lag_days"] == 2


def test_name_only_history_bridges_to_unambiguous_stable_id(tmp_path: Path) -> None:
    start = date(2024, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.002] * 500), price_rows(start, [0.0] * 500)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    candidate = purchase(
        start + timedelta(days=250), trade_id="candidate", bioguide_id="X001"
    )

    profile = runtime.profile_for_trade(candidate, [prior, candidate])

    assert profile["sample_count"] == 1
    assert profile["investor_key"].startswith("id-x001|")
    assert runtime.profiles == {}


def test_low_confidence_sector_mapping_falls_back_to_spy(tmp_path: Path) -> None:
    start = date(2024, 1, 1)

    class WeakSectorProvider(DeterministicProvider):
        def sector(self, ticker: str) -> dict[str, object]:
            return {
                "industry": "Technology",
                "benchmark": "XLK",
                "sector": "Technology",
                "mapping_confidence": 0.1,
                "mapping_source": "weak-test",
            }

    provider = WeakSectorProvider(
        price_rows(start, [0.002] * 500), price_rows(start, [0.0] * 500)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    candidate = purchase(start + timedelta(days=250), trade_id="candidate")

    profile = runtime.profile_for_trade(candidate, [prior, candidate])
    result = next(item for item in profile["trade_results"] if item["trade_id"] == "prior")

    assert result["benchmark"] == "SPY"
    assert result["sector_mapping"]["reported_benchmark"] == "XLK"
    assert result["sector_mapping"]["mapping_source"] == "broad_market_low_confidence"


def test_applying_modifier_is_idempotent_and_preserves_hard_caps() -> None:
    analysis = {
        "score": 70,
        "raw_score": 74,
        "hard_caps": [{"maximum_score": 75}],
        "score_components": {},
    }
    profile = {"modifier": 8, "edge_score": 80, "sample_count": 10}
    rules = {"thresholds": {"high_priority": 80, "watchlist": 65, "weak_signal": 50}}

    once = apply_profile_to_analysis(analysis, profile, rules)
    twice = apply_profile_to_analysis(once, profile, rules)

    assert once == twice
    assert once["raw_score"] == 82
    assert once["score"] == 75
    assert once["final_score"] == 75


def test_market_cache_merges_sources_and_uses_stale_data_on_provider_failure(tmp_path: Path) -> None:
    ai_dir = tmp_path / "ai"
    edge_path = ai_dir / "investor-edge-market" / "AAA-daily.json"
    core_path = ai_dir / "market-cache" / "AAA-daily.json"
    edge_path.parent.mkdir(parents=True)
    core_path.parent.mkdir(parents=True)
    edge_rows = [
        {"date": "2025-01-01", "close": 100.0},
        {"date": "2025-01-02", "close": 101.0},
    ]
    core_rows = [
        {"date": "2025-01-02", "close": 101.0},
        {"date": "2025-01-03", "close": 102.0},
    ]
    edge_path.write_text(json.dumps({"rows": edge_rows}), encoding="utf-8")
    core_path.write_text(json.dumps({"rows": core_rows}), encoding="utf-8")

    class FailedSession:
        def get(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("provider unavailable")

    provider = MarketHistoryProvider(
        ai_dir=ai_dir,
        session=FailedSession(),
        alphavantage_api_key="configured",
        request_timeout=(1.0, 1.0),
        config={"network_request_budget_per_run": 2, "market_cache_hours": 0},
    )
    result = provider.daily(
        "AAA",
        minimum_date=date(2025, 1, 1),
        required_through=date(2025, 2, 1),
    )

    assert [item["date"] for item in result] == ["2025-01-01", "2025-01-02", "2025-01-03"]
    assert json.loads(edge_path.read_text(encoding="utf-8"))["rows"] == edge_rows
    assert provider.errors


def test_backfill_is_bounded_durable_and_idempotent(tmp_path: Path) -> None:
    start = date(2024, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.003] * 800),
        price_rows(start, [0.0005] * 800),
    )
    config = core_config(backfill_analysis_limit_per_run=2)
    history = [
        purchase(start + timedelta(days=10 + index * 30), trade_id=f"history-{index}")
        for index in range(4)
    ]
    candidate = purchase(start + timedelta(days=500), trade_id="candidate")
    runtime = InvestorEdgeRuntime(config, tmp_path, provider, {})

    first = runtime.profile_for_trade(candidate, [*history, candidate])
    first_keys = set(runtime.observations)
    assert first["sample_count"] == 2
    assert runtime.backfill_processed_this_run == 2
    assert len(first_keys) == 2
    assert (tmp_path / OBSERVATION_FILE).exists()

    repeated = runtime.profile_for_trade(candidate, [*history, candidate])
    assert repeated["sample_count"] == 2
    assert runtime.backfill_processed_this_run == 2
    assert set(runtime.observations) == first_keys

    payload = json.loads((tmp_path / OBSERVATION_FILE).read_text(encoding="utf-8"))
    resumed = InvestorEdgeRuntime(
        config,
        tmp_path,
        provider,
        {},
        payload["observations"],
    )
    completed = resumed.profile_for_trade(candidate, [*history, candidate])
    assert completed["sample_count"] == 4
    assert resumed.backfill_processed_this_run == 2
    assert len(resumed.observations) == 4
    assert first_keys < set(resumed.observations)


def test_unavailable_history_backoff_prevents_newer_trade_from_starving_older_work(
    tmp_path: Path,
) -> None:
    start = date(2024, 1, 1)
    stock_rows = price_rows(start, [0.003] * 800)
    benchmark_rows = price_rows(start, [0.0005] * 800)

    class SelectiveProvider(DeterministicProvider):
        def daily(
            self,
            ticker: str,
            *,
            minimum_date: date | None = None,
            required_through: date | None = None,
        ) -> list[dict[str, object]]:
            self.daily_calls.append(ticker)
            if ticker == "BAD":
                return []
            return self.benchmark_rows if ticker in {"SPY", "XLK"} else self.stock_rows

    config = core_config(backfill_analysis_limit_per_run=1)
    good = purchase(start + timedelta(days=10), trade_id="good", ticker="GOOD")
    bad = purchase(start + timedelta(days=40), trade_id="bad", ticker="BAD")
    candidate_day = start + timedelta(days=500)
    first_candidate = purchase(candidate_day, trade_id="candidate-1")
    first_provider = SelectiveProvider(stock_rows, benchmark_rows)
    first_runtime = InvestorEdgeRuntime(config, tmp_path, first_provider, {})

    first = first_runtime.profile_for_trade(
        first_candidate, [good, bad, first_candidate]
    )

    assert first["sample_count"] == 0
    assert first_runtime.backfill_processed_this_run == 1
    assert first_provider.daily_calls == ["BAD", "XLK"]
    payload = json.loads((tmp_path / OBSERVATION_FILE).read_text(encoding="utf-8"))
    unavailable = next(iter(payload["observations"].values()))
    assert unavailable["last_attempt_status"] == "unavailable"
    assert unavailable["retry_after_as_of"] > unavailable["last_attempted_as_of"]

    second_candidate = purchase(
        candidate_day,
        trade_id="candidate-2",
        filed_date=(date.fromisoformat(first_candidate["filed_date"]) + timedelta(days=1)).isoformat(),
    )
    second_provider = SelectiveProvider(stock_rows, benchmark_rows)
    resumed = InvestorEdgeRuntime(
        config, tmp_path, second_provider, {}, payload["observations"]
    )
    second = resumed.profile_for_trade(
        second_candidate, [good, bad, second_candidate]
    )

    assert second["sample_count"] == 1
    assert resumed.backfill_processed_this_run == 1
    assert second_provider.daily_calls == ["GOOD", "XLK"]
    assert len(resumed.observations) == 2


def test_observation_retention_is_bounded_and_prefers_current_method_recent_rows(
    tmp_path: Path,
) -> None:
    start = date(2024, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.001] * 20), price_rows(start, [0.0] * 20)
    )
    config = core_config(observation_retention_limit=3)
    seed = InvestorEdgeRuntime(config, tmp_path, provider, {})
    current_hash = seed.method_hash

    def observation(
        key: str, *, method_hash: str, transaction_date: str
    ) -> dict[str, object]:
        return {
            "observation_key": key,
            "method_hash": method_hash,
            "trade_id": key,
            "transaction_date": transaction_date,
            "last_attempted_as_of": transaction_date,
            "updated_utc": f"{transaction_date}T12:00:00Z",
            "picker_outcomes": {"5": {"alpha_percent": 1.0}},
            "followable_outcomes": {"5": {"alpha_percent": 1.0}},
        }

    observations = {
        "current-1": observation(
            "current-1", method_hash=current_hash, transaction_date="2025-01-01"
        ),
        "current-2": observation(
            "current-2", method_hash=current_hash, transaction_date="2025-02-01"
        ),
        "current-3": observation(
            "current-3", method_hash=current_hash, transaction_date="2025-03-01"
        ),
        "current-4": observation(
            "current-4", method_hash=current_hash, transaction_date="2025-04-01"
        ),
        "old-newer": observation(
            "old-newer", method_hash="obsolete-method", transaction_date="2030-01-01"
        ),
        "old-older": observation(
            "old-older", method_hash="obsolete-method", transaction_date="2020-01-01"
        ),
    }

    runtime = InvestorEdgeRuntime(config, tmp_path, provider, {}, observations)

    assert set(runtime.observations) == {"current-2", "current-3", "current-4"}
    assert runtime.observations_pruned_this_run == 3
    runtime.save()
    payload = json.loads((tmp_path / OBSERVATION_FILE).read_text(encoding="utf-8"))
    assert set(payload["observations"]) == set(runtime.observations)
    assert payload["backfill"]["retention_limit"] == 3
    assert payload["backfill"]["stored_observation_count"] == 3
    assert payload["backfill"]["pruned_this_run"] == 3


def test_per_horizon_observation_is_filled_later_without_duplicate_trade_state(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400),
        price_rows(start, [0.0005] * 400),
    )
    config = core_config(backfill_analysis_limit_per_run=1)
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    early_candidate = purchase(start + timedelta(days=20), trade_id="early")
    first_runtime = InvestorEdgeRuntime(config, tmp_path, provider, {})
    early = first_runtime.profile_for_trade(early_candidate, [prior, early_candidate])
    assert early["followable_alpha_by_horizon"]["5"] is not None
    assert early["followable_alpha_by_horizon"]["20"] is None
    assert len(first_runtime.observations) == 1

    payload = json.loads((tmp_path / OBSERVATION_FILE).read_text(encoding="utf-8"))
    later_candidate = purchase(start + timedelta(days=250), trade_id="later")
    resumed = InvestorEdgeRuntime(config, tmp_path, provider, {}, payload["observations"])
    later = resumed.profile_for_trade(later_candidate, [prior, later_candidate])
    assert later["followable_alpha_by_horizon"]["120"] is not None
    assert len(resumed.observations) == 1


def test_later_as_of_can_extend_same_observation_in_one_runtime(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400), price_rows(start, [0.0005] * 400)
    )
    runtime = InvestorEdgeRuntime(
        core_config(backfill_analysis_limit_per_run=2), tmp_path, provider, {}
    )
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    early_candidate = purchase(start + timedelta(days=20), trade_id="early")
    later_candidate = purchase(start + timedelta(days=250), trade_id="later")

    early = runtime.profile_for_trade(early_candidate, [prior, early_candidate])
    later = runtime.profile_for_trade(later_candidate, [prior, later_candidate])

    assert early["followable_alpha_by_horizon"]["120"] is None
    assert later["followable_alpha_by_horizon"]["120"] is not None
    assert runtime.backfill_processed_this_run == 2
    assert len(runtime.observations) == 1


def test_identity_upgrade_reuses_observation_and_migrates_last_good_profile(
    tmp_path: Path,
) -> None:
    start = date(2024, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.003] * 600), price_rows(start, [0.0005] * 600)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    name_candidate = purchase(start + timedelta(days=250), trade_id="name-candidate")
    stable_candidate = purchase(
        start + timedelta(days=260), trade_id="stable-candidate", bioguide_id="X001"
    )

    first = runtime.profile_for_trade(name_candidate, [prior, name_candidate])
    calls_after_first = len(provider.daily_calls)
    upgraded = runtime.profile_for_trade(stable_candidate, [prior, stable_candidate])

    assert first["sample_count"] == upgraded["sample_count"] == 1
    assert len(runtime.observations) == 1
    assert len(provider.daily_calls) == calls_after_first

    name_key = investor_key(prior)
    stable_key = investor_key(stable_candidate)
    runtime.profiles[name_key] = {
        "method_hash": runtime.method_hash,
        "as_of_date": (start + timedelta(days=10)).isoformat(),
        "sample_count": 3,
        "effective_sample_count": 3.0,
        "horizon_coverage": 1.0,
        "identity": investor_identity(prior),
        "marker": "name-last-good",
    }
    preserved = runtime._profile(  # noqa: SLF001 - profile-key migration regression
        filer=str(stable_candidate["filer"]),
        owner=str(stable_candidate["owner"]),
        key=stable_key,
        history=[prior],
        current_ticker="",
        as_of=start + timedelta(days=20),
        identity=investor_identity(stable_candidate),
    )

    assert preserved["marker"] == "name-last-good"
    assert preserved["investor_key"] == stable_key
    assert stable_key in runtime.profiles
    assert name_key not in runtime.profiles


def test_partial_refresh_does_not_replace_equal_sample_richer_last_good(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400), price_rows(start, [0.0005] * 400)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    key = investor_key(prior)
    runtime.profiles[key] = {
        "method_hash": runtime.method_hash,
        "as_of_date": (start + timedelta(days=10)).isoformat(),
        "sample_count": 1,
        "effective_sample_count": 1.0,
        "horizon_coverage": 1.0,
        "marker": "richer",
    }

    result = runtime._profile(  # noqa: SLF001 - regression coverage for persistence guard
        filer=str(prior["filer"]),
        owner=str(prior["owner"]),
        key=key,
        history=[prior],
        current_ticker="",
        as_of=start + timedelta(days=20),
        identity=investor_identity(prior),
    )

    assert result["marker"] == "richer"
    assert result["profile_status"] == "stale_last_good"
    assert runtime.profiles[key]["marker"] == "richer"


def test_partial_refresh_with_more_thin_samples_keeps_richer_last_good(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400), price_rows(start, [0.0005] * 400)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    history = [
        purchase(start + timedelta(days=index), trade_id=f"prior-{index}")
        for index in range(11)
    ]
    key = investor_key(history[0])
    runtime.profiles[key] = {
        "method_hash": runtime.method_hash,
        "as_of_date": (start + timedelta(days=10)).isoformat(),
        "sample_count": 10,
        "effective_sample_count": 10.0,
        "horizon_coverage": 1.0,
        "identity": investor_identity(history[0]),
        "marker": "ten-full-observations",
    }

    result = runtime._profile(  # noqa: SLF001 - richer-profile persistence regression
        filer=str(history[0]["filer"]),
        owner=str(history[0]["owner"]),
        key=key,
        history=history,
        current_ticker="",
        as_of=start + timedelta(days=20),
        identity=investor_identity(history[0]),
    )

    assert result["marker"] == "ten-full-observations"
    assert result["profile_status"] == "stale_last_good"


def test_historical_partial_refresh_rejects_richer_future_last_good(
    tmp_path: Path,
) -> None:
    start = date(2025, 1, 1)
    cutoff = start + timedelta(days=20)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400), price_rows(start, [0.0005] * 400)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    key = investor_key(prior)
    runtime.profiles[key] = {
        "method_hash": runtime.method_hash,
        "as_of_date": (cutoff + timedelta(days=100)).isoformat(),
        "sample_count": 20,
        "effective_sample_count": 20.0,
        "horizon_coverage": 1.0,
        "edge_score": 99.0,
        "identity": investor_identity(prior),
        "marker": "future-last-good",
    }

    result = runtime._profile(  # noqa: SLF001 - historical persistence guard
        filer=str(prior["filer"]),
        owner=str(prior["owner"]),
        key=key,
        history=[prior],
        current_ticker="",
        as_of=cutoff,
        identity=investor_identity(prior),
    )

    assert result.get("marker") is None
    assert result["edge_score"] != 99.0
    assert result["as_of_date"] == cutoff.isoformat()
    assert result["profile_status"] == "partial"
    assert runtime.profiles[key]["as_of_date"] == cutoff.isoformat()


@pytest.mark.parametrize("persisted_as_of", [None, "not-a-date"])
def test_historical_partial_refresh_rejects_unverifiable_last_good_cutoff(
    tmp_path: Path,
    persisted_as_of: str | None,
) -> None:
    start = date(2025, 1, 1)
    cutoff = start + timedelta(days=20)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400), price_rows(start, [0.0005] * 400)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    key = investor_key(prior)
    runtime.profiles[key] = {
        "method_hash": runtime.method_hash,
        "as_of_date": persisted_as_of,
        "sample_count": 20,
        "effective_sample_count": 20.0,
        "horizon_coverage": 1.0,
        "identity": investor_identity(prior),
        "marker": "unverifiable-last-good",
    }

    result = runtime._profile(  # noqa: SLF001 - historical persistence guard
        filer=str(prior["filer"]),
        owner=str(prior["owner"]),
        key=key,
        history=[prior],
        current_ticker="",
        as_of=cutoff,
        identity=investor_identity(prior),
    )

    assert result.get("marker") is None
    assert result["as_of_date"] == cutoff.isoformat()
    assert result["profile_status"] == "partial"


def test_historical_leaderboard_rejects_richer_future_last_good(
    tmp_path: Path,
) -> None:
    start = date(2025, 1, 1)
    cutoff = start + timedelta(days=20)
    provider = DeterministicProvider(
        price_rows(start, [0.004] * 400), price_rows(start, [0.0005] * 400)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    prior = purchase(start + timedelta(days=5), trade_id="prior")
    key = investor_key(prior)
    runtime.profiles[key] = {
        "method_hash": runtime.method_hash,
        "as_of_date": (cutoff + timedelta(days=100)).isoformat(),
        "sample_count": 20,
        "effective_sample_count": 20.0,
        "horizon_coverage": 1.0,
        "edge_score": 99.0,
        "identity": investor_identity(prior),
        "marker": "future-leaderboard-profile",
    }

    leaderboard = runtime.refresh_leaderboard([prior], as_of=cutoff)

    assert len(leaderboard) == 1
    profile = leaderboard[0]
    assert profile["investor_key"] == key
    assert profile.get("marker") is None
    assert profile["edge_score"] != 99.0
    assert profile["as_of_date"] == cutoff.isoformat()
    assert profile["profile_status"] == "partial"
    assert runtime.profiles[key]["as_of_date"] == cutoff.isoformat()


def test_ambiguous_name_only_profile_is_not_migrated_to_first_stable_id(
    tmp_path: Path,
) -> None:
    start = date(2024, 1, 1)
    provider = DeterministicProvider(
        price_rows(start, [0.002] * 500), price_rows(start, [0.0] * 500)
    )
    runtime = InvestorEdgeRuntime(core_config(), tmp_path, provider, {})
    name_only = purchase(start + timedelta(days=1), trade_id="name")
    stable_a = purchase(
        start + timedelta(days=2), trade_id="stable-a", bioguide_id="A001"
    )
    stable_b = purchase(
        start + timedelta(days=3), trade_id="stable-b", bioguide_id="B001"
    )
    name_key = investor_key(name_only)
    stable_key = investor_key(stable_a)
    runtime.profiles[name_key] = {
        "method_hash": runtime.method_hash,
        "sample_count": 20,
        "effective_sample_count": 20.0,
        "horizon_coverage": 1.0,
        "identity": investor_identity(name_only),
        "marker": "ambiguous-name-profile",
    }

    profile = runtime.profile_for_investor(stable_key, [name_only, stable_a, stable_b])

    assert profile.get("marker") is None
    assert name_key in runtime.profiles
    assert stable_key in runtime.profiles


def test_market_coverage_allows_long_weekend_but_not_missing_trading_week() -> None:
    long_weekend_rows = [{"date": "2025-01-03", "close": 100.0}]
    stale_rows = [{"date": "2025-01-06", "close": 100.0}]

    assert _rows_cover(
        long_weekend_rows, date(2025, 1, 3), date(2025, 1, 7)
    ) is True
    assert _rows_cover(stale_rows, date(2025, 1, 6), date(2025, 1, 10)) is False
