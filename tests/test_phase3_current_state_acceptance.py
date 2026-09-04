from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_current_state_acceptance.yml')


def test_acceptance_is_self_path_scoped_main_one_shot():
    text = WORKFLOW.read_text(encoding='utf-8')
    trigger = text.split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in trigger
    assert 'push:' not in trigger
    assert 'group: runtime-v2-live-controller' in text
    assert 'name: Phase 3 current state acceptance' in text
    assert "github.repository_id == '1349678672'" in text
    assert 'ONESHOT_MARKER: phase3-acceptance/current-state-v1.claimed' in text


def test_acceptance_only_runs_admin_status_with_execution_override():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert '--args=-m,runtime_v2,status' in text
    assert 'gcloud run jobs update' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text


def test_acceptance_temporary_permissions_are_removed_and_verified():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'cleanup_all' in text
    assert 'trap cleanup_all EXIT' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'gcloud logging views remove-iam-policy-binding' in text
    assert 'gcloud run jobs remove-iam-policy-binding' in text
    assert 'Temporary admin execution authority remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view accessor remains.' in text


def test_acceptance_requires_exact_generation_one_sources():
    text = WORKFLOW.read_text(encoding='utf-8')
    for value in ('33723283663', '100546743583', '9881049089',
                  '33723462162', '100547268592', '9881124215',
                  '33579058808', '100089268533', '9827727750'):
        assert value in text
    assert "head.get('generation') != 1" in text
    assert "provenance.get('authority') != 'github_actions_migration'" in text
    assert "provenance.get('repository_id') != 1349678672" in text


def test_acceptance_requires_generation_one_shadow_dashboard_with_exact_inputs():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "dashboard.get('generation') != 1" in text
    assert "provenance.get('mode') != 'shadow'" in text
    assert "inputs.get(namespace) != heads[namespace].get('snapshot_sha256')" in text
    assert "'simulation' in heads" in text


def test_acceptance_requires_no_phase3_producer_runs_and_paused_schedulers():
    text = WORKFLOW.read_text(encoding='utf-8')
    for name in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
    assert "for producer in ('legislative', 'executive', 'ai')" in text
    assert 'side_effects_possible' in text


def test_acceptance_rechecks_private_sql_admin_baseline_and_nonpublic_web():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'Cloud SQL is not private-only with a private address.' in text
    assert 'Runtime v2 web service has public allUsers access.' in text
    assert 'Admin args changed after execution override.' in text
    assert "'phase4_started': False" in text
    assert "'production_authority_transferred': False" in text
