from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import government_trade_tracker as entrypoint
from scripts import legislative_healthcheck
from scripts import run_legislative_sources_resilient as resilient


FAKE_TRANSACTIONAL_TRACKER = r'''#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--branch", required=True)
parser.add_argument("--source", required=True)
parser.add_argument("--state-file", required=True)
parser.add_argument("--ledger-file", required=True)
parser.add_argument("--transactions-file", required=True)
parser.add_argument("--filings-file", required=True)
parser.add_argument("--pending-file", required=True)
parser.add_argument("--result-file", required=True)
parser.add_argument("--run-history-file", required=True)
parser.add_argument("--latest-csv", required=True)
parser.add_argument("--latest-transactions-csv", required=True)
parser.add_argument("--latest-filings-csv", required=True)
parser.add_argument("--watchlist")
parser.add_argument("--senate-lookback-days")
parser.add_argument("--acknowledge-terms", action="store_true")
parser.add_argument("--no-notify", action="store_true")
args = parser.parse_args()

state_path = Path(args.state_file)
state = json.loads(state_path.read_text(encoding="utf-8"))
observed = sorted(state["seen_trades"])
fails = args.source in set(filter(None, os.environ.get("FAKE_FAIL_SOURCES", "").split(",")))
new_transactions = 1 if args.source == os.environ.get("FAKE_NEW_TRANSACTION_SOURCE") else 0
failed_alerts = 1 if args.source == os.environ.get("FAKE_FAILED_ALERT_SOURCE") else 0
state["seen_trades"][args.source] = "discarded" if fails else "committed"
state["last_success_utc"] = "2026-09-05T14:00:00Z"
state_path.write_text(json.dumps(state), encoding="utf-8")
with Path(args.ledger_file).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"source": args.source, "failed": fails}) + "\n")

payload = {
    "branch": "legislative",
    "started_utc": "2026-09-05T13:59:00Z",
    "finished_utc": "2026-09-05T14:00:00Z",
    "source_statuses": {args.source: "blocked" if fails else "ok"},
    "overall_status": "degraded" if fails else "ok",
    "discovery_complete": not fails,
    "source_counts": {} if fails else {args.source: 3},
    "new_filing_counts": {} if fails else {args.source: 0},
    "cataloged_filing_counts": {} if fails else {args.source: 0},
    "baseline_counts": {} if fails else {args.source: 0},
    "transaction_counts": {} if fails else {args.source: new_transactions},
    "purchase_counts": {} if fails else {args.source: new_transactions},
    "alerted_filing_counts": ({args.source: failed_alerts} if fails and failed_alerts else
                               {} if fails else {args.source: 0}),
    "pending_review_counts": {} if fails else {args.source: 0},
    "filings": [], "transactions": [], "purchases": [], "pending_reviews": [],
    "errors": ["SourceUnavailable: required discovery incomplete"] if fails else [],
    "success": not fails,
    "historical_backfill": {},
}
Path(args.result_file).write_text(json.dumps(payload), encoding="utf-8")
with Path(os.environ["FAKE_INTEGRATION_LOG"]).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": sys.argv[1:], "source": args.source,
                             "observed": observed, "no_notify": args.no_notify}) + "\n")
raise SystemExit(1 if fails else 0)
'''


def _write_initial_state(directory: Path) -> dict[str, Path]:
    directory.mkdir(parents=True)
    paths = {
        "state": directory / "state.json",
        "ledger": directory / "purchases.jsonl",
        "transactions": directory / "transactions.jsonl",
        "filings": directory / "filings.jsonl",
        "pending": directory / "pending-review.jsonl",
        "history": directory / "runs.jsonl",
    }
    paths["state"].write_text(json.dumps({
        "version": 1,
        "last_success_utc": "2026-09-04T00:00:00Z",
        "seen_filings": {"house": {}, "senate": {}, "oge": {}},
        "seen_trades": {"prior": "retained"},
        "seen_reviews": {},
    }), encoding="utf-8")
    paths["ledger"].write_text('{"prior":true}\n', encoding="utf-8")
    for key in ("transactions", "filings", "pending", "history"):
        paths[key].write_text("", encoding="utf-8")
    return paths


def _write_restore_receipt(path: Path, state_path: Path, *, consumer_sha: str) -> None:
    artifact_digest = "1" * 64
    path.write_text(json.dumps({
        "version": 1,
        "restored_at_utc": "2026-09-05T13:58:00Z",
        "repository_id": 1349678672,
        "consumer_sha": consumer_sha,
        "predecessor_artifact_id": 9969550055,
        "predecessor_artifact_name": "legislative-tracker-state",
        "predecessor_artifact_created_at": "2026-09-05T12:00:00Z",
        "predecessor_artifact_api_digest": f"sha256:{artifact_digest}",
        "downloaded_zip_sha256": artifact_digest,
        "predecessor_run_id": 33966378019,
        "predecessor_run_attempt": 1,
        "predecessor_head_sha": "b" * 40,
        "predecessor_workflow_id": 987654,
        "predecessor_workflow_file": "legislative_trade_tracker_v2.yml",
        "predecessor_workflow_name": "Legislative purchase tracker v2",
        "restored_state_sha256": hashlib.sha256(state_path.read_bytes()).hexdigest(),
    }) + "\n", encoding="utf-8")


def _set_controlled_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    restore_receipt_path: Path,
    controlled_receipt_path: Path,
) -> str:
    consumer_sha = "a" * 40
    monkeypatch.setenv("RESTORE_RECEIPT_FILE", str(restore_receipt_path))
    monkeypatch.setenv("CONTROLLED_VALIDATION_RECEIPT_FILE", str(controlled_receipt_path))
    monkeypatch.setenv("POLITITRACK_REQUIRE_RESTORE_RECEIPT", "true")
    monkeypatch.setenv("POLITITRACK_CONTROLLED_VALIDATION", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setenv("GITHUB_REPOSITORY_ID", "1349678672")
    monkeypatch.setenv("GITHUB_REPOSITORY", "maglothinm/MyETF-Intelligence")
    monkeypatch.setenv("GITHUB_SHA", consumer_sha)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", "workflow_dispatch")
    return consumer_sha


def test_wrapper_forwards_original_argv_including_equals_form(monkeypatch, tmp_path):
    captured = {}

    def fake_run(arguments, *, tracker_script, **kwargs):
        captured["arguments"] = list(arguments)
        captured["tracker_script"] = tracker_script
        return 19

    monkeypatch.setattr(resilient, "run_tracker_arguments", fake_run)
    arguments = [
        "--branch=legislative",
        "--source=all",
        "--state-file", str(tmp_path / "state.json"),
        "--watchlist=MSFT,BRK.B",
        "--senate-lookback-days", "45",
        "--acknowledge-terms",
        "--no-notify",
    ]
    assert entrypoint.main(arguments) == 19
    assert captured["arguments"] == arguments
    assert captured["tracker_script"].name == "government_trade_tracker_core.py"


def test_degraded_transaction_discards_failed_source_and_binds_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "fake_tracker.py"
    fake.write_text(FAKE_TRANSACTIONAL_TRACKER, encoding="utf-8")
    state_paths = _write_initial_state(tmp_path / "protected")
    result_path = tmp_path / "run" / "legislative-result.json"
    receipt_path = tmp_path / "protected" / "source-status.json"
    restore_receipt_path = tmp_path / "protected" / "restore-receipt.json"
    controlled_receipt_path = tmp_path / "protected" / "controlled-validation-receipt.json"
    consumer_sha = _set_controlled_environment(
        monkeypatch,
        restore_receipt_path=restore_receipt_path,
        controlled_receipt_path=controlled_receipt_path,
    )
    _write_restore_receipt(restore_receipt_path, state_paths["state"], consumer_sha=consumer_sha)
    log_path = tmp_path / "children.jsonl"
    monkeypatch.setenv("FAKE_FAIL_SOURCES", "senate")
    monkeypatch.setenv("FAKE_INTEGRATION_LOG", str(log_path))
    monkeypatch.setenv("SOURCE_STATUS_FILE", str(receipt_path))

    latest_paths = {
        "latest": tmp_path / "run" / "purchases.csv",
        "latest_transactions": tmp_path / "run" / "transactions.csv",
        "latest_filings": tmp_path / "run" / "filings.csv",
    }
    arguments = [
        "--branch=legislative", "--source=all",
        "--state-file", str(state_paths["state"]),
        "--ledger-file", str(state_paths["ledger"]),
        "--transactions-file", str(state_paths["transactions"]),
        "--filings-file", str(state_paths["filings"]),
        "--pending-file", str(state_paths["pending"]),
        "--run-history-file", str(state_paths["history"]),
        "--result-file", str(result_path),
        "--latest-csv", str(latest_paths["latest"]),
        "--latest-transactions-csv", str(latest_paths["latest_transactions"]),
        "--latest-filings-csv", str(latest_paths["latest_filings"]),
        "--watchlist=MSFT,BRK.B", "--senate-lookback-days", "45",
        "--acknowledge-terms", "--no-notify",
    ]
    assert resilient.run_tracker_arguments(
        arguments, tracker_script=fake, sources=("senate", "house")
    ) == 0

    state = json.loads(state_paths["state"].read_text(encoding="utf-8"))
    assert state["seen_trades"] == {"prior": "retained", "house": "committed"}
    ledger = [json.loads(line) for line in state_paths["ledger"].read_text().splitlines()]
    assert ledger == [{"prior": True}, {"source": "house", "failed": False}]
    children = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert children[0]["source"] == "senate"
    assert children[1]["source"] == "house"
    assert children[1]["observed"] == ["prior"]
    assert all(child["no_notify"] for child in children)
    assert all("--watchlist=MSFT,BRK.B" in child["argv"] for child in children)
    assert all("--senate-lookback-days" in child["argv"] for child in children)

    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["success"] is True
    assert result["overall_status"] == "degraded"
    assert result["source_statuses"] == {"house": "ok", "senate": "blocked"}
    history = json.loads(state_paths["history"].read_text(encoding="utf-8"))
    assert history["run_key"] == "123:2"
    assert history["run_url"].endswith("/actions/runs/123")
    assert history["trigger_source"] == "workflow_dispatch"
    assert history["source_statuses"] == result["source_statuses"]

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["durable_state_eligible"] is True
    assert receipt["validation_outcome"] == "zero_change_successor"
    assert receipt["rollback_performed"] is False
    assert receipt["outbound_notifications_attempted"] == 0
    assert receipt["outbound_notifications_sent"] == 0
    assert receipt["notifications_suppressed"] is True
    assert receipt["result_sha256"] == hashlib.sha256(result_path.read_bytes()).hexdigest()
    assert receipt["state_sha256"] == hashlib.sha256(state_paths["state"].read_bytes()).hexdigest()
    assert receipt["restore_receipt_sha256"] == hashlib.sha256(
        restore_receipt_path.read_bytes()
    ).hexdigest()
    assert legislative_healthcheck.main([
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path), "--validate-durable",
        "--restore-receipt", str(restore_receipt_path), "--require-restore-receipt",
        "--controlled-validation-receipt", str(controlled_receipt_path),
        "--require-controlled-validation-receipt", "--require-run-provenance",
        "--require-notifications-suppressed",
    ]) == 0
    assert legislative_healthcheck.main([
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path), "--validate-protected-upload",
        "--restore-receipt", str(restore_receipt_path),
        "--controlled-validation-receipt", str(controlled_receipt_path),
        "--require-run-provenance",
    ]) == 0


def test_compatibility_entrypoint_retains_executable_git_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    mode = subprocess.run(
        ["git", "ls-files", "-s", "scripts/government_trade_tracker.py"],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.split()[0]
    assert mode == "100755"


def test_suppressed_new_notification_eligible_record_blocks_durable_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "fake_tracker.py"
    fake.write_text(FAKE_TRANSACTIONAL_TRACKER, encoding="utf-8")
    state_paths = _write_initial_state(tmp_path / "protected")
    result_path = tmp_path / "legislative-result.json"
    receipt_path = tmp_path / "protected" / "source-status.json"
    restore_receipt_path = tmp_path / "protected" / "restore-receipt.json"
    controlled_receipt_path = tmp_path / "protected" / "controlled-validation-receipt.json"
    consumer_sha = _set_controlled_environment(
        monkeypatch,
        restore_receipt_path=restore_receipt_path,
        controlled_receipt_path=controlled_receipt_path,
    )
    _write_restore_receipt(restore_receipt_path, state_paths["state"], consumer_sha=consumer_sha)
    protected_before = {key: path.read_bytes() for key, path in state_paths.items()}
    monkeypatch.setenv("FAKE_FAIL_SOURCES", "senate")
    monkeypatch.setenv("FAKE_NEW_TRANSACTION_SOURCE", "house")
    monkeypatch.setenv("FAKE_INTEGRATION_LOG", str(tmp_path / "children.jsonl"))
    monkeypatch.setenv("SOURCE_STATUS_FILE", str(receipt_path))
    arguments = [
        "--branch", "legislative", "--source", "all",
        "--state-file", str(state_paths["state"]),
        "--ledger-file", str(state_paths["ledger"]),
        "--transactions-file", str(state_paths["transactions"]),
        "--filings-file", str(state_paths["filings"]),
        "--pending-file", str(state_paths["pending"]),
        "--run-history-file", str(state_paths["history"]),
        "--result-file", str(result_path),
        "--latest-csv", str(tmp_path / "latest.csv"),
        "--latest-transactions-csv", str(tmp_path / "transactions.csv"),
        "--latest-filings-csv", str(tmp_path / "filings.csv"),
        "--no-notify",
    ]
    assert resilient.run_tracker_arguments(arguments, tracker_script=fake) == 0
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["notifications_suppressed"] is True
    assert receipt["notification_eligible_new_records"] == 1
    assert receipt["durable_state_eligible"] is False
    assert receipt["protected_upload_eligible"] is True
    assert receipt["validation_outcome"] == "notification_eligible_rollback"
    assert receipt["rollback_performed"] is True
    assert receipt["rollback_verified"] is True
    assert receipt["outbound_notifications_attempted"] == 0
    assert receipt["outbound_notifications_sent"] == 0
    assert receipt["candidate_state_sha256"] != receipt["state_sha256"]
    for key, path in state_paths.items():
        assert path.read_bytes() == protected_before[key]
    controlled = json.loads(controlled_receipt_path.read_text(encoding="utf-8"))
    assert controlled["validation_outcome"] == "notification_eligible_rollback"
    assert controlled["predecessor_state_sha256"] == receipt["state_sha256"]
    assert controlled["post_run_state_sha256"] == receipt["state_sha256"]
    assert all(item["matches_predecessor"] for item in controlled["protected_files"])
    assert legislative_healthcheck.main([
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path), "--validate-durable",
        "--require-notifications-suppressed",
        "--require-no-notification-eligible-records",
    ]) == 1
    assert legislative_healthcheck.main([
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path), "--validate-protected-upload",
        "--restore-receipt", str(restore_receipt_path),
        "--controlled-validation-receipt", str(controlled_receipt_path),
        "--require-run-provenance",
    ]) == 0


def test_controlled_total_outage_republishes_exact_predecessor_without_deadlock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "fake_tracker.py"
    fake.write_text(FAKE_TRANSACTIONAL_TRACKER, encoding="utf-8")
    state_paths = _write_initial_state(tmp_path / "protected")
    result_path = tmp_path / "legislative-result.json"
    receipt_path = tmp_path / "protected" / "source-status.json"
    restore_receipt_path = tmp_path / "protected" / "restore-receipt.json"
    controlled_receipt_path = tmp_path / "protected" / "controlled-validation-receipt.json"
    consumer_sha = _set_controlled_environment(
        monkeypatch,
        restore_receipt_path=restore_receipt_path,
        controlled_receipt_path=controlled_receipt_path,
    )
    _write_restore_receipt(restore_receipt_path, state_paths["state"], consumer_sha=consumer_sha)
    protected_before = {key: path.read_bytes() for key, path in state_paths.items()}
    monkeypatch.setenv("FAKE_FAIL_SOURCES", "senate,house")
    monkeypatch.setenv("FAKE_INTEGRATION_LOG", str(tmp_path / "children.jsonl"))
    monkeypatch.setenv("SOURCE_STATUS_FILE", str(receipt_path))
    arguments = [
        "--branch", "legislative", "--source", "all",
        "--state-file", str(state_paths["state"]),
        "--ledger-file", str(state_paths["ledger"]),
        "--transactions-file", str(state_paths["transactions"]),
        "--filings-file", str(state_paths["filings"]),
        "--pending-file", str(state_paths["pending"]),
        "--run-history-file", str(state_paths["history"]),
        "--result-file", str(result_path),
        "--latest-csv", str(tmp_path / "latest.csv"),
        "--latest-transactions-csv", str(tmp_path / "transactions.csv"),
        "--latest-filings-csv", str(tmp_path / "filings.csv"),
        "--no-notify",
    ]
    assert resilient.run_tracker_arguments(arguments, tracker_script=fake) == 0
    for key, path in state_paths.items():
        assert path.read_bytes() == protected_before[key]

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["success"] is False
    assert receipt["durable_state_eligible"] is False
    assert receipt["protected_upload_eligible"] is True
    assert receipt["validation_outcome"] == "contained_failure"
    assert receipt["rollback_performed"] is True
    assert receipt["rollback_verified"] is True
    assert receipt["outbound_notifications_attempted"] == 0
    assert receipt["outbound_notifications_sent"] == 0
    controlled = json.loads(controlled_receipt_path.read_text(encoding="utf-8"))
    assert controlled["repository_id"] == 1349678672
    assert controlled["consumer_sha"] == consumer_sha
    assert controlled["run_id"] == 123
    assert controlled["run_attempt"] == 2
    assert controlled["no_outbound_attested"] is True
    assert all(item["matches_predecessor"] for item in controlled["protected_files"])

    common = [
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path),
        "--restore-receipt", str(restore_receipt_path),
        "--controlled-validation-receipt", str(controlled_receipt_path),
        "--require-run-provenance",
    ]
    assert legislative_healthcheck.main([*common, "--validate-durable"]) == 1
    assert legislative_healthcheck.main([*common, "--validate-protected-upload"]) == 0

    controlled["run_attempt"] = 3
    controlled_receipt_path.write_text(json.dumps(controlled), encoding="utf-8")
    receipt["controlled_validation_receipt_sha256"] = hashlib.sha256(
        controlled_receipt_path.read_bytes()
    ).hexdigest()
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    assert legislative_healthcheck.main([*common, "--validate-protected-upload"]) == 1


def test_controlled_run_without_no_notify_cannot_publish_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "fake_tracker.py"
    fake.write_text(FAKE_TRANSACTIONAL_TRACKER, encoding="utf-8")
    state_paths = _write_initial_state(tmp_path / "protected")
    result_path = tmp_path / "legislative-result.json"
    receipt_path = tmp_path / "protected" / "source-status.json"
    restore_receipt_path = tmp_path / "protected" / "restore-receipt.json"
    controlled_receipt_path = tmp_path / "protected" / "controlled-validation-receipt.json"
    consumer_sha = _set_controlled_environment(
        monkeypatch,
        restore_receipt_path=restore_receipt_path,
        controlled_receipt_path=controlled_receipt_path,
    )
    _write_restore_receipt(restore_receipt_path, state_paths["state"], consumer_sha=consumer_sha)
    monkeypatch.setenv("FAKE_FAIL_SOURCES", "senate,house")
    monkeypatch.setenv("FAKE_INTEGRATION_LOG", str(tmp_path / "children.jsonl"))
    monkeypatch.setenv("SOURCE_STATUS_FILE", str(receipt_path))
    arguments = [
        "--branch", "legislative", "--source", "all",
        "--state-file", str(state_paths["state"]),
        "--ledger-file", str(state_paths["ledger"]),
        "--transactions-file", str(state_paths["transactions"]),
        "--filings-file", str(state_paths["filings"]),
        "--pending-file", str(state_paths["pending"]),
        "--run-history-file", str(state_paths["history"]),
        "--result-file", str(result_path),
        "--latest-csv", str(tmp_path / "latest.csv"),
        "--latest-transactions-csv", str(tmp_path / "transactions.csv"),
        "--latest-filings-csv", str(tmp_path / "filings.csv"),
    ]
    assert resilient.run_tracker_arguments(arguments, tracker_script=fake) == 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["notifications_suppressed"] is False
    assert receipt["durable_state_eligible"] is False
    assert receipt["protected_upload_eligible"] is False
    controlled = json.loads(controlled_receipt_path.read_text(encoding="utf-8"))
    assert controlled["no_outbound_attested"] is False
    assert legislative_healthcheck.main([
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path), "--validate-protected-upload",
        "--restore-receipt", str(restore_receipt_path),
        "--controlled-validation-receipt", str(controlled_receipt_path),
        "--require-run-provenance",
    ]) == 1


def test_failed_source_nonzero_delivery_evidence_blocks_contained_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = tmp_path / "fake_tracker.py"
    fake.write_text(FAKE_TRANSACTIONAL_TRACKER, encoding="utf-8")
    state_paths = _write_initial_state(tmp_path / "protected")
    result_path = tmp_path / "legislative-result.json"
    receipt_path = tmp_path / "protected" / "source-status.json"
    restore_receipt_path = tmp_path / "protected" / "restore-receipt.json"
    controlled_receipt_path = tmp_path / "protected" / "controlled-validation-receipt.json"
    consumer_sha = _set_controlled_environment(
        monkeypatch,
        restore_receipt_path=restore_receipt_path,
        controlled_receipt_path=controlled_receipt_path,
    )
    _write_restore_receipt(restore_receipt_path, state_paths["state"], consumer_sha=consumer_sha)
    monkeypatch.setenv("FAKE_FAIL_SOURCES", "senate,house")
    monkeypatch.setenv("FAKE_FAILED_ALERT_SOURCE", "senate")
    monkeypatch.setenv("FAKE_INTEGRATION_LOG", str(tmp_path / "children.jsonl"))
    monkeypatch.setenv("SOURCE_STATUS_FILE", str(receipt_path))
    arguments = [
        "--branch", "legislative", "--source", "all",
        "--state-file", str(state_paths["state"]),
        "--ledger-file", str(state_paths["ledger"]),
        "--transactions-file", str(state_paths["transactions"]),
        "--filings-file", str(state_paths["filings"]),
        "--pending-file", str(state_paths["pending"]),
        "--run-history-file", str(state_paths["history"]),
        "--result-file", str(result_path),
        "--latest-csv", str(tmp_path / "latest.csv"),
        "--latest-transactions-csv", str(tmp_path / "transactions.csv"),
        "--latest-filings-csv", str(tmp_path / "filings.csv"),
        "--no-notify",
    ]
    assert resilient.run_tracker_arguments(arguments, tracker_script=fake) == 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["outbound_notifications_sent"] == 1
    assert receipt["protected_upload_eligible"] is False
    senate = next(item for item in receipt["sources"] if item["source"] == "senate")
    assert senate["notification_delivery_evidence"] == "reported_nonzero"
    assert senate["reported_outbound_notifications_sent"] == 1
    controlled = json.loads(controlled_receipt_path.read_text(encoding="utf-8"))
    assert controlled["no_outbound_attested"] is False
    assert legislative_healthcheck.main([
        "--result", str(result_path), "--state", str(state_paths["state"]),
        "--source-status", str(receipt_path), "--validate-protected-upload",
        "--restore-receipt", str(restore_receipt_path),
        "--controlled-validation-receipt", str(controlled_receipt_path),
        "--require-run-provenance",
    ]) == 1
