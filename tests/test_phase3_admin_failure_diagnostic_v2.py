from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_admin_failure_diagnostic_v2.yml')


def test_v2_diagnostic_is_new_self_path_scoped_main_push():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'name: Phase 3 admin failure diagnostic v2' in text
    assert 'push:' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_admin_failure_diagnostic_v2.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text


def test_v2_diagnostic_never_executes_runtime_or_scheduler():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'gcloud run jobs execute' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'import-gcs' not in text
    assert 'runtime_v2,run' not in text


def test_v2_diagnostic_is_one_shot_and_only_reads_known_failed_execution():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'FAILED_EXECUTION: polititrack-admin-snrjx' in text
    assert 'ONESHOT_MARKER: phase3-diagnostics/admin-failure-v4.claimed' in text
    assert 'gcloud storage ls "${marker_uri}"' in text
    assert 'gcloud storage cp oneshot-marker.txt "${marker_uri}"' in text
    assert 'gcloud run jobs executions describe "${FAILED_EXECUTION}"' in text
    assert 'gcloud logging read' in text


def test_v2_diagnostic_restores_known_admin_baseline_only():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "'[\"-m\",\"runtime_v2\",\"status\"]'" in text
    assert '--args=-m,runtime_v2,init-db,--with-vault' in text
    assert 'Admin job is not at the Terraform Phase 3 baseline.' in text


def test_v2_diagnostic_log_permissions_are_temporary_and_schedulers_stay_paused():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'roles/logging.viewer' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'cleanup_logging' in text
    assert 'Temporary ${role} binding remains after diagnostic cleanup.' in text
    for name in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
