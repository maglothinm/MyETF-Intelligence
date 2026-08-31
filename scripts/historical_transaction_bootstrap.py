"""Bounded, silent reconstruction of transactions for retained catalog-only filings.

This runs inside the existing tracker writer after normal discovery/processing. It
does not initialize state, discover filings, send alerts, or modify prior records.
The optional source-document manifest is a read-only bridge to original cached or
vaulted PDF/HTML bytes, not an alternative authority for tracker state.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

try:
    from . import government_trade_tracker as tracker
except ImportError:  # pragma: no cover - direct tracker execution
    import government_trade_tracker as tracker  # type: ignore


TERMINAL_STATUSES = {"complete", "review_required", "invalid_public_date", "invalid_cached_document", "cached_report_rejected"}


def _official_url(source: str, value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    suffix = {"house": "house.gov", "senate": "senate.gov", "oge": "oge.gov"}.get(source)
    return bool(suffix and parsed.scheme == "https" and not parsed.username and not parsed.password
                and (host == suffix or host.endswith("." + suffix)))


def _original_observation(row: Mapping[str, Any], state: tracker.TrackerState) -> str:
    # Never use the bootstrap clock as public-observation time. A valid original
    # first_seen is authoritative; a retained seen timestamp is the next fallback.
    values = [row.get("first_seen_utc"),
              state.seen_filings.get(str(row.get("source")), {}).get(str(row.get("report_id"))),
              row.get("filed_date")]
    for value in values:
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed > datetime.now(timezone.utc):
            continue
        return str(value)
    return ""


def _manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["documents"]
        if not isinstance(rows, list):
            raise ValueError("documents is not an array")
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict) or not row.get("filing_key"):
                raise ValueError("invalid document entry")
            key = str(row["filing_key"])
            if key in result:
                raise ValueError("ambiguous document entry")
            result[key] = row
        return result
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise tracker.MonitorError("Historical source-document manifest is invalid") from exc


def _cached_document(
    row: Mapping[str, Any], entry: Mapping[str, Any], manifest_path: Path, max_bytes: int,
) -> tuple[bytes, str]:
    root = manifest_path.parent.resolve()
    relative = Path(str(entry.get("path") or ""))
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root) or not relative.parts:
        raise ValueError("invalid cached path")
    if entry.get("source_url") != row.get("source_url") or entry.get("filing_key") != row.get("filing_key"):
        raise ValueError("cached document identity mismatch")
    if path.stat().st_size > max_bytes:
        raise ValueError("cached document exceeds byte limit")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != str(entry.get("sha256") or "").lower():
        raise ValueError("cached document hash mismatch")
    document_format = str(entry.get("format") or "").lower()
    if document_format == "pdf" and data.startswith(b"%PDF"):
        return data, document_format
    if document_format == "html" and str(row.get("source")) == "senate" and b"<" in data[:100]:
        return data, document_format
    raise ValueError("cached document is not an original supported PDF/HTML document")


def _report(row: Mapping[str, Any]) -> tracker.Report | dict[str, Any]:
    if row.get("source") == "oge":
        return {"listing_id": row["report_id"], "name": row.get("filer", ""),
                "date": row.get("filed_date", ""), "document_url": row.get("source_url", ""),
                "access_mode": row.get("access_mode", ""), "title": row.get("title", ""),
                "agency": row.get("agency", "")}
    return tracker.Report(report_id=str(row["report_id"]), source=str(row["source"]),
                          filer=str(row.get("filer", "")), filed_date=str(row.get("filed_date", "")),
                          url=str(row.get("source_url", "")), format=str(row.get("document_format", "")),
                          metadata={key: str(row.get(key, ""))
                                    for key in ("title", "agency", "district", "report_type")})


class _CachedDocumentSession:
    """Serve one hash-verified original document; never make a network request."""

    def __init__(self, url: str, data: bytes, document_format: str):
        self.url = url
        self.response = requests.Response()
        self.response.status_code = 200
        self.response.url = url
        self.response.encoding = "utf-8"
        self.response.headers["Content-Type"] = "application/pdf" if document_format == "pdf" else "text/html"
        self.response._content = data
        self.response._content_consumed = True

    def get(self, url: str, **_kwargs: Any) -> requests.Response:
        if url != self.url:
            raise tracker.MonitorError("Cached document requires an uncached linked document")
        return self.response


class _CachedSenateClient(tracker.SenateClient):
    """Reuse all Senate report validation, replacing only transport with a cache."""

    def __init__(self, document: _CachedDocumentSession):
        super().__init__()
        self.document = document

    def _perform(self, request: Any) -> Any:
        # An already legitimately retrieved artifact needs no new network terms
        # handshake; the enclosing tracker still requires acknowledged terms.
        return request()

    def _request(self, stage: str, method: str, url: str, **_kwargs: Any) -> requests.Response:
        if method != "GET":
            raise tracker.SenateInvalidResponse("report", "unsupported_cached_request")
        return self.document.get(url)


def _parse_cached(
    row: Mapping[str, Any], report: tracker.Report | dict[str, Any], data: bytes,
    document_format: str, config: tracker.TrackerConfig,
) -> tuple[list[tracker.Trade], tracker.PendingReview | None]:
    session = _CachedDocumentSession(str(row["source_url"]), data, document_format)
    if row["source"] == "senate":
        with _CachedSenateClient(session) as senate:
            return tracker.scan_senate_report(senate, report, config)
    if row["source"] == "house":
        return tracker.scan_house_report(session, report, config)
    # This does not request an access-restricted URL: the adapter can return only
    # the original bytes explicitly supplied under this exact filing identity.
    return tracker.scan_oge_listing(session, {**report, "access_mode": "direct"}, config)


def run_historical_transaction_backfill(
    *, config: tracker.TrackerConfig, state: tracker.TrackerState,
    result: tracker.TrackerResult, session: requests.Session,
    filing_index: dict[str, dict[str, Any]], senate_client: Any = None,
) -> dict[str, Any]:
    """Append at most the configured number of retained filing outcomes, silently.

    Callers must have restored the complete provenance-valid tracker artifact and
    completed required discovery first. The function additionally requires an
    existing on-disk state and seen filing identity; it never creates a baseline.
    ``historical-source-documents.json`` (or the configured manifest) has a
    ``documents`` array of ``filing_key, source_url, path, sha256, format`` entries.
    Paths are relative to that manifest; raw bytes must match the exact source.
    """
    if not config.state_path.exists() or not config.terms_acknowledged:
        raise tracker.MonitorError("Historical transaction backfill requires restored state and acknowledged terms")
    limit = max(0, config.historical_filing_backfill_limit_per_run)
    receipt_path = config.state_path.parent / "historical-backfill.jsonl"
    manifest_path = config.historical_source_documents_manifest or config.state_path.parent / "historical-source-documents.json"
    cached = _manifest(manifest_path)
    receipts = tracker.latest_records(receipt_path, "filing_key")
    existing_transactions = tracker.read_jsonl(config.transactions_path)
    transaction_ids = {str(row.get("trade_id")) for row in existing_transactions if row.get("trade_id")}
    purchase_ids = {str(row.get("trade_id")) for row in tracker.read_jsonl(config.ledger_path) if row.get("trade_id")}
    represented_filings = {tracker.filing_key(str(row.get("source")), str(row.get("report_id")))
                           for row in existing_transactions}
    allowed_sources = set(tracker._selected_legislative_sources(config.legislative_source)) if config.branch == "legislative" else {"oge"}
    blocked: Counter[str] = Counter()
    candidates: list[tuple[dict[str, Any], str]] = []
    cataloged_count = 0
    for key, row in filing_index.items():
        if (row.get("branch") != config.branch or row.get("source") not in allowed_sources
                or row.get("status") != "cataloged" or key in represented_filings):
            continue
        cataloged_count += 1
        source, report_id = str(row.get("source")), str(row.get("report_id"))
        if report_id not in state.seen_filings.get(source, {}):
            blocked["missing_seen_filing"] += 1
            continue
        if not _official_url(source, str(row.get("source_url", ""))):
            blocked["non_official_source"] += 1
            continue
        if source == "oge" and row.get("access_mode") != "direct" and key not in cached:
            blocked["access_required"] += 1
            continue
        fingerprint = hashlib.sha256(json.dumps({"source_url": row.get("source_url"),
                                                "first_seen_utc": row.get("first_seen_utc"),
                                                "retained_seen_utc": state.seen_filings[source][report_id],
                                                "filed_date": row.get("filed_date"),
                                                "cache": cached.get(key)}, sort_keys=True).encode()).hexdigest()
        receipt = receipts.get(key, {})
        if receipt.get("status") in TERMINAL_STATUSES and receipt.get("input_fingerprint") == fingerprint:
            if receipt.get("status") != "complete":
                blocked[str(receipt["status"])] += 1
            continue
        candidates.append((row, fingerprint))
    # Previously unattempted filings always get a turn before a retry. Stable
    # latest-first discovery is deterministic; no failing filing owns the queue.
    candidates.sort(key=lambda item: (str(item[0].get("filed_date", "")), str(item[0]["filing_key"])), reverse=True)
    candidates.sort(key=lambda item: str(receipts.get(str(item[0]["filing_key"]), {}).get("attempted_at_utc", "")))
    metrics: dict[str, Any] = {"limit_per_run": limit, "cataloged_without_transactions": cataloged_count,
                               "attempted_this_run": 0, "completed_this_run": 0, "transactions_appended": 0,
                               "cache_hits_this_run": 0, "pending_filing_count": len(candidates),
                               "blocked_filing_counts": dict(blocked)}
    for row, fingerprint in candidates[:limit]:
        key = str(row["filing_key"])
        receipt: dict[str, Any] = {"filing_key": key, "source": row["source"], "report_id": row["report_id"],
                                  "attempted_at_utc": tracker.iso_utc(), "historical_bootstrap": True,
                                  "input_fingerprint": fingerprint, "status": "retryable_error", "transaction_count": 0}
        metrics["attempted_this_run"] += 1
        observation = _original_observation(row, state)
        try:
            if not observation:
                receipt["status"] = "invalid_public_date"
            else:
                report = _report(row)
                if key in cached:
                    try:
                        data, document_format = _cached_document(row, cached[key], manifest_path, config.max_download_bytes)
                    except (OSError, ValueError):
                        receipt["status"] = "invalid_cached_document"
                        raise tracker.MonitorError("invalid_cached_document") from None
                    metrics["cache_hits_this_run"] += 1
                    trades, review = _parse_cached(row, report, data, document_format, config)
                elif row["source"] == "house":
                    trades, review = tracker.scan_house_report(session, report, config)
                elif row["source"] == "senate":
                    if senate_client is None:
                        raise tracker.MonitorError("Senate historical access requires the existing validated client")
                    trades, review = tracker.scan_senate_report(senate_client, report, config)
                else:
                    trades, review = tracker.scan_oge_listing(session, report, config)
                if review:
                    receipt["status"] = "review_required"
                    receipt["reason"] = "paper_or_access_requires_review"
                else:
                    # Retain parser IDs and row fields; only observation provenance
                    # changes from parsing-clock time to original catalog time.
                    trades = [replace(trade, observed_at_utc=observation) for trade in trades]
                    normalized = [{**asdict(trade), "historical_bootstrap": True,
                                   "historical_backfilled_at_utc": receipt["attempted_at_utc"]} for trade in trades]
                    new_by_id = {trade["trade_id"]: trade for trade in reversed(normalized)
                                 if trade["trade_id"] not in transaction_ids}
                    new_rows = list(new_by_id.values())
                    tracker.append_jsonl(config.transactions_path, new_rows)
                    new_purchases = {trade["trade_id"]: trade for trade in reversed(normalized)
                                     if trade["transaction_type"] == "Purchase" and trade["trade_id"] not in purchase_ids}
                    tracker.append_jsonl(config.ledger_path, new_purchases.values())
                    purchase_ids.update(new_purchases)
                    for trade in new_rows:
                        transaction_ids.add(trade["trade_id"])
                        state.seen_trades.setdefault(trade["trade_id"], observation)
                    filing_record = tracker.make_filing_record(report, branch=config.branch, source=str(row["source"]),
                                                               status="processed", first_seen_utc=str(row.get("first_seen_utc") or observation),
                                                               transactions=trades)
                    parsed_fields = asdict(filing_record)
                    # An additive outcome must not erase original catalog fields,
                    # optional future metadata, or the first public-observation time.
                    historical_filing = {**row, **{field: parsed_fields[field] for field in (
                        "status", "updated_at_utc", "transaction_count", "purchase_count", "sale_count",
                        "exchange_count", "review_reason")}, "historical_bootstrap": True}
                    tracker.append_jsonl(config.filings_path, [historical_filing])
                    filing_index[key] = historical_filing
                    receipt.update(status="complete", transaction_count=len(trades), transactions_appended=len(new_rows))
                    metrics["completed_this_run"] += 1
                    metrics["transactions_appended"] += len(new_rows)
        except tracker.PaperFilingError:
            receipt["status"] = "review_required"
            receipt["reason"] = "paper_or_unparseable_document"
        except tracker.SenateAccessDenied:
            receipt["reason"] = "official_access_unavailable"
        except tracker.SenateInvalidResponse:
            receipt["reason"] = "official_report_validation_failed"
            if key in cached:
                receipt["status"] = "cached_report_rejected"
        except tracker.SourceChangedError:
            receipt["reason"] = "transaction_parser_rejected_document"
        except requests.RequestException:
            receipt["reason"] = "official_document_request_failed"
        except (tracker.MonitorError, ValueError, UnicodeError):
            # Raw report content, credentials and access errors never enter the
            # receipt. A retry remains pending; official client rules still apply.
            receipt["reason"] = "invalid_cached_document" if receipt["status"] == "invalid_cached_document" else "document_processing_failed"
        tracker.append_jsonl(receipt_path, [receipt])
        if receipt["status"] != "retryable_error":
            metrics["pending_filing_count"] -= 1
        if receipt["status"] not in {"complete", "retryable_error"}:
            blocked[str(receipt["status"])] += 1
    metrics["blocked_filing_counts"] = dict(sorted(blocked.items()))
    result.historical_backfill = metrics
    return metrics
