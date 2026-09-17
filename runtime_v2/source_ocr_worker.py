"""OCR maintenance inside the existing source producer and snapshot transaction.

No schedule, state bootstrap, notification delivery, or parallel canonical writer.
A failed snapshot cannot acknowledge an upload; replay uses committed receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

from scripts import government_trade_tracker as tracker
from scripts.historical_transaction_bootstrap import _original_observation, _report
from scripts.source_ocr import VERSION, MAX_BYTES, MAX_PAGES, OCRError, extract, now


class OfficialSession(requests.Session):
    """Narrow official-host GET transport; redirects are validated before use."""
    def __init__(self, source):
        super().__init__()
        self.source = source
        self.trust_env = False

    def get(self, url, **kwargs):
        suffix = {"house": "house.gov", "oge": "oge.gov"}[self.source]
        for _ in range(4):
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
            if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443}
                or not (host == suffix or host.endswith("." + suffix))):
                raise OCRError("non_official_document_url")
            response = super().get(url, **{**kwargs, "allow_redirects": False, "stream": True})
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location", "")
                response.close()
                url = urljoin(url, location)
                continue
            if response.status_code in {401, 403}:
                response.close()
                raise OCRError("access_required")
            return response
        raise OCRError("redirect_limit")


def download(filing, config):
    source, report = filing["source"], _report(filing)
    if source == "senate":
        # Existing session/terms and report-response validation are mandatory.
        with tracker.SenateClient() as client:
            response = tracker._senate_page_response(client, report)
            data = tracker.response_bytes(response, "OCR Senate report", MAX_BYTES, safe_diagnostics=True)
            if data.startswith(b"%PDF") or report.format == "pdf":
                return tracker._core._senate_pdf_from_viewer(client, response, data, config)[0]
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(data, "html.parser")
            if soup.find(["img", "iframe", "embed"]):
                raise OCRError("page_image_download_requires_review")
            raise OCRError("native_html_not_applicable")
    if source == "oge" and filing.get("access_mode") != "direct":
        raise OCRError("access_required")
    with OfficialSession(source) as session:
        session.headers["User-Agent"] = config.user_agent
        if source == "oge":
            data = tracker.resolve_oge_pdf(session, report, config)
            if data is None:
                raise OCRError("access_required")
            return data
        response = session.get(filing["source_url"], timeout=(10, 30))
        try:
            response.raise_for_status()
            chunks, total = [], 0
            for chunk in response.iter_content(64 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise OCRError("document_byte_limit")
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.startswith(b"%PDF"):
                raise OCRError("direct_file_unavailable")
            return data
        finally:
            response.close()


def _configuration(directory, branch, environment):
    args = tracker.build_parser().parse_args(["--branch", branch, "--state-file", str(directory / "state.json"), "--no-notify"])
    config = tracker.build_config(args)
    return replace(config, state_path=directory / "state.json", transactions_path=directory / "transactions.jsonl",
                   filings_path=directory / "filings.jsonl", pending_path=directory / "pending-review.jsonl",
                   ledger_path=directory / "purchases.jsonl", max_download_bytes=MAX_BYTES, max_ocr_pages=MAX_PAGES,
                   terms_acknowledged=str(environment.get("DISCLOSURE_TERMS_ACKNOWLEDGED", "")).lower() in {"true", "1", "yes"})


def _matching_filer(filing, evidence):
    words = re.findall(r"[a-z]+", evidence.get("ocr_text", "").lower())
    tokens = [token for token in re.findall(r"[a-z]+", filing.get("filer", "").lower())
              if token not in {"hon", "honorable", "jr", "sr", "iii", "iv"} and len(token) > 1]
    return len(tokens) >= 2 and all(token in words for token in tokens)


def _paper_trades(filing, evidence, rows):
    trades = []
    for row in rows:
        trade = tracker.make_trade(branch=filing["branch"], source=filing["source"], report=_report(filing),
            owner=row.get("owner", ""), asset=row["asset"], ticker="", asset_type="",
            transaction_type=row["transaction_type"], transaction_date=row["transaction_date"],
            notification_date=row["notification_date"], amount=row["amount"],
            raw_row=json.dumps({"sha256": evidence["sha256"], "page": row["page"], "row": row["row"],
                                "asset_as_read": row["asset"]}, sort_keys=True), confidence="medium")
        # Physical row identity preserves two genuinely identical-looking rows.
        identifier = tracker.stable_id("ocr-trade", (filing["filing_key"], evidence["sha256"], str(row["page"]), str(row["row"])))
        trades.append(replace(trade, trade_id=identifier, owner=row.get("owner", ""), ticker="", equity_like=False))
    return trades


def _parse(filing, evidence, approved_rows=None):
    table = evidence["house_table"]
    if approved_rows is not None:
        if filing["source"] != "house" or not table["recognized"] or table["problems"]:
            raise OCRError("unsupported_confirmation_layout")
        if not _matching_filer(filing, evidence):
            raise OCRError("filer_identity_needs_review")
        return _paper_trades(filing, evidence, approved_rows)
    if table["recognized"] and filing["source"] == "house":
        if not _matching_filer(filing, evidence) or table["problems"] or any(row["issues"] for row in table["rows"]):
            raise OCRError("table_needs_review")
        return _paper_trades(filing, evidence, table["rows"])
    text = "\n".join(evidence["native_pages"]).strip()
    parser = lambda value: tracker.parse_house_transactions(value, _report(filing)) if filing["source"] == "house" else tracker.parse_generic_transactions_text(
        value, _report(filing), branch=filing["branch"], source=filing["source"], paper_is_pending=True)
    # Always OCR, but native text remains authoritative for electronic forms.
    # OCR-only generic output is not accepted without validated layout semantics.
    if not text:
        raise OCRError("unsupported_scanned_layout")
    native = parser(text)
    try:
        optical = parser(evidence["ocr_text"])
        signature = lambda trades: sorted((t.asset, t.transaction_type, t.transaction_date, t.amount) for t in trades)
        if signature(native) != signature(optical):
            raise OCRError("native_ocr_disagreement")
    except Exception:
        raise OCRError("native_ocr_disagreement") from None
    return native


def _import(directory, filing, trades, evidence, origin):
    state, missing_state = tracker.load_state(directory / "state.json")
    observation = _original_observation(filing, state)
    if not observation:
        raise OCRError("missing_original_observation")
    existing = tracker.read_jsonl(directory / "transactions.jsonl") + tracker.read_jsonl(directory / "purchases.jsonl")
    matching = [row for row in existing if row.get("source") == filing["source"] and row.get("report_id") == filing["report_id"]]
    current_ids = {row["trade_id"] for row in matching}
    proposed_ids = {trade.trade_id for trade in trades}
    if current_ids and current_ids != proposed_ids:
        # Never append competing OCR rows to a trusted existing transaction set.
        raise OCRError("existing_transaction_conflict")
    if current_ids:
        return 0
    rows = [{**asdict(replace(trade, observed_at_utc=observation)), "historical_bootstrap": True,
             "historical_backfilled_at_utc": now(), "source_ocr": True, "source_document_sha256": evidence["sha256"],
             "source_origin": origin, "ocr_completed_at": evidence["ocr_completed_at"]} for trade in trades]
    tracker.append_jsonl(directory / "transactions.jsonl", rows)
    tracker.append_jsonl(directory / "purchases.jsonl", [row for row in rows if row["transaction_type"] == "Purchase"])
    for row in rows:
        state.seen_trades.setdefault(row["trade_id"], observation)
    tracker.save_state(directory / "state.json", state)
    # Preserve all metadata and first-observation/receipt dates. Leave the original
    # pending-review row and each personal acknowledgement as historical evidence.
    updated = {**filing, "status": "processed", "updated_at_utc": now(), "review_reason": "",
               "transaction_count": len(rows), "purchase_count": sum(row["transaction_type"] == "Purchase" for row in rows),
               "sale_count": sum(row["transaction_type"].startswith("Sale") for row in rows),
               "exchange_count": sum(row["transaction_type"] == "Exchange" for row in rows)}
    tracker.append_jsonl(directory / "filings.jsonl", [updated])
    return len(rows)


def _evidence_path(directory, digest):
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise OCRError("invalid_document_digest")
    return directory / "ocr-evidence" / (digest + "-" + VERSION + ".json")


def _cached_evidence(directory, digest):
    path = _evidence_path(directory, digest)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("sha256") != digest or payload.get("version") != VERSION:
        raise OCRError("invalid_extraction_cache")
    return payload


def run_pass(directory: Path, branch: str, environment, pending_uploads=(), *, loader=download, extractor=extract):
    """Return upload acknowledgements to apply ONLY after canonical commit."""
    if str(environment.get("POLITITRACK_MODE", "production")).lower() != "production":
        raise OCRError("live_ocr_forbidden_in_shadow")
    config = _configuration(directory, branch, environment)
    if not config.terms_acknowledged:
        raise OCRError("disclosure_terms_required")
    state, missing_state = tracker.load_state(directory / "state.json")
    if missing_state or not state.last_success_utc:
        raise OCRError("restored_source_state_required")
    index = tracker.latest_records(directory / "filings.jsonl", "filing_key")
    ledger = directory / "source-ocr.jsonl"
    receipts = tracker.latest_records(ledger, "filing_key")
    incoming = {}
    for item in pending_uploads:
        incoming.setdefault(item["filing_key"], item)
    candidates = []
    for key, filing in index.items():
        if filing.get("branch") != branch or filing.get("source") not in {"house", "senate", "oge"}:
            continue
        receipt = receipts.get(key, {})
        changed = receipt.get("source_url") != filing.get("source_url") or receipt.get("version") != VERSION
        if key not in incoming and not changed and receipt.get("status") in {"complete", "needs_review", "not_applicable"} and receipt.get("revalidate_after", "") > now():
            continue
        if receipt.get("next_attempt_at", "") > now():
            queued = incoming.get(key)
            if queued is None or (queued.get("status") != "approved" and receipt.get("upload_id") == queued.get("upload_id")
                                  and receipt.get("status") in {"retry_delayed", "access_required"}):
                continue
        # Uploads first, then first-observed on this producer cycle, existing
        # parser failures, then oldest untouched history. Never filter by seen IDs.
        is_new = not receipt and filing.get("first_seen_utc", "") >= (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        priority = 0 if key in incoming else 1 if is_new else 2 if filing.get("status") == "review_required" else 3
        candidates.append((priority, receipt.get("attempted_at", ""), filing.get("first_seen_utc", ""), key))
    candidates.sort()
    acknowledgements = []
    started = time.monotonic()
    limit = max(1, min(20, int(environment.get("RUNTIME_SOURCE_OCR_FILES_PER_RUN", "5"))))
    budget = max(30, min(600, int(environment.get("RUNTIME_SOURCE_OCR_SECONDS_PER_RUN", "180"))))
    for _, _, _, key in candidates[:limit]:
        if time.monotonic() - started >= budget:
            break
        filing, upload = index[key], incoming.get(key)
        prior = receipts.get(key, {})
        receipt = {"filing_key": key, "source_url": filing["source_url"], "version": VERSION,
                   "attempted_at": now(), "attempts": int(prior.get("attempts", 0)) + 1,
                   "origin": "user_upload" if upload else "official_download", "status": "retry_delayed"}
        evidence = None
        importing = False
        persisting = False
        request_key = hashlib.sha256(json.dumps({"id": upload["upload_id"], "sha256": upload["sha256"],
            "approved": upload.get("result") if upload.get("status") == "approved" else None}, sort_keys=True).encode()).hexdigest() if upload else None
        if upload and prior.get("upload_request_key") == request_key and prior.get("upload_outcome") and prior.get("status") in {"complete", "needs_review", "not_applicable"}:
            acknowledgements.append(prior["upload_outcome"])
            continue
        receipt["upload_request_key"] = request_key
        receipt["revalidate_after"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat().replace("+00:00", "Z")
        try:
            if upload and upload.get("source_url") != filing["source_url"]:
                raise OCRError("upload_source_changed")
            approval = json.loads(upload["result"])["approved_rows"] if upload and upload.get("status") == "approved" else None
            if approval is not None:
                evidence = _cached_evidence(directory, upload["sha256"])
                if not evidence or evidence.get("sha256") != upload["sha256"]:
                    raise OCRError("approval_evidence_changed")
            else:
                data = upload["payload"] if upload else loader(filing, config)
                digest = hashlib.sha256(data).hexdigest()
                if upload and digest != upload["sha256"]:
                    raise OCRError("upload_digest_mismatch")
                previous_evidence = _cached_evidence(directory, digest)
                if previous_evidence is not None:
                    evidence = previous_evidence
                else:
                    evidence = extractor(data, max_pages=MAX_PAGES, timeout=max(10, min(120, int(budget - (time.monotonic() - started)))))
                del data
            receipt["sha256"] = evidence["sha256"]
            # Coordinates for row/checkbox evidence are retained; individual word
            # arrays are only transient to limit snapshot growth.
            evidence_path = _evidence_path(directory, evidence["sha256"])
            persisting = True
            if not evidence_path.exists():
                evidence_path.parent.mkdir(exist_ok=True)
                temporary = evidence_path.with_suffix(".tmp")
                temporary.write_text(json.dumps({k: v for k, v in evidence.items() if k != "words"}, sort_keys=True), encoding="utf-8")
                temporary.replace(evidence_path)
            persisting = False
            receipt["evidence"] = {k: evidence[k] for k in ("sha256", "version", "page_count", "completed_pages", "ocr_completed_at")}
            receipt["evidence_path"] = str(evidence_path.relative_to(directory))
            if upload and approval is None:
                raise OCRError("upload_confirmation_required")
            trades = _parse(filing, evidence, approval)
            if not trades:
                raise OCRError("zero_transactions_needs_review")
            importing = True
            receipt["transactions_appended"] = _import(directory, filing, trades, evidence,
                "user_confirmed_upload" if approval is not None else receipt["origin"])
            receipt["status"] = "complete"
        except Exception as error:
            if persisting or (importing and not isinstance(error, OCRError)):
                raise  # canonical I/O failures must abort the entire snapshot
            code = str(error) if isinstance(error, OCRError) else type(error).__name__
            # No request URLs with credentials, PDF text, tool stderr or exception
            # message from a network/parser library is copied into diagnostics.
            receipt["error_code"] = code
            receipt["status"] = "needs_review" if evidence is not None else "not_applicable" if code == "native_html_not_applicable" else "access_required" if code in {"access_required", "SenateAccessDenied"} else "retry_delayed"
            delay = min(7 * 86400, 300 * 2 ** min(receipt["attempts"], 11))
            receipt["next_attempt_at"] = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat().replace("+00:00", "Z")
        # Upload-specific result makes a crash after snapshot commit recoverable:
        # caller can replay acknowledgement without resubmitting bytes/imports.
        if upload:
            receipt["upload_id"] = upload["upload_id"]
            preview = {"rows": evidence.get("house_table", {}).get("rows", []),
                       "problems": evidence.get("house_table", {}).get("problems", [])} if evidence else {}
            acknowledgements.append({"upload_id": upload["upload_id"], "sha256": upload["sha256"],
                "status": receipt["status"], "has_evidence": evidence is not None, "preview": {**preview, "error_code": receipt.get("error_code"),
                "filer_matches": bool(evidence and _matching_filer(filing, evidence))}})
            receipt["upload_outcome"] = acknowledgements[-1]
        tracker.append_jsonl(ledger, [receipt])
    return acknowledgements
