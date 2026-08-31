import re
from pathlib import Path

import pytest
import yaml

from scripts import collect_workflow_evidence as evidence
from scripts.run_trigger import trigger_source

REPO = "maglothinm/MyETF-Intelligence"
SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def run(run_id=10, attempt=1, branch="legislative", conclusion="success", start="2026-08-31T12:00:00Z", **kwargs):
    spec = evidence.SPECS[branch]
    return dict(id=run_id, run_attempt=attempt, repository={"id": evidence.REPOSITORY_ID},
                name=spec["name"], path=".github/workflows/" + spec["file"], head_branch="main",
                head_sha=SHA, event="schedule", status="completed", conclusion=conclusion,
                created_at=start, run_started_at=start, updated_at=start, **kwargs)


def job(branch="legislative", conclusion="success", step_conclusion="success"):
    return dict(name=evidence.SPECS[branch]["job"], conclusion=conclusion, status="completed",
                started_at="2026-08-31T12:00:10Z", completed_at="2026-08-31T12:01:00Z",
                steps=[dict(name=evidence.SPECS[branch]["step"], conclusion=step_conclusion,
                            status="completed", started_at=None if step_conclusion == "skipped" else "2026-08-31T12:00:30Z")])


class FakeAPI:
    def __init__(self, runs=None, jobs=None):
        self.runs = runs or [run()]
        self.jobs = jobs or {(10, 1): [job()]}
        self.calls = []
        self.repository = dict(id=evidence.REPOSITORY_ID, full_name=REPO, default_branch="main")

    def __call__(self, path):
        self.calls.append(path)
        if path == "/repos/" + REPO:
            return self.repository
        if "/compare/" in path:
            return {"status": "ahead"}
        if "/actions/workflows/" in path:
            name = path.split("/workflows/")[1].split("/")[0]
            return {"workflow_runs": [row for row in self.runs if row["path"].endswith(name)]}
        match = re.search(r"/runs/(\d+)/attempts/(\d+)", path)
        run_id, attempt = map(int, match.groups())
        if "/jobs?" in path:
            return {"jobs": self.jobs[(run_id, attempt)]}
        return next(row for row in self.runs if row["id"] == run_id and row["run_attempt"] == attempt)


@pytest.mark.parametrize("event,label,expected", [
    ("schedule", "external_scheduler", "schedule"),
    ("workflow_dispatch", "external_scheduler", "external_scheduler"),
    ("workflow_dispatch", "workflow_dispatch", "workflow_dispatch"),
    ("workflow_dispatch", "Bearer secret", "workflow_dispatch"),
    ("workflow_run", "external_scheduler", "workflow_run"),
    ("pull_request", "external_scheduler", "unknown"),
    ("local", "", "local"),
])
def test_trigger_is_a_safe_coarse_label(event, label, expected):
    assert trigger_source({"GITHUB_EVENT_NAME": event, "POLITITRACK_TRIGGER_SOURCE": label}) == expected


def test_actions_success_is_explicit_job_observation_without_collector_timestamp():
    result = evidence.collect(FakeAPI(), REPO, SHA, "2026-08-31T12:05:00Z")
    row = result["branches"]["legislative"]["attempts"][0]
    assert result["available"]
    assert row["run_key"] == "10:1"
    assert row["workflow_started_utc"] == "2026-08-31T12:00:00Z"
    assert row["producer_job_started_utc"] == "2026-08-31T12:00:10Z"
    assert row["started_utc"] is None
    assert row["evidence_source"] == "github_actions"
    assert row["success"] is True
    assert row["error_count"] == 0
    assert row["run_url"].endswith("/10/attempts/1")


def test_failed_job_exports_coarse_count_and_no_raw_secrets():
    failed = run(conclusion="failure")
    failed["display_title"] = "secret title"
    failure_job = job(conclusion="failure", step_conclusion="failure")
    failure_job["steps"][0]["output"] = "secret credential"
    api = FakeAPI([failed], {(10, 1): [failure_job]})
    result = evidence.collect(api, REPO, SHA, "2026-08-31T12:05:00Z")
    row = result["branches"]["legislative"]["attempts"][0]
    assert row["conclusion"] == "failure"
    assert row["error_count"] == 1
    assert "secret" not in str(result)


def test_pending_run_does_not_invent_a_collector_attempt_or_completion():
    pending = run()
    pending.update(status="queued", conclusion=None)
    api = FakeAPI([pending], {(10, 1): []})
    row = evidence.collect(api, REPO, SHA, "2026-08-31T12:05:00Z")["branches"]["legislative"]["attempts"][0]
    assert row["conclusion"] == "queued"
    assert row["success"] is None
    assert row["workflow_created_utc"] == "2026-08-31T12:00:00Z"
    assert row["started_utc"] is row["workflow_started_utc"] is row["finished_utc"] is None


@pytest.mark.parametrize("change", [
    {"repository": {"id": 123}}, {"head_branch": "feature"}, {"event": "pull_request"},
    {"name": "Run Simulation"}, {"path": ".github/workflows/manual_test.yml"},
    {"name": "Publish government trade dashboard"},
])
def test_noncanonical_simulated_or_publication_runs_are_not_collector_evidence(change):
    candidate = run()
    candidate.update(change)
    result = evidence.collect(FakeAPI([candidate]), REPO, SHA, "2026-08-31T12:05:00Z")
    assert result["branches"]["legislative"]["attempts"] == []


def test_repository_mismatch_fails_to_unavailable():
    api = FakeAPI()
    api.repository["id"] = 123
    result = evidence.collect(api, REPO, SHA, "2026-08-31T12:05:00Z")
    assert result["available"] is False
    assert len(api.calls) == 1


def test_api_failure_never_fabricates_a_failure_or_success_record():
    def unavailable(path):
        raise evidence.EvidenceError("github_evidence_unavailable")
    result = evidence.collect(unavailable, REPO, SHA, "2026-08-31T12:05:00Z")
    assert not result["available"]
    assert not any(row["attempts"] for row in result["branches"].values())


def test_late_rerun_of_old_id_is_newest_evidence():
    current = run(50, start="2026-08-31T12:00:00Z")
    rerun = run(2, attempt=3, conclusion="failure", start="2026-08-31T12:15:00Z")
    api = FakeAPI([current, rerun], {(50, 1): [job()], (2, 3): [job(conclusion="failure")]})
    rows = evidence.collect(api, REPO, SHA, "2026-08-31T12:20:00Z")["branches"]["legislative"]["attempts"]
    assert [row["run_key"] for row in rows] == ["2:3", "50:1"]
    assert any("/runs/2/attempts/3/jobs" in path for path in api.calls)


def guard(api):
    evidence.assert_no_unretained_side_effects(api, REPO, SHA, "legislative", 10, 1, 99, 1)


def test_duplicate_after_retained_success_is_safe_to_restore_and_deduplicate():
    guard(FakeAPI())


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "success"])
def test_started_unretained_producer_blocks_alert_replay(conclusion):
    later = run(11, conclusion=conclusion, start="2026-08-31T12:15:00Z")
    api = FakeAPI([run(), later], {(10, 1): [job()], (11, 1): [job(conclusion=conclusion, step_conclusion=conclusion)]})
    with pytest.raises(evidence.EvidenceError, match="unretained_side_effects_possible_run_11_attempt_1"):
        guard(api)


def test_proven_precollector_failure_allows_safe_retry():
    later = run(11, conclusion="failure", start="2026-08-31T12:15:00Z")
    api = FakeAPI([run(), later], {(10, 1): [job()], (11, 1): [job(conclusion="failure", step_conclusion="skipped")]})
    guard(api)


def test_failed_old_run_rerun_also_blocks_despite_lower_run_id():
    old = run(2, conclusion="failure", start="2026-08-31T12:15:00Z")
    api = FakeAPI([run(), old], {(10, 1): [job()], (2, 1): [job(conclusion="failure")]})
    with pytest.raises(evidence.EvidenceError, match="run_2_attempt_1"):
        guard(api)


def test_missing_steps_cannot_prove_no_external_side_effect():
    later = run(11, conclusion="cancelled", start="2026-08-31T12:15:00Z")
    ambiguous = job(conclusion="cancelled")
    ambiguous["steps"] = []
    api = FakeAPI([run(), later], {(10, 1): [job()], (11, 1): [ambiguous]})
    with pytest.raises(evidence.EvidenceError, match="unretained_side_effects"):
        guard(api)


def test_existing_failed_attempt_before_restored_success_does_not_block():
    old = run(2, conclusion="failure", start="2026-08-31T11:30:00Z")
    guard(FakeAPI([run(), old], {(10, 1): [job()]}))


def test_canonical_workflows_keep_single_writer_manual_dispatch_and_retry_guard():
    schedules = {"legislative": "7,22,37,52 * * * *", "executive": "13,43 * * * *"}
    groups = {"legislative": "legislative-purchase-tracker-v2", "executive": "executive-purchase-tracker", "ai": "ai-filing-analyst"}
    for branch, spec in evidence.SPECS.items():
        text = (ROOT / ".github/workflows" / spec["file"]).read_text(encoding="utf-8")
        workflow = yaml.safe_load(text)
        triggers = workflow.get("on", workflow.get(True))
        assert workflow["concurrency"] == {"group": groups[branch], "cancel-in-progress": False}
        assert "workflow_dispatch" in triggers
        assert "collect_workflow_evidence.py" in text
        assert f"--guard-branch {branch}" in text
        assert text.index("--guard-branch") < text.index(f"- name: {spec['step']}")
        if branch != "ai":
            assert triggers["schedule"][0]["cron"] == schedules[branch]
            assert triggers["workflow_dispatch"]["inputs"]["trigger_source"]["options"] == ["workflow_dispatch", "external_scheduler"]


def test_failed_collector_publication_remains_read_only_and_simulations_unchanged():
    text = (ROOT / ".github/workflows/publish_trade_dashboard.yml").read_text(encoding="utf-8")
    assert "--workflow-evidence-file dashboard-input/workflow-evidence.json" in text
    assert "github.event.workflow_run.name != 'Run $10K portfolio simulator'" in text
    assert "actions/upload-artifact@" not in text
    for name in ("manual_test.yml", "filing_simulation.yml"):
        simulation = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "GITHUB_DISPATCH_TOKEN" not in simulation
        assert "collect_workflow_evidence.py" not in simulation
