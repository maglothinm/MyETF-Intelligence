from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_admin_status_diagnose.yml')


def test_diagnostic_trigger_is_issue39_owner_command_only():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'issue_comment:' in text
    assert "github.repository_id == '1349678672'" in text
    assert 'github.event.issue.number == 39' in text
    assert 'github.event.sender.id == 225069210' in text
    assert "github.event.comment.body == '/phase3-diagnose-admin-status'" in text
    assert 'push:' not in text


def test_diagnostic_does_not_execute_runtime_jobs():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'gcloud run jobs execute' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text


def test_diagnostic_repairs_only_known_admin_status_override():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert "'[\"-m\",\"runtime_v2\",\"status\"]'" in text
    assert '--args=-m,runtime_v2,init-db,--with-vault' in text
    assert 'Admin arguments are not the Terraform Phase 3 baseline.' in text


def test_diagnostic_removes_temporary_permissions():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'roles/logging.viewer' in text
    assert 'roles/logging.viewAccessor' in text
    assert text.count('remove-iam-policy-binding') >= 4
    assert 'binding remains after diagnostic cleanup.' in text
    assert 'roles/run.invoker' in text


def test_diagnostic_requires_all_schedulers_paused():
    text = WORKFLOW.read_text(encoding='utf-8')
    for name in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
