from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.run_filing_simulation import (
    GOAL_VALUE,
    STARTING_CAPITAL,
    SimulationError,
    directory_sha256,
    parse_as_of,
    run_simulation,
)


AS_OF = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def filing(
    report_id: str,
    *,
    first_seen: str,
    ticker: str,
    source: str = "house",
) -> dict[str, object]:
    return {
        "filing_key": f"{source}|{report_id}",
        "first_seen_utc": first_seen,
        "updated_at_utc": first_seen,
        "branch": "legislative" if source != "oge" else "executive",
        "source": source,
        "report_id": report_id,
        "filer": f"Filer {ticker}",
        "filed_date": "2026-08-28",
        "source_url": f"https://official.example/{report_id}.pdf",
        "status": "processed",
        "transaction_count": 1,
        "purchase_count": 1,
    }


def trade(
    trade_id: str,
    report_id: str,
    ticker: str,
    *,
    observed: str,
    source: str = "house",
    transaction_type: str = "Purchase",
    equity_like: bool = True,
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "observed_at_utc": observed,
        "branch": "legislative" if source != "oge" else "executive",
        "source": source,
        "report_id": report_id,
        "filer": f"Filer {ticker}",
        "owner": "Self",
        "asset": f"{ticker} Corporation",
        "ticker": ticker,
        "asset_type": "Stock",
        "transaction_type": transaction_type,
        "transaction_date": "2026-08-20",
        "notification_date": "2026-08-28",
        "filed_date": "2026-08-28",
        "amount": "$15,001 - $50,000",
        "source_url": f"https://official.example/{report_id}.pdf",
        "raw_row": "fixture",
        "equity_like": equity_like,
        "parse_confidence": "high",
    }


def analysis(
    analysis_id: str,
    trade_id: str,
    ticker: str,
    *,
    analyzed: str,
    quote: str | None,
    price: float | None,
) -> dict[str, object]:
    market: dict[str, object] = {
        "ticker": ticker,
        "current_price": price,
        "data_status": "complete" if price else "unavailable",
    }
    if quote is not None:
        market["quote_timestamp_utc"] = quote
    return {
        "analysis_id": analysis_id,
        "trade_id": trade_id,
        "analyzed_at_utc": analyzed,
        "model": "fixture-model",
        "ticker": ticker,
        "score": 82,
        "classification": "high_priority",
        "source_url": "https://official.example/report.pdf",
        "entry_plan": {"entry_status": "review_now", "current_price": price},
        "market": market,
        "ai": {
            "evidence_sources": [
                {
                    "title": "Official evidence",
                    "url": "https://evidence.example/item",
                    "published_date": "2026-08-28",
                }
            ]
        },
    }


def fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    legislative = tmp_path / "legislative"
    executive = tmp_path / "executive"
    ai = tmp_path / "ai"
    for directory in (legislative, executive, ai):
        directory.mkdir()
        (directory / "state.json").write_text('{"version":1}\n', encoding="utf-8")

    filings = [
        filing("report-a", first_seen="2026-08-29T10:00:00Z", ticker="AAA"),
        filing("report-b", first_seen="2026-08-29T11:00:00Z", ticker="BBB"),
        filing("report-late", first_seen="2026-08-29T18:00:00Z", ticker="LATE"),
    ]
    transactions = [
        trade(
            "trade-a",
            "report-a",
            "AAA",
            observed="2026-08-29T10:00:00Z",
        ),
        trade(
            "trade-b",
            "report-b",
            "BBB",
            observed="2026-08-29T11:00:00Z",
        ),
        trade(
            "trade-late",
            "report-late",
            "LATE",
            observed="2026-08-29T18:00:00Z",
        ),
        trade(
            "trade-sale",
            "report-a",
            "AAA",
            observed="2026-08-29T10:00:00Z",
            transaction_type="Sale",
        ),
        trade(
            "trade-fund",
            "report-a",
            "FUND",
            observed="2026-08-29T10:00:00Z",
            equity_like=False,
        ),
    ]
    write_jsonl(legislative / "filings.jsonl", filings)
    write_jsonl(legislative / "transactions.jsonl", transactions)
    write_jsonl(
        ai / "analyses.jsonl",
        [
            analysis(
                "analysis-a-before-disclosure",
                "trade-a",
                "AAA",
                analyzed="2026-08-29T09:00:00Z",
                quote="2026-08-29T08:55:00Z",
                price=50.0,
            ),
            analysis(
                "analysis-a-entry",
                "trade-a",
                "AAA",
                analyzed="2026-08-29T12:00:00Z",
                quote="2026-08-29T11:55:00Z",
                price=100.0,
            ),
            analysis(
                "analysis-a-value",
                "trade-a",
                "AAA",
                analyzed="2026-08-29T15:00:00Z",
                quote="2026-08-29T14:55:00Z",
                price=150.0,
            ),
            analysis(
                "analysis-a-future",
                "trade-a",
                "AAA",
                analyzed="2026-08-29T19:00:00Z",
                quote="2026-08-29T18:55:00Z",
                price=300.0,
            ),
            analysis(
                "analysis-b",
                "trade-b",
                "BBB",
                analyzed="2026-08-29T12:30:00Z",
                quote="2026-08-29T12:25:00Z",
                price=250.0,
            ),
        ],
    )
    return legislative, executive, ai


def test_seeded_simulation_is_deterministic_and_outputs_only_state_files(
    tmp_path: Path,
) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    first = run_simulation(
        legislative_dir=legislative,
        executive_dir=executive,
        ai_dir=ai,
        output_dir=tmp_path / "output-one",
        as_of=AS_OF,
        seed="repeatable-seed",
    )
    second = run_simulation(
        legislative_dir=legislative,
        executive_dir=executive,
        ai_dir=ai,
        output_dir=tmp_path / "output-two",
        as_of=AS_OF,
        seed="repeatable-seed",
    )

    assert first == second
    assert first["selection"]["candidate_filing_count"] == 2
    assert first["selection"]["candidate_trade_count"] == 2
    assert {path.name for path in (tmp_path / "output-one").iterdir()} == {
        "simulation-result.json",
        "simulation-runs.jsonl",
    }


def test_inputs_are_not_mutated_and_recorded_hashes_match(tmp_path: Path) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    before_bytes = {
        path: path.read_bytes()
        for directory in (legislative, executive, ai)
        for path in directory.rglob("*")
        if path.is_file()
    }
    before_hashes = {
        "legislative": directory_sha256(legislative),
        "executive": directory_sha256(executive),
        "ai": directory_sha256(ai),
    }

    result = run_simulation(
        legislative_dir=legislative,
        executive_dir=executive,
        ai_dir=ai,
        output_dir=tmp_path / "output",
        as_of=AS_OF,
        trade_id="trade-a",
    )

    assert {path: path.read_bytes() for path in before_bytes} == before_bytes
    assert {name: directory_sha256(path) for name, path in {
        "legislative": legislative,
        "executive": executive,
        "ai": ai,
    }.items()} == before_hashes
    assert result["input_sha256"] == {
        "algorithm": "sha256-tree-v1",
        **before_hashes,
    }
    assert result["safety"] == {
        "paper_only": True,
        "network_calls": False,
        "alerts_sent": False,
        "production_inputs_mutated": False,
    }


def test_as_of_excludes_future_filing_analysis_and_market_price(tmp_path: Path) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    cutoff = parse_as_of("2026-08-29T13:00:00Z")
    result = run_simulation(
        legislative_dir=legislative,
        executive_dir=executive,
        ai_dir=ai,
        output_dir=tmp_path / "output",
        as_of=cutoff,
        trade_id="trade-a",
    )

    assert result["analysis"]["version_count"] == 1
    assert result["accounting"]["entry_price_usd"] == 100.0
    assert result["accounting"]["valuation_price_usd"] == 100.0
    assert result["accounting"]["portfolio_value_usd"] == 10000.0
    assert result["price_context"]["valuation_analysis_id"] == "analysis-a-entry"

    with pytest.raises(SimulationError, match="not an eligible purchase available"):
        run_simulation(
            legislative_dir=legislative,
            executive_dir=executive,
            ai_dir=ai,
            output_dir=tmp_path / "late-output",
            as_of=cutoff,
            trade_id="trade-late",
        )


def test_accounting_uses_earliest_entry_and_latest_as_of_valuation(tmp_path: Path) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    result = run_simulation(
        legislative_dir=legislative,
        executive_dir=executive,
        ai_dir=ai,
        output_dir=tmp_path / "output",
        as_of=AS_OF,
        trade_id="trade-a",
    )

    assert STARTING_CAPITAL == 10000
    assert GOAL_VALUE == 20000
    assert result["accounting"] == {
        "status": "priced",
        "reason": "",
        "strategy": "single_filing_full_allocation_fractional_shares",
        "starting_cash_usd": 10000.0,
        "cash_usd": 0.0,
        "shares": 100.0,
        "entry_price_usd": 100.0,
        "valuation_price_usd": 150.0,
        "position_value_usd": 15000.0,
        "portfolio_value_usd": 15000.0,
        "profit_loss_usd": 5000.0,
        "return_percent": 50.0,
    }
    assert result["objective"] == {
        "starting_capital_usd": 10000.0,
        "goal_value_usd": 20000.0,
        "goal_reached": False,
        "goal_progress_percent": 75.0,
        "remaining_to_goal_usd": 5000.0,
    }
    assert result["provenance"]["filing_source_url"].startswith("https://official.example/")
    assert result["provenance"]["evidence_sources"][0]["url"] == (
        "https://evidence.example/item"
    )


def test_missing_price_is_explicit_and_capital_remains_cash(tmp_path: Path) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    write_jsonl(
        ai / "analyses.jsonl",
        [
            analysis(
                "analysis-a-unpriced",
                "trade-a",
                "AAA",
                analyzed="2026-08-29T12:00:00Z",
                quote="2026-08-29T11:55:00Z",
                price=None,
            )
        ],
    )
    result = run_simulation(
        legislative_dir=legislative,
        executive_dir=executive,
        ai_dir=ai,
        output_dir=tmp_path / "output",
        as_of=AS_OF,
        trade_id="trade-a",
    )

    assert result["accounting"]["status"] == "unpriced"
    assert result["accounting"]["cash_usd"] == 10000.0
    assert result["accounting"]["portfolio_value_usd"] == 10000.0
    assert result["accounting"]["entry_price_usd"] is None
    assert "No retained AI analysis market price" in result["accounting"]["reason"]


def test_history_is_append_only(tmp_path: Path) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    output = tmp_path / "output"
    for _ in range(2):
        run_simulation(
            legislative_dir=legislative,
            executive_dir=executive,
            ai_dir=ai,
            output_dir=output,
            as_of=AS_OF,
            trade_id="trade-b",
        )

    lines = (output / "simulation-runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == json.loads(lines[1])
    assert json.loads((output / "simulation-result.json").read_text()) == json.loads(lines[-1])


def test_no_candidates_fails_clearly_without_writing_output(tmp_path: Path) -> None:
    legislative, executive, ai = fixture_inputs(tmp_path)
    output = tmp_path / "output"
    with pytest.raises(SimulationError, match="No eligible equity purchase filings"):
        run_simulation(
            legislative_dir=legislative,
            executive_dir=executive,
            ai_dir=ai,
            output_dir=output,
            as_of=parse_as_of("2026-08-29T09:00:00Z"),
            seed="none-yet",
        )
    assert not output.exists()


def test_as_of_requires_timezone() -> None:
    with pytest.raises(SimulationError, match="UTC offset or Z"):
        parse_as_of("2026-08-29T16:00:00")
