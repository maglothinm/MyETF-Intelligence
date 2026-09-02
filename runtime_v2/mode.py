"""Fail-closed Runtime v2 operating-mode and side-effect policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class RuntimeModeError(ValueError):
    """The configured Runtime v2 operating mode is unsafe or unknown."""


class RuntimeMode(str, Enum):
    SHADOW = "shadow"
    PRODUCTION = "production"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "RuntimeMode":
        # An omitted mode must never activate production effects.
        value = str(environment.get("POLITITRACK_MODE") or cls.SHADOW.value).strip().casefold()
        try:
            return cls(value)
        except ValueError as exc:
            supported = ", ".join(item.value for item in cls)
            raise RuntimeModeError(
                f"invalid POLITITRACK_MODE {value!r}; expected one of: {supported}"
            ) from exc


_DIRECT_PRODUCTION_KEYS = frozenset(
    {
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "ACTIONS_RESULTS_URL",
        "ACTIONS_RUNTIME_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "GMAIL_ADDRESS",
        "GMAIL_APP_PASSWORD",
        "PUSHOVER_API_TOKEN",
        "PUSHOVER_APP_TOKEN",
        "PUSHOVER_USER_KEY",
    }
)
_PRODUCTION_KEY_MARKERS = (
    "ALERT",
    "BROKERAGE",
    "HEALTHCHECK",
    "NOTIFICATION",
    "NOTIFY",
    "PUSHOVER",
    "PRODUCER_STATUS_CALLBACK",
    "SMTP_",
    "GMAIL",
    "CALLBACK",
    "WEBHOOK",
)


def _is_production_side_effect_key(key: str) -> bool:
    normalized = key.strip().upper()
    return normalized.startswith("ACTIONS_") or normalized in _DIRECT_PRODUCTION_KEYS or any(
        marker in normalized for marker in _PRODUCTION_KEY_MARKERS
    )


@dataclass(frozen=True)
class SideEffectPolicy:
    """Translate one validated mode into child-process safety controls."""

    mode: RuntimeMode

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "SideEffectPolicy":
        return cls(RuntimeMode.from_environment(environment))

    @property
    def production_effects_allowed(self) -> bool:
        return self.mode is RuntimeMode.PRODUCTION

    def child_environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        result = dict(environment)
        result["POLITITRACK_MODE"] = self.mode.value
        if self.production_effects_allowed:
            result["POLITITRACK_NOTIFICATIONS_ENABLED"] = "true"
            return result

        for key in tuple(result):
            if _is_production_side_effect_key(key):
                result[key] = ""
        result.update(
            {
                "AI_REQUIRE_PUSHOVER": "false",
                "AI_SUPPRESS_ALERTS": "true",
                "POLITITRACK_NOTIFICATIONS_ENABLED": "false",
                "POLITITRACK_PROTECTED_ARTIFACT_PUBLISHING": "false",
                "REQUIRE_PUSHOVER": "false",
                "SUPPRESS_ALERTS": "true",
            }
        )
        return result

    def tracker_command(self, command: Sequence[str]) -> list[str]:
        result = list(command)
        if not self.production_effects_allowed and "--no-notify" not in result:
            result.append("--no-notify")
        return result

    def ai_command(self, command: Sequence[str], *, explicitly_suppressed: bool = False) -> list[str]:
        result = list(command)
        if (not self.production_effects_allowed or explicitly_suppressed) and "--suppress-alerts" not in result:
            result.append("--suppress-alerts")
        return result
