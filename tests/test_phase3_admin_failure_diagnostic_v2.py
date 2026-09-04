from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_admin_failure_diagnostic_v2.yml')


def test_v2_diagnostic_is_new_self_path_scoped_main_push():
    text = WORKFLOW.read_text(encoding='utf-8')
    trigger = text.split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in trigger
    assert 'push:' not in trigger
    assert 'group: runtime-v2-live-controller' in text
    assert 'name: Phase 3 admin failure diagnostic v2' in text
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
    assert 'ONESHOT_MARKER: phase3-diagnostics/admin-failure-v6.claimed' in text
    assert 'gcloud storage ls "${marker_uri}"' in text
    assert 'gcloud storage cp oneshot-marker.txt "${marker_uri}"' in text
    assert 'gcloud run jobs executions describe "${FAILED_EXECUTION}"' in text
    assert 'gcloud logging read' in text


def test_v2_diagnostic_restores_known_admin_baseline_only():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "'[\"-m\",\"runtime_v2\",\"status\"]'" in text
    assert '--args=-m,runtime_v2,init-db,--with-vault' in text
    assert 'Admin job is not at the Terraform Phase 3 baseline.' in text


def test_v2_diagnostic_uses_direct_default_view_binding_and_cleans_it_up():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'LOG_BUCKET: _Default' in text
    assert 'LOG_VIEW: _Default' in text
    assert 'LOG_LOCATION: global' in text
    assert 'roles/logging.admin' in text
    assert 'gcloud logging views add-iam-policy-binding "${LOG_VIEW}"' in text
    assert 'gcloud logging views remove-iam-policy-binding "${LOG_VIEW}"' in text
    assert '--role roles/logging.viewAccessor' in text
    assert 'Temporary roles/logging.admin binding remains after diagnostic cleanup.' in text
    assert 'Temporary log-view accessor binding remains after diagnostic cleanup.' in text


def test_v2_diagnostic_bounds_iam_propagation_retry():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'log_read_ok=false' in text
    assert 'for attempt in $(seq 1 12)' in text
    assert 'attempt ${attempt}/12' in text
    assert 'sleep 10' in text
    assert 'Cloud Logging access did not propagate within the bounded diagnostic window.' in text


def test_v2_diagnostic_log_permissions_are_temporary_and_schedulers_stay_paused():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'cleanup_logging' in text
    assert 'trap cleanup_logging EXIT' in text
    assert 'trap - EXIT' in text
    for name in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
