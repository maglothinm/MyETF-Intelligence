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
        "required_markers": (),
        "forbidden_markers": (),
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
        "forbidden_markers": (),
    },
    "ai_filing_analyst.yml": {
        "required_triggers": ("workflow_dispatch", "workflow_run"),
        "required_job": "analyze",
        "required_markers": ("ai-analysis-state", "scripts/ai_filing_analyst.py"),
        "one_of_markers": (),
        "must_be_active": False,
        "forbidden_markers": (),
    },
    "publish_trade_dashboard.yml": {
        "required_triggers": ("workflow_dispatch", "workflow_run"),
        "required_job": "build",
        "required_markers": ("scripts/build_trade_dashboard.py",),
        "one_of_markers": (),
        "must_be_active": False,
        "forbidden_markers": (),
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


def _direct_keys_at(block: list[str], indent: int) -> set[str]:
    prefix = " " * indent
    result: set[str] = set()
    for line in block:
        match = re.match(rf"^{re.escape(prefix)}([A-Za-z0-9_-]+):(?:\s|$)", line)
        if match:
            result.add(match.group(1))
    return result


def _nested_block(lines: list[str], indent: int, key: str) -> list[str]:
    prefix = " " * indent
    start = None
    for index, line in enumerate(lines):
        if re.fullmatch(rf"{re.escape(prefix + key)}:\s*(?:#.*)?", line):
            start = index + 1
            break
    if start is None:
        raise LegacyRouteContractError(f"source contract has no {key} block")
    output: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent:
                break
        output.append(line)
    return output


def _field_value(lines: list[str], indent: int, key: str) -> str:
    prefix = " " * indent
    for index, line in enumerate(lines):
        match = re.fullmatch(rf"{re.escape(prefix + key)}:\s*(.*)", line)
        if not match:
            continue
        first = match.group(1).strip()
        values = [] if first in {"", ">", ">-", "|", "|-"} else [first]
        for continuation in lines[index + 1:]:
            stripped = continuation.strip()
            if not stripped or stripped.startswith("#"):
                continue
            current_indent = len(continuation) - len(continuation.lstrip())
            if current_indent <= indent:
                break
            values.append(stripped)
        return " ".join(values)
    return ""


def _step_blocks(job_block: list[str]) -> list[list[str]]:
    steps = _nested_block(job_block, 4, "steps")
    starts = [
        index for index, line in enumerate(steps)
        if re.match(r"^      -(?:\s|$)", line)
    ]
    output = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(steps)
        output.append(steps[start:end])
    return output


def _named_step(job_block: list[str], name: str) -> list[str]:
    matches = []
    for step in _step_blocks(job_block):
        first = step[0].strip()
        first_name = first.split(":", 1)[1].strip() if first.startswith("- name:") else ""
        nested_name = _field_value(step, 8, "name")
        if (first_name or nested_name).strip('"\'') == name:
            matches.append(step)
    if len(matches) != 1:
        raise LegacyRouteContractError(
            f"Legislative producer requires exactly one {name} step"
        )
    return matches[0]


def _step_direct_value(step: list[str], key: str) -> str:
    first = step[0].strip()
    if first.startswith(f"- {key}:"):
        return first.split(":", 1)[1].strip()
    return _field_value(step, 8, key)


def _verify_legislative_source(text: str) -> None:
    lines = text.splitlines()
    on_block = _nested_block(lines, 0, "on")
    schedule = _nested_block(on_block, 2, "schedule")
    meaningful_schedule = [line for line in schedule if line.strip() and not line.strip().startswith("#")]
    if meaningful_schedule != [
        '    - cron: "7,22,37,52 * * * *"',
        '      timezone: "America/New_York"',
    ]:
        raise LegacyRouteContractError("Legislative production schedule is not exact")

    dispatch = _nested_block(on_block, 2, "workflow_dispatch")
    inputs = _nested_block(dispatch, 4, "inputs")
    if _direct_keys_at(inputs, 6) != {"trigger_source"}:
        raise LegacyRouteContractError("Legislative dispatch inputs are not exact")
    trigger_source = _nested_block(inputs, 6, "trigger_source")
    if (
        _field_value(trigger_source, 8, "required").strip('"\'') != "false"
        or _field_value(trigger_source, 8, "default").strip('"\'') != "workflow_dispatch"
        or _field_value(trigger_source, 8, "type").strip('"\'') != "choice"
    ):
        raise LegacyRouteContractError("Legislative trigger_source input is not production-safe")
    options = _nested_block(trigger_source, 8, "options")
    option_values = [line.strip()[2:].strip('"\'') for line in options if line.strip().startswith("- ")]
    if option_values != ["workflow_dispatch", "external_scheduler"]:
        raise LegacyRouteContractError("Legislative trigger_source options are not exact")

    env_block = _nested_block(lines, 0, "env")
    if _field_value(env_block, 2, "POLITITRACK_CONTROLLED_VALIDATION") != '"false"':
        raise LegacyRouteContractError("Legislative workflow remains in controlled mode")
    trigger_value = _field_value(env_block, 2, "POLITITRACK_TRIGGER_SOURCE")
    if not all(token in trigger_value for token in (
        "github.event_name", "inputs.trigger_source", "workflow_dispatch",
    )):
        raise LegacyRouteContractError("Legislative trigger-source routing is incomplete")

    jobs = _nested_block(lines, 0, "jobs")
    job = _nested_block(jobs, 2, "track")
    condition = _field_value(job, 4, "if")
    if condition != (
        "github.repository_id == '1349678672' && "
        "github.ref_name == github.event.repository.default_branch"
    ):
        raise LegacyRouteContractError(
            "Legislative producer job is not schedule-eligible on canonical main"
        )

    start = _named_step(job, "Signal tracker start")
    terminal = _named_step(job, "Signal tracker terminal result")
    failure = _named_step(job, "Send Pushover failure notification")
    tracker = _named_step(job, "Track House and Senate purchases")
    durable = _named_step(job, "Classify durable Legislative result")
    upload = _named_step(job, "Upload protected tracker state")
    step_order = _step_blocks(job)
    if not (step_order.index(tracker) < step_order.index(durable) < step_order.index(upload)):
        raise LegacyRouteContractError("Legislative validation/upload step order is unsafe")
    for step in step_order:
        run_value = _step_direct_value(step, "run")
        step_id = _step_direct_value(step, "id").strip('"\'')
        if "--no-notify" in run_value:
            raise LegacyRouteContractError("Legislative job retains notification suppression")
        if "--validate-protected-upload" in run_value or step_id == "state_validation":
            raise LegacyRouteContractError(
                "Legislative job retains suppression-specific state validation"
            )
    for line in job:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if re.match(r'^POLITITRACK_CONTROLLED_VALIDATION:\s*["\']?true["\']?$', stripped):
            raise LegacyRouteContractError("Legislative job overrides controlled mode")

    tracker_run = _step_direct_value(tracker, "run")
    tracker_env = _nested_block(tracker, 8, "env")
    if (
        _step_direct_value(tracker, "id").strip('"\'') != "tracker"
        or "python scripts/government_trade_tracker.py" not in tracker_run
        or "--branch legislative --source all" not in tracker_run
        or "--no-notify" in tracker_run
        or "secrets.PUSHOVER_API_TOKEN" not in _field_value(tracker_env, 10, "PUSHOVER_API_TOKEN")
        or "secrets.PUSHOVER_USER_KEY" not in _field_value(tracker_env, 10, "PUSHOVER_USER_KEY")
        or _step_direct_value(tracker, "continue-on-error").strip('"\'') == "true"
    ):
        raise LegacyRouteContractError("Legislative tracker step is not production-wired")

    durable_run = _step_direct_value(durable, "run")
    if (
        _step_direct_value(durable, "id").strip('"\'') != "durable_validation"
        or _step_direct_value(durable, "continue-on-error").strip('"\'') == "true"
        or not all(marker in durable_run for marker in (
            "--validate-durable",
            '--state "$STATE_FILE"',
            '--source-status "$SOURCE_STATUS_FILE"',
            '--restore-receipt "$RESTORE_RECEIPT_FILE"',
            "--require-restore-receipt",
        ))
        or "--validate-protected-upload" in durable_run
    ):
        raise LegacyRouteContractError("Legislative durable-result gate is incomplete")

    upload_if = _step_direct_value(upload, "if")
    upload_with = _nested_block(upload, 8, "with")
    if (
        "actions/upload-artifact@" not in _step_direct_value(upload, "uses")
        or not all(marker in upload_if for marker in (
            "success()",
            "steps.tracker.outcome == 'success'",
            "steps.durable_validation.outcome == 'success'",
        ))
        or _field_value(upload_with, 10, "name").strip('"\'') != "legislative-tracker-state"
        or _field_value(upload_with, 10, "path").strip('"\'') != ".trade-tracker/legislative"
        or _field_value(upload_with, 10, "if-no-files-found").strip('"\'') != "error"
        or _field_value(upload_with, 10, "include-hidden-files").strip('"\'') != "true"
    ):
        raise LegacyRouteContractError("Legislative protected upload is not durably gated")

    for label, step in (("start", start), ("terminal", terminal)):
        step_env = _nested_block(step, 8, "env")
        heartbeat = _field_value(step_env, 10, "HEALTHCHECKS_PING_URL")
        if "secrets.LEGISLATIVE_HEALTHCHECKS_PING_URL" not in heartbeat:
            raise LegacyRouteContractError(f"Legislative {label} heartbeat is not wired")
    failure_env = _nested_block(failure, 8, "env")
    if (
        "secrets.PUSHOVER_API_TOKEN" not in _field_value(failure_env, 10, "PUSHOVER_API_TOKEN")
        or "secrets.PUSHOVER_USER_KEY" not in _field_value(failure_env, 10, "PUSHOVER_USER_KEY")
    ):
        raise LegacyRouteContractError("Legislative failure notification is not wired")


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
        if filename == "legislative_trade_tracker_v2.yml":
            _verify_legislative_source(text)
        for marker in contract["required_markers"]:
            if marker not in text:
                raise LegacyRouteContractError(f"{filename} lacks required route marker {marker}")
        for marker in contract["forbidden_markers"]:
            if marker in text:
                raise LegacyRouteContractError(
                    f"{filename} retains controlled-only route marker {marker}"
                )
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
