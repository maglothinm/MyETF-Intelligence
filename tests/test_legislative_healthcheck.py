import hashlib
import json
from pathlib import Path
from urllib.error import URLError

import pytest
import yaml

from scripts import legislative_healthcheck as hc


def complete():
    return dict(success=True, discovery_complete=True, overall_status="ok",
                source_statuses={"house": "ok", "senate": "ok"},
                source_counts={"house": 883, "senate": 91},
                transaction_counts={"house": 0, "senate": 0},
                pending_review_counts={"house": 0, "senate": 0},
                alerted_filing_counts={"house": 0, "senate": 0})


def degraded():
    return dict(success=True, discovery_complete=False, overall_status="degraded",
                source_statuses={"house": "ok", "senate": "blocked"},
                source_counts={"house": 883},
                transaction_counts={"house": 0},
                pending_review_counts={"house": 0},
                alerted_filing_counts={"house": 0},
                started_utc="2026-09-05T13:00:00Z",
                finished_utc="2026-09-05T13:01:00Z")


def state():
    return dict(version=1, last_success_utc="2026-09-05T13:01:00Z",
                seen_filings={"house": {}, "senate": {}, "oge": {}},
                seen_trades={}, seen_reviews={})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_terminal_failure_is_one_classified_ping_without_source_material(capsys):
    requests = []
    class Accepted:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def send(request, **kwargs):
        requests.append(request)
        return Accepted()
    result = dict(success=False, discovery_complete=False, overall_status="degraded",
                  source_statuses={"house": "ok", "senate": "blocked"},
                  source_counts={"house": 883},
                  errors=["Cookie: sessionid=secret; csrfmiddlewaretoken=secret"],
                  diagnostics="sensitive response body")
    assert hc.signal_terminal(result, base_url="https://hc-ping.com/private-uuid/start",
                              job_status="failure", tracker_outcome="failure", opener=send)
    assert len(requests) == 1
    assert requests[0].full_url.endswith("/private-uuid/fail")
    assert requests[0].data == b"senate_access_denied"
    output = capsys.readouterr().out
    for secret in ("private-uuid", "sessionid", "csrfmiddlewaretoken", "sensitive", "secret"):
        assert secret not in output
    assert "success ping" not in output


@pytest.mark.parametrize("alter", [
    {"success": False}, {"source_counts": {"house": 883}},
    {"source_counts": {"house": 883, "senate": 0}},
    {"source_counts": {"house": 883, "senate": True}},
    {"source_statuses": {"house": "ok", "senate": "error"}},
    {"discovery_complete": False}, {"overall_status": "degraded"},
])
def test_house_only_or_invalid_result_cannot_signal_success(alter):
    result = complete() | alter
    assert not hc.complete_result(result)
    assert hc.terminal_classification(result, "success", "success") != "legislative_complete"


def test_success_requires_successful_job_and_tracker():
    assert hc.complete_result(complete())
    assert hc.terminal_classification(complete(), "success", "success") == "legislative_complete"
    assert hc.terminal_classification(complete(), "failure", "success") == "legislative_workflow_failed"
    assert hc.terminal_classification(complete(), "success", "failure") == "legislative_workflow_failed"
    assert hc.complete_catalogs(complete() | {"success": False, "overall_status": "degraded"})


def test_delivery_error_is_not_retried_and_does_not_log_secret(capsys):
    requests = []
    def fail(request, **kwargs):
        requests.append(request)
        raise URLError("https://hc-ping.com/private-key")
    assert not hc.signal_terminal({}, base_url="https://hc-ping.com/private-key",
                                  job_status="failure", tracker_outcome="failure", opener=fail)
    assert len(requests) == 1
    assert "private-key" not in capsys.readouterr().out


def test_invalid_endpoint_is_sanitized_and_redirects_are_not_followed(capsys):
    def must_not_send(*args, **kwargs):
        raise AssertionError("Invalid endpoint must not send a request")
    assert not hc.signal_terminal({}, base_url="malformed-private-secret",
                                  job_status="failure", tracker_outcome="failure", opener=must_not_send)
    assert "private-secret" not in capsys.readouterr().out
    assert hc.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test/") is None


def test_complete_source_gate_exits_nonzero_for_failure_and_malformed_result(tmp_path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"success": False, "overall_status": "degraded"}))
    assert hc.main(["--result", str(path), "--validate-only"]) == 1
    path.write_text("not json")
    assert hc.main(["--result", str(path), "--validate-only"]) == 1
    path.write_text(json.dumps(complete()))
    assert hc.main(["--result", str(path), "--validate-only"]) == 0


@pytest.mark.parametrize("result", [complete(), degraded()])
def test_durable_result_accepts_complete_or_exactly_one_successful_source(result):
    assert hc.durable_result(result)


@pytest.mark.parametrize("alter", [
    {"success": False},
    {"source_statuses": {"house": "ok", "senate": "pending"}},
    {"source_statuses": {"house": "blocked", "senate": "error"}},
    {"source_counts": {"house": 0}},
    {"source_counts": {"house": True}},
    {"overall_status": "ok"},
    {"discovery_complete": True},
])
def test_durable_result_rejects_inconsistent_degraded_evidence(alter):
    assert not hc.durable_result(degraded() | alter)


def test_hashed_suppressed_receipt_binds_degraded_result_and_complete_state(tmp_path):
    result_path = tmp_path / "result.json"
    state_path = tmp_path / "state.json"
    receipt_path = tmp_path / "source-status.json"
    result_path.write_text(json.dumps(degraded()), encoding="utf-8")
    state_path.write_text(json.dumps(state()), encoding="utf-8")
    receipt = {
        "version": 3,
        "started_utc": degraded()["started_utc"],
        "finished_utc": degraded()["finished_utc"],
        "overall_status": "degraded",
        "success": True,
        "durable_state_eligible": True,
        "protected_upload_eligible": True,
        "validation_outcome": "zero_change_successor",
        "protected_state_action": "committed",
        "rollback_performed": False,
        "rollback_verified": False,
        "rollback_reason": "",
        "notifications_suppressed": True,
        "outbound_notifications_attempted": 0,
        "outbound_notifications_sent": 0,
        "notification_eligible_new_records": 0,
        "notification_delivery_count": 0,
        "result_sha256": sha256(result_path),
        "state_sha256": sha256(state_path),
        "sources": [
            {"source": "senate", "returncode": 1, "status": "blocked",
             "state_candidate_valid": False,
             "state_committed": False, "result_file": "senate.json",
             "notification_eligible_new_records": 0,
             "notification_delivery_count": 0,
             "notification_delivery_evidence": "unavailable",
             "reported_outbound_notifications_sent": None},
            {"source": "house", "returncode": 0, "status": "ok",
             "state_candidate_valid": True,
             "state_committed": True, "result_file": "house.json",
             "notification_eligible_new_records": 0,
             "notification_delivery_count": 0,
             "notification_delivery_evidence": "verified_zero",
             "reported_outbound_notifications_sent": 0},
        ],
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert hc.main([
        "--result", str(result_path), "--state", str(state_path),
        "--source-status", str(receipt_path), "--validate-durable",
        "--require-notifications-suppressed",
        "--require-no-notification-eligible-records",
    ]) == 0

    receipt["notifications_suppressed"] = False
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert hc.main([
        "--result", str(result_path), "--state", str(state_path),
        "--source-status", str(receipt_path), "--validate-durable",
        "--require-notifications-suppressed",
    ]) == 1

    receipt["notifications_suppressed"] = True
    receipt["result_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert hc.main([
        "--result", str(result_path), "--state", str(state_path),
        "--source-status", str(receipt_path), "--validate-durable",
    ]) == 1


def test_workflow_keeps_manual_validation_suppressed_and_state_upload_gated():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load((root / ".github/workflows/legislative_trade_tracker_v2.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert "github.event_name == 'workflow_dispatch'" in workflow["jobs"]["track"]["if"]
    steps = workflow["jobs"]["track"]["steps"]
    tracker = next(step for step in steps if step.get("id") == "tracker")
    assert tracker["continue-on-error"] == "true"
    assert "--no-notify" in tracker["run"]
    assert "PUSHOVER_API_TOKEN" not in tracker.get("env", {})
    assert "PUSHOVER_USER_KEY" not in tracker.get("env", {})
    durable = next(step for step in steps if step.get("id") == "durable_validation")
    assert durable["continue-on-error"] == "true"
    assert "--validate-durable" in durable["run"]
    assert "--require-restore-receipt" in durable["run"]
    assert "--require-controlled-validation-receipt" in durable["run"]
    assert "--require-notifications-suppressed" in durable["run"]
    assert "--require-no-notification-eligible-records" in durable["run"]
    assert "--require-run-provenance" in durable["run"]
    gate = next(step for step in steps if step.get("id") == "state_validation")
    assert gate.get("continue-on-error", "false") == "false"
    assert "--validate-protected-upload" in gate["run"]
    assert "--require-run-provenance" in gate["run"]
    upload = next(step for step in steps if step["name"] == "Upload protected tracker state")
    assert "success()" in upload["if"]
    assert "steps.state_validation.outcome == 'success'" in upload["if"]
    assert "hashFiles" not in upload["if"]
    diagnostic = next(step for step in steps if step["name"] == "Upload run outputs")
    assert "always()" in diagnostic["if"]
    assert diagnostic["continue-on-error"] == "true"
    assert ".trade-tracker/legislative/source-status.json" in diagnostic["with"]["path"]
    assert ".trade-tracker/legislative/restore-receipt.json" in diagnostic["with"]["path"]
    assert ".trade-tracker/legislative/controlled-validation-receipt.json" in diagnostic["with"]["path"]
    workflow_text = (root / ".github/workflows/legislative_trade_tracker_v2.yml").read_text()
    assert "artifact_unexpired=\"$(jq -r '.expired == false'" in workflow_text
    assert ".expired // true" not in workflow_text
    assert "LEGISLATIVE_HEALTHCHECKS_PING_URL" not in workflow_text
    assert "PUSHOVER_API_TOKEN" not in workflow_text
    assert "PUSHOVER_USER_KEY" not in workflow_text
