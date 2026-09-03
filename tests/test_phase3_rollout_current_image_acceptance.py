import json
from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_rollout_current_image_acceptance.yml')
VARS = Path('deploy/runtime-v2/phase3-reconciliation.tfvars.json')
DIGEST = 'sha256:b9758a697338ffdeb7505473819aec70247ac23ed46b15af5b78701ed1f61f9b'
REVISION = '080a3df0f0b912f702a30148cedc831b833a81db'


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_rollout_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 rollout current image and accept' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_rollout_current_image_acceptance.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_canonical_tfvars_are_pinned_to_fresh_immutable_image() -> None:
    config = json.loads(VARS.read_text(encoding='utf-8'))
    assert config['image'].endswith('@' + DIGEST)
    assert config['runtime_environment']['SOURCE_REVISION'] == REVISION
    assert config['runtime_environment']['POLITITRACK_MODE'] == 'shadow'
    assert config['schedules_enabled'] is False
    assert config['public_dashboard_enabled'] is False


def test_rollout_verifies_exact_successful_build_and_digest() -> None:
    text = _text()
    assert 'BUILD_ID: 1db569db-57a1-46fe-a061-0547ac6779b2' in text
    assert f'BUILD_SOURCE_REVISION: {REVISION}' in text
    assert f'IMAGE_DIGEST: {DIGEST}' in text
    assert 'gcloud builds describe "${BUILD_ID}"' in text
    assert '.status == "SUCCESS" and .substitutions._SOURCE_REVISION == $source' in text
    assert 'Pinned Artifact Registry digest does not resolve exactly.' in text


def test_terraform_plan_is_exactly_update_only_on_ten_runtime_resources() -> None:
    text = _text()
    expected = (
        'google_cloud_run_v2_job.admin',
        'google_cloud_run_v2_job.import[\\"ai\\"]',
        'google_cloud_run_v2_job.import[\\"executive\\"]',
        'google_cloud_run_v2_job.import[\\"legislative\\"]',
        'google_cloud_run_v2_job.producer[\\"ai\\"]',
        'google_cloud_run_v2_job.producer[\\"dashboard\\"]',
        'google_cloud_run_v2_job.producer[\\"executive\\"]',
        'google_cloud_run_v2_job.producer[\\"legislative\\"]',
        'google_cloud_run_v2_job.vault_lifecycle[0]',
        'google_cloud_run_v2_service.web',
    )
    for address in expected:
        assert address in text
    assert "if actions != ['update']" in text
    assert 'Image rollout address mismatch.' in text
    assert 'scheduler_changes' in text and 'database_changes' in text
    assert 'iam_changes' in text and 'secret_changes' in text
    assert 'terraform_changed_resources' in text and ': 10' in text


def test_exact_binary_plan_is_hashed_before_apply() -> None:
    text = _text()
    assert 'terraform -chdir=deploy/runtime-v2/terraform plan' in text
    assert '-out="${plan_file}"' in text
    assert 'terraform -chdir=deploy/runtime-v2/terraform show -json' in text
    assert 'live_sha="$(sha256sum "${PLAN_FILE}"' in text
    assert '[[ "${live_sha}" == "${PLAN_SHA}" ]]' in text
    assert 'terraform -chdir=deploy/runtime-v2/terraform apply' in text
    assert '"${PLAN_FILE}"' in text
    assert 'terraform plan' not in text.split('Apply the exact machine-approved binary plan', 1)[1]


def test_only_admin_status_is_executed_and_schedulers_never_run() -> None:
    text = _text()
    assert text.count('gcloud run jobs execute') == 1
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert '--args=-m,runtime_v2,status' in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'gcloud scheduler jobs enable' not in text
    assert 'secrets versions access' not in text


def test_temporary_status_authority_is_removed_and_verified() -> None:
    text = _text()
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'trap cleanup_temporary_access EXIT' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view accessor remains.' in text
    assert 'Temporary admin execution authority remains.' in text
    assert "'temporary_execution_authority_removed': True" in text
    assert "'temporary_logging_authority_removed': True" in text


def test_final_acceptance_preserves_shadow_private_inert_boundaries() -> None:
    text = _text()
    for name in (
        'polititrack-legislative',
        'polititrack-executive',
        'polititrack-ai',
        'polititrack-dashboard',
        'polititrack-vault-lifecycle',
    ):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
    assert '.settings.ipConfiguration.ipv4Enabled == false' in text
    assert '.type == "PRIVATE"' in text
    assert 'any(. == "allUsers")' in text
    assert 'validate_phase3_status.py' in text
    assert "'runtime_job_execution': False" in text
    assert "'scheduler_execution': False" in text
    assert "'production_authority_transferred': False" in text
    assert "'phase4_started': False" in text
    assert 'phase3-acceptance/final-${GITHUB_RUN_ID}.json' in text
