from pathlib import Path

WORKFLOW = Path(".github/workflows/phase3_cloud_discovery.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_phase3_cloud_discovery_is_read_only_by_construction() -> None:
    text = _text()
    for value in (
        "services enable", "repositories create", "buckets create", "storage cp",
        "sql instances create", "run jobs execute", "run deploy",
        "scheduler jobs create", "scheduler jobs update", "secrets versions add",
        "secrets versions access", "add-iam-policy-binding", "builds submit",
        "terraform apply",
    ):
        assert value not in text


def test_phase3_cloud_discovery_is_pinned_to_canonical_boundary() -> None:
    text = _text()
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'PROJECT_NUMBER: "497412818801"' in text
    assert "polititrack-github-phase3/providers/phase3-main" in text
    assert "polititrack-github/providers/phase3-main" not in text
    assert "project-38008d5f-4918-46e6-920" not in text
    assert "secret-transfer" not in text


def test_phase3_cloud_discovery_uses_direct_keyless_federation() -> None:
    text = _text()
    assert text.index("uses: actions/checkout@v7") < text.index("uses: google-github-actions/auth@v3")
    assert "service_account:" not in text
    assert "credentials_json:" not in text
    assert "federation=direct" in text


def test_phase3_cloud_discovery_resolves_project_from_immutable_number() -> None:
    text = _text()
    assert 'gcloud projects describe "${PROJECT_NUMBER}"' in text
    assert "live_project_number" in text
    assert 'echo "PROJECT_ID=${project_id}" >> "${GITHUB_ENV}"' in text


def test_phase3_cloud_discovery_emits_no_secret_values() -> None:
    text = _text()
    assert "secrets list" in text
    assert "--format='value(name)'" in text
    assert "secrets versions access" not in text
    assert "secret_data" not in text


def test_phase3_cloud_discovery_has_single_path_scoped_main_push_trigger() -> None:
    text = _text()
    assert 'push:\n    branches:\n      - main\n    paths:\n      - ".github/workflows/phase3_cloud_discovery.yml"' in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text


def test_phase3_cloud_discovery_records_shadow_controls() -> None:
    text = _text()
    assert '"mode=shadow"' in text
    assert '"schedules_enabled=false"' in text
    assert '"public_dashboard_enabled=false"' in text
