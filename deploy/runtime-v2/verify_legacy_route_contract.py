#!/usr/bin/env python3
"""Verify that the checked-in legacy workflows still form a usable rollback route."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPOSITORY_ID = 1349678672
WORKFLOW_CONTRACTS = {
    "legislative_trade_tracker_v2.yml": {
        "required_triggers": ("schedule", "workflow_dispatch"),
        "required_job": "track",
        "required_markers": ("legislative-tracker-state",),
        "one_of_markers": (
            "scripts/government_trade_tracker.py",
            "scripts/run_legislative_sources_resilient.py",
        ),
        "must_be_active": True,
    },
    "executive_trade_tracker.yml": {
        "required_triggers": ("schedule", "workflow_dispatch"),
        "required_job": "track",
        "required_markers": (
            "executive-tracker-state",
            "scripts/government_trade_tracker.py",
        ),
        "one_of_markers": (),
        "must_be_active": True,
    },
    "ai_filing_analyst.yml": {
        "required_triggers": ("workflow_dispatch", "workflow_run"),
        "required_job": "analyze",
        "required_markers": ("ai-analysis-state", "scripts/ai_filing_analyst.py"),
        "one_of_markers": (),
        "must_be_active": False,
    },
    "publish_trade_dashboard.yml": {
        "required_triggers": ("workflow_dispatch", "workflow_run"),
        "required_job": "build",
        "required_markers": ("scripts/build_trade_dashboard.py",),
        "one_of_markers": (),
        "must_be_active": False,
    },
}


class LegacyRouteContractError(ValueError):
    """Raised when a legacy workflow cannot serve as the retained rollback route."""


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise LegacyRouteContractError(f"{path} is not a JSON object")
    return value


def _top_level_block(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.fullmatch(rf"{re.escape(name)}:\s*(?:#.*)?", line):
            start = index + 1
            break
    if start is None:
        raise LegacyRouteContractError(f"workflow has no top-level {name} block")
    output: list[str] = []
    for line in lines[start:]:
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            break
        output.append(line)
    return output


def _direct_keys(block: list[str]) -> set[str]:
    result: set[str] = set()
    for line in block:
        match = re.match(r"^  ([A-Za-z0-9_-]+):(?:\s|$)", line)
        if match:
            result.add(match.group(1))
    return result


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_legacy_route(root: Path, workflow_states: dict[str, Any]) -> dict[str, Any]:
    expected_names = set(WORKFLOW_CONTRACTS)
    if set(workflow_states) != expected_names:
        raise LegacyRouteContractError("legacy workflow-state inventory is not exact")

    receipts: dict[str, Any] = {}
    for filename, contract in WORKFLOW_CONTRACTS.items():
        state = workflow_states.get(filename)
        if state not in {"active", "disabled_manually"}:
            raise LegacyRouteContractError(f"unsupported workflow state {filename}={state}")
        if contract["must_be_active"] and state != "active":
            raise LegacyRouteContractError(f"rollback collector {filename} is not active")

        path = root / ".github" / "workflows" / filename
        data = path.read_bytes()
        text = data.decode("utf-8")
        triggers = _direct_keys(_top_level_block(text, "on"))
        jobs = _direct_keys(_top_level_block(text, "jobs"))

        missing_triggers = sorted(set(contract["required_triggers"]) - triggers)
        if missing_triggers:
            raise LegacyRouteContractError(
                f"{filename} lacks rollback trigger(s): {', '.join(missing_triggers)}"
            )
        required_job = str(contract["required_job"])
        if required_job not in jobs:
            raise LegacyRouteContractError(f"{filename} lacks rollback job {required_job}")
        for marker in contract["required_markers"]:
            if marker not in text:
                raise LegacyRouteContractError(f"{filename} lacks required route marker {marker}")
        alternatives = tuple(contract["one_of_markers"])
        if alternatives and not any(marker in text for marker in alternatives):
            raise LegacyRouteContractError(f"{filename} has no recognized producer entry point")

        receipts[filename] = {
            "sha256": _sha256(data),
            "state": state,
            "triggers": sorted(triggers),
            "producer_job": required_job,
        }

    return {
        "schema_version": 1,
        "result": "legacy_rollback_route_verified",
        "repository_id": REPOSITORY_ID,
        "legacy_production_route_active": True,
        "workflows": receipts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--workflow-states", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    receipt = verify_legacy_route(args.root, _load_object(args.workflow_states))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
