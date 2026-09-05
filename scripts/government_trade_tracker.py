#!/usr/bin/env python3
"""Compatibility entrypoint for the resilient Legislative collector.

All existing imports receive the original tracker API. Only the canonical command
``--branch legislative --source all`` is routed through the source-isolated
orchestrator, which invokes the unchanged core once for Senate and once for House.

The module proxy deliberately mirrors public monkeypatches into the core module. This
preserves the established test and integration contract: callers that replace
``fetch_house_reports``, ``SenateClient``, notification functions, or other public
symbols continue to affect the original functions' global namespace.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Sequence

try:
    from . import government_trade_tracker_core as _core  # type: ignore
except ImportError:
    import government_trade_tracker_core as _core  # type: ignore

# Preserve the original module's public API for tests and dependent scripts.
for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def _argument_value(arguments: Sequence[str], flag: str) -> str | None:
    value: str | None = None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == flag:
            if index + 1 < len(arguments):
                value = arguments[index + 1]
            index += 2
            continue
        prefix = flag + "="
        if argument.startswith(prefix):
            value = argument[len(prefix):]
        index += 1
    return value


def _use_source_isolation(arguments: Sequence[str]) -> bool:
    return (
        os.environ.get("POLITITRACK_SOURCE_CHILD") != "1"
        and _argument_value(arguments, "--branch") == "legislative"
        and _argument_value(arguments, "--source") == "all"
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not _use_source_isolation(arguments):
        return int(_core.main(arguments))

    try:
        from . import run_legislative_sources_resilient as resilient  # type: ignore
    except ImportError:
        import run_legislative_sources_resilient as resilient  # type: ignore

    core_path = Path(__file__).resolve().with_name("government_trade_tracker_core.py")
    return int(
        resilient.run_tracker_arguments(
            arguments,
            tracker_script=core_path,
        )
    )


class _CoreProxyModule(types.ModuleType):
    """Mirror public assignments so original functions observe caller monkeypatches."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if not name.startswith("_") and hasattr(_core, name):
            setattr(_core, name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)
        if not name.startswith("_") and hasattr(_core, name):
            delattr(_core, name)


sys.modules[__name__].__class__ = _CoreProxyModule


if __name__ == "__main__":
    raise SystemExit(main())
