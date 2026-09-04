#!/usr/bin/env python3
"""Validate the AI analyst's explicit state-publication decision.

This is the workflow boundary between an analyst process and the protected
``ai-analysis-state`` artifact.  It binds the result to the current repository,
run attempt, and source revision, then emits ``state_publishable`` only for a
coherent success or degraded result with a successful-state marker.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

REPOSITORY_ID = 1349678672
SHA_RE = re.compile(r"[0-9a-f]{40}")


class PublicationError(RuntimeError):
    """The analyst result cannot control protected-state publication."""


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PublicationError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"{label} is not a JSON object")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise PublicationError(f"{label} is invalid")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PublicationError(f"{label} is invalid") from exc
    if number < 0:
        raise PublicationError(f"{label} is invalid")
    return number


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise PublicationError(f"{label} is not boolean")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PublicationError(f"{label} is not a list")
    return value


def validate_publication(
    result: Mapping[str, Any],
    *,
    state: Mapping[str, Any] | None,
    repository_id: int,
    run_id: str,
    run_attempt: str,
    source_revision: str,
) -> tuple[str, bool]:
    if result.get("result_schema_version") != 2:
        raise PublicationError("result schema version mismatch")
    if repository_id != REPOSITORY_ID:
        raise PublicationError("canonical repository identity mismatch")
    if result.get("repository_id") != REPOSITORY_ID:
        raise PublicationError("result repository identity mismatch")
    if str(result.get("workflow_run_id") or "") != str(run_id):
        raise PublicationError("result workflow run mismatch")
    if str(result.get("workflow_run_attempt") or "") != str(run_attempt):
        raise PublicationError("result workflow attempt mismatch")
    if not SHA_RE.fullmatch(source_revision):
        raise PublicationError("source revision is invalid")
    if result.get("source_revision") != source_revision:
        raise PublicationError("result source revision mismatch")

    status = str(result.get("run_status") or "")
    publishable = _bool(result.get("state_publishable"), "state_publishable")
    success = _bool(result.get("success"), "success")
    fatal_errors = _list(result.get("fatal_errors"), "fatal_errors")
    deferred = _list(result.get("deferred_candidates"), "deferred_candidates")
    errors = _list(result.get("errors"), "errors")
    delivery_started = _bool(
        result.get("delivery_phase_started"), "delivery_phase_started"
    )
    delivery_attempts = _nonnegative_int(
        result.get("delivery_attempt_count"), "delivery_attempt_count"
    )
    delivery_confirmed = _nonnegative_int(
        result.get("delivery_confirmed_count"), "delivery_confirmed_count"
    )
    delivery_uncertain = _nonnegative_int(
        result.get("delivery_uncertain_count"), "delivery_uncertain_count"
    )
    if delivery_confirmed > delivery_attempts:
        raise PublicationError("confirmed delivery count exceeds attempts")
    if delivery_uncertain > delivery_attempts:
        raise PublicationError("uncertain delivery count exceeds attempts")
    if delivery_confirmed + delivery_uncertain != delivery_attempts:
        raise PublicationError("terminal delivery outcomes do not match attempts")
    if not delivery_started and any(
        (delivery_attempts, delivery_confirmed, delivery_uncertain)
    ):
        raise PublicationError("delivery counts exist before delivery phase")
    if delivery_started and delivery_attempts == 0:
        raise PublicationError("delivery phase has no recorded attempt")
    if list(fatal_errors) != list(errors):
        raise PublicationError("fatal_errors does not match errors")

    if status == "success":
        if not publishable or not success or fatal_errors or deferred:
            raise PublicationError("success result has inconsistent outcome fields")
    elif status == "degraded":
        if not publishable or not success or fatal_errors or not deferred:
            raise PublicationError("degraded result has inconsistent outcome fields")
    elif status == "fatal":
        if publishable or success or not fatal_errors:
            raise PublicationError("fatal result has inconsistent outcome fields")
    else:
        raise PublicationError("run_status is not terminal")

    if publishable:
        if state is None:
            raise PublicationError("publishable result has no state.json")
        marker = state.get("last_success_utc")
        if not isinstance(marker, str) or not marker:
            raise PublicationError("publishable state has no successful-state marker")
        if marker != result.get("finished_utc"):
            raise PublicationError("state marker does not match result completion")
        if delivery_uncertain:
            raise PublicationError("state with uncertain delivery is not publishable")
    return status, publishable


def _write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--repository-id", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument(
        "--analyst-outcome", choices=("success", "failure", "cancelled", "skipped"), required=True
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.result.is_file():
        if args.analyst_outcome == "success":
            print("AI publication refused: analyst succeeded without a result file")
            return 1
        _write_output("state_publishable", "false")
        _write_output("run_status", "missing_result")
        print("AI publication disabled: analyst failed before producing a result file")
        return 0
    try:
        result = _read_object(args.result, "analyst result")
        state = _read_object(args.state, "AI state") if args.state.is_file() else None
        status, publishable = validate_publication(
            result,
            state=state,
            repository_id=args.repository_id,
            run_id=args.run_id,
            run_attempt=args.run_attempt,
            source_revision=args.source_revision,
        )
        if args.analyst_outcome == "success" and not publishable:
            raise PublicationError("successful analyst process marked state non-publishable")
        if args.analyst_outcome != "success" and publishable:
            raise PublicationError("failed analyst process marked state publishable")
    except PublicationError as exc:
        print(f"AI publication refused: {exc}")
        return 1
    _write_output("state_publishable", str(publishable).lower())
    _write_output("run_status", status)
    print(
        "Validated AI publication decision: "
        f"status={status} publishable={str(publishable).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
