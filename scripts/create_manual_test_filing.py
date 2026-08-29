#!/usr/bin/env python3
"""Create an isolated dashboard artifact containing one synthetic test filing.

The source tracker artifacts are treated as immutable.  Each supplied artifact is
copied into a fresh output tree, then one historical processed filing and its
associated transaction records are cloned with TEST-prefixed identifiers.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import secrets
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


FILINGS_FILE = "filings.jsonl"
TRANSACTIONS_FILE = "transactions.jsonl"
PURCHASES_FILE = "purchases.jsonl"
MANIFEST_FILE = "manual-test.json"
STATE_FILE = "state.json"
BRANCH_NAMES = ("legislative", "executive")


class ManualTestError(RuntimeError):
    """Raised when a safe synthetic test artifact cannot be produced."""


@dataclass(frozen=True)
class Candidate:
    branch: str
    source_dir: Path
    filing: dict[str, Any]
    transactions: tuple[dict[str, Any], ...]
    purchases: tuple[dict[str, Any], ...]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ManualTestError(f"Unable to read tracker artifact {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ManualTestError(
                f"Invalid JSONL in {path} at line {line_number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ManualTestError(
                f"Invalid JSONL in {path} at line {line_number}: expected an object"
            )
        records.append(value)
    return records


def _latest_by(records: Iterable[dict[str, Any]], key_field: str) -> list[dict[str, Any]]:
    keyed: dict[str, dict[str, Any]] = {}
    unkeyed: list[dict[str, Any]] = []
    for record in records:
        key = str(record.get(key_field) or "")
        if key:
            keyed[key] = record
        else:
            unkeyed.append(record)
    return [*keyed.values(), *unkeyed]


def _historical_date(value: object, as_of: date) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        return date.fromisoformat(raw[:10]) < as_of
    except ValueError:
        return False


def _is_synthetic(record: Mapping[str, Any]) -> bool:
    return bool(
        record.get("is_synthetic_test")
        or record.get("synthetic_test")
        or record.get("test_metadata")
    )


def _related_rows(
    rows: Iterable[dict[str, Any]], *, source: str, report_id: str
) -> list[dict[str, Any]]:
    matching = (
        row
        for row in rows
        if str(row.get("source") or "").casefold() == source.casefold()
        and str(row.get("report_id") or "") == report_id
        and not _is_synthetic(row)
    )
    return _latest_by(matching, "trade_id")


def find_candidates(
    inputs: Mapping[str, Path], *, as_of: date
) -> list[Candidate]:
    candidates: list[Candidate] = []
    for branch, source_dir in inputs.items():
        filings = _latest_by(_read_jsonl(source_dir / FILINGS_FILE), "filing_key")
        transactions = _read_jsonl(source_dir / TRANSACTIONS_FILE)
        purchases = _read_jsonl(source_dir / PURCHASES_FILE)
        for filing in filings:
            if str(filing.get("status") or "").casefold() != "processed":
                continue
            if _is_synthetic(filing) or not _historical_date(filing.get("filed_date"), as_of):
                continue
            source = str(filing.get("source") or "").strip()
            report_id = str(filing.get("report_id") or "").strip()
            filing_key = str(filing.get("filing_key") or "").strip()
            if not source or not report_id or not filing_key:
                continue
            related_transactions = _related_rows(
                transactions, source=source, report_id=report_id
            )
            related_purchases = _related_rows(
                purchases, source=source, report_id=report_id
            )
            if not related_transactions and not related_purchases:
                continue
            candidates.append(
                Candidate(
                    branch=branch,
                    source_dir=source_dir,
                    filing=filing,
                    transactions=tuple(related_transactions),
                    purchases=tuple(related_purchases),
                )
            )
    return candidates


def _row_identity(row: Mapping[str, Any]) -> str:
    trade_id = str(row.get("trade_id") or "")
    if trade_id:
        return f"trade_id:{trade_id}"
    encoded = json.dumps(dict(row), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _timestamp_for_date(as_of: date, now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc).replace(microsecond=0)
    return datetime.combine(as_of, now.timetz(), tzinfo=timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _validate_paths(inputs: Mapping[str, Path], output_dir: Path) -> None:
    if not inputs:
        raise ManualTestError(
            "At least one restored tracker directory is required: "
            "--legislative-dir and/or --executive-dir"
        )
    resolved_inputs: dict[str, Path] = {}
    for branch, source_dir in inputs.items():
        resolved = source_dir.resolve()
        if not resolved.is_dir():
            raise ManualTestError(f"{branch.title()} tracker directory does not exist: {source_dir}")
        if not (resolved / FILINGS_FILE).is_file():
            raise ManualTestError(
                f"{branch.title()} tracker directory has no {FILINGS_FILE}: {source_dir}"
            )
        if not (resolved / STATE_FILE).is_file():
            raise ManualTestError(
                f"{branch.title()} tracker directory has no {STATE_FILE}: {source_dir}"
            )
        resolved_inputs[branch] = resolved
    if len(set(resolved_inputs.values())) != len(resolved_inputs):
        raise ManualTestError("Legislative and executive inputs must be different directories")

    resolved_output = output_dir.resolve()
    for branch, resolved_input in resolved_inputs.items():
        if _paths_overlap(resolved_input, resolved_output):
            raise ManualTestError(
                f"Output directory must be isolated from the {branch} source directory: "
                f"{output_dir}"
            )
    if output_dir.exists():
        if not output_dir.is_dir():
            raise ManualTestError(f"Output path is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise ManualTestError(
                f"Output directory must be absent or empty to prevent accidental overwrite: {output_dir}"
            )


def _all_existing_ids(inputs: Mapping[str, Path]) -> tuple[set[str], set[str], set[str]]:
    report_ids: set[str] = set()
    filing_keys: set[str] = set()
    trade_ids: set[str] = set()
    for source_dir in inputs.values():
        for row in _read_jsonl(source_dir / FILINGS_FILE):
            report_ids.add(str(row.get("report_id") or ""))
            filing_keys.add(str(row.get("filing_key") or ""))
        for filename in (TRANSACTIONS_FILE, PURCHASES_FILE):
            for row in _read_jsonl(source_dir / filename):
                trade_ids.add(str(row.get("trade_id") or ""))
    return report_ids, filing_keys, trade_ids


def _allocate_ids(
    *,
    candidate: Candidate,
    as_of: date,
    row_identities: Sequence[str],
    existing_ids: tuple[set[str], set[str], set[str]],
    token_factory: Callable[[], str],
) -> tuple[str, str, dict[str, str], str]:
    existing_reports, existing_filings, existing_trades = existing_ids
    source = str(candidate.filing["source"]).upper()
    date_token = as_of.strftime("%Y%m%d")
    for _attempt in range(10):
        token = "".join(character for character in token_factory() if character.isalnum())
        if not token:
            continue
        run_id = f"TEST-{date_token}-{token}"
        report_id = f"{run_id}-REPORT"
        filing_key = f"TEST-{source}-{date_token}-{token}"
        trade_ids = {
            identity: f"{run_id}-TRADE-{index:03d}"
            for index, identity in enumerate(row_identities, start=1)
        }
        if (
            report_id not in existing_reports
            and filing_key not in existing_filings
            and not existing_trades.intersection(trade_ids.values())
        ):
            return report_id, filing_key, trade_ids, run_id
    raise ManualTestError("Unable to allocate unique TEST identifiers after 10 attempts")


def _clone_trade(
    row: Mapping[str, Any],
    *,
    new_report_id: str,
    new_trade_id: str,
    as_of: date,
    observed_at_utc: str,
    base_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    cloned = copy.deepcopy(dict(row))
    original_trade_id = str(row.get("trade_id") or "")
    cloned.update(
        {
            "trade_id": new_trade_id,
            "report_id": new_report_id,
            "filed_date": as_of.isoformat(),
            "observed_at_utc": observed_at_utc,
            "is_synthetic_test": True,
            "is_temporary": True,
            "test_metadata": {
                **base_metadata,
                "original_trade_id": original_trade_id,
            },
        }
    )
    return cloned


def _append_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = list(rows)
    if not materialized:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = False
    if path.exists() and path.stat().st_size:
        with path.open("rb") as handle:
            handle.seek(-1, 2)
            needs_separator = handle.read(1) not in {b"\n", b"\r"}
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        if needs_separator:
            handle.write("\n")
        for row in materialized:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def _mark_test_ids_seen(
    state_path: Path,
    *,
    source: str,
    report_id: str,
    trade_ids: Sequence[str],
    observed_at_utc: str,
    test_metadata: Mapping[str, Any],
) -> None:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManualTestError(f"Unable to update copied tracker state {state_path}: {exc}") from exc
    if not isinstance(state, dict):
        raise ManualTestError(f"Copied tracker state is not a JSON object: {state_path}")
    seen_filings = state.setdefault("seen_filings", {})
    seen_trades = state.setdefault("seen_trades", {})
    if not isinstance(seen_filings, dict) or not isinstance(seen_trades, dict):
        raise ManualTestError(f"Copied tracker state has invalid seen-ID fields: {state_path}")
    source_filings = seen_filings.setdefault(source, {})
    if not isinstance(source_filings, dict):
        raise ManualTestError(
            f"Copied tracker state has invalid seen_filings.{source}: {state_path}"
        )
    source_filings[report_id] = observed_at_utc
    for trade_id in trade_ids:
        seen_trades[trade_id] = observed_at_utc
    state["manual_test"] = {
        **dict(test_metadata),
        "synthetic": True,
        "notifications_sent": False,
    }
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_output_tree(
    *,
    inputs: Mapping[str, Path],
    output_dir: Path,
    candidate: Candidate,
    filing: Mapping[str, Any],
    transactions: Sequence[Mapping[str, Any]],
    purchases: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    source: str,
    report_id: str,
    trade_ids: Sequence[str],
    observed_at_utc: str,
    test_metadata: Mapping[str, Any],
) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.manual-test-", dir=output_dir.parent)
    )
    try:
        for branch, source_dir in inputs.items():
            shutil.copytree(source_dir, staging / branch)
        selected_dir = staging / candidate.branch
        _append_jsonl(selected_dir / FILINGS_FILE, (filing,))
        _append_jsonl(selected_dir / TRANSACTIONS_FILE, transactions)
        _append_jsonl(selected_dir / PURCHASES_FILE, purchases)
        _mark_test_ids_seen(
            selected_dir / STATE_FILE,
            source=source,
            report_id=report_id,
            trade_ids=trade_ids,
            observed_at_utc=observed_at_utc,
            test_metadata=test_metadata,
        )
        (staging / MANIFEST_FILE).write_text(
            json.dumps(dict(manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            output_dir.rmdir()  # Validation guarantees it is empty.
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def generate_manual_test(
    *,
    legislative_dir: Path | None,
    executive_dir: Path | None,
    output_dir: Path,
    as_of: date,
    chooser: Callable[[Sequence[Candidate]], Candidate] = secrets.choice,
    token_factory: Callable[[], str] = lambda: secrets.token_hex(12),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Generate one isolated synthetic filing and return its manifest."""

    inputs = {
        branch: path
        for branch, path in (
            ("legislative", legislative_dir),
            ("executive", executive_dir),
        )
        if path is not None
    }
    _validate_paths(inputs, output_dir)
    candidates = find_candidates(inputs, as_of=as_of)
    if not candidates:
        supplied = ", ".join(f"{branch}={path}" for branch, path in inputs.items())
        raise ManualTestError(
            "No eligible historical processed filing with associated transaction data "
            f"was found before {as_of.isoformat()} in: {supplied}"
        )

    candidate = chooser(candidates)
    all_rows = [*candidate.transactions, *candidate.purchases]
    row_identities = list(dict.fromkeys(_row_identity(row) for row in all_rows))
    report_id, filing_key, trade_ids, run_id = _allocate_ids(
        candidate=candidate,
        as_of=as_of,
        row_identities=row_identities,
        existing_ids=_all_existing_ids(inputs),
        token_factory=token_factory,
    )
    generated_at = _timestamp_for_date(as_of, now or datetime.now(timezone.utc))
    original_filing = candidate.filing
    original_report_id = str(original_filing["report_id"])
    original_filing_key = str(original_filing["filing_key"])
    base_metadata = {
        "kind": "manual_test_filing",
        "temporary": True,
        "generated_at_utc": generated_at,
        "as_of_date": as_of.isoformat(),
        "run_id": run_id,
        "original_branch": candidate.branch,
        "original_source": str(original_filing.get("source") or ""),
        "original_report_id": original_report_id,
        "original_filing_key": original_filing_key,
    }

    cloned_transactions = [
        _clone_trade(
            row,
            new_report_id=report_id,
            new_trade_id=trade_ids[_row_identity(row)],
            as_of=as_of,
            observed_at_utc=generated_at,
            base_metadata=base_metadata,
        )
        for row in candidate.transactions
    ]
    cloned_purchases = [
        _clone_trade(
            row,
            new_report_id=report_id,
            new_trade_id=trade_ids[_row_identity(row)],
            as_of=as_of,
            observed_at_utc=generated_at,
            base_metadata=base_metadata,
        )
        for row in candidate.purchases
    ]

    unique_rows = {
        _row_identity(row): row for row in [*candidate.transactions, *candidate.purchases]
    }
    transaction_types = [str(row.get("transaction_type") or "") for row in unique_rows.values()]
    cloned_filing = copy.deepcopy(original_filing)
    cloned_filing.update(
        {
            "filing_key": filing_key,
            "report_id": report_id,
            "filed_date": as_of.isoformat(),
            "first_seen_utc": generated_at,
            "updated_at_utc": generated_at,
            "status": "processed",
            "transaction_count": len(unique_rows),
            "purchase_count": sum(value == "Purchase" for value in transaction_types),
            "sale_count": sum(value.startswith("Sale") for value in transaction_types),
            "exchange_count": sum(value == "Exchange" for value in transaction_types),
            "is_synthetic_test": True,
            "is_temporary": True,
            "test_metadata": base_metadata,
        }
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "polititrack_manual_test",
        "synthetic": True,
        "temporary": True,
        "notifications_sent": False,
        "generated_at_utc": generated_at,
        "as_of_date": as_of.isoformat(),
        "run_id": run_id,
        "selected_branch": candidate.branch,
        "selected_source": str(original_filing.get("source") or ""),
        "original_report_id": original_report_id,
        "original_filing_key": original_filing_key,
        "test_report_id": report_id,
        "test_filing_key": filing_key,
        "test_trade_ids": list(trade_ids.values()),
        "cloned_transaction_rows": len(cloned_transactions),
        "cloned_purchase_rows": len(cloned_purchases),
        "output_dir": str(output_dir.resolve()),
    }
    _write_output_tree(
        inputs=inputs,
        output_dir=output_dir,
        candidate=candidate,
        filing=cloned_filing,
        transactions=cloned_transactions,
        purchases=cloned_purchases,
        manifest=manifest,
        source=str(original_filing.get("source") or ""),
        report_id=report_id,
        trade_ids=list(trade_ids.values()),
        observed_at_utc=generated_at,
        test_metadata=base_metadata,
    )
    return manifest


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clone one random historical processed filing into an isolated temporary "
            "dashboard artifact. Source tracker directories are never modified."
        )
    )
    parser.add_argument("--legislative-dir", type=Path)
    parser.add_argument("--executive-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=None,
        help="Synthetic filing date in YYYY-MM-DD form (default: current UTC date)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = generate_manual_test(
            legislative_dir=args.legislative_dir,
            executive_dir=args.executive_dir,
            output_dir=args.output_dir,
            as_of=args.as_of or datetime.now(timezone.utc).date(),
        )
    except ManualTestError as exc:
        print(f"Manual test generation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
