from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from requests import Response

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
