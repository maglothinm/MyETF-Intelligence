"""Time/memory-bounded document inspection outside web and collector processes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

try:
    from .source_ocr import MAX_BYTES, MAX_PAGES, OCRError
except ImportError:
    from source_ocr import MAX_BYTES, MAX_PAGES, OCRError


def decoder_environment():
    """Allow only platform and local OCR-data paths, never app credentials."""
    environment = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "LD_LIBRARY_PATH", "TESSDATA_PREFIX") if key in os.environ}
    environment.update(PYTHONNOUSERSITE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", LANG="C.UTF-8")
    return environment


def inspect_bounded(data: bytes, max_pages: int = MAX_PAGES, *, timeout: float = 15):
    if not data or len(data) > MAX_BYTES:
        raise OCRError("document_byte_limit")
    if not isinstance(max_pages, int) or not 0 < max_pages <= MAX_PAGES:
        raise OCRError("document_page_limit")
    # Do not pass application credentials, proxy settings or PYTHONPATH to a
    # document decoder. No user filename or URL becomes a shell argument.
    environment = decoder_environment()
    with tempfile.TemporaryDirectory(prefix="polititrack-probe-") as temporary:
        source = Path(temporary) / "document"
        source.write_bytes(data)
        try:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(source), str(max_pages)],
                capture_output=True, timeout=timeout, env=environment, cwd=temporary, check=False)
        except (subprocess.SubprocessError, OSError):
            raise OCRError("document_inspection_limit") from None
        if len(result.stdout) > 12_000_000:
            raise OCRError("document_inspection_limit")
        try:
            payload = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise OCRError("document_inspection_limit") from None
        if result.returncode or not isinstance(payload, dict) or "info" not in payload:
            code = payload.get("error_code", "document_inspection_failed") if isinstance(payload, dict) else "document_inspection_failed"
            raise OCRError(code if isinstance(code, str) and code.isascii() and code.replace("_", "").isalnum() else "document_inspection_failed")
        return payload["info"]


def _child():
    # The source image runs on Linux. The portable timeout remains active on
    # platforms without resource limits; no cloud credential is ever required.
    if os.name == "posix":
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES))
    try:
        from source_ocr import inspect_document
        data = Path(sys.argv[1]).read_bytes()
        info = inspect_document(data, int(sys.argv[2]))
        print(json.dumps({"info": info}))
    except Exception as error:
        code = str(error) if isinstance(error, OCRError) else "document_inspection_failed"
        print(json.dumps({"error_code": code}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_child())
