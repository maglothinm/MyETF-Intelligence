from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4_harvest_hardened_image.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_harvest_is_canonical_main_and_self_scoped() -> None:
    text = _text()
    assert "name: Phase 4 harvest hardened Runtime image" in text
    assert "branches:\n      - main" in text
    assert '".github/workflows/phase4_harvest_hardened_image.yml"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_harvest_pins_exact_build_and_source() -> None:
    text = _text()
    assert "BUILD_ID: d580d289-c02e-4f07-93e0-d0acfc17ee4b" in text
    assert "BUILD_SOURCE_REVISION: 9b77de78203fec04d46404e1b674325517420c5c" in text
    assert ".substitutions._SOURCE_REVISION == $source" in text
    assert ".projectId == $project" in text
    assert "gcloud builds describe" in text
    assert "gcloud artifacts docker images describe" in text
    assert "sha256:[0-9a-f]{64}" in text


def test_harvest_is_read_only_and_does_not_start_phase4() -> None:
    text = _text()
    for forbidden in (
        "gcloud builds submit",
        "gcloud run jobs execute",
        "gcloud run jobs update",
        "gcloud run services update",
        "gcloud scheduler jobs run",
        "gcloud scheduler jobs resume",
        "terraform apply",
        "secrets versions access",
    ):
        assert forbidden not in text
    assert "build_started_by_this_workflow: false" in text
    assert "deployed: false" in text
    assert "runtime_job_execution: false" in text
    assert "scheduler_execution: false" in text
    assert "production_authority_transferred: false" in text
    assert "phase4_started: false" in text
