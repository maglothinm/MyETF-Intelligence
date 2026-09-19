"""Offline checks for the explicit, journal-preserving health repair release."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_ocr_release_controller import c, recovered, snapshot, digest as journal_digest
from scripts import ocr_oge_pdf_repair_release as repair
from scripts import ocr_health_repair_release as health
from test_ocr_health_repair_release import repair_case as health_case

BUILD = "12345678-1234-1234-1234-123456789abc"


@pytest.fixture
def repair_case(health_case, monkeypatch):
    case = health_case
    health.prepare(c, case.root, BUILD)
    folder = case.root / repair.PREDECESSOR
    state = {"source": repair.HEALTH_SOURCE, "image": repair.HEALTH_IMAGE,
        "status": "complete", "schedules_restored": True, "acceptance_verified": True,
        "last_schedule_observation": {"states": {r["name"]:r["state"] for r in case.cloud["schedules"]}},
        "steps": {"acceptance": {"execution": "polititrack-admin-accepted"}}}
    c.save(folder / "ocr-deployment/journal.json", state)
    monkeypatch.setattr(repair, "COMPLETED_SHA", repair.digest(folder / "ocr-deployment/journal.json"))
    c.save(folder / "ocr-deployment/acceptance-receipt.json",
        {"result": "PASS", "read_only": True, "baseline_preservation_verified": True,
         "published_ocr_health_verified": True, "execution": "polititrack-admin-accepted"})
    monkeypatch.setattr(repair, "load_health_wrapper", lambda: health)
    for name in c.RESOURCES:
        case.cloud[name] = repair.completed_target(c, case.root, name)
    case.cloud["build"]["substitutions"]["_SOURCE_REVISION"] = repair.SOURCE
    case.calls.clear()
    return case


def new_engine(case):
    spec = importlib.util.spec_from_file_location("repair_test_engine", Path(c.__file__))
    engine = importlib.util.module_from_spec(spec); spec.loader.exec_module(engine)
    engine.load_audit_module = case.loader
    return engine


def test_prepare_only_reads_cloud_and_preserves_all_three_attempts(repair_case):
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
    path = case.root / repair.PREDECESSOR / "ocr-deployment/journal.json"
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


@pytest.mark.parametrize("change", [
    lambda s:s.update(status="enabled_verifying"),
    lambda s:s.update(acceptance_verified=False),
    lambda s:s.update(schedules_restored=False),
    lambda s:s.update(image=c.IMAGE),
])
def test_incomplete_predecessor_cannot_be_promoted(repair_case, monkeypatch, change):
    case = repair_case
    path = case.root / repair.PREDECESSOR / "ocr-deployment/journal.json"
    state = c.load(path); change(state); c.save(path, state)
    monkeypatch.setattr(repair, "COMPLETED_SHA", repair.digest(path))
    with pytest.raises(c.Stop, match="not complete"):
        repair.prepare(c, case.root, BUILD)
    assert not case.calls


def test_predecessor_wrapper_checksum_is_mandatory(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "repair.py"))
    (tmp_path / "ocr_health_repair_release.py").write_text("raise AssertionError('must not import')")
    with pytest.raises(RuntimeError, match="predecessor wrapper"):
        repair.load_health_wrapper()
