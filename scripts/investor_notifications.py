"""Owner-requested Investor Edge alerts on the existing atomic Runtime outbox."""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import runtime_notifications as outbox
except ImportError:
    import runtime_notifications as outbox

POLICY_PATH = Path(__file__).resolve().parents[1] / "config/investor_notifications.json"
JOURNAL_FILE = "investor-edge-alerts.json"


def recipient(value: str) -> str:
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r"[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+", value):
        raise ValueError("Invalid investor notification recipient")
    return value


def policy() -> dict[str, Any]:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    threshold = value.get("edge_threshold")
    if not isinstance(value.get("enabled"), bool) or isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError("Invalid investor notification policy")
    recipient(value.get("recipient"))
    return value


def runtime_recipient() -> str:
    if not outbox.deferred():
        return ""
    value = policy()
    return value["recipient"] if value["enabled"] else ""


def _journal(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "profiles": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("profiles"), dict):
        raise ValueError("Invalid Investor Edge alert history")
    for key, entry in value["profiles"].items():
        if not isinstance(key, str) or not isinstance(entry, dict) or not isinstance(entry.get("above"), bool) or type(entry.get("episode")) is not int or entry["episode"] < 0:
            raise ValueError("Invalid Investor Edge alert history entry")
    return value


def stage_profile_alerts(ai_dir: Path, profiles: Mapping[str, Mapping[str, Any]], *, dashboard_url: str, suppress_alerts: bool, now: datetime | None = None) -> int:
    """One email per observed crossing, including initially qualifying profiles.

    The new journal travels inside the existing AI snapshot. Unknown, stale, or
    absent evidence never resets eligibility or replays an already staged alert.
    Delivery availability is the time the current profile threshold is observed,
    independent of the dates of the historical trades used to calculate it.
    """
    address = runtime_recipient() if not suppress_alerts else ""
    if not address:
        return 0
    configured = policy()
    path = Path(ai_dir) / JOURNAL_FILE
    journal = _journal(path)
    at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    staged = 0
    for key, profile in sorted(profiles.items()):
        if not isinstance(profile, Mapping) or profile.get("is_synthetic_test") is True or profile.get("simulation") is True or str(key).casefold().startswith(("test:", "test-", "simulation:")):
            continue
        score = profile.get("edge_score")
        if (isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 100
                or profile.get("minimum_sample_met") is not True or profile.get("profile_status") not in {"complete", "partial"}):
            continue
        prior = journal["profiles"].get(key, {"above": False, "episode": 0})
        above = score > configured["edge_threshold"]
        episode = prior["episode"] + int(above and not prior["above"])
        if above and not prior["above"]:
            identity = profile.get("identity") or {}
            filer = str(profile.get("filer") or profile.get("filer_name") or identity.get("filer") or identity.get("filer_name") or key)
            owner = str(profile.get("owner") or profile.get("owner_raw") or "Owner unavailable")
            url = dashboard_url.rstrip("/") + "/investor-edge.html"
            message = (f"{filer} / {owner}\nInvestor Edge rating: {score:g}\n"
                       f"Alert rule: strictly above {configured['edge_threshold']:.1f}\n"
                       f"Completed observations: {profile.get('sample_count', 'Unavailable')}\n"
                       f"Profile as of: {profile.get('as_of_date', 'Unavailable')}\n"
                       f"Observed: {at}\n\n{url}\n\nPaper research for review.")
            outbox.stage_notification(channel="gmail", key=outbox.record_key("investor-edge-threshold-v1", address, key, episode), filed_date=at,
                                      payload={"title": f"PolitiTrack Investor Edge: {filer} — {score:g}"[:250], "message": message[:10000], "url": url[:2048], "url_title": "Investor profile", "recipient": address})
            staged += 1
        journal["profiles"][key] = {"above": above, "episode": episode}
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(journal, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    return staged
