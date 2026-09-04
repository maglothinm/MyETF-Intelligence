from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_reconcile_private_ip_acceptance.yml')
TERRAFORM = Path('deploy/runtime-v2/terraform/main.tf')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_workflow_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    trigger = text.split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in trigger
    assert 'push:' not in trigger
    assert 'group: runtime-v2-live-controller' in text
    assert 'name: Phase 3 reconcile private IP and accept' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_reconciliation_changes_only_admin_private_ip_setting() -> None:
    text = _text()
    assert 'gcloud run jobs update "${ADMIN_JOB}"' in text
    assert '--update-env-vars PRIVATE_IP=true' in text
    assert 'Admin command or arguments changed during PRIVATE_IP reconciliation.' in text
    assert "for key in ('image', 'service_account', 'network', 'subnetwork')" in text
    assert "f'Admin {key} changed during PRIVATE_IP reconciliation.'" in text
    assert 'gcloud run jobs update polititrack-legislative' not in text
    assert 'gcloud run jobs update polititrack-executive' not in text
    assert 'gcloud run jobs update polititrack-ai' not in text
    assert 'gcloud run jobs update polititrack-dashboard' not in text


def test_only_admin_read_only_status_execution_is_allowed() -> None:
    text = _text()
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert '--args=-m,runtime_v2,status' in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'gcloud scheduler jobs enable' not in text
    assert 'secrets versions access' not in text


def test_temporary_execution_and_logging_authority_are_removed() -> None:
    text = _text()
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'trap cleanup_temporary_access EXIT' in text
    assert 'Temporary admin execution authority remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view accessor remains.' in text
    assert "'temporary_execution_authority_removed': True" in text
    assert "'temporary_logging_authority_removed': True" in text


def test_phase3_inert_and_private_boundaries_are_rechecked() -> None:
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
    assert "'phase4_started': False" in text
    assert "'production_authority_transferred': False" in text


def test_terraform_declares_admin_private_ip_true() -> None:
    text = TERRAFORM.read_text(encoding='utf-8')
    admin = text.split('resource "google_cloud_run_v2_job" "admin"', 1)[1].split(
        'resource "google_cloud_run_v2_job" "import"', 1
    )[0]
    assert 'name  = "PRIVATE_IP"' in admin
    assert 'value = "true"' in admin
