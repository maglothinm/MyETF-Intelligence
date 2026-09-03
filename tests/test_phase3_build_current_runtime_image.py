from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_build_current_runtime_image.yml')
CONFIG = Path('deploy/runtime-v2/cloudbuild-no-source.yaml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_build_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 build current Runtime image' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_build_current_runtime_image.yml"' in text
    assert '"deploy/runtime-v2/cloudbuild-no-source.yaml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_build_reconciles_only_intended_builder_project_roles() -> None:
    text = _text()
    assert 'DEPLOYER_SERVICE_ACCOUNT: polititrack-phase3-deployer@' in text
    for role in (
        'roles/cloudbuild.builds.editor',
        'roles/serviceusage.serviceUsageConsumer',
        'roles/serviceusage.serviceUsageViewer',
    ):
        assert role in text
    assert 'gcloud projects add-iam-policy-binding "${PROJECT_ID}"' in text
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


def test_build_bypasses_source_staging_and_fetches_exact_commit_inside_build() -> None:
    text = _text()
    config = CONFIG.read_text(encoding='utf-8')
    assert 'gcloud builds submit \\' in text
    assert '--no-source' in text
    assert '--config deploy/runtime-v2/cloudbuild-no-source.yaml' in text
    assert '_SOURCE_REVISION=${GITHUB_SHA}' in text
    assert '_SOURCE_REPOSITORY=${SOURCE_REPOSITORY}' in text
    assert 'source_staging_used: false' in text
    assert 'source_fetched_inside_build: true' in text
    assert 'gcloud builds submit .' not in text
    assert 'git clone --filter=blob:none --no-checkout "${_SOURCE_REPOSITORY}"' in config
    assert 'git -C /workspace/repository fetch --depth=1 origin "${_SOURCE_REVISION}"' in config
    assert 'git -C /workspace/repository checkout --detach FETCH_HEAD' in config
    assert 'test "$(git -C /workspace/repository rev-parse HEAD)" = "${_SOURCE_REVISION}"' in config


def test_build_waits_for_project_permissions_only() -> None:
    text = _text()
    assert 'for attempt in $(seq 1 18)' in text
    assert 'gcloud services list --enabled --project "${PROJECT_ID}" --limit=1' in text
    assert 'gcloud builds list --project "${PROJECT_ID}" --limit=1' in text
    assert 'gcloud storage ls' not in text
    assert 'gcloud storage buckets describe' not in text
    assert 'Builder project permissions did not become effective within the bounded readiness window.' in text


def test_build_uses_isolated_builder_and_immutable_digest() -> None:
    text = _text()
    assert 'Authenticate as isolated Phase 3 builder' in text
    assert 'polititrack-phase3-builder@' in text
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
