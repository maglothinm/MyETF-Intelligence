"""Behavioral failure injection for protected artifact authority and publication."""
from __future__ import annotations

import copy
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest

from scripts import protected_state as ps

REPO = "owner/PolitiTrack"
SHA = "a" * 40
OLD_SHA = "b" * 40
START = "2026-08-30T10:00:00Z"
CREATED = "2026-08-30T10:01:00Z"
FINISH = "2026-08-30T10:02:00Z"
NEXT_START = "2026-08-30T10:03:00Z"
NEXT_SEAL = "2026-08-30T10:04:00Z"
NEXT_CREATED = "2026-08-30T10:05:00Z"
NEXT_FINISH = "2026-08-30T10:06:00Z"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ps.canonical_bytes(value))


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def run_row(run_id: int = 200, *, start: str = START, finish: str = FINISH) -> dict:
    return {"run_key": f"{run_id}:1", "started_utc": start, "finished_utc": finish, "success": True, "errors": [], "run_url": f"https://github.com/{REPO}/actions/runs/{run_id}"}


def fixture_state(root: Path, pipeline: str = "legislative") -> Path:
    common = {"version": 1, "last_attempt_utc": START, "last_success_utc": FINISH}
    if pipeline == "ai":
        state = {**common, "completed_analysis_ids": {}, "candidate_alert_deliveries": {}, "positions": {}, "last_portfolio_refresh_utc": None}
        write_rows(root / "analyses.jsonl", [])
        write_json(root / "investor-edge-profiles.json", {"version": "v1", "profiles": {}})
        write_json(root / "investor-edge-observations.json", {"version": "v1", "observations": {}})
        write_json(root / "investor-edge-leaderboard.json", {"version": "v1", "generated_utc": FINISH, "investors": []})
    else:
        state = {**common, "seen_filings": {"house": {"h1": START}, "senate": {"s1": START}, "oge": {}}, "seen_trades": {}, "seen_reviews": {}, "last_counts": {}}
        for name in ("filings.jsonl", "pending-review.jsonl", "transactions.jsonl", "purchases.jsonl"):
            write_rows(root / name, [])
    write_json(root / "state.json", state)
    write_rows(root / "runs.jsonl", [run_row()])
    return root


def archive_directory(root: Path) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                zipped.writestr(path.relative_to(root).as_posix(), path.read_bytes())
    return output.getvalue()


class FakeAPI(ps.GitHubAPI):
    def __init__(self):
        super().__init__()
        self.routes: dict[str, object] = {}
        self.blobs: dict[str, bytes] = {}
        self.fail_paths: set[str] = set()
        self.calls: list[str] = []

    def json(self, path: str):
        self.calls.append(path)
        if path in self.fail_paths:
            raise ps.StateSafetyError("injected GitHub API failure")
        if path not in self.routes:
            raise AssertionError(f"Unexpected API request: {path}")
        return copy.deepcopy(self.routes[path])

    def bytes(self, path: str):
        self.calls.append(path)
        if path in self.fail_paths:
            raise ps.StateSafetyError("injected GitHub API failure")
        return self.blobs[path]


def run_payload(run_id: int = 200, *, attempts: int = 1, updated: str = FINISH, pipeline: str = "legislative") -> dict:
    spec = ps.PIPELINES[pipeline]
    return {"id": run_id, "name": spec.display_name, "path": spec.path, "repository": {"id": ps.REPOSITORY_ID}, "head_branch": "main", "head_sha": SHA, "run_attempt": attempts, "run_started_at": START, "updated_at": updated, "conclusion": "success"}


def job_payload(job_id: int = 2001, *, start: str = START, finish: str | None = FINISH, pipeline: str = "legislative") -> dict:
    return {"id": job_id, "name": ps.PIPELINES[pipeline].job, "status": "completed" if finish else "in_progress", "conclusion": "success" if finish else None, "started_at": start, "completed_at": finish}


def set_jobs(api: FakeAPI, run_id: int, attempt: int, jobs: list[dict]) -> None:
    api.routes[f"/repos/{REPO}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100&page=1"] = {"total_count": len(jobs), "jobs": jobs}


@pytest.fixture
def scenario(tmp_path: Path):
    root = fixture_state(tmp_path / "checkpoint")
    archive = archive_directory(root)
    snapshot = ps.snapshot_directory(root, "legislative")
    api = FakeAPI()
    api.routes[f"/repositories/{ps.REPOSITORY_ID}"] = {"id": ps.REPOSITORY_ID, "full_name": REPO, "default_branch": "main", "archived": False}
    api.routes[f"/repos/{REPO}/git/ref/heads/main"] = {"object": {"sha": SHA}}
    api.routes[f"/repos/{REPO}/compare/{SHA}...{SHA}"] = {"status": "identical"}
    artifact = {"id": 501, "name": "legislative-tracker-state", "expired": False, "created_at": CREATED, "digest": "sha256:" + ps.digest(archive), "workflow_run": {"id": 200}}
    artifact_path = f"/repos/{REPO}/actions/artifacts?name=legislative-tracker-state&per_page=100&page=1"
    api.routes[artifact_path] = {"total_count": 1, "artifacts": [artifact]}
    source_run = run_payload()
    current = run_payload(300, updated=NEXT_SEAL)
    current.update({"conclusion": None, "run_started_at": NEXT_START})
    api.routes[f"/repos/{REPO}/actions/runs/200"] = source_run
    api.routes[f"/repos/{REPO}/actions/runs/200/attempts/1"] = source_run
    api.routes[f"/repos/{REPO}/actions/runs/300/attempts/1"] = current
    run_list = f"/repos/{REPO}/actions/runs?per_page=100&page=1"
    api.routes[run_list] = {"total_count": 2, "workflow_runs": [current, source_run]}
    set_jobs(api, 200, 1, [job_payload()])
    set_jobs(api, 300, 1, [job_payload(3001, start=NEXT_START, finish=None)])
    api.blobs[f"/repos/{REPO}/actions/artifacts/501/zip"] = archive
    entry = {"pipeline": "legislative", "run_id": 200, "run_attempt": 1, "head_sha": SHA, "workflow_path": ps.PIPELINES["legislative"].path, "workflow_name": ps.PIPELINES["legislative"].display_name, "job_name": "track", "job_id": 2001, "created_at": CREATED, "zip_sha256": ps.digest(archive), "files": snapshot["files"], "absent_files": snapshot["absent_files"], "evidence": "verified offline test fixture"}
    allow = {"version": 1, "repository_id": ps.REPOSITORY_ID, "default_branch": "main", "artifacts": {"501": entry}}
    allow_path = tmp_path / "allowlist.json"
    write_json(allow_path, allow)
    env = {"GITHUB_REPOSITORY_ID": str(ps.REPOSITORY_ID), "GITHUB_REPOSITORY": REPO, "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "300", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "track"}
    return {"api": api, "root": root, "archive": archive, "snapshot": snapshot, "artifact": artifact, "artifact_path": artifact_path, "run_list": run_list, "allow": allow, "allow_path": allow_path, "env": env, "tmp": tmp_path}


def restore(scenario: dict, **overrides):
    args = dict(api=scenario["api"], pipeline="legislative", destination=scenario["tmp"] / "restored", receipt_path=scenario["tmp"] / "receipt.json", consumer_sha=SHA, env=scenario["env"], allowlist_path=scenario["allow_path"])
    args.update(overrides)
    return ps.restore(**args)


def test_verified_premanifest_migration_preserves_every_byte(scenario):
    receipt = restore(scenario)
    assert receipt["generation"] == 0
    assert receipt["selected"]["artifact_id"] == 501
    assert ps.snapshot_directory(scenario["tmp"] / "restored", "legislative") == scenario["snapshot"]


@pytest.mark.parametrize("field", ["seen_trades", "seen_reviews", "seen_filings", "last_counts", "last_success_utc"])
def test_missing_state_fields_never_default_to_empty(tmp_path, field):
    root = fixture_state(tmp_path / "state")
    state = ps.read_json(root / "state.json")
    del state[field]
    write_json(root / "state.json", state)
    with pytest.raises(ps.StateSafetyError, match="missing"):
        ps.snapshot_directory(root, "legislative")


@pytest.mark.parametrize("name", ["filings.jsonl", "transactions.jsonl", "purchases.jsonl", "pending-review.jsonl", "runs.jsonl", "state.json"])
def test_missing_required_ledgers_block(tmp_path, name):
    root = fixture_state(tmp_path / "state")
    (root / name).unlink()
    with pytest.raises(ps.StateSafetyError, match="Missing"):
        ps.snapshot_directory(root, "legislative")


@pytest.mark.parametrize("data", [b'{broken}\n', b'[]\n', b'{}', b'\n', b'{"run_key":"x","run_key":"y"}\n', b'{"x":NaN}\n'])
def test_malformed_or_ambiguous_jsonl_blocks(tmp_path, data):
    root = fixture_state(tmp_path / "state")
    (root / "runs.jsonl").write_bytes(data)
    with pytest.raises(ps.StateSafetyError):
        ps.snapshot_directory(root, "legislative")


@pytest.mark.parametrize("field", ["positions", "completed_analysis_ids", "candidate_alert_deliveries"])
def test_missing_ai_maps_block(tmp_path, field):
    root = fixture_state(tmp_path / "ai", "ai")
    state = ps.read_json(root / "state.json")
    del state[field]
    write_json(root / "state.json", state)
    with pytest.raises(ps.StateSafetyError, match="missing"):
        ps.snapshot_directory(root, "ai")


@pytest.mark.parametrize("field", ["positions", "candidate_alert_deliveries"])
def test_malformed_ai_entries_are_not_silently_discarded(tmp_path, field):
    root = fixture_state(tmp_path / "ai", "ai")
    state = ps.read_json(root / "state.json")
    state[field]["keep-me"] = 7
    write_json(root / "state.json", state)
    with pytest.raises(ps.StateSafetyError, match="object"):
        ps.snapshot_directory(root, "ai")


@pytest.mark.parametrize("name", ["investor-edge-profiles.json", "investor-edge-observations.json", "investor-edge-leaderboard.json"])
def test_corrupt_or_missing_edge_history_blocks(tmp_path, name):
    root = fixture_state(tmp_path / "ai", "ai")
    (root / name).write_bytes(b"broken")
    with pytest.raises(ps.StateSafetyError, match="malformed"):
        ps.snapshot_directory(root, "ai")


@pytest.mark.parametrize("filename", ["../state.json", "/state.json", "C:/state.json", "..\\state.json"])
def test_zip_traversal_blocks_before_extract(tmp_path, filename):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(filename, b"{}")
    with pytest.raises(ps.StateSafetyError, match="Unsafe archive path"):
        ps.safe_extract(output.getvalue(), tmp_path / "staging")


def test_zip_symlink_blocks(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        entry = zipfile.ZipInfo("state.json")
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, "outside")
    with pytest.raises(ps.StateSafetyError, match="symlink"):
        ps.safe_extract(output.getvalue(), tmp_path / "staging")


def test_multiple_zip_state_roots_block(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("a/state.json", "{}")
        archive.writestr("b/state.json", "{}")
    with pytest.raises(ps.StateSafetyError, match="exactly one"):
        ps.safe_extract(output.getvalue(), tmp_path / "staging")


@pytest.mark.parametrize("key,value", [("GITHUB_REPOSITORY_ID", "123"), ("GITHUB_REPOSITORY", "owner/fork"), ("GITHUB_REF", "refs/heads/other")])
def test_wrong_runtime_identity_blocks_without_install(scenario, key, value):
    scenario["env"][key] = value
    with pytest.raises(ps.StateSafetyError):
        restore(scenario)
    assert not (scenario["tmp"] / "restored").exists()


def test_wrong_default_branch_blocks(scenario):
    scenario["api"].routes[f"/repositories/{ps.REPOSITORY_ID}"]["default_branch"] = "other"
    with pytest.raises(ps.StateSafetyError, match="default branch"):
        restore(scenario)


def test_stale_writer_commit_blocks(scenario):
    with pytest.raises(ps.StateSafetyError, match="Stale-code"):
        restore(scenario, consumer_sha=OLD_SHA)


def test_foreign_producer_sha_blocks(scenario):
    scenario["api"].routes[f"/repos/{REPO}/compare/{SHA}...{SHA}"] = {"status": "diverged"}
    with pytest.raises(ps.StateSafetyError, match="ancestor"):
        restore(scenario)


@pytest.mark.parametrize("mutation,match", [({"expired": True}, "expired"), ({"digest": "sha256:" + "0" * 64}, "digest"), ({"workflow_run": {}}, "producer run")])
def test_invalid_newest_artifact_blocks(scenario, mutation, match):
    scenario["api"].routes[scenario["artifact_path"]]["artifacts"][0].update(mutation)
    with pytest.raises(ps.StateSafetyError, match=match):
        restore(scenario)


def test_no_artifact_is_not_bootstrap_authorization(scenario):
    scenario["api"].routes[scenario["artifact_path"]] = {"total_count": 0, "artifacts": []}
    with pytest.raises(ps.StateSafetyError, match="blank initialization"):
        restore(scenario)


def test_unexpected_newer_workflow_blocks_instead_of_older_fallback(scenario):
    newer = {**scenario["artifact"], "id": 502, "created_at": NEXT_CREATED, "workflow_run": {"id": 250}}
    scenario["api"].routes[scenario["artifact_path"]] = {"total_count": 2, "artifacts": [scenario["artifact"], newer]}
    scenario["api"].routes[f"/repos/{REPO}/actions/runs/250"] = {**run_payload(250), "path": ".github/workflows/retired-writer.yml"}
    with pytest.raises(ps.StateSafetyError, match="Unexpected producer"):
        restore(scenario)


def test_later_successful_attempt_of_lower_run_id_blocks(scenario):
    older = run_payload(100, attempts=2, updated=NEXT_FINISH)
    scenario["api"].routes[scenario["run_list"]]["workflow_runs"].append(older)
    scenario["api"].routes[scenario["run_list"]]["total_count"] = 3
    set_jobs(scenario["api"], 100, 1, [job_payload(1001, start="2026-08-29T10:00:00Z", finish="2026-08-29T10:02:00Z")])
    set_jobs(scenario["api"], 100, 2, [job_payload(1002, start=NEXT_START, finish=NEXT_FINISH)])
    with pytest.raises(ps.StateSafetyError, match="high-water.*100/2"):
        restore(scenario)


def test_later_successful_job_in_failed_run_still_blocks(scenario):
    newer = run_payload(250, updated=NEXT_FINISH)
    newer["conclusion"] = "failure"
    scenario["api"].routes[scenario["run_list"]]["workflow_runs"].append(newer)
    scenario["api"].routes[scenario["run_list"]]["total_count"] = 3
    set_jobs(scenario["api"], 250, 1, [job_payload(2501, start=NEXT_START, finish=NEXT_FINISH)])
    with pytest.raises(ps.StateSafetyError, match="high-water"):
        restore(scenario)


def test_later_retired_writer_without_artifact_still_blocks(scenario):
    retired = run_payload(100, updated=NEXT_FINISH)
    retired.update({"name": "Legislative purchase tracker", "path": ".github/workflows/legislative_trade_tracker.yml"})
    scenario["api"].routes[scenario["run_list"]]["workflow_runs"].append(retired)
    scenario["api"].routes[scenario["run_list"]]["total_count"] = 3
    set_jobs(scenario["api"], 100, 1, [job_payload(1001, start=NEXT_START, finish=NEXT_FINISH)])
    with pytest.raises(ps.StateSafetyError, match="Unexpected protected producer"):
        restore(scenario)


def test_skipped_nondefault_branch_is_not_mistaken_for_a_producer(scenario):
    branch_run = run_payload(100, updated=NEXT_FINISH)
    branch_run["head_branch"] = "test-branch"
    scenario["api"].routes[scenario["run_list"]]["workflow_runs"].append(branch_run)
    scenario["api"].routes[scenario["run_list"]]["total_count"] = 3
    skipped = job_payload(1001, start=NEXT_START, finish=NEXT_FINISH)
    skipped["conclusion"] = "skipped"
    set_jobs(scenario["api"], 100, 1, [skipped])
    assert restore(scenario)["selected"]["artifact_id"] == 501


def test_exact_attempt_failure_is_not_hidden_by_aggregate_success(scenario):
    scenario["api"].routes[f"/repos/{REPO}/actions/runs/200/attempts/1"] = {**run_payload(), "conclusion": "failure"}
    with pytest.raises(ps.StateSafetyError, match="unsuccessful exact"):
        restore(scenario)


def test_artifact_outside_job_window_blocks(scenario):
    scenario["api"].routes[scenario["artifact_path"]]["artifacts"][0]["created_at"] = NEXT_CREATED
    with pytest.raises(ps.StateSafetyError, match="map uniquely"):
        restore(scenario)


def test_duplicate_authoritative_jobs_are_ambiguous(scenario):
    set_jobs(scenario["api"], 200, 1, [job_payload(), job_payload(2002)])
    with pytest.raises(ps.StateSafetyError, match="ambiguous"):
        restore(scenario)


@pytest.mark.parametrize("route", ["repository", "artifacts", "attempt", "jobs", "runs", "archive"])
def test_api_failure_never_installs_partial_state(scenario, route):
    paths = {"repository": f"/repositories/{ps.REPOSITORY_ID}", "artifacts": scenario["artifact_path"], "attempt": f"/repos/{REPO}/actions/runs/200/attempts/1", "jobs": f"/repos/{REPO}/actions/runs/200/attempts/1/jobs?per_page=100&page=1", "runs": scenario["run_list"], "archive": f"/repos/{REPO}/actions/artifacts/501/zip"}
    scenario["api"].fail_paths.add(paths[route])
    with pytest.raises(ps.StateSafetyError, match="injected"):
        restore(scenario)
    assert not (scenario["tmp"] / "restored").exists()
    assert not (scenario["tmp"] / "receipt.json").exists()


@pytest.mark.parametrize("mutation", ["not_allowed", "zip_hash", "file_hash", "file_size", "row_count", "run_attempt"])
def test_premanifest_exception_requires_exact_verified_allowlist(scenario, mutation):
    entry = scenario["allow"]["artifacts"]["501"]
    if mutation == "not_allowed":
        scenario["allow"]["artifacts"] = {}
    elif mutation == "zip_hash":
        entry["zip_sha256"] = "0" * 64
    elif mutation == "run_attempt":
        entry["run_attempt"] = 2
    else:
        field = {"file_hash": "sha256", "file_size": "size", "row_count": "rows"}[mutation]
        entry["files"]["runs.jsonl"][field] = "0" * 64 if field == "sha256" else 999
    write_json(scenario["allow_path"], scenario["allow"])
    with pytest.raises(ps.StateSafetyError):
        restore(scenario)
    assert not (scenario["tmp"] / "restored").exists()


def test_existing_destination_is_never_replaced(scenario):
    destination = scenario["tmp"] / "restored"
    destination.mkdir()
    (destination / "user-data").write_text("preserve")
    with pytest.raises(ps.StateSafetyError, match="already exists"):
        restore(scenario)
    assert (destination / "user-data").read_text() == "preserve"


@pytest.mark.parametrize("mutation", ["prefix", "remove_file", "drop_filing_id", "regress_time"])
def test_successor_preserves_bytes_and_ids(scenario, mutation):
    before = scenario["snapshot"]
    root = scenario["root"]
    if mutation == "prefix":
        write_rows(root / "runs.jsonl", [run_row(999)])
    elif mutation == "remove_file":
        # Optional legacy cache/ledger disappearance is caught too.
        before = copy.deepcopy(before)
        before["files"]["notification-outbox.jsonl"] = {"size": 0, "sha256": ps.digest(b""), "rows": 0}
    else:
        state = ps.read_json(root / "state.json")
        if mutation == "drop_filing_id":
            state["seen_filings"]["house"] = {}
        else:
            state["last_success_utc"] = START
        write_json(root / "state.json", state)
    with pytest.raises(ps.StateSafetyError):
        ps.assert_continuity(before, ps.snapshot_directory(root, "legislative"), root, "legislative")


def test_append_only_successor_can_be_sealed(scenario, monkeypatch):
    restore(scenario)
    root = scenario["tmp"] / "restored"
    with (root / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run_row(300, start=NEXT_START, finish=NEXT_SEAL)) + "\n")
    state = ps.read_json(root / "state.json")
    state["last_success_utc"] = NEXT_SEAL
    write_json(root / "state.json", state)
    monkeypatch.setattr(ps, "utc_now", lambda: NEXT_SEAL)
    manifest = ps.seal(api=scenario["api"], pipeline="legislative", directory=root, receipt_path=scenario["tmp"] / "receipt.json", consumer_sha=SHA, env=scenario["env"])
    assert manifest["generation"] == 1
    assert manifest["predecessor"]["artifact_id"] == 501
    assert manifest["inventory"]["files"]["runs.jsonl"]["rows"] == 2
    assert ps.read_json(root / ps.MANIFEST_NAME) == manifest


def test_authority_advancing_between_restore_and_seal_blocks(scenario):
    restore(scenario)
    scenario["api"].routes[scenario["artifact_path"]]["artifacts"][0]["id"] = 999
    with pytest.raises(ps.StateSafetyError, match="advanced after restore"):
        ps.seal(api=scenario["api"], pipeline="legislative", directory=scenario["tmp"] / "restored", receipt_path=scenario["tmp"] / "receipt.json", consumer_sha=SHA, env=scenario["env"])
    assert not (scenario["tmp"] / "restored" / ps.MANIFEST_NAME).exists()


def test_pagination_fetches_beyond_first_hundred_and_rejects_truncation():
    api = FakeAPI()
    api.routes["/items?per_page=100&page=1"] = {"total_count": 101, "artifacts": [{"id": i} for i in range(100)]}
    api.routes["/items?per_page=100&page=2"] = {"total_count": 101, "artifacts": [{"id": 100}]}
    assert len(api.pages("/items", "artifacts")) == 101
    api.routes["/items?per_page=100&page=2"] = {"total_count": 102, "artifacts": [{"id": 100}]}
    with pytest.raises(ps.StateSafetyError, match="Incomplete"):
        api.pages("/items", "artifacts")


def test_repeated_pagination_fails_closed():
    api = FakeAPI()
    batch = [{"id": i} for i in range(100)]
    api.routes["/items?per_page=100&page=1"] = {"artifacts": batch}
    api.routes["/items?per_page=100&page=2"] = {"artifacts": batch}
    with pytest.raises(ps.StateSafetyError, match="repeated"):
        api.pages("/items", "artifacts")


def test_full_manifest_detects_mutations(scenario, monkeypatch):
    restore(scenario)
    root = scenario["tmp"] / "restored"
    with (root / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run_row(300, start=NEXT_START, finish=NEXT_SEAL)) + "\n")
    monkeypatch.setattr(ps, "utc_now", lambda: NEXT_SEAL)
    manifest = ps.seal(api=scenario["api"], pipeline="legislative", directory=root, receipt_path=scenario["tmp"] / "receipt.json", consumer_sha=SHA, env=scenario["env"])
    selected = {"artifact_id": 502, "created_at": NEXT_CREATED, "producer": manifest["producer"]}
    snapshot = ps.snapshot_directory(root, "legislative")
    ps.validate_manifest(manifest, snapshot, selected, "legislative")
    for field in ("inventory", "producer", "predecessor"):
        altered = copy.deepcopy(manifest)
        if field == "inventory":
            altered[field]["files"]["state.json"]["sha256"] = "0" * 64
        elif field == "producer":
            altered[field]["job_id"] = 999
        else:
            altered[field]["artifact_id"] = 502
        with pytest.raises(ps.StateSafetyError):
            ps.validate_manifest(altered, snapshot, selected, "legislative")


def test_manifested_successor_restores_with_verified_predecessor_prefix(scenario, monkeypatch):
    restore(scenario)
    root = scenario["tmp"] / "restored"
    with (root / "runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run_row(300, start=NEXT_START, finish=NEXT_SEAL)) + "\n")
    monkeypatch.setattr(ps, "utc_now", lambda: NEXT_SEAL)
    manifest = ps.seal(api=scenario["api"], pipeline="legislative", directory=root, receipt_path=scenario["tmp"] / "receipt.json", consumer_sha=SHA, env=scenario["env"])
    archive = archive_directory(root)
    api = scenario["api"]
    artifact = {"id": 502, "name": "legislative-tracker-state", "expired": False, "created_at": NEXT_CREATED, "digest": "sha256:" + ps.digest(archive), "workflow_run": {"id": 300}}
    api.routes[scenario["artifact_path"]] = {"total_count": 2, "artifacts": [artifact, scenario["artifact"]]}
    source = run_payload(300, updated=NEXT_FINISH)
    source["run_started_at"] = NEXT_START
    api.routes[f"/repos/{REPO}/actions/runs/300"] = source
    api.routes[f"/repos/{REPO}/actions/runs/300/attempts/1"] = source
    api.routes[scenario["run_list"]] = {"total_count": 2, "workflow_runs": [source, run_payload()]}
    set_jobs(api, 300, 1, [job_payload(3001, start=NEXT_START, finish=NEXT_FINISH)])
    api.routes[f"/repos/{REPO}/actions/artifacts/501"] = scenario["artifact"]
    api.blobs[f"/repos/{REPO}/actions/artifacts/502/zip"] = archive
    receipt = restore(scenario, destination=scenario["tmp"] / "next-restore", receipt_path=scenario["tmp"] / "next-receipt.json")
    assert receipt["generation"] == manifest["generation"] == 1
    assert receipt["selected"]["artifact_id"] == 502
    assert receipt["snapshot"]["files"]["runs.jsonl"]["rows"] == 2


def test_seal_without_new_successful_run_is_rejected(scenario):
    restore(scenario)
    with pytest.raises(ps.StateSafetyError, match="exactly one"):
        ps.seal(api=scenario["api"], pipeline="legislative", directory=scenario["tmp"] / "restored", receipt_path=scenario["tmp"] / "receipt.json", consumer_sha=SHA, env=scenario["env"])


@pytest.mark.parametrize("action", ["archive", "delete", "erase_outcome"])
def test_completed_edge_observations_must_survive_in_active_or_archive(tmp_path, action):
    root = fixture_state(tmp_path / "ai", "ai")
    observation = {"observation_key": "old-method-key", "trade_id": "trade-1", "method_hash": "old-method", "picker_outcomes": {"5": {"alpha_percent": 3.5}}, "followable_outcomes": {"5": {"alpha_percent": 1.5}}}
    write_json(root / "investor-edge-observations.json", {"version": "v1", "observations": {"old-method-key": observation}})
    before = ps.snapshot_directory(root, "ai")
    if action == "archive":
        write_json(root / "investor-edge-observations-archive.json", {"version": "v1", "observations": {"old-method-key": observation}})
        write_json(root / "investor-edge-observations.json", {"version": "v1", "observations": {}})
        ps.assert_continuity(before, ps.snapshot_directory(root, "ai"), root, "ai")
    else:
        if action == "delete":
            observations = {}
        else:
            observation["picker_outcomes"] = {}
            observations = {"old-method-key": observation}
        write_json(root / "investor-edge-observations.json", {"version": "v1", "observations": observations})
        with pytest.raises(ps.StateSafetyError, match="Investor Edge"):
            ps.assert_continuity(before, ps.snapshot_directory(root, "ai"), root, "ai")


def simulation_scenario(scenario):
    api = scenario["api"]
    root = scenario["tmp"] / "simulation-checkpoint"
    result = {"schema_version": 1, "simulation_id": "test-simulation", "status": "success", "success": True, "mode": "offline_historical_replay", "as_of_utc": START, "run_url": f"https://github.com/{REPO}/actions/runs/400", "objective": {"starting_capital_usd": 10000, "goal_value_usd": 20000}, "accounting": {}, "safety": {"paper_only": True, "network_calls": False, "alerts_sent": False, "production_inputs_mutated": False}}
    write_json(root / "simulation-result.json", result)
    write_rows(root / "simulation-runs.jsonl", [result])
    archive = archive_directory(root)
    run = run_payload(400)
    run.update({"name": ps.SIMULATION.display_name, "path": ps.SIMULATION.path})
    api.routes[f"/repos/{REPO}/actions/runs/400"] = run
    api.routes[f"/repos/{REPO}/actions/runs/400/attempts/1"] = run
    job = job_payload(4001)
    job["name"] = "simulate"
    set_jobs(api, 400, 1, [job])
    api.routes[scenario["run_list"]] = {"total_count": 1, "workflow_runs": [run]}
    artifact = {"id": 601, "name": "simulation-state", "expired": False, "created_at": CREATED, "digest": "sha256:" + ps.digest(archive), "workflow_run": {"id": 400}}
    path = f"/repos/{REPO}/actions/artifacts?name=simulation-state&per_page=100&page=1"
    api.routes[path] = {"total_count": 1, "artifacts": [artifact]}
    api.blobs[f"/repos/{REPO}/actions/artifacts/601/zip"] = archive
    return root, result, path, artifact


def restore_simulation(scenario):
    return ps.restore_simulation(api=scenario["api"], destination=scenario["tmp"] / "simulation-restored", consumer_sha=SHA, env=scenario["env"])


def test_optional_simulation_restores_valid_complete_history(scenario):
    root, _, _, _ = simulation_scenario(scenario)
    result = restore_simulation(scenario)
    assert result["history_count"] == 1
    assert (scenario["tmp"] / "simulation-restored" / "simulation-runs.jsonl").read_bytes() == (root / "simulation-runs.jsonl").read_bytes()


def test_optional_simulation_skips_only_when_never_created(scenario):
    _, _, path, _ = simulation_scenario(scenario)
    scenario["api"].routes[path] = {"total_count": 0, "artifacts": []}
    scenario["api"].routes[scenario["run_list"]] = {"total_count": 0, "workflow_runs": []}
    assert restore_simulation(scenario) is None
    assert not (scenario["tmp"] / "simulation-restored").exists()


def test_optional_simulation_missing_artifact_after_success_blocks(scenario):
    _, _, path, _ = simulation_scenario(scenario)
    scenario["api"].routes[path] = {"total_count": 0, "artifacts": []}
    with pytest.raises(ps.StateSafetyError, match="high-water"):
        restore_simulation(scenario)


def test_optional_simulation_cannot_hide_a_deleted_predecessor(scenario):
    simulation_scenario(scenario)
    old = run_payload(100, updated="2026-08-29T10:02:00Z")
    old.update({"path": ps.SIMULATION.path, "name": ps.SIMULATION.display_name})
    scenario["api"].routes[scenario["run_list"]]["workflow_runs"].append(old)
    scenario["api"].routes[scenario["run_list"]]["total_count"] = 2
    job = job_payload(1001, start="2026-08-29T10:00:00Z", finish="2026-08-29T10:02:00Z")
    job["name"] = "simulate"
    set_jobs(scenario["api"], 100, 1, [job])
    with pytest.raises(ps.StateSafetyError, match="predecessor artifact missing"):
        restore_simulation(scenario)


@pytest.mark.parametrize("mutation", ["missing_history", "mismatched_result", "unsafe", "wrong_url", "extra_file", "incomplete_history"])
def test_invalid_optional_simulation_never_silently_disappears(scenario, mutation):
    root, result, path, artifact = simulation_scenario(scenario)
    if mutation == "missing_history":
        (root / "simulation-runs.jsonl").unlink()
    elif mutation == "extra_file":
        (root / "state.json").write_text("{}")
    elif mutation == "mismatched_result":
        result["simulation_id"] = "changed"
        write_json(root / "simulation-result.json", result)
    elif mutation == "incomplete_history":
        write_rows(root / "simulation-runs.jsonl", [result, result])
    else:
        if mutation == "unsafe":
            result["safety"]["production_inputs_mutated"] = True
        else:
            result["run_url"] = "https://github.com/other/repo/actions/runs/400"
        write_json(root / "simulation-result.json", result)
        write_rows(root / "simulation-runs.jsonl", [result])
    archive = archive_directory(root)
    scenario["api"].routes[path]["artifacts"][0]["digest"] = "sha256:" + ps.digest(archive)
    scenario["api"].blobs[f"/repos/{REPO}/actions/artifacts/601/zip"] = archive
    with pytest.raises(ps.StateSafetyError):
        restore_simulation(scenario)
    assert not (scenario["tmp"] / "simulation-restored").exists()


@pytest.mark.parametrize("mutation", [None, "rewrite_prefix", "drop_prefix"])
def test_simulation_restore_checks_actual_predecessor_bytes(scenario, mutation):
    _, previous, path, artifact = simulation_scenario(scenario)
    api = scenario["api"]
    result = {**copy.deepcopy(previous), "simulation_id": "successor", "run_url": f"https://github.com/{REPO}/actions/runs/500", "as_of_utc": NEXT_START}
    history = [copy.deepcopy(previous), result]
    if mutation == "rewrite_prefix":
        history[0]["simulation_id"] = "rewritten"
    elif mutation == "drop_prefix":
        history = [result]
    root = scenario["tmp"] / "simulation-successor"
    write_json(root / "simulation-result.json", result)
    write_rows(root / "simulation-runs.jsonl", history)
    archive = archive_directory(root)
    latest_artifact = {**artifact, "id": 602, "created_at": NEXT_CREATED, "digest": "sha256:" + ps.digest(archive), "workflow_run": {"id": 500}}
    api.routes[path] = {"total_count": 2, "artifacts": [artifact, latest_artifact]}
    api.blobs[f"/repos/{REPO}/actions/artifacts/602/zip"] = archive
    run = run_payload(500, updated=NEXT_FINISH)
    run.update({"name": ps.SIMULATION.display_name, "path": ps.SIMULATION.path, "run_started_at": NEXT_START})
    api.routes[f"/repos/{REPO}/actions/runs/500"] = run
    api.routes[f"/repos/{REPO}/actions/runs/500/attempts/1"] = run
    job = job_payload(5001, start=NEXT_START, finish=NEXT_FINISH)
    job["name"] = "simulate"
    set_jobs(api, 500, 1, [job])
    old_run = api.routes[f"/repos/{REPO}/actions/runs/400"]
    api.routes[scenario["run_list"]] = {"total_count": 2, "workflow_runs": [run, old_run]}
    if mutation is None:
        assert restore_simulation(scenario)["history_count"] == 2
    else:
        with pytest.raises(ps.StateSafetyError, match="predecessor byte prefix"):
            restore_simulation(scenario)


def test_pending_edge_horizons_may_complete_without_rewriting_prior_outcomes(tmp_path):
    root = fixture_state(tmp_path / "ai", "ai")
    observation = {"observation_key": "obs", "trade_id": "trade", "method_hash": "method",
                   "picker_outcomes": {"5": {"alpha_percent": 1}, "20": None},
                   "followable_outcomes": {"5": None}}
    write_json(root / "investor-edge-observations.json", {"version": 1, "observations": {"obs": observation}})
    before = ps.snapshot_directory(root, "ai")
    observation["picker_outcomes"]["20"] = {"alpha_percent": 2}
    observation["followable_outcomes"]["5"] = {"alpha_percent": 3}
    write_json(root / "investor-edge-observations.json", {"version": 1, "observations": {"obs": observation}})
    ps.assert_continuity(before, ps.snapshot_directory(root, "ai"), root, "ai")
    observation["picker_outcomes"]["5"] = {"alpha_percent": 999}
    write_json(root / "investor-edge-observations.json", {"version": 1, "observations": {"obs": observation}})
    with pytest.raises(ps.StateSafetyError, match="Completed Investor Edge outcome"):
        ps.assert_continuity(before, ps.snapshot_directory(root, "ai"), root, "ai")


def test_runtime_archive_collisions_preserve_original_ids_and_all_payload_versions(tmp_path):
    from types import SimpleNamespace
    from scripts.investor_edge import InvestorEdgeRuntime

    root = fixture_state(tmp_path / "ai", "ai")
    old = {"observation_key": "obs", "trade_id": "trade", "method_hash": "method",
           "transaction_date": "2024-01-01", "picker_outcomes": {"5": None}, "followable_outcomes": {}}
    mature = copy.deepcopy(old)
    mature["picker_outcomes"]["5"] = {"alpha_percent": 2}
    latest = {**copy.deepcopy(old), "observation_key": "new", "trade_id": "new-trade", "transaction_date": "2025-01-01"}
    write_json(root / "investor-edge-observations-archive.json", {"version": 1, "observations": {"obs": old}})
    write_json(root / "investor-edge-observations.json", {"version": 1, "observations": {"obs": mature, "new": latest}})
    before = ps.snapshot_directory(root, "ai")
    runtime = InvestorEdgeRuntime({"observation_retention_limit": 1}, root,
                                  SimpleNamespace(errors=[], network_requests=0), {},
                                  {"obs": mature, "new": latest})
    runtime._save_observations()
    archive = ps.read_json(root / "investor-edge-observations-archive.json")["observations"]
    assert archive["obs"] == old
    assert len(archive) == 2 and mature in archive.values()
    assert all(row["observation_key"] == "obs" for row in archive.values())
    ps.assert_continuity(before, ps.snapshot_directory(root, "ai"), root, "ai")
    key = next(key for key in archive if key != "obs")
    archive[key]["picker_outcomes"]["5"] = {"alpha_percent": 999}
    with pytest.raises(ps.StateSafetyError, match="archive revision hash"):
        ps.validate_edge({"version": 1, "observations": archive}, "investor-edge-observations-archive.json")


def test_archived_observations_are_immutable_even_when_horizons_were_pending(tmp_path):
    root = fixture_state(tmp_path / "ai", "ai")
    old = {"observation_key": "obs", "trade_id": "trade", "method_hash": "method",
           "picker_outcomes": {"5": None}, "followable_outcomes": {}}
    archive_path = root / "investor-edge-observations-archive.json"
    write_json(archive_path, {"version": 1, "observations": {"obs": old}})
    before = ps.snapshot_directory(root, "ai")
    old["picker_outcomes"]["5"] = {"alpha_percent": 2}
    write_json(archive_path, {"version": 1, "observations": {"obs": old}})
    with pytest.raises(ps.StateSafetyError, match="Archived Investor Edge record changed"):
        ps.assert_continuity(before, ps.snapshot_directory(root, "ai"), root, "ai")
