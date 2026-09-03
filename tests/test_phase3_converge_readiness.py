from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_converge_readiness.yml')
CONTROLLER = Path('deploy/runtime-v2/converge-phase3-readiness.sh')


def _workflow() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def _controller() -> str:
    return CONTROLLER.read_text(encoding='utf-8')


def test_workflow_separates_pr_static_checks_from_main_cloud_execution():
    text = _workflow()
    assert 'pull_request:' in text
    assert 'push:' in text
    assert "github.event_name == 'pull_request'" in text
    assert "github.event_name == 'push'" in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'cancel-in-progress: false' in text


def test_controller_never_executes_a_producer_or_scheduler():
    text = _controller()
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert '--args=-m,runtime_v2,status' in text
    assert 'gcloud run jobs execute "${ADMIN_JOB}"' in text
    assert text.count('gcloud run jobs execute') == 1


def test_controller_repairs_only_declared_private_ip_environment_drift():
    text = _controller()
    assert '--update-env-vars=PRIVATE_IP=true' in text
    assert 'gcloud run jobs update "${job}"' in text
    assert 'gcloud run services update "${WEB_SERVICE}"' in text
    assert 'gcloud run jobs deploy' not in text
    assert 'gcloud run deploy' not in text
    assert 'gcloud sql instances patch' not in text
    assert 'terraform apply' not in text
    assert 'assert_admin_baseline' in text


def test_controller_requires_inert_private_nonpublic_boundaries():
    text = _controller()
    for name in (
        'polititrack-legislative',
        'polititrack-executive',
        'polititrack-ai',
        'polititrack-dashboard',
        'polititrack-vault-lifecycle',
    ):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
    assert '.settings.ipConfiguration.ipv4Enabled == false' in text
    assert '.type == "PRIVATE"' in text
    assert 'allUsers' in text


def test_controller_temporary_authority_is_narrow_and_removed_before_acceptance():
    text = _controller()
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/run.invoker' not in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'trap cleanup_temporary_access EXIT' in text
    assert 'verify_temporary_access_removed' in text
    assert 'Temporary admin execution authority remains.' in text
    assert 'Temporary Logging Admin remains.' in text
    assert 'Temporary log-view accessor remains.' in text


def test_controller_validates_exact_phase3_receipt_and_round_trip_digest():
    text = _controller()
    assert 'validate_phase3_status.py' in text
    assert "'result': 'phase3_ready_for_phase4'" in text
    assert "'phase4_started': False" in text
    assert "'production_authority_transferred': False" in text
    assert 'phase3-acceptance/final/phase3-acceptance.json' in text
    assert 'Private acceptance receipt round-trip digest mismatch.' in text


def test_workflow_creates_readiness_tag_only_after_controller_success():
    text = _workflow()
    controller = text.index('Converge and validate Phase 3 readiness')
    tag = text.index('Create immutable Phase 4 readiness tag')
    assert controller < tag
    assert 'git tag phase3-ready "${GITHUB_SHA}"' in text
    assert 'git push origin refs/tags/phase3-ready' in text
    assert 'contents: write' in text
