from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_harvest_current_runtime_build.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_harvest_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 harvest current Runtime build' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_harvest_current_runtime_build.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_harvest_is_pinned_to_exact_submitted_build_and_source() -> None:
    text = _text()
    assert 'BUILD_ID: 1db569db-57a1-46fe-a061-0547ac6779b2' in text
    assert 'BUILD_SOURCE_REVISION: 080a3df0f0b912f702a30148cedc831b833a81db' in text
    assert 'gcloud builds describe "${BUILD_ID}"' in text
    assert '.substitutions._SOURCE_REVISION == $source' in text
    assert '.projectId == $project' in text
    assert 'build_status: $status' in text


def test_harvest_requires_success_and_immutable_new_digest() -> None:
    text = _text()
    assert '[[ "${status}" == "SUCCESS" ]]' in text
    assert 'sha256:[0-9a-f]{64}' in text
    assert 'CURRENT_DEPLOYED_DIGEST' in text
    assert 'Successful build unexpectedly resolved to the stale deployed image digest.' in text
    assert 'phase3_current_runtime_image_harvested' in text
    assert 'immutable_image' in text


def test_harvest_does_not_build_deploy_or_execute_runtime() -> None:
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
    assert 'build_started_by_this_workflow: false' in text
    assert 'deployed: false' in text
    assert 'runtime_job_execution: false' in text
    assert 'scheduler_execution: false' in text
    assert 'production_authority_transferred: false' in text
    assert 'phase4_started: false' in text
