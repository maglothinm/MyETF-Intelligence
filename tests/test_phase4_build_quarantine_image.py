from pathlib import Path


WORKFLOW = Path('.github/workflows/phase4_build_quarantine_image.yml')
CONFIG = Path('deploy/runtime-v2/cloudbuild-no-source.yaml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_phase4_build_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 4 build quarantine-safe Runtime image' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase4_build_quarantine_image.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text
    assert 'group: runtime-v2-image-build' in text
    assert 'cancel-in-progress: false' in text


def test_phase4_build_grants_only_service_account_level_actas() -> None:
    text = _text()
    assert 'gcloud builds get-default-service-account' in text
    assert '--format=\'value(serviceAccountEmail)\'' in text
    assert 'gcloud iam service-accounts add-iam-policy-binding "${default_build_service_account}"' in text
    assert '--member "serviceAccount:${BUILDER_SERVICE_ACCOUNT}"' in text
    assert '--role roles/iam.serviceAccountUser' in text
    assert 'default_build_service_account_only' in text
    assert 'unexpected project-wide Service Account User role' in text
    assert 'gcloud projects add-iam-policy-binding "${PROJECT_ID}"' not in text
    assert 'roles/iam.serviceAccountAdmin' not in text
    assert 'roles/owner' not in text
    assert 'roles/editor' not in text


def test_phase4_build_keeps_submitter_and_executor_separate() -> None:
    text = _text()
    assert 'Authenticate as constrained Phase 3 deployer' in text
    assert 'Authenticate as isolated Phase 3 builder' in text
    assert 'id: builder-auth' in text
    assert 'Refusing to collapse the isolated submitter and build-execution identities.' in text
    assert 'CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE: ${{ steps.builder-auth.outputs.credentials_file_path }}' in text
    assert 'service_account_impersonation_url' in text
    assert 'contains($account)' in text


def test_phase4_build_fetches_exact_commit_inside_no_source_build() -> None:
    text = _text()
    config = CONFIG.read_text(encoding='utf-8')
    assert 'gcloud builds submit \\' in text
    assert '--no-source' in text
    assert '--region "${REGION}"' in text
    assert '--config deploy/runtime-v2/cloudbuild-no-source.yaml' in text
    assert '_SOURCE_REVISION=${GITHUB_SHA}' in text
    assert '_SOURCE_REPOSITORY=${SOURCE_REPOSITORY}' in text
    assert 'source_staging_used: false' in text
    assert 'source_fetched_inside_build: true' in text
    assert 'git clone --filter=blob:none --no-checkout "${_SOURCE_REPOSITORY}"' in config
    assert 'git -C /workspace/repository checkout --detach FETCH_HEAD' in config


def test_phase4_build_requires_private_routing_source_and_immutable_digest() -> None:
    text = _text()
    assert 'def _use_private_ip' in text
    assert 'IPTypes.PRIVATE if _use_private_ip(config) else IPTypes.PUBLIC' in text
    assert 'sha256:[0-9a-f]{64}' in text
    assert 'CURRENT_DEPLOYED_DIGEST' in text
    assert 'phase4_quarantine_runtime_image_built' in text
    assert 'immutable_image' in text
    assert 'store_sha256' in text
    assert 'runner_sha256' in text
    assert 'migration_sha256' in text
    assert 'migrations/20260904_runtime_v2_mode_quarantine.sql' in text
    assert 'runtime_mode_evidence' in text
    assert 'legacy_unverified' in text
    assert 'runtime_job_runs_success_snapshot' in text
    assert 'OBSOLETE_HARDENED_DIGEST' in text
    assert 'sha256:310e1042c7fe3e87a996eb0eaa676b6b3abcae0e909cb5e49f6c638935ac12a7' in text


def test_phase4_build_performs_no_deployment_or_runtime_execution() -> None:
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
    assert 'production_authority_transferred: false' in text
    assert 'phase4_started: true' in text
    assert 'phase4_producer_execution: false' in text
