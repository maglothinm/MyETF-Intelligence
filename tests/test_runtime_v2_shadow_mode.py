from __future__ import annotations

import json
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
        self.successful_run_id = None
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
        successful_run_id=None,
    ):
        assert expected_parent_sha256 == "b" * 64
        assert allow_initial is False
        self.provenance = dict(provenance)
        self.successful_run_id = successful_run_id
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
    assert store.lock.successful_run_id == "run-1"
    assert "--no-notify" in commands[0]
    assert store.lock.finished == []


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


def test_run_row_persists_explicit_runtime_mode_evidence():
    connection = _CaptureConnection()
    locked = LockedNamespace(connection, "legislative")
    locked.start_run("legislative", "shadow", REVISION, "shadow")
    sql, params = connection.calls[-1]
    assert "runtime_mode" in sql
    assert "runtime_mode_evidence" in sql
    assert params[-2] == "shadow"
    assert json.loads(params[-1]) == {
        "schema_version": 1,
        "kind": "runner_explicit",
        "mode": "shadow",
    }
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


def test_quarantine_schema_records_mode_evidence_without_state_reset():
    migration = (
        ROOT / "migrations/20260904_runtime_v2_mode_quarantine.sql"
    ).read_text(encoding="utf-8")
    upper_migration = migration.upper()

    assert migration.startswith("BEGIN;")
    assert migration.rstrip().endswith("COMMIT;")
    assert "ADD COLUMN IF NOT EXISTS runtime_mode_evidence jsonb" in migration
    assert "ALTER COLUMN runtime_mode DROP NOT NULL" in migration
    assert "ALTER COLUMN runtime_mode_evidence DROP DEFAULT" in migration
    assert "ALTER COLUMN runtime_mode_evidence SET NOT NULL" in migration
    assert "ALTER COLUMN runtime_mode SET NOT NULL" not in migration
    assert "SET runtime_mode = 'production'" not in migration
    assert "DROP TABLE" not in upper_migration
    assert "DELETE FROM RUNTIME_STATE_HEADS" not in upper_migration
    assert "DELETE FROM RUNTIME_STATE_SNAPSHOTS" not in upper_migration
    assert "UPDATE runtime_state_heads" not in migration
    assert "UPDATE runtime_state_snapshots" not in migration


def test_quarantine_schema_repairs_only_exact_snapshot_attestations():
    migration = (
        ROOT / "migrations/20260904_runtime_v2_mode_quarantine.sql"
    ).read_text(encoding="utf-8")
    repair = migration[
        migration.index("UPDATE runtime_job_runs AS job_run") :
        migration.index("-- A missing immutable mode")
    ]

    assert "SET runtime_mode = snapshot.source_provenance ->> 'mode'" in repair
    assert "'kind', 'snapshot_provenance'" in repair
    assert "'previous_observed_value'" in repair
    assert "job_run.runtime_mode_evidence IS NULL" in repair
    assert "job_run.runtime_mode IS NULL" not in repair
    assert "job_run.status = 'success'" in repair
    assert "job_run.snapshot_id = snapshot.snapshot_id" in repair
    assert "job_run.snapshot_sha256 = snapshot.snapshot_sha256" in repair
    assert "job_run.namespace = snapshot.namespace" in repair
    assert "job_run.source_revision = snapshot.source_revision" in repair
    assert "snapshot.source_provenance ->> 'authority' = 'runtime_v2'" in repair
    assert "snapshot.source_provenance ->> 'job' = job_run.job_name" in repair
    assert "snapshot.source_provenance ->> 'mode' IN ('shadow', 'production')" in repair


def test_quarantine_schema_nulls_unverified_legacy_modes_and_preserves_observation():
    migration = (
        ROOT / "migrations/20260904_runtime_v2_mode_quarantine.sql"
    ).read_text(encoding="utf-8")
    quarantine = migration[
        migration.index("UPDATE runtime_job_runs\nSET runtime_mode_evidence") :
        migration.index(
            "ALTER TABLE runtime_job_runs\n"
            "    ALTER COLUMN runtime_mode_evidence DROP DEFAULT"
        )
    ]

    assert "'kind', 'legacy_unverified'" in quarantine
    assert "'observed_value', runtime_mode" in quarantine
    assert "'reason', 'no_exact_linked_snapshot_mode'" in quarantine
    assert "runtime_mode = NULL" in quarantine
    assert "WHERE runtime_mode_evidence IS NULL" in quarantine


def test_quarantine_schema_rejects_unattested_or_mismatched_effective_modes():
    migration = (
        ROOT / "migrations/20260904_runtime_v2_mode_quarantine.sql"
    ).read_text(encoding="utf-8")

    repair = migration.index("UPDATE runtime_job_runs AS job_run")
    quarantine = migration.index("UPDATE runtime_job_runs\nSET runtime_mode_evidence")
    evidence_not_null = migration.index(
        "ALTER COLUMN runtime_mode_evidence SET NOT NULL"
    )
    cross_table_guard = migration.index(
        "-- JSON evidence is not allowed to self-attest."
    )
    commit = migration.rindex("COMMIT;")

    assert repair < quarantine < evidence_not_null < cross_table_guard < commit
    assert "ADD CONSTRAINT runtime_job_runs_mode_evidence_check" in migration
    assert "runtime_mode_evidence ->> 'kind' = 'legacy_unverified'" in migration
    assert "runtime_mode IS NULL" in migration
    assert "runtime_mode_evidence ->> 'kind' = 'runner_explicit'" in migration
    assert "runtime_mode_evidence ->> 'mode' = runtime_mode" in migration
    assert "status IN ('running', 'failure', 'skipped')" in migration
    assert "runtime_mode_evidence ->> 'kind' = 'snapshot_provenance'" in migration
    assert "status = 'success'" in migration
    assert "snapshot_id IS NOT NULL" in migration
    assert "snapshot_sha256 IS NOT NULL" in migration
    assert (
        "runtime mode evidence is not exactly linked to snapshot provenance"
        in migration
    )
