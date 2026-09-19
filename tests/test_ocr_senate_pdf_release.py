"""Fresh release identity and immutable four-attempt continuation boundaries."""
import importlib.util
from pathlib import Path

import pytest

from scripts import ocr_senate_pdf_release as repair
from scripts import ocr_oge_pdf_repair_release as pdf
from test_ocr_release_controller import c, recovered, snapshot
from test_ocr_health_repair_release import repair_case as health_case
from test_ocr_oge_pdf_repair_release import repair_case as pdf_case, new_engine, BUILD


@pytest.fixture
def case(pdf_case, monkeypatch):
    case = pdf_case
    pdf.prepare(c, case.root, BUILD)
    folder = case.root / repair.PREVIOUS_WORKSPACE
    state = {"source": repair.PREVIOUS_SOURCE, "image": repair.PREVIOUS_IMAGE,
             "status": "recovered_original_configuration", "schedules_restored": True,
             "producer_submission_started": False,
             "last_schedule_observation": {"states": {x["name"]: x["state"] for x in case.cloud["schedules"]}},
             "steps": {"baseline": {"job": "polititrack-admin", "image": pdf.HEALTH_IMAGE,
                       "execution": "polititrack-admin-baseline", "completed": True, "read_only": True}}}
    c.save(folder / "ocr-deployment/journal.json", state)
    c.save(folder / "ocr-deployment/baseline-receipt.json",
           {"execution": "polititrack-admin-baseline", "result": "PASS", "read_only": True,
            "latest_production_runs": [{"status": "failure"}]})
    monkeypatch.setattr(repair, "PREVIOUS_SHA", pdf.digest(folder / "ocr-deployment/journal.json"))
    # A separate module keeps the already-completed predecessor implementation
    # intact. Test-only fixture hashes stand in for actual immutable receipts.
    spec = importlib.util.spec_from_file_location("test_successor_procedure", Path(pdf.__file__))
    procedure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(procedure)
    procedure.COMPLETED_SHA = pdf.COMPLETED_SHA
    procedure.load_health_wrapper = pdf.load_health_wrapper
    case.procedure = repair.configure_procedure(procedure)
    case.cloud["build"]["substitutions"]["_SOURCE_REVISION"] = repair.SOURCE
    case.calls.clear()
    return case


def test_four_closed_attempts_are_sealed_and_new_baseline_is_required(case):
    proc = case.procedure
    sealed = proc.sealed_predecessors(c, case.root)
    assert sum(name.endswith("journal.json") for name in sealed) == 4
    proc.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    assert c.load(workspace / "predecessors.json") == sealed
    assert proc.sealed_predecessors(c, case.root) == sealed
    assert len(case.calls) == 10  # all reads, asserted by the shared fixture
    engine = new_engine(case)
    proc.configure_engine(engine, c, case.root, workspace)
    release = engine.Release(workspace, engine.load_audit_module())
    assert release.state["source"] == repair.SOURCE
    assert release.state["status"] == "preparing" and release.state["steps"] == {}
    assert not release.state["producer_submission_started"]
    assert not (release.folder / "baseline-receipt.json").exists()
    saved = release.path.read_bytes()
    (case.root / repair.PREVIOUS_WORKSPACE / "added-receipt.json").write_text("TEST changed")
    with pytest.raises(c.Stop, match="evidence changed"):
        release.persist()
    assert release.path.read_bytes() == saved


@pytest.mark.parametrize("change", [
    {"producer_submission_started": True}, {"installation_verified": True},
    {"activation_verified": True}, {"acceptance_verified": True},
    {"recovery_error": "unresolved"}, {"status": "enabled_verifying"},
    {"schedules_restored": False}, {"steps": {}}, {"image": "different"},
])
def test_unreviewed_fourth_attempt_rejected_even_with_matching_hash(case, monkeypatch, change):
    path = case.root / repair.PREVIOUS_WORKSPACE / "ocr-deployment/journal.json"
    state = c.load(path); state.update(change); c.save(path, state)
    monkeypatch.setattr(repair, "PREVIOUS_SHA", pdf.digest(path))
    before = snapshot(case.root)
    with pytest.raises(c.Stop):
        case.procedure.prepare(c, case.root, BUILD)
    assert not case.calls and snapshot(case.root) == before


def test_changed_fourth_journal_is_rejected_before_any_cloud_read(case):
    path = case.root / repair.PREVIOUS_WORKSPACE / "ocr-deployment/journal.json"
    path.write_bytes(path.read_bytes() + b"\n")
    before = snapshot(case.root)
    with pytest.raises(c.Stop, match="fourth closed journal changed"):
        case.procedure.prepare(c, case.root, BUILD)
    assert not case.calls and snapshot(case.root) == before


def test_old_build_cannot_be_deployed_as_new_repair(case):
    case.cloud["build"]["substitutions"]["_SOURCE_REVISION"] = repair.PREVIOUS_SOURCE
    with pytest.raises(c.Stop, match="targets another source"):
        case.procedure.prepare(c, case.root, BUILD)
    assert not (case.root / repair.WORKSPACE_NAME).exists()


def test_closed_new_attempt_is_not_reopened(case, monkeypatch):
    proc = case.procedure; proc.prepare(c, case.root, BUILD)
    workspace = case.root / repair.WORKSPACE_NAME
    path = workspace / "ocr-deployment/journal.json"
    c.save(path, {"status": "recovered_original_configuration"})
    (workspace / ".ocr-deployment.lock").touch()  # every real closed attempt already owns this file
    engine = new_engine(case); proc.configure_engine(engine, c, case.root, workspace)
    before = snapshot(case.root)
    monkeypatch.setattr(engine.sys, "argv", ["controller", "--workspace", str(workspace), "--deploy"])
    with pytest.raises(engine.Stop, match="closed"):
        engine.main()
    assert snapshot(case.root) == before


def test_procedure_checksum_prevents_unreviewed_code_loading(tmp_path, monkeypatch):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "successor.py"))
    (tmp_path / "ocr_oge_pdf_repair_release.py").write_text("raise AssertionError('must not run')")
    with pytest.raises(RuntimeError, match="procedure differs"):
        repair.load_procedure()


def test_actual_pinned_procedure_can_be_loaded_without_writes():
    proc = repair.configure_procedure(repair.load_procedure())
    assert proc.SOURCE == repair.SOURCE and proc.WORKSPACE_NAME == repair.WORKSPACE_NAME
