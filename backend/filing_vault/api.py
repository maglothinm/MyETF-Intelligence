"""Known-ID Flask API and versioned acknowledgements without ambient cookies."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from urllib.parse import urlsplit

from flask import Blueprint, Response, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from . import schema
from .providers import ProviderError
from .service import CACHE_TTL_SECONDS, VaultError, utc_iso
from .storage import StorageError

ACK_TYPE = "federal_financial_disclosure"
ACK_VERSION = "1"
ACK_POLICY_VERSION = "source-access-policy-1"
ACK_TEXT = (
    "Federal financial disclosure reports are subject to statutory restrictions "
    "governing their acquisition and use. By continuing, you acknowledge those "
    "restrictions. This PolitiTrack acknowledgement does not replace a government "
    "acknowledgement, OGE Form 201, or an agency disclosure request when required."
)
LOG = logging.getLogger("polititrack.filing_vault")


def _origin(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            return None
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    except ValueError:
        return None


class RequestLimiter:
    """Bounded process-local abuse guard; production also needs proxy rate limits."""

    def __init__(self, *, clock=time.time):
        self.clock, self.entries, self.lock = clock, OrderedDict(), threading.Lock()

    def allow(self, key, limit, period):
        with self.lock:
            now = self.clock()
            timestamps = [stamp for stamp in self.entries.pop(key, []) if stamp > now - period]
            allowed = len(timestamps) < limit
            if allowed:
                timestamps.append(now)
            self.entries[key] = timestamps
            while len(self.entries) > 10000:
                self.entries.popitem(last=False)
            return allowed


def create_blueprint(service, *, secret_key, allowed_origins=()):
    if not isinstance(secret_key, str) or len(secret_key) < 32:
        raise ValueError("VAULT_SECRET_KEY must contain at least 32 characters")
    allowed = {_origin(value) for value in allowed_origins}
    if None in allowed or "*" in allowed:
        raise ValueError("VAULT_ALLOWED_ORIGINS requires exact HTTP(S) origins")
    signer = URLSafeTimedSerializer(secret_key, salt="polititrack-vault-ack-v1")
    limiter = RequestLimiter(clock=service.clock)
    blueprint = Blueprint("filing_vault", __name__, url_prefix="/api")

    def origin_allowed():
        origin = request.headers.get("Origin")
        if origin is None:
            return request.method in {"GET", "HEAD", "OPTIONS"}
        return _origin(origin) in allowed | {_origin(request.host_url)}

    @blueprint.before_request
    def protect_boundary():
        if not origin_allowed():
            raise VaultError("ORIGIN_DENIED", "This browser origin is not allowed to use the Filing Vault.", status=403)
        if request.method == "OPTIONS":
            return Response(status=204)
        if request.method == "POST" and request.mimetype != "application/json":
            raise VaultError("JSON_REQUIRED", "Submit this operation as JSON from the PolitiTrack application.", status=415)
        if request.method == "POST":
            # Bound this blueprint without changing unrelated embedded API
            # routes. Reading only limit+1 bytes also bounds chunked requests
            # when Content-Length is absent; Flask retains any stricter app cap.
            configured = current_app.config.get("MAX_CONTENT_LENGTH")
            limit = min(int(configured), 16 * 1024) if configured else 16 * 1024
            if request.content_length is not None and request.content_length > limit:
                raise VaultError("REQUEST_TOO_LARGE", "Filing Vault requests must be no larger than 16 KiB.", status=413)
            body = request.stream.read(limit + 1)
            # A stricter Flask LimitedStream may stop exactly at its cap without
            # exposing the extra byte. Conservatively reject an unknown-length
            # body that fills the cap, rather than accept a truncated JSON prefix.
            if len(body) > limit or (request.environ.get("wsgi.input_terminated") and len(body) >= limit):
                raise VaultError("REQUEST_TOO_LARGE", "Filing Vault requests must be no larger than 16 KiB.", status=413)
            try:
                g.vault_payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                raise VaultError("INVALID_JSON", "Provide a valid JSON request body.", status=400) from None

    @blueprint.after_request
    def secure_response(response):
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "sandbox; default-src 'none'; script-src 'none'; object-src 'none'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
        origin = request.headers.get("Origin")
        if origin and origin_allowed():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Expose-Headers"] = "X-Filing-Warning, X-Filing-Cache, X-Filing-SHA256, Content-Disposition"
            response.headers["Access-Control-Max-Age"] = "600"
        return response

    @blueprint.errorhandler(VaultError)
    @blueprint.errorhandler(ProviderError)
    def vault_error(exc):
        payload = {"code": exc.code, "message": exc.message}
        if getattr(exc, "filing", None):
            payload["filing"] = exc.filing
        return jsonify(payload), exc.status

    @blueprint.errorhandler(StorageError)
    @blueprint.errorhandler(SQLAlchemyError)
    def storage_error(_exc):
        # Database and storage exception strings may contain connection details.
        LOG.warning("vault_backend_unavailable")
        return jsonify(code="VAULT_UNAVAILABLE", message="The Filing Vault is temporarily unavailable. Please retry or open the Official Source."), 503

    @blueprint.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(code="HTTP_" + str(exc.code), message=exc.description), exc.code

    def receipt(optional=False):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer ") or len(authorization) > 4096:
            if optional:
                return None
            raise VaultError("ACKNOWLEDGEMENT_REQUIRED", "Acknowledge the Federal Financial Disclosure Notice to open this filing.", status=403)
        try:
            token = signer.loads(authorization[7:], max_age=CACHE_TTL_SECONDS)
            session_id = token["session"]
            if not isinstance(session_id, str) or len(session_id) > 128:
                raise ValueError("invalid session")
        except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
            if optional:
                return None
            raise VaultError("ACKNOWLEDGEMENT_REQUIRED", "The acknowledgement has expired. Please acknowledge the current notice.", status=403) from None
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()
        with service.engine.connect() as conn:
            ack = conn.execute(select(schema.acknowledgements).where(
                schema.acknowledgements.c.session_hash == session_hash)).mappings().first()
        if (not ack or ack["expires_at"] <= service.clock() or ack["version"] != ACK_VERSION
                or ack["policy_version"] != ACK_POLICY_VERSION or ack["acknowledgement_type"] != ACK_TYPE):
            if optional:
                return None
            raise VaultError("ACKNOWLEDGEMENT_REQUIRED", "Please acknowledge the current Federal Financial Disclosure Notice.", status=403)
        return dict(ack)

    def limited(kind, identifier, limit, period):
        key = kind + ":" + hmac.new(secret_key.encode(), str(identifier).encode(), hashlib.sha256).hexdigest()
        if not limiter.allow(key, limit, period):
            raise VaultError("RATE_LIMITED", "Too many Filing Vault requests. Please wait a moment and retry.", status=429)

    @blueprint.route("/filing-acknowledgements", methods=["GET", "POST"])
    def acknowledgement():
        if request.method == "GET":
            ack = receipt(optional=True)
            return jsonify(acknowledgement_type=ACK_TYPE, version=ACK_VERSION, policy_version=ACK_POLICY_VERSION,
                           text=ACK_TEXT, acknowledged=bool(ack), notice_required=not bool(ack),
                           accepted_at=utc_iso(ack["accepted_at"]) if ack else None)
        limited("ack", request.remote_addr or "unknown", 20, 3600)
        data = g.vault_payload
        if (not isinstance(data, dict) or data.get("accepted") is not True
                or data.get("version") != ACK_VERSION or data.get("policy_version") != ACK_POLICY_VERSION):
            raise VaultError("ACKNOWLEDGEMENT_INVALID", "Accept the current notice and policy versions before continuing.", status=400)
        current = receipt(optional=True)
        if current:
            # Do not extend a receipt's expiry simply because it was checked.
            return jsonify(acknowledged=True, token=request.headers["Authorization"][7:],
                           accepted_at=utc_iso(current["accepted_at"]), expires_at=utc_iso(current["expires_at"]),
                           acknowledgement_type=ACK_TYPE, version=ACK_VERSION, policy_version=ACK_POLICY_VERSION)
        session_id, now = secrets.token_urlsafe(32), service.clock()
        session_hash = hashlib.sha256(session_id.encode()).hexdigest()
        with service._transaction() as conn:
            conn.execute(insert(schema.acknowledgements).values(session_hash=session_hash,
                acknowledgement_type=ACK_TYPE, version=ACK_VERSION, policy_version=ACK_POLICY_VERSION,
                accepted_at=now, expires_at=now + CACHE_TTL_SECONDS))
        LOG.info("acknowledgement_accepted version=%s policy=%s", ACK_VERSION, ACK_POLICY_VERSION)
        return jsonify(acknowledged=True, token=signer.dumps({"session": session_id}),
                       accepted_at=utc_iso(now), expires_at=utc_iso(now + CACHE_TTL_SECONDS),
                       acknowledgement_type=ACK_TYPE, version=ACK_VERSION, policy_version=ACK_POLICY_VERSION), 201

    @blueprint.get("/filings")
    def filings():
        try:
            limit = int(request.args.get("limit", 100))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            raise VaultError("INVALID_PAGINATION", "Use integer limit and offset values.", status=400) from None
        return jsonify(service.list_filings(source=request.args.get("source"), search=request.args.get("search", "")[:200],
                       status=request.args.get("status"), filing_type=request.args.get("filing_type"),
                       sort=request.args.get("sort", "newest_filing"), limit=limit, offset=offset))

    @blueprint.get("/filings/<path:filing_id>")
    def filing(filing_id):
        return jsonify(filing=service.get_filing(filing_id))

    @blueprint.get("/filings/<path:filing_id>/official-source")
    def official(filing_id):
        record = service.get_filing(filing_id)
        return jsonify(filing_id=filing_id, official_source_url=record["official_source_url"])

    @blueprint.get("/filings/<path:filing_id>/document")
    def document(filing_id):
        ack = receipt()
        limited("document", ack["session_hash"], 120, 60)
        result = service.document(filing_id)
        # ID is hashed for a safe download filename; internal object keys never
        # appear in routes, headers or API metadata.
        suffix = "pdf" if result.content_type == "application/pdf" else "html"
        filename = "filing-" + hashlib.sha256(filing_id.encode()).hexdigest()[:20] + "." + suffix
        response = Response(result.body, mimetype=result.content_type)
        disposition = "attachment" if request.args.get("download") == "1" else "inline"
        response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        response.headers["X-Filing-Cache"] = "HIT" if result.cache_hit else "MISS"
        response.headers["X-Filing-SHA256"] = result.filing["sha256"]
        if result.warning:
            response.headers["X-Filing-Warning"] = result.warning
        return response

    @blueprint.post("/filings/<path:filing_id>/refresh")
    def refresh(filing_id):
        ack = receipt()
        limited("refresh", ack["session_hash"], 6, 60)
        result = service.document(filing_id, refresh=True)
        return jsonify(filing=result.filing, warning=result.warning, cache_hit=result.cache_hit)

    return blueprint
