"""Same-origin, authenticated API for each person's durable review history."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .review_accounts import LOGICAL_ID, PersonalReviewStore, ReviewError, SESSION_SECONDS

COOKIE = "__Host-polititrack-review-session"


def publication_identities(root):
    model = json.loads((root / "data/dashboard-insights.json").read_text(encoding="utf-8"))
    reviews = model["reviews"]
    identities = reviews["manual_exception_identities"]
    ids = reviews["manual_exception_ids"]
    if (not isinstance(identities, dict) or not isinstance(ids, list)
        or len(ids) != len(set(ids)) or set(identities) != set(ids)
        or reviews["manual_exception"] != len(ids)
        or any(not isinstance(value, str) or not LOGICAL_ID.fullmatch(value) for value in identities.values())):
        raise ReviewError("REVIEW_PUBLICATION_UNAVAILABLE", "The retained review inventory is unavailable. Try again shortly.", 503)
    return identities


def create_blueprint(store: PersonalReviewStore, cache):
    blueprint = Blueprint("personal_reviews", __name__, url_prefix="/api/reviews")

    @blueprint.before_request
    def boundary():
        enabled = str(current_app.config.get("RUNTIME_PERSONAL_REVIEWS_ENABLED", "")).lower() in {"1", "true", "yes"}
        if not enabled:
            raise ReviewError("REVIEWS_UNAVAILABLE", "Personal review sign-in is temporarily unavailable.", 503)
        if request.method != "GET":
            origin = current_app.config.get("RUNTIME_REVIEW_ORIGIN") or request.host_url.rstrip("/")
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
                raise ReviewError("REVIEWS_UNAVAILABLE", "Personal review sign-in is temporarily unavailable.", 503)
            if request.headers.get("Origin") != origin.rstrip("/") or request.headers.get("X-PolitiTrack-Review-Request") != "1":
                raise ReviewError("ORIGIN_DENIED", "Open PolitiTrack to make this change.", 403)
            if request.mimetype != "application/json":
                raise ReviewError("JSON_REQUIRED", "Submit the change from the PolitiTrack form.", 415)
            limit = 256 * 1024 if request.endpoint == "personal_reviews.import_saved" else 16 * 1024
            if request.content_length is not None and request.content_length > limit:
                raise ReviewError("REQUEST_TOO_LARGE", "This review request is too large.", 413)
            raw = request.stream.read(limit + 1)
            if len(raw) > limit or (request.environ.get("wsgi.input_terminated") and len(raw) >= limit):
                raise ReviewError("REQUEST_TOO_LARGE", "This review request is too large.", 413)
            try:
                g.review_payload = json.loads(raw)
                if not isinstance(g.review_payload, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                raise ReviewError("INVALID_JSON", "The review request is invalid.") from None

    @blueprint.after_request
    def privacy(response):
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Vary"] = "Cookie"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @blueprint.errorhandler(ReviewError)
    def review_error(error):
        return jsonify(code=error.code, message=error.message), error.status

    @blueprint.errorhandler(Exception)
    def unavailable(error):
        if isinstance(error, HTTPException):
            return jsonify(code="REQUEST_REJECTED", message="The review request could not be accepted."), error.code
        current_app.logger.error("Personal review service unavailable: %s", type(error).__name__)
        return jsonify(code="REVIEWS_UNAVAILABLE", message="Your saved reviews are temporarily unavailable. Try again shortly."), 503

    def account(required=True):
        value = store.account_for_session(request.cookies.get(COOKIE))
        if required and not value:
            raise ReviewError("SIGN_IN_REQUIRED", "Sign in to load your saved reviews.", 401)
        return value

    def account_for_change():
        owner = account()
        if g.review_payload.get("expected_account_id") != owner["account_id"]:
            raise ReviewError("ACCOUNT_CHANGED", "The signed-in account changed. Refresh before saving a review.", 409)
        return owner

    def signed_in(token):
        owner = store.account_for_session(token)
        response = jsonify(authenticated=True, **store.read(owner["account_id"]))
        response.set_cookie(COOKIE, token, secure=True, httponly=True, samesite="Strict", path="/", max_age=SESSION_SECONDS)
        return response

    @blueprint.get("/session")
    def session():
        owner = account(required=False)
        if not owner:
            return jsonify(authenticated=False)
        return jsonify(authenticated=True, **store.read(owner["account_id"]))

    @blueprint.get("/state")
    def state():
        return jsonify(authenticated=True, **store.read(account()["account_id"]))

    @blueprint.post("/activate")
    def activate():
        data = g.review_payload
        return signed_in(store.activate(data.get("invitation"), data.get("password"), remote=request.remote_addr or "unknown"))

    @blueprint.post("/login")
    def login():
        data = g.review_payload
        return signed_in(store.login(data.get("username"), data.get("password"), remote=request.remote_addr or "unknown"))

    @blueprint.post("/logout")
    def logout():
        store.logout(request.cookies.get(COOKIE))
        response = jsonify(authenticated=False)
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="Strict")
        return response

    @blueprint.post("/acknowledgements")
    def change():
        owner, data = account_for_change(), g.review_payload
        identities = publication_identities(cache.refresh())
        review_id = data.get("review_id")
        if not isinstance(review_id, str) or identities.get(review_id) != data.get("logical_review_id") or review_id not in identities:
            raise ReviewError("REVIEW_CHANGED", "This review changed in the current publication. Refresh and try again.", 409)
        result = store.set_acknowledged(owner["account_id"], review_id, data.get("logical_review_id"),
            data.get("acknowledged"), data.get("expected_revision"), data.get("request_id"))
        return jsonify(authenticated=True, **result)

    @blueprint.post("/import")
    def import_saved():
        owner, data = account_for_change(), g.review_payload
        if data.get("version") != 1:
            raise ReviewError("INVALID_IMPORT", "This saved review format is not supported.")
        result = store.import_legacy(owner["account_id"], data.get("acknowledged"), publication_identities(cache.refresh()))
        return jsonify(authenticated=True, **result)

    return blueprint
