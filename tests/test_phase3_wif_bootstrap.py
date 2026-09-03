from pathlib import Path

SCRIPT = Path("deploy/runtime-v2/initialize-github-wif.ps1")


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_wif_bootstrap_defaults_to_nonmutating_preflight() -> None:
    text = _text()
    apply_gate = text.index("if (-not $Apply)")
    assert "[switch]$Apply" in text
    for mutation in (
        "@('services','enable')",
        "'workload-identity-pools','create'",
        "'providers','create-oidc'",
        "'projects','add-iam-policy-binding'",
    ):
        assert text.index(mutation) > apply_gate
    assert "No Google Cloud resource or IAM policy was changed" in text


def test_wif_bootstrap_pins_immutable_ids_and_main_ref() -> None:
    text = _text()
    assert "[string]$ProjectNumber = '497412818801'" in text
    assert "$ExpectedRepositoryId = '1349678672'" in text
    assert "$ExpectedRepositoryOwnerId = '225069210'" in text
    assert "$ExpectedRef = 'refs/heads/main'" in text
    assert "& $gcloud projects describe $ProjectNumber" in text
    assert "$resolvedProjectNumber -ne $ProjectNumber" in text


def test_wif_provider_restricts_admission() -> None:
    text = _text()
    assert "assertion.repository_id == '$ExpectedRepositoryId'" in text
    assert "assertion.repository_owner_id == '$ExpectedRepositoryOwnerId'" in text
    assert "assertion.ref == '$ExpectedRef'" in text
    assert "attribute.repository_id=assertion.repository_id" in text
    assert "attribute.repository_owner_id=assertion.repository_owner_id" in text
    assert "attribute.ref=assertion.ref" in text
    assert "https://token.actions.githubusercontent.com/" in text


def test_wif_bootstrap_is_direct_and_has_no_keys_or_secret_payload_access() -> None:
    text = _text().lower()
    assert "service-accounts" not in text
    assert "serviceaccount:" not in text
    assert "keys create" not in text
    assert "credentials_json" not in text
    assert "secrets versions access" not in text
    assert "secretmanager.secretaccessor" not in text
    assert "direct federation" in text


def test_wif_bootstrap_grants_only_expected_read_only_discovery_roles() -> None:
    text = _text()
    for role in (
        "roles/serviceusage.serviceUsageViewer", "roles/artifactregistry.viewer",
        "roles/storage.bucketViewer", "roles/cloudsql.viewer",
        "roles/compute.networkViewer", "roles/iam.securityReviewer",
        "roles/iam.workloadIdentityPoolViewer", "roles/secretmanager.viewer",
        "roles/run.viewer", "roles/cloudscheduler.viewer",
    ):
        assert role in text
    for role in (
        "roles/owner", "roles/editor", "roles/iam.serviceAccountTokenCreator",
        "roles/iam.workloadIdentityUser", "roles/secretmanager.secretAccessor",
        "roles/run.invoker", "roles/run.admin", "roles/storage.admin",
        "roles/cloudsql.admin", "roles/compute.admin",
        "roles/serviceusage.serviceUsageAdmin",
    ):
        assert role not in text


def test_wif_bootstrap_binds_roles_to_repository_principal_set() -> None:
    text = _text()
    assert "principalSet://iam.googleapis.com/$poolResource/attribute.repository_id/$ExpectedRepositoryId" in text
    assert "'--member',$principalSet" in text
