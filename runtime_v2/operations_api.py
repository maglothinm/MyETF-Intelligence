"""Private same-origin run controls; ordinary review accounts cannot dispatch."""
import json
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .operations import CloudRunJobs, JOBS, OperationStore, request_uuid, unavailable
from .review_accounts import ReviewError
from .review_api import COOKIE


def create_blueprint(reviews, operations=None, cloud=None):
    blueprint = Blueprint("operations", __name__, url_prefix="/api/operations")
    store = operations or OperationStore()

    @blueprint.before_request
    def boundary():
        if (str(current_app.config.get("RUNTIME_OPERATIONS_ENABLED", "")).lower() != "true"
            or str(current_app.config.get("RUNTIME_PERSONAL_REVIEWS_ENABLED", "")).lower() != "true"):
            raise unavailable()
        account = reviews.account_for_session(request.cookies.get(COOKIE))
        if not account:
            raise ReviewError("SIGN_IN_REQUIRED", "Sign in to use run controls.", 401)
        allowed = set(str(current_app.config.get("RUNTIME_OPERATIONS_ACCOUNT_IDS", "")).split(","))
        if account["account_id"] not in allowed:
            raise ReviewError("OPERATOR_REQUIRED", "Only the owner can start production runs.", 403)
        g.operation_account = account["account_id"]
        if request.method != "GET":
            origin = str(current_app.config.get("RUNTIME_REVIEW_ORIGIN", ""))
            parsed = urlsplit(origin)
            if (parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment or parsed.username):
                raise unavailable()
            if request.headers.get("Origin") != origin.rstrip("/") or request.headers.get("X-PolitiTrack-Operation-Request") != "1":
                raise ReviewError("ORIGIN_DENIED", "Open PolitiTrack to start this run.", 403)
            if request.mimetype != "application/json":
                raise ReviewError("JSON_REQUIRED", "Use the Run now button to start a run.", 415)
            raw = request.stream.read(4097)
            if len(raw) > 4096:
                raise ReviewError("REQUEST_TOO_LARGE", "The run request is too large.", 413)
            try:
                g.operation_payload = json.loads(raw)
                if not isinstance(g.operation_payload, dict) or set(g.operation_payload) != {"expected_account_id", "request_id"}:
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                raise ReviewError("INVALID_REQUEST", "Refresh before starting a run.") from None
            if g.operation_payload["expected_account_id"] != g.operation_account:
                raise ReviewError("ACCOUNT_CHANGED", "The signed-in account changed. Refresh before starting a run.", 409)
            request_uuid(g.operation_payload["request_id"])

    @blueprint.after_request
    def privacy(response):
        response.headers.update({"Cache-Control": "private, no-store, max-age=0", "Pragma": "no-cache",
            "Vary": "Cookie", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
        return response

    @blueprint.errorhandler(ReviewError)
    def expected(error):
        return jsonify(code=error.code, message=error.message), error.status

    @blueprint.errorhandler(Exception)
    def unexpected(error):
        if isinstance(error, HTTPException):
            return jsonify(code="REQUEST_REJECTED", message="This run request could not be accepted."), error.code
        current_app.logger.error("Run control unavailable: %s", type(error).__name__)
        return expected(unavailable())

    def client():
        return cloud or CloudRunJobs(current_app.config.get("RUNTIME_OPERATIONS_PROJECT"),
                                    current_app.config.get("RUNTIME_OPERATIONS_REGION"))

    @blueprint.get("")
    def status():
        runtime = client()
        return jsonify(account_id=g.operation_account, jobs={job: store.status(job, runtime) for job in JOBS})

    @blueprint.post("/<job>/runs")
    def start(job):
        if job not in JOBS:
            raise ReviewError("UNKNOWN_JOB", "This service has no manual run control.", 404)
        result = store.start(job, g.operation_account, g.operation_payload["request_id"], client())
        return jsonify(account_id=g.operation_account, job=job, latest_request=result), 202

    return blueprint
