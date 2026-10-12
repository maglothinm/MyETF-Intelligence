"""Read-only personal-review projection of committed source OCR outcomes.

These rows are dashboard inventory, not new producer evidence or upload
confirmations. Existing pending-review IDs and personal histories stay intact.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .review_identity import SOURCE_OCR_REVIEW, SOURCE_OCR_UNAVAILABLE


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,120}\Z")
_FILING_FIELDS = ("filing_key", "source", "branch", "report_id", "filer", "title", "agency",
                  "filed_date", "source_url", "access_mode", "document_format", "chamber",
                  "first_seen_utc", "is_synthetic_test", "is_nonproduction", "is_temporary", "test_metadata")
_REVIEW_REASONS = {
    "PaperFilingError": "The document layout could not be parsed reliably.",
    "native_ocr_disagreement": "Extracted text does not agree with the document's text layer.",
    "document_byte_limit": "The document exceeds the permitted file size.",
    "document_page_limit": "The document exceeds the page limit used for this OCR attempt.",
    "upload_confirmation_required": "Uploaded extraction still requires your confirmation.",
    "existing_transaction_conflict": "Extracted transactions conflict with previously retained transactions.",
    "unsupported_scanned_layout": "The scanned document layout is not supported for automatic extraction.",
    "unsupported_confirmation_layout": "This document layout cannot be confirmed through the extraction form.",
    "zero_transactions_needs_review": "The extraction did not produce validated transaction rows.",
    "unreadable_page_needs_review": "One or more pages could not be read reliably.",
    "filer_identity_needs_review": "The extracted filer does not match the retained filing reliably.",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("missing_attempt_identity")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError):
        raise ValueError("missing_attempt_identity") from None


def _content_version(receipt: Mapping[str, Any]) -> tuple[str, Any]:
    """Use retained content evidence, or one identified unknown-byte attempt.

    Revalidation dates and source_checked_at are intentionally excluded. A new
    unknown-byte attempt cannot inherit acknowledgement of an older attempt.
    """
    values = []
    if receipt.get("sha256") not in (None, ""):
        values.append(receipt["sha256"])
    evidence = receipt.get("evidence")
    if evidence is not None and not isinstance(evidence, Mapping):
        raise ValueError("incomplete_document_identity")
    if evidence:
        if not evidence.get("sha256"):
            raise ValueError("incomplete_document_identity")
        values.append(evidence["sha256"])
    outcome = receipt.get("upload_outcome")
    if outcome is not None and not isinstance(outcome, Mapping):
        raise ValueError("conflicting_upload_identity")
    if outcome:
        if (not isinstance(receipt.get("upload_id"), str) or not receipt["upload_id"].strip()
                or outcome.get("upload_id") != receipt["upload_id"]):
            raise ValueError("conflicting_upload_identity")
        if outcome.get("sha256") not in (None, ""):
            values.append(outcome["sha256"])
    if values:
        if any(not isinstance(value, str) or not _DIGEST.fullmatch(value) for value in values):
            raise ValueError("invalid_document_identity")
        if len(set(values)) != 1:
            raise ValueError("conflicting_document_identity")
        return "sha256", values[0]
    attempted_at = _timestamp(receipt.get("attempted_at"))
    attempts, version, origin = receipt.get("attempts"), receipt.get("version"), receipt.get("origin")
    if (type(attempts) is not int or attempts < 1 or not isinstance(version, str)
            or not _CODE.fullmatch(version) or not isinstance(origin, str) or origin not in {"official_download", "user_upload"}
            or (origin == "user_upload" and (not isinstance(receipt.get("upload_id"), str)
                                             or not receipt["upload_id"].strip()))):
        raise ValueError("missing_attempt_identity")
    return "receipt-v1", [receipt.get("source_url"), version, origin, attempted_at,
                           attempts, receipt.get("upload_id") or ""]


def project_source_ocr_reviews(
    filings: Sequence[Mapping[str, Any]], receipts: Mapping[str, Mapping[str, Any]], branch: str,
) -> list[dict[str, Any]]:
    """Project latest needs-review receipts with exact retained filing identity.

    Incomplete or contradictory receipt identities remain visible as Other
    review inventory, without an acknowledgement action. No source files change.
    """
    if branch not in {"legislative", "executive"}:
        return []
    counts = Counter(row.get("filing_key") for row in filings if isinstance(row.get("filing_key"), str))
    result = []
    for filing in filings:
        key, source = filing.get("filing_key"), filing.get("source")
        if (not isinstance(key, str) or not key or counts[key] != 1
                or not isinstance(source, str) or source not in {"house", "senate", "oge"} or filing.get("branch") != branch
                or (source == "oge") != (branch == "executive")):
            continue
        receipt = receipts.get(key)
        if not isinstance(receipt, Mapping) or receipt.get("status") != "needs_review":
            continue
        code = receipt.get("error_code")
        row = {field: filing[field] for field in _FILING_FIELDS if field in filing}
        row.update(review_kind="source_ocr", ocr_status="needs_review", ocr_error_code=code,
                   observed_at_utc=receipt.get("attempted_at"), filing_status=filing.get("status"))
        try:
            if (receipt.get("filing_key") != key or not isinstance(filing.get("source_url"), str) or not filing["source_url"]
                    or not isinstance(receipt.get("source_url"), str)
                    or receipt.get("source_url") != filing["source_url"]):
                raise ValueError("source_document_changed")
            if not isinstance(code, str) or not _CODE.fullmatch(code):
                raise ValueError("missing_review_reason_identity")
            version_kind, version = _content_version(receipt)
            identity = _digest(["source-ocr-review-v1", source, "filing_key", key, code, version_kind, version])[:32]
            row.update(review_id="review:source-ocr:" + identity,
                       logical_review_id="review-logical-v1:" + identity,
                       exception_code=SOURCE_OCR_REVIEW, review_identity_status="available",
                       ocr_review_version_kind=version_kind,
                       reason="Source OCR review: " + _REVIEW_REASONS.get(code, code.replace("_", " ") + "."))
            if version_kind == "sha256":
                row["ocr_document_sha256"] = version
            else:
                row["reason"] += " Document bytes are unverified; acknowledgement applies to this recorded attempt."
        except ValueError as error:
            # Do not put a guessed identity into the API's manual-exception map.
            # This ID locates unavailable evidence only and is not acknowledgeable.
            identity = _digest(["source-ocr-unavailable-v1", key, receipt])[:32]
            row.update(review_id="review:source-ocr-unavailable:" + identity,
                       logical_review_id="review-unavailable-v1:" + identity,
                       exception_code=SOURCE_OCR_UNAVAILABLE, review_identity_status="unavailable",
                       reason="Source OCR needs review, but its document identity cannot be verified for acknowledgement ("
                              + str(error).replace("_", " ") + ").")
        result.append(row)
    return result
