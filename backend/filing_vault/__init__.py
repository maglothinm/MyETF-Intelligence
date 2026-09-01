"""Optional Filing Vault service, reusing Flask, SQLAlchemy and private Supabase.

Importing this package never opens the legacy eager database connection. The
application factory is usable independently by a WSGI server and by tests.
"""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from werkzeug.exceptions import HTTPException

from .api import create_blueprint
from .providers import ProviderRegistry, SecureHTTPClient
from .service import VaultService
from .storage import FileObjectStore, SupabaseObjectStore


def _csv(value):
    if isinstance(value, (list, tuple, set)):
        return tuple(value)
    return tuple(item.strip() for item in str(value or "").split(",") if item.strip())


def configured_service(config):
    supplied = config.get("VAULT_SERVICE")
    if supplied:
        return supplied
    mode = config.get("VAULT_ENV", "production")
    database = config.get("VAULT_DATABASE_URL") or config.get("SQLALCHEMY_DATABASE_URI")
    if not database:
        raise ValueError("VAULT_DATABASE_URL must point to the persistent application database")
    if database.startswith("sqlite") and mode not in {"development", "test"}:
        raise ValueError("SQLite is supported only for explicit Filing Vault development/testing")
    if not database.startswith(("postgresql://", "postgresql+psycopg2://", "sqlite://")):
        raise ValueError("Use the existing PostgreSQL database or explicit development SQLite")
    options = {"pool_pre_ping": True}
    if database.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 5}
        if database.endswith(":memory:") or database == "sqlite://":
            options["poolclass"] = StaticPool
    engine = create_engine(database, **options)
    backend = config.get("VAULT_STORAGE_BACKEND", "supabase")
    maximum = int(config.get("VAULT_MAX_DOCUMENT_BYTES", 25 * 1024 * 1024))
    if maximum < 1024 or maximum > 50 * 1024 * 1024:
        raise ValueError("VAULT_MAX_DOCUMENT_BYTES must be between 1 KiB and 50 MiB")
    if backend == "filesystem":
        if mode not in {"development", "test"} or not config.get("VAULT_FILE_ROOT"):
            raise ValueError("Filesystem storage requires explicit development/test mode and VAULT_FILE_ROOT")
        store = FileObjectStore(config["VAULT_FILE_ROOT"],
                                repository_root=Path(__file__).resolve().parents[2], max_bytes=maximum)
    elif backend == "supabase":
        store = SupabaseObjectStore(config.get("VAULT_SUPABASE_URL", ""),
                                    config.get("VAULT_SUPABASE_KEY", ""),
                                    config.get("VAULT_SUPABASE_BUCKET", ""), max_bytes=maximum)
    else:
        raise ValueError("Unknown Filing Vault storage backend")
    providers = ProviderRegistry(http_client=SecureHTTPClient(max_bytes=maximum),
                                 agency_hosts=_csv(config.get("VAULT_AGENCY_HOSTS")),
                                 acknowledged_sources=_csv(config.get("VAULT_ACKNOWLEDGED_SOURCES")))
    return VaultService(engine, store, providers)


def init_app(app):
    """Register the optional API on the existing Flask application."""
    service = configured_service(app.config)
    app.extensions["filing_vault"] = service
    app.register_blueprint(create_blueprint(service,
        secret_key=app.config.get("VAULT_SECRET_KEY", ""),
        allowed_origins=_csv(app.config.get("VAULT_ALLOWED_ORIGINS"))))
    return service


def create_vault_app(config=None):
    app = Flask(__name__)
    app.config.update({key: value for key, value in os.environ.items() if key.startswith("VAULT_")})
    app.config.update(MAX_CONTENT_LENGTH=16 * 1024)
    if config:
        app.config.update(config)
    init_app(app)

    @app.errorhandler(HTTPException)
    def http_error(exc):
        # Missing/invalid API routes also return a useful, non-HTML error.
        response = jsonify(code="HTTP_" + str(exc.code), message=exc.description)
        response.status_code = exc.code
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app


__all__ = ["VaultService", "create_vault_app", "init_app"]
