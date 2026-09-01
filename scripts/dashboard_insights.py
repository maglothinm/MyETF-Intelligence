"""Read-only, public presentation model for the static PolitiTrack dashboard.

This module neither reads nor writes production state. Counts describe separate
retained populations; it does not change eligibility, classifications or scores.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import parse_qsl, urlsplit

try:
    from .collector_freshness import (FRESHNESS_POLICY, REQUIRED_BRANCHES, branch_freshness,
                                      nonproduction_evidence, overall_status, production_run, trigger_source)
except ImportError:  # pragma: no cover - direct-script execution
    from collector_freshness import (FRESHNESS_POLICY, REQUIRED_BRANCHES, branch_freshness,
                                     nonproduction_evidence, overall_status, production_run, trigger_source)


VERSION = 1
QUALIFYING = {"high_priority": 0, "watchlist": 1}
BRANCHES = REQUIRED_BRANCHES
_PRIVATE_KEY = re.compile(
    r"(?:secret|password|passwd|credential|recipient|heartbeat|healthcheck|"
    r"api[_-]?key|access[_-]?token|auth[_-]?token|user[_-]?key|app[_-]?token|"
    r"authorization|cookie|private[_-]?config|delivery[_-]?(?:payload|state)|"
    r"gmail[_-]?(?:address|email)|(?:email|mail)[_-]?(?:address|to|from)|"
    r"token|private[_-]?key|^to$|^cc$|^bcc$|^config$|^configuration$|^environment$|^env$|"
    r"^delivery$|^delivery_journal$|^alert_delivery$)", re.I
)
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_TOKEN = re.compile(r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]{12,})\b")
_LABELED_SECRET = re.compile(
    r"\b((?:api[_ -]?key|token|secret|password|authorization)\s*[:=]\s*)[^\s,;]+", re.I
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.I)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Mapping[str, Any]]:
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _text(value: Any, limit: int = 500) -> str:
    return _scrub_text(value)[:limit] if isinstance(value, str) else ""


def optional_number(value: Any) -> float | None:
    """Accept finite numeric values, never booleans, blanks, NaN or infinity."""
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _first(*values: Any) -> Any:
    return next((value for value in values if value is not None and value != ""), None)


def _positive(value: Any) -> float | None:
    number = optional_number(value)
    return number if number is not None and number > 0 else None


def _count(value: Any) -> int | None:
    number = optional_number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def optional_timestamp(value: Any) -> str | None:
    result = _instant(value)
    return result.isoformat().replace("+00:00", "Z") if result is not None else None


def _date(value: Any) -> str | None:
    result = _instant(value)
    return result.date().isoformat() if result is not None else None


def _unsafe_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").casefold()
        return bool(
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username or parsed.password
            or "healthcheck" in host or host == "hc-ping.com" or host.endswith(".hc-ping.com")
            or any(part in parsed.path.casefold() for part in ("/heartbeat/", "/heartbeat", "/hc-ping/"))
            or any(_PRIVATE_KEY.search(key) for key, _ in parse_qsl(parsed.query))
        )
    except ValueError:
        return True


def safe_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or any(ord(char) < 33 or char in "<>\"'" for char in value) or _unsafe_url(value):
        return None
    return value


def _scrub_text(value: str) -> str:
    value = _URL.sub(lambda match: "[private URL removed]" if _unsafe_url(match.group()) else match.group(), value)
    value = _EMAIL.sub("[address removed]", value)
    value = _TOKEN.sub("[credential removed]", value)
    value = _LABELED_SECRET.sub(lambda match: match.group(1) + "[removed]", value)
    return _BEARER.sub("Bearer [removed]", value)


def public_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Copy compatibility data while removing private configuration and secrets.

    Public record text remains text, including HTML-like strings: the renderer
    must escape it. We do not serialize arbitrary objects, NaN or credentials.
    Existing benign simulation notification status fields are kept for consumers.
    """
    def clean(value: Any, path: tuple[str, ...] = ()) -> Any:
        if isinstance(value, Mapping):
            result = {}
            for key, item in value.items():
                if not isinstance(key, str) or _PRIVATE_KEY.search(key):
                    continue
                if key == "notification" and isinstance(item, Mapping):
                    # Preserve the existing replay's coarse provider statuses,
                    # never a provider request/response object or delivery body.
                    result[key] = {provider: _scrub_text(status) for provider, status in item.items()
                                   if provider in {"pushover", "email", "gmail"} and isinstance(status, str)}
                else:
                    result[key] = clean(item, path + (key,))
            # Normalize every explicit exclusion to one coarse public field.
            # Private environment/test metadata remains removed, while JSON and
            # CSV consumers retain the same production boundary as the builder.
            isolated_replay = path == ("simulation",)
            if nonproduction_evidence(value) and not isolated_replay:
                result["is_nonproduction"] = True
            return result
        if isinstance(value, (list, tuple)):
            return [clean(item, path + ("[]",)) for item in value]
        if isinstance(value, str):
            return _scrub_text(value)
        if value is None or isinstance(value, bool) or isinstance(value, int):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        return None

    return clean(payload)


def _flag(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.strip().casefold() == "true")


def is_synthetic(row: Mapping[str, Any]) -> bool:
    return nonproduction_evidence(row)


def _filing_identity(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("source") or ""), str(row.get("report_id") or "")


def review_category(row: Mapping[str, Any], filing: Mapping[str, Any] | None = None) -> str:
    """Separate request inventory from parser exceptions using retained fields."""
    filing = _mapping(filing)
    access = str(_first(row.get("access_mode"), filing.get("access_mode")) or "").casefold().replace("-", "_")
    reason = " ".join(str(value or "") for value in (row.get("reason"), row.get("review_reason"), filing.get("review_reason"))).casefold()
    if access in {"request", "request_only", "access_required", "access_limited", "restricted"}:
        return "access_required"
    if re.search(r"(?:access.*(?:request|limit)|request.only|form\s*201|requires? (?:an? )?request)", reason):
        return "access_required"
    source = str(_first(row.get("source"), filing.get("source")) or "").casefold()
    if source == "oge" and "no direct pdf" in reason:
        return "access_required"
    if re.search(r"(?:pars(?:e|er|ing)|manual|paper (?:filing|report)|ocr|malformed|unsupported (?:format|document))", reason):
        return "manual_exception"
    return "other"


def _synthetic_predicate(payload: Mapping[str, Any]) -> Callable[[Mapping[str, Any]], bool]:
    """Share synthetic ancestry between the overview and complete review export."""
    filings = _rows(payload.get("filings"))
    test_filings = {_filing_identity(row) for row in filings if is_synthetic(row) and all(_filing_identity(row))}
    test_keys = {row["filing_key"] for row in filings if is_synthetic(row) and isinstance(row.get("filing_key"), str) and row["filing_key"]}

    def linked_test(row: Mapping[str, Any]) -> bool:
        key = row.get("filing_key")
        return (is_synthetic(row) or _filing_identity(row) in test_filings
                or (isinstance(key, str) and key in test_keys))

    test_trades = {row["trade_id"] for row in _rows(payload.get("transactions"))
                   if linked_test(row) and isinstance(row.get("trade_id"), str) and row["trade_id"]}

    def matches(row: Mapping[str, Any]) -> bool:
        trade_id = row.get("trade_id")
        return linked_test(row) or (isinstance(trade_id, str) and trade_id in test_trades)

    return matches


def review_rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Add presentation metadata to every retained review, without changing state.

    Explicit filing keys take precedence; otherwise only a complete, unique
    source/report identity can join a filing. No key, status or timestamp is
    constructed. Existing review metadata takes precedence over filing values.
    The complete list is also the source of the overview's review counts.
    """
    by_key: dict[str, list[Mapping[str, Any]]] = {}
    by_identity: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for filing in _rows(payload.get("filings")):
        key = filing.get("filing_key")
        if isinstance(key, str) and key:
            by_key.setdefault(key, []).append(filing)
        identity = _filing_identity(filing)
        if all(identity):
            by_identity.setdefault(identity, []).append(filing)

    is_test = _synthetic_predicate(payload)
    result = []
    for row in _rows(payload.get("reviews")):
        key = row.get("filing_key")
        candidates = (by_key.get(key, []) if isinstance(key, str) and key
                      else by_identity.get(_filing_identity(row), []))
        filing = candidates[0] if len(candidates) == 1 else {}
        # A contradictory explicit key is not permission to attach a different
        # source record, even if the key itself exists in the filing inventory.
        if any(row.get(field) not in (None, "") and str(row[field]) != str(filing.get(field) or "")
               for field in ("source", "report_id") if filing):
            filing = {}
        enriched = dict(row)
        for field in ("filing_key", "source", "branch", "report_id", "filer", "title", "agency",
                      "filed_date", "source_url", "access_mode", "review_reason", "document_format",
                      "chamber", "first_seen_utc", "updated_at_utc"):
            if enriched.get(field) in (None, "") and filing.get(field) not in (None, ""):
                enriched[field] = filing[field]
        if enriched.get("reason") in (None, "") and enriched.get("review_reason") not in (None, ""):
            enriched["reason"] = enriched["review_reason"]
        if enriched.get("filing_status") in (None, "") and filing.get("status") not in (None, ""):
            enriched["filing_status"] = filing["status"]
        enriched["filing_available"] = bool(filing)
        enriched["category"] = review_category(row, filing)
        enriched["is_synthetic_test"] = is_test(row)
        result.append(enriched)
    return result


def source_filters(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """Publish filter dimensions from retained branch/source taxonomy, not aliases."""
    sources = {"house", "senate", "oge"}
    branches = {"executive", "legislative"}
    for name in ("filings", "transactions", "reviews", "analyses", "portfolio", "runs", "ai_runs"):
        for row in _rows(payload.get(name)):
            for field, values in (("source", sources), ("branch", branches)):
                if field == "branch" and name in {"runs", "ai_runs"}:
                    # Worker health (for example AI) is not a disclosure branch.
                    continue
                value = row.get(field)
                if isinstance(value, str) and value.strip():
                    values.add(value)
    for source in _mapping(_mapping(payload.get("summary")).get("sources")):
        if isinstance(source, str) and source.strip():
            sources.add(source)

    def label(value: str) -> str:
        return {"oge": "OGE", "ai": "AI"}.get(value.casefold(), _text(value).replace("_", " ").title())

    return ([{"value": "branch:" + branch, "label": label(branch), "field": "branch"}
             for branch in sorted(branches)]
            + [{"value": source, "label": label(source), "field": "source"}
               for source in sorted(sources)])


def _flat_record(row: Mapping[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: _text(row.get(field)) for field in fields}


_FILING_PUBLIC = ("filing_key", "filing_id", "filing_resolution", "source", "branch", "report_id", "filer", "title", "agency", "status", "access_mode")
_REVIEW_PUBLIC = ("review_id", "filing_key", "filing_id", "filing_resolution", "source", "branch", "report_id", "filer", "title", "agency", "reason")
_SIGNAL_PUBLIC = ("analysis_id", "trade_id", "filing_key", "filing_id", "filing_resolution", "source", "branch", "report_id", "filer", "owner", "ticker", "asset", "amount", "transaction_type", "classification")


def _filing(row: Mapping[str, Any]) -> dict[str, Any]:
    return {**_flat_record(row, _FILING_PUBLIC), "filed_date": _date(row.get("filed_date")),
            "observed_at_utc": optional_timestamp(row.get("first_seen_utc")),
            "updated_at_utc": optional_timestamp(row.get("updated_at_utc")), "source_url": safe_url(row.get("source_url"))}


def _review(row: Mapping[str, Any], category: str) -> dict[str, Any]:
    return {**_flat_record(row, _REVIEW_PUBLIC), "category": category,
            "filed_date": _date(row.get("filed_date")), "observed_at_utc": optional_timestamp(row.get("observed_at_utc")),
            "source_url": safe_url(row.get("source_url"))}


def _signal(row: Mapping[str, Any]) -> dict[str, Any]:
    entry, market, edge, ai = (_mapping(row.get(key)) for key in ("entry_plan", "market", "investor_edge", "ai"))
    direction = _text(_first(row.get("signal_direction"), entry.get("signal_direction")))
    if direction not in {"bullish", "bearish"}:
        tx_type = str(row.get("transaction_type") or "").casefold()
        direction = "bullish" if tx_type == "purchase" else ("bearish" if tx_type.startswith(("sale", "disposition")) else "unknown")
    current = _positive(_first(market.get("current_price"), entry.get("current_price")))
    low, high = _positive(entry.get("review_band_low")), _positive(entry.get("review_band_high"))
    maximum_chase = optional_number(entry.get("maximum_chase_percent"))
    if maximum_chase is not None and maximum_chase < 0:
        maximum_chase = None
    tx_close = _positive(_first(entry.get("transaction_date_close"), market.get("transaction_date_close")))
    ceiling = _positive(entry.get("chase_ceiling"))
    if ceiling is None and tx_close is not None and maximum_chase is not None and direction == "bullish":
        ceiling = optional_number(tx_close * (1 + maximum_chase / 100))
    if low is None or high is None or low >= high:
        low = high = None
    band = None
    if low is not None and high is not None and current is not None:
        domain = [low, high, current] + ([ceiling] if ceiling is not None else [])
        minimum, maximum = min(domain), max(domain)
        if maximum > minimum:
            band = {"low": low, "high": high, "current": current, "chase_ceiling": ceiling,
                    "minimum": minimum, "maximum": maximum}
    observed, filed = _instant(row.get("observed_at_utc")), _instant(row.get("filed_date"))
    transaction = _instant(row.get("transaction_date"))
    lag = optional_number(row.get("investor_edge_current_disclosure_lag_days"))
    if lag is None and transaction and (observed or filed):
        days = ((observed or filed).date() - transaction.date()).days
        lag = days if days >= 0 else None
    evidence = []
    seen_urls: set[str] = set()
    for item in _rows(ai.get("evidence_sources")):
        url = safe_url(item.get("url"))
        if url and url not in seen_urls:
            seen_urls.add(url)
            evidence.append({"title": _text(item.get("title"), 140) or "Evidence", "url": url})
    observations = _count(_first(row.get("investor_edge_observation_count"), edge.get("sample_count"), edge.get("observation_count")))
    edge_status = _text(_first(row.get("investor_edge_status"), edge.get("status"))) or "unavailable"
    has_edge_outcomes = bool(observations is not None and observations > 0
                             and edge_status.casefold() not in {"unavailable", "disabled", "error", "neutral", "missing"}
                             and not edge_status.casefold().startswith("insufficient"))
    relevant_alpha = optional_number(row.get("investor_edge_relevant_followable_alpha"))
    followable_alpha = _first(relevant_alpha, optional_number(row.get("investor_edge_followable_alpha")))
    alpha_label = _text(row.get("investor_edge_relevant_alpha_label")) if relevant_alpha is not None else ""
    return {
        **_flat_record(row, _SIGNAL_PUBLIC), "direction": direction,
        "source_url": safe_url(row.get("source_url")), "transaction_date": _date(row.get("transaction_date")),
        "filed_date": _date(row.get("filed_date")), "observed_at_utc": optional_timestamp(row.get("observed_at_utc")),
        "analyzed_at_utc": optional_timestamp(row.get("analyzed_at_utc")), "disclosure_lag_days": lag,
        "score": optional_number(row.get("score")), "final_score": optional_number(_first(row.get("final_score"), row.get("score"))),
        "base_score": optional_number(row.get("base_score")),
        "edge_modifier": optional_number(_first(row.get("investor_edge_modifier"), edge.get("modifier"))),
        "edge_score": optional_number(_first(row.get("investor_edge_score"), edge.get("edge_score"))),
        "edge_confidence": optional_number(_first(row.get("investor_edge_confidence"), edge.get("confidence"))),
        "edge_confidence_label": _text(_first(row.get("investor_edge_confidence_label"), edge.get("confidence_label"))),
        "edge_observation_count": observations,
        "edge_status": edge_status,
        "edge_relevant_alpha_label": alpha_label if has_edge_outcomes else "",
        "edge_followable_alpha": followable_alpha if has_edge_outcomes else None,
        "edge_hit_rate_percent": optional_number(row.get("investor_edge_hit_rate_percent")) if has_edge_outcomes else None,
        "edge_sector_alpha": optional_number(row.get("investor_edge_sector_alpha")) if has_edge_outcomes else None,
        "current_price": current, "quote_timestamp_utc": optional_timestamp(market.get("quote_timestamp_utc")),
        "entry_status": _text(entry.get("entry_status")) or "unavailable", "review_band_low": low, "review_band_high": high,
        "chase_ceiling": ceiling, "maximum_chase_percent": maximum_chase,
        "signal_expires_utc": optional_timestamp(entry.get("signal_expires_utc")), "price_band": band,
        "why": _text(ai.get("analysis_summary"), 360), "evidence": evidence[:8], "paper_only": True,
    }


def _run_status(row: Mapping[str, Any]) -> str:
    conclusion = str(row.get("conclusion") or "").casefold()
    if _errors(row.get("errors")) or (_count(row.get("error_count")) or 0) > 0:
        return "failure"
    if conclusion in {"failure", "timed_out", "action_required", "startup_failure"}:
        return "failure"
    if conclusion in {"cancelled", "skipped", "neutral", "queued", "in_progress", "pending", "waiting"} or row.get("enabled") is False:
        return "unknown"
    if conclusion and conclusion != "success":
        return "unknown"
    if row.get("success") is False:
        return "failure"
    return "success" if row.get("success") is True else "unknown"


def _errors(value: Any) -> list[str]:
    if isinstance(value, list):
        errors = []
        for item in value:
            if isinstance(item, str) and item.strip():
                errors.append(_text(item, 300))
            elif item:
                errors.append("Retained run reports an error; details unavailable.")
        return errors
    if isinstance(value, str):
        return [_text(value, 300)] if value.strip() else []
    return ["Retained run reports an error; details unavailable."] if value else []


def _sum_counts(value: Any) -> int | None:
    if not isinstance(value, Mapping) or not value:
        return None
    counts = [_count(number) for number in value.values()]
    return sum(counts) if all(number is not None for number in counts) else None


def _run(row: Mapping[str, Any], branch: str) -> dict[str, Any]:
    key = _text(row.get("run_key"), 200)
    if not key:
        key = hashlib.sha256((str(row.get("run_url") or "") + "|" + str(row.get("run_attempt") or "") + "|" + str(row.get("started_utc") or "") + "|" + str(row.get("finished_utc") or "")).encode()).hexdigest()[:24]
    status = _run_status(row)
    return {"id": f"{branch}:{key}", "branch": branch, "started_utc": optional_timestamp(row.get("started_utc")),
            "workflow_started_utc": optional_timestamp(row.get("workflow_started_utc")),
            "producer_job_started_utc": optional_timestamp(row.get("producer_job_started_utc")),
            "workflow_created_utc": optional_timestamp(row.get("workflow_created_utc")),
            "finished_utc": optional_timestamp(row.get("finished_utc")),
            "timestamp_evidence_invalid": any(row.get(field) not in (None, "") and _instant(row.get(field)) is None
                                              for field in ("started_utc", "finished_utc", "workflow_started_utc", "producer_job_started_utc")),
            "success": row.get("success") if isinstance(row.get("success"), bool) else None,
            "status": status, "conclusion": _text(row.get("conclusion")) or status,
            "error_count": max(len(_errors(row.get("errors"))), _count(row.get("error_count")) or 0),
            "errors": _errors(row.get("errors")), "run_url": safe_url(row.get("run_url")),
            "trigger_source": trigger_source(row),
            "evidence_source": "github_actions" if row.get("evidence_source") == "github_actions" else "retained_state",
            "state_evidence": row.get("evidence_source") != "github_actions",
            "new_record_count": _count(row.get("completed_count")) if branch == "ai" else _sum_counts(row.get("new_filing_counts"))}


def _run_time(row: Mapping[str, Any]) -> float:
    # A workflow can be queued before a producer that executes first. Actual
    # collector/job execution, then completion, outranks queue/workflow time.
    instant = _instant(row.get("started_utc") or row.get("producer_job_started_utc") or row.get("finished_utc")
                       or row.get("workflow_started_utc") or row.get("workflow_created_utc"))
    return instant.timestamp() if instant else float("-inf")


def _completion_time(row: Mapping[str, Any], as_of: datetime | None) -> datetime | None:
    """Reject impossible execution chronology without inventing missing starts."""
    finished = _instant(row.get("finished_utc"))
    if not finished or row.get("timestamp_evidence_invalid") or (as_of and finished > as_of):
        return None
    for field in ("started_utc", "workflow_started_utc", "producer_job_started_utc"):
        if row.get(field) not in (None, ""):
            started = _instant(row.get(field))
            if not started or started > finished:
                return None
    return finished


def _known_attempt(row: Mapping[str, Any], as_of: datetime | None) -> bool:
    started = _instant(row.get("started_utc") or row.get("producer_job_started_utc") or row.get("workflow_started_utc"))
    finished = _instant(row.get("finished_utc"))
    return bool(started and as_of and started <= as_of and not row.get("timestamp_evidence_invalid")
                and (finished is None or started <= finished))


def _health(runs: list[Mapping[str, Any]], ai_runs: list[Mapping[str, Any]], as_of: datetime | None,
            workflow_evidence: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    branches, all_runs = [], []
    observation = _mapping(workflow_evidence)
    for branch in BRANCHES:
        retained = ai_runs if branch == "ai" else [row for row in runs if row.get("branch") == branch]
        by_id = {row["id"]: row for raw in retained if production_run(raw, branch) for row in [_run(raw, branch)]}
        observed_branch = _mapping(_mapping(observation.get("branches")).get(branch))
        available = observed_branch.get("available", observation.get("available")) if observation else None
        for raw in _rows(observed_branch.get("attempts")):
            if not production_run(raw, branch) or raw.get("evidence_source") != "github_actions":
                continue
            row = _run(raw, branch)
            prior = by_id.get(row["id"])
            if prior:
                # Actions conclusions supplement a validated artifact, never replace
                # its actual collector completion with workflow/job timestamps.
                prior["workflow_started_utc"] = row["workflow_started_utc"]
                if row["status"] == "failure":
                    prior.update(status="failure", conclusion=row["conclusion"], success=False,
                                 error_count=max(prior["error_count"], row["error_count"]))
            else:
                # A successful Actions job alone does not prove retained state or
                # a successful collector execution. It cannot advance freshness.
                if row["status"] == "success":
                    row["status"] = "unknown"
                by_id[row["id"]] = row
        ordered = sorted(by_id.values(), key=lambda row: (_run_time(row), row["id"]), reverse=True)
        all_runs.extend(ordered)
        pending = {"queued", "in_progress", "pending", "waiting"}
        newest = ordered[0] if ordered else {}
        attempted = next((row for row in ordered if _known_attempt(row, as_of)), {})
        last = next((row for row in ordered if row.get("conclusion") not in pending), {})
        success = next((row for row in ordered if row["state_evidence"] and row["status"] == "success"
                        and as_of and _completion_time(row, as_of)), {})
        incomplete = available is False or any(_run_time(row) == float("-inf") for row in ordered)
        latest_time = _completion_time(last, as_of)
        incomplete = incomplete or bool(last and (latest_time is None or as_of is None or latest_time > as_of))
        incomplete = incomplete or last.get("status") == "unknown"
        latest_success = (True if last.get("state_evidence") and last.get("status") == "success"
                          else False if last.get("status") == "failure" else None)
        freshness = branch_freshness(branch, last_success_utc=success.get("finished_utc"),
                                     latest_run_success=latest_success, latest_status=last.get("status", "unknown"),
                                     as_of=as_of, evidence_incomplete=incomplete)
        branches.append({**freshness,
                         "last_run_utc": last.get("finished_utc"),
                         "last_attempt_utc": attempted.get("started_utc") or attempted.get("producer_job_started_utc") or attempted.get("workflow_started_utc"),
                         "last_attempt_timestamp_kind": ("collector_start" if attempted.get("started_utc") else "producer_job_start"
                                                         if attempted.get("producer_job_started_utc") else "workflow_start"
                                                         if attempted.get("workflow_started_utc") else None),
                         "latest_conclusion": last.get("conclusion", "unknown"),
                         "attempt_conclusion": newest.get("conclusion", "unknown"),
                         "trigger_source": newest.get("trigger_source"),
                         "workflow_evidence_available": available,
                         "errors": last.get("errors", []), "error_count": last.get("error_count", 0),
                         "new_record_count": last.get("new_record_count"),
                         "run_url": newest.get("run_url"), "timeline": ordered[:10]})
    return {"status": overall_status(branches), "branches": branches,
            "as_of_utc": optional_timestamp(as_of.isoformat()) if as_of else None,
            "required_branches": list(REQUIRED_BRANCHES),
            "policy": {branch: dict(policy) for branch, policy in FRESHNESS_POLICY.items()},
            "workflow_evidence_observed_at_utc": optional_timestamp(observation.get("observed_at_utc")),
            "workflow_evidence_available": observation.get("available") if observation else None}, all_runs


def source_data_through(payload: Mapping[str, Any], *, as_of: datetime | None = None) -> str | None:
    """Newest retained production source observation, never publication/AI time."""
    is_test = _synthetic_predicate(payload)
    clock = as_of or _instant(_mapping(payload.get("summary")).get("generated_utc"))
    timestamps = [row.get(field)
                  for name, fields in (("filings", ("updated_at_utc", "first_seen_utc")),
                                       ("transactions", ("observed_at_utc",)), ("reviews", ("observed_at_utc",)))
                  for row in _rows(payload.get(name)) if not is_test(row) for field in fields]
    timestamps.extend(row.get("finished_utc") for row in _rows(payload.get("runs"))
                      if not is_synthetic(row) and production_run(row, str(row.get("branch") or ""))
                      and _run_status(row) == "success" and _completion_time(row, clock))
    valid = [instant for raw in timestamps if (instant := _instant(raw)) and (clock is None or instant <= clock)]
    newest = max(valid, default=None)
    return optional_timestamp(newest.isoformat()) if newest else None


def _simulation(value: Any) -> dict[str, Any]:
    row = _mapping(value)
    objective, accounting, analysis, trade, filing, price = (_mapping(row.get(key)) for key in ("objective", "accounting", "analysis", "trade", "filing", "price_context"))
    starting = _positive(_first(objective.get("starting_capital_usd"), accounting.get("starting_cash_usd")))
    current = optional_number(accounting.get("portfolio_value_usd"))
    goal = _positive(objective.get("goal_value_usd"))
    priced = accounting.get("status") == "priced"
    change = round(current - starting, 2) if priced and current is not None and starting is not None else None
    return {"available": bool(row), "status": _text(row.get("status")) or "unavailable",
            "label": "SIMULATED — SINGLE-RUN HISTORICAL REPLAY", "simulation_id": _text(row.get("simulation_id")),
            "as_of_utc": optional_timestamp(row.get("as_of_utc")), "starting_value": starting, "current_value": current,
            "change_usd": change, "change_percent": round(change / starting * 100, 4) if change is not None and starting is not None else None,
            "remaining_to_goal": round(max(0, goal - current), 2) if goal is not None and current is not None else None,
            "goal_value": goal, "ticker": _text(trade.get("ticker")), "score": optional_number(analysis.get("score")),
            "classification": _text(analysis.get("classification")), "entry_utc": optional_timestamp(price.get("entry_price_timestamp_utc")),
            "valuation_utc": optional_timestamp(price.get("valuation_price_timestamp_utc")),
            "run_url": safe_url(row.get("run_url")), "source_url": safe_url(filing.get("source_url")),
            "priced": priced, "persistent_history": False, "history_note": "No persistent portfolio history yet."}


def _build_sha() -> str | None:
    sha = os.environ.get("GITHUB_SHA", "")
    if re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        return sha.lower()
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent.parent,
                                capture_output=True, text=True, timeout=5, check=False)
        sha = result.stdout.strip()
        return sha.lower() if result.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40}", sha) else None
    except (OSError, subprocess.SubprocessError):
        return None


def _ids(rows: list[Mapping[str, Any]], key: str) -> list[str]:
    return sorted({hashlib.sha256(str(row[key]).encode()).hexdigest()[:24] for row in rows if isinstance(row.get(key), str) and row[key]})


def _historical_bootstrap_predicate(payload: Mapping[str, Any]) -> Callable[[Mapping[str, Any]], bool]:
    """Keep reconstructed old records visible, but out of new-event inventory."""
    filings = _rows(payload.get("filings"))
    old_filings = {_filing_identity(row) for row in filings
                   if _flag(row.get("historical_bootstrap")) and all(_filing_identity(row))}
    old_keys = {row["filing_key"] for row in filings
                if _flag(row.get("historical_bootstrap")) and isinstance(row.get("filing_key"), str) and row["filing_key"]}

    def linked(row: Mapping[str, Any]) -> bool:
        key = row.get("filing_key")
        return (_flag(row.get("historical_bootstrap")) or _filing_identity(row) in old_filings
                or isinstance(key, str) and key in old_keys)

    old_trades = {row["trade_id"] for row in _rows(payload.get("transactions"))
                  if linked(row) and isinstance(row.get("trade_id"), str) and row["trade_id"]}

    def matches(row: Mapping[str, Any]) -> bool:
        trade_id = row.get("trade_id")
        return linked(row) or isinstance(trade_id, str) and trade_id in old_trades

    return matches


def build_insights(payload: Mapping[str, Any], *, as_of: datetime | str | None = None) -> dict[str, Any]:
    """Create a compact additive view model without mutating any source object."""
    summary = _mapping(payload.get("summary"))
    filings, transactions, reviews, analyses, runs, ai_runs, portfolio = (
        _rows(payload.get(key)) for key in ("filings", "transactions", "reviews", "analyses", "runs", "ai_runs", "portfolio")
    )
    reviews = review_rows(payload)
    is_test = _synthetic_predicate(payload)
    production = {}
    synthetic = {}
    for name, rows in (("filings", filings), ("transactions", transactions), ("reviews", reviews), ("analyses", analyses)):
        production[name] = [row for row in rows if not is_test(row)]
        synthetic[name] = len(rows) - len(production[name])
    filings, transactions, reviews, analyses = (production[key] for key in ("filings", "transactions", "reviews", "analyses"))
    is_bootstrap = _historical_bootstrap_predicate(payload)
    event_filings, event_transactions, event_analyses = (
        [row for row in rows if not is_bootstrap(row)] for rows in (filings, transactions, analyses)
    )
    bootstrap_analysis_ids = {str(row.get("analysis_id") or "") for row in analyses if is_bootstrap(row)}
    signals = [_signal(row) for row in analyses if row.get("classification") in QUALIFYING]
    signals.sort(key=lambda row: (QUALIFYING[row["classification"]], -(row["final_score"] if row["final_score"] is not None else -1), -(_instant(row["analyzed_at_utc"]).timestamp() if row["analyzed_at_utc"] else 0), row["analysis_id"]))
    status = Counter(str(row.get("status") or "unknown").casefold() for row in filings)
    categories = [_review(row, row["category"]) for row in reviews]
    review_counts = Counter(row["category"] for row in categories)
    categories.sort(key=lambda row: (row["category"] == "manual_exception", row["observed_at_utc"] or "", row["review_id"]), reverse=True)
    purchases = sum(str(row.get("transaction_type") or "").casefold() in {"purchase", "buy"} for row in transactions)
    sales = sum(str(row.get("transaction_type") or "").casefold().startswith(("sale", "disposition", "sell")) for row in transactions)
    generated = optional_timestamp(summary.get("generated_utc"))
    clock = _instant(as_of.isoformat() if isinstance(as_of, datetime) else as_of) if as_of is not None else _instant(generated)
    production_runs = [row for row in runs if not is_synthetic(row) and production_run(row, str(row.get("branch") or ""))]
    production_ai_runs = [row for row in ai_runs if not is_synthetic(row) and production_run(row, "ai")]
    health, normalized_runs = _health(production_runs, production_ai_runs, clock, _mapping(payload.get("workflow_evidence")))
    simulation = _simulation(payload.get("simulation"))
    data_through = source_data_through(payload, as_of=clock)
    incidents = []
    for branch in health["branches"]:
        if branch["status"] == "failure":
            failed = next(row for row in branch["timeline"] if row["status"] == "failure")
            incidents.append({"id": "failure:" + failed["id"], "branch": branch["branch"], "kind": "failure",
                              "since": failed["finished_utc"], "url": failed["run_url"],
                              "summary": f"{branch['branch'].title()} latest retained run failed or reported errors."})
    open_positions = sum(row.get("status") == "open" and not is_test(row) for row in portfolio)
    closed_positions = sum(row.get("status") == "closed" and not is_test(row) for row in portfolio)
    result = {
        "version": VERSION, "build_sha": _build_sha(), "generated_utc": generated, "data_through_utc": data_through,
        "repository_url": safe_url(summary.get("repository_url")),
        "source_filters": source_filters(payload),
        "coverage": {"cataloged_only": status["cataloged"] + status["cataloged_only"], "processed": status["processed"],
                     "review_required": status["review_required"], "other_filings": sum(count for name, count in status.items() if name not in {"cataloged", "cataloged_only", "processed", "review_required"}),
                     "filings": len(filings), "transactions": len(transactions), "analyses": len(analyses), "qualifying_signals": len(signals),
                     "note": "Separate retained populations, not a conversion funnel. Cataloged does not mean transactions parsed; review rows and filing statuses are separate inventories."},
        "composition": {"population": len(transactions), "purchases": purchases, "sales": sales, "other": len(transactions) - purchases - sales,
                        "note": "Parsed post-upgrade transaction ledger; not complete historical government-trading volume. Counts do not imply dollar exposure."},
        "reviews": {
            "access_required": review_counts["access_required"],
            "manual_exception": review_counts["manual_exception"],
            "manual_exception_ids": sorted(
                str(row["review_id"])
                for row in categories
                if row["category"] == "manual_exception" and row.get("review_id")
            ),
            "other": review_counts["other"],
            "total": len(reviews),
            "latest": categories[:8],
        },
        "signals": signals[:48], "signals_truncated": len(signals) > 48,
        "health": health, "latest_filings": [_filing(row) for row in sorted(filings, key=lambda row: str(row.get("updated_at_utc") or row.get("first_seen_utc") or ""), reverse=True)[:8]],
        "simulation": simulation, "synthetic": synthetic,
        "paper": {"open_positions": open_positions, "closed_positions": closed_positions,
                  "label": "PAPER TRADING", "empty_note": "No open paper positions" if not open_positions else None},
        "notifications": {"filing_ids": _ids(event_filings, "filing_key"), "trade_ids": _ids(event_transactions, "trade_id"), "analysis_ids": _ids(event_analyses, "analysis_id"),
                          "run_ids": sorted({row["id"] for row in normalized_runs}), "simulation_ids": [simulation["simulation_id"]] if simulation["simulation_id"] else [],
                          "qualifying_signals": [{"analysis_id": row["analysis_id"], "classification": row["classification"], "ticker": row["ticker"], "analyzed_at": row["analyzed_at_utc"], "link": row["source_url"]} for row in signals if row["analysis_id"] not in bootstrap_analysis_ids],
                          "runs": [{"id": row["id"], "branch": row["branch"], "status": row["status"], "conclusion": row["status"], "at": row["finished_utc"], "url": row["run_url"], "error_count": row["error_count"]} for row in normalized_runs],
                          "current_incidents": incidents,
                          "simulation_results": [{"simulation_id": simulation["simulation_id"], "kind": "historical_replay", "timestamp": generated, "cutoff_utc": simulation["as_of_utc"], "url": simulation["run_url"], "status": simulation["status"]}] if simulation["simulation_id"] else []},
    }
    return result
