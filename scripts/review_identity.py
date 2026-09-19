"""Stable parser-exception identity, shared by ingestion and publication.

Legacy evidence IDs are never rewritten. Only known historical parser messages
are classified here; unknown legacy records keep their individual evidence ID
until a producer supplies an explicit code. Display wording is not hash material.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


PAPER_REVIEW = "paper_filing_manual_review"
UNPARSEABLE_TABLE = "unparseable_transaction_table"
ACCESS_REQUIRED = "disclosure_access_required"
PARSER_CODES = frozenset({PAPER_REVIEW, UNPARSEABLE_TABLE,
                          "missing_required_transaction_fields", "unsupported_disclosure_format"})


def exception_code(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("exception_code") or "").strip()
    if explicit:
        return explicit
    # Compatibility for the exact families emitted before structured codes.
    reason = " ".join(str(row.get("reason") or row.get("review_reason") or "").split()).casefold()
    if "does not preserve enough row structure" in reason:
        return UNPARSEABLE_TABLE
    if ("paper/scanned ptr" in reason or "paper ptr is rendered as page images" in reason
            or "paper filing" in reason or "paper-format filing" in reason):
        return PAPER_REVIEW
    if "oge form 201 request" in reason:
        return ACCESS_REQUIRED
    return ""


def logical_review_id(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("logical_review_id") or "").strip()
    if explicit:
        return explicit
    code = exception_code(row)
    source = str(row.get("source") or "").strip().casefold()
    # Tag the namespace: a URL and a report ID with identical text are distinct.
    identity = next(((field, str(row[field]).strip())
                     for field in ("report_id", "filing_key", "source_record_id", "source_url")
                     if str(row.get(field) or "").strip()), None)
    if not source or not identity or not code:
        return str(row.get("review_id") or "")
    material = json.dumps([source, *identity, code], ensure_ascii=False, separators=(",", ":"))
    return "review-logical-v1:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
