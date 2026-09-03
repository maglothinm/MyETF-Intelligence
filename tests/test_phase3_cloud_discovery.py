from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_cloud_discovery.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_phase3_cloud_discovery_is_read_only_by_construction() -> None:
    text = _text()
    forbidden = (
        "services enable",
        "artifacts repositories create",
        "storage buckets create",
        "storage cp",
        "sql instances create",
        "run jobs execute",
        "run deploy",
        "scheduler jobs create",
        "scheduler jobs update",
        "secrets versions add",
        "projects add-iam-policy-binding",
        "builds submit",
        "terraform apply",
    )
    for value in forbidden:
        assert value not in text


def test_phase3_cloud_discovery_is_pinned_to_canonical_boundary() -> None:
    text = _text()
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "project-38008d5f-4918-46e6-920" in text
    assert "497412818801" in text
    assert "projects/497412818801/locations/global/workloadIdentityPools/polititrack-github/providers/secret-transfer" in text
    assert "polititrack-secret-transfer@project-38008d5f-4918-46e6-920.iam.gserviceaccount.com" in text


def test_phase3_cloud_discovery_emits_no_secret_values() -> None:
    text = _text()
    assert "secrets list" in text
    assert "--format='value(name)'" in text
    assert "secrets versions access" not in text
    assert "secret_data" not in text
    assert "secrets." not in text


def test_phase3_cloud_discovery_runs_only_when_it_is_added_or_dispatched() -> None:
    text = _text()
    assert 'paths:\n      - ".github/workflows/phase3_cloud_discovery.yml"' in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text


def test_phase3_cloud_discovery_records_shadow_controls() -> None:
    text = _text()
    assert '"mode=shadow"' in text
    assert '"schedules_enabled=false"' in text
    assert '"public_dashboard_enabled=false"' in text
