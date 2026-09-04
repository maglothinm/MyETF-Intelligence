from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_converge_schema_and_close.yml")
WRAPPER = Path("deploy/runtime-v2/converge-phase3-schema-and-close.sh")
PROBE = Path("deploy/runtime-v2/gcs_status_probe.py")


def test_workflow_is_canonical_main_and_self_scoped() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split('permissions:', 1)[0]
    assert 'workflow_dispatch:' in trigger
    assert 'push:' not in trigger
    assert 'group: runtime-v2-live-controller' in text
    assert "name: Phase 3 converge schema and close" in text
    assert '"deploy/runtime-v2/converge-phase3-schema-and-close.sh"' in text
    assert '"deploy/runtime-v2/gcs_status_probe.py"' in text
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text


def test_probe_allows_additive_schema_init_only_in_phase3() -> None:
    text = PROBE.read_text(encoding="utf-8")
    assert "[initialize-schema]" in text
    assert 'initialize_schema = len(args) == 4 and args[3] == "initialize-schema"' in text
    assert 'if initialize_schema and phase != "phase3"' in text
    assert 'store.initialize_schema()' in text
    assert 'receipt["schema_initialized"] = True' in text
    assert '"protected_state_changed_by_schema_initialize": False' in text
    assert "DROP TABLE" not in text
    assert "TRUNCATE" not in text
    assert "DELETE FROM" not in text


def test_wrapper_executes_only_schema_probe_then_existing_closeout() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert text.count("gcloud run jobs execute") == 1
    assert "phase3,initialize-schema" in text
    assert "gcs_status_probe.py" in text
    assert 'bash "${GITHUB_WORKSPACE}/deploy/runtime-v2/close-phase3-gcs-v2.sh"' in text
    for forbidden in (
        "runtime_v2,run",
        "import-gcs",
        "gcloud scheduler jobs run",
        "gcloud scheduler jobs resume",
        "gcloud scheduler jobs enable",
        "gcloud sql instances patch",
        "terraform apply",
        "secrets versions access",
        "POLITITRACK_MODE=production",
    ):
        assert forbidden not in text


def test_wrapper_requires_paused_schedulers_and_narrow_temporary_iam() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    for scheduler in (
        "polititrack-legislative",
        "polititrack-executive",
        "polititrack-ai",
        "polititrack-dashboard",
        "polititrack-vault-lifecycle",
    ):
        assert scheduler in text
    assert '[[ "${state}" == "PAUSED" ]]' in text
    assert "roles/run.jobsExecutorWithOverrides" in text
    assert "roles/storage.objectCreator" in text
    assert "trap cleanup EXIT" in text
    assert "verify_absent" in text
    assert "Temporary admin execution authority remains." in text
    assert "Temporary schema-probe object authority remains." in text
    assert "roles/storage.admin" not in text
    assert "roles/owner" not in text
    assert "roles/editor" not in text


def test_wrapper_fail_closes_on_schema_receipt() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert ".schema_initialize_requested == true" in text
    assert ".schema_initialized == true" in text
    assert ".protected_state_changed_by_schema_initialize == false" in text
    assert ".database_private_ip_selected == true" in text
    assert "Runtime v2 additive schema convergence failed." in text
