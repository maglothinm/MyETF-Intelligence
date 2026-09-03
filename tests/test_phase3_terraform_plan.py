import json
from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_terraform_plan.yml")
MOVED = Path("deploy/runtime-v2/terraform/moved.tf")
CONFIG = Path("deploy/runtime-v2/phase3-reconciliation.tfvars.json")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _moved_text() -> str:
    return MOVED.read_text(encoding="utf-8")


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_phase3_plan_runs_only_on_canonical_main_boundary() -> None:
    text = _text()
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text
    assert "project-38008d5f-4918-46e6-920" in text
    assert "polititrack-github-phase3/providers/phase3-main" in text
    assert "polititrack-phase3-deployer@" in text


def test_phase3_plan_is_plan_only_and_never_executes_runtime() -> None:
    text = _text()
    forbidden = (
        "terraform apply",
        "terraform import",
        "run jobs execute",
        "run jobs run",
        "scheduler jobs resume",
        "scheduler jobs run",
        "scheduler jobs update",
        "secrets versions access",
        "storage cp",
        "builds submit",
    )
    for value in forbidden:
        assert value not in text
    assert "terraform -chdir=deploy/runtime-v2/terraform plan" in text
    assert "terraform_apply=false" in text
    assert "runtime_job_execution=false" in text
    assert "state_import=false" in text


def test_frozen_reconciliation_config_preserves_phase3_controls() -> None:
    config = _config()
    assert config["project_id"] == "project-38008d5f-4918-46e6-920"
    assert config["region"] == "us-central1"
    assert config["runtime_environment"]["POLITITRACK_MODE"] == "shadow"
    assert config["schedules_enabled"] is False
    assert config["public_dashboard_enabled"] is False
    assert config["vault_enabled"] is True
    assert config["dashboard_allowed_origins"] == ""
    assert config["vault_acknowledged_sources"] == ""
    assert config["vault_agency_hosts"] == ""


def test_frozen_reconciliation_config_preserves_existing_nonsecret_runtime_behavior() -> None:
    env = _config()["runtime_environment"]
    expected = {
        "AI_ANALYSIS_ENABLED": "true",
        "AI_FETCH_DOCUMENT_TEXT": "true",
        "AI_MAX_ANALYSES_PER_RUN": "20",
        "AI_OPENAI_MIN_REQUEST_INTERVAL_SECONDS": "65",
        "AI_PAPER_TRADING_ONLY": "true",
        "AI_REQUIRE_PUSHOVER": "false",
        "AI_WEB_SEARCH_ENABLED": "true",
        "ALLOW_EMPTY_SOURCES": "false",
        "DISCLOSURE_TERMS_ACKNOWLEDGED": "TRUE",
        "INVESTOR_EDGE_ENABLED": "true",
        "NOTIFY_ALL_FILINGS": "true",
        "NOTIFY_EQUITY_ONLY": "true",
        "NOTIFY_PENDING_REVIEWS": "true",
        "OPENAI_MODEL": "gpt-5.6-terra",
        "OPENAI_REASONING_EFFORT": "medium",
        "REQUIRE_PUSHOVER": "false",
        "SOURCE_REVISION": "080a3df0f0b912f702a30148cedc831b833a81db",
    }
    for name, value in expected.items():
        assert env[name] == value


def test_frozen_reconciliation_config_contains_secret_ids_only() -> None:
    secrets = _config()["runtime_secrets"]
    assert secrets == {
        "ALPHAVANTAGE_API_KEY": "polititrack-alphavantage-api-key",
        "FINNHUB_API_KEY": "polititrack-finnhub-api-key",
        "OPENAI_API_KEY": "polititrack-openai-api-key",
    }
    serialized = CONFIG.read_text(encoding="utf-8").lower()
    assert "secret_data" not in serialized
    assert "password" not in secrets


def test_phase3_plan_uses_frozen_immutable_image_without_building() -> None:
    text = _text()
    config = _config()
    assert config["image"] == (
        "us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/"
        "polititrack/runtime-v2@sha256:b9758a697338ffdeb7505473819aec70247ac23ed46b15af5b78701ed1f61f9b"
    )
    assert "builds submit" not in text


def test_phase3_plan_uses_readonly_provider_lock_and_frozen_var_file() -> None:
    text = _text()
    assert "terraform_wrapper: false" in text
    assert "-lockfile=readonly" in text
    assert 'RECONCILIATION_VARS: ../phase3-reconciliation.tfvars.json' in text
    assert '-var-file="${RECONCILIATION_VARS}"' in text
    assert "phase3-plan.auto.tfvars.json" not in text
    assert "json.dumps(data" not in text


def test_phase3_plan_reads_detailed_exit_code_without_terraform_wrapper() -> None:
    text = _text()
    assert "-detailed-exitcode" in text
    assert 'elif [[ "$status" -eq 2 ]]' in text
    assert 'echo "plan_result=changes_present"' in text


def test_phase3_plan_does_not_upload_binary_plan_or_raw_state() -> None:
    text = _text()
    assert "-out=" not in text
    assert "terraform show -json" not in text
    assert "state pull" not in text
    assert "binary_plan_uploaded=false" in text
    assert "raw_state_uploaded=false" in text
    assert "phase3-state-list.txt" in text
    assert "phase3-terraform-plan.txt" in text
    assert "reconciliation_config_sha256" in text
    assert "terraform_lock_sha256" in text


def test_phase3_plan_authenticates_with_keyless_deployer() -> None:
    text = _text()
    assert "uses: google-github-actions/auth@v3" in text
    assert "service_account: ${{ env.DEPLOYER_SERVICE_ACCOUNT }}" in text
    assert "credentials_json:" not in text
    assert "uses: google-github-actions/setup-gcloud@v3" in text


def test_phase3_plan_self_triggers_for_frozen_config_or_state_move_changes() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert '      - ".github/workflows/phase3_terraform_plan.yml"' in text
    assert '      - "deploy/runtime-v2/phase3-reconciliation.tfvars.json"' in text
    assert '      - "deploy/runtime-v2/terraform/moved.tf"' in text
    assert "schedule:" not in text


def test_state_moves_preserve_only_unchanged_underlying_resources() -> None:
    text = _moved_text()
    for old, new in (
        ("google_service_account.runtime", "google_service_account.producer"),
        (
            'google_project_iam_member.runtime_cloudsql["roles/cloudsql.client"]',
            'google_project_iam_member.database_client["producer"]',
        ),
        (
            "google_secret_manager_secret_iam_member.database_password",
            'google_secret_manager_secret_iam_member.database_password["producer"]',
        ),
    ):
        assert f"from = {old}" in text
        assert f"to   = {new}" in text
    assert text.count("moved {") == 3


def test_state_moves_do_not_hide_intended_phase3_identity_transitions() -> None:
    text = _moved_text()
    for forbidden in (
        "scheduler",
        "migration_runtime",
        "migration_import",
        "vault_runtime",
        "vault_object_admin",
        "vault_signing_key",
        "public_dashboard",
    ):
        assert forbidden not in text
