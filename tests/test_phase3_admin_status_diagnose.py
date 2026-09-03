from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_admin_status_diagnose.yml')
PULSE = Path('.github/workflows/phase3_diagnostic_pulse.yml')


def test_diagnostic_trigger_is_directly_path_scoped_and_other_triggers_remain_guarded():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'push:' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_admin_status_diagnose.yml"' in text
    assert "github.event_name == 'push'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'issue_comment:' in text
    assert 'workflow_run:' in text
    assert 'Legislative purchase tracker v2' in text
    assert 'Executive purchase tracker' in text
    assert 'AI filing analyst and paper portfolio' in text
    assert 'Publish government trade dashboard' in text
    assert 'Runtime v2 safety tests' in text
    assert 'Phase 3 diagnostic trigger pulse' in text
    assert "github.repository_id == '1349678672'" in text
    assert 'github.event.issue.number == 39' in text
    assert 'github.event.sender.id == 225069210' in text
    assert "github.event.comment.body == '/phase3-diagnose-admin-status'" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text


def test_diagnostic_pulse_is_noop_read_only_and_self_path_scoped():
    text = PULSE.read_text(encoding='utf-8')
    assert 'name: Phase 3 diagnostic trigger pulse' in text
    assert 'push:' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_diagnostic_pulse.yml"' in text
    assert 'permissions:\n  contents: read' in text
    assert 'id-token: write' not in text
    assert 'pages: write' not in text
    assert 'actions: write' not in text
    assert 'gcloud' not in text
    assert 'gh api' not in text
    assert 'curl' not in text
    assert 'run jobs' not in text
    assert 'scheduler' not in text.casefold()
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'echo "Phase 3 diagnostic trigger pulse: ${GITHUB_SHA}"' in text


def test_diagnostic_is_one_shot_through_private_state_bucket_marker():
    text = WORKFLOW.read_text(encoding='utf-8')
    assert 'STATE_BUCKET: project-38008d5f-4918-46e6-920-polititrack-tfstate' in text
    assert 'ONESHOT_MARKER: phase3-diagnostics/admin-status-v3.claimed' in text
    assert 'gcloud storage ls "${marker_uri}"' in text
    assert 'gcloud storage cp oneshot-marker.txt "${marker_uri}"' in text
    assert 'skipping duplicate execution' in text


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
