from pathlib import Path


def test_shared_controller_uses_supported_cloud_run_execution_lookup():
    text = Path("deploy/runtime-v2/runtime_promotion_control.sh").read_text(encoding="utf-8")
    assert "gcloud run jobs executions describe-latest" not in text
    assert "status.latestCreatedExecution.name" in text
    assert "Unable to resolve the latest execution for" in text
