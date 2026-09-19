"""Offline checks for the explicit, journal-preserving health repair release."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_ocr_release_controller import c, recovered, snapshot, digest as journal_digest
from scripts import ocr_health_repair_release as repair

BUILD = "12345678-1234-1234-1234-123456789abc"


@pytest.fixture
def repair_case(recovered, monkeypatch):
    root = recovered
    for name in c.RESOURCES:
        task = {"containers": [{"image": c.IMAGE, "env": []}]}
        spec = task if name.endswith("-web") else {"template": {"spec": task}}
        c.save(root / (name + ".json"), {"spec": {"template": {"spec": spec}}})
    schedules = [{"name": "polititrack-" + p, "state": "ENABLED", "schedule": "0 * * * *"} for p in c.PRODUCERS]
    schedules.append({"name": "polititrack-vault-lifecycle", "state": "PAUSED", "schedule": "17 3 * * *"})
    c.save(root / "schedules.json", schedules)
    c.save(root / "summary.json", {"source": c.SOURCE, "image": c.IMAGE})
    files = [root / "summary.json", root / "schedules.json", *[root / (n + ".json") for n in c.RESOURCES]]
    (root / "SHA256SUMS").write_text("".join(repair.digest(p) + "  " + p.name + "\n" for p in files))
    monkeypatch.setattr(repair, "ORIGINAL_SHA", journal_digest(root))
    original = c.recovery_review(root, repair.ORIGINAL_SHA)
    state = {"predecessor": original, "source": c.SOURCE, "image": c.IMAGE,
        "status": "recovered_new_image_ocr_disabled", "schedules_restored": True,
        "last_schedule_observation": {"states": {s["name"]: s["state"] for s in schedules}},
        "steps": {"recovery-preservation": {"execution": "polititrack-admin-preserved"}}}
    c.save(root / repair.PREDECESSOR / "journal.json", state)
    monkeypatch.setattr(repair, "RECOVERED_SHA", repair.digest(root / repair.PREDECESSOR / "journal.json"))
    c.save(root / repair.PREDECESSOR / "recovery-preservation-receipt.json",
        {"result": "PASS", "read_only": True, "baseline_preservation_verified": True,
         "execution": "polititrack-admin-preserved"})
    cloud = {name: repair.recovered_target(c, root, name) for name in c.RESOURCES}
    cloud.update(schedules=schedules,
        build={"id": BUILD, "status": "SUCCESS", "substitutions": {"_SOURCE_REVISION": repair.SOURCE},
               "results": {"images": [{"name": c.IMAGE.split("@")[0] + ":repair", "digest": "sha256:" + "b" * 64}]}},
        registry={"image_summary": {"digest": "sha256:" + "b" * 64}},
        database={"settings": {"ipConfiguration": {"ipv4Enabled": False, "privateNetwork": "existing"},
                               "backupConfiguration": {"enabled": True, "pointInTimeRecoveryEnabled": True}}})
    calls = []
    def read(_folder, label, *args):
        calls.append((label, args))
        assert not {"update", "execute", "pause", "resume", "create"} & set(args)
        return copy.deepcopy(cloud[label])
    def loader():
        module = SimpleNamespace(SOURCE=c.SOURCE, RELEASE_IMAGE=c.IMAGE, read_gcloud=read)
        def verify(folder):
            for line in (folder / "SHA256SUMS").read_text().splitlines():
                expected, name = line.split("  ", 1)
                c.require(repair.digest(folder / name) == expected, "Preparation manifest differs.")
            summary = c.load(folder / "summary.json")
            c.require(summary["source"] == module.SOURCE and summary["image"] == module.RELEASE_IMAGE,
                      "Preparation targets another release.")
        module.verify_preparation = verify
        return module
    monkeypatch.setattr(c, "load_audit_module", loader)
    return SimpleNamespace(root=root, cloud=cloud, calls=calls, loader=loader)


def new_engine(case):
    spec = importlib.util.spec_from_file_location("repair_test_engine", Path(c.__file__))
    engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
    engine.load_audit_module = case.loader
    return engine


def test_prepare_only_reads_cloud_and_preserves_both_attempts(repair_case):
    case = repair_case
    before = repair.sealed_predecessors(c, case.root)
    repair.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    assert repair.sealed_predecessors(c, case.root) == before
    assert c.load(workspace / "predecessors.json") == before
    assert not (workspace / "ocr-deployment").exists()
    assert c.load(workspace / "summary.json")["frozen_baseline"] is False
    assert len(case.calls) == 10
    repair.verify_seal(c, case.root, workspace)
    old = snapshot(case.root)
    with pytest.raises(c.Stop, match="already exists"):
        repair.prepare(c, case.root, BUILD)
    assert snapshot(case.root) == old


@pytest.mark.parametrize("target,change", [
    ("build", lambda x: x.update(status="WORKING")),
    ("build", lambda x: x["substitutions"].update(_SOURCE_REVISION="f" * 40)),
    ("build", lambda x: x["results"]["images"].append(copy.deepcopy(x["results"]["images"][0]))),
    ("registry", lambda x: x["image_summary"].update(digest="sha256:" + "c" * 64)),
    ("database", lambda x: x["settings"]["ipConfiguration"].update(ipv4Enabled=True)),
    ("database", lambda x: x["settings"]["backupConfiguration"].update(pointInTimeRecoveryEnabled=False)),
    ("schedules", lambda x: x[0].update(schedule="1 * * * *")),
    ("schedules", lambda x: x[-1].update(state="ENABLED")),
    ("polititrack-web", lambda x: c.container(x, "polititrack-web").update(image="other-image")),
])
def test_preparation_rejects_unverified_release_or_changed_production(repair_case, target, change):
    case = repair_case
    before = repair.sealed_predecessors(c, case.root)
    change(case.cloud[target])
    with pytest.raises(c.Stop):
        repair.prepare(c, case.root, BUILD)
    assert not (case.root / repair.WORKSPACE_NAME).exists()
    assert repair.sealed_predecessors(c, case.root) == before


def test_new_engine_requires_fresh_empty_attempt_and_preserves_original_pins(repair_case):
    case = repair_case; repair.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    old_source, old_image = c.SOURCE, c.IMAGE
    engine = new_engine(case)
    repair.configure_engine(engine, c, case.root, workspace)
    release = engine.Release(workspace, engine.load_audit_module())
    assert release.state["source"] == repair.SOURCE
    assert release.state["status"] == "preparing"
    assert release.state["steps"] == {} and release.state["paused"] == []
    assert release.state["producer_submission_started"] is False
    assert not any(release.state.get(k) for k in ("installation_verified", "activation_verified", "acceptance_verified"))
    assert not (release.folder / "baseline-receipt.json").exists()
    assert (c.SOURCE, c.IMAGE) == (old_source, old_image)
    saved = release.path.read_bytes()
    (case.root / repair.PREDECESSOR / "new-receipt.json").write_text("changed")
    with pytest.raises(c.Stop, match="evidence changed"):
        release.persist()
    assert release.path.read_bytes() == saved


@pytest.mark.parametrize("path", ["summary.json", "state-audit/receipt.json", "predecessors.json"])
def test_changed_preparation_is_rejected_without_dispatch(repair_case, path):
    case = repair_case; repair.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    data = c.load(workspace / path); data["changed"] = True; c.save(workspace / path, data)
    before = snapshot(case.root); calls = list(case.calls)
    with pytest.raises(c.Stop):
        repair.configure_engine(new_engine(case), c, case.root, workspace)
    assert snapshot(case.root) == before and case.calls == calls


def test_changed_recovered_journal_is_rejected_before_any_cloud_read(repair_case):
    case = repair_case
    path = case.root / repair.PREDECESSOR / "journal.json"
    state = c.load(path); state["status"] = "enabled_verifying"; c.save(path, state)
    before = snapshot(case.root)
    with pytest.raises(c.Stop, match="journal changed"):
        repair.prepare(c, case.root, BUILD)
    assert case.calls == [] and snapshot(case.root) == before


def test_closed_repair_attempt_cannot_reopen_or_run_recovery(repair_case, monkeypatch):
    case = repair_case; repair.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    c.save(workspace / "ocr-deployment/journal.json", {"status": "recovered_new_image_ocr_disabled"})
    engine = new_engine(case); repair.configure_engine(engine, c, case.root, workspace)
    before = (workspace / "ocr-deployment/journal.json").read_bytes()
    monkeypatch.setattr(engine.sys, "argv", ["controller", "--workspace", str(workspace), "--deploy"])
    with pytest.raises(engine.Stop, match="closed"):
        engine.main()
    assert (workspace / "ocr-deployment/journal.json").read_bytes() == before


def test_original_controller_checksum_is_mandatory(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "repair.py"))
    (tmp_path / "ocrv2.py").write_text("raise AssertionError('must not import')")
    with pytest.raises(RuntimeError, match="controller beside"):
        repair.load_controller()
