from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_build_current_runtime_image.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_build_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 build current Runtime image' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_build_current_runtime_image.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_build_reconciles_only_intended_builder_project_and_bucket_roles() -> None:
    text = _text()
    assert 'DEPLOYER_SERVICE_ACCOUNT: polititrack-phase3-deployer@' in text
    assert 'CLOUD_BUILD_BUCKET: project-38008d5f-4918-46e6-920_cloudbuild' in text
    for role in (
        'roles/cloudbuild.builds.editor',
        'roles/serviceusage.serviceUsageConsumer',
        'roles/serviceusage.serviceUsageViewer',
        'roles/storage.objectAdmin',
        'roles/storage.bucketViewer',
    ):
        assert role in text
    assert 'gcloud projects add-iam-policy-binding "${PROJECT_ID}"' in text
    assert 'gcloud storage buckets add-iam-policy-binding "gs://${CLOUD_BUILD_BUCKET}"' in text
    assert '--member "serviceAccount:${BUILDER_SERVICE_ACCOUNT}"' in text
    assert 'roles/storage.admin' not in text
    assert 'roles/owner' not in text
    assert "'roles/editor'" not in text


def test_build_pins_commands_to_builder_auth_output() -> None:
    text = _text()
    assert 'id: builder-auth' in text
    assert 'CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE: ${{ steps.builder-auth.outputs.credentials_file_path }}' in text
    assert 'GOOGLE_APPLICATION_CREDENTIALS: ${{ steps.builder-auth.outputs.credentials_file_path }}' in text
    assert 'GOOGLE_GHA_CREDS_PATH: ${{ steps.builder-auth.outputs.credentials_file_path }}' in text
    assert 'credential_file="${CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE}"' in text
    assert 'service_account_impersonation_url' in text
    assert 'contains($account)' in text
    assert 'The active credential file does not impersonate the isolated Phase 3 builder.' in text
    assert 'gcloud auth list' not in text
    assert 'builder_credentials_pinned: true' in text


def test_build_waits_until_builder_permissions_are_effective() -> None:
    text = _text()
    assert 'for attempt in $(seq 1 18)' in text
    assert 'gcloud storage buckets describe "gs://${CLOUD_BUILD_BUCKET}"' in text
    assert 'gcloud storage ls "gs://${CLOUD_BUILD_BUCKET}" --limit=1' in text
    assert 'gcloud services list --enabled --project "${PROJECT_ID}" --limit=1' in text
    assert 'gcloud builds list --project "${PROJECT_ID}" --limit=1' in text
    assert 'Builder permissions did not become effective within the bounded readiness window.' in text


def test_build_uses_isolated_builder_and_immutable_digest() -> None:
    text = _text()
    assert 'Authenticate as isolated Phase 3 builder' in text
    assert 'polititrack-phase3-builder@' in text
    assert 'gcloud builds submit .' in text
    assert '--config deploy/runtime-v2/cloudbuild.yaml' in text
    assert 'gcloud artifacts docker images describe' in text
    assert 'sha256:[0-9a-f]{64}' in text
    assert 'immutable_image' in text
    assert 'phase3_current_runtime_image_built' in text


def test_build_requires_private_routing_source() -> None:
    text = _text()
    assert 'def _use_private_ip' in text
    assert 'IPTypes.PRIVATE if _use_private_ip(config) else IPTypes.PUBLIC' in text
    assert 'Current source lacks private Cloud SQL routing' in text


def test_build_performs_no_deployment_or_runtime_execution() -> None:
    text = _text()
    forbidden = (
        'gcloud run jobs update',
        'gcloud run services update',
        'gcloud run deploy',
        'gcloud run jobs execute',
        'terraform apply',
        'gcloud scheduler jobs run',
        'gcloud scheduler jobs resume',
        'gcloud scheduler jobs enable',
        'secrets versions access',
    )
    for value in forbidden:
        assert value not in text
    assert 'deployed: false' in text
    assert 'runtime_job_execution: false' in text
    assert 'scheduler_execution: false' in text
    assert 'phase4_started: false' in text
