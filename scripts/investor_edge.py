#!/usr/bin/env python3
"""Historical government-investor performance scoring for PolitiTrack.

Investor Edge is intentionally deterministic. It evaluates prior disclosed purchases by
filer + disclosed owner, measures benchmark-relative returns from both the transaction
and public filing dates, shrinks small samples toward neutral, and applies a bounded
modifier to the existing PolitiTrack score. The module also writes a standalone heat-map page
into the generated dashboard site.
"""

from __future__ import annotations

import html
import hashlib
import json
import math
import os
import re
import statistics
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import requests
import yaml

EDGE_VERSION = "2026-08-29.5"
DEFAULT_CONFIG = Path("config/investor_edge.yml")
PROFILE_FILE = "investor-edge-profiles.json"
LEADERBOARD_FILE = "investor-edge-leaderboard.json"
OBSERVATION_FILE = "investor-edge-observations.json"
MAX_MODIFIER_LIMIT = 12
MIN_SECTOR_MAPPING_CONFIDENCE = 0.50

OWNER_ALIASES: dict[str, tuple[str, ...]] = {
    "Self": ("self", "filer", "reporting person", "direct", "s"),
    "Spouse": ("spouse", "sp", "wife", "husband"),
    "Joint": ("joint", "jt", "joint account", "jointly held"),
    "Dependent": ("dependent", "dependent child", "dc", "child"),
    "Trust": ("trust", "family trust", "revocable trust", "irrevocable trust", "trust or entity"),
    "Managed": ("managed", "managed account", "investment manager", "blind trust"),
    "Other": ("other", "entity"),
}

KNOWN_FUND_TICKERS = {
    "DIA", "EFA", "EF", "ETF", "IWM", "QQQ", "SPY", "VTI", "VOO",
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
}
FUND_TERMS = (
    "exchange traded fund", "exchange-traded fund", " etf", "index fund",
    "mutual fund", "diversified fund", "target date fund",
)
NONDISCRETIONARY_TERMS = (
    "automatic investment", "automatic plan", "blind trust", "dividend reinvestment",
    "drip", "employee plan", "grant", "inheritance", "managed account", "reinvestment",
    "restricted stock award", "10b5-1", "transfer", "vesting", "vested",
)

SECTOR_BENCHMARKS: tuple[tuple[tuple[str, ...], str, str], ...] = (
    (("technology", "software", "semiconductor", "computer", "electronic", "internet"), "XLK", "Technology"),
    (("health", "biotech", "pharma", "medical", "life science"), "XLV", "Health care"),
    (("bank", "financial", "insurance", "capital market", "credit"), "XLF", "Financials"),
    (("aerospace", "defense", "industrial", "machinery", "transport", "construction"), "XLI", "Industrials"),
    (("consumer cyclical", "retail", "auto", "restaurant", "hotel", "leisure"), "XLY", "Consumer discretionary"),
    (("consumer defensive", "food", "beverage", "household", "tobacco"), "XLP", "Consumer staples"),
    (("energy", "oil", "gas", "coal"), "XLE", "Energy"),
    (("utility", "utilities"), "XLU", "Utilities"),
    (("real estate", "reit"), "XLRE", "Real estate"),
    (("materials", "chemical", "metals", "mining", "paper", "packaging"), "XLB", "Materials"),
    (("communication", "telecom", "media", "entertainment"), "XLC", "Communication services"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | None = None) -> str:
    return (value or _utc_now()).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _public_date(record: Mapping[str, Any]) -> date | None:
    """Return the first date PolitiTrack can prove the disclosure was observable."""
    return _parse_date(record.get("observed_at_utc")) or _parse_date(
        record.get("filed_date")
    )


def _followable_anchor(record: Mapping[str, Any]) -> date | None:
    """Use the first trading session after public observation, never the same day."""
    public_date = _public_date(record)
    return public_date + timedelta(days=1) if public_date else None


def _normal(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _redact_sensitive(value: Any, *secrets: str) -> str:
    """Remove provider credentials from errors before they reach durable state."""
    text = _normal(value)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return re.sub(
        r"(?i)(apikey|api_key|token)=([^&\s]+)",
        r"\1=[redacted]",
        text,
    )


def _identity_part(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _normal(value).casefold()).strip("-")


def _ticker_symbol(value: Any) -> str:
    symbol = _normal(value).upper().replace("/", ".")
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,19}", symbol):
        return ""
    if ".." in symbol or symbol.endswith((".", "-")):
        return ""
    return symbol


def _owner_identity(value: Any) -> dict[str, Any]:
    """Canonicalize disclosed ownership without silently treating missing data as Self."""
    raw = _normal(value)
    material = re.sub(r"[^a-z0-9]+", " ", raw.casefold()).strip()
    if not material:
        return {
            "owner": "Other",
            "owner_category": "Other",
            "owner_key": "other-unknown",
            "owner_raw": raw,
            "owner_confidence": 0.20,
            "owner_confidence_label": "Low",
            "owner_fallback": True,
            "owner_fallback_reason": "missing_owner",
        }

    for category, aliases in OWNER_ALIASES.items():
        if material in aliases:
            confidence = 0.98 if material == category.casefold() else 0.92
            return {
                "owner": category,
                "owner_category": category,
                "owner_key": _identity_part(category),
                "owner_raw": raw,
                "owner_confidence": confidence,
                "owner_confidence_label": "High",
                "owner_fallback": False,
                "owner_fallback_reason": "",
            }

    patterns = (
        ("Spouse", ("spouse", "wife", "husband")),
        ("Joint", ("joint", "jointly")),
        ("Dependent", ("dependent", "child")),
        ("Managed", ("managed", "manager", "blind trust")),
        ("Trust", ("trust",)),
        ("Self", ("self", "filer", "reporting person")),
    )
    for category, terms in patterns:
        if any(term in material for term in terms):
            return {
                "owner": category,
                "owner_category": category,
                "owner_key": _identity_part(category),
                "owner_raw": raw,
                "owner_confidence": 0.72,
                "owner_confidence_label": "Medium",
                "owner_fallback": True,
                "owner_fallback_reason": "pattern_normalization",
            }

    return {
        "owner": "Other",
        "owner_category": "Other",
        "owner_key": f"other-{_identity_part(raw)}",
        "owner_raw": raw,
        "owner_confidence": 0.35,
        "owner_confidence_label": "Low",
        "owner_fallback": True,
        "owner_fallback_reason": "unrecognized_owner",
    }


def investor_identity(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable, consensus-ready filer/owner identity with provenance."""
    filer = _normal(record.get("filer"))
    identifier = ""
    identifier_source = ""
    for field_name in (
        "filer_id", "bioguide_id", "reporting_person_id", "person_id", "member_id"
    ):
        candidate = _identity_part(record.get(field_name))
        if candidate:
            identifier = candidate
            identifier_source = field_name
            break
    if identifier:
        # Provider field names vary for the same public identifier. The value is
        # canonical; provenance remains available in filer_identity_source.
        filer_key = f"id-{identifier}"
        filer_confidence = 1.0
    else:
        filer_key = _identity_part(filer)
        identifier_source = "normalized_name" if filer_key else "missing"
        filer_confidence = 0.75 if filer_key else 0.0

    owner = _owner_identity(record.get("owner"))
    owner_key = str(owner.get("owner_key") or "other-unknown")
    key = f"{filer_key}|{owner_key}" if filer_key else ""
    confidence = min(filer_confidence, float(owner["owner_confidence"]))
    return {
        "investor_key": key,
        "filer": filer,
        "filer_key": filer_key,
        "filer_name_key": _identity_part(filer),
        "filer_stable_id": identifier,
        "filer_identity_source": identifier_source,
        "filer_identity_confidence": round(filer_confidence, 4),
        **owner,
        "identity_confidence": round(confidence, 4),
        "identity_confidence_label": (
            "High" if confidence >= 0.85 else "Medium" if confidence >= 0.55 else "Low"
        ),
        "identity_fallback": bool(owner["owner_fallback"] or not identifier),
    }


def investor_key(record: Mapping[str, Any]) -> str:
    """Return the filer/owner identity used for skill attribution."""
    return str(investor_identity(record).get("investor_key") or "")


def _matching_investor_records(
    target: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Bridge name-only history to one unambiguous stable-ID identity."""
    target_identity = investor_identity(target)
    target_stable = str(target_identity.get("filer_stable_id") or "")
    target_name = str(target_identity.get("filer_name_key") or "")
    target_owner = str(target_identity.get("owner_key") or "")
    identities = [(item, investor_identity(item)) for item in records]

    same_name_owner = [
        (item, identity)
        for item, identity in identities
        if target_name
        and str(identity.get("filer_name_key") or "") == target_name
        and str(identity.get("owner_key") or "") == target_owner
    ]
    stable_ids = {
        str(identity.get("filer_stable_id") or "")
        for _, identity in same_name_owner
        if identity.get("filer_stable_id")
    }
    if target_stable:
        matched = [
            item
            for item, identity in identities
            if str(identity.get("owner_key") or "") == target_owner
            and str(identity.get("filer_stable_id") or "") == target_stable
        ]
        if stable_ids == {target_stable}:
            matched.extend(
                item
                for item, identity in same_name_owner
                if not identity.get("filer_stable_id") and item not in matched
            )
        return matched
    if len(stable_ids) <= 1:
        return [item for item, _ in same_name_owner]
    return [
        item for item, identity in same_name_owner if not identity.get("filer_stable_id")
    ]


def matching_investor_records(
    target: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Public identity-compatibility helper for simulation and reporting surfaces."""
    return _matching_investor_records(target, records)


def _method_config(config: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "version", "minimum_completed_trades", "confidence_prior_trades",
        "sector_confidence_prior_trades", "max_history_trades", "alpha_clip_percent",
        "alpha_score_points_per_percent", "benchmark_default", "horizons",
        "horizon_weights", "edge_weights", "max_modifier",
    )
    return {key: config.get(key) for key in keys}


def method_config_hash(config: Mapping[str, Any]) -> str:
    material = json.dumps(_method_config(config), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{EDGE_VERSION}|{material}".encode("utf-8")).hexdigest()[:20]


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    candidate = Path(path or os.environ.get("INVESTOR_EDGE_CONFIG") or DEFAULT_CONFIG)
    if not candidate.exists():
        payload = {
            "version": 2,
            "enabled": True,
            "max_modifier": 12,
            "minimum_completed_trades": 3,
            "confidence_prior_trades": 8,
            "max_history_trades": 40,
            "leaderboard_max_investors": 40,
            "backfill_analysis_limit_per_run": 30,
            "observation_retention_limit": 2000,
            "network_request_budget_per_run": 40,
            "market_cache_hours": 24,
            "profile_cache_hours": 168,
            "sector_confidence_prior_trades": 4,
            "history_lookback_days": 2200,
            "alpha_clip_percent": 25.0,
            "alpha_score_points_per_percent": 2.5,
            "benchmark_default": "SPY",
            "horizons": [5, 20, 60, 120],
            "horizon_weights": {"5": 0.15, "20": 0.30, "60": 0.35, "120": 0.20},
            "edge_weights": {
                "followable_alpha": 0.45,
                "picker_alpha": 0.20,
                "hit_rate": 0.15,
                "consistency": 0.10,
                "sector_skill": 0.10,
            },
        }
    else:
        payload = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Investor Edge config must be an object: {candidate}")
    enabled_override = os.environ.get("INVESTOR_EDGE_ENABLED", "").strip().casefold()
    if enabled_override:
        if enabled_override not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
            raise ValueError("INVESTOR_EDGE_ENABLED must be a boolean value")
        payload["enabled"] = enabled_override in {"1", "true", "yes", "on"}
    return payload


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _cache_fresh(path: Path, hours: float) -> bool:
    if not path.exists():
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return _utc_now() - modified <= timedelta(hours=max(0.0, hours))


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _coerce_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        parsed = _parse_date(row.get("date"))
        close = _safe_float(row.get("close"))
        if parsed is None or close is None or close <= 0:
            continue
        cleaned.append({"date": parsed.isoformat(), "close": close})
    cleaned.sort(key=lambda item: item["date"])
    return cleaned


def _rows_cover(
    rows: Sequence[Mapping[str, Any]],
    minimum: date | None,
    required_through: date | None = None,
) -> bool:
    if not rows:
        return False
    oldest = _parse_date(rows[0].get("date"))
    newest = _parse_date(rows[-1].get("date"))
    if minimum is not None and (oldest is None or oldest > minimum):
        return False
    if required_through is not None:
        if newest is None:
            return False
        expected = required_through
        while expected.weekday() >= 5:
            expected -= timedelta(days=1)
        # Permit at most two nominal weekday sessions after the newest row. This
        # covers a long weekend/provider close lag without accepting a missing week.
        nominal_sessions = 0
        cursor = newest + timedelta(days=1)
        while cursor <= expected:
            if cursor.weekday() < 5:
                nominal_sessions += 1
            cursor += timedelta(days=1)
        if nominal_sessions > 2:
            return False
    return True


def _merge_rows(*groups: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for rows in groups:
        for row in _coerce_rows(item for item in rows if isinstance(item, Mapping)):
            by_date[str(row["date"])] = row
    return [by_date[key] for key in sorted(by_date)]


class MarketHistoryProvider:
    """Bounded, cached daily-price and sector lookup provider."""

    def __init__(
        self,
        *,
        ai_dir: Path,
        session: requests.Session,
        alphavantage_api_key: str = "",
        finnhub_api_key: str = "",
        alphavantage_entitlement: str = "",
        request_timeout: tuple[float, float] = (15.0, 60.0),
        config: Mapping[str, Any],
    ) -> None:
        self.ai_dir = ai_dir
        self.session = session
        self.alphavantage_api_key = alphavantage_api_key
        self.finnhub_api_key = finnhub_api_key
        self.alphavantage_entitlement = alphavantage_entitlement
        self.request_timeout = request_timeout
        self.config = dict(config)
        self.request_budget = max(
            0,
            min(100, int(self.config.get("network_request_budget_per_run", 40))),
        )
        self.network_requests = 0
        self.memory: dict[str, list[dict[str, Any]]] = {}
        self.sector_memory: dict[str, dict[str, Any]] = {}
        self.errors: list[str] = []

    def _can_request(self) -> bool:
        return self.network_requests < max(0, self.request_budget)

    def _safe_error(self, label: str, value: Any) -> str:
        return f"{label}: {_redact_sensitive(value, self.alphavantage_api_key, self.finnhub_api_key)}"

    def _get(self, url: str, *, params: Mapping[str, Any]) -> requests.Response | None:
        if not self._can_request():
            return None
        self.network_requests += 1
        response = self.session.get(url, params=dict(params), timeout=self.request_timeout)
        response.raise_for_status()
        return response

    def _edge_cache(self, ticker: str) -> Path:
        return self.ai_dir / "investor-edge-market" / f"{ticker.upper()}-daily.json"

    def _core_cache(self, ticker: str) -> Path:
        return self.ai_dir / "market-cache" / f"{ticker.upper()}-daily.json"

    def daily(
        self,
        ticker: str,
        *,
        minimum_date: date | None = None,
        required_through: date | None = None,
    ) -> list[dict[str, Any]]:
        ticker = _ticker_symbol(ticker)
        if not ticker:
            return []
        cached_memory = self.memory.get(ticker)
        if cached_memory is not None and _rows_cover(
            cached_memory, minimum_date, required_through
        ):
            return cached_memory

        cache_hours = float(self.config.get("market_cache_hours", 24))
        edge_path = self._edge_cache(ticker)
        edge_payload = _read_json(edge_path)
        edge_rows = (
            _coerce_rows(item for item in edge_payload.get("rows", []) if isinstance(item, Mapping))
            if isinstance(edge_payload, dict)
            else []
        )
        core_path = self._core_cache(ticker)
        core_payload = _read_json(core_path)
        core_rows = (
            _coerce_rows(item for item in core_payload.get("rows", []) if isinstance(item, Mapping))
            if isinstance(core_payload, dict)
            else []
        )
        cached_rows = _merge_rows(core_rows, edge_rows)
        historical_request = bool(
            required_through and required_through < _utc_now().date() - timedelta(days=7)
        )
        edge_is_last_good_stale = bool(
            isinstance(edge_payload, dict) and edge_payload.get("stale_if_error")
        )
        cache_is_fresh = (
            _cache_fresh(edge_path, cache_hours) and not edge_is_last_good_stale
        ) or _cache_fresh(core_path, cache_hours)
        if _rows_cover(cached_rows, minimum_date, required_through) and (
            historical_request or cache_is_fresh
        ):
            self.memory[ticker] = cached_rows
            return cached_rows

        fresh_rows = self._fetch_alphavantage(ticker, outputsize="full")
        network_rows = list(fresh_rows)
        merged = _merge_rows(cached_rows, network_rows)
        if not _rows_cover(merged, minimum_date, required_through):
            fallback = self._fetch_finnhub(ticker, minimum_date=minimum_date)
            network_rows = _merge_rows(network_rows, fallback)
            merged = _merge_rows(merged, fallback)
        if not network_rows and not _rows_cover(merged, minimum_date, required_through):
            compact = self._fetch_alphavantage(ticker, outputsize="compact")
            network_rows = _merge_rows(network_rows, compact)
            merged = _merge_rows(merged, compact)

        # Stale, non-empty data is strictly preferable to losing a last-good
        # history during a transient provider outage. Never replace it with empty.
        rows = merged or cached_rows
        self.memory[ticker] = rows
        if rows and (network_rows or not edge_rows):
            _atomic_json(
                edge_path,
                {
                    "ticker": ticker,
                    "fetched_utc": _iso_utc(),
                    "minimum_requested_date": minimum_date.isoformat() if minimum_date else "",
                    "required_through": required_through.isoformat() if required_through else "",
                    "rows": rows,
                    "stale_if_error": not bool(network_rows),
                    "errors": self.errors[-5:],
                },
            )
        return rows

    def _fetch_alphavantage(self, ticker: str, *, outputsize: str) -> list[dict[str, Any]]:
        if not self.alphavantage_api_key or not self._can_request():
            return []
        params: dict[str, Any] = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": outputsize,
            "apikey": self.alphavantage_api_key,
        }
        if self.alphavantage_entitlement:
            params["entitlement"] = self.alphavantage_entitlement
        try:
            response = self._get("https://www.alphavantage.co/query", params=params)
            if response is None:
                return []
            payload = response.json()
            if not isinstance(payload, dict):
                return []
            series = payload.get("Time Series (Daily)") or {}
            if not isinstance(series, dict):
                message = payload.get("Information") or payload.get("Note") or payload.get("Error Message")
                if message:
                    self.errors.append(self._safe_error(f"Alpha Vantage {ticker}", message)[:400])
                return []
            rows = []
            for row_date, values in series.items():
                if not isinstance(values, Mapping):
                    continue
                close = _safe_float(values.get("4. close"))
                if close and _parse_date(row_date):
                    rows.append({"date": str(row_date), "close": close})
            return _coerce_rows(rows)
        except Exception as exc:  # noqa: BLE001
            self.errors.append(
                self._safe_error(f"Alpha Vantage {ticker}", f"{type(exc).__name__}: {exc}")
            )
            return []

    def _fetch_finnhub(
        self, ticker: str, *, minimum_date: date | None = None
    ) -> list[dict[str, Any]]:
        if not self.finnhub_api_key or not self._can_request():
            return []
        lookback = int(self.config.get("history_lookback_days", 2200))
        end = _utc_now()
        start = end - timedelta(days=max(180, lookback))
        if minimum_date is not None:
            requested_start = datetime.combine(
                minimum_date - timedelta(days=10), datetime.min.time(), tzinfo=timezone.utc
            )
            start = min(start, requested_start)
        params = {
            "symbol": ticker,
            "resolution": "D",
            "from": int(start.timestamp()),
            "to": int(end.timestamp()),
            "token": self.finnhub_api_key,
        }
        try:
            response = self._get("https://finnhub.io/api/v1/stock/candle", params=params)
            if response is None:
                return []
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("s") != "ok":
                self.errors.append(self._safe_error(f"Finnhub candle {ticker}", payload)[:400])
                return []
            timestamps = payload.get("t") or []
            closes = payload.get("c") or []
            rows = []
            for stamp, close in zip(timestamps, closes):
                numeric = _safe_float(close)
                if numeric and stamp:
                    dt = datetime.fromtimestamp(float(stamp), tz=timezone.utc)
                    rows.append({"date": dt.date().isoformat(), "close": numeric})
            return _coerce_rows(rows)
        except Exception as exc:  # noqa: BLE001
            self.errors.append(
                self._safe_error(f"Finnhub candle {ticker}", f"{type(exc).__name__}: {exc}")
            )
            return []

    def sector(self, ticker: str) -> dict[str, Any]:
        ticker = _ticker_symbol(ticker)
        if not ticker:
            return {
                "industry": "",
                "benchmark": str(self.config.get("benchmark_default", "SPY")),
                "sector": "Broad market",
                "mapping_confidence": 0.0,
                "mapping_source": "invalid_ticker",
            }
        if ticker in self.sector_memory:
            return self.sector_memory[ticker]
        path = self.ai_dir / "investor-edge-market" / f"{ticker}-profile.json"
        cache_hours = float(self.config.get("profile_cache_hours", 168))
        cached = _read_json(path)
        cached_industry = _normal(cached.get("industry")) if isinstance(cached, dict) else ""
        industry = cached_industry
        cache_is_fresh = _cache_fresh(path, cache_hours)
        if not cache_is_fresh and self.finnhub_api_key and self._can_request():
            try:
                response = self._get(
                    "https://finnhub.io/api/v1/stock/profile2",
                    params={"symbol": ticker, "token": self.finnhub_api_key},
                )
                if response is not None:
                    payload = response.json()
                    if isinstance(payload, dict):
                        fetched_industry = _normal(payload.get("finnhubIndustry"))
                        if fetched_industry:
                            industry = fetched_industry
                if industry:
                    _atomic_json(path, {"ticker": ticker, "industry": industry, "fetched_utc": _iso_utc()})
            except Exception as exc:  # noqa: BLE001
                self.errors.append(
                    self._safe_error(f"Finnhub profile {ticker}", f"{type(exc).__name__}: {exc}")
                )
        benchmark = str(self.config.get("benchmark_default", "SPY"))
        sector_name = "Broad market"
        mapping_confidence = 0.25 if industry else 0.10
        mapping_source = "broad_market_fallback"
        material = industry.casefold()
        for terms, candidate, name in SECTOR_BENCHMARKS:
            if any(term in material for term in terms):
                benchmark = candidate
                sector_name = name
                mapping_confidence = 0.90
                mapping_source = "finnhub_industry_keyword"
                break
        result = {
            "industry": industry,
            "benchmark": benchmark,
            "sector": sector_name,
            "mapping_confidence": mapping_confidence,
            "mapping_source": mapping_source,
        }
        self.sector_memory[ticker] = result
        return result


def _price_index_on_or_after(rows: Sequence[Mapping[str, Any]], anchor: date) -> int | None:
    for index, row in enumerate(rows):
        row_date = _parse_date(row.get("date"))
        if row_date and row_date >= anchor:
            return index
    return None


def _close_on_or_after(rows: Sequence[Mapping[str, Any]], anchor: date) -> tuple[date, float] | None:
    index = _price_index_on_or_after(rows, anchor)
    if index is None:
        return None
    parsed = _parse_date(rows[index].get("date"))
    close = _safe_float(rows[index].get("close"))
    if parsed is None or close is None:
        return None
    return parsed, close


def _window_return(
    rows: Sequence[Mapping[str, Any]],
    anchor: date,
    horizon: int,
    *,
    as_of: date | None = None,
) -> tuple[date, date, float] | None:
    index = _price_index_on_or_after(rows, anchor)
    if index is None or index + horizon >= len(rows):
        return None
    start = rows[index]
    end = rows[index + horizon]
    start_date = _parse_date(start.get("date"))
    end_date = _parse_date(end.get("date"))
    start_close = _safe_float(start.get("close"))
    end_close = _safe_float(end.get("close"))
    if start_date is None or end_date is None or not start_close or end_close is None:
        return None
    if as_of is not None and end_date > as_of:
        return None
    return start_date, end_date, ((end_close / start_close) - 1.0) * 100.0


def _benchmark_return(
    rows: Sequence[Mapping[str, Any]],
    start_date: date,
    end_date: date,
    *,
    as_of: date | None = None,
) -> float | None:
    start = _close_on_or_after(rows, start_date)
    end = _close_on_or_after(rows, end_date)
    if not start or not end or not start[1]:
        return None
    if as_of is not None and end[0] > as_of:
        return None
    return ((end[1] / start[1]) - 1.0) * 100.0


def _outcome_for_horizon(
    stock_rows: Sequence[Mapping[str, Any]],
    benchmark_rows: Sequence[Mapping[str, Any]],
    anchor: date,
    horizon: int,
    *,
    as_of: date | None = None,
) -> dict[str, Any] | None:
    stock_window = _window_return(stock_rows, anchor, horizon, as_of=as_of)
    if not stock_window:
        return None
    entry_date, exit_date, stock_return = stock_window
    stock_entry = _close_on_or_after(stock_rows, entry_date)
    stock_exit = _close_on_or_after(stock_rows, exit_date)
    benchmark_entry = _close_on_or_after(benchmark_rows, entry_date)
    benchmark_exit = _close_on_or_after(benchmark_rows, exit_date)
    if not stock_entry or not stock_exit or not benchmark_entry or not benchmark_exit:
        return None
    if as_of is not None and benchmark_exit[0] > as_of:
        return None
    benchmark_return = ((benchmark_exit[1] / benchmark_entry[1]) - 1.0) * 100.0
    return {
        "horizon_trading_days": int(horizon),
        "anchor_date": anchor.isoformat(),
        "entry_date": entry_date.isoformat(),
        "exit_date": exit_date.isoformat(),
        "stock_entry_price": round(stock_entry[1], 6),
        "stock_exit_price": round(stock_exit[1], 6),
        "benchmark_entry_date": benchmark_entry[0].isoformat(),
        "benchmark_exit_date": benchmark_exit[0].isoformat(),
        "benchmark_entry_price": round(benchmark_entry[1], 6),
        "benchmark_exit_price": round(benchmark_exit[1], 6),
        "stock_return_percent": round(stock_return, 4),
        "benchmark_return_percent": round(benchmark_return, 4),
        "alpha_percent": round(stock_return - benchmark_return, 4),
    }


def _outcomes_for_anchor(
    stock_rows: Sequence[Mapping[str, Any]],
    benchmark_rows: Sequence[Mapping[str, Any]],
    anchor: date,
    horizons: Sequence[int],
    *,
    as_of: date | None = None,
) -> dict[str, dict[str, Any] | None]:
    return {
        str(horizon): _outcome_for_horizon(
            stock_rows, benchmark_rows, anchor, int(horizon), as_of=as_of
        )
        for horizon in horizons
    }


def _alphas_for_anchor(
    stock_rows: Sequence[Mapping[str, Any]],
    benchmark_rows: Sequence[Mapping[str, Any]],
    anchor: date,
    horizons: Sequence[int],
    *,
    as_of: date | None = None,
) -> dict[str, float | None]:
    outcomes = _outcomes_for_anchor(
        stock_rows, benchmark_rows, anchor, horizons, as_of=as_of
    )
    return {
        key: _safe_float(value.get("alpha_percent")) if isinstance(value, Mapping) else None
        for key, value in outcomes.items()
    }


def _weighted_alpha(values: Mapping[str, Any], weights: Mapping[str, Any], clip: float) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for horizon, raw_weight in weights.items():
        value = _safe_float(values.get(str(horizon)))
        weight = _safe_float(raw_weight)
        if value is None or weight is None or weight <= 0:
            continue
        numerator += max(-clip, min(clip, value)) * weight
        denominator += weight
    return numerator / denominator if denominator else None


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.fmean(clean) if clean else None


def _weighted_mean(values: Iterable[tuple[float | None, float]]) -> float | None:
    clean = [
        (float(value), float(weight))
        for value, weight in values
        if value is not None
        and math.isfinite(float(value))
        and math.isfinite(float(weight))
        and float(weight) > 0
    ]
    denominator = sum(weight for _, weight in clean)
    return sum(value * weight for value, weight in clean) / denominator if denominator else None


def _hit_rate(values: Iterable[tuple[float | None, float]]) -> float | None:
    clean = [
        (float(value), float(weight))
        for value, weight in values
        if value is not None and float(weight) > 0
    ]
    denominator = sum(weight for _, weight in clean)
    return (
        sum((1.0 if value > 0 else 0.0) * weight for value, weight in clean)
        / denominator
        * 100.0
        if denominator
        else None
    )


def _available_horizon_weight(values: Mapping[str, Any], weights: Mapping[str, Any]) -> float:
    total = sum(max(0.0, float(_safe_float(weight) or 0.0)) for weight in weights.values())
    if total <= 0:
        return 0.0
    available = sum(
        max(0.0, float(_safe_float(weight) or 0.0))
        for horizon, weight in weights.items()
        if _safe_float(values.get(str(horizon))) is not None
    )
    return max(0.0, min(1.0, available / total))


def _normalized_sector_mapping(
    value: Mapping[str, Any] | None, default_benchmark: str
) -> dict[str, Any]:
    mapping = dict(value or {})
    benchmark = _ticker_symbol(mapping.get("benchmark")) or default_benchmark
    industry = _normal(mapping.get("industry"))
    sector = _normal(mapping.get("sector")) or "Broad market"
    confidence = _safe_float(mapping.get("mapping_confidence"))
    if confidence is None:
        confidence = 0.85 if industry and benchmark != default_benchmark else 0.25
    source = _normal(mapping.get("mapping_source")) or (
        "provider_sector" if industry and benchmark != default_benchmark else "broad_market_fallback"
    )
    reported_benchmark = benchmark
    reported_sector = sector
    if confidence < MIN_SECTOR_MAPPING_CONFIDENCE:
        benchmark = default_benchmark
        sector = "Broad market"
        source = "broad_market_low_confidence"
    return {
        **mapping,
        "industry": industry,
        "benchmark": benchmark,
        "sector": sector,
        "reported_benchmark": reported_benchmark,
        "reported_sector": reported_sector,
        "mapping_confidence": round(max(0.0, min(1.0, confidence)), 4),
        "mapping_source": source,
    }


def _alpha_score(alpha: float | None, config: Mapping[str, Any]) -> float:
    if alpha is None:
        return 50.0
    points = float(config.get("alpha_score_points_per_percent", 2.5))
    return max(0.0, min(100.0, 50.0 + alpha * points))


def _confidence_label(value: float, samples: int) -> str:
    if samples < 3 or value < 0.35:
        return "Low"
    if value < 0.7:
        return "Medium"
    return "High"


def history_trade_eligibility(record: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministically classify a historical observation and explain exclusions."""
    excluded: list[str] = []
    warnings: list[str] = []
    quality_weight = 1.0
    transaction_type = _normal(record.get("transaction_type")).casefold()
    ticker = _ticker_symbol(record.get("ticker"))
    asset_type = _normal(record.get("asset_type")).casefold()
    material = " ".join(
        _normal(record.get(field_name))
        for field_name in ("asset", "asset_type", "raw_row", "comment")
    ).casefold()
    identity = investor_identity(record)
    tx_date = _parse_date(record.get("transaction_date"))
    public_date = _public_date(record)
    reported_filed_date = _parse_date(record.get("filed_date"))

    def flagged(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return _normal(value).casefold() in {"1", "true", "yes", "on"}

    if transaction_type != "purchase":
        excluded.append("not_purchase")
    if not ticker:
        excluded.append("unresolved_ticker")
    if tx_date is None:
        excluded.append("invalid_transaction_date")
    if public_date is None:
        excluded.append("missing_public_date")
    if tx_date is not None and public_date is not None and public_date < tx_date:
        excluded.append("public_date_before_transaction")
    elif (
        tx_date is not None
        and reported_filed_date is not None
        and reported_filed_date < tx_date
    ):
        excluded.append("filed_date_before_transaction")
    if (
        flagged(record.get("is_synthetic_test"))
        or flagged(record.get("synthetic_test"))
        or flagged(record.get("is_temporary"))
        or bool(record.get("test_metadata"))
    ):
        excluded.append("synthetic_or_temporary")
    if record.get("equity_like") is not True:
        excluded.append("not_confidently_equity")
    if ticker in KNOWN_FUND_TICKERS or asset_type in {"ef", "etf"} or any(
        term in f" {material}" for term in FUND_TERMS
    ):
        excluded.append("fund_or_etf")
    nondiscretionary = sorted(
        {term for term in NONDISCRETIONARY_TERMS if term in material}
    )
    if nondiscretionary:
        excluded.append("nondiscretionary_or_managed")
    if identity.get("owner_category") == "Managed":
        excluded.append("managed_owner")

    parse_confidence = _normal(record.get("parse_confidence")).casefold()
    if parse_confidence == "low":
        excluded.append("low_parse_confidence")
    elif parse_confidence == "medium":
        quality_weight *= 0.80
        warnings.append("medium_parse_confidence")
    elif parse_confidence not in {"high"}:
        quality_weight *= 0.65
        warnings.append("missing_parse_confidence")

    intent = _normal(record.get("transaction_intent")).casefold()
    if intent == "likely_routine":
        excluded.append("likely_routine")
    elif intent in {"possibly_discretionary", "unclear"}:
        quality_weight *= 0.65
        warnings.append(f"transaction_intent_{intent}")

    identity_confidence = float(identity.get("identity_confidence") or 0.0)
    if identity_confidence < 0.40:
        quality_weight *= 0.45
        warnings.append("low_identity_confidence")
    elif identity_confidence < 0.70:
        quality_weight *= 0.75
        warnings.append("medium_identity_confidence")

    return {
        "eligible": not excluded,
        "excluded_reasons": excluded,
        "quality_warnings": warnings,
        "quality_weight": round(max(0.0, min(1.0, quality_weight)), 4),
        "nondiscretionary_terms": nondiscretionary,
        "identity": identity,
    }


def _history_trade_eligible(record: Mapping[str, Any]) -> bool:
    return bool(history_trade_eligibility(record).get("eligible"))


@dataclass
class InvestorEdgeRuntime:
    config: dict[str, Any]
    ai_dir: Path
    provider: MarketHistoryProvider
    profiles: dict[str, dict[str, Any]]
    observations: dict[str, dict[str, Any]] = field(default_factory=dict)
    backfill_processed_this_run: int = 0
    attempted_observation_keys: set[str] = field(default_factory=set)
    last_observation_key: str = ""
    observations_pruned_this_run: int = 0

    def __post_init__(self) -> None:
        # Old methodology versions and long-lived unavailable attempts must not
        # make the durable artifact grow without bound.
        self._prune_observations()

    @classmethod
    def create(
        cls,
        *,
        ai_dir: Path,
        session: requests.Session,
        alphavantage_api_key: str,
        finnhub_api_key: str,
        alphavantage_entitlement: str,
        request_timeout: tuple[float, float],
        config_path: Path | str | None = None,
    ) -> "InvestorEdgeRuntime":
        edge_config = load_config(config_path)
        profile_payload = _read_json(ai_dir / PROFILE_FILE)
        profiles = profile_payload.get("profiles", {}) if isinstance(profile_payload, dict) else {}
        if not isinstance(profiles, dict):
            profiles = {}
        observation_payload = _read_json(ai_dir / OBSERVATION_FILE)
        observations = (
            observation_payload.get("observations", {})
            if isinstance(observation_payload, dict)
            else {}
        )
        if not isinstance(observations, dict):
            observations = {}
        provider = MarketHistoryProvider(
            ai_dir=ai_dir,
            session=session,
            alphavantage_api_key=alphavantage_api_key,
            finnhub_api_key=finnhub_api_key,
            alphavantage_entitlement=alphavantage_entitlement,
            request_timeout=request_timeout,
            config=edge_config,
        )
        return cls(
            edge_config,
            ai_dir,
            provider,
            {str(k): dict(v) for k, v in profiles.items() if isinstance(v, dict)},
            {str(k): dict(v) for k, v in observations.items() if isinstance(v, dict)},
        )

    @property
    def enabled(self) -> bool:
        value = self.config.get("enabled", False)
        if isinstance(value, bool):
            return value
        return str(value).strip().casefold() in {"1", "true", "yes", "on"}

    @property
    def method_hash(self) -> str:
        return method_config_hash(self.config)

    @property
    def backfill_limit(self) -> int:
        return max(
            0,
            min(500, int(self.config.get("backfill_analysis_limit_per_run", 30))),
        )

    @property
    def observation_retention_limit(self) -> int:
        configured = self.config.get("observation_retention_limit")
        if configured is not None:
            return max(1, min(100_000, int(configured)))
        history = max(1, min(250, int(self.config.get("max_history_trades", 40))))
        investors = max(
            1, min(1_000, int(self.config.get("leaderboard_max_investors", 40)))
        )
        # Leave room for current candidates and durable unavailable-attempt
        # metadata in addition to the bounded leaderboard history.
        return max(100, min(100_000, history * investors + self.backfill_limit * 4))

    @staticmethod
    def _observation_has_outcomes(observation: Mapping[str, Any]) -> bool:
        return any(
            isinstance(detail, Mapping)
            for field_name in ("picker_outcomes", "followable_outcomes")
            for detail in (
                (observation.get(field_name) or {}).values()
                if isinstance(observation.get(field_name), Mapping)
                else ()
            )
        )

    def _prune_observations(self) -> None:
        limit = self.observation_retention_limit
        if len(self.observations) <= limit:
            return

        def retention_rank(item: tuple[str, Mapping[str, Any]]) -> tuple[Any, ...]:
            key, observation = item
            return (
                str(observation.get("method_hash") or "") == self.method_hash,
                str(observation.get("transaction_date") or ""),
                self._observation_has_outcomes(observation),
                str(observation.get("last_attempted_as_of") or ""),
                str(observation.get("updated_utc") or ""),
                key,
            )

        retained = sorted(self.observations.items(), key=retention_rank, reverse=True)[
            :limit
        ]
        removed = len(self.observations) - len(retained)
        self.observations = {str(key): dict(value) for key, value in retained}
        self.observations_pruned_this_run += removed

    def _save_observations(self) -> None:
        self._prune_observations()
        _atomic_json(
            self.ai_dir / OBSERVATION_FILE,
            {
                "version": EDGE_VERSION,
                "method_hash": self.method_hash,
                "generated_utc": _iso_utc(),
                "backfill": {
                    "limit_per_run": self.backfill_limit,
                    "processed_this_run": self.backfill_processed_this_run,
                    "last_observation_key": self.last_observation_key,
                    "retention_limit": self.observation_retention_limit,
                    "stored_observation_count": len(self.observations),
                    "pruned_this_run": self.observations_pruned_this_run,
                },
                "observations": self.observations,
            },
        )

    def _observation_key(
        self,
        item: Mapping[str, Any],
        *,
        benchmark: str,
    ) -> str:
        material = (
            self.method_hash,
            str(item.get("trade_id") or ""),
            _ticker_symbol(item.get("ticker")),
            str(_parse_date(item.get("transaction_date")) or ""),
            str(_public_date(item) or ""),
            str(_followable_anchor(item) or ""),
            benchmark,
            _normal(item.get("amount")),
        )
        digest = hashlib.sha256("\x1f".join(material).encode("utf-8")).hexdigest()[:32]
        return f"observation:{digest}"

    def _provider_daily(
        self,
        ticker: str,
        *,
        minimum_date: date | None,
        required_through: date | None,
    ) -> list[dict[str, Any]]:
        try:
            return self.provider.daily(
                ticker,
                minimum_date=minimum_date,
                required_through=required_through,
            )
        except TypeError as exc:
            # Preserve compatibility with existing provider adapters that predate
            # required-through coverage.
            if "required_through" not in str(exc):
                raise
            return self.provider.daily(ticker, minimum_date=minimum_date)

    @staticmethod
    def _visible_outcomes(
        outcomes: Mapping[str, Any],
        horizons: Sequence[int],
        as_of: date,
    ) -> dict[str, dict[str, Any] | None]:
        visible: dict[str, dict[str, Any] | None] = {}
        for horizon in horizons:
            key_h = str(horizon)
            detail = outcomes.get(key_h)
            exit_date = _parse_date(detail.get("exit_date")) if isinstance(detail, Mapping) else None
            visible[key_h] = dict(detail) if isinstance(detail, Mapping) and exit_date and exit_date <= as_of else None
        return visible

    def _observation_for_trade(
        self,
        item: Mapping[str, Any],
        *,
        key: str,
        sector: Mapping[str, Any],
        as_of: date,
        horizons: Sequence[int],
    ) -> tuple[dict[str, Any], str]:
        ticker = _ticker_symbol(item.get("ticker"))
        tx_date = _parse_date(item.get("transaction_date"))
        public_date = _public_date(item)
        followable_date = _followable_anchor(item)
        benchmark = _ticker_symbol(sector.get("benchmark")) or str(
            self.config.get("benchmark_default", "SPY")
        )
        observation_key = self._observation_key(item, benchmark=benchmark)
        cached = dict(self.observations.get(observation_key) or {})
        picker_cached = cached.get("picker_outcomes") or {}
        followable_cached = cached.get("followable_outcomes") or {}
        missing = [
            str(horizon)
            for horizon in horizons
            if not isinstance(picker_cached.get(str(horizon)), Mapping)
            or not isinstance(followable_cached.get(str(horizon)), Mapping)
        ]
        last_attempted_as_of = _parse_date(cached.get("last_attempted_as_of"))
        retry_after_as_of = _parse_date(cached.get("retry_after_as_of"))
        attempt_token = f"{observation_key}|{as_of.isoformat()}"
        can_attempt = (
            bool(missing)
            and attempt_token not in self.attempted_observation_keys
            and (last_attempted_as_of is None or as_of > last_attempted_as_of)
            and (retry_after_as_of is None or as_of >= retry_after_as_of)
            and self.backfill_processed_this_run < self.backfill_limit
            and ticker
            and tx_date is not None
            and public_date is not None
            and followable_date is not None
        )
        status = "cached" if cached else "deferred"
        if can_attempt:
            self.attempted_observation_keys.add(attempt_token)
            self.backfill_processed_this_run += 1
            minimum_date = min(tx_date, public_date) - timedelta(days=10)
            stock_rows = self._provider_daily(
                ticker, minimum_date=minimum_date, required_through=as_of
            )
            benchmark_rows = self._provider_daily(
                benchmark, minimum_date=minimum_date, required_through=as_of
            )
            if stock_rows and benchmark_rows:
                picker_new = _outcomes_for_anchor(
                    stock_rows, benchmark_rows, tx_date, horizons, as_of=as_of
                )
                followable_new = _outcomes_for_anchor(
                    stock_rows, benchmark_rows, followable_date, horizons, as_of=as_of
                )
                merged_picker = {
                    **{str(k): dict(v) for k, v in picker_cached.items() if isinstance(v, Mapping)},
                    **{str(k): dict(v) for k, v in picker_new.items() if isinstance(v, Mapping)},
                }
                merged_followable = {
                    **{str(k): dict(v) for k, v in followable_cached.items() if isinstance(v, Mapping)},
                    **{str(k): dict(v) for k, v in followable_new.items() if isinstance(v, Mapping)},
                }
                cached = {
                    **cached,
                    "observation_key": observation_key,
                    "version": EDGE_VERSION,
                    "method_hash": self.method_hash,
                    "investor_key": key,
                    "trade_id": str(item.get("trade_id") or ""),
                    "ticker": ticker,
                    "transaction_date": tx_date.isoformat(),
                    "public_disclosure_date": public_date.isoformat(),
                    "followable_anchor_date": followable_date.isoformat(),
                    "benchmark": benchmark,
                    "sector": dict(sector),
                    "picker_outcomes": merged_picker,
                    "followable_outcomes": merged_followable,
                    "last_attempted_as_of": as_of.isoformat(),
                    "retry_after_as_of": "",
                    "consecutive_unavailable_attempts": 0,
                    "last_attempt_status": "available",
                    "updated_utc": _iso_utc(),
                }
                self.observations[observation_key] = cached
                self.last_observation_key = observation_key
                self._save_observations()
                status = "backfilled"
            else:
                failures = int(cached.get("consecutive_unavailable_attempts") or 0) + 1
                retry_days = min(30, 2 ** min(failures, 4))
                cached = {
                    **cached,
                    "observation_key": observation_key,
                    "version": EDGE_VERSION,
                    "method_hash": self.method_hash,
                    "investor_key": key,
                    "trade_id": str(item.get("trade_id") or ""),
                    "ticker": ticker,
                    "transaction_date": tx_date.isoformat(),
                    "public_disclosure_date": public_date.isoformat(),
                    "followable_anchor_date": followable_date.isoformat(),
                    "benchmark": benchmark,
                    "sector": dict(sector),
                    "picker_outcomes": {
                        str(k): dict(v)
                        for k, v in picker_cached.items()
                        if isinstance(v, Mapping)
                    },
                    "followable_outcomes": {
                        str(k): dict(v)
                        for k, v in followable_cached.items()
                        if isinstance(v, Mapping)
                    },
                    "last_attempted_as_of": as_of.isoformat(),
                    "retry_after_as_of": (as_of + timedelta(days=retry_days)).isoformat(),
                    "consecutive_unavailable_attempts": failures,
                    "last_attempt_status": "unavailable",
                    "updated_utc": _iso_utc(),
                }
                self.observations[observation_key] = cached
                self.last_observation_key = observation_key
                self._save_observations()
                status = "unavailable"
        visible = {
            **cached,
            "observation_key": observation_key,
            "investor_key": key,
            "picker_outcomes": self._visible_outcomes(
                cached.get("picker_outcomes") or {}, horizons, as_of
            ),
            "followable_outcomes": self._visible_outcomes(
                cached.get("followable_outcomes") or {}, horizons, as_of
            ),
        }
        visible_missing = any(
            not isinstance((visible.get("picker_outcomes") or {}).get(str(horizon)), Mapping)
            or not isinstance((visible.get("followable_outcomes") or {}).get(str(horizon)), Mapping)
            for horizon in horizons
        )
        has_visible_outcome = self._observation_has_outcomes(visible)
        if (
            cached
            and visible_missing
            and not has_visible_outcome
            and str(cached.get("last_attempt_status") or "") == "unavailable"
        ):
            status = "unavailable"
        elif cached and visible_missing:
            status = "partial_cached"
        elif cached and status != "backfilled":
            status = "cached"
        return visible, status

    def profile_for_trade(
        self,
        trade: Mapping[str, Any],
        all_transactions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        identity = investor_identity(trade)
        key = str(identity.get("investor_key") or "")
        if not key or not self.enabled:
            return neutral_profile(trade, reason="Investor Edge disabled or filer identity unavailable")
        current_tx_date = _parse_date(trade.get("transaction_date")) or _utc_now().date()
        as_of = (
            _parse_date(trade.get("analyzed_at_utc"))
            or _parse_date(trade.get("observed_at_utc"))
            or _parse_date(trade.get("filed_date"))
            or _utc_now().date()
        )
        current_ticker = _ticker_symbol(trade.get("ticker"))
        current_trade_id = str(trade.get("trade_id") or "")
        compatible = _matching_investor_records(trade, all_transactions)
        history = [
            item
            for item in compatible
            if (not current_trade_id or str(item.get("trade_id") or "") != current_trade_id)
            and (_parse_date(item.get("transaction_date")) or current_tx_date) < current_tx_date
            and (_public_date(item) is None or _public_date(item) < as_of)
        ]
        profile = self._profile(
            filer=str(trade.get("filer") or ""),
            owner=str(trade.get("owner") or ""),
            key=key,
            history=history,
            current_ticker=current_ticker,
            as_of=as_of,
            identity=identity,
        )
        public_date = _public_date(trade)
        profile = dict(profile)
        profile["current_public_disclosure_date"] = (
            public_date.isoformat() if public_date else ""
        )
        profile["current_followable_anchor_date"] = (
            _followable_anchor(trade).isoformat() if _followable_anchor(trade) else ""
        )
        profile["current_disclosure_lag_days"] = (
            (public_date - current_tx_date).days
            if public_date is not None and public_date >= current_tx_date
            else None
        )
        return profile

    def profile_for_investor(
        self,
        key: str,
        records: Sequence[Mapping[str, Any]],
        *,
        as_of: date | None = None,
    ) -> dict[str, Any]:
        as_of = as_of or _utc_now().date()
        seeds = [item for item in records if investor_key(item) == key]
        compatible = _matching_investor_records(seeds[-1], records) if seeds else []
        matching = [
            item
            for item in compatible
            if (_parse_date(item.get("transaction_date")) or as_of) <= as_of
            and (_public_date(item) is None or _public_date(item) <= as_of)
        ]
        latest = max(
            matching,
            key=lambda item: _parse_date(item.get("transaction_date")) or date.min,
            default={},
        )
        identity_record = next(
            (item for item in reversed(matching) if investor_key(item) == key), latest
        )
        identity = investor_identity(identity_record) if identity_record else {
            "investor_key": key,
            "filer": "",
            "owner": "Other",
            "identity_confidence": 0.0,
            "identity_confidence_label": "Low",
            "identity_fallback": True,
        }
        return self._profile(
            filer=str(latest.get("filer") or ""),
            owner=str(latest.get("owner") or ""),
            key=key,
            history=matching,
            current_ticker="",
            as_of=as_of,
            identity=identity,
        )

    @staticmethod
    def _persisted_profile_identity(profile: Mapping[str, Any]) -> dict[str, Any]:
        raw_identity = profile.get("identity") or {}
        identity = dict(raw_identity) if isinstance(raw_identity, Mapping) else {}
        filer = _normal(profile.get("filer") or identity.get("filer"))
        if not identity.get("filer_name_key"):
            identity["filer_name_key"] = _identity_part(filer)
        owner_value = (
            profile.get("owner_raw")
            or identity.get("owner_raw")
            or profile.get("owner")
            or identity.get("owner")
        )
        if not identity.get("owner_key"):
            identity["owner_key"] = _owner_identity(owner_value).get("owner_key")
        if not identity.get("filer_stable_id"):
            filer_key = str(identity.get("filer_key") or "")
            if filer_key.startswith("id-"):
                identity["filer_stable_id"] = filer_key[3:]
        return identity

    def _previous_profile(
        self,
        key: str,
        target_identity: Mapping[str, Any],
        *,
        allow_name_bridge: bool,
    ) -> tuple[str, dict[str, Any]]:
        exact = self.profiles.get(key)
        if isinstance(exact, Mapping):
            return key, dict(exact)

        target_name = str(target_identity.get("filer_name_key") or "")
        target_owner = str(target_identity.get("owner_key") or "")
        target_stable = str(target_identity.get("filer_stable_id") or "")
        described: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for profile_key, profile_value in self.profiles.items():
            if not isinstance(profile_value, Mapping):
                continue
            profile = dict(profile_value)
            identity = self._persisted_profile_identity(profile)
            if str(identity.get("owner_key") or "") != target_owner:
                continue
            described.append((str(profile_key), profile, identity))

        if target_stable:
            stable_matches = [
                candidate
                for candidate in described
                if str(candidate[2].get("filer_stable_id") or "") == target_stable
            ]
            if stable_matches:
                profile_key, profile, _ = stable_matches[-1]
                return profile_key, profile
            conflicting = any(
                target_name
                and str(identity.get("filer_name_key") or "") == target_name
                and identity.get("filer_stable_id")
                and str(identity.get("filer_stable_id")) != target_stable
                for _, _, identity in described
            )
            if allow_name_bridge and not conflicting:
                name_only = [
                    candidate
                    for candidate in described
                    if target_name
                    and str(candidate[2].get("filer_name_key") or "") == target_name
                    and not candidate[2].get("filer_stable_id")
                ]
                if name_only:
                    profile_key, profile, _ = name_only[-1]
                    return profile_key, profile
            return "", {}

        same_name = [
            candidate
            for candidate in described
            if target_name
            and str(candidate[2].get("filer_name_key") or "") == target_name
        ]
        stable_ids = {
            str(identity.get("filer_stable_id") or "")
            for _, _, identity in same_name
            if identity.get("filer_stable_id")
        }
        if allow_name_bridge and len(stable_ids) <= 1 and same_name:
            profile_key, profile, _ = same_name[-1]
            return profile_key, profile
        name_only = [candidate for candidate in same_name if not candidate[2].get("filer_stable_id")]
        if name_only:
            profile_key, profile, _ = name_only[-1]
            return profile_key, profile
        return "", {}

    def _profile(
        self,
        *,
        filer: str,
        owner: str,
        key: str,
        history: Sequence[Mapping[str, Any]],
        current_ticker: str,
        as_of: date | None = None,
        identity: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        as_of = as_of or _utc_now().date()
        identity_payload = dict(identity or investor_identity({"filer": filer, "owner": owner}))
        identity_payload["investor_key"] = key
        max_history = max(0, min(250, int(self.config.get("max_history_trades", 40))))
        history_sorted = sorted(
            history,
            key=lambda item: _parse_date(item.get("transaction_date")) or date.min,
            reverse=True,
        )
        assessed = [(item, history_trade_eligibility(item)) for item in history_sorted]
        eligible_pairs = [pair for pair in assessed if pair[1].get("eligible")][:max_history]
        excluded_pairs = [pair for pair in assessed if not pair[1].get("eligible")]
        default_benchmark = _ticker_symbol(self.config.get("benchmark_default")) or "SPY"
        current_sector = (
            _normalized_sector_mapping(self.provider.sector(current_ticker), default_benchmark)
            if current_ticker
            else {
                "benchmark": "",
                "sector": "",
                "industry": "",
                "mapping_confidence": 0.0,
                "mapping_source": "no_current_candidate",
            }
        )
        horizons = []
        for value in self.config.get("horizons") or [5, 20, 60, 120]:
            horizon = int(value)
            if horizon > 0 and horizon not in horizons:
                horizons.append(horizon)
        horizon_weights = self.config.get("horizon_weights") or {"5": .15, "20": .30, "60": .35, "120": .20}
        clip = float(self.config.get("alpha_clip_percent", 25.0))
        trade_results: list[dict[str, Any]] = []

        for item, assessment in excluded_pairs[:max_history]:
            tx_date = _parse_date(item.get("transaction_date"))
            public_date = _public_date(item)
            reported_filed_date = _parse_date(item.get("filed_date"))
            item_identity = dict(assessment.get("identity") or {})
            trade_results.append(
                {
                    "trade_id": str(item.get("trade_id") or ""),
                    "ticker": _ticker_symbol(item.get("ticker")),
                    "asset": _normal(item.get("asset")),
                    "owner": str(item_identity.get("owner_raw") or item.get("owner") or ""),
                    "transaction_date": tx_date.isoformat() if tx_date else "",
                    "filed_date": reported_filed_date.isoformat() if reported_filed_date else "",
                    "public_disclosure_date": public_date.isoformat() if public_date else "",
                    "followable_anchor_date": (
                        _followable_anchor(item).isoformat() if _followable_anchor(item) else ""
                    ),
                    "observed_at_utc": str(item.get("observed_at_utc") or ""),
                    "amount": str(item.get("amount") or ""),
                    "source_url": str(item.get("source_url") or ""),
                    "status": "excluded",
                    "eligible": False,
                    "counts_toward_edge": False,
                    "excluded_reasons": list(assessment.get("excluded_reasons") or []),
                    "quality_warnings": list(assessment.get("quality_warnings") or []),
                    "quality_weight": float(assessment.get("quality_weight") or 0.0),
                    "identity": item_identity,
                    "picker_alpha_by_horizon": {str(h): None for h in horizons},
                    "followable_alpha_by_horizon": {str(h): None for h in horizons},
                    "picker_outcomes": {str(h): None for h in horizons},
                    "followable_outcomes": {str(h): None for h in horizons},
                }
            )

        for item, assessment in eligible_pairs:
            ticker = _ticker_symbol(item.get("ticker"))
            tx_date = _parse_date(item.get("transaction_date"))
            public_date = _public_date(item)
            reported_filed_date = _parse_date(item.get("filed_date"))
            if not ticker or tx_date is None or public_date is None:
                continue
            sector = _normalized_sector_mapping(self.provider.sector(ticker), default_benchmark)
            benchmark = str(sector.get("benchmark") or default_benchmark)
            observation, observation_status = self._observation_for_trade(
                item,
                key=key,
                sector=sector,
                as_of=as_of,
                horizons=horizons,
            )
            picker_outcomes = observation.get("picker_outcomes") or {}
            followable_outcomes = observation.get("followable_outcomes") or {}
            tx_alphas = {
                str(horizon): _safe_float(
                    (picker_outcomes.get(str(horizon)) or {}).get("alpha_percent")
                )
                for horizon in horizons
            }
            disclosure_alphas = {
                str(horizon): _safe_float(
                    (followable_outcomes.get(str(horizon)) or {}).get("alpha_percent")
                )
                for horizon in horizons
            }
            picker = _weighted_alpha(tx_alphas, horizon_weights, clip)
            followable = _weighted_alpha(disclosure_alphas, horizon_weights, clip)
            quality_weight = float(assessment.get("quality_weight") or 0.0)
            picker_coverage = _available_horizon_weight(tx_alphas, horizon_weights)
            followable_coverage = _available_horizon_weight(disclosure_alphas, horizon_weights)
            disclosure_lag = (public_date - tx_date).days
            picker_entry_price = next(
                (
                    _safe_float((picker_outcomes.get(str(h)) or {}).get("stock_entry_price"))
                    for h in horizons
                    if _safe_float((picker_outcomes.get(str(h)) or {}).get("stock_entry_price"))
                    is not None
                ),
                None,
            )
            followable_entry_price = next(
                (
                    _safe_float((followable_outcomes.get(str(h)) or {}).get("stock_entry_price"))
                    for h in horizons
                    if _safe_float((followable_outcomes.get(str(h)) or {}).get("stock_entry_price"))
                    is not None
                ),
                None,
            )
            item_identity = dict(assessment.get("identity") or {})
            trade_results.append(
                {
                    "trade_id": str(item.get("trade_id") or ""),
                    "ticker": ticker,
                    "asset": _normal(item.get("asset")),
                    "owner": str(item_identity.get("owner_raw") or item.get("owner") or ""),
                    "transaction_date": tx_date.isoformat(),
                    "filed_date": reported_filed_date.isoformat() if reported_filed_date else "",
                    "public_disclosure_date": public_date.isoformat(),
                    "followable_anchor_date": (
                        _followable_anchor(item).isoformat() if _followable_anchor(item) else ""
                    ),
                    "observed_at_utc": str(item.get("observed_at_utc") or ""),
                    "disclosure_lag_days": disclosure_lag,
                    "amount": str(item.get("amount") or ""),
                    "source_url": str(item.get("source_url") or ""),
                    "benchmark": benchmark,
                    "sector": sector.get("sector") or "Broad market",
                    "sector_mapping": sector,
                    "status": (
                        "partial_scored"
                        if observation_status == "partial_cached"
                        and (picker is not None or followable is not None)
                        else "scored"
                        if picker is not None or followable is not None
                        else observation_status
                    ),
                    "observation_status": observation_status,
                    "observation_key": str(observation.get("observation_key") or ""),
                    "eligible": True,
                    "counts_toward_edge": followable is not None,
                    "excluded_reasons": [],
                    "quality_warnings": list(assessment.get("quality_warnings") or []),
                    "quality_weight": round(quality_weight, 4),
                    "identity": item_identity,
                    "transaction_entry_price": picker_entry_price,
                    "disclosure_entry_price": followable_entry_price,
                    "picker_alpha_by_horizon": tx_alphas,
                    "followable_alpha_by_horizon": disclosure_alphas,
                    "picker_stock_return_by_horizon": {
                        str(h): _safe_float((picker_outcomes.get(str(h)) or {}).get("stock_return_percent"))
                        for h in horizons
                    },
                    "picker_benchmark_return_by_horizon": {
                        str(h): _safe_float((picker_outcomes.get(str(h)) or {}).get("benchmark_return_percent"))
                        for h in horizons
                    },
                    "followable_stock_return_by_horizon": {
                        str(h): _safe_float((followable_outcomes.get(str(h)) or {}).get("stock_return_percent"))
                        for h in horizons
                    },
                    "followable_benchmark_return_by_horizon": {
                        str(h): _safe_float((followable_outcomes.get(str(h)) or {}).get("benchmark_return_percent"))
                        for h in horizons
                    },
                    "picker_outcomes": picker_outcomes,
                    "followable_outcomes": followable_outcomes,
                    "picker_horizon_coverage": round(picker_coverage, 4),
                    "followable_horizon_coverage": round(followable_coverage, 4),
                    "effective_sample_weight": round(quality_weight * followable_coverage, 4),
                    "picker_weighted_alpha": round(picker, 4) if picker is not None else None,
                    "followable_weighted_alpha": round(followable, 4) if followable is not None else None,
                }
            )

        trade_results.sort(
            key=lambda item: (str(item.get("transaction_date") or ""), str(item.get("trade_id") or "")),
            reverse=True,
        )
        eligible_results = [item for item in trade_results if item.get("eligible") is True]
        samples = [item for item in eligible_results if item.get("followable_weighted_alpha") is not None]
        n = len(samples)
        considered = len(history_sorted)
        eligible_count = len(eligible_pairs)
        coverage = n / eligible_count if eligible_count else 0.0
        effective_n = sum(float(item.get("effective_sample_weight") or 0.0) for item in samples)
        followable_mean = _weighted_mean(
            (
                _safe_float(item.get("followable_weighted_alpha")),
                float(item.get("effective_sample_weight") or 0.0),
            )
            for item in samples
        )
        picker_mean = _weighted_mean(
            (
                _safe_float(item.get("picker_weighted_alpha")),
                float(item.get("quality_weight") or 0.0)
                * float(item.get("picker_horizon_coverage") or 0.0),
            )
            for item in eligible_results
        )

        horizon_means: dict[str, float | None] = {}
        picker_horizon_means: dict[str, float | None] = {}
        followable_hit_rates: dict[str, float | None] = {}
        picker_hit_rates: dict[str, float | None] = {}
        for horizon in horizons:
            key_h = str(horizon)
            horizon_means[key_h] = _weighted_mean(
                (
                    _safe_float((item.get("followable_alpha_by_horizon") or {}).get(key_h)),
                    float(item.get("quality_weight") or 0.0),
                )
                for item in eligible_results
            )
            picker_horizon_means[key_h] = _weighted_mean(
                (
                    _safe_float((item.get("picker_alpha_by_horizon") or {}).get(key_h)),
                    float(item.get("quality_weight") or 0.0),
                )
                for item in eligible_results
            )
            followable_hit_rates[key_h] = _hit_rate(
                (
                    _safe_float((item.get("followable_alpha_by_horizon") or {}).get(key_h)),
                    float(item.get("quality_weight") or 0.0),
                )
                for item in eligible_results
            )
            picker_hit_rates[key_h] = _hit_rate(
                (
                    _safe_float((item.get("picker_alpha_by_horizon") or {}).get(key_h)),
                    float(item.get("quality_weight") or 0.0),
                )
                for item in eligible_results
            )

        weighted_followable_hit_rate = _hit_rate(
            (
                _safe_float(item.get("followable_weighted_alpha")),
                float(item.get("effective_sample_weight") or 0.0),
            )
            for item in samples
        )
        weighted_picker_hit_rate = _hit_rate(
            (
                _safe_float(item.get("picker_weighted_alpha")),
                float(item.get("quality_weight") or 0.0)
                * float(item.get("picker_horizon_coverage") or 0.0),
            )
            for item in eligible_results
        )
        hit_rate = weighted_followable_hit_rate if weighted_followable_hit_rate is not None else 50.0

        consistency_weight = sum(float(item.get("effective_sample_weight") or 0.0) for item in samples)
        variance = (
            sum(
                float(item.get("effective_sample_weight") or 0.0)
                * (float(item.get("followable_weighted_alpha") or 0.0) - float(followable_mean or 0.0)) ** 2
                for item in samples
            )
            / consistency_weight
            if consistency_weight and followable_mean is not None
            else 0.0
        )
        stdev = math.sqrt(max(0.0, variance))
        if followable_mean is None:
            consistency_score = 50.0
        else:
            consistency_score = max(0.0, min(100.0, 50.0 + 10.0 * followable_mean / (stdev + 2.0)))

        sector_prior = max(0.0, float(self.config.get("sector_confidence_prior_trades", 4)))
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in samples:
            mapping = item.get("sector_mapping") or {}
            if (
                str(mapping.get("sector") or "") == "Broad market"
                or float(mapping.get("mapping_confidence") or 0.0) < 0.50
                or str(item.get("benchmark") or "") == default_benchmark
            ):
                continue
            grouped.setdefault(str(item.get("benchmark") or ""), []).append(item)
        sector_performance: list[dict[str, Any]] = []
        for benchmark, group in sorted(grouped.items()):
            sector_effective_n = sum(float(item.get("effective_sample_weight") or 0.0) for item in group)
            sector_alpha = _weighted_mean(
                (
                    _safe_float(item.get("followable_weighted_alpha")),
                    float(item.get("effective_sample_weight") or 0.0),
                )
                for item in group
            )
            mapping_confidence = _weighted_mean(
                (
                    _safe_float((item.get("sector_mapping") or {}).get("mapping_confidence")),
                    float(item.get("effective_sample_weight") or 0.0),
                )
                for item in group
            ) or 0.0
            sector_confidence = (
                sector_effective_n / (sector_effective_n + sector_prior)
                if sector_effective_n and sector_prior >= 0
                else (1.0 if sector_effective_n else 0.0)
            ) * mapping_confidence
            raw_sector_score = _alpha_score(sector_alpha, self.config)
            shrunk_sector_score = 50.0 + sector_confidence * (raw_sector_score - 50.0)
            sector_performance.append(
                {
                    "sector": str((group[0].get("sector_mapping") or {}).get("sector") or ""),
                    "benchmark": benchmark,
                    "sample_count": len(group),
                    "effective_sample_count": round(sector_effective_n, 4),
                    "followable_alpha": round(sector_alpha, 2) if sector_alpha is not None else None,
                    "hit_rate_percent": round(
                        _hit_rate(
                            (
                                _safe_float(item.get("followable_weighted_alpha")),
                                float(item.get("effective_sample_weight") or 0.0),
                            )
                            for item in group
                        )
                        or 0.0,
                        1,
                    ),
                    "raw_score": round(raw_sector_score, 1),
                    "confidence": round(sector_confidence, 4),
                    "score": round(max(0.0, min(100.0, shrunk_sector_score)), 1),
                }
            )
        sector_performance.sort(
            key=lambda item: (
                float(item.get("score") or 50.0),
                float(item.get("effective_sample_count") or 0.0),
                str(item.get("sector") or ""),
            ),
            reverse=True,
        )
        strongest_sector = dict(sector_performance[0]) if sector_performance else {}
        current_sector_record = next(
            (
                item
                for item in sector_performance
                if item.get("benchmark") == current_sector.get("benchmark")
            ),
            None,
        )
        if (
            current_ticker
            and current_sector_record
            and str(current_sector.get("sector") or "") != "Broad market"
            and float(current_sector.get("mapping_confidence") or 0.0) >= 0.50
        ):
            sector_score = float(current_sector_record.get("score") or 50.0)
            sector_confidence = float(current_sector_record.get("confidence") or 0.0)
            sector_samples = grouped.get(str(current_sector.get("benchmark") or ""), [])
        else:
            sector_score = 50.0
            sector_confidence = 0.0
            sector_samples = []

        followable_score = _alpha_score(followable_mean, self.config)
        picker_score = _alpha_score(picker_mean, self.config)
        weights = self.config.get("edge_weights") or {}
        raw_edge = (
            followable_score * float(weights.get("followable_alpha", 0.45))
            + picker_score * float(weights.get("picker_alpha", 0.20))
            + hit_rate * float(weights.get("hit_rate", 0.15))
            + consistency_score * float(weights.get("consistency", 0.10))
            + sector_score * float(weights.get("sector_skill", 0.10))
        )
        weight_sum = sum(float(weights.get(name, 0.0)) for name in ("followable_alpha", "picker_alpha", "hit_rate", "consistency", "sector_skill"))
        raw_edge = raw_edge / weight_sum if weight_sum else 50.0

        prior = max(0.0, float(self.config.get("confidence_prior_trades", 8)))
        minimum = max(1, int(self.config.get("minimum_completed_trades", 3)))
        confidence = effective_n / (effective_n + prior) if effective_n else 0.0
        confidence *= min(1.0, coverage / 0.60) if coverage else 0.0
        confidence *= min(1.0, effective_n / minimum)
        confidence *= float(identity_payload.get("identity_confidence") or 0.0)
        adjusted_edge = 50.0 + confidence * (raw_edge - 50.0)
        adjusted_edge = max(0.0, min(100.0, adjusted_edge))
        max_modifier = max(
            0,
            min(MAX_MODIFIER_LIMIT, int(self.config.get("max_modifier", MAX_MODIFIER_LIMIT))),
        )
        modifier = int(round((adjusted_edge - 50.0) / 50.0 * max_modifier))
        modifier = max(-max_modifier, min(max_modifier, modifier))
        disclosure_lags = [
            int(item.get("disclosure_lag_days") or 0)
            for item in eligible_results
            if item.get("disclosure_lag_days") is not None
        ]
        excluded_reason_counts = Counter(
            reason
            for _, assessment in excluded_pairs
            for reason in (assessment.get("excluded_reasons") or [])
        )

        pending_trade_count = sum(
            item.get("observation_status")
            in {"deferred", "unavailable", "partial_cached"}
            for item in eligible_results
        )
        profile = {
            "version": EDGE_VERSION,
            "method_hash": self.method_hash,
            "config_version": self.config.get("version"),
            "generated_utc": _iso_utc(),
            "as_of_date": as_of.isoformat(),
            "investor_key": key,
            "filer": filer,
            "owner": str(identity_payload.get("owner") or owner),
            "owner_raw": str(identity_payload.get("owner_raw") or owner),
            "identity": identity_payload,
            "identity_confidence": round(float(identity_payload.get("identity_confidence") or 0.0), 4),
            "identity_confidence_label": str(identity_payload.get("identity_confidence_label") or "Low"),
            "edge_score": round(adjusted_edge, 1),
            "raw_edge_score": round(raw_edge, 1),
            "modifier": modifier,
            "confidence": round(confidence, 4),
            "confidence_label": _confidence_label(confidence, n),
            "sample_count": n,
            "effective_sample_count": round(effective_n, 4),
            "considered_trade_count": considered,
            "eligible_trade_count": eligible_count,
            "excluded_trade_count": len(excluded_pairs),
            "excluded_reason_counts": dict(sorted(excluded_reason_counts.items())),
            "coverage": round(coverage, 4),
            "horizon_coverage": round(effective_n / n, 4) if n else 0.0,
            "followable_alpha": round(followable_mean, 2) if followable_mean is not None else None,
            "picker_alpha": round(picker_mean, 2) if picker_mean is not None else None,
            "followable_alpha_by_horizon": {
                key_h: round(value, 2) if value is not None else None for key_h, value in horizon_means.items()
            },
            "picker_alpha_by_horizon": {
                key_h: round(value, 2) if value is not None else None for key_h, value in picker_horizon_means.items()
            },
            "followable_hit_rate_by_horizon": {
                key_h: round(value, 1) if value is not None else None
                for key_h, value in followable_hit_rates.items()
            },
            "picker_hit_rate_by_horizon": {
                key_h: round(value, 1) if value is not None else None
                for key_h, value in picker_hit_rates.items()
            },
            "weighted_followable_hit_rate_percent": (
                round(weighted_followable_hit_rate, 1)
                if weighted_followable_hit_rate is not None
                else None
            ),
            "weighted_picker_hit_rate_percent": (
                round(weighted_picker_hit_rate, 1) if weighted_picker_hit_rate is not None else None
            ),
            "hit_rate_percent": round(hit_rate, 1),
            "consistency_score": round(consistency_score, 1),
            "sector_skill_score": round(sector_score, 1),
            "sector_skill_confidence": round(sector_confidence, 4),
            "sector_comparable_count": len(sector_samples),
            "current_sector": current_sector,
            "sector_performance": sector_performance,
            "strongest_sector": strongest_sector,
            "average_disclosure_lag_days": round(statistics.fmean(disclosure_lags), 1) if disclosure_lags else None,
            "median_disclosure_lag_days": round(float(statistics.median(disclosure_lags)), 1) if disclosure_lags else None,
            "backfill_processed_this_run": self.backfill_processed_this_run,
            "backfill_limit_per_run": self.backfill_limit,
            "backfill_pending_trade_count": pending_trade_count,
            "profile_status": "partial" if pending_trade_count else "complete",
            "methodology": {
                "benchmarking": "Sector ETF when Finnhub industry data is available; otherwise SPY",
                "anchors": ["transaction_date", "first_trading_session_after_public_observation"],
                "horizons_trading_days": horizons,
                "horizon_weights": dict(horizon_weights),
                "edge_weights": dict(weights),
                "alpha_clip_percent": clip,
                "alpha_score_points_per_percent": float(
                    self.config.get("alpha_score_points_per_percent", 2.5)
                ),
                "confidence_prior_trades": prior,
                "sector_confidence_prior_trades": sector_prior,
                "modifier_range": [-max_modifier, max_modifier],
                "small_sample_shrinkage": True,
                "as_of_cutoff": as_of.isoformat(),
                "method_hash": self.method_hash,
            },
            "trade_results": trade_results,
            "data_errors": self.provider.errors[-10:],
        }
        refresh_incomplete = any(
            item.get("observation_status")
            in {"deferred", "unavailable", "partial_cached"}
            for item in eligible_results
        )
        if current_ticker:
            # Candidate profiles are time-censored and sector-specific. They are
            # returned to the analysis but never replace the global last-good profile.
            return profile
        target_name = str(identity_payload.get("filer_name_key") or "")
        target_owner = str(identity_payload.get("owner_key") or "")
        target_stable = str(identity_payload.get("filer_stable_id") or "")
        history_identities = [investor_identity(item) for item in history]
        allow_name_bridge = any(
            str(item_identity.get("filer_name_key") or "") == target_name
            and str(item_identity.get("owner_key") or "") == target_owner
            and bool(item_identity.get("filer_stable_id")) != bool(target_stable)
            for item_identity in history_identities
        )
        previous_key, previous = self._previous_profile(
            key,
            identity_payload,
            allow_name_bridge=allow_name_bridge,
        )
        previous_samples = int(previous.get("sample_count") or 0)
        previous_effective = float(previous.get("effective_sample_count") or 0.0)
        previous_horizon_coverage = float(previous.get("horizon_coverage") or 0.0)
        previous_as_of = _parse_date(previous.get("as_of_date"))
        historical_cutoff = as_of < _utc_now().date()
        previous_within_cutoff = (
            previous_as_of <= as_of
            if previous_as_of is not None
            else not historical_cutoff
        )
        current_horizon_coverage = effective_n / n if n else 0.0
        previous_has_effective = previous.get("effective_sample_count") is not None
        previous_is_richer = (
            previous_effective > effective_n + 1e-9
            or (
                abs(previous_effective - effective_n) <= 1e-9
                and previous_horizon_coverage > current_horizon_coverage + 1e-9
            )
            or (not previous_has_effective and previous_samples > n)
        )
        if (
            refresh_incomplete
            and previous_is_richer
            and previous_within_cutoff
            and str(previous.get("method_hash") or "") == self.method_hash
        ):
            preserved = dict(previous)
            preserved["profile_status"] = "stale_last_good"
            preserved["investor_key"] = key
            preserved["identity"] = {
                **(
                    dict(preserved.get("identity") or {})
                    if isinstance(preserved.get("identity"), Mapping)
                    else {}
                ),
                **identity_payload,
                "investor_key": key,
            }
            preserved["last_refresh_attempt_utc"] = _iso_utc()
            preserved["data_errors"] = self.provider.errors[-10:]
            self.profiles[key] = preserved
            if previous_key and previous_key != key:
                self.profiles.pop(previous_key, None)
            return preserved
        self.profiles[key] = profile
        if previous_key and previous_key != key:
            self.profiles.pop(previous_key, None)
        return profile

    def refresh_leaderboard(
        self,
        transactions: Sequence[Mapping[str, Any]],
        *,
        as_of: date | None = None,
    ) -> list[dict[str, Any]]:
        eligible = [item for item in transactions if _history_trade_eligible(item)]
        identified = [(item, investor_identity(item)) for item in eligible]
        stable_by_name_owner: dict[tuple[str, str], set[str]] = {}
        for _, identity in identified:
            group = (
                str(identity.get("filer_name_key") or ""),
                str(identity.get("owner_key") or ""),
            )
            stable = str(identity.get("filer_stable_id") or "")
            if group[0] and stable:
                stable_by_name_owner.setdefault(group, set()).add(stable)

        canonical_keys: list[str] = []
        for _, identity in identified:
            key = str(identity.get("investor_key") or "")
            if not identity.get("filer_stable_id"):
                group = (
                    str(identity.get("filer_name_key") or ""),
                    str(identity.get("owner_key") or ""),
                )
                stable_ids = stable_by_name_owner.get(group, set())
                if len(stable_ids) == 1:
                    key = f"id-{next(iter(stable_ids))}|{group[1]}"
            canonical_keys.append(key)
        counts = Counter(canonical_keys)
        keys = [key for key, _ in counts.most_common(int(self.config.get("leaderboard_max_investors", 40))) if key]
        leaderboard = [
            self.profile_for_investor(key, transactions, as_of=as_of) for key in keys
        ]
        leaderboard.sort(key=lambda item: (float(item.get("edge_score") or 50), int(item.get("sample_count") or 0)), reverse=True)
        return leaderboard

    def save(self, leaderboard: Sequence[Mapping[str, Any]] | None = None) -> None:
        self._save_observations()
        _atomic_json(
            self.ai_dir / PROFILE_FILE,
            {
                "version": EDGE_VERSION,
                "method_hash": self.method_hash,
                "generated_utc": _iso_utc(),
                "profiles": self.profiles,
                "network_requests_this_run": self.provider.network_requests,
                "errors": self.provider.errors[-20:],
            },
        )
        if leaderboard is not None:
            _atomic_json(
                self.ai_dir / LEADERBOARD_FILE,
                {
                    "version": EDGE_VERSION,
                    "method_hash": self.method_hash,
                    "generated_utc": _iso_utc(),
                    "investors": list(leaderboard),
                },
            )


def neutral_profile(record: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    identity = investor_identity(record)
    return {
        "version": EDGE_VERSION,
        "generated_utc": _iso_utc(),
        "investor_key": str(identity.get("investor_key") or ""),
        "filer": str(record.get("filer") or ""),
        "owner": str(identity.get("owner") or record.get("owner") or "Other"),
        "owner_raw": str(identity.get("owner_raw") or record.get("owner") or ""),
        "identity": identity,
        "identity_confidence": float(identity.get("identity_confidence") or 0.0),
        "identity_confidence_label": str(identity.get("identity_confidence_label") or "Low"),
        "edge_score": 50.0,
        "raw_edge_score": 50.0,
        "modifier": 0,
        "confidence": 0.0,
        "confidence_label": "Low",
        "sample_count": 0,
        "effective_sample_count": 0.0,
        "considered_trade_count": 0,
        "eligible_trade_count": 0,
        "excluded_trade_count": 0,
        "excluded_reason_counts": {},
        "coverage": 0.0,
        "horizon_coverage": 0.0,
        "followable_alpha": None,
        "picker_alpha": None,
        "followable_alpha_by_horizon": {"5": None, "20": None, "60": None, "120": None},
        "picker_alpha_by_horizon": {"5": None, "20": None, "60": None, "120": None},
        "followable_hit_rate_by_horizon": {"5": None, "20": None, "60": None, "120": None},
        "picker_hit_rate_by_horizon": {"5": None, "20": None, "60": None, "120": None},
        "weighted_followable_hit_rate_percent": None,
        "weighted_picker_hit_rate_percent": None,
        "hit_rate_percent": 50.0,
        "consistency_score": 50.0,
        "sector_skill_score": 50.0,
        "sector_comparable_count": 0,
        "current_sector": {},
        "sector_performance": [],
        "strongest_sector": {},
        "average_disclosure_lag_days": None,
        "median_disclosure_lag_days": None,
        "methodology": {"reason": reason},
        "trade_results": [],
        "data_errors": [],
    }


def classification_for_score(score: int, rules: Mapping[str, Any]) -> str:
    thresholds = rules.get("thresholds") or {}
    if score >= int(thresholds.get("high_priority", 80)):
        return "high_priority"
    if score >= int(thresholds.get("watchlist", 65)):
        return "watchlist"
    if score >= int(thresholds.get("weak_signal", 50)):
        return "weak_signal"
    return "archive"


def apply_profile_to_analysis(
    analysis: Mapping[str, Any],
    profile: Mapping[str, Any],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply an Investor Edge modifier without defeating existing hard caps."""
    updated = dict(analysis)
    base_score = int(
        updated.get("base_score")
        if updated.get("base_score") is not None
        else updated.get("score") or 0
    )
    base_raw = int(
        updated.get("base_raw_score")
        if updated.get("base_raw_score") is not None
        else updated.get("raw_score") or base_score
    )
    modifier = max(
        -MAX_MODIFIER_LIMIT,
        min(MAX_MODIFIER_LIMIT, int(profile.get("modifier") or 0)),
    )
    adjusted_raw = max(0, min(100, base_raw + modifier))
    hard_caps = updated.get("hard_caps") or []
    cap_values = [
        int(item.get("maximum_score"))
        for item in hard_caps
        if isinstance(item, Mapping) and item.get("maximum_score") is not None
    ]
    adjusted = min([adjusted_raw, *cap_values]) if cap_values else adjusted_raw
    adjusted = max(0, min(100, int(adjusted)))
    components = dict(updated.get("score_components") or {})
    components["investor_edge_modifier"] = modifier
    updated.update(
        {
            "base_score": base_score,
            "base_raw_score": base_raw,
            "score": adjusted,
            "final_score": adjusted,
            "raw_score": adjusted_raw,
            "classification": classification_for_score(adjusted, rules),
            "score_components": components,
            "investor_edge_modifier": modifier,
            "investor_edge": dict(profile),
            "score_method_version": (
                f"{EDGE_VERSION}:{profile.get('method_hash')}"
                if profile.get("method_hash")
                else EDGE_VERSION
            ),
        }
    )
    return updated


def _percent_cell(value: Any) -> str:
    number = _safe_float(value)
    return "—" if number is None else f"{number:+.2f}%"


def _heat_class(value: Any, *, neutral: float = 0.0) -> str:
    number = _safe_float(value)
    if number is None:
        return "heat-na"
    delta = number - neutral
    if delta >= 8:
        return "heat-pos-3"
    if delta >= 3:
        return "heat-pos-2"
    if delta > 0:
        return "heat-pos-1"
    if delta <= -8:
        return "heat-neg-3"
    if delta <= -3:
        return "heat-neg-2"
    if delta < 0:
        return "heat-neg-1"
    return "heat-neutral"


def _edge_class(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return "heat-na"
    return _heat_class(number - 50.0)


def build_dashboard_addon(ai_dir: Path | None, output_dir: Path) -> None:
    """Create the Investor Edge heat-map page and link it from the native dashboard."""

    from urllib.parse import urlparse
    try:
        from .dashboard_insights import public_payload, safe_url
    except ImportError:
        from dashboard_insights import public_payload, safe_url

    horizons = ("5", "20", "60", "120")

    def help_control(key: str, label: str) -> str:
        # Resolve copy from the shared PT.HELP presentation object at runtime.
        return (
            "<button type='button' class='help' "
            f"data-tooltip-key='{html.escape(key, quote=True)}' data-tooltip='' "
            f"aria-label='Explain {html.escape(label, quote=True)}'>?</button>"
        )

    def text_cell(value: Any, *, fallback: str = "—") -> str:
        text = str(value or "").strip()
        return html.escape(text if text else fallback, quote=True)

    def first_value(mapping: Mapping[str, Any], *names: str) -> Any:
        for name in names:
            value = mapping.get(name)
            if value is not None and value != "":
                return value
        return None

    def horizon_value(mapping: Any, horizon: str) -> Any:
        if not isinstance(mapping, Mapping):
            return None
        value = mapping.get(horizon)
        return value if value is not None else mapping.get(int(horizon))

    def integer_cell(value: Any) -> str:
        number = _safe_float(value)
        return "—" if number is None else f"{int(number):,}"

    def confidence_cell(item: Mapping[str, Any]) -> str:
        confidence = _safe_float(
            first_value(item, "confidence", "identity_confidence")
        )
        label = str(
            first_value(item, "confidence_label", "identity_confidence_label") or ""
        ).strip()
        numeric = "—" if confidence is None else f"{confidence * 100:.1f}%"
        label_html = f"<small>{text_cell(label)}</small>" if label else ""
        return f"<strong>{numeric}</strong>{label_html}"

    def price_cell(value: Any) -> str:
        number = _safe_float(value)
        if number is None:
            return "—"
        rendered = f"{number:,.4f}".rstrip("0").rstrip(".")
        return f"${rendered}"

    def safe_http_url(value: Any) -> str:
        raw = safe_url(value)
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
        except ValueError:
            return ""
        return raw if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc else ""

    def outcome_for(
        trade: Mapping[str, Any], anchor: str, horizon: str
    ) -> Mapping[str, Any]:
        outcomes = trade.get(f"{anchor}_outcomes") or {}
        detail = horizon_value(outcomes, horizon)
        return detail if isinstance(detail, Mapping) else {}

    def outcome_metric(
        trade: Mapping[str, Any], anchor: str, horizon: str, metric: str
    ) -> Any:
        detail = outcome_for(trade, anchor, horizon)
        if detail.get(metric) is not None:
            return detail.get(metric)
        legacy_names = {
            "stock_return_percent": f"{anchor}_stock_return_by_horizon",
            "benchmark_return_percent": f"{anchor}_benchmark_return_by_horizon",
            "alpha_percent": f"{anchor}_alpha_by_horizon",
        }
        return horizon_value(trade.get(legacy_names[metric]) or {}, horizon)

    def entry_price(trade: Mapping[str, Any], anchor: str) -> Any:
        direct_names = (
            ("transaction_entry_price", "picker_entry_price")
            if anchor == "picker"
            else ("disclosure_entry_price", "followable_entry_price")
        )
        direct = first_value(trade, *direct_names)
        if direct is not None:
            return direct
        for horizon in horizons:
            detail = outcome_for(trade, anchor, horizon)
            if detail.get("stock_entry_price") is not None:
                return detail.get("stock_entry_price")
        return None

    def counts_toward_edge(trade: Mapping[str, Any]) -> bool | None:
        explicit = trade.get("counts_toward_edge")
        if isinstance(explicit, bool):
            return explicit
        if trade.get("eligible") is False or str(trade.get("status") or "") == "excluded":
            return False
        status = str(trade.get("status") or "")
        if status == "scored":
            return True
        if trade.get("eligible") is True:
            return any(
                _safe_float(trade.get(name)) is not None
                for name in ("followable_weighted_alpha", "picker_weighted_alpha")
            )
        return None

    def render_return_rows(trade: Mapping[str, Any]) -> str:
        rows: list[str] = []
        for horizon in horizons:
            for anchor, label in (("picker", "Transaction"), ("followable", "Disclosure")):
                stock = outcome_metric(
                    trade, anchor, horizon, "stock_return_percent"
                )
                benchmark = outcome_metric(
                    trade, anchor, horizon, "benchmark_return_percent"
                )
                alpha = outcome_metric(trade, anchor, horizon, "alpha_percent")
                rows.append(
                    "<tr>"
                    f"<th scope='row'>{horizon}D</th>"
                    f"<td>{label}</td>"
                    f"<td>{_percent_cell(stock)}</td>"
                    f"<td>{_percent_cell(benchmark)}</td>"
                    f"<td class='{_heat_class(alpha)}'>{_percent_cell(alpha)}</td>"
                    "</tr>"
                )
        return "".join(rows)

    def render_trade_card(
        trade: Mapping[str, Any], *, group_id: str, trade_index: int
    ) -> str:
        identity = trade.get("identity") or {}
        if not isinstance(identity, Mapping):
            identity = {}
        public_date = first_value(
            trade,
            "public_disclosure_date",
            "actual_public_disclosure_date",
            "filed_date",
            "disclosure_date",
            "observed_at_utc",
        )
        owner = first_value(trade, "owner", "owner_account", "account")
        if owner is None:
            owner = first_value(identity, "owner", "owner_raw")
        source = first_value(
            trade, "source_url", "source_filing_url", "filing_url", "source_filing"
        )
        if isinstance(source, Mapping):
            source = first_value(source, "url", "source_url", "href")
        href = safe_http_url(source)
        source_html = (
            f"<a href='{html.escape(href, quote=True)}' target='_blank' "
            "rel='noopener noreferrer'>Official filing</a>"
            if href
            else "—"
        )
        counts = counts_toward_edge(trade)
        counts_text = "Yes" if counts is True else "No" if counts is False else "—"
        exclusions = trade.get("excluded_reasons") or []
        if isinstance(exclusions, Sequence) and not isinstance(exclusions, (str, bytes)):
            exclusion_text = "; ".join(str(value) for value in exclusions if value)
        else:
            exclusion_text = str(exclusions or "")
        if not exclusion_text and trade.get("eligible") is True:
            exclusion_text = "None recorded"
        quality_warnings = trade.get("quality_warnings") or []
        if isinstance(quality_warnings, Sequence) and not isinstance(
            quality_warnings, (str, bytes)
        ):
            warning_text = "; ".join(str(value) for value in quality_warnings if value)
        else:
            warning_text = str(quality_warnings or "")
        ticker = text_cell(trade.get("ticker"), fallback="Unknown ticker")
        asset = text_cell(trade.get("asset"))
        outcome_id = f"{group_id}-trade-{trade_index}-outcomes"
        return (
            "<article class='trade-card'>"
            "<header class='trade-card-header'>"
            f"<div><p class='trade-kicker'>Historical observation</p><h3>{ticker}</h3>"
            f"<p>{asset}</p></div><span class='status-pill'>{text_cell(trade.get('status'))}</span>"
            "</header>"
            "<dl class='trade-facts'>"
            f"<div><dt>Transaction date</dt><dd>{text_cell(trade.get('transaction_date'))}</dd></div>"
            f"<div><dt>Actual public disclosure</dt><dd>{text_cell(public_date)}</dd></div>"
            f"<div><dt>Followable anchor</dt><dd>{text_cell(trade.get('followable_anchor_date'))}</dd></div>"
            f"<div><dt>Disclosure lag</dt><dd>{integer_cell(trade.get('disclosure_lag_days'))}{'d' if _safe_float(trade.get('disclosure_lag_days')) is not None else ''}</dd></div>"
            f"<div><dt>Owner / account</dt><dd>{text_cell(owner)}</dd></div>"
            f"<div><dt>Amount / range</dt><dd>{text_cell(trade.get('amount'))}</dd></div>"
            f"<div><dt>Transaction entry {help_control('transactionOutcomes', 'transaction-date outcomes')}</dt><dd>{price_cell(entry_price(trade, 'picker'))}</dd></div>"
            f"<div><dt>Disclosure entry {help_control('disclosureOutcomes', 'post-disclosure outcomes')}</dt><dd>{price_cell(entry_price(trade, 'followable'))}</dd></div>"
            f"<div><dt>Benchmark</dt><dd>{text_cell(trade.get('benchmark'))}</dd></div>"
            f"<div><dt>Counts toward Edge</dt><dd>{counts_text}</dd></div>"
            f"<div><dt>Source filing</dt><dd>{source_html}</dd></div>"
            f"<div class='wide'><dt>Exclusions</dt><dd>{text_cell(exclusion_text)}</dd></div>"
            f"<div class='wide'><dt>Quality notes</dt><dd>{text_cell(warning_text)}</dd></div>"
            "</dl>"
            f"<div class='outcome-table-wrap' id='{outcome_id}'>"
            "<table class='outcome-table'>"
            f"<caption>Stock, benchmark, and excess returns for {ticker}</caption>"
            "<thead><tr><th scope='col'>Horizon</th><th scope='col'>Entry anchor</th>"
            "<th scope='col'>Stock return</th><th scope='col'>Benchmark return</th>"
            "<th scope='col'>Excess return</th></tr></thead>"
            f"<tbody>{render_return_rows(trade)}</tbody></table></div>"
            "</article>"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    leaderboard_payload = (
        _read_json((ai_dir or Path("__missing__")) / LEADERBOARD_FILE)
        if ai_dir
        else None
    )
    investors = (
        leaderboard_payload.get("investors", [])
        if isinstance(leaderboard_payload, dict)
        else []
    )
    investors = public_payload({"investors": [dict(item) for item in investors if isinstance(item, Mapping)]})["investors"]
    generated = (
        str((leaderboard_payload or {}).get("generated_utc") or _iso_utc())
        if isinstance(leaderboard_payload, dict)
        else _iso_utc()
    )

    rows: list[str] = []
    valid_edges: list[float] = []
    for investor_index, item in enumerate(investors):
        group_id = f"investor-{investor_index}"
        identity = item.get("identity") or {}
        if not isinstance(identity, Mapping):
            identity = {}
        investor_key_value = first_value(item, "investor_key", "identity_key")
        if investor_key_value is None:
            investor_key_value = first_value(identity, "investor_key", "identity_key")
        owner = first_value(item, "owner", "owner_account", "account")
        owner_raw = first_value(item, "owner_raw", "account_name")
        if owner_raw is None:
            owner_raw = first_value(identity, "owner_raw", "account")
        owner_detail = (
            f"<small>{text_cell(owner_raw)}</small>"
            if owner_raw and str(owner_raw).strip() != str(owner or "").strip()
            else ""
        )
        sample_number = _safe_float(
            first_value(item, "sample_count", "observation_count")
        )
        has_observations = bool(sample_number is not None and sample_number > 0 and item.get("status") not in {"insufficient_data", "unavailable", "error", "disabled"} and item.get("minimum_sample_met") is not False)
        confidence = _safe_float(
            first_value(item, "confidence", "identity_confidence")
        )
        low_sample = bool(
            sample_number is None
            or sample_number < 3
            or confidence is None
            or confidence < 0.35
        )
        group_class = "low-sample" if low_sample else ""
        edge_value = _safe_float(item.get("edge_score")) if has_observations else None
        hit_value = (
            _safe_float(
                first_value(
                    item,
                    "weighted_followable_hit_rate_percent",
                    "hit_rate_percent",
                )
            )
            if has_observations
            else None
        )
        if edge_value is not None:
            valid_edges.append(edge_value)
        followable_horizons = item.get("followable_alpha_by_horizon") or {}
        strongest = item.get("strongest_sector") or {}
        if not isinstance(strongest, Mapping):
            strongest = {}
        if not strongest:
            sector_rows = item.get("sector_performance") or []
            if (
                isinstance(sector_rows, Sequence)
                and not isinstance(sector_rows, (str, bytes))
                and sector_rows
                and isinstance(sector_rows[0], Mapping)
            ):
                strongest = sector_rows[0]
        strongest_name = first_value(strongest, "sector", "name")
        strongest_details: list[str] = []
        if strongest.get("followable_alpha") is not None:
            strongest_details.append(_percent_cell(strongest.get("followable_alpha")))
        if strongest.get("sample_count") is not None:
            strongest_details.append(
                f"n={integer_cell(strongest.get('sample_count'))}"
            )
        strongest_html = text_cell(strongest_name)
        if strongest_details:
            strongest_html += f"<small>{' · '.join(strongest_details)}</small>"
        modifier = _safe_float(item.get("modifier")) if has_observations else None
        modifier_html = (
            f"<small>{modifier:+.0f} modifier</small>" if modifier is not None else ""
        )
        horizon_cells = "".join(
            (
                f"<td class='{_heat_class(horizon_value(followable_horizons, horizon) if has_observations else None)}'>"
                f"{_percent_cell(horizon_value(followable_horizons, horizon) if has_observations else None)}</td>"
            )
            for horizon in horizons
        )
        lag_value = (
            first_value(
                item,
                "average_disclosure_lag_days",
                "median_disclosure_lag_days",
            )
            if has_observations
            else None
        )
        lag_number = _safe_float(lag_value)
        lag_html = "—" if lag_number is None else f"{lag_number:.1f}d"
        trade_results = item.get("trade_results") or []
        if not isinstance(trade_results, Sequence) or isinstance(
            trade_results, (str, bytes)
        ):
            trade_results = []
        trade_cards = "".join(
            render_trade_card(trade, group_id=group_id, trade_index=trade_index)
            for trade_index, trade in enumerate(trade_results)
            if isinstance(trade, Mapping)
        )
        if not trade_cards:
            trade_cards = (
                "<p class='empty-detail'>No retained historical trade results are "
                "available for this investor.</p>"
            )
        rows.append(
            f"<tr class='investor-row {group_class}' data-edge-group='{group_id}'>"
            f"<td class='key-cell'><code>{text_cell(investor_key_value)}</code></td>"
            f"<td class='filer-cell'><strong>{text_cell(item.get('filer'), fallback='Unknown filer')}</strong></td>"
            f"<td class='owner-cell'><strong>{text_cell(owner, fallback='Unknown owner')}</strong>{owner_detail}</td>"
            f"<td class='{_edge_class(edge_value)}'><strong>{'—' if edge_value is None else f'{edge_value:.1f}'}</strong>{modifier_html}</td>"
            f"<td>{confidence_cell(item)}</td>"
            f"<td>{integer_cell(sample_number)}"
            + (f"<small class='history-building'>Building history — insufficient completed observations (n = {integer_cell(sample_number)})</small>" if not has_observations or (sample_number is not None and sample_number < 3) else "")
            + "</td>"
            f"{horizon_cells}"
            f"<td class='{_heat_class(hit_value, neutral=50.0)}'>{'—' if hit_value is None else f'{hit_value:.1f}%'}</td>"
            f"<td>{lag_html}</td>"
            f"<td class='sector-cell'>{strongest_html}</td>"
            "</tr>"
            f"<tr class='detail-row {group_class}' data-edge-group='{group_id}'>"
            "<td colspan='13'>"
            f"<details id='{group_id}-details'><summary>Historical trade drilldown for "
            f"{text_cell(item.get('filer'), fallback='Unknown filer')} / "
            f"{text_cell(owner, fallback='Unknown owner')} "
            f"({integer_cell(len(trade_results))} retained)</summary>"
            f"<div class='trade-grid'>{trade_cards}</div></details>"
            "</td></tr>"
        )

    page = f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <meta name='color-scheme' content='dark'>
  <meta http-equiv='Content-Security-Policy' content="default-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'">
  <title>PolitiTrack Investor Edge</title>
  <link rel='stylesheet' href='investor-edge.css'>
</head>
<body>
<header class='site-header'>
  <div><p class='eyebrow'>Historical filer performance</p><h1>Investor Edge {help_control('investorEdge', 'Investor Edge')}</h1><p class='subtitle'>Benchmark-relative outcomes from disclosed government purchases, emphasizing returns available from the first session after public observation.</p></div>
  <div class='header-actions'><a class='button secondary' href='index.html#investor-edge'>Main dashboard</a><button class='button' data-dialog='risk-dialog'>Methodology &amp; Risk</button><a class='button secondary' href='wallboard.html'>Wallboard</a></div>
</header>
<main>
<details class='notice edge-reading'><summary>How to read the heat map</summary><p>Edge 50 is neutral. Green means prior purchases beat their sector benchmark after disclosure; red means they lagged. Low-sample rows are deliberately faded. The PolitiTrack modifier is capped at ±12 points and never overrides an existing hard cap. Insufficient history is unavailable, not neutral performance.</p></details>
<section class='summary-grid'>
  <article class='metric-card'><span>Investors profiled</span><strong>{len(investors)}</strong></article>
  <article class='metric-card'><span>High-confidence profiles {help_control('edgeConfidence', 'Investor Edge confidence')}</span><strong>{sum(str(i.get('confidence_label') or '').casefold() == 'high' and (_safe_float(i.get('sample_count')) or 0) > 0 for i in investors)}</strong></article>
  <article class='metric-card'><span>Positive edge</span><strong>{sum(value > 55 for value in valid_edges)}</strong></article>
  <article class='metric-card'><span>Generated</span><strong class='date'>{text_cell(generated)}</strong></article>
</section>
<section class='panel'>
  <div class='panel-header'><div><h2>Investor performance heat map</h2><p>5/20/60/120-session values are average benchmark-relative returns from the first trading session after public observation. Open a drilldown to inspect transaction- and post-disclosure evidence.</p></div></div>
  <label class='search-label' for='edge-search'>Filter investors and historical trades<input id='edge-search' type='search' placeholder='Identity, filer, owner, ticker, sector…' autocomplete='off'></label>
  <div class='table-wrap'><table id='edge-table'><caption class='visually-hidden'>Investor Edge leaderboard with grouped historical-trade drilldowns</caption><thead><tr><th scope='col'>Investor identity / key</th><th scope='col'>Filer</th><th scope='col'>Owner / account</th><th scope='col'>Edge {help_control('investorEdge', 'Investor Edge')}</th><th scope='col'>Confidence {help_control('edgeConfidence', 'Investor Edge confidence')}</th><th scope='col'>Observations</th><th scope='col'>5D followable α {help_control('followableAlpha', '5-session followable alpha')}</th><th scope='col'>20D followable α {help_control('followableAlpha', '20-session followable alpha')}</th><th scope='col'>60D followable α {help_control('followableAlpha', '60-session followable alpha')}</th><th scope='col'>120D followable α {help_control('followableAlpha', '120-session followable alpha')}</th><th scope='col'>Hit rate {help_control('followableHitRate', 'followable hit rate')}</th><th scope='col'>Avg disclosure lag</th><th scope='col'>Strongest sector {help_control('sectorEdge', 'sector edge')}</th></tr></thead><tbody>{''.join(rows) if rows else "<tr><td colspan='13' class='empty-row'>Investor Edge has no scored historical observations yet. Profiles will populate as cached historical prices become available.</td></tr>"}</tbody></table></div>
</section>
<section class='panel methodology'><h2>Methodology</h2><p>Each filer + disclosed owner is scored separately. Returns are benchmarked to a sector ETF when the industry mapping is sufficiently confident, otherwise SPY. Historical outcomes are measured from the transaction date and from the first session after public observation. The score weights followable alpha 45%, picker alpha 20%, hit rate 15%, consistency 10%, and sector skill 10%, then shrinks small samples toward 50.</p></section>
</main>
<script src='investor-edge.js'></script>
</body></html>"""

    css = """:root {
  --bg: #07111c;
  --surface: #0c1928;
  --surface-2: #102237;
  --border: #23405c;
  --text: #eaf3fb;
  --muted: #91a8bd;
  --success: #70d6a1;
  --danger: #ff8f8f;
  --accent: #69b7ff;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); }
a { color: #a8d7ff; }
.site-header, main { width: min(100% - 40px, 1600px); margin: auto; }
.site-header { display: flex; justify-content: space-between; gap: 24px; align-items: end; padding: 40px 0 24px; }
.eyebrow, .trade-kicker { margin: 0; color: var(--accent); font-size: .74rem; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }
.subtitle, .panel p, .notice, .metric-card span, small { color: var(--muted); }
h1 { margin: .2rem 0; font-size: clamp(2rem, 5vw, 4.4rem); }
h2 { margin: .2rem 0 1rem; }
.header-actions { display: flex; gap: 10px; }
.button { display: inline-block; padding: 10px 14px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface-2); color: var(--text); text-decoration: none; }
.notice, .panel, .metric-card { border: 1px solid var(--border); border-radius: 14px; background: var(--surface); }
.notice { display: flex; gap: 10px; padding: 14px 16px; margin: 0 0 18px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
.metric-card { padding: 16px; }
.metric-card span, .metric-card strong { display: block; }
.metric-card strong { margin-top: 8px; font-size: 1.8rem; }
.metric-card strong.date { font-size: .9rem; line-height: 1.3; }
.panel { padding: 18px; margin: 18px 0; }
.panel-header { display: flex; justify-content: space-between; }
.search-label { display: block; max-width: 440px; margin: 12px 0; color: var(--muted); font-size: .85rem; }
.search-label input { display: block; width: 100%; margin-top: 6px; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface-2); color: var(--text); }
.search-label input:focus-visible, summary:focus-visible, a:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
.table-wrap, .outcome-table-wrap { overflow: auto; border: 1px solid var(--border); border-radius: 10px; }
#edge-table { width: 100%; min-width: 1480px; border-collapse: collapse; }
#edge-table > thead > tr > th, #edge-table > tbody > tr > td { padding: 11px 10px; border-bottom: 1px solid var(--border); text-align: right; white-space: nowrap; }
#edge-table > thead > tr > th { position: sticky; top: 0; z-index: 2; background: #0d1d2e; color: var(--muted); font-size: .72rem; letter-spacing: .05em; text-transform: uppercase; }
#edge-table > thead > tr > th:first-child, #edge-table > tbody > tr > td:first-child { text-align: left; }
.key-cell { max-width: 250px; }
.key-cell code { display: block; overflow-wrap: anywhere; white-space: normal; }
.filer-cell strong, .owner-cell strong, .owner-cell small, .sector-cell small { display: block; }
.low-sample { opacity: .52; }
.detail-row.low-sample { opacity: .68; }
.detail-row > td { padding: 0 14px 14px !important; background: rgba(5, 14, 24, .72); text-align: left !important; white-space: normal !important; }
.detail-row[hidden], .investor-row[hidden] { display: none; }
details { border: 1px solid var(--border); border-radius: 10px; background: var(--surface-2); }
summary { padding: 13px 15px; color: var(--accent); font-weight: 800; cursor: pointer; }
.trade-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 590px), 1fr)); gap: 14px; padding: 0 14px 14px; }
.trade-card { min-width: 0; padding: 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.trade-card-header { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
.trade-card h3 { margin: 4px 0; font-size: 1.25rem; }
.trade-card-header p:last-child { margin: 0; }
.status-pill { padding: 4px 8px; border: 1px solid var(--border); border-radius: 999px; color: var(--muted); font-size: .72rem; }
.trade-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 16px; margin: 14px 0; }
.trade-facts div { min-width: 0; padding-bottom: 6px; border-bottom: 1px solid rgba(35, 64, 92, .55); }
.trade-facts .wide { grid-column: 1 / -1; }
.trade-facts dt { color: var(--muted); font-size: .7rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.trade-facts dd { margin: 3px 0 0; overflow-wrap: anywhere; }
.outcome-table { width: 100%; min-width: 620px; border-collapse: collapse; }
.outcome-table caption { padding: 9px; color: var(--muted); font-size: .78rem; text-align: left; }
.outcome-table th, .outcome-table td { padding: 8px; border-top: 1px solid var(--border); text-align: right; }
.outcome-table th:first-child, .outcome-table td:nth-child(2) { text-align: left; }
.empty-row { padding: 32px !important; text-align: center !important; }
.empty-detail { padding: 0 14px 14px; }
.heat-pos-3 { background: rgba(46, 160, 100, .35); color: #b8f4d4; }
.heat-pos-2 { background: rgba(46, 160, 100, .22); color: #a2e8c5; }
.heat-pos-1 { background: rgba(46, 160, 100, .12); }
.heat-neg-3 { background: rgba(205, 70, 70, .35); color: #ffd0d0; }
.heat-neg-2 { background: rgba(205, 70, 70, .22); color: #ffc0c0; }
.heat-neg-1 { background: rgba(205, 70, 70, .12); }
.heat-neutral, .heat-na { color: var(--muted); }
.methodology { line-height: 1.55; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 850px) {
  .site-header { align-items: start; flex-direction: column; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .trade-facts { grid-template-columns: 1fr; }
  .trade-facts .wide { grid-column: auto; }
}
@media (max-width: 520px) {
  .site-header, main { width: min(100% - 20px, 1600px); }
  .summary-grid { grid-template-columns: 1fr; }
  .notice { flex-direction: column; }
}
@media (prefers-color-scheme: light) {
  :root { --bg: #eff4f8; --surface: #fff; --surface-2: #f4f7fa; --border: #cbd8e4; --text: #132235; --muted: #536a7f; }
  #edge-table > thead > tr > th { background: #e8f1f8; }
  .detail-row > td { background: #edf3f8; }
  .heat-pos-3 { color: #174f33; }
  .heat-neg-3 { color: #7d2525; }
}
"""
    js = """const input = document.getElementById("edge-search");
const groupedRows = new Map();
for (const row of document.querySelectorAll("#edge-table tbody [data-edge-group]")) {
  const key = row.dataset.edgeGroup;
  if (!groupedRows.has(key)) groupedRows.set(key, []);
  groupedRows.get(key).push(row);
}
function filterInvestorGroups() {
  const query = input ? input.value.trim().toLowerCase() : "";
  for (const rows of groupedRows.values()) {
    const searchable = rows.map(row => row.textContent || "").join(" ").toLowerCase();
    const visible = !query || searchable.includes(query);
    for (const row of rows) row.hidden = !visible;
    if (!visible) {
      const detail = rows.map(row => row.querySelector("details")).find(Boolean);
      if (detail) detail.open = false;
    }
  }
}
let filterTimer;
if (input) input.addEventListener("input", () => {clearTimeout(filterTimer); filterTimer = setTimeout(filterInvestorGroups, 180);});
"""
    # Reuse the complete generator-owned risk dialog and accessible tooltip behavior.
    assets = Path(__file__).with_name("dashboard_assets")
    shell = (assets / "index.html").read_text(encoding="utf-8")
    risk_start = shell.index('<dialog id="risk-dialog"')
    risk = shell[risk_start:shell.index("</dialog>", risk_start) + len("</dialog>")]
    page = page.replace("</main>", '</main>' + risk + '<div id="tooltip" role="tooltip" hidden></div>')
    js = (assets / "common.js").read_text(encoding="utf-8") + "\n" + js + "\nPT.setupDialogsAndTooltips();\n"
    css = (assets / "styles.css").read_text(encoding="utf-8") + "\n" + css + "\n" + (assets / "investor-edge-overrides.css").read_text(encoding="utf-8")
    (output_dir / "investor-edge.html").write_text(page, encoding="utf-8")
    (output_dir / "investor-edge.css").write_text(css, encoding="utf-8")
    (output_dir / "investor-edge.js").write_text(js, encoding="utf-8")
    data_dir = output_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(data_dir / "investor-edge.json", {"generated_utc": generated, "investors": investors})

    index_path = output_dir / "index.html"
    if index_path.exists():
        index = index_path.read_text(encoding="utf-8")
        marker = '<div class="header-actions">'
        link = '<a class="button secondary" href="investor-edge.html">Investor Edge</a>'
        if 'href="#investor-edge"' not in index and link not in index and marker in index:
            index = index.replace(marker, marker + "\n      " + link, 1)
            index_path.write_text(index, encoding="utf-8")
