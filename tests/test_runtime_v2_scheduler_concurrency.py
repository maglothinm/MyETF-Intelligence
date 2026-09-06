from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime_v2 import cli
from runtime_v2.mode import RuntimeMode
from runtime_v2.store import LockedNamespace, NamespaceBusy, PostgresSnapshotStore, SnapshotHead


ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "deploy" / "runtime-v2" / "terraform" / "main.tf"


class _Connection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_read_only_restore_never_enters_the_namespace_writer_lock(monkeypatch, tmp_path) -> None:
    connection = _Connection()
    store = object.__new__(PostgresSnapshotStore)
    store._connect = lambda: connection

    def forbidden_lock(*_args, **_kwargs):
        raise AssertionError("read-only restore attempted to take a writer lock")

    store.locked = forbidden_lock
    expected = SnapshotHead("legislative", 12, "id", "a" * 64, "2026-09-06T00:00:00Z", "f" * 40, {})

    def fake_restore(self, destination):
        assert self.connection is connection
        assert self.namespace == "legislative"
        destination.mkdir(parents=True)
        (destination / "state.json").write_text('{"last_success_utc":"2026-09-06T00:00:00Z"}\n')
        return expected

    monkeypatch.setattr(LockedNamespace, "restore", fake_restore)

    assert store.restore_latest("legislative", tmp_path / "state") == expected
    assert connection.closed is True


def test_external_scheduler_coalesces_duplicate_writer(monkeypatch, capsys) -> None:
    class _Runner:
        def run(self, _job):
            raise NamespaceBusy("another ai writer is already running")

    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", "external_scheduler")
    monkeypatch.setattr(cli, "resolve_runtime_mode", lambda: RuntimeMode.PRODUCTION)
    monkeypatch.setattr(cli, "PostgresSnapshotStore", lambda: object())
    monkeypatch.setattr(cli, "JobRunner", lambda *_args, **_kwargs: _Runner())

    assert cli.main(["run", "ai"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "coalesced"
    assert payload["reason"] == "writer_already_running"


def test_controlled_smoke_does_not_hide_a_duplicate_writer(monkeypatch) -> None:
    class _Runner:
        def run(self, _job):
            raise NamespaceBusy("another ai writer is already running")

    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", "phase5_smoke")
    monkeypatch.setattr(cli, "resolve_runtime_mode", lambda: RuntimeMode.PRODUCTION)
    monkeypatch.setattr(cli, "PostgresSnapshotStore", lambda: object())
    monkeypatch.setattr(cli, "JobRunner", lambda *_args, **_kwargs: _Runner())

    with pytest.raises(NamespaceBusy):
        cli.main(["run", "ai"])


def test_scheduler_contract_bounds_ai_overlap_and_sends_json() -> None:
    text = TERRAFORM.read_text(encoding="utf-8")
    assert 'schedule = "14,44 * * * *"' in text
    assert text.count('body        = base64encode("{}")') >= 2
    assert text.count('"Content-Type" = "application/json"') >= 2
