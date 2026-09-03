from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3_gcp_auth_inventory.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_auth_inventory_reports_presence_only() -> None:
    text = _text()
    assert 'printf \'%s=present\\n\' "$name"' in text
    assert 'printf \'%s=absent\\n\' "$name"' in text
    assert 'printf \'%s=%s\\n\' "$name" "$value"' not in text
    assert 'echo "$value"' not in text


def test_auth_inventory_has_no_cloud_or_secret_mutation() -> None:
    text = _text()
    forbidden = (
        "google-github-actions/auth",
        "setup-gcloud",
        "gcloud ",
        "terraform ",
        "secrets versions",
        "add-iam-policy-binding",
        "create_credentials_file",
    )
    for value in forbidden:
        assert value not in text


def test_auth_inventory_is_one_shot_and_canonical() -> None:
    text = _text()
    assert "github.repository_id == '1349678672'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert 'paths:\n      - ".github/workflows/phase3_gcp_auth_inventory.yml"' in text
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
