from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from scripts.create_manual_test_filing import ManualTestError, generate_manual_test
from scripts.build_trade_dashboard import build_payload, build_site, load_branch


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def tree_snapshot(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def filing(
    *,
    report_id: str = "house:2026:100",
    filed_date: str = "2026-08-20",
    status: str = "processed",
) -> dict[str, object]:
    return {
        "filing_key": f"house|{report_id}",
        "first_seen_utc": "2026-08-20T10:00:00Z",
        "updated_at_utc": "2026-08-20T10:05:00Z",
        "branch": "legislative",
        "source": "house",
        "report_id": report_id,
        "filer": "Example Representative",
        "filed_date": filed_date,
        "source_url": "https://example.test/original-filing.pdf",
        "document_format": "pdf",
        "chamber": "House",
        "title": "Representative",
        "agency": "",
        "district": "MA-01",
        "report_type": "Periodic Transaction Report",
        "access_mode": "direct",
        "status": status,
        "transaction_count": 2,
        "purchase_count": 1,
        "sale_count": 1,
        "exchange_count": 0,
        "review_reason": "",
    }


def trade(
    trade_id: str,
    transaction_type: str,
    *,
    report_id: str = "house:2026:100",
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "observed_at_utc": "2026-08-20T10:05:00Z",
        "branch": "legislative",
        "source": "house",
        "report_id": report_id,
        "filer": "Example Representative",
        "chamber": "House",
        "title": "Representative",
        "agency": "",
        "owner": "Self",
        "asset": "Example Corporation",
        "ticker": "EXM",
        "asset_type": "Stock",
        "transaction_type": transaction_type,
        "transaction_date": "2026-08-12",
        "notification_date": "2026-08-18",
        "filed_date": "2026-08-20",
        "amount": "$1,001 - $15,000",
        "source_url": "https://example.test/original-filing.pdf",
        "raw_row": f"Example Corporation {transaction_type}",
        "equity_like": True,
        "parse_confidence": "high",
    }


def tracker_state() -> dict[str, object]:
    return {
        "version": 1,
        "seen_filings": {
            "house": {"house:2026:100": "2026-08-20T10:05:00Z"},
            "senate": {},
            "oge": {},
        },
        "seen_trades": {
            "trade:buy": "2026-08-20T10:05:00Z",
            "trade:sale": "2026-08-20T10:05:00Z",
        },
        "seen_reviews": {},
        "last_attempt_utc": "2026-08-20T10:00:00Z",
        "last_success_utc": "2026-08-20T10:05:00Z",
        "last_counts": {"house": 1},
    }


def make_legislative_artifact(directory: Path) -> None:
    write_jsonl(
        directory / "filings.jsonl",
        [
            filing(status="cataloged"),
            filing(),  # The latest record for this key is eligible.
            filing(report_id="house:today", filed_date="2026-08-29"),
            filing(report_id="house:unparsed", status="cataloged"),
        ],
    )
    purchase = trade("trade:buy", "Purchase")
    sale = trade("trade:sale", "Sale (Full)")
    write_jsonl(directory / "transactions.jsonl", [purchase, sale])
    write_jsonl(directory / "purchases.jsonl", [purchase])
    write_jsonl(directory / "runs.jsonl", [{"run_key": "real:1", "success": True}])
    (directory / "state.json").write_text(
        json.dumps(tracker_state(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (directory / "retained-diagnostic.txt").write_text("keep me\n", encoding="utf-8")


def make_executive_artifact(directory: Path) -> None:
    directory.mkdir(parents=True)
    write_jsonl(directory / "filings.jsonl", [])
    (directory / "state.json").write_text(
        json.dumps(
            {
                "version": 1,
                "seen_filings": {"house": {}, "senate": {}, "oge": {}},
                "seen_trades": {},
            }
        ),
        encoding="utf-8",
    )
    (directory / "executive-only.txt").write_text("real executive data\n", encoding="utf-8")


def test_generator_copies_full_inputs_and_appends_one_consistent_test_clone(
    tmp_path: Path,
) -> None:
    legislative = tmp_path / "restored-legislative"
    executive = tmp_path / "restored-executive"
    output = tmp_path / "manual-preview-input"
    make_legislative_artifact(legislative)
    make_executive_artifact(executive)
    source_before = {
        "legislative": tree_snapshot(legislative),
        "executive": tree_snapshot(executive),
    }

    manifest = generate_manual_test(
        legislative_dir=legislative,
        executive_dir=executive,
        output_dir=output,
        as_of=date(2026, 8, 29),
        chooser=lambda candidates: candidates[0],
        token_factory=lambda: "a1b2c3",
        now=datetime(2026, 8, 29, 14, 15, 16, tzinfo=timezone.utc),
    )

    # Inputs remain byte-for-byte unchanged and every retained source file is copied.
    assert tree_snapshot(legislative) == source_before["legislative"]
    assert tree_snapshot(executive) == source_before["executive"]
    assert (output / "legislative" / "retained-diagnostic.txt").read_text() == "keep me\n"
    assert (output / "executive" / "executive-only.txt").read_text() == "real executive data\n"
    assert read_jsonl(output / "legislative" / "runs.jsonl") == [
        {"run_key": "real:1", "success": True}
    ]

    output_filings = read_jsonl(output / "legislative" / "filings.jsonl")
    output_transactions = read_jsonl(output / "legislative" / "transactions.jsonl")
    output_purchases = read_jsonl(output / "legislative" / "purchases.jsonl")
    assert len(output_filings) == 5
    assert len(output_transactions) == 4
    assert len(output_purchases) == 2

    test_filing = output_filings[-1]
    test_transactions = output_transactions[-2:]
    test_purchase = output_purchases[-1]
    assert test_filing["filing_key"].startswith("TEST-")
    assert test_filing["report_id"].startswith("TEST-")
    assert all(row["trade_id"].startswith("TEST-") for row in test_transactions)
    assert len({row["trade_id"] for row in test_transactions}) == 2
    assert test_purchase["trade_id"] == test_transactions[0]["trade_id"]
    assert test_purchase["report_id"] == test_filing["report_id"]
    assert all(row["report_id"] == test_filing["report_id"] for row in test_transactions)

    # Only observation/filing dates and identifiers are changed; source facts survive.
    assert test_filing["filed_date"] == "2026-08-29"
    assert test_filing["first_seen_utc"] == "2026-08-29T14:15:16Z"
    assert test_filing["updated_at_utc"] == "2026-08-29T14:15:16Z"
    assert test_filing["source_url"] == "https://example.test/original-filing.pdf"
    assert {row["transaction_date"] for row in test_transactions} == {"2026-08-12"}
    assert {row["source_url"] for row in test_transactions} == {
        "https://example.test/original-filing.pdf"
    }
    assert {row["filed_date"] for row in test_transactions} == {"2026-08-29"}
    assert {row["observed_at_utc"] for row in test_transactions} == {
        "2026-08-29T14:15:16Z"
    }
    assert test_filing["transaction_count"] == 2
    assert test_filing["purchase_count"] == 1
    assert test_filing["sale_count"] == 1

    for row in [test_filing, *test_transactions, test_purchase]:
        assert row["is_synthetic_test"] is True
        assert row["is_temporary"] is True
        assert row["test_metadata"]["kind"] == "manual_test_filing"
        assert row["test_metadata"]["original_report_id"] == "house:2026:100"

    copied_state = json.loads((output / "legislative" / "state.json").read_text())
    assert copied_state["seen_filings"]["house"][test_filing["report_id"]] == (
        "2026-08-29T14:15:16Z"
    )
    assert set(manifest["test_trade_ids"]).issubset(copied_state["seen_trades"])
    assert copied_state["manual_test"]["notifications_sent"] is False
    assert copied_state["last_success_utc"] == "2026-08-20T10:05:00Z"

    assert manifest["temporary"] is True
    assert manifest["synthetic"] is True
    assert manifest["notifications_sent"] is False
    assert manifest["original_report_id"] == "house:2026:100"
    assert json.loads((output / "manual-test.json").read_text()) == manifest

    # The normal dashboard builder consumes the isolated tree and retains the test rows.
    payload = build_payload(
        load_branch(output / "legislative", "legislative"),
        load_branch(output / "executive", "executive"),
        repository_url="https://example.test/PolitiTrack",
    )
    assert any(row["filing_key"] == test_filing["filing_key"] for row in payload["filings"])
    assert set(manifest["test_trade_ids"]).issubset(
        {row["trade_id"] for row in payload["transactions"]}
    )
    assert payload["summary"]["manual_test_filing_count"] == 1
    assert payload["summary"]["manual_test_transaction_count"] == 2
    site_dir = tmp_path / "site"
    build_site(payload, site_dir)
    rendered_index = (site_dir / "index.html").read_text(encoding="utf-8")
    rendered_app = (site_dir / "app.js").read_text(encoding="utf-8")
    rendered_filings = json.loads((site_dir / "data" / "filings.json").read_text())
    rendered_summary = json.loads((site_dir / "data" / "summary.json").read_text())
    rendered_filings_csv = (site_dir / "data" / "filings.csv").read_text(encoding="utf-8")
    assert "app.js" in rendered_index
    assert "Manual Test preview" in rendered_index
    assert "Temporary Manual Test" in rendered_app
    assert any(row["filing_key"] == test_filing["filing_key"] for row in rendered_filings)
    assert rendered_summary["manual_test_filing_count"] == 1
    assert rendered_summary["manual_test_transaction_count"] == 2
    assert test_filing["filing_key"] in rendered_filings_csv


def test_generator_supports_one_input_and_purchase_only_historical_records(
    tmp_path: Path,
) -> None:
    legislative = tmp_path / "legislative"
    legislative.mkdir()
    write_jsonl(legislative / "filings.jsonl", [filing()])
    write_jsonl(legislative / "purchases.jsonl", [trade("trade:legacy", "Purchase")])
    (legislative / "state.json").write_text(json.dumps(tracker_state()), encoding="utf-8")

    manifest = generate_manual_test(
        legislative_dir=legislative,
        executive_dir=None,
        output_dir=tmp_path / "output",
        as_of=date(2026, 8, 29),
        chooser=lambda candidates: candidates[0],
        token_factory=lambda: "legacy",
        now=datetime(2026, 8, 29, tzinfo=timezone.utc),
    )

    assert manifest["cloned_transaction_rows"] == 0
    assert manifest["cloned_purchase_rows"] == 1
    assert not (tmp_path / "output" / "executive").exists()
    assert len(read_jsonl(tmp_path / "output" / "legislative" / "purchases.jsonl")) == 2


def test_generator_fails_clearly_without_eligible_filing_and_leaves_no_output(
    tmp_path: Path,
) -> None:
    legislative = tmp_path / "legislative"
    legislative.mkdir()
    write_jsonl(
        legislative / "filings.jsonl",
        [filing(status="cataloged"), filing(report_id="house:today", filed_date="2026-08-29")],
    )
    (legislative / "state.json").write_text(json.dumps(tracker_state()), encoding="utf-8")
    before = tree_snapshot(legislative)

    with pytest.raises(
        ManualTestError,
        match="No eligible historical processed filing with associated transaction data",
    ):
        generate_manual_test(
            legislative_dir=legislative,
            executive_dir=None,
            output_dir=tmp_path / "output",
            as_of=date(2026, 8, 29),
        )

    assert not (tmp_path / "output").exists()
    assert tree_snapshot(legislative) == before


def test_generator_rejects_output_inside_source(tmp_path: Path) -> None:
    legislative = tmp_path / "legislative"
    make_legislative_artifact(legislative)

    with pytest.raises(ManualTestError, match="must be isolated"):
        generate_manual_test(
            legislative_dir=legislative,
            executive_dir=None,
            output_dir=legislative / "unsafe-output",
            as_of=date(2026, 8, 29),
        )

    assert not (legislative / "unsafe-output").exists()
