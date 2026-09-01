#!/usr/bin/env python3
"""Fail-closed authority, integrity, and continuity for protected Actions state.

The GitHub artifact is the authority; a directory, cache, timestamp, or successful
source-code test is not.  Restores validate a staged archive before installation.
Every producer must seal its output against the restore receipt immediately before
upload.  The only pre-manifest exception is an explicitly hash-verified migration
allowlist; it is never a fallback to a different/older artifact.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import quote, urlparse

REPOSITORY_ID = 1349678672
DEFAULT_BRANCH = "main"
MANIFEST_NAME = "protected-state-manifest.json"
MANIFEST_VERSION = 1
DEFAULT_ALLOWLIST = Path(__file__).resolve().parents[1] / "docs/protected-state-migration.json"
SHA256 = re.compile(r"^[a-f0-9]{64}$")
COMMIT_SHA = re.compile(r"^[a-f0-9]{40}$")
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024


class StateSafetyError(RuntimeError):
    """A continuity incident: stop without promoting or initializing state."""


@dataclass(frozen=True)
class Pipeline:
    name: str
    artifact: str
    workflow: str
    display_name: str
    job: str

    @property
    def path(self) -> str:
        return f".github/workflows/{self.workflow}"


PIPELINES = {
    "legislative": Pipeline("legislative", "legislative-tracker-state", "legislative_trade_tracker_v2.yml", "Legislative purchase tracker v2", "track"),
    "executive": Pipeline("executive", "executive-tracker-state", "executive_trade_tracker.yml", "Executive purchase tracker", "track"),
    "ai": Pipeline("ai", "ai-analysis-state", "ai_filing_analyst.yml", "AI filing analyst and paper portfolio", "analyze"),
}
TRACKER_FILES = {
    "state.json", "filings.jsonl", "transactions.jsonl", "purchases.jsonl",
    "pending-review.jsonl", "runs.jsonl", "historical-backfill.jsonl",
    "historical-source-documents.json",
}
AI_FILES = {"state.json", "analyses.jsonl", "runs.jsonl", "paper-portfolio.jsonl", "investor-edge-profiles.json", "investor-edge-observations.json", "investor-edge-leaderboard.json", "investor-edge-observations-archive.json"}
CACHE_DIRECTORIES = {"documents", "market-cache", "sec-cache", "investor-edge-market"}
RETIRED_PRODUCER_PATHS = {"legislative": {".github/workflows/legislative_trade_tracker.yml"}, "executive": set(), "ai": set()}
SIMULATION = Pipeline("simulation", "simulation-state", "filing_simulation.yml", "Run $10K portfolio simulator", "simulate")
MAX_SOURCE_DOCUMENT_BYTES = 100 * 1024 * 1024
HISTORICAL_STATUSES = {
    "retryable_error", "complete", "review_required", "invalid_public_date",
    "invalid_cached_document", "cached_report_rejected",
}
HISTORICAL_REASONS = {
    "paper_or_access_requires_review", "paper_or_unparseable_document",
    "official_access_unavailable", "official_report_validation_failed",
    "transaction_parser_rejected_document", "official_document_request_failed",
    "invalid_cached_document", "document_processing_failed",
}


def require(condition: Any, message: str) -> None:
    if not condition:
        raise StateSafetyError(message)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp(value: Any, label: str) -> datetime:
    require(isinstance(value, str) and value, f"{label}: missing timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateSafetyError(f"{label}: invalid timestamp") from exc
    require(parsed.tzinfo is not None, f"{label}: timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data: bytes | str, label: str) -> Any:
    def invalid_constant(value: str) -> None:
        raise StateSafetyError(f"{label}: non-finite JSON number {value}")
    try:
        return json.loads(data, object_pairs_hook=_unique_pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError) as exc:
        raise StateSafetyError(f"{label}: malformed JSON") from exc


def read_json(path: Path) -> Any:
    require(path.is_file(), f"Missing required JSON file: {path.name}")
    return parse_json(path.read_bytes(), path.name)


def object_fields(value: Any, fields: Mapping[str, Any], label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label}: must be an object")
    for name, expected in fields.items():
        require(name in value, f"{label}: missing {name}")
        item = value[name]
        types = expected if isinstance(expected, tuple) else (expected,)
        require(type(item) in types, f"{label}.{name}: invalid type")
    return value


def string_map(value: Any, label: str) -> dict[str, str]:
    require(isinstance(value, dict), f"{label}: must be an object")
    require(all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in value.items()), f"{label}: requires nonempty string IDs and values")
    return value


def validate_state_payload(payload: Any, pipeline: str) -> dict[str, Any]:
    """Validate persisted state without defaulting missing collections to empty."""
    common = {"version": int, "last_attempt_utc": (str, type(None)), "last_success_utc": str}
    if pipeline != "ai":
        state = object_fields(payload, {**common, "seen_filings": dict, "seen_trades": dict, "seen_reviews": dict, "last_counts": dict}, "state.json")
        for source in ("house", "senate", "oge"):
            require(source in state["seen_filings"], f"state.json: missing seen_filings.{source}")
            string_map(state["seen_filings"][source], f"seen_filings.{source}")
        string_map(state["seen_trades"], "seen_trades")
        string_map(state["seen_reviews"], "seen_reviews")
        require(all(type(v) is int and v >= 0 for v in state["last_counts"].values()), "last_counts: expected nonnegative integers")
    else:
        state = object_fields(payload, {**common, "positions": dict, "completed_analysis_ids": dict, "candidate_alert_deliveries": dict, "last_portfolio_refresh_utc": (str, type(None))}, "state.json")
        string_map(state["completed_analysis_ids"], "completed_analysis_ids")
        for key, position in state["positions"].items():
            validate_position(position, f"position {key}")
            require(position["position_id"] == key, f"position {key}: identity mismatch")
        for key, delivery in state["candidate_alert_deliveries"].items():
            validate_delivery(delivery, f"delivery {key}")
            require(delivery["delivery_id"] == key, f"delivery {key}: identity mismatch")
    require(state["version"] == 1, "Unsupported protected state version")
    timestamp(state["last_success_utc"], "state.last_success_utc")
    if state["last_attempt_utc"] is not None:
        timestamp(state["last_attempt_utc"], "state.last_attempt_utc")
    return state


def validate_position(value: Any, label: str) -> None:
    object_fields(value, {"position_id": str, "trade_id": str, "analysis_id": str, "ticker": str, "status": str, "quantity": (int, float), "entry_price": (int, float), "paper_only": bool}, label)
    require(all(value[key] for key in ("position_id", "trade_id", "analysis_id", "ticker")), f"{label}: missing stable identity")
    require(value["paper_only"] is True and value["status"] in {"open", "closed"}, f"{label}: invalid paper position")
    require(value["quantity"] > 0 and value["entry_price"] > 0, f"{label}: invalid quantity/price")


def validate_delivery(value: Any, label: str) -> None:
    object_fields(value, {"delivery_id": str, "analysis_id": str, "trade_id": str, "requested_channels": list, "delivered_channels": dict, "channel_errors": dict, "alert": dict}, label)
    require(value["delivery_id"] and value["analysis_id"] and value["trade_id"], f"{label}: missing stable identity")
    require(set(value["requested_channels"]) <= {"pushover", "gmail"}, f"{label}: invalid channel")
    string_map(value["delivered_channels"], f"{label}.delivered_channels")
    require(set(value["delivered_channels"]) <= set(value["requested_channels"]), f"{label}: unrequested delivery")
    object_fields(value["alert"], {"title": str, "message": str, "url": str}, f"{label}.alert")


def validate_record(record: Any, filename: str, pipeline: str, line: int) -> None:
    label = f"{filename}:{line}"
    require(isinstance(record, dict), f"{label}: JSONL rows must be objects")
    if filename in {"transactions.jsonl", "purchases.jsonl"}:
        fields = {key: str for key in ("trade_id", "observed_at_utc", "branch", "source", "report_id", "filer", "owner", "asset", "ticker", "asset_type", "transaction_type", "transaction_date", "filed_date", "amount", "source_url", "parse_confidence")}
        fields["equity_like"] = bool
        object_fields(record, fields, label)
        require(record["trade_id"] and record["report_id"], f"{label}: missing trade identity")
        require(record["branch"] == pipeline, f"{label}: wrong pipeline")
        if filename == "purchases.jsonl":
            require(record["transaction_type"] == "Purchase", f"{label}: nonpurchase in purchase ledger")
    elif filename == "filings.jsonl":
        object_fields(record, {**{k: str for k in ("filing_key", "first_seen_utc", "updated_at_utc", "branch", "source", "report_id", "filer", "filed_date", "source_url", "status")}, **{k: int for k in ("transaction_count", "purchase_count", "sale_count", "exchange_count")}}, label)
        require(record["filing_key"] and record["report_id"] and record["branch"] == pipeline, f"{label}: invalid filing identity")
        require(all(record[k] >= 0 for k in ("transaction_count", "purchase_count", "sale_count", "exchange_count")), f"{label}: negative count")
    elif filename == "pending-review.jsonl":
        object_fields(record, {k: str for k in ("review_id", "observed_at_utc", "branch", "source", "report_id", "filer", "filed_date", "source_url", "reason")}, label)
        require(record["review_id"] and record["report_id"] and record["branch"] == pipeline, f"{label}: invalid review identity")
    elif filename == "historical-backfill.jsonl":
        required = {
            "filing_key": str, "source": str, "report_id": str,
            "attempted_at_utc": str, "historical_bootstrap": bool,
            "input_fingerprint": str, "status": str, "transaction_count": int,
        }
        object_fields(record, required, label)
        allowed_fields = set(required) | {"transactions_appended", "reason"}
        require(set(record) <= allowed_fields, f"{label}: unexpected historical receipt field")
        expected_sources = {"house", "senate"} if pipeline == "legislative" else {"oge"}
        require(record["source"] in expected_sources, f"{label}: wrong historical source for pipeline")
        require(
            record["filing_key"].startswith(record["source"] + "|") and record["report_id"],
            f"{label}: invalid historical filing identity",
        )
        require(record["historical_bootstrap"] is True, f"{label}: missing historical marker")
        require(bool(SHA256.fullmatch(record["input_fingerprint"])), f"{label}: invalid input fingerprint")
        require(record["status"] in HISTORICAL_STATUSES, f"{label}: invalid historical status")
        require(record["transaction_count"] >= 0, f"{label}: negative transaction count")
        timestamp(record["attempted_at_utc"], f"{label}.attempted_at_utc")
        if "reason" in record:
            require(record["reason"] in HISTORICAL_REASONS, f"{label}: invalid historical reason")
        if record["status"] == "complete":
            appended = record.get("transactions_appended")
            require(type(appended) is int and 0 <= appended <= record["transaction_count"], f"{label}: invalid appended transaction count")
            require("reason" not in record, f"{label}: completed receipt cannot contain a failure reason")
        else:
            require("transactions_appended" not in record, f"{label}: unsuccessful receipt cannot append transactions")
    elif filename == "runs.jsonl":
        object_fields(record, {"run_key": str, "started_utc": str, "finished_utc": str, "success": bool, "errors": list, "run_url": str}, label)
        require(record["run_key"], f"{label}: missing run identity")
        require(timestamp(record["finished_utc"], label) >= timestamp(record["started_utc"], label), f"{label}: reversed run times")
    elif filename == "analyses.jsonl":
        object_fields(record, {"analysis_id": str, "trade_id": str, "analyzed_at_utc": str, "analysis_status": str, "ticker": str, "score": (int, float), "classification": str, "market": dict, "ai": dict, "entry_plan": dict, "paper_only": bool}, label)
        require(record["analysis_id"] and record["trade_id"] and record["paper_only"] is True, f"{label}: invalid analysis identity/mode")
        require(record["analysis_status"] == "complete", f"{label}: incomplete analysis")
        timestamp(record["analyzed_at_utc"], label)
    elif filename == "paper-portfolio.jsonl":
        validate_position(record, label)
        object_fields(record, {"event_id": str, "event_type": str}, label)
        require(record["event_id"] and record["event_type"] in {"open", "update", "close"}, f"{label}: invalid portfolio event")
    elif filename == "notification-outbox.jsonl":
        # The producer owns notification creation, never live delivery.  The
        # dispatcher validates provider/channel-specific payloads separately.
        require(isinstance(record.get("delivery_id") or record.get("notification_id"), str), f"{label}: missing notification identity")
    else:
        raise StateSafetyError(f"No protected JSONL schema for {filename}")


def validate_edge(payload: Any, filename: str) -> None:
    require(isinstance(payload, dict), f"{filename}: expected object")
    if filename == "investor-edge-leaderboard.json":
        object_fields(payload, {"version": (str, int), "generated_utc": str, "investors": list}, filename)
        for row in payload["investors"]:
            object_fields(row, {"investor_key": str, "sample_count": int, "edge_score": (int, float)}, filename)
        return
    field = "profiles" if filename == "investor-edge-profiles.json" else "observations"
    object_fields(payload, {"version": (str, int), field: dict}, filename)
    for key, value in payload[field].items():
        require(isinstance(key, str) and key and isinstance(value, dict), f"{filename}: invalid {field} entry")
        identity = "investor_key" if field == "profiles" else "observation_key"
        if filename == "investor-edge-observations-archive.json" and value.get(identity) != key:
            revision = digest(json.dumps(value, sort_keys=True).encode())
            require(key == f"{value.get(identity)}:revision:{revision}", f"{filename}: archive revision hash/identity mismatch")
        else:
            require(value.get(identity) == key, f"{filename}: {identity} mismatch")
        if field == "profiles":
            object_fields(value, {"sample_count": int, "edge_score": (int, float), "trade_results": list}, f"{filename}/{key}")
        else:
            object_fields(value, {"trade_id": str, "method_hash": str, "picker_outcomes": dict, "followable_outcomes": dict}, f"{filename}/{key}")


def validate_historical_source_documents(root: Path, pipeline: str) -> set[str]:
    """Return the exact hash-bound source-document paths admitted by the manifest."""
    manifest_path = root / "historical-source-documents.json"
    if not manifest_path.exists():
        return set()
    require(pipeline in {"legislative", "executive"}, "Historical source documents are tracker-only")
    manifest = read_json(manifest_path)
    object_fields(manifest, {"documents": list}, "historical-source-documents.json")
    require(set(manifest) == {"documents"}, "Historical source-document manifest has unexpected fields")
    admitted: set[str] = set()
    filing_keys: set[str] = set()
    for number, entry in enumerate(manifest["documents"], 1):
        label = f"historical-source-documents.json/documents/{number}"
        object_fields(
            entry,
            {"filing_key": str, "source_url": str, "path": str, "sha256": str, "format": str},
            label,
        )
        require(
            set(entry) == {"filing_key", "source_url", "path", "sha256", "format"},
            f"{label}: unexpected field",
        )
        filing_key = entry["filing_key"]
        source = filing_key.split("|", 1)[0]
        expected_sources = {"house", "senate"} if pipeline == "legislative" else {"oge"}
        require(source in expected_sources and "|" in filing_key, f"{label}: wrong filing identity for pipeline")
        require(filing_key not in filing_keys, f"{label}: duplicate filing identity")
        filing_keys.add(filing_key)

        raw_path = entry["path"]
        relative = PurePosixPath(raw_path)
        require(
            raw_path == relative.as_posix() and "\\" not in raw_path and not relative.is_absolute()
            and bool(relative.parts) and all(part not in {"", ".", ".."} for part in relative.parts),
            f"{label}: unsafe source-document path",
        )
        require(raw_path not in TRACKER_FILES | {MANIFEST_NAME}, f"{label}: source document collides with protected metadata")
        require(raw_path not in admitted, f"{label}: duplicate source-document path")
        admitted.add(raw_path)

        parsed = urlparse(entry["source_url"])
        suffix = {"house": "house.gov", "senate": "senate.gov", "oge": "oge.gov"}[source]
        host = (parsed.hostname or "").lower()
        require(
            parsed.scheme == "https" and not parsed.username and not parsed.password
            and (host == suffix or host.endswith("." + suffix)),
            f"{label}: source URL is not an official HTTPS origin",
        )
        expected_hash = entry["sha256"].lower()
        require(entry["sha256"] == expected_hash and bool(SHA256.fullmatch(expected_hash)), f"{label}: invalid SHA-256")
        document_format = entry["format"].lower()
        require(entry["format"] == document_format and document_format in {"pdf", "html"}, f"{label}: unsupported document format")
        require(document_format != "html" or source == "senate", f"{label}: only Senate HTML originals are supported")
        suffixes = {"pdf": {".pdf"}, "html": {".html", ".htm"}}[document_format]
        require(relative.suffix.lower() in suffixes, f"{label}: source-document extension/format mismatch")

        document_path = root.joinpath(*relative.parts)
        require(document_path.is_file() and not document_path.is_symlink(), f"{label}: source document is missing or not a regular file")
        size = document_path.stat().st_size
        require(0 < size <= MAX_SOURCE_DOCUMENT_BYTES, f"{label}: source document exceeds the allowed size or is empty")
        data = document_path.read_bytes()
        require(digest(data) == expected_hash, f"{label}: source-document hash mismatch")
        require(
            (document_format == "pdf" and data.startswith(b"%PDF"))
            or (document_format == "html" and b"<" in data[:100]),
            f"{label}: source-document bytes do not match the declared format",
        )
    return admitted


def snapshot_directory(root: Path, pipeline: str) -> dict[str, Any]:
    """Inventory every byte and validate the schema of every retained data file."""
    require(pipeline in PIPELINES, "Unknown protected pipeline")
    require(root.is_dir() and not root.is_symlink(), "Protected state directory is missing or a symlink")
    inventory: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    ledgers: dict[str, list[dict[str, Any]]] = {}
    historical_documents = validate_historical_source_documents(root, pipeline)
    allowed = (AI_FILES if pipeline == "ai" else TRACKER_FILES) | {"notification-outbox.jsonl"} | historical_documents
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"State may not contain symlinks: {path.name}")
        if path.is_dir():
            continue
        require(path.is_file(), "State contains a nonregular file")
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        parts = PurePosixPath(relative).parts
        cache = pipeline == "ai" and len(parts) > 1 and parts[0] in CACHE_DIRECTORIES
        require(relative in allowed or cache, f"Unrecognized protected state file: {relative}")
        data = path.read_bytes()
        info: dict[str, Any] = {"sha256": digest(data), "size": len(data)}
        if relative in historical_documents:
            # The manifest validator already bound identity, origin, format and
            # these exact bytes. Raw originals are never interpreted as state.
            pass
        elif relative.endswith(".jsonl"):
            require(not data or data.endswith(b"\n"), f"{relative}: unterminated JSONL tail")
            rows = []
            for number, line in enumerate(data.splitlines(), 1):
                require(bool(line.strip()), f"{relative}:{number}: blank ledger record")
                record = parse_json(line, f"{relative}:{number}")
                validate_record(record, relative, pipeline, number)
                rows.append(record)
            ledgers[relative] = rows
            info["rows"] = len(rows)
        elif relative.endswith(".json") or relative.endswith(".json.gz"):
            try:
                raw = gzip.decompress(data) if relative.endswith(".gz") else data
            except (OSError, EOFError) as exc:
                raise StateSafetyError(f"{relative}: invalid gzip data") from exc
            payload = parse_json(raw, relative)
            require(isinstance(payload, (dict, list)), f"{relative}: invalid JSON root")
            payloads[relative] = payload
            if relative == "state.json":
                validate_state_payload(payload, pipeline)
            elif relative.startswith("investor-edge-") and not cache:
                validate_edge(payload, relative)
        else:
            raise StateSafetyError(f"No state schema for {relative}")
        inventory[relative] = info
    require("state.json" in payloads, "Missing state.json")
    state = payloads["state.json"]
    required = {"state.json", "runs.jsonl"}
    if pipeline == "ai":
        required |= {"analyses.jsonl", "investor-edge-profiles.json", "investor-edge-observations.json", "investor-edge-leaderboard.json"}
        if state["positions"]:
            required.add("paper-portfolio.jsonl")
    else:
        required |= {"filings.jsonl", "pending-review.jsonl"}
        if pipeline == "legislative" or state["seen_trades"]:
            required |= {"transactions.jsonl", "purchases.jsonl"}
    require(required <= set(inventory), f"Missing protected file(s): {', '.join(sorted(required - set(inventory)))}")
    require(bool(ledgers["runs.jsonl"]), "Protected state has no run history")
    if pipeline != "ai":
        transaction_ids = {r["trade_id"] for r in ledgers.get("transactions.jsonl", [])}
        require(transaction_ids <= set(state["seen_trades"]), "Transaction ledger IDs absent from state")
        require({r["trade_id"] for r in ledgers.get("purchases.jsonl", [])} <= transaction_ids, "Purchase ledger is not a subset of transactions")
        require({r["review_id"] for r in ledgers["pending-review.jsonl"]} <= set(state["seen_reviews"]), "Review ledger IDs absent from state")
    else:
        analysis_ids = {r["analysis_id"] for r in ledgers["analyses.jsonl"]}
        require(analysis_ids <= set(state["completed_analysis_ids"]), "Analysis ledger IDs absent from state")
        require({r["position_id"] for r in ledgers.get("paper-portfolio.jsonl", [])} <= set(state["positions"]), "Portfolio ledger IDs absent from state")
    durable_payloads = {name: payload for name, payload in payloads.items() if "/" not in name}
    return {"files": inventory, "absent_files": sorted(allowed - set(inventory)), "payloads": durable_payloads, "counts": {name: len(rows) for name, rows in ledgers.items()}}


def assert_continuity(before: Mapping[str, Any], after: Mapping[str, Any], root: Path, pipeline: str) -> None:
    """Previous ledger bytes and stable identities must survive every successor."""
    for name, info in before["files"].items():
        require(name in after["files"], f"Previously retained file disappeared: {name}")
        if name.endswith(".jsonl"):
            with (root / name).open("rb") as handle:
                prefix = handle.read(info["size"])
            require(len(prefix) == info["size"] and digest(prefix) == info["sha256"], f"Ledger predecessor prefix changed: {name}")
            require(after["files"][name]["rows"] >= info["rows"], f"Ledger record count regressed: {name}")
    old_document_manifest = before["payloads"].get("historical-source-documents.json")
    if old_document_manifest is not None:
        new_document_manifest = after["payloads"].get("historical-source-documents.json")
        require(new_document_manifest is not None, "Historical source-document manifest disappeared")
        old_entries = {row["filing_key"]: row for row in old_document_manifest["documents"]}
        new_entries = {row["filing_key"]: row for row in new_document_manifest["documents"]}
        for filing_key, entry in old_entries.items():
            require(new_entries.get(filing_key) == entry, f"Historical source-document binding changed: {filing_key}")
            relative = entry["path"]
            require(after["files"][relative] == before["files"][relative], f"Historical source-document bytes changed: {relative}")
    old_state = before["payloads"]["state.json"]
    new_state = after["payloads"]["state.json"]
    maps = ("completed_analysis_ids", "positions", "candidate_alert_deliveries") if pipeline == "ai" else ("seen_trades", "seen_reviews")
    for field in maps:
        require(set(old_state[field]) <= set(new_state[field]), f"Protected IDs disappeared: {field}")
    if pipeline != "ai":
        for source, values in old_state["seen_filings"].items():
            require(set(values) <= set(new_state["seen_filings"].get(source, {})), f"Protected filing IDs disappeared: {source}")
    else:
        for key, delivery in old_state["candidate_alert_deliveries"].items():
            current = new_state["candidate_alert_deliveries"][key]
            require(current["alert"] == delivery["alert"], f"Immutable notification snapshot changed: {key}")
            require(set(delivery["requested_channels"]) <= set(current["requested_channels"]), f"Requested notification channel disappeared: {key}")
            for channel, delivered_at in delivery["delivered_channels"].items():
                require(current["delivered_channels"].get(channel) == delivered_at, f"Accepted notification bookkeeping changed: {key}/{channel}")
        old_profiles = before["payloads"].get("investor-edge-profiles.json", {}).get("profiles", {})
        new_profiles = after["payloads"].get("investor-edge-profiles.json", {}).get("profiles", {})
        require(set(old_profiles) <= set(new_profiles), "Investor Edge profile identities disappeared")
        active_file = "investor-edge-observations.json"
        archive_file = "investor-edge-observations-archive.json"
        new_archive = after["payloads"].get(archive_file, {}).get("observations", {})
        candidates = [
            row for filename in (active_file, archive_file)
            for row in after["payloads"].get(filename, {}).get("observations", {}).values()
        ]
        for filename in (active_file, archive_file):
            prior = before["payloads"].get(filename, {}).get("observations", {})
            for storage_key, observation in prior.items():
                if filename == archive_file:
                    require(new_archive.get(storage_key) == observation, f"Archived Investor Edge record changed/disappeared: {storage_key}")
                identity = observation["observation_key"]
                matches = [row for row in candidates if row.get("observation_key") == identity]
                require(matches, f"Investor Edge observation identity disappeared: {identity}")
                # Pending horizons may mature, but previously completed outcomes
                # must remain verbatim in an active or immutable archived version.
                complete = [(field, horizon, value)
                            for field in ("picker_outcomes", "followable_outcomes")
                            for horizon, value in observation.get(field, {}).items()
                            if value is not None]
                require(any(all(row.get(field, {}).get(horizon) == value
                                for field, horizon, value in complete)
                            for row in matches),
                        f"Completed Investor Edge outcome changed/disappeared: {identity}")
    require(timestamp(new_state["last_success_utc"], "success") >= timestamp(old_state["last_success_utc"], "previous success"), "State success timestamp regressed")


def safe_extract(archive: bytes, staging: Path, *, root_filename: str = "state.json") -> Path:
    """Reject traversal, symlinks, duplicate paths, and ambiguous payload roots."""
    require(len(archive) <= MAX_ARCHIVE_BYTES, "Archive exceeds safety size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            entries = zipped.infolist()
            require(sum(item.file_size for item in entries) <= MAX_ARCHIVE_BYTES, "Unpacked archive exceeds safety size limit")
            seen: set[str] = set()
            for item in entries:
                name = item.filename
                parts = name.rstrip("/").split("/")
                require(name and "\\" not in name and ":" not in name and not name.startswith("/") and all(part not in {"", ".", ".."} and part == part.rstrip(" .") for part in parts), "Unsafe archive path")
                require(name.casefold() not in seen, "Duplicate archive path")
                seen.add(name.casefold())
                require(not stat.S_ISLNK(item.external_attr >> 16), "Archive contains symlink")
            zipped.extractall(staging)
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        if isinstance(exc, StateSafetyError):
            raise
        raise StateSafetyError("Unreadable protected archive") from exc
    state_files = list(staging.rglob(root_filename))
    require(len(state_files) == 1, f"Archive must contain exactly one {root_filename}")
    root = state_files[0].parent
    require(all(path.is_relative_to(root) for path in staging.rglob("*") if path.is_file()), "Archive has files outside its state root")
    return root


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    require(not temporary.exists(), "Refusing to overwrite an existing pending state file")
    try:
        temporary.write_bytes(canonical_bytes(value))
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class GitHubAPI:
    """Small injectable, read-only GitHub client. Never prints credential output."""

    def __init__(self) -> None:
        self.cache: dict[str, Any] = {}

    def bytes(self, path: str) -> bytes:
        result = subprocess.run(["gh", "api", "--method", "GET", "-H", "Accept: application/vnd.github+json", path], capture_output=True, check=False)
        require(result.returncode == 0, f"GitHub API request failed: {path.split('?')[0]}; no state was promoted")
        return result.stdout

    def json(self, path: str) -> Any:
        if path not in self.cache:
            self.cache[path] = parse_json(self.bytes(path), "GitHub API response")
        return self.cache[path]

    def pages(self, path: str, key: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[int] = set()
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            payload = self.json(f"{path}{separator}per_page=100&page={page}")
            require(isinstance(payload, dict) and isinstance(payload.get(key), list), f"Malformed GitHub pagination for {key}")
            batch = payload[key]
            for record in batch:
                require(isinstance(record, dict) and type(record.get("id")) is int, f"Malformed GitHub {key} entry")
                require(record["id"] not in seen, f"Unstable/repeated GitHub {key} pagination; retry from a fresh snapshot")
                seen.add(record["id"])
                records.append(record)
            if len(batch) < 100:
                total = payload.get("total_count")
                require(total is None or total <= len(records), f"Incomplete GitHub {key} pagination")
                return records
            page += 1


def repository_context(api: GitHubAPI, env: Mapping[str, str], consumer_sha: str, *, writer: bool) -> dict[str, Any]:
    require(env.get("GITHUB_REPOSITORY_ID") == str(REPOSITORY_ID), "Refusing execution outside literal canonical repository ID 1349678672")
    require(bool(COMMIT_SHA.fullmatch(consumer_sha)), "Invalid consumer commit SHA")
    repository = api.json(f"/repositories/{REPOSITORY_ID}")
    require(repository.get("id") == REPOSITORY_ID and repository.get("default_branch") == DEFAULT_BRANCH, "Canonical repository/default branch mismatch")
    require(repository.get("full_name") == env.get("GITHUB_REPOSITORY"), "Runtime repository name does not resolve to canonical numeric identity")
    require(not repository.get("archived"), "Canonical repository is archived")
    full_name = repository["full_name"]
    reference = api.json(f"/repos/{full_name}/git/ref/heads/{DEFAULT_BRANCH}")
    live_sha = reference.get("object", {}).get("sha")
    require(isinstance(live_sha, str) and COMMIT_SHA.fullmatch(live_sha), "Invalid canonical default-branch SHA")
    if writer:
        require(consumer_sha == live_sha, "Stale-code execution blocked: consuming commit is not current canonical main")
        require(env.get("GITHUB_REF") == f"refs/heads/{DEFAULT_BRANCH}", "Protected state writers must run on canonical main")
    return {"id": REPOSITORY_ID, "full_name": full_name, "default_branch": DEFAULT_BRANCH, "head_sha": live_sha}


def _run_binding(payload: Mapping[str, Any], spec: Pipeline) -> bool:
    return payload.get("repository", {}).get("id") == REPOSITORY_ID and payload.get("head_branch") == DEFAULT_BRANCH and str(payload.get("path", "")).split("@", 1)[0] == spec.path and payload.get("name") == spec.display_name


def _jobs(api: GitHubAPI, full_name: str, run_id: int, attempt: int) -> list[dict[str, Any]]:
    return api.pages(f"/repos/{full_name}/actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs")


def resolve_producer(api: GitHubAPI, full_name: str, artifact: Mapping[str, Any], spec: Pipeline, consumer_sha: str) -> dict[str, Any]:
    run_id = artifact.get("workflow_run", {}).get("id")
    require(type(run_id) is int and run_id > 0, "Artifact has no exact producer run")
    run = api.json(f"/repos/{full_name}/actions/runs/{run_id}")
    require(_run_binding(run, spec), f"Unexpected producer of {spec.artifact}: run {run_id}")
    count = run.get("run_attempt")
    require(type(count) is int and count >= 1, "Artifact run has invalid attempt metadata")
    created = timestamp(artifact.get("created_at"), "artifact.created_at")
    matches = []
    for number in range(1, count + 1):
        attempt = api.json(f"/repos/{full_name}/actions/runs/{run_id}/attempts/{number}")
        require(attempt.get("run_attempt") == number and attempt.get("id") == run_id, "Ambiguous run-attempt identity")
        require(_run_binding(attempt, spec), "Run attempt has unexpected producer identity")
        jobs = _jobs(api, full_name, run_id, number)
        relevant = [job for job in jobs if job.get("name") == spec.job]
        require(len(relevant) == 1, f"Run {run_id}/{number}: authoritative job is missing or ambiguous")
        job = relevant[0]
        if not job.get("started_at") or not job.get("completed_at"):
            continue
        started = timestamp(job["started_at"], "job.started_at")
        completed = timestamp(job["completed_at"], "job.completed_at")
        if started <= created <= completed:
            require(attempt.get("conclusion") == "success" and job.get("conclusion") == "success", f"Artifact was produced by an unsuccessful exact attempt/job: {run_id}/{number}")
            head_sha = attempt.get("head_sha", "")
            require(isinstance(head_sha, str) and COMMIT_SHA.fullmatch(head_sha), "Invalid producer SHA")
            comparison = api.json(f"/repos/{full_name}/compare/{head_sha}...{consumer_sha}")
            require(comparison.get("status") in {"ahead", "identical"}, "Producer commit is not an ancestor of consumer")
            matches.append({"run_id": run_id, "run_attempt": number, "head_sha": head_sha, "head_branch": DEFAULT_BRANCH, "workflow_path": spec.path, "workflow_name": spec.display_name, "job_name": spec.job, "job_id": job["id"], "job_started_at": job["started_at"], "job_completed_at": job["completed_at"], "run_started_at": attempt["run_started_at"]})
    require(len(matches) == 1, "Artifact does not map uniquely to one successful producer job/attempt window")
    return matches[0]


def check_high_water(api: GitHubAPI, full_name: str, spec: Pipeline, selected: Mapping[str, Any]) -> None:
    """Inspect ALL run IDs: an old run can acquire the newest rerun attempt."""
    boundary = timestamp(selected["job_completed_at"], "selected producer completion")
    for run in api.pages(f"/repos/{full_name}/actions/runs", "workflow_runs"):
        path = str(run.get("path", "")).split("@", 1)[0]
        if path != spec.path and run.get("name") != spec.display_name and path not in RETIRED_PRODUCER_PATHS.get(spec.name, set()):
            continue
        if run.get("updated_at") and timestamp(run["updated_at"], "run.updated_at") < boundary:
            continue
        count = run.get("run_attempt")
        require(type(count) is int and count >= 1, "Cannot establish producer high-water: invalid attempt count")
        for number in range(1, count + 1):
            if run["id"] == selected["run_id"] and number == selected["run_attempt"]:
                continue
            for job in _jobs(api, full_name, run["id"], number):
                if job.get("name") != spec.job or job.get("conclusion") != "success":
                    continue
                completed = timestamp(job.get("completed_at"), "successful producer job completion")
                if completed >= boundary:
                    require(_run_binding(run, spec), f"Unexpected protected producer identity at later successful run {run['id']}/{number}")
                require(completed < boundary, f"Producer high-water violation: later successful {spec.name} attempt {run['id']}/{number} has no selected authoritative successor")


def select_authority(api: GitHubAPI, repository: Mapping[str, Any], pipeline: str, consumer_sha: str) -> dict[str, Any]:
    spec = PIPELINES[pipeline]
    selected = select_named_authority(api, repository, spec, consumer_sha)
    require(selected is not None, "Protected state cannot be optional")
    return selected


def select_named_authority(api: GitHubAPI, repository: Mapping[str, Any], spec: Pipeline, consumer_sha: str, *, allow_never_created: bool = False) -> dict[str, Any] | None:
    full_name = repository["full_name"]
    # This is repository-global by artifact NAME, never restricted to the known
    # workflow. A retired/foreign workflow's newer write is a blocker, not skipped.
    artifacts = api.pages(f"/repos/{full_name}/actions/artifacts?name={quote(spec.artifact)}", "artifacts")
    if not artifacts and allow_never_created:
        check_high_water(api, full_name, spec, {"job_completed_at": "1970-01-01T00:00:00Z", "run_id": -1, "run_attempt": -1})
        return None
    require(artifacts, f"No {spec.artifact} exists; blank initialization is prohibited")
    require(all(row.get("name") == spec.artifact for row in artifacts), "GitHub artifact-name query returned unexpected data")
    artifacts.sort(key=lambda row: (timestamp(row.get("created_at"), "artifact.created_at"), row["id"]), reverse=True)
    artifact = artifacts[0]
    require(artifact.get("expired") is False, f"Newest {spec.artifact} is expired; recovery is required")
    producer = resolve_producer(api, full_name, artifact, spec, consumer_sha)
    check_high_water(api, full_name, spec, producer)
    return {"artifact_id": artifact["id"], "artifact_name": spec.artifact, "created_at": artifact["created_at"], "digest": artifact.get("digest"), "producer": producer}


def validate_simulation_directory(root: Path, selected: Mapping[str, Any], full_name: str) -> dict[str, Any]:
    files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    require(files == {"simulation-result.json", "simulation-runs.jsonl"}, "Simulation artifact must contain exactly result and complete history")
    result = read_json(root / "simulation-result.json")
    data = (root / "simulation-runs.jsonl").read_bytes()
    require(data and data.endswith(b"\n"), "Simulation history is missing/unterminated")
    history = []
    for number, line in enumerate(data.splitlines(), 1):
        require(bool(line.strip()), "Simulation history contains blank records")
        row = parse_json(line, f"simulation-runs.jsonl:{number}")
        object_fields(row, {"schema_version": int, "simulation_id": str, "status": str, "success": bool, "mode": str, "as_of_utc": str, "run_url": str, "objective": dict, "accounting": dict, "safety": dict}, f"simulation run {number}")
        require(row["schema_version"] == 1 and row["simulation_id"] and row["status"] == "success" and row["success"] is True and row["mode"] == "offline_historical_replay", "Simulation history has invalid identity/status/mode")
        timestamp(row["as_of_utc"], "simulation.as_of_utc")
        object_fields(row["safety"], {"paper_only": bool, "network_calls": bool, "alerts_sent": bool, "production_inputs_mutated": bool}, "simulation.safety")
        require(row["safety"]["paper_only"] is True and all(row["safety"][field] is False for field in ("network_calls", "alerts_sent", "production_inputs_mutated")), "Simulation isolation attestation failed")
        object_fields(row["objective"], {"starting_capital_usd": (int, float), "goal_value_usd": (int, float)}, "simulation.objective")
        require(row["objective"]["starting_capital_usd"] == 10000 and row["objective"]["goal_value_usd"] == 20000, "Unexpected historical simulation objective")
        history.append(row)
    require(history[-1] == result, "Simulation result is not the exact final history record")
    owner = full_name.split("/", 1)[0]
    allowed_repositories = {full_name, f"{owner}/MyETF-Intelligence", f"{owner}/PolitiTrack"}
    expected_urls = {f"https://github.com/{name}/actions/runs/{selected['producer']['run_id']}" for name in allowed_repositories}
    require(result["run_url"] in expected_urls, "Simulation result run URL does not match canonical producer")
    return {"result": result, "history": history, "history_bytes": data}


def restore_simulation(*, api: GitHubAPI, destination: Path, consumer_sha: str, env: Mapping[str, str]) -> dict[str, Any] | None:
    """Dashboard optional means never-created, not failed validation or expiry."""
    require(not destination.exists(), "Simulation restore destination already exists")
    repository = repository_context(api, env, consumer_sha, writer=False)
    selected = select_named_authority(api, repository, SIMULATION, consumer_sha, allow_never_created=True)
    if selected is None:
        return None
    archive = api.bytes(f"/repos/{repository['full_name']}/actions/artifacts/{selected['artifact_id']}/zip")
    if selected.get("digest") is not None:
        require(selected["digest"] == "sha256:" + digest(archive), "Simulation archive digest mismatch")
    with tempfile.TemporaryDirectory(prefix="polititrack-simulation-restore-") as temp:
        root = safe_extract(archive, Path(temp), root_filename="simulation-result.json")
        validated = validate_simulation_directory(root, selected, repository["full_name"])
        artifacts = api.pages(f"/repos/{repository['full_name']}/actions/artifacts?name=simulation-state", "artifacts")
        artifacts.sort(key=lambda row: (timestamp(row["created_at"], "simulation artifact time"), row["id"]), reverse=True)
        if len(artifacts) > 1:
            previous = artifacts[1]
            require(previous.get("expired") is False, "Simulation immediate predecessor expired; history recovery required")
            previous_producer = resolve_producer(api, repository["full_name"], previous, SIMULATION, selected["producer"]["head_sha"])
            previous_selected = {"artifact_id": previous["id"], "producer": previous_producer}
            previous_archive = api.bytes(f"/repos/{repository['full_name']}/actions/artifacts/{previous['id']}/zip")
            if previous.get("digest") is not None:
                require(previous["digest"] == "sha256:" + digest(previous_archive), "Simulation predecessor archive digest mismatch")
            with tempfile.TemporaryDirectory(prefix="polititrack-simulation-predecessor-") as prior_temp:
                previous_root = safe_extract(previous_archive, Path(prior_temp), root_filename="simulation-result.json")
                prior_data = validate_simulation_directory(previous_root, previous_selected, repository["full_name"])
                prefix = prior_data["history_bytes"]
                require(validated["history_bytes"].startswith(prefix), "Simulation history changed/truncated its predecessor byte prefix")
                tail = validated["history_bytes"][len(prefix):].splitlines()
                require(len(tail) == 1 and parse_json(tail[0], "appended simulation result") == validated["result"], "Simulation history must append exactly one successor result")
        else:
            require(len(validated["history"]) == 1, "Simulation predecessor artifact is missing; complete lineage cannot be established")
            for run in api.pages(f"/repos/{repository['full_name']}/actions/runs", "workflow_runs"):
                if str(run.get("path", "")).split("@", 1)[0] != SIMULATION.path:
                    continue
                count = run.get("run_attempt")
                require(type(count) is int and count >= 1, "Cannot prove simulation was never previously produced")
                for attempt in range(1, count + 1):
                    if run["id"] == selected["producer"]["run_id"] and attempt == selected["producer"]["run_attempt"]:
                        continue
                    previous_jobs = _jobs(api, repository["full_name"], run["id"], attempt)
                    require(not any(job.get("name") == SIMULATION.job and job.get("conclusion") == "success" for job in previous_jobs), "Simulation predecessor artifact missing after an earlier successful producer")
        destination.parent.mkdir(parents=True, exist_ok=True)
        installing = destination.with_name(destination.name + ".validated-staging")
        require(not installing.exists(), "Simulation staging directory already exists")
        try:
            shutil.copytree(root, installing)
            os.replace(installing, destination)
        finally:
            if installing.exists():
                shutil.rmtree(installing)
        return {"selected": selected, "history_count": len(validated["history"])}


def _inventory_only(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {"files": snapshot["files"], "absent_files": snapshot["absent_files"], "counts": snapshot["counts"]}


def validate_manifest(manifest: Any, snapshot: Mapping[str, Any], selected: Mapping[str, Any], pipeline: str) -> None:
    object_fields(manifest, {"manifest_version": int, "repository_id": int, "default_branch": str, "pipeline": str, "artifact_name": str, "created_at": str, "producer": dict, "predecessor": dict, "generation": int, "inventory": dict, "inventory_sha256": str}, MANIFEST_NAME)
    require(manifest["manifest_version"] == MANIFEST_VERSION and manifest["repository_id"] == REPOSITORY_ID and manifest["default_branch"] == DEFAULT_BRANCH, "Manifest version/canonical identity mismatch")
    require(manifest["pipeline"] == pipeline and manifest["artifact_name"] == PIPELINES[pipeline].artifact, "Manifest pipeline mismatch")
    require(manifest["generation"] >= 1, "Invalid manifest generation")
    for key in ("run_id", "run_attempt", "head_sha", "head_branch", "workflow_path", "workflow_name", "job_name", "job_id", "job_started_at", "run_started_at"):
        require(manifest["producer"].get(key) == selected["producer"].get(key), f"Manifest producer mismatch: {key}")
    sealed_at = timestamp(manifest["created_at"], "manifest.created_at")
    require(timestamp(selected["producer"]["job_started_at"], "job start") <= sealed_at <= timestamp(selected["created_at"], "artifact created"), "Manifest falls outside producing job/artifact time window")
    predecessor = object_fields(manifest["predecessor"], {"artifact_id": int, "created_at": str, "producer": dict, "inventory_sha256": str}, "manifest.predecessor")
    object_fields(predecessor["producer"], {"run_id": int, "run_attempt": int, "head_sha": str, "head_branch": str, "workflow_path": str, "workflow_name": str, "job_name": str, "job_id": int, "job_started_at": str, "job_completed_at": str, "run_started_at": str}, "manifest.predecessor.producer")
    spec = PIPELINES[pipeline]
    require(predecessor["producer"]["head_branch"] == DEFAULT_BRANCH and predecessor["producer"]["workflow_path"] == spec.path and predecessor["producer"]["workflow_name"] == spec.display_name and predecessor["producer"]["job_name"] == spec.job, "Manifest predecessor producer binding mismatch")
    require(bool(COMMIT_SHA.fullmatch(predecessor["producer"]["head_sha"])), "Invalid predecessor commit SHA")
    require(predecessor["artifact_id"] != selected["artifact_id"] and predecessor["artifact_id"] > 0, "Manifest predecessor self-reference/invalid identity")
    require(timestamp(predecessor["created_at"], "predecessor.created_at") < timestamp(selected["created_at"], "artifact.created_at"), "Manifest predecessor timestamp does not precede successor")
    require(bool(SHA256.fullmatch(predecessor["inventory_sha256"])), "Invalid predecessor inventory hash")
    inventory = _inventory_only(snapshot)
    require(manifest["inventory"] == inventory, "Manifest inventory/schema/count/hash mismatch")
    require(manifest["inventory_sha256"] == digest(canonical_bytes(inventory)), "Manifest inventory root hash mismatch")


def validate_migration(allowlist: Any, selected: Mapping[str, Any], snapshot: Mapping[str, Any], archive_hash: str, pipeline: str) -> None:
    require(isinstance(allowlist, dict) and allowlist.get("version") == 1 and allowlist.get("repository_id") == REPOSITORY_ID and allowlist.get("default_branch") == DEFAULT_BRANCH, "Invalid explicit pre-manifest migration allowlist")
    entry = allowlist.get("artifacts", {}).get(str(selected["artifact_id"]))
    require(isinstance(entry, dict), f"Pre-manifest artifact {selected['artifact_id']} is not an explicitly verified migration checkpoint")
    require(entry.get("pipeline") == pipeline and entry.get("zip_sha256") == archive_hash, "Pre-manifest checkpoint ZIP/pipeline mismatch")
    for field in ("run_id", "run_attempt", "head_sha", "workflow_path", "workflow_name", "job_name", "job_id"):
        require(entry.get(field) == selected["producer"].get(field), f"Pre-manifest producer mismatch: {field}")
    require(entry.get("created_at") == selected["created_at"], "Pre-manifest artifact timestamp mismatch")
    require(entry.get("files") == snapshot["files"], "Pre-manifest full inventory/hash/count mismatch")
    # The schema may define additional genuinely optional empty output files
    # introduced after checkpoint capture, but every recorded absence is exact.
    require(set(entry.get("absent_files", [])) <= set(snapshot["absent_files"]), "Pre-manifest checkpoint absent-file inventory mismatch")
    require(bool(entry.get("evidence")), "Migration checkpoint has no verification evidence")


def verify_predecessor(api: GitHubAPI, repository: Mapping[str, Any], manifest: Mapping[str, Any], snapshot: Mapping[str, Any], root: Path, pipeline: str, allowlist_path: Path) -> None:
    """Verify immediate lineage and actual prefix bytes, not self-reported counts."""
    prior = manifest["predecessor"]
    artifact = api.json(f"/repos/{repository['full_name']}/actions/artifacts/{prior['artifact_id']}")
    require(artifact.get("id") == prior["artifact_id"] and artifact.get("name") == PIPELINES[pipeline].artifact and artifact.get("created_at") == prior["created_at"], "Predecessor artifact identity mismatch")
    require(artifact.get("expired") is False, "Immediate predecessor expired; explicit continuity recovery is required")
    producer = resolve_producer(api, repository["full_name"], artifact, PIPELINES[pipeline], manifest["producer"]["head_sha"])
    require(producer == prior["producer"], "Predecessor exact run/job/attempt metadata mismatch")
    selected = {"artifact_id": artifact["id"], "artifact_name": artifact["name"], "created_at": artifact["created_at"], "digest": artifact.get("digest"), "producer": producer}
    archive = api.bytes(f"/repos/{repository['full_name']}/actions/artifacts/{artifact['id']}/zip")
    archive_hash = digest(archive)
    if artifact.get("digest") is not None:
        require(artifact["digest"] == f"sha256:{archive_hash}", "Predecessor archive digest mismatch")
    with tempfile.TemporaryDirectory(prefix="polititrack-predecessor-") as temp:
        prior_root = safe_extract(archive, Path(temp))
        before = snapshot_directory(prior_root, pipeline)
        manifest_path = prior_root / MANIFEST_NAME
        if manifest_path.exists():
            previous_manifest = read_json(manifest_path)
            validate_manifest(previous_manifest, before, selected, pipeline)
            require(prior.get("manifest_sha256") == digest(manifest_path.read_bytes()), "Predecessor manifest digest mismatch")
            generation = previous_manifest["generation"]
        else:
            validate_migration(read_json(allowlist_path), selected, before, archive_hash, pipeline)
            require(prior.get("manifest_sha256") is None, "Unexpected predecessor manifest digest")
            generation = 0
        require(manifest["generation"] == generation + 1, "Manifest lineage generation skipped/regressed")
        require(prior["inventory_sha256"] == digest(canonical_bytes(_inventory_only(before))), "Predecessor inventory digest mismatch")
        assert_continuity(before, snapshot, root, pipeline)


def restore(*, api: GitHubAPI, pipeline: str, destination: Path, receipt_path: Path, consumer_sha: str, env: Mapping[str, str], read_only: bool = False, allowlist_path: Path = DEFAULT_ALLOWLIST) -> dict[str, Any]:
    require(not destination.exists(), f"Restore destination already exists; refusing to replace local state: {destination}")
    require(not receipt_path.exists(), "Restore receipt already exists; use an isolated fresh run directory")
    repository = repository_context(api, env, consumer_sha, writer=not read_only)
    selected = select_authority(api, repository, pipeline, consumer_sha)
    archive = api.bytes(f"/repos/{repository['full_name']}/actions/artifacts/{selected['artifact_id']}/zip")
    archive_hash = digest(archive)
    if selected["digest"] is not None:
        require(selected["digest"] == f"sha256:{archive_hash}", "GitHub archive digest mismatch")
    with tempfile.TemporaryDirectory(prefix="polititrack-restore-") as temp:
        staged_root = safe_extract(archive, Path(temp))
        snapshot = snapshot_directory(staged_root, pipeline)
        manifest_path = staged_root / MANIFEST_NAME
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            validate_manifest(manifest, snapshot, selected, pipeline)
            verify_predecessor(api, repository, manifest, snapshot, staged_root, pipeline, allowlist_path)
            generation = manifest["generation"]
            manifest_sha = digest(manifest_path.read_bytes())
        else:
            validate_migration(read_json(allowlist_path), selected, snapshot, archive_hash, pipeline)
            generation = 0
            manifest_sha = None
        receipt = {"receipt_version": 1, "repository_id": REPOSITORY_ID, "default_branch": DEFAULT_BRANCH, "pipeline": pipeline, "consumer_sha": consumer_sha, "selected": selected, "generation": generation, "manifest_sha256": manifest_sha, "archive_sha256": archive_hash, "snapshot": snapshot}
        destination.parent.mkdir(parents=True, exist_ok=True)
        # copytree refuses existing paths, and the fully validated temporary
        # sibling is renamed only after all bytes have copied successfully.
        installing = destination.with_name(destination.name + ".validated-staging")
        require(not installing.exists(), "Restore staging path already exists")
        try:
            shutil.copytree(staged_root, installing)
            os.replace(installing, destination)
        finally:
            if installing.exists():
                shutil.rmtree(installing)
        write_json_atomic(receipt_path, receipt)
        if read_only:
            for path in destination.rglob("*"):
                path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            destination.chmod(destination.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return receipt


def current_producer(api: GitHubAPI, repository: Mapping[str, Any], pipeline: str, env: Mapping[str, str], consumer_sha: str) -> dict[str, Any]:
    spec = PIPELINES[pipeline]
    try:
        run_id = int(env["GITHUB_RUN_ID"])
        number = int(env["GITHUB_RUN_ATTEMPT"])
    except (KeyError, ValueError) as exc:
        raise StateSafetyError("Missing producer run/attempt identity") from exc
    require(run_id > 0 and number > 0 and env.get("GITHUB_JOB") == spec.job, "Unexpected authoritative producer job")
    attempt = api.json(f"/repos/{repository['full_name']}/actions/runs/{run_id}/attempts/{number}")
    require(_run_binding(attempt, spec) and attempt.get("head_sha") == consumer_sha and attempt.get("run_attempt") == number, "Current producing attempt identity mismatch")
    jobs = [job for job in _jobs(api, repository["full_name"], run_id, number) if job.get("name") == spec.job]
    require(len(jobs) == 1 and jobs[0].get("status") == "in_progress", "Seal must run inside the one active authoritative job")
    job = jobs[0]
    timestamp(job.get("started_at"), "current job start")
    return {"run_id": run_id, "run_attempt": number, "head_sha": consumer_sha, "head_branch": DEFAULT_BRANCH, "workflow_path": spec.path, "workflow_name": spec.display_name, "job_name": spec.job, "job_id": job["id"], "job_started_at": job["started_at"], "run_started_at": attempt["run_started_at"]}


def seal(*, api: GitHubAPI, pipeline: str, directory: Path, receipt_path: Path, consumer_sha: str, env: Mapping[str, str]) -> dict[str, Any]:
    repository = repository_context(api, env, consumer_sha, writer=True)
    receipt = read_json(receipt_path)
    require(receipt.get("receipt_version") == 1 and receipt.get("repository_id") == REPOSITORY_ID and receipt.get("default_branch") == DEFAULT_BRANCH and receipt.get("pipeline") == pipeline and receipt.get("consumer_sha") == consumer_sha, "Missing/mismatched verified restore receipt")
    # Recheck the high-water immediately before publication, not just at restore.
    latest = select_authority(api, repository, pipeline, consumer_sha)
    require(latest == receipt["selected"], "Protected authority advanced after restore; refusing stale successor")
    producer = current_producer(api, repository, pipeline, env, consumer_sha)
    snapshot = snapshot_directory(directory, pipeline)
    assert_continuity(receipt["snapshot"], snapshot, directory, pipeline)
    require(snapshot["files"]["runs.jsonl"]["rows"] == receipt["snapshot"]["files"]["runs.jsonl"]["rows"] + 1, "Producer must append exactly one successful run-history record")
    last_run = parse_json((directory / "runs.jsonl").read_bytes().splitlines()[-1], "latest run-history record")
    require(last_run.get("run_key") == f"{producer['run_id']}:{producer['run_attempt']}" and last_run.get("success") is True and not last_run.get("errors"), "Latest run-history record does not prove this successful producer attempt")
    inventory = _inventory_only(snapshot)
    predecessor = {"artifact_id": latest["artifact_id"], "created_at": latest["created_at"], "producer": latest["producer"], "manifest_sha256": receipt["manifest_sha256"], "inventory_sha256": digest(canonical_bytes(_inventory_only(receipt["snapshot"])))}
    manifest = {"manifest_version": MANIFEST_VERSION, "repository_id": REPOSITORY_ID, "default_branch": DEFAULT_BRANCH, "pipeline": pipeline, "artifact_name": PIPELINES[pipeline].artifact, "created_at": utc_now(), "producer": producer, "predecessor": predecessor, "generation": receipt["generation"] + 1, "inventory": inventory, "inventory_sha256": digest(canonical_bytes(inventory))}
    write_json_atomic(directory / MANIFEST_NAME, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("restore", "seal", "validate"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--pipeline", choices=PIPELINES, required=True)
        sub.add_argument("--destination" if name == "restore" else "--directory", type=Path, required=True)
        if name != "validate":
            sub.add_argument("--receipt", type=Path, required=True)
            sub.add_argument("--consumer-sha", default=os.environ.get("GITHUB_SHA", ""))
        if name == "restore":
            sub.add_argument("--read-only", action="store_true")
            sub.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    optional_simulation = subparsers.add_parser("restore-simulation")
    optional_simulation.add_argument("--destination", type=Path, required=True)
    optional_simulation.add_argument("--consumer-sha", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args(argv)
    try:
        if args.command == "restore-simulation":
            result = restore_simulation(api=GitHubAPI(), destination=args.destination, consumer_sha=args.consumer_sha, env=os.environ)
            print("Historical simulation has never been successfully created; optional dashboard input omitted" if result is None else f"Verified simulation artifact {result['selected']['artifact_id']} with {result['history_count']} history records")
        elif args.command == "validate":
            snapshot = snapshot_directory(args.directory, args.pipeline)
            print(json.dumps({"validated": args.pipeline, "files": len(snapshot["files"]), "counts": snapshot["counts"]}, sort_keys=True))
        elif args.command == "restore":
            receipt = restore(api=GitHubAPI(), pipeline=args.pipeline, destination=args.destination, receipt_path=args.receipt, consumer_sha=args.consumer_sha, env=os.environ, read_only=args.read_only, allowlist_path=args.allowlist)
            selected = receipt["selected"]
            print(f"Verified {args.pipeline}: artifact {selected['artifact_id']}, run {selected['producer']['run_id']}, attempt {selected['producer']['run_attempt']}, generation {receipt['generation']}")
        else:
            manifest = seal(api=GitHubAPI(), pipeline=args.pipeline, directory=args.directory, receipt_path=args.receipt, consumer_sha=args.consumer_sha, env=os.environ)
            print(f"Sealed {args.pipeline} generation {manifest['generation']} with {len(manifest['inventory']['files'])} inventoried files")
        return 0
    except (StateSafetyError, OSError, KeyError, TypeError) as exc:
        print(f"Protected state BLOCKED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
