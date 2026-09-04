from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_closeout_gcs_v2.yml")
SCRIPT = Path("deploy/runtime-v2/close-phase3-gcs-v2.sh")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_workflow_is_canonical_main_and_self_scoped() -> None:
    text = _workflow()
    trigger = text.split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in trigger
    assert 'push:' not in trigger
    assert 'group: runtime-v2-live-controller' in text
    assert "name: Phase 3 GCS closeout v2" in text
    assert '"deploy/runtime-v2/close-phase3-gcs-v2.sh"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text
    assert "contents: write" in text
    assert "id-token: write" in text


def test_script_addresses_checkout_explicitly() -> None:
    text = _script()
    assert 'root="${GITHUB_WORKSPACE}"' in text
    assert 'git -C "${root}" ls-remote origin refs/tags/phase3-ready' in text
    assert 'git -C "${root}" tag phase3-ready "${GITHUB_SHA}"' in text
    assert 'git -C "${root}" push --atomic origin HEAD:main refs/tags/phase3-ready' in text
    assert "git ls-remote origin" not in text.replace(
        'git -C "${root}" ls-remote origin', ""
    )


def test_script_uses_private_gcs_evidence_without_logging() -> None:
    text = _script()
    assert "gcs_status_probe.py" in text
    assert "phase3-acceptance/probes/" in text
    assert "gcloud storage cat" in text
    assert "private_gcs_probe" in text
    assert "gcloud logging read" not in text
    assert "roles/logging.admin" not in text
    assert "roles/logging.viewAccessor" not in text


def test_script_executes_exactly_one_nonproducer_admin_probe() -> None:
    text = _script()
    assert text.count("gcloud run jobs execute") == 1
    assert "gcloud run jobs execute \"${ADMIN_JOB}\"" in text
    assert "gcs_status_probe.py" in text
    assert "phase3" in text
    for forbidden in (
        "runtime_v2,run",
        "import-gcs",
        "gcloud scheduler jobs run",
        "gcloud scheduler jobs resume",
        "gcloud scheduler jobs enable",
        "terraform apply",
        "gcloud run deploy",
        "gcloud run jobs deploy",
        "gcloud sql instances patch",
        "secrets versions access",
        "POLITITRACK_MODE=production",
    ):
        assert forbidden not in text


def test_temporary_authority_is_narrow_and_verified_removed() -> None:
    text = _script()
    assert "roles/run.jobsExecutorWithOverrides" in text
    assert "roles/storage.objectCreator" in text
    assert "trap cleanup EXIT" in text
    assert "verify_temporary_access_absent" in text
    assert "Temporary admin execution authority remains." in text
    assert "Temporary probe object-creator authority remains." in text
    assert "roles/storage.admin" not in text
    assert "roles/owner" not in text
    assert "roles/editor" not in text


def test_phase3_acceptance_and_private_boundaries_are_enforced() -> None:
    text = _script()
    for scheduler in (
        "polititrack-legislative",
        "polititrack-executive",
        "polititrack-ai",
        "polititrack-dashboard",
        "polititrack-vault-lifecycle",
    ):
        assert scheduler in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
    assert ".settings.ipConfiguration.ipv4Enabled == false" in text
    assert '.type == "PRIVATE"' in text
    assert 'any(. == "allUsers")' in text
    assert '["-m","runtime_v2","init-db","--with-vault"]' in text
    assert "validate_phase3_status.py" in text
    assert '"phase4_started": False' in text
    assert '"production_authority_transferred": False' in text


def test_readiness_publication_is_atomic_and_after_private_receipt() -> None:
    text = _script()
    receipt = text.index('final_uri="gs://${STATE_BUCKET}/phase3-acceptance/final/phase3-acceptance.json"')
    tag = text.index('git -C "${root}" tag phase3-ready')
    push = text.index('git -C "${root}" push --atomic origin HEAD:main refs/tags/phase3-ready')
    assert receipt < tag < push
    assert "docs/runtime-v2/phase3/PHASE4_READY.md" in text
    assert "Remote phase3-ready tag does not target the accepted commit." in text
