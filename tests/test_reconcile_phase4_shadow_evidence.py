from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "deploy"
    / "runtime-v2"
    / "reconcile_phase4_shadow_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("reconcile_phase4_shadow_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
reconcile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reconcile)

SOURCE = "8908f067298078f8c013e90cf6b7ad8ad420285b"
IMAGE = "us-central1-docker.pkg.dev/example/runtime@sha256:" + "b" * 64
BASE_GENS = {"legislative": 2, "executive": 2, "ai": 3, "dashboard": 2}


def digest(name: str, generation: int) -> str:
    return hashlib.sha256(f"{name}:{generation}".encode()).hexdigest()


def baseline_status() -> dict:
    return {
        "heads": [
            {
                "namespace": name,
                "generation": BASE_GENS[name],
                "snapshot_id": f"legacy-{name}-{BASE_GENS[name]}",
                "snapshot_sha256": digest(name, BASE_GENS[name]),
                "parent_sha256": digest(name, BASE_GENS[name] - 1),
                "source_revision": "legacy",
                "provenance": {"authority": "legacy"},
            }
            for name in reconcile.NAMESPACES
        ],
        "latest_runs": [],
    }


def inventory() -> dict:
    return {
        "repository_id": reconcile.REPOSITORY_ID,
        "classification": "legacy_unverified",
        "observed_baseline_heads": {
            name: {
                "generation": BASE_GENS[name],
                "snapshot_sha256": digest(name, BASE_GENS[name]),
            }
            for name in reconcile.NAMESPACES
        },
    }


def guards() -> tuple[dict, dict]:
    preflight = {
        "canonical_repository_verified": True,
        "canonical_main_verified": True,
        "project_boundary_verified": True,
        "image_digest_verified": True,
        "cloud_sql_private_only": True,
        "producer_schedulers_paused": True,
        "web_public_invoker_absent": True,
        "persistent_job_configuration_verified": True,
        "legacy_production_route_active": True,
    }
    cleanup = {
        "temporary_execution_authority_removed": True,
        "temporary_logging_authority_removed": True,
        "temporary_service_account_user_removed": True,
        "cloud_sql_private_only": True,
        "producer_schedulers_paused": True,
        "web_public_invoker_absent": True,
        "legacy_production_route_active": True,
    }
    return preflight, cleanup


def build_observations(
    start: dict,
    *,
    label: str,
    failures: set[int] | None = None,
    clock: datetime,
) -> tuple[list[dict], dict, datetime]:
    failures = failures or set()
    heads = {item["namespace"]: copy.deepcopy(item) for item in start["heads"]}
    latest = {item["job_name"]: copy.deepcopy(item) for item in start.get("latest_runs", [])}
    observations = []
    sequence = 0
    for cycle in (1, 2):
        for job in reconcile.CYCLE_ORDER:
            sequence += 1
            started = clock
            finished = started + timedelta(seconds=20)
            clock = finished + timedelta(seconds=1)
            run_id = f"{label}-run-{sequence}"
            execution = f"polititrack-{job}-{label}-{sequence}"
            if sequence in failures:
                run = {
                    "run_id": run_id,
                    "job_name": job,
                    "status": "failure",
                    "error_code": "CalledProcessError",
                    "runtime_mode": "shadow",
                    "runtime_mode_verified": True,
                    "runtime_mode_evidence": {"kind": "runner_explicit", "mode": "shadow"},
                    "trigger_source": "shadow",
                    "side_effects_possible": False,
                    "source_revision": SOURCE,
                    "parent_sha256": None,
                    "snapshot_created_at": None,
                    "snapshot_generation": None,
                    "snapshot_id": None,
                    "snapshot_sha256": None,
                    "started_at": started.isoformat().replace("+00:00", "Z"),
                    "finished_at": finished.isoformat().replace("+00:00", "Z"),
                }
            else:
                old = heads[job]
                generation = old["generation"] + 1
                provenance = {
                    "authority": "runtime_v2",
                    "job": job,
                    "mode": "shadow",
                    "trigger_source": "shadow",
                }
                if job == "ai":
                    provenance["inputs"] = {
                        name: {
                            "generation": heads[name]["generation"],
                            "snapshot_sha256": heads[name]["snapshot_sha256"],
                        }
                        for name in ("legislative", "executive")
                    }
                elif job == "dashboard":
                    provenance["inputs"] = {
                        name: heads[name]["snapshot_sha256"]
                        for name in ("legislative", "executive", "ai")
                    }
                heads[job] = {
                    "namespace": job,
                    "generation": generation,
                    "snapshot_id": f"{label}-{job}-{generation}",
                    "snapshot_sha256": digest(job, generation),
                    "parent_sha256": old["snapshot_sha256"],
                    "source_revision": SOURCE,
                    "provenance": provenance,
                }
                run = {
                    "run_id": run_id,
                    "job_name": job,
                    "status": "success",
                    "runtime_mode": "shadow",
                    "runtime_mode_verified": True,
                    "runtime_mode_evidence": {"kind": "snapshot_provenance", "mode": "shadow"},
                    "trigger_source": "shadow",
                    "side_effects_possible": False,
                    "source_revision": SOURCE,
                    "snapshot_generation": generation,
                    "snapshot_id": heads[job]["snapshot_id"],
                    "snapshot_sha256": heads[job]["snapshot_sha256"],
                    "started_at": started.isoformat().replace("+00:00", "Z"),
                    "finished_at": finished.isoformat().replace("+00:00", "Z"),
                }
            latest[job] = run
            status = {
                "heads": [copy.deepcopy(heads[name]) for name in reconcile.NAMESPACES],
                "latest_runs": [copy.deepcopy(latest[name]) for name in sorted(latest)],
            }
            observations.append(
                {
                    "cycle": cycle,
                    "sequence": sequence,
                    "job": job,
                    "cloud_run_execution": execution,
                    "status": status,
                }
            )
    return observations, observations[-1]["status"], clock


def manifest(observations: list[dict]) -> dict:
    preflight, cleanup = guards()
    return {
        "schema_version": 1,
        "phase": "phase4",
        "preflight": preflight,
        "executions": observations,
        "cleanup": cleanup,
    }


def write_archive(path: Path, baseline: dict, observations: list[dict]) -> None:
    evidence_manifest = manifest(observations)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("baseline.json", json.dumps(baseline))
        bundle.writestr("manifest.json", json.dumps(evidence_manifest))
        bundle.writestr(
            "observations.ndjson",
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in observations),
        )
        bundle.writestr("cleanup.json", '{"result":"phase4_cleanup_started"}\n')


def current_manifest() -> dict:
    preflight, cleanup = guards()
    preflight.update(
        {
            "current_status_captured": True,
            "runtime_shadow_mode_verified": True,
            "evidence_control_files_verified": True,
            "legacy_route_source_verified": True,
        }
    )
    cleanup.update(
        {
            "runtime_shadow_mode_verified": True,
            "no_producer_execution_performed": True,
        }
    )
    return {
        "schema_version": 1,
        "phase": "phase4_reconciliation",
        "preflight": preflight,
        "cleanup": cleanup,
    }


def source_metadata(pin: dict) -> tuple[dict, dict, dict]:
    run = {
        "id": pin["run_id"],
        "run_number": pin["run_number"],
        "run_attempt": pin["run_attempt"],
        "workflow_id": 350129720,
        "name": "Phase 4 live shadow validation v6",
        "path": ".github/workflows/phase4_live_shadow_validation_v6.yml",
        "event": pin["event"],
        "head_branch": "main",
        "head_sha": pin["head_sha"],
        "status": "completed",
        "conclusion": "failure",
        "repository": {"id": reconcile.REPOSITORY_ID},
        "head_repository": {"id": reconcile.REPOSITORY_ID},
    }
    artifact = {
        "id": pin["artifact_id"],
        "name": "phase4-readiness",
        "size_in_bytes": pin["artifact_size_in_bytes"],
        "digest": pin["artifact_digest"],
        "expires_at": pin["artifact_expires_at"],
        "expired": False,
        "workflow_run": {
            "id": pin["run_id"],
            "repository_id": reconcile.REPOSITORY_ID,
            "head_repository_id": reconcile.REPOSITORY_ID,
            "head_branch": "main",
            "head_sha": pin["head_sha"],
        },
    }
    jobs = {
        "total_count": 1,
        "jobs": [
            {
                "id": pin["job_id"],
                "name": "controlled-shadow-acceptance",
                "status": "completed",
                "conclusion": "failure",
                "steps": [
                    {
                        "name": "Execute two serialized, evidence-bound shadow cycles",
                        "conclusion": "failure",
                    },
                    {"name": "Fail-closed cleanup and evidence check", "conclusion": "success"},
                    {"name": "Upload Phase 4 readiness evidence", "conclusion": "success"},
                ],
            }
        ],
    }
    return run, artifact, jobs


def fixture(tmp_path: Path) -> dict:
    repository_root = tmp_path / "repo"
    control_files = {}
    for relative in reconcile.CONTROL_FILES:
        path = repository_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"pinned {relative}\n", encoding="utf-8")
        control_files[relative] = hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()

    start = baseline_status()
    run6_observations, run6_final, clock = build_observations(
        start,
        label="run6",
        failures={3, 7},
        clock=datetime(2026, 9, 4, 13, 0, tzinfo=timezone.utc),
    )
    run7_baseline = {"heads": copy.deepcopy(run6_final["heads"]), "latest_runs": []}
    run7_observations, current_status, _ = build_observations(
        run7_baseline,
        label="run7",
        clock=clock,
    )
    run6_archive = tmp_path / "run6.zip"
    run7_archive = tmp_path / "run7.zip"
    write_archive(run6_archive, start, run6_observations)
    write_archive(run7_archive, run7_baseline, run7_observations)

    runs = []
    for role, archive, run_id, job_id, head_sha, event, failures in (
        (
            "anchored_partial_history",
            run6_archive,
            1006,
            2006,
            "6" * 40,
            "push",
            [
                {
                    "sequence": item["sequence"],
                    "job": item["job"],
                    "cloud_run_execution": item["cloud_run_execution"],
                    "run_id": next(
                        run["run_id"]
                        for run in item["status"]["latest_runs"]
                        if run["job_name"] == item["job"]
                    ),
                }
                for item in (run6_observations[2], run6_observations[6])
            ],
        ),
        (
            "completed_two_cycle_history",
            run7_archive,
            1007,
            2007,
            "7" * 40,
            "workflow_dispatch",
            [],
        ),
    ):
        runs.append(
            {
                "role": role,
                "run_id": run_id,
                "run_number": 6 if role == "anchored_partial_history" else 7,
                "run_attempt": 1,
                "head_sha": head_sha,
                "event": event,
                "conclusion": "failure",
                "job_id": job_id,
                "artifact_id": 3000 + run_id,
                "artifact_name": "phase4-readiness",
                "artifact_size_in_bytes": archive.stat().st_size,
                "artifact_digest": f"sha256:{hashlib.sha256(archive.read_bytes()).hexdigest()}",
                "artifact_expires_at": "2026-12-03T13:28:55Z",
                "expected_successful_receipts": 6 if failures else 8,
                "expected_failed_receipts": failures,
            }
        )
    descriptor = {
        "schema_version": 1,
        "result": "phase4_shadow_evidence_reconciliation_authorized",
        "repository_id": reconcile.REPOSITORY_ID,
        "repository": reconcile.REPOSITORY,
        "workflow": {
            "id": 350129720,
            "name": "Phase 4 live shadow validation v6",
            "path": ".github/workflows/phase4_live_shadow_validation_v6.yml",
        },
        "evidence_control_revision": "7" * 40,
        "runtime_source_revision": SOURCE,
        "control_files": control_files,
        "runs": runs,
        "expected_final_heads": reconcile._head_summary(
            reconcile._heads(run7_observations[-1]["status"])
        ),
        "immutable_inventory_preserved": True,
        "additional_producer_execution_authorized": False,
        "production_authority_transferred": False,
    }
    sources = {}
    for pin, archive in zip(runs, (run6_archive, run7_archive)):
        run, artifact, jobs = source_metadata(pin)
        sources[pin["role"]] = {
            "run": run,
            "artifact": artifact,
            "jobs": jobs,
            "archive": archive,
        }
    return {
        "descriptor": descriptor,
        "inventory": inventory(),
        "repository_root": repository_root,
        "current_status": current_status,
        "current_manifest": current_manifest(),
        "control_revision": "c" * 40,
        "runtime_source_revision": SOURCE,
        "image": IMAGE,
        "sources": sources,
    }


def test_reconciliation_accepts_pinned_history_without_rebaselining(tmp_path: Path) -> None:
    receipt = reconcile.reconcile_phase4(**fixture(tmp_path))

    assert receipt["result"] == "phase4_ready_for_phase5"
    assert receipt["unique_successful_execution_receipts"] == 8
    assert receipt["controlled_shadow_cycles"] == 2
    assert receipt["reconciliation"]["immutable_inventory_preserved"] is True
    assert receipt["reconciliation"]["historical_prefix_successful_receipts"] == 6
    assert len(receipt["reconciliation"]["historical_prefix_failed_receipts"]) == 2
    assert receipt["reconciliation"]["additional_producer_execution_performed"] is False


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda data: data["sources"]["anchored_partial_history"]["artifact"].update(
                digest="sha256:" + "0" * 64
            ),
            "artifact 4006 digest mismatch",
        ),
        (
            lambda data: data["descriptor"]["expected_final_heads"]["ai"].update(
                snapshot_sha256="0" * 64
            ),
            "replayed final heads",
        ),
        (
            lambda data: data["current_status"]["heads"][0].update(snapshot_sha256="0" * 64),
            "current legislative snapshot_sha256",
        ),
        (
            lambda data: data["current_manifest"]["preflight"].update(
                legacy_route_source_verified=False
            ),
            "legacy_route_source_verified",
        ),
    ],
)
def test_reconciliation_rejects_tampered_evidence(tmp_path: Path, mutate, message: str) -> None:
    data = fixture(tmp_path)
    mutate(data)
    with pytest.raises(reconcile.PromotionValidationError, match=message):
        reconcile.reconcile_phase4(**data)


def test_reconciliation_rejects_control_drift(tmp_path: Path) -> None:
    data = fixture(tmp_path)
    path = data["repository_root"] / reconcile.CONTROL_FILES[0]
    path.write_text("changed\n", encoding="utf-8")
    with pytest.raises(reconcile.PromotionValidationError, match="differs from the evidence revision"):
        reconcile.reconcile_phase4(**data)


def test_archive_reader_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../baseline.json", "{}")
    with pytest.raises(reconcile.PromotionValidationError, match="unsafe member path"):
        reconcile._archive_members(archive)
