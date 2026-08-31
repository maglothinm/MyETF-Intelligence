#!/usr/bin/env python3
"""Build a static, searchable review dashboard from PolitiTrack state artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:  # Support both package and direct-script execution.
    from .dashboard_branding import copy_branding_assets
    from .investor_edge import build_dashboard_addon
    from .dashboard_insights import build_insights, public_payload, review_rows, source_data_through
    from .filing_resources import filing_catalog, attach_filing_ids, api_origin
except ImportError:  # pragma: no cover - direct execution path
    from dashboard_branding import copy_branding_assets  # type: ignore
    from investor_edge import build_dashboard_addon  # type: ignore
    from dashboard_insights import build_insights, public_payload, review_rows, source_data_through  # type: ignore
    from filing_resources import filing_catalog, attach_filing_ids, api_origin  # type: ignore

DEFAULT_OUTPUT = Path("trade-dashboard-site")

FILING_FIELDS = (
    "filing_key",
    "first_seen_utc",
    "updated_at_utc",
    "branch",
    "source",
    "report_id",
    "filer",
    "filed_date",
    "source_url",
    "document_format",
    "chamber",
    "title",
    "agency",
    "district",
    "report_type",
    "access_mode",
    "status",
    "transaction_count",
    "purchase_count",
    "sale_count",
    "exchange_count",
    "review_reason",
    "is_synthetic_test",
    "is_temporary",
    "test_metadata",
)

TRANSACTION_FIELDS = (
    "trade_id",
    "observed_at_utc",
    "branch",
    "source",
    "report_id",
    "filer",
    "chamber",
    "title",
    "agency",
    "owner",
    "asset",
    "ticker",
    "asset_type",
    "transaction_type",
    "signal_direction",
    "transaction_date",
    "notification_date",
    "filed_date",
    "amount",
    "source_url",
    "raw_row",
    "equity_like",
    "parse_confidence",
    "is_synthetic_test",
    "is_temporary",
    "test_metadata",
)

REVIEW_FIELDS = (
    "review_id",
    "observed_at_utc",
    "branch",
    "source",
    "report_id",
    "filer",
    "filed_date",
    "source_url",
    "reason",
    "title",
    "agency",
    "category",
    "filing_key",
    "filing_available",
    "filing_status",
    "review_status",
    "status",
    "access_mode",
    "review_reason",
    "first_seen_utc",
    "updated_at_utc",
    "is_synthetic_test",
)

RUN_FIELDS = (
    "run_key",
    "branch",
    "started_utc",
    "finished_utc",
    "success",
    "source_counts",
    "new_filing_counts",
    "cataloged_filing_counts",
    "baseline_counts",
    "transaction_counts",
    "purchase_counts",
    "pending_review_counts",
    "errors",
    "run_url",
    "event_name",
    "trigger_source",
    "run_attempt",
)

ANALYSIS_FIELDS = (
    "analysis_id",
    "trade_id",
    "analyzed_at_utc",
    "analysis_status",
    "model",
    "branch",
    "source",
    "report_id",
    "filer",
    "title",
    "agency",
    "chamber",
    "owner",
    "ticker",
    "asset",
    "asset_type",
    "transaction_type",
    "transaction_date",
    "filed_date",
    "observed_at_utc",
    "amount",
    "source_url",
    "score",
    "raw_score",
    "base_score",
    "base_raw_score",
    "final_score",
    "classification",
    "score_components",
    "hard_caps",
    "transaction_age_days",
    "repeated_purchase_count_90d",
    "market",
    "sec",
    "ai",
    "entry_plan",
    "investor_edge_status",
    "investor_edge_error",
    "investor_edge_modifier",
    "investor_edge_score",
    "investor_edge_confidence",
    "investor_edge_confidence_label",
    "investor_edge_observation_count",
    "investor_edge_relevant_alpha_label",
    "investor_edge_relevant_followable_alpha",
    "investor_edge_followable_alpha",
    "investor_edge_hit_rate_percent",
    "investor_edge_sector_alpha",
    "investor_edge_current_disclosure_lag_days",
    "investor_edge_average_disclosure_lag_days",
    "investor_edge_strongest_sector",
    "investor_edge",
    "score_method_version",
    "paper_only",
    "is_synthetic_test",
    "is_temporary",
    "test_metadata",
)

PORTFOLIO_FIELDS = (
    "position_id",
    "trade_id",
    "analysis_id",
    "ticker",
    "filer",
    "owner",
    "source_url",
    "score",
    "classification",
    "status",
    "opened_at_utc",
    "evaluation_horizon_utc",
    "closed_at_utc",
    "exit_reason",
    "allocation_percent",
    "entry_price",
    "exit_price",
    "quantity",
    "initial_notional",
    "current_price",
    "market_value",
    "unrealized_pnl",
    "realized_pnl",
    "return_percent",
    "last_updated_utc",
    "paper_only",
)

AI_RUN_FIELDS = (
    "run_key",
    "started_utc",
    "finished_utc",
    "success",
    "enabled",
    "eligible_transaction_count",
    "skipped_existing_count",
    "attempted_count",
    "completed_count",
    "high_priority_count",
    "watchlist_count",
    "weak_signal_count",
    "archive_count",
    "alerted_count",
    "paper_positions_opened",
    "paper_positions_updated",
    "paper_positions_closed",
    "errors",
    "warnings",
    "run_url",
    "event_name",
    "trigger_source",
    "run_attempt",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL in {path} at line {number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"Expected an object in {path} at line {number}")
        records.append(value)
    return records


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    return value if isinstance(value, dict) else {}


def load_workflow_evidence(path: Path | None) -> dict[str, Any]:
    """An explicitly requested but missing/malformed observation is unavailable.

    Omitted observations support older/local builders. A requested observation
    must never fall back to that compatibility mode and make fresh state green.
    """
    if path is None:
        return {}
    unavailable = {"schema_version": 1, "available": False, "branches": {}}
    try:
        value = read_json_object(path)
    except (OSError, ValueError):
        return unavailable
    if (type(value.get("schema_version")) is not int or value["schema_version"] != 1
            or not isinstance(value.get("available"), bool) or not isinstance(value.get("branches"), dict)):
        return unavailable
    for details in value["branches"].values():
        if (not isinstance(details, dict) or not isinstance(details.get("available"), bool)
                or not isinstance(details.get("attempts"), list)
                or any(not isinstance(row, dict) for row in details["attempts"])):
            return unavailable
    if value["available"]:
        for branch in ("legislative", "executive", "ai"):
            details = value["branches"].get(branch)
            if (not isinstance(details, dict) or details.get("available") is not True
                    or not isinstance(details.get("attempts"), list)
                    or any(not isinstance(row, dict) for row in details["attempts"])):
                return unavailable
    elif all(value["branches"].get(branch, {}).get("available") is True for branch in ("legislative", "executive", "ai")):
        return unavailable
    return value


def latest_by(records: Iterable[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        record_key = str(record.get(key) or "")
        if record_key:
            latest[record_key] = dict(record)
    return list(latest.values())


def date_sort_value(record: Mapping[str, Any], *fields: str) -> tuple[str, ...]:
    return tuple(str(record.get(field) or "") for field in fields)


def load_branch(directory: Path | None, branch: str) -> dict[str, Any]:
    if directory is None or not directory.exists():
        return {
            "branch": branch,
            "filings": [],
            "transactions": [],
            "reviews": [],
            "runs": [],
            "state": {},
        }

    filings = latest_by(read_jsonl(directory / "filings.jsonl"), "filing_key")
    transactions = latest_by(read_jsonl(directory / "transactions.jsonl"), "trade_id")
    # Preserve purchases collected before the all-transaction ledger was introduced.
    transaction_index = {str(item.get("trade_id")): item for item in transactions}
    for purchase in read_jsonl(directory / "purchases.jsonl"):
        trade_id = str(purchase.get("trade_id") or "")
        if trade_id and trade_id not in transaction_index:
            transaction_index[trade_id] = dict(purchase)
    transactions = list(transaction_index.values())
    reviews = latest_by(read_jsonl(directory / "pending-review.jsonl"), "review_id")
    runs = latest_by(read_jsonl(directory / "runs.jsonl"), "run_key")
    state = read_json_object(directory / "state.json")

    for item in filings:
        item.setdefault("branch", branch)
    for item in transactions:
        item.setdefault("branch", branch)
    for item in reviews:
        item.setdefault("branch", branch)
    for item in runs:
        item.setdefault("branch", branch)

    return {
        "branch": branch,
        "filings": filings,
        "transactions": transactions,
        "reviews": reviews,
        "runs": runs,
        "state": state,
    }


def load_ai(directory: Path | None) -> dict[str, Any]:
    if directory is None or not directory.exists():
        return {"analyses": [], "portfolio": [], "runs": [], "state": {}}

    analyses = latest_by(read_jsonl(directory / "analyses.jsonl"), "trade_id")
    portfolio_records = latest_by(read_jsonl(directory / "paper-portfolio.jsonl"), "position_id")
    portfolio = {str(item.get("position_id") or ""): dict(item) for item in portfolio_records if item.get("position_id")}
    runs = latest_by(read_jsonl(directory / "runs.jsonl"), "run_key")
    state = read_json_object(directory / "state.json")
    state_positions = state.get("positions") or {}
    if isinstance(state_positions, dict):
        for position_id, position in state_positions.items():
            if isinstance(position, dict):
                portfolio[str(position_id)] = dict(position)
    return {
        "analyses": analyses,
        "portfolio": list(portfolio.values()),
        "runs": runs,
        "state": state,
    }


def load_simulation(directory: Path | None) -> dict[str, Any]:
    """Load the isolated $10K-agent result without merging it into live state."""
    if directory is None or not directory.exists():
        return {}
    return read_json_object(directory / "simulation-result.json")


def _optional_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def _first_present(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None and value != "":
            return value
    return None


def _relevant_edge_alpha(profile: Mapping[str, Any]) -> tuple[str, float | None]:
    direct = _optional_number(
        _first_present(
            profile,
            "relevant_followable_alpha",
            "current_sector_followable_alpha",
        )
    )
    if direct is not None:
        return "relevant", direct
    horizons = profile.get("followable_alpha_by_horizon") or {}
    if isinstance(horizons, Mapping):
        for horizon in ("20", "5", "60", "120"):
            value = _optional_number(horizons.get(horizon))
            if value is not None:
                return f"{horizon}D", value
    return "overall", _optional_number(profile.get("followable_alpha"))


def _current_sector_alpha(profile: Mapping[str, Any]) -> float | None:
    direct = _optional_number(
        _first_present(
            profile,
            "sector_alpha",
            "current_sector_alpha",
            "relevant_sector_alpha",
            "sector_edge_alpha",
        )
    )
    if direct is not None:
        return direct
    current = profile.get("current_sector") or {}
    current_sector = ""
    current_benchmark = ""
    if isinstance(current, Mapping):
        current_sector = str(current.get("sector") or current.get("name") or "")
        current_benchmark = str(current.get("benchmark") or "")
    rows = profile.get("sector_performance") or []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_sector = str(row.get("sector") or row.get("name") or "")
        row_benchmark = str(row.get("benchmark") or "")
        if current_sector and row_sector.casefold() != current_sector.casefold():
            continue
        if not current_sector and current_benchmark and row_benchmark != current_benchmark:
            continue
        if not current_sector and not current_benchmark:
            continue
        value = _optional_number(
            _first_present(
                row,
                "followable_alpha",
                "weighted_followable_alpha",
                "alpha_percent",
                "alpha",
            )
        )
        if value is not None:
            return value
    return None


def analysis_export_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Feature-detect and flatten Edge values without inventing missing metrics."""

    result = dict(record)
    raw_profile = result.get("investor_edge") or {}
    profile = dict(raw_profile) if isinstance(raw_profile, Mapping) else {}
    observations = _optional_number(
        _first_present(
            result,
            "investor_edge_observation_count",
        )
    )
    if observations is None:
        observations = _optional_number(
            _first_present(
                profile,
                "sample_count",
                "observation_count",
                "completed_observation_count",
            )
        )
    has_observations = bool(observations is not None and observations > 0)
    alpha_label, alpha = _relevant_edge_alpha(profile)
    strongest = profile.get("strongest_sector") or {}
    strongest_name = ""
    if isinstance(strongest, Mapping):
        strongest_name = str(strongest.get("sector") or strongest.get("name") or "")

    result["final_score"] = _first_present(result, "final_score", "score")
    result["investor_edge_status"] = str(
        _first_present(result, "investor_edge_status")
        or profile.get("status")
        or profile.get("profile_status")
        or ("unavailable" if not profile else ("scored" if has_observations else "neutral"))
    )
    if result.get("investor_edge_modifier") is None and profile:
        result["investor_edge_modifier"] = _optional_number(profile.get("modifier"))
    result["investor_edge_observation_count"] = observations

    derived = {
        "investor_edge_score": _optional_number(profile.get("edge_score")),
        "investor_edge_confidence": _optional_number(
            _first_present(profile, "confidence", "identity_confidence")
        ),
        "investor_edge_confidence_label": str(
            _first_present(profile, "confidence_label", "identity_confidence_label") or ""
        ),
        "investor_edge_relevant_alpha_label": alpha_label if alpha is not None else "",
        "investor_edge_relevant_followable_alpha": alpha,
        "investor_edge_followable_alpha": _optional_number(profile.get("followable_alpha")),
        "investor_edge_hit_rate_percent": _optional_number(
            _first_present(
                profile,
                "weighted_followable_hit_rate_percent",
                "hit_rate_percent",
                "followable_hit_rate_percent",
            )
        ),
        "investor_edge_sector_alpha": _current_sector_alpha(profile),
        "investor_edge_current_disclosure_lag_days": _optional_number(
            profile.get("current_disclosure_lag_days")
        ),
        "investor_edge_average_disclosure_lag_days": _optional_number(
            _first_present(
                profile,
                "average_disclosure_lag_days",
                "median_disclosure_lag_days",
            )
        ),
        "investor_edge_strongest_sector": strongest_name,
    }
    for field, value in derived.items():
        if result.get(field) in (None, ""):
            if field == "investor_edge_current_disclosure_lag_days":
                result[field] = value
            else:
                result[field] = value if has_observations else ("" if isinstance(value, str) else None)
    return result


def _flatten_for_csv(record: Mapping[str, Any], fieldnames: Sequence[str]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for field in fieldnames:
        value = record.get(field, "")
        if isinstance(value, (dict, list)):
            flattened[field] = json.dumps(value, sort_keys=True)
        else:
            flattened[field] = value
    return flattened


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(_flatten_for_csv(row, fieldnames))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def max_timestamp(values: Iterable[str]) -> str:
    cleaned = [value for value in values if value]
    return max(cleaned) if cleaned else ""


def source_summary(
    filings: Sequence[Mapping[str, Any]],
    runs: Sequence[Mapping[str, Any]],
    states: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    sources = ("house", "senate", "oge")
    counts = Counter(str(item.get("source") or "") for item in filings)
    summary: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_runs = [
            run
            for run in runs
            if source in (run.get("source_counts") or {})
        ]
        source_runs.sort(key=lambda run: str(run.get("finished_utc") or ""), reverse=True)
        latest_run = source_runs[0] if source_runs else {}
        last_success = ""
        for run in source_runs:
            if bool(run.get("success")):
                last_success = str(run.get("finished_utc") or "")
                break
        if not last_success:
            last_success = max_timestamp(
                str(state.get("last_success_utc") or "") for state in states
            )
        summary[source] = {
            "source": source,
            "filing_count": counts.get(source, 0),
            "last_run_utc": str(latest_run.get("finished_utc") or ""),
            "last_success_utc": last_success,
            "latest_success": latest_run.get("success") if latest_run else None,
            "latest_error": "; ".join(str(item) for item in (latest_run.get("errors") or [])),
            "visible_count": int((latest_run.get("source_counts") or {}).get(source, 0) or 0),
        }
    return summary


def build_payload(
    legislative: dict[str, Any],
    executive: dict[str, Any],
    *,
    repository_url: str,
    ai: dict[str, Any] | None = None,
    simulation: dict[str, Any] | None = None,
    workflow_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filings = legislative["filings"] + executive["filings"]
    transactions = legislative["transactions"] + executive["transactions"]
    reviews = legislative["reviews"] + executive["reviews"]
    runs = legislative["runs"] + executive["runs"]
    ai = ai or {"analyses": [], "portfolio": [], "runs": [], "state": {}}
    simulation = dict(simulation or {})
    analyses = [
        analysis_export_record(item)
        for item in latest_by(ai.get("analyses", []), "trade_id")
    ]
    portfolio = latest_by(ai.get("portfolio", []), "position_id")
    ai_runs = latest_by(ai.get("runs", []), "run_key")

    filings = latest_by(filings, "filing_key")
    transactions = latest_by(transactions, "trade_id")
    reviews = latest_by(reviews, "review_id")
    runs = latest_by(runs, "run_key")

    filings.sort(key=lambda item: date_sort_value(item, "filed_date", "updated_at_utc", "filing_key"), reverse=True)
    transactions.sort(
        key=lambda item: date_sort_value(
            item, "filed_date", "transaction_date", "observed_at_utc", "trade_id"
        ),
        reverse=True,
    )
    reviews.sort(key=lambda item: date_sort_value(item, "filed_date", "observed_at_utc", "review_id"), reverse=True)
    runs.sort(key=lambda item: date_sort_value(item, "finished_utc", "run_key"), reverse=True)
    analyses.sort(key=lambda item: date_sort_value(item, "analyzed_at_utc", "analysis_id"), reverse=True)
    portfolio.sort(key=lambda item: date_sort_value(item, "opened_at_utc", "position_id"), reverse=True)
    ai_runs.sort(key=lambda item: date_sort_value(item, "finished_utc", "run_key"), reverse=True)

    status_counts = Counter(str(item.get("status") or "unknown") for item in filings)
    transaction_type_counts = Counter(
        str(item.get("transaction_type") or "Unknown") for item in transactions
    )
    purchase_count = sum(
        str(item.get("transaction_type") or "") == "Purchase" for item in transactions
    )
    manual_test_filing_count = sum(bool(item.get("is_synthetic_test")) for item in filings)
    manual_test_transaction_count = sum(
        bool(item.get("is_synthetic_test")) for item in transactions
    )
    classification_counts = Counter(
        str(item.get("classification") or "unknown") for item in analyses
    )
    direction_counts = Counter(
        str(item.get("signal_direction") or "unknown") for item in analyses
    )
    high_priority_bullish_count = sum(
        str(item.get("classification") or "") == "high_priority"
        and str(item.get("signal_direction") or "") == "bullish"
        for item in analyses
    )
    high_priority_bearish_count = sum(
        str(item.get("classification") or "") == "high_priority"
        and str(item.get("signal_direction") or "") == "bearish"
        for item in analyses
    )
    open_positions = [item for item in portfolio if str(item.get("status") or "") == "open"]
    closed_positions = [item for item in portfolio if str(item.get("status") or "") == "closed"]
    open_paper_pnl = sum(float(item.get("unrealized_pnl") or 0) for item in open_positions)
    realized_paper_pnl = sum(float(item.get("realized_pnl") or 0) for item in closed_positions)
    generated_utc = utc_now_iso()
    latest_timestamp = source_data_through({
        "summary": {"generated_utc": generated_utc}, "filings": filings,
        "transactions": transactions, "reviews": reviews, "runs": runs,
    })
    states = [legislative.get("state", {}), executive.get("state", {})]
    sources = source_summary(filings, runs, states)

    summary = {
        "generated_utc": generated_utc,
        "data_through_utc": latest_timestamp,
        "repository_url": repository_url,
        "filing_count": len(filings),
        "transaction_count": len(transactions),
        "purchase_count": purchase_count,
        "manual_test_filing_count": manual_test_filing_count,
        "manual_test_transaction_count": manual_test_transaction_count,
        "review_count": len(reviews),
        "run_count": len(runs),
        "analysis_count": len(analyses),
        "high_priority_count": classification_counts.get("high_priority", 0),
        "high_priority_bullish_count": high_priority_bullish_count,
        "high_priority_bearish_count": high_priority_bearish_count,
        "watchlist_count": classification_counts.get("watchlist", 0),
        "direction_counts": dict(sorted(direction_counts.items())),
        "open_paper_position_count": len(open_positions),
        "closed_paper_position_count": len(closed_positions),
        "open_paper_pnl": round(open_paper_pnl, 2),
        "realized_paper_pnl": round(realized_paper_pnl, 2),
        "classification_counts": dict(sorted(classification_counts.items())),
        "ai_last_success_utc": str((ai.get("state") or {}).get("last_success_utc") or ""),
        "status_counts": dict(sorted(status_counts.items())),
        "transaction_type_counts": dict(sorted(transaction_type_counts.items())),
        "sources": sources,
        "coverage_note": (
            "Cataloged filings show what the tracker can currently see. A 'Cataloged only' "
            "record predates transaction backfill and has not necessarily been parsed. "
            "AI scores are evidence-constrained research rankings and all positions are simulated."
        ),
    }
    return {
        "summary": summary,
        "filings": filings,
        "transactions": transactions,
        "reviews": reviews,
        "runs": runs,
        "analyses": analyses,
        "portfolio": portfolio,
        "ai_runs": ai_runs,
        "simulation": simulation,
        "workflow_evidence": dict(workflow_evidence or {}),
    }


# Source assets remain generator-owned; generated Pages files are never edited.
ASSET_DIR = Path(__file__).with_name("dashboard_assets")
INDEX_HTML = (ASSET_DIR / "index.html").read_text(encoding="utf-8")
STYLES_CSS = (ASSET_DIR / "styles.css").read_text(encoding="utf-8")
WALLBOARD_HTML = (ASSET_DIR / "wallboard.html").read_text(encoding="utf-8")
WALLBOARD_CSS = (ASSET_DIR / "wallboard.css").read_text(encoding="utf-8")
_SHARED_JS = "\n".join((ASSET_DIR / name).read_text(encoding="utf-8") for name in ("notifications.js", "common.js"))
APP_JS = _SHARED_JS + "\n" + (ASSET_DIR / "app.js").read_text(encoding="utf-8")
WALLBOARD_JS = _SHARED_JS + "\n" + (ASSET_DIR / "wallboard.js").read_text(encoding="utf-8")


def build_site(payload: Mapping[str, Any], output_dir: Path) -> None:
    # Public projection only; never publish private delivery payloads or modify inputs.
    payload = public_payload(payload)
    payload["reviews"] = review_rows(payload)
    catalog = filing_catalog(payload)
    payload = attach_filing_ids(payload, catalog)
    vault_origin = api_origin(os.environ.get("FILING_VAULT_API_ORIGIN", ""))
    output_dir = output_dir.resolve()
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=parent))
    try:
        data_dir = temp_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        write_json(data_dir / "summary.json", payload["summary"])
        write_json(data_dir / "filing-resources.json", catalog)
        write_json(data_dir / "filing-vault-config.json", {"api_origin": vault_origin})
        insights = attach_filing_ids(build_insights(payload), catalog)
        (data_dir / "dashboard-insights.json").write_text(json.dumps(insights, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        write_json(data_dir / "filings.json", payload["filings"])
        write_json(data_dir / "transactions.json", payload["transactions"])
        write_json(data_dir / "pending-reviews.json", payload["reviews"])
        write_json(data_dir / "runs.json", payload["runs"])
        write_json(data_dir / "ai-analyses.json", payload["analyses"])
        write_json(data_dir / "paper-portfolio.json", payload["portfolio"])
        write_json(data_dir / "ai-runs.json", payload["ai_runs"])
        write_json(data_dir / "simulation.json", payload.get("simulation", {}))
        write_csv(data_dir / "filings.csv", payload["filings"], FILING_FIELDS)
        write_csv(data_dir / "transactions.csv", payload["transactions"], TRANSACTION_FIELDS)
        write_csv(data_dir / "pending-reviews.csv", payload["reviews"], REVIEW_FIELDS)
        write_csv(data_dir / "runs.csv", payload["runs"], RUN_FIELDS)
        write_csv(data_dir / "ai-analyses.csv", payload["analyses"], ANALYSIS_FIELDS)
        write_csv(data_dir / "paper-portfolio.csv", payload["portfolio"], PORTFOLIO_FIELDS)
        write_csv(data_dir / "ai-runs.csv", payload["ai_runs"], AI_RUN_FIELDS)
        (temp_dir / "index.html").write_text(INDEX_HTML, encoding="utf-8")
        (temp_dir / "404.html").write_text(INDEX_HTML, encoding="utf-8")
        (temp_dir / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
        (temp_dir / "app.js").write_text(APP_JS, encoding="utf-8")
        (temp_dir / "wallboard.html").write_text(WALLBOARD_HTML, encoding="utf-8")
        (temp_dir / "wallboard.css").write_text(WALLBOARD_CSS, encoding="utf-8")
        (temp_dir / "wallboard.js").write_text(WALLBOARD_JS, encoding="utf-8")
        vault_html = (ASSET_DIR / "filing-vault.html").read_text(encoding="utf-8")
        if vault_origin:
            vault_html = vault_html.replace("connect-src 'self';", f"connect-src 'self' {vault_origin};")
        (temp_dir / "filing-vault.html").write_text(vault_html, encoding="utf-8")
        (temp_dir / "filing-vault.css").write_text((ASSET_DIR / "filing-vault.css").read_text(encoding="utf-8"), encoding="utf-8")
        (temp_dir / "filing-vault.js").write_text(_SHARED_JS + "\n" + (ASSET_DIR / "filing-vault.js").read_text(encoding="utf-8"), encoding="utf-8")
        shutil.copyfile(ASSET_DIR / "filing-pdf.js", temp_dir / "filing-pdf.js")
        shutil.copyfile(ASSET_DIR / "filing-pdf.css", temp_dir / "filing-pdf.css")
        shutil.copytree(ASSET_DIR / "vendor" / "pdfjs", temp_dir / "vendor" / "pdfjs")
        copy_branding_assets(temp_dir)
        (temp_dir / ".nojekyll").write_text("", encoding="utf-8")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        temp_dir.replace(output_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislative-dir", type=Path)
    parser.add_argument("--executive-dir", type=Path)
    parser.add_argument("--ai-dir", type=Path)
    parser.add_argument("--simulation-dir", type=Path)
    parser.add_argument("--workflow-evidence-file", type=Path,
                        help="Read-only validated canonical Actions attempt observations")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--repository-url",
        default=(
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', 'maglothinm/PolitiTrack').strip('/')}"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    legislative = load_branch(args.legislative_dir, "legislative")
    executive = load_branch(args.executive_dir, "executive")
    ai = load_ai(args.ai_dir)
    simulation = load_simulation(args.simulation_dir)
    workflow_evidence = load_workflow_evidence(args.workflow_evidence_file)
    payload = build_payload(
        legislative,
        executive,
        repository_url=args.repository_url,
        ai=ai,
        simulation=simulation,
        workflow_evidence=workflow_evidence,
    )
    build_site(payload, args.output_dir)
    build_dashboard_addon(args.ai_dir, args.output_dir)
    print(
        f"Dashboard built at {args.output_dir}: "
        f"{len(payload['filings'])} filings, {len(payload['transactions'])} transactions, "
        f"{len(payload['reviews'])} review items, {len(payload['analyses'])} AI analyses, "
        f"{len(payload['portfolio'])} paper positions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
