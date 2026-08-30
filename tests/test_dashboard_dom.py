"""Optional DOM checks of an actual generated fixture build, without live browsing."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.build_trade_dashboard import build_payload, build_site, load_branch


def test_generated_dashboard_dom(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    node = os.environ.get("POLITITRACK_TEST_NODE") or shutil.which("node")
    modules = Path(os.environ.get("POLITITRACK_TEST_NODE_MODULES", repository / ".remediation/ui-test-tools/node_modules"))
    if not node or not (modules / "jsdom/package.json").exists() or not (modules / "axe-core/package.json").exists():
        pytest.skip("Optional JSDOM/axe fixture checks require Node, jsdom and axe-core")
    output = tmp_path / "dom-fixture-site"
    payload = build_payload(
        load_branch(None, "legislative"),
        load_branch(None, "executive"),
        repository_url="https://github.com/maglothinm/MyETF-Intelligence",
    )
    build_site(payload, output)
    env = dict(os.environ, POLITITRACK_TEST_BUILD=str(output), POLITITRACK_TEST_NODE_MODULES=str(modules))
    result = subprocess.run(
        [node, "--test", "tests/dashboard_dom.test.cjs"],
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
