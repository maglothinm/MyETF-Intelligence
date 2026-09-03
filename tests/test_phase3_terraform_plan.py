from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_terraform_plan.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


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


def test_phase3_plan_preserves_shadow_and_paused_scheduler_controls() -> None:
    text = _text()
    assert "POLITITRACK_MODE=\"shadow\"" in text
    assert "schedules_enabled=false" in text
    assert "public_dashboard_enabled=false" in text
    assert "vault_enabled=true" in text


def test_phase3_plan_uses_existing_immutable_image_without_building() -> None:
    text = _text()
    assert "runtime-v2@sha256:82b691179c422aba5c3ffa205e1a2d548f8cd6e8e9ed8ac2b5df5f7f8c71a565" in text
    assert "builds submit" not in text


def test_phase3_plan_does_not_upload_binary_plan_or_raw_state() -> None:
    text = _text()
    assert "-out=" not in text
    assert "terraform show -json" not in text
    assert "state pull" not in text
    assert "binary_plan_uploaded=false" in text
    assert "phase3-state-list.txt" in text
    assert "phase3-terraform-plan.txt" in text


def test_phase3_plan_authenticates_with_keyless_deployer() -> None:
    text = _text()
    assert "uses: google-github-actions/auth@v3" in text
    assert "service_account: ${{ env.DEPLOYER_SERVICE_ACCOUNT }}" in text
    assert "credentials_json:" not in text
    assert "uses: google-github-actions/setup-gcloud@v3" in text


def test_phase3_plan_self_triggers_only_when_its_workflow_changes() -> None:
    text = _text()
    assert "workflow_dispatch:" in text
    assert '      - ".github/workflows/phase3_terraform_plan.yml"' in text
    assert "schedule:" not in text
