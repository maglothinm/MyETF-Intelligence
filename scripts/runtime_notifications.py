"""Stage Runtime v2 notification intents; this module never sends a message."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "durable_outbox_v1"
MODE_KEY = "POLITITRACK_NOTIFICATION_MODE"
PATH_KEY = "POLITITRACK_NOTIFICATION_OUTBOX"
NAMESPACE_KEY = "POLITITRACK_NOTIFICATION_NAMESPACE"


def deferred() -> bool:
    mode = os.environ.get(MODE_KEY, "")
    if mode not in ("", CONTRACT, "disabled"):
        raise ValueError("invalid Runtime notification mode")
    return mode == CONTRACT


def record_key(*parts: object) -> str:
    return json.dumps([str(part) for part in parts], separators=(",", ":"), ensure_ascii=True)


def delivery_id(namespace: str, channel: str, key: str) -> str:
    return hashlib.sha256(record_key(namespace, channel, key).encode()).hexdigest()


def available_date(value: str) -> str | None:
    value = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def validate_intent(intent: Mapping[str, Any], namespace: str) -> dict[str, Any]:
    required = {"schema_version", "namespace", "delivery_id", "channel", "record_key", "available_on", "payload"}
    if set(intent) != required or intent["schema_version"] != 1 or namespace not in {"legislative", "executive", "ai"}:
        raise ValueError("invalid notification intent shape")
    channel, key = intent["channel"], intent["record_key"]
    if channel not in {"pushover", "gmail"} or not isinstance(key, str) or not key or len(key) > 4096:
        raise ValueError("invalid notification identity")
    if intent["namespace"] != namespace or intent["delivery_id"] != delivery_id(namespace, channel, key):
        raise ValueError("notification intent identity mismatch")
    day = intent["available_on"]
    if day is not None and (not isinstance(day, str) or available_date(day) != day):
        raise ValueError("invalid notification availability date")
    payload = intent["payload"]
    limits = {"title": 250, "message": 10000, "url": 2048, "url_title": 100}
    if channel == "gmail" and isinstance(payload, dict) and "recipient" in payload:
        try:
            from .investor_notifications import recipient
        except ImportError:
            from investor_notifications import recipient
        recipient(payload["recipient"])
        limits["recipient"] = 254
    if not isinstance(payload, dict) or set(payload) != set(limits):
        raise ValueError("invalid notification payload")
    if any(not isinstance(payload[key], str) or len(payload[key]) > maximum for key, maximum in limits.items()):
        raise ValueError("notification payload exceeds bounds")
    return dict(intent)


def stage_notification(*, channel: str, key: str, filed_date: str, payload: Mapping[str, str]) -> bool:
    """Return true when staged; absence of runtime mode preserves legacy routing."""
    if not deferred():
        if os.environ.get(MODE_KEY) == "disabled":
            raise ValueError("notifications are disabled in this Runtime mode")
        return False
    namespace = os.environ.get(NAMESPACE_KEY, "")
    path = Path(os.environ.get(PATH_KEY, ""))
    if not path.is_absolute() or path.name != "notification-intents.jsonl" or not path.parent.is_dir() or path.is_symlink():
        raise ValueError("Runtime notification staging path is missing or unsafe")
    intent = validate_intent({
        "schema_version": 1, "namespace": namespace,
        "delivery_id": delivery_id(namespace, channel, key), "channel": channel,
        "record_key": key, "available_on": available_date(filed_date), "payload": dict(payload),
    }, namespace)
    encoded = (json.dumps(intent, sort_keys=True) + "\n").encode()
    descriptor = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "ab") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return True


def read_intents(path: Path, namespace: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("notification staging file is unsafe or too large")
    rows = [validate_intent(json.loads(line), namespace) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) > 10000:
        raise ValueError("too many notification intents")
    return rows
