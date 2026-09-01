"""Read-only collector freshness policy shared with dashboard presentation.

Elapsed time is evidence of missing collection, never a manufactured run. The
browser receives these policies and can keep aging a published snapshot without
depending on another successful dashboard publication.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


REQUIRED_BRANCHES = ("legislative", "executive", "ai")
FRESHNESS_POLICY = {
    "legislative": {
        "expected_interval_minutes": 15,
        "stale_after_minutes": 30,
        "cadence_label": "Every 15 minutes",
        "trigger_relationship": "Canonical collector schedule or authenticated dispatch",
    },
    "executive": {
        "expected_interval_minutes": 30,
        "stale_after_minutes": 60,
        "cadence_label": "Every 30 minutes",
        "trigger_relationship": "Canonical collector schedule or authenticated dispatch",
    },
    "ai": {
        "expected_interval_minutes": 15,
        "stale_after_minutes": 75,
        "cadence_label": "After collector success (about every 15 minutes)",
        "trigger_relationship": (
            "workflow_run after successful collectors; 75-minute freshness bound "
            "allows the Legislative 30-minute freshness window plus the AI job's "
            "45-minute timeout. This is an input opportunity, not a separate AI cron."
        ),
    },
}
WORKFLOWS = {
    "legislative": ("legislative_trade_tracker_v2.yml", "Legislative purchase tracker v2"),
    "executive": ("executive_trade_tracker.yml", "Executive purchase tracker"),
    "ai": ("ai_filing_analyst.yml", "AI filing analyst and paper portfolio"),
}
TRIGGER_SOURCES = frozenset({"schedule", "workflow_dispatch", "external_scheduler", "manual_test", "workflow_run"})
_NONPRODUCTION = frozenset({"test", "testing", "synthetic", "simulation", "manual_test", "local", "publication", "publish", "pages"})


def utc_instant(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def utc_string(value: Any) -> str | None:
    instant = utc_instant(value)
    return instant.isoformat().replace("+00:00", "Z") if instant is not None else None


def _flag(value: Any) -> bool:
    return value is True or isinstance(value, str) and value.strip().casefold() == "true"


def nonproduction_evidence(row: Mapping[str, Any]) -> bool:
    """Recognize explicit exclusions before private metadata is redacted."""
    if any(_flag(row.get(key)) for key in ("is_nonproduction", "is_synthetic_test", "is_temporary", "is_simulation", "simulation", "is_test", "test")):
        return True
    if row.get("test_metadata") or row.get("simulation_id"):
        return True
    if any(str(row.get(key) or "").strip().casefold() in _NONPRODUCTION
           for key in ("event_name", "trigger_source", "mode", "execution_mode", "environment", "source")):
        return True
    return any(re.search(r"(?:^|[|:])(?:TEST|SIMULATION)(?:[-_:]|$)", str(row.get(key) or ""), re.I)
               for key in ("run_key", "filing_key", "report_id", "trade_id", "analysis_id"))


def production_run(row: Mapping[str, Any], branch: str) -> bool:
    """Reject explicit nonproduction identity, while retaining legacy history.

    The caller supplies histories from provenance-validated production artifacts.
    Older histories lack workflow/event metadata; absence is not invented identity.
    Any conflicting identity or TEST marker, when present, disqualifies the row.
    """
    if branch not in WORKFLOWS or row.get("branch") not in (None, "", branch) or nonproduction_evidence(row):
        return False
    filename, display_name = WORKFLOWS[branch]
    for key in ("workflow_file", "workflow_path", "path"):
        value = str(row.get(key) or "").split("@", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
        if value and value != filename:
            return False
    for key in ("workflow_name", "workflow"):
        value = row.get(key)
        if isinstance(value, str) and value and value not in {display_name, filename, ".github/workflows/" + filename}:
            return False
    return True


def trigger_source(row: Mapping[str, Any]) -> str | None:
    value = row.get("trigger_source") or row.get("event_name")
    return value if isinstance(value, str) and value in TRIGGER_SOURCES else None


def branch_freshness(
    branch: str,
    *,
    last_success_utc: Any,
    latest_run_success: bool | None,
    latest_status: str,
    as_of: Any,
    evidence_incomplete: bool = False,
) -> dict[str, Any]:
    """Evaluate immutable completion evidence at a supplied UTC instant.

    Latest failure wins even when an earlier successful run is recent. A run is
    stale strictly after its threshold; exactly on the boundary remains fresh.
    Overdue/missed intervals are estimates since successful completion, not proof
    that a scheduler dispatched or skipped a particular wall-clock cron window.
    """
    policy = FRESHNESS_POLICY[branch]
    clock, success = utc_instant(as_of), utc_instant(last_success_utc)
    valid = clock is not None and success is not None and success <= clock
    age = (clock - success).total_seconds() / 60 if valid else None
    interval, threshold = policy["expected_interval_minutes"], policy["stale_after_minutes"]
    fresh = age <= threshold if age is not None else None
    status = "unknown"
    if latest_status == "failure":
        status = "failure"
    elif fresh is False:
        status = "stale"
    elif fresh is True and latest_run_success is True and latest_status == "success" and not evidence_incomplete:
        status = "success"
    return {
        "branch": branch, "status": status,
        "last_success_utc": utc_string(success) if valid else None,
        "latest_run_success": latest_run_success,
        "fresh": fresh,
        "age_minutes": round(age, 3) if age is not None else None,
        "age_seconds": int(age * 60) if age is not None else None,
        "expected_interval_minutes": interval,
        "expected_cadence_seconds": interval * 60,
        "stale_after_minutes": threshold,
        "next_expected_utc": utc_string(success + timedelta(minutes=interval)) if valid else None,
        "overdue_minutes": round(max(0, age - interval), 3) if age is not None else None,
        "estimated_missed_intervals": max(0, math.floor(age / interval) - 1) if age is not None else None,
        "cadence_label": policy["cadence_label"],
        "trigger_relationship": policy["trigger_relationship"],
        "evidence_incomplete": evidence_incomplete,
    }


def overall_status(branches: list[Mapping[str, Any]]) -> str:
    statuses = {row.get("status", "unknown") for row in branches}
    if {row.get("branch") for row in branches} != set(REQUIRED_BRANCHES):
        statuses.add("unknown")
    return next((status for status in ("failure", "stale", "unknown", "success") if status in statuses), "unknown")
