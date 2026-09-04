#!/usr/bin/env python3
"""Hardened production entry point for the PolitiTrack AI filing analyst.

The existing analyst owns parsing, scoring, paper-position, and Investor Edge
semantics.  This entry point adds bounded structured-output recovery, separates
candidate deferrals from fatal state-integrity errors, and records durable alert-
delivery evidence before any external channel can be attempted.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from requests import Session

try:  # Support package imports and direct script execution.
    from . import ai_filing_analyst as legacy
except ImportError:  # pragma: no cover - direct execution path
    import ai_filing_analyst as legacy  # type: ignore

LOGGER = logging.getLogger("polititrack-ai-analyst")
REPOSITORY_ID = 1349678672
DEFAULT_OUTPUT_TOKENS = 4_000
ESCALATED_OUTPUT_TOKENS = 8_000
MAX_STRUCTURED_OUTPUT_ATTEMPTS = 2


class FatalAnalystConfigurationError(legacy.AnalystError):
    """A non-retryable configuration/authentication defect invalidates the run."""


class StructuredOutputDeferred(legacy.AnalystError):
    """A candidate-scoped model response could not be validated after retries."""

    def __init__(self, message: str, diagnostics: Sequence[Mapping[str, Any]]):
        super().__init__(message)
        self.diagnostics = tuple(dict(item) for item in diagnostics)


@dataclass(frozen=True)
class OpenAIResult(legacy.OpenAIResult):
    diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass
class AnalystRunResult(legacy.AnalystRunResult):
    result_schema_version: int = 2
    run_status: str = "pending"
    state_publishable: bool = False
    fatal_errors: list[str] = field(default_factory=list)
    deferred_candidates: list[dict[str, Any]] = field(default_factory=list)
    delivery_phase_started: bool = False
    delivery_attempt_count: int = 0
    delivery_confirmed_count: int = 0
    delivery_uncertain_count: int = 0
    repository_id: int | None = None
    workflow_run_id: str = ""
    workflow_run_attempt: str = "1"
    source_revision: str = ""


def _safe_identifier(value: Any, *, limit: int = 200) -> str:
    text = re.sub(r"[^A-Za-z0-9._:/-]+", "_", str(value or "").strip())
    return text[:limit]


def _safe_error(exc: BaseException, config: legacy.AnalystConfig) -> str:
    text = legacy.normalize_text(str(exc))
    for secret in (
        config.openai_api_key,
        config.finnhub_api_key,
        config.alphavantage_api_key,
        config.pushover_api_token,
        config.pushover_user_key,
        config.gmail_app_password,
    ):
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|token|password)(\s*[:=]\s*)([^\s,&]+)",
        r"\1\2[redacted]",
        text,
    )
    return text[:600]


def _object_value(value: Any, name: str, default: Any = "") -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _response_request_id(response: Any) -> str:
    for attribute in ("_request_id", "request_id"):
        value = getattr(response, attribute, "")
        if value:
            return _safe_identifier(value)
    raw_response = getattr(response, "_response", None)
    headers = getattr(raw_response, "headers", None)
    if headers is not None:
        try:
            value = headers.get("x-request-id") or headers.get("request-id")
        except AttributeError:
            value = ""
        if value:
            return _safe_identifier(value)
    return ""


def _response_diagnostic(
    *,
    attempt: int,
    token_limit: int,
    response: Any = None,
    error_type: str = "",
    error: str = "",
) -> dict[str, Any]:
    status = _safe_identifier(getattr(response, "status", ""), limit=80)
    incomplete = getattr(response, "incomplete_details", None)
    reason = _safe_identifier(_object_value(incomplete, "reason", ""), limit=120)
    return {
        "attempt": attempt,
        "max_output_tokens": token_limit,
        "response_id": _safe_identifier(getattr(response, "id", "")),
        "request_id": _response_request_id(response),
        "terminal_status": status,
        "incomplete_reason": reason,
        "error_type": _safe_identifier(error_type, limit=120),
        "error": error[:600],
    }


def _exception_error_code(exc: BaseException) -> str:
    body = getattr(exc, "body", None)
    if not isinstance(body, Mapping):
        return ""
    nested = body.get("error")
    payload = nested if isinstance(nested, Mapping) else body
    return legacy.normalize_text(
        str(payload.get("code") or payload.get("type") or "")
    ).casefold()


def _retry_delay(exc: BaseException, attempt_index: int) -> float:
    delay = min(30.0, float(2**attempt_index))
    message = str(exc).casefold()
    retry_after_match = re.search(
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)s",
        message,
    )
    if retry_after_match:
        delay = max(delay, float(retry_after_match.group(1)))
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        try:
            retry_after = headers.get("retry-after")
            if retry_after:
                delay = max(delay, float(retry_after))
        except (TypeError, ValueError, AttributeError):
            pass
    return delay


def openai_analyze(
    context: Mapping[str, Any],
    config: legacy.AnalystConfig,
    schema: Mapping[str, Any],
    *,
    client_factory: Callable[..., Any] | None = None,
) -> OpenAIResult:
    """Return exact validated JSON or raise a candidate-scoped deferral.

    No malformed output is repaired.  Every retry is another strict-schema model
    request, and diagnostics contain identifiers/status only, never raw output.
    """

    if not config.openai_api_key:
        raise FatalAnalystConfigurationError(
            "OPENAI_API_KEY is required for eligible filing analysis"
        )
    if client_factory is None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - exercised in Actions
            raise FatalAnalystConfigurationError(
                "The openai Python package is not installed; install requirements-ai.txt"
            ) from exc
        client_factory = OpenAI

    client = client_factory(api_key=config.openai_api_key, max_retries=0)
    kwargs: dict[str, Any] = {
        "model": config.model,
        "instructions": legacy.ANALYST_INSTRUCTIONS,
        "input": json.dumps(context, sort_keys=True, ensure_ascii=False),
        "reasoning": {"effort": config.reasoning_effort},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "government_trade_analysis",
                "description": (
                    "Evidence-constrained directional analysis of a disclosed "
                    "government equity transaction"
                ),
                "schema": dict(schema),
                "strict": True,
            }
        },
        "store": False,
    }
    if config.web_search_enabled:
        kwargs["tools"] = [{"type": "web_search"}]

    diagnostics: list[dict[str, Any]] = []
    token_limit = DEFAULT_OUTPUT_TOKENS
    last_message = "OpenAI structured output could not be validated"

    for attempt_index in range(MAX_STRUCTURED_OUTPUT_ATTEMPTS):
        attempt = attempt_index + 1
        kwargs["max_output_tokens"] = token_limit
        response = None
        try:
            legacy.pace_openai_request()
            response = client.responses.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - classified below
            message = _safe_error(exc, config)
            message_lower = str(exc).casefold()
            status_code = getattr(exc, "status_code", None)
            error_code = _exception_error_code(exc)
            diagnostic = _response_diagnostic(
                attempt=attempt,
                token_limit=token_limit,
                response=getattr(exc, "response", None),
                error_type=type(exc).__name__,
                error=message,
            )
            diagnostics.append(diagnostic)

            if error_code == "insufficient_quota" or "insufficient_quota" in message_lower:
                quota_error = legacy.OpenAIQuotaError(
                    "OpenAI API quota is exhausted or unavailable; check "
                    "project/organization billing and limits before retrying"
                )
                quota_error.diagnostics = tuple(diagnostics)  # type: ignore[attr-defined]
                raise quota_error from exc

            if "request too large" in message_lower and "tokens per min" in message_lower:
                raise FatalAnalystConfigurationError(
                    "OpenAI request exceeds the model TPM allowance; reduce "
                    "analysis context before production execution"
                ) from exc

            fatal_error_codes = {
                "invalid_api_key",
                "authentication_error",
                "permission_denied",
                "model_not_found",
                "invalid_request_error",
            }
            if status_code in {400, 401, 403, 404} or error_code in fatal_error_codes:
                raise FatalAnalystConfigurationError(
                    f"OpenAI configuration or authorization failed: "
                    f"{type(exc).__name__}: {message}"
                ) from exc

            retryable_status = status_code in {408, 409, 429} or (
                isinstance(status_code, int) and status_code >= 500
            )
            retryable_exception = type(exc).__name__ in {
                "APIConnectionError",
                "APITimeoutError",
                "InternalServerError",
            }
            last_message = f"OpenAI request failed: {type(exc).__name__}: {message}"
            if not (retryable_status or retryable_exception):
                break
            if attempt >= MAX_STRUCTURED_OUTPUT_ATTEMPTS:
                break
            delay = _retry_delay(exc, attempt_index)
            LOGGER.warning(
                "Transient OpenAI API error (%s, status=%s); retrying in %.1fs "
                "(attempt %s/%s)",
                type(exc).__name__,
                status_code,
                delay,
                attempt + 1,
                MAX_STRUCTURED_OUTPUT_ATTEMPTS,
            )
            time.sleep(delay)
            continue

        status = str(getattr(response, "status", "") or "").strip().casefold()
        incomplete = getattr(response, "incomplete_details", None)
        reason = str(_object_value(incomplete, "reason", "") or "").strip()
        if status != "completed":
            diagnostics.append(
                _response_diagnostic(
                    attempt=attempt,
                    token_limit=token_limit,
                    response=response,
                    error_type="IncompleteResponse",
                    error=(
                        f"terminal status {status or 'missing'}"
                        f"; reason {reason or 'unavailable'}"
                    ),
                )
            )
            last_message = (
                "OpenAI response did not reach completed status"
                f" ({status or 'missing'}; {reason or 'reason unavailable'})"
            )
            if reason.casefold() == "max_output_tokens":
                token_limit = ESCALATED_OUTPUT_TOKENS
            if attempt < MAX_STRUCTURED_OUTPUT_ATTEMPTS:
                continue
            break

        output_text = str(getattr(response, "output_text", "") or "")
        if not output_text:
            diagnostics.append(
                _response_diagnostic(
                    attempt=attempt,
                    token_limit=token_limit,
                    response=response,
                    error_type="EmptyStructuredOutput",
                    error="completed response contained no structured output text",
                )
            )
            last_message = "OpenAI returned no structured output text"
            if attempt < MAX_STRUCTURED_OUTPUT_ATTEMPTS:
                continue
            break

        try:
            payload = json.loads(output_text)
            if not isinstance(payload, dict):
                raise legacy.AnalystError(
                    "OpenAI structured output was not an object"
                )
            validated = legacy.validate_ai_payload(payload)
        except (json.JSONDecodeError, legacy.AnalystError, TypeError, ValueError) as exc:
            diagnostics.append(
                _response_diagnostic(
                    attempt=attempt,
                    token_limit=token_limit,
                    response=response,
                    error_type=type(exc).__name__,
                    error=_safe_error(exc, config),
                )
            )
            last_message = f"OpenAI returned invalid structured output: {_safe_error(exc, config)}"
            if attempt < MAX_STRUCTURED_OUTPUT_ATTEMPTS:
                continue
            break

        diagnostics.append(
            _response_diagnostic(
                attempt=attempt,
                token_limit=token_limit,
                response=response,
            )
        )
        usage = getattr(response, "usage", None)
        return OpenAIResult(
            payload=validated,
            response_id=_safe_identifier(getattr(response, "id", "")),
            input_tokens=(
                int(getattr(usage, "input_tokens", 0)) if usage else None
            ),
            output_tokens=(
                int(getattr(usage, "output_tokens", 0)) if usage else None
            ),
            diagnostics=tuple(diagnostics),
        )

    raise StructuredOutputDeferred(last_message, diagnostics)


def _result_metadata(result: AnalystRunResult) -> None:
    repository_id = os.environ.get("GITHUB_REPOSITORY_ID", "") or os.environ.get(
        "POLITITRACK_REPOSITORY_ID", ""
    )
    result.repository_id = (
        int(repository_id) if repository_id.isdigit() else REPOSITORY_ID
    )
    result.workflow_run_id = _safe_identifier(os.environ.get("GITHUB_RUN_ID", ""))
    result.workflow_run_attempt = _safe_identifier(
        os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    )
    result.source_revision = _safe_identifier(
        os.environ.get("SOURCE_REVISION") or os.environ.get("GITHUB_SHA") or ""
    )


def _deferred_candidate(
    trade: Mapping[str, Any],
    exc: BaseException,
    config: legacy.AnalystConfig,
    *,
    reason: str,
) -> dict[str, Any]:
    diagnostics = getattr(exc, "diagnostics", ())
    return {
        "trade_id": str(trade.get("trade_id") or ""),
        "ticker": str(trade.get("ticker") or "unknown"),
        "reason": reason,
        "error_type": type(exc).__name__,
        "error": _safe_error(exc, config),
        "diagnostics": [dict(item) for item in diagnostics if isinstance(item, Mapping)],
    }


def _pending_channels(delivery: Mapping[str, Any]) -> set[str]:
    requested = {
        str(channel)
        for channel in (delivery.get("requested_channels") or [])
        if str(channel) in {"pushover", "gmail"}
    }
    delivered_value = delivery.get("delivered_channels") or {}
    delivered = (
        {str(channel) for channel, timestamp in delivered_value.items() if timestamp}
        if isinstance(delivered_value, Mapping)
        else set()
    )
    return requested - delivered


def _checkpoint_result(
    config: legacy.AnalystConfig,
    result: AnalystRunResult,
) -> None:
    _result_metadata(result)
    legacy.write_json(config.result_path, asdict(result))


def _deliver_pending_candidate_alerts(
    config: legacy.AnalystConfig,
    result: AnalystRunResult,
    state: legacy.AIState,
    state_path: Path,
) -> None:
    """Deliver queued alerts with a durable pre-send uncertainty boundary.

    The result file is checkpointed before every external call.  A process death
    after that point therefore remains fail-closed even when the channel response
    was never observed.  Successful channel acceptance is persisted immediately
    in the local state before the next channel is attempted.
    """

    if config.suppress_alerts:
        return
    pending_ids = [
        delivery_id
        for delivery_id in sorted(state.candidate_alert_deliveries)
        if _pending_channels(state.candidate_alert_deliveries[delivery_id])
    ][: legacy.MAX_CANDIDATE_ALERT_RETRIES_PER_RUN]
    if not pending_ids:
        return

    for delivery_id in pending_ids:
        delivery = state.candidate_alert_deliveries[delivery_id]
        alert_value = delivery.get("alert") or {}
        if not isinstance(alert_value, Mapping):
            result.errors.append(
                f"Candidate alert delivery {delivery_id}: invalid alert snapshot"
            )
            return
        alert = {
            "title": str(alert_value.get("title") or "PolitiTrack candidate"),
            "message": str(alert_value.get("message") or ""),
            "url": str(alert_value.get("url") or ""),
        }
        delivered_value = delivery.get("delivered_channels") or {}
        delivered = (
            dict(delivered_value) if isinstance(delivered_value, Mapping) else {}
        )
        errors_value = delivery.get("channel_errors") or {}
        channel_errors = (
            dict(errors_value) if isinstance(errors_value, Mapping) else {}
        )
        delivered_for_alert = False

        for channel in ("pushover", "gmail"):
            if channel not in _pending_channels(delivery):
                continue

            result.delivery_phase_started = True
            result.run_status = "delivery_in_progress"
            result.state_publishable = False
            result.success = False
            result.delivery_attempt_count += 1
            attempted_at = legacy.iso_utc()
            delivery["last_attempt_utc"] = attempted_at
            attempt_history = delivery.get("channel_attempts") or []
            if not isinstance(attempt_history, list):
                attempt_history = []
            attempt_history.append(
                {
                    "channel": channel,
                    "attempted_at_utc": attempted_at,
                    "workflow_run_id": result.workflow_run_id,
                    "workflow_run_attempt": result.workflow_run_attempt,
                }
            )
            delivery["channel_attempts"] = attempt_history[-100:]
            legacy.save_state(state_path, state)
            _checkpoint_result(config, result)

            try:
                if channel == "pushover":
                    accepted = legacy._notification_post(
                        config,
                        title=alert["title"],
                        message=alert["message"],
                        url=(
                            alert["url"]
                            or str(delivery.get("source_url") or "")
                        ),
                        url_title="Open PolitiTrack analysis",
                        priority=0,
                    )
                else:
                    accepted = legacy._send_candidate_email(config, alert)
            except Exception as exc:  # External acceptance is now uncertain.
                channel_errors[channel] = (
                    f"{type(exc).__name__}: {_safe_error(exc, config)}"
                )
                delivery["channel_errors"] = channel_errors
                legacy.save_state(state_path, state)
                result.delivery_uncertain_count += 1
                result.errors.append(
                    f"Candidate alert delivery {delivery_id}/{channel}: "
                    f"{type(exc).__name__}: {_safe_error(exc, config)}"
                )
                _checkpoint_result(config, result)
                return

            if not accepted:
                channel_errors[channel] = "Channel returned no acceptance"
                delivery["channel_errors"] = channel_errors
                legacy.save_state(state_path, state)
                result.delivery_uncertain_count += 1
                result.errors.append(
                    f"Candidate alert delivery {delivery_id}/{channel}: "
                    "channel returned no acceptance"
                )
                _checkpoint_result(config, result)
                return

            delivered[channel] = legacy.iso_utc()
            channel_errors.pop(channel, None)
            delivery["delivered_channels"] = delivered
            delivery["channel_errors"] = channel_errors
            legacy.save_state(state_path, state)
            result.delivery_confirmed_count += 1
            delivered_for_alert = True
            _checkpoint_result(config, result)

        if delivered_for_alert:
            result.alerted_count += 1
            _checkpoint_result(config, result)


def _append_run_history(
    config: legacy.AnalystConfig,
    result: AnalystRunResult,
) -> None:
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', 'maglothinm/PolitiTrack')}/"
            f"actions/runs/{os.environ['GITHUB_RUN_ID']}"
        )
    record = {
        "run_key": (
            f"{os.environ.get('GITHUB_RUN_ID', result.started_utc)}:"
            f"{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
        ),
        "started_utc": result.started_utc,
        "finished_utc": result.finished_utc,
        "success": result.success,
        "run_status": result.run_status,
        "state_publishable": result.state_publishable,
        "enabled": result.enabled,
        "eligible_transaction_count": result.eligible_transaction_count,
        "historical_transaction_count": result.historical_transaction_count,
        "historical_bootstrap_transaction_count": (
            result.historical_bootstrap_transaction_count
        ),
        "investor_edge_maintenance_status": (
            result.investor_edge_maintenance_status
        ),
        "skipped_existing_count": result.skipped_existing_count,
        "attempted_count": result.attempted_count,
        "completed_count": result.completed_count,
        "deferred_candidate_count": len(result.deferred_candidates),
        "high_priority_count": result.high_priority_count,
        "watchlist_count": result.watchlist_count,
        "weak_signal_count": result.weak_signal_count,
        "archive_count": result.archive_count,
        "alerted_count": result.alerted_count,
        "paper_positions_opened": result.paper_positions_opened,
        "paper_positions_updated": result.paper_positions_updated,
        "paper_positions_closed": result.paper_positions_closed,
        "market_analyses_refreshed": result.market_analyses_refreshed,
        "market_signal_upgrades": result.market_signal_upgrades,
        "delivery_phase_started": result.delivery_phase_started,
        "delivery_attempt_count": result.delivery_attempt_count,
        "delivery_confirmed_count": result.delivery_confirmed_count,
        "delivery_uncertain_count": result.delivery_uncertain_count,
        "fatal_errors": result.fatal_errors,
        "deferred_candidates": result.deferred_candidates,
        "warnings": result.warnings,
        "run_url": run_url,
        "event_name": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "trigger_source": legacy.trigger_source(),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "source_revision": result.source_revision,
    }
    legacy.append_jsonl(config.ai_dir / "runs.jsonl", [record])


def _write_step_summary(result: AnalystRunResult) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [
        "## PolitiTrack AI filing analyst",
        "",
        f"- Status: **{result.run_status}**",
        f"- State publishable: **{str(result.state_publishable).lower()}**",
        f"- Eligible parsed directional transactions: **{result.eligible_transaction_count}**",
        f"- Retained historical transactions: **{result.historical_transaction_count}**",
        f"- New analyses completed: **{result.completed_count}**",
        f"- Deferred candidates: **{len(result.deferred_candidates)}**",
        f"- High priority: **{result.high_priority_count}**",
        f"- Watchlist: **{result.watchlist_count}**",
        f"- Paper positions opened: **{result.paper_positions_opened}**",
        f"- Delivery phase started: **{str(result.delivery_phase_started).lower()}**",
        (
            "- Delivery attempts / confirmed / uncertain: "
            f"**{result.delivery_attempt_count} / "
            f"{result.delivery_confirmed_count} / "
            f"{result.delivery_uncertain_count}**"
        ),
        "",
    ]
    if result.fatal_errors:
        lines.extend(
            [
                "### Fatal errors",
                "",
                *(f"- `{legacy._summary_cell(error)}`" for error in result.fatal_errors),
                "",
            ]
        )
    if result.deferred_candidates:
        lines.extend(["### Deferred candidates", ""])
        for item in result.deferred_candidates[:30]:
            lines.append(
                "- `{ticker} / {trade_id}` — {reason}: {error}".format(
                    ticker=legacy._summary_cell(item.get("ticker") or "unknown"),
                    trade_id=legacy._summary_cell(item.get("trade_id") or ""),
                    reason=legacy._summary_cell(item.get("reason") or "deferred"),
                    error=legacy._summary_cell(item.get("error") or ""),
                )
            )
        lines.append("")
    if result.warnings:
        lines.extend(
            [
                "### Warnings",
                "",
                *(f"- {legacy._summary_cell(warning)}" for warning in result.warnings[:30]),
                "",
            ]
        )
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _finish_analyst_run(
    config: legacy.AnalystConfig,
    result: AnalystRunResult,
    state: legacy.AIState,
    state_path: Path,
) -> AnalystRunResult:
    result.finished_utc = legacy.iso_utc()
    result.fatal_errors = list(result.errors)
    if result.fatal_errors:
        result.run_status = "fatal"
        result.state_publishable = False
        result.success = False
    elif result.deferred_candidates:
        result.run_status = "degraded"
        result.state_publishable = True
        result.success = True
    else:
        result.run_status = "success"
        result.state_publishable = True
        result.success = True
    if result.state_publishable:
        state.last_success_utc = result.finished_utc
    _result_metadata(result)
    legacy.save_state(state_path, state)
    all_analyses = legacy.read_jsonl(config.ai_dir / "analyses.jsonl")
    legacy.write_latest_outputs(config, all_analyses, state)
    legacy.write_json(config.result_path, asdict(result))
    _append_run_history(config, result)
    _write_step_summary(result)
    return result


def run_analyst(
    config: legacy.AnalystConfig,
    *,
    session: Session | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> AnalystRunResult:
    result = AnalystRunResult(started_utc=legacy.iso_utc(), enabled=config.enabled)
    _result_metadata(result)
    config.ai_dir.mkdir(parents=True, exist_ok=True)
    state_path = config.ai_dir / "state.json"
    try:
        state, _ = legacy.load_state(state_path)
    except Exception as exc:  # State is not safe to overwrite or promote.
        result.errors.append(
            f"AI state restore: {type(exc).__name__}: {_safe_error(exc, config)}"
        )
        result.finished_utc = legacy.iso_utc()
        result.run_status = "fatal"
        result.fatal_errors = list(result.errors)
        legacy.write_json(config.result_path, asdict(result))
        _write_step_summary(result)
        return result

    state.last_attempt_utc = result.started_utc
    legacy.save_state(state_path, state)

    try:
        if not config.paper_trading_only:
            result.errors.append(
                "AI_PAPER_TRADING_ONLY must remain true; real brokerage execution "
                "is not implemented"
            )
            return _finish_analyst_run(config, result, state, state_path)
        if not config.enabled:
            return _finish_analyst_run(config, result, state, state_path)

        rules = legacy.load_rules(config.rules_path)
        schema = legacy.load_schema(config.schema_path)
        rules_hash = legacy.json_hash(rules)
        historical_transactions, filings = (
            legacy.load_complete_retained_transaction_history(config)
        )
        result.historical_transaction_count = len(historical_transactions)
        result.historical_bootstrap_transaction_count = sum(
            trade.get("historical_bootstrap") is True
            for trade in historical_transactions
        )
        eligible = [
            trade
            for trade in historical_transactions
            if legacy.eligible_trade(trade, rules)
        ]
        eligible.sort(
            key=lambda row: (
                str(row.get("observed_at_utc") or ""),
                str(row.get("filed_date") or ""),
                str(row.get("trade_id") or ""),
            ),
            reverse=True,
        )
        result.eligible_transaction_count = len(eligible)

        existing_analyses = legacy.read_jsonl(config.ai_dir / "analyses.jsonl")
        for analysis_id in {
            str(row.get("analysis_id") or "") for row in existing_analyses
        }:
            if analysis_id:
                state.completed_analysis_ids.setdefault(
                    analysis_id, result.started_utc
                )

        new_candidates, result.skipped_existing_count = (
            legacy.select_new_analysis_candidates(
                eligible, config, state, rules_hash
            )
        )
        result.attempted_count = 0
        session = session or legacy.build_session(
            config.repository_url or "PolitiTrack AI filing analyst"
        )

        investor_edge: Any = None
        try:
            investor_edge = legacy.InvestorEdgeRuntime.create(
                ai_dir=config.ai_dir,
                session=session,
                alphavantage_api_key=config.alphavantage_api_key,
                finnhub_api_key=config.finnhub_api_key,
                alphavantage_entitlement=config.alphavantage_entitlement,
                request_timeout=config.request_timeout,
                config_path=Path(
                    os.environ.get("INVESTOR_EDGE_CONFIG", "").strip()
                    or config.rules_path.with_name("investor_edge.yml")
                ),
            )
        except Exception as exc:
            result.warnings.append(
                f"Investor Edge disabled: {type(exc).__name__}: "
                f"{_safe_error(exc, config)}"
            )
        maintenance_ok = legacy.maintain_investor_edge(
            investor_edge, historical_transactions, result.warnings
        )
        if maintenance_ok is False:
            result.investor_edge_maintenance_status = "failed"
            result.errors.append(
                "Investor Edge global maintenance/persistence failed; protected "
                "state must not be promoted"
            )
            return _finish_analyst_run(config, result, state, state_path)

        ticker_map = (
            legacy.load_sec_ticker_map(config, session, result.warnings)
            if new_candidates
            else {}
        )
        trades_by_id = {
            str(item.get("trade_id") or ""): item
            for item in historical_transactions
        }
        latest_existing = legacy.latest_by(existing_analyses, "trade_id")
        refresh_limit = int(
            (rules.get("analysis") or {}).get(
                "max_market_refreshes_per_run", 50
            )
        )
        pending_ids = {
            str(item.get("trade_id") or "") for item in new_candidates
        }
        refresh_candidates = [
            row
            for trade_id, row in latest_existing.items()
            if trade_id not in pending_ids
            and row.get("historical_bootstrap") is not True
            and (trades_by_id.get(trade_id) or {}).get("historical_bootstrap")
            is not True
            and legacy.analysis_needs_market_refresh(row)
        ]
        refresh_candidates.sort(
            key=lambda row: str(row.get("analyzed_at_utc") or ""),
            reverse=True,
        )
        for prior in refresh_candidates[: max(0, refresh_limit)]:
            trade_id = str(prior.get("trade_id") or "")
            trade = trades_by_id.get(trade_id)
            if not trade:
                continue
            try:
                refreshed_market = legacy.market_context(
                    trade, config, session, result.warnings
                )
                if legacy.json_hash(refreshed_market) == legacy.json_hash(
                    prior.get("market") or {}
                ):
                    continue
                refreshed = legacy.refresh_analysis_market(
                    prior,
                    trade,
                    historical_transactions,
                    refreshed_market,
                    rules,
                    investor_edge,
                )
                result.market_analyses_refreshed += 1
                prior_class = str(prior.get("classification") or "archive")
                prior_entry = str(
                    (prior.get("entry_plan") or {}).get("entry_status") or ""
                )
                new_class = str(refreshed.get("classification") or "archive")
                new_entry = str(
                    (refreshed.get("entry_plan") or {}).get("entry_status") or ""
                )
                upgraded = new_class in {"high_priority", "watchlist"} and (
                    prior_class not in {"high_priority", "watchlist"}
                    or (
                        prior_entry != "review_now"
                        and new_entry == "review_now"
                    )
                )
                if upgraded:
                    result.market_signal_upgrades += 1
                    legacy._queue_candidate_alert(config, refreshed, state)
                opened = legacy.open_paper_position(refreshed, state, rules)
                if opened:
                    opened["event_id"] = legacy.stable_id(
                        "paper-event",
                        (
                            opened["position_id"],
                            "open",
                            opened["opened_at_utc"],
                        ),
                    )
                    opened["event_type"] = "open"
                    legacy.append_jsonl(
                        config.ai_dir / "paper-portfolio.jsonl", [opened]
                    )
                    result.paper_positions_opened += 1
                legacy.append_jsonl(
                    config.ai_dir / "analyses.jsonl", [refreshed]
                )
                legacy.save_state(state_path, state)
            except Exception as exc:
                result.warnings.append(
                    f"Market refresh {str(prior.get('ticker') or 'unknown')} / "
                    f"{trade_id}: {type(exc).__name__}: "
                    f"{_safe_error(exc, config)}"
                )

        for index, trade in enumerate(new_candidates):
            result.attempted_count += 1
            try:
                filing = legacy.filing_for_trade(trade, filings)
                market = legacy.market_context(
                    trade, config, session, result.warnings
                )
                sec = legacy.sec_context(
                    str(trade.get("ticker") or ""),
                    config,
                    session,
                    ticker_map,
                    rules,
                    result.warnings,
                )
                document = legacy.document_text(
                    trade, filing, config, session, result.warnings
                )
                context = legacy.build_analysis_context(
                    trade,
                    filing,
                    historical_transactions,
                    document,
                    market,
                    sec,
                    rules,
                )
                ai_result = openai_analyze(
                    context,
                    config,
                    schema,
                    client_factory=client_factory,
                )
                record = legacy.build_analysis_record(
                    trade=trade,
                    filing=filing,
                    ai_result=ai_result,
                    market=market,
                    sec=sec,
                    document=document,
                    all_transactions=historical_transactions,
                    rules=rules,
                    rules_hash=rules_hash,
                    config=config,
                    investor_edge=investor_edge,
                )
                record["openai_diagnostics"] = [
                    dict(item) for item in ai_result.diagnostics
                ]
                result.analyses.append(record)
                result.completed_count += 1
                classification = str(
                    record.get("classification") or "archive"
                )
                if classification == "high_priority":
                    result.high_priority_count += 1
                elif classification == "watchlist":
                    result.watchlist_count += 1
                elif classification == "weak_signal":
                    result.weak_signal_count += 1
                else:
                    result.archive_count += 1
                if classification in {"high_priority", "watchlist"}:
                    legacy._queue_candidate_alert(config, record, state)
                opened = legacy.open_paper_position(record, state, rules)
                if opened:
                    opened["event_id"] = legacy.stable_id(
                        "paper-event",
                        (
                            opened["position_id"],
                            "open",
                            opened["opened_at_utc"],
                        ),
                    )
                    opened["event_type"] = "open"
                    legacy.append_jsonl(
                        config.ai_dir / "paper-portfolio.jsonl", [opened]
                    )
                    result.paper_positions_opened += 1
                state.completed_analysis_ids[str(record["analysis_id"])] = str(
                    record["analyzed_at_utc"]
                )
                legacy.append_jsonl(
                    config.ai_dir / "analyses.jsonl", [record]
                )
                legacy.save_state(state_path, state)
            except FatalAnalystConfigurationError as exc:
                result.errors.append(
                    f"OpenAI configuration / {str(trade.get('trade_id') or '')}: "
                    f"{_safe_error(exc, config)}"
                )
                break
            except legacy.OpenAIQuotaError as exc:
                result.deferred_candidates.append(
                    _deferred_candidate(
                        trade, exc, config, reason="openai_quota_unavailable"
                    )
                )
                for remaining in new_candidates[index + 1 :]:
                    result.deferred_candidates.append(
                        {
                            "trade_id": str(remaining.get("trade_id") or ""),
                            "ticker": str(
                                remaining.get("ticker") or "unknown"
                            ),
                            "reason": "not_attempted_after_openai_quota",
                            "error_type": "OpenAIQuotaError",
                            "error": (
                                "Batch stopped after OpenAI reported "
                                "insufficient quota"
                            ),
                            "diagnostics": [],
                        }
                    )
                result.warnings.append(
                    "Remaining AI analyses were deferred because OpenAI reported "
                    "insufficient_quota. They remain pending after billing or "
                    "quota is restored."
                )
                break
            except legacy.AnalystError as exc:  # Candidate remains pending for a later run.
                LOGGER.exception(
                    "AI analysis deferred for %s", trade.get("trade_id")
                )
                result.deferred_candidates.append(
                    _deferred_candidate(
                        trade, exc, config, reason="candidate_analysis_failed"
                    )
                )
            except Exception as exc:  # Unexpected code defects are fatal, not silently deferred.
                LOGGER.exception(
                    "Unexpected AI analyst failure for %s", trade.get("trade_id")
                )
                result.errors.append(
                    f"Unexpected candidate failure {str(trade.get('ticker') or 'unknown')} / "
                    f"{str(trade.get('trade_id') or '')}: {type(exc).__name__}: "
                    f"{_safe_error(exc, config)}"
                )
                break

        portfolio_events, updated, closed = legacy.update_paper_positions(
            state, config, rules, session, result.warnings
        )
        if portfolio_events:
            legacy.append_jsonl(
                config.ai_dir / "paper-portfolio.jsonl", portfolio_events
            )
        result.paper_positions_updated += updated
        result.paper_positions_closed += closed

        final_maintenance_ok = legacy.maintain_investor_edge(
            investor_edge,
            historical_transactions,
            result.warnings,
            allow_backfill=False,
        )
        result.investor_edge_maintenance_status = (
            "failed"
            if maintenance_ok is False or final_maintenance_ok is False
            else "disabled"
            if maintenance_ok is None
            else "complete"
        )
        if result.investor_edge_maintenance_status == "failed":
            result.errors.append(
                "Investor Edge global maintenance/persistence failed; protected "
                "state must not be promoted"
            )

        if not result.errors:
            _deliver_pending_candidate_alerts(
                config, result, state, state_path
            )
        return _finish_analyst_run(config, result, state, state_path)
    except Exception as exc:  # Unscoped failures are state-integrity failures.
        LOGGER.exception("Fatal AI analyst failure")
        result.errors.append(
            f"AI analyst fatal: {type(exc).__name__}: {_safe_error(exc, config)}"
        )
        return _finish_analyst_run(config, result, state, state_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = legacy.build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = legacy.build_config(args)
    result = run_analyst(config)
    if result.state_publishable:
        LOGGER.info(
            "AI analyst %s: eligible=%s analyzed=%s deferred=%s high=%s "
            "watch=%s opened=%s",
            result.run_status,
            result.eligible_transaction_count,
            result.completed_count,
            len(result.deferred_candidates),
            result.high_priority_count,
            result.watchlist_count,
            result.paper_positions_opened,
        )
        return 0
    LOGGER.error("AI analyst fatal: %s", "; ".join(result.fatal_errors))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
