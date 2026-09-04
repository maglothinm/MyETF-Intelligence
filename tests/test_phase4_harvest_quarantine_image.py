from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4_harvest_quarantine_image.yml")
SOURCE = "8908f067298078f8c013e90cf6b7ad8ad420285b"
BUILD_ID = "d2b84173-eafa-4fb6-b9ac-a3e232d273f4"
BUILD_TAG = "8908f0672980"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_harvest_is_one_shot_canonical_read_only_controller() -> None:
    text = _text()
    trigger = text.split("permissions:", 1)[0]
    assert "push:" in trigger and "- main" in trigger
    assert '".github/workflows/phase4_harvest_quarantine_image.yml"' in trigger
    assert "workflow_dispatch:" not in trigger
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "group: runtime-v2-image-build" in text
    assert "github.repository_id == '1349678672'" in text


def test_harvest_reuses_only_the_submitted_exact_build() -> None:
    text = _text()
    assert f"BUILD_ID: {BUILD_ID}" in text
    assert f"BUILD_SOURCE_REVISION: {SOURCE}" in text
    assert f"BUILD_TAG: {BUILD_TAG}" in text
    assert 'gcloud builds describe "${BUILD_ID}"' in text
    assert "gcloud builds submit" not in text
    assert "exact_build_reused" in text
    assert "build_resubmitted" in text
    assert "SUBMIT_WORKFLOW_RUN_ID: \"33823547823\"" in text
    assert "SUBMIT_ARTIFACT_ID: \"9919214769\"" in text


def test_harvest_fails_closed_on_build_identity_and_digest() -> None:
    text = _text()
    assert '.substitutions._SOURCE_REVISION == $source' in text
    assert '.substitutions._TAG == $tag' in text
    assert '.status == "SUCCESS"' in text
    assert 'any(.results.images[]?; .digest == $digest or .digest == $bare_digest)' in text
    assert "CURRENT_DEPLOYED_DIGEST" in text
    assert "OBSOLETE_HARDENED_DIGEST" in text


def test_harvest_has_no_runtime_or_cloud_mutation() -> None:
    text = _text()
    forbidden = (
        "gcloud run jobs execute",
        "gcloud run jobs update",
        "gcloud scheduler jobs run",
        "gcloud scheduler jobs resume",
        "terraform apply",
        "git push",
        "secrets versions access",
    )
    for value in forbidden:
        assert value not in text
    assert '"runtime_job_execution": false' not in text  # jq uses unquoted keys
    assert "runtime_job_execution: false" in text
    assert "phase4_producer_execution: false" in text
