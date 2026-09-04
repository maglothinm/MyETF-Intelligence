from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts import ai_retry_guard as guard
from scripts.ai_retry_guard import (
    AdjudicatingAPI,
    RetryAdjudicationError,
    validate_hardened_no_delivery,
    validate_legacy_incident,
)

REPOSITORY = "maglothinm/MyETF-Intelligence"
HEAD = "d603e9b40ffb78c51f635589bc886875f411299b"

def _artifact(artifact_id: int, name: str, digest: str, run_id: int, head: str = HEAD) -> dict:
    return {
        "id": artifact_id,
        "name": name,
        "expired": False,
        "digest": f"sha256:{digest}",
        "workflow_run": {
            "id": run_id,
            "result_schema_version": 2,
        "repository_id": 1349678672,
            "head_sha": head,
        },
    }


def _run(run_id: int, attempt: int, *, head: str = HEAD, conclusion: str = "failure") -> dict:
    return {
        "id": run_id,
        "run_attempt": attempt,
        "head_sha": head,
        "head_branch": "main",
        "name": "AI filing analyst and paper portfolio",
        "path": ".github/workflows/ai_filing_analyst.yml",
        "workflow_id": 344663669,
        "conclusion": conclusion,
        "event": "workflow_run",
        "repository": {"id": 1349678672},
    }


def _jobs() -> dict:
    return {
        "total_count": 1,
        "jobs": [
            {
                "name": "analyze",
                "conclusion": "failure",
                "steps": [
                    {
                        "name": "Analyze new filing purchases",
                        "status": "completed",
                        "conclusion": "failure",
                    }
                ],
            }
        ],
    }


def _legacy_result() -> dict:
    return {
        "success": False,
        "attempted_count": 20,
        "completed_count": 19,
        "high_priority_count": 0,
        "watchlist_count": 0,
        "weak_signal_count": 0,
        "archive_count": 19,
        "alerted_count": 0,
        "paper_positions_opened": 0,
        "paper_positions_updated": 0,
        "paper_positions_closed": 0,
        "market_signal_upgrades": 0,
        "errors": [
            "SOLS / trade:69aca1536296edcfe2d0a17b52b1d579: AnalystError: "
            "OpenAI returned invalid JSON: Unterminated string starting at: "
            "line 1 column 3296 (char 3295)"
        ],
        "analyses": [
            {"trade_id": f"trade:{index}", "classification": "archive"}
            for index in range(19)
        ],
    }


def _legacy_api(tmp_path: Path) -> tuple[dict[str, dict], dict[int, bytes], Path]:
    raw_result = json.dumps(_legacy_result(), sort_keys=True).encode()
    diagnostic_stream = io.BytesIO()
    with zipfile.ZipFile(
        diagnostic_stream, "w", compression=zipfile.ZIP_DEFLATED
    ) as bundle:
        bundle.writestr("ai-analysis-result.json", raw_result)
    diagnostic_archive = diagnostic_stream.getvalue()
    diagnostic_digest = hashlib.sha256(diagnostic_archive).hexdigest()
    result_digest = hashlib.sha256(raw_result).hexdigest()

    predecessor_state = {
        "version": 1,
        "last_success_utc": "2026-09-02T13:57:34Z",
        "candidate_alert_deliveries": {},
        "positions": {},
    }
    predecessor_stream = io.BytesIO()
    with zipfile.ZipFile(
        predecessor_stream, "w", compression=zipfile.ZIP_DEFLATED
    ) as bundle:
        bundle.writestr("state.json", json.dumps(predecessor_state))
    predecessor_archive = predecessor_stream.getvalue()
    predecessor_digest = hashlib.sha256(predecessor_archive).hexdigest()

    manifest = {
        "schema_version": 1,
        "issue": 121,
        "decision": "safe_to_replay",
        "repository": {
            "id": 1349678672,
            "full_name": REPOSITORY,
            "default_branch": "main",
        },
        "workflow": {
            "path": ".github/workflows/ai_filing_analyst.yml",
            "name": "AI filing analyst and paper portfolio",
            "workflow_id": 344663669,
            "job": "analyze",
            "step": "Analyze new filing purchases",
        },
        "attempt": {
            "run_id": 33646778055,
            "run_attempt": 1,
            "head_sha": HEAD,
            "conclusion": "failure",
        },
        "predecessor": {
            "artifact_name": "ai-analysis-state",
            "artifact_id": 9849967781,
            "artifact_digest": "sha256:" + predecessor_digest,
            "producer_run_id": 33638794359,
            "producer_run_attempt": 1,
            "head_sha": HEAD,
            "required_state": predecessor_state,
        },
        "diagnostic": {
            "artifact_name": "ai-analysis-output-33646778055",
            "artifact_id": 9854021376,
            "artifact_digest": "sha256:" + diagnostic_digest,
            "result_file": "ai-analysis-result.json",
            "result_file_sha256": result_digest,
        },
        "source_blobs": {
            ".github/workflows/ai_filing_analyst.yml": "8dc872026de7fda219fca64771d0f009b81cd1ff",
            "scripts/ai_filing_analyst.py": "c064f0e6e87109e06a1e31dc9d46c907cf1956c0",
        },
        "required_result": {
            key: value
            for key, value in _legacy_result().items()
            if key != "analyses"
        }
        | {"allowed_classifications": ["archive"]},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    mapping = {
        f"/repos/{REPOSITORY}/actions/runs/33646778055/attempts/1": _run(
            33646778055, 1
        ),
        f"/repos/{REPOSITORY}/actions/runs/33638794359/attempts/1": _run(
            33638794359, 1, conclusion="success"
        ),
        f"/repos/{REPOSITORY}/actions/runs/33638794359/attempts/1/jobs?per_page=100": {
            "total_count": 1,
            "jobs": [
                {
                    "name": "analyze",
                    "conclusion": "success",
                    "steps": [],
                }
            ],
        },
        f"/repos/{REPOSITORY}/actions/artifacts/9849967781": _artifact(
            9849967781,
            "ai-analysis-state",
            predecessor_digest,
            33638794359,
        ),
        f"/repos/{REPOSITORY}/actions/artifacts/9854021376": _artifact(
            9854021376,
            "ai-analysis-output-33646778055",
            diagnostic_digest,
            33646778055,
        ),
        f"/repos/{REPOSITORY}/git/commits/{HEAD}": {
            "tree": {"sha": "b" * 40},
        },
        f"/repos/{REPOSITORY}/git/trees/{'b' * 40}?recursive=1": {
            "truncated": False,
            "tree": [
                {
                    "path": ".github/workflows/ai_filing_analyst.yml",
                    "type": "blob",
                    "sha": "8dc872026de7fda219fca64771d0f009b81cd1ff",
                },
                {
                    "path": "scripts/ai_filing_analyst.py",
                    "type": "blob",
                    "sha": "c064f0e6e87109e06a1e31dc9d46c907cf1956c0",
                },
            ],
        },
        f"/repos/{REPOSITORY}/actions/runs/33646778055/attempts/1/jobs?per_page=100": _jobs(),
    }
    return (
        mapping,
        {
            9849967781: predecessor_archive,
            9854021376: diagnostic_archive,
        },
        manifest_path,
    )


def _pin_generated_manifest(
    monkeypatch: pytest.MonkeyPatch, manifest_path: Path
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        guard,
        "LEGACY_PREDECESSOR_DIGEST",
        manifest["predecessor"]["artifact_digest"].removeprefix("sha256:"),
    )
    monkeypatch.setattr(
        guard,
        "LEGACY_DIAGNOSTIC_DIGEST",
        manifest["diagnostic"]["artifact_digest"].removeprefix("sha256:"),
    )
    monkeypatch.setattr(
        guard,
        "LEGACY_RESULT_DIGEST",
        manifest["diagnostic"]["result_file_sha256"],
    )


class FakeAPI:
    def __init__(self, mapping: dict[str, dict]):
        self.mapping = mapping

    def __call__(self, path: str) -> dict:
        return self.mapping[path]


def test_exact_legacy_incident_validates_against_pinned_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapping, archives, manifest_path = _legacy_api(tmp_path)
    _pin_generated_manifest(monkeypatch, manifest_path)
    validate_legacy_incident(
        FakeAPI(mapping),
        REPOSITORY,
        33646778055,
        1,
        33638794359,
        1,
        lambda _repo, artifact_id, _token: archives[artifact_id],
        "token",
        manifest_path=manifest_path,
    )


def test_legacy_adjudication_rejects_altered_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapping, archives, manifest_path = _legacy_api(tmp_path)
    _pin_generated_manifest(monkeypatch, manifest_path)
    with pytest.raises(RetryAdjudicationError, match="archive_digest"):
        validate_legacy_incident(
            FakeAPI(mapping),
            REPOSITORY,
            33646778055,
            1,
            33638794359,
            1,
            lambda _repo, artifact_id, _token: (
                archives[artifact_id] + b"changed"
                if artifact_id == 9854021376
                else archives[artifact_id]
            ),
            "token",
            manifest_path=manifest_path,
        )



def test_legacy_adjudication_rejects_scope_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapping, archives, manifest_path = _legacy_api(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["attempt"]["run_id"] = 33646778056
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _pin_generated_manifest(monkeypatch, manifest_path)
    with pytest.raises(RetryAdjudicationError, match="scope_mismatch"):
        validate_legacy_incident(
            FakeAPI(mapping),
            REPOSITORY,
            33646778055,
            1,
            33638794359,
            1,
            lambda _repo, artifact_id, _token: archives[artifact_id],
            "token",
            manifest_path=manifest_path,
        )

def _zip_result(result: dict) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("ai-analysis-result.json", json.dumps(result))
    return stream.getvalue()


def _future_api(result: dict, *, run_id: int = 400, attempt: int = 1):
    head = "a" * 40
    archive = _zip_result(result)
    digest = hashlib.sha256(archive).hexdigest()
    artifact = _artifact(900, f"ai-analysis-output-{run_id}-{attempt}", digest, run_id, head)
    mapping = {
        f"/repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}": _run(
            run_id, attempt, head=head
        ),
        f"/repos/{REPOSITORY}/actions/runs/{run_id}/artifacts?per_page=100": {
            "total_count": 1,
            "artifacts": [artifact],
        },
        f"/repos/{REPOSITORY}/actions/artifacts/900": artifact,
    }
    return FakeAPI(mapping), archive


def _fatal_result(**overrides):
    result = {
        "result_schema_version": 2,
        "repository_id": 1349678672,
        "workflow_run_id": "400",
        "workflow_run_attempt": "1",
        "source_revision": "a" * 40,
        "run_status": "fatal",
        "state_publishable": False,
        "success": False,
        "delivery_phase_started": False,
        "delivery_attempt_count": 0,
        "delivery_confirmed_count": 0,
        "delivery_uncertain_count": 0,
        "fatal_errors": ["state integrity failure"],
        "errors": ["state integrity failure"],
        "deferred_candidates": [],
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize(
    "result",
    [
        _fatal_result(),
        _fatal_result(
            run_status="success",
            state_publishable=True,
            success=True,
            fatal_errors=[],
            errors=[],
            deferred_candidates=[],
        ),
        _fatal_result(
            run_status="degraded",
            state_publishable=True,
            success=True,
            fatal_errors=[],
            errors=[],
            deferred_candidates=[{"trade_id": "trade:deferred"}],
        ),
    ],
)
def test_hardened_terminal_attempt_without_delivery_is_replay_safe(result) -> None:
    api, archive = _future_api(result)
    assert validate_hardened_no_delivery(
        api,
        REPOSITORY,
        400,
        1,
        lambda *_args: archive,
        "token",
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("delivery_phase_started", True),
        ("delivery_attempt_count", 1),
        ("delivery_uncertain_count", 1),
        ("state_publishable", True),
    ],
)
def test_hardened_attempt_with_uncertain_or_started_delivery_is_blocked(field, value) -> None:
    api, archive = _future_api(_fatal_result(**{field: value}))
    assert not validate_hardened_no_delivery(
        api,
        REPOSITORY,
        400,
        1,
        lambda *_args: archive,
        "token",
    )


def test_proxy_changes_only_exactly_adjudicated_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mapping, archives, manifest_path = _legacy_api(tmp_path)
    _pin_generated_manifest(monkeypatch, manifest_path)
    api = AdjudicatingAPI(
        FakeAPI(mapping),
        repository=REPOSITORY,
        producer_run=33638794359,
        producer_attempt=1,
        token="token",
        artifact_loader=lambda _repo, artifact_id, _token: archives[artifact_id],
        manifest_path=manifest_path,
    )
    path = f"/repos/{REPOSITORY}/actions/runs/33646778055/attempts/1/jobs?per_page=100"
    transformed = api(path)
    step = transformed["jobs"][0]["steps"][0]
    assert step["conclusion"] == "skipped"
    assert step["retry_adjudication"] == "safe_to_replay"
    assert mapping[path]["jobs"][0]["steps"][0]["conclusion"] == "failure"
