#!/usr/bin/env python3
"""Run one deterministic, offline PolitiTrack filing simulation.

The simulator treats retained tracker and AI artifacts as immutable evidence.  It
selects a purchase that was observable at ``--as-of``, reconstructs pricing only
from AI analysis records available by that instant, and writes a paper result to
an isolated output directory.  It never calls a network service or sends an
alert.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import secrets
import sys
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence


STARTING_CAPITAL = Decimal("10000.00")
GOAL_VALUE = Decimal("20000.00")
SHARE_QUANTUM = Decimal("0.00000001")
MONEY_QUANTUM = Decimal("0.01")
TICKER_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")
RESULT_FILENAME = "simulation-result.json"
RUNS_FILENAME = "simulation-runs.jsonl"


class SimulationError(RuntimeError):
    """Raised when an offline simulation cannot be completed safely."""


def parse_as_of(value: str) -> datetime:
    """Parse a timezone-aware ISO-8601 timestamp and normalize it to UTC."""

    cleaned = value.strip()
    if not cleaned:
        raise SimulationError("--as-of must be a non-empty ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SimulationError(f"Invalid --as-of timestamp {value!r}: {exc}") from exc
    if parsed.tzinfo is None:
        raise SimulationError("--as-of must include a UTC offset or Z suffix")
    return parsed.astimezone(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_optional_instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_optional_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SimulationError(f"Could not read input {path}: {exc}") from exc
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SimulationError(f"Invalid JSONL in {path} at line {number}: {exc}") from exc
        if not isinstance(value, dict):
            raise SimulationError(f"Expected an object in {path} at line {number}")
        records.append(value)
    return records


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SimulationError(f"Could not hash input {path}: {exc}") from exc
    return digest.hexdigest()


def directory_sha256(directory: Path) -> str:
    """Return a stable SHA-256 tree digest without following symlinks."""

    directory = directory.resolve()
    if not directory.is_dir():
        raise SimulationError(f"Input directory does not exist: {directory}")
    digest = hashlib.sha256()
    for root, dirnames, filenames in os.walk(directory, followlinks=False):
        dirnames.sort()
        filenames.sort()
        root_path = Path(root)
        for name in filenames:
            path = root_path / name
            relative = path.relative_to(directory).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(b"symlink\0")
                digest.update(os.readlink(path).encode("utf-8"))
            else:
                digest.update(b"file\0")
                digest.update(_file_sha256(path).encode("ascii"))
            digest.update(b"\n")
    return digest.hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_paths(
    legislative_dir: Path,
    executive_dir: Path,
    ai_dir: Path,
    output_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    inputs = tuple(path.resolve() for path in (legislative_dir, executive_dir, ai_dir))
    output = output_dir.resolve()
    if len(set(inputs)) != len(inputs):
        raise SimulationError("Legislative, Executive, and AI input directories must differ")
    for input_dir in inputs:
        if not input_dir.is_dir():
            raise SimulationError(f"Input directory does not exist: {input_dir}")
        if _is_relative_to(output, input_dir) or _is_relative_to(input_dir, output):
            raise SimulationError(
                f"Output directory must be separate from every input directory: {output}"
            )
    return inputs[0], inputs[1], inputs[2], output


def _record_available_at(record: Mapping[str, Any], field: str) -> datetime | None:
    return parse_optional_instant(record.get(field))


def _filing_key(record: Mapping[str, Any]) -> str:
    existing = str(record.get("filing_key") or "").strip()
    if existing:
        return existing
    source = str(record.get("source") or "").strip().casefold()
    report_id = str(record.get("report_id") or "").strip()
    return f"{source}|{report_id}" if source and report_id else ""


def _latest_filings_as_of(directory: Path, as_of: datetime) -> dict[str, dict[str, Any]]:
    selected: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for record in _read_jsonl(directory / "filings.jsonl"):
        key = _filing_key(record)
        if not key:
            continue
        available = _record_available_at(record, "updated_at_utc") or _record_available_at(
            record, "first_seen_utc"
        )
        first_seen = _record_available_at(record, "first_seen_utc")
        if available is None or available > as_of or (first_seen is not None and first_seen > as_of):
            continue
        prior = selected.get(key)
        if prior is None or (available, key) >= (prior[0], key):
            selected[key] = (available, dict(record))
    return {key: item[1] for key, item in selected.items()}


def _latest_transactions_as_of(directory: Path, as_of: datetime) -> dict[str, dict[str, Any]]:
    selected: dict[str, tuple[datetime, dict[str, Any]]] = {}
    for filename in ("transactions.jsonl", "purchases.jsonl"):
        for record in _read_jsonl(directory / filename):
            trade_id = str(record.get("trade_id") or "").strip()
            observed = _record_available_at(record, "observed_at_utc")
            if not trade_id or observed is None or observed > as_of:
                continue
            # A duplicate retained row must not move the disclosure forward in
            # time.  The earliest observation is the information-availability
            # boundary used by the historical replay.
            prior = selected.get(trade_id)
            if prior is None or (observed, filename) < (prior[0], filename):
                selected[trade_id] = (observed, dict(record))
    return {key: item[1] for key, item in selected.items()}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _eligible_purchase(
    trade: Mapping[str, Any],
    filing: Mapping[str, Any] | None,
    as_of: datetime,
) -> bool:
    if filing is None:
        return False
    if str(trade.get("transaction_type") or "").strip().casefold() != "purchase":
        return False
    ticker = str(trade.get("ticker") or "").strip().upper()
    if not TICKER_RE.fullmatch(ticker) or not _truthy(trade.get("equity_like")):
        return False
    if not str(trade.get("source_url") or filing.get("source_url") or "").strip():
        return False
    filed = parse_optional_date(trade.get("filed_date") or filing.get("filed_date"))
    transaction_date = parse_optional_date(trade.get("transaction_date"))
    if filed is not None and filed > as_of.date():
        return False
    if transaction_date is not None and transaction_date > as_of.date():
        return False
    return True


def _load_candidates(
    legislative_dir: Path,
    executive_dir: Path,
    as_of: datetime,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    filings_by_key: dict[str, dict[str, Any]] = {}
    for branch, directory in (
        ("legislative", legislative_dir),
        ("executive", executive_dir),
    ):
        filings = _latest_filings_as_of(directory, as_of)
        filings_by_key.update(filings)
        for trade in _latest_transactions_as_of(directory, as_of).values():
            source = str(trade.get("source") or "").strip().casefold()
            report_id = str(trade.get("report_id") or "").strip()
            key = f"{source}|{report_id}" if source and report_id else ""
            filing = filings.get(key)
            if not _eligible_purchase(trade, filing, as_of):
                continue
            item = dict(trade)
            item["branch"] = str(item.get("branch") or branch)
            item["filing_key"] = key
            candidates.append(item)
    candidates.sort(
        key=lambda item: (
            str(item.get("filing_key") or ""),
            str(item.get("trade_id") or ""),
        )
    )
    return candidates, filings_by_key


def _select_candidate(
    candidates: Sequence[dict[str, Any]],
    *,
    seed: str | None,
    trade_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not candidates:
        raise SimulationError(
            "No eligible equity purchase filings were available at the requested --as-of timestamp"
        )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[str(candidate["filing_key"])].append(candidate)

    if trade_id:
        matches = [item for item in candidates if str(item.get("trade_id")) == trade_id]
        if not matches:
            raise SimulationError(
                f"Trade {trade_id!r} is not an eligible purchase available at --as-of"
            )
        selected = matches[0]
        selection = {
            "method": "explicit_trade_id",
            "seed": None,
            "candidate_filing_count": len(groups),
            "candidate_trade_count": len(candidates),
        }
        return selected, selection

    effective_seed = seed or secrets.token_hex(16)
    rng = random.Random(effective_seed)
    filing_key = rng.choice(sorted(groups))
    selected = rng.choice(sorted(groups[filing_key], key=lambda item: str(item["trade_id"])))
    selection = {
        "method": "seeded_random" if seed is not None else "random_recorded_seed",
        "seed": effective_seed,
        "candidate_filing_count": len(groups),
        "candidate_trade_count": len(candidates),
    }
    return selected, selection


def _analysis_versions(
    ai_dir: Path,
    trade_id: str,
    as_of: datetime,
    *,
    not_before: datetime,
) -> list[dict[str, Any]]:
    versions: list[dict[str, Any]] = []
    for record in _read_jsonl(ai_dir / "analyses.jsonl"):
        if str(record.get("trade_id") or "") != trade_id:
            continue
        analyzed = parse_optional_instant(record.get("analyzed_at_utc"))
        embedded_observed = parse_optional_instant(record.get("observed_at_utc"))
        # Older retained tracker snapshots can carry an earlier first-observed
        # timestamp than the newest tracker artifact.  Accept that provenance
        # only when it precedes the analysis that embeds it.
        effective_not_before = not_before
        if (
            embedded_observed is not None
            and analyzed is not None
            and embedded_observed <= analyzed
            and embedded_observed < effective_not_before
        ):
            effective_not_before = embedded_observed
        if analyzed is None or analyzed < effective_not_before or analyzed > as_of:
            continue
        versions.append(dict(record))
    versions.sort(
        key=lambda item: (
            parse_optional_instant(item.get("analyzed_at_utc")) or datetime.min.replace(tzinfo=timezone.utc),
            str(item.get("analysis_id") or ""),
        )
    )
    return versions


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", False):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _price_snapshot(record: Mapping[str, Any], as_of: datetime) -> dict[str, Any] | None:
    analyzed = parse_optional_instant(record.get("analyzed_at_utc"))
    if analyzed is None or analyzed > as_of:
        return None
    market = record.get("market") if isinstance(record.get("market"), dict) else {}
    entry_plan = record.get("entry_plan") if isinstance(record.get("entry_plan"), dict) else {}
    price = _decimal(market.get("current_price") or entry_plan.get("current_price"))
    if price is None:
        return None
    quote = parse_optional_instant(market.get("quote_timestamp_utc"))
    refreshed = parse_optional_instant(record.get("market_refreshed_at_utc"))
    known_at = max(value for value in (analyzed, quote, refreshed) if value is not None)
    if known_at > as_of:
        return None
    return {
        "analysis": dict(record),
        "price": price,
        "price_timestamp": quote or refreshed or analyzed,
        "known_at": known_at,
        "timestamp_source": (
            "market.quote_timestamp_utc"
            if quote is not None
            else "market_refreshed_at_utc"
            if refreshed is not None
            else "analyzed_at_utc"
        ),
    }


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def _number(value: Decimal, quantum: Decimal = SHARE_QUANTUM) -> float:
    return float(value.quantize(quantum, rounding=ROUND_HALF_UP))


def _accounting(versions: Sequence[dict[str, Any]], as_of: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshots = [snapshot for item in versions if (snapshot := _price_snapshot(item, as_of))]
    snapshots.sort(
        key=lambda item: (
            item["known_at"],
            str(item["analysis"].get("analysis_id") or ""),
        )
    )
    if not snapshots:
        return (
            {
                "status": "unpriced",
                "reason": "No retained AI analysis market price was available by --as-of",
                "strategy": "single_filing_full_allocation_fractional_shares",
                "starting_cash_usd": _money(STARTING_CAPITAL),
                "cash_usd": _money(STARTING_CAPITAL),
                "shares": None,
                "entry_price_usd": None,
                "valuation_price_usd": None,
                "position_value_usd": None,
                "portfolio_value_usd": _money(STARTING_CAPITAL),
                "profit_loss_usd": 0.0,
                "return_percent": 0.0,
            },
            {"available_version_count": len(versions), "priced_version_count": 0},
        )

    entry = snapshots[0]
    valuation = max(
        snapshots,
        key=lambda item: (
            item["price_timestamp"],
            item["known_at"],
            str(item["analysis"].get("analysis_id") or ""),
        ),
    )
    shares = (STARTING_CAPITAL / entry["price"]).quantize(
        SHARE_QUANTUM, rounding=ROUND_DOWN
    )
    invested = (shares * entry["price"]).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    cash = STARTING_CAPITAL - invested
    position_value = (shares * valuation["price"]).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
    portfolio_value = cash + position_value
    profit_loss = portfolio_value - STARTING_CAPITAL
    return_percent = (profit_loss / STARTING_CAPITAL) * Decimal("100")
    accounting = {
        "status": "priced",
        "reason": "",
        "strategy": "single_filing_full_allocation_fractional_shares",
        "starting_cash_usd": _money(STARTING_CAPITAL),
        "cash_usd": _money(cash),
        "shares": _number(shares),
        "entry_price_usd": _number(entry["price"], Decimal("0.0001")),
        "valuation_price_usd": _number(valuation["price"], Decimal("0.0001")),
        "position_value_usd": _money(position_value),
        "portfolio_value_usd": _money(portfolio_value),
        "profit_loss_usd": _money(profit_loss),
        "return_percent": _number(return_percent, Decimal("0.01")),
    }
    price_context = {
        "available_version_count": len(versions),
        "priced_version_count": len(snapshots),
        "entry_analysis_id": str(entry["analysis"].get("analysis_id") or ""),
        "entry_analyzed_at_utc": str(entry["analysis"].get("analyzed_at_utc") or ""),
        "entry_price_timestamp_utc": iso_utc(entry["price_timestamp"]),
        "entry_price_timestamp_source": entry["timestamp_source"],
        "valuation_analysis_id": str(valuation["analysis"].get("analysis_id") or ""),
        "valuation_analyzed_at_utc": str(
            valuation["analysis"].get("analyzed_at_utc") or ""
        ),
        "valuation_price_timestamp_utc": iso_utc(valuation["price_timestamp"]),
        "valuation_price_timestamp_source": valuation["timestamp_source"],
    }
    return accounting, price_context


def _evidence_sources(versions: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for analysis in versions:
        ai_payload = analysis.get("ai") if isinstance(analysis.get("ai"), dict) else {}
        for item in ai_payload.get("evidence_sources") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "title": str(item.get("title") or ""),
                    "url": url,
                    "published_date": str(item.get("published_date") or item.get("date") or ""),
                }
            )
    return sources


def _compact_analysis(versions: Sequence[dict[str, Any]], as_of: datetime) -> dict[str, Any]:
    if not versions:
        return {"status": "not_available_as_of", "version_count": 0}
    latest = versions[-1]
    return {
        "status": "available",
        "version_count": len(versions),
        "latest_analysis_id": str(latest.get("analysis_id") or ""),
        "latest_analyzed_at_utc": str(latest.get("analyzed_at_utc") or ""),
        "model": str(latest.get("model") or ""),
        "score": latest.get("score"),
        "classification": str(latest.get("classification") or ""),
        "entry_status": str((latest.get("entry_plan") or {}).get("entry_status") or ""),
        "all_records_within_as_of": all(
            (parse_optional_instant(item.get("analyzed_at_utc")) or as_of) <= as_of
            for item in versions
        ),
    }


def _result_id(
    *,
    as_of: datetime,
    trade_id: str,
    selection: Mapping[str, Any],
    hashes: Mapping[str, str],
) -> str:
    material = json.dumps(
        {
            "as_of": iso_utc(as_of),
            "trade_id": trade_id,
            "selection": dict(selection),
            "hashes": dict(hashes),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "simulation:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _validate_existing_history(path: Path) -> None:
    if not path.exists():
        return
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SimulationError(
                f"Refusing to append to invalid history {path} at line {number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise SimulationError(f"Refusing to append to non-object history line {number}")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = False
    if path.is_file() and path.stat().st_size:
        with path.open("rb") as previous:
            previous.seek(-1, os.SEEK_END)
            needs_separator = previous.read(1) not in (b"\n", b"\r")
    with path.open("a", encoding="utf-8") as handle:
        if needs_separator:
            handle.write("\n")
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_simulation(
    *,
    legislative_dir: Path,
    executive_dir: Path,
    ai_dir: Path,
    output_dir: Path,
    as_of: datetime,
    seed: str | None = None,
    trade_id: str | None = None,
) -> dict[str, Any]:
    legislative_dir, executive_dir, ai_dir, output_dir = _validate_paths(
        legislative_dir, executive_dir, ai_dir, output_dir
    )
    if as_of.tzinfo is None:
        raise SimulationError("as_of must be timezone-aware")
    as_of = as_of.astimezone(timezone.utc)

    hashes_before = {
        "legislative": directory_sha256(legislative_dir),
        "executive": directory_sha256(executive_dir),
        "ai": directory_sha256(ai_dir),
    }
    candidates, filings = _load_candidates(legislative_dir, executive_dir, as_of)
    selected, selection = _select_candidate(candidates, seed=seed, trade_id=trade_id)
    selected_trade_id = str(selected.get("trade_id") or "")
    filing = filings[str(selected["filing_key"])]
    observed_at = parse_optional_instant(selected.get("observed_at_utc"))
    if observed_at is None:  # Eligibility already rejects this; retain a fail-closed guard.
        raise SimulationError(f"Selected trade {selected_trade_id!r} has no valid observation time")
    versions = _analysis_versions(
        ai_dir,
        selected_trade_id,
        as_of,
        not_before=observed_at,
    )
    accounting, price_context = _accounting(versions, as_of)
    portfolio_value = Decimal(str(accounting["portfolio_value_usd"]))
    goal_remaining = max(Decimal("0"), GOAL_VALUE - portfolio_value)
    goal_progress = (portfolio_value / GOAL_VALUE) * Decimal("100")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip("/")
    github_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    run_url = (
        f"{server_url}/{repository}/actions/runs/{github_run_id}"
        if repository and github_run_id
        else ""
    )
    ticker = str(selected.get("ticker") or "").upper()

    result = {
        "schema_version": 1,
        "status": "success",
        "success": True,
        "simulation_id": _result_id(
            as_of=as_of,
            trade_id=selected_trade_id,
            selection=selection,
            hashes=hashes_before,
        ),
        "mode": "offline_historical_replay",
        "as_of_utc": iso_utc(as_of),
        "run_url": run_url,
        "message": (
            f"Selected {ticker}; {accounting['status']} paper portfolio value "
            f"${float(portfolio_value):,.2f} toward the $20,000.00 goal."
        ),
        "selection": selection,
        "objective": {
            "starting_capital_usd": _money(STARTING_CAPITAL),
            "goal_value_usd": _money(GOAL_VALUE),
            "goal_reached": portfolio_value >= GOAL_VALUE,
            "goal_progress_percent": _number(goal_progress, Decimal("0.01")),
            "remaining_to_goal_usd": _money(goal_remaining),
        },
        "filing": {
            "filing_key": str(selected.get("filing_key") or ""),
            "branch": str(selected.get("branch") or filing.get("branch") or ""),
            "source": str(selected.get("source") or filing.get("source") or ""),
            "report_id": str(selected.get("report_id") or filing.get("report_id") or ""),
            "filer": str(selected.get("filer") or filing.get("filer") or ""),
            "filed_date": str(selected.get("filed_date") or filing.get("filed_date") or ""),
            "first_seen_utc": str(filing.get("first_seen_utc") or ""),
            "status": str(filing.get("status") or ""),
            "source_url": str(filing.get("source_url") or selected.get("source_url") or ""),
        },
        "trade": {
            "trade_id": selected_trade_id,
            "ticker": ticker,
            "asset": str(selected.get("asset") or ""),
            "owner": str(selected.get("owner") or ""),
            "transaction_type": str(selected.get("transaction_type") or ""),
            "transaction_date": str(selected.get("transaction_date") or ""),
            "observed_at_utc": str(selected.get("observed_at_utc") or ""),
            "amount": str(selected.get("amount") or ""),
            "source_url": str(selected.get("source_url") or filing.get("source_url") or ""),
        },
        "analysis": _compact_analysis(versions, as_of),
        "price_context": price_context,
        "accounting": accounting,
        "provenance": {
            "filing_source_url": str(filing.get("source_url") or ""),
            "trade_source_url": str(selected.get("source_url") or ""),
            "analysis_source_urls": sorted(
                {
                    str(item.get("source_url") or "")
                    for item in versions
                    if str(item.get("source_url") or "")
                }
            ),
            "evidence_sources": _evidence_sources(versions),
        },
        "input_sha256": {
            "algorithm": "sha256-tree-v1",
            **hashes_before,
        },
        "safety": {
            "paper_only": True,
            "network_calls": False,
            "alerts_sent": False,
            "production_inputs_mutated": False,
        },
        # Finalize metadata before the one append. Rewriting JSONL later would
        # change valid predecessor formatting and violate byte-prefix continuity.
        "notification": {"pushover": "not_requested", "email": "not_requested"},
        "notification_status": "Pushover: not_requested; email: not_requested",
    }

    hashes_after = {
        "legislative": directory_sha256(legislative_dir),
        "executive": directory_sha256(executive_dir),
        "ai": directory_sha256(ai_dir),
    }
    if hashes_after != hashes_before:
        raise SimulationError("A production input changed while the simulation was running")

    output_dir.mkdir(parents=True, exist_ok=True)
    history_path = output_dir / RUNS_FILENAME
    _validate_existing_history(history_path)
    _atomic_write_json(output_dir / RESULT_FILENAME, result)
    _append_jsonl(history_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislative-dir", type=Path, required=True)
    parser.add_argument("--executive-dir", type=Path, required=True)
    parser.add_argument("--ai-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO-8601 cutoff")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--seed", help="Deterministic random-selection seed")
    selection.add_argument("--trade-id", help="Replay one explicit eligible purchase trade")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_simulation(
            legislative_dir=args.legislative_dir,
            executive_dir=args.executive_dir,
            ai_dir=args.ai_dir,
            output_dir=args.output_dir,
            as_of=parse_as_of(args.as_of),
            seed=args.seed,
            trade_id=args.trade_id,
        )
    except SimulationError as exc:
        print(f"Simulation failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"Simulation {result['simulation_id']} selected {result['trade']['trade_id']} "
        f"({result['trade']['ticker']}); accounting={result['accounting']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
