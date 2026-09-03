"""Inspect restored Runtime v2 snapshots without exposing their contents."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


_NAMESPACES = ("legislative", "executive", "ai", "dashboard")
_ID_KEYS = frozenset(
    {
        "id",
        "ticker",
        "symbol",
        "accession_number",
        "filing_url",
        "source_url",
        "transaction_key",
        "purchase_key",
        "analysis_key",
        "position_key",
    }
)
_HISTORY_MARKERS = (
    "analysis",
    "filing",
    "history",
    "ledger",
    "position",
    "purchase",
    "run",
    "transaction",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_target(bucket_name: str, object_name: str) -> None:
    if (
        not bucket_name
        or "/" in bucket_name
        or "\\" in bucket_name
        or not object_name.startswith("phase4-acceptance/probes/")
        or "\\" in object_name
        or any(part in {"", ".", ".."} for part in object_name.split("/"))
        or not object_name.endswith(".json")
    ):
        raise ValueError("unsafe private consistency-probe target")


def _identifier_hash(path: str, key: str, value: Any) -> str:
    normalized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{path}\0{key}\0{normalized}".encode("utf-8")).hexdigest()


def _walk_identifiers(value: Any, path: str = "$") -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            lower = str(key).casefold()
            if lower in _ID_KEYS or lower.endswith("_id"):
                if child not in (None, "", [], {}):
                    yield _identifier_hash(path, lower, child)
            yield from _walk_identifiers(child, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            yield from _walk_identifiers(child, f"{path}[]")


def _record_file(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix()
    raw = path.read_bytes()
    result: dict[str, Any] = {
        "path": relative,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "kind": "binary",
        "record_count": None,
        "identifier_hashes": [],
        "parse_error": "",
    }
    suffix = path.suffix.casefold()
    identifiers: set[str] = set()
    try:
        if suffix == ".json":
            value = json.loads(raw.decode("utf-8"))
            identifiers.update(_walk_identifiers(value))
            result["kind"] = "json"
            result["record_count"] = len(value) if isinstance(value, list) else 1
        elif suffix == ".jsonl":
            count = 0
            for line in raw.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                value = json.loads(line)
                identifiers.update(_walk_identifiers(value))
                count += 1
            result["kind"] = "jsonl"
            result["record_count"] = count
        elif suffix == ".csv":
            rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            for row in rows:
                identifiers.update(_walk_identifiers(row))
            result["kind"] = "csv"
            result["record_count"] = len(rows)
        elif suffix in {".html", ".css", ".js", ".txt", ".md"}:
            raw.decode("utf-8")
            result["kind"] = "text"
    except BaseException as exc:
        result["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    result["identifier_hashes"] = sorted(identifiers)
    return result


def _namespace_receipt(store: Any, namespace: str, root: Path) -> dict[str, Any]:
    destination = root / namespace
    head = store.restore_latest(namespace, destination)
    files = [
        _record_file(path, destination)
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    ]
    all_identifiers = sorted(
        {identifier for item in files for identifier in item["identifier_hashes"]}
    )
    history_counts = {
        item["path"]: item["record_count"]
        for item in files
        if item["record_count"] is not None
        and any(marker in Path(item["path"]).name.casefold() for marker in _HISTORY_MARKERS)
    }
    last_success = ""
    state = destination / "state.json"
    if state.is_file():
        value = json.loads(state.read_text(encoding="utf-8"))
        last_success = str(value.get("last_success_utc") or "") if isinstance(value, dict) else ""
    required_files = {}
    if namespace == "dashboard":
        for relative in ("index.html", "filing-vault.html", "data/summary.json"):
            required_files[relative] = (destination / relative).is_file()
    return {
        "head": {
            "generation": head.generation,
            "snapshot_sha256": head.snapshot_sha256,
            "source_revision": head.source_revision,
            "provenance": head.provenance,
        },
        "file_count": len(files),
        "files": files,
        "identifier_hashes": all_identifiers,
        "history_counts": history_counts,
        "last_success_utc": last_success,
        "parse_errors": [
            {"path": item["path"], "error": item["parse_error"]}
            for item in files
            if item["parse_error"]
        ],
        "required_files": required_files,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        raise SystemExit("usage: gcs_phase4_consistency_probe.py BUCKET OBJECT LABEL")
    bucket_name, object_name, label = args
    if label not in {"baseline", "final"}:
        raise SystemExit("label must be baseline or final")
    _safe_target(bucket_name, object_name)

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "probe": "runtime_v2_snapshot_consistency",
        "label": label,
        "observed_at_utc": _utc_now(),
        "ok": False,
    }
    try:
        from runtime_v2.store import PostgresSnapshotStore

        store = PostgresSnapshotStore()
        with tempfile.TemporaryDirectory(prefix="polititrack-phase4-consistency-") as raw:
            root = Path(raw)
            receipt["namespaces"] = {
                namespace: _namespace_receipt(store, namespace, root)
                for namespace in _NAMESPACES
            }
        errors = [
            item
            for value in receipt["namespaces"].values()
            for item in value["parse_errors"]
        ]
        dashboard_required = receipt["namespaces"]["dashboard"]["required_files"]
        receipt["ok"] = not errors and all(dashboard_required.values())
    except BaseException as exc:
        receipt.update(
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:1000],
                "traceback_tail": traceback.format_exc().splitlines()[-20:],
            }
        )

    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    from google.cloud import storage

    storage.Client().bucket(bucket_name).blob(object_name).upload_from_string(
        payload,
        content_type="application/json",
        if_generation_match=0,
    )
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
