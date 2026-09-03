"""Write a non-secret Runtime v2 Phase 3 acceptance snapshot to private GCS."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .store import PostgresSnapshotStore, StateStoreError


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--object", default="phase3/acceptance/status.json")
    return parser


def _safe_bucket(value: str) -> str:
    name = value.strip()
    if not name or "/" in name or "\\" in name:
        raise StateStoreError("acceptance bucket name is unsafe")
    return name


def _safe_object(value: str) -> str:
    path = value.strip()
    if not path.startswith("phase3/acceptance/") or "\\" in path:
        raise StateStoreError("acceptance object path is unsafe")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        raise StateStoreError("acceptance object path is unsafe")
    return path


def build_receipt(store: PostgresSnapshotStore) -> dict:
    status = store.status()
    return {
        "schema_version": 1,
        "generated_at_utc": _utc_now(),
        "runtime": status,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bucket_name = _safe_bucket(args.bucket)
    object_name = _safe_object(args.object)
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - image dependency failure
        raise StateStoreError("Google Cloud Storage dependency is unavailable") from exc

    receipt = build_receipt(PostgresSnapshotStore())
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    bucket.blob(object_name).upload_from_string(payload, content_type="application/json")
    print(json.dumps({"result": "phase3_acceptance_written", "bucket": bucket_name, "object": object_name}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StateStoreError, OSError, ValueError) as exc:
        print(f"Runtime v2 acceptance refused the operation: {exc}")
        raise SystemExit(1)
