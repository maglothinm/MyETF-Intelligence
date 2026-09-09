"""Explicit, reviewed recovery of one credential-free Legislative failure.

This is not a general guard override. The original run is never edited, and the
case becomes ineligible as soon as another run starts or its accepted head moves.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import closing
from pathlib import Path
from typing import Any

from .store import LockedNamespace, StateStoreError


CASE = "legislative-20260908-no-delivery"
RECEIPT_SHA256 = "778865518665e1447907b2d51b643b80cc89afed00c955a4c2f30f3e44583fb0"
RECEIPT_PATH = Path(__file__).resolve().parents[1] / "config" / "runtime-retry-adjudications" / (CASE + ".json")


def load_receipt(case: str) -> dict[str, Any]:
    if case != CASE:
        raise StateStoreError("unknown reviewed Legislative recovery case")
    try:
        raw = RECEIPT_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != RECEIPT_SHA256:
            raise StateStoreError("Legislative recovery evidence digest mismatch")
        return json.loads(raw)
    except (OSError, ValueError) as exc:
        raise StateStoreError("Legislative recovery evidence is unreadable") from exc


def assert_adjudicated_retry_safe(locked: LockedNamespace, case: str) -> dict[str, Any]:
    receipt = load_receipt(case)
    if locked.namespace != "legislative":
        raise StateStoreError("Legislative recovery cannot authorize another namespace")
    head = locked.head()
    expected = receipt["accepted_parent"]
    if head is None or any(
        getattr(head, field) != expected[field]
        for field in ("namespace", "generation", "snapshot_id", "snapshot_sha256")
    ):
        raise StateStoreError("Legislative recovery parent changed")
    with closing(locked.connection.cursor()) as cursor:
        # Check every run since the parent, not just the most recent failure.
        # The held namespace advisory lock prevents a competing producer start.
        cursor.execute(
            "SELECT to_jsonb(r) FROM runtime_job_runs r "
            "JOIN runtime_state_heads h ON h.namespace = r.namespace "
            "WHERE r.namespace = %s AND r.started_at > h.updated_at "
            "ORDER BY r.started_at, r.run_id",
            (locked.namespace,),
        )
        runs = [row[0] for row in cursor.fetchall()]
    if runs != [receipt["failed_run"]]:
        raise StateStoreError("Legislative recovery run inventory changed")
    return {
        "case": case,
        "receipt_sha256": RECEIPT_SHA256,
        "failed_run_id": receipt["failed_run"]["run_id"],
        "parent_sha256": expected["snapshot_sha256"],
        "finding": "delivery_impossible_without_credentials",
        "original_failed_run_preserved": True,
    }
