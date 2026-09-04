from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_data_plane_audit.yml')


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_one_shot_main_trigger():
    text = workflow_text()
    trigger = text.split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in trigger
    assert 'push:' not in trigger
    assert 'group: runtime-v2-live-controller' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text


def test_only_admin_job_is_executed():
    text = workflow_text()
    assert 'ADMIN_JOB: polititrack-admin' in text
    assert '--args=-m,runtime_v2,status' in text
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text


def test_cleanup_is_mandatory():
    text = workflow_text()
    assert 'trap cleanup EXIT' in text
    assert 'remove-iam-policy-binding "${ADMIN_JOB}"' in text
    assert 'projects remove-iam-policy-binding' in text
    assert 'Admin arguments were not restored.' in text
    assert 'Temporary admin invoker binding remains after cleanup.' in text
    assert 'Temporary logging viewer binding remains after cleanup.' in text


def test_generation_one_sources_are_pinned():
    text = workflow_text()
    assert "'legislative': 9881049089" in text
    assert "'executive': 9881124215" in text
    assert "'ai': 9827727750" in text
    assert "head.get('generation') != 1" in text
    assert "provenance.get('repository_id') != 1349678672" in text
    assert "provenance.get('mode') != 'shadow'" in text


def test_schedulers_must_remain_paused():
    text = workflow_text()
    for name in ('polititrack-legislative', 'polititrack-executive', 'polititrack-ai', 'polititrack-dashboard', 'polititrack-vault-lifecycle'):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
