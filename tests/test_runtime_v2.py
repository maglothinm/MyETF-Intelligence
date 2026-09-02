import hashlib
import io
import json
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from runtime_v2.archive import SnapshotArchiveError, extract_verified_zip, pack_directory, unpack_directory
from runtime_v2.cli import _normalize_import, _validated_provenance, _verify_import_archive
from runtime_v2.mode import RuntimeMode, RuntimeModeError
from runtime_v2.runner import JobRunner
from runtime_v2.store import PostgresSnapshotStore, SnapshotHead, StateStoreError
from backend.filing_vault.storage import GoogleCloudObjectStore, StorageError


def _receipt(tmp_path: Path, namespace: str = "legislative") -> dict:
    authorities = {
        "legislative": ("legislative_trade_tracker_v2.yml", "legislative-tracker-state", "track"),
        "executive": ("executive_trade_tracker.yml", "executive-tracker-state", "track"),
        "ai": ("ai_filing_analyst.yml", "ai-analysis-state", "analyze"),
    }
    workflow, artifact, job = authorities[namespace]
    archive = tmp_path / f"{namespace}.zip"
    archive.write_bytes(b"verified archive")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return {
        "namespace": namespace,
        "repository_id": 1349678672,
        "repository_full_name": "maglothinm/MyETF-Intelligence",
        "workflow_path": f".github/workflows/{workflow}",
        "artifact_name": artifact,
        "artifact_id": 2,
        "artifact_digest": f"sha256:{digest}",
        "archive_sha256": digest,
        "archive_path": str(archive),
        "run_id": 3,
        "run_attempt": 1,
        "job_id": 4,
        "job_name": job,
        "head_sha": "a" * 40,
        "head_branch": "main",
        "conclusion": "success",
    }


def test_snapshot_archive_is_deterministic_and_round_trips(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.json").write_text('{"last_success_utc":"2026-09-01T00:00:00Z"}\n')
    (source / "nested").mkdir()
    (source / "nested" / "ledger.jsonl").write_text('{"id":1}\n')

    first = pack_directory(source)
    second = pack_directory(source)
    assert first.payload == second.payload
    assert first.sha256 == hashlib.sha256(first.payload).hexdigest()

    destination = tmp_path / "destination"
    unpack_directory(
        first.payload,
        destination,
        expected_sha256=first.sha256,
        expected_manifest=first.manifest,
    )
    assert (destination / "state.json").read_bytes() == (source / "state.json").read_bytes()
    assert (destination / "nested" / "ledger.jsonl").read_bytes() == (source / "nested" / "ledger.jsonl").read_bytes()


def test_snapshot_archive_rejects_traversal(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../outside", b"bad")
    payload = stream.getvalue()
    manifest = {
        "schema_version": 1,
        "files": [{"path": "../outside", "size": 3, "sha256": hashlib.sha256(b"bad").hexdigest()}],
    }
    with pytest.raises(SnapshotArchiveError):
        unpack_directory(
            payload,
            tmp_path / "destination",
            expected_sha256=hashlib.sha256(payload).hexdigest(),
            expected_manifest=manifest,
        )
    assert not (tmp_path / "outside").exists()


def test_snapshot_archive_rejects_tampering(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "state.json").write_text("{}")
    packed = pack_directory(source)
    with pytest.raises(SnapshotArchiveError, match="payload hash"):
        unpack_directory(
            packed.payload + b"x",
            tmp_path / "destination",
            expected_sha256=packed.sha256,
            expected_manifest=packed.manifest,
        )


def test_migration_provenance_requires_canonical_repository(tmp_path):
    receipt = tmp_path / "receipt.json"
    payload = _receipt(tmp_path)
    payload["repository_id"] = 1
    receipt.write_text(json.dumps(payload))
    with pytest.raises(StateStoreError, match="canonical"):
        _validated_provenance(receipt, "legislative")


def test_migration_provenance_binds_download_to_github_digest(tmp_path):
    receipt = tmp_path / "receipt.json"
    payload = _receipt(tmp_path)
    payload["archive_sha256"] = "b" * 64
    receipt.write_text(json.dumps(payload))
    with pytest.raises(StateStoreError, match="does not match"):
        _validated_provenance(receipt, "legislative")


def test_migration_archive_is_rechecked_at_import_time(tmp_path):
    receipt = tmp_path / "receipt.json"
    payload = _receipt(tmp_path)
    receipt.write_text(json.dumps(payload))
    validated = _validated_provenance(receipt, "legislative")
    _verify_import_archive(validated, Path(payload["archive_path"]))
    Path(payload["archive_path"]).write_bytes(b"changed")
    with pytest.raises(StateStoreError, match="changed"):
        _verify_import_archive(validated, Path(payload["archive_path"]))


def test_external_migration_zip_rejects_traversal(tmp_path):
    archive = tmp_path / "artifact.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("../outside", b"bad")
    with pytest.raises(SnapshotArchiveError, match="unsafe path"):
        extract_verified_zip(archive, tmp_path / "destination")
    assert not (tmp_path / "outside").exists()


def test_migration_input_requires_success_marker(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    (source / "state.json").write_text("{}")
    with pytest.raises(StateStoreError, match="successful-state"):
        _normalize_import(source, tmp_path / "normalized")


def test_tracker_command_never_uses_repository_state_paths(tmp_path):
    runner = object.__new__(JobRunner)
    runner.root = Path(__file__).resolve().parents[1]
    runner.python = "python"
    command = runner._tracker_command("legislative", tmp_path / "state", tmp_path / "output")
    rendered = " ".join(str(value) for value in command)
    assert str(tmp_path / "state" / "state.json") in rendered
    assert ".trade-tracker/legislative" not in rendered


class _RunnerLock:
    def __init__(self, owner, namespace):
        self.owner = owner
        self.namespace = namespace

    def assert_retry_safe(self):
        self.owner.retry_checks.append(self.namespace)

    def head(self):
        return SnapshotHead(
            self.namespace,
            1,
            f"{self.namespace}-snapshot",
            "d" * 64,
            "2026-09-01T00:00:00Z",
            "a" * 40,
            {},
        )

    def restore(self, destination):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "state.json").write_text(
            '{"last_success_utc":"2026-09-01T00:00:00Z"}\n',
            encoding="utf-8",
        )
        return self.head()

    def start_run(self, job_name, trigger, revision, *, operating_mode):
        self.owner.starts.append((job_name, trigger, revision, operating_mode))
        return f"{job_name}-run"

    def commit(self, source, **kwargs):
        assert (source / "state.json").is_file()
        self.owner.commits.append((self.namespace, kwargs))
        return SnapshotHead(
            self.namespace,
            2,
            f"{self.namespace}-successor",
            "e" * 64,
            "2026-09-02T00:00:00Z",
            kwargs["source_revision"],
            dict(kwargs["provenance"]),
        )

    def finish_run(self, run_id, **kwargs):
        self.owner.finishes.append((run_id, kwargs))


class _RunnerStore:
    def __init__(self):
        self.starts = []
        self.commits = []
        self.finishes = []
        self.retry_checks = []

    @contextmanager
    def locked(self, namespace):
        yield _RunnerLock(self, namespace)

    def restore_latest(self, namespace, destination):
        return _RunnerLock(self, namespace).restore(destination)


def _capturing_runner(mode, store, executed, **extra_environment):
    environment = {
        "POLITITRACK_MODE": mode,
        "HEALTHCHECKS_PING_URL": "https://hc-ping.com/production",
        "LEGISLATIVE_HEALTHCHECKS_PING_URL": "https://hc-ping.com/legislative",
        "PUSHOVER_API_TOKEN": "production-pushover-token",
        "PUSHOVER_USER_KEY": "production-pushover-user",
        "GMAIL_ADDRESS": "alerts@example.invalid",
        "GMAIL_APP_PASSWORD": "production-gmail-password",
        "ALERT_WEBHOOK_URL": "https://alerts.example.invalid/hook",
        "NOTIFICATION_CALLBACK_URL": "https://alerts.example.invalid/callback",
        "GH_TOKEN": "production-github-token",
        **extra_environment,
    }
    runner = JobRunner(
        store,
        repository_root=Path(__file__).resolve().parents[1],
        source_revision="a" * 40,
        environment=environment,
    )
    runner._execute = lambda command: executed.append(list(command))
    return runner


def test_runtime_mode_defaults_to_shadow_and_rejects_unknown_values():
    assert RuntimeMode.from_environment({}) is RuntimeMode.SHADOW
    assert RuntimeMode.from_environment({"POLITITRACK_MODE": "production"}) is RuntimeMode.PRODUCTION
    with pytest.raises(RuntimeModeError, match="invalid POLITITRACK_MODE"):
        RuntimeMode.from_environment({"POLITITRACK_MODE": "enabled"})


@pytest.mark.parametrize("branch", ["legislative", "executive"])
def test_shadow_trackers_suppress_notifications_and_still_commit_state(branch):
    store = _RunnerStore()
    executed = []
    runner = _capturing_runner("shadow", store, executed)

    head = runner.run(branch)

    tracker = next(command for command in executed if "government_trade_tracker.py" in " ".join(command))
    assert "--no-notify" in tracker
    healthchecks = [command for command in executed if "legislative_healthcheck.py" in " ".join(command)]
    assert all("--validate-only" in command for command in healthchecks)
    assert head.generation == 2
    assert store.commits[-1][1]["provenance"]["operating_mode"] == "shadow"
    assert store.starts[-1][3] == "shadow"
    assert not any(
        protected in " ".join(command)
        for command in executed
        for protected in ("legislative-tracker-state", "executive-tracker-state", "ai-analysis-state")
    )

    child = runner._env()
    for key in (
        "HEALTHCHECKS_PING_URL",
        "LEGISLATIVE_HEALTHCHECKS_PING_URL",
        "PUSHOVER_API_TOKEN",
        "PUSHOVER_USER_KEY",
        "GMAIL_ADDRESS",
        "GMAIL_APP_PASSWORD",
        "ALERT_WEBHOOK_URL",
        "NOTIFICATION_CALLBACK_URL",
        "GH_TOKEN",
    ):
        assert child[key] == ""
    assert child["POLITITRACK_NOTIFICATIONS_ENABLED"] == "false"
    assert child["POLITITRACK_PROTECTED_ARTIFACT_PUBLISHING"] == "false"


def test_shadow_ai_suppresses_alerts_and_still_commits_state():
    store = _RunnerStore()
    executed = []
    runner = _capturing_runner("shadow", store, executed)

    head = runner.run("ai")

    analyst = next(command for command in executed if "ai_filing_analyst.py" in " ".join(command))
    assert "--suppress-alerts" in analyst
    assert head.generation == 2
    assert store.commits[-1][1]["provenance"]["operating_mode"] == "shadow"
    assert store.starts[-1][3] == "shadow"


@pytest.mark.parametrize(
    ("job", "script", "suppression"),
    [
        ("legislative", "government_trade_tracker.py", "--no-notify"),
        ("executive", "government_trade_tracker.py", "--no-notify"),
        ("ai", "ai_filing_analyst.py", "--suppress-alerts"),
    ],
)
def test_production_mode_permits_normal_side_effect_paths(job, script, suppression):
    store = _RunnerStore()
    executed = []
    runner = _capturing_runner("production", store, executed)

    runner.run(job)

    producer = next(command for command in executed if script in " ".join(command))
    assert suppression not in producer
    child = runner._env()
    assert child["PUSHOVER_API_TOKEN"] == "production-pushover-token"
    assert child["GMAIL_APP_PASSWORD"] == "production-gmail-password"
    assert child["HEALTHCHECKS_PING_URL"] == "https://hc-ping.com/production"
    assert child["POLITITRACK_NOTIFICATIONS_ENABLED"] == "true"
    assert store.starts[-1][3] == "production"
    assert store.commits[-1][1]["provenance"]["operating_mode"] == "production"


def test_shadow_contract_is_wired_into_terraform_and_database():
    root = Path(__file__).resolve().parents[1]
    variables = (root / "deploy/runtime-v2/terraform/variables.tf").read_text(encoding="utf-8")
    infrastructure = (root / "deploy/runtime-v2/terraform/main.tf").read_text(encoding="utf-8")
    migration = (root / "migrations/20260901_runtime_v2.sql").read_text(encoding="utf-8")
    ci_workflow = (root / ".github/workflows/investor_edge_tests.yml").read_text(encoding="utf-8")
    assert 'default     = "shadow"' in variables
    assert 'name  = "POLITITRACK_MODE"' in infrastructure
    assert "producer_runtime_secrets" in infrastructure
    for marker in ("ACTIONS_", "BROKERAGE", "GITHUB_TOKEN", "GH_TOKEN", "NOTIFICATION", "NOTIFY"):
        assert marker in infrastructure
    assert "operating_mode text NOT NULL DEFAULT 'shadow'" in migration
    assert "runtime_job_runs_operating_mode_check" in migration
    assert "CHECK (operating_mode IN ('shadow', 'production'))" in migration
    assert "tests/test_create_manual_test_filing.py \\\n            tests/test_runtime_v2.py" in ci_workflow


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, _params=()):
        self.connection.statements.append(sql)
        if "pg_try_advisory_lock" in sql:
            self._row = (self.connection.acquire,)
        elif "pg_advisory_unlock" in sql:
            self._row = (True,)

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _Connection:
    def __init__(self, acquire):
        self.acquire = acquire
        self.statements = []
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def close(self):
        self.closed = True


def _store_with_connection(connection):
    store = PostgresSnapshotStore("postgresql://runtime")
    store._connect = lambda: connection
    return store


def test_failed_lock_acquisition_does_not_unlock_another_writer():
    connection = _Connection(acquire=False)
    store = _store_with_connection(connection)
    with pytest.raises(StateStoreError, match="already running"):
        with store.locked("legislative"):
            pass
    assert not any("pg_advisory_unlock" in sql for sql in connection.statements)
    assert connection.closed


def test_acquired_lock_is_released():
    connection = _Connection(acquire=True)
    store = _store_with_connection(connection)
    with store.locked("executive") as locked:
        assert locked.namespace == "executive"
    assert any("pg_advisory_unlock" in sql for sql in connection.statements)
    assert connection.closed


class _DashboardLock:
    def head(self):
        return SnapshotHead("dashboard", 1, "snapshot", "d" * 64, "2026-09-01T00:00:00Z", "a" * 40, {})

    def restore(self, destination):
        (destination / "index.html").write_text("<h1>PolitiTrack</h1>", encoding="utf-8")
        return self.head()


class _DashboardStore:
    @contextmanager
    def locked(self, namespace):
        assert namespace == "dashboard"
        yield _DashboardLock()


def test_web_app_rejects_path_escape_and_serves_snapshot():
    pytest.importorskip("flask")
    from runtime_v2.web import create_app

    app = create_app({"TESTING": True}, store=_DashboardStore())
    client = app.test_client()
    assert client.get("/healthz").status_code == 200
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-PolitiTrack-Snapshot"] == "d" * 64
    escaped = client.get("/..%2F..%2Foutside.txt")
    assert escaped.status_code == 404


class _IamConfiguration:
    uniform_bucket_level_access_enabled = True
    public_access_prevention = "enforced"


class _Blob:
    def __init__(self, name, objects):
        self.name = name
        self.objects = objects
        self.size = None
        self.generation = 1

    def upload_from_string(self, body, **_kwargs):
        self.objects[self.name] = bytes(body)

    def exists(self, **_kwargs):
        return self.name in self.objects

    def reload(self, **_kwargs):
        self.size = len(self.objects[self.name])

    def download_as_bytes(self, **_kwargs):
        return self.objects[self.name]

    def delete(self, **_kwargs):
        self.objects.pop(self.name, None)


class _Bucket:
    iam_configuration = _IamConfiguration()

    def __init__(self, name, objects):
        self.name = name
        self.objects = objects

    def reload(self, **_kwargs):
        pass

    def blob(self, name):
        return _Blob(name, self.objects)


class _StorageClient:
    def __init__(self):
        self.objects = {}
        self._bucket = None

    def bucket(self, name):
        self._bucket = _Bucket(name, self.objects)
        return self._bucket

    def list_blobs(self, _bucket, prefix):
        return [_Blob(name, self.objects) for name in sorted(self.objects) if name.startswith(prefix)]


def test_google_cloud_vault_store_round_trip():
    client = _StorageClient()
    store = GoogleCloudObjectStore("private-vault-123", client=client, max_bytes=1024)
    key = "filings/house/filer/filing/digest.pdf"
    store.put(key, b"evidence", "application/pdf")
    assert store.get(key) == b"evidence"
    assert list(store.list_objects()) == [key]
    store.delete(key)
    assert store.get(key) is None


def test_google_cloud_vault_store_requires_public_access_prevention():
    client = _StorageClient()
    bucket = client.bucket("private-vault-123")
    bucket.iam_configuration = type(
        "IamConfiguration",
        (),
        {"uniform_bucket_level_access_enabled": True, "public_access_prevention": "inherited"},
    )()
    client.bucket = lambda _name: bucket
    with pytest.raises(StorageError, match="public access prevention"):
        GoogleCloudObjectStore("private-vault-123", client=client)
