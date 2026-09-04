from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_closeout_gcs.yml")
CONTROLLER = Path("deploy/runtime-v2/closeout-phase3-gcs.sh")
PROBE = Path("deploy/runtime-v2/gcs_status_probe.py")


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _controller() -> str:
    return CONTROLLER.read_text(encoding="utf-8")


def _probe() -> str:
    return PROBE.read_text(encoding="utf-8")


def test_closeout_is_canonical_self_scoped_main_push() -> None:
    text = _workflow()
    assert "name: Phase 3 closeout through private GCS evidence" in text
    assert "branches:" in text and "- main" in text
    for path in (
        ".github/workflows/phase3_closeout_gcs.yml",
        "deploy/runtime-v2/closeout-phase3-gcs.sh",
        "deploy/runtime-v2/gcs_status_probe.py",
    ):
        assert f'"{path}"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_closeout_uses_private_gcs_instead_of_cloud_logging() -> None:
    text = _controller()
    assert "gcs_status_probe.py" in text
    assert "phase3-acceptance/probes/" in text
    assert "gcloud storage cat" in text
    assert "gcloud logging read" not in text
    assert "roles/logging.admin" not in text
    assert "roles/logging.viewAccessor" not in text


def test_closeout_executes_only_one_read_only_admin_probe() -> None:
    text = _controller()
    assert text.count("gcloud run jobs execute") == 1
    assert '--args="-c,${bootstrap},${STATE_BUCKET},${probe_object},phase3"' in text
    for producer in (
        "polititrack-legislative",
        "polititrack-executive",
        "polititrack-ai",
        "polititrack-dashboard",
    ):
        assert f'gcloud run jobs execute "{producer}"' not in text
    for forbidden in (
        "runtime_v2,run",
        "import-gcs",
        "gcloud scheduler jobs run",
        "gcloud scheduler jobs resume",
        "gcloud scheduler jobs enable",
        "secrets versions access",
        "terraform apply",
        "gcloud run deploy",
        "gcloud sql instances patch",
    ):
        assert forbidden not in text


def test_temporary_probe_authority_is_narrow_and_removed() -> None:
    text = _controller()
    assert "roles/run.jobsExecutorWithOverrides" in text
    assert "roles/storage.objectCreator" in text
    assert "roles/storage.objectAdmin" in text
    assert "roles/storage.admin" in text
    assert "cleanup()" in text
    assert "trap cleanup EXIT" in text
    assert "remove-iam-policy-binding" in text
    assert "verify_temporary_access_absent" in text
    assert "Temporary admin execution authority remains." in text
    assert "Temporary probe object-creator authority remains." in text
    assert "Admin service account has unexpected project-wide object-write authority." in text


def test_closeout_rechecks_inert_private_boundary() -> None:
    text = _controller()
    for name in (
        "polititrack-legislative",
        "polititrack-executive",
        "polititrack-ai",
        "polititrack-dashboard",
        "polititrack-vault-lifecycle",
    ):
        assert name in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
    assert ".settings.ipConfiguration.ipv4Enabled == false" in text
    assert '.type == "PRIVATE"' in text
    assert 'any(. == "allUsers")' in text
    assert '["-m","runtime_v2","init-db","--with-vault"]' in text
    assert "validate_phase3_status.py" in text


def test_closeout_writes_verified_receipt_and_atomic_readiness_marker() -> None:
    text = _controller()
    assert "phase3-acceptance/final/phase3-acceptance.json" in text
    assert "sha256sum" in text
    assert "git tag phase3-ready" in text
    assert "docs/runtime-v2/phase3/PHASE4_READY.md" in text
    assert "git push --atomic origin HEAD:main refs/tags/phase3-ready" in text
    assert '"phase4_started": False' in text
    assert '"production_authority_transferred": False' in text


def test_probe_is_nonsecret_and_fail_closed() -> None:
    text = _probe()
    assert '"phase3-acceptance/probes/"' in text
    assert '"phase4-acceptance/probes/"' in text
    assert "if_generation_match=0" in text
    assert '"private_ip_env"' in text
    assert '"database_private_ip_selected"' in text
    assert '"database_module_sha256"' in text
    assert '"cloud_sql_connector_version"' in text
    assert '"error_type"' in text
    assert '"error_message"' in text
    assert '"traceback_tail"' in text
    assert 'os.environ.get("DB_PASSWORD")' not in text
    assert "return 1" in text


def test_probe_collects_status_and_immutable_history_metadata() -> None:
    text = _probe()
    assert "PostgresSnapshotStore" in text
    assert "store.status()" in text
    assert "store.workflow_evidence()" in text
    assert "FROM runtime_job_runs ORDER BY started_at, run_id" in text
    assert "FROM runtime_state_snapshots ORDER BY namespace, generation" in text
    assert '"side_effects_possible"' in text
    assert '"evidence_sha256"' in text
    assert "payload bytea" not in text
    assert "manifest" not in text
