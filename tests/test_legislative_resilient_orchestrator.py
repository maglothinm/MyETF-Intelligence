from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_legislative_sources_resilient as resilient


FAKE_TRACKER = r'''#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--branch")
p.add_argument("--source", required=True)
p.add_argument("--result-file", required=True)
p.add_argument("--run-history-file")
p.add_argument("--no-notify", action="store_true")
p.add_argument("--verbose", action="store_true")
a = p.parse_args()
fail = set(filter(None, os.environ.get("FAKE_FAIL_SOURCES", "").split(",")))
status = "blocked" if a.source == "senate" else "error"
success = a.source not in fail
payload = {
  "branch": "legislative", "started_utc": "2026-09-05T00:00:00Z",
  "finished_utc": "2026-09-05T00:00:01Z",
  "source_statuses": {a.source: "ok" if success else status},
  "overall_status": "ok" if success else "degraded",
  "discovery_complete": success,
  "source_counts": {a.source: 1} if success else {},
  "new_filing_counts": {a.source: 0} if success else {},
  "cataloged_filing_counts": {a.source: 0} if success else {},
  "baseline_counts": {a.source: 0} if success else {},
  "transaction_counts": {a.source: 0} if success else {},
  "purchase_counts": {a.source: 0} if success else {},
  "alerted_filing_counts": {a.source: 0} if success else {},
  "pending_review_counts": {a.source: 0} if success else {},
  "filings": [], "transactions": [], "purchases": [], "pending_reviews": [],
  "errors": [] if success else ["SenateAccessDenied: required discovery incomplete"],
  "success": success, "historical_backfill": {}
}
Path(a.result_file).write_text(json.dumps(payload), encoding="utf-8")
with Path(os.environ["FAKE_ARGS_LOG"]).open("a", encoding="utf-8") as h:
    h.write(json.dumps(sys.argv[1:]) + "\n")
sys.exit(0 if success else 1)
'''


def run_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failures: str, *, no_notify: bool = True):
    tracker = tmp_path / "fake_tracker.py"
    tracker.write_text(FAKE_TRACKER, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RESULT_FILE", "legislative-result.json")
    monkeypatch.setenv("RUN_HISTORY_FILE", ".trade-tracker/legislative/runs.jsonl")
    monkeypatch.setenv("FAKE_ARGS_LOG", str(tmp_path / "args.jsonl"))
    monkeypatch.setenv("FAKE_FAIL_SOURCES", failures)
    argv = ["--tracker-script", str(tracker), "--python", resilient.sys.executable]
    if no_notify:
        argv.append("--no-notify")
    code = resilient.main(argv)
    result = json.loads((tmp_path / "legislative-result.json").read_text(encoding="utf-8"))
    status = json.loads((tmp_path / "legislative-source-status.json").read_text(encoding="utf-8"))
    arguments = [json.loads(line) for line in (tmp_path / "args.jsonl").read_text().splitlines()]
    history = (tmp_path / ".trade-tracker/legislative/runs.jsonl").read_text().splitlines()
    return code, result, status, arguments, history


def test_senate_outage_preserves_house_success_and_durable_state_eligibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    code, result, status, arguments, history = run_fake(tmp_path, monkeypatch, "senate")
    assert code == 0
    assert result["success"] is True
    assert result["overall_status"] == "degraded"
    assert result["discovery_complete"] is False
    assert result["source_statuses"] == {"house": "ok", "senate": "blocked"}
    assert result["source_counts"] == {"house": 1}
    assert status["success"] is True
    assert status["notifications_suppressed"] is True
    assert len(history) == 1
    assert all("--no-notify" in item for item in arguments)


def test_both_sources_succeed_as_one_combined_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    code, result, status, _arguments, history = run_fake(tmp_path, monkeypatch, "")
    assert code == 0
    assert result["success"] is True
    assert result["overall_status"] == "ok"
    assert result["discovery_complete"] is True
    assert result["source_statuses"] == {"house": "ok", "senate": "ok"}
    assert result["source_counts"] == {"house": 1, "senate": 1}
    assert status["overall_status"] == "ok"
    assert len(history) == 1


def test_both_sources_fail_nonzero_without_false_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    code, result, status, _arguments, history = run_fake(tmp_path, monkeypatch, "senate,house")
    assert code == 1
    assert result["success"] is False
    assert result["overall_status"] == "error"
    assert result["source_statuses"] == {"house": "error", "senate": "blocked"}
    assert status["success"] is False
    assert len(history) == 1
