from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_runtime_image_routing_diagnostic.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_diagnostic_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 Runtime image routing diagnostic' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_runtime_image_routing_diagnostic.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_diagnostic_executes_only_python_introspection() -> None:
    text = _text()
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert '--args="-c,${diagnostic_code}"' in text
    assert 'USE_PRIVATE=' in text
    assert 'DATABASE_SHA256=' in text
    assert 'CONNECTOR_VERSION=' in text
    assert 'PRIVATE_VALUE=' in text
    assert 'PUBLIC_VALUE=' in text
    assert 'runtime_v2,status' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'secrets versions access' not in text


def test_diagnostic_never_outputs_secret_values() -> None:
    text = _text()
    assert 'DB_PASSWORD=' not in text
    assert 'DATABASE_URL=' not in text
    assert 'secretKeyRef' not in text
    assert 'secrets versions access' not in text


def test_temporary_execution_and_logging_roles_are_removed() -> None:
    text = _text()
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'trap cleanup EXIT' in text
    assert 'Temporary admin execution authority remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view accessor remains.' in text


def test_persistent_admin_job_and_schedulers_remain_unchanged() -> None:
    text = _text()
    assert 'Unexpected admin command baseline.' in text
    assert 'Unexpected admin argument baseline.' in text
    assert 'Admin PRIVATE_IP is not true before image diagnostic.' in text
    assert 'Admin command changed after diagnostic override.' in text
    assert 'Admin args changed after diagnostic override.' in text
    assert 'Admin PRIVATE_IP changed after image diagnostic.' in text
    for name in (
        'polititrack-legislative',
        'polititrack-executive',
        'polititrack-ai',
        'polititrack-dashboard',
        'polititrack-vault-lifecycle',
    ):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
