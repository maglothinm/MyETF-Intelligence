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
import json
import math
import os
import re
import statistics
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import requests
import yaml

EDGE_VERSION = "2026-08-29.2"
DEFAULT_CONFIG = Path("config/investor_edge.yml")
PROFILE_FILE = "investor-edge-profiles.json"
LEADERBOARD_FILE = "investor-edge-leaderboard.json"
MAX_MODIFIER_LIMIT = 12

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


def investor_key(record: Mapping[str, Any]) -> str:
    """Return the filer/owner identity used for skill attribution."""
    filer = _identity_part(record.get("filer"))
    owner = _identity_part(record.get("owner") or "unknown")
    return f"{filer}|{owner}" if filer else ""


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    candidate = Path(path or os.environ.get("INVESTOR_EDGE_CONFIG") or DEFAULT_CONFIG)
    if not candidate.exists():
        payload = {
            "version": 1,
            "enabled": False,
            "max_modifier": 12,
            "minimum_completed_trades": 3,
            "confidence_prior_trades": 8,
            "max_history_trades": 40,
            "leaderboard_max_investors": 40,
            "backfill_analysis_limit_per_run": 30,
            "network_request_budget_per_run": 40,
            "market_cache_hours": 24,
            "profile_cache_hours": 168,
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


def _rows_cover(rows: Sequence[Mapping[str, Any]], minimum: date | None) -> bool:
    if not rows:
        return False
    if minimum is None:
        return True
    oldest = _parse_date(rows[0].get("date"))
    return bool(oldest and oldest <= minimum)


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
        self.sector_memory: dict[str, dict[str, str]] = {}
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

    def daily(self, ticker: str, *, minimum_date: date | None = None) -> list[dict[str, Any]]:
        ticker = _ticker_symbol(ticker)
        if not ticker:
            return []
        cached_memory = self.memory.get(ticker)
        if cached_memory is not None and _rows_cover(cached_memory, minimum_date):
            return cached_memory

        cache_hours = float(self.config.get("market_cache_hours", 24))
        edge_path = self._edge_cache(ticker)
        cached = _read_json(edge_path) if _cache_fresh(edge_path, cache_hours) else None
        if isinstance(cached, dict) and isinstance(cached.get("rows"), list):
            rows = _coerce_rows(item for item in cached["rows"] if isinstance(item, Mapping))
            if _rows_cover(rows, minimum_date):
                self.memory[ticker] = rows
                return rows

        core = _read_json(self._core_cache(ticker))
        if isinstance(core, dict) and isinstance(core.get("rows"), list):
            rows = _coerce_rows(item for item in core["rows"] if isinstance(item, Mapping))
            if _rows_cover(rows, minimum_date):
                self.memory[ticker] = rows
                return rows

        rows = self._fetch_alphavantage(ticker, outputsize="full")
        if not _rows_cover(rows, minimum_date):
            fallback = self._fetch_finnhub(ticker)
            if len(fallback) > len(rows):
                rows = fallback
        if not rows:
            rows = self._fetch_alphavantage(ticker, outputsize="compact")

        self.memory[ticker] = rows
        _atomic_json(
            edge_path,
            {
                "ticker": ticker,
                "fetched_utc": _iso_utc(),
                "minimum_requested_date": minimum_date.isoformat() if minimum_date else "",
                "rows": rows,
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

    def _fetch_finnhub(self, ticker: str) -> list[dict[str, Any]]:
        if not self.finnhub_api_key or not self._can_request():
            return []
        lookback = int(self.config.get("history_lookback_days", 2200))
        end = _utc_now()
        start = end - timedelta(days=max(180, lookback))
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

    def sector(self, ticker: str) -> dict[str, str]:
        ticker = _ticker_symbol(ticker)
        if not ticker:
            return {"industry": "", "benchmark": str(self.config.get("benchmark_default", "SPY")), "sector": "Broad market"}
        if ticker in self.sector_memory:
            return self.sector_memory[ticker]
        path = self.ai_dir / "investor-edge-market" / f"{ticker}-profile.json"
        cache_hours = float(self.config.get("profile_cache_hours", 168))
        cached = _read_json(path) if _cache_fresh(path, cache_hours) else None
        industry = ""
        if isinstance(cached, dict):
            industry = _normal(cached.get("industry"))
        elif self.finnhub_api_key and self._can_request():
            try:
                response = self._get(
                    "https://finnhub.io/api/v1/stock/profile2",
                    params={"symbol": ticker, "token": self.finnhub_api_key},
                )
                if response is not None:
                    payload = response.json()
                    if isinstance(payload, dict):
                        industry = _normal(payload.get("finnhubIndustry"))
                _atomic_json(path, {"ticker": ticker, "industry": industry, "fetched_utc": _iso_utc()})
            except Exception as exc:  # noqa: BLE001
                self.errors.append(
                    self._safe_error(f"Finnhub profile {ticker}", f"{type(exc).__name__}: {exc}")
                )
        benchmark = str(self.config.get("benchmark_default", "SPY"))
        sector_name = "Broad market"
        material = industry.casefold()
        for terms, candidate, name in SECTOR_BENCHMARKS:
            if any(term in material for term in terms):
                benchmark = candidate
                sector_name = name
                break
        result = {"industry": industry, "benchmark": benchmark, "sector": sector_name}
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
    rows: Sequence[Mapping[str, Any]], anchor: date, horizon: int
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
    return start_date, end_date, ((end_close / start_close) - 1.0) * 100.0


def _benchmark_return(
    rows: Sequence[Mapping[str, Any]], start_date: date, end_date: date
) -> float | None:
    start = _close_on_or_after(rows, start_date)
    end = _close_on_or_after(rows, end_date)
    if not start or not end or not start[1]:
        return None
    return ((end[1] / start[1]) - 1.0) * 100.0


def _alphas_for_anchor(
    stock_rows: Sequence[Mapping[str, Any]],
    benchmark_rows: Sequence[Mapping[str, Any]],
    anchor: date,
    horizons: Sequence[int],
) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for horizon in horizons:
        window = _window_return(stock_rows, anchor, int(horizon))
        if not window:
            result[str(horizon)] = None
            continue
        start_date, end_date, stock_return = window
        benchmark_return = _benchmark_return(benchmark_rows, start_date, end_date)
        result[str(horizon)] = (
            round(stock_return - benchmark_return, 4) if benchmark_return is not None else None
        )
    return result


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


def _history_trade_eligible(record: Mapping[str, Any]) -> bool:
    if str(record.get("transaction_type") or "") != "Purchase":
        return False
    if not _ticker_symbol(record.get("ticker")):
        return False
    if record.get("equity_like") is False:
        return False
    return _parse_date(record.get("transaction_date")) is not None


@dataclass
class InvestorEdgeRuntime:
    config: dict[str, Any]
    ai_dir: Path
    provider: MarketHistoryProvider
    profiles: dict[str, dict[str, Any]]

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
        provider = MarketHistoryProvider(
            ai_dir=ai_dir,
            session=session,
            alphavantage_api_key=alphavantage_api_key,
            finnhub_api_key=finnhub_api_key,
            alphavantage_entitlement=alphavantage_entitlement,
            request_timeout=request_timeout,
            config=edge_config,
        )
        return cls(edge_config, ai_dir, provider, {str(k): dict(v) for k, v in profiles.items() if isinstance(v, dict)})

    @property
    def enabled(self) -> bool:
        value = self.config.get("enabled", False)
        if isinstance(value, bool):
            return value
        return str(value).strip().casefold() in {"1", "true", "yes", "on"}

    def profile_for_trade(
        self,
        trade: Mapping[str, Any],
        all_transactions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        key = investor_key(trade)
        if not key or not self.enabled:
            return neutral_profile(trade, reason="Investor Edge disabled or filer identity unavailable")
        current_tx_date = _parse_date(trade.get("transaction_date")) or _utc_now().date()
        current_public_date = (
            _parse_date(trade.get("filed_date"))
            or _parse_date(trade.get("observed_at_utc"))
            or _utc_now().date()
        )
        current_ticker = _ticker_symbol(trade.get("ticker"))
        history = [
            item
            for item in all_transactions
            if investor_key(item) == key
            and str(item.get("trade_id") or "") != str(trade.get("trade_id") or "")
            and _history_trade_eligible(item)
            and (_parse_date(item.get("transaction_date")) or current_tx_date) < current_tx_date
            and (
                _parse_date(item.get("filed_date"))
                or _parse_date(item.get("observed_at_utc"))
                or current_public_date
            )
            < current_public_date
        ]
        return self._profile(
            filer=str(trade.get("filer") or ""),
            owner=str(trade.get("owner") or ""),
            key=key,
            history=history,
            current_ticker=current_ticker,
        )

    def profile_for_investor(
        self,
        key: str,
        records: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        eligible = [item for item in records if investor_key(item) == key and _history_trade_eligible(item)]
        filer = str(eligible[-1].get("filer") or "") if eligible else ""
        owner = str(eligible[-1].get("owner") or "") if eligible else ""
        return self._profile(filer=filer, owner=owner, key=key, history=eligible, current_ticker="")

    def _profile(
        self,
        *,
        filer: str,
        owner: str,
        key: str,
        history: Sequence[Mapping[str, Any]],
        current_ticker: str,
    ) -> dict[str, Any]:
        max_history = max(0, min(250, int(self.config.get("max_history_trades", 40))))
        history_sorted = sorted(
            history,
            key=lambda item: str(item.get("transaction_date") or ""),
            reverse=True,
        )[: max(0, max_history)]
        if not history_sorted:
            profile = neutral_profile({"filer": filer, "owner": owner}, reason="No prior eligible purchases")
            profile["investor_key"] = key
            self.profiles[key] = profile
            return profile

        earliest = min((_parse_date(item.get("transaction_date")) for item in history_sorted), default=None)
        current_sector = self.provider.sector(current_ticker) if current_ticker else {"benchmark": "", "sector": "", "industry": ""}
        horizons = [int(value) for value in (self.config.get("horizons") or [5, 20, 60, 120])]
        horizon_weights = self.config.get("horizon_weights") or {"5": .15, "20": .30, "60": .35, "120": .20}
        clip = float(self.config.get("alpha_clip_percent", 25.0))
        trade_results: list[dict[str, Any]] = []

        for item in history_sorted:
            ticker = _ticker_symbol(item.get("ticker"))
            tx_date = _parse_date(item.get("transaction_date"))
            filed_date = _parse_date(item.get("filed_date")) or _parse_date(item.get("observed_at_utc"))
            if not ticker or tx_date is None or filed_date is None:
                continue
            sector = self.provider.sector(ticker)
            benchmark = sector.get("benchmark") or str(self.config.get("benchmark_default", "SPY"))
            stock_rows = self.provider.daily(ticker, minimum_date=earliest)
            benchmark_rows = self.provider.daily(benchmark, minimum_date=earliest)
            if not stock_rows or not benchmark_rows:
                continue
            tx_alphas = _alphas_for_anchor(stock_rows, benchmark_rows, tx_date, horizons)
            disclosure_alphas = _alphas_for_anchor(stock_rows, benchmark_rows, filed_date, horizons)
            picker = _weighted_alpha(tx_alphas, horizon_weights, clip)
            followable = _weighted_alpha(disclosure_alphas, horizon_weights, clip)
            if picker is None and followable is None:
                continue
            trade_results.append(
                {
                    "trade_id": str(item.get("trade_id") or ""),
                    "ticker": ticker,
                    "transaction_date": tx_date.isoformat(),
                    "filed_date": filed_date.isoformat(),
                    "disclosure_lag_days": max(0, (filed_date - tx_date).days),
                    "amount": str(item.get("amount") or ""),
                    "benchmark": benchmark,
                    "sector": sector.get("sector") or "Broad market",
                    "picker_alpha_by_horizon": tx_alphas,
                    "followable_alpha_by_horizon": disclosure_alphas,
                    "picker_weighted_alpha": round(picker, 4) if picker is not None else None,
                    "followable_weighted_alpha": round(followable, 4) if followable is not None else None,
                }
            )

        samples = [item for item in trade_results if item.get("followable_weighted_alpha") is not None]
        n = len(samples)
        considered = len(history_sorted)
        coverage = n / considered if considered else 0.0
        followable_mean = _mean(_safe_float(item.get("followable_weighted_alpha")) for item in samples)
        picker_mean = _mean(_safe_float(item.get("picker_weighted_alpha")) for item in trade_results)

        horizon_means: dict[str, float | None] = {}
        picker_horizon_means: dict[str, float | None] = {}
        for horizon in horizons:
            key_h = str(horizon)
            horizon_means[key_h] = _mean(
                _safe_float((item.get("followable_alpha_by_horizon") or {}).get(key_h)) for item in trade_results
            )
            picker_horizon_means[key_h] = _mean(
                _safe_float((item.get("picker_alpha_by_horizon") or {}).get(key_h)) for item in trade_results
            )

        hits: list[bool] = []
        for item in samples:
            twenty = _safe_float((item.get("followable_alpha_by_horizon") or {}).get("20"))
            fallback = _safe_float(item.get("followable_weighted_alpha"))
            measure = twenty if twenty is not None else fallback
            if measure is not None:
                hits.append(measure > 0)
        hit_rate = (sum(hits) / len(hits) * 100.0) if hits else 50.0

        followable_values = [
            float(item["followable_weighted_alpha"])
            for item in samples
            if _safe_float(item.get("followable_weighted_alpha")) is not None
        ]
        stdev = statistics.pstdev(followable_values) if len(followable_values) >= 2 else 0.0
        if followable_mean is None:
            consistency_score = 50.0
        else:
            consistency_score = max(0.0, min(100.0, 50.0 + 10.0 * followable_mean / (stdev + 2.0)))

        if current_sector.get("benchmark"):
            sector_samples = [
                item for item in samples
                if item.get("benchmark") == current_sector.get("benchmark")
            ]
            sector_alpha = _mean(
                _safe_float(item.get("followable_weighted_alpha")) for item in sector_samples
            )
            sector_score = (
                _alpha_score(sector_alpha, self.config) if len(sector_samples) >= 2 else 50.0
            )
        else:
            # A global leaderboard has no current candidate sector. Keep this component
            # neutral rather than counting the same all-sector alpha twice.
            sector_samples = []
            sector_score = 50.0

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

        prior = float(self.config.get("confidence_prior_trades", 8))
        minimum = max(1, int(self.config.get("minimum_completed_trades", 3)))
        confidence = n / (n + prior) if n else 0.0
        confidence *= min(1.0, coverage / 0.60) if coverage else 0.0
        confidence *= min(1.0, n / minimum)
        adjusted_edge = 50.0 + confidence * (raw_edge - 50.0)
        adjusted_edge = max(0.0, min(100.0, adjusted_edge))
        max_modifier = max(
            0,
            min(MAX_MODIFIER_LIMIT, int(self.config.get("max_modifier", MAX_MODIFIER_LIMIT))),
        )
        modifier = int(round((adjusted_edge - 50.0) / 50.0 * max_modifier))
        modifier = max(-max_modifier, min(max_modifier, modifier))
        disclosure_lags = [int(item.get("disclosure_lag_days") or 0) for item in trade_results]

        profile = {
            "version": EDGE_VERSION,
            "generated_utc": _iso_utc(),
            "investor_key": key,
            "filer": filer,
            "owner": owner,
            "edge_score": round(adjusted_edge, 1),
            "raw_edge_score": round(raw_edge, 1),
            "modifier": modifier,
            "confidence": round(confidence, 4),
            "confidence_label": _confidence_label(confidence, n),
            "sample_count": n,
            "considered_trade_count": considered,
            "coverage": round(coverage, 4),
            "followable_alpha": round(followable_mean, 2) if followable_mean is not None else None,
            "picker_alpha": round(picker_mean, 2) if picker_mean is not None else None,
            "followable_alpha_by_horizon": {
                key_h: round(value, 2) if value is not None else None for key_h, value in horizon_means.items()
            },
            "picker_alpha_by_horizon": {
                key_h: round(value, 2) if value is not None else None for key_h, value in picker_horizon_means.items()
            },
            "hit_rate_percent": round(hit_rate, 1),
            "consistency_score": round(consistency_score, 1),
            "sector_skill_score": round(sector_score, 1),
            "sector_comparable_count": len(sector_samples),
            "current_sector": current_sector,
            "average_disclosure_lag_days": round(statistics.fmean(disclosure_lags), 1) if disclosure_lags else None,
            "methodology": {
                "benchmarking": "Sector ETF when Finnhub industry data is available; otherwise SPY",
                "anchors": ["transaction_date", "public_filed_date"],
                "horizons_trading_days": horizons,
                "modifier_range": [-max_modifier, max_modifier],
                "small_sample_shrinkage": True,
            },
            "trade_results": trade_results,
            "data_errors": self.provider.errors[-10:],
        }
        self.profiles[key] = profile
        return profile

    def refresh_leaderboard(self, transactions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        counts = Counter(investor_key(item) for item in transactions if _history_trade_eligible(item))
        keys = [key for key, _ in counts.most_common(int(self.config.get("leaderboard_max_investors", 40))) if key]
        leaderboard = [self.profile_for_investor(key, transactions) for key in keys]
        leaderboard.sort(key=lambda item: (float(item.get("edge_score") or 50), int(item.get("sample_count") or 0)), reverse=True)
        return leaderboard

    def save(self, leaderboard: Sequence[Mapping[str, Any]] | None = None) -> None:
        _atomic_json(
            self.ai_dir / PROFILE_FILE,
            {
                "version": EDGE_VERSION,
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
                    "generated_utc": _iso_utc(),
                    "investors": list(leaderboard),
                },
            )


def neutral_profile(record: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "version": EDGE_VERSION,
        "generated_utc": _iso_utc(),
        "investor_key": investor_key(record),
        "filer": str(record.get("filer") or ""),
        "owner": str(record.get("owner") or ""),
        "edge_score": 50.0,
        "raw_edge_score": 50.0,
        "modifier": 0,
        "confidence": 0.0,
        "confidence_label": "Low",
        "sample_count": 0,
        "considered_trade_count": 0,
        "coverage": 0.0,
        "followable_alpha": None,
        "picker_alpha": None,
        "followable_alpha_by_horizon": {"5": None, "20": None, "60": None, "120": None},
        "picker_alpha_by_horizon": {"5": None, "20": None, "60": None, "120": None},
        "hit_rate_percent": 50.0,
        "consistency_score": 50.0,
        "sector_skill_score": 50.0,
        "sector_comparable_count": 0,
        "current_sector": {},
        "average_disclosure_lag_days": None,
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
    base_score = int(updated.get("score") or 0)
    base_raw = int(updated.get("raw_score") or base_score)
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
            "raw_score": adjusted_raw,
            "classification": classification_for_score(adjusted, rules),
            "score_components": components,
            "investor_edge_modifier": modifier,
            "investor_edge": dict(profile),
            "score_method_version": EDGE_VERSION,
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
    output_dir.mkdir(parents=True, exist_ok=True)
    leaderboard_payload = _read_json((ai_dir or Path("__missing__")) / LEADERBOARD_FILE) if ai_dir else None
    investors = leaderboard_payload.get("investors", []) if isinstance(leaderboard_payload, dict) else []
    investors = [dict(item) for item in investors if isinstance(item, Mapping)]
    generated = str((leaderboard_payload or {}).get("generated_utc") or _iso_utc()) if isinstance(leaderboard_payload, dict) else _iso_utc()

    rows = []
    for item in investors:
        horizons = item.get("followable_alpha_by_horizon") or {}
        confidence = float(item.get("confidence") or 0)
        opacity_class = "low-confidence" if confidence < .35 else ""
        rows.append(
            "<tr class='{opacity}'>"
            "<td class='investor'><strong>{filer}</strong><small>{owner}</small></td>"
            "<td class='{edge_cls}'><strong>{edge:.1f}</strong><small>{modifier:+d} PolitiTrack</small></td>"
            "<td><strong>{confidence_label}</strong><small>{samples} scored / {considered} considered</small></td>"
            "<td class='{h5c}'>{h5}</td><td class='{h20c}'>{h20}</td><td class='{h60c}'>{h60}</td><td class='{h120c}'>{h120}</td>"
            "<td class='{followc}'>{follow}</td><td class='{pickerc}'>{picker}</td>"
            "<td class='{hitc}'>{hit:.1f}%</td><td>{lag}</td>"
            "</tr>".format(
                opacity=opacity_class,
                filer=html.escape(str(item.get("filer") or "Unknown")),
                owner=html.escape(str(item.get("owner") or "Unknown owner")),
                edge_cls=_edge_class(item.get("edge_score")),
                edge=float(item.get("edge_score") or 50),
                modifier=int(item.get("modifier") or 0),
                confidence_label=html.escape(str(item.get("confidence_label") or "Low")),
                samples=int(item.get("sample_count") or 0),
                considered=int(item.get("considered_trade_count") or 0),
                h5c=_heat_class(horizons.get("5")), h5=_percent_cell(horizons.get("5")),
                h20c=_heat_class(horizons.get("20")), h20=_percent_cell(horizons.get("20")),
                h60c=_heat_class(horizons.get("60")), h60=_percent_cell(horizons.get("60")),
                h120c=_heat_class(horizons.get("120")), h120=_percent_cell(horizons.get("120")),
                followc=_heat_class(item.get("followable_alpha")), follow=_percent_cell(item.get("followable_alpha")),
                pickerc=_heat_class(item.get("picker_alpha")), picker=_percent_cell(item.get("picker_alpha")),
                hitc=_heat_class(item.get("hit_rate_percent"), neutral=50.0),
                hit=float(item.get("hit_rate_percent") or 50),
                lag=(f"{float(item['average_disclosure_lag_days']):.1f}d" if item.get("average_disclosure_lag_days") is not None else "—"),
            )
        )

    page = f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <meta name='color-scheme' content='dark light'>
  <meta http-equiv='Content-Security-Policy' content="default-src 'self'; style-src 'self'; script-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'">
  <title>PolitiTrack Investor Edge</title>
  <link rel='stylesheet' href='investor-edge.css'>
</head>
<body>
<header class='site-header'>
  <div><p class='eyebrow'>Historical filer performance</p><h1>Investor Edge</h1><p class='subtitle'>Benchmark-relative outcomes from disclosed government purchases, emphasizing returns still available after public filing.</p></div>
  <div class='header-actions'><a class='button secondary' href='index.html'>Main dashboard</a><a class='button secondary' href='wallboard.html'>Wallboard</a></div>
</header>
<main>
<section class='notice'><strong>How to read it:</strong><span>Edge 50 is neutral. Green means prior purchases beat their sector benchmark after disclosure; red means they lagged. Low-sample rows are deliberately faded. The PolitiTrack modifier is capped at ±12 points and never overrides an existing hard cap.</span></section>
<section class='summary-grid'>
  <article class='metric-card'><span>Investors profiled</span><strong>{len(investors)}</strong></article>
  <article class='metric-card'><span>High-confidence profiles</span><strong>{sum(str(i.get('confidence_label')) == 'High' for i in investors)}</strong></article>
  <article class='metric-card'><span>Positive edge</span><strong>{sum(float(i.get('edge_score') or 50) > 55 for i in investors)}</strong></article>
  <article class='metric-card'><span>Generated</span><strong class='date'>{html.escape(generated)}</strong></article>
</section>
<section class='panel'>
  <div class='panel-header'><div><h2>Investor performance heat map</h2><p>5/20/60/120-day values are average abnormal returns from the public filing date. Picker alpha is measured from the underlying transaction date.</p></div></div>
  <label class='search-label'>Filter investors<input id='edge-search' type='search' placeholder='Filer or owner'></label>
  <div class='table-wrap'><table id='edge-table'><thead><tr><th>Investor / owner</th><th>Edge</th><th>Confidence</th><th>5D</th><th>20D</th><th>60D</th><th>120D</th><th>Followable alpha</th><th>Picker alpha</th><th>Hit rate</th><th>Avg disclosure lag</th></tr></thead><tbody>{''.join(rows) if rows else "<tr><td colspan='11' class='empty-row'>Investor Edge has no scored historical observations yet. Profiles will populate as cached historical prices become available.</td></tr>"}</tbody></table></div>
</section>
<section class='panel methodology'><h2>Methodology</h2><p>Each filer + disclosed owner is scored separately. Returns are benchmarked to a sector ETF when industry classification is available, otherwise SPY. Historical outcomes are measured from both transaction and filing dates. The score weights followable alpha 45%, picker alpha 20%, hit rate 15%, consistency 10%, and sector skill 10%, then shrinks small samples toward 50.</p></section>
</main>
<script src='investor-edge.js'></script>
</body></html>"""

    css = """:root{--bg:#07111c;--surface:#0c1928;--surface-2:#102237;--border:#23405c;--text:#eaf3fb;--muted:#91a8bd;--success:#70d6a1;--danger:#ff8f8f;--accent:#69b7ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}.site-header,main{width:min(100% - 40px,1500px);margin:auto}.site-header{display:flex;justify-content:space-between;gap:24px;align-items:end;padding:40px 0 24px}.eyebrow{text-transform:uppercase;letter-spacing:.14em;color:var(--accent);font-size:.74rem;font-weight:800}.subtitle,.panel p,.notice,.metric-card span,small{color:var(--muted)}h1{margin:.2rem 0;font-size:clamp(2rem,5vw,4.4rem)}h2{margin:.2rem 0 1rem}.header-actions{display:flex;gap:10px}.button{display:inline-block;padding:10px 14px;border:1px solid var(--border);border-radius:9px;text-decoration:none;color:var(--text);background:var(--surface-2)}.notice,.panel,.metric-card{border:1px solid var(--border);background:var(--surface);border-radius:14px}.notice{display:flex;gap:10px;padding:14px 16px;margin:0 0 18px}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.metric-card{padding:16px}.metric-card span,.metric-card strong{display:block}.metric-card strong{font-size:1.8rem;margin-top:8px}.metric-card strong.date{font-size:.9rem;line-height:1.3}.panel{padding:18px;margin:18px 0}.panel-header{display:flex;justify-content:space-between}.search-label{display:block;max-width:360px;color:var(--muted);font-size:.85rem;margin:12px 0}.search-label input{display:block;width:100%;margin-top:6px;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--surface-2);color:var(--text)}.table-wrap{overflow:auto;border:1px solid var(--border);border-radius:10px}table{width:100%;border-collapse:collapse;min-width:1180px}th,td{padding:11px 10px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}th{position:sticky;top:0;background:#0d1d2e;color:var(--muted);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em}th:first-child,td:first-child{text-align:left}.investor strong,.investor small{display:block}.low-confidence{opacity:.52}.heat-pos-3{background:rgba(46,160,100,.35);color:#b8f4d4}.heat-pos-2{background:rgba(46,160,100,.22);color:#a2e8c5}.heat-pos-1{background:rgba(46,160,100,.12)}.heat-neg-3{background:rgba(205,70,70,.35);color:#ffd0d0}.heat-neg-2{background:rgba(205,70,70,.22);color:#ffc0c0}.heat-neg-1{background:rgba(205,70,70,.12)}.heat-neutral,.heat-na{color:var(--muted)}.empty-row{text-align:center!important;padding:32px}.methodology{line-height:1.55}@media(max-width:850px){.site-header{align-items:start;flex-direction:column}.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.site-header,main{width:min(100% - 20px,1500px)}.summary-grid{grid-template-columns:1fr}.notice{flex-direction:column}}@media(prefers-color-scheme:light){:root{--bg:#eff4f8;--surface:#fff;--surface-2:#f4f7fa;--border:#cbd8e4;--text:#132235;--muted:#536a7f}th{background:#e8f1f8}.heat-pos-3{color:#174f33}.heat-neg-3{color:#7d2525}}"""
    js = """const input=document.getElementById('edge-search');const rows=[...document.querySelectorAll('#edge-table tbody tr')];if(input){input.addEventListener('input',()=>{const q=input.value.trim().toLowerCase();for(const row of rows){row.hidden=!!q&&!row.textContent.toLowerCase().includes(q);}});}"""
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
        if link not in index and marker in index:
            index = index.replace(marker, marker + "\n      " + link, 1)
            index_path.write_text(index, encoding="utf-8")
