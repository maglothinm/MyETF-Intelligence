from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "deploy"
    / "runtime-v2"
    / "verify_legislative_validation_evidence.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_legislative_validation_evidence", MODULE_PATH
)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


TIMES = {
    "run_created": "2026-09-05T14:00:00Z",
    "run_started": "2026-09-05T14:00:01Z",
    "job_started": "2026-09-05T14:00:02Z",
    "receipt_started": "2026-09-05T14:00:03Z",
    "receipt_finished": "2026-09-05T14:00:04Z",
    "artifact_created": "2026-09-05T14:00:05Z",
    "job_completed": "2026-09-05T14:00:06Z",
    "run_updated": "2026-09-05T14:00:07Z",
    "expires": "2099-09-05T14:00:05Z",
}


def _run(command: list[str], cwd: Path) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, value in members.items():
            bundle.writestr(name, value)


def _git_repository(path: Path) -> tuple[str, str]:
    path.mkdir()
    _run(["git", "init", "--initial-branch=main"], path)
    _run(["git", "config", "user.email", "validation@example.invalid"], path)
    _run(["git", "config", "user.name", "Validation Test"], path)
    for relative in verifier.IMPLEMENTATION_PATHS:
        target = path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"validated implementation: {relative}\n", encoding="utf-8")
    workflow = path / verifier.WORKFLOW_PATH
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        """name: Legislative purchase tracker v2
on: workflow_dispatch
jobs:
  track:
    steps:
      - run: python scripts/government_trade_tracker.py --branch legislative --source all --no-notify
      - run: python scripts/legislative_healthcheck.py --require-notifications-suppressed --require-no-notification-eligible-records
""",
        encoding="utf-8",
    )
    _run(["git", "add", "."], path)
    _run(
        ["git", "update-index", "--chmod=+x", "scripts/government_trade_tracker.py"],
        path,
    )
    _run(["git", "commit", "-m", "controlled validation source"], path)
    validation_sha = _run(["git", "rev-parse", "HEAD"], path)

    workflow.write_text(
        """name: Legislative purchase tracker v2
on:
  schedule:
    - cron: '7,22,37,52 * * * *'
  workflow_dispatch:
jobs:
  track:
    steps:
      - run: python scripts/government_trade_tracker.py --branch legislative --source all
""",
        encoding="utf-8",
    )
    _run(["git", "add", "."], path)
    _run(["git", "commit", "-m", "restore schedule after validation"], path)
    control_sha = _run(["git", "rev-parse", "HEAD"], path)
    return validation_sha, control_sha


def _fixture(tmp_path: Path) -> argparse.Namespace:
    repository = tmp_path / "repo"
    validation_sha, control_sha = _git_repository(repository)
    run_id = 4000
    attempt = 1
    state_id = 5001
    output_id = 5002
    workflow_id = 6000
    job_id = 7000

    state = {
        "version": 1,
        "last_success_utc": TIMES["receipt_finished"],
        "seen_filings": {"house": {}, "senate": {}, "oge": {}},
        "seen_trades": {},
        "seen_reviews": {},
    }
    result = {
        "branch": "legislative",
        "started_utc": TIMES["receipt_started"],
        "finished_utc": TIMES["receipt_finished"],
        "success": True,
        "overall_status": "degraded",
        "discovery_complete": False,
        "source_statuses": {"house": "ok", "senate": "blocked"},
        "source_counts": {"house": 15},
        "transaction_counts": {"house": 0},
        "pending_review_counts": {"house": 0},
        "alerted_filing_counts": {"house": 0},
    }
    state_bytes = (json.dumps(state, sort_keys=True) + "\n").encode()
    result_bytes = (json.dumps(result, sort_keys=True) + "\n").encode()
    restore = {
        "version": 1,
        "restored_at_utc": "2026-09-05T14:00:02Z",
        "repository_id": verifier.REPOSITORY_ID,
        "consumer_sha": validation_sha,
        "predecessor_artifact_id": 3001,
        "predecessor_artifact_name": verifier.STATE_ARTIFACT_NAME,
        "predecessor_artifact_created_at": "2026-09-05T13:00:00Z",
        "predecessor_artifact_api_digest": "sha256:" + "a" * 64,
        "downloaded_zip_sha256": "a" * 64,
        "predecessor_run_id": 3000,
        "predecessor_run_attempt": 1,
        "predecessor_head_sha": validation_sha,
        "predecessor_workflow_id": 6000,
        "predecessor_workflow_file": "legislative_trade_tracker_v2.yml",
        "predecessor_workflow_name": verifier.WORKFLOW_NAME,
        "restored_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
    }
    restore_bytes = (json.dumps(restore, sort_keys=True) + "\n").encode()
    protected_payloads = {
        "state": state_bytes,
        "ledger": b"",
        "transactions": b"",
        "filings": b"",
        "pending": b"",
        "history": b"{}\n",
    }
    protected_files = [
        {
            "key": key,
            "existed_before": True,
            "before_sha256": hashlib.sha256(value).hexdigest(),
            "existed_after": True,
            "after_sha256": hashlib.sha256(value).hexdigest(),
            "matches_predecessor": True,
        }
        for key, value in protected_payloads.items()
    ]
    controlled = {
        "version": 1,
        "attested_at_utc": TIMES["receipt_finished"],
        "repository_id": verifier.REPOSITORY_ID,
        "repository": verifier.REPOSITORY,
        "consumer_sha": validation_sha,
        "run_id": run_id,
        "run_attempt": attempt,
        "trigger_source": "workflow_dispatch",
        "controlled_validation": True,
        "notifications_suppressed": True,
        "no_outbound_attested": True,
        "outbound_notifications_attempted": 0,
        "outbound_notifications_sent": 0,
        "notification_delivery_count": 0,
        "notification_eligible_new_records": 0,
        "collection_success": True,
        "overall_status": "degraded",
        "validation_outcome": "zero_change_successor",
        "protected_state_action": "committed",
        "rollback_performed": False,
        "rollback_reason": "",
        "rollback_verified": False,
        "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "restore_receipt_sha256": hashlib.sha256(restore_bytes).hexdigest(),
        "predecessor_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "candidate_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "post_run_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "protected_files": protected_files,
    }
    controlled_bytes = (json.dumps(controlled, sort_keys=True) + "\n").encode()
    receipt = {
        "version": 3,
        "started_utc": TIMES["receipt_started"],
        "finished_utc": TIMES["receipt_finished"],
        "success": True,
        "overall_status": "degraded",
        "durable_state_eligible": True,
        "protected_upload_eligible": True,
        "notifications_suppressed": True,
        "notification_eligible_new_records": 0,
        "notification_delivery_count": 0,
        "validation_outcome": "zero_change_successor",
        "protected_state_action": "committed",
        "rollback_performed": False,
        "rollback_verified": False,
        "outbound_notifications_attempted": 0,
        "outbound_notifications_sent": 0,
        "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "candidate_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "restore_receipt_sha256": hashlib.sha256(restore_bytes).hexdigest(),
        "controlled_validation_receipt_sha256": hashlib.sha256(controlled_bytes).hexdigest(),
        "sources": [
            {
                "source": "senate",
                "returncode": 1,
                "status": "blocked",
                "state_candidate_valid": False,
                "state_committed": False,
                "result_file": "legislative-result-senate.json",
                "notification_eligible_new_records": 0,
                "notification_delivery_count": 0,
            },
            {
                "source": "house",
                "returncode": 0,
                "status": "ok",
                "state_candidate_valid": True,
                "state_committed": True,
                "result_file": "legislative-result-house.json",
                "notification_eligible_new_records": 0,
                "notification_delivery_count": 0,
            },
        ],
    }
    receipt_bytes = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    state_archive = tmp_path / "state.zip"
    output_archive = tmp_path / "output.zip"
    _write_zip(
        state_archive,
        {
            "state.json": state_bytes,
            "source-status.json": receipt_bytes,
            "restore-receipt.json": restore_bytes,
            "controlled-validation-receipt.json": controlled_bytes,
            "purchases.jsonl": protected_payloads["ledger"],
            "transactions.jsonl": protected_payloads["transactions"],
            "filings.jsonl": protected_payloads["filings"],
            "runs.jsonl": protected_payloads["history"],
            "pending-review.jsonl": protected_payloads["pending"],
        },
    )
    _write_zip(
        output_archive,
        {
            "legislative-result.json": result_bytes,
            "legislative-latest-purchases.csv": b"filing_key\n",
            "legislative-latest-transactions.csv": b"transaction_key\n",
            "legislative-latest-filings.csv": b"filing_key\n",
            ".trade-tracker/legislative/source-status.json": receipt_bytes,
            ".trade-tracker/legislative/restore-receipt.json": restore_bytes,
            ".trade-tracker/legislative/controlled-validation-receipt.json": controlled_bytes,
        },
    )
    descriptor = {
        "schema_version": 1,
        "result": verifier.DESCRIPTOR_RESULT,
        "repository_id": verifier.REPOSITORY_ID,
        "repository": verifier.REPOSITORY,
        "workflow": {
            "id": workflow_id,
            "name": verifier.WORKFLOW_NAME,
            "path": verifier.WORKFLOW_PATH,
        },
        "validation": {
            "run_id": run_id,
            "run_number": 77,
            "run_attempt": attempt,
            "job_id": job_id,
            "head_sha": validation_sha,
            "expected_outcome": "zero_change_successor",
        },
        "artifacts": {
            "protected_state": {
                "id": state_id,
                "name": verifier.STATE_ARTIFACT_NAME,
                "size_in_bytes": state_archive.stat().st_size,
                "digest": "sha256:" + hashlib.sha256(state_archive.read_bytes()).hexdigest(),
                "expires_at": TIMES["expires"],
            },
            "diagnostic_output": {
                "id": output_id,
                "name": f"legislative-purchase-output-{run_id}-{attempt}",
                "size_in_bytes": output_archive.stat().st_size,
                "digest": "sha256:" + hashlib.sha256(output_archive.read_bytes()).hexdigest(),
                "expires_at": TIMES["expires"],
            },
        },
        "predecessor": {
            "artifact_id": restore["predecessor_artifact_id"],
            "artifact_name": restore["predecessor_artifact_name"],
            "artifact_size_in_bytes": 123456,
            "artifact_digest": restore["predecessor_artifact_api_digest"],
            "artifact_created_at": restore["predecessor_artifact_created_at"],
            "artifact_expires_at": TIMES["expires"],
            "run_id": restore["predecessor_run_id"],
            "run_attempt": restore["predecessor_run_attempt"],
            "head_sha": restore["predecessor_head_sha"],
            "workflow_id": restore["predecessor_workflow_id"],
            "workflow_file": restore["predecessor_workflow_file"],
            "workflow_name": restore["predecessor_workflow_name"],
        },
        "additional_validation_run_authorized": False,
        "production_authority_transferred": False,
    }
    run = {
        "id": run_id,
        "run_number": 77,
        "run_attempt": attempt,
        "workflow_id": workflow_id,
        "name": verifier.WORKFLOW_NAME,
        "path": verifier.WORKFLOW_PATH + "@refs/heads/main",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": validation_sha,
        "status": "completed",
        "conclusion": "success",
        "created_at": TIMES["run_created"],
        "run_started_at": TIMES["run_started"],
        "updated_at": TIMES["run_updated"],
        "repository": {"id": verifier.REPOSITORY_ID},
        "head_repository": {"id": verifier.REPOSITORY_ID},
    }
    steps = [
        {"name": name, "status": "completed", "conclusion": "success"}
        for name in sorted(verifier.REQUIRED_SUCCESSFUL_STEPS)
    ]
    steps.append(
        {
            "name": verifier.CLASSIFICATION_STEP,
            "status": "completed",
            "conclusion": "success",
        }
    )
    jobs = {
        "total_count": 1,
        "jobs": [
            {
                "id": job_id,
                "run_id": run_id,
                "run_attempt": attempt,
                "head_sha": validation_sha,
                "name": verifier.AUTHORITATIVE_JOB,
                "status": "completed",
                "conclusion": "success",
                "started_at": TIMES["job_started"],
                "completed_at": TIMES["job_completed"],
                "steps": steps,
            }
        ],
    }

    def artifact(role: str) -> dict:
        pin = descriptor["artifacts"][role]
        return {
            **pin,
            "expired": False,
            "created_at": TIMES["artifact_created"],
            "updated_at": TIMES["artifact_created"],
            "workflow_run": {
                "id": run_id,
                "repository_id": verifier.REPOSITORY_ID,
                "head_repository_id": verifier.REPOSITORY_ID,
                "head_branch": "main",
                "head_sha": validation_sha,
            },
        }

    artifacts = {
        "total_count": 2,
        "artifacts": [artifact("protected_state"), artifact("diagnostic_output")],
    }
    predecessor_artifact = {
        "id": descriptor["predecessor"]["artifact_id"],
        "name": descriptor["predecessor"]["artifact_name"],
        "size_in_bytes": descriptor["predecessor"]["artifact_size_in_bytes"],
        "digest": descriptor["predecessor"]["artifact_digest"],
        "created_at": descriptor["predecessor"]["artifact_created_at"],
        "updated_at": descriptor["predecessor"]["artifact_created_at"],
        "expires_at": descriptor["predecessor"]["artifact_expires_at"],
        "expired": False,
        "workflow_run": {
            "id": descriptor["predecessor"]["run_id"],
            "repository_id": verifier.REPOSITORY_ID,
            "head_repository_id": verifier.REPOSITORY_ID,
            "head_branch": "main",
            "head_sha": descriptor["predecessor"]["head_sha"],
        },
    }
    compare = {
        "status": "ahead",
        "ahead_by": 1,
        "behind_by": 0,
        "base_commit": {"sha": validation_sha},
        "head_commit": {"sha": control_sha},
        "merge_base_commit": {"sha": validation_sha},
    }

    files = {}
    for name, value in {
        "descriptor": descriptor,
        "run": run,
        "jobs": jobs,
        "artifacts": artifacts,
        "predecessor_artifact": predecessor_artifact,
        "compare": compare,
    }.items():
        path = tmp_path / f"{name}.json"
        _write_json(path, value)
        files[name] = path
    return argparse.Namespace(
        descriptor=files["descriptor"],
        run_metadata=files["run"],
        jobs_metadata=files["jobs"],
        artifacts_metadata=files["artifacts"],
        predecessor_artifact_metadata=files["predecessor_artifact"],
        state_archive=state_archive,
        output_archive=output_archive,
        compare_metadata=files["compare"],
        repository_root=repository,
        control_revision=control_sha,
        output=tmp_path / "verified.json",
    )


def _mutate_json(path: Path, change) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    change(value)
    _write_json(path, value)


def test_valid_pinned_manual_run_issues_prerequisite_receipt(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    receipt = verifier.verify(arguments)
    assert receipt["result"] == "legislative_controlled_validation_verified"
    assert receipt["notifications_suppressed"] is True
    assert receipt["notification_eligible_new_records"] == 0
    assert receipt["successful_sources"] == ["house"]
    assert receipt["implementation_source_continuity_verified"] is True
    assert receipt["source_status_receipt_verified"] is True
    assert receipt["controlled_validation_receipt_verified"] is True
    assert set(receipt["implementation_sha256"]) == set(verifier.IMPLEMENTATION_PATHS)


def test_safe_notification_eligible_rollback_is_a_distinct_accepted_outcome(
    tmp_path: Path,
) -> None:
    arguments = _fixture(tmp_path)
    state_members = verifier._archive_members(arguments.state_archive)
    output_members = verifier._archive_members(arguments.output_archive)
    result = json.loads(output_members[verifier.OUTPUT_RESULT_PATH])
    result["transaction_counts"]["house"] = 1
    result_bytes = (json.dumps(result, sort_keys=True) + "\n").encode()
    output_members[verifier.OUTPUT_RESULT_PATH] = result_bytes
    controlled = json.loads(
        state_members[verifier.STATE_CONTROLLED_RECEIPT_PATH]
    )
    controlled.update(
        validation_outcome="notification_eligible_rollback",
        protected_state_action="rolled_back",
        rollback_performed=True,
        rollback_reason="notification_eligible_records",
        rollback_verified=True,
        notification_eligible_new_records=1,
        candidate_state_sha256="b" * 64,
        result_sha256=hashlib.sha256(result_bytes).hexdigest(),
    )
    controlled_bytes = (json.dumps(controlled, sort_keys=True) + "\n").encode()
    state_members[verifier.STATE_CONTROLLED_RECEIPT_PATH] = controlled_bytes
    output_members[
        ".trade-tracker/legislative/controlled-validation-receipt.json"
    ] = controlled_bytes
    receipt = json.loads(state_members[verifier.STATE_RECEIPT_PATH])
    receipt.update(
        validation_outcome="notification_eligible_rollback",
        durable_state_eligible=False,
        notification_eligible_new_records=1,
        protected_state_action="rolled_back",
        rollback_performed=True,
        rollback_verified=True,
        candidate_state_sha256="b" * 64,
        result_sha256=hashlib.sha256(result_bytes).hexdigest(),
        controlled_validation_receipt_sha256=hashlib.sha256(controlled_bytes).hexdigest(),
    )
    receipt["sources"][1]["state_committed"] = False
    receipt["sources"][1]["notification_eligible_new_records"] = 1
    receipt_bytes = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    state_members[verifier.STATE_RECEIPT_PATH] = receipt_bytes
    output_members[".trade-tracker/legislative/source-status.json"] = receipt_bytes
    _write_zip(arguments.state_archive, state_members)
    _write_zip(arguments.output_archive, output_members)

    descriptor = json.loads(arguments.descriptor.read_text(encoding="utf-8"))
    descriptor["validation"]["expected_outcome"] = "notification_eligible_rollback"
    jobs = json.loads(arguments.jobs_metadata.read_text(encoding="utf-8"))
    classifier = next(
        step
        for step in jobs["jobs"][0]["steps"]
        if step["name"] == verifier.CLASSIFICATION_STEP
    )
    classifier["conclusion"] = "failure"
    _write_json(arguments.jobs_metadata, jobs)
    artifacts = json.loads(arguments.artifacts_metadata.read_text(encoding="utf-8"))
    for role, archive in (
        ("protected_state", arguments.state_archive),
        ("diagnostic_output", arguments.output_archive),
    ):
        pin = descriptor["artifacts"][role]
        pin["size_in_bytes"] = archive.stat().st_size
        pin["digest"] = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
        metadata = next(item for item in artifacts["artifacts"] if item["id"] == pin["id"])
        metadata["size_in_bytes"] = pin["size_in_bytes"]
        metadata["digest"] = pin["digest"]
    _write_json(arguments.descriptor, descriptor)
    _write_json(arguments.artifacts_metadata, artifacts)

    verified = verifier.verify(arguments)
    assert verified["controlled_validation_outcome"] == "notification_eligible_rollback"
    assert verified["notification_eligible_new_records"] == 1
    assert verified["zero_notification_eligible_changes_verified"] is False
    assert verified["predecessor_state_rollback_verified"] is True
    assert verified["no_outbound_notifications_verified"] is True


def test_artifact_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    _mutate_json(
        arguments.descriptor,
        lambda value: value["artifacts"]["protected_state"].update(
            digest="sha256:" + "0" * 64
        ),
    )
    with pytest.raises(verifier.LegislativeValidationError, match="digest mismatch"):
        verifier.verify(arguments)


def test_predecessor_artifact_metadata_must_match_the_descriptor_pin(
    tmp_path: Path,
) -> None:
    arguments = _fixture(tmp_path)
    _mutate_json(
        arguments.predecessor_artifact_metadata,
        lambda value: value.update(id=9969550055),
    )
    with pytest.raises(
        verifier.LegislativeValidationError,
        match="predecessor artifact id mismatch",
    ):
        verifier.verify(arguments)


def test_unsafe_archive_member_fails_closed(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    with zipfile.ZipFile(arguments.state_archive, "a") as bundle:
        bundle.writestr("../escape.json", "{}")
    descriptor = json.loads(arguments.descriptor.read_text(encoding="utf-8"))
    pin = descriptor["artifacts"]["protected_state"]
    pin["size_in_bytes"] = arguments.state_archive.stat().st_size
    pin["digest"] = "sha256:" + hashlib.sha256(arguments.state_archive.read_bytes()).hexdigest()
    _write_json(arguments.descriptor, descriptor)
    artifacts = json.loads(arguments.artifacts_metadata.read_text(encoding="utf-8"))
    metadata = next(item for item in artifacts["artifacts"] if item["id"] == pin["id"])
    metadata["size_in_bytes"] = pin["size_in_bytes"]
    metadata["digest"] = pin["digest"]
    _write_json(arguments.artifacts_metadata, artifacts)
    with pytest.raises(verifier.LegislativeValidationError, match="unsafe member path"):
        verifier.verify(arguments)


def test_receipt_and_output_artifact_must_be_identical(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    output_members = verifier._archive_members(arguments.output_archive)
    receipt_name = ".trade-tracker/legislative/source-status.json"
    receipt = json.loads(output_members[receipt_name])
    receipt["notifications_suppressed"] = False
    output_members[receipt_name] = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    _write_zip(arguments.output_archive, output_members)
    descriptor = json.loads(arguments.descriptor.read_text(encoding="utf-8"))
    pin = descriptor["artifacts"]["diagnostic_output"]
    pin["size_in_bytes"] = arguments.output_archive.stat().st_size
    pin["digest"] = "sha256:" + hashlib.sha256(arguments.output_archive.read_bytes()).hexdigest()
    _write_json(arguments.descriptor, descriptor)
    artifacts = json.loads(arguments.artifacts_metadata.read_text(encoding="utf-8"))
    metadata = next(item for item in artifacts["artifacts"] if item["id"] == pin["id"])
    metadata["size_in_bytes"] = pin["size_in_bytes"]
    metadata["digest"] = pin["digest"]
    _write_json(arguments.artifacts_metadata, artifacts)
    with pytest.raises(verifier.LegislativeValidationError, match="different source-status"):
        verifier.verify(arguments)


def test_notification_eligible_change_fails_closed(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    state_members = verifier._archive_members(arguments.state_archive)
    output_members = verifier._archive_members(arguments.output_archive)
    result = json.loads(output_members[verifier.OUTPUT_RESULT_PATH])
    result["transaction_counts"]["house"] = 1
    result_bytes = (json.dumps(result, sort_keys=True) + "\n").encode()
    output_members[verifier.OUTPUT_RESULT_PATH] = result_bytes
    receipt = json.loads(state_members[verifier.STATE_RECEIPT_PATH])
    receipt["notification_eligible_new_records"] = 1
    receipt["result_sha256"] = hashlib.sha256(result_bytes).hexdigest()
    receipt["sources"][1]["notification_eligible_new_records"] = 1
    receipt_bytes = (json.dumps(receipt, sort_keys=True) + "\n").encode()
    state_members[verifier.STATE_RECEIPT_PATH] = receipt_bytes
    output_members[".trade-tracker/legislative/source-status.json"] = receipt_bytes
    _write_zip(arguments.state_archive, state_members)
    _write_zip(arguments.output_archive, output_members)
    descriptor = json.loads(arguments.descriptor.read_text(encoding="utf-8"))
    artifacts = json.loads(arguments.artifacts_metadata.read_text(encoding="utf-8"))
    for role, archive in (
        ("protected_state", arguments.state_archive),
        ("diagnostic_output", arguments.output_archive),
    ):
        pin = descriptor["artifacts"][role]
        pin["size_in_bytes"] = archive.stat().st_size
        pin["digest"] = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
        metadata = next(item for item in artifacts["artifacts"] if item["id"] == pin["id"])
        metadata["size_in_bytes"] = pin["size_in_bytes"]
        metadata["digest"] = pin["digest"]
    _write_json(arguments.descriptor, descriptor)
    _write_json(arguments.artifacts_metadata, artifacts)
    with pytest.raises(verifier.LegislativeValidationError, match="notification_eligible_new_records mismatch|notification-eligible"):
        verifier.verify(arguments)


def test_non_ancestor_control_revision_fails_closed(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    _mutate_json(
        arguments.compare_metadata,
        lambda value: value["merge_base_commit"].update(sha="0" * 40),
    )
    with pytest.raises(verifier.LegislativeValidationError, match="merge-base"):
        verifier.verify(arguments)


def test_implementation_drift_after_validation_fails_closed(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    relative = verifier.IMPLEMENTATION_PATHS[0]
    target = arguments.repository_root / relative
    target.write_text("changed after validation\n", encoding="utf-8")
    _run(["git", "add", relative], arguments.repository_root)
    _run(["git", "commit", "-m", "unvalidated implementation drift"], arguments.repository_root)
    new_control = _run(["git", "rev-parse", "HEAD"], arguments.repository_root)
    arguments.control_revision = new_control
    _mutate_json(
        arguments.compare_metadata,
        lambda value: (
            value["head_commit"].update(sha=new_control),
            value.update(ahead_by=2),
        ),
    )
    with pytest.raises(verifier.LegislativeValidationError, match="implementation changed"):
        verifier.verify(arguments)


def test_tracker_executable_mode_drift_fails_closed(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    _run(
        ["git", "update-index", "--chmod=-x", "scripts/government_trade_tracker.py"],
        arguments.repository_root,
    )
    _run(
        ["git", "commit", "-m", "drop tracker executable mode"],
        arguments.repository_root,
    )
    new_control = _run(["git", "rev-parse", "HEAD"], arguments.repository_root)
    arguments.control_revision = new_control
    _mutate_json(
        arguments.compare_metadata,
        lambda value: (
            value["head_commit"].update(sha=new_control),
            value.update(ahead_by=2),
        ),
    )
    with pytest.raises(verifier.LegislativeValidationError, match="executable mode"):
        verifier.verify(arguments)


def test_missing_descriptor_is_a_hard_failure(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    arguments.descriptor = tmp_path / "not-yet-issued.json"
    with pytest.raises(verifier.LegislativeValidationError, match="unable to read"):
        verifier.verify(arguments)


def test_cli_writes_no_receipt_on_failure(tmp_path: Path) -> None:
    arguments = _fixture(tmp_path)
    _mutate_json(
        arguments.jobs_metadata,
        lambda value: value["jobs"][0].update(conclusion="failure"),
    )
    argv = [
        "--descriptor", str(arguments.descriptor),
        "--run-metadata", str(arguments.run_metadata),
        "--jobs-metadata", str(arguments.jobs_metadata),
        "--artifacts-metadata", str(arguments.artifacts_metadata),
        "--predecessor-artifact-metadata",
        str(arguments.predecessor_artifact_metadata),
        "--state-archive", str(arguments.state_archive),
        "--output-archive", str(arguments.output_archive),
        "--compare-metadata", str(arguments.compare_metadata),
        "--repository-root", str(arguments.repository_root),
        "--control-revision", arguments.control_revision,
        "--output", str(arguments.output),
    ]
    assert verifier.main(argv) == 1
    assert not arguments.output.exists()
