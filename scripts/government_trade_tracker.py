#!/usr/bin/env python3
"""Compatibility entrypoint for the resilient Legislative collector.

All existing imports continue to receive the original tracker API. Only the canonical
``--branch legislative --source all`` command is routed through the source-isolated
orchestrator, which invokes the unchanged core once for Senate and once for House.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from . import government_trade_tracker_core as _core  # type: ignore
except ImportError:
    import government_trade_tracker_core as _core  # type: ignore

# Preserve the original module's public API for tests and dependent scripts.
for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def _argument_value(flag: str) -> str | None:
    arguments = sys.argv[1:]
    try:
        index = arguments.index(flag)
    except ValueError:
        return None
    return arguments[index + 1] if index + 1 < len(arguments) else None


def _use_source_isolation() -> bool:
    return (
        os.environ.get("POLITITRACK_SOURCE_CHILD") != "1"
        and _argument_value("--branch") == "legislative"
        and _argument_value("--source") == "all"
    )


def main() -> int:
    if not _use_source_isolation():
        return int(_core.main())

    try:
        from . import run_legislative_sources_resilient as resilient  # type: ignore
    except ImportError:
        import run_legislative_sources_resilient as resilient  # type: ignore

    core_path = Path(__file__).resolve().with_name("government_trade_tracker_core.py")
    arguments = ["--tracker-script", str(core_path)]
    if "--no-notify" in sys.argv[1:]:
        arguments.append("--no-notify")
    if "--verbose" in sys.argv[1:]:
        arguments.append("--verbose")
    return int(resilient.main(arguments))


if __name__ == "__main__":
    raise SystemExit(main())
