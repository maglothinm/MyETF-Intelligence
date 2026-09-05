"""Validate complete discovery and send one classified terminal heartbeat.

Never forward tracker result JSON, exception text, source response bodies, or
credential-bearing URLs to logs or Healthchecks. The workflow owns start pings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def read_result(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def complete_catalogs(result: dict) -> bool:
    counts = result.get("source_counts", {})
    statuses = result.get("source_statuses", {})
    return (
        result.get("discovery_complete") is True
        and isinstance(counts, dict)
        and isinstance(statuses, dict)
        and all(statuses.get(source) == "ok" for source in ("house", "senate"))
        and all(type(counts.get(source)) is int and counts[source] > 0
                for source in ("house", "senate"))
    )


def complete_result(result: dict) -> bool:
    return (result.get("success") is True and result.get("overall_status") == "ok"
            and complete_catalogs(result))


def durable_result(result: dict) -> bool:
    """Accept a complete run or one committed official source, never zero sources."""
    statuses = result.get("source_statuses")
    counts = result.get("source_counts")
    if not isinstance(statuses, dict) or set(statuses) != {"house", "senate"}:
        return False
    if not isinstance(counts, dict):
        return False
    successful = [source for source in ("house", "senate") if statuses[source] == "ok"]
    if any(status not in {"ok", "blocked", "error"} for status in statuses.values()):
        return False
    if any(type(counts.get(source)) is not int or counts[source] <= 0
           for source in successful):
        return False
    if result.get("success") is not True or len(successful) not in {1, 2}:
        return False
    if len(successful) == 2:
        return (result.get("overall_status") == "ok"
                and result.get("discovery_complete") is True)
    return (result.get("overall_status") == "degraded"
            and result.get("discovery_complete") is False)


def complete_state(state: dict) -> bool:
    return (
        state.get("version") == 1
        and isinstance(state.get("last_success_utc"), str)
        and bool(state["last_success_utc"].strip())
        and isinstance(state.get("seen_filings"), dict)
        and isinstance(state.get("seen_trades"), dict)
        and isinstance(state.get("seen_reviews"), dict)
    )


def notification_eligible_new_records(result: dict) -> int | None:
    total = 0
    for field in ("transaction_counts", "pending_review_counts"):
        values = result.get(field)
        if not isinstance(values, dict):
            return None
        for source in ("house", "senate"):
            value = values.get(source, 0)
            if type(value) is not int or value < 0:
                return None
            total += value
    return total


def notification_delivery_count(result: dict) -> int | None:
    values = result.get("alerted_filing_counts")
    if not isinstance(values, dict):
        return None
    total = 0
    for source in ("house", "senate"):
        value = values.get(source, 0)
        if type(value) is not int or value < 0:
            return None
        total += value
    return total


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_receipt_evidence(result: dict, receipt: dict, *, action: str) -> bool:
    eligible_count = notification_eligible_new_records(result)
    delivery_count = notification_delivery_count(result)
    result_statuses = result.get("source_statuses")
    if (
        not isinstance(result_statuses, dict)
        or set(result_statuses) != {"house", "senate"}
        or any(status not in {"ok", "blocked", "error"}
               for status in result_statuses.values())
        or action not in {"committed", "rolled_back"}
        or receipt.get("version") != 3
        or receipt.get("success") is not result.get("success")
        or receipt.get("overall_status") != result.get("overall_status")
        or receipt.get("started_utc") != result.get("started_utc")
        or receipt.get("finished_utc") != result.get("finished_utc")
        or receipt.get("protected_state_action") != action
        or receipt.get("rollback_performed") is not (action == "rolled_back")
        or receipt.get("rollback_verified") is not (action == "rolled_back")
        or (action == "rolled_back" and not receipt.get("rollback_reason"))
        or (action == "committed" and receipt.get("rollback_reason") != "")
        or not isinstance(receipt.get("durable_state_eligible"), bool)
        or not isinstance(receipt.get("protected_upload_eligible"), bool)
        or not isinstance(receipt.get("notifications_suppressed"), bool)
        or eligible_count is None
        or delivery_count is None
        or receipt.get("notification_eligible_new_records") != eligible_count
        or receipt.get("notification_delivery_count") != delivery_count
        or receipt.get("outbound_notifications_sent") != delivery_count
        or (receipt.get("notifications_suppressed") is True
            and receipt.get("outbound_notifications_attempted") != 0)
    ):
        return False

    sources = receipt.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        return False
    indexed = {}
    receipt_eligible_total = 0
    receipt_delivery_total = 0
    reported_delivery_total = 0
    for item in sources:
        if not isinstance(item, dict) or item.get("source") not in {"house", "senate"}:
            return False
        source = item["source"]
        if source in indexed:
            return False
        returncode = item.get("returncode")
        candidate = item.get("state_candidate_valid")
        committed = item.get("state_committed")
        status = item.get("status")
        source_eligible = item.get("notification_eligible_new_records")
        source_deliveries = item.get("notification_delivery_count")
        delivery_evidence = item.get("notification_delivery_evidence")
        reported_deliveries = item.get("reported_outbound_notifications_sent")
        if (type(returncode) is not int or not isinstance(candidate, bool)
                or not isinstance(committed, bool)):
            return False
        if (type(source_eligible) is not int or source_eligible < 0
                or type(source_deliveries) is not int or source_deliveries < 0):
            return False
        if delivery_evidence == "unavailable":
            if reported_deliveries is not None:
                return False
        elif delivery_evidence == "verified_zero":
            if reported_deliveries != 0:
                return False
        elif delivery_evidence == "reported_nonzero":
            if type(reported_deliveries) is not int or reported_deliveries <= 0:
                return False
            reported_delivery_total += reported_deliveries
        elif delivery_evidence == "contradictory":
            return False
        else:
            return False
        if delivery_evidence == "verified_zero":
            reported_delivery_total += 0
        if status != result_statuses.get(source):
            return False
        if status == "ok":
            if returncode != 0 or candidate is not True:
                return False
            if committed is not (action == "committed"):
                return False
        elif returncode == 0 or candidate is not False or committed is not False:
            return False
        indexed[source] = item
        receipt_eligible_total += source_eligible
        receipt_delivery_total += source_deliveries
    return (
        set(indexed) == {"house", "senate"}
        and receipt_eligible_total == eligible_count
        and receipt_delivery_total == delivery_count
        and receipt.get("outbound_notifications_sent") == reported_delivery_total
    )


def controlled_validation_receipt(
    result: dict,
    source_receipt: dict,
    receipt: dict,
    *,
    result_path: Path,
    state_path: Path,
    restore_receipt_path: Path,
    action: str,
    require_run_provenance: bool = False,
) -> bool:
    eligible_count = notification_eligible_new_records(result)
    delivery_count = notification_delivery_count(result)
    try:
        result_hash = _sha256(result_path)
        state_hash = _sha256(state_path)
        restore_hash = _sha256(restore_receipt_path)
        restore = read_result(restore_receipt_path)
    except OSError:
        return False
    no_outbound = bool(
        source_receipt.get("notifications_suppressed") is True
        and source_receipt.get("outbound_notifications_attempted") == 0
        and source_receipt.get("outbound_notifications_sent") == 0
        and delivery_count == 0
    )
    if (
        receipt.get("version") != 1
        or receipt.get("attested_at_utc") != result.get("finished_utc")
        or receipt.get("notifications_suppressed")
            is not source_receipt.get("notifications_suppressed")
        or receipt.get("no_outbound_attested") is not no_outbound
        or receipt.get("outbound_notifications_attempted")
            != source_receipt.get("outbound_notifications_attempted")
        or receipt.get("outbound_notifications_sent")
            != source_receipt.get("outbound_notifications_sent")
        or receipt.get("notification_delivery_count") != delivery_count
        or receipt.get("notification_eligible_new_records") != eligible_count
        or receipt.get("collection_success") is not result.get("success")
        or receipt.get("overall_status") != result.get("overall_status")
        or receipt.get("protected_state_action") != action
        or receipt.get("rollback_performed") is not (action == "rolled_back")
        or receipt.get("rollback_verified")
            is not source_receipt.get("rollback_verified")
        or receipt.get("rollback_reason") != source_receipt.get("rollback_reason")
        or receipt.get("validation_outcome") != source_receipt.get("validation_outcome")
        or receipt.get("candidate_state_sha256")
            != source_receipt.get("candidate_state_sha256")
        or receipt.get("result_sha256") != result_hash
        or receipt.get("restore_receipt_sha256") != restore_hash
        or receipt.get("post_run_state_sha256") != state_hash
    ):
        return False

    files = receipt.get("protected_files")
    if not isinstance(files, list) or len(files) != 6:
        return False
    indexed: dict[str, dict] = {}
    for item in files:
        if not isinstance(item, dict) or item.get("key") not in {
            "state", "ledger", "transactions", "filings", "pending", "history"
        }:
            return False
        key = item["key"]
        if key in indexed:
            return False
        before_exists = item.get("existed_before")
        after_exists = item.get("existed_after")
        before_hash = item.get("before_sha256")
        after_hash = item.get("after_sha256")
        if not isinstance(before_exists, bool) or not isinstance(after_exists, bool):
            return False
        if ((before_exists and not re.fullmatch(r"[0-9a-f]{64}", str(before_hash)))
                or (not before_exists and before_hash != "")
                or (after_exists and not re.fullmatch(r"[0-9a-f]{64}", str(after_hash)))
                or (not after_exists and after_hash != "")):
            return False
        matches = before_exists == after_exists and before_hash == after_hash
        if item.get("matches_predecessor") is not matches:
            return False
        indexed[key] = item
    if set(indexed) != {"state", "ledger", "transactions", "filings", "pending", "history"}:
        return False
    if (
        receipt.get("predecessor_state_sha256") != indexed["state"]["before_sha256"]
        or receipt.get("post_run_state_sha256") != indexed["state"]["after_sha256"]
        or restore.get("version") != 1
        or restore.get("restored_state_sha256") != indexed["state"]["before_sha256"]
        or type(restore.get("repository_id")) is not int
        or restore["repository_id"] <= 0
        or not re.fullmatch(r"[0-9a-f]{40}", str(restore.get("consumer_sha", "")))
        or type(restore.get("predecessor_artifact_id")) is not int
        or restore["predecessor_artifact_id"] <= 0
        or restore.get("predecessor_artifact_name") != "legislative-tracker-state"
        or not isinstance(restore.get("predecessor_artifact_created_at"), str)
        or not restore["predecessor_artifact_created_at"]
        or not re.fullmatch(
            r"sha256:[0-9a-f]{64}",
            str(restore.get("predecessor_artifact_api_digest", "")),
        )
        or restore.get("downloaded_zip_sha256")
            != str(restore.get("predecessor_artifact_api_digest", ""))[7:]
        or type(restore.get("predecessor_run_id")) is not int
        or restore["predecessor_run_id"] <= 0
        or type(restore.get("predecessor_run_attempt")) is not int
        or restore["predecessor_run_attempt"] <= 0
        or not re.fullmatch(r"[0-9a-f]{40}", str(restore.get("predecessor_head_sha", "")))
        or type(restore.get("predecessor_workflow_id")) is not int
        or restore["predecessor_workflow_id"] <= 0
        or restore.get("predecessor_workflow_file") != "legislative_trade_tracker_v2.yml"
        or restore.get("predecessor_workflow_name") != "Legislative purchase tracker v2"
    ):
        return False

    if action == "rolled_back":
        if (receipt.get("rollback_verified") is not True
                or not receipt.get("rollback_reason")
                or not all(item["matches_predecessor"] for item in files)
                or not no_outbound):
            return False
    elif (receipt.get("rollback_verified") is not False
          or receipt.get("rollback_reason") != ""):
        return False

    if action == "committed":
        if (receipt.get("validation_outcome") != "zero_change_successor"
                or receipt.get("candidate_state_sha256") != state_hash):
            return False
    elif receipt.get("validation_outcome") == "notification_eligible_rollback":
        if (eligible_count is None or eligible_count <= 0
                or receipt.get("candidate_state_sha256")
                    == receipt.get("predecessor_state_sha256")):
            return False
    elif receipt.get("validation_outcome") != "contained_failure":
        return False

    if require_run_provenance:
        expected_repository_id = os.environ.get("GITHUB_REPOSITORY_ID", "")
        expected_run_id = os.environ.get("GITHUB_RUN_ID", "")
        expected_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        expected_sha = os.environ.get("GITHUB_SHA", "")
        if (
            receipt.get("controlled_validation") is not True
            or receipt.get("trigger_source") != "workflow_dispatch"
            or not expected_repository_id.isdigit()
            or receipt.get("repository_id") != int(expected_repository_id)
            or receipt.get("repository") != os.environ.get("GITHUB_REPOSITORY", "")
            or not expected_run_id.isdigit()
            or receipt.get("run_id") != int(expected_run_id)
            or not expected_attempt.isdigit()
            or receipt.get("run_attempt") != int(expected_attempt)
            or not re.fullmatch(r"[0-9a-f]{40}", expected_sha)
            or receipt.get("consumer_sha") != expected_sha
            or restore.get("repository_id") != int(expected_repository_id)
            or restore.get("consumer_sha") != expected_sha
        ):
            return False
    return True


def durable_receipt(
    result: dict,
    receipt: dict,
    *,
    result_path: Path,
    state_path: Path,
    restore_receipt_path: Path | None = None,
    controlled_validation_receipt_path: Path | None = None,
    require_restore_receipt: bool = False,
    require_controlled_validation_receipt: bool = False,
    require_notifications_suppressed: bool = False,
    require_no_notification_eligible_records: bool = False,
    require_run_provenance: bool = False,
) -> bool:
    try:
        hashes_match = (
            receipt.get("result_sha256") == _sha256(result_path)
            and receipt.get("state_sha256") == _sha256(state_path)
        )
    except OSError:
        return False
    if require_restore_receipt:
        if restore_receipt_path is None:
            return False
        try:
            if receipt.get("restore_receipt_sha256") != _sha256(restore_receipt_path):
                return False
        except OSError:
            return False
    controlled_receipt = {}
    if require_controlled_validation_receipt:
        if controlled_validation_receipt_path is None:
            return False
        try:
            if (receipt.get("controlled_validation_receipt_sha256")
                    != _sha256(controlled_validation_receipt_path)):
                return False
            controlled_receipt = read_result(controlled_validation_receipt_path)
        except OSError:
            return False
    if not hashes_match:
        return False
    eligible_count = notification_eligible_new_records(result)
    delivery_count = notification_delivery_count(result)
    if (
        not _source_receipt_evidence(result, receipt, action="committed")
        or receipt.get("durable_state_eligible") is not True
        or receipt.get("protected_upload_eligible") is not True
        or receipt.get("validation_outcome") != "zero_change_successor"
        or eligible_count is None
        or delivery_count is None
        or (require_notifications_suppressed
            and receipt.get("notifications_suppressed") is not True)
        or (require_no_notification_eligible_records and eligible_count != 0)
        or (require_no_notification_eligible_records and delivery_count != 0)
    ):
        return False
    if require_no_notification_eligible_records:
        alerted = result.get("alerted_filing_counts")
        if not isinstance(alerted, dict):
            return False
        for source, status in result["source_statuses"].items():
            if status == "ok" and (type(alerted.get(source)) is not int
                                   or alerted[source] != 0):
                return False
    if require_controlled_validation_receipt:
        if restore_receipt_path is None or not controlled_validation_receipt(
            result,
            receipt,
            controlled_receipt,
            result_path=result_path,
            state_path=state_path,
            restore_receipt_path=restore_receipt_path,
            action="committed",
            require_run_provenance=require_run_provenance,
        ):
            return False
    return True


def protected_upload_receipt(
    result: dict,
    source_receipt: dict,
    controlled_receipt: dict,
    *,
    result_path: Path,
    state_path: Path,
    restore_receipt_path: Path,
    controlled_receipt_path: Path,
    require_run_provenance: bool = False,
) -> bool:
    try:
        hashes_match = (
            source_receipt.get("result_sha256") == _sha256(result_path)
            and source_receipt.get("state_sha256") == _sha256(state_path)
            and source_receipt.get("restore_receipt_sha256")
                == _sha256(restore_receipt_path)
            and source_receipt.get("controlled_validation_receipt_sha256")
                == _sha256(controlled_receipt_path)
        )
    except OSError:
        return False
    action = source_receipt.get("protected_state_action")
    if (
        not hashes_match
        or action not in {"committed", "rolled_back"}
        or source_receipt.get("protected_upload_eligible") is not True
        or source_receipt.get("notifications_suppressed") is not True
        or source_receipt.get("outbound_notifications_attempted") != 0
        or source_receipt.get("outbound_notifications_sent") != 0
        or controlled_receipt.get("no_outbound_attested") is not True
        or not _source_receipt_evidence(result, source_receipt, action=action)
        or not complete_state(read_result(state_path))
        or not controlled_validation_receipt(
            result,
            source_receipt,
            controlled_receipt,
            result_path=result_path,
            state_path=state_path,
            restore_receipt_path=restore_receipt_path,
            action=action,
            require_run_provenance=require_run_provenance,
        )
    ):
        return False
    if action == "committed":
        return (
            source_receipt.get("durable_state_eligible") is True
            and source_receipt.get("validation_outcome") == "zero_change_successor"
            and notification_eligible_new_records(result) == 0
            and notification_delivery_count(result) == 0
        )
    return (
        source_receipt.get("durable_state_eligible") is False
        and source_receipt.get("rollback_performed") is True
        and source_receipt.get("rollback_verified") is True
        and source_receipt.get("notifications_suppressed") is True
        and source_receipt.get("outbound_notifications_attempted") == 0
        and source_receipt.get("outbound_notifications_sent") == 0
        and source_receipt.get("validation_outcome") in {
            "notification_eligible_rollback", "contained_failure"
        }
    )


def terminal_classification(result: dict, job_status: str, tracker_outcome: str) -> str:
    if job_status == "success" and tracker_outcome == "success" and complete_result(result):
        return "legislative_complete"
    statuses = result.get("source_statuses", {})
    if isinstance(statuses, dict) and statuses.get("senate") == "blocked":
        return "senate_access_denied"
    if isinstance(statuses, dict) and statuses.get("senate") == "error":
        return "senate_source_error"
    if result.get("overall_status") == "degraded":
        return "legislative_discovery_incomplete"
    return "legislative_workflow_failed"


def signal_terminal(result: dict, *, base_url: str, job_status: str,
                    tracker_outcome: str, opener=None) -> bool:
    classification = terminal_classification(result, job_status, tracker_outcome)
    if not base_url:
        print("Healthchecks terminal ping: unconfigured")
        return False
    base_url = base_url.rstrip("/")
    for suffix in ("/start", "/fail"):
        if base_url.endswith(suffix):
            base_url = base_url[:-len(suffix)].rstrip("/")
    success = classification == "legislative_complete"
    try:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or any(ord(char) < 32 for char in base_url)):
            raise ValueError("invalid heartbeat URL")
        request = Request(base_url if success else base_url + "/fail",
                          data=classification.encode("ascii"), method="POST",
                          headers={"Content-Type": "text/plain"})
        opener = opener or build_opener(NoRedirect()).open
        # Exactly one terminal request; internal source retries have already ended.
        with opener(request, timeout=20) as response:
            accepted = 200 <= response.status < 300
            print(f"Healthchecks {'success' if success else 'failure'} ping: "
                  f"HTTP {response.status}; classification={classification}")
            return accepted
    except (URLError, OSError, ValueError):
        print(f"Healthchecks terminal delivery failed; classification={classification}")
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=Path("legislative-result.json"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--validate-durable", action="store_true")
    parser.add_argument("--validate-protected-upload", action="store_true")
    parser.add_argument("--discovery-only", action="store_true")
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("STATE_FILE", ".trade-tracker/legislative/state.json")),
    )
    parser.add_argument(
        "--source-status",
        type=Path,
        default=Path(os.environ.get("SOURCE_STATUS_FILE", "legislative-source-status.json")),
    )
    parser.add_argument(
        "--restore-receipt",
        type=Path,
        default=Path(
            os.environ.get(
                "RESTORE_RECEIPT_FILE",
                ".trade-tracker/legislative/restore-receipt.json",
            )
        ),
    )
    parser.add_argument("--require-restore-receipt", action="store_true")
    parser.add_argument(
        "--controlled-validation-receipt",
        type=Path,
        default=Path(
            os.environ.get(
                "CONTROLLED_VALIDATION_RECEIPT_FILE",
                ".trade-tracker/legislative/controlled-validation-receipt.json",
            )
        ),
    )
    parser.add_argument("--require-controlled-validation-receipt", action="store_true")
    parser.add_argument("--require-notifications-suppressed", action="store_true")
    parser.add_argument("--require-no-notification-eligible-records", action="store_true")
    parser.add_argument("--require-run-provenance", action="store_true")
    args = parser.parse_args(argv)
    if sum((args.validate_only, args.validate_durable,
            args.validate_protected_upload, args.discovery_only)) > 1:
        parser.error("choose only one validation mode")
    result = read_result(args.result)
    if args.discovery_only:
        return 0 if complete_catalogs(result) else 1
    if args.validate_durable:
        state = read_result(args.state)
        receipt = read_result(args.source_status)
        valid = (
            durable_result(result)
            and complete_state(state)
            and durable_receipt(
                result,
                receipt,
                result_path=args.result,
                state_path=args.state,
                restore_receipt_path=args.restore_receipt,
                controlled_validation_receipt_path=args.controlled_validation_receipt,
                require_restore_receipt=args.require_restore_receipt,
                require_controlled_validation_receipt=(
                    args.require_controlled_validation_receipt
                ),
                require_notifications_suppressed=args.require_notifications_suppressed,
                require_no_notification_eligible_records=(
                    args.require_no_notification_eligible_records
                ),
                require_run_provenance=args.require_run_provenance,
            )
        )
        print("Legislative durable-state validation: " + ("pass" if valid else "fail"))
        return 0 if valid else 1
    if args.validate_protected_upload:
        source_receipt = read_result(args.source_status)
        controlled_receipt = read_result(args.controlled_validation_receipt)
        valid = protected_upload_receipt(
            result,
            source_receipt,
            controlled_receipt,
            result_path=args.result,
            state_path=args.state,
            restore_receipt_path=args.restore_receipt,
            controlled_receipt_path=args.controlled_validation_receipt,
            require_run_provenance=args.require_run_provenance,
        )
        print("Legislative protected-state upload validation: "
              + ("pass" if valid else "fail"))
        return 0 if valid else 1
    if args.validate_only:
        valid = complete_result(result)
        print("Legislative complete-source validation: " + ("pass" if valid else "fail"))
        return 0 if valid else 1
    accepted = signal_terminal(result, base_url=os.environ.get("HEALTHCHECKS_PING_URL", ""),
                               job_status=os.environ.get("JOB_STATUS", "failure"),
                               tracker_outcome=os.environ.get("TRACKER_OUTCOME", "failure"))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
