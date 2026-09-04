"""Validate Phase 4 shadow evidence and Phase 5 production promotion evidence.

This validator is deliberately cloud-agnostic.  The controller captures immutable
Cloud Run execution names and a Runtime v2 status snapshot after every producer.
This module rejects gaps, overlaps, duplicate receipts, non-attested modes, broken
snapshot chains, stale AI/dashboard inputs, or incomplete authority cleanup.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

NAMESPACES = ("legislative", "executive", "ai", "dashboard")
CYCLE_ORDER = NAMESPACES
PRODUCER_SCHEDULERS = tuple(f"polititrack-{name}" for name in NAMESPACES)
LEGACY_WORKFLOWS = (
    "legislative_trade_tracker_v2.yml",
    "executive_trade_tracker.yml",
    "ai_filing_analyst.yml",
    "publish_trade_dashboard.yml",
)


class PromotionValidationError(ValueError):
    """Raised when live promotion evidence is incomplete or contradictory."""


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PromotionValidationError(f"{path} is not a JSON object")
    return value


def _required_true(source: Mapping[str, Any], names: Iterable[str], label: str) -> None:
    missing = [name for name in names if source.get(name) is not True]
    if missing:
        raise PromotionValidationError(f"{label} is missing affirmative evidence: {', '.join(missing)}")


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise PromotionValidationError(f"{label} timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PromotionValidationError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise PromotionValidationError(f"{label} timestamp is not timezone-aware")
    return parsed


def _heads(status: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = status.get("heads")
    if not isinstance(raw, list):
        raise PromotionValidationError("status heads are missing")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        namespace = item.get("namespace")
        if namespace in NAMESPACES:
            if namespace in result:
                raise PromotionValidationError(f"status has duplicate {namespace} heads")
            result[namespace] = item
    if tuple(sorted(result)) != tuple(sorted(NAMESPACES)):
        raise PromotionValidationError("status does not contain exactly the four protected heads")
    for namespace, head in result.items():
        if not isinstance(head.get("generation"), int) or head["generation"] < 1:
            raise PromotionValidationError(f"{namespace} head has an invalid generation")
        digest = head.get("snapshot_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise PromotionValidationError(f"{namespace} head has no valid snapshot digest")
        if not isinstance(head.get("provenance"), dict):
            raise PromotionValidationError(f"{namespace} head has no provenance")
    return result


def _latest_runs(status: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = status.get("latest_runs")
    if not isinstance(raw, list):
        raise PromotionValidationError("status latest_runs are missing")
    result: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("job_name")
        if name in NAMESPACES:
            if name in result:
                raise PromotionValidationError(f"status has duplicate latest run for {name}")
            result[name] = item
    return result


def _copy_heads(status: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {name: dict(value) for name, value in _heads(status).items()}


def _assert_inventory_baseline(
    baseline_heads: Mapping[str, Mapping[str, Any]], inventory: Mapping[str, Any]
) -> None:
    if inventory.get("repository_id") != 1349678672:
        raise PromotionValidationError("legacy inventory repository boundary mismatch")
    if inventory.get("classification") != "legacy_unverified":
        raise PromotionValidationError("legacy inventory classification changed")
    expected = inventory.get("observed_baseline_heads")
    if not isinstance(expected, dict):
        raise PromotionValidationError("legacy inventory has no observed baseline heads")
    for namespace in NAMESPACES:
        item = expected.get(namespace)
        if not isinstance(item, dict):
            raise PromotionValidationError(f"legacy inventory lacks {namespace}")
        actual = baseline_heads[namespace]
        for key in ("generation", "snapshot_sha256"):
            if actual.get(key) != item.get(key):
                raise PromotionValidationError(
                    f"Phase 4 baseline {namespace} {key} differs from recovered immutable history"
                )


def _assert_head_transition(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
    job: str,
) -> None:
    for namespace in NAMESPACES:
        old = before[namespace]
        new = after[namespace]
        if namespace == job:
            if new.get("generation") != old.get("generation", 0) + 1:
                raise PromotionValidationError(f"{job} did not advance exactly one generation")
            if new.get("parent_sha256") != old.get("snapshot_sha256"):
                raise PromotionValidationError(f"{job} parent digest does not bind the preceding head")
            if new.get("snapshot_sha256") == old.get("snapshot_sha256"):
                raise PromotionValidationError(f"{job} successor reused its parent digest")
        else:
            for key in ("generation", "snapshot_sha256"):
                if new.get(key) != old.get(key):
                    raise PromotionValidationError(
                        f"{job} execution unexpectedly changed {namespace} {key}"
                    )


def _assert_inputs(job: str, heads: Mapping[str, Mapping[str, Any]]) -> None:
    provenance = heads[job].get("provenance") or {}
    inputs = provenance.get("inputs") or {}
    if job == "ai":
        for namespace in ("legislative", "executive"):
            item = inputs.get(namespace)
            if not isinstance(item, dict):
                raise PromotionValidationError(f"AI provenance lacks structured {namespace} input")
            if item.get("generation") != heads[namespace].get("generation"):
                raise PromotionValidationError(f"AI {namespace} input generation is stale")
            if item.get("snapshot_sha256") != heads[namespace].get("snapshot_sha256"):
                raise PromotionValidationError(f"AI {namespace} input digest is stale")
    elif job == "dashboard":
        for namespace in ("legislative", "executive", "ai"):
            if inputs.get(namespace) != heads[namespace].get("snapshot_sha256"):
                raise PromotionValidationError(f"dashboard {namespace} input digest is stale")


def _validate_sequence(
    *,
    baseline: Mapping[str, Any],
    observations: list[Any],
    expected_mode: str,
    expected_trigger: str,
    cycles: int,
    runtime_source_revision: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    expected = [job for _ in range(cycles) for job in CYCLE_ORDER]
    if len(observations) != len(expected):
        raise PromotionValidationError(
            f"expected {len(expected)} execution observations, found {len(observations)}"
        )
    previous_heads = _copy_heads(baseline)
    run_ids: set[str] = set()
    execution_names: set[str] = set()
    accepted: list[dict[str, Any]] = []
    previous_finished: datetime | None = None

    for index, (raw_observation, expected_job) in enumerate(zip(observations, expected), start=1):
        if not isinstance(raw_observation, dict):
            raise PromotionValidationError(f"observation {index} is not an object")
        job = raw_observation.get("job")
        if job != expected_job:
            raise PromotionValidationError(
                f"observation {index} is {job!r}, expected {expected_job!r}"
            )
        execution = raw_observation.get("cloud_run_execution")
        if not isinstance(execution, str) or not execution:
            raise PromotionValidationError(f"{job} observation has no Cloud Run execution name")
        if execution in execution_names:
            raise PromotionValidationError(f"duplicate Cloud Run execution {execution}")
        execution_names.add(execution)

        status = raw_observation.get("status")
        if not isinstance(status, dict):
            raise PromotionValidationError(f"{job} observation has no status snapshot")
        current_heads = _heads(status)
        _assert_head_transition(previous_heads, current_heads, job)
        run = _latest_runs(status).get(job)
        if not run:
            raise PromotionValidationError(f"{job} latest run is missing")
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise PromotionValidationError(f"{job} run has no run_id")
        if run_id in run_ids:
            raise PromotionValidationError(f"duplicate Runtime v2 run receipt {run_id}")
        run_ids.add(run_id)

        if run.get("status") != "success":
            raise PromotionValidationError(f"{job} did not finish successfully")
        if run.get("runtime_mode") != expected_mode or run.get("runtime_mode_verified") is not True:
            raise PromotionValidationError(f"{job} lacks verified {expected_mode} mode evidence")
        if run.get("trigger_source") != expected_trigger:
            raise PromotionValidationError(f"{job} trigger source is not {expected_trigger}")
        if run.get("side_effects_possible") is not False:
            raise PromotionValidationError(f"{job} reports possible external side effects")
        if run.get("source_revision") != runtime_source_revision:
            raise PromotionValidationError(f"{job} runtime source revision mismatch")
        if run.get("snapshot_generation") != current_heads[job].get("generation"):
            raise PromotionValidationError(f"{job} run generation does not match its head")
        if run.get("snapshot_sha256") != current_heads[job].get("snapshot_sha256"):
            raise PromotionValidationError(f"{job} run digest does not match its head")

        provenance = current_heads[job].get("provenance") or {}
        for key, value in {
            "authority": "runtime_v2",
            "job": job,
            "mode": expected_mode,
            "trigger_source": expected_trigger,
        }.items():
            if provenance.get(key) != value:
                raise PromotionValidationError(f"{job} snapshot provenance {key} mismatch")
        if current_heads[job].get("source_revision") != runtime_source_revision:
            raise PromotionValidationError(f"{job} head source revision mismatch")
        _assert_inputs(job, current_heads)

        started = _parse_time(run.get("started_at"), f"{job} started_at")
        finished = _parse_time(run.get("finished_at"), f"{job} finished_at")
        if finished < started:
            raise PromotionValidationError(f"{job} finished before it started")
        if previous_finished is not None and started < previous_finished:
            raise PromotionValidationError(f"{job} overlapped the preceding protected writer")
        previous_finished = finished

        accepted.append(
            {
                "sequence": index,
                "cycle": ((index - 1) // len(CYCLE_ORDER)) + 1,
                "job": job,
                "cloud_run_execution": execution,
                "run_id": run_id,
                "started_at": run["started_at"],
                "finished_at": run["finished_at"],
                "generation": current_heads[job]["generation"],
                "snapshot_sha256": current_heads[job]["snapshot_sha256"],
            }
        )
        previous_heads = {name: dict(value) for name, value in current_heads.items()}

    return previous_heads, accepted


def _base_preflight(preflight: Mapping[str, Any]) -> None:
    _required_true(
        preflight,
        (
            "canonical_repository_verified",
            "canonical_main_verified",
            "project_boundary_verified",
            "image_digest_verified",
            "cloud_sql_private_only",
            "producer_schedulers_paused",
            "web_public_invoker_absent",
            "persistent_job_configuration_verified",
        ),
        "preflight",
    )


def _base_cleanup(cleanup: Mapping[str, Any]) -> None:
    _required_true(
        cleanup,
        (
            "temporary_execution_authority_removed",
            "temporary_logging_authority_removed",
            "temporary_service_account_user_removed",
            "cloud_sql_private_only",
        ),
        "cleanup",
    )


def validate_phase4(
    *,
    baseline: dict[str, Any],
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    control_revision: str,
    runtime_source_revision: str,
    image: str,
) -> dict[str, Any]:
    if manifest.get("phase") != "phase4":
        raise PromotionValidationError("manifest phase is not phase4")
    preflight = manifest.get("preflight")
    cleanup = manifest.get("cleanup")
    if not isinstance(preflight, dict) or not isinstance(cleanup, dict):
        raise PromotionValidationError("Phase 4 preflight or cleanup evidence is missing")
    _base_preflight(preflight)
    _required_true(preflight, ("legacy_production_route_active",), "Phase 4 preflight")
    _base_cleanup(cleanup)
    _required_true(
        cleanup,
        ("producer_schedulers_paused", "web_public_invoker_absent", "legacy_production_route_active"),
        "Phase 4 cleanup",
    )
    baseline_heads = _heads(baseline)
    _assert_inventory_baseline(baseline_heads, inventory)
    observations = manifest.get("executions")
    if not isinstance(observations, list):
        raise PromotionValidationError("Phase 4 execution manifest is missing")
    final_heads, receipts = _validate_sequence(
        baseline=baseline,
        observations=observations,
        expected_mode="shadow",
        expected_trigger="shadow",
        cycles=2,
        runtime_source_revision=runtime_source_revision,
    )
    return {
        "schema_version": 1,
        "result": "phase4_ready_for_phase5",
        "repository_id": 1349678672,
        "control_revision": control_revision,
        "runtime_source_revision": runtime_source_revision,
        "immutable_image": image,
        "controlled_shadow_cycles": 2,
        "unique_successful_execution_receipts": len(receipts),
        "executions": receipts,
        "baseline_heads": {
            name: {
                "generation": baseline_heads[name]["generation"],
                "snapshot_sha256": baseline_heads[name]["snapshot_sha256"],
            }
            for name in NAMESPACES
        },
        "final_heads": {
            name: {
                "generation": final_heads[name]["generation"],
                "snapshot_sha256": final_heads[name]["snapshot_sha256"],
            }
            for name in NAMESPACES
        },
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
    }


def validate_phase5(
    *,
    baseline: dict[str, Any],
    manifest: dict[str, Any],
    phase4_certificate: dict[str, Any],
    control_revision: str,
    runtime_source_revision: str,
    image: str,
) -> dict[str, Any]:
    if manifest.get("phase") != "phase5":
        raise PromotionValidationError("manifest phase is not phase5")
    if phase4_certificate.get("result") != "phase4_ready_for_phase5":
        raise PromotionValidationError("Phase 4 readiness certificate is not valid")
    for key, value in {
        "repository_id": 1349678672,
        "control_revision": control_revision,
        "runtime_source_revision": runtime_source_revision,
        "immutable_image": image,
        "phase5_ready": True,
    }.items():
        if phase4_certificate.get(key) != value:
            raise PromotionValidationError(f"Phase 4 certificate {key} mismatch")

    baseline_heads = _heads(baseline)
    certified_heads = phase4_certificate.get("final_heads")
    if not isinstance(certified_heads, dict):
        raise PromotionValidationError("Phase 4 certificate has no final heads")
    for namespace in NAMESPACES:
        expected = certified_heads.get(namespace)
        if not isinstance(expected, dict):
            raise PromotionValidationError(f"Phase 4 certificate lacks {namespace} head")
        for key in ("generation", "snapshot_sha256"):
            if baseline_heads[namespace].get(key) != expected.get(key):
                raise PromotionValidationError(
                    f"Phase 5 baseline {namespace} {key} differs from the Phase 4 certificate"
                )

    preflight = manifest.get("preflight")
    cleanup = manifest.get("cleanup")
    promotion = manifest.get("promotion")
    if not all(isinstance(value, dict) for value in (preflight, cleanup, promotion)):
        raise PromotionValidationError("Phase 5 preflight, cleanup, or promotion evidence is missing")
    assert isinstance(preflight, dict) and isinstance(cleanup, dict) and isinstance(promotion, dict)
    _base_preflight(preflight)
    _required_true(
        preflight,
        ("phase4_certificate_verified", "legacy_workflows_disabled", "legacy_runs_drained"),
        "Phase 5 preflight",
    )
    _base_cleanup(cleanup)

    observations = manifest.get("executions")
    if not isinstance(observations, list):
        raise PromotionValidationError("Phase 5 execution manifest is missing")
    final_heads, receipts = _validate_sequence(
        baseline=baseline,
        observations=observations,
        expected_mode="production",
        expected_trigger="phase5_smoke",
        cycles=1,
        runtime_source_revision=runtime_source_revision,
    )

    _required_true(
        promotion,
        (
            "legacy_workflows_disabled",
            "legacy_runs_drained",
            "runtime_jobs_production_mode",
            "web_public_invoker_present",
            "healthz_ok",
            "readyz_ok",
            "dashboard_ok",
            "cloud_sql_private_only",
            "rollback_armed",
        ),
        "Phase 5 promotion",
    )
    if promotion.get("production_route") != "runtime_v2":
        raise PromotionValidationError("production route is not Runtime v2")
    enabled = promotion.get("enabled_producer_schedulers")
    if not isinstance(enabled, list) or tuple(sorted(enabled)) != tuple(sorted(PRODUCER_SCHEDULERS)):
        raise PromotionValidationError("the four Runtime v2 producer schedulers are not exactly enabled")
    disabled_legacy = promotion.get("disabled_legacy_workflows")
    if not isinstance(disabled_legacy, list) or tuple(sorted(disabled_legacy)) != tuple(sorted(LEGACY_WORKFLOWS)):
        raise PromotionValidationError("the four legacy production workflows are not exactly disabled")
    if promotion.get("vault_scheduler_state") != "PAUSED":
        raise PromotionValidationError("Filing Vault scheduler state changed during Phase 5")
    dashboard_digest = final_heads["dashboard"]["snapshot_sha256"]
    for key in ("ready_snapshot_sha256", "served_snapshot_sha256"):
        if promotion.get(key) != dashboard_digest:
            raise PromotionValidationError(f"public dashboard {key} does not match accepted head")
    web_url = promotion.get("web_url")
    if not isinstance(web_url, str) or not web_url.startswith("https://"):
        raise PromotionValidationError("public Runtime v2 web URL is invalid")

    _required_true(
        cleanup,
        (
            "legacy_workflows_disabled",
            "producer_schedulers_enabled",
            "web_public_invoker_present",
            "runtime_jobs_production_mode",
        ),
        "Phase 5 cleanup",
    )

    return {
        "schema_version": 1,
        "result": "phase5_complete",
        "repository_id": 1349678672,
        "control_revision": control_revision,
        "runtime_source_revision": runtime_source_revision,
        "immutable_image": image,
        "production_route": "runtime_v2",
        "production_authority_transferred": True,
        "unique_successful_smoke_receipts": len(receipts),
        "executions": receipts,
        "baseline_heads": {
            name: {
                "generation": baseline_heads[name]["generation"],
                "snapshot_sha256": baseline_heads[name]["snapshot_sha256"],
            }
            for name in NAMESPACES
        },
        "final_heads": {
            name: {
                "generation": final_heads[name]["generation"],
                "snapshot_sha256": final_heads[name]["snapshot_sha256"],
            }
            for name in NAMESPACES
        },
        "enabled_producer_schedulers": list(PRODUCER_SCHEDULERS),
        "disabled_legacy_workflows": list(LEGACY_WORKFLOWS),
        "vault_scheduler_state": "PAUSED",
        "web_url": web_url,
        "served_snapshot_sha256": dashboard_digest,
        "cloud_sql_private_only": True,
        "temporary_authority_removed": True,
        "rollback_armed": True,
        "phase6_started": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("phase4", "phase5"), required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--phase4-certificate", type=Path)
    parser.add_argument("--control-revision", required=True)
    parser.add_argument("--runtime-source-revision", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline = _load(args.baseline)
    manifest = _load(args.manifest)
    if args.phase == "phase4":
        if args.inventory is None:
            parser.error("--inventory is required for phase4")
        receipt = validate_phase4(
            baseline=baseline,
            manifest=manifest,
            inventory=_load(args.inventory),
            control_revision=args.control_revision,
            runtime_source_revision=args.runtime_source_revision,
            image=args.image,
        )
    else:
        if args.phase4_certificate is None:
            parser.error("--phase4-certificate is required for phase5")
        receipt = validate_phase5(
            baseline=baseline,
            manifest=manifest,
            phase4_certificate=_load(args.phase4_certificate),
            control_revision=args.control_revision,
            runtime_source_revision=args.runtime_source_revision,
            image=args.image,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
