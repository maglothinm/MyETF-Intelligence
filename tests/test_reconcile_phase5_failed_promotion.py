from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import struct
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "deploy"
    / "runtime-v2"
    / "reconcile_phase5_failed_promotion.py"
)
SPEC = importlib.util.spec_from_file_location("reconcile_phase5_failed_promotion", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

IMAGE = "us-central1-docker.pkg.dev/example/runtime-v2@sha256:" + "b" * 64
DASHBOARD_DIGEST = "0f601d" + "d" * 58
ANALYSIS_ID = "analysis:deterministic"
TRADE_ID = "trade:deterministic"
DOCUMENT_HASH = "c" * 64


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _zip(path: Path, members: dict[str, bytes | str], *, infos: list[tuple[zipfile.ZipInfo, bytes]] | None = None) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, value in members.items():
            bundle.writestr(name, value)
        for info, value in infos or []:
            bundle.writestr(info, value)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode()


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(_json_bytes(row) for row in rows)


def _head(name: str, generation: int, digest: str | None = None, *, mode: str = "shadow", trigger: str = "shadow") -> dict[str, Any]:
    return {
        "namespace": name,
        "generation": generation,
        "snapshot_sha256": digest or _digest(f"{name}:{generation}"),
        "parent_sha256": _digest(f"{name}:{generation - 1}"),
        "source_revision": validator.RUNTIME_SOURCE_REVISION,
        "provenance": {
            "authority": "runtime_v2",
            "job": name,
            "mode": mode,
            "trigger_source": trigger,
        },
    }


def _latest_run(name: str, head: dict[str, Any], run_id: str, *, mode: str, trigger: str, start: datetime) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "job_name": name,
        "status": "success",
        "runtime_mode": mode,
        "runtime_mode_verified": True,
        "trigger_source": trigger,
        "side_effects_possible": False,
        "source_revision": validator.RUNTIME_SOURCE_REVISION,
        "snapshot_generation": head["generation"],
        "snapshot_sha256": head["snapshot_sha256"],
        "started_at": start.isoformat().replace("+00:00", "Z"),
        "finished_at": (start + timedelta(seconds=20)).isoformat().replace("+00:00", "Z"),
    }


def _base_status() -> dict[str, Any]:
    start = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
    heads = [_head(name, index + 8) for index, name in enumerate(validator.NAMESPACES)]
    runs = [
        _latest_run(name, head, f"phase4-{name}", mode="shadow", trigger="shadow", start=start + timedelta(minutes=index))
        for index, (name, head) in enumerate(zip(validator.NAMESPACES, heads))
    ]
    return {"heads": heads, "latest_runs": runs}


def _observations(start_status: dict[str, Any], *, clock: datetime, run_prefix: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status = copy.deepcopy(start_status)
    heads = {item["namespace"]: item for item in status["heads"]}
    latest = {item["job_name"]: item for item in status["latest_runs"]}
    observations: list[dict[str, Any]] = []
    for sequence, name in enumerate(validator.NAMESPACES, start=1):
        old = heads[name]
        digest = DASHBOARD_DIGEST if name == "dashboard" and run_prefix == "old" else _digest(
            f"{run_prefix}:{name}:{old['generation'] + 1}"
        )
        provenance: dict[str, Any] = {
            "authority": "runtime_v2",
            "job": name,
            "mode": "production",
            "trigger_source": "phase5_smoke",
        }
        if name == "ai":
            provenance["inputs"] = {
                upstream: {
                    "generation": heads[upstream]["generation"],
                    "snapshot_sha256": heads[upstream]["snapshot_sha256"],
                }
                for upstream in ("legislative", "executive")
            }
        if name == "dashboard":
            provenance["inputs"] = {
                upstream: heads[upstream]["snapshot_sha256"]
                for upstream in ("legislative", "executive", "ai")
            }
        heads[name] = {
            "namespace": name,
            "generation": old["generation"] + 1,
            "snapshot_sha256": digest,
            "parent_sha256": old["snapshot_sha256"],
            "source_revision": validator.RUNTIME_SOURCE_REVISION,
            "provenance": provenance,
        }
        latest[name] = _latest_run(
            name,
            heads[name],
            f"{run_prefix}-runtime-{name}",
            mode="production",
            trigger="phase5_smoke",
            start=clock,
        )
        snapshot = {
            "heads": [copy.deepcopy(heads[item]) for item in validator.NAMESPACES],
            "latest_runs": [copy.deepcopy(latest[item]) for item in validator.NAMESPACES],
        }
        observations.append(
            {
                "cycle": 1,
                "sequence": sequence,
                "job": name,
                "cloud_run_execution": f"polititrack-{name}-{run_prefix}",
                "status": snapshot,
            }
        )
        clock += timedelta(seconds=30)
    return observations, observations[-1]["status"]


def _certificate(base: dict[str, Any]) -> dict[str, Any]:
    heads = {item["namespace"]: item for item in base["heads"]}
    executions = []
    for cycle in (1, 2):
        for sequence, name in enumerate(validator.NAMESPACES, start=1):
            run = next(item for item in base["latest_runs"] if item["job_name"] == name)
            if cycle == 1:
                started = datetime(2026, 9, 5, 8, sequence, tzinfo=timezone.utc)
                finished = started + timedelta(seconds=20)
                run_id = f"phase4-cycle1-{name}"
                generation = heads[name]["generation"] - 1
                snapshot = _digest(f"phase4-cycle1-{name}")
            else:
                started = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
                finished = datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00"))
                run_id = run["run_id"]
                generation = heads[name]["generation"]
                snapshot = heads[name]["snapshot_sha256"]
            executions.append(
                {
                    "sequence": (cycle - 1) * 4 + sequence,
                    "cycle": cycle,
                    "job": name,
                    "cloud_run_execution": f"phase4-{cycle}-{name}",
                    "run_id": run_id,
                    "started_at": started.isoformat().replace("+00:00", "Z"),
                    "finished_at": finished.isoformat().replace("+00:00", "Z"),
                    "generation": generation,
                    "snapshot_sha256": snapshot,
                }
            )
    return {
        "schema_version": 1,
        "result": "phase4_ready_for_phase5",
        "repository_id": validator.REPOSITORY_ID,
        "control_revision": validator.CERTIFIED_CONTROL_REVISION,
        "runtime_source_revision": validator.RUNTIME_SOURCE_REVISION,
        "immutable_image": IMAGE,
        "phase5_ready": True,
        "controlled_shadow_cycles": 2,
        "unique_successful_execution_receipts": 8,
        "production_authority_transferred": False,
        "executions": executions,
        "final_heads": {
            name: {
                "generation": heads[name]["generation"],
                "snapshot_sha256": heads[name]["snapshot_sha256"],
            }
            for name in validator.NAMESPACES
        },
    }


def _run_pin(run_id: int, path: str, conclusion: str, *, head: str, job_id: int, job_name: str, start: str, finish: str, run_number: int) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_number": run_number,
        "run_attempt": 1,
        "event": "workflow_dispatch" if run_id != validator.PHASE4_RUN_ID else "push",
        "head_sha": head,
        "conclusion": conclusion,
        "created_at": start,
        "run_started_at": start,
        "updated_at": finish,
        "workflow": {"id": run_id + 100, "name": f"workflow-{run_id}", "path": path},
        "job": {"id": job_id, "name": job_name, "started_at": start, "completed_at": finish},
    }


def _run_api(pin: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": pin["run_id"],
        "run_number": pin["run_number"],
        "run_attempt": pin["run_attempt"],
        "workflow_id": pin["workflow"]["id"],
        "name": pin["workflow"]["name"],
        "path": pin["workflow"]["path"],
        "event": pin["event"],
        "head_branch": "main",
        "head_sha": pin["head_sha"],
        "status": "completed",
        "conclusion": pin["conclusion"],
        "created_at": pin["created_at"],
        "run_started_at": pin["run_started_at"],
        "updated_at": pin["updated_at"],
        "repository": {"id": validator.REPOSITORY_ID},
        "head_repository": {"id": validator.REPOSITORY_ID},
    }


def _jobs_api(pin: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_count": 1,
        "jobs": [
            {
                "id": pin["job"]["id"],
                "name": pin["job"]["name"],
                "status": "completed",
                "conclusion": pin["conclusion"],
                "run_id": pin["run_id"],
                "run_attempt": pin["run_attempt"],
                "head_sha": pin["head_sha"],
                "started_at": pin["job"]["started_at"],
                "completed_at": pin["job"]["completed_at"],
            }
        ],
    }


def _artifact_pin(
    path: Path,
    artifact_id: int,
    name: str,
    run_id: int,
    head_sha: str,
    *,
    producer: bool = True,
    created_at: str = "2026-09-05T17:40:00Z",
) -> tuple[dict[str, Any], dict[str, Any]]:
    pin: dict[str, Any] = {
        "id": artifact_id,
        "name": name,
        "size_in_bytes": path.stat().st_size,
        "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "expires_at": "2026-12-04T12:00:00Z",
    }
    if not producer:
        pin.update(producer_run_id=run_id, producer_head_sha=head_sha)
    metadata = dict(pin)
    metadata.update(
        {
            "created_at": created_at,
            "expired": False,
            "workflow_run": {
                "id": run_id,
                "repository_id": validator.REPOSITORY_ID,
                "head_repository_id": validator.REPOSITORY_ID,
                "head_branch": "main",
                "head_sha": head_sha,
            },
        }
    )
    return pin, metadata


class Evidence:
    pass


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Evidence:
    monkeypatch.setattr(validator, "_verify_tree_equal_descendant", lambda *_args: None)
    monkeypatch.setattr(
        validator, "_verify_frozen_legacy_successor_revision", lambda *_args: None
    )
    item = Evidence()
    base = _base_status()
    cert = _certificate(base)
    cert_bytes = _json_bytes(cert)
    cert_sha = hashlib.sha256(cert_bytes).hexdigest()
    item.phase4_archive = tmp_path / "phase4.zip"
    _zip(
        item.phase4_archive,
        {
            "phase4-ready.json": cert_bytes,
            "phase4-ready.sha256": f"{cert_sha}  phase4-ready.json\n",
            "nested/evidence.json": "{}\n",
        },
    )

    clock = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    old_observations, current_status = _observations(base, clock=clock, run_prefix="old")
    item.current_status = current_status
    item.failed_archive = tmp_path / "failed.zip"
    failed_members: dict[str, bytes | str] = {
        "baseline.json": _json_bytes(base),
        "observations.ndjson": _jsonl(old_observations),
        "phase4/phase4-ready.json": cert_bytes,
        "phase4/phase4-ready.sha256": f"{cert_sha}  phase4-ready.json\n",
        "rollback.json": "{}\n",
    }
    status_members = []
    for index, (name, observation) in enumerate(zip(validator.NAMESPACES, old_observations), start=1):
        member = f"smoke-sequence-{index}-{name}-status.json"
        status_members.append(member)
        failed_members[member] = _json_bytes(observation["status"])
    _zip(item.failed_archive, failed_members)

    legacy_analysis = {
        "analysis_id": ANALYSIS_ID,
        "trade_id": TRADE_ID,
        "document_content_hash": DOCUMENT_HASH,
        "openai_response_id": "legacy-response",
        "classification": "archive",
        "score": 25,
    }
    previous_analyses = [
        {
            "analysis_id": f"previous-analysis-{index}",
            "trade_id": f"previous-trade-{index}",
            "document_content_hash": _digest(f"doc-{index}"),
        }
        for index in range(12)
    ]
    previous_runs = [{"run_key": f"previous:{index}", "success": True} for index in range(60)]
    ai_start = "2026-09-05T12:00:40Z"
    ai_finish = "2026-09-05T12:01:10Z"
    legacy_run_record = {
        "run_key": f"{validator.CONCURRENT_LEGACY_AI_RUN_ID}:1",
        "success": True,
        "run_status": "success",
        "state_publishable": True,
        "attempted_count": 1,
        "completed_count": 1,
        "alerted_count": 0,
        "delivery_phase_started": False,
        "delivery_attempt_count": 0,
        "delivery_confirmed_count": 0,
        "delivery_uncertain_count": 0,
    }
    predecessor_state = {
        "version": 1,
        "last_success_utc": "2026-09-05T11:00:00Z",
        "candidate_alert_deliveries": {},
        "completed_analysis_ids": {},
    }
    successor_state = copy.deepcopy(predecessor_state)
    successor_state["last_success_utc"] = ai_finish
    successor_state["completed_analysis_ids"][ANALYSIS_ID] = ai_start
    item.predecessor_archive = tmp_path / "legacy-before.zip"
    _zip(
        item.predecessor_archive,
        {
            "analyses.jsonl": _jsonl(previous_analyses),
            "runs.jsonl": _jsonl(previous_runs),
            "state.json": _json_bytes(predecessor_state),
        },
    )
    item.state_archive = tmp_path / "legacy-after.zip"
    _zip(
        item.state_archive,
        {
            "analyses.jsonl": _jsonl(previous_analyses + [legacy_analysis]),
            "runs.jsonl": _jsonl(previous_runs + [legacy_run_record]),
            "state.json": _json_bytes(successor_state),
        },
    )
    legacy_result = {
        "result_schema_version": 2,
        "repository_id": validator.REPOSITORY_ID,
        "workflow_run_id": str(validator.CONCURRENT_LEGACY_AI_RUN_ID),
        "workflow_run_attempt": "1",
        "source_revision": "3" * 40,
        "run_status": "success",
        "state_publishable": True,
        "success": True,
        "started_utc": ai_start,
        "finished_utc": ai_finish,
        "attempted_count": 1,
        "completed_count": 1,
        "alerted_count": 0,
        "delivery_phase_started": False,
        "delivery_attempt_count": 0,
        "delivery_confirmed_count": 0,
        "delivery_uncertain_count": 0,
        "fatal_errors": [],
        "errors": [],
        "deferred_candidates": [],
        "analyses": [legacy_analysis],
    }
    item.output_archive = tmp_path / "legacy-output.zip"
    _zip(item.output_archive, {"ai-analysis-result.json": _json_bytes(legacy_result)})

    phase4_pin = _run_pin(
        validator.PHASE4_RUN_ID,
        validator.PHASE4_WORKFLOW_PATH,
        "success",
        head=validator.CERTIFIED_CONTROL_REVISION,
        job_id=501,
        job_name="controlled-shadow-acceptance",
        start="2026-09-05T16:57:06Z",
        finish="2026-09-05T17:03:52Z",
        run_number=12,
    )
    failed_pin = _run_pin(
        validator.FAILED_PHASE5_RUN_ID,
        validator.PHASE5_WORKFLOW_PATH,
        "failure",
        head=validator.CERTIFIED_CONTROL_REVISION,
        job_id=502,
        job_name="promote-production-authority",
        start="2026-09-05T11:50:00Z",
        finish="2026-09-05T13:00:00Z",
        run_number=11,
    )
    legacy_pin = _run_pin(
        validator.CONCURRENT_LEGACY_AI_RUN_ID,
        validator.AI_WORKFLOW_PATH,
        "success",
        head="3" * 40,
        job_id=503,
        job_name="analyze",
        start=ai_start,
        finish=ai_finish,
        run_number=61,
    )
    recovery_pins = [
        _run_pin(
            run_id,
            validator.RECOVERY_PATHS[role],
            "success",
            head="4" * 40,
            job_id=600 + index,
            job_name="track",
            start=f"2026-09-05T12:1{index}:00Z",
            finish=f"2026-09-05T12:1{index}:30Z",
            run_number=100 + index,
        )
        | {"role": role}
        for index, (role, run_id) in enumerate(zip(("legislative", "executive"), validator.RECOVERY_RUN_IDS))
    ]
    item.recovery_archives = []
    item.recovery_predecessor_archives = []
    item.recovery_output_archives = []
    item.recovery_artifact_metadatas = []
    item.recovery_predecessor_artifact_metadatas = []
    item.recovery_output_artifact_metadatas = []
    for index, (role, run_id, recovery_pin) in enumerate(
        zip(("legislative", "executive"), validator.RECOVERY_RUN_IDS, recovery_pins)
    ):
        started = datetime.fromisoformat(recovery_pin["job"]["started_at"].replace("Z", "+00:00"))
        result_started = started + timedelta(seconds=5)
        result_finished = started + timedelta(seconds=20)
        dimensions = copy.deepcopy(validator.RECOVERY_COUNT_DIMENSIONS[role])
        source_counts = {"house": 10, "senate": 5} if role == "legislative" else {"oge": 20}
        historical = {"completed_this_run": 0, "transactions_appended": 0}
        result = {
            "branch": role,
            "success": True,
            "overall_status": "ok",
            "discovery_complete": role == "legislative",
            "source_statuses": {"house": "ok", "senate": "ok"} if role == "legislative" else {},
            "source_counts": source_counts,
            "started_utc": result_started.isoformat().replace("+00:00", "Z"),
            "finished_utc": result_finished.isoformat().replace("+00:00", "Z"),
            "historical_backfill": historical,
            "filings": [],
            "transactions": [],
            "purchases": [],
            "pending_reviews": [],
            "errors": [],
        }
        for field in (
            "baseline_counts",
            "new_filing_counts",
            "cataloged_filing_counts",
            "transaction_counts",
            "purchase_counts",
            "pending_review_counts",
            "alerted_filing_counts",
        ):
            result[field] = copy.deepcopy(dimensions)
        run_receipt = {
            key: copy.deepcopy(result[key])
            for key in (
                "branch",
                "success",
                "overall_status",
                "started_utc",
                "finished_utc",
                "errors",
                "baseline_counts",
                "new_filing_counts",
                "cataloged_filing_counts",
                "transaction_counts",
                "purchase_counts",
                "pending_review_counts",
                "source_counts",
                "historical_backfill",
            )
        }
        run_receipt.update(
            run_key=f"{run_id}:1",
            event_name="workflow_dispatch",
            trigger_source="workflow_dispatch",
        )
        predecessor_run_receipt = {
            "run_key": f"predecessor-{role}:1",
            "branch": role,
            "success": True,
        }
        predecessor_runs = _jsonl([predecessor_run_receipt])
        predecessor_state = {
            "version": 1,
            "last_attempt_utc": "2026-09-05T11:00:00Z",
            "last_success_utc": "2026-09-05T11:00:00Z",
            "last_counts": source_counts,
            "seen_filings": {role: {"stable": "value"}},
        }
        state = copy.deepcopy(predecessor_state)
        state["last_attempt_utc"] = result["started_utc"]
        state["last_success_utc"] = result["finished_utc"]
        domain_members = {
            name: f"stable-{role}-{name}\n".encode()
            for name in validator.RECOVERY_PROTECTED_DOMAIN_MEMBERS[role]
        }
        predecessor_archive = tmp_path / f"recovery-{role}-predecessor.zip"
        _zip(
            predecessor_archive,
            domain_members
            | {
                "state.json": _json_bytes(predecessor_state),
                "runs.jsonl": predecessor_runs,
            },
        )
        state_archive = tmp_path / f"recovery-{role}-state.zip"
        _zip(
            state_archive,
            domain_members
            | {
                "state.json": _json_bytes(state),
                "runs.jsonl": predecessor_runs + _jsonl([run_receipt]),
            },
        )
        output_archive = tmp_path / f"recovery-{role}-output.zip"
        _zip(
            output_archive,
            {validator.RECOVERY_RESULT_MEMBERS[role]: _json_bytes(result)},
        )
        artifact_pin, artifact_metadata = _artifact_pin(
            state_archive,
            7100 + index,
            validator.RECOVERY_ARTIFACT_NAMES[role],
            run_id,
            recovery_pin["head_sha"],
        )
        predecessor_pin, predecessor_metadata = _artifact_pin(
            predecessor_archive,
            7050 + index,
            validator.RECOVERY_ARTIFACT_NAMES[role],
            33970010000 + index,
            "9" * 40,
            producer=False,
            created_at="2026-09-05T11:00:00Z",
        )
        output_name = (
            f"legislative-purchase-output-{run_id}-1"
            if role == "legislative"
            else f"executive-purchase-output-{run_id}"
        )
        output_pin, output_metadata = _artifact_pin(
            output_archive,
            7200 + index,
            output_name,
            run_id,
            recovery_pin["head_sha"],
        )
        recovery_pin.update(
            predecessor_artifact=predecessor_pin,
            artifact=artifact_pin,
            output_artifact=output_pin,
        )
        item.recovery_predecessor_archives.append(predecessor_archive)
        item.recovery_archives.append(state_archive)
        item.recovery_output_archives.append(output_archive)
        item.recovery_predecessor_artifact_metadatas.append(predecessor_metadata)
        item.recovery_artifact_metadatas.append(artifact_metadata)
        item.recovery_output_artifact_metadatas.append(output_metadata)

    frozen_successor_pins = []
    item.frozen_successor_archives = []
    item.frozen_successor_output_archives = []
    item.frozen_successor_artifact_metadatas = []
    item.frozen_successor_output_artifact_metadatas = []
    for index, (role, run_id, recovery_pin) in enumerate(
        zip(
            ("legislative", "executive"),
            validator.FROZEN_LEGACY_SUCCESSOR_RUN_IDS,
            recovery_pins,
        )
    ):
        successor_pin = _run_pin(
            run_id,
            validator.RECOVERY_PATHS[role],
            "success",
            head=validator.FROZEN_LEGACY_SUCCESSOR_REVISION,
            job_id=800 + index,
            job_name="track",
            start=f"2026-09-05T18:1{index}:00Z",
            finish=f"2026-09-05T18:1{index}:30Z",
            run_number=200 + index,
        ) | {"role": role}
        successor_pin["event"] = "schedule"
        with zipfile.ZipFile(item.recovery_archives[index]) as bundle:
            successor_members = {name: bundle.read(name) for name in bundle.namelist()}
        with zipfile.ZipFile(item.recovery_output_archives[index]) as bundle:
            successor_result = json.loads(bundle.read(validator.RECOVERY_RESULT_MEMBERS[role]))
        successor_result["started_utc"] = f"2026-09-05T18:1{index}:05Z"
        successor_result["finished_utc"] = f"2026-09-05T18:1{index}:20Z"
        state = json.loads(successor_members["state.json"])
        state["last_attempt_utc"] = successor_result["started_utc"]
        state["last_success_utc"] = successor_result["finished_utc"]
        successor_members["state.json"] = _json_bytes(state)
        successor_receipt = {
            key: copy.deepcopy(successor_result[key])
            for key in (
                "branch",
                "success",
                "overall_status",
                "started_utc",
                "finished_utc",
                "errors",
                "baseline_counts",
                "new_filing_counts",
                "cataloged_filing_counts",
                "transaction_counts",
                "purchase_counts",
                "pending_review_counts",
                "source_counts",
                "historical_backfill",
            )
        }
        successor_receipt.update(
            run_key=f"{run_id}:1",
            event_name="schedule",
            trigger_source="schedule",
        )
        successor_members["runs.jsonl"] += _jsonl([successor_receipt])
        successor_archive = tmp_path / f"frozen-successor-{role}-state.zip"
        _zip(successor_archive, successor_members)
        successor_output_archive = tmp_path / f"frozen-successor-{role}-output.zip"
        _zip(
            successor_output_archive,
            {validator.RECOVERY_RESULT_MEMBERS[role]: _json_bytes(successor_result)},
        )
        artifact_pin, artifact_metadata = _artifact_pin(
            successor_archive,
            7300 + index,
            validator.RECOVERY_ARTIFACT_NAMES[role],
            run_id,
            validator.FROZEN_LEGACY_SUCCESSOR_REVISION,
            created_at="2026-09-05T18:20:00Z",
        )
        output_name = (
            f"legislative-purchase-output-{run_id}-1"
            if role == "legislative"
            else f"executive-purchase-output-{run_id}"
        )
        output_pin, output_metadata = _artifact_pin(
            successor_output_archive,
            7400 + index,
            output_name,
            run_id,
            validator.FROZEN_LEGACY_SUCCESSOR_REVISION,
            created_at="2026-09-05T18:20:00Z",
        )
        predecessor_pin = copy.deepcopy(recovery_pin["artifact"])
        predecessor_pin.update(
            producer_run_id=recovery_pin["run_id"],
            producer_head_sha=recovery_pin["head_sha"],
        )
        successor_pin.update(
            predecessor_artifact=predecessor_pin,
            artifact=artifact_pin,
            output_artifact=output_pin,
        )
        frozen_successor_pins.append(successor_pin)
        item.frozen_successor_archives.append(successor_archive)
        item.frozen_successor_output_archives.append(successor_output_archive)
        item.frozen_successor_artifact_metadatas.append(artifact_metadata)
        item.frozen_successor_output_artifact_metadatas.append(output_metadata)

    phase4_artifact, item.phase4_artifact_metadata = _artifact_pin(
        item.phase4_archive, 7001, "phase4-readiness", validator.PHASE4_RUN_ID, validator.CERTIFIED_CONTROL_REVISION
    )
    failed_artifact, item.failed_artifact_metadata = _artifact_pin(
        item.failed_archive, 7002, "phase5-completion", validator.FAILED_PHASE5_RUN_ID, validator.CERTIFIED_CONTROL_REVISION
    )
    predecessor_pin, item.predecessor_artifact_metadata = _artifact_pin(
        item.predecessor_archive, 7003, "ai-analysis-state", 33970000000, "2" * 40, producer=False
    )
    state_pin, item.state_artifact_metadata = _artifact_pin(
        item.state_archive, 7004, "ai-analysis-state", validator.CONCURRENT_LEGACY_AI_RUN_ID, "3" * 40
    )
    output_pin, item.output_artifact_metadata = _artifact_pin(
        item.output_archive,
        7005,
        f"ai-analysis-output-{validator.CONCURRENT_LEGACY_AI_RUN_ID}-1",
        validator.CONCURRENT_LEGACY_AI_RUN_ID,
        "3" * 40,
    )
    phase4_pin.update(artifact=phase4_artifact, certificate_sha256=cert_sha)
    failed_pin.update(artifact=failed_artifact, status_members=status_members)
    legacy_pin.update(
        predecessor_artifact=predecessor_pin,
        state_artifact=state_pin,
        output_artifact=output_pin,
        expected_counts={
            "predecessor_analyses": 12,
            "successor_analyses": 13,
            "predecessor_runs": 60,
            "successor_runs": 61,
        },
        conflict={
            "runtime_snapshot_sha256": DASHBOARD_DIGEST,
            "analysis_id": ANALYSIS_ID,
            "trade_id": TRADE_ID,
            "document_content_hash": DOCUMENT_HASH,
        },
        merge_or_import_authorized=False,
    )
    dashboard_pin = _run_pin(
        33974683885,
        validator.DASHBOARD_WORKFLOW_PATH,
        "success",
        head="1" * 40,
        job_id=504,
        job_name="publish",
        start="2026-09-05T09:00:00Z",
        finish="2026-09-05T09:01:00Z",
        run_number=90,
    ) | {"role": "dashboard"}
    item.descriptor = {
        "schema_version": 1,
        "result": "phase5_failed_promotion_reconciliation_authorized",
        "repository_id": validator.REPOSITORY_ID,
        "repository": validator.REPOSITORY,
        "certified_control_revision": validator.CERTIFIED_CONTROL_REVISION,
        "certified_tree_sha": validator.CERTIFIED_TREE_SHA,
        "runtime_source_revision": validator.RUNTIME_SOURCE_REVISION,
        "immutable_image": IMAGE,
        "rebaseline_authorized": False,
        "legacy_artifact_merge_or_import_authorized": False,
        "expected_continuation_heads": {
            head["namespace"]: {
                "generation": head["generation"],
                "snapshot_sha256": head["snapshot_sha256"],
            }
            for head in current_status["heads"]
        },
        "phase4": phase4_pin,
        "failed_phase5": failed_pin,
        "concurrent_legacy_ai": legacy_pin,
        "recovery_runs": recovery_pins,
        "frozen_legacy_successors": frozen_successor_pins,
        "legacy_dashboard": dashboard_pin,
    }
    item.phase4_source = {
        "run": _run_api(phase4_pin),
        "jobs": _jobs_api(phase4_pin),
        "artifact": item.phase4_artifact_metadata,
        "archive": item.phase4_archive,
    }
    item.failed_source = {
        "run": _run_api(failed_pin),
        "jobs": _jobs_api(failed_pin),
        "artifact": item.failed_artifact_metadata,
        "archive": item.failed_archive,
    }
    item.legacy_source = {
        "run": _run_api(legacy_pin),
        "jobs": _jobs_api(legacy_pin),
        "predecessor_artifact": item.predecessor_artifact_metadata,
        "predecessor_archive": item.predecessor_archive,
        "state_artifact": item.state_artifact_metadata,
        "state_archive": item.state_archive,
        "output_artifact": item.output_artifact_metadata,
        "output_archive": item.output_archive,
    }
    item.recovery_run_metadatas = [_run_api(pin) for pin in recovery_pins]
    item.recovery_jobs_metadatas = [_jobs_api(pin) for pin in recovery_pins]
    item.frozen_successor_run_metadatas = [
        _run_api(pin) for pin in frozen_successor_pins
    ]
    item.frozen_successor_jobs_metadatas = [
        _jobs_api(pin) for pin in frozen_successor_pins
    ]
    item.legacy_run_inventories = [
        {"total_count": 1, "workflow_runs": [_run_api(pin)]}
        for pin in (
            frozen_successor_pins[0],
            frozen_successor_pins[1],
            legacy_pin,
            dashboard_pin,
        )
    ]
    item.legacy_artifact_inventories = [
        {"total_count": 1, "artifacts": [metadata]}
        for metadata in (
            item.frozen_successor_artifact_metadatas[0],
            item.frozen_successor_artifact_metadatas[1],
            item.state_artifact_metadata,
        )
    ]
    item.current_ai_analyses = [
        {
            "analysis_id": ANALYSIS_ID,
            "trade_id": TRADE_ID,
            "document_content_hash": DOCUMENT_HASH,
            "openai_response_id": "runtime-response",
            "classification": "watchlist",
            "score": 70,
        }
    ]
    item.replay_kwargs = {
        "descriptor": item.descriptor,
        "repository_root": tmp_path,
        "current_status": item.current_status,
        "current_ai_analyses": item.current_ai_analyses,
        "phase4_source": item.phase4_source,
        "failed_source": item.failed_source,
        "legacy_ai_source": item.legacy_source,
        "recovery_run_metadatas": item.recovery_run_metadatas,
        "recovery_jobs_metadatas": item.recovery_jobs_metadatas,
        "recovery_predecessor_artifact_metadatas": item.recovery_predecessor_artifact_metadatas,
        "recovery_predecessor_archives": item.recovery_predecessor_archives,
        "recovery_artifact_metadatas": item.recovery_artifact_metadatas,
        "recovery_archives": item.recovery_archives,
        "recovery_output_artifact_metadatas": item.recovery_output_artifact_metadatas,
        "recovery_output_archives": item.recovery_output_archives,
        "frozen_successor_run_metadatas": item.frozen_successor_run_metadatas,
        "frozen_successor_jobs_metadatas": item.frozen_successor_jobs_metadatas,
        "frozen_successor_artifact_metadatas": item.frozen_successor_artifact_metadatas,
        "frozen_successor_archives": item.frozen_successor_archives,
        "frozen_successor_output_artifact_metadatas": (
            item.frozen_successor_output_artifact_metadatas
        ),
        "frozen_successor_output_archives": item.frozen_successor_output_archives,
        "legacy_run_inventories": item.legacy_run_inventories,
        "legacy_artifact_inventories": item.legacy_artifact_inventories,
    }
    return item


def _replay(evidence: Evidence) -> dict[str, Any]:
    return validator.reconcile_failed_phase5(**evidence.replay_kwargs)


def _terminal(
    replay: dict[str, Any], evidence: Evidence
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    baseline = copy.deepcopy(replay["invalidated_smoke_prefix"]["final_heads"])
    old_by_job = {item["job"]: item for item in replay["invalidated_smoke_prefix"]["executions"]}
    baseline_status = {
        "heads": [
            {
                "namespace": name,
                "generation": baseline[name]["generation"],
                "snapshot_sha256": baseline[name]["snapshot_sha256"],
                "parent_sha256": _digest(f"terminal-parent-{name}"),
                "source_revision": validator.RUNTIME_SOURCE_REVISION,
                "provenance": {"authority": "runtime_v2"},
            }
            for name in validator.NAMESPACES
        ],
        "latest_runs": [
            {
                "run_id": old_by_job[name]["run_id"],
                "job_name": name,
                "status": "success",
                "runtime_mode": "production",
                "runtime_mode_verified": True,
                "trigger_source": "phase5_smoke",
                "side_effects_possible": False,
                "source_revision": validator.RUNTIME_SOURCE_REVISION,
                "snapshot_generation": old_by_job[name]["generation"],
                "snapshot_sha256": old_by_job[name]["snapshot_sha256"],
                "started_at": old_by_job[name]["started_at"],
                "finished_at": old_by_job[name]["finished_at"],
            }
            for name in validator.NAMESPACES
        ],
    }
    observations, _final = _observations(
        baseline_status,
        clock=datetime(2026, 9, 5, 14, 0, tzinfo=timezone.utc),
        run_prefix="fresh",
    )
    dashboard = observations[-1]["status"]["heads"][-1]["snapshot_sha256"]
    interval_start = datetime(2026, 9, 5, 13, 59, 50, tzinfo=timezone.utc)
    interval_finish = datetime(2026, 9, 5, 14, 2, 0, tzinfo=timezone.utc)
    runtime_inventories = []
    for observation in observations:
        role = observation["job"]
        latest = next(
            row for row in observation["status"]["latest_runs"] if row["job_name"] == role
        )
        app_start = datetime.fromisoformat(latest["started_at"].replace("Z", "+00:00"))
        app_finish = datetime.fromisoformat(latest["finished_at"].replace("Z", "+00:00"))
        job_name = f"polititrack-{role}"
        runtime_inventories.append(
            {
                "job": role,
                "capture_limit": 1000,
                "returned_count": 1,
                "executions": [
                    {
                        "metadata": {
                            "name": observation["cloud_run_execution"],
                            "creationTimestamp": (app_start - timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
                            "labels": {"run.googleapis.com/job": job_name},
                            "ownerReferences": [{"kind": "Job", "name": job_name}],
                        },
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [
                                        {
                                            "image": IMAGE,
                                            "env": [
                                                {
                                                    "name": "POLITITRACK_TRIGGER_SOURCE",
                                                    "value": "phase5_smoke",
                                                },
                                                {
                                                    "name": "SOURCE_REVISION",
                                                    "value": validator.RUNTIME_SOURCE_REVISION,
                                                },
                                                {
                                                    "name": "POLITITRACK_MODE",
                                                    "value": "production",
                                                },
                                            ],
                                        }
                                    ]
                                }
                            }
                        },
                        "status": {
                            "startTime": (app_start - timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
                            "completionTime": (app_finish + timedelta(seconds=5)).isoformat().replace("+00:00", "Z"),
                            "conditions": [{"type": "Completed", "status": "True"}],
                            "succeededCount": 1,
                        },
                    }
                ],
            }
        )
    workflow_states = [
        {
            "id": pin["workflow"]["id"],
            "name": pin["workflow"]["name"],
            "path": pin["workflow"]["path"],
            "state": "disabled_manually",
        }
        for pin in (
            evidence.descriptor["frozen_legacy_successors"][0],
            evidence.descriptor["frozen_legacy_successors"][1],
            evidence.descriptor["concurrent_legacy_ai"],
            evidence.descriptor["legacy_dashboard"],
        )
    ]
    terminal_inputs = {
        "terminal_legacy_run_inventories": copy.deepcopy(evidence.legacy_run_inventories),
        "terminal_legacy_workflow_states": workflow_states,
        "terminal_runtime_execution_inventories": runtime_inventories,
    }
    terminal_inputs["terminal_evidence_digests"] = {
        "legacy_run_inventories": [
            validator._canonical_sha256(value)
            for value in terminal_inputs["terminal_legacy_run_inventories"]
        ],
        "legacy_workflow_states": [
            validator._canonical_sha256(value)
            for value in terminal_inputs["terminal_legacy_workflow_states"]
        ],
        "runtime_execution_inventories": [
            validator._canonical_sha256(value)
            for value in terminal_inputs["terminal_runtime_execution_inventories"]
        ],
    }
    common = {
        "canonical_repository_verified": True,
        "canonical_main_verified": True,
        "project_boundary_verified": True,
        "image_digest_verified": True,
        "cloud_sql_private_only": True,
        "producer_schedulers_paused": True,
        "web_public_invoker_absent": True,
        "persistent_job_configuration_verified": True,
    }
    preflight = dict(common)
    preflight.update(
        {
            "phase4_certificate_verified": True,
            "failed_promotion_replay_verified": True,
            "concurrent_writer_incident_acknowledged": True,
            "old_smoke_prefix_invalidated": True,
            "legacy_ai_artifact_quarantined": True,
            "frozen_legacy_successors_verified": True,
            "legacy_runs_drained": True,
            "legacy_workflows_disabled": True,
            "continuation_heads_verified": True,
            "no_rebaseline_performed": True,
            "full_snapshot_chain_preserved": True,
            "temporary_private_web_invoker_removed": True,
            "no_concurrent_legacy_runs": True,
            "fresh_cycle_global_one_writer_verified": True,
        }
    )
    promotion = {
        "production_route": "runtime_v2",
        "legacy_workflows_disabled": True,
        "legacy_runs_drained": True,
        "runtime_jobs_production_mode": True,
        "web_public_invoker_present": True,
        "healthz_ok": False,
        "healthz_platform_diagnostic_only": True,
        "api_healthz_accepted": False,
        "readyz_ok": True,
        "dashboard_ok": True,
        "cloud_sql_private_only": True,
        "rollback_armed": True,
        "fresh_cycle_global_one_writer_verified": True,
        "enabled_producer_schedulers": list(validator.PRODUCER_SCHEDULERS),
        "disabled_legacy_workflows": list(validator.LEGACY_WORKFLOWS),
        "vault_scheduler_state": "PAUSED",
        "ready_snapshot_sha256": dashboard,
        "served_snapshot_sha256": dashboard,
        "web_url": "https://polititrack.example.run.app",
        "public_route": {
            "health_gate_paths": ["/readyz", "/"],
            "healthz_classification": "gfe_404_platform_diagnostic_only",
            "api_healthz_accepted": False,
            "readyz_accepted": True,
            "root_accepted": True,
            "dashboard_snapshot_verified": True,
        },
        "public_route_verification": {
            "schema_version": 1,
            "result": "phase5_retry_public_route_verified",
            "url": "https://polititrack.example.run.app",
            "expected_snapshot_sha256": dashboard,
            "healthz": {
                "http_status": 404,
                "classification": "gfe_404_platform_diagnostic_only",
                "server": "Google Frontend",
                "certification_gate": False,
            },
            "api_healthz": {"queried": False, "accepted_as_health": False},
            "readyz": {
                "http_status": 200,
                "content_type": "application/json; charset=utf-8",
                "json_verified": True,
                "expected_snapshot_verified": True,
                "certification_gate": True,
            },
            "dashboard": {
                "http_status": 200,
                "content_type": "text/html; charset=utf-8",
                "html_verified": True,
                "snapshot_header_verified": True,
                "certification_gate": True,
            },
        },
    }
    cleanup = {
        "temporary_execution_authority_removed": True,
        "temporary_logging_authority_removed": True,
        "temporary_service_account_user_removed": True,
        "cloud_sql_private_only": True,
        "legacy_workflows_disabled": True,
        "producer_schedulers_enabled": True,
        "web_public_invoker_present": True,
        "runtime_jobs_production_mode": True,
        "no_rebaseline_performed": True,
        "full_snapshot_chain_preserved": True,
        "temporary_private_web_invoker_removed": True,
    }
    replay_sha256 = validator._canonical_sha256(replay)
    manifest = {
        "schema_version": 1,
        "phase": "phase5_reconciliation_completion",
        "control_revision": "5" * 40,
        "retry": {
            "kind": "failed_phase5_retry_with_fresh_smoke_cycle",
            "failed_phase5_run_id": validator.FAILED_PHASE5_RUN_ID,
            "failed_prefix_replay_result": "phase5_failed_promotion_reconciled",
            "invalidated_smoke_prefix_certification_eligible": False,
            "concurrent_legacy_ai_successor_quarantined": True,
            "merge_or_import_authorized": False,
            "failed_prefix_replay_sha256": replay_sha256,
        },
        "preflight": preflight,
        "executions": observations,
        "promotion": promotion,
        "cleanup": cleanup,
        "one_writer_evidence": {
            "fresh_cycle_interval": {
                "started_at": interval_start.isoformat().replace("+00:00", "Z"),
                "finished_at": interval_finish.isoformat().replace("+00:00", "Z"),
            },
            "legacy_run_inventories_sha256": {
                role: digest
                for role, digest in zip(
                    validator.LEGACY_HIGH_WATER_ROLES,
                    terminal_inputs["terminal_evidence_digests"]["legacy_run_inventories"],
                )
            },
            "legacy_workflow_states_sha256": {
                role: digest
                for role, digest in zip(
                    validator.LEGACY_HIGH_WATER_ROLES,
                    terminal_inputs["terminal_evidence_digests"]["legacy_workflow_states"],
                )
            },
            "runtime_execution_inventories_sha256": {
                role: digest
                for role, digest in zip(
                    validator.LEGACY_HIGH_WATER_ROLES,
                    terminal_inputs["terminal_evidence_digests"]["runtime_execution_inventories"],
                )
            },
            "overlapping_legacy_run_count": 0,
            "unexpected_runtime_execution_count": 0,
            "expected_runtime_execution_count": 4,
        },
        "phase6_started": False,
    }
    return baseline_status, manifest, terminal_inputs | {"replay_sha256": replay_sha256}


def test_replay_is_forensic_and_invalidates_old_four(evidence: Evidence) -> None:
    receipt = _replay(evidence)
    assert receipt["result"] == "phase5_failed_promotion_reconciled"
    assert receipt["certification_eligible"] is False
    assert receipt["invalidated_smoke_prefix"]["unique_successful_receipts"] == 4
    assert receipt["invalidated_smoke_prefix"]["certification_eligible"] is False
    assert receipt["continuation_heads"] == evidence.descriptor["expected_continuation_heads"]
    assert receipt["concurrent_legacy_ai"]["global_one_writer_interval_violated"] is True
    assert receipt["concurrent_legacy_ai"]["disposition"] == "quarantined_separate_legacy_artifact"
    assert receipt["concurrent_legacy_ai"]["merge_or_import_authorized"] is False
    assert receipt["reconciliation"]["fresh_clean_smoke_cycle_required"] is True
    assert receipt["reconciliation"]["rebaseline_performed"] is False
    assert receipt["reconciliation"]["full_snapshot_chain_preserved"] is True
    assert receipt["reconciliation"]["frozen_legacy_successors_verified"] is True
    assert [item["run_id"] for item in receipt["recovery_runs"]] == list(
        validator.RECOVERY_RUN_IDS
    )
    assert [item["run_id"] for item in receipt["frozen_legacy_successors"]] == list(
        validator.FROZEN_LEGACY_SUCCESSOR_RUN_IDS
    )
    assert all(
        item["incident_only_revision_allowlist_verified"]
        and item["protected_domain_data_unchanged"]
        and item["run_receipt_appended_count"] == 1
        for item in receipt["frozen_legacy_successors"]
    )
    assert [item["run_id"] for item in receipt["legacy_high_water"]["runs"][:2]] == list(
        validator.FROZEN_LEGACY_SUCCESSOR_RUN_IDS
    )


def test_completion_certifies_only_a_fresh_clean_cycle(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    receipt = validator.complete_phase5(
        descriptor=evidence.descriptor,
        replay=replay,
        terminal_baseline=baseline,
        terminal_manifest=manifest,
        control_revision="5" * 40,
        **terminal_inputs,
    )
    assert receipt["result"] == "phase5_complete"
    assert receipt["unique_successful_smoke_receipts"] == 4
    assert [item["run_id"] for item in receipt["executions"]] == [
        f"fresh-runtime-{name}" for name in validator.NAMESPACES
    ]
    assert receipt["reconciliation"]["invalidated_smoke_prefix"]["unique_successful_receipts"] == 4
    assert receipt["reconciliation"]["additional_runtime_producer_execution_performed"] is True
    assert receipt["reconciliation"]["additional_runtime_producer_execution_count"] == 4
    assert receipt["reconciliation"]["rebaseline_performed"] is False
    assert receipt["reconciliation"]["full_snapshot_chain_preserved"] is True
    assert [
        item["run_id"] for item in receipt["reconciliation"]["frozen_legacy_successors"]
    ] == list(validator.FROZEN_LEGACY_SUCCESSOR_RUN_IDS)
    assert receipt["production_authority_transferred"] is True
    assert receipt["phase6_started"] is False


@pytest.mark.parametrize(
    ("member", "message"),
    [
        ("../escape", "unsafe member path"),
        ("/absolute", "unsafe member name"),
        ("C:/absolute", "unsafe member name"),
        ("a//b", "unsafe member path"),
    ],
)
def test_archive_rejects_unsafe_paths(tmp_path: Path, member: str, message: str) -> None:
    path = tmp_path / "unsafe.zip"
    _zip(path, {member: "bad"})
    with pytest.raises(validator.PromotionValidationError, match=message):
        validator._artifact_members(path)


def test_archive_rejects_duplicate_and_case_collision(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as bundle:
        bundle.writestr("same.json", "1")
        bundle.writestr("same.json", "2")
    with pytest.raises(validator.PromotionValidationError, match="duplicate member"):
        validator._artifact_members(duplicate)
    collision = tmp_path / "collision.zip"
    _zip(collision, {"State.json": "1", "state.JSON": "2"})
    with pytest.raises(validator.PromotionValidationError, match="case-colliding"):
        validator._artifact_members(collision)


def test_archive_rejects_backslash_member(tmp_path: Path) -> None:
    path = tmp_path / "backslash.zip"
    _zip(path, {"dir/file": "bad"})
    data = bytearray(path.read_bytes())
    needle = b"dir/file"
    assert data.count(needle) == 2
    path.write_bytes(bytes(data).replace(needle, b"dir\\file"))
    with pytest.raises(validator.PromotionValidationError, match="unsafe member name"):
        validator._artifact_members(path)


def test_archive_rejects_symlink(tmp_path: Path) -> None:
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat_mode := 0o120777) << 16
    assert stat_mode & 0o170000 == 0o120000
    path = tmp_path / "link.zip"
    _zip(path, {}, infos=[(info, b"target")])
    with pytest.raises(validator.PromotionValidationError, match="symbolic link"):
        validator._artifact_members(path)


def _set_encrypted_flag(path: Path) -> None:
    data = bytearray(path.read_bytes())
    local = data.index(b"PK\x03\x04")
    flags = struct.unpack_from("<H", data, local + 6)[0]
    struct.pack_into("<H", data, local + 6, flags | 1)
    central = data.index(b"PK\x01\x02")
    flags = struct.unpack_from("<H", data, central + 8)[0]
    struct.pack_into("<H", data, central + 8, flags | 1)
    path.write_bytes(data)


def test_archive_rejects_encrypted_member(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.zip"
    _zip(path, {"state.json": "{}"})
    _set_encrypted_flag(path)
    with pytest.raises(validator.PromotionValidationError, match="encrypted member"):
        validator._artifact_members(path)


def test_archive_rejects_oversized_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "large.zip"
    _zip(path, {"large": "12345"})
    monkeypatch.setattr(validator, "MAX_MEMBER_BYTES", 4)
    with pytest.raises(validator.PromotionValidationError, match="size limit"):
        validator._artifact_members(path)


def test_artifact_digest_and_size_are_both_pinned(evidence: Evidence) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["failed_source"] = dict(bad["failed_source"])
    bad["failed_source"]["artifact"] = copy.deepcopy(bad["failed_source"]["artifact"])
    bad["failed_source"]["artifact"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(validator.PromotionValidationError, match="API digest mismatch"):
        validator.reconcile_failed_phase5(**bad)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    bad["descriptor"]["failed_phase5"]["artifact"]["size_in_bytes"] += 1
    with pytest.raises(validator.PromotionValidationError, match="downloaded size mismatch"):
        validator.reconcile_failed_phase5(**bad)


def test_exact_run_and_job_metadata_is_required(evidence: Evidence) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["failed_source"] = dict(bad["failed_source"])
    bad["failed_source"]["run"] = copy.deepcopy(bad["failed_source"]["run"])
    bad["failed_source"]["run"]["run_attempt"] = 2
    with pytest.raises(validator.PromotionValidationError, match="run_attempt mismatch"):
        validator.reconcile_failed_phase5(**bad)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["failed_source"] = dict(bad["failed_source"])
    bad["failed_source"]["jobs"] = copy.deepcopy(bad["failed_source"]["jobs"])
    bad["failed_source"]["jobs"]["jobs"].append(copy.deepcopy(bad["failed_source"]["jobs"]["jobs"][0]))
    bad["failed_source"]["jobs"]["total_count"] = 2
    with pytest.raises(validator.PromotionValidationError, match="ambiguous"):
        validator.reconcile_failed_phase5(**bad)


def test_phase4_certificate_checksum_is_required(evidence: Evidence, tmp_path: Path) -> None:
    bad_archive = tmp_path / "bad-phase4.zip"
    with zipfile.ZipFile(evidence.phase4_archive) as bundle:
        members = {info.filename: bundle.read(info) for info in bundle.infolist()}
    members["phase4-ready.sha256"] = b"0" * 64 + b"  phase4-ready.json\n"
    _zip(bad_archive, members)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["phase4_source"] = dict(bad["phase4_source"])
    bad["phase4_source"]["archive"] = bad_archive
    pin, metadata = _artifact_pin(
        bad_archive, 7001, "phase4-readiness", validator.PHASE4_RUN_ID, validator.CERTIFIED_CONTROL_REVISION
    )
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    pin["certificate_sha256"] = bad["descriptor"]["phase4"]["certificate_sha256"]
    bad["descriptor"]["phase4"]["artifact"] = pin
    bad["phase4_source"]["artifact"] = metadata
    with pytest.raises(validator.PromotionValidationError, match="certificate checksum mismatch"):
        validator.reconcile_failed_phase5(**bad)


def test_observation_must_equal_its_status_file(evidence: Evidence, tmp_path: Path) -> None:
    bad_archive = tmp_path / "status-mismatch.zip"
    with zipfile.ZipFile(evidence.failed_archive) as bundle:
        members = {info.filename: bundle.read(info) for info in bundle.infolist()}
    status = json.loads(members["smoke-sequence-1-legislative-status.json"])
    status["label"] = "different"
    members["smoke-sequence-1-legislative-status.json"] = _json_bytes(status)
    _zip(bad_archive, members)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["failed_source"] = dict(bad["failed_source"])
    bad["failed_source"]["archive"] = bad_archive
    pin, metadata = _artifact_pin(
        bad_archive,
        7002,
        "phase5-completion",
        validator.FAILED_PHASE5_RUN_ID,
        validator.CERTIFIED_CONTROL_REVISION,
    )
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    pin["status_members"] = bad["descriptor"]["failed_phase5"]["status_members"]
    bad["descriptor"]["failed_phase5"]["artifact"] = pin
    bad["failed_source"]["artifact"] = metadata
    with pytest.raises(validator.PromotionValidationError, match="status file mismatch"):
        validator.reconcile_failed_phase5(**bad)


def test_current_heads_and_latest_receipts_must_match_prefix(evidence: Evidence) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["current_status"] = copy.deepcopy(bad["current_status"])
    bad["current_status"]["heads"][0]["snapshot_sha256"] = "0" * 64
    with pytest.raises(validator.PromotionValidationError, match="current Runtime state legislative snapshot_sha256"):
        validator.reconcile_failed_phase5(**bad)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["current_status"] = copy.deepcopy(bad["current_status"])
    bad["current_status"]["latest_runs"][0]["run_id"] = "wrong"
    with pytest.raises(validator.PromotionValidationError, match="current Runtime legislative run_id"):
        validator.reconcile_failed_phase5(**bad)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda e: e["descriptor"]["concurrent_legacy_ai"].update(merge_or_import_authorized=True), "merge/import authorization"),
        (lambda e: e["current_ai_analyses"].clear(), "deterministic IDs exactly once"),
        (lambda e: e["current_ai_analyses"][0].update(openai_response_id="legacy-response"), "does not differ in openai_response_id"),
    ],
)
def test_legacy_ai_duplicate_must_be_quarantined_and_conflicting(evidence: Evidence, mutate, message: str) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    mutate(bad)
    with pytest.raises(validator.PromotionValidationError, match=message):
        validator.reconcile_failed_phase5(**bad)


def test_legacy_ai_prefix_must_be_byte_preserved(evidence: Evidence, tmp_path: Path) -> None:
    bad_archive = tmp_path / "bad-prefix.zip"
    with zipfile.ZipFile(evidence.state_archive) as bundle:
        members = {info.filename: bundle.read(info) for info in bundle.infolist()}
    members["analyses.jsonl"] = b'{"rewritten":true}\n' + members["analyses.jsonl"]
    _zip(bad_archive, members)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["legacy_ai_source"] = dict(bad["legacy_ai_source"])
    bad["legacy_ai_source"]["state_archive"] = bad_archive
    pin, metadata = _artifact_pin(
        bad_archive,
        7004,
        "ai-analysis-state",
        validator.CONCURRENT_LEGACY_AI_RUN_ID,
        "3" * 40,
    )
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    bad["descriptor"]["concurrent_legacy_ai"]["state_artifact"] = pin
    bad["legacy_ai_source"]["state_artifact"] = metadata
    with pytest.raises(validator.PromotionValidationError, match="exact predecessor byte prefix"):
        validator.reconcile_failed_phase5(**bad)


def test_legacy_result_requires_one_publishable_analysis_and_zero_alerts(evidence: Evidence, tmp_path: Path) -> None:
    for field, value, message in (
        ("completed_count", 0, "completed_count mismatch"),
        ("alerted_count", 1, "alerted_count mismatch"),
        ("state_publishable", False, "state_publishable mismatch"),
    ):
        with zipfile.ZipFile(evidence.output_archive) as bundle:
            result = json.loads(bundle.read("ai-analysis-result.json"))
        result[field] = value
        archive = tmp_path / f"bad-{field}.zip"
        _zip(archive, {"ai-analysis-result.json": _json_bytes(result)})
        bad = copy.deepcopy(evidence.replay_kwargs)
        bad["legacy_ai_source"] = dict(bad["legacy_ai_source"])
        bad["legacy_ai_source"]["output_archive"] = archive
        pin, metadata = _artifact_pin(
            archive,
            7005,
            f"ai-analysis-output-{validator.CONCURRENT_LEGACY_AI_RUN_ID}-1",
            validator.CONCURRENT_LEGACY_AI_RUN_ID,
            "3" * 40,
        )
        bad["descriptor"] = copy.deepcopy(bad["descriptor"])
        bad["descriptor"]["concurrent_legacy_ai"]["output_artifact"] = pin
        bad["legacy_ai_source"]["output_artifact"] = metadata
        with pytest.raises(validator.PromotionValidationError, match=message):
            validator.reconcile_failed_phase5(**bad)


def test_recovery_metadata_and_order_are_exact(evidence: Evidence) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["recovery_run_metadatas"] = list(reversed(bad["recovery_run_metadatas"]))
    with pytest.raises(validator.PromotionValidationError, match="incident run id pin|API id mismatch"):
        validator.reconcile_failed_phase5(**bad)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    bad["descriptor"]["recovery_runs"][0]["head_sha"] = "6" * 40
    with pytest.raises(validator.PromotionValidationError, match="head_sha mismatch"):
        validator.reconcile_failed_phase5(**bad)


def test_recovery_artifacts_must_prove_exact_zero_change(
    evidence: Evidence, tmp_path: Path
) -> None:
    with zipfile.ZipFile(evidence.recovery_output_archives[0]) as bundle:
        result = json.loads(bundle.read("legislative-result.json"))
    result["new_filing_counts"]["house"] = 1
    changed = tmp_path / "changed-recovery-output.zip"
    _zip(changed, {"legislative-result.json": _json_bytes(result)})
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    pin, metadata = _artifact_pin(
        changed,
        7200,
        f"legislative-purchase-output-{validator.RECOVERY_RUN_IDS[0]}-1",
        validator.RECOVERY_RUN_IDS[0],
        bad["descriptor"]["recovery_runs"][0]["head_sha"],
    )
    bad["descriptor"]["recovery_runs"][0]["output_artifact"] = pin
    bad["recovery_output_artifact_metadatas"] = list(
        bad["recovery_output_artifact_metadatas"]
    )
    bad["recovery_output_artifact_metadatas"][0] = metadata
    bad["recovery_output_archives"] = list(bad["recovery_output_archives"])
    bad["recovery_output_archives"][0] = changed
    with pytest.raises(validator.PromotionValidationError, match="new_filing_counts mismatch"):
        validator.reconcile_failed_phase5(**bad)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("domain", "protected domain member filings.jsonl changed"),
        ("runs", "runs are not an exact predecessor byte prefix"),
        ("state", "recovery state non-marker content mismatch"),
        ("state_null", "recovery state non-marker content mismatch"),
    ],
)
def test_recovery_requires_predecessor_bound_protected_continuity(
    evidence: Evidence, tmp_path: Path, mutation: str, message: str
) -> None:
    with zipfile.ZipFile(evidence.recovery_archives[0]) as bundle:
        members = {name: bundle.read(name) for name in bundle.namelist()}
    if mutation == "domain":
        members["filings.jsonl"] += b'{"unexpected":"business-change"}\n'
    elif mutation == "runs":
        records = members["runs.jsonl"].splitlines(keepends=True)
        records[0] = b'{"run_key":"rewritten-predecessor"}\n'
        members["runs.jsonl"] = b"".join(records)
    elif mutation == "state":
        state = json.loads(members["state.json"])
        state["seen_filings"]["legislative"]["unexpected"] = "mutation"
        members["state.json"] = _json_bytes(state)
    else:
        state = json.loads(members["state.json"])
        state["unexpected_null"] = None
        members["state.json"] = _json_bytes(state)

    changed = tmp_path / f"changed-recovery-state-{mutation}.zip"
    _zip(changed, members)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    pin, metadata = _artifact_pin(
        changed,
        7100,
        validator.RECOVERY_ARTIFACT_NAMES["legislative"],
        validator.RECOVERY_RUN_IDS[0],
        bad["descriptor"]["recovery_runs"][0]["head_sha"],
    )
    bad["descriptor"]["recovery_runs"][0]["artifact"] = pin
    bad["recovery_artifact_metadatas"] = list(bad["recovery_artifact_metadatas"])
    bad["recovery_artifact_metadatas"][0] = metadata
    bad["recovery_archives"] = list(bad["recovery_archives"])
    bad["recovery_archives"][0] = changed
    with pytest.raises(validator.PromotionValidationError, match=message):
        validator.reconcile_failed_phase5(**bad)


def test_recovery_predecessor_artifact_is_exactly_pinned(evidence: Evidence) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["recovery_predecessor_artifact_metadatas"] = list(
        bad["recovery_predecessor_artifact_metadatas"]
    )
    bad["recovery_predecessor_artifact_metadatas"][1] = copy.deepcopy(
        bad["recovery_predecessor_artifact_metadatas"][1]
    )
    bad["recovery_predecessor_artifact_metadatas"][1]["workflow_run"]["id"] += 1
    with pytest.raises(validator.PromotionValidationError, match="workflow_run id mismatch"):
        validator.reconcile_failed_phase5(**bad)


def test_frozen_successor_run_and_artifact_metadata_are_exact(evidence: Evidence) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["frozen_successor_run_metadatas"] = list(bad["frozen_successor_run_metadatas"])
    bad["frozen_successor_run_metadatas"][0] = copy.deepcopy(
        bad["frozen_successor_run_metadatas"][0]
    )
    bad["frozen_successor_run_metadatas"][0]["id"] += 1
    with pytest.raises(validator.PromotionValidationError, match="API id mismatch"):
        validator.reconcile_failed_phase5(**bad)

    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["frozen_successor_artifact_metadatas"] = list(
        bad["frozen_successor_artifact_metadatas"]
    )
    bad["frozen_successor_artifact_metadatas"][1] = copy.deepcopy(
        bad["frozen_successor_artifact_metadatas"][1]
    )
    bad["frozen_successor_artifact_metadatas"][1]["id"] += 1
    with pytest.raises(validator.PromotionValidationError, match="API id mismatch"):
        validator.reconcile_failed_phase5(**bad)

    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    bad["descriptor"]["frozen_legacy_successors"][0]["predecessor_artifact"]["id"] += 1
    with pytest.raises(validator.PromotionValidationError, match="successor predecessor id mismatch"):
        validator.reconcile_failed_phase5(**bad)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("domain", "protected domain member filings.jsonl changed"),
        ("state", "recovery state non-marker content mismatch"),
        ("receipt", "protected run receipt run_key mismatch"),
    ],
)
def test_frozen_successor_requires_exact_zero_change_lineage(
    evidence: Evidence, tmp_path: Path, mutation: str, message: str
) -> None:
    with zipfile.ZipFile(evidence.frozen_successor_archives[0]) as bundle:
        members = {name: bundle.read(name) for name in bundle.namelist()}
    if mutation == "domain":
        members["filings.jsonl"] += b'{"unexpected":"successor-business-change"}\n'
    elif mutation == "state":
        state = json.loads(members["state.json"])
        state["unexpected_null"] = None
        members["state.json"] = _json_bytes(state)
    else:
        rows = members["runs.jsonl"].splitlines(keepends=True)
        latest = json.loads(rows[-1])
        latest["run_key"] = "wrong-successor:1"
        rows[-1] = _json_bytes(latest)
        members["runs.jsonl"] = b"".join(rows)

    changed = tmp_path / f"changed-frozen-successor-{mutation}.zip"
    _zip(changed, members)
    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["descriptor"] = copy.deepcopy(bad["descriptor"])
    pin, metadata = _artifact_pin(
        changed,
        7300,
        validator.RECOVERY_ARTIFACT_NAMES["legislative"],
        validator.FROZEN_LEGACY_SUCCESSOR_RUN_IDS[0],
        validator.FROZEN_LEGACY_SUCCESSOR_REVISION,
        created_at="2026-09-05T18:20:00Z",
    )
    bad["descriptor"]["frozen_legacy_successors"][0]["artifact"] = pin
    bad["frozen_successor_artifact_metadatas"] = list(
        bad["frozen_successor_artifact_metadatas"]
    )
    bad["frozen_successor_artifact_metadatas"][0] = metadata
    bad["frozen_successor_archives"] = list(bad["frozen_successor_archives"])
    bad["frozen_successor_archives"][0] = changed
    with pytest.raises(validator.PromotionValidationError, match=message):
        validator.reconcile_failed_phase5(**bad)


def test_frozen_successor_revision_has_only_incident_control_paths() -> None:
    validator._verify_frozen_legacy_successor_revision(MODULE_PATH.parents[2])
    assert validator.FROZEN_LEGACY_SUCCESSOR_DIFF == {
        ".github/workflows/phase5_failed_promotion_retry.yml": "A",
        ".github/workflows/runtime_v2_tests.yml": "M",
        "deploy/runtime-v2/phase5-retry-evidence-33979778020.json": "A",
        "deploy/runtime-v2/phase5_failed_promotion_retry_control.sh": "A",
        "deploy/runtime-v2/reconcile_phase5_failed_promotion.py": "A",
        "docs/DECISIONS.md": "M",
        "tests/test_phase5_failed_promotion_retry.py": "A",
        "tests/test_reconcile_phase5_failed_promotion.py": "A",
    }


def test_replay_rejects_later_legacy_run_and_newer_protected_artifact(
    evidence: Evidence,
) -> None:
    bad = copy.deepcopy(evidence.replay_kwargs)
    later = copy.deepcopy(bad["legacy_run_inventories"][0]["workflow_runs"][0])
    later["id"] += 999
    later["created_at"] = "2026-09-05T18:00:00Z"
    later["run_started_at"] = "2026-09-05T18:00:01Z"
    later["updated_at"] = "2026-09-05T18:01:00Z"
    bad["legacy_run_inventories"][0]["workflow_runs"].insert(0, later)
    bad["legacy_run_inventories"][0]["total_count"] = 2
    with pytest.raises(validator.PromotionValidationError, match="high-water run id mismatch"):
        validator.reconcile_failed_phase5(**bad)

    bad = copy.deepcopy(evidence.replay_kwargs)
    newer = copy.deepcopy(bad["legacy_artifact_inventories"][0]["artifacts"][0])
    newer["id"] += 999
    newer["created_at"] = "2026-09-05T19:00:00Z"
    bad["legacy_artifact_inventories"][0]["artifacts"].append(newer)
    bad["legacy_artifact_inventories"][0]["total_count"] = 2
    with pytest.raises(
        validator.PromotionValidationError, match="protected artifact high-water id mismatch"
    ):
        validator.reconcile_failed_phase5(**bad)

    bad = copy.deepcopy(evidence.replay_kwargs)
    bad["legacy_artifact_inventories"][1]["total_count"] = 2
    with pytest.raises(validator.PromotionValidationError, match="artifact inventory is incomplete"):
        validator.reconcile_failed_phase5(**bad)


def test_phase4_certificate_requires_two_unique_ordered_cycles(evidence: Evidence) -> None:
    certificate = _certificate(_base_status())
    certificate["executions"][4]["run_id"] = certificate["executions"][0]["run_id"]
    with pytest.raises(validator.PromotionValidationError, match="eight unique Runtime receipts"):
        validator._validate_phase4_receipts(certificate)
    certificate = _certificate(_base_status())
    certificate["executions"][4]["generation"] = certificate["executions"][0]["generation"]
    with pytest.raises(validator.PromotionValidationError, match="second-cycle generation mismatch"):
        validator._validate_phase4_receipts(certificate)


def test_git_binding_requires_same_tree_descendant(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "file.txt").write_text("same\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=tmp_path, check=True)
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=tmp_path, text=True).strip()
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "same tree"], cwd=tmp_path, check=True)
    descendant = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    validator._verify_tree_equal_descendant(tmp_path, base, descendant, tree)
    (tmp_path / "file.txt").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "commit", "-qam", "changed tree"], cwd=tmp_path, check=True)
    changed = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    with pytest.raises(validator.PromotionValidationError, match="tree.*mismatch"):
        validator._verify_tree_equal_descendant(tmp_path, base, changed, tree)


def test_completion_rejects_rebaseline_or_missing_route_guard(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    manifest["preflight"]["no_rebaseline_performed"] = False
    with pytest.raises(validator.PromotionValidationError, match="completion preflight"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    manifest["promotion"]["public_route"]["health_gate_paths"] = ["/healthz"]
    with pytest.raises(validator.PromotionValidationError, match="health gate paths"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


@pytest.mark.parametrize(
    ("status", "server", "classification"),
    [
        (404, "Google Frontend", "gfe_404_platform_diagnostic_only"),
        (200, "Google Frontend", "supplemental_application_diagnostic_only"),
        (503, "Google Frontend", "http_503_platform_diagnostic_only"),
        (0, "", "unavailable_platform_diagnostic_only"),
    ],
)
def test_completion_treats_all_healthz_outcomes_as_bound_non_gating_diagnostics(
    evidence: Evidence, status: int, server: str, classification: str
) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    healthz = manifest["promotion"]["public_route_verification"]["healthz"]
    healthz.update(http_status=status, server=server, classification=classification)
    manifest["promotion"]["public_route"]["healthz_classification"] = classification
    receipt = validator.complete_phase5(
        descriptor=evidence.descriptor,
        replay=replay,
        terminal_baseline=baseline,
        terminal_manifest=manifest,
        control_revision="5" * 40,
        **terminal_inputs,
    )
    assert receipt["result"] == "phase5_complete"


def test_completion_rejects_unbound_healthz_diagnostic_classification(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    manifest["promotion"]["public_route_verification"]["healthz"]["classification"] = (
        "supplemental_application_diagnostic_only"
    )
    with pytest.raises(validator.PromotionValidationError, match="captured classification mismatch"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def test_completion_rejects_baseline_drift_and_old_receipt_reuse(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    baseline["heads"][0]["generation"] += 1
    with pytest.raises(validator.PromotionValidationError, match="terminal baseline legislative generation"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


@pytest.mark.parametrize(
    "missing",
    ["phase4_certificate", "failed_phase5", "recovery_runs", "frozen_legacy_successors"],
)
def test_completion_requires_full_semantic_replay(
    evidence: Evidence, missing: str
) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    del replay[missing]
    with pytest.raises(validator.PromotionValidationError, match="replay"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def test_completion_rejects_tampered_invalidated_prefix(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    replay["invalidated_smoke_prefix"]["certification_eligible"] = True
    replay["invalidated_smoke_prefix"]["unique_successful_receipts"] = 999
    with pytest.raises(validator.PromotionValidationError, match="certification_eligible mismatch"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def _rehash_terminal_input(
    manifest: dict[str, Any], terminal_inputs: dict[str, Any], field: str, index: int
) -> None:
    digest = validator._canonical_sha256(terminal_inputs[field][index])
    terminal_inputs["terminal_evidence_digests"][field.removeprefix("terminal_")][index] = digest
    manifest["one_writer_evidence"][f"{field.removeprefix('terminal_')}_sha256"][
        validator.LEGACY_HIGH_WATER_ROLES[index]
    ] = digest


def test_completion_derives_global_one_writer_from_raw_inventories(
    evidence: Evidence,
) -> None:
    replay = _replay(evidence)
    baseline, manifest, original_inputs = _terminal(replay, evidence)

    terminal_inputs = copy.deepcopy(original_inputs)
    extra = copy.deepcopy(terminal_inputs["terminal_runtime_execution_inventories"][0]["executions"][0])
    extra["metadata"]["name"] += "-unexpected"
    terminal_inputs["terminal_runtime_execution_inventories"][0]["executions"].append(extra)
    terminal_inputs["terminal_runtime_execution_inventories"][0]["returned_count"] = 2
    _rehash_terminal_input(
        manifest, terminal_inputs, "terminal_runtime_execution_inventories", 0
    )
    with pytest.raises(validator.PromotionValidationError, match="exactly one execution overlapping"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )

    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    overlapping = copy.deepcopy(
        terminal_inputs["terminal_legacy_run_inventories"][0]["workflow_runs"][0]
    )
    overlapping["id"] += 77
    overlapping["created_at"] = "2026-09-05T08:00:00Z"
    overlapping["run_started_at"] = "2026-09-05T14:00:00Z"
    overlapping["updated_at"] = "2026-09-05T14:01:00Z"
    terminal_inputs["terminal_legacy_run_inventories"][0]["workflow_runs"].append(overlapping)
    terminal_inputs["terminal_legacy_run_inventories"][0]["total_count"] = 2
    _rehash_terminal_input(manifest, terminal_inputs, "terminal_legacy_run_inventories", 0)
    with pytest.raises(validator.PromotionValidationError, match="overlaps the fresh cycle"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def test_completion_rejects_enabled_legacy_workflow_or_missing_execution(
    evidence: Evidence,
) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    terminal_inputs["terminal_legacy_workflow_states"][2]["state"] = "active"
    _rehash_terminal_input(manifest, terminal_inputs, "terminal_legacy_workflow_states", 2)
    with pytest.raises(validator.PromotionValidationError, match="workflow state state mismatch"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )

    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    terminal_inputs["terminal_runtime_execution_inventories"][3]["executions"] = []
    _rehash_terminal_input(
        manifest, terminal_inputs, "terminal_runtime_execution_inventories", 3
    )
    with pytest.raises(validator.PromotionValidationError, match="execution returned count mismatch"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def test_completion_allows_unrelated_execution_outside_fresh_interval(
    evidence: Evidence,
) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    outside = copy.deepcopy(
        terminal_inputs["terminal_runtime_execution_inventories"][0]["executions"][0]
    )
    outside["metadata"]["name"] += "-later"
    outside["metadata"]["creationTimestamp"] = "2026-09-05T15:00:00Z"
    outside["status"]["startTime"] = "2026-09-05T15:00:00Z"
    outside["status"]["completionTime"] = "2026-09-05T15:01:00Z"
    terminal_inputs["terminal_runtime_execution_inventories"][0]["executions"].append(outside)
    terminal_inputs["terminal_runtime_execution_inventories"][0]["returned_count"] = 2
    _rehash_terminal_input(
        manifest, terminal_inputs, "terminal_runtime_execution_inventories", 0
    )
    receipt = validator.complete_phase5(
        descriptor=evidence.descriptor,
        replay=replay,
        terminal_baseline=baseline,
        terminal_manifest=manifest,
        control_revision="5" * 40,
        **terminal_inputs,
    )
    assert receipt["result"] == "phase5_complete"


def test_completion_rejects_truncated_authoritative_inventories(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    terminal_inputs["terminal_legacy_run_inventories"][3]["total_count"] = 2
    _rehash_terminal_input(manifest, terminal_inputs, "terminal_legacy_run_inventories", 3)
    with pytest.raises(validator.PromotionValidationError, match="inventory is incomplete"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )

    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    # A claimed second result that is absent from the supplied array could be
    # the omitted overlapping writer; count equality makes that fail closed.
    terminal_inputs["terminal_runtime_execution_inventories"][0]["returned_count"] = 2
    _rehash_terminal_input(
        manifest, terminal_inputs, "terminal_runtime_execution_inventories", 0
    )
    with pytest.raises(validator.PromotionValidationError, match="returned count mismatch"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def test_completion_replay_checksum_is_bound_by_manifest(evidence: Evidence) -> None:
    replay = _replay(evidence)
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    terminal_inputs["replay_sha256"] = "0" * 64
    with pytest.raises(validator.PromotionValidationError, match="replay receipt checksum mismatch"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    manifest["executions"][0]["status"]["latest_runs"][0]["run_id"] = replay[
        "invalidated_smoke_prefix"
    ]["executions"][0]["run_id"]
    with pytest.raises(validator.PromotionValidationError, match="reused an invalidated Runtime receipt"):
        validator.complete_phase5(
            descriptor=evidence.descriptor,
            replay=replay,
            terminal_baseline=baseline,
            terminal_manifest=manifest,
            control_revision="5" * 40,
            **terminal_inputs,
        )


def test_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(validator.PromotionValidationError, match="duplicate JSON key"):
        validator._load_object(path)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_cli_round_trip_replay_and_complete(evidence: Evidence, tmp_path: Path) -> None:
    files: dict[str, Path] = {}
    values = {
        "descriptor": evidence.descriptor,
        "current_status": evidence.current_status,
        "current_ai_analyses": evidence.current_ai_analyses,
        "phase4_run": evidence.phase4_source["run"],
        "phase4_artifact": evidence.phase4_source["artifact"],
        "phase4_jobs": evidence.phase4_source["jobs"],
        "failed_run": evidence.failed_source["run"],
        "failed_artifact": evidence.failed_source["artifact"],
        "failed_jobs": evidence.failed_source["jobs"],
        "legacy_run": evidence.legacy_source["run"],
        "legacy_jobs": evidence.legacy_source["jobs"],
        "predecessor_artifact": evidence.legacy_source["predecessor_artifact"],
        "state_artifact": evidence.legacy_source["state_artifact"],
        "output_artifact": evidence.legacy_source["output_artifact"],
    }
    for name, value in values.items():
        files[name] = tmp_path / f"{name}.json"
        _write_json(files[name], value)
    recovery_runs = []
    recovery_jobs = []
    recovery_predecessor_artifacts = []
    recovery_artifacts = []
    recovery_output_artifacts = []
    for index, (run, jobs) in enumerate(zip(evidence.recovery_run_metadatas, evidence.recovery_jobs_metadatas)):
        run_path = tmp_path / f"recovery-run-{index}.json"
        jobs_path = tmp_path / f"recovery-jobs-{index}.json"
        predecessor_artifact_path = tmp_path / f"recovery-predecessor-artifact-{index}.json"
        artifact_path = tmp_path / f"recovery-artifact-{index}.json"
        output_artifact_path = tmp_path / f"recovery-output-artifact-{index}.json"
        _write_json(run_path, run)
        _write_json(jobs_path, jobs)
        _write_json(
            predecessor_artifact_path,
            evidence.recovery_predecessor_artifact_metadatas[index],
        )
        _write_json(artifact_path, evidence.recovery_artifact_metadatas[index])
        _write_json(output_artifact_path, evidence.recovery_output_artifact_metadatas[index])
        recovery_runs.append(run_path)
        recovery_jobs.append(jobs_path)
        recovery_predecessor_artifacts.append(predecessor_artifact_path)
        recovery_artifacts.append(artifact_path)
        recovery_output_artifacts.append(output_artifact_path)
    frozen_successor_runs = []
    frozen_successor_jobs = []
    frozen_successor_artifacts = []
    frozen_successor_output_artifacts = []
    for index, (run, jobs) in enumerate(
        zip(evidence.frozen_successor_run_metadatas, evidence.frozen_successor_jobs_metadatas)
    ):
        run_path = tmp_path / f"frozen-successor-run-{index}.json"
        jobs_path = tmp_path / f"frozen-successor-jobs-{index}.json"
        artifact_path = tmp_path / f"frozen-successor-artifact-{index}.json"
        output_artifact_path = tmp_path / f"frozen-successor-output-artifact-{index}.json"
        _write_json(run_path, run)
        _write_json(jobs_path, jobs)
        _write_json(artifact_path, evidence.frozen_successor_artifact_metadatas[index])
        _write_json(
            output_artifact_path,
            evidence.frozen_successor_output_artifact_metadatas[index],
        )
        frozen_successor_runs.append(run_path)
        frozen_successor_jobs.append(jobs_path)
        frozen_successor_artifacts.append(artifact_path)
        frozen_successor_output_artifacts.append(output_artifact_path)
    legacy_run_inventory_paths = []
    for index, value in enumerate(evidence.legacy_run_inventories):
        path = tmp_path / f"legacy-run-inventory-{index}.json"
        _write_json(path, value)
        legacy_run_inventory_paths.append(path)
    legacy_artifact_inventory_paths = []
    for index, value in enumerate(evidence.legacy_artifact_inventories):
        path = tmp_path / f"legacy-artifact-inventory-{index}.json"
        _write_json(path, value)
        legacy_artifact_inventory_paths.append(path)
    replay_path = tmp_path / "replay.json"
    args = [
        "replay",
        "--descriptor", str(files["descriptor"]),
        "--repository-root", str(tmp_path),
        "--current-status", str(files["current_status"]),
        "--current-ai-analyses", str(files["current_ai_analyses"]),
        "--phase4-run-metadata", str(files["phase4_run"]),
        "--phase4-artifact-metadata", str(files["phase4_artifact"]),
        "--phase4-jobs-metadata", str(files["phase4_jobs"]),
        "--phase4-archive", str(evidence.phase4_archive),
        "--failed-run-metadata", str(files["failed_run"]),
        "--failed-artifact-metadata", str(files["failed_artifact"]),
        "--failed-jobs-metadata", str(files["failed_jobs"]),
        "--failed-archive", str(evidence.failed_archive),
        "--legacy-ai-run-metadata", str(files["legacy_run"]),
        "--legacy-ai-jobs-metadata", str(files["legacy_jobs"]),
        "--legacy-ai-predecessor-artifact-metadata", str(files["predecessor_artifact"]),
        "--legacy-ai-predecessor-archive", str(evidence.predecessor_archive),
        "--legacy-ai-state-artifact-metadata", str(files["state_artifact"]),
        "--legacy-ai-state-archive", str(evidence.state_archive),
        "--legacy-ai-output-artifact-metadata", str(files["output_artifact"]),
        "--legacy-ai-output-archive", str(evidence.output_archive),
    ]
    for path in recovery_runs:
        args += ["--recovery-run-metadata", str(path)]
    for path in recovery_jobs:
        args += ["--recovery-jobs-metadata", str(path)]
    for path in recovery_predecessor_artifacts:
        args += ["--recovery-predecessor-artifact-metadata", str(path)]
    for path in evidence.recovery_predecessor_archives:
        args += ["--recovery-predecessor-archive", str(path)]
    for path in recovery_artifacts:
        args += ["--recovery-artifact-metadata", str(path)]
    for path in evidence.recovery_archives:
        args += ["--recovery-archive", str(path)]
    for path in recovery_output_artifacts:
        args += ["--recovery-output-artifact-metadata", str(path)]
    for path in evidence.recovery_output_archives:
        args += ["--recovery-output-archive", str(path)]
    for path in frozen_successor_runs:
        args += ["--frozen-successor-run-metadata", str(path)]
    for path in frozen_successor_jobs:
        args += ["--frozen-successor-jobs-metadata", str(path)]
    for path in frozen_successor_artifacts:
        args += ["--frozen-successor-artifact-metadata", str(path)]
    for path in evidence.frozen_successor_archives:
        args += ["--frozen-successor-archive", str(path)]
    for path in frozen_successor_output_artifacts:
        args += ["--frozen-successor-output-artifact-metadata", str(path)]
    for path in evidence.frozen_successor_output_archives:
        args += ["--frozen-successor-output-archive", str(path)]
    for path in legacy_run_inventory_paths:
        args += ["--legacy-run-inventory", str(path)]
    for path in legacy_artifact_inventory_paths:
        args += ["--legacy-artifact-inventory", str(path)]
    args += ["--output", str(replay_path)]
    assert validator.main(args) == 0
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    baseline, manifest, terminal_inputs = _terminal(replay, evidence)
    replay_sha = hashlib.sha256(replay_path.read_bytes()).hexdigest()
    checksum_path = tmp_path / "failed-prefix-replay.sha256"
    checksum_path.write_text(f"{replay_sha}  {replay_path.name}\n", encoding="ascii")
    manifest["retry"]["failed_prefix_replay_sha256"] = replay_sha
    baseline_path = tmp_path / "terminal-baseline.json"
    manifest_path = tmp_path / "terminal-manifest.json"
    complete_path = tmp_path / "complete.json"
    _write_json(baseline_path, baseline)
    terminal_paths: dict[str, list[Path]] = {}
    for key in (
        "terminal_legacy_run_inventories",
        "terminal_legacy_workflow_states",
        "terminal_runtime_execution_inventories",
    ):
        terminal_paths[key] = []
        digest_key = key.removeprefix("terminal_")
        digest_map = manifest["one_writer_evidence"][f"{digest_key}_sha256"]
        for role, value in zip(validator.LEGACY_HIGH_WATER_ROLES, terminal_inputs[key]):
            path = tmp_path / f"terminal-{digest_key}-{role}.json"
            _write_json(path, value)
            terminal_paths[key].append(path)
            digest_map[role] = hashlib.sha256(path.read_bytes()).hexdigest()
    _write_json(manifest_path, manifest)
    complete_args = [
            "complete",
            "--descriptor", str(files["descriptor"]),
            "--replay", str(replay_path),
            "--replay-checksum", str(checksum_path),
            "--terminal-baseline", str(baseline_path),
            "--terminal-manifest", str(manifest_path),
            "--control-revision", "5" * 40,
            "--output", str(complete_path),
    ]
    for path in terminal_paths["terminal_legacy_run_inventories"]:
        complete_args += ["--terminal-legacy-run-inventory", str(path)]
    for path in terminal_paths["terminal_legacy_workflow_states"]:
        complete_args += ["--terminal-legacy-workflow-state", str(path)]
    for path in terminal_paths["terminal_runtime_execution_inventories"]:
        complete_args += ["--terminal-runtime-execution-inventory", str(path)]
    assert validator.main(complete_args) == 0
    assert json.loads(complete_path.read_text(encoding="utf-8"))["result"] == "phase5_complete"
