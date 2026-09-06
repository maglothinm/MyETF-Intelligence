from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one repair anchor, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Runtime v2 store: preserve writer exclusion, but do not take a writer lock to
# read one already-committed immutable snapshot.
replace_once(
    "runtime_v2/store.py",
    'class StateStoreError(RuntimeError):\n    """The durable state contract could not be satisfied."""\n\n\n@dataclass(frozen=True)\n',
    'class StateStoreError(RuntimeError):\n    """The durable state contract could not be satisfied."""\n\n\nclass NamespaceBusy(StateStoreError):\n    """A scheduled writer was coalesced because its namespace is already active."""\n\n\n@dataclass(frozen=True)\n',
)
replace_once(
    "runtime_v2/store.py",
    '            if not acquired:\n                raise StateStoreError(f"another {namespace} writer is already running")\n',
    '            if not acquired:\n                raise NamespaceBusy(f"another {namespace} writer is already running")\n',
)
replace_once(
    "runtime_v2/store.py",
    '    def restore_latest(self, namespace: str, destination: Path) -> SnapshotHead:\n        with self.locked(namespace) as locked:\n            return locked.restore(destination)\n',
    '''    def restore_latest(self, namespace: str, destination: Path) -> SnapshotHead:\n        """Restore one immutable committed head without taking its writer lock.\n\n        The head and payload are selected by one joined SQL statement. PostgreSQL\n        therefore returns either the prior committed snapshot or its committed\n        successor, never a partially published state. Taking the namespace writer\n        lock here made AI collide with active collectors and made Dashboard collide\n        with every active producer.\n        """\n        if namespace not in NAMESPACES:\n            raise StateStoreError("unknown runtime state namespace")\n        connection = self._connect()\n        try:\n            return LockedNamespace(connection, namespace).restore(destination)\n        finally:\n            connection.close()\n''',
)

# CLI: scheduled duplicate writers coalesce; manual/certification invocations still
# fail loudly so validation cannot hide an overlap defect.
replace_once("runtime_v2/cli.py", "import json\nimport re\n", "import json\nimport os\nimport re\n")
replace_once(
    "runtime_v2/cli.py",
    "from .store import NAMESPACES, PostgresSnapshotStore, StateStoreError\n",
    "from .store import NAMESPACES, NamespaceBusy, PostgresSnapshotStore, StateStoreError\n",
)
replace_once(
    "runtime_v2/cli.py",
    '            import os\n\n            config = {key: value for key, value in os.environ.items() if key.startswith("VAULT_")}\n',
    '            config = {key: value for key, value in os.environ.items() if key.startswith("VAULT_")}\n',
)
replace_once(
    "runtime_v2/cli.py",
    '    if args.command == "run":\n        head = JobRunner(store, mode=selected_mode).run(args.job)\n        print(\n',
    '''    if args.command == "run":\n        try:\n            head = JobRunner(store, mode=selected_mode).run(args.job)\n        except NamespaceBusy as exc:\n            trigger = str(os.environ.get("POLITITRACK_TRIGGER_SOURCE") or "external_scheduler")\n            if trigger != "external_scheduler":\n                raise\n            print(\n                json.dumps(\n                    {\n                        "result": "coalesced",\n                        "mode": selected_mode.value,\n                        "namespace": args.job,\n                        "reason": "writer_already_running",\n                        "detail": str(exc),\n                    },\n                    sort_keys=True,\n                )\n            )\n            return 0\n        print(\n''',
)

# Terraform: bound the AI writer cadence and make Scheduler POST payloads explicit.
replace_once(
    "deploy/runtime-v2/terraform/main.tf",
    '''    ai = {\n      schedule = "14,29,44,59 * * * *"\n      memory   = "4Gi"\n      cpu      = "2"\n    }\n''',
    '''    ai = {\n      # Twenty paced analyses can require more than 21 minutes before document\n      # fetching, model latency, retries, Investor Edge, and publication. A\n      # 15-minute writer cadence guaranteed overlapping executions under backlog.\n      schedule = "14,44 * * * *"\n      memory   = "4Gi"\n      cpu      = "2"\n    }\n''',
)
replace_once(
    "deploy/runtime-v2/terraform/main.tf",
    '''    http_method = "POST"\n    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.vault_lifecycle[0].name}:run"\n    oauth_token {\n''',
    '''    http_method = "POST"\n    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.vault_lifecycle[0].name}:run"\n    body        = base64encode("{}")\n    headers = {\n      "Content-Type" = "application/json"\n    }\n    oauth_token {\n''',
)
replace_once(
    "deploy/runtime-v2/terraform/main.tf",
    '''    http_method = "POST"\n    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.producer[each.key].name}:run"\n    oauth_token {\n''',
    '''    http_method = "POST"\n    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.producer[each.key].name}:run"\n    body        = base64encode("{}")\n    headers = {\n      "Content-Type" = "application/json"\n    }\n    oauth_token {\n''',
)

# Make the regression test part of the permanent Runtime v2 safety workflow.
replace_once(
    ".github/workflows/runtime_v2_tests.yml",
    '      - "tests/test_runtime_v2_terraform_safety.py"\n',
    '      - "tests/test_runtime_v2_terraform_safety.py"\n      - "tests/test_runtime_v2_scheduler_concurrency.py"\n',
)
replace_once(
    ".github/workflows/runtime_v2_tests.yml",
    '            tests/test_runtime_v2_terraform_safety.py \\\n',
    '            tests/test_runtime_v2_terraform_safety.py \\\n            tests/test_runtime_v2_scheduler_concurrency.py \\\n',
)

(ROOT / "tests/test_runtime_v2_scheduler_concurrency.py").write_text(
    '''from __future__ import annotations\n\nimport json\nfrom pathlib import Path\n\nimport pytest\n\nfrom runtime_v2 import cli\nfrom runtime_v2.mode import RuntimeMode\nfrom runtime_v2.store import LockedNamespace, NamespaceBusy, PostgresSnapshotStore, SnapshotHead\n\n\nROOT = Path(__file__).resolve().parents[1]\nTERRAFORM = ROOT / "deploy" / "runtime-v2" / "terraform" / "main.tf"\n\n\nclass _Connection:\n    def __init__(self) -> None:\n        self.closed = False\n\n    def close(self) -> None:\n        self.closed = True\n\n\ndef test_read_only_restore_never_enters_the_namespace_writer_lock(monkeypatch, tmp_path) -> None:\n    connection = _Connection()\n    store = object.__new__(PostgresSnapshotStore)\n    store._connect = lambda: connection\n\n    def forbidden_lock(*_args, **_kwargs):\n        raise AssertionError("read-only restore attempted to take a writer lock")\n\n    store.locked = forbidden_lock\n    expected = SnapshotHead("legislative", 12, "id", "a" * 64, "2026-09-06T00:00:00Z", "f" * 40, {})\n\n    def fake_restore(self, destination):\n        assert self.connection is connection\n        assert self.namespace == "legislative"\n        destination.mkdir(parents=True)\n        (destination / "state.json").write_text('{"last_success_utc":"2026-09-06T00:00:00Z"}\\n')\n        return expected\n\n    monkeypatch.setattr(LockedNamespace, "restore", fake_restore)\n\n    assert store.restore_latest("legislative", tmp_path / "state") == expected\n    assert connection.closed is True\n\n\ndef test_external_scheduler_coalesces_duplicate_writer(monkeypatch, capsys) -> None:\n    class _Runner:\n        def run(self, _job):\n            raise NamespaceBusy("another ai writer is already running")\n\n    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", "external_scheduler")\n    monkeypatch.setattr(cli, "resolve_runtime_mode", lambda: RuntimeMode.PRODUCTION)\n    monkeypatch.setattr(cli, "PostgresSnapshotStore", lambda: object())\n    monkeypatch.setattr(cli, "JobRunner", lambda *_args, **_kwargs: _Runner())\n\n    assert cli.main(["run", "ai"]) == 0\n    payload = json.loads(capsys.readouterr().out)\n    assert payload["result"] == "coalesced"\n    assert payload["reason"] == "writer_already_running"\n\n\ndef test_controlled_smoke_does_not_hide_a_duplicate_writer(monkeypatch) -> None:\n    class _Runner:\n        def run(self, _job):\n            raise NamespaceBusy("another ai writer is already running")\n\n    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", "phase5_smoke")\n    monkeypatch.setattr(cli, "resolve_runtime_mode", lambda: RuntimeMode.PRODUCTION)\n    monkeypatch.setattr(cli, "PostgresSnapshotStore", lambda: object())\n    monkeypatch.setattr(cli, "JobRunner", lambda *_args, **_kwargs: _Runner())\n\n    with pytest.raises(NamespaceBusy):\n        cli.main(["run", "ai"])\n\n\ndef test_scheduler_contract_bounds_ai_overlap_and_sends_json() -> None:\n    text = TERRAFORM.read_text(encoding="utf-8")\n    assert 'schedule = "14,44 * * * *"' in text\n    assert text.count('body        = base64encode("{}")') >= 2\n    assert text.count('"Content-Type" = "application/json"') >= 2\n''',
    encoding="utf-8",
)

print("Runtime v2 scheduler/concurrency repair applied")
