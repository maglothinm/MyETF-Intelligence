"""Conservative OGE 278-T row parsing with independent native/OCR agreement.

This module never downloads, writes state, infers owners/tickers, or sends alerts.
Only a recognized numbered table is accepted. Ambiguous trailing asset fragments,
missing rows/pages/headers and any text disagreement leave the whole filing in review.
"""
from __future__ import annotations

import re
from datetime import datetime

PARSER_VERSION = "oge-278t-table-v1"


class OGETableError(ValueError):
    """Safe diagnostic code without source text."""


HEADER = re.compile(
    r"#\s+DESCRIPTION\s+TYPE\s+DATE\s+NOTIFICATION\s+"
    r"(?:AMOUNT\s+RECEIVED\s+OVER\s+30\s+DAYS\s+AGO|"
    r"RECEIVED\s+OVER\s+30\s+DAYS\s+AGO\s+AMOUNT)",
    re.IGNORECASE,
)
FORM = re.compile(r"OGE\s+Form\s+278\s*[-–]\s*T\b", re.IGNORECASE)
OPTICAL_HEADER = re.compile(HEADER.pattern.replace(r"#\s+", r"(?:#\s+)?", 1), re.IGNORECASE)
ROW_START = re.compile(r"(?m)^[ \t]*(\d{1,4})(?:[ \t]+|\r?\n)")
STOP = re.compile(r"(?im)^[ \t]*(Endnotes|Summary of Contents|Privacy Act Statement)\s*$")
FOOTER = re.compile(r"(?m)^[^\n]{1,160} - Page \d+[ \t]*$")
ROW = re.compile(
    r"(?P<asset>.+?)\s+(?P<type>Purchase|Sale(?:\s*\((?:Partial|Full)\))?|Exchange)"
    r"\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<late>Yes|No)"
    r"\s+(?P<amount>\$[\d,]+\s*[-–—]\s*\$[\d,]+|Over\s+\$[\d,]+)",
    re.IGNORECASE,
)
RANGES = {
    (1001, 15000), (15001, 50000), (50001, 100000), (100001, 250000),
    (250001, 500000), (500001, 1000000), (1000001, 5000000),
    (5000001, 25000000), (25000001, 50000000),
}
AMOUNT_END = re.compile(r"\$[\d,]+\s*[-–—]\s*\$[\d,]+|Over\s+\$[\d,]+", re.IGNORECASE)
OPTICAL_REORDERED_ROW = re.compile(
    r"(?P<type>Purchase|Sale(?:\s*\((?:Partial|Full)\))?|Exchange)"
    r"\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+(?P<late>Yes|No)"
    r"\s+(?P<asset>.+?)\s+(?P<amount>\$[\d,]+\s*[-–—]\s*\$[\d,]+|Over\s+\$[\d,]+)",
    re.IGNORECASE,
)


def _space(value):
    return " ".join(value.split())


def _amount(value):
    if value.lower().startswith("over"):
        if int(re.sub(r"\D", "", value)) != 50000000:
            raise OGETableError("oge_amount_needs_review")
        return "Over $50,000,000"
    low, high = (int(re.sub(r"\D", "", part)) for part in re.split(r"[-–—]", value))
    if (low, high) not in RANGES:
        raise OGETableError("oge_amount_needs_review")
    return f"${low:,} - ${high:,}"


def _rows(pages, *, optical=False):
    if not FORM.search("\n".join(pages)):
        raise OGETableError("oge_unsupported_form")
    rows = []
    ended = False
    for page_number, page in enumerate(pages, 1):
        headers = list((OPTICAL_HEADER if optical else HEADER).finditer(page))
        if not headers:
            # A later page with transaction fields but no recognized header
            # cannot be omitted while earlier pages are accepted.
            if re.search(r"\b(?:Purchase|Sale|Exchange)\s+\d{1,2}/\d{1,2}/\d{4}", page, re.I):
                raise OGETableError("oge_table_header_missing")
            continue
        if ended or len(headers) != 1:
            raise OGETableError("oge_table_boundary_needs_review")
        table = page[headers[0].end():]
        stop = STOP.search(table)
        if stop:
            table = table[:stop.start()]
            ended = True
        footer = FOOTER.search(table)
        if footer:
            if table[footer.end():].strip():
                raise OGETableError("oge_table_boundary_needs_review")
            table = table[:footer.start()]
        markers = list(ROW_START.finditer(table))
        chunks = []
        if not markers and optical:
            # Tesseract's sparse-text mode can omit the narrow row-number
            # column. Accept only complete amount-terminated field groups in
            # order; the independent native parse must still supply every
            # sequential row number and agree on all fields and row counts.
            start = 0
            for amount in AMOUNT_END.finditer(table):
                chunks.append((len(rows) + len(chunks) + 1, table[start:amount.end()]))
                start = amount.end()
            if table[start:].strip() or not chunks:
                raise OGETableError("oge_table_rows_needs_review")
        else:
            if not markers or table[:markers[0].start()].strip():
                raise OGETableError("oge_table_rows_needs_review")
            for index, marker in enumerate(markers):
                end = markers[index + 1].start() if index + 1 < len(markers) else len(table)
                chunks.append((int(marker.group(1)), table[marker.end():end]))
        for number, content in chunks:
            if number != len(rows) + 1:
                raise OGETableError("oge_table_row_sequence")
            value = _space(content)
            match = ROW.fullmatch(value)
            if match is None and optical:
                match = OPTICAL_REORDERED_ROW.fullmatch(value)
            if not match:
                raise OGETableError("oge_table_rows_needs_review")
            asset = _space(match["asset"])
            if not asset or len(asset) > 3000 or re.search(
                r"\b(?:DESCRIPTION|NOTIFICATION|RECEIVED OVER|ENDNOTES)\b| - Page \d+", asset, re.I
            ):
                raise OGETableError("oge_asset_needs_review")
            try:
                date = datetime.strptime(match["date"], "%m/%d/%Y").date().isoformat()
            except ValueError:
                raise OGETableError("oge_date_needs_review") from None
            kind = _space(match["type"]).lower()
            kind = {"purchase": "Purchase", "sale": "Sale", "sale (partial)": "Sale (Partial)",
                    "sale (full)": "Sale (Full)", "exchange": "Exchange"}.get(kind)
            if kind is None:
                raise OGETableError("oge_type_needs_review")
            rows.append({"page": page_number, "row": number, "asset": asset,
                         "transaction_type": kind, "transaction_date": date,
                         "notification_over_30_days": match["late"].lower() == "yes",
                         "notification_date": "", "owner": "", "amount": _amount(match["amount"])})
    if not rows:
        raise OGETableError("oge_table_rows_needs_review")
    return rows


def parse_verified_oge(native_pages, ocr_text):
    """Return whole-document rows only when two independent extractions agree."""
    if (not isinstance(native_pages, list) or not native_pages
            or not all(isinstance(page, str) for page in native_pages)
            or not isinstance(ocr_text, str)):
        raise OGETableError("oge_extraction_needs_review")
    optical_pages = ocr_text.split("\f")
    if len(native_pages) != len(optical_pages):
        raise OGETableError("oge_page_coverage_disagreement")
    native, optical = _rows(native_pages), _rows(optical_pages, optical=True)
    if native != optical:
        raise OGETableError("native_ocr_disagreement")
    return native
