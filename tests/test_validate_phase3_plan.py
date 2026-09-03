import copy

import pytest

from scripts.validate_phase3_plan import PlanSafetyError, validate


IMAGE = "us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:" + "a" * 64


def _run_job(name: str, *, shadow: bool = True, private_ip: bool = True, acceptance: bool = False):
    env = []
    if shadow:
        env.append({"name": "POLITITRACK_MODE", "value": "shadow"})
    if private_ip:
        env.append({"name": "PRIVATE_IP", "value": "true"})
    args = ["-m", "runtime_v2.acceptance"] if acceptance else ["-m", "runtime_v2", "run", name]
    return {
        "address": f"google_cloud_run_v2_job.{name}",
        "type": "google_cloud_run_v2_job",
        "values": {
            "name": "polititrack-acceptance" if acceptance else f"polititrack-{name}",
            "template": [{"template": [{"containers": [{"image": IMAGE, "args": args, "env": env}]}]}],
        },
    }


def _plan():
    resources = [
        {
            "address": "google_sql_database_instance.runtime",
            "type": "google_sql_database_instance",
            "values": {
                "deletion_protection": True,
                "settings": [{"ip_configuration": [{"ipv4_enabled": False, "private_network": "network-id"}]}],
            },
        },
        {"address": "google_compute_network.runtime", "type": "google_compute_network", "values": {"name": "runtime"}},
        {"address": "google_compute_subnetwork.runtime", "type": "google_compute_subnetwork", "values": {"name": "runtime"}},
        {
            "address": "google_service_networking_connection.private_vpc",
            "type": "google_service_networking_connection",
            "values": {"network": "network-id"},
        },
        {
            "address": "google_cloud_scheduler_job.producer[\"legislative\"]",
            "type": "google_cloud_scheduler_job",
            "values": {"name": "polititrack-legislative", "paused": True},
        },
        {
            "address": "google_storage_bucket.migration",
            "type": "google_storage_bucket",
            "values": {
                "name": "project-polititrack-migration",
                "uniform_bucket_level_access": True,
                "public_access_prevention": "enforced",
                "versioning": [{"enabled": True}],
            },
        },
        _run_job("legislative"),
        _run_job("executive"),
        _run_job("ai"),
        _run_job("dashboard"),
        _run_job("acceptance", shadow=False, acceptance=True),
        {
            "address": "google_cloud_run_v2_service.web",
            "type": "google_cloud_run_v2_service",
            "values": {
                "name": "polititrack-web",
                "template": [{"containers": [{"image": IMAGE, "env": [{"name": "PRIVATE_IP", "value": "true"}]}]}],
            },
        },
    ]
    for index in range(7):
        resources.append(
            {
                "address": f"google_service_account.identity_{index}",
                "type": "google_service_account",
                "values": {"account_id": f"polititrack-identity-{index}"},
            }
        )
    return {"planned_values": {"root_module": {"resources": resources}}}


def _resource(plan, address):
    for resource in plan["planned_values"]["root_module"]["resources"]:
        if resource.get("address") == address:
            return resource
    raise AssertionError(address)


def test_phase3_plan_accepts_private_shadow_boundary():
    result = validate(_plan(), IMAGE)
    assert result["result"] == "phase3_plan_accepted"
    assert result["scheduler_all_paused"] is True
    assert result["cloud_sql_public_ipv4"] is False
    assert result["acceptance_job_count"] == 1
    assert result["runtime_image"] == IMAGE


def test_phase3_plan_rejects_unpaused_scheduler():
    plan = _plan()
    _resource(plan, 'google_cloud_scheduler_job.producer["legislative"]')["values"]["paused"] = False
    with pytest.raises(PlanSafetyError, match="not paused"):
        validate(plan, IMAGE)


def test_phase3_plan_rejects_public_cloud_sql():
    plan = _plan()
    sql = _resource(plan, "google_sql_database_instance.runtime")
    sql["values"]["settings"][0]["ip_configuration"][0]["ipv4_enabled"] = True
    with pytest.raises(PlanSafetyError, match="public IPv4"):
        validate(plan, IMAGE)


def test_phase3_plan_rejects_public_dashboard_binding():
    plan = _plan()
    plan["planned_values"]["root_module"]["resources"].append(
        {
            "address": "google_cloud_run_v2_service_iam_member.public_dashboard[0]",
            "type": "google_cloud_run_v2_service_iam_member",
            "values": {"member": "allUsers"},
        }
    )
    with pytest.raises(PlanSafetyError, match="allUsers"):
        validate(plan, IMAGE)


def test_phase3_plan_rejects_mutable_or_mismatched_image():
    with pytest.raises(PlanSafetyError, match="reviewed immutable image"):
        validate(_plan(), IMAGE.replace("a" * 64, "b" * 64))


def test_phase3_plan_rejects_missing_acceptance_job():
    plan = _plan()
    resources = plan["planned_values"]["root_module"]["resources"]
    plan["planned_values"]["root_module"]["resources"] = [
        resource for resource in resources if resource.get("address") != "google_cloud_run_v2_job.acceptance"
    ]
    with pytest.raises(PlanSafetyError, match="acceptance job"):
        validate(plan, IMAGE)
