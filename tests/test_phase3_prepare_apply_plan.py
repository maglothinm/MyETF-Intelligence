from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_prepare_apply_plan.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_saved_plan_runs_only_on_canonical_main_boundary() -> None:
    text = _text()
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text
    assert "project-38008d5f-4918-46e6-920" in text
    assert "polititrack-github-phase3/providers/phase3-main" in text
    assert "polititrack-phase3-deployer@" in text


def test_saved_plan_uses_exact_locked_toolchain_and_frozen_inputs() -> None:
    text = _text()
    assert 'terraform_version: "1.11.4"' in text
    assert "terraform_wrapper: false" in text
    assert "-lockfile=readonly" in text
    assert 'RECONCILIATION_VARS: ../phase3-reconciliation.tfvars.json' in text
    assert '-var-file="${RECONCILIATION_VARS}"' in text


def test_saved_plan_is_not_an_apply_or_runtime_execution_workflow() -> None:
    text = _text()
    forbidden = (
        "terraform apply",
        "terraform import",
        "run jobs execute",
        "run jobs run",
        "scheduler jobs resume",
        "scheduler jobs run",
        "scheduler jobs update",
        "secrets versions access",
        "builds submit",
    )
    for value in forbidden:
        assert value not in text
    assert '"terraform_apply": False' in text
    assert '"runtime_job_execution": False' in text
    assert '"state_import": False' in text


def test_saved_plan_requires_reviewed_action_counts_and_exact_delete_allowlist() -> None:
    text = _text()
    assert "(create_count, update_count, delete_count) != (28, 17, 10)" in text
    assert "delete_addresses != allowed_delete" in text
    expected_delete_addresses = (
        'google_cloud_run_v2_job_iam_member.scheduler[\\"ai\\"]',
        'google_cloud_run_v2_job_iam_member.scheduler[\\"dashboard\\"]',
        'google_cloud_run_v2_job_iam_member.scheduler[\\"executive\\"]',
        'google_cloud_run_v2_job_iam_member.scheduler[\\"legislative\\"]',
        "google_cloud_run_v2_job_iam_member.vault_scheduler[0]",
        "google_cloud_run_v2_service_iam_member.public_dashboard[0]",
        "google_secret_manager_secret_iam_member.vault_signing_key",
        "google_storage_bucket_iam_member.migration_runtime",
        "google_storage_bucket_iam_member.vault_runtime[0]",
        "google_storage_bucket_iam_member.vault_runtime_metadata[0]",
    )
    for address in expected_delete_addresses:
        assert address.replace("\\\"", '"') in text


def test_saved_plan_machine_policy_requires_schedulers_paused_and_private_sql() -> None:
    text = _text()
    assert "after.get(\"paused\") is not True" in text
    assert "Cloud SQL public IPv4 is not disabled in saved plan." in text
    assert 'ip_config.get("ipv4_enabled") is not False' in text
    assert '"all_schedulers_paused": True' in text
    assert '"cloud_sql_public_ipv4": False' in text


def test_saved_plan_machine_policy_preserves_producer_environment_and_private_ip() -> None:
    text = _text()
    for value in (
        '"POLITITRACK_MODE": "shadow"',
        '"AI_ANALYSIS_ENABLED": "true"',
        '"AI_WEB_SEARCH_ENABLED": "true"',
        '"OPENAI_MODEL": "gpt-5.6-terra"',
        '"SOURCE_REVISION": "c20958f6c22077411d3787bc8aa74c08c0b26fc3"',
    ):
        assert value in text
    assert 'env.get("PRIVATE_IP") != "true"' in text
    assert '"producer_environment_preserved": True' in text
    assert '"producer_private_ip": True' in text


def test_binary_plan_and_plan_json_never_enter_github_artifact() -> None:
    text = _text()
    assert '-out="${plan_file}"' in text
    assert 'terraform -chdir=deploy/runtime-v2/terraform show -json "${plan_file}"' in text
    assert '"binary_plan_github_uploaded": False' in text
    assert '"plan_json_uploaded": False' in text
    upload = text[text.index("- name: Upload non-sensitive saved-plan evidence") :]
    assert "phase3-runtime-v2.tfplan" not in upload
    assert "phase3-runtime-v2-plan.json" not in upload
    assert "phase3-apply-plan-redacted.txt" in upload
    assert "phase3-apply-plan-actions.txt" in upload
    assert "phase3-runtime-v2.receipt.json" in upload


def test_binary_plan_is_hash_bound_in_private_state_bucket_and_roundtrip_verified() -> None:
    text = _text()
    assert 'plan_uri="gs://${STATE_BUCKET}/phase3-plans/${GITHUB_SHA}/phase3-runtime-v2.tfplan"' in text
    assert 'receipt_uri="gs://${STATE_BUCKET}/phase3-plans/${GITHUB_SHA}/phase3-runtime-v2.receipt.json"' in text
    assert 'gcloud storage cp "${PLAN_FILE}" "${PLAN_URI}" --quiet' in text
    assert 'gcloud storage cp "${PLAN_URI}" "${roundtrip}" --quiet' in text
    assert 'roundtrip_sha' in text
    assert '"plan_sha256": "${plan_sha}"' in text


def test_sensitive_local_plan_material_is_deleted_after_private_storage() -> None:
    text = _text()
    assert "Delete sensitive local plan JSON and binary after storage" in text
    assert 'rm -f "${PLAN_FILE:-}" "${PLAN_JSON:-}"' in text


def test_saved_plan_self_trigger_is_one_shot_and_nonrecurring() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert '      - ".github/workflows/phase3_prepare_apply_plan.yml"' in text
    assert "schedule:" not in text
