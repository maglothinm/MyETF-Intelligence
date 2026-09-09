"""Durable per-record delivery, independent of producer success and retries."""
from __future__ import annotations

import json
import smtplib
import time
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Callable, Mapping

from scripts.runtime_notifications import CONTRACT, validate_intent


class DeliveryRejected(RuntimeError):
    """The transport established that no submission was accepted."""


def _event(cursor: Any, delivery_id: str, event_type: str, details: Mapping[str, Any] | None = None) -> None:
    cursor.execute(
        "INSERT INTO runtime_notification_events (event_id, delivery_id, event_type, details) "
        "VALUES (%s::uuid, %s, %s, %s::jsonb)",
        (str(uuid.uuid4()), delivery_id, event_type, json.dumps(dict(details or {}), sort_keys=True)),
    )


@contextmanager
def _transaction(connection: Any):
    previous = connection.autocommit
    if not previous:
        raise RuntimeError("delivery transaction must be outside the snapshot transaction")
    connection.autocommit = False
    try:
        with closing(connection.cursor()) as cursor:
            yield cursor
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.autocommit = previous


def _known_no_delivery(run: Mapping[str, Any]) -> dict[str, Any] | None:
    if run.get("status") == "failure" and run.get("side_effects_possible") is False:
        return {"basis": "original_run_records_no_possible_side_effects"}
    # A pinned incident proof resolves only this exact original row; inability
    # to load it becomes a delivery hold, never a producer liveness barrier.
    try:
        from .legislative_recovery import CASE, RECEIPT_SHA256, load_receipt

        receipt = load_receipt(CASE)
        if dict(run) == receipt["failed_run"]:
            return {"basis": "immutable_execution_and_image_without_delivery_credentials", "case": CASE, "receipt_sha256": RECEIPT_SHA256}
    except (OSError, ValueError, RuntimeError):
        pass
    return None


def prepare_legacy_fences(connection: Any, namespace: str) -> None:
    """Under the namespace lock, retain legacy uncertainty without stopping work."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(
            "SELECT to_jsonb(r) FROM runtime_job_runs r "
            "JOIN runtime_state_heads h ON h.namespace = r.namespace "
            "WHERE r.namespace = %s AND r.runtime_mode = 'production' "
            "AND r.status IN ('failure', 'running') AND r.started_at > h.updated_at "
            "AND COALESCE(r.runtime_mode_evidence ->> 'notification_contract', '') <> %s "
            "ORDER BY r.started_at, r.run_id",
            (namespace, CONTRACT),
        )
        runs = [row[0] for row in cursor.fetchall()]
        for run in runs:
            proof = _known_no_delivery(run)
            cutoff = run.get("finished_at") or datetime.now(timezone.utc).isoformat()
            evidence = {"original_run": run, **(proof or {"basis": "legacy_delivery_record_scope_unavailable"})}
            cursor.execute(
                "INSERT INTO runtime_notification_legacy_fences "
                "(failed_run_id, namespace, cutoff_at, finding, evidence) "
                "VALUES (%s::uuid, %s, %s::timestamptz, %s, %s::jsonb) "
                "ON CONFLICT (failed_run_id) DO NOTHING",
                (run["run_id"], namespace, cutoff, "no_delivery" if proof else "unresolved", json.dumps(evidence, sort_keys=True)),
            )


def enqueue_in_snapshot_transaction(cursor: Any, namespace: str, snapshot_id: str, run_id: str, intents: list[dict[str, Any]]) -> None:
    """Called ONLY inside the existing snapshot/head/run commit transaction."""
    if not intents:
        return
    cursor.execute(
        "SELECT failed_run_id::text, cutoff_at FROM runtime_notification_legacy_fences "
        "WHERE namespace = %s AND finding = 'unresolved' ORDER BY cutoff_at",
        (namespace,),
    )
    fences = cursor.fetchall()
    for raw in intents:
        intent = validate_intent(raw, namespace)
        # Date-only official filings on the uncertain attempt's date, and unknown
        # dates, cannot prove that an old unretained attempt never saw the record.
        # Hold those records individually; subsequent official filing dates pass.
        held_by = [str(row[0]) for row in fences if intent["available_on"] is None or intent["available_on"] <= row[1].astimezone(timezone.utc).date().isoformat()]
        status = "legacy_held" if held_by else "pending"
        cursor.execute(
            "INSERT INTO runtime_notification_deliveries "
            "(delivery_id, namespace, channel, record_key, available_on, payload, snapshot_id, producer_run_id, status, legacy_run_ids) "
            "VALUES (%s, %s, %s, %s, %s::date, %s::jsonb, %s::uuid, %s::uuid, %s, %s::jsonb) "
            "ON CONFLICT (delivery_id) DO NOTHING RETURNING delivery_id",
            (intent["delivery_id"], namespace, intent["channel"], intent["record_key"], intent["available_on"], json.dumps(intent["payload"], sort_keys=True), snapshot_id, run_id, status, json.dumps(held_by)),
        )
        inserted = cursor.fetchone()
        if inserted:
            _event(cursor, str(inserted[0]), status, {"producer_run_id": run_id, "snapshot_id": snapshot_id, "legacy_run_ids": held_by})


def configured_channels(environment: Mapping[str, str]) -> list[str]:
    pairs = {"pushover": ("PUSHOVER_API_TOKEN", "PUSHOVER_USER_KEY"), "gmail": ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")}
    return [channel for channel, keys in pairs.items() if all(str(environment.get(key) or "").strip() for key in keys)]


def send_notification(channel: str, payload: Mapping[str, str], environment: Mapping[str, str]) -> bool:
    """Only fixed existing provider endpoints; no credentials enter the journal."""
    if channel == "pushover":
        import requests

        response = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": environment["PUSHOVER_API_TOKEN"], "user": environment["PUSHOVER_USER_KEY"], **payload, "priority": "0"},
            timeout=(15, 30),
        )
        # An explicit application rejection establishes no acceptance. Transport
        # exceptions, malformed responses and ambiguous HTTP errors remain unknown.
        data = response.json()
        if isinstance(data, dict) and data.get("status") == 0:
            raise DeliveryRejected("pushover_rejected")
        response.raise_for_status()
        return isinstance(data, dict) and data.get("status") == 1
    if channel != "gmail":
        raise ValueError("unknown delivery channel")
    address = environment["GMAIL_ADDRESS"]
    message = EmailMessage()
    message["Subject"] = payload["title"]
    message["From"] = address
    message["To"] = address
    message.set_content(payload["message"])
    submission_possible = False
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(address, environment["GMAIL_APP_PASSWORD"])
            submission_possible = True
            refused = server.send_message(message)
            if refused:
                raise DeliveryRejected("gmail_recipient_rejected")
    except DeliveryRejected:
        raise
    except Exception as exc:
        if not submission_possible:
            raise DeliveryRejected("gmail_not_submitted") from None
        raise RuntimeError("gmail_acceptance_unknown") from None
    return True


class NotificationDispatcher:
    """Invoked after snapshot commit while the producer's namespace lock is held."""

    def __init__(self, connection: Any, namespace: str, environment: Mapping[str, str], *, send: Callable | None = None):
        self.connection = connection
        self.namespace = namespace
        self.environment = environment
        self.send = send or send_notification

    def _recover_interrupted_claims(self) -> None:
        with _transaction(self.connection) as cursor:
            cursor.execute(
                "UPDATE runtime_notification_deliveries SET status = 'uncertain', completed_at = now(), error_code = 'interrupted_delivery' "
                "WHERE namespace = %s AND status = 'sending' RETURNING delivery_id",
                (self.namespace,),
            )
            for row in cursor.fetchall():
                _event(cursor, str(row[0]), "uncertain", {"error_code": "interrupted_delivery"})

    def _claim(self, delivery_id: str) -> tuple | None:
        with _transaction(self.connection) as cursor:
            cursor.execute(
                "UPDATE runtime_notification_deliveries SET status = 'sending', attempted_at = now() "
                "WHERE delivery_id = %s AND namespace = %s AND status = 'pending' "
                "RETURNING channel, payload",
                (delivery_id, self.namespace),
            )
            row = cursor.fetchone()
            if row:
                _event(cursor, delivery_id, "sending")
            return row

    def _finish(self, delivery_id: str, status: str, error_code: str = "") -> None:
        with _transaction(self.connection) as cursor:
            cursor.execute(
                "UPDATE runtime_notification_deliveries SET status = %s, completed_at = now(), error_code = %s "
                "WHERE delivery_id = %s AND namespace = %s AND status = 'sending' RETURNING delivery_id",
                (status, error_code[:160], delivery_id, self.namespace),
            )
            if cursor.fetchone() is None:
                raise RuntimeError("delivery claim changed before completion")
            _event(cursor, delivery_id, status, {"error_code": error_code[:160]})

    def dispatch(self, *, limit: int = 20, budget_seconds: float = 60) -> dict[str, int]:
        counts = {"accepted": 0, "uncertain": 0, "rejected": 0}
        self._recover_interrupted_claims()
        channels = configured_channels(self.environment)
        if not channels:
            return counts
        with closing(self.connection.cursor()) as cursor:
            cursor.execute(
                "SELECT delivery_id FROM runtime_notification_deliveries "
                "WHERE namespace = %s AND status = 'pending' AND channel = ANY(%s) "
                "ORDER BY queued_at, delivery_id LIMIT %s",
                (self.namespace, channels, min(max(int(limit), 0), 100)),
            )
            pending = [str(row[0]) for row in cursor.fetchall()]
        started = time.monotonic()
        for key in pending:
            if time.monotonic() - started >= budget_seconds:
                break
            claimed = self._claim(key)
            if claimed is None:
                continue
            channel, payload = claimed
            # The sending claim/event have COMMITTED before this external call.
            status, error = "uncertain", "acceptance_not_confirmed"
            try:
                if self.send(channel, payload, self.environment):
                    status, error = "accepted", ""
            except DeliveryRejected:
                status, error = "rejected", "provider_rejected_before_acceptance"
            except Exception as exc:
                error = type(exc).__name__
            self._finish(key, status, error)
            counts[status] += 1
        return counts


def notification_status(connection: Any) -> dict[str, Any]:
    with closing(connection.cursor()) as cursor:
        cursor.execute("SELECT namespace, status, count(*) FROM runtime_notification_deliveries GROUP BY namespace, status ORDER BY namespace, status")
        counts = [{"namespace":r[0], "status":r[1], "count":int(r[2])} for r in cursor.fetchall()]
        cursor.execute("SELECT failed_run_id::text, namespace, cutoff_at, finding FROM runtime_notification_legacy_fences ORDER BY recorded_at")
        fences = [{"failed_run_id":r[0], "namespace":r[1], "cutoff_at":r[2].isoformat(), "finding":r[3]} for r in cursor.fetchall()]
        cursor.execute("SELECT delivery_id, namespace, channel, status, record_key, legacy_run_ids, error_code FROM runtime_notification_deliveries WHERE status IN ('uncertain','rejected','legacy_held','sending') ORDER BY queued_at DESC LIMIT 100")
        held = [dict(zip(('delivery_id','namespace','channel','status','record_key','legacy_run_ids','error_code'), row)) for row in cursor.fetchall()]
    return {"contract": CONTRACT, "counts": counts, "legacy_fences": fences, "held_deliveries": held}
