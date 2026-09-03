from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

import runtime_v2.cli as runtime_cli
from runtime_v2.mode import RuntimeMode, RuntimeModeError, resolve_runtime_mode
from runtime_v2.runner import JobRunner
from runtime_v2.store import LockedNamespace, SnapshotHead, StateStoreError


ROOT = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def _runner(mode: str, **environment: str) -> JobRunner:
    values = {"POLITITRACK_MODE": mode, **environment}
    return JobRunner(
        object(),
        repository_root=ROOT,
        source_revision=REVISION,
        environment=values,
        mode=mode,
    )


@pytest.mark.parametrize(
    "environment",
    ({}, {"POLITITRACK_MODE": ""}, {"POLITITRACK_MODE": "unsafe"}),
)
def test_runtime_mode_is_required_and_closed(environment):
    with pytest.raises(RuntimeModeError):
        resolve_runtime_mode(environment)


def test_runtime_mode_is_normalized():
    assert resolve_runtime_mode({"POLITITRACK_MODE": " Shadow "}) is RuntimeMode.SHADOW
    assert resolve_runtime_mode({"POLITITRACK_MODE": "PRODUCTION"}) is RuntimeMode.PRODUCTION


def test_cli_rejects_missing_mode_before_constructing_store(monkeypatch):
    monkeypatch.delenv("POLITITRACK_MODE", raising=False)
    constructed = False

    def forbidden_store():
        nonlocal constructed
        constructed = True
        raise AssertionError("database construction must not occur")

    monkeypatch.setattr(runtime_cli, "PostgresSnapshotStore", forbidden_store)
    with pytest.raises(RuntimeModeError):
        runtime_cli.main(["run", "legislative"])
    assert constructed is False


def test_runner_rejects_missing_or_conflicting_mode():
    with pytest.raises(RuntimeModeError):
        JobRunner(
            object(),
            repository_root=ROOT,
            source_revision=REVISION,
            environment={},
        )
    with pytest.raises(RuntimeModeError, match="conflicts"):
        JobRunner(
            object(),
            repository_root=ROOT,
            source_revision=REVISION,
            environment={"POLITITRACK_MODE": "production"},
            mode="shadow",
        )


def test_shadow_tracker_commands_always_disable_notifications(tmp_path):
    runner = _runner("shadow")
    for branch in ("legislative", "executive"):
        command = runner._tracker_command(branch, tmp_path / "state", tmp_path / "output")
        assert "--no-notify" in command


def test_shadow_ai_command_always_suppresses_alerts(tmp_path):
    runner = _runner("shadow", SUPPRESS_ALERTS="false")
    command = runner._ai_command(
        tmp_path / "legislative",
        tmp_path / "executive",
        tmp_path / "ai",
        tmp_path,
    )
    assert "--suppress-alerts" in command


def test_production_command_behavior_is_not_forced_into_shadow(tmp_path):
    runner = _runner("production")
    tracker = runner._tracker_command("legislative", tmp_path / "state", tmp_path / "output")
    ai = runner._ai_command(
        tmp_path / "legislative",
        tmp_path / "executive",
        tmp_path / "ai",
        tmp_path,
    )
    assert "--no-notify" not in tracker
    assert "--suppress-alerts" not in ai


def test_production_explicit_suppression_still_works(tmp_path):
    runner = _runner(
        "production",
        SUPPRESS_NOTIFICATIONS="true",
        SUPPRESS_ALERTS="true",
    )
    tracker = runner._tracker_command("executive", tmp_path / "state", tmp_path / "output")
    ai = runner._ai_command(
        tmp_path / "legislative",
        tmp_path / "executive",
        tmp_path / "ai",
        tmp_path,
    )
    assert "--no-notify" in tracker
    assert "--suppress-alerts" in ai


def test_shadow_environment_strips_external_delivery_and_actions_credentials():
    runner = _runner(
        "shadow",
        OPENAI_API_KEY="read-capability-retained",
        FINNHUB_API_KEY="read-capability-retained",
        PUSHOVER_API_TOKEN="blocked",
        GMAIL_APP_PASSWORD="blocked",
        LEGISLATIVE_HEALTHCHECKS_PING_URL="blocked",
        CUSTOM_CALLBACK_URL="blocked",
        GITHUB_TOKEN="blocked",
        ACTIONS_RUNTIME_TOKEN="blocked",
    )
    environment = runner._env()
    assert environment["POLITITRACK_MODE"] == "shadow"
    assert environment["POLITITRACK_TRIGGER_SOURCE"] == "shadow"
    assert environment["SUPPRESS_ALERTS"] == "true"
    assert environment["SUPPRESS_NOTIFICATIONS"] == "true"
    assert environment["OPENAI_API_KEY"] == "read-capability-retained"
    assert environment["FINNHUB_API_KEY"] == "read-capability-retained"
    for key in (
        "PUSHOVER_API_TOKEN",
        "GMAIL_APP_PASSWORD",
        "LEGISLATIVE_HEALTHCHECKS_PING_URL",
        "CUSTOM_CALLBACK_URL",
        "GITHUB_TOKEN",
        "ACTIONS_RUNTIME_TOKEN",
    ):
        assert key not in environment


def test_production_environment_retains_delivery_configuration():
    runner = _runner(
        "production",
        PUSHOVER_API_TOKEN="retained",
        LEGISLATIVE_HEALTHCHECKS_PING_URL="retained",
    )
    environment = runner._env()
    assert environment["POLITITRACK_TRIGGER_SOURCE"] == "external_scheduler"
    assert environment["PUSHOVER_API_TOKEN"] == "retained"
    assert environment["LEGISLATIVE_HEALTHCHECKS_PING_URL"] == "retained"


class _RunLock:
    def __init__(self, namespace: str):
        self.namespace = namespace
        self.started = []
        self.provenance = None
        self.finished = []

    def assert_retry_safe(self):
        return None

    def restore(self, destination: Path):
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "state.json").write_text(
            '{"last_success_utc":"2026-09-02T00:00:00Z"}\n',
            encoding="utf-8",
        )
        return SnapshotHead(
            self.namespace,
            1,
            "snapshot-1",
            "b" * 64,
            "2026-09-02T00:00:00Z",
            REVISION,
            {},
        )

    def start_run(self, job_name, trigger_source, source_revision, runtime_mode):
        self.started.append((job_name, trigger_source, source_revision, runtime_mode))
        return "run-1"

    def commit(
        self,
        _source,
        *,
        expected_parent_sha256,
        source_revision,
        provenance,
        allow_initial=False,
    ):
        assert expected_parent_sha256 == "b" * 64
        assert allow_initial is False
        self.provenance = dict(provenance)
        return SnapshotHead(
            self.namespace,
            2,
            "snapshot-2",
            "c" * 64,
            "2026-09-02T00:01:00Z",
            source_revision,
            dict(provenance),
        )

    def finish_run(self, run_id, **values):
        self.finished.append((run_id, values))


class _RunStore:
    def __init__(self):
        self.lock = _RunLock("legislative")

    @contextmanager
    def locked(self, namespace):
        assert namespace == "legislative"
        yield self.lock


def test_shadow_run_and_snapshot_evidence_record_mode(monkeypatch):
    store = _RunStore()
    runner = JobRunner(
        store,
        repository_root=ROOT,
        source_revision=REVISION,
        environment={"POLITITRACK_MODE": "shadow"},
    )
    commands = []
    monkeypatch.setattr(runner, "_execute", lambda args: commands.append(list(args)))

    head = runner.run("legislative")

    assert head.provenance["mode"] == "shadow"
    assert store.lock.started == [("legislative", "shadow", REVISION, "shadow")]
    assert store.lock.provenance["mode"] == "shadow"
    assert "--no-notify" in commands[0]
    assert store.lock.finished[-1][1]["status"] == "success"


class _CaptureCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.connection.calls.append((sql, params))

    def close(self):
        return None


class _CaptureConnection:
    def __init__(self):
        self.calls = []

    def cursor(self):
        return _CaptureCursor(self)


def test_run_row_persists_runtime_mode():
    connection = _CaptureConnection()
    locked = LockedNamespace(connection, "legislative")
    locked.start_run("legislative", "shadow", REVISION, "shadow")
    sql, params = connection.calls[-1]
    assert "runtime_mode" in sql
    assert params[-1] == "shadow"
    with pytest.raises(StateStoreError, match="invalid"):
        locked.start_run("legislative", "shadow", REVISION, "unsafe")


def test_terraform_defaults_to_shadow_and_keeps_schedules_gated():
    variables = (ROOT / "deploy/runtime-v2/terraform/variables.tf").read_text(encoding="utf-8")
    safety = (ROOT / "deploy/runtime-v2/terraform/safety.tf").read_text(encoding="utf-8")
    example = (ROOT / "deploy/runtime-v2/terraform/terraform.tfvars.example").read_text(
        encoding="utf-8"
    )
    assert 'POLITITRACK_MODE = "shadow"' in variables
    assert 'POLITITRACK_MODE = "shadow"' in example
    assert "!var.schedules_enabled" in safety
    assert '== "production"' in safety


def test_schema_records_runtime_mode_without_state_reset():
    migration = (ROOT / "migrations/20260901_runtime_v2.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS runtime_mode" in migration
    assert "runtime_mode IN ('shadow', 'production')" in migration
    assert "DROP TABLE" not in migration.upper()
