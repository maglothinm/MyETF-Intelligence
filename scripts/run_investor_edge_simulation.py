#!/usr/bin/env python3
"""Run one isolated, deterministic candidate through the production analysis path.

The caller supplies tracker and AI directories that have already been cloned into a
temporary workspace.  This helper never calls OpenAI, market APIs, SMTP, Pushover, or
any other network service.  It persists the synthetic analysis and an alert preview so
the normal dashboard builder can exercise the same records used in production.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # Support package imports and direct workflow execution.
    from .ai_filing_analyst import (
        DEFAULT_RULES,
        DEFAULT_SCHEMA,
        AnalystConfig,
        OpenAIResult,
        build_analysis_record,
        eligible_trade,
        format_candidate_alert,
        json_hash,
        load_rules,
        load_tracker_data,
        write_json,
    )
    from .government_trade_tracker import append_jsonl
    from .investor_edge import (
        LEADERBOARD_FILE,
        OBSERVATION_FILE,
        PROFILE_FILE,
        PRICE_BASIS,
        InvestorEdgeRuntime,
        history_trade_eligibility,
        investor_key,
        matching_investor_records,
        load_config as load_edge_config,
    )
except ImportError:  # pragma: no cover - direct execution path
    from ai_filing_analyst import (  # type: ignore
        DEFAULT_RULES,
        DEFAULT_SCHEMA,
        AnalystConfig,
        OpenAIResult,
        build_analysis_record,
        eligible_trade,
        format_candidate_alert,
        json_hash,
        load_rules,
        load_tracker_data,
        write_json,
    )
    from government_trade_tracker import append_jsonl  # type: ignore
    from investor_edge import (  # type: ignore
        LEADERBOARD_FILE,
        OBSERVATION_FILE,
        PROFILE_FILE,
        PRICE_BASIS,
        InvestorEdgeRuntime,
        history_trade_eligibility,
        investor_key,
        matching_investor_records,
        load_config as load_edge_config,
    )


class SimulationError(RuntimeError):
    """Raised when the isolated production-path simulation is invalid."""


class OfflineMarketHistoryProvider:
    """Deterministic provider adapter with the production runtime's interface."""

    price_basis = PRICE_BASIS
    provider_name = "deterministic_fixture"

    def __init__(self, *, as_of: date) -> None:
        self.as_of = as_of
        self.errors: list[str] = []
        self.network_requests = 0
        self.alphavantage_api_key = ""
        self.finnhub_api_key = ""
        self._rows: dict[str, list[dict[str, Any]]] = {}

    def sector(self, ticker: str) -> dict[str, Any]:
        normalized = str(ticker or "").strip().upper()
        if normalized in {"SPY", "XLK"}:
            return {
                "industry": "Benchmark",
                "benchmark": "SPY",
                "sector": "Broad market",
                "mapping_confidence": 1.0,
                "mapping_source": "simulation_fixture",
            }
        return {
            "industry": "Technology",
            "benchmark": "XLK",
            "sector": "Technology",
            "mapping_confidence": 1.0,
            "mapping_source": "simulation_fixture",
        }

    def daily(
        self,
        ticker: str,
        *,
        minimum_date: date | None = None,
        required_through: date | None = None,
    ) -> list[dict[str, Any]]:
        del required_through
        normalized = str(ticker or "").strip().upper()
        if not normalized:
            return []
        if normalized not in self._rows:
            start = min(minimum_date or self.as_of, self.as_of - timedelta(days=2600))
            start -= timedelta(days=10)
            slope = 0.00045 if normalized in {"SPY", "XLK"} else 0.00125
            # Keep the fixture stable while allowing different stocks to have distinct paths.
            slope += (sum(ord(character) for character in normalized) % 7) / 100_000
            rows: list[dict[str, Any]] = []
            cursor = start
            value = 50.0 + (sum(ord(character) for character in normalized) % 30)
            while cursor <= self.as_of:
                if cursor.weekday() < 5:
                    value *= 1.0 + slope
                    rows.append({"date": cursor.isoformat(), "close": round(value, 6)})
                cursor += timedelta(days=1)
            self._rows[normalized] = rows
        return list(self._rows[normalized])


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SimulationError(f"Unable to read cloned AI state {path}: {exc}") from exc
    return dict(payload) if isinstance(payload, Mapping) else {}


def _simulation_config(
    *, ai_dir: Path, rules_path: Path, schema_path: Path, dashboard_url: str
) -> AnalystConfig:
    return AnalystConfig(
        legislative_dir=None,
        executive_dir=None,
        ai_dir=ai_dir,
        schema_path=schema_path,
        rules_path=rules_path,
        result_path=ai_dir / "simulation-analyst-result.json",
        analyses_csv_path=ai_dir / "simulation-latest-analyses.csv",
        portfolio_csv_path=ai_dir / "simulation-paper-portfolio.csv",
        enabled=True,
        paper_trading_only=True,
        reanalyze_existing=True,
        suppress_alerts=True,
        max_analyses=1,
        model="simulation-fixture",
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
        dashboard_url=dashboard_url,
        repository_url="",
        max_download_bytes=0,
        max_ocr_pages=0,
        request_timeout=(1.0, 1.0),
        gmail_address="",
        gmail_app_password="",
    )


def _fixed_ai_result() -> OpenAIResult:
    return OpenAIResult(
        payload={
            "analysis_summary": (
                "Deterministic synthetic context used only to verify the production "
                "scoring, Investor Edge, dashboard, and alert-preview path."
            ),
            "transaction_intent": "likely_discretionary",
            "owner_significance": "direct_household",
            "filer_relevance_score": 20,
            "policy_contract_relevance_score": 15,
            "market_confirmation_score": 10,
            "confidence": 0.75,
            "positive_factors": ["Synthetic production-path verification"],
            "negative_factors": ["No live market or contextual research was requested"],
            "contradictory_evidence": [],
            "evidence_sources": [
                {
                    "title": "Deterministic simulation evidence",
                    "url": "https://example.invalid/polititrack-simulation-evidence",
                    "published_date": "",
                    "claim": "Local fixture used only to exercise the external-evidence gate.",
                }
            ],
            "external_context_status": "not_requested",
        },
        response_id="simulation-no-openai-request",
        input_tokens=None,
        output_tokens=None,
    )


def _market_fixture(
    provider: OfflineMarketHistoryProvider, trade: Mapping[str, Any]
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    raw_transaction_date = str(trade.get("transaction_date") or "")[:10]
    try:
        transaction_date = date.fromisoformat(raw_transaction_date)
    except ValueError as exc:
        raise SimulationError("Synthetic candidate has no valid transaction date") from exc
    rows = provider.daily(ticker, minimum_date=transaction_date)
    transaction_row = next(
        (row for row in rows if str(row.get("date") or "") >= transaction_date.isoformat()),
        None,
    )
    if not rows or not transaction_row:
        raise SimulationError(f"Offline price fixture could not cover {ticker}")
    current_price = float(rows[-1]["close"])
    transaction_close = float(transaction_row["close"])
    daily = [
        {
            "date": str(row["date"]),
            "open": float(row["close"]) * 0.998,
            "high": float(row["close"]) * 1.01,
            "low": float(row["close"]) * 0.99,
            "close": float(row["close"]),
            "volume": 2_000_000,
        }
        for row in rows[-40:]
    ]
    return {
        "ticker": ticker,
        "status": "simulation_fixture",
        "current_price": round(current_price, 4),
        "transaction_date_close": round(transaction_close, 4),
        "average_volume_20d": 2_000_000,
        "atr_14": round(current_price * 0.02, 4),
        "daily": daily,
        "errors": [],
        "offline": True,
    }


def _matching_filing(
    trade: Mapping[str, Any], filings: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    source = str(trade.get("source") or "").casefold()
    report_id = str(trade.get("report_id") or "")
    for filing in filings:
        if (
            str(filing.get("source") or "").casefold() == source
            and str(filing.get("report_id") or "") == report_id
        ):
            return dict(filing)
    raise SimulationError("Synthetic candidate has no matching cloned filing")


def simulate_analysis_record(
    *,
    legislative_dir: Path | None,
    executive_dir: Path | None,
    ai_dir: Path,
    result_file: Path,
    rules_path: Path = DEFAULT_RULES,
    schema_path: Path = DEFAULT_SCHEMA,
    edge_config_path: Path | None = None,
    dashboard_url: str = "index.html?tab=analyses",
) -> dict[str, Any]:
    """Build and persist one synthetic record using the production scoring/Edge path."""

    all_transactions: list[dict[str, Any]] = []
    all_filings: list[dict[str, Any]] = []
    for branch, directory in (
        ("legislative", legislative_dir),
        ("executive", executive_dir),
    ):
        transactions, filings = load_tracker_data(directory)
        for row in transactions:
            row.setdefault("branch", branch)
        for row in filings:
            row.setdefault("branch", branch)
        all_transactions.extend(transactions)
        all_filings.extend(filings)

    rules = load_rules(rules_path)

    def scoring_view(row: Mapping[str, Any]) -> dict[str, Any]:
        """Remove isolation markers only inside this offline simulation fixture."""
        result = dict(row)
        for field_name in (
            "is_synthetic_test",
            "synthetic_test",
            "is_temporary",
            "test_metadata",
        ):
            result.pop(field_name, None)
        return result

    candidates = [
        row
        for row in all_transactions
        if bool(row.get("is_synthetic_test"))
        and eligible_trade(row, rules)
        and history_trade_eligibility(scoring_view(row)).get("eligible")
    ]
    explicitly_selected = [
        row
        for row in candidates
        if isinstance(row.get("test_metadata"), Mapping)
        and bool((row.get("test_metadata") or {}).get("investor_edge_candidate"))
    ]
    if explicitly_selected:
        candidates = explicitly_selected
    else:
        candidates = [
            row
            for row in candidates
            if not (
                isinstance(row.get("test_metadata"), Mapping)
                and (row.get("test_metadata") or {}).get("investor_edge_fixture_role")
                == "prior_history"
            )
        ]
    candidates.sort(
        key=lambda row: (
            str(row.get("filed_date") or ""),
            str(row.get("trade_id") or ""),
        ),
        reverse=True,
    )
    if not candidates:
        raise SimulationError(
            "No synthetic Investor Edge-eligible purchase exists in the isolated tracker tree"
        )
    synthetic_trade = dict(candidates[0])
    filing = _matching_filing(synthetic_trade, all_filings)
    trade = scoring_view(synthetic_trade)
    scoring_transactions = [scoring_view(row) for row in all_transactions]
    raw_as_of = str(trade.get("filed_date") or filing.get("filed_date") or "")[:10]
    try:
        as_of = date.fromisoformat(raw_as_of)
    except ValueError as exc:
        raise SimulationError("Synthetic candidate has no valid public filing date") from exc

    ai_dir.mkdir(parents=True, exist_ok=True)
    edge_config = load_edge_config(edge_config_path)
    edge_config["enabled"] = True
    edge_config["network_request_budget_per_run"] = 0
    minimum = max(1, int(edge_config.get("minimum_completed_trades", 3)))
    current_date = date.fromisoformat(str(trade["transaction_date"])[:10])
    mature_weight = 0.0
    for prior in matching_investor_records(trade, scoring_transactions):
        assessment = history_trade_eligibility(prior)
        prior_date = str(prior.get("transaction_date") or "")[:10]
        public_date = str(prior.get("observed_at_utc") or prior.get("filed_date") or "")[:10]
        if (assessment.get("eligible") and prior_date < current_date.isoformat()
                and public_date and public_date <= (as_of - timedelta(days=190)).isoformat()):
            mature_weight += float(assessment.get("quality_weight") or 0)
    supplemental_history = []
    if mature_weight < minimum:
        # The acceptance fixture must exercise the real minimum-sample gate.
        # Keep every invented record TEST-marked in the reported evidence;
        # strip markers only in the in-memory deterministic scoring adapter.
        prototype = {**synthetic_trade, "parse_confidence": "high", "transaction_intent": "discretionary"}
        quality = float(history_trade_eligibility(scoring_view(prototype)).get("quality_weight") or 0)
        if not quality:
            raise SimulationError("Cannot construct an eligible isolated history fixture")
        fixture_count = math.ceil(minimum / quality)
        for index in range(fixture_count):
            fixture_date = min(current_date, as_of) - timedelta(days=400 + index * 30)
            public_date = fixture_date + timedelta(days=7)
            fixture = {
                **prototype,
                "trade_id": f"TEST-{trade['trade_id']}-MINIMUM-HISTORY-{index + 1:03d}",
                "transaction_date": fixture_date.isoformat(),
                "filed_date": public_date.isoformat(),
                "observed_at_utc": f"{public_date.isoformat()}T12:00:00Z",
                "is_synthetic_test": True,
                "is_temporary": True,
                "test_metadata": {"investor_edge_fixture_role": "prior_history", "reason": "minimum_sample_acceptance"},
            }
            supplemental_history.append(fixture)
            scoring_transactions.append(scoring_view(fixture))
        synthetic_trade.setdefault("test_metadata", {})["supplemental_history_ids"] = [row["trade_id"] for row in supplemental_history]
    edge_config["backfill_analysis_limit_per_run"] = max(
        minimum + len(supplemental_history), int(edge_config.get("backfill_analysis_limit_per_run", 1))
    )
    profiles_payload = _read_mapping(ai_dir / PROFILE_FILE)
    profiles = profiles_payload.get("profiles") or {}
    if not isinstance(profiles, Mapping):
        profiles = {}
    observations_payload = _read_mapping(ai_dir / OBSERVATION_FILE)
    observations = observations_payload.get("observations") or {}
    if not isinstance(observations, Mapping):
        observations = {}
    provider = OfflineMarketHistoryProvider(as_of=as_of)
    runtime = InvestorEdgeRuntime(
        edge_config,
        ai_dir,
        provider,  # type: ignore[arg-type]
        {str(key): dict(value) for key, value in profiles.items() if isinstance(value, Mapping)},
        {
            str(key): dict(value)
            for key, value in observations.items()
            if isinstance(value, Mapping)
        },
    )
    config = _simulation_config(
        ai_dir=ai_dir,
        rules_path=rules_path,
        schema_path=schema_path,
        dashboard_url=dashboard_url,
    )
    record = build_analysis_record(
        trade=trade,
        filing=filing,
        ai_result=_fixed_ai_result(),
        market=_market_fixture(provider, trade),
        sec={"status": "simulation_fixture", "recent_filings": [], "errors": []},
        document={
            "status": "simulation_fixture",
            "content_hash": "simulation-no-document-download",
            "url": str(trade.get("source_url") or ""),
        },
        all_transactions=scoring_transactions,
        rules=rules,
        rules_hash=json_hash(rules),
        config=config,
        investor_edge=runtime,
        scoring_now=datetime(
            as_of.year, as_of.month, as_of.day, 12, 0, tzinfo=timezone.utc
        ),
    )
    profile = record.get("investor_edge") or {}
    if not isinstance(profile, Mapping):
        raise SimulationError("Production path did not persist an Investor Edge profile")
    expected_identity = investor_key(trade)
    assertions = {
        "synthetic_metadata_carried": bool(
            record.get("is_synthetic_test") and record.get("test_metadata")
        ),
        "identity_matches": bool(
            expected_identity
            and str(profile.get("investor_key") or "") == expected_identity
        ),
        "history_scored": int(record.get("investor_edge_observation_count") or 0) > 0,
        "edge_persisted": record.get("investor_edge_score") is not None,
        "confidence_persisted": record.get("investor_edge_confidence") is not None,
        "edge_status_persisted": str(record.get("investor_edge_status") or "")
        == "scored",
        "minimum_sample_gate_passed": bool(profile.get("minimum_sample_met")),
        "adjusted_price_basis_verified": profile.get("price_basis") == PRICE_BASIS,
        "base_score_persisted": record.get("base_score") is not None,
        "final_score_persisted": record.get("final_score") is not None,
        "modifier_persisted": record.get("investor_edge_modifier") is not None,
        "classification_persisted": bool(record.get("classification")),
        "candidate_alert_eligible": str(record.get("classification") or "")
        in {"high_priority", "watchlist"},
        "network_requests_zero": provider.network_requests == 0,
    }
    append_jsonl(ai_dir / "analyses.jsonl", [record])
    # The production scoring path already censored the candidate (and any cloned
    # source row with the same identity) when it built this profile. Persist that
    # exact snapshot so the isolated leaderboard cannot reintroduce the trade.
    candidate_profile = dict(profile)
    runtime.profiles[expected_identity] = candidate_profile
    runtime.save([candidate_profile])
    alert_preview = format_candidate_alert(record, dashboard_url)
    persisted_profiles = _read_mapping(ai_dir / PROFILE_FILE).get("profiles") or {}
    persisted_profile = (
        persisted_profiles.get(expected_identity)
        if isinstance(persisted_profiles, Mapping)
        else None
    )
    leaderboard_payload = _read_mapping(ai_dir / LEADERBOARD_FILE)
    leaderboard_rows = leaderboard_payload.get("investors") or []
    leaderboard_profile = next(
        (
            item
            for item in leaderboard_rows
            if isinstance(item, Mapping)
            and str(item.get("investor_key") or "") == expected_identity
        ),
        None,
    )
    record_edge = record.get("investor_edge_score")
    record_sample = int(record.get("investor_edge_observation_count") or 0)
    record_as_of = str(record.get("analyzed_at_utc") or "")[:10]
    profile_edge = candidate_profile.get("edge_score")
    profile_sample = int(candidate_profile.get("sample_count") or 0)
    profile_as_of = str(candidate_profile.get("as_of_date") or "")
    assertions.update(
        {
            "analysis_written_for_dashboard": (ai_dir / "analyses.jsonl").is_file(),
            "profile_written_for_dashboard": bool(
                isinstance(persisted_profile, Mapping)
            ),
            "leaderboard_written_for_dashboard": (ai_dir / LEADERBOARD_FILE).is_file(),
            "record_profile_edge_agree": record_edge == profile_edge,
            "record_profile_sample_agree": record_sample == profile_sample,
            "record_profile_as_of_agrees": record_as_of
            == profile_as_of
            == as_of.isoformat(),
            "persisted_profile_agrees": bool(
                isinstance(persisted_profile, Mapping)
                and persisted_profile.get("edge_score") == profile_edge
                and int(persisted_profile.get("sample_count") or 0) == profile_sample
                and str(persisted_profile.get("as_of_date") or "") == profile_as_of
            ),
            "leaderboard_profile_agrees": bool(
                isinstance(leaderboard_profile, Mapping)
                and leaderboard_profile.get("edge_score") == profile_edge
                and int(leaderboard_profile.get("sample_count") or 0) == profile_sample
                and str(leaderboard_profile.get("as_of_date") or "") == profile_as_of
            ),
            "alert_preview_generated": bool(
                alert_preview.get("title") and alert_preview.get("message")
            ),
            "alert_preview_contains_edge": "Edge " in alert_preview.get("message", ""),
        }
    )
    failed = [name for name, passed in assertions.items() if not passed]
    if failed:
        raise SimulationError(
            "Production-path simulation assertions failed: " + ", ".join(failed)
        )
    result = {
        "schema_version": 1,
        "kind": "investor_edge_run_simulation",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "offline": True,
        "real_alerts_sent": False,
        "openai_requests": 0,
        "network_requests": provider.network_requests,
        "restored_profile_count": len(profiles),
        "restored_observation_count": len(observations),
        "supplemental_history_fixtures": supplemental_history,
        "candidate_trade_id": str(trade.get("trade_id") or ""),
        "investor_key": expected_identity,
        "assertions": assertions,
        "verification": {"passed": all(assertions.values()), "assertions": assertions},
        "analysis": record,
        "alert_preview": alert_preview,
        "dashboard_inputs": {
            "analyses": str((ai_dir / "analyses.jsonl").resolve()),
            "profiles": str((ai_dir / PROFILE_FILE).resolve()),
            "leaderboard": str((ai_dir / LEADERBOARD_FILE).resolve()),
        },
    }
    write_json(result_file, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislative-dir", type=Path)
    parser.add_argument("--executive-dir", type=Path)
    parser.add_argument("--ai-dir", type=Path, required=True)
    parser.add_argument("--result-file", type=Path, required=True)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--investor-edge-config", type=Path)
    parser.add_argument("--dashboard-url", default="index.html?tab=analyses")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = simulate_analysis_record(
            legislative_dir=args.legislative_dir,
            executive_dir=args.executive_dir,
            ai_dir=args.ai_dir,
            result_file=args.result_file,
            rules_path=args.rules,
            schema_path=args.schema,
            edge_config_path=args.investor_edge_config,
            dashboard_url=args.dashboard_url,
        )
    except SimulationError as exc:
        print(f"Run Simulation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
