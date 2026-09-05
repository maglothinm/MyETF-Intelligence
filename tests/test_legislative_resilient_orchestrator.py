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
p.add_argument("--state-file", required=True)
p.add_argument("--ledger-file", required=True)
p.add_argument("--transactions-file", required=True)
p.add_argument("--filings-file", required=True)
p.add_argument("--pending-file", required=True)
p.add_argument("--latest-csv", required=True)
p.add_argument("--latest-transactions-csv", required=True)
p.add_argument("--latest-filings-csv", required=True)
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
state_path = Path(a.state_file)
state = json.loads(state_path.read_text(encoding="utf-8"))
state["last_success_utc"] = "2026-09-05T00:00:01Z"
state["seen_trades"][a.source] = "committed" if success else "discard-me"
state_path.write_text(json.dumps(state), encoding="utf-8")
with Path(a.ledger_file).open("a", encoding="utf-8") as h:
    h.write(json.dumps({"source": a.source, "success": success}) + "\n")
with Path(os.environ["FAKE_ARGS_LOG"]).open("a", encoding="utf-8") as h:
    h.write(json.dumps(sys.argv[1:]) + "\n")
sys.exit(0 if success else 1)
'''


def run_fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failures: str, *, no_notify: bool = True):
    tracker = tmp_path / "fake_tracker.py"
    tracker.write_text(FAKE_TRACKER, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for name in (
        "GITHUB_EVENT_NAME",
        "GITHUB_REPOSITORY",
        "GITHUB_REPOSITORY_ID",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_RUN_ID",
        "GITHUB_SERVER_URL",
        "GITHUB_SHA",
        "POLITITRACK_CONTROLLED_VALIDATION",
        "POLITITRACK_REQUIRE_RESTORE_RECEIPT",
        "POLITITRACK_TRIGGER_SOURCE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RESULT_FILE", "legislative-result.json")
    # Keep this unit-test fixture independent of workflow-level output paths.
    monkeypatch.setenv("SOURCE_STATUS_FILE", "legislative-source-status.json")
    monkeypatch.setenv("RUN_HISTORY_FILE", ".trade-tracker/legislative/runs.jsonl")
    monkeypatch.setenv("FAKE_ARGS_LOG", str(tmp_path / "args.jsonl"))
    monkeypatch.setenv("FAKE_FAIL_SOURCES", failures)
    state_dir = tmp_path / ".trade-tracker/legislative"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text(json.dumps({
        "version": 1,
        "last_success_utc": "2026-09-04T00:00:00Z",
        "seen_filings": {"house": {}, "senate": {}, "oge": {}},
        "seen_trades": {},
        "seen_reviews": {},
    }), encoding="utf-8")
    for name in ("purchases.jsonl", "transactions.jsonl", "filings.jsonl", "pending-review.jsonl"):
        (state_dir / name).write_text("", encoding="utf-8")
    argv = ["--tracker-script", str(tracker), "--python", resilient.sys.executable]
    if no_notify:
        argv.append("--no-notify")
    code = resilient.main(argv)
    result = json.loads((tmp_path / "legislative-result.json").read_text(encoding="utf-8"))
    status = json.loads((tmp_path / "legislative-source-status.json").read_text(encoding="utf-8"))
    arguments = [json.loads(line) for line in (tmp_path / "args.jsonl").read_text().splitlines()]
    history_path = tmp_path / ".trade-tracker/legislative/runs.jsonl"
    history = history_path.read_text().splitlines() if history_path.exists() else []
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
    assert status["version"] == 3
    assert status["durable_state_eligible"] is True
    assert status["validation_outcome"] == "zero_change_successor"
    assert status["notifications_suppressed"] is True
    assert len(history) == 1
    history_record = json.loads(history[0])
    assert history_record["branch"] == "legislative"
    assert history_record["overall_status"] == "degraded"
    assert history_record["run_key"].startswith("run:")
    assert history_record["event_name"] == "local"
    state = json.loads((tmp_path / ".trade-tracker/legislative/state.json").read_text())
    assert state["seen_trades"] == {"house": "committed"}
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
    assert status["durable_state_eligible"] is False
    assert history == []
    state = json.loads((tmp_path / ".trade-tracker/legislative/state.json").read_text())
    assert state["seen_trades"] == {}
