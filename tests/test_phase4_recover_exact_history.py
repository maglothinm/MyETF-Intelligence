from pathlib import Path


WORKFLOW = Path('.github/workflows/phase4_recover_exact_history.yml')


def _text() -> str:
    return WORKFLOW.read_text(encoding='utf-8')


def test_exact_history_recovery_is_canonical_and_read_only() -> None:
    text = _text()
    assert 'name: Phase 4 recover exact Runtime history' in text
    assert 'branches:' in text and '- main' in text
    assert '".github/workflows/phase4_recover_exact_history.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'actions: read' in text
    assert 'contents: read' in text
    permissions = text.split('permissions:', 1)[1].split('concurrency:', 1)[0]
    assert 'contents: write' not in permissions
    assert 'group: phase4-exact-history-read' in text
    assert 'cancel-in-progress: false' in text


def test_exact_history_recovery_is_pinned_to_incident_evidence() -> None:
    text = _text()
    assert 'SOURCE_RUN_ID: "33819641464"' in text
    assert 'SOURCE_ARTIFACT_ID: "9917920173"' in text
    assert (
        'SOURCE_ARTIFACT_SHA256: '
        '7f0851fa00169ed80e92972a32d2e7abbb2825378469b945959226143a06702d'
    ) in text
    assert 'Downloaded evidence artifact digest mismatch.' in text
    assert "exact('schema-probe.json', 'phase3-schema-converge-')" in text
    assert "exact('probe.json', 'phase3-closeout-gcs-v2-')" in text
    assert "exact('status.json', 'phase3-closeout-gcs-v2-')" in text


def test_exact_history_recovery_exports_lineage_without_payloads() -> None:
    text = _text()
    for value in (
        "'snapshot_id'",
        "'snapshot_sha256'",
        "'parent_sha256'",
        "'generation'",
        "'source_revision'",
        "'provenance'",
        "'run_id'",
        "'runtime_mode'",
        "'side_effects_possible'",
        "'run_history'",
        "'snapshot_history'",
    ):
        assert value in text
    assert "'payload'" not in text
    assert "'mutation_performed': False" in text


def test_exact_history_recovery_cannot_touch_runtime_or_cloud() -> None:
    text = _text()
    bounded = text.rsplit('# BOUNDED_EVIDENCE_READER', 1)[1]
    for forbidden in (
        'google-github-actions/auth',
        'gcloud ',
        'run jobs execute',
        'scheduler jobs',
        'terraform apply',
        'secrets versions access',
        'storage cp',
    ):
        assert forbidden not in bounded
    assert "'runtime_job_execution': False" in text
    assert "'scheduler_execution': False" in text
    assert "'production_authority_transferred': False" in text
