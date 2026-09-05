#!/usr/bin/env python3
"""Run House and Senate collectors independently while preserving one durable state.

The underlying tracker remains fail-closed for each official source. This orchestrator
isolates a source outage so a blocked Senate endpoint does not suppress a healthy House
collection (and vice versa). A run succeeds in degraded mode when at least one source
completes; it fails when neither source completes.
"""

from __future__ import annotations

import argparse
import json
import os
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


def iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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
        for field in MAP_FIELDS:
            values = payload.get(field)
            if isinstance(values, dict):
                combined[field].update(values)
        for field in LIST_FIELDS:
            values = payload.get(field)
            if isinstance(values, list):
                combined[field].extend(value for value in values if isinstance(value, dict))
        historical = payload.get("historical_backfill")
        if isinstance(historical, dict):
            combined["historical_backfill"].update(historical)

        if item["returncode"] == 0:
            combined["source_statuses"][source] = str(
                combined["source_statuses"].get(source) or "ok"
            )
        else:
            status = "error"
            statuses = payload.get("source_statuses")
            if isinstance(statuses, dict) and statuses.get(source):
                status = str(statuses[source])
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _write_summary(payload: dict[str, Any], source_runs: list[dict[str, Any]]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return
    lines = [
        "## Legislative source-isolated collection",
        "",
        f"- Success: **{str(payload['success']).lower()}**",
        f"- Overall status: **{payload['overall_status']}**",
        f"- Durable-state eligible: **{str(payload['success']).lower()}**",
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

    result_path = Path(os.environ.get("RESULT_FILE", "legislative-result.json"))
    run_history_path = Path(
        os.environ.get("RUN_HISTORY_FILE", ".trade-tracker/legislative/runs.jsonl")
    )
    status_path = Path(args.status_file)
    started = iso_utc()
    source_runs: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="polititrack-legislative-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        for source in sources:
            source_result = result_path.with_name(
                f"{result_path.stem}-{source}{result_path.suffix or '.json'}"
            )
            source_history = temp_dir / f"{source}-runs.jsonl"
            source_summary = temp_dir / f"{source}-summary.md"
            command = [
                args.python,
                args.tracker_script,
                "--branch",
                "legislative",
                "--source",
                source,
                "--result-file",
                str(source_result),
                "--run-history-file",
                str(source_history),
            ]
            if args.no_notify:
                command.append("--no-notify")
            if args.verbose:
                command.append("--verbose")
            child_env = os.environ.copy()
            child_env["GITHUB_STEP_SUMMARY"] = str(source_summary)
            completed = subprocess.run(command, env=child_env, check=False)
            source_runs.append(
                {
                    "source": source,
                    "returncode": completed.returncode,
                    "result_file": str(source_result),
                    "payload": _load_json(source_result),
                }
            )

    combined = combine_results(source_runs, started_utc=started, finished_utc=iso_utc())
    _write_json(result_path, combined)
    _append_history(run_history_path, combined)
    _write_json(
        status_path,
        {
            "version": 1,
            "started_utc": combined["started_utc"],
            "finished_utc": combined["finished_utc"],
            "overall_status": combined["overall_status"],
            "success": combined["success"],
            "notifications_suppressed": bool(args.no_notify),
            "sources": [
                {
                    "source": item["source"],
                    "returncode": item["returncode"],
                    "status": combined["source_statuses"].get(item["source"], "unknown"),
                    "result_file": item["result_file"],
                }
                for item in source_runs
            ],
        },
    )
    _write_summary(combined, source_runs)
    return 0 if combined["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
