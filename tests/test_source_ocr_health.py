"""OCR health must remain independently observable across failures and commits."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.source_ocr_health import branch_health, run_health, safe_metrics
from scripts import dashboard_insights

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=timezone.utc)
RUN = {"id": "legislative:TEST", "status": "success", "state_evidence": True,
       "started_utc": "2026-09-17T19:55:00Z", "finished_utc": "2026-09-17T19:59:00Z"}


def metrics(**changes):
    return {"enabled": True, "stage": "complete", "started_at": "2026-09-17T19:55:01Z",
            "heartbeat_at": "2026-09-17T19:59:10Z", "finished_at": "2026-09-17T19:59:10Z",
            "intake_status": "ok", "cleanup_status": "complete", **changes}


@pytest.mark.parametrize("changes,expected,activity", [
    ({}, "success", "idle"),
    ({"documents_attempted": 1, "review_remaining": 1}, "success", "complete"),
    ({"documents_attempted": 1, "access_remaining": 1}, "success", "complete"),
    ({"retry_delayed_count": 1}, "failure", "degraded"),
    ({"retry_remaining": 1}, "failure", "degraded"),
    ({"intake_status": "failed"}, "failure", "degraded"),
    ({"cleanup_status": "deferred"}, "failure", "degraded"),
    ({"cleanup_status": "pending"}, "unknown", "cleanup_unconfirmed"),
    ({"stage": "failed"}, "failure", "failed"),
    ({"stage": "skipped"}, "unknown", "blocked_by_collection"),
    ({"stage": "processing", "finished_at": None}, "unknown", "processing"),
    ({"stage": "awaiting_commit", "finished_at": None}, "unknown", "awaiting_commit"),
    ({"enabled": False, "stage": "disabled"}, "unknown", "disabled"),
    ({"heartbeat_at": "2026-09-18T19:59:10Z"}, "unknown", "invalid_evidence"),
])
def test_stage_health_is_not_inferred_from_parent_success(changes, expected, activity):
    result = run_health(metrics(**changes), RUN, NOW)
    assert (result["status"], result["activity"]) == (expected, activity)


def test_complete_stage_requires_a_committed_parent_and_finished_timestamp():
    assert run_health(metrics(), {**RUN, "status": "failure"}, NOW)["status"] == "unknown"
    assert run_health(metrics(finished_at=None), RUN, NOW)["status"] == "unknown"
    assert run_health(metrics(), {**RUN, "state_evidence": False}, NOW)["status"] == "unknown"


def test_stale_heartbeat_and_overdue_terminal_pass_do_not_remain_green():
    future = datetime(2026, 9, 17, 22, 0, tzinfo=timezone.utc)
    assert run_health(metrics(stage="processing", finished_at=None), RUN, future)["activity"] == "stalled"
    assert run_health(metrics(), RUN, future)["status"] == "stale"


def test_latest_attempt_and_stalled_ready_queue_override_previous_success():
    good = {**RUN, "source_ocr_metrics": metrics()}
    bad = {**RUN, "id": "newer", "source_ocr_metrics": metrics(stage="failed")}
    assert branch_health([bad, good], NOW)["status"] == "failure"
    assert branch_health([{**RUN, "source_ocr_metrics": {}}, good], NOW)["required"] is True
    due = {**good, "source_ocr_metrics": metrics(ready_remaining=2)}
    assert branch_health([{**due,"id":str(i)} for i in range(3)], NOW)["activity"] == "stalled"
    waiting = {**good, "source_ocr_metrics": metrics(access_remaining=2, review_remaining=3)}
    assert branch_health([waiting, waiting, waiting], NOW)["status"] == "success"


def test_health_whitelists_and_validates_all_fields():
    result = safe_metrics(metrics(raw_pdf="SECRET", source_url="https://secret.test/?token=secret", account_id="SECRET",
                                  error_code="secret URL https://private.test"))
    assert not {"raw_pdf", "source_url", "account_id"} & result.keys()
    assert result["error_code"] == "unclassified_error"
    for key, value in [("documents_attempted", -1), ("pages_completed", True), ("heartbeat_at", "yesterday"), ("stage", "invented")]:
        with pytest.raises(ValueError): safe_metrics(metrics(**{key: value}))


def test_dashboard_retains_separate_ocr_and_collector_outcomes():
    observed = {"schema_version": 1, "available": True, "observed_at_utc": NOW.isoformat(), "branches": {}}
    for name in ("legislative", "executive", "ai"):
        stage = metrics(cleanup_status="deferred") if name == "legislative" else metrics()
        observed["branches"][name] = {"available": True, "attempts": [{
            "run_key": name, "branch": name, "evidence_source": "runtime_v2", "runtime_mode": "production",
            "runtime_mode_verified": True, "runtime_mode_evidence": {"kind": "snapshot_provenance", "mode": "production", "source_ocr": stage},
            "started_utc": RUN["started_utc"], "finished_utc": RUN["finished_utc"], "success": True, "conclusion": "success",
            "trigger_source": "external_scheduler"}]}
    source = {"summary": {"generated_utc": NOW.isoformat()}, "workflow_evidence": observed}
    result = dashboard_insights.build_insights(source)
    assert result["health"]["status"] == "failure"
    branch = result["health"]["branches"][0]
    assert branch["status"] == "success"
    assert branch["source_ocr"]["status"] == "failure"
    assert branch["timeline"][0]["source_ocr_metrics"]["cleanup_status"] == "deferred"
    # No OCR health record can smuggle document contents into public artifacts.
    observed["branches"]["legislative"]["attempts"][0]["runtime_mode_evidence"]["source_ocr"]["raw_pdf"] = "PRIVATE_DOCUMENT"
    assert "PRIVATE_DOCUMENT" not in json.dumps(dashboard_insights.build_insights(source))


@pytest.mark.parametrize("fault", ["intake", "cleanup", "engine", "collection"])
def test_runner_records_intake_cleanup_engine_and_upstream_failures(monkeypatch, fault):
    import test_runtime_v2_shadow_mode as fixtures
    from runtime_v2.runner import JobRunner
    from runtime_v2 import source_uploads, source_ocr_worker
    store = fixtures._RunStore()
    recorded = []
    monkeypatch.setattr(store.lock, "record_ocr_health", lambda _id, state: recorded.append(copy.deepcopy(state)), raising=False)
    runner = JobRunner(store, source_revision="a" * 40,
                       environment={"POLITITRACK_MODE": "production", "RUNTIME_SOURCE_OCR_ENABLED": "true"})
    def fail(): raise RuntimeError("TEST")
    monkeypatch.setattr(runner, "_execute", lambda *a: fail() if fault == "collection" else None)
    monkeypatch.setattr(runner, "_prepare_notifications", lambda *a: None)
    monkeypatch.setattr(runner, "_notification_commit_options", lambda *a: ({}, {}))
    monkeypatch.setattr(runner, "_dispatch_notifications", lambda *a: None)
    monkeypatch.setattr(source_uploads, "SourceUploadStore", lambda: SimpleNamespace(
        pending=lambda *a: fail() if fault == "intake" else [],
        acknowledge=lambda *a: fail() if fault == "cleanup" else None))
    def work(*a, **kwargs):
        if fault == "engine": fail()
        kwargs["health"].update(documents_attempted=1)
        return [{"TEST": "outcome"}]
    monkeypatch.setattr(source_ocr_worker, "run_pass", work)
    if fault in {"engine", "collection"}:
        with pytest.raises(RuntimeError): runner.run("legislative")
        assert recorded[-1]["stage"] == ("skipped" if fault == "collection" else "failed")
        assert store.lock.provenance is None
    else:
        runner.run("legislative")
        assert recorded[-1]["stage"] == "complete"
        assert recorded[-1]["intake_status" if fault == "intake" else "cleanup_status"] == ("failed" if fault == "intake" else "deferred")
        assert store.lock.provenance["authority"] == "runtime_v2"


def test_worker_reports_actual_ocr_not_only_row_import(tmp_path):
    from test_source_ocr_runtime import source_state, ENV, evidence
    from runtime_v2.source_ocr_worker import run_pass
    report = metrics(stage="processing", finished_at=None)
    beats = []
    directory = source_state(tmp_path)
    run_pass(directory, "legislative", ENV, loader=lambda *a: b"test", extractor=lambda *a, **k: evidence(),
             health=report, on_progress=lambda state: beats.append(copy.deepcopy(state)))
    assert report["documents_attempted"] == report["documents_completed"] == 1
    assert report["pages_completed"] == report["pages_expected"] == 1
    assert report["transactions_appended"] == 2
    assert report["ready_remaining"] == report["unobserved_remaining"] == 0
    assert len(beats) >= 2


def test_real_postgres_ocr_telemetry_survives_atomic_commit_and_cleanup(tmp_path):
    from test_runtime_v2_mode_quarantine import _postgres_connection
    from runtime_v2.store import LockedNamespace, utc_now
    connection = _postgres_connection()
    schema = "ocr_health_" + uuid.uuid4().hex
    cursor = connection.cursor()
    try:
        cursor.execute('CREATE SCHEMA "' + schema + '"')
        cursor.execute('SET search_path TO "' + schema + '"')
        # Use the actual additive Runtime schema in an isolated test-only schema.
        migration = Path(__file__).resolve().parents[1] / "migrations/20260904_runtime_v2_mode_quarantine.sql"
        cursor.execute(migration.read_text())
        locked = LockedNamespace(connection, "legislative")
        run_id = locked.start_run("legislative", "external_scheduler", "a" * 40, "production")
        stamp = utc_now()
        report = metrics(stage="awaiting_commit", started_at=stamp, heartbeat_at=stamp, finished_at=None)
        locked.record_ocr_health(run_id, report)
        directory = tmp_path / "state"; directory.mkdir(); (directory / "state.json").write_text('{"TEST": true}')
        snapshot = locked.commit(directory, expected_parent_sha256=None, source_revision="a" * 40,
            successful_run_id=run_id, allow_initial=True, provenance={"authority": "runtime_v2", "job": "legislative",
                "mode": "production", "trigger_source": "external_scheduler"})
        cursor.execute("SELECT status,runtime_mode_evidence,snapshot_sha256 FROM runtime_job_runs WHERE run_id=%s::uuid", (run_id,))
        row = cursor.fetchone()
        payload = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        assert row[0] == "success" and row[2] == snapshot.snapshot_sha256
        assert payload["kind"] == "snapshot_provenance" and payload["source_ocr"]["stage"] == "awaiting_commit"
        stamp = utc_now()
        locked.record_ocr_health(run_id, {**report, "stage": "complete", "heartbeat_at": stamp, "finished_at": stamp,
                                          "cleanup_status": "deferred"})
        cursor.execute("SELECT status,runtime_mode_evidence,snapshot_sha256 FROM runtime_job_runs WHERE run_id=%s::uuid", (run_id,))
        updated = cursor.fetchone()
        payload = json.loads(updated[1]) if isinstance(updated[1], str) else updated[1]
        assert updated[0] == "success" and updated[2] == row[2]
        assert payload["source_ocr"]["cleanup_status"] == "deferred"
        assert payload["snapshot_sha256"] == snapshot.snapshot_sha256
    finally:
        cursor.execute('SET search_path TO public')
        cursor.execute('DROP SCHEMA IF EXISTS "' + schema + '" CASCADE')
        cursor.close(); connection.close()


def test_previously_ocr_processed_inventory_requires_telemetry_after_old_runs_age_out():
    from test_dashboard_insights import payload, run
    source = payload(filings=[{"filing_key":"house:retained-ocr-case", "branch":"legislative", "source":"house", "ocr_status":"complete"}],
                     runs=[run("legislative"), run("executive")], ai_runs=[run("ai")])
    health = dashboard_insights.build_insights(source)["health"]
    assert health["branches"][0]["source_ocr"]["required"] is True
    assert health["branches"][0]["source_ocr"]["status"] == "unknown"
    assert health["status"] != "success"


def test_missing_ocr_dependency_is_not_reported_as_healthy_idle(tmp_path, monkeypatch):
    from test_source_ocr_runtime import source_state, ENV
    from runtime_v2.source_ocr_worker import run_pass
    from scripts.source_ocr import OCRError
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(OCRError, match="ocr_dependency_unavailable"):
        run_pass(source_state(tmp_path), "legislative", ENV)
