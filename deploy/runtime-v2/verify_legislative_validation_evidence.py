"""Verify pinned evidence from the controlled Legislative validation run.

This verifier is deliberately offline.  The Phase 4 controller downloads the
exact GitHub API responses and artifact archives named by a checked-in evidence
descriptor, then passes those files here.  Certificate issuance remains blocked
when the descriptor is absent or any run, job, artifact, receipt, state, result,
or implementation-continuity claim cannot be reproduced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


class LegislativeValidationError(ValueError):
    """Raised when controlled-validation evidence is incomplete or inconsistent."""


REPOSITORY_ID = 1349678672
REPOSITORY = "maglothinm/MyETF-Intelligence"
WORKFLOW_NAME = "Legislative purchase tracker v2"
WORKFLOW_PATH = ".github/workflows/legislative_trade_tracker_v2.yml"
AUTHORITATIVE_JOB = "track"
STATE_ARTIFACT_NAME = "legislative-tracker-state"
DESCRIPTOR_RESULT = "legislative_controlled_validation_evidence_pinned"
ACCEPTED_OUTCOMES = {
    "zero_change_successor",
    "notification_eligible_rollback",
}
OUTPUT_RESULT_PATH = "legislative-result.json"
OUTPUT_RECEIPT_PATHS = (
    ".trade-tracker/legislative/source-status.json",
    "source-status.json",
)
STATE_RECEIPT_PATH = "source-status.json"
STATE_RESTORE_RECEIPT_PATH = "restore-receipt.json"
OUTPUT_RESTORE_RECEIPT_PATHS = (
    ".trade-tracker/legislative/restore-receipt.json",
    "restore-receipt.json",
)
STATE_PATH = "state.json"
REQUIRED_STATE_MEMBERS = {
    "state.json",
    "source-status.json",
    "restore-receipt.json",
    "purchases.jsonl",
    "transactions.jsonl",
    "filings.jsonl",
    "runs.jsonl",
    "pending-review.jsonl",
}
IMPLEMENTATION_PATHS = (
    "requirements-tracker.txt",
    "scripts/government_trade_tracker.py",
    "scripts/government_trade_tracker_core.py",
    "scripts/run_legislative_sources_resilient.py",
    "scripts/legislative_healthcheck.py",
    "scripts/monitor_disclosures.py",
    "scripts/historical_transaction_bootstrap.py",
    "scripts/run_trigger.py",
)
REQUIRED_SUCCESSFUL_STEPS = {
    "Check out repository",
    "Restore authoritative Legislative state artifact",
    "Run offline tests",
    "Track House and Senate purchases",
    "Validate durable Legislative result",
    "Upload durable tracker state",
    "Upload run outputs",
}
MAX_ARCHIVE_FILE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 128 * 1024 * 1024
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _fail(message: str) -> None:
    raise LegislativeValidationError(message)


def _reject_constant(value: str) -> None:
    _fail(f"non-finite JSON value {value!r} is not permitted")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json_bytes(data: bytes, label: str) -> Any:
    try:
        text = data.decode("utf-8")
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LegislativeValidationError(f"{label} is not valid UTF-8 JSON") from exc


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = _json_bytes(path.read_bytes(), str(path))
    except OSError as exc:
        raise LegislativeValidationError(f"unable to read {path}") from exc
    if not isinstance(value, dict):
        _fail(f"{path} is not a JSON object")
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LegislativeValidationError(f"unable to read {path}") from exc
    return digest.hexdigest()


def _normalized_source(data: bytes, label: str) -> bytes:
    if b"\x00" in data:
        _fail(f"implementation file {label} is not text")
    normalized = data.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        _fail(f"implementation file {label} has unsupported line endings")
    return normalized


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        _fail(f"{label} is not a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise LegislativeValidationError(f"{label} is not a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{label} is not a UTC timestamp")
    return parsed


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(f"{label} is not a positive integer")
    return value


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        _fail(f"{label} mismatch")


def _archive_members(path: Path) -> dict[str, bytes]:
    if not zipfile.is_zipfile(path):
        _fail(f"{path} is not a ZIP archive")
    members: dict[str, bytes] = {}
    folded_names: set[str] = set()
    total = 0
    try:
        with zipfile.ZipFile(path) as bundle:
            for info in bundle.infolist():
                raw_name = info.filename
                if "\x00" in raw_name or "\\" in raw_name:
                    _fail("archive contains an unsafe member name")
                member = PurePosixPath(raw_name)
                if member.is_absolute() or any(
                    part in {"", ".", ".."} for part in member.parts
                ):
                    _fail("archive contains an unsafe member path")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    _fail("archive contains a symbolic link")
                if info.flag_bits & 0x1:
                    _fail("archive contains an encrypted member")
                if info.is_dir():
                    continue
                name = member.as_posix()
                folded = name.casefold()
                if name in members or folded in folded_names:
                    _fail(f"archive contains duplicate member {name}")
                if info.file_size > MAX_ARCHIVE_FILE_BYTES:
                    _fail(f"archive member {name} is too large")
                total += info.file_size
                if total > MAX_ARCHIVE_TOTAL_BYTES:
                    _fail("archive expands beyond the validation evidence limit")
                data = bundle.read(info)
                if len(data) != info.file_size:
                    _fail(f"archive member {name} has an inconsistent size")
                members[name] = data
                folded_names.add(folded)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise LegislativeValidationError(f"unable to read ZIP archive {path}") from exc
    return members


def _artifact_pin(descriptor: Mapping[str, Any], role: str) -> Mapping[str, Any]:
    artifacts = descriptor.get("artifacts")
    if not isinstance(artifacts, Mapping):
        _fail("descriptor artifacts are missing")
    pin = artifacts.get(role)
    if not isinstance(pin, Mapping):
        _fail(f"descriptor artifact role {role!r} is missing")
    return pin


def _validate_descriptor(descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
    _expect(descriptor.get("schema_version"), 1, "descriptor schema_version")
    _expect(descriptor.get("result"), DESCRIPTOR_RESULT, "descriptor result")
    _expect(descriptor.get("repository_id"), REPOSITORY_ID, "descriptor repository_id")
    _expect(descriptor.get("repository"), REPOSITORY, "descriptor repository")
    _expect(
        descriptor.get("additional_validation_run_authorized"),
        False,
        "descriptor additional_validation_run_authorized",
    )
    _expect(
        descriptor.get("production_authority_transferred"),
        False,
        "descriptor production_authority_transferred",
    )

    workflow = descriptor.get("workflow")
    if not isinstance(workflow, Mapping):
        _fail("descriptor workflow is missing")
    _positive_int(workflow.get("id"), "descriptor workflow id")
    _expect(workflow.get("name"), WORKFLOW_NAME, "descriptor workflow name")
    _expect(workflow.get("path"), WORKFLOW_PATH, "descriptor workflow path")

    validation = descriptor.get("validation")
    if not isinstance(validation, Mapping):
        _fail("descriptor validation run is missing")
    for field in ("run_id", "run_number", "run_attempt", "job_id"):
        _positive_int(validation.get(field), f"descriptor validation {field}")
    head_sha = validation.get("head_sha")
    if not isinstance(head_sha, str) or not SHA_PATTERN.fullmatch(head_sha):
        _fail("descriptor validation head_sha is invalid")
    expected_outcome = validation.get("expected_outcome")
    if expected_outcome not in ACCEPTED_OUTCOMES:
        _fail("descriptor validation expected_outcome is invalid")

    expected_artifact_names = {
        "protected_state": STATE_ARTIFACT_NAME,
        "diagnostic_output": (
            f"legislative-purchase-output-{validation['run_id']}-{validation['run_attempt']}"
        ),
    }
    artifact_ids: set[int] = set()
    for role, name in expected_artifact_names.items():
        pin = _artifact_pin(descriptor, role)
        artifact_id = _positive_int(pin.get("id"), f"{role} artifact id")
        if artifact_id in artifact_ids:
            _fail("descriptor reuses an artifact id")
        artifact_ids.add(artifact_id)
        _expect(pin.get("name"), name, f"{role} artifact name")
        _positive_int(pin.get("size_in_bytes"), f"{role} artifact size")
        digest = pin.get("digest")
        if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
            _fail(f"{role} artifact digest is invalid")
        _parse_time(pin.get("expires_at"), f"{role} artifact expires_at")
    return validation


def _validate_run_and_job(
    descriptor: Mapping[str, Any],
    validation: Mapping[str, Any],
    run: Mapping[str, Any],
    jobs: Mapping[str, Any],
) -> tuple[datetime, datetime]:
    workflow = descriptor["workflow"]
    expected_run = {
        "id": validation["run_id"],
        "run_number": validation["run_number"],
        "run_attempt": validation["run_attempt"],
        "workflow_id": workflow["id"],
        "name": WORKFLOW_NAME,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": validation["head_sha"],
        "status": "completed",
        "conclusion": "success",
    }
    for field, expected in expected_run.items():
        _expect(run.get(field), expected, f"validation run {field}")
    run_path = run.get("path")
    if isinstance(run_path, str):
        run_path = run_path.split("@", 1)[0]
    _expect(run_path, WORKFLOW_PATH, "validation run path")
    for field in ("repository", "head_repository"):
        boundary = run.get(field)
        if not isinstance(boundary, Mapping) or boundary.get("id") != REPOSITORY_ID:
            _fail(f"validation run {field} boundary mismatch")

    created = _parse_time(run.get("created_at"), "validation run created_at")
    run_started = _parse_time(run.get("run_started_at"), "validation run run_started_at")
    updated = _parse_time(run.get("updated_at"), "validation run updated_at")
    if not created <= run_started <= updated:
        _fail("validation run timestamps are out of order")

    job_list = jobs.get("jobs")
    if jobs.get("total_count") != 1 or not isinstance(job_list, list) or len(job_list) != 1:
        _fail("validation run job mapping is ambiguous")
    job = job_list[0]
    if not isinstance(job, Mapping):
        _fail("validation job metadata is malformed")
    expected_job = {
        "id": validation["job_id"],
        "run_id": validation["run_id"],
        "run_attempt": validation["run_attempt"],
        "head_sha": validation["head_sha"],
        "name": AUTHORITATIVE_JOB,
        "status": "completed",
        "conclusion": "success",
    }
    for field, expected in expected_job.items():
        _expect(job.get(field), expected, f"validation job {field}")
    started = _parse_time(job.get("started_at"), "validation job started_at")
    completed = _parse_time(job.get("completed_at"), "validation job completed_at")
    if not run_started <= started <= completed <= updated:
        _fail("validation job timestamps are outside the run window")

    steps = job.get("steps")
    if not isinstance(steps, list):
        _fail("validation job steps are missing")
    seen_steps: dict[str, Mapping[str, Any]] = {}
    for step in steps:
        if not isinstance(step, Mapping) or not isinstance(step.get("name"), str):
            _fail("validation job step metadata is malformed")
        name = step["name"]
        if name in seen_steps:
            _fail(f"validation job has duplicate step {name!r}")
        seen_steps[name] = step
    missing = REQUIRED_SUCCESSFUL_STEPS - set(seen_steps)
    if missing:
        _fail(f"validation job is missing required step(s): {', '.join(sorted(missing))}")
    for name in REQUIRED_SUCCESSFUL_STEPS:
        _expect(seen_steps[name].get("status"), "completed", f"step {name} status")
        _expect(seen_steps[name].get("conclusion"), "success", f"step {name} conclusion")
    forbidden = [
        name for name in seen_steps
        if "pushover" in name.casefold() or "signal tracker" in name.casefold()
    ]
    if forbidden:
        _fail("controlled validation unexpectedly contains a notification step")
    return started, completed


def _validate_artifacts(
    descriptor: Mapping[str, Any],
    validation: Mapping[str, Any],
    metadata: Mapping[str, Any],
    archives: Mapping[str, Path],
    *,
    job_started: datetime,
    job_completed: datetime,
) -> dict[str, dict[str, bytes]]:
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, list) or metadata.get("total_count") != 2 or len(artifacts) != 2:
        _fail("validation run must contain exactly the state and diagnostic artifacts")
    by_id: dict[int, Mapping[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or type(artifact.get("id")) is not int:
            _fail("validation artifact metadata is malformed")
        if artifact["id"] in by_id:
            _fail("validation artifact metadata contains duplicate ids")
        by_id[artifact["id"]] = artifact

    loaded: dict[str, dict[str, bytes]] = {}
    for role in ("protected_state", "diagnostic_output"):
        pin = _artifact_pin(descriptor, role)
        artifact = by_id.get(pin["id"])
        if artifact is None:
            _fail(f"{role} artifact metadata is missing")
        for field in ("id", "name", "size_in_bytes", "digest", "expires_at"):
            _expect(artifact.get(field), pin[field], f"{role} artifact {field}")
        _expect(artifact.get("expired"), False, f"{role} artifact expired")
        source_run = artifact.get("workflow_run")
        if not isinstance(source_run, Mapping):
            _fail(f"{role} artifact workflow_run metadata is missing")
        for field, expected in {
            "id": validation["run_id"],
            "repository_id": REPOSITORY_ID,
            "head_repository_id": REPOSITORY_ID,
            "head_branch": "main",
            "head_sha": validation["head_sha"],
        }.items():
            _expect(source_run.get(field), expected, f"{role} artifact workflow_run {field}")
        created = _parse_time(artifact.get("created_at"), f"{role} artifact created_at")
        updated = _parse_time(artifact.get("updated_at"), f"{role} artifact updated_at")
        expires = _parse_time(artifact.get("expires_at"), f"{role} artifact expires_at")
        if not job_started <= created <= updated <= job_completed:
            _fail(f"{role} artifact timestamps are outside the producing job")
        if expires <= datetime.now(timezone.utc):
            _fail(f"{role} artifact has expired")
        archive = archives[role]
        if archive.stat().st_size != pin["size_in_bytes"]:
            _fail(f"{role} downloaded archive size mismatch")
        if f"sha256:{_sha256_file(archive)}" != pin["digest"]:
            _fail(f"{role} downloaded archive digest mismatch")
        loaded[role] = _archive_members(archive)
    return loaded


def _find_output_receipt(members: Mapping[str, bytes]) -> bytes:
    matches = [members[name] for name in OUTPUT_RECEIPT_PATHS if name in members]
    if len(matches) != 1:
        _fail("diagnostic artifact must contain one unambiguous source-status receipt")
    return matches[0]


def _find_output_restore_receipt(members: Mapping[str, bytes]) -> bytes:
    matches = [members[name] for name in OUTPUT_RESTORE_RECEIPT_PATHS if name in members]
    if len(matches) != 1:
        _fail("diagnostic artifact must contain one unambiguous restore receipt")
    return matches[0]


def _notification_eligible_count(result: Mapping[str, Any]) -> int:
    total = 0
    for field in ("transaction_counts", "pending_review_counts"):
        values = result.get(field)
        if not isinstance(values, Mapping):
            _fail(f"validation result {field} is missing")
        for source in ("house", "senate"):
            value = values.get(source, 0)
            if type(value) is not int or value < 0:
                _fail(f"validation result {field}.{source} is invalid")
            total += value
    return total


def _validate_durable_payloads(
    members: Mapping[str, Mapping[str, bytes]],
    *,
    expected_outcome: str,
    validation_revision: str,
    job_started: datetime,
    job_completed: datetime,
) -> dict[str, Any]:
    state_members = members["protected_state"]
    output_members = members["diagnostic_output"]
    missing_state = REQUIRED_STATE_MEMBERS - set(state_members)
    if missing_state:
        _fail(f"state artifact is missing: {', '.join(sorted(missing_state))}")
    if any("/" in name for name in state_members):
        _fail("state artifact contains an unexpected nested member")
    for required in (
        OUTPUT_RESULT_PATH,
        "legislative-latest-purchases.csv",
        "legislative-latest-transactions.csv",
        "legislative-latest-filings.csv",
    ):
        if required not in output_members:
            _fail(f"diagnostic artifact is missing {required}")

    state_receipt_bytes = state_members[STATE_RECEIPT_PATH]
    output_receipt_bytes = _find_output_receipt(output_members)
    if state_receipt_bytes != output_receipt_bytes:
        _fail("state and diagnostic artifacts contain different source-status receipts")
    state_restore_bytes = state_members[STATE_RESTORE_RECEIPT_PATH]
    output_restore_bytes = _find_output_restore_receipt(output_members)
    if state_restore_bytes != output_restore_bytes:
        _fail("state and diagnostic artifacts contain different restore receipts")
    receipt = _json_bytes(state_receipt_bytes, STATE_RECEIPT_PATH)
    restore = _json_bytes(state_restore_bytes, STATE_RESTORE_RECEIPT_PATH)
    state = _json_bytes(state_members[STATE_PATH], STATE_PATH)
    result = _json_bytes(output_members[OUTPUT_RESULT_PATH], OUTPUT_RESULT_PATH)
    if not all(isinstance(value, dict) for value in (receipt, restore, state, result)):
        _fail("validation receipts, state, and result must be JSON objects")

    if receipt.get("version") != 2:
        _fail("source-status receipt schema is not version 2")
    for field, expected in {
        "success": True,
        "notifications_suppressed": True,
        "validation_outcome": expected_outcome,
        "outbound_notifications_attempted": 0,
        "outbound_notifications_sent": 0,
    }.items():
        _expect(receipt.get(field), expected, f"source-status receipt {field}")
    _expect(
        receipt.get("state_sha256"),
        _sha256_bytes(state_members[STATE_PATH]),
        "source-status state_sha256",
    )
    _expect(
        receipt.get("result_sha256"),
        _sha256_bytes(output_members[OUTPUT_RESULT_PATH]),
        "source-status result_sha256",
    )
    _expect(
        receipt.get("restore_receipt_sha256"),
        _sha256_bytes(state_restore_bytes),
        "source-status restore_receipt_sha256",
    )

    _expect(restore.get("version"), 1, "restore receipt version")
    _expect(restore.get("repository_id"), REPOSITORY_ID, "restore receipt repository_id")
    _expect(restore.get("consumer_sha"), validation_revision, "restore receipt consumer_sha")
    _expect(
        restore.get("predecessor_artifact_name"),
        STATE_ARTIFACT_NAME,
        "restore receipt predecessor artifact name",
    )
    for field in (
        "predecessor_artifact_id",
        "predecessor_run_id",
        "predecessor_run_attempt",
        "predecessor_workflow_id",
    ):
        _positive_int(restore.get(field), f"restore receipt {field}")
    predecessor_digest = restore.get("predecessor_artifact_api_digest")
    if not isinstance(predecessor_digest, str) or not DIGEST_PATTERN.fullmatch(
        predecessor_digest
    ):
        _fail("restore receipt predecessor artifact digest is invalid")
    _expect(
        restore.get("downloaded_zip_sha256"),
        predecessor_digest.removeprefix("sha256:"),
        "restore receipt downloaded ZIP digest",
    )
    predecessor_head = restore.get("predecessor_head_sha")
    if not isinstance(predecessor_head, str) or not SHA_PATTERN.fullmatch(predecessor_head):
        _fail("restore receipt predecessor head revision is invalid")
    _expect(
        restore.get("predecessor_workflow_file"),
        "legislative_trade_tracker_v2.yml",
        "restore receipt predecessor workflow file",
    )
    _expect(
        restore.get("predecessor_workflow_name"),
        WORKFLOW_NAME,
        "restore receipt predecessor workflow name",
    )
    restored_state_sha256 = restore.get("restored_state_sha256")
    if not isinstance(restored_state_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", restored_state_sha256
    ):
        _fail("restore receipt state digest is invalid")

    statuses = result.get("source_statuses")
    counts = result.get("source_counts")
    if not isinstance(statuses, Mapping) or set(statuses) != {"house", "senate"}:
        _fail("validation result does not contain exact House and Senate statuses")
    if not isinstance(counts, Mapping):
        _fail("validation result source_counts is missing")
    if any(value not in {"ok", "blocked", "error"} for value in statuses.values()):
        _fail("validation result contains an unsupported source status")
    successful = [source for source in ("house", "senate") if statuses[source] == "ok"]
    if len(successful) not in {1, 2}:
        _fail("controlled validation has no successful official source")
    for source in successful:
        if type(counts.get(source)) is not int or counts[source] <= 0:
            _fail(f"controlled validation {source} catalog is empty or malformed")
    if len(successful) == 2:
        _expect(result.get("overall_status"), "ok", "validation result overall_status")
        _expect(result.get("discovery_complete"), True, "validation result discovery_complete")
    else:
        _expect(result.get("overall_status"), "degraded", "validation result overall_status")
        _expect(result.get("discovery_complete"), False, "validation result discovery_complete")
    _expect(result.get("success"), True, "validation result success")
    for field in ("success", "overall_status", "started_utc", "finished_utc"):
        _expect(receipt.get(field), result.get(field), f"receipt/result {field}")
    eligible_count = _notification_eligible_count(result)
    _expect(
        receipt.get("notification_eligible_new_records"),
        eligible_count,
        "source-status receipt notification_eligible_new_records",
    )
    final_state_sha256 = _sha256_bytes(state_members[STATE_PATH])
    if expected_outcome == "zero_change_successor":
        _expect(receipt.get("durable_state_eligible"), True, "source-status durable_state_eligible")
        _expect(eligible_count, 0, "zero-change notification-eligible records")
        _expect(receipt.get("rollback_performed"), False, "source-status rollback_performed")
        _expect(receipt.get("rollback_verified"), False, "source-status rollback_verified")
    else:
        _expect(receipt.get("durable_state_eligible"), False, "source-status durable_state_eligible")
        if eligible_count <= 0:
            _fail("notification-eligible rollback has no eligible records")
        _expect(receipt.get("rollback_performed"), True, "source-status rollback_performed")
        _expect(receipt.get("rollback_verified"), True, "source-status rollback_verified")
        _expect(
            receipt.get("published_predecessor_state_sha256"),
            restored_state_sha256,
            "source-status published predecessor digest",
        )
        _expect(
            final_state_sha256,
            restored_state_sha256,
            "rolled-back published state digest",
        )
        candidate_digest = receipt.get("discarded_candidate_state_sha256")
        if not isinstance(candidate_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", candidate_digest
        ):
            _fail("rollback receipt lacks the discarded candidate state digest")
        if candidate_digest == final_state_sha256:
            _fail("rollback candidate digest unexpectedly equals the predecessor state")
    alerted = result.get("alerted_filing_counts")
    if not isinstance(alerted, Mapping):
        _fail("validation result alerted_filing_counts is missing")
    for source in successful:
        if alerted.get(source) != 0:
            _fail(f"controlled validation recorded alerts for {source}")

    receipt_sources = receipt.get("sources")
    if not isinstance(receipt_sources, list) or len(receipt_sources) != 2:
        _fail("source-status receipt source entries are incomplete")
    indexed: dict[str, Mapping[str, Any]] = {}
    source_eligible_total = 0
    for item in receipt_sources:
        if not isinstance(item, Mapping) or item.get("source") not in {"house", "senate"}:
            _fail("source-status receipt source entry is malformed")
        source = item["source"]
        if source in indexed:
            _fail("source-status receipt contains duplicate sources")
        returncode = item.get("returncode")
        committed = item.get("state_committed")
        source_eligible = item.get("notification_eligible_new_records")
        if type(returncode) is not int or not isinstance(committed, bool):
            _fail(f"source-status receipt {source} outcome is malformed")
        if type(source_eligible) is not int or source_eligible < 0:
            _fail(f"source-status receipt {source} eligible count is malformed")
        _expect(item.get("status"), statuses[source], f"source-status receipt {source} status")
        if statuses[source] == "ok":
            if returncode != 0 or committed is not True:
                _fail(f"successful source {source} was not committed")
        elif returncode == 0 or committed is not False:
            _fail(f"failed source {source} was unexpectedly committed")
        indexed[source] = item
        source_eligible_total += source_eligible
    if set(indexed) != {"house", "senate"} or source_eligible_total != eligible_count:
        _fail("source-status receipt notification counts do not reconcile")

    if not (
        state.get("version") == 1
        and isinstance(state.get("last_success_utc"), str)
        and state["last_success_utc"].strip()
        and isinstance(state.get("seen_filings"), dict)
        and isinstance(state.get("seen_trades"), dict)
        and isinstance(state.get("seen_reviews"), dict)
    ):
        _fail("controlled validation state is incomplete")
    started = _parse_time(receipt.get("started_utc"), "source-status started_utc")
    finished = _parse_time(receipt.get("finished_utc"), "source-status finished_utc")
    if not job_started <= started <= finished <= job_completed:
        _fail("source-status receipt timestamps are outside the producing job")
    return {
        "overall_status": result["overall_status"],
        "successful_sources": successful,
        "validation_outcome": expected_outcome,
        "notification_eligible_new_records": eligible_count,
        "rollback_verified": expected_outcome == "notification_eligible_rollback",
        "state_sha256": receipt["state_sha256"],
        "result_sha256": receipt["result_sha256"],
        "started_utc": receipt["started_utc"],
        "finished_utc": receipt["finished_utc"],
    }


def _git(repository_root: Path, arguments: Sequence[str], *, text: bool = True) -> Any:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise LegislativeValidationError(
            f"git {' '.join(arguments)} failed for implementation continuity"
        ) from exc
    return completed.stdout


def _validate_implementation_continuity(
    *,
    repository_root: Path,
    validation_sha: str,
    control_revision: str,
    compare: Mapping[str, Any],
) -> dict[str, str]:
    if not SHA_PATTERN.fullmatch(control_revision):
        _fail("control revision is invalid")
    current = _git(repository_root, ["rev-parse", "HEAD"]).strip()
    _expect(current, control_revision, "checked-out control revision")
    _expect(compare.get("status"), "ahead", "validation/control ancestry status")
    base = compare.get("base_commit")
    head = compare.get("head_commit")
    merge_base = compare.get("merge_base_commit")
    if not all(isinstance(value, Mapping) for value in (base, head, merge_base)):
        _fail("GitHub compare metadata is incomplete")
    _expect(base.get("sha"), validation_sha, "compare base revision")
    _expect(head.get("sha"), control_revision, "compare head revision")
    _expect(merge_base.get("sha"), validation_sha, "compare merge-base revision")
    ahead_by = compare.get("ahead_by")
    if type(ahead_by) is not int or ahead_by <= 0:
        _fail("schedule-restoration revision is not after the validation revision")

    hashes: dict[str, str] = {}
    for relative in IMPLEMENTATION_PATHS:
        validation_bytes = _normalized_source(_git(
            repository_root,
            ["show", f"{validation_sha}:{relative}"],
            text=False,
        ), f"{validation_sha}:{relative}")
        control_bytes = _normalized_source(_git(
            repository_root,
            ["show", f"{control_revision}:{relative}"],
            text=False,
        ), f"{control_revision}:{relative}")
        try:
            current_bytes = _normalized_source(
                (repository_root / relative).read_bytes(), relative
            )
        except OSError as exc:
            raise LegislativeValidationError(
                f"current implementation file {relative} is unavailable"
            ) from exc
        if validation_bytes != control_bytes:
            _fail(f"Legislative implementation changed after validation: {relative}")
        if current_bytes != control_bytes:
            _fail(f"checked-out implementation differs from control revision: {relative}")
        hashes[relative] = _sha256_bytes(control_bytes)

    validation_workflow = _git(
        repository_root,
        ["show", f"{validation_sha}:{WORKFLOW_PATH}"],
        text=False,
    )
    if b"--no-notify" not in validation_workflow:
        _fail("validation workflow source did not force --no-notify")
    for forbidden in (
        b"PUSHOVER_API_TOKEN",
        b"PUSHOVER_USER_KEY",
        b"LEGISLATIVE_HEALTHCHECKS_PING_URL",
    ):
        if forbidden in validation_workflow:
            _fail("validation workflow source exposed notification credentials")
    if b"--require-notifications-suppressed" not in validation_workflow:
        _fail("validation workflow source did not gate notification suppression")
    if b"--require-no-notification-eligible-records" not in validation_workflow:
        _fail("validation workflow source did not gate notification-eligible changes")
    return hashes


def verify(arguments: argparse.Namespace) -> dict[str, Any]:
    descriptor = _load_object(arguments.descriptor)
    validation = _validate_descriptor(descriptor)
    run = _load_object(arguments.run_metadata)
    jobs = _load_object(arguments.jobs_metadata)
    artifacts = _load_object(arguments.artifacts_metadata)
    compare = _load_object(arguments.compare_metadata)
    job_started, job_completed = _validate_run_and_job(
        descriptor, validation, run, jobs
    )
    members = _validate_artifacts(
        descriptor,
        validation,
        artifacts,
        {
            "protected_state": arguments.state_archive,
            "diagnostic_output": arguments.output_archive,
        },
        job_started=job_started,
        job_completed=job_completed,
    )
    payload = _validate_durable_payloads(
        members,
        expected_outcome=validation["expected_outcome"],
        validation_revision=validation["head_sha"],
        job_started=job_started,
        job_completed=job_completed,
    )
    implementation = _validate_implementation_continuity(
        repository_root=arguments.repository_root,
        validation_sha=validation["head_sha"],
        control_revision=arguments.control_revision,
        compare=compare,
    )
    descriptor_digest = _sha256_file(arguments.descriptor)
    return {
        "schema_version": 1,
        "result": "legislative_controlled_validation_verified",
        "repository_id": REPOSITORY_ID,
        "validation_run_id": validation["run_id"],
        "validation_run_attempt": validation["run_attempt"],
        "validation_job_id": validation["job_id"],
        "validation_revision": validation["head_sha"],
        "schedule_restoration_revision": arguments.control_revision,
        "validation_revision_is_ancestor": True,
        "implementation_source_continuity_verified": True,
        "implementation_sha256": implementation,
        "state_artifact_id": descriptor["artifacts"]["protected_state"]["id"],
        "output_artifact_id": descriptor["artifacts"]["diagnostic_output"]["id"],
        "artifact_digests_verified": True,
        "safe_archive_contents_verified": True,
        "source_status_receipt_verified": True,
        "controlled_validation_outcome": payload["validation_outcome"],
        "notifications_suppressed": True,
        "no_outbound_notifications_verified": True,
        "notification_eligible_new_records": payload["notification_eligible_new_records"],
        "zero_notification_eligible_changes_verified": (
            payload["validation_outcome"] == "zero_change_successor"
        ),
        "predecessor_state_rollback_verified": payload["rollback_verified"],
        "overall_status": payload["overall_status"],
        "successful_sources": payload["successful_sources"],
        "state_sha256": payload["state_sha256"],
        "result_sha256": payload["result_sha256"],
        "descriptor_sha256": descriptor_digest,
        "additional_validation_run_authorized": False,
        "production_authority_transferred": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--jobs-metadata", type=Path, required=True)
    parser.add_argument("--artifacts-metadata", type=Path, required=True)
    parser.add_argument("--state-archive", type=Path, required=True)
    parser.add_argument("--output-archive", type=Path, required=True)
    parser.add_argument("--compare-metadata", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--control-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        receipt = verify(arguments)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (LegislativeValidationError, OSError) as exc:
        print(f"LegislativeValidationError: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
