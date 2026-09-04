from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_ai_publication import PublicationError, validate_publication

REPO_ID = 1349678672
RUN = "500"
ATTEMPT = "2"
SHA = "a" * 40
FINISHED = "2026-09-04T15:30:00Z"


def _result(status: str = "success") -> dict:
    deferred = [] if status == "success" else [{"trade_id": "trade:1"}]
    return {
        "result_schema_version": 2,
        "repository_id": REPO_ID,
        "workflow_run_id": RUN,
        "workflow_run_attempt": ATTEMPT,
        "source_revision": SHA,
        "run_status": status,
        "state_publishable": True,
        "success": True,
        "fatal_errors": [],
        "deferred_candidates": deferred,
        "errors": [],
        "delivery_phase_started": False,
        "delivery_attempt_count": 0,
        "delivery_confirmed_count": 0,
        "delivery_uncertain_count": 0,
        "finished_utc": FINISHED,
    }


def _state() -> dict:
    return {"version": 1, "last_success_utc": FINISHED}


@pytest.mark.parametrize("status", ["success", "degraded"])
def test_publishable_terminal_result_is_accepted(status: str) -> None:
    assert validate_publication(
        _result(status),
        state=_state(),
        repository_id=REPO_ID,
        run_id=RUN,
        run_attempt=ATTEMPT,
        source_revision=SHA,
    ) == (status, True)


def test_fatal_result_is_valid_but_not_publishable() -> None:
    result = _result()
    result.update(
        {
            "run_status": "fatal",
            "state_publishable": False,
            "success": False,
            "fatal_errors": ["state failed"],
            "errors": ["state failed"],
        }
    )
    assert validate_publication(
        result,
        state=None,
        repository_id=REPO_ID,
        run_id=RUN,
        run_attempt=ATTEMPT,
        source_revision=SHA,
    ) == ("fatal", False)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.update(repository_id=1),
        lambda row: row.update(workflow_run_id="other"),
        lambda row: row.update(source_revision="b" * 40),
        lambda row: row.update(run_status="degraded", deferred_candidates=[]),
        lambda row: row.update(run_status="success", deferred_candidates=[{}]),
        lambda row: row.update(delivery_attempt_count=1),
        lambda row: row.update(delivery_phase_started=True),
        lambda row: row.update(delivery_uncertain_count=1),
    ],
)
def test_inconsistent_result_is_rejected(mutation) -> None:
    result = deepcopy(_result())
    mutation(result)
    with pytest.raises(PublicationError):
        validate_publication(
            result,
            state=_state(),
            repository_id=REPO_ID,
            run_id=RUN,
            run_attempt=ATTEMPT,
            source_revision=SHA,
        )


def test_state_marker_must_match_completion() -> None:
    with pytest.raises(PublicationError, match="marker"):
        validate_publication(
            _result(),
            state={"last_success_utc": "2026-09-04T15:29:59Z"},
            repository_id=REPO_ID,
            run_id=RUN,
            run_attempt=ATTEMPT,
            source_revision=SHA,
        )


def test_workflow_uses_hardened_single_writer_boundary() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ai_filing_analyst.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count("name: ai-analysis-state") == 1
    assert "python scripts/ai_filing_analyst.py" in workflow
    assert "python scripts/ai_retry_guard.py" in workflow
    assert "python scripts/validate_ai_publication.py" in workflow
    facade = (root / "scripts/ai_filing_analyst.py").read_text(encoding="utf-8")
    assert "ai_filing_analyst_legacy.py" in facade
    assert "run_analyst = _hardened.run_analyst" in facade
    assert "main = _hardened.main" in facade
    assert "ai-analysis-output-${{ github.run_id }}-${{ github.run_attempt }}" in workflow
    assert "steps.publication.outputs.state_publishable == 'true'" in workflow
    assert "continue-on-error: true\n        uses: actions/upload-artifact@v7" in workflow


def test_legacy_adjudication_has_no_wildcard_scope() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    path = root / "config/ai-retry-adjudication-33646778055.1.json"
    manifest = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert manifest["issue"] == 121
    assert manifest["decision"] == "safe_to_replay"
    assert manifest["attempt"] == {
        "conclusion": "failure",
        "head_sha": "d603e9b40ffb78c51f635589bc886875f411299b",
        "run_attempt": 1,
        "run_id": 33646778055,
    }
    assert "*" not in path.read_text(encoding="utf-8")
