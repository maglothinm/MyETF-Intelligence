from __future__ import annotations

import copy
import json
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from runtime_v2 import legislative_recovery as recovery
from runtime_v2.runner import JobRunner, RuntimeJobError
from runtime_v2.store import LockedNamespace, SnapshotHead, StateStoreError


ROOT = Path(__file__).resolve().parents[1]


def test_reviewed_case_and_immutable_evidence_digest():
    receipt = recovery.load_receipt(recovery.CASE)
    assert receipt["failed_run"]["side_effects_possible"] is True
    assert receipt["accepted_parent"]["generation"] == 232
    assert receipt["delivery_finding"] == "delivery_impossible_without_credentials"


def test_receipt_tampering_and_arbitrary_case_fail_closed(monkeypatch, tmp_path):
    with pytest.raises(StateStoreError, match="unknown reviewed"):
        recovery.load_receipt("../unreviewed-override")
    path = tmp_path / "receipt.json"
    path.write_text('{"approved":true}')
    monkeypatch.setattr(recovery, "RECEIPT_PATH", path)
    with pytest.raises(StateStoreError, match="digest mismatch"):
        recovery.load_receipt(recovery.CASE)


class ReadConnection:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        self.statements.append((sql, params))
        assert sql.startswith("SELECT ")

    def fetchall(self):
        return [(row,) for row in self.rows]

    def close(self):
        pass


def case_lock():
    receipt = recovery.load_receipt(recovery.CASE)
    parent = receipt["accepted_parent"]
    connection = ReadConnection([copy.deepcopy(receipt["failed_run"])])
    locked = LockedNamespace(connection, "legislative")
    head = SnapshotHead(**parent, created_at="2026-09-08T10:25:04Z", source_revision="a" * 40, provenance={})
    locked.head = lambda: head
    return receipt, locked, head


def test_exact_case_permits_read_only_adjudication_and_preserves_failure():
    receipt, locked, _ = case_lock()
    before = copy.deepcopy(locked.connection.rows)
    evidence = recovery.assert_adjudicated_retry_safe(locked, recovery.CASE)
    assert evidence["failed_run_id"] == receipt["failed_run"]["run_id"]
    assert evidence["original_failed_run_preserved"] is True
    assert locked.connection.rows == before
    assert len(locked.connection.statements) == 1
    assert "LIMIT 1" not in locked.connection.statements[0][0]


@pytest.mark.parametrize("field", ["run_id", "source_revision", "runtime_mode", "runtime_mode_evidence", "status", "snapshot_id", "snapshot_sha256", "side_effects_possible", "started_at", "finished_at", "error_code", "trigger_source", "job_name", "namespace"])
def test_any_failed_run_evidence_drift_is_rejected(field):
    _, locked, _ = case_lock()
    locked.connection.rows[0][field] = "changed"
    with pytest.raises(StateStoreError, match="inventory changed"):
        recovery.assert_adjudicated_retry_safe(locked, recovery.CASE)


@pytest.mark.parametrize("extra_status", ["running", "failure", "success", "skipped"])
def test_case_cannot_be_reused_after_any_new_run(extra_status):
    _, locked, _ = case_lock()
    extra = copy.deepcopy(locked.connection.rows[0])
    extra.update(run_id="another-run", status=extra_status, side_effects_possible=False)
    locked.connection.rows.append(extra)
    with pytest.raises(StateStoreError, match="inventory changed"):
        recovery.assert_adjudicated_retry_safe(locked, recovery.CASE)


@pytest.mark.parametrize("field,value", [("generation", 233), ("snapshot_id", "new"), ("snapshot_sha256", "b" * 64), ("namespace", "ai")])
def test_parent_drift_is_rejected(field, value):
    _, locked, head = case_lock()
    locked.head = lambda: replace(head, **{field: value})
    with pytest.raises(StateStoreError, match="parent changed"):
        recovery.assert_adjudicated_retry_safe(locked, recovery.CASE)


@pytest.mark.parametrize("job,mode", [("ai", "production"), ("executive", "production"), ("dashboard", "production"), ("legislative", "shadow")])
def test_recovery_cannot_authorize_another_job_or_shadow(job, mode):
    runner = JobRunner(object(), source_revision="f" * 40, environment={"POLITITRACK_MODE": mode}, retry_adjudication=recovery.CASE)
    with pytest.raises(RuntimeJobError, match="Legislative production mode"):
        runner.run(job)


class RunLock:
    def __init__(self):
        self.guard_calls = 0
        self.finished = []
        self.started = []

    def assert_retry_safe(self):
        self.guard_calls += 1

    def restore(self, directory):
        directory.mkdir()
        (directory / "state.json").write_text('{"last_success_utc":"2026-09-08T10:25:04Z"}')
        return SnapshotHead("legislative", 232, "parent", "a" * 64, "", "f" * 40, {})

    def start_run(self, *args, **kwargs):
        self.started.append((args, kwargs))
        return "new-run"

    def finish_run(self, run_id, **kwargs):
        self.finished.append((run_id, kwargs))

    def commit(self, *args, **kwargs):
        raise AssertionError("failed complete-source validation must not publish")


class RunStore:
    def __init__(self):
        self.lock = RunLock()

    @contextmanager
    def locked(self, namespace):
        assert namespace == "legislative"
        yield self.lock


@pytest.mark.parametrize("environment,expected", [
    ({}, False),
    ({"PUSHOVER_API_TOKEN": "token"}, False),
    ({"PUSHOVER_USER_KEY": "user"}, False),
    ({"PUSHOVER_API_TOKEN": " ", "PUSHOVER_USER_KEY": "user"}, False),
    ({"PUSHOVER_API_TOKEN": "token", "PUSHOVER_USER_KEY": "user"}, True),
    ({"PUSHOVER_API_TOKEN": "token", "PUSHOVER_USER_KEY": "user", "SUPPRESS_NOTIFICATIONS": "true"}, False),
])
def test_incomplete_source_still_fails_and_delivery_capability_controls_guard(monkeypatch, environment, expected):
    store = RunStore()
    runner = JobRunner(store, source_revision="f" * 40, environment={"POLITITRACK_MODE": "production", **environment})
    commands = []
    def execute(command):
        commands.append(command)
        if len(commands) == 2:
            assert "--validate-only" in command
            raise RuntimeError("Senate catalog incomplete")
    monkeypatch.setattr(runner, "_execute", execute)
    with pytest.raises(RuntimeError, match="Senate catalog incomplete"):
        runner.run("legislative")
    assert store.lock.guard_calls == 1
    assert store.lock.finished == [("new-run", {"status": "failure", "error_code": "RuntimeError", "side_effects_possible": expected})]


def test_recovery_evidence_is_durable_before_collector_starts(monkeypatch):
    store = RunStore()
    runner = JobRunner(store, source_revision="f" * 40, environment={"POLITITRACK_MODE": "production"}, retry_adjudication=recovery.CASE)
    evidence = {"case": recovery.CASE, "receipt_sha256": recovery.RECEIPT_SHA256}
    monkeypatch.setattr(recovery, "assert_adjudicated_retry_safe", lambda *args: evidence)
    def fail(_command):
        assert store.lock.started[0][1]["retry_adjudication"] == evidence
        raise RuntimeError("collector failure")
    monkeypatch.setattr(runner, "_execute", fail)
    with pytest.raises(RuntimeError, match="collector failure"):
        runner.run("legislative")
    assert store.lock.guard_calls == 0


def test_new_run_retains_recovery_case_without_editing_old_failure():
    from test_runtime_v2_shadow_mode import _CaptureConnection
    connection = _CaptureConnection()
    locked = LockedNamespace(connection, "legislative")
    evidence = {"case": recovery.CASE, "receipt_sha256": recovery.RECEIPT_SHA256}
    locked.start_run("legislative", "issue-8-recovery", "f" * 40, "production", retry_adjudication=evidence)
    assert len(connection.calls) == 1
    sql, values = connection.calls[0]
    assert sql.startswith("INSERT INTO runtime_job_runs")
    assert json.loads(values[-1])["retry_adjudication"] == evidence


def test_explicit_recovery_never_reports_a_busy_writer_as_success(monkeypatch):
    from runtime_v2 import cli
    from runtime_v2.mode import RuntimeMode
    from runtime_v2.store import NamespaceBusy
    class BusyRunner:
        def run(self, _job):
            raise NamespaceBusy("writer active")
    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", "external_scheduler")
    monkeypatch.setattr(cli, "resolve_runtime_mode", lambda: RuntimeMode.PRODUCTION)
    monkeypatch.setattr(cli, "PostgresSnapshotStore", lambda: object())
    monkeypatch.setattr(cli, "JobRunner", lambda *args, **kwargs: BusyRunner())
    with pytest.raises(NamespaceBusy):
        cli.main(["run", "legislative", "--retry-adjudication", recovery.CASE])


def test_recovery_success_preserves_complete_source_gate_and_records_case(monkeypatch):
    store = RunStore()
    runner = JobRunner(store, source_revision="f" * 40, environment={"POLITITRACK_MODE": "production"}, retry_adjudication=recovery.CASE)
    evidence = {"case": recovery.CASE, "receipt_sha256": recovery.RECEIPT_SHA256}
    monkeypatch.setattr(recovery, "assert_adjudicated_retry_safe", lambda *args: evidence)
    commands = []
    monkeypatch.setattr(runner, "_execute", lambda command: commands.append(command))
    published = {}
    def commit(_directory, **kwargs):
        published.update(kwargs)
        return kwargs
    monkeypatch.setattr(store.lock, "commit", commit)
    runner.run("legislative")
    assert "--source" in commands[0] and "all" in commands[0]
    assert "--validate-only" in commands[1]
    assert published["expected_parent_sha256"] == "a" * 64
    assert published["provenance"]["retry_adjudication"] == evidence
    assert published["successful_run_id"] == "new-run"


def test_postgres_exact_case_is_read_only_and_consumed_by_next_run():
    from test_runtime_v2_mode_quarantine import _postgres_connection
    connection = _postgres_connection()
    schema = '"legislative_recovery_' + uuid.uuid4().hex + '"'
    receipt = recovery.load_receipt(recovery.CASE)
    parent = receipt["accepted_parent"]
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE SCHEMA {schema}")
        cursor.execute(f"SET search_path TO {schema}")
        cursor.execute((ROOT / "migrations/20260904_runtime_v2_mode_quarantine.sql").read_text())
        cursor.execute(
            "INSERT INTO runtime_state_snapshots (snapshot_id, namespace, generation, snapshot_sha256, source_revision, manifest, payload, created_at) "
            "VALUES (%s::uuid, 'legislative', 232, %s, %s, '{}'::jsonb, %s, '2026-09-08T10:25:04Z'::timestamptz)",
            (parent["snapshot_id"], parent["snapshot_sha256"], receipt["failed_run"]["source_revision"], b"TEST synthetic payload"),
        )
        cursor.execute(
            "INSERT INTO runtime_state_heads VALUES ('legislative', 232, %s::uuid, %s, '2026-09-08T10:25:04Z'::timestamptz)",
            (parent["snapshot_id"], parent["snapshot_sha256"]),
        )
        cursor.execute("INSERT INTO runtime_job_runs SELECT * FROM jsonb_populate_record(NULL::runtime_job_runs, %s::jsonb)", (json.dumps(receipt["failed_run"]),))
        cursor.execute("SELECT to_jsonb(r) FROM runtime_job_runs r")
        before = cursor.fetchall()
        locked = LockedNamespace(connection, "legislative")
        with pytest.raises(StateStoreError, match="retry is blocked"):
            locked.assert_retry_safe()
        evidence = recovery.assert_adjudicated_retry_safe(locked, recovery.CASE)
        cursor.execute("SELECT to_jsonb(r) FROM runtime_job_runs r")
        assert cursor.fetchall() == before
        locked.start_run("legislative", "issue-8-recovery", "f" * 40, "production", retry_adjudication=evidence)
        with pytest.raises(StateStoreError, match="inventory changed"):
            recovery.assert_adjudicated_retry_safe(locked, recovery.CASE)
        cursor.execute("SELECT to_jsonb(r) FROM runtime_job_runs r WHERE run_id=%s::uuid", (receipt["failed_run"]["run_id"],))
        assert cursor.fetchall() == before
    finally:
        connection.rollback()
        connection.autocommit = True
        connection.cursor().execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        connection.close()
