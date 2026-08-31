"""Read-only filing evidence projection; never modifies the tracker ledgers."""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

CATALOG_FIELDS = frozenset({
    "filing_key", "filing_id", "external_filing_id", "report_id", "filer_id", "politician_id",
    "filer", "filer_name", "source", "branch", "report_type", "filing_type", "document_type",
    "filed_date", "filing_date", "report_period", "source_url", "official_source_url",
    "document_url", "document_format", "agency", "title", "district", "chamber",
    "access_mode", "access_class", "access_method", "requires_request", "access_required", "status",
    "is_amended", "supersedes_filing_id", "superseded_by_filing_id",
    "is_synthetic_test", "is_simulation", "is_temporary",
})
SOURCE_FIELDS = frozenset({
    "document_id", "report_id", "report_year", "filing_year", "report_type", "access_mode",
    "access_method", "document_url", "validation_scope", "checked_at", "etag", "last_modified",
    "resolved_document_url", "source_http_status", "validated_document_sha256",
})


def api_origin(value: str) -> str:
    """Only an explicit HTTPS origin (or loopback development origin) is allowed."""
    if not value:
        return ""
    url = urlsplit(value)
    port = url.port  # Reject malformed and out-of-range ports before CSP output.
    if (url.username or url.password or url.query or url.fragment
            or not re.fullmatch(r"https?://(?:[a-zA-Z0-9.-]+|\[::1\])(?::[0-9]+)?/?", value)
            or port == 0
            or url.path not in ("", "/") or not url.hostname
            or (url.scheme != "https" and not (
                url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "[::1]", "::1"}))):
        raise ValueError("FILING_VAULT_API_ORIGIN must be an HTTPS origin, without a path")
    return value.rstrip("/")


def filing_catalog(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Export known IDs and retained metadata, not cached documents or access grants."""
    rows = []
    for original in payload.get("filings", []):
        key = str(original.get("filing_key") or "")
        if not key:
            continue
        row = {key: value for key, value in original.items()
               if key in CATALOG_FIELDS and isinstance(value, (str, int, float, bool, type(None)))}
        for field in ("metadata", "source_metadata"):
            values = original.get(field)
            if isinstance(values, dict):
                row[field] = {key: value for key, value in values.items()
                              if key in SOURCE_FIELDS and isinstance(value, (str, int, float, bool, type(None)))}
        row["filing_id"] = key
        # Access-required and TEST flags stay intact for the server importer.
        rows.append(row)
    return {"schema_version": 1, "repository_id": 1349678672,
            "generated_at": payload.get("summary", {}).get("generated_utc"),
            "filings": rows}


def attach_filing_ids(value: Any, catalog: Mapping[str, Any]) -> Any:
    """Attach only unique, consistent matches; never guess a source from a ticker."""
    by_key = {r["filing_id"]: r for r in catalog["filings"]}
    by_url: dict[str, list[dict]] = defaultdict(list)
    by_report: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in by_key.values():
        if row.get("source_url"):
            by_url[str(row["source_url"])].append(row)
        if row.get("source") and row.get("report_id"):
            by_report[(str(row["source"]), str(row["report_id"]))].append(row)

    def visit(item: Any) -> Any:
        if isinstance(item, list):
            return [visit(v) for v in item]
        if not isinstance(item, dict):
            return item
        result = {k: visit(v) for k, v in item.items()}
        key = str(item.get("filing_key") or item.get("filing_id") or "")
        url = str(item.get("source_url") or "")
        source, report = str(item.get("source") or ""), str(item.get("report_id") or "")
        candidates = ([by_key[key]] if key in by_key else []) if key else by_report.get((source, report), [])
        if not candidates and not key:
            candidates = by_url.get(url, []) if url else []
        if len(candidates) == 1:
            candidate = candidates[0]
            if all(not item.get(field) or not candidate.get(field) or
                   str(item[field]) == str(candidate[field])
                   for field in ("source_url", "report_id", "source")):
                result["filing_id"] = candidate["filing_id"]
        return result
    return visit(value)
