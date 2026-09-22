"""Owner-authorized raw-file intake, separate from disabled Filing Vault controls."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from .review_api import COOKIE
from .local_origin import session_cookie, valid_origin
from .review_accounts import ReviewError
from .source_uploads import SourceUploadStore
from scripts.source_ocr import MAX_BYTES, OCRError


def create_blueprint(accounts, cache, intake=None):
    blueprint = Blueprint("source_ocr", __name__, url_prefix="/api/source-ocr")
    inbox = intake or SourceUploadStore()

    @blueprint.before_request
    def boundary():
        if str(current_app.config.get("RUNTIME_SOURCE_OCR_ENABLED", "")).lower() not in {"true", "1", "yes"}:
            raise ReviewError("OCR_UNAVAILABLE", "Source upload and OCR are not enabled in this deployment.", 503)
        g.ocr_account = accounts.account_for_session(request.cookies.get(session_cookie()))
        if not g.ocr_account:
            raise ReviewError("SIGN_IN_REQUIRED", "Sign in to upload source files.", 401)
        owners = str(current_app.config.get("RUNTIME_SOURCE_OCR_ACCOUNT_IDS", "")).split(",")
        if g.ocr_account["account_id"] not in {owner.strip() for owner in owners if owner.strip()}:
            raise ReviewError("OWNER_REQUIRED", "Source uploads require an authorized account.", 403)
        if request.method != "GET":
            origin = str(current_app.config.get("RUNTIME_REVIEW_ORIGIN", "")).rstrip("/")
            if (not valid_origin(origin)
                or request.headers.get("Origin") != origin or request.headers.get("X-PolitiTrack-Source-Request") != "1"):
                raise ReviewError("ORIGIN_DENIED", "Upload from the PolitiTrack source form.", 403)
            if request.headers.get("X-PolitiTrack-Account") != g.ocr_account["account_id"]:
                raise ReviewError("ACCOUNT_CHANGED", "The signed-in account changed. Refresh before uploading.", 409)

    @blueprint.after_request
    def privacy(response):
        response.headers.update({"Cache-Control": "private, no-store", "Vary": "Cookie", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
        return response

    @blueprint.errorhandler(ReviewError)
    def rejected(error):
        return jsonify(code=error.code, message=error.message), error.status

    @blueprint.errorhandler(OCRError)
    def invalid(error):
        return jsonify(code=str(error), message="The file is invalid, encrypted, oversized or unsupported. Upload a PDF, PNG, JPEG or TIFF of up to 20 MiB. Manual uploads have no page-count cap; file validation and resource safeguards still apply."), 400

    @blueprint.errorhandler(Exception)
    def unavailable(error):
        if isinstance(error, HTTPException):
            return jsonify(code="UPLOAD_REJECTED", message="The upload request was rejected."), error.code
        current_app.logger.error("Source intake unavailable: %s", type(error).__name__)
        return jsonify(code="OCR_UNAVAILABLE", message="The source inbox is temporarily unavailable."), 503

    def filings():
        rows = json.loads((cache.refresh() / "data/filings.json").read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ReviewError("INVENTORY_UNAVAILABLE", "Refresh the source inventory before uploading.", 503)
        return rows

    @blueprint.get("/status")
    def status():
        rows = filings()
        counts = {}
        for row in rows:
            value = row.get("ocr_status", "pending")
            counts[value] = counts.get(value, 0) + 1
        return jsonify(account_id=g.ocr_account["account_id"], uploads=inbox.read(g.ocr_account["account_id"]),
                       coverage=counts, note="Coverage is from the last published source snapshot, not a live queue estimate.")

    @blueprint.post("/upload")
    def upload():
        key = request.args.get("filing_key", "")
        matches = [row for row in filings() if row.get("filing_key") == key]
        if len(matches) != 1 or matches[0].get("source") not in {"house", "senate", "oge"}:
            raise ReviewError("FILING_REQUIRED", "Select one existing official filing to associate with this file.", 400)
        row = matches[0]
        if row.get("branch") != ("executive" if row["source"] == "oge" else "legislative") or not row.get("source_url"):
            raise ReviewError("FILING_INVALID", "The selected filing lacks a usable source identity.", 400)
        if request.content_length is None or not 0 < request.content_length <= MAX_BYTES:
            raise ReviewError("UPLOAD_TOO_LARGE", "Upload a file of up to 20 MiB.", 413)
        # Raw bytes, not multipart: no unbounded form parser or user-controlled
        # filename/path. Content type is advisory; signature/decoding is decisive.
        data = request.stream.read(MAX_BYTES + 1)
        if len(data) != request.content_length:
            raise ReviewError("UPLOAD_INCOMPLETE", "The file upload was incomplete.", 400)
        return jsonify(inbox.submit(g.ocr_account["account_id"], row, data)), 202

    @blueprint.post("/confirm")
    def confirm():
        if request.mimetype != "application/json" or request.content_length is None or request.content_length > 256 * 1024:
            raise ReviewError("INVALID_CONFIRMATION", "Use the source review form to confirm corrected rows.", 400)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ReviewError("INVALID_CONFIRMATION", "The source review request is invalid.")
        return jsonify(inbox.confirm(g.ocr_account["account_id"], payload.get("upload_id"),
                                     payload.get("sha256"), payload.get("rows"))), 202

    return blueprint
