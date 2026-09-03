from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_apply_saved_plan.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_exact_plan_apply_is_one_shot_main_push_only() -> None:
    text = _text()
    assert "on:\n  push:" in text
    assert "workflow_dispatch:" not in text
    assert "schedule:" not in text
    assert '      - ".github/workflows/phase3_apply_saved_plan.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text


def test_exact_plan_apply_is_pinned_to_reviewed_saved_plan() -> None:
    text = _text()
    expected = {
        "SAVED_SOURCE_REVISION": "7f14bba18130fc1d40d2e5d7891078a65c4d4eec",
        "SAVED_PLAN_SHA256": "85101209392051c5abbc3ad5c5671e5f8c3420362ea5a3aaa1ab1a9d2ae1692c",
        "RECONCILIATION_CONFIG_SHA256": "a59da1f64e5dc11885bc9beeeabc8b723ba0dbfb595491102aa5cc8c2eb94aaa",
        "TERRAFORM_LOCK_SHA256": "65dee896a641b225cfb60f7b25ef9bdb8934c8d7adcd81fa47a9754c2280da9b",
        "MOVED_TF_SHA256": "5bd25f6d1465796f9d40779af4b290c16e02a0d24dd42cf6cea5d1617e1ce957",
        "ACTION_INVENTORY_SHA256": "125f8a5f0946e625be21206f3064c4bbb69d0f530a0a1b7e595e1d34e1999841",
    }
    for name, value in expected.items():
        assert f"{name}: {value}" in text
    assert "ref: ${{ env.SAVED_SOURCE_REVISION }}" in text
    assert "git rev-parse HEAD" in text


def test_exact_plan_apply_reverifies_receipt_and_binary_policy() -> None:
    text = _text()
    assert "Downloaded saved-plan SHA-256 mismatch." in text
    assert "Saved-plan receipt verified against hard-coded Phase 3 acceptance constants." in text
    assert "Saved binary plan machine policy re-verified immediately before apply." in text
    assert '(create_count, update_count, delete_count) != (28, 17, 10)' in text
    assert "delete_addresses != allowed_delete" in text
    assert 'after.get("paused") is not True' in text
    assert 'ip_config.get("ipv4_enabled") is not False' in text
    assert 'env.get("PRIVATE_IP") != "true"' in text
    assert '"POLITITRACK_MODE": "shadow"' in text


def test_exact_plan_apply_has_only_one_terraform_apply_and_no_plan_regeneration() -> None:
    text = _text()
    assert text.count("terraform -chdir=deploy/runtime-v2/terraform apply") == 1
    assert 'apply -auto-approve "${RUNNER_TEMP}/phase3-runtime-v2.tfplan"' in text
    assert "terraform -chdir=deploy/runtime-v2/terraform plan" not in text
    assert "terraform import" not in text
    assert "state rm" not in text
    assert "state mv" not in text


def test_exact_plan_apply_never_executes_runtime_or_activates_scheduler() -> None:
    text = _text()
    forbidden = (
        "run jobs execute",
        "run jobs run",
        "scheduler jobs run",
        "scheduler jobs resume",
        "scheduler jobs update",
        "secrets versions access",
        "builds submit",
    )
    for value in forbidden:
        assert value not in text
    assert '"runtime_job_execution": False' in text
    assert '"scheduler_execution": False' in text
    assert '"schedules_enabled": False' in text


def test_exact_plan_apply_postchecks_phase3_isolation() -> None:
    text = _text()
    for required in (
        "gcloud scheduler jobs list",
        "gcloud sql instances describe polititrack-runtime-v2",
        "gcloud compute networks describe polititrack-runtime-v2",
        "gcloud compute networks subnets describe polititrack-runtime-v2",
        "gcloud run jobs describe",
        "gcloud run services describe polititrack-web",
        "get-iam-policy",
    ):
        assert required in text
    for required in (
        '"schedulers_paused": True',
        '"cloud_sql_public_ipv4": False',
        '"cloud_sql_private_ip": True',
        '"private_vpc_verified": True',
        '"split_runtime_identities_verified": True',
        '"producer_shadow_mode_verified": True',
        '"producer_private_ip_verified": True',
        '"public_dashboard_invoker_absent": True',
    ):
        assert required in text


def test_exact_plan_apply_does_not_publish_sensitive_plan_material_to_github() -> None:
    text = _text()
    assert "actions/upload-artifact@v4" in text
    upload = text[text.index("uses: actions/upload-artifact@v4") :]
    assert "phase3-runtime-v2.tfplan" not in upload
    assert "phase3-runtime-v2-plan.json" not in upload
    assert '"binary_plan_github_uploaded": False' in text
    assert '"plan_json_uploaded": False' in text
    assert "rm -f" in text


def test_exact_plan_apply_authenticates_keylessly_as_constrained_deployer() -> None:
    text = _text()
    assert "uses: google-github-actions/auth@v3" in text
    assert "service_account: ${{ env.DEPLOYER_SERVICE_ACCOUNT }}" in text
    assert "credentials_json:" not in text
    assert "polititrack-phase3-deployer@" in text
