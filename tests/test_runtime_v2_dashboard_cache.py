"""Committed dashboard reads stay available while its publisher owns the writer lock."""
from __future__ import annotations

import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from runtime_v2.archive import SnapshotArchiveError, pack_directory, unpack_directory
from runtime_v2.store import NamespaceBusy, PostgresSnapshotStore, SnapshotHead, StateStoreError
from runtime_v2 import web


def _snapshot(tmp_path, generation, *, index=True):
    directory = tmp_path / ("source-" + uuid.uuid4().hex)
    directory.mkdir()
    if index:
        (directory / "index.html").write_text(f"<h1>TEST dashboard {generation}</h1>", encoding="utf-8")
    (directory / "data.json").write_text(json.dumps({"test": True, "generation": generation}), encoding="utf-8")
    packed = pack_directory(directory)
    head = SnapshotHead(
        "dashboard", generation, str(uuid.uuid4()), packed.sha256,
        "2026-10-12T00:00:00Z", "f" * 40,
        {"authority": "runtime_v2", "job": "dashboard", "mode": "shadow", "test": True},
    )
    return head, packed, directory


class _CommittedStore:
    def __init__(self, snapshot):
        self.head, packed, _ = snapshot
        self.archives = {self.head.snapshot_id: packed}
        self.lock_calls = self.head_checks = self.restores = 0
        self.before_restore = None
        self.failure = None

    def locked(self, namespace):
        self.lock_calls += 1
        raise NamespaceBusy(f"another {namespace} writer is already running")

    def publish(self, snapshot):
        self.head, packed, _ = snapshot
        self.archives[self.head.snapshot_id] = packed

    def latest_head(self, namespace):
        assert namespace == "dashboard"
        self.head_checks += 1
        if self.failure:
            raise self.failure
        return self.head

    def restore_latest(self, namespace, destination):
        assert namespace == "dashboard"
        self.restores += 1
        if self.before_restore:
            self.before_restore()
        head = self.head
        packed = self.archives[head.snapshot_id]
        unpack_directory(
            packed.payload, destination,
            expected_sha256=head.snapshot_sha256, expected_manifest=packed.manifest,
        )
        return head


@pytest.fixture
def committed(tmp_path, monkeypatch):
    # All restored copies are isolated TEST fixtures and removed by pytest.
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    original = web.tempfile.mkdtemp
    monkeypatch.setattr(web.tempfile, "mkdtemp", lambda **kw: original(dir=cache_root, **kw))
    return _CommittedStore(_snapshot(tmp_path, 1))


def test_cold_and_expired_reads_do_not_compete_with_dashboard_writer(committed, tmp_path):
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]
    client = app.test_client()
    first = client.get("/index.html")
    assert first.status_code == 200
    assert first.headers["X-PolitiTrack-Snapshot"] == committed.head.snapshot_sha256
    assert first.data == b"<h1>TEST dashboard 1</h1>"
    committed.publish(_snapshot(tmp_path, 2))
    cache._next_check = 0
    second = client.get("/index.html")
    assert second.status_code == 200 and second.data == b"<h1>TEST dashboard 2</h1>"
    assert second.headers["X-PolitiTrack-Snapshot"] == committed.head.snapshot_sha256
    ready = client.get("/readyz")
    assert ready.status_code == 200 and ready.json["snapshot_sha256"] == committed.head.snapshot_sha256
    assert committed.lock_calls == 0


def test_response_preparation_failure_closes_file_and_releases_lease(committed, monkeypatch):
    opened = []

    def fail_preparation(response, target):
        opened.append(response.response.file)
        raise OSError("TEST response preparation failure")

    monkeypatch.setattr(web, "_stream_dashboard_response", fail_preparation)
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]
    with pytest.raises(OSError, match="TEST response preparation failure"):
        app.test_client().get("/index.html")
    assert len(opened) == 1 and opened[0].closed
    assert cache._readers == {}
    assert cache.active.is_dir()


def test_unchanged_head_is_checked_without_unpacking_another_copy(committed):
    cache = web.DashboardCache(committed)
    first = cache.refresh_publication()
    second = cache.refresh_publication(force=True)
    assert first.root == second.root
    assert first.head == second.head
    assert committed.head_checks == 2 and committed.restores == 1


def test_publisher_advancing_between_probe_and_restore_uses_restored_head(committed, tmp_path):
    successor = _snapshot(tmp_path, 2)
    committed.before_restore = lambda: committed.publish(successor)
    cache = web.DashboardCache(committed)
    publication = cache.refresh_publication()
    assert publication.head == successor[0]
    assert cache.sha256 == successor[1].sha256
    assert (publication.root / "index.html").read_bytes() == b"<h1>TEST dashboard 2</h1>"


def test_concurrent_refreshes_share_one_verified_restore(committed):
    cache = web.DashboardCache(committed)
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()

    def pause_restore():
        entered.set()
        assert release.wait(5), "test restore was never released"

    def second_refresh():
        second_started.set()
        return cache.refresh_publication()

    committed.before_restore = pause_restore
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.refresh_publication)
        try:
            assert entered.wait(5)
            second = pool.submit(second_refresh)
            assert second_started.wait(5)
        finally:
            release.set()
        a, b = first.result(timeout=5), second.result(timeout=5)
    assert a == b and committed.restores == 1 and committed.lock_calls == 0


def test_response_keeps_its_directory_and_hash_when_another_refresh_finishes(committed, tmp_path, monkeypatch):
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]
    original = web.send_from_directory
    initial = committed.head

    def publish_during_response(root, filename):
        committed.publish(_snapshot(tmp_path, 2))
        cache.refresh_publication(force=True)
        return original(root, filename)

    monkeypatch.setattr(web, "send_from_directory", publish_during_response)
    response = app.test_client().get("/index.html")
    assert response.data == b"<h1>TEST dashboard 1</h1>"
    assert response.headers["X-PolitiTrack-Snapshot"] == initial.snapshot_sha256
    assert cache.sha256 == committed.head.snapshot_sha256 != initial.snapshot_sha256


@pytest.mark.parametrize("defect", ["payload", "manifest", "missing_index", "missing_head", "database"])
def test_failed_refresh_never_serves_the_previous_snapshot(committed, tmp_path, defect, caplog):
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]
    previous = cache.refresh_publication()
    snapshot = _snapshot(tmp_path, 2, index=defect != "missing_index")
    committed.publish(snapshot)
    if defect == "payload":
        committed.archives[committed.head.snapshot_id] = replace(snapshot[1], payload=b"corrupt")
    elif defect == "manifest":
        manifest = dict(snapshot[1].manifest)
        manifest["files"] = [{**entry, "sha256": "0" * 64} for entry in manifest["files"]]
        committed.archives[committed.head.snapshot_id] = replace(snapshot[1], manifest=manifest)
    elif defect == "missing_head":
        committed.head = None
    elif defect == "database":
        committed.failure = ConnectionError("postgresql://private-credential-test")
    with pytest.raises((SnapshotArchiveError, StateStoreError, ConnectionError)):
        cache.refresh(force=True)
    client = app.test_client()
    response = client.get("/index.html")
    assert response.status_code == 503 and response.json["code"] == "DASHBOARD_UNAVAILABLE"
    assert client.get("/readyz").status_code == 503
    assert cache.active == previous.root
    assert list(previous.root.parent.iterdir()) == [previous.root]
    assert "dashboard_refresh_failed exception_type=" in caplog.text
    assert "private-credential-test" not in caplog.text


@pytest.mark.parametrize("change", ["regression", "same_generation"])
def test_cache_rejects_head_rewind_or_rewritten_generation(committed, tmp_path, change):
    cache = web.DashboardCache(committed)
    cache.refresh()
    committed.publish(_snapshot(tmp_path, 2))
    current = cache.refresh_publication(force=True)
    committed.publish(_snapshot(tmp_path, 1 if change == "regression" else 2))
    with pytest.raises(StateStoreError, match="regressed or changed"):
        cache.refresh(force=True)
    assert cache.active == current.root


def test_retirement_waits_for_all_readers_and_preserves_unowned_directories(committed, tmp_path):
    cache = web.DashboardCache(committed)
    with cache.read() as first:
        unowned = first.root.parent / "polititrack-site-unowned"
        unowned.mkdir()
        (unowned / "keep.txt").write_text("Not owned by this cache", encoding="utf-8")
        with cache.read() as overlapping:
            assert overlapping.root == first.root
            committed.publish(_snapshot(tmp_path, 2))
            with cache.read(force=True) as second:
                assert first.root.exists() and second.root.exists()
            assert first.root.exists()
        assert first.root.exists()  # The first API reader still holds its lease.
    assert not first.root.exists() and second.root.exists()
    assert (unowned / "keep.txt").read_text(encoding="utf-8") == "Not owned by this cache"
    assert cache._readers == {} and cache._retired == set()
    for generation in range(3, 7):
        committed.publish(_snapshot(tmp_path, generation))
        with cache.read(force=True) as newest:
            assert set(newest.root.parent.iterdir()) == {newest.root, unowned}


@pytest.mark.parametrize("encoding", ["identity", "gzip"])
@pytest.mark.parametrize("finish", ["consume", "disconnect"])
def test_stream_lease_survives_publication_until_body_completion_or_close(committed, tmp_path, encoding, finish):
    import gzip

    head, _, directory = _snapshot(tmp_path, 2)
    expected = b"TEST large dashboard resource\n" * 10000
    (directory / "large.txt").write_bytes(expected)
    packed = pack_directory(directory)
    committed.publish((replace(head, snapshot_sha256=packed.sha256), packed, directory))
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]
    response = app.test_client().get("/large.txt", headers={"Accept-Encoding": encoding}, buffered=False)
    assert response.status_code == 200
    old_root = cache.active
    committed.publish(_snapshot(tmp_path, 3))
    with cache.read(force=True) as newest:
        assert old_root.exists() and newest.root.exists()
    assert old_root.exists() and cache._readers[old_root] == 1
    if finish == "consume":
        body = response.get_data()
        assert (gzip.decompress(body) if encoding == "gzip" else body) == expected
        assert not old_root.exists()
    response.close()
    response.close()  # WSGI and Response callbacks may both close the same body.
    assert not old_root.exists() and newest.root.exists() and cache._readers == {}


def test_head_conditional_and_missing_routes_release_their_leases(committed):
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]
    client = app.test_client()
    response = client.get("/index.html")
    assert response.get_data() and cache._readers == {}
    etag = response.headers["ETag"]
    response.close()
    for method, path, headers, expected in [
        ("HEAD", "/index.html", {}, 200),
        ("GET", "/index.html", {"If-None-Match": etag}, 304),
        ("GET", "/missing.css", {}, 404),
        ("GET", "/..%2F..%2Foutside.txt", {}, 404),
    ]:
        result = client.open(path, method=method, headers=headers)
        assert result.status_code == expected and cache._readers == {}
        result.close()


def test_failed_response_construction_releases_lease(committed, monkeypatch):
    app = web.create_app({"TESTING": True}, store=committed)
    cache = app.extensions["runtime_v2_dashboard"]

    def failed_response(*_args, **_kwargs):
        raise OSError("synthetic response failure")

    monkeypatch.setattr(web, "send_from_directory", failed_response)
    with pytest.raises(OSError, match="synthetic"):
        app.test_client().get("/index.html")
    assert cache._readers == {}


def test_busy_retired_file_is_retried_without_failing_current_reads(committed, tmp_path, monkeypatch, caplog):
    cache = web.DashboardCache(committed)
    with cache.read() as first:
        pass
    original = web.shutil.rmtree
    busy = True

    def maybe_busy(root):
        if root == first.root and busy:
            raise PermissionError("synthetic-private-path")
        return original(root)

    monkeypatch.setattr(web.shutil, "rmtree", maybe_busy)
    committed.publish(_snapshot(tmp_path, 2))
    with cache.read(force=True) as second:
        assert first.root in cache._retired and first.root.exists()
    assert first.root.exists() and second.root.exists()
    busy = False
    with cache.read() as still_current:
        assert still_current.root == second.root
    assert not first.root.exists() and second.root.exists() and cache._retired == set()
    assert "dashboard_cache_cleanup_deferred exception_type=PermissionError" in caplog.text
    assert "synthetic-private-path" not in caplog.text


def test_latest_head_reads_metadata_without_a_writer_lock_and_closes_connection():
    statements = []

    class Connection:
        closed = False

        def cursor(self):
            return self

        def execute(self, sql, params):
            statements.append((sql, params))

        def fetchone(self):
            return (7, "committed", "a" * 64, datetime(2026, 10, 12, tzinfo=timezone.utc), "f" * 40, {})

        def close(self):
            self.closed = True

    connection = Connection()
    store = object.__new__(PostgresSnapshotStore)
    store._connect = lambda: connection
    head = store.latest_head("dashboard")
    assert head.generation == 7 and head.snapshot_sha256 == "a" * 64
    assert connection.closed
    assert len(statements) == 1 and statements[0][1] == ("dashboard",)
    assert "payload" not in statements[0][0] and "advisory" not in statements[0][0]
    with pytest.raises(StateStoreError, match="unknown"):
        store.latest_head("not-a-namespace")


def test_postgres_serves_committed_snapshot_through_an_active_publisher_transaction(tmp_path, monkeypatch):
    if os.environ.get("RUNTIME_V2_TEST_POSTGRES") != "1":
        pytest.skip("PostgreSQL integration service is not enabled")
    import pg8000.dbapi

    schema = "dashboard_cache_test_" + uuid.uuid4().hex
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    original = web.tempfile.mkdtemp
    monkeypatch.setattr(web.tempfile, "mkdtemp", lambda **kw: original(dir=cache_root, **kw))

    def connection(*, use_schema=True):
        conn = pg8000.dbapi.connect(
            user="postgres", password="runtime-v2-test", host="127.0.0.1", port=5432, database="postgres",
        )
        conn.autocommit = True
        with closing(conn.cursor()) as cursor:
            if use_schema:
                cursor.execute('SET search_path TO "' + schema + '"')
            cursor.execute("SET statement_timeout TO '5s'")
        return conn

    admin = connection(use_schema=False)
    try:
        with closing(admin.cursor()) as cursor:
            cursor.execute('CREATE SCHEMA "' + schema + '"')
            cursor.execute('SET search_path TO "' + schema + '"')
            migration = Path(__file__).resolve().parents[1] / "migrations/20260904_runtime_v2_mode_quarantine.sql"
            cursor.execute(migration.read_text(encoding="utf-8"))
        store = object.__new__(PostgresSnapshotStore)
        store._connect = connection
        first_fixture = _snapshot(tmp_path, 1)
        second, second_packed, _ = _snapshot(tmp_path, 2)
        app = web.create_app({"TESTING": True}, store=store)
        cache = app.extensions["runtime_v2_dashboard"]
        client = app.test_client()
        with store.locked("dashboard") as publisher:
            first = publisher.commit(
                first_fixture[2], expected_parent_sha256=None,
                source_revision="f" * 40, provenance=first_fixture[0].provenance, allow_initial=True,
            )
            with pytest.raises(NamespaceBusy):
                with store.locked("dashboard"):
                    pytest.fail("the existing writer lock was displaced")
            # Hold a successor's INSERT and head update uncommitted, exactly the
            # transaction boundary a reader must not mistake for missing state.
            publisher.connection.autocommit = False
            try:
                with closing(publisher.connection.cursor()) as cursor:
                    cursor.execute(
                        "INSERT INTO runtime_state_snapshots "
                        "(snapshot_id, namespace, generation, parent_sha256, snapshot_sha256, "
                        "source_revision, source_provenance, manifest, payload) "
                        "VALUES (%s::uuid, 'dashboard', 2, %s, %s, %s, %s::jsonb, %s::jsonb, %s)",
                        (second.snapshot_id, first.snapshot_sha256, second.snapshot_sha256, "f" * 40,
                         json.dumps(second.provenance), json.dumps(second_packed.manifest), second_packed.payload),
                    )
                    cursor.execute(
                        "UPDATE runtime_state_heads SET generation=2, snapshot_id=%s::uuid, "
                        "snapshot_sha256=%s WHERE namespace='dashboard'",
                        (second.snapshot_id, second.snapshot_sha256),
                    )
                for _ in range(2):  # Cold and expired warm reads during the active transaction.
                    cache._next_check = 0
                    response = client.get("/index.html")
                    assert response.status_code == 200 and response.data == b"<h1>TEST dashboard 1</h1>"
                    assert response.headers["X-PolitiTrack-Snapshot"] == first.snapshot_sha256
                publisher.connection.commit()
            finally:
                publisher.connection.rollback()
                publisher.connection.autocommit = True
            cache._next_check = 0
            response = client.get("/index.html")
            assert response.status_code == 200 and response.data == b"<h1>TEST dashboard 2</h1>"
            assert response.headers["X-PolitiTrack-Snapshot"] == second.snapshot_sha256
            assert client.get("/readyz").json["snapshot_sha256"] == second.snapshot_sha256
            with pytest.raises(NamespaceBusy):
                with store.locked("dashboard"):
                    pytest.fail("dashboard reads released another session's writer lock")
            with closing(admin.cursor()) as cursor:
                cursor.execute("SELECT snapshot_sha256, payload FROM runtime_state_snapshots ORDER BY generation")
                assert [(str(row[0]), bytes(row[1])) for row in cursor.fetchall()] == [
                    (first.snapshot_sha256, first_fixture[1].payload),
                    (second.snapshot_sha256, second_packed.payload),
                ]
    finally:
        with closing(admin.cursor()) as cursor:
            cursor.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
        admin.close()
