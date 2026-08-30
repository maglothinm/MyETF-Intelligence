"""Exercise the production browser-local event engine with deterministic Node mocks."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_browser_local_notification_engine() -> None:
    node = os.environ.get("POLITITRACK_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable; run dashboard_notifications.test.cjs in Linux CI")
    repository = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, "--test", "tests/dashboard_notifications.test.cjs", "tests/dashboard_notification_integration.test.cjs"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
