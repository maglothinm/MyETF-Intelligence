from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_harvest_current_runtime_build.yml')
BUILD_ID = 'd580d289-c02e-4f07-93e0-d0acfc17ee4b'
SOURCE = '9b77de78203fec04d46404e1b674325517420c5c'
STALE_DIGEST = 'sha256:b9758a697338ffdeb7505473819aec70247ac23ed46b15af5b78701ed1f61f9b'


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_harvest_is_canonical_self_path_scoped_main_push() -> None:
    text = _text()
    assert 'name: Phase 3 harvest hardened Runtime build' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase3_harvest_current_runtime_build.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text
    assert 'cancel-in-progress: false' in text


def test_harvest_is_pinned_to_exact_submitted_build_and_source() -> None:
    text = _text()
    assert f'BUILD_ID: {BUILD_ID}' in text
    assert f'BUILD_SOURCE_REVISION: {SOURCE}' in text
    assert f'CURRENT_DEPLOYED_DIGEST: {STALE_DIGEST}' in text
    assert 'gcloud builds describe "${BUILD_ID}"' in text
    assert '.substitutions._SOURCE_REVISION == $source' in text
    assert '.projectId == $project' in text
    assert 'git merge-base --is-ancestor "${BUILD_SOURCE_REVISION}" "${GITHUB_SHA}"' in text
    assert 'build_status: $status' in text


def test_harvest_requires_success_and_immutable_new_digest() -> None:
    text = _text()
    assert '[[ "${status}" == "SUCCESS" ]]' in text
    assert 'sha256:[0-9a-f]{64}' in text
    assert 'Successful build unexpectedly resolved to the stale deployed image digest.' in text
    assert 'phase3_hardened_runtime_image_harvested' in text
    assert 'immutable_image' in text


def test_harvest_requires_fail_closed_migration_and_records_source_hashes() -> None:
    text = _text()
    assert "snapshot.source_provenance ->> 'mode'" in text
    assert 'cannot provenance-derive runtime_job_runs.runtime_mode for every legacy run' in text
    assert 'Canonical migration still contains the unsafe blanket production backfill.' in text
    for field in (
        'database_sha256',
        'store_sha256',
        'runner_sha256',
        'migration_sha256',
        'dockerfile_sha256',
        'requirements_sha256',
    ):
        assert field in text
    assert 'fail_closed_runtime_mode_migration: true' in text
    assert 'atomic_snapshot_head_run_commit: true' in text


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
