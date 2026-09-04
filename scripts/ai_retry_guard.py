#!/usr/bin/env python3
"""Fail-closed AI retry guard with exact, evidence-bound adjudication.

The general workflow-evidence guard remains unchanged.  This AI-only adapter may
mark one attempt as non-side-effecting only after either:

* the immutable issue-121 legacy incident manifest and its exact diagnostic
  artifact validate; or
* a later hardened diagnostic artifact proves that alert delivery never began.

No wildcard, command-line bypass, or branch-wide exemption exists.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, urlopen

try:  # Support package imports and direct script execution.
    from . import collect_workflow_evidence as evidence
except ImportError:  # pragma: no cover - direct execution path
    import collect_workflow_evidence as evidence  # type: ignore

REPOSITORY_ID = 1349678672
CANONICAL_REPOSITORY_NAMES = frozenset(
    {"maglothinm/MyETF-Intelligence", "maglothinm/PolitiTrack"}
)
LEGACY_MANIFEST = Path("config/ai-retry-adjudication-33646778055.1.json")
LEGACY_MANIFEST_SHA256 = "ee9bc55516c3122bc1f1464cd6a62c919f06bc1918362b80d78a85d83a209e1f"
LEGACY_RUN_ID = 33646778055
LEGACY_RUN_ATTEMPT = 1
LEGACY_HEAD_SHA = "d603e9b40ffb78c51f635589bc886875f411299b"
LEGACY_PREDECESSOR_RUN_ID = 33638794359
LEGACY_PREDECESSOR_ATTEMPT = 1
LEGACY_PREDECESSOR_ARTIFACT_ID = 9849967781
LEGACY_PREDECESSOR_DIGEST = (
    "14ec9b28b51b830924bb4252546b0ca65fba7e30f7f1b60003dfd90c838c3193"
)
LEGACY_DIAGNOSTIC_ARTIFACT_ID = 9854021376
LEGACY_DIAGNOSTIC_DIGEST = (
    "f67d8e25ea8bf2e201a20e4006af400bf5fd418d9c970766a6c5bb3eaa8b6b73"
)
LEGACY_RESULT_DIGEST = (
    "9429fc3d29c3bfec2c9949d3c294ad9ff98c62b57f787a0bde3b9081cfb00228"
)
MAX_ARTIFACT_BYTES = 8_000_000
SHA256_RE = re.compile(r"(?:sha256:)?([0-9a-f]{64})")
JOBS_PATH_RE = re.compile(
    r"^/repos/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/actions/runs/"
    r"(?P<run_id>[1-9][0-9]*)/attempts/(?P<attempt>[1-9][0-9]*)/jobs\?per_page=100$"
)


class RetryAdjudicationError(evidence.EvidenceError):
    """The attempted exemption lacks exact durable proof."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: Any) -> str:
    match = SHA256_RE.fullmatch(str(value or "").strip())
    if not match:
        raise RetryAdjudicationError("invalid_artifact_digest")
    return match.group(1)


def _positive_int(value: Any, label: str) -> int:
    number = evidence.positive_int(value)
    if number is None:
        raise RetryAdjudicationError(f"invalid_{label}")
    return number


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RetryAdjudicationError(f"invalid_{label}")
    return value


def load_legacy_manifest(path: Path = LEGACY_MANIFEST) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if (
            path.resolve() == LEGACY_MANIFEST.resolve()
            and _sha256(raw) != LEGACY_MANIFEST_SHA256
        ):
            raise RetryAdjudicationError("legacy_adjudication_digest_mismatch")
        value = json.loads(raw)
    except RetryAdjudicationError:
        raise
    except (OSError, ValueError) as exc:
        raise RetryAdjudicationError("legacy_adjudication_unreadable") from exc
    if not isinstance(value, dict):
        raise RetryAdjudicationError("legacy_adjudication_invalid")
    if value.get("schema_version") != 1 or value.get("decision") != "safe_to_replay":
        raise RetryAdjudicationError("legacy_adjudication_not_approved")
    if value.get("issue") != 121:
        raise RetryAdjudicationError("legacy_adjudication_issue_mismatch")
    return value


def _safe_zip_member(info: zipfile.ZipInfo) -> bool:
    path = PurePosixPath(info.filename)
    mode = (info.external_attr >> 16) & 0o170000
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and mode != 0o120000
        and not info.is_dir()
    )


def _result_from_artifact(archive: bytes, result_name: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            matches = [
                info
                for info in bundle.infolist()
                if _safe_zip_member(info)
                and PurePosixPath(info.filename).name == result_name
            ]
            if len(matches) != 1:
                raise RetryAdjudicationError("diagnostic_result_ambiguous")
            if matches[0].file_size > 4_000_000:
                raise RetryAdjudicationError("diagnostic_result_too_large")
            raw = bundle.read(matches[0])
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise RetryAdjudicationError("diagnostic_artifact_invalid_zip") from exc
    try:
        result = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise RetryAdjudicationError("diagnostic_result_invalid_json") from exc
    if not isinstance(result, dict):
        raise RetryAdjudicationError("diagnostic_result_not_object")
    return result


def _download_artifact(repository: str, artifact_id: int, token: str) -> bytes:
    """Download through GitHub, dropping Authorization before the signed redirect."""

    if not token:
        raise RetryAdjudicationError("github_credentials_unavailable")
    endpoint = (
        f"https://api.github.com/repos/{repository}/actions/artifacts/"
        f"{artifact_id}/zip"
    )
    request = Request(
        endpoint,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "PolitiTrack-AI-Retry-Adjudication",
        },
    )
    opener = build_opener(evidence.NoRedirect())
    try:
        opener.open(request, timeout=25)
    except HTTPError as exc:
        if exc.code not in {301, 302, 303, 307, 308}:
            raise RetryAdjudicationError("diagnostic_artifact_download_failed") from None
        location = str(exc.headers.get("Location") or "")
    else:  # GitHub documents this endpoint as a redirect.
        raise RetryAdjudicationError("diagnostic_artifact_redirect_missing")

    parsed = urlparse(location)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise RetryAdjudicationError("diagnostic_artifact_redirect_invalid")
    try:
        with urlopen(
            Request(location, headers={"User-Agent": "PolitiTrack-AI-Retry-Adjudication"}),
            timeout=30,
        ) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_ARTIFACT_BYTES:
                raise RetryAdjudicationError("diagnostic_artifact_too_large")
            payload = response.read(MAX_ARTIFACT_BYTES + 1)
    except RetryAdjudicationError:
        raise
    except Exception:
        raise RetryAdjudicationError("diagnostic_artifact_download_failed") from None
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise RetryAdjudicationError("diagnostic_artifact_too_large")
    return payload


def _artifact_metadata(
    get: Callable[[str], Mapping[str, Any]],
    repository: str,
    artifact_id: int,
) -> Mapping[str, Any]:
    payload = get(f"/repos/{repository}/actions/artifacts/{artifact_id}")
    if not isinstance(payload, Mapping) or payload.get("id") != artifact_id:
        raise RetryAdjudicationError("artifact_identity_mismatch")
    if payload.get("expired") is True:
        raise RetryAdjudicationError("artifact_expired")
    workflow_run = _mapping(payload.get("workflow_run"), "artifact_workflow_run")
    if workflow_run.get("repository_id") != REPOSITORY_ID:
        raise RetryAdjudicationError("artifact_repository_mismatch")
    return payload


def _attempt_metadata(
    get: Callable[[str], Mapping[str, Any]],
    repository: str,
    run_id: int,
    attempt: int,
) -> Mapping[str, Any]:
    run = get(f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}")
    if (
        not isinstance(run, Mapping)
        or run.get("id") != run_id
        or run.get("run_attempt") != attempt
        or not isinstance(run.get("repository"), Mapping)
        or run["repository"].get("id") != REPOSITORY_ID
    ):
        raise RetryAdjudicationError("attempt_identity_mismatch")
    return run


def _verify_source_blobs(
    get: Callable[[str], Mapping[str, Any]],
    repository: str,
    head_sha: str,
    expected: Mapping[str, Any],
) -> None:
    commit = get(f"/repos/{repository}/git/commits/{head_sha}")
    tree_value = commit.get("tree") if isinstance(commit, Mapping) else None
    tree_sha = str(tree_value.get("sha") or "") if isinstance(tree_value, Mapping) else ""
    if not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
        raise RetryAdjudicationError("source_commit_tree_missing")
    tree = get(f"/repos/{repository}/git/trees/{tree_sha}?recursive=1")
    rows = tree.get("tree") if isinstance(tree, Mapping) else None
    if not isinstance(rows, list) or tree.get("truncated") is True:
        raise RetryAdjudicationError("source_tree_incomplete")
    found = {
        str(row.get("path")): str(row.get("sha"))
        for row in rows
        if isinstance(row, Mapping) and row.get("type") == "blob"
    }
    for path, sha in expected.items():
        if found.get(str(path)) != str(sha):
            raise RetryAdjudicationError("legacy_source_blob_mismatch")


def validate_legacy_incident(
    get: Callable[[str], Mapping[str, Any]],
    repository: str,
    run_id: int,
    attempt: int,
    producer_run: int,
    producer_attempt: int,
    artifact_loader: Callable[[str, int, str], bytes],
    token: str,
    *,
    manifest_path: Path = LEGACY_MANIFEST,
) -> None:
    manifest = load_legacy_manifest(manifest_path)
    repo = _mapping(manifest.get("repository"), "manifest_repository")
    workflow = _mapping(manifest.get("workflow"), "manifest_workflow")
    selected = _mapping(manifest.get("attempt"), "manifest_attempt")
    predecessor = _mapping(manifest.get("predecessor"), "manifest_predecessor")
    diagnostic = _mapping(manifest.get("diagnostic"), "manifest_diagnostic")
    required = _mapping(manifest.get("required_result"), "manifest_required_result")
    source_blobs = _mapping(manifest.get("source_blobs"), "manifest_source_blobs")

    if (
        repository not in CANONICAL_REPOSITORY_NAMES
        or repo.get("id") != REPOSITORY_ID
        or repo.get("full_name") != "maglothinm/MyETF-Intelligence"
        or repo.get("default_branch") != "main"
        or workflow.get("path") != ".github/workflows/ai_filing_analyst.yml"
        or workflow.get("name") != "AI filing analyst and paper portfolio"
        or workflow.get("job") != "analyze"
        or workflow.get("step") != "Analyze new filing purchases"
        or selected.get("run_id") != LEGACY_RUN_ID
        or selected.get("run_attempt") != LEGACY_RUN_ATTEMPT
        or selected.get("head_sha") != LEGACY_HEAD_SHA
        or run_id != LEGACY_RUN_ID
        or attempt != LEGACY_RUN_ATTEMPT
        or predecessor.get("producer_run_id") != LEGACY_PREDECESSOR_RUN_ID
        or predecessor.get("producer_run_attempt") != LEGACY_PREDECESSOR_ATTEMPT
        or predecessor.get("artifact_id") != LEGACY_PREDECESSOR_ARTIFACT_ID
        or _digest(predecessor.get("artifact_digest")) != LEGACY_PREDECESSOR_DIGEST
        or diagnostic.get("artifact_id") != LEGACY_DIAGNOSTIC_ARTIFACT_ID
        or _digest(diagnostic.get("artifact_digest")) != LEGACY_DIAGNOSTIC_DIGEST
        or _digest(diagnostic.get("result_file_sha256")) != LEGACY_RESULT_DIGEST
        or producer_run != LEGACY_PREDECESSOR_RUN_ID
        or producer_attempt != LEGACY_PREDECESSOR_ATTEMPT
    ):
        raise RetryAdjudicationError("legacy_adjudication_scope_mismatch")

    run = _attempt_metadata(get, repository, run_id, attempt)
    if (
        run.get("head_sha") != selected.get("head_sha")
        or run.get("head_branch") != "main"
        or run.get("name") != workflow.get("name")
        or str(run.get("path", "")).split("@", 1)[0] != workflow.get("path")
        or run.get("workflow_id") != workflow.get("workflow_id")
        or run.get("conclusion") != selected.get("conclusion")
    ):
        raise RetryAdjudicationError("legacy_attempt_metadata_mismatch")

    producer = _attempt_metadata(
        get, repository, producer_run, producer_attempt
    )
    if (
        producer.get("head_sha") != predecessor.get("head_sha")
        or producer.get("head_branch") != "main"
        or producer.get("name") != workflow.get("name")
        or str(producer.get("path", "")).split("@", 1)[0]
        != workflow.get("path")
        or producer.get("workflow_id") != workflow.get("workflow_id")
        or producer.get("conclusion") != "success"
    ):
        raise RetryAdjudicationError("legacy_predecessor_attempt_mismatch")
    producer_jobs = [
        job
        for job in evidence.jobs_for(
            get, repository, producer_run, producer_attempt
        )
        if job.get("name") == workflow.get("job")
        and job.get("conclusion") == "success"
    ]
    if len(producer_jobs) != 1:
        raise RetryAdjudicationError("legacy_predecessor_job_mismatch")

    predecessor_id = _positive_int(predecessor.get("artifact_id"), "predecessor_artifact_id")
    predecessor_metadata = _artifact_metadata(get, repository, predecessor_id)
    predecessor_run_metadata = _mapping(
        predecessor_metadata.get("workflow_run"), "predecessor_workflow_run"
    )
    if (
        predecessor_metadata.get("name") != predecessor.get("artifact_name")
        or _digest(predecessor_metadata.get("digest"))
        != _digest(predecessor.get("artifact_digest"))
        or predecessor_run_metadata.get("id") != producer_run
        or predecessor_run_metadata.get("head_sha") != predecessor.get("head_sha")
    ):
        raise RetryAdjudicationError("legacy_predecessor_mismatch")

    predecessor_archive = artifact_loader(repository, predecessor_id, token)
    if _sha256(predecessor_archive) != _digest(predecessor.get("artifact_digest")):
        raise RetryAdjudicationError("legacy_predecessor_archive_digest_mismatch")
    predecessor_state = _result_from_artifact(predecessor_archive, "state.json")
    required_state = _mapping(
        predecessor.get("required_state"), "manifest_predecessor_required_state"
    )
    if (
        predecessor_state.get("last_success_utc")
        != required_state.get("last_success_utc")
        or predecessor_state.get("candidate_alert_deliveries")
        != required_state.get("candidate_alert_deliveries")
        or predecessor_state.get("positions") != required_state.get("positions")
    ):
        raise RetryAdjudicationError("legacy_predecessor_state_mismatch")

    _verify_source_blobs(
        get, repository, str(selected.get("head_sha") or ""), source_blobs
    )

    artifact_id = _positive_int(diagnostic.get("artifact_id"), "diagnostic_artifact_id")
    metadata = _artifact_metadata(get, repository, artifact_id)
    artifact_run = _mapping(metadata.get("workflow_run"), "diagnostic_workflow_run")
    if (
        metadata.get("name") != diagnostic.get("artifact_name")
        or artifact_run.get("id") != run_id
        or artifact_run.get("head_sha") != selected.get("head_sha")
        or _digest(metadata.get("digest")) != _digest(diagnostic.get("artifact_digest"))
    ):
        raise RetryAdjudicationError("legacy_diagnostic_metadata_mismatch")

    archive = artifact_loader(repository, artifact_id, token)
    if _sha256(archive) != _digest(diagnostic.get("artifact_digest")):
        raise RetryAdjudicationError("legacy_diagnostic_archive_digest_mismatch")
    result_name = str(diagnostic.get("result_file") or "")
    result = _result_from_artifact(archive, result_name)

    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        matches = [
            info
            for info in bundle.infolist()
            if _safe_zip_member(info)
            and PurePosixPath(info.filename).name == result_name
        ]
        raw_result = bundle.read(matches[0])
    if _sha256(raw_result) != _digest(diagnostic.get("result_file_sha256")):
        raise RetryAdjudicationError("legacy_diagnostic_result_digest_mismatch")

    scalar_fields = (
        "success",
        "attempted_count",
        "completed_count",
        "high_priority_count",
        "watchlist_count",
        "weak_signal_count",
        "archive_count",
        "alerted_count",
        "paper_positions_opened",
        "paper_positions_updated",
        "paper_positions_closed",
        "market_signal_upgrades",
    )
    for field in scalar_fields:
        if result.get(field) != required.get(field):
            raise RetryAdjudicationError("legacy_diagnostic_result_mismatch")
    if result.get("errors") != required.get("errors"):
        raise RetryAdjudicationError("legacy_diagnostic_error_mismatch")
    analyses = result.get("analyses")
    if not isinstance(analyses, list) or len(analyses) != required.get("completed_count"):
        raise RetryAdjudicationError("legacy_diagnostic_analysis_count_mismatch")
    allowed = set(required.get("allowed_classifications") or [])
    if not allowed or any(
        not isinstance(row, Mapping) or row.get("classification") not in allowed
        for row in analyses
    ):
        raise RetryAdjudicationError("legacy_diagnostic_alerting_analysis")
    if len({str(row.get("trade_id") or "") for row in analyses}) != len(analyses):
        raise RetryAdjudicationError("legacy_diagnostic_duplicate_analysis")


def _future_output_artifact(
    get: Callable[[str], Mapping[str, Any]],
    repository: str,
    run_id: int,
    attempt: int,
) -> Mapping[str, Any] | None:
    payload = get(f"/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100")
    rows = payload.get("artifacts") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list) or payload.get("total_count", len(rows)) > len(rows):
        raise RetryAdjudicationError("attempt_artifact_history_incomplete")
    name = f"ai-analysis-output-{run_id}-{attempt}"
    matches = [
        row
        for row in rows
        if isinstance(row, Mapping)
        and row.get("name") == name
        and row.get("expired") is not True
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise RetryAdjudicationError("attempt_diagnostic_artifact_ambiguous")
    return matches[0]


def validate_hardened_no_delivery(
    get: Callable[[str], Mapping[str, Any]],
    repository: str,
    run_id: int,
    attempt: int,
    artifact_loader: Callable[[str, int, str], bytes],
    token: str,
) -> bool:
    run = _attempt_metadata(get, repository, run_id, attempt)
    if (
        run.get("head_branch") != "main"
        or run.get("name") != "AI filing analyst and paper portfolio"
        or str(run.get("path", "")).split("@", 1)[0]
        != ".github/workflows/ai_filing_analyst.yml"
        or run.get("conclusion") not in evidence.FAILED
    ):
        return False
    artifact = _future_output_artifact(get, repository, run_id, attempt)
    if artifact is None:
        return False
    artifact_id = _positive_int(artifact.get("id"), "diagnostic_artifact_id")
    metadata = _artifact_metadata(get, repository, artifact_id)
    artifact_run = _mapping(metadata.get("workflow_run"), "attempt_diagnostic_workflow_run")
    if (
        metadata.get("name") != artifact.get("name")
        or artifact_run.get("id") != run_id
        or artifact_run.get("head_sha") != run.get("head_sha")
    ):
        raise RetryAdjudicationError("attempt_diagnostic_metadata_mismatch")
    archive = artifact_loader(repository, artifact_id, token)
    if _sha256(archive) != _digest(metadata.get("digest")):
        raise RetryAdjudicationError("attempt_diagnostic_digest_mismatch")
    result = _result_from_artifact(archive, "ai-analysis-result.json")
    fatal_errors = result.get("fatal_errors")
    deferred = result.get("deferred_candidates")
    errors = result.get("errors")
    status = result.get("run_status")
    publishable = result.get("state_publishable")
    success = result.get("success")
    terminal_consistent = (
        status == "success"
        and publishable is True
        and success is True
        and fatal_errors == []
        and deferred == []
        and errors == []
    ) or (
        status == "degraded"
        and publishable is True
        and success is True
        and fatal_errors == []
        and isinstance(deferred, list)
        and bool(deferred)
        and errors == []
    ) or (
        status == "fatal"
        and publishable is False
        and success is False
        and isinstance(fatal_errors, list)
        and bool(fatal_errors)
        and errors == fatal_errors
    )
    return (
        result.get("result_schema_version") == 2
        and result.get("repository_id") == REPOSITORY_ID
        and str(result.get("workflow_run_id") or "") == str(run_id)
        and str(result.get("workflow_run_attempt") or "") == str(attempt)
        and result.get("source_revision") == run.get("head_sha")
        and terminal_consistent
        and result.get("delivery_phase_started") is False
        and result.get("delivery_attempt_count") == 0
        and result.get("delivery_confirmed_count") == 0
        and result.get("delivery_uncertain_count") == 0
    )


class AdjudicatingAPI:
    """Delegate GitHub evidence, altering only an exactly proven-safe AI step."""

    def __init__(
        self,
        base: Callable[[str], Mapping[str, Any]],
        *,
        repository: str,
        producer_run: int,
        producer_attempt: int,
        token: str,
        artifact_loader: Callable[[str, int, str], bytes] = _download_artifact,
        manifest_path: Path = LEGACY_MANIFEST,
    ):
        self.base = base
        self.repository = repository
        self.producer_run = producer_run
        self.producer_attempt = producer_attempt
        self.token = token
        self.artifact_loader = artifact_loader
        self.manifest_path = manifest_path
        self._safe: dict[tuple[int, int], bool] = {}

    def _is_safe(self, run_id: int, attempt: int) -> bool:
        key = (run_id, attempt)
        if key in self._safe:
            return self._safe[key]
        manifest = load_legacy_manifest(self.manifest_path)
        selected = _mapping(manifest.get("attempt"), "manifest_attempt")
        if (
            selected.get("run_id") == run_id
            and selected.get("run_attempt") == attempt
        ):
            predecessor = _mapping(
                manifest.get("predecessor"), "manifest_predecessor"
            )
            if (
                predecessor.get("producer_run_id") != self.producer_run
                or predecessor.get("producer_run_attempt")
                != self.producer_attempt
            ):
                self._safe[key] = False
                return False
            validate_legacy_incident(
                self.base,
                self.repository,
                run_id,
                attempt,
                self.producer_run,
                self.producer_attempt,
                self.artifact_loader,
                self.token,
                manifest_path=self.manifest_path,
            )
            safe = True
        else:
            safe = validate_hardened_no_delivery(
                self.base,
                self.repository,
                run_id,
                attempt,
                self.artifact_loader,
                self.token,
            )
        self._safe[key] = safe
        return safe

    def __call__(self, path: str) -> Mapping[str, Any]:
        payload = self.base(path)
        match = JOBS_PATH_RE.fullmatch(path)
        if not match or match.group("repository") != self.repository:
            return payload
        run_id = int(match.group("run_id"))
        attempt = int(match.group("attempt"))
        if not self._is_safe(run_id, attempt):
            return payload

        transformed = copy.deepcopy(payload)
        jobs = transformed.get("jobs") if isinstance(transformed, dict) else None
        if not isinstance(jobs, list):
            raise RetryAdjudicationError("adjudicated_jobs_invalid")
        matched_steps = 0
        for job in jobs:
            if not isinstance(job, dict) or job.get("name") != "analyze":
                continue
            steps = job.get("steps")
            if not isinstance(steps, list):
                continue
            for step in steps:
                if (
                    isinstance(step, dict)
                    and step.get("name") == "Analyze new filing purchases"
                ):
                    step["status"] = "completed"
                    step["conclusion"] = "skipped"
                    step["retry_adjudication"] = "safe_to_replay"
                    matched_steps += 1
        if matched_steps != 1:
            raise RetryAdjudicationError("adjudicated_step_ambiguous")
        return transformed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-run", type=int, required=True)
    parser.add_argument("--producer-attempt", type=int, required=True)
    args = parser.parse_args(argv)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    consumer = os.environ.get("GITHUB_SHA", "")
    token = os.environ.get("GH_TOKEN", "")
    try:
        base = evidence.GitHubAPI(token)
        api = AdjudicatingAPI(
            base,
            repository=repository,
            producer_run=args.producer_run,
            producer_attempt=args.producer_attempt,
            token=token,
        )
        evidence.assert_no_unretained_side_effects(
            api,
            repository,
            consumer,
            "ai",
            args.producer_run,
            args.producer_attempt,
            int(os.environ.get("GITHUB_RUN_ID", "0")),
            int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        )
    except evidence.EvidenceError as exc:
        print(
            f"Production retry blocked: {exc}. Review delivery/state continuity "
            "before retrying."
        )
        return 1
    print("No unretained side-effecting AI attempt found after exact evidence checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
