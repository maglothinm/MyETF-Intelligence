from __future__ import annotations

import copy
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "deploy" / "runtime-v2" / "validate_runtime_promotion.py"
SPEC = importlib.util.spec_from_file_location("validate_runtime_promotion", MODULE_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)

SOURCE = "8908f067298078f8c013e90cf6b7ad8ad420285b"
CONTROL = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/example/runtime-v2@sha256:" + "b" * 64
BASE_GENS = {"legislative": 2, "executive": 2, "ai": 3, "dashboard": 2}


def digest(name: str, generation: int) -> str:
    import hashlib

    return hashlib.sha256(f"{name}:{generation}".encode()).hexdigest()


def baseline_status() -> dict:
    heads = []
    for name in validator.NAMESPACES:
        generation = BASE_GENS[name]
        heads.append(
            {
                "namespace": name,
                "generation": generation,
                "snapshot_sha256": digest(name, generation),
                "parent_sha256": digest(name, generation - 1),
                "source_revision": "legacy",
                "provenance": {"authority": "legacy"},
            }
        )
    return {"heads": heads, "latest_runs": []}


def inventory() -> dict:
    return {
        "repository_id": 1349678672,
        "classification": "legacy_unverified",
        "observed_baseline_heads": {
            name: {
                "generation": BASE_GENS[name],
                "snapshot_sha256": digest(name, BASE_GENS[name]),
            }
            for name in validator.NAMESPACES
        },
    }


def common_preflight() -> dict:
    return {
        "canonical_repository_verified": True,
        "canonical_main_verified": True,
        "project_boundary_verified": True,
        "image_digest_verified": True,
        "cloud_sql_private_only": True,
        "producer_schedulers_paused": True,
        "web_public_invoker_absent": True,
        "persistent_job_configuration_verified": True,
    }


def common_cleanup() -> dict:
    return {
        "temporary_execution_authority_removed": True,
        "temporary_logging_authority_removed": True,
        "temporary_service_account_user_removed": True,
        "cloud_sql_private_only": True,
    }


def observations(*, mode: str, trigger: str, cycles: int, start: dict | None = None) -> list[dict]:
    status = copy.deepcopy(start or baseline_status())
    heads = {item["namespace"]: item for item in status["heads"]}
    clock = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)
    result = []
    sequence = 0
    for _ in range(cycles):
        for job in validator.CYCLE_ORDER:
            sequence += 1
            old = copy.deepcopy(heads[job])
            generation = old["generation"] + 1
            provenance = {
                "authority": "runtime_v2",
                "job": job,
                "mode": mode,
                "trigger_source": trigger,
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
                "snapshot_sha256": digest(job, generation),
                "parent_sha256": old["snapshot_sha256"],
                "source_revision": SOURCE,
                "provenance": provenance,
            }
            started = clock
            finished = started + timedelta(seconds=30)
            clock = finished + timedelta(seconds=1)
            run = {
                "run_id": f"run-{mode}-{sequence}",
                "job_name": job,
                "status": "success",
                "runtime_mode": mode,
                "runtime_mode_verified": True,
                "trigger_source": trigger,
                "side_effects_possible": False,
                "source_revision": SOURCE,
                "snapshot_generation": generation,
                "snapshot_sha256": heads[job]["snapshot_sha256"],
                "started_at": started.isoformat().replace("+00:00", "Z"),
                "finished_at": finished.isoformat().replace("+00:00", "Z"),
            }
            snapshot = {
                "heads": [copy.deepcopy(heads[name]) for name in validator.NAMESPACES],
                "latest_runs": [run],
            }
            result.append(
                {
                    "job": job,
                    "cloud_run_execution": f"polititrack-{job}-{mode}-{sequence}",
                    "status": snapshot,
                }
            )
    return result


def phase4_manifest() -> dict:
    preflight = common_preflight()
    preflight["legacy_production_route_active"] = True
    cleanup = common_cleanup()
    cleanup.update(
        {
            "producer_schedulers_paused": True,
            "web_public_invoker_absent": True,
            "legacy_production_route_active": True,
        }
    )
    return {
        "phase": "phase4",
        "preflight": preflight,
        "executions": observations(mode="shadow", trigger="shadow", cycles=2),
        "cleanup": cleanup,
    }


def phase4_certificate() -> dict:
    return validator.validate_phase4(
        baseline=baseline_status(),
        manifest=phase4_manifest(),
        inventory=inventory(),
        control_revision=CONTROL,
        runtime_source_revision=SOURCE,
        image=IMAGE,
    )


def phase5_manifest(cert: dict | None = None) -> tuple[dict, dict]:
    certificate = cert or phase4_certificate()
    base = {
        "heads": [
            {
                "namespace": name,
                "generation": certificate["final_heads"][name]["generation"],
                "snapshot_sha256": certificate["final_heads"][name]["snapshot_sha256"],
                "parent_sha256": digest(name, certificate["final_heads"][name]["generation"] - 1),
                "source_revision": SOURCE,
                "provenance": {"authority": "runtime_v2"},
            }
            for name in validator.NAMESPACES
        ],
        "latest_runs": [],
    }
    preflight = common_preflight()
    preflight.update(
        {
            "phase4_certificate_verified": True,
            "legacy_workflows_disabled": True,
            "legacy_runs_drained": True,
        }
    )
    cleanup = common_cleanup()
    cleanup.update(
        {
            "legacy_workflows_disabled": True,
            "producer_schedulers_enabled": True,
            "web_public_invoker_present": True,
            "runtime_jobs_production_mode": True,
        }
    )
    executions = observations(
        mode="production", trigger="phase5_smoke", cycles=1, start=base
    )
    final_dashboard = executions[-1]["status"]["heads"][-1]["snapshot_sha256"]
    promotion = {
        "legacy_workflows_disabled": True,
        "legacy_runs_drained": True,
        "runtime_jobs_production_mode": True,
        "web_public_invoker_present": True,
        "healthz_ok": True,
        "readyz_ok": True,
        "dashboard_ok": True,
        "cloud_sql_private_only": True,
        "rollback_armed": True,
        "production_route": "runtime_v2",
        "enabled_producer_schedulers": list(validator.PRODUCER_SCHEDULERS),
        "disabled_legacy_workflows": list(validator.LEGACY_WORKFLOWS),
        "vault_scheduler_state": "PAUSED",
        "ready_snapshot_sha256": final_dashboard,
        "served_snapshot_sha256": final_dashboard,
        "web_url": "https://polititrack-web.example.run.app",
    }
    return base, {
        "phase": "phase5",
        "preflight": preflight,
        "executions": executions,
        "promotion": promotion,
        "cleanup": cleanup,
    }


def test_phase4_accepts_two_exact_shadow_cycles() -> None:
    receipt = phase4_certificate()
    assert receipt["result"] == "phase4_ready_for_phase5"
    assert receipt["unique_successful_execution_receipts"] == 8
    assert receipt["final_heads"]["legislative"]["generation"] == 4
    assert receipt["final_heads"]["ai"]["generation"] == 5
    assert receipt["production_authority_transferred"] is False


def test_phase4_rejects_recovered_baseline_mismatch() -> None:
    bad = baseline_status()
    bad["heads"][0]["generation"] += 1
    with pytest.raises(validator.PromotionValidationError, match="recovered immutable history"):
        validator.validate_phase4(
            baseline=bad,
            manifest=phase4_manifest(),
            inventory=inventory(),
            control_revision=CONTROL,
            runtime_source_revision=SOURCE,
            image=IMAGE,
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda m: m["executions"][0].update(job="executive"), "expected 'legislative'"),
        (
            lambda m: m["executions"][1].update(
                cloud_run_execution=m["executions"][0]["cloud_run_execution"]
            ),
            "duplicate Cloud Run execution",
        ),
        (
            lambda m: m["executions"][0]["status"]["latest_runs"][0].update(
                side_effects_possible=True
            ),
            "possible external side effects",
        ),
        (
            lambda m: m["executions"][0]["status"]["latest_runs"][0].update(
                runtime_mode_verified=False
            ),
            "verified shadow mode",
        ),
        (
            lambda m: m["executions"][0]["status"]["heads"][0].update(generation=9),
            "exactly one generation",
        ),
        (
            lambda m: m["executions"][0]["status"]["heads"][0].update(
                parent_sha256="0" * 64
            ),
            "parent digest",
        ),
        (
            lambda m: m["executions"][0]["status"]["heads"][1].update(
                snapshot_sha256="0" * 64
            ),
            "unexpectedly changed executive",
        ),
        (
            lambda m: m["executions"][2]["status"]["heads"][2]["provenance"]["inputs"][
                "legislative"
            ].update(snapshot_sha256="0" * 64),
            "AI legislative input digest is stale",
        ),
    ],
)
def test_phase4_rejects_corrupt_evidence(mutate, message: str) -> None:
    manifest = phase4_manifest()
    mutate(manifest)
    with pytest.raises(validator.PromotionValidationError, match=message):
        validator.validate_phase4(
            baseline=baseline_status(),
            manifest=manifest,
            inventory=inventory(),
            control_revision=CONTROL,
            runtime_source_revision=SOURCE,
            image=IMAGE,
        )


def test_phase4_rejects_overlapping_writers() -> None:
    manifest = phase4_manifest()
    first = manifest["executions"][0]["status"]["latest_runs"][0]
    second = manifest["executions"][1]["status"]["latest_runs"][0]
    second["started_at"] = first["started_at"]
    with pytest.raises(validator.PromotionValidationError, match="overlapped"):
        validator.validate_phase4(
            baseline=baseline_status(),
            manifest=manifest,
            inventory=inventory(),
            control_revision=CONTROL,
            runtime_source_revision=SOURCE,
            image=IMAGE,
        )


def test_phase5_accepts_exact_production_smoke_and_public_route() -> None:
    cert = phase4_certificate()
    base, manifest = phase5_manifest(cert)
    receipt = validator.validate_phase5(
        baseline=base,
        manifest=manifest,
        phase4_certificate=cert,
        control_revision=CONTROL,
        runtime_source_revision=SOURCE,
        image=IMAGE,
    )
    assert receipt["result"] == "phase5_complete"
    assert receipt["production_authority_transferred"] is True
    assert receipt["unique_successful_smoke_receipts"] == 4
    assert receipt["vault_scheduler_state"] == "PAUSED"
    assert receipt["phase6_started"] is False


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda m: m["promotion"].update(production_route="github_actions"),
            "production route is not Runtime v2",
        ),
        (
            lambda m: m["promotion"].update(enabled_producer_schedulers=[]),
            "four Runtime v2 producer schedulers",
        ),
        (
            lambda m: m["promotion"].update(vault_scheduler_state="ENABLED"),
            "Filing Vault scheduler state changed",
        ),
        (
            lambda m: m["promotion"].update(served_snapshot_sha256="0" * 64),
            "served_snapshot_sha256",
        ),
        (
            lambda m: m["preflight"].update(legacy_runs_drained=False),
            "Phase 5 preflight",
        ),
    ],
)
def test_phase5_rejects_incomplete_cutover(mutate, message: str) -> None:
    cert = phase4_certificate()
    base, manifest = phase5_manifest(cert)
    mutate(manifest)
    with pytest.raises(validator.PromotionValidationError, match=message):
        validator.validate_phase5(
            baseline=base,
            manifest=manifest,
            phase4_certificate=cert,
            control_revision=CONTROL,
            runtime_source_revision=SOURCE,
            image=IMAGE,
        )
