from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_harvest_current_status.yml')
VALIDATOR = Path('deploy/runtime-v2/validate_phase3_status.py')


def test_harvest_is_self_path_scoped_and_one_shot():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'name: Phase 3 harvest current status' in text
    assert 'push:' in text and '- main' in text
    assert '".github/workflows/phase3_harvest_current_status.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert 'ONESHOT_MARKER: phase3-acceptance/harvest-current-status-v1.claimed' in text


def test_harvest_never_executes_or_updates_a_runtime_job():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'gcloud run jobs execute' not in text
    assert 'gcloud run jobs update' not in text
    assert 'roles/run.jobsExecutorWithOverrides' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text


def test_harvest_requires_existing_current_status_execution():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "status.latestCreatedExecution.name" in text
    assert 'gcloud run jobs executions describe "${status_execution}"' in text
    assert "'[\"-m\",\"runtime_v2\",\"status\"]'" in text
    assert '2026-09-03T18:08:00Z' in text
    assert '.type == "Completed" and .status == "True"' in text


def test_harvest_removes_temporary_logging_access_and_keeps_schedulers_paused():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'cleanup_logging' in text
    assert 'trap cleanup_logging EXIT' in text
    assert 'Temporary log-view accessor remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    for name in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text


def test_harvest_rechecks_private_sql_and_nonpublic_web():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'Cloud SQL is not private-only with a private address.' in text
    assert 'Runtime v2 web service has public allUsers access.' in text


def test_validator_contains_exact_phase3_sources_and_phase4_stop():
    text = VALIDATOR.read_text(encoding='utf-8')
    compile(text, str(VALIDATOR), 'exec')
    for value in ('33723283663', '100546743583', '9881049089',
                  '33723462162', '100547268592', '9881124215',
                  '33579058808', '100089268533', '9827727750'):
        assert value in text
    assert 'github_actions_migration' in text
    assert 'dashboard generation is not 1' in text
    assert 'dashboard generation 1 was not created in shadow mode' in text
    assert 'Runtime v2 producer run exists for' in text
    assert 'simulation durable head exists during Phase 3' in text
    assert '"phase4_started": False' in text
    assert '"production_authority_transferred": False' in text
    assert '"temporary_execution_authority_granted": False' in text
