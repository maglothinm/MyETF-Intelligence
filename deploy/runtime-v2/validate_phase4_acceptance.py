"""Validate controlled Runtime v2 shadow acceptance before Phase 5."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


NAMESPACES = ("legislative", "executive", "ai", "dashboard")
CYCLE_ORDER = ["legislative", "executive", "ai", "dashboard"]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _heads(probe: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["namespace"]: item
        for item in probe.get("status", {}).get("heads", [])
        if isinstance(item, dict) and item.get("namespace")
    }


def _run_ids(probe: dict[str, Any]) -> set[str]:
    return {
        str(item.get("run_id"))
        for item in probe.get("run_history", [])
        if item.get("run_id")
    }


def _new_runs(
    before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    existing = _run_ids(before)
    return [
        item
        for item in after.get("run_history", [])
        if item.get("run_id") and str(item["run_id"]) not in existing
    ]


def _time(value: str | None) -> datetime:
    if not value:
        raise ValueError("run timestamp is missing")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _assert_heads_equal(
    first: dict[str, dict[str, Any]], second: dict[str, dict[str, Any]], label: str
) -> None:
    for namespace in NAMESPACES:
        if namespace not in first or namespace not in second:
            raise ValueError(f"{label}: missing {namespace} head")
        for key in ("generation", "snapshot_sha256"):
            if first[namespace].get(key) != second[namespace].get(key):
                raise ValueError(f"{label}: {namespace} {key} changed unexpectedly")


def _assert_generations(
    heads: dict[str, dict[str, Any]], generation: int, label: str
) -> None:
    for namespace in NAMESPACES:
        head = heads.get(namespace)
        if not head or head.get("generation") != generation:
            raise ValueError(f"{label}: {namespace} is not generation {generation}")
        digest = str(head.get("snapshot_sha256") or "")
        if len(digest) != 64:
            raise ValueError(f"{label}: {namespace} has no valid snapshot digest")


def _assert_shadow_cycle(runs: list[dict[str, Any]], label: str) -> None:
    ordered = sorted(runs, key=lambda item: (_time(item.get("started_at")), item["run_id"]))
    names = [item.get("job_name") for item in ordered]
    if names != CYCLE_ORDER:
        raise ValueError(f"{label}: producer order was {names}, expected {CYCLE_ORDER}")
    for item in ordered:
        if item.get("status") != "success":
            raise ValueError(f"{label}: {item.get('job_name')} did not succeed")
        if item.get("runtime_mode") != "shadow" or item.get("trigger_source") != "shadow":
            raise ValueError(f"{label}: {item.get('job_name')} was not a shadow run")
        if item.get("side_effects_possible"):
            raise ValueError(f"{label}: {item.get('job_name')} reports possible side effects")
        if not item.get("snapshot_sha256"):
            raise ValueError(f"{label}: {item.get('job_name')} has no committed snapshot")
    for previous, current in zip(ordered, ordered[1:]):
        if _time(previous.get("finished_at")) > _time(current.get("started_at")):
            raise ValueError(
                f"{label}: {previous.get('job_name')} overlapped {current.get('job_name')}"
            )


def _assert_dashboard_inputs(heads: dict[str, dict[str, Any]], label: str) -> None:
    dashboard = heads["dashboard"]
    provenance = dashboard.get("provenance") or {}
    if (
        provenance.get("authority") != "runtime_v2"
        or provenance.get("job") != "dashboard"
        or provenance.get("mode") != "shadow"
        or provenance.get("trigger_source") != "shadow"
    ):
        raise ValueError(f"{label}: dashboard provenance is not a shadow Runtime v2 run")
    inputs = provenance.get("inputs") or {}
    for namespace in ("legislative", "executive", "ai"):
        if inputs.get(namespace) != heads[namespace].get("snapshot_sha256"):
            raise ValueError(f"{label}: dashboard {namespace} input hash mismatch")


def _assert_snapshot_chains(final_probe: dict[str, Any]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in NAMESPACES}
    for item in final_probe.get("snapshot_history", []):
        namespace = item.get("namespace")
        if namespace in grouped:
            grouped[namespace].append(item)
    for namespace, items in grouped.items():
        items.sort(key=lambda item: item.get("generation", 0))
        generations = [item.get("generation") for item in items]
        if generations != [1, 2, 3]:
            raise ValueError(f"{namespace} snapshot generations are {generations}, expected [1, 2, 3]")
        if items[0].get("parent_sha256") not in (None, ""):
            raise ValueError(f"{namespace} generation 1 unexpectedly has a parent")
        if items[1].get("parent_sha256") != items[0].get("snapshot_sha256"):
            raise ValueError(f"{namespace} generation 2 parent mismatch")
        if items[2].get("parent_sha256") != items[1].get("snapshot_sha256"):
            raise ValueError(f"{namespace} generation 3 parent mismatch")


def _assert_consistency(
    baseline: dict[str, Any], final: dict[str, Any], final_heads: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if baseline.get("ok") is not True or final.get("ok") is not True:
        raise ValueError("snapshot consistency probe did not succeed")
    baseline_namespaces = baseline.get("namespaces") or {}
    final_namespaces = final.get("namespaces") or {}
    retained: dict[str, Any] = {}
    for namespace in NAMESPACES:
        before = baseline_namespaces.get(namespace) or {}
        after = final_namespaces.get(namespace) or {}
        if before.get("parse_errors") or after.get("parse_errors"):
            raise ValueError(f"{namespace} snapshot contains parse errors")
        if int(before.get("file_count") or 0) < 1 or int(after.get("file_count") or 0) < 1:
            raise ValueError(f"{namespace} snapshot inventory is empty")
        before_paths = {item.get("path") for item in before.get("files", [])}
        after_paths = {item.get("path") for item in after.get("files", [])}
        if not before_paths.issubset(after_paths):
            raise ValueError(f"{namespace} dropped retained files")
        if namespace != "dashboard":
            before_ids = set(before.get("identifier_hashes") or [])
            after_ids = set(after.get("identifier_hashes") or [])
            if not before_ids.issubset(after_ids):
                raise ValueError(f"{namespace} dropped retained identifiers")
            for path, count in (before.get("history_counts") or {}).items():
                final_count = (after.get("history_counts") or {}).get(path)
                if final_count is None or int(final_count) < int(count):
                    raise ValueError(f"{namespace} history regressed for {path}")
            if not before.get("last_success_utc") or not after.get("last_success_utc"):
                raise ValueError(f"{namespace} successful-state marker is missing")
            if _time(after["last_success_utc"]) < _time(before["last_success_utc"]):
                raise ValueError(f"{namespace} successful-state marker regressed")
        else:
            if not all((after.get("required_files") or {}).values()):
                raise ValueError("final dashboard snapshot lacks required files")
        head = after.get("head") or {}
        if (
            head.get("generation") != 3
            or head.get("snapshot_sha256") != final_heads[namespace].get("snapshot_sha256")
        ):
            raise ValueError(f"{namespace} consistency receipt does not match final head")
        retained[namespace] = {
            "baseline_file_count": before.get("file_count"),
            "final_file_count": after.get("file_count"),
            "baseline_identifier_count": len(before.get("identifier_hashes") or []),
            "final_identifier_count": len(after.get("identifier_hashes") or []),
            "history_counts": after.get("history_counts") or {},
        }
    return retained


def validate(
    *,
    baseline: dict[str, Any],
    lock: dict[str, Any],
    after_failure: dict[str, Any],
    after_cycle1: dict[str, Any],
    final: dict[str, Any],
    baseline_consistency: dict[str, Any],
    final_consistency: dict[str, Any],
    executions: dict[str, Any],
    browser: dict[str, Any],
    source_revision: str,
    phase3_tag_sha: str,
) -> dict[str, Any]:
    for name, probe in (
        ("baseline", baseline),
        ("after_failure", after_failure),
        ("after_cycle1", after_cycle1),
        ("final", final),
    ):
        if probe.get("ok") is not True or probe.get("phase") != "phase4":
            raise ValueError(f"{name} private status probe is not valid")
        if probe.get("private_ip_env") != "true" or probe.get("database_private_ip_selected") is not True:
            raise ValueError(f"{name} did not use private Cloud SQL routing")

    baseline_heads = _heads(baseline)
    failure_heads = _heads(after_failure)
    cycle1_heads = _heads(after_cycle1)
    final_heads = _heads(final)
    _assert_generations(baseline_heads, 1, "baseline")
    _assert_heads_equal(baseline_heads, failure_heads, "controlled failure")

    failure_runs = _new_runs(baseline, after_failure)
    if len(failure_runs) != 1:
        raise ValueError(f"controlled failure created {len(failure_runs)} run rows")
    failure = failure_runs[0]
    if (
        failure.get("job_name") != "legislative"
        or failure.get("status") != "failure"
        or failure.get("runtime_mode") != "shadow"
        or failure.get("trigger_source") != "shadow"
        or failure.get("side_effects_possible")
        or failure.get("snapshot_sha256")
        or not failure.get("error_code")
    ):
        raise ValueError("controlled legislative failure was not safely classified")

    cycle1_runs = _new_runs(after_failure, after_cycle1)
    _assert_shadow_cycle(cycle1_runs, "cycle 1")
    _assert_generations(cycle1_heads, 2, "cycle 1")
    _assert_dashboard_inputs(cycle1_heads, "cycle 1")

    cycle2_runs = _new_runs(after_cycle1, final)
    _assert_shadow_cycle(cycle2_runs, "cycle 2")
    _assert_generations(final_heads, 3, "cycle 2")
    _assert_dashboard_inputs(final_heads, "cycle 2")
    _assert_snapshot_chains(final)

    phase4_runs = _new_runs(baseline, final)
    if len(phase4_runs) != 9:
        raise ValueError(f"Phase 4 created {len(phase4_runs)} run rows, expected 9")
    if any(item.get("runtime_mode") != "shadow" for item in phase4_runs):
        raise ValueError("a Phase 4 run was not in shadow mode")
    if any(item.get("side_effects_possible") for item in phase4_runs):
        raise ValueError("a Phase 4 run reports possible external side effects")

    if (
        lock.get("ok") is not True
        or lock.get("first_lock_acquired") is not True
        or lock.get("second_lock_refused") is not True
        or lock.get("state_advanced") is not False
    ):
        raise ValueError("advisory-lock exclusion was not proven")
    lock_before = lock.get("head_before") or {}
    lock_after = lock.get("head_after") or {}
    if (
        lock_before.get("generation") != 1
        or lock_before.get("snapshot_sha256") != baseline_heads["legislative"].get("snapshot_sha256")
        or lock_after.get("snapshot_sha256") != lock_before.get("snapshot_sha256")
    ):
        raise ValueError("lock probe did not preserve the Phase 3 legislative head")

    expected_executions = [
        ("controlled_failure", "legislative", "failure"),
        *[("cycle1", name, "success") for name in CYCLE_ORDER],
        *[("cycle2", name, "success") for name in CYCLE_ORDER],
    ]
    actual_executions = [
        (item.get("stage"), item.get("job"), item.get("expected_conclusion"))
        for item in executions.get("executions", [])
    ]
    if actual_executions != expected_executions:
        raise ValueError("Cloud Run execution manifest does not match the authorized sequence")
    execution_names = [item.get("execution") for item in executions.get("executions", [])]
    if any(not name for name in execution_names) or len(set(execution_names)) != len(execution_names):
        raise ValueError("Cloud Run execution manifest contains missing or duplicate executions")

    retained = _assert_consistency(
        baseline_consistency, final_consistency, final_heads
    )

    if browser.get("result") != "phase4_private_dashboard_browser_accepted":
        raise ValueError("private dashboard browser acceptance did not succeed")
    if browser.get("expected_snapshot_sha256") != final_heads["dashboard"].get("snapshot_sha256"):
        raise ValueError("browser acceptance used the wrong dashboard snapshot")
    if browser.get("console_errors") or browser.get("page_errors") or browser.get("failed_responses"):
        raise ValueError("browser acceptance reported client-side errors")
    route_names = [item.get("route") for item in browser.get("routes", [])]
    if route_names != ["/", "/filing-vault.html"]:
        raise ValueError("browser acceptance did not cover the required routes")
    if any(item.get("status") != 200 for item in browser.get("routes", [])):
        raise ValueError("a browser route did not return HTTP 200")
    if browser.get("summary_status") != 200:
        raise ValueError("dashboard summary JSON was unavailable")

    return {
        "schema_version": 1,
        "result": "phase4_ready_for_phase5",
        "source_revision": source_revision,
        "phase3_tag_sha": phase3_tag_sha,
        "controlled_shadow_cycles": 2,
        "controlled_failure": {
            "job": "legislative",
            "run_id": failure["run_id"],
            "error_code": failure["error_code"],
            "head_advanced": False,
            "side_effects_possible": False,
        },
        "advisory_lock_exclusion": True,
        "final_generations": {
            namespace: final_heads[namespace]["generation"] for namespace in NAMESPACES
        },
        "final_snapshot_sha256": {
            namespace: final_heads[namespace]["snapshot_sha256"] for namespace in NAMESPACES
        },
        "retained_state_consistency": retained,
        "private_dashboard_browser_accepted": True,
        "runtime_mode": "shadow",
        "external_delivery_suppressed": True,
        "healthchecks_suppressed": True,
        "protected_github_artifact_operation": False,
        "github_pages_publication": False,
        "schedulers_paused": True,
        "cloud_sql_private_only": True,
        "web_public_invoker_absent": True,
        "temporary_execution_authority_removed": True,
        "temporary_probe_storage_authority_removed": True,
        "temporary_web_invoker_removed": True,
        "production_authority_transferred": False,
        "phase5_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--after-failure", type=Path, required=True)
    parser.add_argument("--after-cycle1", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--baseline-consistency", type=Path, required=True)
    parser.add_argument("--final-consistency", type=Path, required=True)
    parser.add_argument("--executions", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--phase3-tag-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    receipt = validate(
        baseline=_load(args.baseline),
        lock=_load(args.lock),
        after_failure=_load(args.after_failure),
        after_cycle1=_load(args.after_cycle1),
        final=_load(args.final),
        baseline_consistency=_load(args.baseline_consistency),
        final_consistency=_load(args.final_consistency),
        executions=_load(args.executions),
        browser=_load(args.browser),
        source_revision=args.source_revision,
        phase3_tag_sha=args.phase3_tag_sha,
    )
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
