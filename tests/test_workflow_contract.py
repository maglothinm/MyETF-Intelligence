"""Contract wiring checks; producer/restore behavior lives in test_protected_state."""
from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
WRITERS = {
    "legislative-tracker-state": ("legislative_trade_tracker_v2.yml", "track"),
    "executive-tracker-state": ("executive_trade_tracker.yml", "track"),
    "ai-analysis-state": ("ai_filing_analyst.yml", "analyze"),
}


def workflow(filename):
    return yaml.load((WORKFLOWS / filename).read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def uploads(job):
    return [step for step in job.get("steps", []) if step.get("uses", "").startswith("actions/upload-artifact@")]


def test_exactly_one_guarded_sealed_writer_per_protected_artifact():
    found = {name: [] for name in WRITERS}
    for path in WORKFLOWS.glob("*.yml"):
        flow = workflow(path.name)
        for job_id, job in flow["jobs"].items():
            for upload in uploads(job):
                artifact = upload.get("with", {}).get("name")
                if artifact not in WRITERS:
                    continue
                found[artifact].append((path.name, job_id))
                guard = job.get("if", "")
                assert "github.repository_id == '1349678672'" in guard
                assert "github.ref_name == github.event.repository.default_branch" in guard
                assert flow["concurrency"]["cancel-in-progress"] == "false"
                assert "steps.state_seal.outcome == 'success'" in upload["if"]
                previous = job["steps"][job["steps"].index(upload)-1]
                assert previous["id"] == "state_seal"
                assert "scripts/protected_state.py seal" in previous["run"]
                assert previous.get("continue-on-error", "false") == "false"
                assert upload["with"]["if-no-files-found"] == "error"
    assert found == {name: [binding] for name, binding in WRITERS.items()}


@pytest.mark.parametrize("artifact,binding", WRITERS.items())
def test_steps_after_protected_upload_cannot_flip_the_authoritative_job_to_failure(artifact, binding):
    filename, job_id = binding
    job = workflow(filename)["jobs"][job_id]
    protected_upload = next(
        step for step in uploads(job) if step.get("with", {}).get("name") == artifact
    )
    later_steps = job["steps"][job["steps"].index(protected_upload) + 1:]
    assert later_steps
    for step in later_steps:
        assert step.get("continue-on-error") == "true", step.get("name")


@pytest.mark.parametrize("filename", [
    "legislative_trade_tracker_v2.yml", "executive_trade_tracker.yml",
    "ai_filing_analyst.yml", "manual_test.yml", "filing_simulation.yml",
    "publish_trade_dashboard.yml",
])
def test_all_consumers_use_the_shared_fail_closed_restore(filename):
    text = (WORKFLOWS / filename).read_text(encoding="utf-8")
    assert "scripts/protected_state.py restore" in text
    assert "actions/cache/restore" not in text
    assert "actions/cache/save" not in text
    assert "initialize_state:" not in text
    assert "bootstrap_alerts:" not in text


@pytest.mark.parametrize("filename", ["manual_test.yml", "filing_simulation.yml"])
def test_simulations_have_no_alert_credentials_or_extra_state_authority(filename):
    text = (WORKFLOWS / filename).read_text(encoding="utf-8")
    flow = workflow(filename)
    assert not re.search(r"secrets\s*\.", text)
    assert not re.search(r"secrets\s*\[", text)
    assert "durable_store" not in text and "simulation_request" not in text
    assert "delivery_journal" not in text
    assert "--read-only" in text
    assert flow["permissions"] == {"actions": "read", "contents": "read"}
    assert set(flow["jobs"]) == {"simulate"}
    job = flow["jobs"]["simulate"]
    assert "1349678672" in job["if"] and "refs/heads/main" in job["if"]
    assert not job.get("permissions")
    outputs = uploads(job)
    assert len(outputs) == 1
    expected = "simulation-state" if filename == "filing_simulation.yml" else "simulation-dashboard-${{ github.run_id }}-${{ github.run_attempt }}"
    assert outputs[0]["with"]["name"] == expected
    if filename == "manual_test.yml":
        assert outputs[0]["with"]["retention-days"] == "1"
        previous = job["steps"][job["steps"].index(outputs[0])-1]
        assert "before != after" in previous["run"]
        assert "production_inputs_unchanged" in previous["run"]
    else:
        previous = job["steps"][job["steps"].index(outputs[0])-1]
        assert "predecessor prefix" in previous["run"]
        assert "len(appended) != 1" in previous["run"]


def test_existing_schedules_and_retired_writers_remain_unchanged():
    for name, cron in [("legislative_trade_tracker_v2.yml", "7,22,37,52 * * * *"), ("executive_trade_tracker.yml", "13,43 * * * *")]:
        assert workflow(name)["on"]["schedule"] == [{"cron": cron, "timezone": "America/New_York"}]
    for name in ("legislative_trade_tracker.yml", "import_migrated_state.yml", "paper_agent.yml"):
        assert not (WORKFLOWS / name).exists()
    assert not (ROOT / "scripts/durable_store.py").exists()
    assert not (ROOT / "scripts/delivery_journal.py").exists()


def test_publisher_checks_identity_and_optional_history_not_silent_fallback():
    flow = workflow("publish_trade_dashboard.yml")
    guard = flow["jobs"]["build"]["if"]
    assert "github.repository_id == '1349678672'" in guard
    assert "github.ref == 'refs/heads/main'" in guard
    assert "github.event.workflow_run.conclusion == 'success'" in guard
    text = (WORKFLOWS / "publish_trade_dashboard.yml").read_text(encoding="utf-8")
    assert "scripts/protected_state.py restore-simulation" in text


def test_held_delivery_authority_is_not_in_production_analyst():
    code = (ROOT / "scripts/ai_filing_analyst.py").read_text(encoding="utf-8")
    assert "delivery_journal" not in code and "GitHubDurableStore" not in code
    assert "POLITITRACK_DURABLE_DELIVERY" not in code


@pytest.mark.parametrize("filename,branch", [
    ("legislative_trade_tracker_v2.yml", "legislative"),
    ("executive_trade_tracker.yml", "executive"),
    ("ai_filing_analyst.yml", "ai"),
])
def test_writers_keep_the_unretained_side_effect_guard(filename, branch):
    text = (WORKFLOWS / filename).read_text(encoding="utf-8")
    assert "scripts/collect_workflow_evidence.py" in text
    assert f"--guard-branch {branch}" in text
    assert ".selected.producer.run_id" in text
    assert ".selected.producer.run_attempt" in text


@pytest.mark.parametrize("filename", ["legislative_trade_tracker_v2.yml", "executive_trade_tracker.yml"])
def test_external_dispatch_labels_are_a_closed_allowlist(filename):
    flow = workflow(filename)
    dispatch = flow["on"]["workflow_dispatch"]
    source = dispatch["inputs"]["trigger_source"]
    assert source["type"] == "choice"
    assert source["default"] == "workflow_dispatch"
    assert source["options"] == ["workflow_dispatch", "external_scheduler"]
    assert "POLITITRACK_TRIGGER_SOURCE" in flow["env"]


def test_current_legislative_discovery_and_historical_backfill_contract_is_preserved():
    text = (WORKFLOWS / "legislative_trade_tracker_v2.yml").read_text(encoding="utf-8")
    assert "--branch legislative --source all" in text
    assert "tests/test_senate_client.py" in text
    assert "tests/test_legislative_healthcheck.py" in text
    assert "tests/test_historical_transaction_bootstrap.py" in text
    assert "steps.discovery_validation.outcome == 'success'" in text


def test_analyst_accepts_only_expected_successful_collector_triggers():
    text = (WORKFLOWS / "ai_filing_analyst.yml").read_text(encoding="utf-8")
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == github.event.repository.default_branch" in text
    assert "github.event.workflow_run.event == 'schedule'" in text
    assert "github.event.workflow_run.event == 'workflow_dispatch'" in text
