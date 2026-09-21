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
SNAPSHOT_MODE_EVIDENCE = {
    "schema_version": 1,
    "kind": "snapshot_provenance",
    "mode": "shadow",
    "snapshot_id": "00000000-0000-0000-0000-000000000012",
    "snapshot_sha256": "1" * 64,
}
LEGACY_MODE_EVIDENCE = {
    "schema_version": 1,
    "kind": "legacy_unverified",
    "observed_value": "production",
}


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
        elif "AND r.status = 'success'" in sql:
            self.rows = []  # Real SQL selection is covered by the integration test.
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
            SNAPSHOT_MODE_EVIDENCE,
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
                    SNAPSHOT_MODE_EVIDENCE,
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
    assert run["runtime_mode"] == "shadow"
    assert run["runtime_mode_verified"] is True
    assert run["observed_runtime_mode"] is None
    assert run["runtime_mode_evidence"] == SNAPSHOT_MODE_EVIDENCE
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

    assert evidence["branches"]["legislative"]["available"] is True
    attempt = evidence["branches"]["legislative"]["attempts"][0]
    assert attempt["run_id"] == attempt["run_key"]
    assert attempt["runtime_mode"] == "shadow"
    assert attempt["runtime_mode_verified"] is True
    assert attempt["observed_runtime_mode"] is None
    assert attempt["runtime_mode_evidence"] == SNAPSHOT_MODE_EVIDENCE
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


def _legacy_read_connection() -> _ReadConnection:
    connection = _ReadConnection()
    connection.run_row = (
        "00000000-0000-0000-0000-000000000098",
        "legislative",
        "legislative",
        None,
        LEGACY_MODE_EVIDENCE,
        "success",
        "external_scheduler",
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
    connection.audit_rows["legislative"] = [
        (
            "00000000-0000-0000-0000-000000000098",
            "success",
            STARTED,
            FINISHED,
            "external_scheduler",
            None,
            LEGACY_MODE_EVIDENCE,
            "",
            REVISION,
            "00000000-0000-0000-0000-000000000012",
            "1" * 64,
            "0" * 64,
            12,
            CREATED,
        )
    ]
    return connection


def test_status_preserves_but_does_not_attest_legacy_runtime_mode() -> None:
    connection = _legacy_read_connection()

    status = _store_with_read_connection(connection).status()

    run = status["latest_runs"][0]
    assert run["runtime_mode"] is None
    assert run["runtime_mode_verified"] is False
    assert run["observed_runtime_mode"] == "production"
    assert run["runtime_mode_evidence"] == LEGACY_MODE_EVIDENCE


def test_workflow_audit_excludes_legacy_runtime_mode_from_available_evidence() -> None:
    connection = _legacy_read_connection()

    evidence = _store_with_read_connection(connection).workflow_evidence()

    branch = evidence["branches"]["legislative"]
    assert branch["available"] is False
    attempt = branch["attempts"][0]
    assert attempt["runtime_mode"] is None
    assert attempt["runtime_mode_verified"] is False
    assert attempt["observed_runtime_mode"] == "production"
    assert attempt["runtime_mode_evidence"] == LEGACY_MODE_EVIDENCE


def test_postgres_success_history_is_independent_of_attempt_window_and_rejects_bad_receipts():
    """Exercise the production SQL against failures, quarantine and bad lineage."""
    import json
    import uuid
    from datetime import timedelta
    from types import SimpleNamespace
    from test_runtime_v2_mode_quarantine import _postgres_connection, _create_predecessor_schema
    from scripts.dashboard_insights import build_insights

    connection = _postgres_connection()
    cursor = connection.cursor()
    schema = 'dashboard_history_' + uuid.uuid4().hex
    as_of = datetime.now(timezone.utc)
    generation = 0
    ids = {}

    def seed(name, minutes, *, mode='production', kind='snapshot_provenance', status='success',
             retries=0, ocr=True, document=False, mismatch=None):
        nonlocal generation
        generation += 1
        run_id, snapshot_id = str(uuid.uuid4()), str(uuid.uuid4())
        started = as_of - timedelta(minutes=minutes)
        finished = started + timedelta(minutes=1)
        digest = f'{generation:064x}'
        stage = {'enabled': True, 'stage': 'complete', 'started_at': started.isoformat(),
                 'heartbeat_at': finished.isoformat(), 'finished_at': finished.isoformat(),
                 'intake_status': 'ok', 'cleanup_status': 'complete', 'retry_remaining': retries}
        if document:
            stage['last_document_completed_at'] = (finished - timedelta(seconds=1)).isoformat()
        if mismatch == 'ocr_time':
            stage['heartbeat_at'] = (as_of + timedelta(days=1)).isoformat()
        evidence = {'kind': kind, 'mode': mode, 'snapshot_id': snapshot_id, 'snapshot_sha256': digest}
        if ocr:
            evidence['source_ocr'] = stage
        provenance = {'authority': 'runtime_v2', 'mode': mode, 'job': 'executive', 'trigger_source': 'external_scheduler'}
        cursor.execute(
            'INSERT INTO runtime_state_snapshots (snapshot_id,namespace,generation,snapshot_sha256,source_revision,'
            'source_provenance,manifest,payload,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (snapshot_id, 'ai' if mismatch == 'namespace' else 'executive', generation, digest,
             'bad' if mismatch == 'revision' else REVISION, json.dumps(provenance), '{}', b'test',
             started - timedelta(seconds=1) if mismatch == 'chronology' else finished))
        cursor.execute(
            'INSERT INTO runtime_job_runs (run_id,job_name,namespace,trigger_source,source_revision,runtime_mode,'
            'runtime_mode_evidence,status,started_at,finished_at,snapshot_id,snapshot_sha256) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
            (run_id, 'executive', 'executive', 'external_scheduler', REVISION, mode,
             json.dumps(evidence), status, started, finished, snapshot_id,
             '0' * 64 if mismatch == 'hash' else digest))
        ids[name] = run_id
        return finished.isoformat().replace('+00:00', 'Z')

    try:
        cursor.execute('CREATE SCHEMA "' + schema + '"')
        cursor.execute('SET search_path TO "' + schema + '"')
        _create_predecessor_schema(cursor)
        cursor.execute('ALTER TABLE runtime_job_runs ADD COLUMN runtime_mode_evidence jsonb')
        healthy = seed('healthy', 360, document=True)
        completed = seed('completed', 300, retries=4, document=True)
        collected = seed('collector', 240, ocr=False)
        # Malformed OCR may accompany a valid collection, but cannot advance OCR.
        collected = seed('bad_ocr', 230, mismatch='ocr_time', document=True)
        for i, mismatch in enumerate(['namespace', 'revision', 'chronology', 'hash']):
            seed(mismatch, 220 - i, mismatch=mismatch)
        seed('shadow', 210, mode='shadow')
        seed('legacy', 209, kind='legacy_unverified')
        seed('future', -1440)
        for i in range(20):
            seed(f'failed{i}', 120 - i * 5, status='failure')
        store = PostgresSnapshotStore('postgresql://test')
        store._connect = lambda: SimpleNamespace(cursor=connection.cursor, close=lambda: None)
        cursor.execute('BEGIN READ ONLY')
        evidence = store.workflow_evidence()
        cursor.execute('COMMIT')
        branch = evidence['branches']['executive']
        assert branch['available'] is True
        assert len(branch['attempts']) == 7
        assert {row['run_id'] for row in branch['successful_attempts']} == {
            ids['healthy'], ids['completed'], ids['bad_ocr']}
        model = build_insights({'summary': {'generated_utc': as_of.isoformat()}, 'workflow_evidence': evidence})
        executive = model['health']['branches'][1]
        assert executive['last_success_utc'] == collected
        assert executive['source_ocr']['last_success_at'] == healthy
        assert executive['source_ocr']['last_completed_pass_at'] == completed
        expected_document = (datetime.fromisoformat(completed.replace('Z', '+00:00')) - timedelta(seconds=1)).isoformat().replace('+00:00', 'Z')
        assert executive['source_ocr']['last_document_completed_at'] == expected_document
        # The SQL read and dashboard derivation cannot mutate any receipts.
        cursor.execute('SELECT count(*) FROM runtime_job_runs')
        assert cursor.fetchone()[0] == generation
    finally:
        cursor.execute('ROLLBACK')
        cursor.execute('SET search_path TO public')
        cursor.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
        cursor.close()
        connection.close()
