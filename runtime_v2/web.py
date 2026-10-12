"""Cloud Run web application for the generated dashboard and Filing Vault API."""

from __future__ import annotations

import os
import logging
import shutil
import tempfile
import threading
import time
import zlib
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import safe_join
from werkzeug.wsgi import ClosingIterator

from .store import PostgresSnapshotStore, SnapshotHead, StateStoreError


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


@dataclass(frozen=True)
class DashboardPublication:
    root: Path
    head: SnapshotHead


class DashboardCache:
    def __init__(self, store: PostgresSnapshotStore, refresh_seconds: int = 30):
        self.store = store
        self.refresh_seconds = max(5, refresh_seconds)
        self._lock = threading.RLock()
        self._publication: DashboardPublication | None = None
        self._next_check = 0.0
        self._readers: dict[Path, int] = {}
        self._retired: set[Path] = set()

    @property
    def active(self) -> Path | None:
        publication = self._publication
        return publication.root if publication else None

    @property
    def sha256(self) -> str:
        publication = self._publication
        return publication.head.snapshot_sha256 if publication else ""

    def refresh(self, *, force: bool = False) -> Path:
        return self.refresh_publication(force=force).root

    @contextmanager
    def read(self, *, force: bool = False):
        """Keep a verified publication alive through a file read or response body."""
        with self._lock:
            publication = self.refresh_publication(force=force)
            self._readers[publication.root] = self._readers.get(publication.root, 0) + 1
        try:
            yield publication
        finally:
            with self._lock:
                remaining = self._readers[publication.root] - 1
                if remaining:
                    self._readers[publication.root] = remaining
                else:
                    del self._readers[publication.root]
                self._prune_retired()

    def _prune_retired(self) -> None:
        """Remove only this instance's unused copies, never another process's cache."""
        current = self._publication.root if self._publication else None
        for root in tuple(self._retired):
            if root == current or self._readers.get(root, 0):
                continue
            try:
                shutil.rmtree(root)
            except FileNotFoundError:
                self._retired.discard(root)
            except OSError as exc:
                # Windows can briefly retain an open file handle after a response
                # closes. Keep this owned path queued; don't fail a verified read.
                logging.getLogger(__name__).warning(
                    "dashboard_cache_cleanup_deferred exception_type=%s", type(exc).__name__,
                )
            else:
                self._retired.discard(root)

    @staticmethod
    def _assert_forward(head: SnapshotHead, previous: SnapshotHead | None) -> None:
        if previous is not None and (
            head.generation < previous.generation
            or (
                head.generation == previous.generation
                and (head.snapshot_id, head.snapshot_sha256)
                != (previous.snapshot_id, previous.snapshot_sha256)
            )
        ):
            raise StateStoreError("dashboard head regressed or changed an immutable generation")

    def refresh_publication(self, *, force: bool = False) -> DashboardPublication:
        """Return one verified directory and its matching committed snapshot head."""
        now = time.monotonic()
        publication = self._publication
        if not force and publication is not None and now < self._next_check:
            return publication
        with self._lock:
            now = time.monotonic()
            publication = self._publication
            if not force and publication is not None and now < self._next_check:
                return publication
            destination: Path | None = None
            try:
                # Readers observe an immutable committed head while the sole
                # publisher builds its successor. They must not compete for the
                # publisher's exclusive advisory lock.
                head = self.store.latest_head("dashboard")
                if head is None:
                    raise StateStoreError("no published Runtime v2 dashboard exists")
                self._assert_forward(head, publication.head if publication else None)
                if (
                    publication is None
                    or head.snapshot_sha256 != publication.head.snapshot_sha256
                    or not (publication.root / "index.html").is_file()
                ):
                    destination = Path(tempfile.mkdtemp(prefix="polititrack-site-"))
                    restored = self.store.restore_latest("dashboard", destination)
                    self._assert_forward(restored, head)
                    if not (destination / "index.html").is_file():
                        raise StateStoreError("dashboard snapshot has no index.html")
                    # The publisher can advance between the metadata probe and
                    # restore. Only the restore's exact head describes these bytes.
                    publication = DashboardPublication(destination, restored)
                else:
                    publication = DashboardPublication(publication.root, head)
                previous = self._publication
                self._publication = publication
                if previous is not None and previous.root != publication.root:
                    self._retired.add(previous.root)
                self._prune_retired()
            except Exception:
                if destination is not None:
                    self._retired.add(destination)
                    self._prune_retired()
                # A failed forced check also invalidates the ordinary cache TTL;
                # following requests must not hide a known verification failure.
                self._next_check = 0.0
                raise
            self._next_check = now + self.refresh_seconds
            return publication


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    store: PostgresSnapshotStore | None = None,
    review_store=None,
    operation_store=None,
    operation_cloud=None,
    source_upload_store=None,
) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update({key: value for key, value in os.environ.items() if key.startswith(("VAULT_", "RUNTIME_"))})
    if config:
        app.config.update(config)
    from .local_origin import is_local
    if is_local(app.config):
        @app.before_request
        def require_loopback():
            # Do not trust forwarded headers or DNS names in local mode.
            if request.remote_addr != "127.0.0.1" or request.host != "127.0.0.1:8765":
                return jsonify(code="LOCAL_ONLY", message="Open PolitiTrack on this computer."), 403
    runtime_store = store or PostgresSnapshotStore()
    cache = DashboardCache(runtime_store, int(app.config.get("RUNTIME_DASHBOARD_REFRESH_SECONDS", 30)))
    app.extensions["runtime_v2_store"] = runtime_store
    app.extensions["runtime_v2_dashboard"] = cache

    from .review_accounts import PersonalReviewStore
    from .review_api import create_blueprint

    personal_reviews = review_store or PersonalReviewStore()
    app.extensions["personal_reviews"] = personal_reviews
    app.register_blueprint(create_blueprint(personal_reviews, cache))
    from .billing_api import create_blueprint as billing_blueprint
    app.register_blueprint(billing_blueprint(personal_reviews))
    from .operations_api import create_blueprint as operations_blueprint
    app.register_blueprint(operations_blueprint(personal_reviews, operation_store, operation_cloud))
    from .source_ocr_api import create_blueprint as source_ocr_blueprint
    app.register_blueprint(source_ocr_blueprint(personal_reviews, cache, source_upload_store))

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
            with cache.read() as publication:
                return jsonify(status="ready", dashboard=True, snapshot_sha256=publication.head.snapshot_sha256)
        except Exception as exc:
            app.logger.error("dashboard_refresh_failed exception_type=%s", type(exc).__name__)
            return jsonify(status="unavailable", dashboard=False), 503

    @app.get("/")
    @app.get("/<path:filename>")
    def dashboard(filename: str = "index.html"):
        lease = cache.read()
        try:
            publication = lease.__enter__()
        except Exception as exc:
            app.logger.error("dashboard_refresh_failed exception_type=%s", type(exc).__name__)
            return jsonify(code="DASHBOARD_UNAVAILABLE", message="The latest verified dashboard is unavailable."), 503
        released = False
        release_guard = threading.Lock()

        def release():
            nonlocal released
            with release_guard:
                if released:
                    return
                released = True
            lease.__exit__(None, None, None)

        response = None
        try:
            root = publication.root
            candidate = safe_join(str(root), filename)
            if candidate is None:
                release()
                return jsonify(code="NOT_FOUND", message="The requested dashboard resource does not exist."), 404
            target = Path(candidate)
            if not target.is_file():
                if "." not in Path(filename).name:
                    target = root / "index.html"
                if not target.is_file():
                    release()
                    return jsonify(code="NOT_FOUND", message="The requested dashboard resource does not exist."), 404
            response = send_from_directory(root, target.relative_to(root).as_posix())
            response = _stream_dashboard_response(response, target)
            response.headers["X-PolitiTrack-Snapshot"] = publication.head.snapshot_sha256
            response.headers["X-Content-Type-Options"] = "nosniff"
            body = response.response
            body_closed = False
            close_guard = threading.Lock()

            def close_body():
                nonlocal body_closed
                with close_guard:
                    if body_closed:
                        return
                    body_closed = True
                try:
                    close = getattr(body, "close", None)
                    if close:
                        close()
                finally:
                    release()

            def leased_body():
                try:
                    yield from body
                finally:
                    close_body()

            # Direct-passthrough WSGI bodies can bypass Response.close callbacks.
            # Cover exhaustion, client disconnect, and a body never iterated.
            response.response = ClosingIterator(leased_body(), close_body)
            response.call_on_close(close_body)
            if request.method == "HEAD" or response.status_code in {204, 304}:
                close_body()
            return response
        except Exception:
            try:
                if response is not None:
                    response.close()
            finally:
                release()
            raise

    return app
