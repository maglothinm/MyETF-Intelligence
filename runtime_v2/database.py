"""Database connections for local PostgreSQL and Cloud SQL."""

from __future__ import annotations

import atexit
import os
import threading
from typing import Any, Mapping


_connector: Any | None = None
_connector_lock = threading.Lock()


class DatabaseConfigurationError(RuntimeError):
    """Runtime database configuration is absent or unsafe."""


def _environment(config: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return os.environ if config is None else config


def database_url(config: Mapping[str, Any] | None = None) -> str:
    value = str(_environment(config).get("DATABASE_URL") or "").strip()
    if value.startswith("postgresql+psycopg2://"):
        value = "postgresql://" + value.split("://", 1)[1]
    return value


def _cloud_sql_settings(config: Mapping[str, Any] | None = None) -> tuple[str, str, str, str]:
    values = _environment(config)
    instance = str(values.get("INSTANCE_CONNECTION_NAME") or "").strip()
    database = str(values.get("DB_NAME") or "polititrack").strip()
    user = str(values.get("DB_USER") or values.get("DB_IAM_USER") or "").strip()
    password = str(values.get("DB_PASSWORD") or "")
    if not instance or not database or not user:
        raise DatabaseConfigurationError(
            "set DATABASE_URL or INSTANCE_CONNECTION_NAME, DB_NAME, and DB_USER"
        )
    return instance, database, user, password


def _use_private_ip(config: Mapping[str, Any] | None = None) -> bool:
    value = str(_environment(config).get("PRIVATE_IP") or "").strip().lower()
    if not value:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise DatabaseConfigurationError("PRIVATE_IP must be a boolean value")


def _cloud_connector():
    global _connector
    if _connector is None:
        with _connector_lock:
            if _connector is None:
                try:
                    from google.cloud.sql.connector import Connector
                except ImportError as exc:  # pragma: no cover - image dependency failure
                    raise DatabaseConfigurationError("Cloud SQL connector dependency is unavailable") from exc
                _connector = Connector(refresh_strategy="LAZY")
    return _connector


def close_connector() -> None:
    global _connector
    if _connector is not None:
        _connector.close()
        _connector = None


atexit.register(close_connector)


def connect(config: Mapping[str, Any] | None = None):
    """Return a DB-API PostgreSQL connection using the configured Cloud SQL route."""
    url = database_url(config)
    if url:
        if not url.startswith(("postgresql://", "postgres://")):
            raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL connection URL")
        try:
            import psycopg2
        except ImportError as exc:  # pragma: no cover - image dependency failure
            raise DatabaseConfigurationError("psycopg2 dependency is unavailable") from exc
        return psycopg2.connect(url, connect_timeout=15)

    instance, name, user, password = _cloud_sql_settings(config)
    try:
        from google.cloud.sql.connector import IPTypes
    except ImportError as exc:  # pragma: no cover - image dependency failure
        raise DatabaseConfigurationError("Cloud SQL connector dependency is unavailable") from exc

    options = {
        "user": user,
        "db": name,
        "enable_iam_auth": not bool(password),
        "timeout": 15,
        "ip_type": IPTypes.PRIVATE if _use_private_ip(config) else IPTypes.PUBLIC,
    }
    if password:
        options["password"] = password
    return _cloud_connector().connect(instance, "pg8000", **options)


def sqlalchemy_engine(config: Mapping[str, Any] | None = None):
    """Build a pooled SQLAlchemy engine over the same connection contract."""
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:  # pragma: no cover - image dependency failure
        raise DatabaseConfigurationError("SQLAlchemy dependency is unavailable") from exc
    url = database_url(config)
    if url:
        return create_engine(url, pool_pre_ping=True)
    return create_engine(
        "postgresql+pg8000://",
        creator=lambda: connect(config),
        pool_pre_ping=True,
        pool_recycle=1800,
    )
