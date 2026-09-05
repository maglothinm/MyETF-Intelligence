#!/usr/bin/env python3
"""Read-only Actions observations and the production retry side-effect guard.

This never restores, downloads, uploads, or updates protected state. Successful
Actions observations are not collector-completion/source-currency evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPOSITORY_ID = 1349678672
SPECS = {
    "legislative": {"file": "legislative_trade_tracker_v2.yml", "name": "Legislative purchase tracker v2",
                    "job": "track", "step": "Track House and Senate purchases"},
    "executive": {"file": "executive_trade_tracker.yml", "name": "Executive purchase tracker",
                  "job": "track", "step": "Track executive-branch purchases"},
    "ai": {"file": "ai_filing_analyst.yml", "name": "AI filing analyst and paper portfolio",
           "job": "analyze", "step": "Analyze new filing purchases"},
}
FAILED = {"failure", "timed_out", "startup_failure", "action_required"}
CONCLUSIONS = FAILED | {"success", "cancelled", "skipped", "neutral", "stale"}
EVENTS = {"schedule", "workflow_dispatch", "workflow_run"}
PENDING = {"queued", "in_progress", "waiting", "pending", "requested"}
PINNED_RECOVERY_PRODUCERS = {
    "legislative": {
        "run_id": 33966378019,
        "run_attempt": 1,
        "head_sha": "23cc3b83cf468ed65d228b5208d30eff8798f5ff",
        "workflow_id": 345003824,
        "event": "push",
    },
}


class EvidenceError(RuntimeError):
    """A deliberately sanitized error; API bodies and credentials never escape."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def utc(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(str(value))
        return number if number > 0 else None
    except (ValueError, TypeError):
        return None


class GitHubAPI:
    def __init__(self, token: str):
        if not token:
            raise EvidenceError("github_credentials_unavailable")
        self.token = token
        self.opener = build_opener(NoRedirect())
        self.cache: dict[str, Mapping[str, Any]] = {}

    def __call__(self, path: str) -> Mapping[str, Any]:
        # Paths are constructed from allowlisted workflow names and validated metadata.
        if not path.startswith("/repos/") or "\n" in path or "\r" in path:
            raise EvidenceError("invalid_github_path")
        if path in self.cache:
            return self.cache[path]
        request = Request("https://api.github.com" + path, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "PolitiTrack-Workflow-Evidence",
        })
        try:
            with self.opener.open(request, timeout=25) as response:
                payload = json.loads(response.read(8_000_001))
            if not isinstance(payload, dict):
                raise ValueError("expected object")
            self.cache[path] = payload
            return payload
        except Exception:
            raise EvidenceError("github_evidence_unavailable") from None


def repository_context(get: Callable, repository: str) -> tuple[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise EvidenceError("invalid_repository")
    repo = get("/repos/" + repository)
    if repo.get("id") != REPOSITORY_ID or repo.get("archived") or repo.get("disabled"):
        raise EvidenceError("canonical_repository_mismatch")
    name, branch = repo.get("full_name"), repo.get("default_branch")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", name):
        raise EvidenceError("invalid_repository")
    if not isinstance(branch, str) or not branch or len(branch) > 255:
        raise EvidenceError("invalid_default_branch")
    return name, branch


def matches_run_identity(run: Mapping, spec: Mapping, branch: str) -> bool:
    return (isinstance(run, Mapping) and isinstance(run.get("repository"), Mapping)
            and run["repository"].get("id") == REPOSITORY_ID
            and run.get("head_branch") == branch
            and run.get("name") == spec["name"]
            and str(run.get("path", "")).split("@", 1)[0] == ".github/workflows/" + spec["file"]
            and bool(re.fullmatch(r"[0-9a-f]{40}", str(run.get("head_sha", "")))))


def matches_run(run: Mapping, spec: Mapping, branch: str) -> bool:
    return matches_run_identity(run, spec, branch) and run.get("event") in EVENTS


def matches_restored_producer(run: Mapping, spec: Mapping, default: str, branch: str) -> bool:
    if matches_run(run, spec, default):
        return True
    pinned = PINNED_RECOVERY_PRODUCERS.get(branch)
    return (pinned is not None and matches_run_identity(run, spec, default)
            and run.get("id") == pinned["run_id"]
            and run.get("run_attempt") == pinned["run_attempt"]
            and run.get("head_sha") == pinned["head_sha"]
            and run.get("workflow_id") == pinned["workflow_id"]
            and run.get("event") == pinned["event"])


def validate_ancestry(get: Callable, repository: str, head: str, consumer: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", consumer):
        raise EvidenceError("invalid_consumer_commit")
    if head != consumer and get(f"/repos/{repository}/compare/{head}...{consumer}").get("status") not in {"ahead", "identical"}:
        raise EvidenceError("producer_not_ancestor")


def jobs_for(get: Callable, repository: str, run_id: int, attempt: int) -> list[dict]:
    payload = get(f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    jobs = payload.get("jobs")
    if (not isinstance(jobs, list) or any(not isinstance(job, dict) for job in jobs)
            or payload.get("total_count", len(jobs)) > len(jobs)):
        raise EvidenceError("incomplete_job_evidence")
    return jobs


def run_summaries(get: Callable, repository: str, default: str, spec: Mapping) -> list[Mapping]:
    # Run IDs are creation order, not attempt order: an old run can be rerun today.
    # Inspect every summary, with an explicit fail-closed bound, before selecting.
    summaries = []
    for page in range(1, 101):
        query = urlencode({"branch": default, "per_page": 100, "page": page})
        payload = get(f"/repos/{repository}/actions/workflows/{spec['file']}/runs?{query}")
        rows = payload.get("workflow_runs")
        if not isinstance(rows, list):
            raise EvidenceError("incomplete_attempt_history")
        summaries.extend(row for row in rows if matches_run(row, spec, default))
        if len(rows) < 100:
            return summaries
    raise EvidenceError("attempt_history_limit_exceeded")


def observation(run: Mapping, jobs: list[dict], branch: str, repository: str) -> dict:
    spec = SPECS[branch]
    selected = [job for job in jobs if job.get("name") == spec["job"]]
    if len(selected) > 1:
        raise EvidenceError("ambiguous_authoritative_job")
    job = selected[0] if selected else {}
    conclusion = job.get("conclusion")
    conclusion = conclusion if conclusion in CONCLUSIONS else None
    pending = job.get("status") if job.get("status") in PENDING else run.get("status")
    if conclusion is None and pending in PENDING:
        conclusion = "queued" if pending == "requested" else pending
    # Optional continue-on-error Healthchecks/diagnostics do not fail collection.
    # Failure of the authoritative job is the qualifying operational error.
    errors = (max(1, sum(step.get("conclusion") in FAILED for step in job.get("steps", [])))
              if conclusion in FAILED else 0)
    return {
        "run_key": f"{run['id']}:{run['run_attempt']}", "branch": branch,
        "run_attempt": run["run_attempt"], "evidence_source": "github_actions",
        "workflow_created_utc": utc(run.get("created_at")),
        "workflow_started_utc": (utc(run.get("run_started_at"))
                                 if conclusion not in {"queued", "waiting", "pending"} else None),
        "started_utc": None,  # Workflow/job start is not the Python collector start.
        "finished_utc": utc(job.get("completed_at")),
        "producer_job_started_utc": utc(job.get("started_at")),
        "producer_job_conclusion": conclusion, "conclusion": conclusion,
        "success": True if conclusion == "success" else (False if conclusion in FAILED else None),
        "error_count": errors, "event_name": run["event"], "trigger_source": run["event"],
        "run_url": f"https://github.com/{repository}/actions/runs/{run['id']}/attempts/{run['run_attempt']}",
    }


def collect(get: Callable, repository: str, consumer: str, observed_at: str) -> dict:
    result = {"schema_version": 1, "observed_at_utc": utc(observed_at), "available": False,
              "branches": {name: {"available": False, "attempts": []} for name in SPECS}}
    try:
        repository, default = repository_context(get, repository)
    except EvidenceError:
        return result
    for branch, spec in SPECS.items():
        try:
            summaries = run_summaries(get, repository, default, spec)
            # Five recent attempts plus the newest failure and success suffice for
            # latest-conclusion overlay; the protected JSONL owns the full timeline.
            summaries.sort(key=lambda row: max(utc(row.get("run_started_at")) or "", utc(row.get("updated_at")) or ""), reverse=True)
            runs = summaries[:5]
            for conclusions in (FAILED, {"success"}):
                extra = next((row for row in summaries if row.get("conclusion") in conclusions), None)
                if extra is not None and extra not in runs:
                    runs.append(extra)
            attempts = []
            for summary in runs:
                if not matches_run(summary, spec, default):
                    continue
                run_id, attempt = positive_int(summary.get("id")), positive_int(summary.get("run_attempt"))
                if not run_id or not attempt or attempt > 50:
                    raise EvidenceError("invalid_attempt_evidence")
                # A pending rerun must not hide its previously failed attempt.
                # Walk backwards until an actual success/failure job is observed.
                for exact_attempt in range(attempt, 0, -1):
                    run = get(f"/repos/{repository}/actions/runs/{run_id}/attempts/{exact_attempt}")
                    if (not matches_run(run, spec, default) or run.get("run_attempt") != exact_attempt
                            or run.get("id") != run_id):
                        raise EvidenceError("attempt_identity_mismatch")
                    validate_ancestry(get, repository, run["head_sha"], consumer)
                    item = observation(run, jobs_for(get, repository, run_id, exact_attempt), branch, repository)
                    attempts.append(item)
                    if item["conclusion"] in FAILED | {"success"}:
                        break
            attempts.sort(key=lambda row: (row.get("producer_job_started_utc")
                                          or row.get("workflow_started_utc")
                                          or row.get("workflow_created_utc") or ""), reverse=True)
            result["branches"][branch] = {"available": True, "attempts": attempts}
        except (EvidenceError, KeyError, TypeError, ValueError):
            # Fail to unavailable, not to a fabricated successful or failed run.
            continue
    result["available"] = all(value["available"] for value in result["branches"].values())
    return result


def assert_no_unretained_side_effects(get: Callable, repository: str, consumer: str, branch: str,
                                    producer_run: int, producer_attempt: int,
                                    current_run: int, current_attempt: int) -> None:
    """Stop a duplicate/retry from resending after an unretained attempt.

    A failed step may already have delivered an alert. The last good artifact
    cannot establish delivery deduplication for that attempt. Only skipped or
    demonstrably unstarted collector/analyst steps are safe to retry normally.
    """
    repository, default = repository_context(get, repository)
    spec = SPECS[branch]
    producer = get(f"/repos/{repository}/actions/runs/{producer_run}/attempts/{producer_attempt}")
    if (not matches_restored_producer(producer, spec, default, branch) or producer.get("id") != producer_run
            or producer.get("run_attempt") != producer_attempt or producer.get("conclusion") != "success"):
        raise EvidenceError("invalid_restored_producer")
    validate_ancestry(get, repository, producer["head_sha"], consumer)
    producer_jobs = [job for job in jobs_for(get, repository, producer_run, producer_attempt)
                     if job.get("name") == spec["job"] and job.get("conclusion") == "success"]
    if len(producer_jobs) != 1:
        raise EvidenceError("invalid_restored_producer_job")
    # Queue/start timestamps do not establish execution order. The successful
    # producing job completion is the safe boundary for subsequent side effects.
    boundary = utc(producer_jobs[0].get("completed_at"))
    if not boundary:
        raise EvidenceError("missing_producer_time")
    for page in range(1, 101):
        query = urlencode({"branch": default, "per_page": 100, "page": page})
        payload = get(f"/repos/{repository}/actions/workflows/{spec['file']}/runs?{query}")
        runs = payload.get("workflow_runs")
        if not isinstance(runs, list):
            raise EvidenceError("incomplete_attempt_history")
        for summary in runs:
            # Read the complete run listing: a rerun can have an older run ID.
            if not matches_run_identity(summary, spec, default):
                continue
            updated = utc(summary.get("updated_at"))
            if updated and updated < boundary:
                continue
            run_id, count = positive_int(summary.get("id")), positive_int(summary.get("run_attempt"))
            if not run_id or not count or count > 100:
                raise EvidenceError("ambiguous_attempt_history")
            for attempt in range(1, count + 1):
                if (run_id, attempt) in {(producer_run, producer_attempt), (current_run, current_attempt)}:
                    continue
                run = get(f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}")
                if (not matches_run_identity(run, spec, default) or run.get("id") != run_id
                        or run.get("run_attempt") != attempt):
                    raise EvidenceError("attempt_identity_mismatch")
                jobs = jobs_for(get, repository, run_id, attempt)
                matching = [job for job in jobs if job.get("name") == spec["job"]]
                if not matching and run.get("status") in {"queued", "waiting", "requested", "pending"}:
                    continue
                if not matching and run.get("conclusion") == "skipped":
                    continue
                if len(matching) != 1:
                    raise EvidenceError("ambiguous_authoritative_job")
                job = matching[0]
                if job.get("status") in {"queued", "pending", "waiting", "requested"} and not job.get("started_at"):
                    continue
                finished = utc(job.get("completed_at"))
                if finished and finished < boundary:
                    continue
                if job.get("conclusion") == "skipped":
                    continue
                steps = [step for step in job.get("steps", []) if step.get("name") == spec["step"]]
                if len(steps) == 1 and (steps[0].get("conclusion") == "skipped"
                                       or (steps[0].get("status") in {"queued", "pending"}
                                           and not steps[0].get("started_at"))):
                    continue
                validate_ancestry(get, repository, run["head_sha"], consumer)
                raise EvidenceError(f"unretained_side_effects_possible_run_{run_id}_attempt_{attempt}")
        if len(runs) < 100:
            return
    raise EvidenceError("attempt_history_limit_exceeded")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--guard-branch", choices=SPECS)
    parser.add_argument("--producer-run", type=int)
    parser.add_argument("--producer-attempt", type=int)
    args = parser.parse_args()
    repository, consumer = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_SHA", "")
    try:
        api = GitHubAPI(os.environ.get("GH_TOKEN", ""))
        if args.guard_branch:
            if not args.producer_run or not args.producer_attempt:
                raise EvidenceError("missing_restored_producer")
            assert_no_unretained_side_effects(api, repository, consumer, args.guard_branch,
                                             args.producer_run, args.producer_attempt,
                                             int(os.environ.get("GITHUB_RUN_ID", "0")),
                                             int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")))
            print("No unretained side-effecting producer attempt found.")
            return 0
        if not args.output:
            parser.error("--output is required for an observation")
        result = collect(api, repository, consumer, datetime.now(timezone.utc).isoformat())
    except EvidenceError as exc:
        if args.guard_branch:
            print(f"Production retry blocked: {exc}. Review delivery/state continuity before retrying.")
            return 1
        result = {"schema_version": 1, "available": False,
                  "observed_at_utc": datetime.now(timezone.utc).isoformat(), "branches": {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Actions evidence collected." if result["available"] else "Actions evidence incomplete or unavailable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
