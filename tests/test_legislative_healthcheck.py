import json
from pathlib import Path
from urllib.error import URLError

import pytest
import yaml

from scripts import legislative_healthcheck as hc


def complete():
    return dict(success=True, discovery_complete=True, overall_status="ok",
                source_statuses={"house": "ok", "senate": "ok"},
                source_counts={"house": 883, "senate": 91})


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


def test_workflow_keeps_terminal_failure_nonzero_and_state_upload_gated():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load((root / ".github/workflows/legislative_trade_tracker_v2.yml").read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["track"]["steps"]
    tracker = next(step for step in steps if step.get("id") == "tracker")
    assert tracker.get("continue-on-error", "false") == "false"
    gate = next(step for step in steps if step.get("id") == "discovery_validation")
    assert gate.get("continue-on-error", "false") == "false"
    upload = next(step for step in steps if step["name"] == "Upload durable tracker state")
    assert "success()" in upload["if"]
    assert "steps.tracker.outcome == 'success'" in upload["if"]
    assert "steps.discovery_validation.outcome == 'success'" in upload["if"]
    diagnostic = next(step for step in steps if step["name"] == "Upload run outputs")
    assert "always()" in diagnostic["if"]
    terminals = [step for step in steps if "scripts/legislative_healthcheck.py" in step.get("run", "") and "--validate-only" not in step["run"] and "--discovery-only" not in step["run"]]
    assert len(terminals) == 1
    assert "always()" in terminals[0]["if"]
    assert "--retry" not in terminals[0]["run"]
    assert "--data-binary" not in terminals[0]["run"]
    failure_notice = next(step for step in steps if step["name"] == "Send Pushover failure notification")
    assert "--discovery-only; then\n  exit 0" in failure_notice["run"]
