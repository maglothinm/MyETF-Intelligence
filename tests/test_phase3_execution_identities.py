from pathlib import Path


SCRIPT = Path("deploy/runtime-v2/initialize-phase3-execution-identities.ps1")


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _terraform_permissions_block(text: str) -> str:
    start = text.index("$terraformPermissions = @(")
    end = text.index("\n)\n\n$forbiddenTerraformPermissions", start) + 2
    return text[start:end]


def test_execution_identity_bootstrap_defaults_to_preflight_only() -> None:
    text = _text()
    apply_gate = text.index("if (-not $Apply)")
    apply_body = text[apply_gate:]
    assert "[switch]$Apply" in text
    assert "exit 0" in text[apply_gate : text.index("$servicesToEnable", apply_gate)]
    assert "Invoke-Checked $gcloud (@('services', 'enable')" in apply_body
    assert "Ensure-ServiceAccount $projectId $DeployerServiceAccountId" in apply_body
    assert "Ensure-ServiceAccount $projectId $BuilderServiceAccountId" in apply_body
    assert "'iam', 'roles', 'create'" in apply_body
    assert "'storage', 'buckets', 'add-iam-policy-binding'" in apply_body
    assert "'artifacts', 'repositories', 'add-iam-policy-binding'" in apply_body
    assert "Preflight only. No service account, IAM binding, custom role, or API state was changed." in text


def test_execution_identity_bootstrap_pins_live_wif_boundary() -> None:
    text = _text()
    assert "[string]$ProjectNumber = '497412818801'" in text
    assert "[string]$PoolId = 'polititrack-github-phase3'" in text
    assert "[string]$ProviderId = 'phase3-main'" in text
    assert "$ExpectedRepositoryId = '1349678672'" in text
    assert "$ExpectedRepositoryOwnerId = '225069210'" in text
    assert "$ExpectedRef = 'refs/heads/main'" in text
    assert "$provider.state -ne 'ACTIVE'" in text
    assert "$provider.attributeCondition -ne $expectedCondition" in text


def test_deployer_and_builder_are_separate_keyless_identities() -> None:
    text = _text()
    assert "polititrack-phase3-deployer" in text
    assert "polititrack-phase3-builder" in text
    assert "roles/iam.workloadIdentityUser" in text
    assert "keys create" not in text.lower()
    assert "credentials_json" not in text.lower()
    assert "builder_terraform_authority=false" in text


def test_custom_terraform_role_excludes_execution_secret_access_and_destroy() -> None:
    permissions = _terraform_permissions_block(_text())
    forbidden = (
        "secretmanager.versions.access",
        "run.jobs.run",
        "run.jobs.runWithOverrides",
        "run.routes.invoke",
        "cloudscheduler.jobs.run",
        "cloudscheduler.jobs.enable",
        "run.jobs.delete",
        "run.services.delete",
        "cloudscheduler.jobs.delete",
        "secretmanager.secrets.delete",
        "secretmanager.versions.destroy",
        "storage.buckets.delete",
    )
    for permission in forbidden:
        assert permission not in permissions


def test_custom_terraform_role_contains_required_nonexecution_control_permissions() -> None:
    permissions = _terraform_permissions_block(_text())
    required = (
        "serviceusage.services.enable",
        "storage.buckets.setIamPolicy",
        "secretmanager.secrets.setIamPolicy",
        "secretmanager.versions.add",
        "run.jobs.create",
        "run.jobs.update",
        "run.jobs.setIamPolicy",
        "run.services.create",
        "run.services.update",
        "run.services.setIamPolicy",
        "cloudscheduler.jobs.create",
        "cloudscheduler.jobs.update",
        "cloudscheduler.jobs.pause",
    )
    for permission in required:
        assert permission in permissions


def test_deployer_uses_service_specific_infrastructure_roles_not_owner_editor() -> None:
    text = _text()
    for role in (
        "roles/compute.networkAdmin",
        "roles/servicenetworking.networksAdmin",
        "roles/cloudsql.admin",
        "roles/iam.serviceAccountAdmin",
        "roles/iam.serviceAccountUser",
        "roles/resourcemanager.projectIamAdmin",
    ):
        assert role in text
    assert "'roles/owner'" not in text
    assert "'roles/editor'" not in text
    assert "'roles/run.admin'" not in text
    assert "'roles/cloudscheduler.admin'" not in text
    assert "'roles/secretmanager.admin'" not in text


def test_builder_only_receives_build_and_read_support_roles() -> None:
    text = _text()
    assert "roles/cloudbuild.builds.editor" in text
    assert "roles/serviceusage.serviceUsageConsumer" in text
    assert "roles/artifactregistry.reader" in text
    assert '"serviceAccount:$builderEmail" $terraformRoleName' not in text
    assert '"serviceAccount:$builderEmail" \'roles/cloudsql.admin\'' not in text


def test_only_missing_network_apis_are_enabled() -> None:
    text = _text()
    assert "gcloud services list --enabled" in text
    assert "'compute.googleapis.com' -in $enabledServices" in text
    assert "'servicenetworking.googleapis.com' -in $enabledServices" in text
    assert "$servicesToEnable" in text
    assert "cloudbilling.googleapis.com" not in text


def test_state_and_build_object_access_are_bucket_scoped() -> None:
    text = _text()
    assert '"gs://$stateBucket"' in text
    assert '"gs://$cloudBuildBucket"' in text
    assert "roles/storage.objectAdmin" in text
    assert "roles/storage.admin" not in text
