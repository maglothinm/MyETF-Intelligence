from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_finalize_readiness.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_finalizer_is_self_path_scoped_to_canonical_main():
    text = _text()
    assert 'name: Phase 3 finalize readiness' in text
    assert '".github/workflows/phase3_finalize_readiness.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_finalizer_never_runs_a_runtime_producer_or_scheduler():
    text = _text()
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert '--args=-m,runtime_v2,status' in text
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/run.invoker' not in text


def test_finalizer_reconciles_only_private_ip_environment_drift():
    text = _text()
    assert '--update-env-vars=PRIVATE_IP=true' in text
    assert 'gcloud run jobs update "${job}"' in text
    assert 'gcloud run services update "${WEB_SERVICE}"' in text
    assert 'gcloud run jobs deploy' not in text
    assert 'gcloud run deploy' not in text
    assert 'gcloud sql instances patch' not in text
    assert 'terraform apply' not in text
    assert 'Admin command changed during reconciliation.' in text
    assert 'Admin args changed during reconciliation.' in text


def test_finalizer_is_one_shot_and_keeps_phase3_inert():
    text = _text()
    assert 'ONESHOT_MARKER: phase3-acceptance/finalize-readiness-v1.claimed' in text
    assert 'gcloud storage ls "${marker_uri}"' in text
    assert 'gcloud storage cp oneshot-marker.txt "${marker_uri}"' in text
    for name in (
        'polititrack-legislative',
        'polititrack-executive',
        'polititrack-ai',
        'polititrack-dashboard',
        'polititrack-vault-lifecycle',
    ):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text


def test_finalizer_uses_temporary_log_and_execution_access_with_cleanup():
    text = _text()
    assert 'trap cleanup_temporary_access EXIT' in text
    assert 'gcloud logging views add-iam-policy-binding "${LOG_VIEW}"' in text
    assert 'gcloud logging views remove-iam-policy-binding "${LOG_VIEW}"' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'roles/logging.admin' in text
    assert 'Temporary admin execution authority remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view accessor remains.' in text


def test_finalizer_requires_private_cloud_boundary_and_nonpublic_web():
    text = _text()
    assert '.settings.ipConfiguration.ipv4Enabled == false' in text
    assert '.type == "PRIVATE"' in text
    assert 'allUsers' in text
    assert 'Runtime v2 web service has public allUsers access.' in text


def test_finalizer_uses_canonical_status_validator_and_durable_receipt():
    text = _text()
    assert 'validate_phase3_status.py' in text
    assert '--status status.json' in text
    assert 'ACCEPTANCE_OBJECT: phase3-acceptance/final/phase3-acceptance.json' in text
    assert 'gcloud storage cp phase3-acceptance.json "${acceptance_uri}"' in text
    assert 'Private acceptance receipt round-trip digest mismatch.' in text
    assert "'private_ip_environment_reconciled': True" in text
