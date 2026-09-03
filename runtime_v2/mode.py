from __future__ import annotations

import os
from enum import Enum
from typing import Mapping


class RuntimeModeError(RuntimeError):
    """Raised when Runtime v2 is not given an explicit safe operating mode."""


class RuntimeMode(str, Enum):
    SHADOW = "shadow"
    PRODUCTION = "production"

    @property
    def is_shadow(self) -> bool:
        return self is RuntimeMode.SHADOW


def resolve_runtime_mode(environment: Mapping[str, str] | None = None) -> RuntimeMode:
    """Resolve POLITITRACK_MODE and fail closed when it is absent or invalid."""

    source = os.environ if environment is None else environment
    raw_value = str(source.get("POLITITRACK_MODE", "")).strip().lower()
    if not raw_value:
        raise RuntimeModeError(
            "POLITITRACK_MODE is required and must be either 'shadow' or 'production'"
        )
    try:
        return RuntimeMode(raw_value)
    except ValueError as exc:
        raise RuntimeModeError(
            "POLITITRACK_MODE must be either 'shadow' or 'production'; "
            f"received {raw_value!r}"
        ) from exc
