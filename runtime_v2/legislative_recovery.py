"""Immutable no-delivery evidence for one original Legislative failed run.

This receipt can resolve legacy notification uncertainty. Collection liveness
does not depend on this case, its parent generation, or receipt availability.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .store import StateStoreError


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
