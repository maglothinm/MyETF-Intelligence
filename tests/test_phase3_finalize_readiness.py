from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_finalize_readiness.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_finalizer_is_canonical_main_only_and_one_shot() -> None:
    text = _text()
    assert 'name: Phase 3 finalize readiness' in text
    assert '".github/workflows/phase3_finalize_readiness.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'CLAIM_OBJECT: phase3-acceptance/finalize-readiness-v2.claimed' in text
    assert 'READY_OBJECT: phase3-acceptance/PHASE3_READY.json' in text


def test_finalizer_repairs_only_private_ip_and_preserves_job_shape() -> None:
    text = _text()
    assert '--update-env-vars=PRIVATE_IP=true' in text
    assert '--set-env-vars' not in text
    assert 'command or args changed.' in text
    assert 'image or identity changed.' in text
    assert 'VPC attachment changed.' in text
    assert 'environment-name set changed unexpectedly.' in text
    for job in (
        'polititrack-admin', 'polititrack-legislative', 'polititrack-executive',
        'polititrack-ai', 'polititrack-dashboard', 'polititrack-import-legislative',
        'polititrack-import-executive', 'polititrack-import-ai',
    ):
        assert job in text


def test_finalizer_keeps_producers_shadow_and_schedulers_paused() -> None:
    text = _text()
    assert 'POLITITRACK_MODE' in text
    assert '[[ "${mode}" == "shadow" ]]' in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert '[[ "${state}" == "PAUSED" ]]' in text


def test_finalizer_executes_only_read_only_admin_status_probe() -> None:
    text = _text()
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert '--args=-m,runtime_v2,status' in text
    assert '--update-env-vars=PRIVATE_IP=true' in text
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'Status execution did not use private routing.' in text
    assert 'Current private-route status execution failed.' in text


def test_finalizer_cleans_temporary_access_before_acceptance() -> None:
    text = _text()
    assert 'cleanup_temporary_access' in text
    assert 'trap cleanup_temporary_access EXIT' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'Temporary log-view access remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary execution authority remains.' in text


def test_finalizer_uses_existing_exact_validator_and_private_receipt() -> None:
    text = _text()
    assert 'validate_phase3_status.py' in text
    assert '--status status.json' in text
    assert 'PHASE3_READY.json' in text
    assert 'gcloud storage cp PHASE3_READY.json "${ready_uri}"' in text
    assert 'Private readiness receipt round trip changed.' in text
    assert "'phase4_producer_jobs_shadow': True" in text
    assert "'all_runtime_jobs_private_ip': True" in text
    assert 'READY_BRANCH: phase3-ready' in text


def test_finalizer_never_reads_secret_payloads_or_transfers_production() -> None:
    text = _text()
    assert 'secrets versions access' not in text
    assert 'secretmanager.versions.access' not in text
    assert 'POLITITRACK_MODE=production' not in text
    assert 'production_authority_transferred' not in text or 'validate_phase3_status.py' in text
    assert 'allUsers' in text
    assert 'Runtime v2 web service is public.' in text
