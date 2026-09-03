#!/usr/bin/env python3
"""Fail closed unless a Terraform plan satisfies the Phase 3 isolation contract."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Iterable


class PlanSafetyError(RuntimeError):
    pass


def _resources(module: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield from module.get("resources") or []
    for child in module.get("child_modules") or []:
        yield from _resources(child)


def _env_pairs(value: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(value, dict):
        if isinstance(value.get("name"), str) and isinstance(value.get("value"), str):
            result[value["name"]] = value["value"]
        for nested in value.values():
            result.update(_env_pairs(nested))
    elif isinstance(value, list):
        for nested in value:
            result.update(_env_pairs(nested))
    return result


def _images(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if isinstance(value.get("image"), str):
            found.append(value["image"])
        for nested in value.values():
            found.extend(_images(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_images(nested))
    return found


def validate(plan: dict[str, Any], expected_image: str) -> dict[str, Any]:
    root = ((plan.get("planned_values") or {}).get("root_module") or {})
    resources = list(_resources(root))
    if not resources:
        raise PlanSafetyError("Terraform plan contains no planned resources")

    by_type: dict[str, list[dict[str, Any]]] = {}
    for resource in resources:
        by_type.setdefault(str(resource.get("type") or ""), []).append(resource)

    sql_instances = by_type.get("google_sql_database_instance", [])
    if len(sql_instances) != 1:
        raise PlanSafetyError("Phase 3 requires exactly one Cloud SQL instance")
    sql_values = sql_instances[0].get("values") or {}
    settings = (sql_values.get("settings") or [{}])[0] or {}
    ip_configuration = (settings.get("ip_configuration") or [{}])[0] or {}
    if ip_configuration.get("ipv4_enabled") is not False:
        raise PlanSafetyError("Cloud SQL public IPv4 must be disabled")
    if not str(ip_configuration.get("private_network") or "").strip():
        raise PlanSafetyError("Cloud SQL must use a private network")
    if sql_values.get("deletion_protection") is not True:
        raise PlanSafetyError("Cloud SQL deletion protection must be enabled")

    networks = by_type.get("google_compute_network", [])
    subnetworks = by_type.get("google_compute_subnetwork", [])
    private_connections = by_type.get("google_service_networking_connection", [])
    if len(networks) != 1 or len(subnetworks) != 1 or len(private_connections) != 1:
        raise PlanSafetyError("Phase 3 private VPC boundary is incomplete")

    scheduler_jobs = by_type.get("google_cloud_scheduler_job", [])
    if not scheduler_jobs:
        raise PlanSafetyError("Phase 3 plan contains no scheduler resources")
    for resource in scheduler_jobs:
        if (resource.get("values") or {}).get("paused") is not True:
            raise PlanSafetyError(f"scheduler {resource.get('address')} is not paused")

    public_bindings = [
        resource
        for resource in by_type.get("google_cloud_run_v2_service_iam_member", [])
        if (resource.get("values") or {}).get("member") == "allUsers"
    ]
    if public_bindings:
        raise PlanSafetyError("Phase 3 dashboard would grant unauthenticated allUsers access")

    buckets = by_type.get("google_storage_bucket", [])
    if not buckets:
        raise PlanSafetyError("Phase 3 requires at least the private migration bucket")
    for resource in buckets:
        values = resource.get("values") or {}
        if values.get("uniform_bucket_level_access") is not True:
            raise PlanSafetyError(f"bucket {resource.get('address')} lacks uniform bucket-level access")
        if str(values.get("public_access_prevention") or "").lower() != "enforced":
            raise PlanSafetyError(f"bucket {resource.get('address')} lacks public-access prevention")
        versioning = (values.get("versioning") or [{}])[0] or {}
        if versioning.get("enabled") is not True:
            raise PlanSafetyError(f"bucket {resource.get('address')} lacks versioning")

    run_resources = (
        by_type.get("google_cloud_run_v2_job", [])
        + by_type.get("google_cloud_run_v2_service", [])
    )
    if not run_resources:
        raise PlanSafetyError("Phase 3 plan contains no Cloud Run resources")
    all_images: set[str] = set()
    producer_shadow_count = 0
    private_ip_count = 0
    acceptance_jobs = []
    for resource in run_resources:
        values = resource.get("values") or {}
        images = _images(values)
        all_images.update(images)
        env = _env_pairs(values)
        if env.get("POLITITRACK_MODE") == "shadow":
            producer_shadow_count += 1
        if env.get("PRIVATE_IP") == "true":
            private_ip_count += 1
        if resource.get("type") == "google_cloud_run_v2_job" and values.get("name") == "polititrack-acceptance":
            acceptance_jobs.append(resource)
            if env.get("PRIVATE_IP") != "true":
                raise PlanSafetyError("Phase 3 acceptance job must use private Cloud SQL connectivity")
            args = values.get("template") or []
            if "runtime_v2.acceptance" not in json.dumps(args, sort_keys=True):
                raise PlanSafetyError("Phase 3 acceptance job does not run the dedicated acceptance writer")

    if len(acceptance_jobs) != 1:
        raise PlanSafetyError("Phase 3 requires exactly one private acceptance job")
    if all_images != {expected_image}:
        raise PlanSafetyError(
            f"all Runtime v2 containers must use exactly the reviewed immutable image; found {sorted(all_images)}"
        )
    if "@sha256:" not in expected_image:
        raise PlanSafetyError("expected image is not immutable")
    if producer_shadow_count < 4:
        raise PlanSafetyError("not all producer jobs are explicitly in shadow mode")
    if private_ip_count < 6:
        raise PlanSafetyError("not all database-using Runtime v2 components request private IP")

    service_accounts = {
        str((resource.get("values") or {}).get("email") or (resource.get("values") or {}).get("account_id") or "")
        for resource in by_type.get("google_service_account", [])
    }
    service_accounts.discard("")
    if len(service_accounts) < 7:
        raise PlanSafetyError("Phase 3 service identities are not sufficiently separated")

    return {
        "result": "phase3_plan_accepted",
        "resource_count": len(resources),
        "scheduler_count": len(scheduler_jobs),
        "scheduler_all_paused": True,
        "public_dashboard_binding_count": 0,
        "cloud_sql_public_ipv4": False,
        "cloud_sql_private_network": True,
        "private_bucket_count": len(buckets),
        "service_identity_count": len(service_accounts),
        "acceptance_job_count": 1,
        "runtime_image": expected_image,
        "runtime_mode": "shadow",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-image", required=True)
    args = parser.parse_args()
    plan = json.load(sys.stdin)
    try:
        result = validate(plan, args.expected_image)
    except PlanSafetyError as exc:
        print(f"Phase 3 Terraform plan refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
