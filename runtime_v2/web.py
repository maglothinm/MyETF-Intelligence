"""Cloud Run web application for the generated dashboard and Filing Vault API."""

from __future__ import annotations

import os
import tempfile
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Mapping

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import safe_join

from .store import PostgresSnapshotStore, StateStoreError


def _truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _stream_dashboard_response(response, target: Path):
    """Keep growing public ledgers below Cloud Run's buffered response limit."""
    text_asset = target.suffix.lower() in {".json", ".csv", ".html", ".js", ".css", ".svg", ".txt"}
    compressible = text_asset and target.stat().st_size >= 65536
    if compressible:
        response.vary.add("Accept-Encoding")
    if response.status_code == 200 and compressible and request.accept_encodings["gzip"] > 0:
        response.headers["Content-Encoding"] = "gzip"
        etag, _ = response.get_etag()
        if etag:
            # Identity and gzip are semantically equivalent, not byte-identical.
            response.set_etag(etag, weak=True)
        response.headers.pop("Content-Length", None)
        response.automatically_set_content_length = False
        if request.method != "HEAD":
            original = response.response

            def encoded():
                compressor = zlib.compressobj(wbits=31)
                try:
                    for chunk in original:
                        compressed = compressor.compress(chunk)
                        if compressed:
                            yield compressed
                    yield compressor.flush()
                finally:
                    original.close()

            response.response = encoded()
            response.direct_passthrough = False
            response.call_on_close(original.close)
    elif response.status_code in {200, 206} and request.method != "HEAD" and (response.content_length or 0) >= 32 * 1024 * 1024:
        # Identity-only clients also need streaming. Let the WSGI server select
        # chunked transfer encoding; application code must not set that header.
        response.headers.pop("Content-Length", None)
        response.automatically_set_content_length = False
    return response


class DashboardCache:
    def __init__(self, store: PostgresSnapshotStore, refresh_seconds: int = 30):
        self.store = store
        self.refresh_seconds = max(5, refresh_seconds)
        self._lock = threading.Lock()
        self._active: Path | None = None
        self._sha256 = ""
        self._next_check = 0.0

    @property
    def active(self) -> Path | None:
        return self._active

    @property
    def sha256(self) -> str:
        return self._sha256

    def refresh(self, *, force: bool = False) -> Path:
        now = time.monotonic()
        if not force and self._active is not None and now < self._next_check:
            return self._active
        with self._lock:
            now = time.monotonic()
            if not force and self._active is not None and now < self._next_check:
                return self._active
            with self.store.locked("dashboard") as locked:
                head = locked.head()
                if head is None:
                    raise StateStoreError("no published Runtime v2 dashboard exists")
                if self._active is None or head.snapshot_sha256 != self._sha256:
                    destination = Path(tempfile.mkdtemp(prefix="polititrack-site-"))
                    locked.restore(destination)
                    if not (destination / "index.html").is_file():
                        raise StateStoreError("dashboard snapshot has no index.html")
                    self._active = destination
                    self._sha256 = head.snapshot_sha256
            self._next_check = now + self.refresh_seconds
            return self._active


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    store: PostgresSnapshotStore | None = None,
    review_store=None,
    operation_store=None,
    operation_cloud=None,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update({key: value for key, value in os.environ.items() if key.startswith(("VAULT_", "RUNTIME_"))})
    if config:
        app.config.update(config)
    runtime_store = store or PostgresSnapshotStore()
    cache = DashboardCache(runtime_store, int(app.config.get("RUNTIME_DASHBOARD_REFRESH_SECONDS", 30)))
    app.extensions["runtime_v2_store"] = runtime_store
    app.extensions["runtime_v2_dashboard"] = cache

    from .review_accounts import PersonalReviewStore
    from .review_api import create_blueprint

    personal_reviews = review_store or PersonalReviewStore()
    app.extensions["personal_reviews"] = personal_reviews
    app.register_blueprint(create_blueprint(personal_reviews, cache))
    from .operations_api import create_blueprint as operations_blueprint
    app.register_blueprint(operations_blueprint(personal_reviews, operation_store, operation_cloud))

    if _truthy(app.config.get("VAULT_ENABLED")):
        from backend.filing_vault import init_app
        from .database import sqlalchemy_engine

        if not app.config.get("VAULT_DATABASE_URL") and not os.environ.get("DATABASE_URL"):
            app.config["VAULT_ENGINE"] = sqlalchemy_engine()
        else:
            app.config.setdefault("VAULT_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
        init_app(app)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok", service="polititrack-runtime-v2")

    @app.get("/readyz")
    def ready():
        try:
            cache.refresh()
        except Exception:
            return jsonify(status="unavailable", dashboard=False), 503
        return jsonify(status="ready", dashboard=True, snapshot_sha256=cache.sha256)

    @app.get("/")
    @app.get("/<path:filename>")
    def dashboard(filename: str = "index.html"):
        try:
            root = cache.refresh()
        except Exception:
            return jsonify(code="DASHBOARD_UNAVAILABLE", message="The latest verified dashboard is unavailable."), 503
        candidate = safe_join(str(root), filename)
        if candidate is None:
            return jsonify(code="NOT_FOUND", message="The requested dashboard resource does not exist."), 404
        target = Path(candidate)
        if not target.is_file():
            if "." not in Path(filename).name:
                target = root / "index.html"
            if not target.is_file():
                return jsonify(code="NOT_FOUND", message="The requested dashboard resource does not exist."), 404
        response = _stream_dashboard_response(send_from_directory(root, target.relative_to(root).as_posix()), target)
        response.headers["X-PolitiTrack-Snapshot"] = cache.sha256
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app
