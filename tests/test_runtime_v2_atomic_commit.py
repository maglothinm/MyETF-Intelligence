from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from runtime_v2.store import LockedNamespace, StateStoreError


class _AtomicCursor:
    def __init__(self, connection):
        self.connection = connection
        self.row = None

    def execute(self, sql, params=()):
        self.connection.events.append(("execute", sql, params, self.connection.autocommit))
        if "FROM runtime_state_heads" in sql:
            self.row = (
                7,
                "11111111-1111-1111-1111-111111111111",
                "a" * 64,
                datetime(2026, 9, 3, tzinfo=timezone.utc),
                "b" * 40,
                {},
            )
        elif "INSERT INTO runtime_state_snapshots" in sql:
            self.row = (datetime(2026, 9, 3, 1, tzinfo=timezone.utc),)
        elif "UPDATE runtime_job_runs AS job_run" in sql:
            exact_match = (
                self.connection.run_is_running
                and self.connection.exact_provenance_match
            )
            self.row = (params[3],) if exact_match else None
        else:
            self.row = None

    def fetchone(self):
        return self.row

    def close(self):
        return None


class _AtomicConnection:
    def __init__(self, *, run_is_running=True, exact_provenance_match=True):
        self.autocommit = True
        self.run_is_running = run_is_running
        self.exact_provenance_match = exact_provenance_match
        self.events = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _AtomicCursor(self)

    def commit(self):
        self.events.append(("commit",))
        self.commits += 1

    def rollback(self):
        self.events.append(("rollback",))
        self.rollbacks += 1


def _source(tmp_path):
    source = tmp_path / "state"
    source.mkdir()
    (source / "state.json").write_text(
        '{"last_success_utc":"2026-09-03T00:00:00Z"}\n',
        encoding="utf-8",
    )
    return source


def test_snapshot_head_and_successful_run_commit_in_one_transaction(tmp_path):
    connection = _AtomicConnection()
    locked = LockedNamespace(connection, "legislative")
    run_id = "22222222-2222-2222-2222-222222222222"

    snapshot = locked.commit(
        _source(tmp_path),
        expected_parent_sha256="a" * 64,
        source_revision="b" * 40,
        provenance={
            "authority": "runtime_v2",
            "job": "legislative",
            "mode": "shadow",
        },
        successful_run_id=run_id,
    )

    statements = [event for event in connection.events if event[0] == "execute"]
    success = next(event for event in statements if "status = 'success'" in event[1])
    assert all(event[3] is False for event in statements)
    assert success[2][0] == snapshot.snapshot_id
    assert success[2][1] == snapshot.snapshot_sha256
    assert json.loads(success[2][2]) == {
        "schema_version": 1,
        "kind": "snapshot_provenance",
        "mode": "shadow",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_sha256": snapshot.snapshot_sha256,
    }
    assert success[2][3:] == (
        run_id,
        "legislative",
        snapshot.snapshot_id,
        snapshot.snapshot_sha256,
    )
    assert "committed_snapshot.namespace = job_run.namespace" in success[1]
    assert "committed_snapshot.source_revision = job_run.source_revision" in success[1]
    assert (
        "committed_snapshot.source_provenance ->> 'authority' = 'runtime_v2'"
        in success[1]
    )
    assert (
        "committed_snapshot.source_provenance ->> 'job' = job_run.job_name"
        in success[1]
    )
    assert "committed_snapshot.created_at >= job_run.started_at" in success[1]
    assert "committed_snapshot.created_at <= now()" in success[1]
    assert (
        "committed_snapshot.source_provenance ->> 'trigger_source' = "
        "job_run.trigger_source"
        in success[1]
    )
    assert (
        "committed_snapshot.source_provenance ->> 'mode' = job_run.runtime_mode"
        in success[1]
    )
    assert connection.events[-1] == ("commit",)
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.autocommit is True


def test_missing_running_run_rolls_back_snapshot_and_head(tmp_path):
    connection = _AtomicConnection(run_is_running=False)
    locked = LockedNamespace(connection, "legislative")

    with pytest.raises(StateStoreError, match="atomically complete"):
        locked.commit(
            _source(tmp_path),
            expected_parent_sha256="a" * 64,
            source_revision="b" * 40,
            provenance={
                "authority": "runtime_v2",
                "job": "legislative",
                "mode": "shadow",
            },
            successful_run_id="22222222-2222-2222-2222-222222222222",
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.events[-1] == ("rollback",)
    assert connection.autocommit is True


def test_missing_exact_snapshot_provenance_match_rolls_back(tmp_path):
    connection = _AtomicConnection(exact_provenance_match=False)
    locked = LockedNamespace(connection, "legislative")

    with pytest.raises(StateStoreError, match="atomically complete"):
        locked.commit(
            _source(tmp_path),
            expected_parent_sha256="a" * 64,
            source_revision="b" * 40,
            provenance={
                "authority": "runtime_v2",
                "job": "legislative",
                "mode": "shadow",
            },
            successful_run_id="22222222-2222-2222-2222-222222222222",
        )

    statements = [event for event in connection.events if event[0] == "execute"]
    success = next(event for event in statements if "status = 'success'" in event[1])
    assert "FROM runtime_state_snapshots AS committed_snapshot" in success[1]
    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.events[-1] == ("rollback",)
    assert connection.autocommit is True


def test_failure_completion_cannot_overwrite_an_atomic_success():
    connection = _AtomicConnection()
    locked = LockedNamespace(connection, "legislative")

    locked.finish_run(
        "22222222-2222-2222-2222-222222222222",
        status="failure",
        error_code="ConnectionError",
    )

    sql, params = connection.events[-1][1:3]
    assert "namespace = %s" in sql
    assert "status = 'running'" in sql
    assert params[-1] == "legislative"


def test_finish_run_rejects_non_atomic_success_without_writing():
    connection = _AtomicConnection()
    locked = LockedNamespace(connection, "legislative")

    with pytest.raises(
        StateStoreError,
        match="successful runtime jobs must commit their snapshot atomically",
    ):
        locked.finish_run(
            "22222222-2222-2222-2222-222222222222",
            status="success",
        )

    assert connection.events == []
