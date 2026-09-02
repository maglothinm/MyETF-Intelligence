#!/usr/bin/env python3
"""Track newly disclosed government purchases from official House, Senate, and OGE sources.

The tracker is intentionally fail-closed for electronic sources: a source schema change,
missing durable state, unreadable electronic report, or failed required notification exits
non-zero. Known paper filings are retained as manual-review records instead of being
silently discarded.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests import Response, Session

try:  # Support both ``python -m scripts...`` and direct script execution.
    from .run_trigger import trigger_source
    from .monitor_disclosures import (
        DEFAULT_MAX_DOWNLOAD_BYTES,
        DEFAULT_MAX_OCR_PAGES,
        DEFAULT_TIMEOUT,
        PUSHOVER_MESSAGES_URL,
        MonitorError,
        Report,
        SenateAccessDenied,
        SenateClient,
        SenateInvalidResponse,
        SourceChangedError,
        _senate_page_response,
        build_session,
        checked_response,
        extract_pdf_text,
        fetch_house_reports,
        fetch_pdf_bytes,
        fetch_senate_reports,
        normalize_text,
        parse_bool,
        response_bytes,
        utc_now,
    )
except ImportError:  # pragma: no cover - direct execution path
    from run_trigger import trigger_source
    from monitor_disclosures import (  # type: ignore
        DEFAULT_MAX_DOWNLOAD_BYTES,
        DEFAULT_MAX_OCR_PAGES,
        DEFAULT_TIMEOUT,
        PUSHOVER_MESSAGES_URL,
        MonitorError,
        Report,
        SenateAccessDenied,
        SenateClient,
        SenateInvalidResponse,
        SourceChangedError,
        _senate_page_response,
        build_session,
        checked_response,
        extract_pdf_text,
        fetch_house_reports,
        fetch_pdf_bytes,
        fetch_senate_reports,
        normalize_text,
        parse_bool,
        response_bytes,
        utc_now,
    )

LOGGER = logging.getLogger("government-trade-tracker")

STATE_VERSION = 1
DEFAULT_LEGISLATIVE_STATE = Path(".trade-tracker/legislative/state.json")
DEFAULT_EXECUTIVE_STATE = Path(".trade-tracker/executive/state.json")
DEFAULT_LEGISLATIVE_LEDGER = Path(".trade-tracker/legislative/purchases.jsonl")
DEFAULT_EXECUTIVE_LEDGER = Path(".trade-tracker/executive/purchases.jsonl")
DEFAULT_LEGISLATIVE_TRANSACTIONS = Path(".trade-tracker/legislative/transactions.jsonl")
DEFAULT_EXECUTIVE_TRANSACTIONS = Path(".trade-tracker/executive/transactions.jsonl")
DEFAULT_LEGISLATIVE_FILINGS = Path(".trade-tracker/legislative/filings.jsonl")
DEFAULT_EXECUTIVE_FILINGS = Path(".trade-tracker/executive/filings.jsonl")
DEFAULT_LEGISLATIVE_RUN_HISTORY = Path(".trade-tracker/legislative/runs.jsonl")
DEFAULT_EXECUTIVE_RUN_HISTORY = Path(".trade-tracker/executive/runs.jsonl")
DEFAULT_LEGISLATIVE_PENDING = Path(".trade-tracker/legislative/pending-review.jsonl")
DEFAULT_EXECUTIVE_PENDING = Path(".trade-tracker/executive/pending-review.jsonl")
DEFAULT_LEGISLATIVE_RESULT = Path("legislative-result.json")
DEFAULT_EXECUTIVE_RESULT = Path("executive-result.json")
DEFAULT_LEGISLATIVE_CSV = Path("legislative-latest-purchases.csv")
DEFAULT_EXECUTIVE_CSV = Path("executive-latest-purchases.csv")
DEFAULT_LEGISLATIVE_TRANSACTIONS_CSV = Path("legislative-latest-transactions.csv")
DEFAULT_EXECUTIVE_TRANSACTIONS_CSV = Path("executive-latest-transactions.csv")
DEFAULT_LEGISLATIVE_FILINGS_CSV = Path("legislative-latest-filings.csv")
DEFAULT_EXECUTIVE_FILINGS_CSV = Path("executive-latest-filings.csv")
DEFAULT_SENATE_LOOKBACK_DAYS = 180
DEFAULT_MAX_SEEN_FILINGS = 50_000
DEFAULT_MAX_SEEN_TRADES = 250_000
DEFAULT_LATEST_CSV_ROWS = 1_000

OWNER_LABELS = {
    "": "Self",
    "SELF": "Self",
    "SP": "Spouse",
    "SPOUSE": "Spouse",
    "JT": "Joint",
    "JOINT": "Joint",
    "DC": "Dependent Child",
    "DEPENDENT CHILD": "Dependent Child",
    "CHILD": "Dependent Child",
}

TRANSACTION_LABELS = {
    "P": "Purchase",
    "PURCHASE": "Purchase",
    "BUY": "Purchase",
    "S": "Sale",
    "S (FULL)": "Sale (Full)",
    "S (PARTIAL)": "Sale (Partial)",
    "SALE": "Sale",
    "SALE (FULL)": "Sale (Full)",
    "SALE (PARTIAL)": "Sale (Partial)",
    "E": "Exchange",
    "EXCHANGE": "Exchange",
}

HOUSE_TRANSACTION_RE = re.compile(
    r"(?<![A-Z0-9])(?P<type>P|E|S(?:\s*\((?:Full|Partial)\))?)\s+"
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"(?P<notification>\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"(?P<amount>(?:Over\s+)?\$[\d,]+(?:\.\d{2})?(?:\s*[-–—]\s*\$?[\d,]+(?:\.\d{2})?)?)",
    re.IGNORECASE,
)

GENERIC_TRANSACTION_RE = re.compile(
    r"(?P<type>Purchase|Sale(?:\s*\((?:Full|Partial)\))?|Exchange)\s+"
    r"(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\s+"
    r"(?:(?P<notice>Yes|No)\s+)?"
    r"(?P<amount>(?:Over\s+)?\$[\d,]+(?:\.\d{2})?(?:\s*[-–—]\s*\$?[\d,]+(?:\.\d{2})?)?)",
    re.IGNORECASE,
)

DATE_RE = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b")
AMOUNT_RE = re.compile(
    r"(?:Over\s+)?\$[\d,]+(?:\.\d{2})?(?:\s*[-–—]\s*\$?[\d,]+(?:\.\d{2})?)?",
    re.IGNORECASE,
)
TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,7})\)")
ASSET_CODE_RE = re.compile(r"\[([A-Z0-9]{2,5})\]\s*$", re.IGNORECASE)

EQUITY_CODES = {"ST", "OP", "SO", "RS", "RSU", "EF", "ETF"}
EQUITY_TYPE_TERMS = (
    "stock",
    "common equity",
    "preferred equity",
    "stock option",
    "exchange traded fund",
    "exchange-traded fund",
    "etf",
)
NON_EQUITY_TERMS = (
    "bond",
    "note",
    "treasury",
    "municipal",
    "certificate of deposit",
    "money market",
    "mutual fund",
    "index fund",
    "real estate",
    "limited partnership",
    "private equity fund",
    "venture fund",
)


class NotificationError(MonitorError):
    """Raised when a required purchase or review notification cannot be delivered."""


class PaperFilingError(MonitorError):
    """Raised for a known paper filing that requires a human review."""


@dataclass(frozen=True)
class Trade:
    trade_id: str
    observed_at_utc: str
    branch: str
    source: str
    report_id: str
    filer: str
    chamber: str
    title: str
    agency: str
    owner: str
    asset: str
    ticker: str
    asset_type: str
    transaction_type: str
    transaction_date: str
    notification_date: str
    filed_date: str
    amount: str
    source_url: str
    raw_row: str
    equity_like: bool
    parse_confidence: str


@dataclass(frozen=True)
class FilingRecord:
    filing_key: str
    first_seen_utc: str
    updated_at_utc: str
    branch: str
    source: str
    report_id: str
    filer: str
    filed_date: str
    source_url: str
    document_format: str
    chamber: str
    title: str
    agency: str
    district: str
    report_type: str
    access_mode: str
    status: str
    transaction_count: int
    purchase_count: int
    sale_count: int
    exchange_count: int
    review_reason: str


@dataclass(frozen=True)
class PendingReview:
    review_id: str
    observed_at_utc: str
    branch: str
    source: str
    report_id: str
    filer: str
    filed_date: str
    source_url: str
    reason: str
    title: str = ""
    agency: str = ""


@dataclass
class TrackerState:
    version: int = STATE_VERSION
    seen_filings: dict[str, dict[str, str]] = field(
        default_factory=lambda: {"house": {}, "senate": {}, "oge": {}}
    )
    seen_trades: dict[str, str] = field(default_factory=dict)
    seen_reviews: dict[str, str] = field(default_factory=dict)
    last_attempt_utc: str | None = None
    last_success_utc: str | None = None
    last_counts: dict[str, int] = field(default_factory=dict)

    def is_filing_seen(self, source: str, filing_id: str) -> bool:
        return filing_id in self.seen_filings.setdefault(source, {})

    def mark_filing_seen(self, source: str, filing_id: str, timestamp: str) -> None:
        self.seen_filings.setdefault(source, {})[filing_id] = timestamp

    def prune(self) -> None:
        for source, records in self.seen_filings.items():
            if len(records) > DEFAULT_MAX_SEEN_FILINGS:
                ordered = sorted(records.items(), key=lambda item: item[1], reverse=True)
                self.seen_filings[source] = dict(ordered[:DEFAULT_MAX_SEEN_FILINGS])
        if len(self.seen_trades) > DEFAULT_MAX_SEEN_TRADES:
            ordered = sorted(self.seen_trades.items(), key=lambda item: item[1], reverse=True)
            self.seen_trades = dict(ordered[:DEFAULT_MAX_SEEN_TRADES])
        if len(self.seen_reviews) > DEFAULT_MAX_SEEN_FILINGS:
            ordered = sorted(self.seen_reviews.items(), key=lambda item: item[1], reverse=True)
            self.seen_reviews = dict(ordered[:DEFAULT_MAX_SEEN_FILINGS])


@dataclass(frozen=True)
class TrackerConfig:
    branch: str
    legislative_source: str
    state_path: Path
    ledger_path: Path
    transactions_path: Path
    filings_path: Path
    run_history_path: Path
    pending_path: Path
    result_path: Path
    latest_csv_path: Path
    latest_transactions_csv_path: Path
    latest_filings_csv_path: Path
    oge_listings_path: Path | None
    bootstrap_alerts: bool
    no_notify: bool
    senate_lookback_days: int
    max_download_bytes: int
    max_ocr_pages: int
    user_agent: str
    pushover_api_token: str
    pushover_user_key: str
    require_pushover: bool
    notify_equity_only: bool
    notify_pending_reviews: bool
    notify_all_filings: bool
    watchlist: tuple[str, ...]
    allow_empty_sources: bool
    allow_state_initialization: bool
    terms_acknowledged: bool
    historical_filing_backfill_limit_per_run: int = 20
    historical_source_documents_manifest: Path | None = None


@dataclass
class TrackerResult:
    branch: str
    started_utc: str
    finished_utc: str = ""
    source_statuses: dict[str, str] = field(default_factory=dict)
    overall_status: str = "pending"
    discovery_complete: bool = False
    source_counts: dict[str, int] = field(default_factory=dict)
    new_filing_counts: dict[str, int] = field(default_factory=dict)
    cataloged_filing_counts: dict[str, int] = field(default_factory=dict)
    baseline_counts: dict[str, int] = field(default_factory=dict)
    transaction_counts: dict[str, int] = field(default_factory=dict)
    purchase_counts: dict[str, int] = field(default_factory=dict)
    alerted_filing_counts: dict[str, int] = field(default_factory=dict)
    pending_review_counts: dict[str, int] = field(default_factory=dict)
    filings: list[dict[str, Any]] = field(default_factory=list)
    transactions: list[dict[str, Any]] = field(default_factory=list)
    purchases: list[dict[str, Any]] = field(default_factory=list)
    pending_reviews: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = False
    historical_backfill: dict[str, Any] = field(default_factory=dict)


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_watchlist(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        value = normalize_text(part)
        if value and value.casefold() not in seen:
            values.append(value)
            seen.add(value.casefold())
    return tuple(values)


def normalize_date(value: str) -> str:
    value = normalize_text(value)
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value


def normalize_amount(value: str) -> str:
    value = normalize_text(value).replace("—", "-").replace("–", "-")
    return re.sub(r"\s*-\s*", " - ", value)


def owner_label(value: str) -> str:
    normalized = normalize_text(value).upper()
    return OWNER_LABELS.get(normalized, normalize_text(value) or "Unknown")


def transaction_label(value: str) -> str:
    normalized = normalize_text(value).upper()
    return TRANSACTION_LABELS.get(normalized, normalize_text(value).title())


def extract_ticker(asset: str, explicit: str = "") -> str:
    explicit = normalize_text(explicit).upper()
    if explicit not in {"", "--", "N/A", "NONE"} and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,7}", explicit):
        return explicit
    matches = TICKER_RE.findall(asset.upper())
    return matches[0] if matches else ""


def infer_asset_type(asset: str, explicit: str = "") -> str:
    explicit = normalize_text(explicit)
    if explicit and explicit not in {"--", "None", "N/A"}:
        return explicit
    code_match = ASSET_CODE_RE.search(asset)
    if code_match:
        return code_match.group(1).upper()
    lowered = asset.casefold()
    if "stock option" in lowered or " call option" in lowered or " put option" in lowered:
        return "Stock Option"
    if "common stock" in lowered or "preferred stock" in lowered or re.search(r"\bstock\b", lowered):
        return "Stock"
    if "etf" in lowered or "exchange traded fund" in lowered or "exchange-traded fund" in lowered:
        return "ETF"
    if "bond" in lowered:
        return "Bond"
    return "Unknown"


def is_equity_like(asset: str, asset_type: str, ticker: str) -> bool:
    lowered_asset = asset.casefold()
    lowered_type = asset_type.casefold()
    code = asset_type.upper()
    if code in EQUITY_CODES:
        return True
    if any(term in lowered_type for term in EQUITY_TYPE_TERMS):
        return True
    if any(term in lowered_type for term in NON_EQUITY_TERMS):
        return False
    if any(term in lowered_asset for term in NON_EQUITY_TERMS):
        return False
    if any(term in lowered_asset for term in EQUITY_TYPE_TERMS):
        return True
    # A disclosed ticker with no bond/fund language is a useful medium-confidence
    # equity signal. The raw row remains available for review.
    return bool(ticker)


def clean_asset(asset: str) -> str:
    asset = normalize_text(asset)
    asset = re.sub(r"^(?:SP|JT|DC)\s+", "", asset, flags=re.IGNORECASE)
    return asset.strip(" |-")


def stable_id(prefix: str, values: Iterable[str]) -> str:
    material = "\x1f".join(normalize_text(value) for value in values)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


def make_trade(
    *,
    branch: str,
    source: str,
    report: Report | Mapping[str, Any],
    owner: str,
    asset: str,
    ticker: str,
    asset_type: str,
    transaction_type: str,
    transaction_date: str,
    notification_date: str,
    amount: str,
    raw_row: str,
    confidence: str,
) -> Trade:
    if isinstance(report, Report):
        report_id = report.report_id
        filer = report.filer
        filed_date = report.filed_date
        source_url = report.url
        chamber = report.source.title() if report.source in {"house", "senate"} else ""
        title = report.metadata.get("title", "")
        agency = report.metadata.get("agency", "")
    else:
        report_id = str(report.get("listing_id") or report.get("report_id") or "")
        filer = str(report.get("name") or report.get("filer") or "Unknown filer")
        filed_date = str(report.get("date") or report.get("filed_date") or "Unknown")
        source_url = str(
            report.get("document_url")
            or report.get("url")
            or report.get("request_url")
            or ""
        )
        chamber = str(report.get("chamber") or "")
        title = str(report.get("title") or "")
        agency = str(report.get("agency") or "")

    asset = clean_asset(asset)
    ticker = extract_ticker(asset, ticker)
    asset_type = infer_asset_type(asset, asset_type)
    transaction_type = transaction_label(transaction_type)
    transaction_date = normalize_date(transaction_date)
    notification_date = normalize_date(notification_date) if notification_date else ""
    amount = normalize_amount(amount)
    trade_id = stable_id(
        "trade",
        (
            source,
            report_id,
            filer,
            owner,
            asset,
            ticker,
            asset_type,
            transaction_type,
            transaction_date,
            amount,
        ),
    )
    return Trade(
        trade_id=trade_id,
        observed_at_utc=iso_utc(),
        branch=branch,
        source=source,
        report_id=report_id,
        filer=normalize_text(filer),
        chamber=normalize_text(chamber),
        title=normalize_text(title),
        agency=normalize_text(agency),
        owner=owner_label(owner),
        asset=asset,
        ticker=ticker,
        asset_type=asset_type,
        transaction_type=transaction_type,
        transaction_date=transaction_date,
        notification_date=notification_date,
        filed_date=normalize_date(filed_date),
        amount=amount,
        source_url=source_url,
        raw_row=normalize_text(raw_row),
        equity_like=is_equity_like(asset, asset_type, ticker),
        parse_confidence=confidence,
    )


def filing_key(source: str, report_id: str) -> str:
    return f"{normalize_text(source).casefold()}|{normalize_text(report_id)}"


def _filing_source_fields(
    report: Report | Mapping[str, Any],
    *,
    source: str,
) -> dict[str, str]:
    if isinstance(report, Report):
        metadata = report.metadata
        return {
            "report_id": report.report_id,
            "filer": report.filer,
            "filed_date": report.filed_date,
            "source_url": report.url,
            "document_format": report.format,
            "chamber": report.source.title() if report.source in {"house", "senate"} else "",
            "title": metadata.get("title", ""),
            "agency": metadata.get("agency", ""),
            "district": metadata.get("district", ""),
            "report_type": metadata.get("report_type", "Periodic Transaction Report"),
            "access_mode": "direct",
        }

    report_id = str(report.get("listing_id") or report.get("report_id") or "")
    source_url = str(
        report.get("document_url")
        or report.get("request_url")
        or report.get("url")
        or ""
    )
    access_mode = normalize_text(str(report.get("access_mode") or "unknown")).casefold()
    if access_mode == "direct" or source_url.casefold().endswith(".pdf"):
        document_format = "pdf"
    elif access_mode == "request":
        document_format = "request"
    else:
        document_format = "unknown"
    return {
        "report_id": report_id,
        "filer": str(report.get("name") or report.get("filer") or "Unknown filer"),
        "filed_date": str(report.get("date") or report.get("filed_date") or "Unknown"),
        "source_url": source_url,
        "document_format": document_format,
        "chamber": str(report.get("chamber") or ""),
        "title": str(report.get("title") or ""),
        "agency": str(report.get("agency") or ""),
        "district": str(report.get("district") or ""),
        "report_type": str(
            report.get("document_type")
            or report.get("report_type")
            or "Periodic Transaction Report"
        ),
        "access_mode": access_mode,
    }


def make_filing_record(
    report: Report | Mapping[str, Any],
    *,
    branch: str,
    source: str,
    status: str,
    first_seen_utc: str | None = None,
    transactions: Sequence[Trade] = (),
    review: PendingReview | None = None,
) -> FilingRecord:
    fields = _filing_source_fields(report, source=source)
    report_id = fields["report_id"]
    now = iso_utc()
    purchase_count = sum(tx.transaction_type == "Purchase" for tx in transactions)
    sale_count = sum(tx.transaction_type.startswith("Sale") for tx in transactions)
    exchange_count = sum(tx.transaction_type == "Exchange" for tx in transactions)
    return FilingRecord(
        filing_key=filing_key(source, report_id),
        first_seen_utc=first_seen_utc or now,
        updated_at_utc=now,
        branch=normalize_text(branch),
        source=normalize_text(source).casefold(),
        report_id=report_id,
        filer=normalize_text(fields["filer"]),
        filed_date=normalize_date(fields["filed_date"]),
        source_url=fields["source_url"],
        document_format=normalize_text(fields["document_format"]).casefold(),
        chamber=normalize_text(fields["chamber"]),
        title=normalize_text(fields["title"]),
        agency=normalize_text(fields["agency"]),
        district=normalize_text(fields["district"]),
        report_type=normalize_text(fields["report_type"]),
        access_mode=normalize_text(fields["access_mode"]).casefold(),
        status=normalize_text(status).casefold().replace(" ", "_"),
        transaction_count=len(transactions),
        purchase_count=purchase_count,
        sale_count=sale_count,
        exchange_count=exchange_count,
        review_reason=review.reason if review else "",
    )


def is_house_paper_text(text: str) -> bool:
    normalized = normalize_text(text).casefold()
    paper_markers = (
        "amount of transaction",
        "type of transaction",
        "hand delivered",
        "provide full name not ticker symbol",
    )
    electronic_markers = ("filing status:", "subholding of:")
    return any(marker in normalized for marker in paper_markers) and not any(
        marker in normalized for marker in electronic_markers
    )


def _house_transaction_region(text: str) -> list[str]:
    lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
    start = 0
    for index, line in enumerate(lines):
        if "$200?" in line or "Cap. Gains" in line:
            start = index + 1
            break
        if line.casefold() == "transactions":
            start = index + 1
    end = len(lines)
    for index in range(start, len(lines)):
        lowered = lines[index].casefold()
        if (
            "for the complete list of asset type abbreviations" in lowered
            or lowered.startswith("investment vehicle details")
            or lowered.startswith("initial public offerings")
            or lowered.startswith("certification and signature")
        ):
            end = index
            break
    return lines[start:end]


def parse_house_transactions(text: str, report: Report) -> list[Trade]:
    """Parse electronically generated House PTR text into normalized transactions."""
    if is_house_paper_text(text):
        raise PaperFilingError("House filing is a paper/scanned PTR; checkbox semantics require review")

    lines = _house_transaction_region(text)

    def _house_metadata_or_header(line: str) -> bool:
        value = normalize_text(line)
        lowered = value.casefold()
        return (
            bool(re.match(r"^(?:F\s*S|S\s*O|D)\s*:", value, re.IGNORECASE))
            or lowered.startswith(
                ("filing status:", "subholding of:", "id owner asset", "type date gains")
            )
            or value == "$200?"
        )

    # pdfplumber may place the transaction columns before the trailing asset
    # text/ticker. Reassemble those physical lines into one logical row before
    # the existing transaction parser sees them.
    prepared: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]

        if _house_metadata_or_header(line):
            index += 1
            continue

        match = HOUSE_TRANSACTION_RE.search(line)
        if match and line[: match.start()].strip():
            continuation: list[str] = []
            next_index = index + 1

            while next_index < len(lines):
                candidate = lines[next_index]
                if (
                    _house_metadata_or_header(candidate)
                    or HOUSE_TRANSACTION_RE.search(candidate)
                ):
                    break
                continuation.append(candidate)
                next_index += 1

            if continuation:
                asset = line[: match.start()].strip()
                transaction = line[match.start() :].strip()

                # Example:
                # "$15,001 -" + "Shares (ACN) [ST] $50,000"
                if re.search(r"[-–—]\s*$", transaction):
                    upper = re.search(
                        r"(\$[\d,]+(?:\.\d{2})?)\s*$",
                        continuation[-1],
                    )
                    if upper:
                        transaction = f"{transaction} {upper.group(1)}"
                        continuation[-1] = continuation[-1][: upper.start()].strip()

                asset = normalize_text(
                    " ".join([asset, *[part for part in continuation if part]])
                )
                line = f"{asset} {transaction}"
                index = next_index
                prepared.append(line)
                continue

        prepared.append(line)
        index += 1

    lines = prepared
    transactions: list[Trade] = []
    trade_id_occurrences: dict[str, int] = {}
    buffer: list[str] = []
    skip_prefixes = (
        "f s:",
        "s o:",
        "filing status:",
        "subholding of:",
        "filing id #",
        "id owner asset",
        "type date notification",
        "date amount",
    )

    index = 0
    while index < len(lines):
        line = lines[index]
        lowered = line.casefold()
        if lowered.startswith(skip_prefixes):
            index += 1
            continue
        # PDF text extraction sometimes wraps the upper half of an amount range onto
        # the next line. Join that continuation before matching the transaction.
        if re.search(r"\$[\d,]+\s*[-–—]\s*$", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if re.fullmatch(r"\$?[\d,]+(?:\.\d{2})?", next_line):
                line = f"{line} {next_line}"
                index += 1

        buffer.append(line)
        combined = normalize_text(" ".join(buffer))
        match = HOUSE_TRANSACTION_RE.search(combined)
        if match:
            asset_prefix = combined[: match.start()].strip()
            amount_value = match.group("amount")

            # Some House PDFs interleave the second half of the asset description
            # between the lower and upper values of the disclosed amount range:
            #
            #   Alphabet Inc. - Class A Common
            #   S (partial) 08/24/2026 08/24/2026 $50,001 -
            #   Stock (GOOGL) [ST]
            #   $100,000
            #
            # Do not finalize the row until the upper bound is available.
            trailing = combined[match.end():].strip()
            if trailing[:1] in {"-", "–", "—"}:
                remainder = trailing[1:].strip()
                upper_match = re.search(
                    r"\$?[\d,]+(?:\.\d{2})?\s*$",
                    remainder,
                )
                if upper_match is None:
                    index += 1
                    continue

                asset_suffix = remainder[: upper_match.start()].strip()
                if asset_suffix:
                    asset_prefix = normalize_text(
                        f"{asset_prefix} {asset_suffix}"
                    )
                amount_value = normalize_amount(
                    f"{amount_value} - {upper_match.group(0)}"
                )

            owner_code = ""
            owner_match = re.match(r"^(SP|JT|DC)\s+", asset_prefix, re.IGNORECASE)
            if owner_match:
                owner_code = owner_match.group(1).upper()
                asset_prefix = asset_prefix[owner_match.end() :]
            asset_code_match = ASSET_CODE_RE.search(asset_prefix)
            asset_code = asset_code_match.group(1).upper() if asset_code_match else ""
            trade = make_trade(
                branch="legislative",
                source="house",
                report=report,
                owner=owner_code,
                asset=asset_prefix,
                ticker="",
                asset_type=asset_code,
                transaction_type=match.group("type"),
                transaction_date=match.group("date"),
                notification_date=match.group("notification"),
                amount=amount_value,
                raw_row=combined,
                confidence="high",
            )
            base_trade_id = trade.trade_id
            occurrence = trade_id_occurrences.get(base_trade_id, 0) + 1
            trade_id_occurrences[base_trade_id] = occurrence

            # A filing may legitimately contain two otherwise-identical
            # transactions from different accounts/trusts. Preserve both.
            if occurrence > 1:
                trade = replace(
                    trade,
                    trade_id=stable_id(
                        "trade",
                        (base_trade_id, f"occurrence:{occurrence}"),
                    ),
                )

            transactions.append(trade)
            buffer = []
        elif len(combined) > 5_000:
            raise SourceChangedError(
                f"House PTR parser accumulated an implausibly long transaction row for {report.report_id}"
            )
        index += 1

    if not transactions:
        excerpt = normalize_text(text)[:500]
        raise SourceChangedError(
            f"Electronic House PTR {report.report_id} contains no parseable transactions: {excerpt!r}"
        )
    return transactions


def _canonical_header(value: str) -> str:
    value = normalize_text(value).casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


def _header_index(headers: Sequence[str], *candidates: str) -> int | None:
    for candidate in candidates:
        candidate = _canonical_header(candidate)
        for index, header in enumerate(headers):
            if header == candidate:
                return index
    for candidate in candidates:
        candidate = _canonical_header(candidate)
        for index, header in enumerate(headers):
            if candidate in header:
                return index
    return None


def _cell(cells: Sequence[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(cells):
        return ""
    return cells[index]


def _infer_senate_cells(cells: Sequence[str]) -> dict[str, str]:
    date_index = next((i for i, value in enumerate(cells) if DATE_RE.fullmatch(value)), None)
    type_index = next(
        (
            i
            for i, value in enumerate(cells)
            if transaction_label(value).startswith(("Purchase", "Sale", "Exchange"))
            and normalize_text(value).upper() in TRANSACTION_LABELS
        ),
        None,
    )
    amount_index = next((i for i, value in enumerate(cells) if AMOUNT_RE.fullmatch(value)), None)
    if date_index is None or type_index is None or amount_index is None:
        return {}
    owner = cells[date_index + 1] if date_index + 1 < len(cells) else ""
    ticker = cells[date_index + 2] if date_index + 2 < len(cells) else ""
    asset_start = date_index + 3
    asset_end = type_index
    asset_type = ""
    if asset_end - asset_start >= 2:
        asset_type = cells[asset_end - 1]
        asset_end -= 1
    asset = " ".join(cells[asset_start:asset_end])
    return {
        "date": cells[date_index],
        "owner": owner,
        "ticker": ticker,
        "asset": asset,
        "asset_type": asset_type,
        "type": cells[type_index],
        "amount": cells[amount_index],
        "comment": " | ".join(cells[amount_index + 1 :]),
    }


def parse_senate_html_transactions(html: str, report: Report) -> list[Trade]:
    soup = BeautifulSoup(html, "html.parser")
    parsed: list[Trade] = []
    found_transaction_table = False

    for table in soup.find_all("table"):
        header_cells = table.find_all("th")
        headers = [_canonical_header(cell.get_text(" ", strip=True)) for cell in header_cells]
        date_index = _header_index(headers, "transaction date", "date")
        owner_index = _header_index(headers, "owner")
        ticker_index = _header_index(headers, "ticker")
        asset_index = _header_index(headers, "asset name", "asset")
        asset_type_index = _header_index(headers, "asset type")
        type_index = _header_index(headers, "transaction type", "type")
        amount_index = _header_index(headers, "amount")
        comment_index = _header_index(headers, "comment")

        if date_index is not None and type_index is not None and amount_index is not None:
            found_transaction_table = True

        for row in table.find_all("tr"):
            cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            if not cells:
                continue
            values: dict[str, str]
            if found_transaction_table and headers:
                values = {
                    "date": _cell(cells, date_index),
                    "owner": _cell(cells, owner_index),
                    "ticker": _cell(cells, ticker_index),
                    "asset": _cell(cells, asset_index),
                    "asset_type": _cell(cells, asset_type_index),
                    "type": _cell(cells, type_index),
                    "amount": _cell(cells, amount_index),
                    "comment": _cell(cells, comment_index),
                }
            else:
                values = _infer_senate_cells(cells)
            if not values:
                continue
            tx_type = transaction_label(values["type"])
            if tx_type not in {"Purchase", "Sale", "Sale (Full)", "Sale (Partial)", "Exchange"}:
                continue
            raw = " | ".join(cells)
            if values.get("comment"):
                raw = f"{raw} | {values['comment']}"
            parsed.append(
                make_trade(
                    branch="legislative",
                    source="senate",
                    report=report,
                    owner=values.get("owner", ""),
                    asset=values.get("asset", ""),
                    ticker=values.get("ticker", ""),
                    asset_type=values.get("asset_type", ""),
                    transaction_type=values["type"],
                    transaction_date=values["date"],
                    notification_date="",
                    amount=values["amount"],
                    raw_row=raw,
                    confidence="high",
                )
            )

    if not parsed:
        raise SenateInvalidResponse("report", "no_parseable_transaction_rows")
    return parsed


def parse_generic_transactions_text(
    text: str,
    report: Report | Mapping[str, Any],
    *,
    branch: str,
    source: str,
    paper_is_pending: bool = True,
) -> list[Trade]:
    """Parse OGE-style or paper-report text where transaction type is written out."""
    lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
    parsed: list[Trade] = []
    buffer: list[str] = []
    header_terms = (
        "description type date",
        "transaction date owner",
        "periodic transaction report",
        "notification received over 30 days ago",
    )
    stop_terms = (
        "comments of reviewing officials",
        "certification and signature",
        "filer's certification",
        "reviewing official",
    )

    for line in lines:
        lowered = line.casefold()
        if any(term in lowered for term in header_terms):
            buffer = []
            continue
        if any(lowered.startswith(term) for term in stop_terms):
            buffer = []
            continue
        if re.search(r"\$[\d,]+\s*[-–—]\s*$", line):
            buffer.append(line)
            continue
        buffer.append(line)
        combined = normalize_text(" ".join(buffer))
        match = GENERIC_TRANSACTION_RE.search(combined)
        if not match:
            if len(combined) > 3_500:
                buffer = buffer[-8:]
            continue
        prefix = combined[: match.start()].strip(" |-")
        # Remove obvious row numbers and owner labels when present.
        prefix = re.sub(r"^\d+\s+", "", prefix)
        owner = ""
        owner_match = re.match(
            r"^(Self|Spouse|Joint|Dependent Child|SP|JT|DC)\s+",
            prefix,
            re.IGNORECASE,
        )
        if owner_match:
            owner = owner_match.group(1)
            prefix = prefix[owner_match.end() :]
        asset_type = infer_asset_type(prefix)
        parsed.append(
            make_trade(
                branch=branch,
                source=source,
                report=report,
                owner=owner,
                asset=prefix,
                ticker="",
                asset_type=asset_type,
                transaction_type=match.group("type"),
                transaction_date=match.group("date"),
                notification_date="",
                amount=match.group("amount"),
                raw_row=combined,
                confidence="medium",
            )
        )
        buffer = []

    if not parsed and paper_is_pending:
        raise PaperFilingError("Filing text does not preserve enough row structure for reliable parsing")
    if not parsed:
        raise SourceChangedError("Electronic filing contains no parseable transaction rows")
    return parsed


def purchases_only(transactions: Iterable[Trade]) -> list[Trade]:
    return [trade for trade in transactions if trade.transaction_type == "Purchase"]


def load_state(path: Path) -> tuple[TrackerState, bool]:
    if not path.exists():
        return TrackerState(), True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"Tracker state is unreadable: {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != STATE_VERSION:
        raise MonitorError(
            f"Unsupported tracker state in {path}; expected version {STATE_VERSION}"
        )
    seen_payload = payload.get("seen_filings", {})
    seen_filings: dict[str, dict[str, str]] = {"house": {}, "senate": {}, "oge": {}}
    for source in seen_filings:
        source_payload = seen_payload.get(source, {})
        if not isinstance(source_payload, dict):
            raise MonitorError(f"State field seen_filings.{source} must be an object")
        seen_filings[source] = {str(k): str(v) for k, v in source_payload.items()}
    return (
        TrackerState(
            version=STATE_VERSION,
            seen_filings=seen_filings,
            seen_trades={str(k): str(v) for k, v in payload.get("seen_trades", {}).items()},
            seen_reviews={str(k): str(v) for k, v in payload.get("seen_reviews", {}).items()},
            last_attempt_utc=payload.get("last_attempt_utc"),
            last_success_utc=payload.get("last_success_utc"),
            last_counts={str(k): int(v) for k, v in payload.get("last_counts", {}).items()},
        ),
        False,
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        temp_name = handle.name
    Path(temp_name).replace(path)


def save_state(path: Path, state: TrackerState) -> None:
    state.prune()
    payload = {
        "version": state.version,
        "seen_filings": state.seen_filings,
        "seen_trades": state.seen_trades,
        "seen_reviews": state.seen_reviews,
        "last_attempt_utc": state.last_attempt_utc,
        "last_success_utc": state.last_success_utc,
        "last_counts": state.last_counts,
    }
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    rows = list(records)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MonitorError(f"Invalid JSONL in {path} at line {line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise MonitorError(f"JSONL record in {path} at line {line_number} is not an object")
        records.append(value)
    return records


def latest_records(path: Path, key_field: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(path):
        key = str(record.get(key_field) or "")
        if key:
            latest[key] = record
    return latest


def _filing_record_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    ignored = {"updated_at_utc"}
    left_payload = {key: value for key, value in left.items() if key not in ignored}
    right_payload = {key: value for key, value in right.items() if key not in ignored}
    return left_payload == right_payload


def upsert_filing_record(
    path: Path,
    index: dict[str, dict[str, Any]],
    record: FilingRecord,
) -> bool:
    payload = asdict(record)
    existing = index.get(record.filing_key)
    if existing:
        # Preserve additive provenance (including silent historical bootstrap)
        # and unknown retained metadata when refreshing known catalog fields.
        payload = {**existing, **payload}
        # A routine catalog pass must never erase a parsed or review-required outcome.
        if record.status in {"cataloged", "detected"} and str(existing.get("status")) in {
            "processed",
            "review_required",
        }:
            payload.update(
                {
                    "first_seen_utc": existing.get("first_seen_utc", record.first_seen_utc),
                    "status": existing.get("status", record.status),
                    "transaction_count": existing.get("transaction_count", 0),
                    "purchase_count": existing.get("purchase_count", 0),
                    "sale_count": existing.get("sale_count", 0),
                    "exchange_count": existing.get("exchange_count", 0),
                    "review_reason": existing.get("review_reason", ""),
                }
            )
        elif existing.get("first_seen_utc"):
            payload["first_seen_utc"] = existing["first_seen_utc"]
        if _filing_record_equivalent(existing, payload):
            return False
    append_jsonl(path, (payload,))
    index[record.filing_key] = payload
    return True


def catalog_visible_filings(
    *,
    config: TrackerConfig,
    state: TrackerState,
    result: TrackerResult,
    source: str,
    reports: Sequence[Report | Mapping[str, Any]],
    filing_index: dict[str, dict[str, Any]],
    treat_unseen_as_new: bool,
) -> None:
    cataloged = 0
    for report in reports:
        fields = _filing_source_fields(report, source=source)
        report_id = fields["report_id"]
        unseen = not state.is_filing_seen(source, report_id)
        status = "detected" if unseen and treat_unseen_as_new else "cataloged"
        key = filing_key(source, report_id)
        existing = filing_index.get(key)
        record = make_filing_record(
            report,
            branch=config.branch,
            source=source,
            status=status,
            first_seen_utc=(str(existing.get("first_seen_utc")) if existing else None),
        )
        if upsert_filing_record(config.filings_path, filing_index, record):
            cataloged += 1
        if unseen and treat_unseen_as_new:
            # The final processed/review record replaces this provisional record in the UI.
            result.filings.append(asdict(record))
    result.cataloged_filing_counts[source] = cataloged


def write_records_csv(
    records: Sequence[Mapping[str, Any]],
    output_path: Path,
    fieldnames: Sequence[str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
        temp_name = handle.name
    Path(temp_name).replace(output_path)


def write_latest_csv(ledger_path: Path, output_path: Path, max_rows: int = DEFAULT_LATEST_CSV_ROWS) -> None:
    rows = read_jsonl(ledger_path)
    rows.sort(
        key=lambda row: (
            str(row.get("filed_date", "")),
            str(row.get("observed_at_utc", "")),
            str(row.get("trade_id", "")),
        ),
        reverse=True,
    )
    rows = rows[:max_rows]
    fieldnames = [field.name for field in Trade.__dataclass_fields__.values()]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        newline="",
        encoding="utf-8",
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        temp_name = handle.name
    Path(temp_name).replace(output_path)


def write_latest_filings_csv(
    filings_path: Path,
    output_path: Path,
    max_rows: int = 10_000,
) -> None:
    rows = list(latest_records(filings_path, "filing_key").values())
    rows.sort(
        key=lambda row: (
            str(row.get("filed_date", "")),
            str(row.get("updated_at_utc", "")),
            str(row.get("filing_key", "")),
        ),
        reverse=True,
    )
    fieldnames = [field.name for field in FilingRecord.__dataclass_fields__.values()]
    write_records_csv(rows[:max_rows], output_path, fieldnames)


def write_result(path: Path, result: TrackerResult) -> None:
    atomic_write_text(path, json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")


def append_run_history(path: Path, result: TrackerResult) -> None:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip("/")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else ""
    record = {
        "run_key": f"{run_id}:{run_attempt}" if run_id else stable_id(
            "run", (result.branch, result.started_utc, result.finished_utc)
        ),
        "branch": result.branch,
        "started_utc": result.started_utc,
        "finished_utc": result.finished_utc,
        "success": result.success,
        "source_statuses": result.source_statuses,
        "overall_status": result.overall_status,
        "source_counts": result.source_counts,
        "new_filing_counts": result.new_filing_counts,
        "cataloged_filing_counts": result.cataloged_filing_counts,
        "baseline_counts": result.baseline_counts,
        "transaction_counts": result.transaction_counts,
        "purchase_counts": result.purchase_counts,
        "pending_review_counts": result.pending_review_counts,
        "historical_backfill": result.historical_backfill,
        "errors": result.errors,
        "run_url": run_url,
        "event_name": os.environ.get("GITHUB_EVENT_NAME")
        or ("runtime_v2" if os.environ.get("POLITITRACK_MODE") else "local"),
        "trigger_source": trigger_source(),
        "mode": os.environ.get("POLITITRACK_MODE", ""),
        "run_attempt": run_attempt,
    }
    append_jsonl(path, (record,))


def _selected_legislative_sources(value: str) -> tuple[str, ...]:
    return ("house", "senate") if value == "all" else (value,)


def scan_house_report(session: Session, report: Report, config: TrackerConfig) -> tuple[list[Trade], PendingReview | None]:
    pdf_bytes = fetch_pdf_bytes(
        session,
        report.url,
        config,  # runtime duck typing: fetch_pdf_bytes uses max_download_bytes only
        f"House PTR {report.metadata.get('document_id', report.report_id)}",
    )
    try:
        text = extract_pdf_text(pdf_bytes, config.max_ocr_pages)
        return parse_house_transactions(text, report), None
    except PaperFilingError as exc:
        review = make_pending_review(
            branch="legislative",
            source="house",
            report_id=report.report_id,
            filer=report.filer,
            filed_date=report.filed_date,
            source_url=report.url,
            reason=str(exc),
        )
        return [], review


def _senate_pdf_from_viewer(
    session: SenateClient,
    response: Response,
    data: bytes,
    config: TrackerConfig,
) -> tuple[bytes, str]:
    content_type = response.headers.get("Content-Type", "").lower()
    if data.startswith(b"%PDF"):
        return data, response.url
    if "application/pdf" in content_type:
        raise SenateInvalidResponse("report_pdf", "invalid_pdf_signature")
    soup = BeautifulSoup(data, "html.parser")
    link = soup.find("a", href=re.compile(r"\.pdf(?:$|\?)", re.IGNORECASE))
    if not link or not link.get("href"):
        page_text = normalize_text(soup.get_text(" ", strip=True))
        if (
            "filing document - print view" in page_text.casefold()
            and re.search(r"\bpage\s+\d+\s+of\s+\d+\b", page_text, re.IGNORECASE)
        ):
            raise PaperFilingError(
                "Senate paper PTR is rendered as page images and exposes no direct PDF; "
                "manual review is required"
            )
        raise SenateInvalidResponse("report_viewer", "missing_pdf_link")
    pdf_url = urljoin(response.url, str(link["href"]))
    pdf_response = checked_response(
        session.get(pdf_url, timeout=DEFAULT_TIMEOUT),
        "Senate paper PTR PDF",
    )
    pdf_bytes = response_bytes(
        pdf_response, "Senate paper PTR PDF", config.max_download_bytes, safe_diagnostics=True,
    )
    if not pdf_bytes.startswith(b"%PDF"):
        raise SenateInvalidResponse("report_pdf", "invalid_pdf_signature")
    return pdf_bytes, pdf_url


def scan_senate_report(session: SenateClient, report: Report, config: TrackerConfig) -> tuple[list[Trade], PendingReview | None]:
    response = _senate_page_response(session, report)
    try:
        return _parse_senate_report_response(session, response, report, config)
    except SenateAccessDenied:
        raise
    except Exception:
        # Shared PDF/parsing helpers can expose exception text from document
        # content. Only a classified Senate error may cross this boundary.
        session.reject_report(response)
        raise SenateInvalidResponse("report", "invalid_report_content") from None


def _parse_senate_report_response(
    session: SenateClient, response: Response, report: Report, config: TrackerConfig,
) -> tuple[list[Trade], PendingReview | None]:
    data = response_bytes(response, "Senate PTR", config.max_download_bytes, safe_diagnostics=True)
    content_type = response.headers.get("Content-Type", "").lower()

    if report.format == "pdf" or data.startswith(b"%PDF") or "application/pdf" in content_type:
        try:
            pdf_bytes, _pdf_url = _senate_pdf_from_viewer(
                session, response, data, config
            )
        except PaperFilingError as exc:
            return [], make_pending_review(
                branch="legislative",
                source="senate",
                report_id=report.report_id,
                filer=report.filer,
                filed_date=report.filed_date,
                source_url=report.url,
                reason=str(exc),
            )

        try:
            text = extract_pdf_text(pdf_bytes, config.max_ocr_pages, safe_diagnostics=True)
            transactions = parse_generic_transactions_text(
                text,
                report,
                branch="legislative",
                source="senate",
                paper_is_pending=True,
            )
            return transactions, None
        except PaperFilingError as exc:
            return [], make_pending_review(
                branch="legislative",
                source="senate",
                report_id=report.report_id,
                filer=report.filer,
                filed_date=report.filed_date,
                source_url=report.url,
                reason=str(exc),
            )

    html = data.decode(response.encoding or "utf-8", errors="replace")
    return parse_senate_html_transactions(html, report), None


def make_pending_review(
    *,
    branch: str,
    source: str,
    report_id: str,
    filer: str,
    filed_date: str,
    source_url: str,
    reason: str,
    title: str = "",
    agency: str = "",
) -> PendingReview:
    review_id = stable_id("review", (source, report_id, filer, source_url, reason))
    return PendingReview(
        review_id=review_id,
        observed_at_utc=iso_utc(),
        branch=branch,
        source=source,
        report_id=report_id,
        filer=normalize_text(filer),
        filed_date=normalize_date(filed_date),
        source_url=source_url,
        reason=normalize_text(reason),
        title=normalize_text(title),
        agency=normalize_text(agency),
    )


def load_oge_listings(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"OGE listing file is unreadable: {path}: {exc}") from exc
    listings = payload.get("listings") if isinstance(payload, dict) else payload
    if not isinstance(listings, list):
        raise MonitorError(f"OGE listing file does not contain a listings array: {path}")
    normalized: list[dict[str, Any]] = []
    for item in listings:
        if not isinstance(item, dict):
            raise MonitorError(f"OGE listing is not an object: {item!r}")
        listing_id = str(item.get("listing_id") or "")
        if not listing_id:
            raise MonitorError(f"OGE listing is missing listing_id: {item!r}")
        normalized.append(dict(item))
    deduped = {str(item["listing_id"]): item for item in normalized}
    return sorted(deduped.values(), key=lambda item: (str(item.get("date", "")), str(item["listing_id"])))


def resolve_oge_pdf(session: Session, listing: Mapping[str, Any], config: TrackerConfig) -> bytes | None:
    access_mode = normalize_text(str(listing.get("access_mode", "unknown"))).casefold()
    if access_mode == "request":
        return None
    url = str(listing.get("document_url") or listing.get("url") or "").strip()
    if not url:
        return None
    response = checked_response(session.get(url, timeout=DEFAULT_TIMEOUT), f"OGE disclosure {url}")
    data = response_bytes(response, f"OGE disclosure {url}", config.max_download_bytes)
    content_type = response.headers.get("Content-Type", "").lower()
    if data.startswith(b"%PDF") or "application/pdf" in content_type:
        return data
    soup = BeautifulSoup(data, "html.parser")
    pdf_links = [
        urljoin(response.url, str(link["href"]))
        for link in soup.find_all("a", href=True)
        if re.search(r"\.pdf(?:$|\?)", str(link["href"]), re.IGNORECASE)
    ]
    if pdf_links:
        pdf_response = checked_response(
            session.get(pdf_links[0], timeout=DEFAULT_TIMEOUT),
            f"OGE disclosure PDF {pdf_links[0]}",
        )
        return response_bytes(
            pdf_response,
            f"OGE disclosure PDF {pdf_links[0]}",
            config.max_download_bytes,
        )
    page_text = normalize_text(soup.get_text(" ", strip=True)).casefold()
    if "form 201" in page_text or "request" in page_text:
        return None
    raise SourceChangedError(f"OGE disclosure landing page has no PDF or request path: {url}")


def scan_oge_listing(
    session: Session,
    listing: Mapping[str, Any],
    config: TrackerConfig,
) -> tuple[list[Trade], PendingReview | None]:
    pdf_bytes = resolve_oge_pdf(session, listing, config)
    listing_id = str(listing["listing_id"])
    filer = str(listing.get("name") or "Unknown filer")
    filed_date = str(listing.get("date") or "Unknown")
    source_url = str(
        listing.get("document_url")
        or listing.get("request_url")
        or listing.get("url")
        or ""
    )
    if pdf_bytes is None:
        return [], make_pending_review(
            branch="executive",
            source="oge",
            report_id=listing_id,
            filer=filer,
            filed_date=filed_date,
            source_url=source_url,
            reason="OGE Form 278-T is listed, but access requires an OGE Form 201 request or no direct PDF was published",
            title=str(listing.get("title") or ""),
            agency=str(listing.get("agency") or ""),
        )
    try:
        text = extract_pdf_text(pdf_bytes, config.max_ocr_pages)
        transactions = parse_generic_transactions_text(
            text,
            listing,
            branch="executive",
            source="oge",
            paper_is_pending=True,
        )
        return transactions, None
    except PaperFilingError as exc:
        return [], make_pending_review(
            branch="executive",
            source="oge",
            report_id=listing_id,
            filer=filer,
            filed_date=filed_date,
            source_url=source_url,
            reason=str(exc),
            title=str(listing.get("title") or ""),
            agency=str(listing.get("agency") or ""),
        )


def trade_matches_watchlist(trade: Trade, watchlist: Sequence[str]) -> bool:
    if not watchlist:
        return True
    haystack = f"{trade.ticker} {trade.asset}".casefold()
    return any(item.casefold() in haystack for item in watchlist)


def selected_for_notification(trades: Sequence[Trade], config: TrackerConfig) -> list[Trade]:
    selected = [trade for trade in trades if trade_matches_watchlist(trade, config.watchlist)]
    if config.notify_equity_only:
        selected = [trade for trade in selected if trade.equity_like]
    return selected


def _truncate(value: str, limit: int) -> str:
    value = normalize_text(value)
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _pushover_post(
    session: Session,
    config: TrackerConfig,
    *,
    title: str,
    message: str,
    url: str,
    url_title: str,
) -> None:
    if config.no_notify:
        LOGGER.warning("Notification suppressed (--no-notify): %s — %s", title, message)
        return
    if not config.pushover_api_token or not config.pushover_user_key:
        if config.require_pushover:
            raise NotificationError("Pushover credentials are required but missing")
        LOGGER.warning("Pushover credentials are absent; notification logged only: %s", title)
        return
    response = session.post(
        PUSHOVER_MESSAGES_URL,
        data={
            "token": config.pushover_api_token,
            "user": config.pushover_user_key,
            "title": _truncate(title, 250),
            "message": _truncate(message, 1024),
            "url": url,
            "url_title": _truncate(url_title, 100),
            "priority": "0",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        excerpt = normalize_text(response.text)[:300]
        raise NotificationError(
            f"Pushover returned HTTP {response.status_code}: {excerpt!r}"
        ) from exc
    try:
        body = response.json()
    except requests.JSONDecodeError as exc:
        raise NotificationError("Pushover returned non-JSON content") from exc
    if body.get("status") != 1:
        raise NotificationError(f"Pushover rejected notification: {body!r}")


def send_purchase_notification(
    session: Session,
    config: TrackerConfig,
    filing_label: str,
    trades: Sequence[Trade],
) -> bool:
    selected = selected_for_notification(trades, config)
    if not selected:
        return False
    filer = selected[0].filer
    source = selected[0].source.title()
    lines = [f"{filer} • {source} • {len(selected)} disclosed purchase(s)"]
    for trade in selected[:7]:
        asset_label = trade.ticker or _truncate(trade.asset, 32)
        owner = f" • {trade.owner}" if trade.owner and trade.owner != "Self" else ""
        lines.append(
            f"{asset_label} • {trade.amount} • {trade.transaction_date}{owner}"
        )
    if len(selected) > 7:
        lines.append(f"+{len(selected) - 7} more purchase(s)")
    _pushover_post(
        session,
        config,
        title=f"Government purchase disclosure: {filer}",
        message="\n".join(lines),
        url=selected[0].source_url,
        url_title=f"Open {filing_label}",
    )
    return True


def send_filing_notification(
    session: Session,
    config: TrackerConfig,
    filing_label: str,
    transactions: Sequence[Trade],
) -> bool:
    if not config.notify_all_filings:
        return send_purchase_notification(
            session,
            config,
            filing_label,
            purchases_only(transactions),
        )
    if not transactions:
        return False

    filer = transactions[0].filer
    source = transactions[0].source.title()
    purchases = sum(tx.transaction_type == "Purchase" for tx in transactions)
    sales = sum(tx.transaction_type.startswith("Sale") for tx in transactions)
    exchanges = sum(tx.transaction_type == "Exchange" for tx in transactions)
    summary_parts = []
    if purchases:
        summary_parts.append(f"{purchases} purchase{'s' if purchases != 1 else ''}")
    if sales:
        summary_parts.append(f"{sales} sale{'s' if sales != 1 else ''}")
    if exchanges:
        summary_parts.append(f"{exchanges} exchange{'s' if exchanges != 1 else ''}")
    if not summary_parts:
        summary_parts.append(f"{len(transactions)} transaction{'s' if len(transactions) != 1 else ''}")

    lines = [f"{filer} • {source} • {', '.join(summary_parts)}"]
    for trade in transactions[:7]:
        asset_label = trade.ticker or _truncate(trade.asset, 28)
        owner = f" • {trade.owner}" if trade.owner and trade.owner != "Self" else ""
        lines.append(
            f"{trade.transaction_type}: {asset_label} • {trade.amount} • "
            f"{trade.transaction_date}{owner}"
        )
    if len(transactions) > 7:
        lines.append(f"+{len(transactions) - 7} more transaction(s)")

    _pushover_post(
        session,
        config,
        title=f"Government filing: {filer}",
        message="\n".join(lines),
        url=transactions[0].source_url,
        url_title=f"Open {filing_label}",
    )
    return True


def send_pending_notification(
    session: Session,
    config: TrackerConfig,
    review: PendingReview,
) -> bool:
    if not config.notify_pending_reviews:
        return False
    message = f"{review.filer} • {review.source.title()}\n{review.reason}"
    _pushover_post(
        session,
        config,
        title=f"Government filing needs review: {review.filer}",
        message=message,
        url=review.source_url,
        url_title="Open filing or request page",
    )
    return True


def commit_filing_outcome(
    *,
    session: Session,
    config: TrackerConfig,
    state: TrackerState,
    result: TrackerResult,
    source: str,
    filing: Report | Mapping[str, Any],
    filing_id: str,
    filing_label: str,
    trades: Sequence[Trade],
    review: PendingReview | None,
    filing_index: dict[str, dict[str, Any]],
) -> None:
    fresh_transactions = [trade for trade in trades if trade.trade_id not in state.seen_trades]
    fresh_purchases = purchases_only(fresh_transactions)
    alerted = False
    if fresh_transactions:
        alerted = send_filing_notification(
            session,
            config,
            filing_label,
            fresh_transactions,
        )
    if review and review.review_id not in state.seen_reviews:
        alerted = send_pending_notification(session, config, review) or alerted

    timestamp = iso_utc()
    if fresh_transactions:
        append_jsonl(
            config.transactions_path,
            (asdict(trade) for trade in fresh_transactions),
        )
        for trade in fresh_transactions:
            state.seen_trades[trade.trade_id] = timestamp
            result.transactions.append(asdict(trade))
        result.transaction_counts[source] = (
            result.transaction_counts.get(source, 0) + len(fresh_transactions)
        )

    if fresh_purchases:
        append_jsonl(config.ledger_path, (asdict(trade) for trade in fresh_purchases))
        result.purchases.extend(asdict(trade) for trade in fresh_purchases)
        result.purchase_counts[source] = (
            result.purchase_counts.get(source, 0) + len(fresh_purchases)
        )

    if review and review.review_id not in state.seen_reviews:
        append_jsonl(config.pending_path, (asdict(review),))
        state.seen_reviews[review.review_id] = timestamp
        result.pending_reviews.append(asdict(review))
        result.pending_review_counts[source] = result.pending_review_counts.get(source, 0) + 1

    key = filing_key(source, filing_id)
    existing = filing_index.get(key)
    filing_record = make_filing_record(
        filing,
        branch=config.branch,
        source=source,
        status="review_required" if review else "processed",
        first_seen_utc=(str(existing.get("first_seen_utc")) if existing else None),
        transactions=trades,
        review=review,
    )
    upsert_filing_record(config.filings_path, filing_index, filing_record)
    result.filings = [
        item for item in result.filings if str(item.get("filing_key")) != filing_record.filing_key
    ]
    result.filings.append(asdict(filing_record))

    if alerted:
        result.alerted_filing_counts[source] = result.alerted_filing_counts.get(source, 0) + 1
    state.mark_filing_seen(source, filing_id, timestamp)
    save_state(config.state_path, state)


def _baseline_source(
    state: TrackerState,
    source: str,
    filing_ids: Iterable[str],
    result: TrackerResult,
) -> None:
    timestamp = iso_utc()
    ids = list(filing_ids)
    for filing_id in ids:
        state.mark_filing_seen(source, filing_id, timestamp)
    result.baseline_counts[source] = len(ids)


def should_baseline_source(
    state: TrackerState,
    source: str,
    config: TrackerConfig,
) -> bool:
    """Return whether a silent baseline is authorized for a source with no state.

    An existing but incomplete state file must not silently authorize a new source on a
    later scheduled run. Initialization must be explicit on the run that establishes the
    source baseline. ``bootstrap_alerts`` is also explicit, but processes rather than
    baselines every visible filing.
    """
    if state.seen_filings.get(source):
        return False
    if config.bootstrap_alerts:
        return False
    if not config.allow_state_initialization:
        raise MonitorError(
            f"{source.title()} has no durable baseline and "
            "ALLOW_STATE_INITIALIZATION is false. Run the workflow manually with "
            "initialize_state=true, or restore a complete state artifact."
        )
    return True


def run_legislative(
    config: TrackerConfig,
    state: TrackerState,
    result: TrackerResult,
    session: Session,
    filing_index: dict[str, dict[str, Any]],
) -> None:
    """Discover every required source before making any durable or alert side effect.

    The Senate client stays alive through report/PDF downloads. Its authenticated
    cookies are never shared with House downloads or the notification session.
    """
    current_year = utc_now().year
    sources = _selected_legislative_sources(config.legislative_source)
    catalogs: dict[str, list[Report]] = {}
    baselines: dict[str, bool] = {}
    result.source_statuses = {source: "pending" for source in sources}
    senate_client = SenateClient() if "senate" in sources else None
    try:
        # Discovery is read-only: even the attempt timestamp and run history wait.
        for source in sources:
            try:
                if source == "house":
                    reports = fetch_house_reports(
                        session,
                        years=(current_year - 1, current_year),
                        max_download_bytes=config.max_download_bytes,
                    )
                else:
                    reports = fetch_senate_reports(
                        senate_client,
                        lookback_days=config.senate_lookback_days,
                    )
                if not isinstance(reports, list) or any(
                    not isinstance(report, Report)
                    or report.source != source
                    or not report.report_id
                    or not report.url
                    for report in reports
                ):
                    raise SourceChangedError(f"{source.title()} returned an invalid PTR catalog")
                if not reports and not config.allow_empty_sources:
                    raise SourceChangedError(f"{source.title()} returned zero PTRs")
                catalogs[source] = reports
                result.source_counts[source] = len(reports)
                result.source_statuses[source] = "ok"
            except Exception as exc:
                result.source_statuses[source] = (
                    "blocked" if isinstance(exc, SenateAccessDenied) else "error"
                )
                result.overall_status = "degraded"
                raise

        # A missing source baseline must also fail before another source writes.
        for source in sources:
            baselines[source] = should_baseline_source(state, source, config)
        result.discovery_complete = True
        state.last_attempt_utc = result.started_utc
        save_state(config.state_path, state)

        for source in sources:
            reports = catalogs[source]
            result.transaction_counts[source] = 0
            result.purchase_counts[source] = 0
            result.pending_review_counts[source] = 0
            result.alerted_filing_counts[source] = 0
            source_bootstrap = baselines[source]
            unseen = [report for report in reports if not state.is_filing_seen(source, report.report_id)]
            result.new_filing_counts[source] = len(unseen)
            result.baseline_counts[source] = 0

            catalog_visible_filings(
                config=config,
                state=state,
                result=result,
                source=source,
                reports=reports,
                filing_index=filing_index,
                treat_unseen_as_new=not (source_bootstrap and not config.bootstrap_alerts),
            )

            if source_bootstrap and not config.bootstrap_alerts:
                _baseline_source(state, source, (report.report_id for report in reports), result)
                state.last_counts[source] = len(reports)
                save_state(config.state_path, state)
                LOGGER.info("Baselined and cataloged %s existing %s PTRs", len(reports), source)
                continue

            for report in unseen:
                LOGGER.info("Scanning new %s PTR for %s: %s", source, report.filer, report.url)
                if source == "house":
                    trades, review = scan_house_report(session, report, config)
                else:
                    trades, review = scan_senate_report(senate_client, report, config)
                commit_filing_outcome(
                    session=session,
                    config=config,
                    state=state,
                    result=result,
                    source=source,
                    filing=report,
                    filing_id=report.report_id,
                    filing_label=f"{source.title()} PTR",
                    trades=trades,
                    review=review,
                    filing_index=filing_index,
                )
            state.last_counts[source] = len(reports)
        # One bounded maintenance pass, using this same authoritative writer and
        # (for Senate) the existing validated session. It never sends alerts.
        if not any(baselines.values()):
            _run_historical_backfill(config, state, result, session, filing_index, senate_client)
    finally:
        if senate_client is not None:
            senate_client.close()


def run_executive(
    config: TrackerConfig,
    state: TrackerState,
    result: TrackerResult,
    session: Session,
    filing_index: dict[str, dict[str, Any]],
) -> None:
    if config.oge_listings_path is None:
        raise ValueError("--oge-listings-file is required for the executive branch")
    listings = load_oge_listings(config.oge_listings_path)
    source = "oge"
    result.source_counts[source] = len(listings)
    result.transaction_counts[source] = 0
    result.purchase_counts[source] = 0
    result.pending_review_counts[source] = 0
    result.alerted_filing_counts[source] = 0
    if not listings and not config.allow_empty_sources:
        raise SourceChangedError("OGE discovery returned zero Form 278-T listings")

    source_bootstrap = should_baseline_source(state, source, config)
    unseen = [item for item in listings if not state.is_filing_seen(source, str(item["listing_id"]))]
    result.new_filing_counts[source] = len(unseen)
    result.baseline_counts[source] = 0

    catalog_visible_filings(
        config=config,
        state=state,
        result=result,
        source=source,
        reports=listings,
        filing_index=filing_index,
        treat_unseen_as_new=not (source_bootstrap and not config.bootstrap_alerts),
    )

    if source_bootstrap and not config.bootstrap_alerts:
        _baseline_source(state, source, (str(item["listing_id"]) for item in listings), result)
        state.last_counts[source] = len(listings)
        save_state(config.state_path, state)
        LOGGER.info("Baselined and cataloged %s existing OGE 278-T listings", len(listings))
        return

    for listing in unseen:
        listing_id = str(listing["listing_id"])
        LOGGER.info("Scanning new OGE listing for %s", listing.get("name", "Unknown filer"))
        trades, review = scan_oge_listing(session, listing, config)
        commit_filing_outcome(
            session=session,
            config=config,
            state=state,
            result=result,
            source=source,
            filing=listing,
            filing_id=listing_id,
            filing_label="OGE Form 278-T",
            trades=trades,
            review=review,
            filing_index=filing_index,
        )
    state.last_counts[source] = len(listings)
    _run_historical_backfill(config, state, result, session, filing_index)


def _run_historical_backfill(
    config: TrackerConfig, state: TrackerState, result: TrackerResult, session: Session,
    filing_index: dict[str, dict[str, Any]], senate_client: SenateClient | None = None,
) -> None:
    try:
        from .historical_transaction_bootstrap import run_historical_transaction_backfill
    except ImportError:  # pragma: no cover - direct script execution
        from historical_transaction_bootstrap import run_historical_transaction_backfill
    run_historical_transaction_backfill(config=config, state=state, result=result, session=session,
                                        filing_index=filing_index, senate_client=senate_client)


def _markdown_cell(value: Any) -> str:
    return normalize_text(str(value or "")).replace("|", "\\|").replace("\n", " ")


def _write_step_summary(result: TrackerResult) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = [
        "## Government filing tracker",
        "",
        f"- Branch: **{_markdown_cell(result.branch.title())}**",
        f"- Success: **{str(result.success).lower()}**",
        f"- Status: **{_markdown_cell(result.overall_status)}**",
        f"- Started: `{result.started_utc}`",
        f"- Finished: `{result.finished_utc}`",
    ]
    dashboard_url = os.environ.get("DASHBOARD_URL", "").strip()
    if dashboard_url:
        lines.append(f"- Review dashboard: [{dashboard_url}]({dashboard_url})")

    lines.extend(
        [
            "",
            "### Source summary",
            "",
            "| Source | Status | Visible | New filings | Transactions | Purchases | Review items | Newly cataloged | Baselined |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for source in sorted(result.source_counts.keys() | result.source_statuses.keys()):
        unavailable = result.source_statuses.get(source) in {"pending", "blocked", "error"}
        visible = "Unavailable" if unavailable else result.source_counts[source]
        not_processed = "—" if not result.discovery_complete and result.branch == "legislative" else 0
        lines.append(
            f"| {source.title()} | {result.source_statuses.get(source, 'ok')} | {visible} | "
            f"{result.new_filing_counts.get(source, not_processed)} | "
            f"{result.transaction_counts.get(source, not_processed)} | "
            f"{result.purchase_counts.get(source, not_processed)} | "
            f"{result.pending_review_counts.get(source, not_processed)} | "
            f"{result.cataloged_filing_counts.get(source, not_processed)} | "
            f"{result.baseline_counts.get(source, not_processed)} |"
        )

    if result.filings:
        lines.extend(
            [
                "",
                "### Newly detected filings",
                "",
                "| Source | Filer | Filed | Status | Official filing |",
                "|---|---|---|---|---|",
            ]
        )
        for filing in result.filings[:25]:
            url = str(filing.get("source_url") or "")
            link = f"[Open]({url})" if url else "Unavailable"
            lines.append(
                f"| {_markdown_cell(str(filing.get('source', '')).title())} | "
                f"{_markdown_cell(filing.get('filer'))} | "
                f"{_markdown_cell(filing.get('filed_date'))} | "
                f"{_markdown_cell(str(filing.get('status', '')).replace('_', ' ').title())} | "
                f"{link} |"
            )
        if len(result.filings) > 25:
            lines.append(
                f"\n_And {len(result.filings) - 25} more filing(s) in the output artifact/dashboard._"
            )
    elif result.success:
        lines.extend(["", "### Newly detected filings", "", "No new filings were detected in this run."])

    if result.transactions:
        lines.extend(
            [
                "",
                "### Newly disclosed transactions",
                "",
                "| Type | Filer | Owner | Ticker / asset | Amount | Transaction date | Filing |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for trade in result.transactions[:25]:
            asset = trade.get("ticker") or trade.get("asset") or ""
            url = str(trade.get("source_url") or "")
            link = f"[Open]({url})" if url else "Unavailable"
            lines.append(
                f"| {_markdown_cell(trade.get('transaction_type'))} | "
                f"{_markdown_cell(trade.get('filer'))} | "
                f"{_markdown_cell(trade.get('owner'))} | "
                f"{_markdown_cell(asset)} | "
                f"{_markdown_cell(trade.get('amount'))} | "
                f"{_markdown_cell(trade.get('transaction_date'))} | {link} |"
            )
        if len(result.transactions) > 25:
            lines.append(
                f"\n_And {len(result.transactions) - 25} more transaction(s) in the output artifact/dashboard._"
            )

    if result.pending_reviews:
        lines.extend(
            [
                "",
                "### Manual review required",
                "",
                "| Source | Filer | Filed | Reason | Filing/request page |",
                "|---|---|---|---|---|",
            ]
        )
        for review in result.pending_reviews[:25]:
            url = str(review.get("source_url") or "")
            link = f"[Open]({url})" if url else "Unavailable"
            lines.append(
                f"| {_markdown_cell(str(review.get('source', '')).title())} | "
                f"{_markdown_cell(review.get('filer'))} | "
                f"{_markdown_cell(review.get('filed_date'))} | "
                f"{_markdown_cell(review.get('reason'))} | {link} |"
            )

    if result.errors:
        lines.extend(["", "### Errors", *[f"- {_markdown_cell(error)}" for error in result.errors]])
    Path(summary_path).open("a", encoding="utf-8").write("\n".join(lines) + "\n")


def run_tracker(config: TrackerConfig, session: Session | None = None) -> TrackerResult:
    started = iso_utc()
    result = TrackerResult(branch=config.branch, started_utc=started)
    session = session or build_session(config.user_agent)
    try:
        if not config.terms_acknowledged:
            raise MonitorError(
                "DISCLOSURE_TERMS_ACKNOWLEDGED is false. Review the statutory use restrictions, "
                "then explicitly acknowledge them before accessing disclosure reports."
            )
        if (
            config.require_pushover
            and not config.no_notify
            and (not config.pushover_api_token or not config.pushover_user_key)
        ):
            raise NotificationError(
                "REQUIRE_PUSHOVER is enabled, but PUSHOVER_API_TOKEN/PUSHOVER_USER_KEY are missing"
            )
        if not config.state_path.exists() and not config.allow_state_initialization:
            raise MonitorError(
                "Tracker state is missing and ALLOW_STATE_INITIALIZATION is false. "
                "Restore the state artifact or explicitly initialize a new baseline."
            )

        state, _brand_new_state = load_state(config.state_path)
        filing_index = latest_records(config.filings_path, "filing_key")
        if config.branch == "legislative":
            run_legislative(config, state, result, session, filing_index)
        else:
            state.last_attempt_utc = started
            save_state(config.state_path, state)
            run_executive(config, state, result, session, filing_index)
        state.last_success_utc = iso_utc()
        save_state(config.state_path, state)
        result.success = True
        result.overall_status = "ok"
        return result
    except Exception as exc:
        result.overall_status = "degraded" if config.branch == "legislative" else "error"
        if config.branch == "legislative" and not result.discovery_complete:
            # Senate response diagnostics belong in sanitized client logs only.
            # Exception text can include source content/URLs; never export it here.
            result.errors.append(f"{type(exc).__name__}: required discovery incomplete")
        else:
            result.errors.append(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        result.finished_utc = iso_utc()
        # Diagnostic exports are separate from the protected continuity directory.
        try:
            write_latest_csv(config.ledger_path, config.latest_csv_path)
            write_latest_csv(
                config.transactions_path,
                config.latest_transactions_csv_path,
            )
            write_latest_filings_csv(
                config.filings_path,
                config.latest_filings_csv_path,
            )
            if config.branch != "legislative" or result.discovery_complete:
                append_run_history(config.run_history_path, result)
        except Exception as output_exc:  # pragma: no cover - defensive secondary failure path
            LOGGER.exception("Could not finalize tracker reporting outputs")
            result.errors.append(f"ReportingError: {output_exc}")
            result.success = False
            result.overall_status = "degraded" if config.branch == "legislative" else "error"
        write_result(config.result_path, result)
        _write_step_summary(result)


def build_config(args: argparse.Namespace) -> TrackerConfig:
    env = os.environ
    branch = args.branch
    if branch == "legislative":
        default_state = DEFAULT_LEGISLATIVE_STATE
        default_ledger = DEFAULT_LEGISLATIVE_LEDGER
        default_transactions = DEFAULT_LEGISLATIVE_TRANSACTIONS
        default_filings = DEFAULT_LEGISLATIVE_FILINGS
        default_run_history = DEFAULT_LEGISLATIVE_RUN_HISTORY
        default_pending = DEFAULT_LEGISLATIVE_PENDING
        default_result = DEFAULT_LEGISLATIVE_RESULT
        default_csv = DEFAULT_LEGISLATIVE_CSV
        default_transactions_csv = DEFAULT_LEGISLATIVE_TRANSACTIONS_CSV
        default_filings_csv = DEFAULT_LEGISLATIVE_FILINGS_CSV
    else:
        default_state = DEFAULT_EXECUTIVE_STATE
        default_ledger = DEFAULT_EXECUTIVE_LEDGER
        default_transactions = DEFAULT_EXECUTIVE_TRANSACTIONS
        default_filings = DEFAULT_EXECUTIVE_FILINGS
        default_run_history = DEFAULT_EXECUTIVE_RUN_HISTORY
        default_pending = DEFAULT_EXECUTIVE_PENDING
        default_result = DEFAULT_EXECUTIVE_RESULT
        default_csv = DEFAULT_EXECUTIVE_CSV
        default_transactions_csv = DEFAULT_EXECUTIVE_TRANSACTIONS_CSV
        default_filings_csv = DEFAULT_EXECUTIVE_FILINGS_CSV

    user_agent = env.get(
        "DISCLOSURE_USER_AGENT",
        "PolitiTrackGovernmentTradeTracker/1.0 (+https://github.com/maglothinm/MyETF-Intelligence)",
    ).strip()
    if not user_agent:
        raise ValueError("DISCLOSURE_USER_AGENT must not be empty")
    return TrackerConfig(
        branch=branch,
        legislative_source=args.source,
        state_path=Path(args.state_file or env.get("STATE_FILE", default_state)),
        ledger_path=Path(args.ledger_file or env.get("LEDGER_FILE", default_ledger)),
        transactions_path=Path(
            args.transactions_file or env.get("TRANSACTIONS_FILE", default_transactions)
        ),
        filings_path=Path(args.filings_file or env.get("FILINGS_FILE", default_filings)),
        run_history_path=Path(
            args.run_history_file or env.get("RUN_HISTORY_FILE", default_run_history)
        ),
        pending_path=Path(args.pending_file or env.get("PENDING_FILE", default_pending)),
        result_path=Path(args.result_file or env.get("RESULT_FILE", default_result)),
        latest_csv_path=Path(args.latest_csv or env.get("LATEST_CSV", default_csv)),
        latest_transactions_csv_path=Path(
            args.latest_transactions_csv
            or env.get("LATEST_TRANSACTIONS_CSV", default_transactions_csv)
        ),
        latest_filings_csv_path=Path(
            args.latest_filings_csv or env.get("LATEST_FILINGS_CSV", default_filings_csv)
        ),
        oge_listings_path=(
            Path(args.oge_listings_file or env["OGE_LISTINGS_FILE"])
            if (args.oge_listings_file or env.get("OGE_LISTINGS_FILE"))
            else None
        ),
        bootstrap_alerts=(
            args.bootstrap_alerts or parse_bool(env.get("BOOTSTRAP_ALERTS"), default=False)
        ),
        no_notify=args.no_notify,
        senate_lookback_days=int(
            args.senate_lookback_days
            or env.get("SENATE_LOOKBACK_DAYS", DEFAULT_SENATE_LOOKBACK_DAYS)
        ),
        max_download_bytes=int(env.get("MAX_DOWNLOAD_BYTES", DEFAULT_MAX_DOWNLOAD_BYTES)),
        max_ocr_pages=int(env.get("OCR_MAX_PAGES", DEFAULT_MAX_OCR_PAGES)),
        user_agent=user_agent,
        pushover_api_token=env.get("PUSHOVER_API_TOKEN", "").strip(),
        pushover_user_key=env.get("PUSHOVER_USER_KEY", "").strip(),
        require_pushover=parse_bool(env.get("REQUIRE_PUSHOVER"), default=False),
        notify_equity_only=parse_bool(env.get("NOTIFY_EQUITY_ONLY"), default=True),
        notify_pending_reviews=parse_bool(env.get("NOTIFY_PENDING_REVIEWS"), default=True),
        notify_all_filings=parse_bool(env.get("NOTIFY_ALL_FILINGS"), default=False),
        watchlist=parse_watchlist(args.watchlist or env.get("WATCHLIST")),
        allow_empty_sources=parse_bool(env.get("ALLOW_EMPTY_SOURCES"), default=False),
        allow_state_initialization=parse_bool(
            env.get("ALLOW_STATE_INITIALIZATION"), default=False
        ),
        terms_acknowledged=(
            args.acknowledge_terms
            or parse_bool(env.get("DISCLOSURE_TERMS_ACKNOWLEDGED"), default=False)
        ),
        historical_filing_backfill_limit_per_run=max(0, int(
            args.historical_filing_backfill_limit_per_run
            if args.historical_filing_backfill_limit_per_run is not None
            else env.get("HISTORICAL_FILING_BACKFILL_LIMIT_PER_RUN", "20")
        )),
        historical_source_documents_manifest=(
            Path(args.historical_source_documents_manifest or env["HISTORICAL_SOURCE_DOCUMENTS_MANIFEST"])
            if args.historical_source_documents_manifest or env.get("HISTORICAL_SOURCE_DOCUMENTS_MANIFEST")
            else None
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", choices=("legislative", "executive"), required=True)
    parser.add_argument(
        "--source",
        choices=("all", "house", "senate"),
        default="all",
        help="Legislative source to query (default: all)",
    )
    parser.add_argument("--oge-listings-file", help="JSON produced by oge_disclosures.py")
    parser.add_argument("--state-file")
    parser.add_argument("--ledger-file")
    parser.add_argument("--transactions-file")
    parser.add_argument("--filings-file")
    parser.add_argument("--run-history-file")
    parser.add_argument("--pending-file")
    parser.add_argument("--result-file")
    parser.add_argument("--latest-csv")
    parser.add_argument("--latest-transactions-csv")
    parser.add_argument("--latest-filings-csv")
    parser.add_argument("--watchlist", help="Optional comma-separated ticker/company alert filter")
    parser.add_argument("--senate-lookback-days", type=int)
    parser.add_argument("--bootstrap-alerts", action="store_true")
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--acknowledge-terms", action="store_true")
    parser.add_argument("--historical-filing-backfill-limit-per-run", type=int)
    parser.add_argument("--historical-source-documents-manifest")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        config = build_config(args)
        result = run_tracker(config)
    except (MonitorError, ValueError, requests.RequestException) as exc:
        LOGGER.error("Government purchase tracking failed: %s", exc)
        return 1
    except Exception:
        LOGGER.exception("Unexpected government purchase tracking failure")
        return 1
    if not result.success:
        LOGGER.error("Government purchase tracking did not complete successfully")
        return 1
    LOGGER.info(
        "Tracking succeeded: visible=%s new=%s purchases=%s pending=%s",
        result.source_counts,
        result.new_filing_counts,
        result.purchase_counts,
        result.pending_review_counts,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
