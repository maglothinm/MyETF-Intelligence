from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import government_trade_tracker as tracker
from scripts import historical_transaction_bootstrap as bootstrap


def config_at(tmp_path: Path, *, branch: str = "legislative", limit: int = 20) -> tracker.TrackerConfig:
    args = tracker.build_parser().parse_args(["--branch", branch])
    config = tracker.build_config(args)
    return replace(config, state_path=tmp_path / "state.json", transactions_path=tmp_path / "transactions.jsonl",
                   ledger_path=tmp_path / "purchases.jsonl", filings_path=tmp_path / "filings.jsonl",
                   pending_path=tmp_path / "pending-review.jsonl", terms_acknowledged=True,
                   historical_filing_backfill_limit_per_run=limit, historical_source_documents_manifest=None,
                   # Prove silence is intrinsic, not dependent on --no-notify.
                   no_notify=False)


def filing(number: int, *, source: str = "house") -> dict:
    return {"filing_key": f"{source}|{source}:2025:{number}", "branch": "executive" if source == "oge" else "legislative",
            "source": source, "report_id": f"{source}:2025:{number}", "filer": f"Historical Official {number}",
            "filed_date": f"2025-04-{number:02d}", "first_seen_utc": "2025-04-25T10:11:12Z",
            "source_url": f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2025/{number}.pdf" if source == "house"
            else f"https://efdsearch.senate.gov/search/view/ptr/{number}/" if source == "senate"
            else f"https://extapps2.oge.gov/201/request/{number}",
            "document_format": "pdf" if source == "house" else "html" if source == "senate" else "request",
            "access_mode": "direct" if source != "oge" else "request", "status": "cataloged",
            "transaction_count": 0, "purchase_count": 0, "sale_count": 0, "exchange_count": 0,
            "chamber": source.title(), "title": "", "agency": "", "district": "", "report_type": "PTR",
            "review_reason": "", "updated_at_utc": "2025-04-25T10:11:12Z"}


def trade_for(report: tracker.Report, *, kind: str = "P") -> tracker.Trade:
    return tracker.make_trade(branch="legislative", source=report.source, report=report, owner="SP",
                              asset="Microsoft Corporation (MSFT) [ST]", ticker="MSFT", asset_type="ST",
                              transaction_type=kind, transaction_date="2025-04-01", notification_date="2025-04-02",
                              amount="$1,001 - $15,000", raw_row="historical test fixture", confidence="high")


def baseline(config: tracker.TrackerConfig, rows: list[dict]) -> tuple[tracker.TrackerState, dict]:
    state = tracker.TrackerState()
    for row in rows:
        state.seen_filings[row["source"]][row["report_id"]] = "2025-04-25T10:11:12Z"
    state.seen_trades["prior-trade"] = "2024-01-01T00:00:00Z"
    state.seen_reviews["prior-review"] = "2024-01-01T00:00:00Z"
    tracker.save_state(config.state_path, state)
    tracker.append_jsonl(config.filings_path, rows)
    return state, {row["filing_key"]: row for row in rows}


def run(config, state, index, **kwargs):
    result = tracker.TrackerResult(branch=config.branch, started_utc="2026-08-31T12:00:00Z")
    session = Mock()
    session.get.side_effect = AssertionError("Unexpected network")
    metrics = bootstrap.run_historical_transaction_backfill(config=config, state=state, result=result,
                                                           session=session, filing_index=index, **kwargs)
    return result, metrics, session


def test_catalog_backfill_is_bounded_idempotent_and_never_notifies(tmp_path, monkeypatch):
    config = config_at(tmp_path, limit=1)
    rows = [filing(1), filing(2)]
    rows[0]["original_source_metadata"] = {"preserve": "unchanged"}
    state, index = baseline(config, rows)
    old_filings = copy.deepcopy(state.seen_filings)
    old_reviews = copy.deepcopy(state.seen_reviews)
    old_prefix = config.filings_path.read_bytes()
    notification = Mock(side_effect=AssertionError("Historical records must never alert"))
    monkeypatch.setattr(tracker, "send_filing_notification", notification)
    monkeypatch.setattr(tracker, "send_pending_notification", notification)
    scanner = Mock(side_effect=lambda session, report, cfg: ([trade_for(report), trade_for(report, kind="S")], None))
    monkeypatch.setattr(tracker, "scan_house_report", scanner)

    result, first, _ = run(config, state, index)
    assert first["attempted_this_run"] == first["completed_this_run"] == 1
    assert first["pending_filing_count"] == 1
    assert result.filings == result.transactions == result.purchases == []
    assert result.alerted_filing_counts == result.new_filing_counts == result.baseline_counts == {}
    assert config.filings_path.read_bytes().startswith(old_prefix)
    first_prefix = config.transactions_path.read_bytes()
    second_result, second, _ = run(config, state, index)
    assert second["completed_this_run"] == 1 and second["pending_filing_count"] == 0
    assert config.transactions_path.read_bytes().startswith(first_prefix)
    before_third = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    _, third, _ = run(config, state, index)
    assert third["attempted_this_run"] == 0
    assert {path: path.read_bytes() for path in before_third} == before_third
    assert state.seen_filings == old_filings and state.seen_reviews == old_reviews
    assert state.seen_trades["prior-trade"] == "2024-01-01T00:00:00Z"
    assert scanner.call_count == 2 and notification.call_count == 0
    transactions = tracker.read_jsonl(config.transactions_path)
    assert len(transactions) == 4 and len(tracker.read_jsonl(config.ledger_path)) == 2
    assert all(row["historical_bootstrap"] is True for row in transactions)
    assert all(row["observed_at_utc"] == "2025-04-25T10:11:12Z" for row in transactions)
    assert all(row["first_seen_utc"] == "2025-04-25T10:11:12Z" for row in index.values())
    assert all(row["historical_bootstrap"] is True for row in index.values())
    assert index[rows[0]["filing_key"]]["original_source_metadata"] == {"preserve": "unchanged"}
    assert {row["trade_id"] for row in transactions} == {
        trade_for(bootstrap._report(row), kind=kind).trade_id for row in rows for kind in ("P", "S")}
    tracker.catalog_visible_filings(config=config, state=state, result=result, source="house",
                                    reports=[bootstrap._report(row) for row in rows], filing_index=index,
                                    treat_unseen_as_new=True)
    assert all(row["historical_bootstrap"] is True for row in index.values())
    assert index[rows[0]["filing_key"]]["original_source_metadata"] == {"preserve": "unchanged"}
    assert result.filings == []


def test_official_cached_original_document_is_used_before_network(tmp_path, monkeypatch):
    config = config_at(tmp_path)
    row = filing(1)
    state, index = baseline(config, [row])
    data = b"%PDF-original-source-fixture"
    (tmp_path / "source.pdf").write_bytes(data)
    (tmp_path / "historical-source-documents.json").write_text(json.dumps({"documents": [{
        "filing_key": row["filing_key"], "source_url": row["source_url"], "path": "source.pdf",
        "sha256": hashlib.sha256(data).hexdigest(), "format": "pdf"}]}))
    # Reuse the actual House parser, supplying the source extractor's text.
    monkeypatch.setattr(tracker, "extract_pdf_text", lambda *args, **kwargs: """
        Transactions
        SP Microsoft Corporation (MSFT) [ST]
        P 04/01/2025 04/02/2025 $1,001 - $15,000
        F S: New
        * For the complete list of asset type abbreviations
    """)
    scanner = Mock(wraps=tracker.scan_house_report)
    monkeypatch.setattr(tracker, "scan_house_report", scanner)
    _, metrics, session = run(config, state, index)
    assert metrics["cache_hits_this_run"] == metrics["completed_this_run"] == 1
    assert metrics["transactions_appended"] == 1
    assert scanner.call_count == 1 and session.get.call_count == 0
    assert tracker.read_jsonl(config.transactions_path)[0]["ticker"] == "MSFT"


@pytest.mark.parametrize("bad_field,bad_value", [("sha256", "0" * 64), ("path", "../outside.pdf"),
                                                ("source_url", "https://example.com/wrong.pdf")])
def test_invalid_cached_document_fails_closed_without_network(tmp_path, monkeypatch, bad_field, bad_value):
    config = config_at(tmp_path)
    row = filing(1)
    state, index = baseline(config, [row])
    data = b"%PDF-original"
    (tmp_path / "source.pdf").write_bytes(data)
    entry = {"filing_key": row["filing_key"], "source_url": row["source_url"], "path": "source.pdf",
             "sha256": hashlib.sha256(data).hexdigest(), "format": "pdf", bad_field: bad_value}
    (tmp_path / "historical-source-documents.json").write_text(json.dumps({"documents": [entry]}))
    scanner = Mock(side_effect=AssertionError("Corrupt cache must not bypass validation"))
    monkeypatch.setattr(tracker, "scan_house_report", scanner)
    _, metrics, _ = run(config, state, index)
    assert metrics["completed_this_run"] == 0
    assert metrics["blocked_filing_counts"] == {"invalid_cached_document": 1}
    assert not config.transactions_path.exists()
    assert scanner.call_count == 0


def test_oge_request_inventory_is_blocked_without_fetch_or_new_review(tmp_path, monkeypatch):
    config = config_at(tmp_path, branch="executive", limit=1)
    state, index = baseline(config, [filing(1, source="oge"), filing(2, source="oge")])
    scanner = Mock(side_effect=AssertionError("Do not bypass Form 201"))
    monkeypatch.setattr(tracker, "scan_oge_listing", scanner)
    before = copy.deepcopy(asdict(state))
    _, metrics, session = run(config, state, index)
    assert metrics["blocked_filing_counts"] == {"access_required": 2}
    assert metrics["attempted_this_run"] == metrics["pending_filing_count"] == 0
    assert scanner.call_count == session.get.call_count == 0
    assert asdict(state) == before and not config.pending_path.exists()


def test_failed_old_filing_does_not_starve_unattempted_filings(tmp_path, monkeypatch):
    config = config_at(tmp_path, limit=1)
    state, index = baseline(config, [filing(1), filing(2)])
    calls = []
    def scan(session, report, cfg):
        calls.append(report.report_id)
        if report.report_id.endswith(":2"):
            raise tracker.SourceChangedError("private untrusted document details must not be exported")
        return [trade_for(report)], None
    monkeypatch.setattr(tracker, "scan_house_report", scan)
    _, first, _ = run(config, state, index)
    _, second, _ = run(config, state, index)
    assert calls == ["house:2025:2", "house:2025:1"]
    assert first["pending_filing_count"] == 2 and second["pending_filing_count"] == 1
    assert second["completed_this_run"] == 1
    assert "private untrusted" not in (tmp_path / "historical-backfill.jsonl").read_text()


def test_duplicates_and_existing_ids_are_never_appended_again(tmp_path, monkeypatch):
    config = config_at(tmp_path)
    row = filing(1)
    state, index = baseline(config, [row])
    purchase = trade_for(bootstrap._report(row))
    sale = trade_for(bootstrap._report(row), kind="S")
    state.seen_trades[sale.trade_id] = "2025-04-26T00:00:00Z"
    monkeypatch.setattr(tracker, "scan_house_report", lambda *args: ([purchase, purchase, sale], None))
    _, metrics, _ = run(config, state, index)
    assert metrics["transactions_appended"] == 2
    assert len(tracker.read_jsonl(config.transactions_path)) == 2
    assert state.seen_trades[sale.trade_id] == "2025-04-26T00:00:00Z"


@pytest.mark.parametrize("body", ["<html>login</html>", "<html>Access denied</html>", "<html></html>",
                                "<html><table><tr><th>Transaction Date</th><th>Type</th><th>Amount</th></tr></table></html>"])
def test_cached_senate_report_uses_normal_session_and_parser_validation(tmp_path, body):
    config = config_at(tmp_path)
    row = filing(1, source="senate")
    state, index = baseline(config, [row])
    data = body.encode()
    (tmp_path / "source.html").write_bytes(data)
    (tmp_path / "historical-source-documents.json").write_text(json.dumps({"documents": [{
        "filing_key": row["filing_key"], "source_url": row["source_url"], "path": "source.html",
        "sha256": hashlib.sha256(data).hexdigest(), "format": "html"}]}))
    _, metrics, session = run(config, state, index)
    assert metrics["completed_this_run"] == 0
    assert metrics["blocked_filing_counts"] == {"cached_report_rejected": 1}
    assert session.get.call_count == 0 and not config.transactions_path.exists()
    assert tracker.read_jsonl(tmp_path / "historical-backfill.jsonl")[0]["reason"] == "official_report_validation_failed"


def test_cached_senate_valid_report_passes_existing_parser(tmp_path):
    config = config_at(tmp_path)
    row = filing(1, source="senate")
    state, index = baseline(config, [row])
    data = b"""<html><table><tr><th>Transaction Date</th><th>Owner</th><th>Ticker</th>
    <th>Asset Name</th><th>Asset Type</th><th>Transaction Type</th><th>Amount</th></tr>
    <tr><td>04/01/2025</td><td>Spouse</td><td>MSFT</td><td>Microsoft</td>
    <td>Stock</td><td>Purchase</td><td>$1,001 - $15,000</td></tr></table></html>"""
    (tmp_path / "source.html").write_bytes(data)
    (tmp_path / "historical-source-documents.json").write_text(json.dumps({"documents": [{
        "filing_key": row["filing_key"], "source_url": row["source_url"], "path": "source.html",
        "sha256": hashlib.sha256(data).hexdigest(), "format": "html"}]}))
    _, metrics, session = run(config, state, index)
    assert metrics["completed_this_run"] == metrics["transactions_appended"] == 1
    assert session.get.call_count == 0
    trade = tracker.read_jsonl(config.transactions_path)[0]
    assert trade["source"] == "senate" and trade["owner"] == "Spouse" and trade["ticker"] == "MSFT"


def test_restore_terms_and_original_observation_are_required(tmp_path, monkeypatch):
    config = config_at(tmp_path)
    state = tracker.TrackerState()
    with pytest.raises(tracker.MonitorError, match="restored state"):
        run(config, state, {})
    row = filing(1)
    row["first_seen_utc"] = row["filed_date"] = "invalid"
    state, index = baseline(config, [row])
    state.seen_filings["house"][row["report_id"]] = "invalid"
    _, metrics, _ = run(config, state, index)
    assert metrics["blocked_filing_counts"] == {"invalid_public_date": 1}
    assert metrics["transactions_appended"] == 0
    assert not config.transactions_path.exists()
    with pytest.raises(tracker.MonitorError, match="acknowledged terms"):
        run(replace(config, terms_acknowledged=False), state, index)


def test_configuration_budget_is_separate_and_can_be_disabled(monkeypatch):
    monkeypatch.setenv("HISTORICAL_FILING_BACKFILL_LIMIT_PER_RUN", "7")
    parser = tracker.build_parser()
    assert tracker.build_config(parser.parse_args(["--branch", "legislative"])).historical_filing_backfill_limit_per_run == 7
    assert tracker.build_config(parser.parse_args(["--branch", "executive", "--historical-filing-backfill-limit-per-run", "0"])).historical_filing_backfill_limit_per_run == 0


def test_normal_successful_tracker_runs_maintain_history_with_no_new_filings(tmp_path, monkeypatch):
    config = replace(config_at(tmp_path), legislative_source="house", run_history_path=tmp_path / "runs.jsonl",
                     result_path=tmp_path / "result.json", latest_csv_path=tmp_path / "purchases.csv",
                     latest_transactions_csv_path=tmp_path / "transactions.csv", latest_filings_csv_path=tmp_path / "filings.csv")
    row = filing(1)
    state, index = baseline(config, [row])
    report = bootstrap._report(row)
    original_seen_filings = copy.deepcopy(state.seen_filings)
    monkeypatch.setattr(tracker, "fetch_house_reports", lambda *args, **kwargs: [report])
    scanner = Mock(return_value=([trade_for(report)], None))
    monkeypatch.setattr(tracker, "scan_house_report", scanner)
    notifier = Mock(side_effect=AssertionError("Historical maintenance must never alert"))
    monkeypatch.setattr(tracker, "send_filing_notification", notifier)
    monkeypatch.setattr(tracker, "send_pending_notification", notifier)
    session = Mock()
    session.get.side_effect = AssertionError("Unexpected network")
    first = tracker.run_tracker(config, session)
    second = tracker.run_tracker(config, session)
    assert first.success and second.success
    assert first.new_filing_counts == second.new_filing_counts == {"house": 0}
    assert first.historical_backfill["completed_this_run"] == 1
    assert second.historical_backfill["completed_this_run"] == 0
    assert scanner.call_count == 1 and notifier.call_count == session.get.call_count == 0
    persisted, is_new = tracker.load_state(config.state_path)
    assert not is_new and persisted.seen_filings == original_seen_filings
    assert len(tracker.read_jsonl(config.transactions_path)) == 1
    assert tracker.read_jsonl(config.run_history_path)[0]["historical_backfill"]["completed_this_run"] == 1
