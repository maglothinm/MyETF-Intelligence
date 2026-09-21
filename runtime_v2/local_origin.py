"""Explicit loopback-only deployment boundary; remote deployments retain HTTPS."""
from urllib.parse import urlsplit

from flask import current_app, request


def is_local(config=None):
    config = current_app.config if config is None else config
    return str(config.get("RUNTIME_LOCAL_ONLY", "")).lower() == "true"


def valid_origin(origin):
    parsed = urlsplit(origin)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query
            or parsed.fragment or parsed.path not in {"", "/"}):
        return False
    if is_local():
        return (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                and parsed.port == 8765 and request.remote_addr == "127.0.0.1"
                and request.host == "127.0.0.1:8765")
    return parsed.scheme == "https"


def session_cookie():
    return "polititrack_local_session" if is_local() else "__Host-polititrack-review-session"
