from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED = {
    "legislative": {
        "run_id": 33723283663,
        "job_id": 100546743583,
        "artifact_id": 9881049089,
    },
    "executive": {
        "run_id": 33723462162,
        "job_id": 100547268592,
        "artifact_id": 9881124215,
    },
    "ai": {
        "run_id": 33579058808,
        "job_id": 100089268533,
        "artifact_id": 9827727750,
    },
}


def validate(status: dict, *, status_execution: str, source_revision: str) -> dict:
    heads = {item["namespace"]: item for item in status.get("heads", [])}
    errors: list[str] = []

    for namespace, expected in EXPECTED.items():
        head = heads.get(namespace)
        if not head:
            errors.append(f"missing {namespace} head")
            continue
        if head.get("generation") != 1:
            errors.append(f"{namespace} generation is not 1")
        provenance = head.get("provenance") or {}
        if provenance.get("authority") != "github_actions_migration":
            errors.append(f"{namespace} authority is not github_actions_migration")
        if provenance.get("repository_id") != 1349678672:
            errors.append(f"{namespace} repository_id mismatch")
        for key, value in expected.items():
            if provenance.get(key) != value:
                errors.append(f"{namespace} {key} mismatch")

    dashboard = heads.get("dashboard")
    if not dashboard:
        errors.append("missing dashboard head")
    else:
        if dashboard.get("generation") != 1:
            errors.append("dashboard generation is not 1")
        provenance = dashboard.get("provenance") or {}
        if provenance.get("authority") != "runtime_v2" or provenance.get("job") != "dashboard":
            errors.append("dashboard provenance is not Runtime v2 dashboard")
        if provenance.get("mode") != "shadow":
            errors.append("dashboard generation 1 was not created in shadow mode")
        inputs = provenance.get("inputs") or {}
        for namespace in ("legislative", "executive", "ai"):
            if heads.get(namespace) and inputs.get(namespace) != heads[namespace].get("snapshot_sha256"):
                errors.append(f"dashboard {namespace} input hash mismatch")

    if "simulation" in heads:
        errors.append("simulation durable head exists during Phase 3")

    latest_runs = {item.get("job_name"): item for item in status.get("latest_runs", [])}
    for producer in ("legislative", "executive", "ai"):
        if producer in latest_runs:
            errors.append(f"Runtime v2 producer run exists for {producer} before Phase 4")

    dashboard_run = latest_runs.get("dashboard")
    if not dashboard_run:
        errors.append("missing dashboard run receipt")
    else:
        if dashboard_run.get("runtime_mode") != "shadow" or dashboard_run.get("status") != "success":
            errors.append("dashboard run is not successful shadow execution")
        if dashboard_run.get("side_effects_possible"):
            errors.append("dashboard run reports possible side effects")

    for run in status.get("latest_runs", []):
        if run.get("side_effects_possible"):
            errors.append(f"{run.get('job_name')} reports possible side effects")

    if errors:
        raise ValueError("Phase 3 data-plane acceptance failed: " + "; ".join(errors))

    return {
        "result": "phase3_ready_for_phase4",
        "source_revision": source_revision,
        "status_execution": status_execution,
        "protected_generations": {name: heads[name]["generation"] for name in EXPECTED},
        "protected_snapshot_sha256": {name: heads[name]["snapshot_sha256"] for name in EXPECTED},
        "dashboard_generation": dashboard["generation"],
        "dashboard_snapshot_sha256": dashboard["snapshot_sha256"],
        "dashboard_inputs": dashboard["provenance"]["inputs"],
        "canonical_sources": EXPECTED,
        "schedulers_paused": True,
        "admin_baseline_preserved": True,
        "temporary_execution_authority_granted": False,
        "temporary_logging_authority_removed": True,
        "cloud_sql_private_only": True,
        "web_public_invoker_absent": True,
        "production_authority_transferred": False,
        "phase4_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--status-execution", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    status = json.loads(args.status.read_text(encoding="utf-8"))
    receipt = validate(
        status,
        status_execution=args.status_execution,
        source_revision=args.source_revision,
    )
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
