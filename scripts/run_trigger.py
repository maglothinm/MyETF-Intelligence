"""Non-secret trigger metadata shared by the canonical production workers."""

from __future__ import annotations

import os
from typing import Mapping


def trigger_source(env: Mapping[str, str] | None = None) -> str:
    """An input labels a dispatch; it is never proof of scheduler authentication."""
    env = os.environ if env is None else env
    event = env.get("GITHUB_EVENT_NAME", "local")
    if event == "workflow_dispatch":
        return ("external_scheduler" if env.get("POLITITRACK_TRIGGER_SOURCE") == "external_scheduler"
                else "workflow_dispatch")
    if event in {"schedule", "workflow_run"}:
        return event
    return "local" if event == "local" else "unknown"
