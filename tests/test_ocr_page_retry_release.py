"""A completed release must remain sealed while the full normal gates run."""
import importlib.util
from pathlib import Path

import pytest

from scripts import ocr_page_retry_release as repair
from scripts import ocr_activation_read_recovery_release as retry
from scripts import ocr_executive_recovery_release as executive
from scripts import ocr_oge_pdf_repair_release as pdf
from test_ocr_release_controller import c, recovered, snapshot
from test_ocr_oge_pdf_repair_release import new_engine, BUILD
from test_ocr_activation_read_recovery_release import (
    case as accepted_case, executive_case, health_case, pdf_case, senate_case)


@pytest.fixture
def case(accepted_case, monkeypatch):
    case = accepted_case
    accepted = case.procedure
    accepted.prepare(c, case.root, executive.BUILD)
    folder = case.root / repair.PREVIOUS_WORKSPACE
    state = dict(status="complete", source=repair.PREVIOUS_SOURCE, image=repair.PREVIOUS_IMAGE,
        installation_verified=True, activation_verified=True, acceptance_verified=True,
        live_assets_verified=True, live_ocr_api_auth_boundary_verified=True, schedules_restored=True,
        last_schedule_observation={"states":{r["name"]:r["state"] for r in case.cloud["schedules"]}},
        steps={"acceptance":dict(execution="polititrack-admin-accepted", job="polititrack-admin",
            image=repair.PREVIOUS_IMAGE, read_only=True, completed=True)})
    c.save(folder / "ocr-deployment/journal.json", state)
    c.save(folder / "ocr-deployment/acceptance-receipt.json", dict(result="PASS", read_only=True,
        execution="polititrack-admin-accepted", baseline_preservation_verified=True,
        published_ocr_health_verified=True))
    monkeypatch.setattr(repair, "PREVIOUS_SHA", pdf.digest(folder / "ocr-deployment/journal.json"))
    spec = importlib.util.spec_from_file_location("fresh_page_retry_procedure", Path(pdf.__file__))
    procedure = importlib.util.module_from_spec(spec); spec.loader.exec_module(procedure)
    case.procedure = repair.configure_procedure(procedure, accepted, retry)
    for name in c.RESOURCES:
        case.cloud[name] = case.procedure.completed_target(c, case.root, name)
    case.cloud["build"].update(id=BUILD, substitutions={"_SOURCE_REVISION":repair.SOURCE})
    case.cloud["build"]["results"]["images"][0]["digest"] = "sha256:" + "d" * 64
    case.cloud["registry"]["image_summary"]["digest"] = "sha256:" + "d" * 64
    case.calls.clear()
    return case


def test_all_eight_attempts_preserved_and_normal_lifecycle_unchanged(case):
    before = case.procedure.sealed_predecessors(c, case.root)
    assert sum(n.endswith("journal.json") for n in before) == 8
    case.procedure.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    assert c.load(workspace / "predecessors.json") == before
    assert c.load(workspace / "state-audit/receipt.json") == c.load(
        case.root / repair.PREVIOUS_WORKSPACE / "ocr-deployment/acceptance-receipt.json")
    engine = new_engine(case)
    case.procedure.configure_engine(engine, c, case.root, workspace)
    assert engine.SOURCE == repair.SOURCE and engine.BUILD == BUILD
    assert engine.IMAGE.endswith("@sha256:" + "d" * 64)
    for method in ("run", "execute", "audit", "recover", "update", "verify_live", "preflight", "pause", "drain"):
        assert getattr(engine.Release, method).__code__.co_code == getattr(c.Release, method).__code__.co_code
    assert engine.AUDIT_EXTRA == c.AUDIT_EXTRA
    assert not (workspace / "ocr-deployment").exists()
    release = engine.Release(workspace, engine.load_audit_module())
    assert release.state["status"] == "preparing" and not release.state["steps"]
    assert not release.state["producer_submission_started"]
    assert case.procedure.sealed_predecessors(c, case.root) == before
    for name in c.RESOURCES:
        assert c.container(release.original[name], name)["image"] == repair.PREVIOUS_IMAGE
        if name in c.OCR_RESOURCES:
            assert {e["name"]:e.get("value") for e in c.container(release.original[name], name)["env"]}[
                "RUNTIME_SOURCE_OCR_ENABLED"] == "true"


@pytest.mark.parametrize("change", [dict(status="enabled_verifying"), dict(schedules_restored=False),
    dict(acceptance_verified=False), dict(live_assets_verified=False), dict(live_ocr_api_auth_boundary_verified=False),
    dict(source="other"), dict(image="other"), dict(last_error="failed"), dict(recovery_error="failed")])
def test_incomplete_predecessor_cannot_prepare_even_with_matching_hash(case, monkeypatch, change):
    path = case.root / repair.PREVIOUS_WORKSPACE / "ocr-deployment/journal.json"
    state = c.load(path); state.update(change); c.save(path, state)
    monkeypatch.setattr(repair, "PREVIOUS_SHA", pdf.digest(path))
    before = snapshot(case.root)
    with pytest.raises(c.Stop, match="not fully accepted"):
        case.procedure.prepare(c, case.root, BUILD)
    assert not case.calls and snapshot(case.root) == before


@pytest.mark.parametrize("change", [dict(execution="wrong"), dict(result="FAIL"), dict(read_only=False),
    dict(baseline_preservation_verified=False), dict(published_ocr_health_verified=False)])
def test_independent_acceptance_evidence_is_required(case, change):
    path = case.root / repair.PREVIOUS_WORKSPACE / "ocr-deployment/acceptance-receipt.json"
    receipt = c.load(path); receipt.update(change); c.save(path, receipt)
    with pytest.raises(c.Stop, match="independent acceptance receipt"):
        case.procedure.prepare(c, case.root, BUILD)
    assert not case.calls


def test_changed_old_evidence_blocks_new_journal_persistence(case):
    case.procedure.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    engine = new_engine(case); case.procedure.configure_engine(engine, c, case.root, workspace)
    release = engine.Release(workspace, engine.load_audit_module())
    old = release.path.read_bytes()
    (case.root / repair.PREVIOUS_WORKSPACE / "new-evidence.json").write_text("{}")
    with pytest.raises(c.Stop, match="evidence changed"):
        release.persist()
    assert release.path.read_bytes() == old


@pytest.mark.parametrize("target", ["source", "image", "schedule", "feature", "journal"])
def test_changed_production_or_build_cannot_prepare(case, target):
    if target == "source":
        case.cloud["build"]["substitutions"]["_SOURCE_REVISION"] = executive.SOURCE
    elif target == "image":
        c.container(case.cloud["polititrack-executive"], "polititrack-executive")["image"] = "other"
    elif target == "schedule":
        case.cloud["schedules"][0]["schedule"] = "1 * * * *"
    elif target == "feature":
        c.container(case.cloud["polititrack-ai"], "polititrack-ai")["env"].append(
            {"name":"CURRENT_OPPORTUNITY_ENABLED", "value":"true"})
    else:
        path = case.root / repair.PREVIOUS_WORKSPACE / "ocr-deployment/journal.json"
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(c.Stop):
        case.procedure.prepare(c, case.root, BUILD)
    assert not (case.root / repair.WORKSPACE_NAME).exists()


def test_wrong_pin_rejects_module_without_executing_it(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "repair.py"))
    (tmp_path / "other.py").write_text("raise AssertionError('do not run')")
    with pytest.raises(RuntimeError, match="reviewed procedure differs"):
        repair.load_pinned("other", "0" * 64)


def test_actual_procedures_load_without_cloud_side_effects():
    procedure = repair.load_procedure()
    assert procedure.SOURCE == repair.SOURCE and procedure.WORKSPACE_NAME == repair.WORKSPACE_NAME
    assert str(procedure.PREDECESSOR) == repair.PREVIOUS_WORKSPACE
