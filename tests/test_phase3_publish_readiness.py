from pathlib import Path


WORKFLOW = Path('.github/workflows/phase3_publish_readiness.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_gate_separates_pr_static_checks_from_canonical_main_publication():
    text = _text()
    assert 'pull_request:' in text
    assert 'push:' in text
    assert "github.event_name == 'pull_request'" in text
    assert "github.event_name == 'push'" in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'cancel-in-progress: false' in text


def test_gate_never_executes_runtime_producers_or_schedulers():
    text = _text()
    assert 'gcloud run jobs execute' not in text
    assert 'gcloud scheduler jobs run' not in text
    assert 'gcloud scheduler jobs resume' not in text
    assert 'gcloud scheduler jobs update' not in text
    assert 'runtime_v2,run' not in text
    assert 'import-gcs' not in text
    assert 'secrets versions access' not in text


def test_gate_reverifies_private_inert_cloud_boundaries():
    text = _text()
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
    assert 'PRIVATE_IP' in text
    assert 'polititrack-admin-v2@' in text


def test_gate_requires_all_temporary_phase3_authority_to_be_absent():
    text = _text()
    assert 'roles/run.jobsExecutorWithOverrides' in text
    assert 'roles/logging.admin' in text
    assert 'roles/logging.viewAccessor' in text
    assert 'roles/storage.objectCreator' in text
    assert 'Temporary Phase 3 execution authority remains.' in text
    assert 'Temporary Phase 3 logging administrator authority remains.' in text
    assert 'Temporary Phase 3 log-view authority remains.' in text
    assert 'Temporary Phase 3 probe-storage authority remains.' in text
    assert 'add-iam-policy-binding' not in text


def test_gate_requires_exact_private_phase3_receipt_and_lineage():
    text = _text()
    assert 'phase3-acceptance/final/phase3-acceptance.json' in text
    assert '.result == "phase3_ready_for_phase4"' in text
    assert '.acceptance_channel == "private_gcs_probe"' in text
    assert '.phase4_started == false' in text
    assert '.production_authority_transferred == false' in text
    assert '.protected_generations.legislative == 1' in text
    assert '.protected_generations.executive == 1' in text
    assert '.protected_generations.ai == 1' in text
    assert '.dashboard_generation == 1' in text
    assert 'git merge-base --is-ancestor "${receipt_source}" "${GITHUB_SHA}"' in text


def test_marker_and_immutable_tag_publish_atomically():
    text = _text()
    assert 'docs/runtime-v2/phase3/PHASE4_READY.md' in text
    assert 'git tag phase3-ready "${marker_commit}"' in text
    assert 'git push --atomic origin "${marker_commit}:refs/heads/main" refs/tags/phase3-ready' in text
    assert 'Partial Phase 3 readiness publication exists.' in text
    assert 'Canonical main moved after this gate started.' in text
    assert 'Phase 4 may perform only the controlled shadow acceptance authorized by issue #82.' in text


def test_publication_does_not_mutate_phase3_acceptance_or_production_authority():
    text = _text()
    assert 'gcloud storage cp "${final_uri}" "${evidence}/phase3-acceptance.json"' in text
    assert 'gcloud storage cp "${evidence}/phase3-acceptance.json"' not in text
    assert 'POLITITRACK_MODE=production' not in text
    assert 'production_authority_transferred == false' in text
    assert 'Phase 5 promotion' in text
