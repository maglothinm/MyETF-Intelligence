"""Versioned PostgreSQL snapshot store and single-writer advisory locks."""

from __future__ import annotations

import json
import os
import uuid
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from .archive import pack_directory, unpack_directory
from .database import DatabaseConfigurationError, connect, database_url


NAMESPACES = frozenset({"legislative", "executive", "ai", "dashboard", "simulation"})
RUNTIME_MODES = frozenset({"shadow", "production"})
ATTESTED_MODE_EVIDENCE_KINDS = frozenset({"runner_explicit", "snapshot_provenance"})


class StateStoreError(RuntimeError):
    """The durable state contract could not be satisfied."""


@dataclass(frozen=True)
class SnapshotHead:
    namespace: str
    generation: int
    snapshot_id: str
    snapshot_sha256: str
    created_at: str
    source_revision: str
    provenance: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _runtime_mode_fields(runtime_mode: Any, raw_evidence: Any) -> dict[str, Any]:
    evidence = dict(_json(raw_evidence) or {})
    kind = evidence.get("kind")
    mode = str(runtime_mode) if runtime_mode is not None else None
    return {
        "runtime_mode": mode,
        "runtime_mode_verified": (
            mode in RUNTIME_MODES
            and kind in ATTESTED_MODE_EVIDENCE_KINDS
            and evidence.get("mode") == mode
        ),
        "observed_runtime_mode": (
            evidence.get("observed_value")
            if kind == "legacy_unverified"
            else None
        ),
        "runtime_mode_evidence": evidence,
    }


class LockedNamespace:
    def __init__(self, connection: Any, namespace: str):
        self.connection = connection
        self.namespace = namespace

    def _head_row(self, *, for_update: bool = False) -> tuple[Any, ...] | None:
        suffix = " FOR UPDATE" if for_update else ""
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT h.generation, h.snapshot_id::text, h.snapshot_sha256, "
                "s.created_at, s.source_revision, s.source_provenance "
                "FROM runtime_state_heads h JOIN runtime_state_snapshots s "
                "ON s.snapshot_id = h.snapshot_id WHERE h.namespace = %s" + suffix,
                (self.namespace,),
            )
            return cursor.fetchone()

    def head(self) -> SnapshotHead | None:
        row = self._head_row()
        if row is None:
            return None
        return SnapshotHead(
            self.namespace,
            int(row[0]),
            str(row[1]),
            str(row[2]),
            row[3].isoformat().replace("+00:00", "Z"),
            str(row[4] or ""),
            dict(_json(row[5]) or {}),
        )

    def assert_retry_safe(self) -> None:
        """Fail closed after an unretained run may have emitted an alert."""
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT r.run_id::text FROM runtime_job_runs r "
                "JOIN runtime_state_heads h ON h.namespace = r.namespace "
                "WHERE r.namespace = %s AND r.status = 'failure' "
                "AND r.side_effects_possible = true AND r.started_at > h.updated_at "
                "ORDER BY r.started_at DESC LIMIT 1",
                (self.namespace,),
            )
            row = cursor.fetchone()
        if row is not None:
            raise StateStoreError(
                f"{self.namespace} retry is blocked because the last unretained run may have sent an alert"
            )

    def restore(self, destination: Path) -> SnapshotHead:
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT h.generation, h.snapshot_id::text, h.snapshot_sha256, "
                "s.created_at, s.source_revision, s.source_provenance, s.manifest, s.payload "
                "FROM runtime_state_heads h JOIN runtime_state_snapshots s "
                "ON s.snapshot_id = h.snapshot_id WHERE h.namespace = %s",
                (self.namespace,),
            )
            row = cursor.fetchone()
        if row is None:
            raise StateStoreError(f"no durable {self.namespace} snapshot exists")
        head = SnapshotHead(
            self.namespace,
            int(row[0]),
            str(row[1]),
            str(row[2]),
            row[3].isoformat().replace("+00:00", "Z"),
            str(row[4] or ""),
            dict(_json(row[5]) or {}),
        )
        unpack_directory(
            bytes(row[7]),
            destination,
            expected_sha256=head.snapshot_sha256,
            expected_manifest=dict(_json(row[6]) or {}),
        )
        return head

    def commit(
        self,
        source: Path,
        *,
        expected_parent_sha256: str | None,
        source_revision: str,
        provenance: Mapping[str, Any],
        allow_initial: bool = False,
        successful_run_id: str | None = None,
    ) -> SnapshotHead:
        packed = pack_directory(source)
        provenance_payload = dict(provenance)
        previous_autocommit = self.connection.autocommit
        self.connection.autocommit = False
        try:
            row = self._head_row(for_update=True)
            if row is None:
                if not allow_initial or expected_parent_sha256 is not None:
                    raise StateStoreError(f"refusing to initialize {self.namespace} without an explicit import")
                generation, parent = 1, None
            else:
                parent = str(row[2])
                if not expected_parent_sha256 or parent != expected_parent_sha256:
                    raise StateStoreError(f"{self.namespace} head changed while the job was running")
                generation = int(row[0]) + 1
            snapshot_id = str(uuid.uuid4())
            with closing(self.connection.cursor()) as cursor:
                cursor.execute(
                    "INSERT INTO runtime_state_snapshots "
                    "(snapshot_id, namespace, generation, parent_sha256, snapshot_sha256, "
                    "source_revision, source_provenance, manifest, payload) "
                    "VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s) "
                    "RETURNING created_at",
                    (
                        snapshot_id,
                        self.namespace,
                        generation,
                        parent,
                        packed.sha256,
                        source_revision,
                        json.dumps(provenance_payload, sort_keys=True),
                        json.dumps(packed.manifest, sort_keys=True),
                        packed.payload,
                    ),
                )
                created_at = cursor.fetchone()[0]
                snapshot = SnapshotHead(
                    self.namespace,
                    generation,
                    snapshot_id,
                    packed.sha256,
                    created_at.isoformat().replace("+00:00", "Z"),
                    source_revision,
                    provenance_payload,
                )
                cursor.execute(
                    "INSERT INTO runtime_state_heads "
                    "(namespace, generation, snapshot_id, snapshot_sha256, updated_at) "
                    "VALUES (%s, %s, %s::uuid, %s, now()) "
                    "ON CONFLICT (namespace) DO UPDATE SET generation = EXCLUDED.generation, "
                    "snapshot_id = EXCLUDED.snapshot_id, snapshot_sha256 = EXCLUDED.snapshot_sha256, "
                    "updated_at = EXCLUDED.updated_at",
                    (self.namespace, generation, snapshot_id, packed.sha256),
                )
                if successful_run_id is not None:
                    mode = provenance_payload.get("mode")
                    if mode not in RUNTIME_MODES:
                        raise StateStoreError(
                            f"cannot atomically complete {self.namespace} run without an attested mode"
                        )
                    mode_evidence = {
                        "schema_version": 1,
                        "kind": "snapshot_provenance",
                        "mode": mode,
                        "snapshot_id": snapshot.snapshot_id,
                        "snapshot_sha256": snapshot.snapshot_sha256,
                    }
                    cursor.execute(
                        "UPDATE runtime_job_runs AS job_run "
                        "SET status = 'success', finished_at = now(), "
                        "snapshot_id = %s::uuid, snapshot_sha256 = %s, error_code = '', "
                        "side_effects_possible = false, runtime_mode_evidence = %s::jsonb "
                        "FROM runtime_state_snapshots AS committed_snapshot "
                        "WHERE job_run.run_id = %s::uuid AND job_run.namespace = %s "
                        "AND job_run.status = 'running' "
                        "AND job_run.runtime_mode_evidence ->> 'kind' = 'runner_explicit' "
                        "AND job_run.runtime_mode_evidence ->> 'mode' = job_run.runtime_mode "
                        "AND committed_snapshot.snapshot_id = %s::uuid "
                        "AND committed_snapshot.snapshot_sha256 = %s "
                        "AND committed_snapshot.namespace = job_run.namespace "
                        "AND committed_snapshot.source_revision = job_run.source_revision "
                        "AND committed_snapshot.created_at >= job_run.started_at "
                        "AND committed_snapshot.created_at <= now() "
                        "AND committed_snapshot.source_provenance ->> 'authority' = 'runtime_v2' "
                        "AND committed_snapshot.source_provenance ->> 'job' = job_run.job_name "
                        "AND committed_snapshot.source_provenance ->> 'trigger_source' = job_run.trigger_source "
                        "AND committed_snapshot.source_provenance ->> 'mode' = job_run.runtime_mode "
                        "RETURNING job_run.run_id::text",
                        (
                            snapshot.snapshot_id,
                            snapshot.snapshot_sha256,
                            json.dumps(mode_evidence, sort_keys=True),
                            successful_run_id,
                            self.namespace,
                            snapshot.snapshot_id,
                            snapshot.snapshot_sha256,
                        ),
                    )
                    if cursor.fetchone() is None:
                        raise StateStoreError(
                            f"cannot atomically complete {self.namespace} run"
                        )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            self.connection.autocommit = previous_autocommit
        return snapshot

    def start_run(
        self,
        job_name: str,
        trigger_source: str,
        source_revision: str,
        runtime_mode: str,
    ) -> str:
        if runtime_mode not in RUNTIME_MODES:
            raise StateStoreError("invalid Runtime v2 mode")
        run_id = str(uuid.uuid4())
        mode_evidence = {
            "schema_version": 1,
            "kind": "runner_explicit",
            "mode": runtime_mode,
        }
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "INSERT INTO runtime_job_runs "
                "(run_id, job_name, namespace, trigger_source, source_revision, runtime_mode, "
                "runtime_mode_evidence, status, started_at) "
                "VALUES (%s::uuid, %s, %s, %s, %s, %s, %s::jsonb, 'running', now())",
                (
                    run_id,
                    job_name,
                    self.namespace,
                    trigger_source,
                    source_revision,
                    runtime_mode,
                    json.dumps(mode_evidence, sort_keys=True),
                ),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        snapshot: SnapshotHead | None = None,
        error_code: str = "",
        side_effects_possible: bool = False,
    ) -> None:
        if status not in {"failure", "skipped"}:
            raise StateStoreError(
                "successful runtime jobs must commit their snapshot atomically"
            )
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "UPDATE runtime_job_runs SET status = %s, finished_at = now(), "
                "snapshot_id = %s::uuid, snapshot_sha256 = %s, error_code = %s, "
                "side_effects_possible = %s WHERE run_id = %s::uuid "
                "AND namespace = %s AND status = 'running'",
                (
                    status,
                    snapshot.snapshot_id if snapshot else None,
                    snapshot.snapshot_sha256 if snapshot else None,
                    error_code[:160],
                    side_effects_possible,
                    run_id,
                    self.namespace,
                ),
            )


class PostgresSnapshotStore:
    """Small immutable-blob state layer for the existing file-based collectors."""

    def __init__(self, database_url_value: str | None = None):
        self.environment = dict(os.environ)
        if database_url_value is not None:
            self.environment["DATABASE_URL"] = database_url_value
        try:
            value = database_url(self.environment)
            if not value:
                for required in ("INSTANCE_CONNECTION_NAME", "DB_NAME"):
                    if not str(self.environment.get(required) or "").strip():
                        raise DatabaseConfigurationError(f"missing {required}")
                if not str(
                    self.environment.get("DB_USER") or self.environment.get("DB_IAM_USER") or ""
                ).strip():
                    raise DatabaseConfigurationError("missing DB_USER")
        except DatabaseConfigurationError as exc:
            raise StateStoreError(str(exc)) from exc
        self.database_url = value

    def _connect(self):
        try:
            connection = connect(self.environment)
        except DatabaseConfigurationError as exc:
            raise StateStoreError(str(exc)) from exc
        connection.autocommit = True
        return connection

    def initialize_schema(self, migration: Path | None = None) -> None:
        path = (
            migration
            or Path(__file__).resolve().parents[1]
            / "migrations"
            / "20260904_runtime_v2_mode_quarantine.sql"
        )
        sql = path.read_text(encoding="utf-8")
        connection = self._connect()
        try:
            connection.autocommit = False
            with closing(connection.cursor()) as cursor:
                cursor.execute(sql)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def locked(self, namespace: str) -> Iterator[LockedNamespace]:
        if namespace not in NAMESPACES:
            raise StateStoreError("unknown runtime state namespace")
        connection = self._connect()
        key = "polititrack-runtime-v2:" + namespace
        acquired = False
        try:
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (key,))
                acquired = cursor.fetchone()[0]
            if not acquired:
                raise StateStoreError(f"another {namespace} writer is already running")
            yield LockedNamespace(connection, namespace)
        finally:
            try:
                if acquired:
                    with closing(connection.cursor()) as cursor:
                        cursor.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))
            finally:
                connection.close()

    def restore_latest(self, namespace: str, destination: Path) -> SnapshotHead:
        with self.locked(namespace) as locked:
            return locked.restore(destination)

    def status(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            with closing(connection.cursor()) as cursor:
                cursor.execute(
                    "SELECT h.namespace, h.generation, h.snapshot_id::text, h.snapshot_sha256, "
                    "s.parent_sha256, s.created_at, h.updated_at, s.source_revision, "
                    "s.source_provenance FROM runtime_state_heads h "
                    "JOIN runtime_state_snapshots s ON s.snapshot_id = h.snapshot_id "
                    "ORDER BY h.namespace"
                )
                heads = [
                    {
                        "namespace": row[0],
                        "generation": int(row[1]),
                        "snapshot_id": row[2],
                        "snapshot_sha256": row[3],
                        "parent_sha256": row[4],
                        "created_at": row[5].isoformat().replace("+00:00", "Z"),
                        "updated_at": row[6].isoformat().replace("+00:00", "Z"),
                        "source_revision": row[7],
                        "provenance": dict(_json(row[8]) or {}),
                    }
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    "SELECT DISTINCT ON (r.job_name) r.run_id::text, r.job_name, r.namespace, "
                    "r.runtime_mode, r.runtime_mode_evidence, r.status, r.trigger_source, "
                    "r.source_revision, r.started_at, r.finished_at, r.snapshot_id::text, "
                    "r.snapshot_sha256, s.parent_sha256, s.generation, s.created_at, "
                    "r.error_code, r.side_effects_possible "
                    "FROM runtime_job_runs r LEFT JOIN runtime_state_snapshots s "
                    "ON s.snapshot_id = r.snapshot_id "
                    "ORDER BY r.job_name, r.started_at DESC, r.run_id DESC"
                )
                runs = [
                    {
                        "run_id": row[0],
                        "job_name": row[1],
                        "namespace": row[2],
                        **_runtime_mode_fields(row[3], row[4]),
                        "status": row[5],
                        "trigger_source": row[6],
                        "source_revision": row[7],
                        "started_at": row[8].isoformat().replace("+00:00", "Z"),
                        "finished_at": row[9].isoformat().replace("+00:00", "Z") if row[9] else None,
                        "snapshot_id": row[10],
                        "snapshot_sha256": row[11],
                        "parent_sha256": row[12],
                        "snapshot_generation": int(row[13]) if row[13] is not None else None,
                        "snapshot_created_at": (
                            row[14].isoformat().replace("+00:00", "Z")
                            if row[14]
                            else None
                        ),
                        "error_code": row[15] or "",
                        "side_effects_possible": bool(row[16]),
                    }
                    for row in cursor.fetchall()
                ]
            return {"heads": heads, "latest_runs": runs}
        finally:
            connection.close()

    def workflow_evidence(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            branches: dict[str, Any] = {}
            with closing(connection.cursor()) as cursor:
                for branch in ("legislative", "executive", "ai"):
                    cursor.execute(
                        "SELECT r.run_id::text, r.status, r.started_at, r.finished_at, "
                        "r.trigger_source, r.runtime_mode, r.runtime_mode_evidence, "
                        "r.error_code, r.source_revision, r.snapshot_id::text, "
                        "r.snapshot_sha256, s.parent_sha256, s.generation, "
                        "s.created_at "
                        "FROM runtime_job_runs r LEFT JOIN runtime_state_snapshots s "
                        "ON s.snapshot_id = r.snapshot_id "
                        "WHERE r.namespace = %s ORDER BY r.started_at DESC, r.run_id DESC LIMIT 7",
                        (branch,),
                    )
                    attempts = []
                    for row in cursor.fetchall():
                        conclusion = row[1]
                        attempts.append(
                            {
                                "run_key": row[0],
                                "run_id": row[0],
                                "branch": branch,
                                "run_attempt": 1,
                                "evidence_source": "runtime_v2",
                                **_runtime_mode_fields(row[5], row[6]),
                                "workflow_created_utc": row[2].isoformat().replace("+00:00", "Z"),
                                "workflow_started_utc": row[2].isoformat().replace("+00:00", "Z"),
                                "started_utc": row[2].isoformat().replace("+00:00", "Z"),
                                "finished_utc": row[3].isoformat().replace("+00:00", "Z") if row[3] else None,
                                "producer_job_started_utc": row[2].isoformat().replace("+00:00", "Z"),
                                "producer_job_conclusion": conclusion,
                                "conclusion": conclusion,
                                "success": True if conclusion == "success" else (False if conclusion == "failure" else None),
                                "error_count": 1 if conclusion == "failure" else 0,
                                "event_name": row[4] or "external_scheduler",
                                "trigger_source": row[4] or "external_scheduler",
                                "run_url": "",
                                "error_code": row[7] or "",
                                "source_revision": row[8],
                                "snapshot_id": row[9],
                                "snapshot_sha256": row[10],
                                "parent_sha256": row[11],
                                "snapshot_generation": int(row[12]) if row[12] is not None else None,
                                "snapshot_created_utc": (
                                    row[13].isoformat().replace("+00:00", "Z")
                                    if row[13]
                                    else None
                                ),
                            }
                        )
                    branches[branch] = {
                        "available": any(
                            attempt["conclusion"] == "success"
                            and attempt["runtime_mode_verified"]
                            and attempt["runtime_mode_evidence"].get("kind")
                            == "snapshot_provenance"
                            and attempt["snapshot_id"]
                            == attempt["runtime_mode_evidence"].get("snapshot_id")
                            and attempt["snapshot_sha256"]
                            == attempt["runtime_mode_evidence"].get("snapshot_sha256")
                            for attempt in attempts
                        ),
                        "attempts": attempts,
                    }
            return {
                "schema_version": 1,
                "observed_at_utc": utc_now(),
                "available": all(branches[name]["available"] for name in branches),
                "branches": branches,
            }
        finally:
            connection.close()
