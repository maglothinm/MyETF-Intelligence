"""Public, bounded OCR stage telemetry. Never infer OCR success from collection."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA_VERSION = 1
STAGES = frozenset({"disabled", "waiting_for_collection", "processing", "awaiting_commit", "complete", "failed", "skipped"})
COUNTS = (
    "inventory_count", "eligible_count", "documents_attempted", "documents_completed",
    "extractions_reused", "acknowledgements_replayed", "pages_completed", "pages_expected",
    "transactions_appended", "complete_count", "needs_review_count", "access_required_count",
    "retry_delayed_count", "not_applicable_count", "ready_remaining", "review_remaining",
    "access_remaining", "retry_remaining", "unobserved_remaining",
)
TIMES = ("started_at", "heartbeat_at", "finished_at", "last_document_completed_at", "oldest_ready_at")
CODE_KEYS = ("error_code", "intake_error_code", "cleanup_error_code")


def instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except ValueError:
        return None


def safe_metrics(value: Mapping[str, Any]) -> dict[str, Any]:
    """Whitelist stage fields: no raw documents, URLs, account IDs or stderr."""
    if not isinstance(value, Mapping) or value.get("stage") not in STAGES:
        raise ValueError("invalid_ocr_health_stage")
    result = {"schema_version": SCHEMA_VERSION, "enabled": value.get("enabled") is True, "stage": value["stage"]}
    for key in COUNTS:
        number = value.get(key, 0)
        if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= 1_000_000_000:
            raise ValueError("invalid_ocr_health_count")
        result[key] = number
    for key in TIMES:
        date = value.get(key)
        if date is not None:
            parsed = instant(date)
            if parsed is None:
                raise ValueError("invalid_ocr_health_timestamp")
            result[key] = parsed.isoformat().replace("+00:00", "Z")
    for key in CODE_KEYS:
        code = value.get(key)
        if code:
            # Only code-shaped identifiers. Document text is never a health error.
            result[key] = code if isinstance(code, str) and len(code) <= 100 and code.isascii() and all(c.isalnum() or c == "_" for c in code) else "unclassified_error"
    for key, allowed in (("intake_status", {"pending", "ok", "failed"}),
                         ("cleanup_status", {"pending", "complete", "deferred", "not_needed"})):
        if value.get(key) in allowed:
            result[key] = value[key]
    version = value.get("engine_version")
    if isinstance(version, str) and len(version) <= 80 and all(c.isalnum() or c in "._-" for c in version):
        result["engine_version"] = version
    seconds = value.get("duration_seconds")
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and 0 <= seconds <= 86400:
        result["duration_seconds"] = round(seconds, 3)
    return result


def run_health(metrics: Any, run: Mapping[str, Any], as_of: datetime | None,
               stale_after_minutes: float = 90) -> dict[str, Any]:
    """Derive an OCR outcome separately from the parent run's conclusion."""
    result: dict[str, Any] = {"status": "unknown", "activity": "not_reported", "enabled": None,
                              "detail": "This run has no verified OCR-stage evidence.",
                              "run_id": run.get("id") or run.get("run_key"), "stale_after_minutes": stale_after_minutes}
    if not isinstance(metrics, Mapping):
        return result
    try:
        clean = safe_metrics(metrics)
    except ValueError:
        result["detail"] = "OCR-stage telemetry is malformed; success is not established."
        return result
    result.update(clean)
    result["activity"] = clean["stage"]
    if not clean["enabled"]:
        result.update(activity="disabled", detail="OCR was disabled for this source run.")
        return result
    start, heartbeat, finish = (instant(clean.get(key)) for key in ("started_at", "heartbeat_at", "finished_at"))
    parent_start = instant(run.get("started_utc") or run.get("producer_job_started_utc"))
    document_finished = instant(clean.get("last_document_completed_at"))
    if (not as_of or not start or not heartbeat or heartbeat < start or heartbeat > as_of
        or (parent_start and start < parent_start) or (document_finished and (document_finished < start or document_finished > heartbeat)) or (finish and (finish < start or finish > as_of or heartbeat < finish))):
        result.update(activity="invalid_evidence", detail="OCR timestamps cannot establish a current processing outcome.")
        return result
    result["age_minutes"] = max(0, (as_of - (finish or heartbeat)).total_seconds() / 60)
    if clean["stage"] == "failed":
        result.update(status="failure", detail="OCR processing failed; collector success does not clear this failure.")
    elif clean["stage"] == "skipped":
        result.update(activity="blocked_by_collection", detail="Source collection failed before OCR completed; this is not an OCR success.")
    elif clean["stage"] in {"processing", "waiting_for_collection", "awaiting_commit"}:
        limit = 30 if clean["stage"] == "waiting_for_collection" else 10
        result["heartbeat_limit_minutes"] = limit
        if result["age_minutes"] > limit:
            result.update(status="stale", activity="stalled", detail="OCR has no recent stage heartbeat; processing may have stopped.")
        else:
            result["detail"] = {"processing": "OCR is processing documents; a committed outcome is not yet confirmed.",
                                "waiting_for_collection": "OCR is waiting for this run's source collection to complete.",
                                "awaiting_commit": "OCR evidence is awaiting confirmed snapshot commit and cleanup."}[clean["stage"]]
    elif clean["stage"] == "complete":
        if not finish or run.get("status") != "success" or not run.get("state_evidence", False):
            result.update(activity="unconfirmed_commit", detail="OCR has no matching successful canonical commit.")
        elif clean.get("intake_status") == "failed" or clean.get("cleanup_status") == "deferred" or clean["retry_delayed_count"] or clean["retry_remaining"]:
            result.update(status="failure", activity="degraded", detail="OCR completed only partially: intake, document processing or post-commit cleanup needs attention.")
        elif clean.get("cleanup_status") not in {"complete", "not_needed"}:
            result.update(activity="cleanup_unconfirmed", detail="OCR cleanup is not confirmed; files may still be awaiting acknowledgement.")
        elif result["age_minutes"] > stale_after_minutes:
            result.update(status="stale", activity="overdue", detail="The latest completed OCR maintenance pass is overdue.")
        else:
            result.update(status="success", activity="idle" if not clean["documents_attempted"] and not clean["acknowledgements_replayed"] else "complete",
                          detail="OCR maintenance completed; documents needing interpretation or access are tracked separately.")
    return result


def branch_health(timeline: list[Mapping[str, Any]], as_of: datetime | None,
                  stale_after_minutes: float = 90) -> dict[str, Any]:
    """Latest attempt wins. Do not let an older success hide a newer OCR fault."""
    if not timeline:
        return run_health(None, {}, as_of, stale_after_minutes)
    result = run_health(timeline[0].get("source_ocr_metrics"), timeline[0], as_of, stale_after_minutes)
    result["required"] = any((row.get("source_ocr_metrics") or {}).get("enabled") is True for row in timeline)
    successes = [run_health(row.get("source_ocr_metrics"), row, as_of, stale_after_minutes) for row in timeline]
    result["last_success_at"] = next((row.get("finished_at") for row in successes
        if row["status"] in {"success", "stale"} and row.get("stage") == "complete" and row.get("cleanup_status") in {"complete", "not_needed"}), None)
    result["last_document_completed_at"] = next((row.get("last_document_completed_at") for row in successes if row.get("last_document_completed_at")), None)
    # A due backlog with no movement over three independent completed attempts is
    # a stall. Waiting for access/review/backoff alone is not a stall.
    recent = successes[:3]
    if len(recent) == 3 and len({row.get("run_id") for row in recent}) == 3 and result["status"] == "success" and all(
        row.get("stage") == "complete" and row.get("ready_remaining", 0) > 0 and
        row.get("documents_attempted", 0) == 0 and row.get("acknowledgements_replayed", 0) == 0 for row in recent
    ):
        result.update(status="stale", activity="stalled", detail="Ready OCR work made no progress across three source runs.")
    return result
