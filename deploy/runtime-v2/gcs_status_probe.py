"""Write non-secret Runtime v2 status evidence to a private GCS object."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import sys
import traceback
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ALLOWED_PREFIXES = (
    "phase3-acceptance/probes/",
    "phase4-acceptance/probes/",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    if hasattr(value, "isoformat"):
        return value.isoformat().replace("+00:00", "Z")
    return value


def _safe_target(bucket_name: str, object_name: str) -> None:
    if (
        not bucket_name
        or "/" in bucket_name
        or "\\" in bucket_name
        or not object_name.startswith(_ALLOWED_PREFIXES)
        or "\\" in object_name
        or any(part in {"", ".", ".."} for part in object_name.split("/"))
        or not object_name.endswith(".json")
    ):
        raise ValueError("unsafe private probe target")


def _query_history(store: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    connection = store._connect()
    try:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT run_id::text, job_name, namespace, trigger_source, "
                "source_revision, runtime_mode, status, started_at, finished_at, "
                "snapshot_sha256, error_code, side_effects_possible "
                "FROM runtime_job_runs ORDER BY started_at, run_id"
            )
            runs = [
                {
                    "run_id": row[0],
                    "job_name": row[1],
                    "namespace": row[2],
                    "trigger_source": row[3],
                    "source_revision": row[4],
                    "runtime_mode": row[5],
                    "status": row[6],
                    "started_at": _json_value(row[7]),
                    "finished_at": _json_value(row[8]) if row[8] else None,
                    "snapshot_sha256": row[9] or "",
                    "error_code": row[10] or "",
                    "side_effects_possible": bool(row[11]),
                }
                for row in cursor.fetchall()
            ]
            cursor.execute(
                "SELECT namespace, generation, parent_sha256, snapshot_sha256, "
                "created_at, source_revision, source_provenance "
                "FROM runtime_state_snapshots ORDER BY namespace, generation"
            )
            snapshots = [
                {
                    "namespace": row[0],
                    "generation": int(row[1]),
                    "parent_sha256": row[2],
                    "snapshot_sha256": row[3],
                    "created_at": _json_value(row[4]),
                    "source_revision": row[5],
                    "provenance": _json_value(row[6]) or {},
                }
                for row in cursor.fetchall()
            ]
        return runs, snapshots
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) not in {3, 4}:
        raise SystemExit(
            "usage: gcs_status_probe.py BUCKET OBJECT PHASE [initialize-schema]"
        )
    bucket_name, object_name, phase = args[:3]
    initialize_schema = len(args) == 4 and args[3] == "initialize-schema"
    if len(args) == 4 and not initialize_schema:
        raise SystemExit("optional operation must be initialize-schema")
    if phase not in {"phase3", "phase4"}:
        raise SystemExit("phase must be phase3 or phase4")
    if initialize_schema and phase != "phase3":
        raise SystemExit("schema initialization is permitted only during Phase 3")
    _safe_target(bucket_name, object_name)

    receipt: dict[str, Any] = {
        "schema_version": 2,
        "probe": "runtime_v2_private_status",
        "phase": phase,
        "observed_at_utc": _utc_now(),
        "ok": False,
        "private_ip_env": str(os.environ.get("PRIVATE_IP") or ""),
        "instance_connection_name": str(os.environ.get("INSTANCE_CONNECTION_NAME") or ""),
        "source_revision": str(os.environ.get("SOURCE_REVISION") or ""),
        "schema_initialize_requested": initialize_schema,
        "schema_initialized": False,
        "protected_state_changed_by_schema_initialize": False,
    }

    try:
        from google.cloud.sql.connector import IPTypes
        from runtime_v2 import database as database_module
        from runtime_v2.store import PostgresSnapshotStore

        receipt.update(
            {
                "database_private_ip_selected": bool(
                    database_module._use_private_ip(dict(os.environ))
                ),
                "database_module_sha256": hashlib.sha256(
                    Path(database_module.__file__).read_bytes()
                ).hexdigest(),
                "cloud_sql_connector_version": importlib.metadata.version(
                    "cloud-sql-python-connector"
                ),
                "connector_private_value": IPTypes.PRIVATE.value,
                "connector_public_value": IPTypes.PUBLIC.value,
            }
        )
        store = PostgresSnapshotStore()
        if initialize_schema:
            store.initialize_schema()
            receipt["schema_initialized"] = True
        status = store.status()
        workflow_evidence = store.workflow_evidence()
        run_history, snapshot_history = _query_history(store)
        evidence = {
            "status": status,
            "workflow_evidence": workflow_evidence,
            "run_history": run_history,
            "snapshot_history": snapshot_history,
        }
        receipt.update(evidence)
        receipt["evidence_sha256"] = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        receipt["ok"] = True
    except BaseException as exc:
        receipt.update(
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:1000],
                "traceback_tail": traceback.format_exc().splitlines()[-20:],
            }
        )

    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    from google.cloud import storage

    storage.Client().bucket(bucket_name).blob(object_name).upload_from_string(
        payload,
        content_type="application/json",
        if_generation_match=0,
    )
    if not receipt["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
