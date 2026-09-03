"""Prove Runtime v2 advisory-lock exclusion without advancing state."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


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
        raise ValueError("unsafe private lock-probe target")


def _head(store: Any, namespace: str) -> dict[str, Any]:
    status = store.status()
    return next(item for item in status["heads"] if item["namespace"] == namespace)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: gcs_phase4_lock_probe.py BUCKET OBJECT")
    bucket_name, object_name = args
    _safe_target(bucket_name, object_name)

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "probe": "runtime_v2_advisory_lock_exclusion",
        "observed_at_utc": _utc_now(),
        "namespace": "legislative",
        "ok": False,
        "first_lock_acquired": False,
        "second_lock_refused": False,
        "state_advanced": False,
    }

    try:
        from runtime_v2.store import PostgresSnapshotStore, StateStoreError

        first_store = PostgresSnapshotStore()
        second_store = PostgresSnapshotStore()
        before = _head(first_store, "legislative")
        receipt["head_before"] = before
        with first_store.locked("legislative"):
            receipt["first_lock_acquired"] = True
            try:
                with second_store.locked("legislative"):
                    receipt["unexpected_second_lock_acquired"] = True
            except StateStoreError as exc:
                receipt["second_lock_refused"] = True
                receipt["refusal_type"] = type(exc).__name__
                receipt["refusal_message"] = str(exc)[:300]
        after = _head(first_store, "legislative")
        receipt["head_after"] = after
        receipt["state_advanced"] = (
            before["generation"] != after["generation"]
            or before["snapshot_sha256"] != after["snapshot_sha256"]
        )
        receipt["ok"] = bool(
            receipt["first_lock_acquired"]
            and receipt["second_lock_refused"]
            and not receipt["state_advanced"]
        )
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
