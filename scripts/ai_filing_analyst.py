#!/usr/bin/env python3
"""Compatibility entry point for the hardened PolitiTrack AI analyst.

The pre-issue-121 implementation is retained byte-for-byte in
``ai_filing_analyst_legacy.py`` so historical incident evidence remains auditable.
It is executed into this module's namespace before the hardened controller is
loaded. Existing imports, monkeypatch-based tests, and Runtime v2 therefore keep
one shared module namespace while every production entry path uses the hardened
run controller.
"""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_NAME = __name__
_MODULE_PACKAGE = __package__
_MODULE_FILE = __file__
_LEGACY_PATH = Path(__file__).with_name("ai_filing_analyst_legacy.py")

# Direct-script execution would otherwise make the hardened module import this
# file a second time under the top-level name ``ai_filing_analyst``.
if _MODULE_NAME == "__main__":
    sys.modules.setdefault("ai_filing_analyst", sys.modules[_MODULE_NAME])

try:
    _legacy_source = _LEGACY_PATH.read_text(encoding="utf-8")
except OSError as exc:  # Fail closed before any state access or external call.
    raise SystemExit(f"AI analyst legacy core is unavailable: {exc}") from exc

# Compile with the retained file name for useful traceback provenance.  A
# temporary non-main module name prevents the legacy file's own CLI footer from
# running during namespace initialization.
_LEGACY_MODULE_NAME = "ai_filing_analyst_legacy_embedded"
sys.modules[_LEGACY_MODULE_NAME] = sys.modules[_MODULE_NAME]
globals()["__name__"] = _LEGACY_MODULE_NAME
globals()["__file__"] = str(_LEGACY_PATH)
try:
    exec(compile(_legacy_source, str(_LEGACY_PATH), "exec"), globals(), globals())
finally:
    globals()["__name__"] = _MODULE_NAME
    globals()["__package__"] = _MODULE_PACKAGE
    globals()["__file__"] = _MODULE_FILE

try:
    if _MODULE_PACKAGE:
        from . import ai_filing_analyst_hardened as _hardened
    else:  # pragma: no cover - production Actions and Runtime v2 direct path
        import ai_filing_analyst_hardened as _hardened  # type: ignore
except ImportError as exc:
    raise SystemExit(f"AI analyst hardened controller is unavailable: {exc}") from exc

# Preserve the established module API while routing both imports and direct
# execution through the hardened controller.
openai_analyze = _hardened.openai_analyze
run_analyst = _hardened.run_analyst
main = _hardened.main
FatalAnalystConfigurationError = _hardened.FatalAnalystConfigurationError
StructuredOutputDeferred = _hardened.StructuredOutputDeferred
HardenedAnalystRunResult = _hardened.AnalystRunResult
HardenedOpenAIResult = _hardened.OpenAIResult

if _MODULE_NAME == "__main__":
    raise SystemExit(main())
