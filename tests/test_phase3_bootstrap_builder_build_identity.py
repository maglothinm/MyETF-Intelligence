from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_bootstrap_builder_build_identity.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_bootstrap_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 bootstrap builder build identity' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_bootstrap_builder_build_identity.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_deployer_receives_only_read_only_cloud_build_discovery() -> None:
    text = _text()
    assert '--role roles/cloudbuild.builds.viewer' in text
    assert 'deployer_cloud_build_access: "viewer_only"' in text
    assert 'roles/cloudbuild.builds.editor' not in text
    assert 'roles/cloudbuild.builds.builder' not in text
    assert 'roles/owner' not in text
    assert 'roles/editor' not in text


def test_builder_actas_is_bound_only_on_resolved_default_build_identity() -> None:
    text = _text()
    assert 'gcloud builds get-default-service-account' in text
    assert '--format=\'value(serviceAccountEmail)\'' in text
    assert 'gcloud iam service-accounts add-iam-policy-binding "${default_build_service_account}"' in text
    assert '--member "${member_builder}"' in text
    assert '--role roles/iam.serviceAccountUser' in text
    assert 'builder_actas_scope: "default_build_service_account_only"' in text
    assert 'Builder has unexpected project-wide Service Account User authority.' in text
    assert 'Refusing to collapse the isolated submitter and build-execution identities.' in text


def test_bootstrap_performs_no_build_deployment_or_runtime_execution() -> None:
    text = _text()
    forbidden = (
        'gcloud builds submit',
        'gcloud run jobs update',
        'gcloud run services update',
        'gcloud run deploy',
        'gcloud run jobs execute',
        'terraform apply',
        'gcloud scheduler jobs run',
        'gcloud scheduler jobs resume',
        'gcloud scheduler jobs enable',
        'secrets versions access',
    )
    for value in forbidden:
        assert value not in text
    assert 'build_started: false' in text
    assert 'deployed: false' in text
    assert 'runtime_job_execution: false' in text
    assert 'scheduler_execution: false' in text
    assert 'production_authority_transferred: false' in text
    assert 'phase4_started: false' in text
