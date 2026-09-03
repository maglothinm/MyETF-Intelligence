from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from runtime_v2.runner import JobRunner
from runtime_v2.store import PostgresSnapshotStore, SnapshotHead


REVISION = "f" * 40
STARTED = datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc)
CREATED = datetime(2026, 9, 3, 10, 1, tzinfo=timezone.utc)
FINISHED = datetime(2026, 9, 3, 10, 2, tzinfo=timezone.utc)


def _write_success_state(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "state.json").write_text(
        '{"last_success_utc":"2026-09-03T10:00:00Z"}\n',
        encoding="utf-8",
    )


class _AiLock:
    def __init__(self) -> None:
        self.provenance = None

    def assert_retry_safe(self) -> None:
        pass

    def restore(self, destination: Path) -> SnapshotHead:
        _write_success_state(destination)
        return SnapshotHead("ai", 4, "ai-parent-id", "a" * 64, STARTED.isoformat(), REVISION, {})

    def start_run(self, *_args) -> str:
        return "00000000-0000-0000-0000-000000000003"

    def commit(
        self,
        _source: Path,
        *,
        expected_parent_sha256: str | None,
        source_revision: str,
        provenance: dict,
        allow_initial: bool = False,
        successful_run_id: str | None = None,
    ) -> SnapshotHead:
        assert expected_parent_sha256 == "a" * 64
        assert source_revision == REVISION
        assert allow_initial is False
        assert successful_run_id == "00000000-0000-0000-0000-000000000003"
        self.provenance = dict(provenance)
        return SnapshotHead("ai", 5, "ai-output-id", "b" * 64, CREATED.isoformat(), REVISION, provenance)

    def finish_run(self, *_args, **_kwargs) -> None:
        raise AssertionError("a successful AI run is completed atomically with its snapshot")


class _AiStore:
    def __init__(self) -> None:
        self.lock = _AiLock()
        self.input_heads = {
            "legislative": SnapshotHead(
                "legislative", 12, "legislative-id", "1" * 64, STARTED.isoformat(), REVISION, {}
            ),
            "executive": SnapshotHead(
                "executive", 9, "executive-id", "2" * 64, STARTED.isoformat(), REVISION, {}
            ),
        }

    @contextmanager
    def locked(self, namespace: str):
        assert namespace == "ai"
        yield self.lock

    def restore_latest(self, namespace: str, destination: Path) -> SnapshotHead:
        _write_success_state(destination)
        return self.input_heads[namespace]


def test_ai_snapshot_records_exact_input_generations_and_hashes(monkeypatch) -> None:
    store = _AiStore()
    runner = JobRunner(
        store,
        repository_root=Path(__file__).resolve().parents[1],
        source_revision=REVISION,
        environment={"POLITITRACK_MODE": "shadow"},
    )
    monkeypatch.setattr(runner, "_execute", lambda _args: None)

    runner.run("ai")

    assert store.lock.provenance["inputs"] == {
        "legislative": {"generation": 12, "snapshot_sha256": "1" * 64},
        "executive": {"generation": 9, "snapshot_sha256": "2" * 64},
    }


class _ReadCursor:
    def __init__(self, connection: "_ReadConnection") -> None:
        self.connection = connection
        self.rows = []

    def execute(self, sql: str, params=()) -> None:
        self.connection.statements.append((sql, params))
        if "ORDER BY h.namespace" in sql:
            self.rows = [self.connection.head_row]
        elif "DISTINCT ON (r.job_name)" in sql:
            self.rows = [self.connection.run_row]
        elif "WHERE r.namespace = %s" in sql:
            self.rows = list(self.connection.audit_rows.get(params[0], []))
        else:  # pragma: no cover - makes an unexpected read query fail loudly
            raise AssertionError(f"unexpected query: {sql}")

    def fetchall(self):
        return list(self.rows)

    def close(self) -> None:
        pass


class _ReadConnection:
    def __init__(self) -> None:
        self.statements = []
        self.closed = False
        self.head_row = (
            "legislative",
            12,
            "00000000-0000-0000-0000-000000000012",
            "1" * 64,
            "0" * 64,
            CREATED,
            FINISHED,
            REVISION,
            {"authority": "runtime_v2"},
        )
        self.run_row = (
            "00000000-0000-0000-0000-000000000099",
            "legislative",
            "legislative",
            "shadow",
            "success",
            "shadow",
            REVISION,
            STARTED,
            FINISHED,
            "00000000-0000-0000-0000-000000000012",
            "1" * 64,
            "0" * 64,
            12,
            CREATED,
            "",
            False,
        )
        self.audit_rows = {
            "legislative": [
                (
                    "00000000-0000-0000-0000-000000000099",
                    "success",
                    STARTED,
                    FINISHED,
                    "shadow",
                    "shadow",
                    "",
                    REVISION,
                    "00000000-0000-0000-0000-000000000012",
                    "1" * 64,
                    "0" * 64,
                    12,
                    CREATED,
                )
            ]
        }

    def cursor(self) -> _ReadCursor:
        return _ReadCursor(self)

    def close(self) -> None:
        self.closed = True


def _store_with_read_connection(connection: _ReadConnection) -> PostgresSnapshotStore:
    store = PostgresSnapshotStore("postgresql://runtime")
    store._connect = lambda: connection
    return store


def test_status_exposes_snapshot_and_run_receipt_lineage() -> None:
    connection = _ReadConnection()

    status = _store_with_read_connection(connection).status()

    head = status["heads"][0]
    assert head == {
        "namespace": "legislative",
        "generation": 12,
        "snapshot_id": "00000000-0000-0000-0000-000000000012",
        "snapshot_sha256": "1" * 64,
        "parent_sha256": "0" * 64,
        "created_at": "2026-09-03T10:01:00Z",
        "updated_at": "2026-09-03T10:02:00Z",
        "source_revision": REVISION,
        "provenance": {"authority": "runtime_v2"},
    }
    run = status["latest_runs"][0]
    assert run["run_id"] == "00000000-0000-0000-0000-000000000099"
    assert run["trigger_source"] == "shadow"
    assert run["source_revision"] == REVISION
    assert run["snapshot_id"] == head["snapshot_id"]
    assert run["snapshot_sha256"] == head["snapshot_sha256"]
    assert run["parent_sha256"] == head["parent_sha256"]
    assert run["snapshot_generation"] == head["generation"]
    assert run["started_at"] == "2026-09-03T10:00:00Z"
    assert run["snapshot_created_at"] == "2026-09-03T10:01:00Z"
    assert run["finished_at"] == "2026-09-03T10:02:00Z"
    assert connection.closed is True


def test_workflow_audit_exposes_the_same_receipt_lineage() -> None:
    connection = _ReadConnection()

    evidence = _store_with_read_connection(connection).workflow_evidence()

    attempt = evidence["branches"]["legislative"]["attempts"][0]
    assert attempt["run_id"] == attempt["run_key"]
    assert attempt["trigger_source"] == "shadow"
    assert attempt["source_revision"] == REVISION
    assert attempt["snapshot_id"] == "00000000-0000-0000-0000-000000000012"
    assert attempt["snapshot_sha256"] == "1" * 64
    assert attempt["parent_sha256"] == "0" * 64
    assert attempt["snapshot_generation"] == 12
    assert attempt["started_utc"] == "2026-09-03T10:00:00Z"
    assert attempt["snapshot_created_utc"] == "2026-09-03T10:01:00Z"
    assert attempt["finished_utc"] == "2026-09-03T10:02:00Z"
    assert connection.closed is True
