"""Issue a Phase 4 certificate from pinned, immutable shadow-run evidence.

The normal Phase 4 validator intentionally requires the live baseline to equal
the recovered legacy anchor.  Two failed controller runs legitimately advanced
that baseline before the second run completed two clean shadow cycles.  This
module preserves the original anchor and proves the complete artifact chain
instead of changing the anchor or executing the producers again.
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
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from validate_runtime_promotion import (  # noqa: E402
    CYCLE_ORDER,
    NAMESPACES,
    PromotionValidationError,
    _assert_head_transition,
    _assert_inputs,
    _assert_inventory_baseline,
    _base_cleanup,
    _base_preflight,
    _copy_heads,
    _heads,
    _latest_runs,
    _parse_time,
    _required_true,
    _validate_sequence,
)

REPOSITORY_ID = 1349678672
REPOSITORY = "maglothinm/MyETF-Intelligence"
REQUIRED_ARCHIVE_FILES = (
    "baseline.json",
    "manifest.json",
    "observations.ndjson",
    "cleanup.json",
)
HISTORICAL_CONTROL_FILES = (
    "deploy/runtime-v2/runtime_promotion_control.sh",
    "deploy/runtime-v2/runtime_promotion_observed_state.sh",
    "deploy/runtime-v2/validate_runtime_promotion.py",
)
CURRENT_BOUND_EVIDENCE_FILES = (
    "deploy/runtime-v2/phase4-approved-image.json",
    "deploy/runtime-v2/phase4-legacy-run-inventory.json",
)
CONTROL_FILES = HISTORICAL_CONTROL_FILES + CURRENT_BOUND_EVIDENCE_FILES
MAX_ARCHIVE_FILE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 50 * 1024 * 1024


def _reject_constant(value: str) -> None:
    raise PromotionValidationError(f"non-finite JSON value {value!r} is not permitted")


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PromotionValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json_text(text: str, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromotionValidationError(f"{label} is not valid UTF-8 JSON") from exc


def _load_object(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromotionValidationError(f"unable to read {path}") from exc
    value = _json_text(text, str(path))
    if not isinstance(value, dict):
        raise PromotionValidationError(f"{path} is not a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_text_bytes_sha256(data: bytes, label: str) -> str:
    if b"\x00" in data:
        raise PromotionValidationError(f"control file {label} is not text")
    data = data.replace(b"\r\n", b"\n")
    if b"\r" in data:
        raise PromotionValidationError(f"control file {label} has unsupported line endings")
    return hashlib.sha256(data).hexdigest()


def _assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise PromotionValidationError(f"{label} mismatch")


def _archive_members(archive: Path) -> dict[str, bytes]:
    if not zipfile.is_zipfile(archive):
        raise PromotionValidationError(f"{archive} is not a ZIP archive")
    members: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            raw_name = info.filename
            if "\x00" in raw_name or "\\" in raw_name:
                raise PromotionValidationError("archive contains an unsafe member name")
            member = PurePosixPath(raw_name)
            if member.is_absolute() or any(part in {"", ".", ".."} for part in member.parts):
                raise PromotionValidationError("archive contains an unsafe member path")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise PromotionValidationError("archive contains a symbolic link")
            if info.flag_bits & 0x1:
                raise PromotionValidationError("archive contains an encrypted member")
            if info.is_dir():
                continue
            name = member.as_posix()
            if name in members:
                raise PromotionValidationError(f"archive contains duplicate member {name}")
            if info.file_size > MAX_ARCHIVE_FILE_BYTES:
                raise PromotionValidationError(f"archive member {name} is too large")
            total += info.file_size
            if total > MAX_ARCHIVE_TOTAL_BYTES:
                raise PromotionValidationError("archive expands beyond the evidence limit")
            members[name] = bundle.read(info)
    return members


def _decode_member(members: Mapping[str, bytes], name: str) -> str:
    value = members.get(name)
    if value is None:
        raise PromotionValidationError(f"artifact is missing {name}")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromotionValidationError(f"artifact member {name} is not UTF-8") from exc


def _load_artifact(archive: Path, pin: Mapping[str, Any]) -> dict[str, Any]:
    expected_size = pin.get("artifact_size_in_bytes")
    if not isinstance(expected_size, int) or archive.stat().st_size != expected_size:
        raise PromotionValidationError(f"artifact {pin.get('artifact_id')} size mismatch")
    expected_digest = pin.get("artifact_digest")
    if not isinstance(expected_digest, str) or expected_digest != f"sha256:{_sha256(archive)}":
        raise PromotionValidationError(f"artifact {pin.get('artifact_id')} digest mismatch")

    members = _archive_members(archive)
    for name in REQUIRED_ARCHIVE_FILES:
        if name not in members:
            raise PromotionValidationError(f"artifact is missing {name}")
    if "phase4-ready.json" in members or "phase4-ready.sha256" in members:
        raise PromotionValidationError("failed source artifact unexpectedly contains a certificate")

    baseline = _json_text(_decode_member(members, "baseline.json"), "baseline.json")
    manifest = _json_text(_decode_member(members, "manifest.json"), "manifest.json")
    cleanup = _json_text(_decode_member(members, "cleanup.json"), "cleanup.json")
    if not all(isinstance(item, dict) for item in (baseline, manifest, cleanup)):
        raise PromotionValidationError("artifact baseline, manifest, or cleanup is not an object")
    if cleanup.get("result") != "phase4_cleanup_started":
        raise PromotionValidationError("artifact lacks fail-closed cleanup evidence")

    observations: list[Any] = []
    for number, line in enumerate(_decode_member(members, "observations.ndjson").splitlines(), start=1):
        if not line.strip():
            continue
        value = _json_text(line, f"observations.ndjson line {number}")
        if not isinstance(value, dict):
            raise PromotionValidationError(f"observation line {number} is not an object")
        observations.append(value)
    if manifest.get("executions") != observations:
        raise PromotionValidationError("manifest executions differ from observations.ndjson")
    return {
        "baseline": baseline,
        "manifest": manifest,
        "observations": observations,
        "archive_sha256": _sha256(archive),
    }


def _validate_metadata(
    *,
    pin: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    run: Mapping[str, Any],
    artifact: Mapping[str, Any],
    jobs: Mapping[str, Any],
) -> None:
    workflow = descriptor.get("workflow")
    if not isinstance(workflow, dict):
        raise PromotionValidationError("reconciliation workflow pin is missing")
    expected_run = {
        "id": pin.get("run_id"),
        "run_number": pin.get("run_number"),
        "run_attempt": pin.get("run_attempt"),
        "workflow_id": workflow.get("id"),
        "name": workflow.get("name"),
        "path": workflow.get("path"),
        "event": pin.get("event"),
        "head_branch": "main",
        "head_sha": pin.get("head_sha"),
        "status": "completed",
        "conclusion": pin.get("conclusion"),
    }
    for key, expected in expected_run.items():
        _assert_equal(run.get(key), expected, f"source run {pin.get('run_id')} {key}")
    for key in ("repository", "head_repository"):
        value = run.get(key)
        if not isinstance(value, dict) or value.get("id") != REPOSITORY_ID:
            raise PromotionValidationError(f"source run {pin.get('run_id')} {key} boundary mismatch")

    expected_artifact = {
        "id": pin.get("artifact_id"),
        "name": pin.get("artifact_name"),
        "size_in_bytes": pin.get("artifact_size_in_bytes"),
        "digest": pin.get("artifact_digest"),
        "expires_at": pin.get("artifact_expires_at"),
        "expired": False,
    }
    for key, expected in expected_artifact.items():
        _assert_equal(artifact.get(key), expected, f"artifact {pin.get('artifact_id')} {key}")
    source_run = artifact.get("workflow_run")
    if not isinstance(source_run, dict):
        raise PromotionValidationError("artifact workflow_run metadata is missing")
    for key, expected in {
        "id": pin.get("run_id"),
        "repository_id": REPOSITORY_ID,
        "head_repository_id": REPOSITORY_ID,
        "head_branch": "main",
        "head_sha": pin.get("head_sha"),
    }.items():
        _assert_equal(source_run.get(key), expected, f"artifact workflow_run {key}")

    job_list = jobs.get("jobs")
    if jobs.get("total_count") != 1 or not isinstance(job_list, list) or len(job_list) != 1:
        raise PromotionValidationError(f"source run {pin.get('run_id')} job mapping is ambiguous")
    job = job_list[0]
    if not isinstance(job, dict):
        raise PromotionValidationError("source workflow job metadata is malformed")
    for key, expected in {
        "id": pin.get("job_id"),
        "name": "controlled-shadow-acceptance",
        "status": "completed",
        "conclusion": "failure",
    }.items():
        _assert_equal(job.get(key), expected, f"source job {pin.get('job_id')} {key}")
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise PromotionValidationError("source workflow steps are missing")
    step_results: dict[str, str] = {}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("name"), str):
            raise PromotionValidationError("source workflow step metadata is malformed")
        if step["name"] in step_results:
            raise PromotionValidationError(f"source workflow has duplicate step {step['name']}")
        step_results[step["name"]] = step.get("conclusion")
    expected_steps = {
        "Execute two serialized, evidence-bound shadow cycles": "failure",
        "Fail-closed cleanup and evidence check": "success",
        "Upload Phase 4 readiness evidence": "success",
    }
    for name, conclusion in expected_steps.items():
        _assert_equal(step_results.get(name), conclusion, f"source run {pin.get('run_id')} step {name}")


def _validate_control_files(
    descriptor: Mapping[str, Any], repository_root: Path, evidence_revision: str
) -> None:
    raw = descriptor.get("control_files")
    if not isinstance(raw, dict) or tuple(sorted(raw)) != tuple(sorted(CONTROL_FILES)):
        raise PromotionValidationError("reconciliation control-file set changed")
    root = repository_root.resolve()
    for relative in CONTROL_FILES:
        expected = raw.get(relative)
        if not isinstance(expected, str) or len(expected) != 64:
            raise PromotionValidationError(f"control file {relative} has no pinned digest")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PromotionValidationError(f"control path {relative} escapes the repository") from exc
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "show", f"{evidence_revision}:{relative}"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise PromotionValidationError("unable to read the evidence-control revision") from exc
        if result.returncode != 0:
            raise PromotionValidationError(
                f"control file {relative} is missing from the evidence revision"
            )
        if _normalized_text_bytes_sha256(result.stdout, relative) != expected:
            raise PromotionValidationError(f"control file {relative} differs from the evidence revision")
        if relative in CURRENT_BOUND_EVIDENCE_FILES:
            try:
                current_data = path.read_bytes()
            except OSError as exc:
                raise PromotionValidationError(f"unable to read current evidence file {relative}") from exc
            if _normalized_text_bytes_sha256(current_data, relative) != expected:
                raise PromotionValidationError(
                    f"current evidence file {relative} differs from the evidence revision"
                )


def _validate_phase4_guards(manifest: Mapping[str, Any], label: str) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("phase") != "phase4":
        raise PromotionValidationError(f"{label} manifest identity mismatch")
    preflight = manifest.get("preflight")
    cleanup = manifest.get("cleanup")
    if not isinstance(preflight, dict) or not isinstance(cleanup, dict):
        raise PromotionValidationError(f"{label} preflight or cleanup evidence is missing")
    _base_preflight(preflight)
    _required_true(preflight, ("legacy_production_route_active",), f"{label} preflight")
    _base_cleanup(cleanup)
    _required_true(
        cleanup,
        ("producer_schedulers_paused", "web_public_invoker_absent", "legacy_production_route_active"),
        f"{label} cleanup",
    )


def _assert_observation_labels(observations: list[Any], label: str) -> None:
    expected = [name for _ in range(2) for name in CYCLE_ORDER]
    if len(observations) != len(expected):
        raise PromotionValidationError(f"{label} expected eight observations")
    for index, (observation, job) in enumerate(zip(observations, expected), start=1):
        if not isinstance(observation, dict):
            raise PromotionValidationError(f"{label} observation {index} is not an object")
        if observation.get("sequence") != index:
            raise PromotionValidationError(f"{label} observation sequence {index} mismatch")
        if observation.get("cycle") != ((index - 1) // len(CYCLE_ORDER)) + 1:
            raise PromotionValidationError(f"{label} observation cycle {index} mismatch")
        if observation.get("job") != job:
            raise PromotionValidationError(f"{label} observation {index} job mismatch")
        execution = observation.get("cloud_run_execution")
        if not isinstance(execution, str) or not execution.startswith(f"polititrack-{job}-"):
            raise PromotionValidationError(f"{label} observation {index} execution binding mismatch")


def _same_heads(
    left: Mapping[str, Mapping[str, Any]], right: Mapping[str, Mapping[str, Any]], label: str
) -> None:
    for namespace in NAMESPACES:
        if left[namespace] != right[namespace]:
            raise PromotionValidationError(f"{label} {namespace} head mismatch")


def _validate_success_run(
    *,
    job: str,
    run: Mapping[str, Any],
    previous_heads: Mapping[str, Mapping[str, Any]],
    current_heads: Mapping[str, Mapping[str, Any]],
    runtime_source_revision: str,
) -> None:
    _assert_head_transition(previous_heads, current_heads, job)
    if run.get("snapshot_generation") != current_heads[job].get("generation"):
        raise PromotionValidationError(f"{job} run generation does not match its head")
    if run.get("snapshot_sha256") != current_heads[job].get("snapshot_sha256"):
        raise PromotionValidationError(f"{job} run digest does not match its head")
    provenance = current_heads[job].get("provenance") or {}
    for key, expected in {
        "authority": "runtime_v2",
        "job": job,
        "mode": "shadow",
        "trigger_source": "shadow",
    }.items():
        if provenance.get(key) != expected:
            raise PromotionValidationError(f"{job} snapshot provenance {key} mismatch")
    if current_heads[job].get("source_revision") != runtime_source_revision:
        raise PromotionValidationError(f"{job} head source revision mismatch")
    _assert_inputs(job, current_heads)


def _validate_partial_history(
    *,
    baseline: Mapping[str, Any],
    observations: list[Any],
    pin: Mapping[str, Any],
    runtime_source_revision: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Any]:
    _assert_observation_labels(observations, "anchored partial history")
    expected_failures = pin.get("expected_failed_receipts")
    if not isinstance(expected_failures, list):
        raise PromotionValidationError("partial-history failure pins are missing")
    failure_by_sequence = {
        item.get("sequence"): item for item in expected_failures if isinstance(item, dict)
    }
    if len(failure_by_sequence) != len(expected_failures):
        raise PromotionValidationError("partial-history failure pins are ambiguous")

    previous_heads = _copy_heads(baseline)
    previous_finished = None
    executions: set[str] = set()
    run_ids: set[str] = set()
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, observation in enumerate(observations, start=1):
        job = observation["job"]
        execution = observation["cloud_run_execution"]
        if execution in executions:
            raise PromotionValidationError(f"duplicate Cloud Run execution {execution}")
        executions.add(execution)
        status = observation.get("status")
        if not isinstance(status, dict):
            raise PromotionValidationError(f"partial-history {job} observation has no status")
        current_heads = _heads(status)
        run = _latest_runs(status).get(job)
        if not run:
            raise PromotionValidationError(f"partial-history {job} latest run is missing")
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id or run_id in run_ids:
            raise PromotionValidationError(f"partial-history {job} run receipt is missing or duplicate")
        run_ids.add(run_id)
        if run.get("runtime_mode") != "shadow" or run.get("runtime_mode_verified") is not True:
            raise PromotionValidationError(f"partial-history {job} lacks verified shadow mode")
        if run.get("trigger_source") != "shadow" or run.get("side_effects_possible") is not False:
            raise PromotionValidationError(f"partial-history {job} shadow-safety evidence mismatch")
        if run.get("source_revision") != runtime_source_revision:
            raise PromotionValidationError(f"partial-history {job} source revision mismatch")
        started = _parse_time(run.get("started_at"), f"partial-history {job} started_at")
        finished = _parse_time(run.get("finished_at"), f"partial-history {job} finished_at")
        if finished < started or (previous_finished is not None and started < previous_finished):
            raise PromotionValidationError(f"partial-history {job} overlapped the preceding writer")
        previous_finished = finished

        expected_failure = failure_by_sequence.get(index)
        if expected_failure is None:
            if run.get("status") != "success":
                raise PromotionValidationError(f"partial-history {job} unexpectedly failed")
            _validate_success_run(
                job=job,
                run=run,
                previous_heads=previous_heads,
                current_heads=current_heads,
                runtime_source_revision=runtime_source_revision,
            )
            successes.append(
                {
                    "sequence": index,
                    "job": job,
                    "cloud_run_execution": execution,
                    "run_id": run_id,
                    "generation": current_heads[job]["generation"],
                    "snapshot_sha256": current_heads[job]["snapshot_sha256"],
                }
            )
        else:
            for key, actual in {
                "job": job,
                "cloud_run_execution": execution,
                "run_id": run_id,
            }.items():
                _assert_equal(actual, expected_failure.get(key), f"partial-history failure {index} {key}")
            if run.get("status") != "failure" or run.get("error_code") != "CalledProcessError":
                raise PromotionValidationError(f"partial-history failure {index} classification mismatch")
            mode_evidence = run.get("runtime_mode_evidence")
            if not isinstance(mode_evidence, dict) or mode_evidence.get("kind") != "runner_explicit":
                raise PromotionValidationError(f"partial-history failure {index} mode evidence mismatch")
            for key in ("parent_sha256", "snapshot_created_at", "snapshot_generation", "snapshot_id", "snapshot_sha256"):
                if run.get(key) is not None:
                    raise PromotionValidationError(f"partial-history failure {index} unexpectedly wrote a snapshot")
            _same_heads(previous_heads, current_heads, f"partial-history failure {index}")
            failures.append(
                {
                    "sequence": index,
                    "job": job,
                    "cloud_run_execution": execution,
                    "run_id": run_id,
                    "status": "failure",
                    "snapshot_written": False,
                    "side_effects_possible": False,
                }
            )
        previous_heads = {name: dict(value) for name, value in current_heads.items()}

    if len(successes) != pin.get("expected_successful_receipts"):
        raise PromotionValidationError("partial-history successful receipt count mismatch")
    if len(failures) != len(expected_failures):
        raise PromotionValidationError("partial-history failed receipt count mismatch")
    return previous_heads, successes, failures, previous_finished


def _head_summary(heads: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "generation": heads[name]["generation"],
            "snapshot_sha256": heads[name]["snapshot_sha256"],
        }
        for name in NAMESPACES
    }


def _assert_current_state(
    *,
    current_status: Mapping[str, Any],
    final_heads: Mapping[str, Mapping[str, Any]],
    receipts: list[dict[str, Any]],
    runtime_source_revision: str,
) -> None:
    current_heads = _heads(current_status)
    for namespace in NAMESPACES:
        for key in ("generation", "snapshot_sha256"):
            if current_heads[namespace].get(key) != final_heads[namespace].get(key):
                raise PromotionValidationError(f"current {namespace} {key} differs from replayed history")
    current_runs = _latest_runs(current_status)
    if tuple(sorted(current_runs)) != tuple(sorted(NAMESPACES)):
        raise PromotionValidationError("current status lacks exact latest producer receipts")
    expected_runs = {item["job"]: item for item in receipts[-len(NAMESPACES) :]}
    for namespace in NAMESPACES:
        run = current_runs[namespace]
        expected = expected_runs[namespace]
        for key, value in {
            "run_id": expected["run_id"],
            "status": "success",
            "runtime_mode": "shadow",
            "runtime_mode_verified": True,
            "trigger_source": "shadow",
            "side_effects_possible": False,
            "source_revision": runtime_source_revision,
            "snapshot_generation": final_heads[namespace]["generation"],
            "snapshot_sha256": final_heads[namespace]["snapshot_sha256"],
        }.items():
            if run.get(key) != value:
                raise PromotionValidationError(f"current {namespace} latest receipt {key} mismatch")


def _validate_current_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != 1 or manifest.get("phase") != "phase4_reconciliation":
        raise PromotionValidationError("current reconciliation manifest identity mismatch")
    preflight = manifest.get("preflight")
    cleanup = manifest.get("cleanup")
    if not isinstance(preflight, dict) or not isinstance(cleanup, dict):
        raise PromotionValidationError("current reconciliation guards are missing")
    _base_preflight(preflight)
    _required_true(
        preflight,
        (
            "legacy_production_route_active",
            "legacy_route_source_verified",
            "current_status_captured",
            "runtime_shadow_mode_verified",
        ),
        "current reconciliation preflight",
    )
    if preflight.get("evidence_control_files_verified") is not False:
        raise PromotionValidationError(
            "current reconciliation preflight must not pre-claim evidence control verification"
        )
    _base_cleanup(cleanup)
    _required_true(
        cleanup,
        (
            "producer_schedulers_paused",
            "web_public_invoker_absent",
            "legacy_production_route_active",
            "runtime_shadow_mode_verified",
            "no_producer_execution_performed",
        ),
        "current reconciliation cleanup",
    )


def reconcile_phase4(
    *,
    descriptor: dict[str, Any],
    inventory: dict[str, Any],
    repository_root: Path,
    current_status: dict[str, Any],
    current_manifest: dict[str, Any],
    control_revision: str,
    runtime_source_revision: str,
    image: str,
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    for key, expected in {
        "schema_version": 1,
        "result": "phase4_shadow_evidence_reconciliation_authorized",
        "repository_id": REPOSITORY_ID,
        "repository": REPOSITORY,
        "runtime_source_revision": runtime_source_revision,
        "immutable_inventory_preserved": True,
        "additional_producer_execution_authorized": False,
        "production_authority_transferred": False,
    }.items():
        _assert_equal(descriptor.get(key), expected, f"reconciliation descriptor {key}")
    if not isinstance(control_revision, str) or re.fullmatch(r"[0-9a-f]{40}", control_revision) is None:
        raise PromotionValidationError("current control revision is invalid")
    evidence_revision = descriptor.get("evidence_control_revision")
    if not isinstance(evidence_revision, str) or re.fullmatch(r"[0-9a-f]{40}", evidence_revision) is None:
        raise PromotionValidationError("evidence control revision is invalid")
    if not isinstance(image, str) or re.search(r"@sha256:[0-9a-f]{64}$", image) is None:
        raise PromotionValidationError("approved image is not immutable")
    _validate_control_files(descriptor, repository_root, evidence_revision)
    _validate_current_manifest(current_manifest)

    pins = descriptor.get("runs")
    if not isinstance(pins, list) or len(pins) != 2:
        raise PromotionValidationError("reconciliation requires exactly two pinned source runs")
    pin_by_role = {item.get("role"): item for item in pins if isinstance(item, dict)}
    expected_roles = {"anchored_partial_history", "completed_two_cycle_history"}
    if set(pin_by_role) != expected_roles:
        raise PromotionValidationError("reconciliation source-run roles changed")
    _assert_equal(
        evidence_revision,
        pin_by_role["completed_two_cycle_history"].get("head_sha"),
        "reconciliation evidence control revision",
    )

    loaded: dict[str, dict[str, Any]] = {}
    for role in ("anchored_partial_history", "completed_two_cycle_history"):
        pin = pin_by_role[role]
        source = sources.get(role)
        if not isinstance(source, Mapping):
            raise PromotionValidationError(f"reconciliation source {role} is missing")
        run = source.get("run")
        artifact = source.get("artifact")
        jobs = source.get("jobs")
        archive = source.get("archive")
        if not all(isinstance(value, Mapping) for value in (run, artifact, jobs)) or not isinstance(archive, Path):
            raise PromotionValidationError(f"reconciliation source {role} is incomplete")
        _validate_metadata(pin=pin, descriptor=descriptor, run=run, artifact=artifact, jobs=jobs)
        loaded[role] = _load_artifact(archive, pin)
        _validate_phase4_guards(loaded[role]["manifest"], role)

    partial = loaded["anchored_partial_history"]
    partial_baseline_heads = _heads(partial["baseline"])
    _assert_inventory_baseline(partial_baseline_heads, inventory)
    partial_final, partial_successes, partial_failures, partial_finished = _validate_partial_history(
        baseline=partial["baseline"],
        observations=partial["observations"],
        pin=pin_by_role["anchored_partial_history"],
        runtime_source_revision=runtime_source_revision,
    )

    complete = loaded["completed_two_cycle_history"]
    complete_baseline_heads = _heads(complete["baseline"])
    _same_heads(partial_final, complete_baseline_heads, "cross-artifact chain")
    _assert_observation_labels(complete["observations"], "completed two-cycle history")
    final_heads, receipts = _validate_sequence(
        baseline=complete["baseline"],
        observations=complete["observations"],
        expected_mode="shadow",
        expected_trigger="shadow",
        cycles=2,
        runtime_source_revision=runtime_source_revision,
    )
    if len(receipts) != pin_by_role["completed_two_cycle_history"].get("expected_successful_receipts"):
        raise PromotionValidationError("completed-history receipt count mismatch")
    first_complete_run = _latest_runs(complete["observations"][0]["status"])[CYCLE_ORDER[0]]
    if partial_finished is not None and _parse_time(
        first_complete_run.get("started_at"), "completed-history first started_at"
    ) < partial_finished:
        raise PromotionValidationError("source artifacts contain overlapping writer history")
    all_executions = [item["cloud_run_execution"] for item in partial_successes + partial_failures + receipts]
    all_run_ids = [item["run_id"] for item in partial_successes + partial_failures + receipts]
    if len(set(all_executions)) != len(all_executions) or len(set(all_run_ids)) != len(all_run_ids):
        raise PromotionValidationError("source artifacts reuse an execution or Runtime run receipt")

    expected_final = descriptor.get("expected_final_heads")
    if not isinstance(expected_final, dict) or _head_summary(final_heads) != expected_final:
        raise PromotionValidationError("replayed final heads differ from the pinned reconciliation result")
    _assert_current_state(
        current_status=current_status,
        final_heads=final_heads,
        receipts=receipts,
        runtime_source_revision=runtime_source_revision,
    )

    descriptor_digest = hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "result": "phase4_ready_for_phase5",
        "repository_id": REPOSITORY_ID,
        "control_revision": control_revision,
        "runtime_source_revision": runtime_source_revision,
        "immutable_image": image,
        "controlled_shadow_cycles": 2,
        "unique_successful_execution_receipts": len(receipts),
        "executions": receipts,
        "baseline_heads": _head_summary(complete_baseline_heads),
        "final_heads": _head_summary(final_heads),
        "runtime_mode": "shadow",
        "external_delivery_suppressed": True,
        "healthchecks_suppressed": True,
        "schedulers_paused": True,
        "cloud_sql_private_only": True,
        "web_public_invoker_absent": True,
        "legacy_production_route_active": True,
        "temporary_authority_removed": True,
        "production_authority_transferred": False,
        "phase5_ready": True,
        "reconciliation": {
            "kind": "artifact_pinned_failed_run_replay",
            "descriptor_sha256": descriptor_digest,
            "evidence_control_revision": descriptor["evidence_control_revision"],
            "control_files_match_evidence_revision": True,
            "immutable_inventory_preserved": True,
            "immutable_anchor_heads": _head_summary(partial_baseline_heads),
            "cross_artifact_chain_verified": True,
            "completed_two_cycle_history_verified": True,
            "current_heads_verified": True,
            "current_latest_receipts_verified": True,
            "additional_producer_execution_performed": False,
            "historical_prefix_successful_receipts": len(partial_successes),
            "historical_prefix_failed_receipts": partial_failures,
            "source_runs": [
                {
                    "role": role,
                    "run_id": pin_by_role[role]["run_id"],
                    "run_attempt": pin_by_role[role]["run_attempt"],
                    "head_sha": pin_by_role[role]["head_sha"],
                    "artifact_id": pin_by_role[role]["artifact_id"],
                    "artifact_sha256": loaded[role]["archive_sha256"],
                }
                for role in ("anchored_partial_history", "completed_two_cycle_history")
            ],
        },
    }


def _source(arguments: argparse.Namespace, prefix: str) -> dict[str, Any]:
    return {
        "run": _load_object(getattr(arguments, f"{prefix}_run_metadata")),
        "artifact": _load_object(getattr(arguments, f"{prefix}_artifact_metadata")),
        "jobs": _load_object(getattr(arguments, f"{prefix}_jobs_metadata")),
        "archive": getattr(arguments, f"{prefix}_archive"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--descriptor", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--current-status", type=Path, required=True)
    parser.add_argument("--current-manifest", type=Path, required=True)
    parser.add_argument("--control-revision", required=True)
    parser.add_argument("--runtime-source-revision", required=True)
    parser.add_argument("--image", required=True)
    for prefix in ("run6", "run7"):
        parser.add_argument(f"--{prefix}-run-metadata", type=Path, required=True)
        parser.add_argument(f"--{prefix}-artifact-metadata", type=Path, required=True)
        parser.add_argument(f"--{prefix}-jobs-metadata", type=Path, required=True)
        parser.add_argument(f"--{prefix}-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = reconcile_phase4(
        descriptor=_load_object(args.descriptor),
        inventory=_load_object(args.inventory),
        repository_root=args.repository_root,
        current_status=_load_object(args.current_status),
        current_manifest=_load_object(args.current_manifest),
        control_revision=args.control_revision,
        runtime_source_revision=args.runtime_source_revision,
        image=args.image,
        sources={
            "anchored_partial_history": _source(args, "run6"),
            "completed_two_cycle_history": _source(args, "run7"),
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
