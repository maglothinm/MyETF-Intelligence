"""Read-only backfill accounting; never score trades or fetch market data.

The journal is carried inside the existing AI observation snapshot. A producer
records one successful maintenance pass; dashboard builds do not advance it.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import math
import statistics
from typing import Any, Callable, Mapping, Sequence

VERSION = 1
CATEGORIES = ("completed", "ready", "queued", "awaiting_maturity", "awaiting_retry", "missing_data", "blocked", "unknown")
LABELS = {
    "caught_up": "Caught up on currently computable history",
    "queued": "Historical work queued",
    "awaiting_maturity": "Waiting for outcome maturity",
    "awaiting_retry": "Waiting for the next eligible retry",
    "missing_data": "Waiting for market data",
    "blocked": "Historical processing needs attention",
    "stalled": "Computable historical work is not advancing",
    "unknown": "Historical backfill status unavailable",
    "disabled": "Historical backfill is disabled",
    "empty": "No eligible history in the published population",
}
REASONS = {
    "complete": "All configured outcomes are available.",
    "cached_work_ready": "Cached prices can complete at least one missing outcome.",
    "unattempted": "Awaiting first evaluation; price availability is not yet established.",
    "outcome_not_mature": "More observed trading sessions are needed. Future returns cannot be backfilled.",
    "daily_attempt_limit": "Already attempted for this UTC date; eligible again on the next UTC date.",
    "provider_backoff": "The previous price lookup was unavailable; the existing retry backoff is active.",
    "prices_missing_or_stale": "Prices are absent, incomplete or not current enough to distinguish a gap from an immature outcome.",
    "invalid_observation": "Required observation identity or date evidence is unavailable.",
    "stale_profile": "A last-good profile is displayed; its current work inventory cannot be established.",
    "no_market_credentials": "Market data credentials are not configured. Configure the existing provider securely; do not enter secrets here.",
}


def instant(value: Any) -> datetime | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def day(value: Any) -> date | None:
    parsed = instant(value)
    return parsed.date() if parsed else None


def utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def outcome_keys(trade: Mapping[str, Any], horizons: Sequence[int], as_of: date) -> set[str]:
    return {
        f"{field}:{h}" for field in ("picker_outcomes", "followable_outcomes") for h in horizons
        if isinstance((detail := _mapping(trade.get(field)).get(str(h))), Mapping)
        and (exit_day := day(detail.get("exit_date"))) is not None and exit_day <= as_of
    }


def inventory(
    profiles: Sequence[Mapping[str, Any]], observations: Mapping[str, Any], *,
    horizons: Sequence[int], as_of: date,
    rows_for: Callable[[str], Sequence[Mapping[str, Any]]],
    computable: Callable[[Mapping[str, Any], str, int, Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]], bool],
    market_configured: bool | None = None,
) -> dict[str, dict[str, Any]]:
    """Disjoint observation states. Read cached rows only, never a provider call.

    A maturity claim requires current stock rows or an anchor still in the
    future. Holidays with no current price are conservatively unknown data,
    not an invented trading-session calendar or fabricated maturity date.
    """
    result: dict[str, dict[str, Any]] = {}
    expected_latest = as_of
    while expected_latest.weekday() >= 5:
        expected_latest -= timedelta(days=1)
    for index, profile in enumerate(profiles):
        for offset, trade in enumerate(profile.get("trade_results") or []):
            if not isinstance(trade, Mapping) or trade.get("eligible") is not True:
                continue
            key = str(trade.get("observation_key") or "")
            cached = _mapping(observations.get(key))
            done = outcome_keys(trade, horizons, as_of)
            category, reason, retry_at = "unknown", "invalid_observation", None
            stock = [r for r in rows_for(str(trade.get("ticker") or "")) if (d := day(r.get("date"))) is not None and d <= as_of]
            benchmark = [r for r in rows_for(str(trade.get("benchmark") or "")) if (d := day(r.get("date"))) is not None and d <= as_of]
            missing = [(field, h) for field in ("picker_outcomes", "followable_outcomes") for h in horizons if f"{field}:{h}" not in done]
            anchors = {"picker_outcomes": day(trade.get("transaction_date")), "followable_outcomes": day(trade.get("followable_anchor_date"))}
            if profile.get("profile_status") == "stale_last_good":
                reason = "stale_profile"
            elif key and horizons and all(anchors.values()):
                if not missing:
                    category, reason = "completed", "complete"
                else:
                    available = any(computable(trade, field, h, stock, benchmark) for field, h in missing)
                    def immature(field: str, horizon: int) -> bool:
                        anchor = anchors[field]
                        if anchor > as_of:
                            return True
                        if not stock or day(stock[-1].get("date")) < expected_latest:
                            return False
                        after = [r for r in stock if day(r.get("date")) >= anchor]
                        return bool(after) and len(after) <= horizon
                    all_immature = all(immature(field, h) for field, h in missing)
                    attempted = day(cached.get("last_attempted_as_of"))
                    retry = day(cached.get("retry_after_as_of"))
                    if all_immature and not available:
                        category, reason = "awaiting_maturity", "outcome_not_mature"
                    elif retry and retry > as_of:
                        category, reason = "awaiting_retry", "provider_backoff"
                        retry_at = utc(datetime.combine(retry, datetime.min.time(), timezone.utc))
                    elif attempted and attempted >= as_of:
                        category, reason = "awaiting_retry", "daily_attempt_limit"
                        retry_at = utc(datetime.combine(attempted + timedelta(days=1), datetime.min.time(), timezone.utc))
                    elif available:
                        category, reason = "ready", "cached_work_ready"
                    elif market_configured is False:
                        category, reason = "blocked", "no_market_credentials"
                    elif not cached:
                        category, reason = "queued", "unattempted"
                    else:
                        category, reason = "missing_data", "prices_missing_or_stale"
            row = {
                "category": category, "reason_code": reason,
                "investor": str(profile.get("filer") or "Unknown filer")[:160],
                "owner": str(profile.get("owner") or "Unknown owner")[:80],
                "ticker": str(trade.get("ticker") or "")[:24],
                "trade_id": str(trade.get("trade_id") or "")[:200],
                "profile_index": index, "next_retry_at": retry_at,
                "completed_outcomes": sorted(done), "missing_outcome_count": len(missing),
            }
            # Do not double-count one observation when identity projections overlap.
            result.setdefault(key or f"unknown:{index}:{offset}", row)
    return result


def record_success(previous: Any, before: Mapping[str, Any], after: Mapping[str, Any], *,
                   method_hash: str, run_id: str, now: datetime, attempted: int) -> dict[str, Any]:
    """One journal event per runtime instance, not per save or dashboard refresh."""
    scope = hashlib.sha256("\n".join(sorted(after)).encode()).hexdigest()
    old = _mapping(previous)
    compatible = old.get("schema_version") == VERSION and old.get("method_hash") == method_hash and old.get("scope_hash") == scope
    raw_events = old.get("events") if compatible else []
    events = [dict(e) for e in raw_events if isinstance(e, Mapping) and instant(e.get("at")) is not None] if isinstance(raw_events, list) else []
    if any(e.get("run_id") == run_id for e in events):
        return dict(old)
    # Out-of-order/replayed instants cannot establish a successful cadence.
    if events and now <= instant(events[-1]["at"]):
        return dict(old)
    ready_before = {k for k, v in before.items() if v["category"] == "ready"}
    ready_after = {k for k, v in after.items() if v["category"] == "ready"}
    advanced = {k for k, v in after.items() if set(v["completed_outcomes"]) - set(before.get(k, {}).get("completed_outcomes", []))}
    completed = sum(v["category"] == "completed" and before.get(k, {}).get("category") != "completed" for k, v in after.items())
    resolved = sum(k in after and after[k]["category"] in {"completed", "awaiting_maturity"} for k in ready_before)
    no_progress = bool(ready_before & ready_after) and not advanced
    streak = (count(events[-1].get("stalled_streak")) or 0) + 1 if events and no_progress else int(no_progress)
    event = {"run_id": run_id, "at": utc(now), "attempted": attempted,
             "ready_before": len(ready_before), "ready_after": len(ready_after),
             "resolved_ready": resolved, "advanced_observations": len(advanced),
             "completed_observations": completed, "stalled_streak": streak}
    events.append(event)
    last_advance = utc(now) if advanced else old.get("last_advancement_at") if compatible else None
    return {"schema_version": VERSION, "method_hash": method_hash, "scope_hash": scope,
            "last_advancement_at": last_advance, "events": events[-24:]}


def report(work: Mapping[str, Any], journal: Any, *, now: datetime, as_of: date,
           enabled: bool, limit: int, stale_after_minutes: int) -> dict[str, Any]:
    counts = {name: 0 for name in CATEGORIES}
    counts.update(Counter(row["category"] for row in work.values()))
    old = _mapping(journal)
    scope = hashlib.sha256("\n".join(sorted(work)).encode()).hexdigest()
    if old.get("scope_hash") != scope:
        old = {}
    events = old.get("events") if old.get("schema_version") == VERSION else []
    events = [e for e in events if isinstance(e, Mapping) and instant(e.get("at"))] if isinstance(events, list) else []
    latest = events[-1] if events else {}
    last_at = instant(latest.get("at"))
    stale = last_at is None or (now - last_at).total_seconds() > stale_after_minutes * 60 or now < last_at
    stalled = bool(counts["ready"] and (count(latest.get("stalled_streak")) or 0) >= 3)
    if not enabled:
        status = "disabled"
    elif not work:
        status = "empty"
    elif counts["unknown"]:
        status = "unknown"
    elif counts["blocked"] or limit == 0 and counts["ready"] + counts["queued"]:
        status = "blocked"
    elif stalled:
        status = "stalled"
    elif counts["ready"] or counts["queued"]:
        status = "queued"
    elif counts["missing_data"]:
        status = "missing_data"
    elif counts["awaiting_retry"]:
        status = "awaiting_retry"
    elif counts["awaiting_maturity"]:
        status = "awaiting_maturity"
    else:
        status = "caught_up"
    # Measured reductions of cache-computable work only. Missing data, first
    # evaluations, future horizons and retry waits never receive a numeric ETA.
    rates = []
    intervals = []
    window = events[-7:]
    for a, b in zip(window, window[1:]):
        seconds = (instant(b["at"]) - instant(a["at"])).total_seconds()
        if 60 <= seconds <= 21600:
            rates.append((count(b.get("resolved_ready")) or 0) / seconds)
            intervals.append(seconds)
    eta = None
    eta_reason = "insufficient_measured_progress"
    if not counts["ready"]:
        eta_reason = "no_currently_computable_work"
    elif stale:
        eta_reason = "successful_run_evidence_stale_or_missing"
    elif stalled or not enabled or limit == 0:
        eta_reason = "processing_not_advancing"
    elif len(rates) >= 3 and all(rate > 0 for rate in rates[-3:]):
        rates = rates[-3:]
        eta = {"lower_seconds": math.ceil(counts["ready"] / max(rates)),
               "upper_seconds": math.ceil(counts["ready"] / min(rates)),
               "basis": "Measured cache-computable completions at the observed successful cadence; excludes all other pending categories.",
               "measured_intervals": len(rates)}
        eta_reason = None
    pending = [row for row in work.values() if row["category"] != "completed"]
    priority = {"blocked": 0, "unknown": 1, "missing_data": 2, "awaiting_retry": 3, "ready": 4, "queued": 5, "awaiting_maturity": 6}
    pending.sort(key=lambda r: (priority[r["category"]], r["investor"], r["ticker"], r["trade_id"]))
    details = [{k: v for k, v in row.items() if k != "completed_outcomes"} for row in pending[:200]]
    retry_dates = [r["next_retry_at"] for r in pending if r["next_retry_at"]]
    return {"schema_version": VERSION, "as_of_date": as_of.isoformat(), "counts": counts,
            "total_observations": len(work), "status": status, "status_label": LABELS[status],
            "caught_up_computable": counts["ready"] == 0 and counts["queued"] == 0 and counts["unknown"] == 0,
            "last_successful_run_at": latest.get("at"), "last_advancement_at": old.get("last_advancement_at"),
            "completed_in_last_run": count(latest.get("completed_observations")),
            "advanced_in_last_run": count(latest.get("advanced_observations")),
            "attempted_in_last_run": count(latest.get("attempted")),
            "stalled_successful_runs": count(latest.get("stalled_streak")),
            "stale_after_minutes": stale_after_minutes, "evidence_stale": stale,
            "next_retry_at": min(retry_dates) if retry_dates else None,
            "next_scheduled_run_at": None,  # A static snapshot cannot verify Scheduler state.
            "observed_interval_seconds": round(statistics.median(intervals)) if intervals else None,
            "eta": eta, "eta_unavailable_reason": eta_reason,
            "details": details, "detail_total": len(pending), "details_truncated": len(pending) > len(details),
            "scope_note": "Bounded published investor history only. Cataloged filing parsing and access reviews are separate; acknowledgements do not complete backfill."}


def public_report(value: Any) -> dict[str, Any] | None:
    """Allowlist public progress fields; reject inconsistent/malformed telemetry."""
    if not isinstance(value, Mapping) or value.get("schema_version") != VERSION:
        return None
    counts = _mapping(value.get("counts"))
    if any(count(counts.get(k)) is None for k in CATEGORIES):
        return None
    if count(value.get("total_observations")) != sum(counts[k] for k in CATEGORIES) or value.get("status") not in LABELS:
        return None
    result = {k: value.get(k) if isinstance(value.get(k), bool) else None for k in ("caught_up_computable", "evidence_stale", "details_truncated")}
    result["as_of_date"] = d.isoformat() if (d := day(value.get("as_of_date"))) else None
    result.update(schema_version=VERSION, counts={k: counts[k] for k in CATEGORIES},
                  total_observations=value["total_observations"], status=value["status"], status_label=LABELS[value["status"]])
    for k in ("last_successful_run_at", "last_advancement_at", "next_retry_at", "next_scheduled_run_at"):
        t = instant(value.get(k)); result[k] = utc(t) if t else None
    for k in ("completed_in_last_run", "advanced_in_last_run", "attempted_in_last_run", "stalled_successful_runs", "stale_after_minutes", "observed_interval_seconds", "detail_total"):
        result[k] = count(value.get(k))
    eta = _mapping(value.get("eta"))
    lower, upper = count(eta.get("lower_seconds")), count(eta.get("upper_seconds"))
    result["eta"] = {"lower_seconds": lower, "upper_seconds": upper, "measured_intervals": count(eta.get("measured_intervals"))} if lower is not None and upper is not None and lower <= upper else None
    valid_eta_reasons = {"insufficient_measured_progress", "no_currently_computable_work", "successful_run_evidence_stale_or_missing", "processing_not_advancing"}
    result["eta_unavailable_reason"] = value.get("eta_unavailable_reason") if value.get("eta_unavailable_reason") in valid_eta_reasons else None
    details = value.get("details")
    result["details"] = []
    for row in details[:200] if isinstance(details, list) else []:
        if not isinstance(row, Mapping) or row.get("category") not in CATEGORIES or row.get("reason_code") not in REASONS:
            continue
        result["details"].append({"category": row["category"], "reason_code": row["reason_code"], "reason": REASONS[row["reason_code"]],
                                 **{k: str(row.get(k) or "")[:200] for k in ("investor", "owner", "ticker", "trade_id")},
                                 "profile_index": count(row.get("profile_index")),
                                 "next_retry_at": utc(t) if (t := instant(row.get("next_retry_at"))) else None,
                                 "missing_outcome_count": count(row.get("missing_outcome_count"))})
    return result
