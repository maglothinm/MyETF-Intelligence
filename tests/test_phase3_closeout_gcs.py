from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_closeout_gcs.yml")
PROBE = Path("deploy/runtime-v2/gcs_status_probe.py")


def test_closeout_is_canonical_and_self_scoped() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "name: Phase 3 closeout through private GCS evidence" in text
    assert 'branches:\n      - main' in text
    assert '".github/workflows/phase3_closeout_gcs.yml"' in text
    assert '"deploy/runtime-v2/gcs_status_probe.py"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_closeout_replaces_cloud_logging_with_private_gcs_probe() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "gcs_status_probe.py" in text
    assert "phase3-acceptance/probes/" in text
    assert "roles/storage.objectCreator" in text
    assert "gcloud storage cat" in text
    assert "private_gcs_probe" in text
    assert "gcloud logging read" not in text
    assert "roles/logging.admin" not in text
    assert "roles/logging.viewAccessor" not in text


def test_closeout_executes_only_one_read_only_admin_probe() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("gcloud run jobs execute") == 1
    assert '--args="-c,${bootstrap},${STATE_BUCKET},${probe_object},phase3"' in text
    for forbidden in (
        "runtime_v2,run",
        "import-gcs",
        "gcloud scheduler jobs run",
        "gcloud scheduler jobs resume",
        "gcloud scheduler jobs enable",
        "terraform apply",
        "gcloud run deploy",
        "gcloud sql instances patch",
        "secrets versions access",
        "POLITITRACK_MODE=production",
    ):
        assert forbidden not in text


def test_closeout_temporary_authority_is_narrow_and_removed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "roles/run.jobsExecutorWithOverrides" in text
    assert "roles/storage.objectCreator" in text
    assert "trap cleanup EXIT" in text
    assert "verify_temporary_access_absent" in text
    assert "Temporary admin execution authority remains." in text
    assert "Temporary probe object-creator authority remains." in text
    assert '"temporary_execution_authority_removed": True' in text
    assert '"temporary_probe_storage_authority_removed": True' in text
    assert "roles/storage.admin" not in text
    assert "roles/owner" not in text
    assert "roles/editor" not in text


def test_closeout_rechecks_inert_private_boundaries_and_acceptance() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
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


def test_closeout_publishes_immutable_phase_boundary_atomically() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "git tag phase3-ready" in text
    assert "docs/runtime-v2/phase3/PHASE4_READY.md" in text
    assert "git push --atomic origin HEAD:main refs/tags/phase3-ready" in text
    assert "phase4_started" in text
    assert "production_authority_transferred" in text


def test_probe_is_nonsecret_fail_closed_and_private_targeted() -> None:
    text = PROBE.read_text(encoding="utf-8")
    assert '"phase3-acceptance/probes/"' in text
    assert '"phase4-acceptance/probes/"' in text
    assert "if_generation_match=0" in text
    assert '"database_private_ip_selected"' in text
    assert '"run_history"' in text
    assert '"snapshot_history"' in text
    assert '"error_type"' in text
    assert '"error_message"' in text
    assert '"traceback_tail"' in text
    assert 'receipt["ok"] = True' in text
    assert 'if not receipt["ok"]' in text
    assert "DB_PASSWORD" not in text
    assert "dict(os.environ)" not in text.replace(
        "database_module._use_private_ip(dict(os.environ))", ""
    )
