from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parents[1] / "deploy" / "runtime-v2" / "verify_legacy_route_contract.py"
)
SPEC = importlib.util.spec_from_file_location("verify_legacy_route_contract", MODULE_PATH)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)

STATES = {
    "legislative_trade_tracker_v2.yml": "active",
    "executive_trade_tracker.yml": "active",
    "ai_filing_analyst.yml": "disabled_manually",
    "publish_trade_dashboard.yml": "active",
}


def write_workflow(root: Path, name: str, triggers: str, job: str, body: str) -> None:
    path = root / ".github" / "workflows" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"name: test\n\non:\n{triggers}\n\njobs:\n  {job}:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {body}\n",
        encoding="utf-8",
    )


def valid_root(tmp_path: Path) -> Path:
    write_workflow(
        tmp_path,
        "legislative_trade_tracker_v2.yml",
        "  schedule:\n    - cron: '1 * * * *'\n  workflow_dispatch:",
        "track",
        "python scripts/run_legislative_sources_resilient.py && echo legislative-tracker-state",
    )
    write_workflow(
        tmp_path,
        "executive_trade_tracker.yml",
        "  schedule:\n    - cron: '2 * * * *'\n  workflow_dispatch:",
        "track",
        "python scripts/government_trade_tracker.py && echo executive-tracker-state",
    )
    write_workflow(
        tmp_path,
        "ai_filing_analyst.yml",
        "  workflow_dispatch:\n  workflow_run:",
        "analyze",
        "python scripts/ai_filing_analyst.py && echo ai-analysis-state",
    )
    write_workflow(
        tmp_path,
        "publish_trade_dashboard.yml",
        "  workflow_dispatch:\n  workflow_run:",
        "build",
        "python scripts/build_trade_dashboard.py",
    )
    return tmp_path


def test_accepts_complete_source_and_trigger_contract(tmp_path: Path) -> None:
    receipt = verifier.verify_legacy_route(valid_root(tmp_path), STATES)
    assert receipt["result"] == "legacy_rollback_route_verified"
    assert receipt["legacy_production_route_active"] is True
    assert receipt["workflows"]["legislative_trade_tracker_v2.yml"]["state"] == "active"


def test_rejects_recovery_only_legislative_workflow(tmp_path: Path) -> None:
    root = valid_root(tmp_path)
    write_workflow(
        root,
        "legislative_trade_tracker_v2.yml",
        "  push:\n    branches: [main]\n  workflow_dispatch:",
        "track",
        "echo legislative-tracker-state",
    )
    with pytest.raises(verifier.LegacyRouteContractError, match="lacks rollback trigger.*schedule"):
        verifier.verify_legacy_route(root, STATES)


def test_rejects_disabled_collector(tmp_path: Path) -> None:
    states = dict(STATES)
    states["executive_trade_tracker.yml"] = "disabled_manually"
    with pytest.raises(verifier.LegacyRouteContractError, match="rollback collector"):
        verifier.verify_legacy_route(valid_root(tmp_path), states)
