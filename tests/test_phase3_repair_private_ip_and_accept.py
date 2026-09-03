from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_repair_private_ip_and_accept.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_repair_gate_is_self_path_scoped_to_canonical_main() -> None:
    text = _text()
    assert 'name: Phase 3 repair private IP and accept' in text
    assert '".github/workflows/phase3_repair_private_ip_and_accept.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'ONESHOT_MARKER: phase3-acceptance/private-ip-repair-v1.claimed' in text


def test_repair_gate_only_updates_admin_private_ip() -> None:
    text = _text()
    assert 'gcloud run jobs update "${ADMIN_JOB}"' in text
    assert '--update-env-vars=PRIVATE_IP=true' in text
    assert '--set-env-vars' not in text
    assert 'Admin command or args changed during private-IP repair.' in text
    assert 'Admin image or execution identity changed during repair.' in text
    assert 'Admin VPC attachment changed during repair.' in text
    assert 'Unexpected admin environment-name drift during repair.' in text


def test_repair_gate_never_runs_producers_or_scheduler() -> None:
    text = _text()
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert '--args=-m,runtime_v2,status' in text
    for producer in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert producer in text
    assert '[[ "${state}" == "PAUSED" ]]' in text


def test_repair_gate_uses_temporary_scoped_execution_and_logging_access() -> None:
    text = _text()
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'cleanup_temporary_access' in text
    assert 'trap cleanup_temporary_access EXIT' in text
    assert 'Temporary execution authority remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view access remains.' in text


def test_repair_gate_validates_exact_phase3_status_and_infrastructure() -> None:
    text = _text()
    assert 'validate_phase3_status.py' in text
    assert 'phase3-acceptance.json' in text
    assert 'PRIVATE_IP=true' in text
    assert 'Cloud SQL is not private-only.' in text
    assert 'Runtime v2 web service is public.' in text
    assert "any(.status.conditions[]?; .type == \"Completed\" and .status == \"True\")" in text
