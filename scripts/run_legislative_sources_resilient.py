#!/usr/bin/env python3
"""Run House and Senate collectors independently while preserving one durable state.

The underlying tracker remains fail-closed for each official source. This orchestrator
isolates a source outage so a blocked Senate endpoint does not suppress a healthy House
collection (and vice versa). A run succeeds in degraded mode when at least one source
completes; it fails when neither source completes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

MAP_FIELDS = (
    "source_statuses",
    "source_counts",
    "new_filing_counts",
    "cataloged_filing_counts",
    "baseline_counts",
    "transaction_counts",
    "purchase_counts",
    "alerted_filing_counts",
    "pending_review_counts",
)
LIST_FIELDS = ("filings", "transactions", "purchases", "pending_reviews")

PATH_OPTIONS = {
    "state": ("--state-file", "STATE_FILE", ".trade-tracker/legislative/state.json"),
    "ledger": ("--ledger-file", "LEDGER_FILE", ".trade-tracker/legislative/purchases.jsonl"),
    "transactions": (
        "--transactions-file",
        "TRANSACTIONS_FILE",
        ".trade-tracker/legislative/transactions.jsonl",
    ),
    "filings": ("--filings-file", "FILINGS_FILE", ".trade-tracker/legislative/filings.jsonl"),
    "pending": (
        "--pending-file",
        "PENDING_FILE",
        ".trade-tracker/legislative/pending-review.jsonl",
    ),
    "result": ("--result-file", "RESULT_FILE", "legislative-result.json"),
    "history": (
        "--run-history-file",
        "RUN_HISTORY_FILE",
        ".trade-tracker/legislative/runs.jsonl",
    ),
    "latest": ("--latest-csv", "LATEST_CSV", "legislative-latest-purchases.csv"),
    "latest_transactions": (
        "--latest-transactions-csv",
        "LATEST_TRANSACTIONS_CSV",
        "legislative-latest-transactions.csv",
    ),
    "latest_filings": (
        "--latest-filings-csv",
        "LATEST_FILINGS_CSV",
        "legislative-latest-filings.csv",
    ),
}

DURABLE_PATH_KEYS = ("state", "ledger", "transactions", "filings", "pending")
LATEST_PATH_KEYS = ("latest", "latest_transactions", "latest_filings")
APPEND_ONLY_PATH_KEYS = ("ledger", "transactions", "filings", "pending")
PROTECTED_STATE_PATH_KEYS = (*DURABLE_PATH_KEYS, "history")


def iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _option_value(arguments: Sequence[str], flag: str) -> str | None:
    value: str | None = None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == flag:
            if index + 1 < len(arguments):
                value = arguments[index + 1]
            index += 2
            continue
        prefix = flag + "="
        if argument.startswith(prefix):
            value = argument[len(prefix):]
        index += 1
    return value


def _replace_option(arguments: Sequence[str], flag: str, value: str) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == flag:
            index += 2
            continue
        if argument.startswith(flag + "="):
            index += 1
            continue
        output.append(argument)
        index += 1
    output.extend((flag, value))
    return output


def _configured_paths(arguments: Sequence[str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for key, (flag, environment, default) in PATH_OPTIONS.items():
        configured = _option_value(arguments, flag) or os.environ.get(environment) or default
        paths[key] = Path(configured)
    return paths


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_state(path: Path) -> bool:
    state = _load_json(path)
    return (
        state.get("version") == 1
        and isinstance(state.get("last_success_utc"), str)
        and bool(state["last_success_utc"].strip())
        and isinstance(state.get("seen_filings"), dict)
        and isinstance(state.get("seen_trades"), dict)
        and isinstance(state.get("seen_reviews"), dict)
    )


def _valid_source_result(payload: dict[str, Any], source: str) -> bool:
    statuses = payload.get("source_statuses")
    counts = payload.get("source_counts")
    count = counts.get(source) if isinstance(counts, dict) else None
    transactions = payload.get("transaction_counts")
    pending = payload.get("pending_review_counts")
    alerted = payload.get("alerted_filing_counts")
    return (
        payload.get("branch") == "legislative"
        and payload.get("success") is True
        and payload.get("discovery_complete") is True
        and payload.get("overall_status") == "ok"
        and isinstance(statuses, dict)
        and statuses.get(source) == "ok"
        and type(count) is int
        and count > 0
        and isinstance(transactions, dict)
        and type(transactions.get(source)) is int
        and transactions[source] >= 0
        and isinstance(pending, dict)
        and type(pending.get(source)) is int
        and pending[source] >= 0
        and isinstance(alerted, dict)
        and type(alerted.get(source)) is int
        and alerted[source] >= 0
    )


def _state_advanced(original: Path, staged: Path) -> bool:
    if not staged.is_file():
        return False
    if not original.is_file():
        return True
    return staged.read_bytes() != original.read_bytes()


def _notification_eligible_new_records(payload: dict[str, Any]) -> int | None:
    total = 0
    for field in ("transaction_counts", "pending_review_counts"):
        values = payload.get(field)
        if not isinstance(values, dict):
            return None
        for source in ("house", "senate"):
            value = values.get(source, 0)
            if type(value) is not int or value < 0:
                return None
            total += value
    return total


def _notification_delivery_count(payload: dict[str, Any]) -> int | None:
    values = payload.get("alerted_filing_counts")
    if not isinstance(values, dict):
        return None
    total = 0
    for source in ("house", "senate"):
        value = values.get(source, 0)
        if type(value) is not int or value < 0:
            return None
        total += value
    return total


def _reported_source_deliveries(payload: dict[str, Any], source: str) -> tuple[str, int | None]:
    values = payload.get("alerted_filing_counts")
    if not isinstance(values, dict) or source not in values:
        return "unavailable", None
    value = values[source]
    if type(value) is not int or value < 0:
        return "contradictory", None
    return ("verified_zero" if value == 0 else "reported_nonzero"), value


def _append_only_prefixes_preserved(
    original_paths: dict[str, Path], staged_paths: dict[str, Path]
) -> bool:
    for key in APPEND_ONLY_PATH_KEYS:
        original = original_paths[key]
        staged = staged_paths[key]
        if original.exists():
            if not staged.exists() or not staged.read_bytes().startswith(original.read_bytes()):
                return False
    return True


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        shutil.copyfile(source, temp_path)
        temp_path.replace(destination)
    finally:
        temp_path.unlink(missing_ok=True)


def _stage_paths(original_paths: dict[str, Path], directory: Path) -> dict[str, Path]:
    staged: dict[str, Path] = {}
    for key in (*DURABLE_PATH_KEYS, *LATEST_PATH_KEYS):
        original = original_paths[key]
        target = directory / f"{key}{original.suffix}"
        staged[key] = target
        if original.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
    return staged


def _promote_source_transaction(
    original_paths: dict[str, Path], staged_paths: dict[str, Path]
) -> None:
    for key in (*DURABLE_PATH_KEYS, *LATEST_PATH_KEYS):
        source = staged_paths[key]
        if source.exists():
            _copy_atomic(source, original_paths[key])


def _snapshot_paths(paths: dict[str, Path]) -> dict[str, bytes | None]:
    return {
        key: paths[key].read_bytes() if paths[key].is_file() else None
        for key in PROTECTED_STATE_PATH_KEYS
    }


def _restore_snapshot(paths: dict[str, Path], snapshot: dict[str, bytes | None]) -> None:
    for key in PROTECTED_STATE_PATH_KEYS:
        destination = paths[key]
        original = snapshot[key]
        if original is None:
            destination.unlink(missing_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=destination.name + ".", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(original)
            Path(temp_name).replace(destination)
        finally:
            Path(temp_name).unlink(missing_ok=True)


def _protected_file_evidence(
    paths: dict[str, Path], snapshot: dict[str, bytes | None]
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for key in PROTECTED_STATE_PATH_KEYS:
        original = snapshot[key]
        current = paths[key].read_bytes() if paths[key].is_file() else None
        evidence.append(
            {
                "key": key,
                "existed_before": original is not None,
                "existed_after": current is not None,
                "before_sha256": hashlib.sha256(original).hexdigest() if original is not None else "",
                "after_sha256": hashlib.sha256(current).hexdigest() if current is not None else "",
                "matches_predecessor": current == original,
            }
        )
    return evidence


def _environment_int(name: str) -> int:
    value = os.environ.get(name, "").strip()
    return int(value) if value.isdigit() else 0


def _unique_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        marker = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if marker in seen:
            continue
        seen.add(marker)
        output.append(record)
    return output


def combine_results(
    source_runs: list[dict[str, Any]], *, started_utc: str, finished_utc: str
) -> dict[str, Any]:
    successful = [item for item in source_runs if item["returncode"] == 0]
    combined: dict[str, Any] = {
        "branch": "legislative",
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "source_statuses": {},
        "overall_status": (
            "ok" if len(successful) == len(source_runs) else "degraded" if successful else "error"
        ),
        "discovery_complete": len(successful) == len(source_runs),
        "source_counts": {},
        "new_filing_counts": {},
        "cataloged_filing_counts": {},
        "baseline_counts": {},
        "transaction_counts": {},
        "purchase_counts": {},
        "alerted_filing_counts": {},
        "pending_review_counts": {},
        "filings": [],
        "transactions": [],
        "purchases": [],
        "pending_reviews": [],
        "errors": [],
        "success": bool(successful),
        "historical_backfill": {},
    }

    for item in source_runs:
        source = str(item["source"])
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        if item["returncode"] == 0:
            for field in MAP_FIELDS:
                values = payload.get(field)
                if isinstance(values, dict):
                    combined[field].update(values)
            for field in LIST_FIELDS:
                values = payload.get(field)
                if isinstance(values, list):
                    combined[field].extend(
                        value for value in values if isinstance(value, dict)
                    )
            historical = payload.get("historical_backfill")
            if isinstance(historical, dict):
                combined["historical_backfill"].update(historical)
            combined["source_statuses"][source] = str(
                combined["source_statuses"].get(source) or "ok"
            )
        else:
            status = "error"
            statuses = payload.get("source_statuses")
            if isinstance(statuses, dict) and statuses.get(source):
                status = str(statuses[source])
            if status not in {"blocked", "error"}:
                status = "error"
            combined["source_statuses"][source] = status
            source_errors = payload.get("errors")
            if isinstance(source_errors, list) and source_errors:
                for error in source_errors:
                    combined["errors"].append(f"{source.title()}: {error}")
            else:
                combined["errors"].append(
                    f"{source.title()}: collector exited {item['returncode']} without a result diagnostic"
                )

    for field in LIST_FIELDS:
        combined[field] = _unique_records(combined[field])
    return combined


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _append_history(path: Path, payload: dict[str, Any]) -> None:
    try:
        from . import government_trade_tracker_core as tracker_core  # type: ignore
    except ImportError:  # pragma: no cover - direct script execution
        import government_trade_tracker_core as tracker_core  # type: ignore

    fields = tracker_core.TrackerResult.__dataclass_fields__
    result = tracker_core.TrackerResult(
        **{name: payload[name] for name in fields if name in payload}
    )
    tracker_core.append_run_history(path, result)


def _write_summary(payload: dict[str, Any], source_runs: list[dict[str, Any]]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return
    lines = [
        "## Legislative source-isolated collection",
        "",
        f"- Success: **{str(payload['success']).lower()}**",
        f"- Overall status: **{payload['overall_status']}**",
        "- Durable-state eligible: **verified by the source-status receipt and validation step**",
        "",
        "| Source | Exit code | Status |",
        "|---|---:|---|",
    ]
    for item in source_runs:
        source = str(item["source"])
        lines.append(
            f"| {source.title()} | {item['returncode']} | "
            f"{payload['source_statuses'].get(source, 'unknown')} |"
        )
    if payload["errors"]:
        lines.extend(["", "### Degraded-source diagnostics"])
        lines.extend(f"- {error}" for error in payload["errors"])
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        default="senate,house",
        help="Comma-separated source order. Defaults to senate,house.",
    )
    parser.add_argument("--no-notify", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--tracker-script",
        default=str(Path(__file__).with_name("government_trade_tracker.py")),
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--status-file",
        default=os.environ.get("SOURCE_STATUS_FILE", "legislative-source-status.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sources = [part.strip().lower() for part in args.sources.split(",") if part.strip()]
    if not sources or len(set(sources)) != len(sources) or any(
        source not in {"house", "senate"} for source in sources
    ):
        raise SystemExit("--sources must contain unique values from: house, senate")

    tracker_arguments = ["--branch", "legislative", "--source", "all"]
    if args.no_notify:
        tracker_arguments.append("--no-notify")
    if args.verbose:
        tracker_arguments.append("--verbose")
    return run_tracker_arguments(
        tracker_arguments,
        sources=sources,
        tracker_script=Path(args.tracker_script),
        python=args.python,
        status_path=Path(args.status_file),
    )


def run_tracker_arguments(
    tracker_arguments: Sequence[str],
    *,
    sources: Sequence[str] = ("senate", "house"),
    tracker_script: Path,
    python: str = sys.executable,
    status_path: Path | None = None,
) -> int:
    sources = tuple(str(source).strip().lower() for source in sources)
    if not sources or len(set(sources)) != len(sources) or any(
        source not in {"house", "senate"} for source in sources
    ):
        raise ValueError("sources must contain unique values from: house, senate")

    paths = _configured_paths(tracker_arguments)
    result_path = paths["result"]
    run_history_path = paths["history"]
    status_path = status_path or Path(
        os.environ.get("SOURCE_STATUS_FILE", "legislative-source-status.json")
    )
    started = iso_utc()
    source_runs: list[dict[str, Any]] = []
    protected_snapshot = _snapshot_paths(paths)

    with tempfile.TemporaryDirectory(prefix="polititrack-legislative-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        for source in sources:
            source_result = result_path.with_name(
                f"{result_path.stem}-{source}{result_path.suffix or '.json'}"
            )
            source_result.parent.mkdir(parents=True, exist_ok=True)
            source_result.unlink(missing_ok=True)
            source_directory = temp_dir / source
            source_directory.mkdir(parents=True, exist_ok=True)
            staged_paths = _stage_paths(paths, source_directory)
            source_history = source_directory / "runs.jsonl"
            source_summary = temp_dir / f"{source}-summary.md"
            child_arguments = list(tracker_arguments)
            child_arguments = _replace_option(child_arguments, "--source", source)
            child_arguments = _replace_option(
                child_arguments, "--result-file", str(source_result)
            )
            child_arguments = _replace_option(
                child_arguments, "--run-history-file", str(source_history)
            )
            for key in (*DURABLE_PATH_KEYS, *LATEST_PATH_KEYS):
                child_arguments = _replace_option(
                    child_arguments, PATH_OPTIONS[key][0], str(staged_paths[key])
                )
            command = [python, str(tracker_script), *child_arguments]
            child_env = os.environ.copy()
            child_env["GITHUB_STEP_SUMMARY"] = str(source_summary)
            completed = subprocess.run(command, env=child_env, check=False)
            payload = _load_json(source_result)
            source_valid = (
                completed.returncode == 0
                and _valid_source_result(payload, source)
                and _valid_state(staged_paths["state"])
                and _state_advanced(paths["state"], staged_paths["state"])
                and _append_only_prefixes_preserved(paths, staged_paths)
            )
            returncode = completed.returncode
            if completed.returncode == 0 and not source_valid:
                returncode = 70
            if source_valid:
                _promote_source_transaction(paths, staged_paths)
            source_runs.append(
                {
                    "source": source,
                    "returncode": returncode,
                    "result_file": str(source_result),
                    "payload": payload,
                    "state_candidate_valid": source_valid,
                    "state_committed": source_valid,
                }
            )

    combined = combine_results(source_runs, started_utc=started, finished_utc=iso_utc())
    _write_json(result_path, combined)
    result_hash = _sha256(result_path)
    restore_receipt_path = Path(
        os.environ.get(
            "RESTORE_RECEIPT_FILE",
            str(paths["state"].with_name("restore-receipt.json")),
        )
    )
    restore_receipt_hash = (
        _sha256(restore_receipt_path) if restore_receipt_path.is_file() else ""
    )
    require_restore_receipt = (
        os.environ.get("POLITITRACK_REQUIRE_RESTORE_RECEIPT", "").strip().lower()
        == "true"
    )
    controlled_validation = (
        os.environ.get("POLITITRACK_CONTROLLED_VALIDATION", "").strip().lower()
        == "true"
    )
    notifications_suppressed = "--no-notify" in tracker_arguments
    notification_eligible_new_records = _notification_eligible_new_records(combined)
    notification_delivery_count = _notification_delivery_count(combined)
    source_delivery_evidence = [
        _reported_source_deliveries(item["payload"], item["source"])
        for item in source_runs
    ]
    contradictory_delivery_evidence = any(
        status == "contradictory" for status, _value in source_delivery_evidence
    )
    outbound_notifications_sent = (
        None
        if contradictory_delivery_evidence
        else sum(value or 0 for _status, value in source_delivery_evidence)
    )
    candidate_state_valid = paths["state"].is_file() and _valid_state(paths["state"])
    candidate_state_sha256 = _sha256(paths["state"]) if paths["state"].is_file() else ""
    durable_state_eligible = bool(
        combined["success"]
        and candidate_state_valid
        and notification_eligible_new_records is not None
        and notification_delivery_count is not None
        and not contradictory_delivery_evidence
        and (not require_restore_receipt or bool(restore_receipt_hash))
        and (not controlled_validation or notifications_suppressed)
        and (not notifications_suppressed or notification_eligible_new_records == 0)
        and (not notifications_suppressed or outbound_notifications_sent == 0)
    )
    rollback_required = notifications_suppressed and not durable_state_eligible
    if rollback_required:
        _restore_snapshot(paths, protected_snapshot)
        for item in source_runs:
            item["state_committed"] = False
    else:
        _append_history(run_history_path, combined)

    state_hash = _sha256(paths["state"]) if paths["state"].is_file() else ""
    protected_files = _protected_file_evidence(paths, protected_snapshot)
    rollback_verified = bool(
        rollback_required and all(item["matches_predecessor"] for item in protected_files)
    )
    protected_state_action = "rolled_back" if rollback_required else "committed"
    if not rollback_required:
        rollback_reason = ""
    elif outbound_notifications_sent not in {0, None} or contradictory_delivery_evidence:
        rollback_reason = "suppressed_delivery_accounting_nonzero"
    elif notification_eligible_new_records not in {0, None}:
        rollback_reason = "notification_eligible_records"
    elif not combined["success"]:
        rollback_reason = "collection_unsuccessful"
    elif not candidate_state_valid:
        rollback_reason = "invalid_candidate_state"
    elif require_restore_receipt and not restore_receipt_hash:
        rollback_reason = "missing_restore_receipt"
    else:
        rollback_reason = "invalid_notification_accounting"

    controlled_receipt_path = Path(
        os.environ.get(
            "CONTROLLED_VALIDATION_RECEIPT_FILE",
            str(paths["state"].with_name("controlled-validation-receipt.json")),
        )
    )
    predecessor_state = protected_snapshot["state"]
    predecessor_state_sha256 = (
        hashlib.sha256(predecessor_state).hexdigest()
        if predecessor_state is not None
        else ""
    )
    outbound_notifications_attempted = 0 if notifications_suppressed else None
    no_outbound_attested = bool(
        notifications_suppressed
        and outbound_notifications_attempted == 0
        and outbound_notifications_sent == 0
    )
    if durable_state_eligible:
        validation_outcome = "zero_change_successor"
    elif (
        rollback_verified
        and notification_eligible_new_records is not None
        and notification_eligible_new_records > 0
        and candidate_state_sha256
        and candidate_state_sha256 != predecessor_state_sha256
    ):
        validation_outcome = "notification_eligible_rollback"
    else:
        validation_outcome = "contained_failure"
    _write_json(
        controlled_receipt_path,
        {
            "version": 1,
            "attested_at_utc": combined["finished_utc"],
            "repository_id": _environment_int("GITHUB_REPOSITORY_ID"),
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "consumer_sha": os.environ.get("GITHUB_SHA", ""),
            "run_id": _environment_int("GITHUB_RUN_ID"),
            "run_attempt": _environment_int("GITHUB_RUN_ATTEMPT"),
            "trigger_source": os.environ.get(
                "POLITITRACK_TRIGGER_SOURCE",
                os.environ.get("GITHUB_EVENT_NAME", "local"),
            ),
            "controlled_validation": controlled_validation,
            "notifications_suppressed": notifications_suppressed,
            "no_outbound_attested": no_outbound_attested,
            "outbound_notifications_attempted": outbound_notifications_attempted,
            "outbound_notifications_sent": outbound_notifications_sent,
            "notification_delivery_count": notification_delivery_count,
            "notification_eligible_new_records": notification_eligible_new_records,
            "collection_success": combined["success"],
            "overall_status": combined["overall_status"],
            "validation_outcome": validation_outcome,
            "protected_state_action": protected_state_action,
            "rollback_performed": rollback_required,
            "rollback_reason": rollback_reason,
            "rollback_verified": rollback_verified,
            "result_sha256": result_hash,
            "restore_receipt_sha256": restore_receipt_hash,
            "predecessor_state_sha256": predecessor_state_sha256,
            "candidate_state_sha256": candidate_state_sha256,
            "post_run_state_sha256": state_hash,
            "protected_files": protected_files,
        },
    )
    controlled_receipt_hash = _sha256(controlled_receipt_path)
    protected_upload_eligible = bool(
        durable_state_eligible
        or (
            controlled_validation
            and no_outbound_attested
            and rollback_verified
            and state_hash
            and _valid_state(paths["state"])
            and restore_receipt_hash
        )
    )
    _write_json(
        status_path,
        {
            "version": 3,
            "started_utc": combined["started_utc"],
            "finished_utc": combined["finished_utc"],
            "overall_status": combined["overall_status"],
            "success": combined["success"],
            "durable_state_eligible": durable_state_eligible,
            "protected_upload_eligible": protected_upload_eligible,
            "validation_outcome": validation_outcome,
            "protected_state_action": protected_state_action,
            "rollback_performed": rollback_required,
            "rollback_verified": rollback_verified,
            "rollback_reason": rollback_reason,
            "notifications_suppressed": notifications_suppressed,
            "outbound_notifications_attempted": outbound_notifications_attempted,
            "outbound_notifications_sent": outbound_notifications_sent,
            "notification_eligible_new_records": notification_eligible_new_records,
            "notification_delivery_count": notification_delivery_count,
            "result_sha256": result_hash,
            "state_sha256": state_hash,
            "candidate_state_sha256": candidate_state_sha256,
            "restore_receipt_sha256": restore_receipt_hash,
            "controlled_validation_receipt_sha256": controlled_receipt_hash,
            "sources": [
                {
                    "source": item["source"],
                    "returncode": item["returncode"],
                    "status": combined["source_statuses"].get(item["source"], "unknown"),
                    "result_file": item["result_file"],
                    "state_candidate_valid": item["state_candidate_valid"],
                    "state_committed": item["state_committed"],
                    "notification_eligible_new_records": (
                        _notification_eligible_new_records(item["payload"])
                        if item["state_candidate_valid"]
                        else 0
                    ),
                    "notification_delivery_count": (
                        _notification_delivery_count(item["payload"])
                        if item["state_candidate_valid"]
                        else 0
                    ),
                    "notification_delivery_evidence": source_delivery_evidence[index][0],
                    "reported_outbound_notifications_sent": source_delivery_evidence[index][1],
                }
                for index, item in enumerate(source_runs)
            ],
        },
    )
    _write_summary(combined, source_runs)
    return 0 if combined["success"] or protected_upload_eligible else 1


if __name__ == "__main__":
    raise SystemExit(main())
