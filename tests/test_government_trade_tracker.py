from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from requests import Response, Session
from requests.cookies import RequestsCookieJar

from scripts import government_trade_tracker as tracker
from scripts.government_trade_tracker import (
    PaperFilingError,
    TrackerConfig,
    TrackerResult,
    TrackerState,
    _senate_pdf_from_viewer,
    catalog_visible_filings,
    commit_filing_outcome,
    is_equity_like,
    load_state,
    make_trade,
    parse_generic_transactions_text,
    parse_house_transactions,
    parse_senate_html_transactions,
    purchases_only,
    save_state,
    should_baseline_source,
    write_latest_csv,
)
from scripts.monitor_disclosures import MonitorError, Report, normalize_text


def house_report(doc_id: str = "20035289") -> Report:
    return Report(
        report_id=f"house:2026:{doc_id}",
        source="house",
        filer="Hon. David J. Taylor",
        filed_date="08/20/2026",
        url=f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/{doc_id}.pdf",
        format="pdf",
        metadata={"document_id": doc_id, "district": "OH02"},
    )


def test_parse_house_electronic_ptr_extracts_all_rows_and_purchases() -> None:
    text = """
    P T R
    Name: Hon. David J. Taylor
    Status: Member
    State/District: OH02
    T
    ID Owner Asset Transaction
    Type
    Date Notification
    Date
    Amount Cap.
    Gains >
    $200?
    Alphabet Inc. - Class A Common
    Stock (GOOGL) [ST]
    P 08/11/2026 08/20/2026 $1,001 - $15,000
    F S: New
    S O: David Taylor Trust > Sardinia Ready Mix 401(k) - Dave
    Alphabet Inc. - Class A Common
    Stock (GOOGL) [ST]
    P 08/11/2026 08/20/2026 $1,001 - $15,000
    F S: New
    S O: David Taylor Trust > Schwab Joint Brokerage #1 (Home Grown)
    Installed Building Products, Inc.
    Common Stock (IBP) [ST]
    P 08/14/2026 08/20/2026 $1,001 - $15,000
    F S: New
    S O: David Taylor Trust > Schwab Joint Brokerage #1 (Home Grown)
    Microsoft Corporation - Common
    Stock (MSFT) [ST]
    S 08/11/2026 08/20/2026 $15,001 -
    $50,000
    F S: New
    S O: David Taylor Trust > Sardinia Ready Mix 401(k) - Dave
    Procter & Gamble Company (PG) [ST] P 08/11/2026 08/20/2026 $1,001 - $15,000
    F S: New
    S O: David Taylor Trust > Sardinia Ready Mix 401(k) - Dave
    * For the complete list of asset type abbreviations
    Investment Vehicle Details
    """
    trades = parse_house_transactions(text, house_report())
    assert len(trades) == 5
    purchases = purchases_only(trades)
    assert len(purchases) == 4
    assert [trade.ticker for trade in purchases] == ["GOOGL", "GOOGL", "IBP", "PG"]
    assert all(trade.asset_type == "ST" for trade in purchases)
    assert all(trade.equity_like for trade in purchases)
    assert trades[3].transaction_type == "Sale"
    assert trades[3].amount == "$15,001 - $50,000"



def test_parse_house_partial_sale_with_house_pdf_control_chars() -> None:
    text = """
    P\x00\x00 T\x00 R
    Name: Hon. Michael Rulli
    Status: Member
    State/District: OH06
    ID Owner Asset Transaction
    Type
    Date Notification
    Date
    Amount Cap.
    Gains >
    $200?
    Alphabet Inc. - Class A Common
    Stock (GOOGL) [ST]
    S (partial) 08/24/2026 08/24/2026 $50,001 -
    $100,000
    F S: New
    S O: Merrill Lynch Roth IRA
    * For the complete list of asset type abbreviations
    """
    report = replace(
        house_report("20035309"),
        filer="Hon. Michael Rulli",
        filed_date="08/25/2026",
    )

    assert "\x00" not in normalize_text(text)

    trades = parse_house_transactions(text, report)
    assert len(trades) == 1

    trade = trades[0]
    assert trade.ticker == "GOOGL"
    assert trade.asset_type == "ST"
    assert trade.transaction_type == "Sale (Partial)"
    assert trade.transaction_date == "2026-08-24"
    assert trade.notification_date == "2026-08-24"
    assert trade.amount == "$50,001 - $100,000"
    assert trade.equity_like is True



def test_house_partial_sale_with_interleaved_asset_suffix() -> None:
    text = """
    P T R
    Name: Hon. Michael Rulli
    Status: Member
    State/District: OH06
    ID Owner Asset Transaction
    Type
    Date Notification
    Date
    Amount Cap.
    Gains >
    $200?
    Alphabet Inc. - Class A Common
    S (partial) 08/24/2026 08/24/2026 $50,001 -
    Stock (GOOGL) [ST]
    $100,000
    F S: New
    S O: Merrill Lynch Roth IRA
    * For the complete list of asset type abbreviations
    """

    report = replace(
        house_report("20035309"),
        filer="Hon. Michael Rulli",
        filed_date="08/25/2026",
    )

    trades = parse_house_transactions(text, report)
    assert len(trades) == 1

    trade = trades[0]
    assert trade.ticker == "GOOGL"
    assert trade.asset_type == "ST"
    assert trade.transaction_type == "Sale (Partial)"
    assert trade.transaction_date == "2026-08-24"
    assert trade.notification_date == "2026-08-24"
    assert trade.amount == "$50,001 - $100,000"
    assert "Stock (GOOGL) [ST]" in trade.asset


def test_parse_house_owner_and_wrapped_asset() -> None:
    text = """
    Transactions
    ID Owner Asset Transaction Type Date Notification Date Amount Cap. Gains > $200?
    SP Advanced Micro Devices, Inc. (AMD)
    [ST]
    P 07/14/2026 08/17/2026 $1,001 - $15,000
    Filing Status: New
    Subholding Of: LIVTR
    * For the complete list of asset type abbreviations
    """
    trade = parse_house_transactions(text, house_report("20035260"))[0]
    assert trade.owner == "Spouse"
    assert trade.ticker == "AMD"
    assert trade.transaction_date == "2026-07-14"
    assert trade.filed_date == "2026-08-20"


def test_house_paper_form_is_routed_to_review() -> None:
    text = """
    UNITED STATES HOUSE OF REPRESENTATIVES
    Periodic Transaction Report
    TYPE OF TRANSACTION
    DATE OF TRANSACTION
    AMOUNT OF TRANSACTION
    Provide full name not ticker symbol
    """
    with pytest.raises(PaperFilingError):
        parse_house_transactions(text, house_report("9116308"))


def test_parse_senate_electronic_html() -> None:
    html = """
    <html><body><table>
      <thead><tr>
        <th>#</th><th>Transaction Date</th><th>Owner</th><th>Ticker</th>
        <th>Asset Name</th><th>Asset Type</th><th>Type</th><th>Amount</th><th>Comment</th>
      </tr></thead>
      <tbody>
        <tr><td>1</td><td>07/30/2026</td><td>Joint</td><td>PYPL</td>
          <td>PayPal Holdings Inc.</td><td>Stock</td><td>Purchase</td>
          <td>$1,001 - $15,000</td><td>--</td></tr>
        <tr><td>2</td><td>07/31/2026</td><td>Joint</td><td>CBOE</td>
          <td>Cboe Global Markets Inc.</td><td>Stock</td><td>Sale</td>
          <td>$1,001 - $15,000</td><td></td></tr>
      </tbody>
    </table></body></html>
    """
    report = Report(
        report_id="senate:https://efdsearch.senate.gov/search/view/ptr/example/",
        source="senate",
        filer="John Boozman",
        filed_date="08/17/2026",
        url="https://efdsearch.senate.gov/search/view/ptr/example/",
        format="html",
        metadata={},
    )
    trades = parse_senate_html_transactions(html, report)
    assert len(trades) == 2
    purchase = purchases_only(trades)[0]
    assert purchase.ticker == "PYPL"
    assert purchase.owner == "Joint"
    assert purchase.asset_type == "Stock"
    assert purchase.equity_like is True



def test_senate_page_image_viewer_routes_to_manual_review(tmp_path: Path) -> None:
    response = Response()
    response.status_code = 200
    response.url = (
        "https://efdsearch.senate.gov/search/view/paper/"
        "ec20cd93-6702-4a29-b3a6-983f4b17f365/"
    )
    response.headers["Content-Type"] = "text/html"
    response._content = b"""
        <html><body>
          <h1>Filing Document - Print View</h1>
          <div>Page 1 of 4</div>
          <div>Rotate (from original position)</div>
          <div>Printer-Friendly</div>
        </body></html>
    """

    config = _tracker_config(tmp_path, initialize=False)

    with pytest.raises(
        PaperFilingError,
        match="rendered as page images",
    ):
        _senate_pdf_from_viewer(
            object(),
            response,
            response.content,
            config,
        )


def test_parse_oge_style_text_keeps_purchase_only_filter_separate() -> None:
    listing = {
        "listing_id": "oge:sample",
        "date": "08/20/2026",
        "name": "Example Official",
        "title": "Secretary",
        "agency": "Example Department",
        "document_url": "https://www.oge.gov/example.pdf",
    }
    text = """
    OGE Form 278-T Periodic Transaction Report
    Name: Example Official
    Position: Secretary
    Agency: Example Department
    Description Type Date Notification Received Over 30 Days Ago Amount
    Chevron Corp. (CVX) Sale 7/15/2026 No $15,001 - $50,000
    Exxon Mobil Corp. (XOM) Purchase 6/10/2026 Yes $15,001 - $50,000
    Comments of Reviewing Officials
    """
    trades = parse_generic_transactions_text(
        text,
        listing,
        branch="executive",
        source="oge",
        paper_is_pending=False,
    )
    assert len(trades) == 2
    purchase = purchases_only(trades)[0]
    assert purchase.ticker == "XOM"
    assert purchase.filer == "Example Official"
    assert purchase.agency == "Example Department"
    assert purchase.transaction_date == "2026-06-10"


def test_state_round_trip_and_latest_csv(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    ledger_path = tmp_path / "purchases.jsonl"
    csv_path = tmp_path / "latest.csv"
    state = TrackerState()
    state.mark_filing_seen("house", "house:1", "2026-08-25T10:00:00Z")
    state.seen_trades["trade:1"] = "2026-08-25T10:00:00Z"
    save_state(state_path, state)
    loaded, is_new = load_state(state_path)
    assert is_new is False
    assert loaded.is_filing_seen("house", "house:1")
    assert loaded.seen_trades["trade:1"] == "2026-08-25T10:00:00Z"

    report = house_report()
    trade = make_trade(
        branch="legislative",
        source="house",
        report=report,
        owner="SP",
        asset="Advanced Micro Devices, Inc. (AMD) [ST]",
        ticker="",
        asset_type="ST",
        transaction_type="P",
        transaction_date="07/14/2026",
        notification_date="08/17/2026",
        amount="$1,001 - $15,000",
        raw_row="sample",
        confidence="high",
    )
    ledger_path.write_text(json.dumps(trade.__dict__) + "\n", encoding="utf-8")
    write_latest_csv(ledger_path, csv_path)
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "trade_id" in csv_text
    assert "AMD" in csv_text


def _tracker_config(tmp_path: Path, *, initialize: bool, bootstrap: bool = False) -> TrackerConfig:
    return TrackerConfig(
        branch="executive",
        legislative_source="all",
        state_path=tmp_path / "state.json",
        ledger_path=tmp_path / "purchases.jsonl",
        transactions_path=tmp_path / "transactions.jsonl",
        filings_path=tmp_path / "filings.jsonl",
        run_history_path=tmp_path / "runs.jsonl",
        pending_path=tmp_path / "pending.jsonl",
        result_path=tmp_path / "result.json",
        latest_csv_path=tmp_path / "latest.csv",
        latest_transactions_csv_path=tmp_path / "latest-transactions.csv",
        latest_filings_csv_path=tmp_path / "latest-filings.csv",
        oge_listings_path=tmp_path / "oge.json",
        bootstrap_alerts=bootstrap,
        no_notify=True,
        senate_lookback_days=180,
        max_download_bytes=10_000_000,
        max_ocr_pages=10,
        user_agent="test",
        pushover_api_token="",
        pushover_user_key="",
        require_pushover=False,
        notify_equity_only=True,
        notify_pending_reviews=True,
        notify_all_filings=True,
        watchlist=(),
        allow_empty_sources=False,
        allow_state_initialization=initialize,
        terms_acknowledged=True,
    )


def test_incomplete_existing_state_cannot_silently_baseline_source(tmp_path: Path) -> None:
    state = TrackerState()
    config = _tracker_config(tmp_path, initialize=False)
    with pytest.raises(MonitorError, match="no durable baseline"):
        should_baseline_source(state, "oge", config)

    authorized = replace(config, allow_state_initialization=True)
    assert should_baseline_source(state, "oge", authorized) is True

    explicit_historical_scan = replace(config, bootstrap_alerts=True)
    assert should_baseline_source(state, "oge", explicit_historical_scan) is False


def test_mutual_fund_ticker_is_not_classified_as_stock_like() -> None:
    assert is_equity_like("Vanguard 500 Index Fund (VFIAX)", "Mutual Fund", "VFIAX") is False
    assert is_equity_like("Vanguard S&P 500 ETF (VOO)", "ETF", "VOO") is True


def test_seen_baseline_is_cataloged_for_dashboard_without_being_reprocessed(tmp_path: Path) -> None:
    config = _tracker_config(tmp_path, initialize=False)
    config = replace(config, branch="legislative")
    state = TrackerState()
    report = house_report("20039999")
    state.mark_filing_seen("house", report.report_id, "2026-08-25T10:00:00Z")
    result = TrackerResult(branch="legislative", started_utc="2026-08-26T10:00:00Z")
    index: dict[str, dict[str, object]] = {}

    catalog_visible_filings(
        config=config,
        state=state,
        result=result,
        source="house",
        reports=[report],
        filing_index=index,
        treat_unseen_as_new=True,
    )

    rows = [json.loads(line) for line in config.filings_path.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["status"] == "cataloged"
    assert rows[0]["filer"] == "Hon. David J. Taylor"
    assert rows[0]["source_url"].endswith("20039999.pdf")
    assert result.filings == []
    assert result.cataloged_filing_counts == {"house": 1}


def test_commit_records_all_transactions_but_purchase_ledger_stays_purchase_only(tmp_path: Path) -> None:
    config = replace(_tracker_config(tmp_path, initialize=True), branch="legislative")
    state = TrackerState()
    report = house_report("20040000")
    state.mark_filing_seen("house", "house:prior", "2026-08-25T10:00:00Z")
    result = TrackerResult(branch="legislative", started_utc="2026-08-26T10:00:00Z")
    result.transaction_counts["house"] = 0
    result.purchase_counts["house"] = 0
    result.pending_review_counts["house"] = 0
    result.alerted_filing_counts["house"] = 0

    purchase = make_trade(
        branch="legislative",
        source="house",
        report=report,
        owner="SELF",
        asset="NVIDIA Corporation (NVDA) [ST]",
        ticker="",
        asset_type="ST",
        transaction_type="P",
        transaction_date="08/20/2026",
        notification_date="08/25/2026",
        amount="$1,001 - $15,000",
        raw_row="purchase",
        confidence="high",
    )
    sale = make_trade(
        branch="legislative",
        source="house",
        report=report,
        owner="SP",
        asset="Microsoft Corporation (MSFT) [ST]",
        ticker="",
        asset_type="ST",
        transaction_type="S",
        transaction_date="08/20/2026",
        notification_date="08/25/2026",
        amount="$15,001 - $50,000",
        raw_row="sale",
        confidence="high",
    )

    commit_filing_outcome(
        session=object(),  # no network use because --no-notify semantics are active
        config=config,
        state=state,
        result=result,
        source="house",
        filing=report,
        filing_id=report.report_id,
        filing_label="House PTR",
        trades=[purchase, sale],
        review=None,
        filing_index={},
    )

    transactions = [json.loads(line) for line in config.transactions_path.read_text().splitlines()]
    purchases = [json.loads(line) for line in config.ledger_path.read_text().splitlines()]
    filings = [json.loads(line) for line in config.filings_path.read_text().splitlines()]
    assert {row["transaction_type"] for row in transactions} == {"Purchase", "Sale"}
    assert [row["transaction_type"] for row in purchases] == ["Purchase"]
    assert filings[-1]["status"] == "processed"
    assert filings[-1]["transaction_count"] == 2
    assert filings[-1]["purchase_count"] == 1
    assert filings[-1]["sale_count"] == 1
    assert result.transaction_counts["house"] == 2
    assert result.purchase_counts["house"] == 1

def test_parse_house_morrison_spinoff_tickers_and_owners() -> None:
    text = """
    Transactions
    SP Accenture plc Class A Ordinary
    Shares (ACN) [ST]
    S 08/11/2026 08/11/2026 $1,001 - $15,000
    F S: New
    S O: Trust 2
    Accenture plc Class A Ordinary
    Shares (ACN) [ST]
    S 08/11/2026 08/11/2026 $1,001 - $15,000
    F S: New
    S O: Trust 1
    SP Accenture plc Class A Ordinary
    Shares (ACN) [ST]
    S 08/11/2026 08/11/2026 $15,001 -
    $50,000
    F S: New
    S O: Trust 8
    SP Mobility Global Inc. Common Stock
    (MBGL) [ST]
    S 08/11/2026 08/11/2026 $1,001 - $15,000
    F S: New
    S O: Trust 8
    D: Asset acquired through a S&P Global (SPGI) spinoff.
    SP Mobility Global Inc. Common Stock
    (MBGL) [ST]
    S 08/11/2026 08/11/2026 $1,001 - $15,000
    F S: New
    S O: Trust 2
    D: Asset acquired through a S&P Global (SPGI) spinoff.
    Mobility Global Inc. Common Stock
    (MBGL) [ST]
    S 08/11/2026 08/11/2026 $1,001 - $15,000
    F S: New
    S O: Trust 1
    D: Asset acquired through a S&P Global (SPGI) spinoff.
    SP Solstice Advanced Materials Inc. -
    Common Stock (SOLS) [ST]
    S 08/11/2026 08/11/2026 $1,001 - $15,000
    * For the complete list of asset type abbreviations
    """

    trades = parse_house_transactions(text, house_report("20035244"))

    assert [(t.ticker, t.owner) for t in trades] == [
        ("ACN", "Spouse"),
        ("ACN", "Self"),
        ("ACN", "Spouse"),
        ("MBGL", "Spouse"),
        ("MBGL", "Spouse"),
        ("MBGL", "Self"),
        ("SOLS", "Spouse"),
    ]
    assert trades[2].amount == "$15,001 - $50,000"
    assert "SPGI" not in {t.ticker for t in trades}
    assert all(t.asset_type == "ST" for t in trades)

def test_house_pdfplumber_transaction_before_asset_continuation() -> None:
    text = """
    Transactions
    SP Accenture plc Class A Ordinary S 08/11/2026 08/11/2026 $15,001 -
    Shares (ACN) [ST] $50,000
    F S : New
    S O : Trust 8
    SP Mobility Global Inc. Common Stock S 08/11/2026 08/11/2026 $1,001 - $15,000
    (MBGL) [ST]
    F S : New
    S O : Trust 8
    D : Asset acquired through a S&P Global (SPGI) spinoff.
    SP Solstice Advanced Materials Inc. - S 08/11/2026 08/11/2026 $1,001 - $15,000
    Common Stock (SOLS) [ST]
    F S : New
    S O : Trust 2
    * For the complete list of asset type abbreviations
    """

    trades = parse_house_transactions(text, house_report("20035244"))

    assert [(t.ticker, t.owner, t.amount) for t in trades] == [
        ("ACN", "Spouse", "$15,001 - $50,000"),
        ("MBGL", "Spouse", "$1,001 - $15,000"),
        ("SOLS", "Spouse", "$1,001 - $15,000"),
    ]
    assert all("SPGI" not in t.asset for t in trades)

def test_house_preserves_identical_transactions_from_separate_accounts() -> None:
    text = """
    Transactions
    SP Mobility Global Inc. Common Stock S 08/11/2026 08/11/2026 $1,001 - $15,000
    (MBGL) [ST]
    F S : New
    S O : Trust 8
    D : Asset acquired through a S&P Global (SPGI) spinoff.
    SP Mobility Global Inc. Common Stock S 08/11/2026 08/11/2026 $1,001 - $15,000
    (MBGL) [ST]
    F S : New
    S O : Trust 2
    D : Asset acquired through a S&P Global (SPGI) spinoff.
    * For the complete list of asset type abbreviations
    """

    trades = parse_house_transactions(text, house_report("20035244"))

    assert len(trades) == 2
    assert [t.ticker for t in trades] == ["MBGL", "MBGL"]
    assert [t.owner for t in trades] == ["Spouse", "Spouse"]
    assert len({t.trade_id for t in trades}) == 2


def senate_report() -> Report:
    url = "https://efdsearch.senate.gov/search/view/ptr/deterministic-fixture/"
    return Report(
        report_id=f"senate:{url}", source="senate", filer="TEST Senate Filer",
        filed_date="08/20/2026", url=url, format="html", metadata={},
    )


def _legislative_fixture(tmp_path: Path) -> tuple[TrackerConfig, dict[str, bytes]]:
    protected = tmp_path / "protected"
    output = tmp_path / "output"
    config = replace(
        _tracker_config(protected, initialize=False),
        branch="legislative", no_notify=False,
        result_path=output / "result.json",
        latest_csv_path=output / "purchases.csv",
        latest_transactions_csv_path=output / "transactions.csv",
        latest_filings_csv_path=output / "filings.csv",
    )
    state = TrackerState(
        seen_filings={"house": {"house:prior": "old"}, "senate": {"senate:prior": "old"}},
        seen_trades={"retained:trade": "old"}, seen_reviews={"retained:review": "old"},
        last_attempt_utc="2026-08-20T00:00:00Z", last_success_utc="2026-08-20T00:00:00Z",
        last_counts={"house": 883, "senate": 91},
    )
    save_state(config.state_path, state)
    for path, record in (
        (config.ledger_path, {"trade_id": "retained:trade", "source": "house"}),
        (config.transactions_path, {"trade_id": "retained:trade", "source": "house"}),
        (config.filings_path, {"filing_key": "retained:filing", "status": "processed"}),
        (config.pending_path, {"review_id": "retained:review"}),
        (config.run_history_path, {"run_key": "prior:1", "success": True}),
    ):
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return config, _protected_bytes(protected)


def _protected_bytes(directory: Path) -> dict[str, bytes]:
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def _forbid_discovery_side_effects(monkeypatch: pytest.MonkeyPatch) -> dict[str, Mock]:
    methods = (
        "scan_house_report", "scan_senate_report", "send_filing_notification",
        "send_purchase_notification", "send_pending_notification", "_pushover_post",
        "_baseline_source", "catalog_visible_filings", "commit_filing_outcome",
        "save_state", "append_run_history",
    )
    spies = {}
    for method in methods:
        spies[method] = Mock(side_effect=AssertionError(f"{method} before discovery completed"))
        monkeypatch.setattr(tracker, method, spies[method])
    return spies


def test_terminal_senate_failure_preserves_all_protected_bytes_and_outputs_degraded_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, before = _legislative_fixture(tmp_path)
    senate_client = Mock()
    monkeypatch.setattr(tracker, "SenateClient", lambda: senate_client)
    monkeypatch.setattr(tracker, "fetch_house_reports", Mock(return_value=[house_report()]))
    monkeypatch.setattr(
        tracker, "fetch_senate_reports",
        Mock(side_effect=MonitorError("sessionid=PRIVATE csrfmiddlewaretoken=MASKED Cookie=COOKIE")),
    )
    spies = _forbid_discovery_side_effects(monkeypatch)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    with pytest.raises(MonitorError):
        tracker.run_tracker(config, session=Mock())
    assert _protected_bytes(config.state_path.parent) == before
    for spy in spies.values():
        spy.assert_not_called()
    senate_client.close.assert_called_once_with()
    result_text = config.result_path.read_text(encoding="utf-8")
    result = json.loads(result_text)
    assert result["source_statuses"] == {"house": "ok", "senate": "error"}
    assert result["overall_status"] == "degraded"
    assert result["success"] is False
    assert result["discovery_complete"] is False
    assert result["source_counts"] == {"house": 1}
    assert result["new_filing_counts"] == result["baseline_counts"] == {}
    assert result["errors"] == ["MonitorError: required discovery incomplete"]
    assert not any(secret in result_text for secret in ("PRIVATE", "MASKED", "COOKIE"))
    assert "Senate | error | Unavailable" in summary.read_text(encoding="utf-8")
    assert config.latest_csv_path.exists() and config.latest_transactions_csv_path.exists()
    assert config.latest_filings_csv_path.exists()


@pytest.mark.parametrize("bad_catalog", [None, {}, "<html>Access denied</html>", [], [house_report()]])
def test_invalid_senate_catalog_is_not_an_empty_success_or_partial_house_run(
    bad_catalog: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, before = _legislative_fixture(tmp_path)
    monkeypatch.setattr(tracker, "SenateClient", Mock())
    monkeypatch.setattr(tracker, "fetch_house_reports", Mock(return_value=[house_report()]))
    monkeypatch.setattr(tracker, "fetch_senate_reports", Mock(return_value=bad_catalog))
    spies = _forbid_discovery_side_effects(monkeypatch)
    with pytest.raises(tracker.SourceChangedError):
        tracker.run_tracker(config, session=Mock())
    assert _protected_bytes(config.state_path.parent) == before
    for spy in spies.values():
        spy.assert_not_called()
    result = json.loads(config.result_path.read_text(encoding="utf-8"))
    assert result["source_statuses"] == {"house": "ok", "senate": "error"}
    assert "senate" not in result["source_counts"]
    assert result["success"] is False


def test_missing_senate_baseline_prevents_all_house_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _before = _legislative_fixture(tmp_path)
    state, _ = load_state(config.state_path)
    state.seen_filings["senate"] = {}
    save_state(config.state_path, state)
    before = _protected_bytes(config.state_path.parent)
    monkeypatch.setattr(tracker, "SenateClient", Mock())
    monkeypatch.setattr(tracker, "fetch_house_reports", Mock(return_value=[house_report()]))
    monkeypatch.setattr(tracker, "fetch_senate_reports", Mock(return_value=[senate_report()]))
    spies = _forbid_discovery_side_effects(monkeypatch)
    with pytest.raises(MonitorError, match="no durable baseline"):
        tracker.run_tracker(config, session=Mock())
    assert _protected_bytes(config.state_path.parent) == before
    for spy in spies.values():
        spy.assert_not_called()


def test_discovery_failure_does_not_mutate_in_memory_state_or_initialize_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(_tracker_config(tmp_path, initialize=True), branch="legislative")
    state = TrackerState()
    before = asdict(state)
    result = TrackerResult(branch="legislative", started_utc="2026-08-30T00:00:00Z")
    filing_index: dict[str, dict] = {}
    monkeypatch.setattr(tracker, "SenateClient", Mock())
    monkeypatch.setattr(tracker, "fetch_house_reports", Mock(return_value=[house_report()]))
    monkeypatch.setattr(tracker, "fetch_senate_reports", Mock(side_effect=MonitorError("blocked")))
    spies = _forbid_discovery_side_effects(monkeypatch)
    with pytest.raises(MonitorError):
        tracker.run_legislative(config, state, result, Mock(), filing_index)
    assert asdict(state) == before
    assert filing_index == {}
    assert not config.state_path.exists()
    for spy in spies.values():
        spy.assert_not_called()


def test_both_catalogs_precede_processing_and_repeated_filings_do_not_alert_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _legislative_fixture(tmp_path)
    house = house_report()
    senate = senate_report()
    events = []
    senate_clients = [Mock(), Mock()]
    monkeypatch.setattr(tracker, "SenateClient", Mock(side_effect=senate_clients))
    def house_catalog(*args, **kwargs):
        events.append("house discovery")
        return [house]
    def senate_catalog(*args, **kwargs):
        events.append("senate discovery")
        return [senate]
    monkeypatch.setattr(tracker, "fetch_house_reports", house_catalog)
    monkeypatch.setattr(tracker, "fetch_senate_reports", senate_catalog)
    purchase = make_trade(
        branch="legislative", source="house", report=house, owner="SELF",
        asset="TEST Example Stock (TEST)", ticker="TEST", asset_type="ST",
        transaction_type="P", transaction_date="08/20/2026",
        notification_date="08/20/2026", amount="$1,001 - $15,000",
        raw_row="deterministic TEST fixture", confidence="high",
    )
    def house_scan(*args):
        assert events[:2] == ["house discovery", "senate discovery"]
        events.append("house scan")
        return [purchase], None
    house_scanner = Mock(side_effect=house_scan)
    senate_scanner = Mock(return_value=([], None))
    notifier = Mock(return_value=True)
    monkeypatch.setattr(tracker, "scan_house_report", house_scanner)
    monkeypatch.setattr(tracker, "scan_senate_report", senate_scanner)
    monkeypatch.setattr(tracker, "send_filing_notification", notifier)
    notification_session = Mock()
    first = tracker.run_tracker(config, session=notification_session)
    preserved = {path: path.read_bytes() for path in (config.ledger_path, config.transactions_path, config.pending_path)}
    second = tracker.run_tracker(config, session=notification_session)
    assert first.success and second.success
    assert first.discovery_complete and second.discovery_complete
    assert first.source_statuses == second.source_statuses == {"house": "ok", "senate": "ok"}
    assert first.overall_status == second.overall_status == "ok"
    assert first.alerted_filing_counts == {"house": 1, "senate": 0}
    assert second.new_filing_counts == second.alerted_filing_counts == {"house": 0, "senate": 0}
    house_scanner.assert_called_once_with(notification_session, house, config)
    senate_scanner.assert_called_once_with(senate_clients[0], senate, config)
    notifier.assert_called_once_with(notification_session, config, "House PTR", [purchase])
    assert {path: path.read_bytes() for path in preserved} == preserved
    for client in senate_clients:
        client.close.assert_called_once_with()
    final_state, _ = load_state(config.state_path)
    assert final_state.is_filing_seen("house", house.report_id)
    assert final_state.is_filing_seen("senate", senate.report_id)
    assert "retained:trade" in final_state.seen_trades
    assert purchase.trade_id in final_state.seen_trades
    assert final_state.seen_reviews == {"retained:review": "old"}


def test_senate_linked_pdf_uses_the_same_authenticated_client(tmp_path: Path) -> None:
    viewer = Response()
    viewer.status_code = 200
    viewer.url = "https://efdsearch.senate.gov/search/view/paper/test/"
    viewer.headers["Content-Type"] = "text/html"
    viewer._content = b'<html><a href="/search/view/paper/test/download.pdf">PDF</a></html>'
    pdf = Response()
    pdf.status_code = 200
    pdf.url = "https://efdsearch.senate.gov/search/view/paper/test/download.pdf"
    pdf.headers["Content-Type"] = "application/pdf"
    pdf._content = b"%PDF-TEST mocked bytes"
    retained_client = Mock()
    retained_client.get.return_value = pdf
    contents, url = _senate_pdf_from_viewer(
        retained_client, viewer, viewer.content, _tracker_config(tmp_path, initialize=False),
    )
    assert contents == pdf.content and url == pdf.url
    retained_client.get.assert_called_once_with(pdf.url, timeout=tracker.DEFAULT_TIMEOUT)


def test_three_landing_403s_exit_nonzero_without_state_changes_or_notifications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    config, before = _legislative_fixture(tmp_path)
    sessions = []
    for _ in range(3):
        response = Response()
        response.status_code = 403
        response.url = "https://efdsearch.senate.gov/search/home/"
        response.headers.update({"Content-Type": "text/html", "Set-Cookie": "sessionid=PRIVATE_SESSION"})
        response._content = (
            b'<html><h1>Access denied</h1><input type="hidden" name="csrfmiddlewaretoken" '
            b'value="PRIVATE_CSRF"><div>Cookie: PRIVATE_COOKIE</div></html>'
        )
        session = Mock(spec=Session)
        session.headers = {}
        session.cookies = RequestsCookieJar()
        session.cookies.set("sessionid", "PRIVATE_SESSION")
        session.get.return_value = response
        sessions.append(session)
    factory = Mock(side_effect=sessions)
    sleep = Mock()
    real_client = tracker.SenateClient(session_factory=factory, sleep=sleep, random=lambda: 0)
    monkeypatch.setattr(tracker, "SenateClient", lambda: real_client)
    monkeypatch.setattr(tracker, "fetch_house_reports", Mock(return_value=[house_report()]))
    monkeypatch.setattr(tracker, "build_config", lambda _args: config)
    monkeypatch.setattr(tracker, "build_session", Mock(return_value=Mock(spec=Session)))
    spies = _forbid_discovery_side_effects(monkeypatch)
    assert tracker.main(["--branch", "legislative"]) == 1
    assert factory.call_count == 3
    assert sleep.call_count == 2
    for session in sessions:
        session.get.assert_called_once()
        session.post.assert_not_called()
        session.close.assert_called_once()
    for spy in spies.values():
        spy.assert_not_called()
    assert _protected_bytes(config.state_path.parent) == before
    result_text = config.result_path.read_text(encoding="utf-8")
    result = json.loads(result_text)
    assert result["success"] is False and result["overall_status"] == "degraded"
    assert result["source_statuses"] == {"house": "ok", "senate": "blocked"}
    assert result["source_counts"] == {"house": 1}
    assert result["errors"] == ["SenateAccessDenied: required discovery incomplete"]
    for secret in ("PRIVATE_SESSION", "PRIVATE_CSRF", "PRIVATE_COOKIE"):
        assert secret not in result_text
        assert secret not in caplog.text


@pytest.mark.parametrize("scenario", ["table", "viewer", "pdf_content_type", "parser_error"])
def test_senate_report_failures_never_export_or_log_response_tokens(
    scenario: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    config, _ = _legislative_fixture(tmp_path)
    report = senate_report()
    response = Response()
    response.status_code = 200
    response.url = report.url
    response.headers["Content-Type"] = "text/html"
    # A table can satisfy the client's broad document check while containing no
    # transactions. Never print the surrounding response when parsing fails.
    response._content = (
        b'<html><h1>Filing</h1><table><tr><td>PRIVATE_COOKIE</td></tr></table>'
        b'<input type="hidden" name="csrfmiddlewaretoken" value="PRIVATE_CSRF">'
        b'<div>sessionid=PRIVATE_SESSION</div></html>'
    )
    if scenario == "viewer":
        report = replace(report, format="pdf")
    elif scenario == "pdf_content_type":
        response.headers["Content-Type"] = "application/pdf"
    elif scenario == "parser_error":
        response._content = b"%PDF-1.7\nPRIVATE_COOKIE PRIVATE_SESSION PRIVATE_CSRF"
        response.headers["Content-Type"] = "application/pdf"
        monkeypatch.setattr(
            tracker, "extract_pdf_text",
            Mock(side_effect=ValueError("PRIVATE_COOKIE PRIVATE_SESSION PRIVATE_CSRF")),
        )
    client = tracker.SenateClient()
    client.session = Mock(spec=Session)
    client.session.cookies = RequestsCookieJar()
    client.session.cookies.set("sessionid", "PRIVATE_SESSION")
    client.form_token = "PRIVATE_CSRF"
    monkeypatch.setattr(client, "get", Mock(return_value=response))
    monkeypatch.setattr(tracker, "SenateClient", lambda: client)
    monkeypatch.setattr(tracker, "fetch_house_reports", Mock(return_value=[house_report()]))
    monkeypatch.setattr(tracker, "fetch_senate_reports", Mock(return_value=[report]))
    monkeypatch.setattr(tracker, "scan_house_report", Mock(return_value=([], None)))
    monkeypatch.setattr(tracker, "build_config", lambda _args: config)
    monkeypatch.setattr(tracker, "build_session", Mock(return_value=Mock(spec=Session)))
    notifier = Mock(side_effect=AssertionError("notification from invalid report"))
    monkeypatch.setattr(tracker, "send_filing_notification", notifier)
    caplog.set_level("INFO")
    assert tracker.main(["--branch", "legislative"]) == 1
    result_text = config.result_path.read_text(encoding="utf-8")
    result = json.loads(result_text)
    assert result["discovery_complete"] is True
    assert result["success"] is False and result["overall_status"] == "degraded"
    assert result["errors"] == [
        "SenateInvalidResponse: senate_invalid_response: stage=report "
        "reason=invalid_report_content status=200 attempt=1"
    ]
    assert "Senate source failure" in caplog.text
    for secret in ("PRIVATE_SESSION", "PRIVATE_CSRF", "PRIVATE_COOKIE"):
        assert secret not in result_text
        assert secret not in caplog.text
    notifier.assert_not_called()


def test_senate_parser_and_pdf_viewer_raise_classified_errors_without_excerpts(tmp_path: Path) -> None:
    token = "PRIVATE_TOKEN_MUST_NEVER_APPEAR"
    html = f"<html><table><tr><td>{token}</td></tr></table></html>"
    with pytest.raises(tracker.SenateInvalidResponse) as parser_error:
        parse_senate_html_transactions(html, senate_report())
    assert token not in str(parser_error.value)
    response = Response()
    response.status_code = 200
    response.url = senate_report().url
    response.headers["Content-Type"] = "text/html"
    response._content = html.encode()
    with pytest.raises(tracker.SenateInvalidResponse) as viewer_error:
        _senate_pdf_from_viewer(Mock(), response, response.content, _tracker_config(tmp_path, initialize=False))
    assert token not in str(viewer_error.value)
