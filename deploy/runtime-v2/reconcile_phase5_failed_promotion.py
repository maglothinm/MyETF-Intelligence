#!/usr/bin/env python3
"""Reconcile the 2026-09-05 failed Phase 5 promotion without rebaselining.

The first Phase 5 attempt advanced all four Runtime v2 heads, but a concurrent
legacy AI writer violated the global one-writer interval.  Its four otherwise
valid smoke observations are therefore only a forensic, invalidated prefix.  A
completion receipt may be issued only after a new, non-overlapping four-job
cycle starts at that prefix's exact final heads and the terminal cutover guards
all pass.

Every cloud input to this module is downloaded by the calling workflow.  This
module performs no network access and never restores, imports, or writes
production state.
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
from typing import Any, Iterable, Mapping, Sequence

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from validate_runtime_promotion import (  # noqa: E402
    LEGACY_WORKFLOWS,
    NAMESPACES,
    PRODUCER_SCHEDULERS,
    PromotionValidationError,
    _base_cleanup,
    _base_preflight,
    _heads,
    _latest_runs,
    _parse_time,
    _required_true,
    _validate_sequence,
)

REPOSITORY_ID = 1349678672
REPOSITORY = "maglothinm/MyETF-Intelligence"
PROJECT_ID = "project-38008d5f-4918-46e6-920"
REGION = "us-central1"
DEPLOYER_MEMBER = (
    "serviceAccount:polititrack-phase3-deployer@"
    "project-38008d5f-4918-46e6-920.iam.gserviceaccount.com"
)
PERMANENT_CONTROL_ROLE = (
    "projects/project-38008d5f-4918-46e6-920/roles/polititrackPhase3Terraform"
)
VAULT_SCHEDULER = "polititrack-vault-lifecycle"

# This is deliberately an incident-specific validator, not a general escape
# hatch around Phase 4/5 invariants.
PHASE4_RUN_ID = 33979432233
FAILED_PHASE5_RUN_ID = 33979778020
FAILED_PHASE5_RETRY_RUN_ID = 33990741282
FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID = 33998014996
CONCURRENT_LEGACY_AI_RUN_ID = 33980946687
RECOVERY_RUN_IDS = (33981311523, 33981312757)
FROZEN_LEGACY_SUCCESSOR_RUN_IDS = (
    33987160591,
    33987130349,
    33992770754,
    33992772006,
    33999935395,
    33999936212,
)
CERTIFIED_CONTROL_REVISION = "48efd8a45bbb51ee89e8b680430e593ac8867046"
CERTIFIED_TREE_SHA = "e6ca055af1973765bea1b3de5c01a5dbd69c0393"
RUNTIME_SOURCE_REVISION = "8908f067298078f8c013e90cf6b7ad8ad420285b"
FROZEN_LEGACY_SUCCESSOR_REVISIONS = (
    "40d252f4b26f8235a8a61d5c05d1e8a1b2bc76f2",
    "7dba656fe37098f0b7a2576f49803eb10d49f1be",
    "093bc9c5ad9100e7bf4474f56bdac58d1079129a",
)
FAILED_PHASE5_RETRY_CONTROL_REVISION = FROZEN_LEGACY_SUCCESSOR_REVISIONS[1]
FAILED_PHASE5_RETRY_SUCCESSOR_CONTROL_REVISION = FROZEN_LEGACY_SUCCESSOR_REVISIONS[2]
RUNTIME_SNAPSHOT_DIGEST_PREFIX = "0f601d"

FROZEN_LEGACY_SUCCESSOR_DIFFS = (
    {
        ".github/workflows/phase5_failed_promotion_retry.yml": "A",
        ".github/workflows/runtime_v2_tests.yml": "M",
        "deploy/runtime-v2/phase5-retry-evidence-33979778020.json": "A",
        "deploy/runtime-v2/phase5_failed_promotion_retry_control.sh": "A",
        "deploy/runtime-v2/reconcile_phase5_failed_promotion.py": "A",
        "docs/DECISIONS.md": "M",
        "tests/test_phase5_failed_promotion_retry.py": "A",
        "tests/test_reconcile_phase5_failed_promotion.py": "A",
    },
    {
        ".github/workflows/phase5_failed_promotion_retry.yml": "M",
        ".github/workflows/runtime_v2_tests.yml": "M",
        "deploy/runtime-v2/phase5-retry-evidence-33979778020.json": "M",
        "deploy/runtime-v2/phase5_failed_promotion_retry_control.sh": "M",
        "deploy/runtime-v2/reconcile_phase5_failed_promotion.py": "M",
        "tests/test_phase5_failed_promotion_retry.py": "M",
        "tests/test_reconcile_phase5_failed_promotion.py": "M",
    },
    {
        ".github/workflows/phase5_failed_promotion_retry.yml": "M",
        ".github/workflows/runtime_v2_tests.yml": "M",
        "deploy/runtime-v2/phase5-retry-evidence-33979778020.json": "M",
        "deploy/runtime-v2/phase5_failed_promotion_retry_control.sh": "M",
        "deploy/runtime-v2/reconcile_phase5_failed_promotion.py": "M",
        "tests/test_phase5_failed_promotion_retry.py": "M",
        "tests/test_phase5_retry_workflow_failure_safety.py": "A",
        "tests/test_reconcile_phase5_failed_promotion.py": "M",
    },
)

PHASE4_WORKFLOW_PATH = ".github/workflows/phase4_live_shadow_validation_v6.yml"
PHASE5_WORKFLOW_PATH = ".github/workflows/phase5_production_promotion_v2.yml"
PHASE5_RETRY_WORKFLOW_PATH = ".github/workflows/phase5_failed_promotion_retry.yml"
AI_WORKFLOW_PATH = ".github/workflows/ai_filing_analyst.yml"
DASHBOARD_WORKFLOW_PATH = ".github/workflows/publish_trade_dashboard.yml"
RECOVERY_PATHS = {
    "legislative": ".github/workflows/legislative_trade_tracker_v2.yml",
    "executive": ".github/workflows/executive_trade_tracker.yml",
}
RECOVERY_ARTIFACT_NAMES = {
    "legislative": "legislative-tracker-state",
    "executive": "executive-tracker-state",
}
RECOVERY_RESULT_MEMBERS = {
    "legislative": "legislative-result.json",
    "executive": "executive-result.json",
}
RECOVERY_PROTECTED_DOMAIN_MEMBERS = {
    "legislative": (
        "filings.jsonl",
        "historical-backfill.jsonl",
        "pending-review.jsonl",
        "purchases.jsonl",
        "transactions.jsonl",
    ),
    "executive": ("filings.jsonl", "pending-review.jsonl"),
}
RECOVERY_COUNT_DIMENSIONS = {
    "legislative": {"house": 0, "senate": 0},
    "executive": {"oge": 0},
}
LEGACY_HIGH_WATER_ROLES = ("legislative", "executive", "ai", "dashboard")

MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA64 = re.compile(r"[0-9a-f]{64}")


def _fail(message: str) -> None:
    raise PromotionValidationError(message)


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
        raise PromotionValidationError(f"{label} is not valid UTF-8 JSON") from exc


def _load_json(path: Path) -> Any:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PromotionValidationError(f"unable to read {path}") from exc
    return _json_bytes(data, str(path))


def _load_object(path: Path) -> dict[str, Any]:
    value = _load_json(path)
    if not isinstance(value, dict):
        _fail(f"{path} is not a JSON object")
    return value


def _load_list_or_object(path: Path) -> Any:
    return _load_json(path)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise PromotionValidationError(f"unable to read {path}") from exc
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        _fail(f"{label} mismatch")


def _require_object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{label} is not a list")
    return value


def _digest_pin(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or not SHA64.fullmatch(value[7:]):
        _fail(f"{label} is not a SHA-256 artifact digest")
    return value[7:]


def _artifact_members(path: Path) -> dict[str, bytes]:
    try:
        archive_size = path.stat().st_size
    except OSError as exc:
        raise PromotionValidationError(f"unable to stat {path}") from exc
    if archive_size > MAX_ARCHIVE_BYTES:
        _fail(f"artifact {path} exceeds the archive size limit")
    if not zipfile.is_zipfile(path):
        _fail(f"artifact {path} is not a ZIP archive")

    members: dict[str, bytes] = {}
    seen_exact: set[str] = set()
    seen_folded: dict[str, str] = {}
    expanded = 0
    try:
        with zipfile.ZipFile(path) as bundle:
            for info in bundle.infolist():
                # On Windows ZipInfo.filename normalizes backslashes to slashes.
                # orig_filename preserves the archive's actual member spelling.
                raw_name = info.orig_filename
                if (
                    not raw_name
                    or "\x00" in raw_name
                    or "\\" in raw_name
                    or raw_name.startswith("/")
                    or re.match(r"^[A-Za-z]:", raw_name)
                ):
                    _fail("artifact contains an unsafe member name")
                directory = raw_name.endswith("/")
                parts = raw_name[:-1].split("/") if directory else raw_name.split("/")
                if not parts or any(part in {"", ".", ".."} for part in parts):
                    _fail("artifact contains an unsafe member path")
                normalized = PurePosixPath(*parts).as_posix() + ("/" if directory else "")
                if normalized != raw_name:
                    _fail("artifact contains a non-canonical member path")
                if raw_name in seen_exact:
                    _fail(f"artifact contains duplicate member {raw_name}")
                seen_exact.add(raw_name)
                folded = raw_name.casefold()
                if folded in seen_folded:
                    _fail(
                        f"artifact contains case-colliding members {seen_folded[folded]} and {raw_name}"
                    )
                seen_folded[folded] = raw_name

                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    _fail("artifact contains a symbolic link")
                if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                    _fail("artifact contains a non-regular member")
                if info.flag_bits & 0x1:
                    _fail("artifact contains an encrypted member")
                if directory or info.is_dir():
                    continue
                if info.file_size > MAX_MEMBER_BYTES:
                    _fail(f"artifact member {raw_name} exceeds the size limit")
                expanded += info.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    _fail("artifact expands beyond the evidence limit")
                members[raw_name] = bundle.read(info)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PromotionValidationError(f"unable to inspect artifact {path}") from exc
    return members


def _member(members: Mapping[str, bytes], name: str) -> bytes:
    value = members.get(name)
    if value is None:
        _fail(f"artifact is missing {name}")
    return value


def _unique_basename(members: Mapping[str, bytes], basename: str) -> bytes:
    matches = [value for name, value in members.items() if PurePosixPath(name).name == basename]
    if len(matches) != 1:
        _fail(f"artifact must contain exactly one {basename}")
    return matches[0]


def _load_pinned_artifact(
    path: Path,
    metadata: Mapping[str, Any],
    pin: Mapping[str, Any],
    *,
    producer_run_id: int,
    producer_head_sha: str,
) -> dict[str, bytes]:
    artifact_id = pin.get("id")
    artifact_name = pin.get("name")
    if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id < 1:
        _fail("artifact ID pin is invalid")
    if not isinstance(artifact_name, str) or not artifact_name:
        _fail(f"artifact {artifact_id} name pin is invalid")
    expires_at = pin.get("expires_at")
    _parse_time(expires_at, f"artifact {artifact_id} expires_at")
    expected_size = pin.get("size_in_bytes")
    if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 1:
        _fail("artifact size pin is invalid")
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        raise PromotionValidationError(f"unable to stat {path}") from exc
    _expect(actual_size, expected_size, f"artifact {pin.get('id')} downloaded size")
    expected_digest = _digest_pin(pin.get("digest"), f"artifact {artifact_id} digest")
    _expect(_sha256_file(path), expected_digest, f"artifact {artifact_id} downloaded digest")

    for key, expected in {
        "id": artifact_id,
        "name": artifact_name,
        "size_in_bytes": expected_size,
        "digest": pin.get("digest"),
        "expires_at": expires_at,
        "expired": False,
    }.items():
        _expect(metadata.get(key), expected, f"artifact {artifact_id} API {key}")
    workflow_run = _require_object(metadata.get("workflow_run"), "artifact workflow_run")
    for key, expected in {
        "id": producer_run_id,
        "repository_id": REPOSITORY_ID,
        "head_repository_id": REPOSITORY_ID,
        "head_branch": "main",
        "head_sha": producer_head_sha,
    }.items():
        _expect(workflow_run.get(key), expected, f"artifact {artifact_id} workflow_run {key}")
    return _artifact_members(path)


def _normalize_workflow_path(value: Any) -> Any:
    if isinstance(value, str):
        return value.split("@", 1)[0]
    return value


def _validate_run_job_metadata(
    pin: Mapping[str, Any],
    run: Mapping[str, Any],
    jobs: Mapping[str, Any],
    *,
    expected_run_id: int,
    expected_path: str,
    expected_conclusion: str,
    expected_job_name: str,
) -> Mapping[str, Any]:
    workflow = _require_object(pin.get("workflow"), "workflow pin")
    job_pin = _require_object(pin.get("job"), "job pin")
    _expect(pin.get("run_id"), expected_run_id, "incident run id pin")
    if not isinstance(pin.get("head_sha"), str) or not SHA40.fullmatch(str(pin.get("head_sha"))):
        _fail(f"run {expected_run_id} head SHA pin is invalid")
    if not isinstance(pin.get("run_attempt"), int) or pin.get("run_attempt") < 1:
        _fail(f"run {expected_run_id} attempt pin is invalid")
    if not isinstance(pin.get("run_number"), int) or pin.get("run_number") < 1:
        _fail(f"run {expected_run_id} number pin is invalid")
    _expect(workflow.get("path"), expected_path, f"run {expected_run_id} workflow path pin")
    _expect(pin.get("conclusion"), expected_conclusion, f"run {expected_run_id} conclusion pin")
    _expect(job_pin.get("name"), expected_job_name, f"run {expected_run_id} job name pin")
    workflow_id = workflow.get("id")
    job_id = job_pin.get("id")
    if isinstance(workflow_id, bool) or not isinstance(workflow_id, int) or workflow_id < 1:
        _fail(f"run {expected_run_id} workflow ID pin is invalid")
    if not isinstance(workflow.get("name"), str) or not workflow.get("name"):
        _fail(f"run {expected_run_id} workflow name pin is invalid")
    if isinstance(job_id, bool) or not isinstance(job_id, int) or job_id < 1:
        _fail(f"run {expected_run_id} job ID pin is invalid")

    for key, expected in {
        "id": expected_run_id,
        "run_number": pin.get("run_number"),
        "run_attempt": pin.get("run_attempt"),
        "workflow_id": workflow.get("id"),
        "name": workflow.get("name"),
        "event": pin.get("event"),
        "head_branch": "main",
        "head_sha": pin.get("head_sha"),
        "status": "completed",
        "conclusion": expected_conclusion,
    }.items():
        _expect(run.get(key), expected, f"run {expected_run_id} API {key}")
    _expect(_normalize_workflow_path(run.get("path")), expected_path, f"run {expected_run_id} API path")
    for key in ("repository", "head_repository"):
        boundary = _require_object(run.get(key), f"run {expected_run_id} {key}")
        _expect(boundary.get("id"), REPOSITORY_ID, f"run {expected_run_id} {key} id")
    for key in ("created_at", "run_started_at", "updated_at"):
        expected = pin.get(key)
        if not isinstance(expected, str) or not expected:
            _fail(f"run {expected_run_id} {key} pin is missing")
        _expect(run.get(key), expected, f"run {expected_run_id} API {key}")
        _parse_time(expected, f"run {expected_run_id} {key}")

    job_list = _require_list(jobs.get("jobs"), f"run {expected_run_id} jobs")
    if jobs.get("total_count") != 1 or len(job_list) != 1:
        _fail(f"run {expected_run_id} authoritative job mapping is ambiguous")
    job = _require_object(job_list[0], f"run {expected_run_id} job")
    for key, expected in {
        "id": job_pin.get("id"),
        "name": job_pin.get("name"),
        "status": "completed",
        "conclusion": expected_conclusion,
        "run_id": expected_run_id,
        "run_attempt": pin.get("run_attempt"),
        "head_sha": pin.get("head_sha"),
    }.items():
        _expect(job.get(key), expected, f"run {expected_run_id} job {key}")
    for key in ("started_at", "completed_at"):
        expected = job_pin.get(key)
        if not isinstance(expected, str) or not expected:
            _fail(f"run {expected_run_id} job {key} pin is missing")
        _expect(job.get(key), expected, f"run {expected_run_id} job {key}")
        _parse_time(expected, f"run {expected_run_id} job {key}")
    if _parse_time(job_pin["completed_at"], "job completed_at") < _parse_time(
        job_pin["started_at"], "job started_at"
    ):
        _fail(f"run {expected_run_id} job completed before it started")
    return job


def _head_summary(heads: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "generation": heads[name]["generation"],
            "snapshot_sha256": heads[name]["snapshot_sha256"],
        }
        for name in NAMESPACES
    }


def _same_heads(actual: Mapping[str, Mapping[str, Any]], expected: Mapping[str, Any], label: str) -> None:
    for namespace in NAMESPACES:
        wanted = _require_object(expected.get(namespace), f"{label} {namespace}")
        for key in ("generation", "snapshot_sha256"):
            _expect(actual[namespace].get(key), wanted.get(key), f"{label} {namespace} {key}")


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PromotionValidationError(f"git {' '.join(arguments)} failed") from exc
    return result.stdout.strip()


def _verify_tree_equal_descendant(
    repository_root: Path, certified_sha: str, descendant_sha: str, expected_tree: str
) -> None:
    certified_tree = _git(repository_root, "rev-parse", f"{certified_sha}^{{tree}}")
    descendant_tree = _git(repository_root, "rev-parse", f"{descendant_sha}^{{tree}}")
    _expect(certified_tree, expected_tree, "certified Git tree")
    _expect(descendant_tree, expected_tree, f"tree for recovery revision {descendant_sha}")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", certified_sha, descendant_sha],
            cwd=repository_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PromotionValidationError(
            f"recovery revision {descendant_sha} is not a certified-tree-equal descendant"
        ) from exc


def _verify_frozen_legacy_successor_revision(repository_root: Path) -> None:
    predecessor = CERTIFIED_CONTROL_REVISION
    for layer, (revision, expected_diff) in enumerate(
        zip(FROZEN_LEGACY_SUCCESSOR_REVISIONS, FROZEN_LEGACY_SUCCESSOR_DIFFS), start=1
    ):
        _expect(
            _git(repository_root, "rev-parse", f"{revision}^{{commit}}"),
            revision,
            f"frozen legacy successor layer {layer} commit",
        )
        try:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", predecessor, revision],
                cwd=repository_root,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PromotionValidationError(
                f"frozen legacy successor layer {layer} does not descend from its predecessor"
            ) from exc

        output = _git(
            repository_root,
            "diff",
            "--name-status",
            "--no-renames",
            predecessor,
            revision,
            "--",
        )
        observed: dict[str, str] = {}
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) != 2 or parts[0] not in {"A", "M", "D"} or parts[1] in observed:
                _fail(
                    f"frozen legacy successor layer {layer} has an ambiguous changed-path inventory"
                )
            observed[parts[1]] = parts[0]
        _expect(
            observed,
            expected_diff,
            f"frozen legacy successor layer {layer} incident-only changed paths",
        )
        predecessor = revision


def _parse_sha256_file(data: bytes, expected_name: str, label: str) -> str:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PromotionValidationError(f"{label} is not ASCII") from exc
    match = re.fullmatch(r"([0-9a-f]{64}) [ *](\S+)\r?\n?", text)
    if match is None or match.group(2) != expected_name:
        _fail(f"{label} is not an exact SHA-256 receipt")
    return match.group(1)


def _validate_phase4_receipts(certificate: Mapping[str, Any]) -> None:
    receipts = _require_list(certificate.get("executions"), "Phase 4 executions")
    expected_jobs = list(NAMESPACES) * 2
    if len(receipts) != 8:
        _fail("Phase 4 certificate does not contain exactly eight executions")
    run_ids: set[str] = set()
    execution_names: set[str] = set()
    by_cycle_job: dict[tuple[int, str], Mapping[str, Any]] = {}
    previous_finished = None
    for index, (value, expected_job) in enumerate(zip(receipts, expected_jobs), start=1):
        receipt = _require_object(value, f"Phase 4 execution {index}")
        expected_cycle = 1 if index <= len(NAMESPACES) else 2
        for key, expected in {
            "sequence": index,
            "cycle": expected_cycle,
            "job": expected_job,
        }.items():
            _expect(receipt.get(key), expected, f"Phase 4 execution {index} {key}")
        run_id = receipt.get("run_id")
        execution = receipt.get("cloud_run_execution")
        if not isinstance(run_id, str) or not run_id or run_id in run_ids:
            _fail("Phase 4 certificate does not contain eight unique Runtime receipts")
        if not isinstance(execution, str) or not execution or execution in execution_names:
            _fail("Phase 4 certificate does not contain eight unique Cloud Run executions")
        run_ids.add(run_id)
        execution_names.add(execution)
        generation = receipt.get("generation")
        digest = receipt.get("snapshot_sha256")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            _fail(f"Phase 4 execution {index} generation is invalid")
        if not isinstance(digest, str) or SHA64.fullmatch(digest) is None:
            _fail(f"Phase 4 execution {index} snapshot digest is invalid")
        started = _parse_time(receipt.get("started_at"), f"Phase 4 execution {index} started_at")
        finished = _parse_time(receipt.get("finished_at"), f"Phase 4 execution {index} finished_at")
        if finished < started:
            _fail(f"Phase 4 execution {index} finished before it started")
        if previous_finished is not None and started < previous_finished:
            _fail(f"Phase 4 execution {index} overlaps its predecessor")
        previous_finished = finished
        by_cycle_job[(expected_cycle, expected_job)] = receipt

    final_heads = _require_object(certificate.get("final_heads"), "Phase 4 final heads")
    if set(final_heads) != set(NAMESPACES):
        _fail("Phase 4 certificate final heads are not the exact four namespaces")
    for job in NAMESPACES:
        first = by_cycle_job[(1, job)]
        second = by_cycle_job[(2, job)]
        _expect(
            second.get("generation"),
            int(first["generation"]) + 1,
            f"Phase 4 {job} second-cycle generation",
        )
        if second.get("snapshot_sha256") == first.get("snapshot_sha256"):
            _fail(f"Phase 4 {job} second cycle did not produce a new snapshot")
        head = _require_object(final_heads.get(job), f"Phase 4 final {job} head")
        _expect(head.get("generation"), second.get("generation"), f"Phase 4 final {job} generation")
        _expect(
            head.get("snapshot_sha256"),
            second.get("snapshot_sha256"),
            f"Phase 4 final {job} snapshot digest",
        )


def _phase4_certificate(
    descriptor: Mapping[str, Any],
    run_metadata: Mapping[str, Any],
    artifact_metadata: Mapping[str, Any],
    jobs_metadata: Mapping[str, Any],
    archive: Path,
) -> tuple[dict[str, Any], bytes]:
    pin = _require_object(descriptor.get("phase4"), "Phase 4 pin")
    _validate_run_job_metadata(
        pin,
        run_metadata,
        jobs_metadata,
        expected_run_id=PHASE4_RUN_ID,
        expected_path=PHASE4_WORKFLOW_PATH,
        expected_conclusion="success",
        expected_job_name="controlled-shadow-acceptance",
    )
    _expect(pin.get("head_sha"), CERTIFIED_CONTROL_REVISION, "Phase 4 certified revision")
    artifact_pin = _require_object(pin.get("artifact"), "Phase 4 artifact pin")
    members = _load_pinned_artifact(
        archive,
        artifact_metadata,
        artifact_pin,
        producer_run_id=PHASE4_RUN_ID,
        producer_head_sha=CERTIFIED_CONTROL_REVISION,
    )
    certificate_bytes = _member(members, "phase4-ready.json")
    certificate_sha = _sha256_bytes(certificate_bytes)
    _expect(certificate_sha, pin.get("certificate_sha256"), "Phase 4 certificate pin")
    receipt_sha = _parse_sha256_file(
        _member(members, "phase4-ready.sha256"), "phase4-ready.json", "Phase 4 checksum"
    )
    _expect(receipt_sha, certificate_sha, "Phase 4 certificate checksum")
    certificate = _json_bytes(certificate_bytes, "phase4-ready.json")
    certificate = dict(_require_object(certificate, "Phase 4 certificate"))
    for key, expected in {
        "result": "phase4_ready_for_phase5",
        "repository_id": REPOSITORY_ID,
        "control_revision": CERTIFIED_CONTROL_REVISION,
        "runtime_source_revision": RUNTIME_SOURCE_REVISION,
        "immutable_image": descriptor.get("immutable_image"),
        "phase5_ready": True,
        "controlled_shadow_cycles": 2,
        "unique_successful_execution_receipts": 8,
        "production_authority_transferred": False,
    }.items():
        _expect(certificate.get(key), expected, f"Phase 4 certificate {key}")
    _validate_phase4_receipts(certificate)
    return certificate, certificate_bytes


def _validate_phase5_baseline(
    baseline: Mapping[str, Any], certificate: Mapping[str, Any]
) -> None:
    heads = _heads(baseline)
    certified_heads = _require_object(certificate.get("final_heads"), "Phase 4 final heads")
    _same_heads(heads, certified_heads, "failed Phase 5 baseline")
    runs = _latest_runs(baseline)
    if set(runs) != set(NAMESPACES):
        _fail("failed Phase 5 baseline lacks the exact four latest receipts")
    certificate_receipts = _require_list(certificate.get("executions"), "Phase 4 executions")
    expected_runs = {
        item.get("job"): item
        for item in certificate_receipts[-len(NAMESPACES) :]
        if isinstance(item, Mapping)
    }
    if set(expected_runs) != set(NAMESPACES):
        _fail("Phase 4 certificate lacks an exact terminal cycle")
    for namespace in NAMESPACES:
        expected = expected_runs[namespace]
        for key, value in {
            "run_id": expected.get("run_id"),
            "status": "success",
            "runtime_mode": "shadow",
            "runtime_mode_verified": True,
            "trigger_source": "shadow",
            "side_effects_possible": False,
            "source_revision": RUNTIME_SOURCE_REVISION,
            "snapshot_generation": certified_heads[namespace].get("generation"),
            "snapshot_sha256": certified_heads[namespace].get("snapshot_sha256"),
        }.items():
            _expect(runs[namespace].get(key), value, f"failed Phase 5 baseline {namespace} {key}")


def _observations_from_ndjson(data: bytes, label: str) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromotionValidationError(f"{label} is not UTF-8") from exc
    observations: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = _json_bytes(line.encode("utf-8"), f"{label} line {number}")
        observations.append(dict(_require_object(value, f"{label} line {number}")))
    return observations


def _failed_phase5_prefix(
    descriptor: Mapping[str, Any],
    certificate: Mapping[str, Any],
    certificate_bytes: bytes,
    run_metadata: Mapping[str, Any],
    artifact_metadata: Mapping[str, Any],
    jobs_metadata: Mapping[str, Any],
    archive: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], Mapping[str, Any]]:
    pin = _require_object(descriptor.get("failed_phase5"), "failed Phase 5 pin")
    job = _validate_run_job_metadata(
        pin,
        run_metadata,
        jobs_metadata,
        expected_run_id=FAILED_PHASE5_RUN_ID,
        expected_path=PHASE5_WORKFLOW_PATH,
        expected_conclusion="failure",
        expected_job_name="promote-production-authority",
    )
    _expect(pin.get("head_sha"), CERTIFIED_CONTROL_REVISION, "failed Phase 5 revision")
    artifact_pin = _require_object(pin.get("artifact"), "failed Phase 5 artifact pin")
    members = _load_pinned_artifact(
        archive,
        artifact_metadata,
        artifact_pin,
        producer_run_id=FAILED_PHASE5_RUN_ID,
        producer_head_sha=CERTIFIED_CONTROL_REVISION,
    )
    if any(PurePosixPath(name).name == "phase5-complete.json" for name in members):
        _fail("failed Phase 5 artifact unexpectedly contains a completion certificate")
    baseline = _json_bytes(_member(members, "baseline.json"), "failed baseline.json")
    baseline = dict(_require_object(baseline, "failed Phase 5 baseline"))
    _validate_phase5_baseline(baseline, certificate)
    embedded_cert = _member(members, "phase4/phase4-ready.json")
    if embedded_cert != certificate_bytes:
        _fail("failed Phase 5 embedded certificate differs from the pinned Phase 4 certificate")
    embedded_checksum = _parse_sha256_file(
        _member(members, "phase4/phase4-ready.sha256"),
        "phase4-ready.json",
        "failed Phase 5 embedded Phase 4 checksum",
    )
    _expect(embedded_checksum, _sha256_bytes(certificate_bytes), "embedded Phase 4 checksum")

    observations = _observations_from_ndjson(
        _member(members, "observations.ndjson"), "failed observations.ndjson"
    )
    status_members = _require_list(pin.get("status_members"), "failed Phase 5 status member pins")
    expected_status_members = [
        f"smoke-sequence-{index}-{job}-status.json"
        for index, job in enumerate(NAMESPACES, start=1)
    ]
    _expect(status_members, expected_status_members, "failed Phase 5 status member list")
    if len(observations) != len(status_members):
        _fail("failed Phase 5 observation/status count mismatch")
    for index, (observation, name, expected_job) in enumerate(
        zip(observations, status_members, NAMESPACES), start=1
    ):
        _expect(observation.get("cycle"), 1, f"failed observation {index} cycle")
        _expect(observation.get("sequence"), index, f"failed observation {index} sequence")
        _expect(observation.get("job"), expected_job, f"failed observation {index} job")
        status = _json_bytes(_member(members, str(name)), f"failed artifact {name}")
        _expect(observation.get("status"), status, f"failed observation {index} status file")

    final_heads, receipts = _validate_sequence(
        baseline=baseline,
        observations=observations,
        expected_mode="production",
        expected_trigger="phase5_smoke",
        cycles=1,
        runtime_source_revision=RUNTIME_SOURCE_REVISION,
    )
    retry_pin = _require_object(
        descriptor.get("failed_phase5_retry"), "failed Phase 5 retry pin"
    )
    expected_heads = _require_object(
        retry_pin.get("baseline_heads"), "failed retry baseline heads"
    )
    _same_heads(final_heads, expected_heads, "failed Phase 5 continuation heads")
    return {
        "baseline": baseline,
        "final_heads": final_heads,
        "receipts": receipts,
    }, observations, job


def _validate_failed_phase5_retry(
    descriptor: Mapping[str, Any],
    run_metadata: Mapping[str, Any],
    artifact_metadata: Mapping[str, Any],
    jobs_metadata: Mapping[str, Any],
    archive: Path,
    prefix: Mapping[str, Any],
) -> dict[str, Any]:
    pin = _require_object(descriptor.get("failed_phase5_retry"), "failed Phase 5 retry pin")
    job = _validate_run_job_metadata(
        pin,
        run_metadata,
        jobs_metadata,
        expected_run_id=FAILED_PHASE5_RETRY_RUN_ID,
        expected_path=PHASE5_RETRY_WORKFLOW_PATH,
        expected_conclusion="failure",
        expected_job_name="reconcile-and-retry",
    )
    _expect(
        pin.get("head_sha"),
        FAILED_PHASE5_RETRY_CONTROL_REVISION,
        "failed Phase 5 retry revision",
    )
    artifact_pin = _require_object(pin.get("artifact"), "failed Phase 5 retry artifact pin")
    members = _load_pinned_artifact(
        archive,
        artifact_metadata,
        artifact_pin,
        producer_run_id=FAILED_PHASE5_RETRY_RUN_ID,
        producer_head_sha=FAILED_PHASE5_RETRY_CONTROL_REVISION,
    )
    forbidden = {"phase5-complete.json", "phase5-complete.sha256", "terminal-manifest.json"}
    present_basenames = {PurePosixPath(name).name for name in members}
    if forbidden & present_basenames:
        _fail("failed Phase 5 retry artifact unexpectedly contains completion evidence")
    for marker in ("live-mutation-started", "route-touched", "retry-rollback-complete"):
        if marker not in present_basenames:
            _fail(f"failed Phase 5 retry artifact is missing {marker}")

    replay_bytes = _unique_basename(members, "failed-prefix-replay.json")
    replay_sha = _sha256_bytes(replay_bytes)
    _expect(
        replay_sha,
        pin.get("predecessor_replay_sha256"),
        "failed Phase 5 retry predecessor replay digest",
    )
    replay_checksum = _parse_sha256_file(
        _unique_basename(members, "failed-prefix-replay.sha256"),
        "failed-prefix-replay.json",
        "failed Phase 5 retry replay checksum",
    )
    _expect(replay_checksum, replay_sha, "failed Phase 5 retry replay checksum")
    embedded_replay = _json_bytes(replay_bytes, "failed Phase 5 retry embedded replay")
    embedded_replay = _require_object(embedded_replay, "failed Phase 5 retry embedded replay")
    for key, expected in {
        "result": "phase5_failed_promotion_reconciled",
        "certification_eligible": False,
        "descriptor_sha256": pin.get("predecessor_descriptor_sha256"),
    }.items():
        _expect(embedded_replay.get(key), expected, f"failed Phase 5 retry replay {key}")
    embedded_reconciliation = _require_object(
        embedded_replay.get("reconciliation"), "failed Phase 5 retry replay reconciliation"
    )
    for key, expected in {
        "additional_runtime_producer_execution_performed": False,
        "production_authority_transferred": False,
        "phase6_started": False,
    }.items():
        _expect(embedded_reconciliation.get(key), expected, f"failed Phase 5 retry replay {key}")
    embedded_successors = _require_list(
        embedded_replay.get("frozen_legacy_successors"),
        "failed Phase 5 retry embedded frozen successors",
    )
    _expect(
        [item.get("run_id") for item in embedded_successors if isinstance(item, Mapping)],
        list(FROZEN_LEGACY_SUCCESSOR_RUN_IDS[:2]),
        "failed Phase 5 retry embedded frozen successor runs",
    )

    baseline = _json_bytes(
        _unique_basename(members, "terminal-baseline.json"),
        "failed Phase 5 retry terminal baseline",
    )
    baseline = dict(_require_object(baseline, "failed Phase 5 retry terminal baseline"))
    prefix_heads = _require_object(prefix.get("final_heads"), "failed Phase 5 prefix heads")
    _same_heads(_heads(baseline), prefix_heads, "failed Phase 5 retry baseline")
    prefix_receipts = _require_list(prefix.get("receipts"), "failed Phase 5 prefix receipts")
    _assert_current_runtime_state(baseline, prefix_heads, prefix_receipts)

    observations = _observations_from_ndjson(
        _unique_basename(members, "observations.ndjson"),
        "failed Phase 5 retry observations.ndjson",
    )
    status_members = _require_list(
        pin.get("status_members"), "failed Phase 5 retry status member pins"
    )
    expected_status_members = [
        f"retry-smoke-sequence-{index}-{role}-status.json"
        for index, role in enumerate(NAMESPACES, start=1)
    ]
    _expect(status_members, expected_status_members, "failed Phase 5 retry status member list")
    if len(observations) != len(status_members):
        _fail("failed Phase 5 retry observation/status count mismatch")
    for index, (observation, name, role) in enumerate(
        zip(observations, status_members, NAMESPACES), start=1
    ):
        for key, expected in {"cycle": 1, "sequence": index, "job": role}.items():
            _expect(observation.get(key), expected, f"failed retry observation {index} {key}")
        status = _json_bytes(
            _unique_basename(members, str(name)), f"failed Phase 5 retry artifact {name}"
        )
        _expect(observation.get("status"), status, f"failed retry observation {index} status file")

    final_heads, receipts = _validate_sequence(
        baseline=baseline,
        observations=observations,
        expected_mode="production",
        expected_trigger="phase5_smoke",
        cycles=1,
        runtime_source_revision=RUNTIME_SOURCE_REVISION,
    )
    successor_pin = _require_object(
        descriptor.get("failed_phase5_retry_successor"),
        "failed Phase 5 retry successor pin",
    )
    expected_heads = _require_object(
        successor_pin.get("baseline_heads"), "failed retry successor baseline heads"
    )
    _same_heads(final_heads, expected_heads, "failed Phase 5 retry continuation heads")
    pinned_terminal_heads = _require_object(
        pin.get("terminal_heads"), "failed Phase 5 retry terminal head pins"
    )
    _same_heads(final_heads, pinned_terminal_heads, "failed Phase 5 retry terminal heads")
    terminal_confirmation = _json_bytes(
        _unique_basename(members, "terminal-confirmation.json"),
        "failed Phase 5 retry terminal confirmation",
    )
    _expect(
        terminal_confirmation,
        observations[-1].get("status"),
        "failed Phase 5 retry terminal confirmation",
    )

    interval_start_text = _unique_basename(members, "fresh-cycle-started-at.txt").decode(
        "ascii"
    ).strip()
    interval_finish_text = _unique_basename(members, "fresh-cycle-finished-at.txt").decode(
        "ascii"
    ).strip()
    interval_start = _parse_time(interval_start_text, "failed retry fresh-cycle started_at")
    interval_finish = _parse_time(interval_finish_text, "failed retry fresh-cycle finished_at")
    if interval_finish < interval_start:
        _fail("failed retry fresh-cycle interval finished before it started")

    legacy_run_inventories = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/legacy-{role}-runs-terminal.json"),
                f"failed retry {role} run inventory",
            ),
            f"failed retry {role} run inventory",
        )
        for role in LEGACY_HIGH_WATER_ROLES
    ]
    legacy_workflow_states = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/legacy-{role}-workflow-terminal.json"),
                f"failed retry {role} workflow state",
            ),
            f"failed retry {role} workflow state",
        )
        for role in LEGACY_HIGH_WATER_ROLES
    ]
    runtime_execution_inventories = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/runtime-{role}-executions-terminal.json"),
                f"failed retry {role} Runtime inventory",
            ),
            f"failed retry {role} Runtime inventory",
        )
        for role in LEGACY_HIGH_WATER_ROLES
    ]
    evidence_files = {
        "legacy_run_inventories": [
            f"incident/legacy-{role}-runs-terminal.json" for role in LEGACY_HIGH_WATER_ROLES
        ],
        "legacy_workflow_states": [
            f"incident/legacy-{role}-workflow-terminal.json"
            for role in LEGACY_HIGH_WATER_ROLES
        ],
        "runtime_execution_inventories": [
            f"incident/runtime-{role}-executions-terminal.json"
            for role in LEGACY_HIGH_WATER_ROLES
        ],
    }
    evidence_digests = {
        field: [_sha256_bytes(_member(members, name)) for name in names]
        for field, names in evidence_files.items()
    }
    one_writer = {
        "fresh_cycle_interval": {
            "started_at": interval_start_text,
            "finished_at": interval_finish_text,
        },
        "overlapping_legacy_run_count": 0,
        "unexpected_runtime_execution_count": 0,
        "expected_runtime_execution_count": 4,
    }
    for field, digests in evidence_digests.items():
        one_writer[f"{field}_sha256"] = dict(zip(LEGACY_HIGH_WATER_ROLES, digests))
    _validate_terminal_one_writer(
        descriptor=descriptor,
        replay=embedded_replay,
        manifest={"one_writer_evidence": one_writer},
        receipts=receipts,
        legacy_run_inventories=legacy_run_inventories,
        legacy_workflow_states=legacy_workflow_states,
        runtime_execution_inventories=runtime_execution_inventories,
        evidence_digests=evidence_digests,
        successor_layer=0,
    )
    legacy_artifact_inventories = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/legacy-{role}-artifacts-terminal.json"),
                f"failed retry {role} artifact inventory",
            ),
            f"failed retry {role} artifact inventory",
        )
        for role in LEGACY_HIGH_WATER_ROLES[:3]
    ]
    _validate_high_water_artifact_inventories(
        descriptor, legacy_artifact_inventories, successor_layer=0
    )

    rollback = _require_object(
        _json_bytes(
            _unique_basename(members, "retry-rollback.json"),
            "failed Phase 5 retry rollback receipt",
        ),
        "failed Phase 5 retry rollback receipt",
    )
    for key, expected in {
        "schema_version": 1,
        "result": "phase5_failed_promotion_retry_rolled_back",
        "runtime_schedulers_paused": True,
        "web_public": False,
        "runtime_mode": "shadow",
        "observed_legacy_route_kind": "historic_active",
        "legacy_route_restored": True,
        "legacy_recovery_required": True,
        "legacy_recovery_action_complete": True,
        "temporary_execution_authority_removed": True,
        "temporary_service_account_user_removed": True,
        "temporary_private_web_invoker_removed": True,
        "cloud_sql_private_only": True,
        "vault_scheduler_state": "PAUSED",
    }.items():
        _expect(rollback.get(key), expected, f"failed Phase 5 retry rollback {key}")
    dispatch = _require_object(
        _json_bytes(
            _unique_basename(members, "legacy-recovery-dispatch.json"),
            "failed Phase 5 retry recovery dispatch",
        ),
        "failed Phase 5 retry recovery dispatch",
    )
    _expect(dispatch.get("result"), "legacy_recovery_runs_succeeded", "failed retry recovery")
    dispatches = _require_list(dispatch.get("workflows"), "failed retry recovery workflows")
    layer_two_pins = _require_list(
        descriptor.get("frozen_legacy_successors"), "frozen successor pins"
    )[2:4]
    if len(dispatches) != 2 or len(layer_two_pins) != 2:
        _fail("failed retry recovery dispatch does not contain exactly two layer-two runs")
    for role, value, successor_pin in zip(("legislative", "executive"), dispatches, layer_two_pins):
        row = _require_object(value, f"failed retry {role} recovery dispatch")
        expected_workflow = PurePosixPath(RECOVERY_PATHS[role]).name
        for key, expected in {
            "result": "legacy_recovery_run_succeeded",
            "workflow": expected_workflow,
            "workflow_id": _require_object(
                successor_pin.get("workflow"), f"{role} successor workflow pin"
            ).get("id"),
            "control_revision": FAILED_PHASE5_RETRY_CONTROL_REVISION,
            "dispatch_attempted": True,
            "run_id": successor_pin.get("run_id"),
            "status": "completed",
            "conclusion": "success",
            "run_attempt": successor_pin.get("run_attempt"),
        }.items():
            _expect(row.get(key), expected, f"failed retry {role} recovery dispatch {key}")
        if _parse_time(
            _require_object(successor_pin.get("job"), f"{role} successor job pin").get(
                "started_at"
            ),
            f"{role} rollback recovery started_at",
        ) <= interval_finish:
            _fail(f"{role} rollback recovery did not begin after the intervening fresh cycle")

    return {
        "run_id": FAILED_PHASE5_RETRY_RUN_ID,
        "artifact_id": artifact_pin.get("id"),
        "head_sha": pin.get("head_sha"),
        "job_id": job.get("id"),
        "conclusion": "failure",
        "result": "clean_cycle_rolled_back_noncertifying",
        "certification_eligible": False,
        "unique_successful_smoke_receipts": 4,
        "executions": receipts,
        "baseline_heads": _head_summary(_heads(baseline)),
        "final_heads": _head_summary(final_heads),
        "legacy_global_one_writer_verified": True,
        "runtime_execution_set_verified": True,
        "rollback_verified": True,
        "production_authority_transferred": False,
        "phase6_started": False,
    }


def _validate_failed_phase5_retry_successor(
    descriptor: Mapping[str, Any],
    run_metadata: Mapping[str, Any],
    artifact_metadata: Mapping[str, Any],
    jobs_metadata: Mapping[str, Any],
    archive: Path,
    prefix: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    frozen_successors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the second sealed retry without collapsing the first retry's lineage."""

    pin = _require_object(
        descriptor.get("failed_phase5_retry_successor"),
        "failed Phase 5 retry successor pin",
    )
    job = _validate_run_job_metadata(
        pin,
        run_metadata,
        jobs_metadata,
        expected_run_id=FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID,
        expected_path=PHASE5_RETRY_WORKFLOW_PATH,
        expected_conclusion="failure",
        expected_job_name="reconcile-and-retry",
    )
    _expect(
        pin.get("head_sha"),
        FAILED_PHASE5_RETRY_SUCCESSOR_CONTROL_REVISION,
        "failed Phase 5 retry successor revision",
    )
    artifact_pin = _require_object(
        pin.get("artifact"), "failed Phase 5 retry successor artifact pin"
    )
    members = _load_pinned_artifact(
        archive,
        artifact_metadata,
        artifact_pin,
        producer_run_id=FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID,
        producer_head_sha=FAILED_PHASE5_RETRY_SUCCESSOR_CONTROL_REVISION,
    )
    forbidden = {"phase5-complete.json", "phase5-complete.sha256", "terminal-manifest.json"}
    present_basenames = {PurePosixPath(name).name for name in members}
    if forbidden & present_basenames:
        _fail("failed Phase 5 retry successor artifact unexpectedly contains completion evidence")
    for marker in ("live-mutation-started", "route-touched", "retry-rollback-complete"):
        if marker not in present_basenames:
            _fail(f"failed Phase 5 retry successor artifact is missing {marker}")

    replay_bytes = _unique_basename(members, "failed-prefix-replay.json")
    replay_sha = _sha256_bytes(replay_bytes)
    _expect(
        replay_sha,
        pin.get("predecessor_replay_sha256"),
        "failed Phase 5 retry successor predecessor replay digest",
    )
    replay_checksum = _parse_sha256_file(
        _unique_basename(members, "failed-prefix-replay.sha256"),
        "failed-prefix-replay.json",
        "failed Phase 5 retry successor replay checksum",
    )
    _expect(replay_checksum, replay_sha, "failed Phase 5 retry successor replay checksum")
    embedded_replay = _require_object(
        _json_bytes(replay_bytes, "failed Phase 5 retry successor embedded replay"),
        "failed Phase 5 retry successor embedded replay",
    )
    for key, expected in {
        "result": "phase5_failed_promotion_reconciled",
        "certification_eligible": False,
        "descriptor_sha256": pin.get("predecessor_descriptor_sha256"),
        "failed_phase5_retry": predecessor,
        "continuation_heads": predecessor.get("final_heads"),
        "current_heads_verified": True,
        "current_latest_receipts_verified": True,
    }.items():
        _expect(
            embedded_replay.get(key),
            expected,
            f"failed Phase 5 retry successor replay {key}",
        )
    expected_invalidated_prefix = {
        "reason": "concurrent_legacy_ai_global_writer",
        "certification_eligible": False,
        "unique_successful_receipts": 4,
        "executions": _require_list(prefix.get("receipts"), "failed Phase 5 prefix receipts"),
        "baseline_heads": _head_summary(
            _heads(_require_object(prefix.get("baseline"), "failed Phase 5 prefix baseline"))
        ),
        "final_heads": _head_summary(
            _require_object(prefix.get("final_heads"), "failed Phase 5 prefix final heads")
        ),
    }
    _expect(
        embedded_replay.get("invalidated_smoke_prefix"),
        expected_invalidated_prefix,
        "failed Phase 5 retry successor embedded invalidated prefix",
    )
    embedded_successors = _require_list(
        embedded_replay.get("frozen_legacy_successors"),
        "failed Phase 5 retry successor embedded frozen successors",
    )
    predecessor_successor_count = 2 * (len(FROZEN_LEGACY_SUCCESSOR_REVISIONS) - 1)
    _expect(
        embedded_successors,
        list(frozen_successors[:predecessor_successor_count]),
        "failed Phase 5 retry successor embedded frozen successor chain",
    )
    embedded_reconciliation = _require_object(
        embedded_replay.get("reconciliation"),
        "failed Phase 5 retry successor replay reconciliation",
    )
    _required_true(
        embedded_reconciliation,
        (
            "failed_retry_intervening_attempt_verified",
            "intervening_runtime_producer_execution_performed",
            "full_snapshot_chain_preserved",
        ),
        "failed Phase 5 retry successor replay reconciliation",
    )
    _expect(
        embedded_reconciliation.get("intervening_runtime_producer_execution_count"),
        4,
        "failed Phase 5 retry successor replay execution count",
    )
    for key in (
        "additional_runtime_producer_execution_performed",
        "production_authority_transferred",
        "phase6_started",
    ):
        _expect(
            embedded_reconciliation.get(key),
            False,
            f"failed Phase 5 retry successor replay {key}",
        )

    baseline = dict(
        _require_object(
            _json_bytes(
                _unique_basename(members, "terminal-baseline.json"),
                "failed Phase 5 retry successor terminal baseline",
            ),
            "failed Phase 5 retry successor terminal baseline",
        )
    )
    predecessor_heads = _require_object(
        predecessor.get("final_heads"), "failed Phase 5 retry predecessor heads"
    )
    predecessor_receipts = _require_list(
        predecessor.get("executions"), "failed Phase 5 retry predecessor receipts"
    )
    _same_heads(_heads(baseline), predecessor_heads, "failed Phase 5 retry successor baseline")
    _assert_current_runtime_state(baseline, predecessor_heads, predecessor_receipts)
    pinned_baseline_heads = _require_object(
        pin.get("baseline_heads"), "failed Phase 5 retry successor baseline pins"
    )
    _same_heads(_heads(baseline), pinned_baseline_heads, "failed retry successor pinned baseline")

    observations = _observations_from_ndjson(
        _unique_basename(members, "observations.ndjson"),
        "failed Phase 5 retry successor observations.ndjson",
    )
    status_members = _require_list(
        pin.get("status_members"), "failed Phase 5 retry successor status member pins"
    )
    expected_status_members = [
        f"retry-smoke-sequence-{index}-{role}-status.json"
        for index, role in enumerate(NAMESPACES, start=1)
    ]
    _expect(
        status_members,
        expected_status_members,
        "failed Phase 5 retry successor status member list",
    )
    if len(observations) != len(status_members):
        _fail("failed Phase 5 retry successor observation/status count mismatch")
    for index, (observation, name, role) in enumerate(
        zip(observations, status_members, NAMESPACES), start=1
    ):
        for key, expected in {"cycle": 1, "sequence": index, "job": role}.items():
            _expect(
                observation.get(key),
                expected,
                f"failed retry successor observation {index} {key}",
            )
        status = _json_bytes(
            _unique_basename(members, str(name)),
            f"failed Phase 5 retry successor artifact {name}",
        )
        _expect(
            observation.get("status"),
            status,
            f"failed retry successor observation {index} status file",
        )

    final_heads, receipts = _validate_sequence(
        baseline=baseline,
        observations=observations,
        expected_mode="production",
        expected_trigger="phase5_smoke",
        cycles=1,
        runtime_source_revision=RUNTIME_SOURCE_REVISION,
    )
    expected_heads = _require_object(
        descriptor.get("expected_continuation_heads"), "expected continuation heads"
    )
    _same_heads(final_heads, expected_heads, "failed Phase 5 retry successor continuation heads")
    pinned_terminal_heads = _require_object(
        pin.get("terminal_heads"), "failed Phase 5 retry successor terminal head pins"
    )
    _same_heads(
        final_heads, pinned_terminal_heads, "failed Phase 5 retry successor terminal heads"
    )
    terminal_confirmation = _json_bytes(
        _unique_basename(members, "terminal-confirmation.json"),
        "failed Phase 5 retry successor terminal confirmation",
    )
    _expect(
        terminal_confirmation,
        observations[-1].get("status"),
        "failed Phase 5 retry successor terminal confirmation",
    )

    all_predecessor_receipts = [
        *_require_list(prefix.get("receipts"), "failed Phase 5 prefix receipts"),
        *predecessor_receipts,
    ]
    predecessor_ids = {item.get("run_id") for item in all_predecessor_receipts}
    predecessor_executions = {
        item.get("cloud_run_execution") for item in all_predecessor_receipts
    }
    if any(item.get("run_id") in predecessor_ids for item in receipts):
        _fail("failed Phase 5 retry successor reused a predecessor Runtime receipt")
    if any(item.get("cloud_run_execution") in predecessor_executions for item in receipts):
        _fail("failed Phase 5 retry successor reused a predecessor Cloud Run execution")
    predecessor_finish = max(
        _parse_time(item.get("finished_at"), "failed retry predecessor finished_at")
        for item in predecessor_receipts
    )
    successor_start = min(
        _parse_time(item.get("started_at"), "failed retry successor started_at")
        for item in receipts
    )
    if successor_start <= predecessor_finish:
        _fail("failed Phase 5 retry successor overlaps its predecessor retry")

    interval_start_text = _unique_basename(members, "fresh-cycle-started-at.txt").decode(
        "ascii"
    ).strip()
    interval_finish_text = _unique_basename(members, "fresh-cycle-finished-at.txt").decode(
        "ascii"
    ).strip()
    interval_start = _parse_time(
        interval_start_text, "failed retry successor fresh-cycle started_at"
    )
    interval_finish = _parse_time(
        interval_finish_text, "failed retry successor fresh-cycle finished_at"
    )
    if interval_finish < interval_start:
        _fail("failed retry successor fresh-cycle interval finished before it started")

    legacy_run_inventories = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/legacy-{role}-runs-terminal.json"),
                f"failed retry successor {role} run inventory",
            ),
            f"failed retry successor {role} run inventory",
        )
        for role in LEGACY_HIGH_WATER_ROLES
    ]
    legacy_workflow_states = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/legacy-{role}-workflow-terminal.json"),
                f"failed retry successor {role} workflow state",
            ),
            f"failed retry successor {role} workflow state",
        )
        for role in LEGACY_HIGH_WATER_ROLES
    ]
    runtime_execution_inventories = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/runtime-{role}-executions-terminal.json"),
                f"failed retry successor {role} Runtime inventory",
            ),
            f"failed retry successor {role} Runtime inventory",
        )
        for role in LEGACY_HIGH_WATER_ROLES
    ]
    evidence_files = {
        "legacy_run_inventories": [
            f"incident/legacy-{role}-runs-terminal.json" for role in LEGACY_HIGH_WATER_ROLES
        ],
        "legacy_workflow_states": [
            f"incident/legacy-{role}-workflow-terminal.json"
            for role in LEGACY_HIGH_WATER_ROLES
        ],
        "runtime_execution_inventories": [
            f"incident/runtime-{role}-executions-terminal.json"
            for role in LEGACY_HIGH_WATER_ROLES
        ],
    }
    evidence_digests = {
        field: [_sha256_bytes(_member(members, name)) for name in names]
        for field, names in evidence_files.items()
    }
    one_writer = {
        "fresh_cycle_interval": {
            "started_at": interval_start_text,
            "finished_at": interval_finish_text,
        },
        "overlapping_legacy_run_count": 0,
        "unexpected_runtime_execution_count": 0,
        "expected_runtime_execution_count": 4,
    }
    for field, digests in evidence_digests.items():
        one_writer[f"{field}_sha256"] = dict(zip(LEGACY_HIGH_WATER_ROLES, digests))
    predecessor_layer = len(FROZEN_LEGACY_SUCCESSOR_REVISIONS) - 2
    _validate_terminal_one_writer(
        descriptor=descriptor,
        replay=embedded_replay,
        manifest={"one_writer_evidence": one_writer},
        receipts=receipts,
        legacy_run_inventories=legacy_run_inventories,
        legacy_workflow_states=legacy_workflow_states,
        runtime_execution_inventories=runtime_execution_inventories,
        evidence_digests=evidence_digests,
        successor_layer=predecessor_layer,
    )
    legacy_artifact_inventories = [
        _require_object(
            _json_bytes(
                _member(members, f"incident/legacy-{role}-artifacts-terminal.json"),
                f"failed retry successor {role} artifact inventory",
            ),
            f"failed retry successor {role} artifact inventory",
        )
        for role in LEGACY_HIGH_WATER_ROLES[:3]
    ]
    _validate_high_water_artifact_inventories(
        descriptor, legacy_artifact_inventories, successor_layer=predecessor_layer
    )

    rollback = _require_object(
        _json_bytes(
            _unique_basename(members, "retry-rollback.json"),
            "failed Phase 5 retry successor rollback receipt",
        ),
        "failed Phase 5 retry successor rollback receipt",
    )
    for key, expected in {
        "schema_version": 1,
        "result": "phase5_failed_promotion_retry_rolled_back",
        "runtime_schedulers_paused": True,
        "web_public": False,
        "runtime_mode": "shadow",
        "observed_legacy_route_kind": "historic_active",
        "legacy_route_restored": True,
        "legacy_recovery_required": True,
        "legacy_recovery_action_complete": True,
        "temporary_execution_authority_removed": True,
        "temporary_service_account_user_removed": True,
        "temporary_private_web_invoker_removed": True,
        "temporary_scheduler_activation_authority_removed": True,
        "temporary_role_viewer_authority_removed": True,
        "cloud_sql_private_only": True,
        "vault_scheduler_state": "PAUSED",
    }.items():
        _expect(rollback.get(key), expected, f"failed Phase 5 retry successor rollback {key}")

    invalidation = _require_object(
        _json_bytes(
            _unique_basename(members, "phase5-completion-invalidation.json"),
            "failed Phase 5 retry successor completion invalidation",
        ),
        "failed Phase 5 retry successor completion invalidation",
    )
    for key, expected in {
        "schema_version": 1,
        "result": "phase5_completion_evidence_invalidated",
        "certification_eligible": False,
        "phase5_completion_claim_valid": False,
        "production_cutover_certified": False,
        "trigger": "workflow_failure_or_cancellation",
        "run_id": str(FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID),
        "run_attempt": str(pin.get("run_attempt")),
        "control_revision": FAILED_PHASE5_RETRY_SUCCESSOR_CONTROL_REVISION,
        "affirmative_completion_evidence_absent_before_rollback_artifact_upload": True,
    }.items():
        _expect(
            invalidation.get(key),
            expected,
            f"failed Phase 5 retry successor invalidation {key}",
        )
    invalidated_files = _require_list(
        invalidation.get("invalidated_files"),
        "failed Phase 5 retry successor invalidated files",
    )
    expected_invalidated_paths = [
        "phase5-complete.json",
        "phase5-complete.sha256",
        "terminal-manifest.json",
    ]
    if len(invalidated_files) != len(expected_invalidated_paths):
        _fail("failed Phase 5 retry successor invalidation file inventory is incomplete")
    for value, expected_path in zip(invalidated_files, expected_invalidated_paths):
        row = _require_object(value, f"failed retry successor invalidation {expected_path}")
        for key, expected in {
            "path": expected_path,
            "existed_before_invalidation": False,
            "prior_sha256": None,
            "disposition": "not_created",
        }.items():
            _expect(row.get(key), expected, f"failed retry successor invalidation {key}")

    dispatch = _require_object(
        _json_bytes(
            _unique_basename(members, "legacy-recovery-dispatch.json"),
            "failed Phase 5 retry successor recovery dispatch",
        ),
        "failed Phase 5 retry successor recovery dispatch",
    )
    _expect(
        dispatch.get("result"),
        "legacy_recovery_runs_succeeded",
        "failed retry successor recovery",
    )
    dispatches = _require_list(
        dispatch.get("workflows"), "failed retry successor recovery workflows"
    )
    layer_three_pins = _require_list(
        descriptor.get("frozen_legacy_successors"), "frozen successor pins"
    )[-2:]
    if len(dispatches) != 2 or len(layer_three_pins) != 2:
        _fail("failed retry successor recovery dispatch does not contain exactly two layer-three runs")
    for role, value, successor_pin in zip(
        ("legislative", "executive"), dispatches, layer_three_pins
    ):
        row = _require_object(value, f"failed retry successor {role} recovery dispatch")
        expected_workflow = PurePosixPath(RECOVERY_PATHS[role]).name
        for key, expected in {
            "result": "legacy_recovery_run_succeeded",
            "workflow": expected_workflow,
            "workflow_id": _require_object(
                successor_pin.get("workflow"), f"{role} layer-three successor workflow pin"
            ).get("id"),
            "control_revision": FAILED_PHASE5_RETRY_SUCCESSOR_CONTROL_REVISION,
            "dispatch_attempted": True,
            "run_id": successor_pin.get("run_id"),
            "status": "completed",
            "conclusion": "success",
            "run_attempt": successor_pin.get("run_attempt"),
        }.items():
            _expect(
                row.get(key), expected, f"failed retry successor {role} recovery dispatch {key}"
            )
        if _parse_time(
            _require_object(
                successor_pin.get("job"), f"{role} layer-three successor job pin"
            ).get("started_at"),
            f"{role} layer-three rollback recovery started_at",
        ) <= interval_finish:
            _fail(f"{role} layer-three rollback recovery did not begin after the fresh cycle")

    return {
        "run_id": FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID,
        "predecessor_run_id": FAILED_PHASE5_RETRY_RUN_ID,
        "artifact_id": artifact_pin.get("id"),
        "head_sha": pin.get("head_sha"),
        "job_id": job.get("id"),
        "conclusion": "failure",
        "result": "clean_cycle_rolled_back_noncertifying",
        "certification_eligible": False,
        "unique_successful_smoke_receipts": 4,
        "executions": receipts,
        "baseline_heads": _head_summary(_heads(baseline)),
        "final_heads": _head_summary(final_heads),
        "predecessor_replay_sha256": replay_sha,
        "legacy_global_one_writer_verified": True,
        "runtime_execution_set_verified": True,
        "completion_evidence_invalidated": True,
        "rollback_verified": True,
        "production_authority_transferred": False,
        "phase6_started": False,
    }


def _assert_current_runtime_state(
    current_status: Mapping[str, Any],
    final_heads: Mapping[str, Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
) -> None:
    current_heads = _heads(current_status)
    _same_heads(current_heads, _head_summary(final_heads), "current Runtime state")
    current_runs = _latest_runs(current_status)
    if set(current_runs) != set(NAMESPACES):
        _fail("current Runtime status lacks exact latest receipts")
    expected_runs = {item["job"]: item for item in receipts}
    for namespace in NAMESPACES:
        expected = expected_runs[namespace]
        for key, value in {
            "run_id": expected["run_id"],
            "status": "success",
            "runtime_mode": "production",
            "runtime_mode_verified": True,
            "trigger_source": "phase5_smoke",
            "side_effects_possible": False,
            "source_revision": RUNTIME_SOURCE_REVISION,
            "snapshot_generation": final_heads[namespace]["generation"],
            "snapshot_sha256": final_heads[namespace]["snapshot_sha256"],
        }.items():
            _expect(current_runs[namespace].get(key), value, f"current Runtime {namespace} {key}")


def _jsonl_records(data: bytes, label: str) -> list[dict[str, Any]]:
    return _observations_from_ndjson(data, label)


def _one_record_append(before: bytes, after: bytes, label: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if before and not before.endswith(b"\n"):
        _fail(f"{label} predecessor lacks a complete-line terminator")
    if not after.startswith(before):
        _fail(f"{label} successor does not preserve the exact predecessor byte prefix")
    previous = _jsonl_records(before, f"{label} predecessor")
    current = _jsonl_records(after, f"{label} successor")
    if len(current) != len(previous) + 1:
        _fail(f"{label} successor did not append exactly one record")
    return previous, current[-1]


def _analysis_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, Mapping):
        candidate = value.get("analyses")
        rows = candidate if isinstance(candidate, list) else []
    else:
        rows = []
    if not all(isinstance(row, Mapping) for row in rows):
        _fail("current Runtime AI analyses response is malformed")
    return list(rows)


def _validate_legacy_ai_conflict(
    descriptor: Mapping[str, Any],
    run_metadata: Mapping[str, Any],
    jobs_metadata: Mapping[str, Any],
    predecessor_artifact_metadata: Mapping[str, Any],
    predecessor_archive: Path,
    state_artifact_metadata: Mapping[str, Any],
    state_archive: Path,
    output_artifact_metadata: Mapping[str, Any],
    output_archive: Path,
    current_ai_analyses: Any,
    current_status: Mapping[str, Any],
    prefix_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    pin = _require_object(descriptor.get("concurrent_legacy_ai"), "concurrent legacy AI pin")
    job = _validate_run_job_metadata(
        pin,
        run_metadata,
        jobs_metadata,
        expected_run_id=CONCURRENT_LEGACY_AI_RUN_ID,
        expected_path=AI_WORKFLOW_PATH,
        expected_conclusion="success",
        expected_job_name="analyze",
    )
    predecessor_pin = _require_object(pin.get("predecessor_artifact"), "legacy AI predecessor pin")
    predecessor_members = _load_pinned_artifact(
        predecessor_archive,
        predecessor_artifact_metadata,
        predecessor_pin,
        producer_run_id=int(predecessor_pin.get("producer_run_id") or 0),
        producer_head_sha=str(predecessor_pin.get("producer_head_sha") or ""),
    )
    state_pin = _require_object(pin.get("state_artifact"), "legacy AI state pin")
    state_members = _load_pinned_artifact(
        state_archive,
        state_artifact_metadata,
        state_pin,
        producer_run_id=CONCURRENT_LEGACY_AI_RUN_ID,
        producer_head_sha=str(pin.get("head_sha")),
    )
    output_pin = _require_object(pin.get("output_artifact"), "legacy AI output pin")
    output_members = _load_pinned_artifact(
        output_archive,
        output_artifact_metadata,
        output_pin,
        producer_run_id=CONCURRENT_LEGACY_AI_RUN_ID,
        producer_head_sha=str(pin.get("head_sha")),
    )
    _expect(predecessor_pin.get("name"), "ai-analysis-state", "legacy AI predecessor name")
    _expect(state_pin.get("name"), "ai-analysis-state", "legacy AI successor name")
    _expect(
        output_pin.get("name"),
        f"ai-analysis-output-{CONCURRENT_LEGACY_AI_RUN_ID}-{pin.get('run_attempt')}",
        "legacy AI output name",
    )
    if len({predecessor_pin.get("id"), state_pin.get("id"), output_pin.get("id")}) != 3:
        _fail("legacy AI artifacts are not three distinct immutable artifacts")

    previous_analyses, appended_analysis = _one_record_append(
        _unique_basename(predecessor_members, "analyses.jsonl"),
        _unique_basename(state_members, "analyses.jsonl"),
        "legacy AI analyses.jsonl",
    )
    previous_runs, appended_run = _one_record_append(
        _unique_basename(predecessor_members, "runs.jsonl"),
        _unique_basename(state_members, "runs.jsonl"),
        "legacy AI runs.jsonl",
    )
    if any(
        row.get("analysis_id") == appended_analysis.get("analysis_id")
        or row.get("trade_id") == appended_analysis.get("trade_id")
        for row in previous_analyses
    ):
        _fail("legacy AI successor did not append a new deterministic analysis identity")
    counts = _require_object(pin.get("expected_counts"), "legacy AI count pins")
    for key, actual, expected in (
        ("predecessor_analyses", len(previous_analyses), 12),
        ("successor_analyses", len(previous_analyses) + 1, 13),
        ("predecessor_runs", len(previous_runs), 60),
        ("successor_runs", len(previous_runs) + 1, 61),
    ):
        _expect(counts.get(key), expected, f"legacy AI incident count pin {key}")
        _expect(actual, expected, f"legacy AI artifact count {key}")

    result = _json_bytes(_unique_basename(output_members, "ai-analysis-result.json"), "AI result")
    result = _require_object(result, "legacy AI result")
    for key, expected in {
        "result_schema_version": 2,
        "repository_id": REPOSITORY_ID,
        "workflow_run_id": str(CONCURRENT_LEGACY_AI_RUN_ID),
        "workflow_run_attempt": str(pin.get("run_attempt")),
        "source_revision": pin.get("head_sha"),
        "run_status": "success",
        "state_publishable": True,
        "success": True,
        "attempted_count": 1,
        "completed_count": 1,
        "alerted_count": 0,
        "delivery_phase_started": False,
        "delivery_attempt_count": 0,
        "delivery_confirmed_count": 0,
        "delivery_uncertain_count": 0,
    }.items():
        _expect(result.get(key), expected, f"legacy AI result {key}")
    result_analyses = _require_list(result.get("analyses"), "legacy AI result analyses")
    if len(result_analyses) != 1:
        _fail("legacy AI result does not contain exactly one successful analysis")
    _expect(result_analyses[0], appended_analysis, "legacy AI appended analysis/result")
    _expect(appended_run.get("run_key"), f"{CONCURRENT_LEGACY_AI_RUN_ID}:{pin.get('run_attempt')}", "legacy AI run key")
    for key, expected in {
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
    }.items():
        _expect(appended_run.get(key), expected, f"legacy AI appended run {key}")

    predecessor_state = _json_bytes(_unique_basename(predecessor_members, "state.json"), "AI predecessor state")
    successor_state = _json_bytes(_unique_basename(state_members, "state.json"), "AI successor state")
    predecessor_state = _require_object(predecessor_state, "AI predecessor state")
    successor_state = _require_object(successor_state, "AI successor state")
    _expect(successor_state.get("last_success_utc"), result.get("finished_utc"), "legacy AI success marker")
    _expect(
        successor_state.get("candidate_alert_deliveries"),
        predecessor_state.get("candidate_alert_deliveries"),
        "legacy AI suppressed-alert state",
    )

    smoke_start = min(_parse_time(item["started_at"], "smoke started_at") for item in prefix_receipts)
    smoke_finish = max(_parse_time(item["finished_at"], "smoke finished_at") for item in prefix_receipts)
    ai_start = _parse_time(job["started_at"], "legacy AI job started_at")
    ai_finish = _parse_time(job["completed_at"], "legacy AI job completed_at")
    if ai_start >= smoke_finish or ai_finish <= smoke_start:
        _fail("legacy AI writer did not overlap the failed Phase 5 protected-writer interval")

    conflict = _require_object(pin.get("conflict"), "legacy/Runtime duplicate conflict pin")
    snapshot_digest = conflict.get("runtime_snapshot_sha256")
    if not isinstance(snapshot_digest, str) or not SHA64.fullmatch(snapshot_digest):
        _fail("Runtime snapshot conflict digest pin is invalid")
    if not snapshot_digest.startswith(RUNTIME_SNAPSHOT_DIGEST_PREFIX):
        _fail("Runtime snapshot conflict digest does not identify the audited incident")
    current_heads = _heads(current_status)
    _expect(
        current_heads["dashboard"].get("snapshot_sha256"),
        snapshot_digest,
        "current dashboard snapshot conflict binding",
    )
    for key in ("analysis_id", "trade_id", "document_content_hash"):
        value = conflict.get(key)
        if not isinstance(value, str) or not value:
            _fail(f"legacy/Runtime conflict {key} pin is missing")
        if key == "document_content_hash" and SHA64.fullmatch(value) is None:
            _fail("legacy/Runtime conflict document_content_hash is invalid")
        _expect(appended_analysis.get(key), value, f"legacy conflict analysis {key}")
    rows = _analysis_rows(current_ai_analyses)
    analysis_id_matches = [
        row for row in rows if row.get("analysis_id") == conflict["analysis_id"]
    ]
    trade_id_matches = [row for row in rows if row.get("trade_id") == conflict["trade_id"]]
    exact = [
        row
        for row in rows
        if row.get("analysis_id") == conflict["analysis_id"]
        and row.get("trade_id") == conflict["trade_id"]
    ]
    if len(analysis_id_matches) != 1 or len(trade_id_matches) != 1 or len(exact) != 1:
        _fail("current Runtime snapshot does not contain the conflicting deterministic IDs exactly once")
    runtime_analysis = exact[0]
    _expect(
        runtime_analysis.get("document_content_hash"),
        conflict["document_content_hash"],
        "Runtime duplicate document content hash",
    )
    for key in ("openai_response_id", "classification", "score"):
        if runtime_analysis.get(key) == appended_analysis.get(key):
            _fail(f"legacy/Runtime duplicate does not differ in {key}")
    _expect(pin.get("merge_or_import_authorized"), False, "legacy artifact merge/import authorization")

    return {
        "run_id": CONCURRENT_LEGACY_AI_RUN_ID,
        "run_attempt": pin.get("run_attempt"),
        "head_sha": pin.get("head_sha"),
        "job_id": job.get("id"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "state_artifact_id": state_pin.get("id"),
        "state_artifact_sha256": _digest_pin(state_pin.get("digest"), "legacy AI state digest"),
        "output_artifact_id": output_pin.get("id"),
        "predecessor_artifact_id": predecessor_pin.get("id"),
        "prefix_preserved": True,
        "analyses_appended": 1,
        "runs_appended": 1,
        "successful_analyses": 1,
        "alerts_attempted": 0,
        "state_publishable": True,
        "global_one_writer_interval_violated": True,
        "conflicting_runtime_snapshot_sha256": snapshot_digest,
        "conflicting_analysis_id": conflict["analysis_id"],
        "conflicting_trade_id": conflict["trade_id"],
        "conflicting_document_content_hash": conflict["document_content_hash"],
        "same_document_content_hash": True,
        "different_openai_response_id": True,
        "different_classification": True,
        "different_score": True,
        "disposition": "quarantined_separate_legacy_artifact",
        "merge_or_import_authorized": False,
    }


def _validate_recoveries(
    descriptor: Mapping[str, Any],
    repository_root: Path,
    run_metadatas: Sequence[Mapping[str, Any]],
    jobs_metadatas: Sequence[Mapping[str, Any]],
    predecessor_artifact_metadatas: Sequence[Mapping[str, Any]],
    predecessor_archives: Sequence[Path],
    artifact_metadatas: Sequence[Mapping[str, Any]],
    archives: Sequence[Path],
    output_artifact_metadatas: Sequence[Mapping[str, Any]],
    output_archives: Sequence[Path],
    *,
    after_time: Any,
) -> list[dict[str, Any]]:
    pins = _require_list(descriptor.get("recovery_runs"), "recovery run pins")
    collections = (
        pins,
        run_metadatas,
        jobs_metadatas,
        predecessor_artifact_metadatas,
        predecessor_archives,
        artifact_metadatas,
        archives,
        output_artifact_metadatas,
        output_archives,
    )
    if any(len(items) != 2 for items in collections):
        _fail("reconciliation requires exactly two recovery runs")
    expected_roles = ("legislative", "executive")
    result: list[dict[str, Any]] = []
    for index, (pin_value, run, jobs, predecessor_metadata, predecessor_archive,
                artifact_metadata, archive, output_metadata, output_archive, role, run_id) in enumerate(
        zip(
            pins,
            run_metadatas,
            jobs_metadatas,
            predecessor_artifact_metadatas,
            predecessor_archives,
            artifact_metadatas,
            archives,
            output_artifact_metadatas,
            output_archives,
            expected_roles,
            RECOVERY_RUN_IDS,
        ),
        start=1,
    ):
        pin = _require_object(pin_value, f"recovery pin {index}")
        _expect(pin.get("role"), role, f"recovery pin {index} role")
        job = _validate_run_job_metadata(
            pin,
            run,
            jobs,
            expected_run_id=run_id,
            expected_path=RECOVERY_PATHS[role],
            expected_conclusion="success",
            expected_job_name="track",
        )
        _verify_tree_equal_descendant(
            repository_root,
            CERTIFIED_CONTROL_REVISION,
            str(pin.get("head_sha")),
            CERTIFIED_TREE_SHA,
        )
        if _parse_time(job["started_at"], f"{role} recovery started_at") < after_time:
            _fail(f"{role} recovery began before the concurrent writer completed")

        predecessor_pin = _require_object(
            pin.get("predecessor_artifact"), f"{role} predecessor artifact pin"
        )
        _expect(
            predecessor_pin.get("name"),
            RECOVERY_ARTIFACT_NAMES[role],
            f"{role} predecessor protected artifact name",
        )
        predecessor_run_id = predecessor_pin.get("producer_run_id")
        predecessor_head_sha = predecessor_pin.get("producer_head_sha")
        if (
            isinstance(predecessor_run_id, bool)
            or not isinstance(predecessor_run_id, int)
            or predecessor_run_id < 1
        ):
            _fail(f"{role} predecessor producer run ID pin is invalid")
        if (
            not isinstance(predecessor_head_sha, str)
            or SHA40.fullmatch(predecessor_head_sha) is None
        ):
            _fail(f"{role} predecessor producer head SHA pin is invalid")
        predecessor_members = _load_pinned_artifact(
            Path(predecessor_archive),
            predecessor_metadata,
            predecessor_pin,
            producer_run_id=predecessor_run_id,
            producer_head_sha=predecessor_head_sha,
        )
        predecessor_created = _parse_time(
            predecessor_metadata.get("created_at"), f"{role} predecessor artifact created_at"
        )
        if predecessor_created >= _parse_time(job["started_at"], f"{role} recovery started_at"):
            _fail(f"{role} predecessor artifact was not created before the recovery")

        artifact_pin = _require_object(pin.get("artifact"), f"{role} recovery artifact pin")
        _expect(
            artifact_pin.get("name"),
            RECOVERY_ARTIFACT_NAMES[role],
            f"{role} recovery protected artifact name",
        )
        state_members = _load_pinned_artifact(
            Path(archive),
            artifact_metadata,
            artifact_pin,
            producer_run_id=run_id,
            producer_head_sha=str(pin.get("head_sha")),
        )
        current_created = _parse_time(
            artifact_metadata.get("created_at"), f"{role} recovery artifact created_at"
        )
        if current_created <= predecessor_created:
            _fail(f"{role} recovery artifact does not succeed its pinned predecessor")
        output_pin = _require_object(
            pin.get("output_artifact"), f"{role} recovery output artifact pin"
        )
        expected_output_name = (
            f"legislative-purchase-output-{run_id}-{pin.get('run_attempt')}"
            if role == "legislative"
            else f"executive-purchase-output-{run_id}"
        )
        _expect(
            output_pin.get("name"), expected_output_name, f"{role} recovery output artifact name"
        )
        output_members = _load_pinned_artifact(
            Path(output_archive),
            output_metadata,
            output_pin,
            producer_run_id=run_id,
            producer_head_sha=str(pin.get("head_sha")),
        )
        recovery_result = _validate_zero_change_recovery(
            role=role,
            run_id=run_id,
            run_attempt=int(pin.get("run_attempt")),
            event=str(pin.get("event")),
            job=job,
            predecessor_members=predecessor_members,
            state_members=state_members,
            output_members=output_members,
        )
        result.append(
            {
                "role": role,
                "run_id": run_id,
                "run_attempt": pin.get("run_attempt"),
                "head_sha": pin.get("head_sha"),
                "job_id": job.get("id"),
                "conclusion": "success",
                "certified_tree_equal_descendant": True,
                "predecessor_artifact_id": predecessor_pin.get("id"),
                "predecessor_artifact_sha256": _digest_pin(
                    predecessor_pin.get("digest"), f"{role} predecessor artifact digest"
                ),
                "protected_artifact_id": artifact_pin.get("id"),
                "protected_artifact_sha256": _digest_pin(
                    artifact_pin.get("digest"), f"{role} protected artifact digest"
                ),
                "output_artifact_id": output_pin.get("id"),
                "output_artifact_sha256": _digest_pin(
                    output_pin.get("digest"), f"{role} output artifact digest"
                ),
                "result_started_at": recovery_result["started_utc"],
                "result_finished_at": recovery_result["finished_utc"],
                "protected_domain_data_unchanged": True,
                "protected_domain_member_count": len(RECOVERY_PROTECTED_DOMAIN_MEMBERS[role]),
                "run_receipt_appended_count": 1,
                "state_change_keys": ["last_attempt_utc", "last_success_utc"],
            }
        )
    return result


def _validate_frozen_legacy_successors(
    descriptor: Mapping[str, Any],
    repository_root: Path,
    predecessor_artifact_metadatas: Sequence[Mapping[str, Any]],
    predecessor_archives: Sequence[Path],
    run_metadatas: Sequence[Mapping[str, Any]],
    jobs_metadatas: Sequence[Mapping[str, Any]],
    artifact_metadatas: Sequence[Mapping[str, Any]],
    archives: Sequence[Path],
    output_artifact_metadatas: Sequence[Mapping[str, Any]],
    output_archives: Sequence[Path],
) -> list[dict[str, Any]]:
    recovery_pins = _require_list(descriptor.get("recovery_runs"), "recovery run pins")
    successor_pins = _require_list(
        descriptor.get("frozen_legacy_successors"), "frozen legacy successor pins"
    )
    expected_count = len(FROZEN_LEGACY_SUCCESSOR_RUN_IDS)
    if len(recovery_pins) != 2:
        _fail("reconciliation requires exactly two original recovery runs")
    if len(predecessor_artifact_metadatas) != 2 or len(predecessor_archives) != 2:
        _fail("reconciliation requires exactly two original successor predecessors")
    if any(
        len(items) != expected_count
        for items in (
            successor_pins,
            run_metadatas,
            jobs_metadatas,
            artifact_metadatas,
            archives,
            output_artifact_metadatas,
            output_archives,
        )
    ):
        _fail(f"reconciliation requires exactly {expected_count} frozen legacy successors")

    _verify_frozen_legacy_successor_revision(repository_root)
    result: list[dict[str, Any]] = []
    roles = ("legislative", "executive") * len(FROZEN_LEGACY_SUCCESSOR_REVISIONS)
    expected_events = ("schedule", "schedule") + ("workflow_dispatch",) * (
        expected_count - 2
    )
    for offset, (pin_value, run, jobs, artifact_metadata, archive, output_metadata, output_archive) in enumerate(
        zip(
            successor_pins,
            run_metadatas,
            jobs_metadatas,
            artifact_metadatas,
            archives,
            output_artifact_metadatas,
            output_archives,
        )
    ):
        index = offset + 1
        role_index = offset % 2
        layer_index = offset // 2
        role = roles[offset]
        run_id = FROZEN_LEGACY_SUCCESSOR_RUN_IDS[offset]
        revision = FROZEN_LEGACY_SUCCESSOR_REVISIONS[layer_index]
        pin = _require_object(pin_value, f"frozen legacy successor pin {index}")
        _expect(pin.get("role"), role, f"frozen legacy successor pin {index} role")
        _expect(pin.get("event"), expected_events[offset], f"{role} layer {layer_index + 1} event")
        _expect(
            pin.get("head_sha"),
            revision,
            f"{role} frozen legacy successor layer {layer_index + 1} revision",
        )
        job = _validate_run_job_metadata(
            pin,
            run,
            jobs,
            expected_run_id=run_id,
            expected_path=RECOVERY_PATHS[role],
            expected_conclusion="success",
            expected_job_name="track",
        )
        prior_layer_pins = (
            recovery_pins
            if layer_index == 0
            else successor_pins[(layer_index - 1) * 2 : layer_index * 2]
        )
        prior_layer_finished = max(
            _parse_time(
                _require_object(value, f"layer {layer_index} predecessor pin")
                .get("job", {})
                .get("completed_at"),
                f"layer {layer_index} predecessor completed_at",
            )
            for value in prior_layer_pins
        )
        if _parse_time(job["started_at"], f"{role} successor started_at") <= prior_layer_finished:
            _fail(
                f"{role} frozen legacy successor layer {layer_index + 1} did not begin "
                "after both prior-layer runs"
            )

        predecessor_run_pin = _require_object(
            recovery_pins[role_index] if layer_index == 0 else successor_pins[offset - 2],
            f"{role} layer {layer_index + 1} predecessor run pin",
        )
        expected_predecessor_artifact_pin = _require_object(
            predecessor_run_pin.get("artifact"),
            f"{role} layer {layer_index + 1} predecessor artifact source pin",
        )
        predecessor_pin = _require_object(
            pin.get("predecessor_artifact"), f"{role} successor predecessor artifact pin"
        )
        for key in ("id", "name", "size_in_bytes", "digest", "expires_at"):
            _expect(
                predecessor_pin.get(key),
                expected_predecessor_artifact_pin.get(key),
                f"{role} successor predecessor {key}",
            )
        _expect(
            predecessor_pin.get("producer_run_id"),
            predecessor_run_pin.get("run_id"),
            f"{role} successor predecessor producer run",
        )
        _expect(
            predecessor_pin.get("producer_head_sha"),
            predecessor_run_pin.get("head_sha"),
            f"{role} successor predecessor producer revision",
        )
        predecessor_metadata = (
            predecessor_artifact_metadatas[role_index]
            if layer_index == 0
            else artifact_metadatas[offset - 2]
        )
        predecessor_archive = (
            predecessor_archives[role_index] if layer_index == 0 else archives[offset - 2]
        )
        predecessor_members = _load_pinned_artifact(
            Path(predecessor_archive),
            predecessor_metadata,
            predecessor_pin,
            producer_run_id=int(predecessor_run_pin["run_id"]),
            producer_head_sha=str(predecessor_run_pin["head_sha"]),
        )
        predecessor_created = _parse_time(
            predecessor_metadata.get("created_at"),
            f"{role} successor predecessor artifact created_at",
        )
        if predecessor_created >= _parse_time(job["started_at"], f"{role} successor started_at"):
            _fail(f"{role} successor predecessor artifact was not created before the run")

        artifact_pin = _require_object(pin.get("artifact"), f"{role} successor artifact pin")
        _expect(
            artifact_pin.get("name"),
            RECOVERY_ARTIFACT_NAMES[role],
            f"{role} successor protected artifact name",
        )
        state_members = _load_pinned_artifact(
            Path(archive),
            artifact_metadata,
            artifact_pin,
            producer_run_id=run_id,
            producer_head_sha=revision,
        )
        current_created = _parse_time(
            artifact_metadata.get("created_at"), f"{role} successor artifact created_at"
        )
        if current_created <= predecessor_created:
            _fail(f"{role} successor artifact does not follow its prior-layer predecessor")

        output_pin = _require_object(
            pin.get("output_artifact"), f"{role} successor output artifact pin"
        )
        expected_output_name = (
            f"legislative-purchase-output-{run_id}-{pin.get('run_attempt')}"
            if role == "legislative"
            else f"executive-purchase-output-{run_id}"
        )
        _expect(
            output_pin.get("name"),
            expected_output_name,
            f"{role} successor output artifact name",
        )
        output_members = _load_pinned_artifact(
            Path(output_archive),
            output_metadata,
            output_pin,
            producer_run_id=run_id,
            producer_head_sha=revision,
        )
        successor_result = _validate_zero_change_recovery(
            role=role,
            run_id=run_id,
            run_attempt=int(pin.get("run_attempt")),
            event=str(pin.get("event")),
            job=job,
            predecessor_members=predecessor_members,
            state_members=state_members,
            output_members=output_members,
        )
        result.append(
            {
                "role": role,
                "run_id": run_id,
                "run_attempt": pin.get("run_attempt"),
                "head_sha": pin.get("head_sha"),
                "job_id": job.get("id"),
                "conclusion": "success",
                "successor_layer": layer_index + 1,
                "incident_only_revision_allowlist_verified": True,
                "predecessor_run_id": predecessor_run_pin.get("run_id"),
                "predecessor_artifact_id": predecessor_pin.get("id"),
                "predecessor_artifact_sha256": _digest_pin(
                    predecessor_pin.get("digest"), f"{role} successor predecessor digest"
                ),
                "protected_artifact_id": artifact_pin.get("id"),
                "protected_artifact_sha256": _digest_pin(
                    artifact_pin.get("digest"), f"{role} successor protected artifact digest"
                ),
                "output_artifact_id": output_pin.get("id"),
                "output_artifact_sha256": _digest_pin(
                    output_pin.get("digest"), f"{role} successor output artifact digest"
                ),
                "result_started_at": successor_result["started_utc"],
                "result_finished_at": successor_result["finished_utc"],
                "protected_domain_data_unchanged": True,
                "protected_domain_member_count": len(RECOVERY_PROTECTED_DOMAIN_MEMBERS[role]),
                "run_receipt_appended_count": 1,
                "state_change_keys": ["last_attempt_utc", "last_success_utc"],
            }
        )
    return result


def _validate_zero_change_recovery(
    *,
    role: str,
    run_id: int,
    run_attempt: int,
    event: str,
    job: Mapping[str, Any],
    predecessor_members: Mapping[str, bytes],
    state_members: Mapping[str, bytes],
    output_members: Mapping[str, bytes],
) -> Mapping[str, Any]:
    for member_name in RECOVERY_PROTECTED_DOMAIN_MEMBERS[role]:
        predecessor_value = _unique_basename(predecessor_members, member_name)
        successor_value = _unique_basename(state_members, member_name)
        if successor_value != predecessor_value:
            _fail(f"{role} protected domain member {member_name} changed during recovery")

    result_member = RECOVERY_RESULT_MEMBERS[role]
    output = _json_bytes(
        _unique_basename(output_members, result_member), f"{role} recovery {result_member}"
    )
    output = _require_object(output, f"{role} recovery result")
    for key, expected in {
        "branch": role,
        "success": True,
        "overall_status": "ok",
        "discovery_complete": role == "legislative",
    }.items():
        _expect(output.get(key), expected, f"{role} recovery result {key}")
    dimensions = RECOVERY_COUNT_DIMENSIONS[role]
    for field in (
        "baseline_counts",
        "new_filing_counts",
        "cataloged_filing_counts",
        "transaction_counts",
        "purchase_counts",
        "pending_review_counts",
        "alerted_filing_counts",
    ):
        _expect(output.get(field), dimensions, f"{role} recovery result {field}")
    for field in ("filings", "transactions", "purchases", "pending_reviews", "errors"):
        _expect(output.get(field), [], f"{role} recovery result {field}")
    expected_sources = {"house": "ok", "senate": "ok"} if role == "legislative" else {}
    _expect(output.get("source_statuses"), expected_sources, f"{role} recovery source statuses")
    historical = _require_object(output.get("historical_backfill"), f"{role} historical backfill")
    _expect(historical.get("completed_this_run"), 0, f"{role} historical completions")
    _expect(historical.get("transactions_appended"), 0, f"{role} historical transactions")

    started = _parse_time(output.get("started_utc"), f"{role} recovery result started_utc")
    finished = _parse_time(output.get("finished_utc"), f"{role} recovery result finished_utc")
    if finished < started:
        _fail(f"{role} recovery result finished before it started")
    if started < _parse_time(job.get("started_at"), f"{role} recovery job started_at"):
        _fail(f"{role} recovery result began before its authoritative job")
    if finished > _parse_time(job.get("completed_at"), f"{role} recovery job completed_at"):
        _fail(f"{role} recovery result finished after its authoritative job")

    predecessor_state = _json_bytes(
        _unique_basename(predecessor_members, "state.json"),
        f"{role} predecessor recovery state",
    )
    predecessor_state = _require_object(predecessor_state, f"{role} predecessor recovery state")
    state = _json_bytes(_unique_basename(state_members, "state.json"), f"{role} recovery state")
    state = _require_object(state, f"{role} recovery state")
    marker_keys = {"last_attempt_utc", "last_success_utc"}
    predecessor_non_markers = {
        key: value for key, value in predecessor_state.items() if key not in marker_keys
    }
    successor_non_markers = {key: value for key, value in state.items() if key not in marker_keys}
    _expect(
        successor_non_markers,
        predecessor_non_markers,
        f"{role} recovery state non-marker content",
    )
    for marker in marker_keys:
        if marker not in predecessor_state or marker not in state:
            _fail(f"{role} recovery state is missing {marker}")
        if predecessor_state[marker] == state[marker]:
            _fail(f"{role} recovery state marker {marker} did not advance")
        if _parse_time(
            state[marker], f"{role} recovery state {marker}"
        ) <= _parse_time(
            predecessor_state[marker], f"{role} predecessor recovery state {marker}"
        ):
            _fail(f"{role} recovery state marker {marker} did not advance chronologically")
    last_success = _parse_time(state.get("last_success_utc"), f"{role} last success marker")
    if last_success < started or last_success > finished:
        _fail(f"{role} last success marker is outside the recovery result interval")
    if (finished - last_success).total_seconds() > 1:
        _fail(f"{role} last success marker is more than one second before result finish")
    last_attempt = _parse_time(state.get("last_attempt_utc"), f"{role} last attempt marker")
    if last_attempt < started or last_attempt > finished:
        _fail(f"{role} last attempt marker is outside the recovery result interval")
    source_counts = _require_object(output.get("source_counts"), f"{role} source counts")
    _expect(state.get("last_counts"), source_counts, f"{role} protected source counts")
    predecessor_runs_bytes = _unique_basename(predecessor_members, "runs.jsonl")
    runs_bytes = _unique_basename(state_members, "runs.jsonl")
    if not runs_bytes.startswith(predecessor_runs_bytes):
        _fail(f"{role} recovery runs are not an exact predecessor byte prefix")
    predecessor_runs = _jsonl_records(
        predecessor_runs_bytes, f"{role} predecessor recovery runs"
    )
    runs = _jsonl_records(runs_bytes, f"{role} recovery runs")
    if len(runs) != len(predecessor_runs) + 1 or runs[:-1] != predecessor_runs:
        _fail(f"{role} recovery did not append exactly one run receipt")
    if not runs:
        _fail(f"{role} recovery protected artifact has no run receipt")
    latest = runs[-1]
    for key, expected in {
        "run_key": f"{run_id}:{run_attempt}",
        "branch": role,
        "event_name": event,
        "trigger_source": event,
        "success": True,
        "overall_status": "ok",
        "started_utc": output.get("started_utc"),
        "finished_utc": output.get("finished_utc"),
        "errors": [],
    }.items():
        _expect(latest.get(key), expected, f"{role} protected run receipt {key}")
    for field in (
        "baseline_counts",
        "new_filing_counts",
        "cataloged_filing_counts",
        "transaction_counts",
        "purchase_counts",
        "pending_review_counts",
        "source_counts",
        "historical_backfill",
    ):
        _expect(latest.get(field), output.get(field), f"{role} result/run receipt {field}")
    return output


def _run_matches_pin(run: Mapping[str, Any], pin: Mapping[str, Any], label: str) -> None:
    workflow = _require_object(pin.get("workflow"), f"{label} workflow pin")
    for key in ("run_id", "run_number", "run_attempt"):
        value = pin.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            _fail(f"{label} {key} pin is invalid")
    if not isinstance(pin.get("head_sha"), str) or SHA40.fullmatch(str(pin.get("head_sha"))) is None:
        _fail(f"{label} head SHA pin is invalid")
    workflow_id = workflow.get("id")
    if isinstance(workflow_id, bool) or not isinstance(workflow_id, int) or workflow_id < 1:
        _fail(f"{label} workflow ID pin is invalid")
    if not isinstance(workflow.get("name"), str) or not workflow.get("name"):
        _fail(f"{label} workflow name pin is invalid")
    for key in ("created_at", "run_started_at", "updated_at"):
        _parse_time(pin.get(key), f"{label} {key} pin")
    for key, expected in {
        "id": pin.get("run_id"),
        "run_number": pin.get("run_number"),
        "run_attempt": pin.get("run_attempt"),
        "workflow_id": workflow.get("id"),
        "name": workflow.get("name"),
        "event": pin.get("event"),
        "head_branch": "main",
        "head_sha": pin.get("head_sha"),
        "status": "completed",
        "conclusion": "success",
        "created_at": pin.get("created_at"),
        "run_started_at": pin.get("run_started_at"),
        "updated_at": pin.get("updated_at"),
    }.items():
        _expect(run.get(key), expected, f"{label} {key}")
    _expect(_normalize_workflow_path(run.get("path")), workflow.get("path"), f"{label} path")
    for key in ("repository", "head_repository"):
        boundary = _require_object(run.get(key), f"{label} {key}")
        _expect(boundary.get("id"), REPOSITORY_ID, f"{label} {key} id")


def _high_water_pins(
    descriptor: Mapping[str, Any], *, successor_layer: int = -1
) -> list[Mapping[str, Any]]:
    successors = _require_list(
        descriptor.get("frozen_legacy_successors"), "frozen legacy successor pins"
    )
    expected_count = len(FROZEN_LEGACY_SUCCESSOR_RUN_IDS)
    if len(successors) != expected_count:
        _fail(f"reconciliation requires exactly {expected_count} frozen legacy successor pins")
    roles = ("legislative", "executive") * len(FROZEN_LEGACY_SUCCESSOR_REVISIONS)
    validated: list[Mapping[str, Any]] = []
    for index, (value, role, run_id) in enumerate(
        zip(successors, roles, FROZEN_LEGACY_SUCCESSOR_RUN_IDS)
    ):
        pin = _require_object(value, f"{role} frozen legacy successor pin {index + 1}")
        layer_index = index // 2
        _expect(pin.get("role"), role, f"{role} frozen successor role {index + 1}")
        _expect(pin.get("run_id"), run_id, f"{role} frozen successor run ID {index + 1}")
        _expect(
            pin.get("head_sha"),
            FROZEN_LEGACY_SUCCESSOR_REVISIONS[layer_index],
            f"{role} frozen successor revision {index + 1}",
        )
        validated.append(pin)
    if successor_layer == -1:
        successor_layer = len(FROZEN_LEGACY_SUCCESSOR_REVISIONS) - 1
    if successor_layer < 0 or successor_layer >= len(FROZEN_LEGACY_SUCCESSOR_REVISIONS):
        _fail("legacy high-water successor layer is invalid")
    legislative, executive = validated[successor_layer * 2 : successor_layer * 2 + 2]
    dashboard = _require_object(descriptor.get("legacy_dashboard"), "legacy dashboard pin")
    _expect(dashboard.get("role"), "dashboard", "legacy dashboard role")
    _expect(
        _require_object(dashboard.get("workflow"), "legacy dashboard workflow").get("path"),
        DASHBOARD_WORKFLOW_PATH,
        "legacy dashboard workflow path",
    )
    return [
        legislative,
        executive,
        _require_object(descriptor.get("concurrent_legacy_ai"), "concurrent legacy AI pin"),
        dashboard,
    ]


def _validate_high_water_run_inventories(
    descriptor: Mapping[str, Any],
    inventories: Sequence[Mapping[str, Any]],
    *,
    label: str,
    successor_layer: int = -1,
) -> tuple[list[dict[str, Any]], list[str]]:
    pins = _high_water_pins(descriptor, successor_layer=successor_layer)
    if len(inventories) != 4:
        _fail(f"{label} requires exactly four legacy workflow run inventories")
    summaries: list[dict[str, Any]] = []
    digests: list[str] = []
    for role, pin, inventory in zip(LEGACY_HIGH_WATER_ROLES, pins, inventories):
        rows = _require_list(inventory.get("workflow_runs"), f"{label} {role} workflow_runs")
        total = inventory.get("total_count")
        if isinstance(total, bool) or not isinstance(total, int) or total != len(rows) or not rows:
            _fail(f"{label} {role} workflow run inventory is incomplete")
        normalized = [
            _require_object(row, f"{label} {role} workflow run") for row in rows
        ]
        ids = [row.get("id") for row in normalized]
        if len(set(ids)) != len(ids):
            _fail(f"{label} {role} workflow run inventory contains duplicate IDs")
        current = normalized[0]
        _run_matches_pin(current, pin, f"{label} {role} high-water run")
        pinned_created = _parse_time(pin.get("created_at"), f"{label} {role} pinned created_at")
        for row in normalized[1:]:
            created = _parse_time(row.get("created_at"), f"{label} {role} run created_at")
            if created >= pinned_created:
                _fail(f"{label} {role} workflow run high-water ordering is ambiguous")
            if row.get("status") != "completed":
                _fail(f"{label} {role} has an older authoritative run still in flight")
        summaries.append(
            {
                "role": role,
                "run_id": pin.get("run_id"),
                "workflow_id": _require_object(pin.get("workflow"), f"{role} workflow").get("id"),
                "workflow_name": _require_object(pin.get("workflow"), f"{role} workflow").get("name"),
                "workflow_path": _require_object(pin.get("workflow"), f"{role} workflow").get("path"),
                "created_at": pin.get("created_at"),
                "status": "completed",
                "conclusion": "success",
            }
        )
        digests.append(_canonical_sha256(inventory))
    return summaries, digests


def _validate_high_water_artifact_inventories(
    descriptor: Mapping[str, Any],
    inventories: Sequence[Mapping[str, Any]],
    *,
    successor_layer: int = -1,
) -> list[str]:
    pins = _high_water_pins(descriptor, successor_layer=successor_layer)[:3]
    artifact_pins = [
        _require_object(pins[0].get("artifact"), "legislative protected artifact pin"),
        _require_object(pins[1].get("artifact"), "executive protected artifact pin"),
        _require_object(pins[2].get("state_artifact"), "AI protected artifact pin"),
    ]
    if len(inventories) != 3:
        _fail("replay requires exactly three protected-artifact inventories")
    digests: list[str] = []
    for role, run_pin, artifact_pin, inventory in zip(
        LEGACY_HIGH_WATER_ROLES[:3], pins, artifact_pins, inventories
    ):
        rows = _require_list(inventory.get("artifacts"), f"{role} artifact inventory")
        total = inventory.get("total_count")
        if isinstance(total, bool) or not isinstance(total, int) or total != len(rows):
            _fail(f"{role} artifact inventory is incomplete")
        live: list[Mapping[str, Any]] = []
        for value in rows:
            row = _require_object(value, f"{role} artifact inventory entry")
            if row.get("expired") is False:
                _parse_time(row.get("created_at"), f"{role} artifact created_at")
                live.append(row)
        if not live:
            _fail(f"{role} artifact inventory has no live protected artifact")
        ids = [row.get("id") for row in live]
        if len(set(ids)) != len(ids):
            _fail(f"{role} artifact inventory contains duplicate live IDs")
        current = max(
            live,
            key=lambda row: (
                _parse_time(row.get("created_at"), f"{role} artifact created_at"),
                int(row.get("id")) if isinstance(row.get("id"), int) else -1,
            ),
        )
        for key, expected in {
            "id": artifact_pin.get("id"),
            "name": artifact_pin.get("name"),
            "size_in_bytes": artifact_pin.get("size_in_bytes"),
            "digest": artifact_pin.get("digest"),
            "expires_at": artifact_pin.get("expires_at"),
            "expired": False,
        }.items():
            _expect(current.get(key), expected, f"{role} protected artifact high-water {key}")
        workflow_run = _require_object(current.get("workflow_run"), f"{role} artifact workflow_run")
        for key, expected in {
            "id": run_pin.get("run_id"),
            "repository_id": REPOSITORY_ID,
            "head_repository_id": REPOSITORY_ID,
            "head_branch": "main",
            "head_sha": run_pin.get("head_sha"),
        }.items():
            _expect(workflow_run.get(key), expected, f"{role} artifact workflow_run {key}")
        digests.append(_canonical_sha256(inventory))
    return digests


def _validate_descriptor(descriptor: Mapping[str, Any]) -> None:
    for key, expected in {
        "schema_version": 1,
        "result": "phase5_failed_promotion_reconciliation_authorized",
        "repository_id": REPOSITORY_ID,
        "repository": REPOSITORY,
        "certified_control_revision": CERTIFIED_CONTROL_REVISION,
        "certified_tree_sha": CERTIFIED_TREE_SHA,
        "runtime_source_revision": RUNTIME_SOURCE_REVISION,
    }.items():
        _expect(descriptor.get(key), expected, f"reconciliation descriptor {key}")
    image = descriptor.get("immutable_image")
    if not isinstance(image, str) or re.search(r"@sha256:[0-9a-f]{64}$", image) is None:
        _fail("reconciliation descriptor immutable image is invalid")
    _expect(descriptor.get("rebaseline_authorized"), False, "descriptor rebaseline authorization")
    _expect(
        descriptor.get("legacy_artifact_merge_or_import_authorized"),
        False,
        "descriptor legacy merge/import authorization",
    )
    _high_water_pins(descriptor)


def _validate_receipt_summary(
    receipts: Sequence[Any], *, cycles: int, label: str
) -> list[Mapping[str, Any]]:
    expected_jobs = list(NAMESPACES) * cycles
    if len(receipts) != len(expected_jobs):
        _fail(f"{label} does not contain exactly {len(expected_jobs)} receipts")
    accepted: list[Mapping[str, Any]] = []
    run_ids: set[str] = set()
    executions: set[str] = set()
    previous_finished = None
    for index, (value, job) in enumerate(zip(receipts, expected_jobs), start=1):
        receipt = _require_object(value, f"{label} receipt {index}")
        for key, expected in {
            "sequence": index,
            "cycle": ((index - 1) // len(NAMESPACES)) + 1,
            "job": job,
        }.items():
            _expect(receipt.get(key), expected, f"{label} receipt {index} {key}")
        run_id = receipt.get("run_id")
        execution = receipt.get("cloud_run_execution")
        if not isinstance(run_id, str) or not run_id or run_id in run_ids:
            _fail(f"{label} contains an invalid or duplicate Runtime receipt")
        if not isinstance(execution, str) or not execution or execution in executions:
            _fail(f"{label} contains an invalid or duplicate Cloud Run execution")
        run_ids.add(run_id)
        executions.add(execution)
        generation = receipt.get("generation")
        digest = receipt.get("snapshot_sha256")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            _fail(f"{label} receipt {index} generation is invalid")
        if not isinstance(digest, str) or SHA64.fullmatch(digest) is None:
            _fail(f"{label} receipt {index} snapshot digest is invalid")
        started = _parse_time(receipt.get("started_at"), f"{label} receipt {index} started_at")
        finished = _parse_time(receipt.get("finished_at"), f"{label} receipt {index} finished_at")
        if finished < started:
            _fail(f"{label} receipt {index} finished before it started")
        if previous_finished is not None and started < previous_finished:
            _fail(f"{label} receipt {index} overlaps its predecessor")
        previous_finished = finished
        accepted.append(receipt)
    return accepted


def _validate_failed_retry_replay_summary(
    descriptor: Mapping[str, Any],
    replay: Mapping[str, Any],
    invalidated_receipts: Sequence[Mapping[str, Any]],
    invalidated_final_heads: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    pin = _require_object(descriptor.get("failed_phase5_retry"), "failed Phase 5 retry pin")
    failed_retry = _require_object(
        replay.get("failed_phase5_retry"), "replay failed Phase 5 retry"
    )
    artifact_pin = _require_object(pin.get("artifact"), "failed Phase 5 retry artifact pin")
    job_pin = _require_object(pin.get("job"), "failed Phase 5 retry job pin")
    for key, expected in {
        "run_id": FAILED_PHASE5_RETRY_RUN_ID,
        "artifact_id": artifact_pin.get("id"),
        "head_sha": FAILED_PHASE5_RETRY_CONTROL_REVISION,
        "job_id": job_pin.get("id"),
        "conclusion": "failure",
        "result": "clean_cycle_rolled_back_noncertifying",
        "certification_eligible": False,
        "unique_successful_smoke_receipts": 4,
        "legacy_global_one_writer_verified": True,
        "runtime_execution_set_verified": True,
        "rollback_verified": True,
        "production_authority_transferred": False,
        "phase6_started": False,
    }.items():
        _expect(failed_retry.get(key), expected, f"replay failed Phase 5 retry {key}")

    baseline_heads = _require_object(
        failed_retry.get("baseline_heads"), "failed Phase 5 retry baseline heads"
    )
    terminal_heads = _require_object(
        failed_retry.get("final_heads"), "failed Phase 5 retry final heads"
    )
    pinned_baseline = _require_object(pin.get("baseline_heads"), "failed retry baseline pins")
    pinned_terminal = _require_object(pin.get("terminal_heads"), "failed retry terminal pins")
    successor_pin = _require_object(
        descriptor.get("failed_phase5_retry_successor"),
        "failed Phase 5 retry successor pin",
    )
    expected_continuation = _require_object(
        successor_pin.get("baseline_heads"), "failed retry successor baseline heads"
    )
    _same_heads(invalidated_final_heads, pinned_baseline, "failed retry pinned baseline")
    _same_heads(baseline_heads, pinned_baseline, "replay failed retry baseline")
    _same_heads(terminal_heads, pinned_terminal, "replay failed retry terminal heads")
    _same_heads(terminal_heads, expected_continuation, "replay failed retry continuation heads")

    receipts = _validate_receipt_summary(
        _require_list(failed_retry.get("executions"), "failed Phase 5 retry executions"),
        cycles=1,
        label="failed Phase 5 retry",
    )
    terminal_receipts = {item["job"]: item for item in receipts}
    for role in NAMESPACES:
        head = _require_object(terminal_heads.get(role), f"failed retry final {role} head")
        _expect(
            head.get("generation"),
            terminal_receipts[role].get("generation"),
            f"failed retry {role} generation",
        )
        _expect(
            head.get("snapshot_sha256"),
            terminal_receipts[role].get("snapshot_sha256"),
            f"failed retry {role} snapshot digest",
        )

    invalidated_ids = {item.get("run_id") for item in invalidated_receipts}
    invalidated_executions = {
        item.get("cloud_run_execution") for item in invalidated_receipts
    }
    if any(item.get("run_id") in invalidated_ids for item in receipts):
        _fail("failed Phase 5 retry reused an invalidated Runtime receipt")
    if any(item.get("cloud_run_execution") in invalidated_executions for item in receipts):
        _fail("failed Phase 5 retry reused an invalidated Cloud Run execution")
    invalidated_finish = max(
        _parse_time(item.get("finished_at"), "invalidated smoke finished_at")
        for item in invalidated_receipts
    )
    retry_start = min(
        _parse_time(item.get("started_at"), "failed retry smoke started_at")
        for item in receipts
    )
    if retry_start <= invalidated_finish:
        _fail("failed Phase 5 retry overlaps the invalidated prefix")
    return receipts


def _validate_failed_retry_successor_replay_summary(
    descriptor: Mapping[str, Any],
    replay: Mapping[str, Any],
    predecessor_receipts: Sequence[Mapping[str, Any]],
    predecessor_final_heads: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    pin = _require_object(
        descriptor.get("failed_phase5_retry_successor"),
        "failed Phase 5 retry successor pin",
    )
    failed_retry = _require_object(
        replay.get("failed_phase5_retry_successor"),
        "replay failed Phase 5 retry successor",
    )
    artifact_pin = _require_object(
        pin.get("artifact"), "failed Phase 5 retry successor artifact pin"
    )
    job_pin = _require_object(pin.get("job"), "failed Phase 5 retry successor job pin")
    for key, expected in {
        "run_id": FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID,
        "predecessor_run_id": FAILED_PHASE5_RETRY_RUN_ID,
        "artifact_id": artifact_pin.get("id"),
        "head_sha": FAILED_PHASE5_RETRY_SUCCESSOR_CONTROL_REVISION,
        "job_id": job_pin.get("id"),
        "conclusion": "failure",
        "result": "clean_cycle_rolled_back_noncertifying",
        "certification_eligible": False,
        "unique_successful_smoke_receipts": 4,
        "predecessor_replay_sha256": pin.get("predecessor_replay_sha256"),
        "legacy_global_one_writer_verified": True,
        "runtime_execution_set_verified": True,
        "completion_evidence_invalidated": True,
        "rollback_verified": True,
        "production_authority_transferred": False,
        "phase6_started": False,
    }.items():
        _expect(
            failed_retry.get(key), expected, f"replay failed Phase 5 retry successor {key}"
        )

    baseline_heads = _require_object(
        failed_retry.get("baseline_heads"),
        "failed Phase 5 retry successor baseline heads",
    )
    terminal_heads = _require_object(
        failed_retry.get("final_heads"), "failed Phase 5 retry successor final heads"
    )
    pinned_baseline = _require_object(
        pin.get("baseline_heads"), "failed retry successor baseline pins"
    )
    pinned_terminal = _require_object(
        pin.get("terminal_heads"), "failed retry successor terminal pins"
    )
    expected_continuation = _require_object(
        descriptor.get("expected_continuation_heads"), "descriptor continuation heads"
    )
    _same_heads(
        predecessor_final_heads,
        pinned_baseline,
        "failed retry successor pinned baseline",
    )
    _same_heads(baseline_heads, pinned_baseline, "replay failed retry successor baseline")
    _same_heads(
        terminal_heads, pinned_terminal, "replay failed retry successor terminal heads"
    )
    _same_heads(
        terminal_heads,
        expected_continuation,
        "replay failed retry successor continuation heads",
    )

    receipts = _validate_receipt_summary(
        _require_list(
            failed_retry.get("executions"), "failed Phase 5 retry successor executions"
        ),
        cycles=1,
        label="failed Phase 5 retry successor",
    )
    terminal_receipts = {item["job"]: item for item in receipts}
    for role in NAMESPACES:
        head = _require_object(
            terminal_heads.get(role), f"failed retry successor final {role} head"
        )
        _expect(
            head.get("generation"),
            terminal_receipts[role].get("generation"),
            f"failed retry successor {role} generation",
        )
        _expect(
            head.get("snapshot_sha256"),
            terminal_receipts[role].get("snapshot_sha256"),
            f"failed retry successor {role} snapshot digest",
        )

    predecessor_ids = {item.get("run_id") for item in predecessor_receipts}
    predecessor_executions = {
        item.get("cloud_run_execution") for item in predecessor_receipts
    }
    if any(item.get("run_id") in predecessor_ids for item in receipts):
        _fail("failed Phase 5 retry successor reused a predecessor Runtime receipt")
    if any(item.get("cloud_run_execution") in predecessor_executions for item in receipts):
        _fail("failed Phase 5 retry successor reused a predecessor Cloud Run execution")
    predecessor_finish = max(
        _parse_time(item.get("finished_at"), "failed retry predecessor finished_at")
        for item in predecessor_receipts
    )
    successor_start = min(
        _parse_time(item.get("started_at"), "failed retry successor started_at")
        for item in receipts
    )
    if successor_start <= predecessor_finish:
        _fail("failed Phase 5 retry successor overlaps its predecessor retry")
    return receipts


def _validate_replay_receipt(descriptor: Mapping[str, Any], replay: Mapping[str, Any]) -> None:
    for key, expected in {
        "schema_version": 1,
        "result": "phase5_failed_promotion_reconciled",
        "repository_id": REPOSITORY_ID,
        "certification_eligible": False,
        "descriptor_sha256": _canonical_sha256(descriptor),
        "certified_control_revision": CERTIFIED_CONTROL_REVISION,
        "runtime_source_revision": RUNTIME_SOURCE_REVISION,
        "immutable_image": descriptor.get("immutable_image"),
        "current_heads_verified": True,
        "current_latest_receipts_verified": True,
    }.items():
        _expect(replay.get(key), expected, f"replay receipt {key}")

    phase4 = _require_object(replay.get("phase4_certificate"), "replay Phase 4 certificate")
    for key, expected in {
        "run_id": PHASE4_RUN_ID,
        "artifact_id": _require_object(descriptor["phase4"].get("artifact"), "Phase 4 artifact").get("id"),
        "certificate_sha256": descriptor["phase4"].get("certificate_sha256"),
        "verified": True,
    }.items():
        _expect(phase4.get(key), expected, f"replay Phase 4 {key}")
    failed = _require_object(replay.get("failed_phase5"), "replay failed Phase 5")
    for key, expected in {
        "run_id": FAILED_PHASE5_RUN_ID,
        "artifact_id": _require_object(
            descriptor["failed_phase5"].get("artifact"), "failed Phase 5 artifact"
        ).get("id"),
        "conclusion": "failure",
        "completion_certificate_present": False,
    }.items():
        _expect(failed.get(key), expected, f"replay failed Phase 5 {key}")

    prefix = _require_object(replay.get("invalidated_smoke_prefix"), "invalidated smoke prefix")
    for key, expected in {
        "reason": "concurrent_legacy_ai_global_writer",
        "certification_eligible": False,
        "unique_successful_receipts": 4,
    }.items():
        _expect(prefix.get(key), expected, f"invalidated smoke prefix {key}")
    receipts = _validate_receipt_summary(
        _require_list(prefix.get("executions"), "invalidated smoke executions"),
        cycles=1,
        label="invalidated smoke prefix",
    )
    baseline_heads = _require_object(prefix.get("baseline_heads"), "invalidated baseline heads")
    final_heads = _require_object(prefix.get("final_heads"), "invalidated final heads")
    failed_retry_pin = _require_object(
        descriptor.get("failed_phase5_retry"), "failed Phase 5 retry pin"
    )
    failed_retry_baseline = _require_object(
        failed_retry_pin.get("baseline_heads"), "failed Phase 5 retry baseline heads"
    )
    for name, mapping in (
        ("invalidated baseline", baseline_heads),
        ("invalidated final", final_heads),
    ):
        if set(mapping) != set(NAMESPACES):
            _fail(f"{name} heads are not the exact four namespaces")
    _same_heads(final_heads, failed_retry_baseline, "invalidated final heads")
    terminal_receipts = {item["job"]: item for item in receipts}
    for role in NAMESPACES:
        head = _require_object(final_heads.get(role), f"invalidated final {role} head")
        _expect(head.get("generation"), terminal_receipts[role].get("generation"), f"invalidated {role} generation")
        _expect(
            head.get("snapshot_sha256"),
            terminal_receipts[role].get("snapshot_sha256"),
            f"invalidated {role} snapshot digest",
        )

    retry_receipts = _validate_failed_retry_replay_summary(
        descriptor, replay, receipts, final_heads
    )
    retry_summary = _require_object(
        replay.get("failed_phase5_retry"), "replay failed Phase 5 retry"
    )
    retry_final_heads = _require_object(
        retry_summary.get("final_heads"), "replay failed Phase 5 retry final heads"
    )
    _validate_failed_retry_successor_replay_summary(
        descriptor, replay, [*receipts, *retry_receipts], retry_final_heads
    )
    continuation = _require_object(replay.get("continuation_heads"), "replay continuation heads")
    expected_continuation = _require_object(
        descriptor.get("expected_continuation_heads"), "descriptor continuation heads"
    )
    if set(continuation) != set(NAMESPACES):
        _fail("replay continuation heads are not the exact four namespaces")
    _same_heads(continuation, expected_continuation, "replay continuation heads")

    legacy = _require_object(replay.get("concurrent_legacy_ai"), "replay legacy AI evidence")
    legacy_pin = _require_object(descriptor.get("concurrent_legacy_ai"), "legacy AI pin")
    conflict = _require_object(legacy_pin.get("conflict"), "legacy AI conflict pin")
    state_pin = _require_object(legacy_pin.get("state_artifact"), "legacy AI state pin")
    output_pin = _require_object(legacy_pin.get("output_artifact"), "legacy AI output pin")
    predecessor_pin = _require_object(
        legacy_pin.get("predecessor_artifact"), "legacy AI predecessor pin"
    )
    for key, expected in {
        "run_id": CONCURRENT_LEGACY_AI_RUN_ID,
        "run_attempt": legacy_pin.get("run_attempt"),
        "head_sha": legacy_pin.get("head_sha"),
        "job_id": _require_object(legacy_pin.get("job"), "legacy AI job pin").get("id"),
        "started_at": _require_object(legacy_pin.get("job"), "legacy AI job pin").get("started_at"),
        "completed_at": _require_object(legacy_pin.get("job"), "legacy AI job pin").get("completed_at"),
        "state_artifact_id": state_pin.get("id"),
        "state_artifact_sha256": _digest_pin(state_pin.get("digest"), "legacy AI state digest"),
        "output_artifact_id": output_pin.get("id"),
        "predecessor_artifact_id": predecessor_pin.get("id"),
        "prefix_preserved": True,
        "analyses_appended": 1,
        "runs_appended": 1,
        "successful_analyses": 1,
        "alerts_attempted": 0,
        "state_publishable": True,
        "global_one_writer_interval_violated": True,
        "conflicting_runtime_snapshot_sha256": conflict.get("runtime_snapshot_sha256"),
        "conflicting_analysis_id": conflict.get("analysis_id"),
        "conflicting_trade_id": conflict.get("trade_id"),
        "conflicting_document_content_hash": conflict.get("document_content_hash"),
        "same_document_content_hash": True,
        "different_openai_response_id": True,
        "different_classification": True,
        "different_score": True,
        "disposition": "quarantined_separate_legacy_artifact",
        "merge_or_import_authorized": False,
    }.items():
        _expect(legacy.get(key), expected, f"replay legacy AI {key}")

    recoveries = _require_list(replay.get("recovery_runs"), "replay recovery runs")
    recovery_pins = _require_list(descriptor.get("recovery_runs"), "recovery run pins")
    if len(recoveries) != 2:
        _fail("replay does not contain exactly two recovery runs")
    for role, run_id, value, pin_value in zip(
        ("legislative", "executive"), RECOVERY_RUN_IDS, recoveries, recovery_pins
    ):
        recovery = _require_object(value, f"replay {role} recovery")
        pin = _require_object(pin_value, f"{role} recovery pin")
        artifact_pin = _require_object(pin.get("artifact"), f"{role} protected artifact pin")
        predecessor_artifact_pin = _require_object(
            pin.get("predecessor_artifact"), f"{role} predecessor artifact pin"
        )
        output_artifact_pin = _require_object(
            pin.get("output_artifact"), f"{role} output artifact pin"
        )
        for key, expected in {
            "role": role,
            "run_id": run_id,
            "run_attempt": pin.get("run_attempt"),
            "head_sha": pin.get("head_sha"),
            "job_id": _require_object(pin.get("job"), f"{role} job pin").get("id"),
            "conclusion": "success",
            "certified_tree_equal_descendant": True,
            "predecessor_artifact_id": predecessor_artifact_pin.get("id"),
            "predecessor_artifact_sha256": _digest_pin(
                predecessor_artifact_pin.get("digest"),
                f"{role} predecessor artifact digest",
            ),
            "protected_artifact_id": artifact_pin.get("id"),
            "protected_artifact_sha256": _digest_pin(
                artifact_pin.get("digest"), f"{role} protected artifact digest"
            ),
            "output_artifact_id": output_artifact_pin.get("id"),
            "output_artifact_sha256": _digest_pin(
                output_artifact_pin.get("digest"), f"{role} output artifact digest"
            ),
            "protected_domain_data_unchanged": True,
            "protected_domain_member_count": len(RECOVERY_PROTECTED_DOMAIN_MEMBERS[role]),
            "run_receipt_appended_count": 1,
            "state_change_keys": ["last_attempt_utc", "last_success_utc"],
        }.items():
            _expect(recovery.get(key), expected, f"replay {role} recovery {key}")
        result_started = _parse_time(
            recovery.get("result_started_at"), f"replay {role} recovery result_started_at"
        )
        result_finished = _parse_time(
            recovery.get("result_finished_at"), f"replay {role} recovery result_finished_at"
        )
        job_pin = _require_object(pin.get("job"), f"{role} recovery job pin")
        if (
            result_finished < result_started
            or result_started < _parse_time(job_pin.get("started_at"), f"{role} job started_at")
            or result_finished > _parse_time(job_pin.get("completed_at"), f"{role} job completed_at")
        ):
            _fail(f"replay {role} recovery result interval is outside its pinned job")

    successors = _require_list(
        replay.get("frozen_legacy_successors"), "replay frozen legacy successors"
    )
    successor_pins = _require_list(
        descriptor.get("frozen_legacy_successors"), "frozen legacy successor pins"
    )
    expected_count = len(FROZEN_LEGACY_SUCCESSOR_RUN_IDS)
    if len(successors) != expected_count or len(successor_pins) != expected_count:
        _fail(f"replay does not contain exactly {expected_count} frozen legacy successors")
    roles = ("legislative", "executive") * len(FROZEN_LEGACY_SUCCESSOR_REVISIONS)
    for offset, (role, run_id, value, pin_value) in enumerate(
        zip(roles, FROZEN_LEGACY_SUCCESSOR_RUN_IDS, successors, successor_pins)
    ):
        layer_index = offset // 2
        successor = _require_object(value, f"replay {role} frozen legacy successor")
        pin = _require_object(pin_value, f"{role} frozen legacy successor pin")
        predecessor_run_pin = _require_object(
            recovery_pins[offset % 2] if layer_index == 0 else successor_pins[offset - 2],
            f"{role} frozen legacy predecessor run pin",
        )
        predecessor_pin = _require_object(
            pin.get("predecessor_artifact"), f"{role} successor predecessor artifact pin"
        )
        predecessor_artifact_pin = _require_object(
            predecessor_run_pin.get("artifact"), f"{role} predecessor protected artifact pin"
        )
        for key in ("id", "name", "size_in_bytes", "digest", "expires_at"):
            _expect(
                predecessor_pin.get(key),
                predecessor_artifact_pin.get(key),
                f"replay {role} successor predecessor {key}",
            )
        _expect(
            predecessor_pin.get("producer_run_id"),
            predecessor_run_pin.get("run_id"),
            f"replay {role} successor predecessor producer run",
        )
        _expect(
            predecessor_pin.get("producer_head_sha"),
            predecessor_run_pin.get("head_sha"),
            f"replay {role} successor predecessor producer revision",
        )
        artifact_pin = _require_object(pin.get("artifact"), f"{role} successor artifact pin")
        output_artifact_pin = _require_object(
            pin.get("output_artifact"), f"{role} successor output artifact pin"
        )
        for key, expected in {
            "role": role,
            "run_id": run_id,
            "run_attempt": pin.get("run_attempt"),
            "head_sha": FROZEN_LEGACY_SUCCESSOR_REVISIONS[layer_index],
            "job_id": _require_object(pin.get("job"), f"{role} successor job pin").get("id"),
            "conclusion": "success",
            "successor_layer": layer_index + 1,
            "incident_only_revision_allowlist_verified": True,
            "predecessor_run_id": predecessor_run_pin.get("run_id"),
            "predecessor_artifact_id": predecessor_pin.get("id"),
            "predecessor_artifact_sha256": _digest_pin(
                predecessor_pin.get("digest"), f"{role} successor predecessor digest"
            ),
            "protected_artifact_id": artifact_pin.get("id"),
            "protected_artifact_sha256": _digest_pin(
                artifact_pin.get("digest"), f"{role} successor protected artifact digest"
            ),
            "output_artifact_id": output_artifact_pin.get("id"),
            "output_artifact_sha256": _digest_pin(
                output_artifact_pin.get("digest"), f"{role} successor output artifact digest"
            ),
            "protected_domain_data_unchanged": True,
            "protected_domain_member_count": len(RECOVERY_PROTECTED_DOMAIN_MEMBERS[role]),
            "run_receipt_appended_count": 1,
            "state_change_keys": ["last_attempt_utc", "last_success_utc"],
        }.items():
            _expect(successor.get(key), expected, f"replay {role} frozen successor {key}")
        result_started = _parse_time(
            successor.get("result_started_at"), f"replay {role} successor result_started_at"
        )
        result_finished = _parse_time(
            successor.get("result_finished_at"), f"replay {role} successor result_finished_at"
        )
        job_pin = _require_object(pin.get("job"), f"{role} successor job pin")
        if (
            result_finished < result_started
            or result_started
            < _parse_time(job_pin.get("started_at"), f"{role} successor job started_at")
            or result_finished
            > _parse_time(job_pin.get("completed_at"), f"{role} successor job completed_at")
        ):
            _fail(f"replay {role} successor result interval is outside its pinned job")

    high_water = _require_object(replay.get("legacy_high_water"), "replay legacy high-water")
    high_water_runs = _require_list(high_water.get("runs"), "replay high-water runs")
    pins = _high_water_pins(descriptor)
    if len(high_water_runs) != 4:
        _fail("replay high-water does not contain exactly four runs")
    for role, value, pin in zip(LEGACY_HIGH_WATER_ROLES, high_water_runs, pins):
        summary = _require_object(value, f"replay {role} high-water")
        for key, expected in {
            "role": role,
            "run_id": pin.get("run_id"),
            "workflow_id": _require_object(pin.get("workflow"), f"{role} workflow pin").get("id"),
            "workflow_name": _require_object(pin.get("workflow"), f"{role} workflow pin").get("name"),
            "workflow_path": _require_object(pin.get("workflow"), f"{role} workflow pin").get("path"),
            "created_at": pin.get("created_at"),
            "status": "completed",
            "conclusion": "success",
        }.items():
            _expect(summary.get(key), expected, f"replay {role} high-water {key}")
    for field, count in (
        ("run_inventory_sha256", 4),
        ("protected_artifact_inventory_sha256", 3),
    ):
        values = _require_list(high_water.get(field), f"replay high-water {field}")
        if len(values) != count or any(not isinstance(v, str) or SHA64.fullmatch(v) is None for v in values):
            _fail(f"replay high-water {field} is invalid")
    _required_true(
        high_water,
        (
            "all_current_runs_exactly_pinned",
            "no_later_or_inflight_authoritative_run",
            "all_current_protected_artifacts_exactly_pinned",
        ),
        "replay high-water",
    )

    reconciliation = _require_object(replay.get("reconciliation"), "replay reconciliation")
    _required_true(
        reconciliation,
        (
            "old_smoke_cycle_invalidated",
            "fresh_clean_smoke_cycle_required",
            "global_one_writer_violation_verified",
            "legacy_ai_artifact_quarantined",
            "frozen_legacy_successors_verified",
            "failed_retry_intervening_attempt_verified",
            "failed_retry_successor_intervening_attempt_verified",
            "intervening_runtime_producer_execution_performed",
            "legacy_high_water_verified",
            "full_snapshot_chain_preserved",
        ),
        "replay reconciliation",
    )
    _expect(
        reconciliation.get("intervening_runtime_producer_execution_count"),
        8,
        "replay reconciliation intervening Runtime execution count",
    )
    for key in (
        "legacy_artifact_merge_or_import_authorized",
        "rebaseline_performed",
        "additional_runtime_producer_execution_performed",
        "production_authority_transferred",
        "phase6_started",
    ):
        _expect(reconciliation.get(key), False, f"replay reconciliation {key}")


def reconcile_failed_phase5(
    *,
    descriptor: dict[str, Any],
    repository_root: Path,
    current_status: dict[str, Any],
    current_ai_analyses: Any,
    phase4_source: Mapping[str, Any],
    failed_source: Mapping[str, Any],
    failed_retry_source: Mapping[str, Any],
    failed_retry_successor_source: Mapping[str, Any],
    legacy_ai_source: Mapping[str, Any],
    recovery_run_metadatas: Sequence[Mapping[str, Any]],
    recovery_jobs_metadatas: Sequence[Mapping[str, Any]],
    recovery_predecessor_artifact_metadatas: Sequence[Mapping[str, Any]],
    recovery_predecessor_archives: Sequence[Path],
    recovery_artifact_metadatas: Sequence[Mapping[str, Any]],
    recovery_archives: Sequence[Path],
    recovery_output_artifact_metadatas: Sequence[Mapping[str, Any]],
    recovery_output_archives: Sequence[Path],
    frozen_successor_run_metadatas: Sequence[Mapping[str, Any]],
    frozen_successor_jobs_metadatas: Sequence[Mapping[str, Any]],
    frozen_successor_artifact_metadatas: Sequence[Mapping[str, Any]],
    frozen_successor_archives: Sequence[Path],
    frozen_successor_output_artifact_metadatas: Sequence[Mapping[str, Any]],
    frozen_successor_output_archives: Sequence[Path],
    legacy_run_inventories: Sequence[Mapping[str, Any]],
    legacy_artifact_inventories: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _validate_descriptor(descriptor)
    _verify_tree_equal_descendant(
        repository_root,
        CERTIFIED_CONTROL_REVISION,
        CERTIFIED_CONTROL_REVISION,
        CERTIFIED_TREE_SHA,
    )
    certificate, certificate_bytes = _phase4_certificate(
        descriptor,
        _require_object(phase4_source.get("run"), "Phase 4 run metadata"),
        _require_object(phase4_source.get("artifact"), "Phase 4 artifact metadata"),
        _require_object(phase4_source.get("jobs"), "Phase 4 jobs metadata"),
        Path(phase4_source["archive"]),
    )
    prefix, raw_observations, _failed_job = _failed_phase5_prefix(
        descriptor,
        certificate,
        certificate_bytes,
        _require_object(failed_source.get("run"), "failed Phase 5 run metadata"),
        _require_object(failed_source.get("artifact"), "failed Phase 5 artifact metadata"),
        _require_object(failed_source.get("jobs"), "failed Phase 5 jobs metadata"),
        Path(failed_source["archive"]),
    )
    failed_prefix_terminal_status = _require_object(
        raw_observations[-1].get("status"), "failed Phase 5 terminal observation status"
    )
    legacy = _validate_legacy_ai_conflict(
        descriptor,
        _require_object(legacy_ai_source.get("run"), "legacy AI run metadata"),
        _require_object(legacy_ai_source.get("jobs"), "legacy AI jobs metadata"),
        _require_object(
            legacy_ai_source.get("predecessor_artifact"), "legacy AI predecessor artifact metadata"
        ),
        Path(legacy_ai_source["predecessor_archive"]),
        _require_object(legacy_ai_source.get("state_artifact"), "legacy AI state artifact metadata"),
        Path(legacy_ai_source["state_archive"]),
        _require_object(legacy_ai_source.get("output_artifact"), "legacy AI output artifact metadata"),
        Path(legacy_ai_source["output_archive"]),
        current_ai_analyses,
        failed_prefix_terminal_status,
        prefix["receipts"],
    )
    recoveries = _validate_recoveries(
        descriptor,
        repository_root,
        recovery_run_metadatas,
        recovery_jobs_metadatas,
        recovery_predecessor_artifact_metadatas,
        recovery_predecessor_archives,
        recovery_artifact_metadatas,
        recovery_archives,
        recovery_output_artifact_metadatas,
        recovery_output_archives,
        after_time=_parse_time(legacy["completed_at"], "legacy AI completed_at"),
    )
    frozen_successors = _validate_frozen_legacy_successors(
        descriptor,
        repository_root,
        recovery_artifact_metadatas,
        recovery_archives,
        frozen_successor_run_metadatas,
        frozen_successor_jobs_metadatas,
        frozen_successor_artifact_metadatas,
        frozen_successor_archives,
        frozen_successor_output_artifact_metadatas,
        frozen_successor_output_archives,
    )
    failed_retry = _validate_failed_phase5_retry(
        descriptor,
        _require_object(failed_retry_source.get("run"), "failed Phase 5 retry run metadata"),
        _require_object(
            failed_retry_source.get("artifact"), "failed Phase 5 retry artifact metadata"
        ),
        _require_object(failed_retry_source.get("jobs"), "failed Phase 5 retry jobs metadata"),
        Path(failed_retry_source["archive"]),
        prefix,
    )
    failed_retry_successor = _validate_failed_phase5_retry_successor(
        descriptor,
        _require_object(
            failed_retry_successor_source.get("run"),
            "failed Phase 5 retry successor run metadata",
        ),
        _require_object(
            failed_retry_successor_source.get("artifact"),
            "failed Phase 5 retry successor artifact metadata",
        ),
        _require_object(
            failed_retry_successor_source.get("jobs"),
            "failed Phase 5 retry successor jobs metadata",
        ),
        Path(failed_retry_successor_source["archive"]),
        prefix,
        failed_retry,
        frozen_successors,
    )
    _assert_current_runtime_state(
        current_status,
        _require_object(
            failed_retry_successor.get("final_heads"),
            "failed Phase 5 retry successor final heads",
        ),
        _require_list(
            failed_retry_successor.get("executions"),
            "failed Phase 5 retry successor executions",
        ),
    )
    high_water_runs, high_water_run_digests = _validate_high_water_run_inventories(
        descriptor, legacy_run_inventories, label="replay"
    )
    high_water_artifact_digests = _validate_high_water_artifact_inventories(
        descriptor, legacy_artifact_inventories
    )
    descriptor_digest = _canonical_sha256(descriptor)
    return {
        "schema_version": 1,
        "result": "phase5_failed_promotion_reconciled",
        "repository_id": REPOSITORY_ID,
        "certification_eligible": False,
        "descriptor_sha256": descriptor_digest,
        "certified_control_revision": CERTIFIED_CONTROL_REVISION,
        "runtime_source_revision": RUNTIME_SOURCE_REVISION,
        "immutable_image": descriptor["immutable_image"],
        "phase4_certificate": {
            "run_id": PHASE4_RUN_ID,
            "artifact_id": descriptor["phase4"]["artifact"]["id"],
            "certificate_sha256": descriptor["phase4"]["certificate_sha256"],
            "verified": True,
        },
        "failed_phase5": {
            "run_id": FAILED_PHASE5_RUN_ID,
            "artifact_id": descriptor["failed_phase5"]["artifact"]["id"],
            "conclusion": "failure",
            "completion_certificate_present": False,
        },
        "invalidated_smoke_prefix": {
            "reason": "concurrent_legacy_ai_global_writer",
            "certification_eligible": False,
            "unique_successful_receipts": 4,
            "executions": prefix["receipts"],
            "baseline_heads": _head_summary(_heads(prefix["baseline"])),
            "final_heads": _head_summary(prefix["final_heads"]),
        },
        "failed_phase5_retry": failed_retry,
        "failed_phase5_retry_successor": failed_retry_successor,
        "continuation_heads": failed_retry_successor["final_heads"],
        "current_heads_verified": True,
        "current_latest_receipts_verified": True,
        "concurrent_legacy_ai": legacy,
        "recovery_runs": recoveries,
        "frozen_legacy_successors": frozen_successors,
        "legacy_high_water": {
            "runs": high_water_runs,
            "run_inventory_sha256": high_water_run_digests,
            "protected_artifact_inventory_sha256": high_water_artifact_digests,
            "all_current_runs_exactly_pinned": True,
            "no_later_or_inflight_authoritative_run": True,
            "all_current_protected_artifacts_exactly_pinned": True,
        },
        "reconciliation": {
            "kind": "incident_bound_failed_phase5_forensic_replay",
            "old_smoke_cycle_invalidated": True,
            "fresh_clean_smoke_cycle_required": True,
            "global_one_writer_violation_verified": True,
            "legacy_ai_artifact_quarantined": True,
            "frozen_legacy_successors_verified": True,
            "failed_retry_intervening_attempt_verified": True,
            "failed_retry_successor_intervening_attempt_verified": True,
            "intervening_runtime_producer_execution_performed": True,
            "intervening_runtime_producer_execution_count": 8,
            "legacy_high_water_verified": True,
            "legacy_artifact_merge_or_import_authorized": False,
            "rebaseline_performed": False,
            "full_snapshot_chain_preserved": True,
            "additional_runtime_producer_execution_performed": False,
            "production_authority_transferred": False,
            "phase6_started": False,
        },
    }


def _validate_digest_map(
    value: Any, actual: Sequence[str], label: str
) -> None:
    mapping = _require_object(value, label)
    if set(mapping) != set(LEGACY_HIGH_WATER_ROLES):
        _fail(f"{label} must bind the exact four producer roles")
    if len(actual) != 4:
        _fail(f"{label} did not receive exactly four raw evidence files")
    for role, digest in zip(LEGACY_HIGH_WATER_ROLES, actual):
        if not isinstance(digest, str) or SHA64.fullmatch(digest) is None:
            _fail(f"{label} {role} raw digest is invalid")
        _expect(mapping.get(role), digest, f"{label} {role}")


def _execution_containers(execution: Mapping[str, Any], label: str) -> list[Any]:
    spec = _require_object(execution.get("spec"), f"{label} spec")
    template = _require_object(spec.get("template"), f"{label} template")
    template_spec = _require_object(template.get("spec"), f"{label} template spec")
    containers = template_spec.get("containers")
    if containers is None:
        inner = _require_object(template_spec.get("template"), f"{label} task template")
        inner_spec = _require_object(inner.get("spec"), f"{label} task template spec")
        containers = inner_spec.get("containers")
    return _require_list(containers, f"{label} containers")


def _validate_terminal_one_writer(
    *,
    descriptor: Mapping[str, Any],
    replay: Mapping[str, Any],
    manifest: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    legacy_run_inventories: Sequence[Mapping[str, Any]],
    legacy_workflow_states: Sequence[Mapping[str, Any]],
    runtime_execution_inventories: Sequence[Mapping[str, Any]],
    evidence_digests: Mapping[str, Sequence[str]],
    successor_layer: int = -1,
) -> None:
    evidence = _require_object(manifest.get("one_writer_evidence"), "terminal one-writer evidence")
    for field in (
        "legacy_run_inventories",
        "legacy_workflow_states",
        "runtime_execution_inventories",
    ):
        _validate_digest_map(
            evidence.get(f"{field}_sha256"),
            evidence_digests.get(field, ()),
            f"terminal {field} digest",
        )

    interval = _require_object(evidence.get("fresh_cycle_interval"), "fresh-cycle interval")
    interval_start = _parse_time(interval.get("started_at"), "fresh-cycle interval started_at")
    interval_finish = _parse_time(interval.get("finished_at"), "fresh-cycle interval finished_at")
    if interval_finish < interval_start:
        _fail("fresh-cycle interval finished before it started")
    receipt_start = _parse_time(receipts[0].get("started_at"), "fresh-cycle first receipt started_at")
    receipt_finish = _parse_time(receipts[-1].get("finished_at"), "fresh-cycle final receipt finished_at")
    if receipt_start < interval_start or receipt_finish > interval_finish:
        _fail("fresh-cycle interval does not contain the four Runtime receipts")

    high_water_summaries, _digests = _validate_high_water_run_inventories(
        descriptor,
        legacy_run_inventories,
        label="terminal",
        successor_layer=successor_layer,
    )
    replay_high_water = _require_object(replay.get("legacy_high_water"), "replay high-water")
    _expect(high_water_summaries, replay_high_water.get("runs"), "terminal/replay legacy high-water")
    for role, inventory in zip(LEGACY_HIGH_WATER_ROLES, legacy_run_inventories):
        rows = _require_list(inventory.get("workflow_runs"), f"terminal {role} workflow runs")
        for value in rows:
            row = _require_object(value, f"terminal {role} workflow run")
            started_value = row.get("run_started_at") or row.get("created_at")
            started = _parse_time(started_value, f"terminal {role} workflow run started_at")
            if row.get("status") == "completed":
                finished = _parse_time(row.get("updated_at"), f"terminal {role} workflow run updated_at")
                overlaps = started < interval_finish and finished > interval_start
            else:
                overlaps = started < interval_finish
            if overlaps:
                _fail(f"terminal {role} legacy workflow run overlaps the fresh cycle")

    pins = _high_water_pins(descriptor, successor_layer=successor_layer)
    if len(legacy_workflow_states) != 4:
        _fail("terminal evidence requires exactly four legacy workflow states")
    for role, pin, state in zip(LEGACY_HIGH_WATER_ROLES, pins, legacy_workflow_states):
        workflow = _require_object(pin.get("workflow"), f"{role} workflow pin")
        for key, expected in {
            "id": workflow.get("id"),
            "name": workflow.get("name"),
            "path": workflow.get("path"),
            "state": "disabled_manually",
        }.items():
            actual = _normalize_workflow_path(state.get(key)) if key == "path" else state.get(key)
            _expect(actual, expected, f"terminal {role} workflow state {key}")

    if len(runtime_execution_inventories) != 4:
        _fail("terminal evidence requires exactly four Runtime execution inventories")
    expected_receipts = {str(item["job"]): item for item in receipts}
    overlapping_names: set[str] = set()
    for role, wrapper in zip(LEGACY_HIGH_WATER_ROLES, runtime_execution_inventories):
        _expect(wrapper.get("job"), role, f"terminal Runtime inventory {role} job")
        executions = _require_list(wrapper.get("executions"), f"terminal {role} executions")
        _expect(wrapper.get("capture_limit"), 1000, f"terminal {role} execution capture limit")
        _expect(
            wrapper.get("returned_count"),
            len(executions),
            f"terminal {role} execution returned count",
        )
        if len(executions) >= 1000:
            _fail(f"terminal {role} execution inventory reached its pagination boundary")
        names: set[str] = set()
        overlapping: list[tuple[Mapping[str, Any], Any, Any]] = []
        for value in executions:
            execution = _require_object(value, f"terminal {role} execution")
            metadata = _require_object(execution.get("metadata"), f"terminal {role} metadata")
            name = metadata.get("name")
            if not isinstance(name, str) or not name or name in names:
                _fail(f"terminal {role} execution inventory has an invalid or duplicate name")
            names.add(name)
            expected_job = f"polititrack-{role}"
            if not name.startswith(f"{expected_job}-"):
                _fail(f"terminal {role} execution name belongs to a different job")
            labels = _require_object(metadata.get("labels"), f"terminal {role} execution labels")
            _expect(
                labels.get("run.googleapis.com/job"),
                expected_job,
                f"terminal {role} execution job label",
            )
            owners = _require_list(
                metadata.get("ownerReferences"), f"terminal {role} execution owners"
            )
            if not any(
                isinstance(owner, Mapping)
                and owner.get("kind") == "Job"
                and owner.get("name") == expected_job
                for owner in owners
            ):
                _fail(f"terminal {role} execution is not owned by the expected job")
            status = _require_object(execution.get("status"), f"terminal {role} execution status")
            started = _parse_time(
                status.get("startTime") or metadata.get("creationTimestamp"),
                f"terminal {role} execution start",
            )
            completion_value = status.get("completionTime")
            finished = (
                _parse_time(completion_value, f"terminal {role} execution completion")
                if completion_value
                else None
            )
            overlaps = started < interval_finish and (finished is None or finished > interval_start)
            if overlaps:
                overlapping.append((execution, started, finished))

        if len(overlapping) != 1:
            _fail(f"terminal {role} does not have exactly one execution overlapping the fresh cycle")
        execution, execution_started, execution_finished = overlapping[0]
        metadata = _require_object(execution.get("metadata"), f"terminal {role} metadata")
        status = _require_object(execution.get("status"), f"terminal {role} execution status")
        expected_receipt = expected_receipts[role]
        _expect(
            metadata.get("name"),
            expected_receipt.get("cloud_run_execution"),
            f"terminal {role} observed execution",
        )
        if execution_finished is None:
            _fail(f"terminal {role} observed execution has not completed")
        if execution_started < interval_start or execution_finished > interval_finish:
            _fail(f"terminal {role} execution falls outside the captured fresh-cycle interval")
        app_started = _parse_time(expected_receipt.get("started_at"), f"terminal {role} receipt start")
        app_finished = _parse_time(expected_receipt.get("finished_at"), f"terminal {role} receipt finish")
        if app_started < execution_started or app_finished > execution_finished:
            _fail(f"terminal {role} Runtime receipt is outside its Cloud Run execution")
        conditions = _require_list(status.get("conditions"), f"terminal {role} execution conditions")
        completed = [
            condition
            for condition in conditions
            if isinstance(condition, Mapping)
            and condition.get("type") == "Completed"
            and str(condition.get("status")).lower() == "true"
        ]
        if len(completed) != 1 or status.get("succeededCount") != 1:
            _fail(f"terminal {role} Cloud Run execution lacks exact success evidence")
        containers = _execution_containers(execution, f"terminal {role} execution")
        if len(containers) != 1:
            _fail(f"terminal {role} execution does not contain exactly one container")
        container = _require_object(containers[0], f"terminal {role} container")
        _expect(container.get("image"), descriptor.get("immutable_image"), f"terminal {role} image")
        env_rows = _require_list(container.get("env"), f"terminal {role} environment")
        env: dict[str, Any] = {}
        for value in env_rows:
            row = _require_object(value, f"terminal {role} environment entry")
            name = row.get("name")
            if not isinstance(name, str) or not name or name in env:
                _fail(f"terminal {role} environment has an invalid or duplicate name")
            env[name] = row.get("value")
        for name, expected in {
            "POLITITRACK_TRIGGER_SOURCE": "phase5_smoke",
            "SOURCE_REVISION": RUNTIME_SOURCE_REVISION,
            "POLITITRACK_MODE": "production",
        }.items():
            _expect(env.get(name), expected, f"terminal {role} environment {name}")
        overlapping_names.add(str(metadata.get("name")))

    expected_names = {str(item["cloud_run_execution"]) for item in receipts}
    _expect(overlapping_names, expected_names, "fresh-cycle overlapping execution set")
    for key, expected in {
        "overlapping_legacy_run_count": 0,
        "unexpected_runtime_execution_count": 0,
        "expected_runtime_execution_count": 4,
    }.items():
        _expect(evidence.get(key), expected, f"terminal one-writer evidence {key}")


def _scheduler_evidence_path(
    paths: Mapping[str, Any], key: str, label: str
) -> Path:
    value = paths.get(key)
    if not isinstance(value, Path):
        _fail(f"{label} path is missing")
    if not value.is_file():
        _fail(f"{label} file is missing")
    return value


def _scheduler_evidence_paths(
    paths: Mapping[str, Any], key: str, count: int, label: str
) -> list[Path]:
    values = paths.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        _fail(f"{label} paths are missing")
    result = list(values)
    if len(result) != count or any(not isinstance(value, Path) or not value.is_file() for value in result):
        _fail(f"{label} does not contain exactly {count} readable files")
    return result


def _scheduler_policy_member_bindings(
    policy: Mapping[str, Any], role: str, member: str, label: str
) -> list[Mapping[str, Any]]:
    bindings = _require_list(policy.get("bindings"), f"{label} bindings")
    matched: list[Mapping[str, Any]] = []
    for value in bindings:
        binding = _require_object(value, f"{label} binding")
        members = _require_list(binding.get("members"), f"{label} binding members")
        if not all(isinstance(item, str) and item for item in members):
            _fail(f"{label} binding members are invalid")
        if binding.get("role") == role and member in members:
            matched.append(binding)
    return matched


def _scheduler_spec_sha256(job: Mapping[str, Any]) -> str:
    transient = {"state", "status", "userUpdateTime", "lastAttemptTime", "scheduleTime"}
    stable = {key: value for key, value in job.items() if key not in transient}
    encoded = json.dumps(
        stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8") + b"\n"
    return _sha256_bytes(encoded)


def _validate_scheduler_activation_authority(
    manifest: Mapping[str, Any], paths: Mapping[str, Any]
) -> None:
    authority = _require_object(
        manifest.get("scheduler_activation_authority"),
        "completion scheduler activation authority",
    )
    scalar_paths = {
        "authority_summary": "scheduler activation authority summary",
        "transition": "scheduler transition",
        "before_policy": "scheduler before-grant policy",
        "granted_policy": "scheduler granted policy",
        "removed_policy": "scheduler removed policy",
        "permanent_control_role": "permanent control role",
        "role_viewer_before_policy": "role viewer before-grant policy",
        "role_viewer_granted_policy": "role viewer granted policy",
        "role_viewer_removed_policy": "role viewer removed policy",
        "role_viewer_condition": "role viewer grant condition",
        "role_viewer_grant_request": "role viewer grant request",
        "condition": "scheduler grant condition",
        "grant_request": "scheduler grant request",
        "resume_attempts": "scheduler resume attempts",
        "before_summary": "scheduler before summary",
        "after_summary": "scheduler after summary",
        "before_inventory": "scheduler before inventory",
        "after_inventory": "scheduler after inventory",
    }
    files = {
        key: _scheduler_evidence_path(paths, key, label)
        for key, label in scalar_paths.items()
    }
    before_jobs = _scheduler_evidence_paths(paths, "before_jobs", 5, "scheduler before jobs")
    after_jobs = _scheduler_evidence_paths(paths, "after_jobs", 5, "scheduler after jobs")
    resume_receipts = _scheduler_evidence_paths(
        paths, "resume_receipts", 4, "scheduler resume receipts"
    )

    summary = _load_object(files["authority_summary"])
    transition = _load_object(files["transition"])
    expected_manifest_authority = dict(summary)
    expected_manifest_authority.update(
        summary_sha256=_sha256_file(files["authority_summary"]), transition=transition
    )
    _expect(
        authority,
        expected_manifest_authority,
        "completion scheduler activation authority/raw evidence",
    )

    grant = _load_object(files["grant_request"])
    condition = _load_object(files["condition"])
    before_policy = _load_object(files["before_policy"])
    granted_policy = _load_object(files["granted_policy"])
    removed_policy = _load_object(files["removed_policy"])
    permanent_role = _load_object(files["permanent_control_role"])
    role_viewer_before_policy = _load_object(files["role_viewer_before_policy"])
    role_viewer_granted_policy = _load_object(files["role_viewer_granted_policy"])
    role_viewer_removed_policy = _load_object(files["role_viewer_removed_policy"])
    role_viewer_condition = _load_object(files["role_viewer_condition"])
    role_viewer_grant = _load_object(files["role_viewer_grant_request"])
    attempts = _jsonl_records(
        files["resume_attempts"].read_bytes(), "scheduler resume attempts"
    )
    before_summary = _load_object(files["before_summary"])
    after_summary = _load_object(files["after_summary"])
    before_inventory = _load_list_or_object(files["before_inventory"])
    after_inventory = _load_list_or_object(files["after_inventory"])

    scheduler_names = list(PRODUCER_SCHEDULERS)
    all_scheduler_names = [*scheduler_names, VAULT_SCHEDULER]
    resource_names = [
        f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{name}" for name in scheduler_names
    ]
    for key, expected in {
        "schema_version": 1,
        "result": "jit_scheduler_activation_authority_removed",
        "absent_before_grant": True,
        "grant_observed": True,
        "physically_absent_after_removal": True,
        "propagation_probe_scheduler": scheduler_names[0],
        "propagation_deadline_seconds": 600,
        "scheduler_transition_result": "exact_four_producer_schedulers_enabled_vault_unchanged",
    }.items():
        _expect(summary.get(key), expected, f"scheduler activation authority {key}")
    _expect(summary.get("grant"), grant, "scheduler activation authority grant")
    _expect(summary.get("attempts"), attempts, "scheduler activation authority attempts")

    for key, expected in {
        "schema_version": 1,
        "result": "scheduler_activation_authority_requested",
        "project_id": PROJECT_ID,
        "location": REGION,
        "member": DEPLOYER_MEMBER,
        "role": "roles/cloudscheduler.admin",
        "condition": condition,
        "condition_scope": "request_time_only",
        "authorized_scheduler_short_names": scheduler_names,
        "exact_authorized_resource_names": resource_names,
    }.items():
        _expect(grant.get(key), expected, f"scheduler grant {key}")
    title = condition.get("title")
    if not isinstance(title, str) or re.fullmatch(
        r"phase5-retry-[1-9][0-9]*-[1-9][0-9]*-scheduler-activation", title
    ) is None:
        _fail("scheduler grant condition title is invalid")
    _expect(
        condition.get("description"),
        "JIT activation of the exact four Phase 5 producer schedules",
        "scheduler grant condition description",
    )
    issued_at = _parse_time(grant.get("issued_at"), "scheduler grant issued_at")
    expires_at = _parse_time(grant.get("expires_at"), "scheduler grant expires_at")
    propagation_deadline = _parse_time(
        grant.get("propagation_deadline_at"), "scheduler grant propagation_deadline_at"
    )
    if not 1190 <= (expires_at - issued_at).total_seconds() <= 1210:
        _fail("scheduler grant is not limited to the exact twenty-minute window")
    if not 595 <= (propagation_deadline - issued_at).total_seconds() <= 605:
        _fail("scheduler propagation deadline is not the exact ten-minute bound")
    if propagation_deadline >= expires_at:
        _fail("scheduler propagation deadline is not before grant expiry")
    _expect(
        condition.get("expression"),
        f'request.time < timestamp("{grant.get("expires_at")}")',
        "scheduler grant condition expression",
    )

    before_grants = _scheduler_policy_member_bindings(
        before_policy, "roles/cloudscheduler.admin", DEPLOYER_MEMBER, "scheduler before policy"
    )
    granted_grants = _scheduler_policy_member_bindings(
        granted_policy, "roles/cloudscheduler.admin", DEPLOYER_MEMBER, "scheduler granted policy"
    )
    removed_grants = _scheduler_policy_member_bindings(
        removed_policy, "roles/cloudscheduler.admin", DEPLOYER_MEMBER, "scheduler removed policy"
    )
    if before_grants:
        _fail("scheduler activation authority was present before the JIT grant")
    if len(granted_grants) != 1 or granted_grants[0].get("condition") != condition:
        _fail("scheduler granted policy lacks the one exact conditional deployer binding")
    if removed_grants:
        _fail("scheduler activation authority remains after cleanup")

    for key, expected in {
        "name": PERMANENT_CONTROL_ROLE,
        "stage": "GA",
    }.items():
        _expect(permanent_role.get(key), expected, f"permanent control role {key}")
    _expect(permanent_role.get("deleted", False), False, "permanent control role deletion state")
    included_permissions = _require_list(
        permanent_role.get("includedPermissions"), "permanent control role permissions"
    )
    if not all(isinstance(value, str) and value for value in included_permissions):
        _fail("permanent control role permissions are invalid")
    forbidden_permissions = {
        "cloudscheduler.jobs.enable",
        "cloudscheduler.jobs.run",
        "cloudscheduler.jobs.delete",
    }
    if forbidden_permissions & set(included_permissions):
        _fail("permanent control role contains forbidden Scheduler activation authority")
    required_permissions = {
        "cloudscheduler.jobs.pause",
        "cloudscheduler.jobs.get",
        "cloudscheduler.jobs.list",
    }
    if not required_permissions <= set(included_permissions):
        _fail("permanent control role lacks its exact read-and-pause Scheduler authority")

    role_viewer_evidence = _require_object(
        permanent_role.get("temporary_role_viewer_evidence"),
        "permanent control role temporary Role Viewer evidence",
    )
    for key, expected in {
        "result": "jit_role_viewer_removed",
        "absent_before_grant": True,
        "grant_observed": True,
        "live_role_described": True,
        "physically_absent_after_removal": True,
    }.items():
        _expect(
            role_viewer_evidence.get(key),
            expected,
            f"temporary Role Viewer evidence {key}",
        )
    _expect(
        role_viewer_evidence.get("grant"),
        role_viewer_grant,
        "temporary Role Viewer evidence grant",
    )
    for key, expected in {
        "schema_version": 1,
        "result": "role_viewer_live_role_capture_requested",
        "project_id": PROJECT_ID,
        "member": DEPLOYER_MEMBER,
        "role": "roles/iam.roleViewer",
        "target_role_name": PERMANENT_CONTROL_ROLE,
        "authorized_operation": "iam.roles.get",
        "condition": role_viewer_condition,
        "condition_scope": "request_time_only",
    }.items():
        _expect(role_viewer_grant.get(key), expected, f"temporary Role Viewer grant {key}")
    role_viewer_title = role_viewer_condition.get("title")
    if not isinstance(role_viewer_title, str) or re.fullmatch(
        r"phase5-retry-[1-9][0-9]*-[1-9][0-9]*-role-viewer", role_viewer_title
    ) is None:
        _fail("temporary Role Viewer condition title is invalid")
    _expect(
        role_viewer_condition.get("description"),
        "JIT read of the exact permanent Phase 3 custom role",
        "temporary Role Viewer condition description",
    )
    role_viewer_issued_at = _parse_time(
        role_viewer_grant.get("issued_at"), "temporary Role Viewer grant issued_at"
    )
    role_viewer_expires_at = _parse_time(
        role_viewer_grant.get("expires_at"), "temporary Role Viewer grant expires_at"
    )
    role_viewer_propagation_deadline = _parse_time(
        role_viewer_grant.get("propagation_deadline_at"),
        "temporary Role Viewer grant propagation_deadline_at",
    )
    if not 890 <= (role_viewer_expires_at - role_viewer_issued_at).total_seconds() <= 910:
        _fail("temporary Role Viewer grant is not limited to the fifteen-minute window")
    if not 595 <= (
        role_viewer_propagation_deadline - role_viewer_issued_at
    ).total_seconds() <= 605:
        _fail("temporary Role Viewer propagation deadline is not the exact ten-minute bound")
    if role_viewer_propagation_deadline >= role_viewer_expires_at:
        _fail("temporary Role Viewer propagation deadline is not before grant expiry")
    _expect(
        role_viewer_condition.get("expression"),
        f'request.time < timestamp("{role_viewer_grant.get("expires_at")}")',
        "temporary Role Viewer condition expression",
    )

    role_viewer_before_bindings = _scheduler_policy_member_bindings(
        role_viewer_before_policy,
        "roles/iam.roleViewer",
        DEPLOYER_MEMBER,
        "Role Viewer before policy",
    )
    role_viewer_granted_bindings = _scheduler_policy_member_bindings(
        role_viewer_granted_policy,
        "roles/iam.roleViewer",
        DEPLOYER_MEMBER,
        "Role Viewer granted policy",
    )
    role_viewer_removed_bindings = _scheduler_policy_member_bindings(
        role_viewer_removed_policy,
        "roles/iam.roleViewer",
        DEPLOYER_MEMBER,
        "Role Viewer removed policy",
    )
    if role_viewer_before_bindings:
        _fail("Role Viewer authority was present before its JIT grant")
    if (
        len(role_viewer_granted_bindings) != 1
        or role_viewer_granted_bindings[0].get("condition") != role_viewer_condition
    ):
        _fail("Role Viewer granted policy lacks the one exact conditional deployer binding")
    if role_viewer_removed_bindings:
        _fail("temporary Role Viewer authority remains after cleanup")
    for label, policy in (
        ("Role Viewer before policy", role_viewer_before_policy),
        ("Role Viewer granted policy", role_viewer_granted_policy),
        ("Role Viewer removed policy", role_viewer_removed_policy),
    ):
        if _scheduler_policy_member_bindings(
            policy, "roles/cloudscheduler.admin", DEPLOYER_MEMBER, label
        ):
            _fail(f"{label} overlaps Scheduler activation authority")
        bindings = _scheduler_policy_member_bindings(
            policy, PERMANENT_CONTROL_ROLE, DEPLOYER_MEMBER, label
        )
        if len(bindings) != 1 or bindings[0].get("condition") is not None:
            _fail(f"{label} does not preserve the exact permanent control-role binding")
    for label, policy in (
        ("scheduler before policy", before_policy),
        ("scheduler granted policy", granted_policy),
        ("scheduler removed policy", removed_policy),
    ):
        if _scheduler_policy_member_bindings(
            policy, "roles/iam.roleViewer", DEPLOYER_MEMBER, label
        ):
            _fail(f"temporary Role Viewer authority overlaps {label}")

    expected_role_viewer_hashes = {
        "before_policy": _sha256_file(files["role_viewer_before_policy"]),
        "granted_policy": _sha256_file(files["role_viewer_granted_policy"]),
        "removed_policy": _sha256_file(files["role_viewer_removed_policy"]),
        "condition": _sha256_file(files["role_viewer_condition"]),
        "grant_request": _sha256_file(files["role_viewer_grant_request"]),
    }
    _expect(
        role_viewer_evidence.get("evidence_sha256"),
        expected_role_viewer_hashes,
        "temporary Role Viewer raw evidence hashes",
    )
    permanent_bindings = _scheduler_policy_member_bindings(
        before_policy, PERMANENT_CONTROL_ROLE, DEPLOYER_MEMBER, "scheduler before policy"
    )
    if len(permanent_bindings) != 1 or permanent_bindings[0].get("condition") is not None:
        _fail("deployer lacks its exact unconditional permanent control-role binding")
    removed_permanent_bindings = _scheduler_policy_member_bindings(
        removed_policy, PERMANENT_CONTROL_ROLE, DEPLOYER_MEMBER, "scheduler removed policy"
    )
    if (
        len(removed_permanent_bindings) != 1
        or removed_permanent_bindings[0].get("condition") is not None
    ):
        _fail("temporary cleanup altered the deployer's permanent control-role binding")

    expected_evidence_hashes = {
        "before_policy": _sha256_file(files["before_policy"]),
        "granted_policy": _sha256_file(files["granted_policy"]),
        "removed_policy": _sha256_file(files["removed_policy"]),
        "permanent_control_role": _sha256_file(files["permanent_control_role"]),
        "condition": _sha256_file(files["condition"]),
        "grant_request": _sha256_file(files["grant_request"]),
        "resume_attempts": _sha256_file(files["resume_attempts"]),
        "scheduler_transition": _sha256_file(files["transition"]),
    }
    _expect(
        summary.get("evidence_sha256"),
        expected_evidence_hashes,
        "scheduler activation authority raw evidence hashes",
    )

    if len(attempts) < 4:
        _fail("scheduler resume attempt timeline is incomplete")
    resumed: list[str] = []
    legislative_attempts: list[int] = []
    for index, value in enumerate(attempts, start=1):
        attempt = _require_object(value, f"scheduler resume attempt {index}")
        scheduler = attempt.get("scheduler")
        outcome = attempt.get("outcome")
        if scheduler not in scheduler_names or outcome not in {"resumed", "iam_propagation_pending"}:
            _fail(f"scheduler resume attempt {index} is outside the authorized transition")
        attempt_number = attempt.get("attempt")
        if isinstance(attempt_number, bool) or not isinstance(attempt_number, int) or attempt_number < 1:
            _fail(f"scheduler resume attempt {index} number is invalid")
        observed_at = _parse_time(attempt.get("observed_at"), f"scheduler resume attempt {index}")
        if observed_at < issued_at or observed_at >= expires_at:
            _fail(f"scheduler resume attempt {index} is outside the JIT authority window")
        digest = attempt.get("evidence_sha256")
        if not isinstance(digest, str) or SHA64.fullmatch(digest) is None:
            _fail(f"scheduler resume attempt {index} evidence digest is invalid")
        denial_error = attempt.get("denial_error")
        if outcome == "resumed":
            _expect(denial_error, None, f"scheduler resume attempt {index} denial error")
        else:
            legislative_resource = resource_names[0]
            if not isinstance(denial_error, str) or any(
                token not in denial_error
                for token in (
                    "PERMISSION_DENIED",
                    "cloudscheduler.jobs.enable",
                    legislative_resource,
                )
            ):
                _fail("scheduler IAM propagation denial is not the exact expected denial")
        if scheduler == scheduler_names[0]:
            legislative_attempts.append(attempt_number)
            if observed_at >= propagation_deadline:
                _fail("first-scheduler propagation attempt exceeded its bounded deadline")
        elif attempt_number != 1 or outcome != "resumed":
            _fail("only the first producer scheduler may use the bounded propagation probe")
        if outcome == "iam_propagation_pending" and scheduler != scheduler_names[0]:
            _fail("IAM propagation probing escaped the first producer scheduler")
        if outcome == "resumed":
            resumed.append(str(scheduler))
    _expect(resumed, scheduler_names, "scheduler resumed producer order")
    _expect(
        legislative_attempts,
        list(range(1, len(legislative_attempts) + 1)),
        "scheduler propagation attempt sequence",
    )
    if attempts[-1].get("scheduler") != scheduler_names[-1] or attempts[-1].get("outcome") != "resumed":
        _fail("scheduler resume timeline lacks a terminal dashboard resume")

    receipt_summaries = _require_list(
        summary.get("resume_receipts"), "scheduler resume receipt hashes"
    )
    if len(receipt_summaries) != 4:
        _fail("scheduler authority summary does not bind exactly four resume receipts")
    actual_receipt_hashes: dict[str, str] = {}
    for path in resume_receipts:
        receipt = _load_object(path)
        resource_name = receipt.get("name")
        if resource_name not in resource_names:
            _fail("scheduler resume receipt names an unauthorized resource")
        scheduler = str(resource_name).rsplit("/", 1)[-1]
        if scheduler in actual_receipt_hashes:
            _fail("scheduler resume receipts contain a duplicate producer")
        _expect(receipt.get("state"), "ENABLED", f"scheduler resume receipt {scheduler} state")
        actual_receipt_hashes[scheduler] = _sha256_file(path)
    expected_receipt_summaries = [
        {"scheduler": name, "sha256": actual_receipt_hashes.get(name)}
        for name in scheduler_names
    ]
    _expect(receipt_summaries, expected_receipt_summaries, "scheduler resume receipt hashes")
    resumed_attempts = [item for item in attempts if item.get("outcome") == "resumed"]
    for attempt, receipt in zip(resumed_attempts, expected_receipt_summaries):
        _expect(attempt.get("scheduler"), receipt["scheduler"], "scheduler resumed attempt binding")
        _expect(attempt.get("evidence_sha256"), receipt["sha256"], "scheduler resume evidence hash")

    def validate_summary(
        value: Mapping[str, Any], phase: str, jobs: Sequence[Path]
    ) -> dict[str, Mapping[str, Any]]:
        for key, expected in {
            "schema_version": 1,
            "phase": phase,
            "project_id": PROJECT_ID,
            "location": REGION,
        }.items():
            _expect(value.get(key), expected, f"scheduler {phase} summary {key}")
        rows = _require_list(value.get("schedulers"), f"scheduler {phase} summary rows")
        if len(rows) != 5:
            _fail(f"scheduler {phase} summary does not contain exactly five jobs")
        by_name: dict[str, Mapping[str, Any]] = {}
        raw_by_name: dict[str, tuple[Path, Mapping[str, Any]]] = {}
        for path in jobs:
            raw = _load_object(path)
            resource_name = raw.get("name")
            if not isinstance(resource_name, str):
                _fail(f"scheduler {phase} raw job name is invalid")
            name = resource_name.rsplit("/", 1)[-1]
            if name in raw_by_name:
                _fail(f"scheduler {phase} raw jobs contain a duplicate")
            raw_by_name[name] = (path, raw)
        _expect(set(raw_by_name), set(all_scheduler_names), f"scheduler {phase} raw job set")
        for index, row_value in enumerate(rows):
            row = _require_object(row_value, f"scheduler {phase} summary row {index + 1}")
            name = row.get("name")
            if name != all_scheduler_names[index] or name in by_name:
                _fail(f"scheduler {phase} summary job order/set is invalid")
            path, raw = raw_by_name[str(name)]
            expected_state = "PAUSED" if phase == "before" or name == VAULT_SCHEDULER else "ENABLED"
            expected_resource = f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{name}"
            for key, expected in {
                "resource_name": expected_resource,
                "state": expected_state,
                "raw_sha256": _sha256_file(path),
                "canonical_spec_sha256": _scheduler_spec_sha256(raw),
            }.items():
                _expect(row.get(key), expected, f"scheduler {phase} {name} {key}")
            _expect(raw.get("name"), expected_resource, f"scheduler {phase} raw {name} name")
            _expect(raw.get("state"), expected_state, f"scheduler {phase} raw {name} state")
            by_name[str(name)] = row
        return by_name

    before_rows = validate_summary(before_summary, "before", before_jobs)
    after_rows = validate_summary(after_summary, "after", after_jobs)
    for phase, inventory in (("before", before_inventory), ("after", after_inventory)):
        values = _require_list(inventory, f"scheduler {phase} list inventory")
        if len(values) != 5:
            _fail(f"scheduler {phase} list inventory does not contain exactly five jobs")
        inventory_by_name: dict[str, Mapping[str, Any]] = {}
        for item in values:
            row = _require_object(item, f"scheduler {phase} list inventory row")
            resource_name = row.get("name")
            if not isinstance(resource_name, str):
                _fail(f"scheduler {phase} list inventory name is invalid")
            name = resource_name.rsplit("/", 1)[-1]
            if name in inventory_by_name:
                _fail(f"scheduler {phase} list inventory contains a duplicate")
            inventory_by_name[name] = row
        _expect(set(inventory_by_name), set(all_scheduler_names), f"scheduler {phase} inventory set")
        for name, row in inventory_by_name.items():
            expected_state = "PAUSED" if phase == "before" or name == VAULT_SCHEDULER else "ENABLED"
            _expect(
                row.get("name"),
                f"projects/{PROJECT_ID}/locations/{REGION}/jobs/{name}",
                f"scheduler {phase} inventory {name} resource name",
            )
            _expect(row.get("state"), expected_state, f"scheduler {phase} inventory {name} state")

    for key, expected in {
        "schema_version": 1,
        "result": "exact_four_producer_schedulers_enabled_vault_unchanged",
        "project_id": PROJECT_ID,
        "location": REGION,
        "before_summary_sha256": _sha256_file(files["before_summary"]),
        "after_summary_sha256": _sha256_file(files["after_summary"]),
        "before": before_summary,
        "after": after_summary,
    }.items():
        _expect(transition.get(key), expected, f"scheduler transition {key}")
    transitions = _require_list(
        transition.get("authorized_transitions"), "scheduler authorized transitions"
    )
    if len(transitions) != 4:
        _fail("scheduler transition does not contain exactly four authorized jobs")
    for name, value in zip(scheduler_names, transitions):
        row = _require_object(value, f"scheduler transition {name}")
        before_row = before_rows[name]
        after_row = after_rows[name]
        for key, expected in {
            "name": name,
            "before_state": "PAUSED",
            "after_state": "ENABLED",
            "before_spec_sha256": before_row.get("canonical_spec_sha256"),
            "after_spec_sha256": after_row.get("canonical_spec_sha256"),
            "spec_unchanged": True,
        }.items():
            _expect(row.get(key), expected, f"scheduler transition {name} {key}")
        _expect(
            row.get("before_spec_sha256"),
            row.get("after_spec_sha256"),
            f"scheduler transition {name} immutable specification",
        )
    vault = _require_object(transition.get("vault"), "scheduler transition vault")
    for key, expected in {
        "name": VAULT_SCHEDULER,
        "before_state": "PAUSED",
        "after_state": "PAUSED",
        "before_spec_sha256": before_rows[VAULT_SCHEDULER].get("canonical_spec_sha256"),
        "after_spec_sha256": after_rows[VAULT_SCHEDULER].get("canonical_spec_sha256"),
        "spec_unchanged": True,
    }.items():
        _expect(vault.get(key), expected, f"scheduler transition vault {key}")
    _expect(
        vault.get("before_spec_sha256"),
        vault.get("after_spec_sha256"),
        "scheduler transition vault immutable specification",
    )


def _validate_completion_manifest(
    manifest: Mapping[str, Any], scheduler_evidence_paths: Mapping[str, Any]
) -> None:
    for key, expected in {"schema_version": 1, "phase": "phase5_reconciliation_completion"}.items():
        _expect(manifest.get(key), expected, f"completion manifest {key}")
    preflight = _require_object(manifest.get("preflight"), "completion preflight")
    cleanup = _require_object(manifest.get("cleanup"), "completion cleanup")
    promotion = _require_object(manifest.get("promotion"), "completion promotion")
    _base_preflight(preflight)
    _required_true(
        preflight,
        (
            "phase4_certificate_verified",
            "failed_promotion_replay_verified",
            "concurrent_writer_incident_acknowledged",
            "old_smoke_prefix_invalidated",
            "legacy_ai_artifact_quarantined",
            "frozen_legacy_successors_verified",
            "failed_retry_intervening_attempt_verified",
            "failed_retry_successor_intervening_attempt_verified",
            "legacy_runs_drained",
            "legacy_workflows_disabled",
            "continuation_heads_verified",
            "no_rebaseline_performed",
            "full_snapshot_chain_preserved",
            "temporary_private_web_invoker_removed",
            "scheduler_activation_authority_absent_before_grant",
            "temporary_role_inspection_authority_removed",
            "no_concurrent_legacy_runs",
            "fresh_cycle_global_one_writer_verified",
        ),
        "completion preflight",
    )
    _base_cleanup(cleanup)
    _required_true(
        cleanup,
        (
            "legacy_workflows_disabled",
            "producer_schedulers_enabled",
            "web_public_invoker_present",
            "runtime_jobs_production_mode",
            "no_rebaseline_performed",
            "full_snapshot_chain_preserved",
            "temporary_private_web_invoker_removed",
            "temporary_scheduler_activation_authority_removed",
            "temporary_role_inspection_authority_removed",
        ),
        "completion cleanup",
    )
    _required_true(
        promotion,
        (
            "legacy_workflows_disabled",
            "legacy_runs_drained",
            "runtime_jobs_production_mode",
            "web_public_invoker_present",
            "readyz_ok",
            "dashboard_ok",
            "cloud_sql_private_only",
            "rollback_armed",
            "fresh_cycle_global_one_writer_verified",
        ),
        "completion promotion",
    )
    _expect(promotion.get("healthz_ok"), False, "completion /healthz diagnostic result")
    _expect(
        promotion.get("healthz_platform_diagnostic_only"),
        True,
        "completion /healthz diagnostic-only classification",
    )
    _expect(
        promotion.get("api_healthz_accepted"),
        False,
        "completion /api/healthz acceptance",
    )
    public_route = _require_object(promotion.get("public_route"), "completion public route contract")
    _expect(
        public_route.get("health_gate_paths"),
        ["/readyz", "/"],
        "completion public health gate paths",
    )
    _expect(
        public_route.get("api_healthz_accepted"),
        False,
        "completion /api/healthz acceptance",
    )
    _required_true(
        public_route,
        ("readyz_accepted", "root_accepted", "dashboard_snapshot_verified"),
        "completion public route",
    )
    route_verification = _require_object(
        promotion.get("public_route_verification"),
        "completion public route verification",
    )
    for key, expected in {
        "schema_version": 1,
        "result": "phase5_retry_public_route_verified",
        "url": promotion.get("web_url"),
        "expected_snapshot_sha256": promotion.get("ready_snapshot_sha256"),
    }.items():
        _expect(route_verification.get(key), expected, f"completion public route verification {key}")
    _expect(
        promotion.get("served_snapshot_sha256"),
        route_verification.get("expected_snapshot_sha256"),
        "completion served public snapshot",
    )

    healthz = _require_object(route_verification.get("healthz"), "completion /healthz diagnostic")
    health_status = healthz.get("http_status")
    if (
        isinstance(health_status, bool)
        or not isinstance(health_status, int)
        or (health_status != 0 and not 100 <= health_status <= 599)
    ):
        _fail("completion /healthz diagnostic HTTP status is invalid")
    server = healthz.get("server")
    if not isinstance(server, str):
        _fail("completion /healthz diagnostic server is invalid")
    server_lower = server.casefold()
    if health_status == 404 and ("google frontend" in server_lower or "gfe" in server_lower):
        expected_health_classification = "gfe_404_platform_diagnostic_only"
    elif health_status == 200:
        expected_health_classification = "supplemental_application_diagnostic_only"
    elif health_status == 0:
        expected_health_classification = "unavailable_platform_diagnostic_only"
    else:
        expected_health_classification = f"http_{health_status:03d}_platform_diagnostic_only"
    _expect(
        healthz.get("classification"),
        expected_health_classification,
        "completion /healthz captured classification",
    )
    _expect(healthz.get("certification_gate"), False, "completion /healthz gate status")
    _expect(
        public_route.get("healthz_classification"),
        healthz.get("classification"),
        "completion /healthz classification binding",
    )

    api_healthz = _require_object(
        route_verification.get("api_healthz"), "completion /api/healthz diagnostic"
    )
    _expect(api_healthz.get("queried"), False, "completion /api/healthz query status")
    _expect(
        api_healthz.get("accepted_as_health"), False, "completion /api/healthz gate status"
    )
    readyz = _require_object(route_verification.get("readyz"), "completion /readyz evidence")
    for key, expected in {
        "http_status": 200,
        "json_verified": True,
        "expected_snapshot_verified": True,
        "certification_gate": True,
    }.items():
        _expect(readyz.get(key), expected, f"completion /readyz {key}")
    ready_content_type = readyz.get("content_type")
    if not isinstance(ready_content_type, str) or not ready_content_type.casefold().startswith(
        "application/json"
    ):
        _fail("completion /readyz content type is invalid")
    dashboard_route = _require_object(
        route_verification.get("dashboard"), "completion dashboard route evidence"
    )
    for key, expected in {
        "http_status": 200,
        "html_verified": True,
        "snapshot_header_verified": True,
        "certification_gate": True,
    }.items():
        _expect(dashboard_route.get(key), expected, f"completion dashboard route {key}")
    dashboard_content_type = dashboard_route.get("content_type")
    if not isinstance(dashboard_content_type, str) or not dashboard_content_type.casefold().startswith(
        "text/html"
    ):
        _fail("completion dashboard route content type is invalid")
    _expect(promotion.get("production_route"), "runtime_v2", "completion production route")
    enabled = promotion.get("enabled_producer_schedulers")
    if not isinstance(enabled, list) or tuple(sorted(enabled)) != tuple(sorted(PRODUCER_SCHEDULERS)):
        _fail("completion does not enable exactly the four Runtime v2 producer schedulers")
    disabled = promotion.get("disabled_legacy_workflows")
    if not isinstance(disabled, list) or tuple(sorted(disabled)) != tuple(sorted(LEGACY_WORKFLOWS)):
        _fail("completion does not disable exactly the four legacy workflows")
    _expect(promotion.get("vault_scheduler_state"), "PAUSED", "completion vault scheduler state")

    _validate_scheduler_activation_authority(manifest, scheduler_evidence_paths)

    retry = _require_object(manifest.get("retry"), "completion retry binding")
    for key, expected in {
        "kind": "failed_phase5_retry_with_fresh_smoke_cycle",
        "failed_phase5_run_id": FAILED_PHASE5_RUN_ID,
        "failed_retry_run_id": FAILED_PHASE5_RETRY_RUN_ID,
        "failed_retry_successor_run_id": FAILED_PHASE5_RETRY_SUCCESSOR_RUN_ID,
        "intervening_retry_certification_eligible": False,
        "intervening_retry_successor_certification_eligible": False,
        "failed_prefix_replay_result": "phase5_failed_promotion_reconciled",
        "invalidated_smoke_prefix_certification_eligible": False,
        "concurrent_legacy_ai_successor_quarantined": True,
        "merge_or_import_authorized": False,
    }.items():
        _expect(retry.get(key), expected, f"completion retry {key}")
    _expect(manifest.get("phase6_started"), False, "completion Phase 6 state")


def complete_phase5(
    *,
    descriptor: dict[str, Any],
    replay: dict[str, Any],
    terminal_baseline: dict[str, Any],
    terminal_manifest: dict[str, Any],
    control_revision: str,
    replay_sha256: str,
    terminal_legacy_run_inventories: Sequence[Mapping[str, Any]],
    terminal_legacy_workflow_states: Sequence[Mapping[str, Any]],
    terminal_runtime_execution_inventories: Sequence[Mapping[str, Any]],
    terminal_evidence_digests: Mapping[str, Sequence[str]],
    scheduler_evidence_paths: Mapping[str, Any],
) -> dict[str, Any]:
    _validate_descriptor(descriptor)
    _validate_replay_receipt(descriptor, replay)
    if not isinstance(replay_sha256, str) or SHA64.fullmatch(replay_sha256) is None:
        _fail("replay receipt checksum is invalid")
    if not isinstance(control_revision, str) or SHA40.fullmatch(control_revision) is None:
        _fail("completion control revision is invalid")
    _expect(
        terminal_manifest.get("control_revision"),
        control_revision,
        "completion manifest control revision",
    )
    reconciliation = _require_object(replay.get("reconciliation"), "replay reconciliation")
    _required_true(
        reconciliation,
        (
            "old_smoke_cycle_invalidated",
            "fresh_clean_smoke_cycle_required",
            "global_one_writer_violation_verified",
            "legacy_ai_artifact_quarantined",
            "full_snapshot_chain_preserved",
        ),
        "replay reconciliation",
    )
    _expect(reconciliation.get("rebaseline_performed"), False, "replay rebaseline")
    _expect(
        reconciliation.get("legacy_artifact_merge_or_import_authorized"),
        False,
        "replay legacy merge/import authorization",
    )
    legacy = _require_object(replay.get("concurrent_legacy_ai"), "replay legacy AI evidence")
    _expect(legacy.get("disposition"), "quarantined_separate_legacy_artifact", "legacy disposition")
    _expect(legacy.get("merge_or_import_authorized"), False, "legacy merge/import authorization")

    continuation = _require_object(replay.get("continuation_heads"), "replay continuation heads")
    baseline_heads = _heads(terminal_baseline)
    _same_heads(baseline_heads, continuation, "clean-cycle terminal baseline")
    prefix = _require_object(replay.get("invalidated_smoke_prefix"), "invalidated smoke prefix")
    prefix_receipts = _require_list(prefix.get("executions"), "invalidated smoke receipts")
    if len(prefix_receipts) != 4:
        _fail("invalidated smoke prefix does not contain exactly four receipts")
    failed_retry = _require_object(
        replay.get("failed_phase5_retry"), "replay failed Phase 5 retry"
    )
    retry_receipts = _require_list(
        failed_retry.get("executions"), "failed Phase 5 retry executions"
    )
    if len(retry_receipts) != 4:
        _fail("failed Phase 5 retry does not contain exactly four receipts")
    failed_retry_successor = _require_object(
        replay.get("failed_phase5_retry_successor"),
        "replay failed Phase 5 retry successor",
    )
    retry_successor_receipts = _require_list(
        failed_retry_successor.get("executions"),
        "failed Phase 5 retry successor executions",
    )
    if len(retry_successor_receipts) != 4:
        _fail("failed Phase 5 retry successor does not contain exactly four receipts")
    latest = _latest_runs(terminal_baseline)
    if set(latest) != set(NAMESPACES):
        _fail("clean-cycle baseline lacks exact latest failed-retry-successor receipts")
    for item in retry_successor_receipts:
        run = latest.get(str(item.get("job")))
        if run is None:
            _fail("clean-cycle baseline lost a failed-retry-successor receipt")
        for key, value in {
            "run_id": item.get("run_id"),
            "status": "success",
            "runtime_mode": "production",
            "runtime_mode_verified": True,
            "trigger_source": "phase5_smoke",
            "side_effects_possible": False,
            "source_revision": RUNTIME_SOURCE_REVISION,
            "snapshot_generation": item.get("generation"),
            "snapshot_sha256": item.get("snapshot_sha256"),
        }.items():
            _expect(run.get(key), value, f"clean-cycle baseline {item.get('job')} {key}")

    _validate_completion_manifest(terminal_manifest, scheduler_evidence_paths)
    retry = _require_object(terminal_manifest.get("retry"), "completion retry binding")
    _expect(
        retry.get("failed_prefix_replay_sha256"),
        replay_sha256,
        "completion replay receipt checksum",
    )
    observations = _require_list(terminal_manifest.get("executions"), "completion executions")
    final_heads, receipts = _validate_sequence(
        baseline=terminal_baseline,
        observations=observations,
        expected_mode="production",
        expected_trigger="phase5_smoke",
        cycles=1,
        runtime_source_revision=RUNTIME_SOURCE_REVISION,
    )
    prior_receipts = [*prefix_receipts, *retry_receipts, *retry_successor_receipts]
    old_ids = {item.get("run_id") for item in prior_receipts}
    old_executions = {item.get("cloud_run_execution") for item in prior_receipts}
    if any(item.get("run_id") in old_ids for item in receipts):
        _fail("fresh smoke cycle reused an invalidated Runtime receipt")
    if any(item.get("cloud_run_execution") in old_executions for item in receipts):
        _fail("fresh smoke cycle reused an invalidated Cloud Run execution")
    old_finish = max(
        _parse_time(item.get("finished_at"), "failed retry smoke finished_at")
        for item in retry_successor_receipts
    )
    new_start = min(_parse_time(item.get("started_at"), "fresh smoke started_at") for item in receipts)
    if new_start <= old_finish:
        _fail("fresh smoke cycle overlaps the intervening failed retry")
    _validate_terminal_one_writer(
        descriptor=descriptor,
        replay=replay,
        manifest=terminal_manifest,
        receipts=receipts,
        legacy_run_inventories=terminal_legacy_run_inventories,
        legacy_workflow_states=terminal_legacy_workflow_states,
        runtime_execution_inventories=terminal_runtime_execution_inventories,
        evidence_digests=terminal_evidence_digests,
    )

    promotion = _require_object(terminal_manifest.get("promotion"), "completion promotion")
    dashboard_digest = final_heads["dashboard"]["snapshot_sha256"]
    for key in ("ready_snapshot_sha256", "served_snapshot_sha256"):
        _expect(promotion.get(key), dashboard_digest, f"completion public dashboard {key}")
    web_url = promotion.get("web_url")
    if not isinstance(web_url, str) or not web_url.startswith("https://"):
        _fail("completion Runtime v2 web URL is invalid")

    return {
        "schema_version": 1,
        "result": "phase5_complete",
        "repository_id": REPOSITORY_ID,
        "control_revision": control_revision,
        "certified_phase4_control_revision": CERTIFIED_CONTROL_REVISION,
        "runtime_source_revision": RUNTIME_SOURCE_REVISION,
        "immutable_image": descriptor["immutable_image"],
        "production_route": "runtime_v2",
        "production_authority_transferred": True,
        "unique_successful_smoke_receipts": 4,
        "executions": receipts,
        "baseline_heads": _head_summary(baseline_heads),
        "final_heads": _head_summary(final_heads),
        "enabled_producer_schedulers": list(PRODUCER_SCHEDULERS),
        "disabled_legacy_workflows": list(LEGACY_WORKFLOWS),
        "vault_scheduler_state": "PAUSED",
        "web_url": web_url,
        "served_snapshot_sha256": dashboard_digest,
        "cloud_sql_private_only": True,
        "temporary_authority_removed": True,
        "temporary_scheduler_activation_authority_removed": True,
        "temporary_role_inspection_authority_removed": True,
        "scheduler_activation_authority": terminal_manifest["scheduler_activation_authority"],
        "rollback_armed": True,
        "phase6_started": False,
        "reconciliation": {
            "kind": "incident_bound_clean_cycle_after_concurrent_writer",
            "descriptor_sha256": replay["descriptor_sha256"],
            "replay_receipt_sha256": replay_sha256,
            "failed_phase5_run_id": FAILED_PHASE5_RUN_ID,
            "phase4_certificate": replay["phase4_certificate"],
            "failed_phase5": replay["failed_phase5"],
            "invalidated_smoke_prefix": prefix,
            "failed_phase5_retry": failed_retry,
            "failed_phase5_retry_successor": failed_retry_successor,
            "concurrent_legacy_ai": legacy,
            "recovery_runs": replay["recovery_runs"],
            "frozen_legacy_successors": replay["frozen_legacy_successors"],
            "legacy_high_water": replay["legacy_high_water"],
            "legacy_ai_artifact_quarantined": True,
            "legacy_artifact_merge_or_import_authorized": False,
            "fresh_clean_smoke_cycle_verified": True,
            "additional_runtime_producer_execution_performed": True,
            "additional_runtime_producer_execution_count": 4,
            "rebaseline_performed": False,
            "full_snapshot_chain_preserved": True,
            "phase6_started": False,
        },
    }


def _source(args: argparse.Namespace, prefix: str) -> dict[str, Any]:
    return {
        "run": _load_object(getattr(args, f"{prefix}_run_metadata")),
        "artifact": _load_object(getattr(args, f"{prefix}_artifact_metadata")),
        "jobs": _load_object(getattr(args, f"{prefix}_jobs_metadata")),
        "archive": getattr(args, f"{prefix}_archive"),
    }


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _add_metadata_source(parser: argparse.ArgumentParser, prefix: str, *, archive: bool = True) -> None:
    parser.add_argument(f"--{prefix.replace('_', '-')}-run-metadata", type=Path, required=True)
    parser.add_argument(f"--{prefix.replace('_', '-')}-jobs-metadata", type=Path, required=True)
    if archive:
        parser.add_argument(f"--{prefix.replace('_', '-')}-artifact-metadata", type=Path, required=True)
        parser.add_argument(f"--{prefix.replace('_', '-')}-archive", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    replay = subparsers.add_parser("replay", help="validate and quarantine the failed attempt")
    replay.add_argument("--descriptor", type=Path, required=True)
    replay.add_argument("--repository-root", type=Path, required=True)
    replay.add_argument("--current-status", type=Path, required=True)
    replay.add_argument("--current-ai-analyses", type=Path, required=True)
    _add_metadata_source(replay, "phase4")
    _add_metadata_source(replay, "failed")
    _add_metadata_source(replay, "failed_retry")
    _add_metadata_source(replay, "failed_retry_successor")
    _add_metadata_source(replay, "legacy_ai", archive=False)
    for label in ("predecessor", "state", "output"):
        replay.add_argument(f"--legacy-ai-{label}-artifact-metadata", type=Path, required=True)
        replay.add_argument(f"--legacy-ai-{label}-archive", type=Path, required=True)
    replay.add_argument("--recovery-run-metadata", type=Path, action="append", required=True)
    replay.add_argument("--recovery-jobs-metadata", type=Path, action="append", required=True)
    replay.add_argument(
        "--recovery-predecessor-artifact-metadata", type=Path, action="append", required=True
    )
    replay.add_argument("--recovery-predecessor-archive", type=Path, action="append", required=True)
    replay.add_argument("--recovery-artifact-metadata", type=Path, action="append", required=True)
    replay.add_argument("--recovery-archive", type=Path, action="append", required=True)
    replay.add_argument(
        "--recovery-output-artifact-metadata", type=Path, action="append", required=True
    )
    replay.add_argument("--recovery-output-archive", type=Path, action="append", required=True)
    replay.add_argument("--frozen-successor-run-metadata", type=Path, action="append", required=True)
    replay.add_argument("--frozen-successor-jobs-metadata", type=Path, action="append", required=True)
    replay.add_argument(
        "--frozen-successor-artifact-metadata", type=Path, action="append", required=True
    )
    replay.add_argument("--frozen-successor-archive", type=Path, action="append", required=True)
    replay.add_argument(
        "--frozen-successor-output-artifact-metadata",
        type=Path,
        action="append",
        required=True,
    )
    replay.add_argument(
        "--frozen-successor-output-archive", type=Path, action="append", required=True
    )
    replay.add_argument("--legacy-run-inventory", type=Path, action="append", required=True)
    replay.add_argument("--legacy-artifact-inventory", type=Path, action="append", required=True)
    replay.add_argument("--output", type=Path, required=True)

    complete = subparsers.add_parser("complete", help="validate the fresh cycle and issue Phase 5")
    complete.add_argument("--descriptor", type=Path, required=True)
    complete.add_argument("--replay", type=Path, required=True)
    complete.add_argument("--replay-checksum", type=Path, required=True)
    complete.add_argument("--terminal-baseline", type=Path, required=True)
    complete.add_argument("--terminal-manifest", type=Path, required=True)
    complete.add_argument(
        "--terminal-legacy-run-inventory", type=Path, action="append", required=True
    )
    complete.add_argument(
        "--terminal-legacy-workflow-state", type=Path, action="append", required=True
    )
    complete.add_argument(
        "--terminal-runtime-execution-inventory", type=Path, action="append", required=True
    )
    for flag in (
        "scheduler-authority-summary",
        "scheduler-transition",
        "scheduler-before-policy",
        "scheduler-granted-policy",
        "scheduler-removed-policy",
        "permanent-control-role",
        "role-viewer-before-policy",
        "role-viewer-granted-policy",
        "role-viewer-removed-policy",
        "role-viewer-condition",
        "role-viewer-grant-request",
        "scheduler-condition",
        "scheduler-grant-request",
        "scheduler-resume-attempts",
        "scheduler-before-summary",
        "scheduler-after-summary",
        "scheduler-before-inventory",
        "scheduler-after-inventory",
    ):
        complete.add_argument(f"--{flag}", type=Path, required=True)
    complete.add_argument("--scheduler-before-job", type=Path, action="append", required=True)
    complete.add_argument("--scheduler-after-job", type=Path, action="append", required=True)
    complete.add_argument(
        "--scheduler-resume-receipt", type=Path, action="append", required=True
    )
    complete.add_argument("--control-revision", required=True)
    complete.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    descriptor = _load_object(args.descriptor)
    if args.mode == "replay":
        receipt = reconcile_failed_phase5(
            descriptor=descriptor,
            repository_root=args.repository_root,
            current_status=_load_object(args.current_status),
            current_ai_analyses=_load_list_or_object(args.current_ai_analyses),
            phase4_source=_source(args, "phase4"),
            failed_source=_source(args, "failed"),
            failed_retry_source=_source(args, "failed_retry"),
            failed_retry_successor_source=_source(args, "failed_retry_successor"),
            legacy_ai_source={
                "run": _load_object(args.legacy_ai_run_metadata),
                "jobs": _load_object(args.legacy_ai_jobs_metadata),
                "predecessor_artifact": _load_object(args.legacy_ai_predecessor_artifact_metadata),
                "predecessor_archive": args.legacy_ai_predecessor_archive,
                "state_artifact": _load_object(args.legacy_ai_state_artifact_metadata),
                "state_archive": args.legacy_ai_state_archive,
                "output_artifact": _load_object(args.legacy_ai_output_artifact_metadata),
                "output_archive": args.legacy_ai_output_archive,
            },
            recovery_run_metadatas=[_load_object(path) for path in args.recovery_run_metadata],
            recovery_jobs_metadatas=[_load_object(path) for path in args.recovery_jobs_metadata],
            recovery_predecessor_artifact_metadatas=[
                _load_object(path) for path in args.recovery_predecessor_artifact_metadata
            ],
            recovery_predecessor_archives=args.recovery_predecessor_archive,
            recovery_artifact_metadatas=[
                _load_object(path) for path in args.recovery_artifact_metadata
            ],
            recovery_archives=args.recovery_archive,
            recovery_output_artifact_metadatas=[
                _load_object(path) for path in args.recovery_output_artifact_metadata
            ],
            recovery_output_archives=args.recovery_output_archive,
            frozen_successor_run_metadatas=[
                _load_object(path) for path in args.frozen_successor_run_metadata
            ],
            frozen_successor_jobs_metadatas=[
                _load_object(path) for path in args.frozen_successor_jobs_metadata
            ],
            frozen_successor_artifact_metadatas=[
                _load_object(path) for path in args.frozen_successor_artifact_metadata
            ],
            frozen_successor_archives=args.frozen_successor_archive,
            frozen_successor_output_artifact_metadatas=[
                _load_object(path) for path in args.frozen_successor_output_artifact_metadata
            ],
            frozen_successor_output_archives=args.frozen_successor_output_archive,
            legacy_run_inventories=[_load_object(path) for path in args.legacy_run_inventory],
            legacy_artifact_inventories=[
                _load_object(path) for path in args.legacy_artifact_inventory
            ],
        )
    else:
        replay_sha256 = _parse_sha256_file(
            args.replay_checksum.read_bytes(), args.replay.name, "replay receipt checksum"
        )
        _expect(_sha256_file(args.replay), replay_sha256, "replay receipt file checksum")
        terminal_run_paths = args.terminal_legacy_run_inventory
        terminal_state_paths = args.terminal_legacy_workflow_state
        terminal_execution_paths = args.terminal_runtime_execution_inventory
        receipt = complete_phase5(
            descriptor=descriptor,
            replay=_load_object(args.replay),
            terminal_baseline=_load_object(args.terminal_baseline),
            terminal_manifest=_load_object(args.terminal_manifest),
            control_revision=args.control_revision,
            replay_sha256=replay_sha256,
            terminal_legacy_run_inventories=[
                _load_object(path) for path in terminal_run_paths
            ],
            terminal_legacy_workflow_states=[
                _load_object(path) for path in terminal_state_paths
            ],
            terminal_runtime_execution_inventories=[
                _load_object(path) for path in terminal_execution_paths
            ],
            terminal_evidence_digests={
                "legacy_run_inventories": [_sha256_file(path) for path in terminal_run_paths],
                "legacy_workflow_states": [_sha256_file(path) for path in terminal_state_paths],
                "runtime_execution_inventories": [
                    _sha256_file(path) for path in terminal_execution_paths
                ],
            },
            scheduler_evidence_paths={
                "authority_summary": args.scheduler_authority_summary,
                "transition": args.scheduler_transition,
                "before_policy": args.scheduler_before_policy,
                "granted_policy": args.scheduler_granted_policy,
                "removed_policy": args.scheduler_removed_policy,
                "permanent_control_role": args.permanent_control_role,
                "role_viewer_before_policy": args.role_viewer_before_policy,
                "role_viewer_granted_policy": args.role_viewer_granted_policy,
                "role_viewer_removed_policy": args.role_viewer_removed_policy,
                "role_viewer_condition": args.role_viewer_condition,
                "role_viewer_grant_request": args.role_viewer_grant_request,
                "condition": args.scheduler_condition,
                "grant_request": args.scheduler_grant_request,
                "resume_attempts": args.scheduler_resume_attempts,
                "before_summary": args.scheduler_before_summary,
                "after_summary": args.scheduler_after_summary,
                "before_inventory": args.scheduler_before_inventory,
                "after_inventory": args.scheduler_after_inventory,
                "before_jobs": args.scheduler_before_job,
                "after_jobs": args.scheduler_after_job,
                "resume_receipts": args.scheduler_resume_receipt,
            },
        )
    _write(args.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
