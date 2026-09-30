"""Local authenticated funding metadata; never a payment or trading API."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from .billing_store import BillingStore
from .local_origin import is_local, session_cookie, valid_origin
from .review_accounts import ReviewError
from scripts.billing_status import compose, read_usage
from scripts.opportunity_common import timestamp


def create_blueprint(review_store, billing_store=None):
    blueprint = Blueprint('billing', __name__, url_prefix='/api/billing')
    store = billing_store or BillingStore()

    @blueprint.before_request
    def boundary():
        if not is_local() or not current_app.config.get('RUNTIME_BILLING_USAGE_PATH'):
            raise ReviewError('LOCAL_BILLING_ONLY', 'Funding metadata is available only on the configured local runtime.', 503)
        if request.remote_addr != '127.0.0.1' or request.host != '127.0.0.1:8765':
            raise ReviewError('LOCAL_ONLY', 'Open funding on the local PolitiTrack origin.', 403)
        if str(current_app.config.get('RUNTIME_PERSONAL_REVIEWS_ENABLED', '')).lower() not in {'true', '1', 'yes'}:
            raise ReviewError('REVIEWS_UNAVAILABLE', 'Existing dashboard sign-in is disabled.', 503)
        owner = review_store.account_for_session(request.cookies.get(session_cookie()))
        if not owner:
            raise ReviewError('SIGN_IN_REQUIRED', 'Sign in with your existing PolitiTrack review account to view funding.', 401)
        g.billing_owner = owner
        if request.method != 'GET':
            origin = current_app.config.get('RUNTIME_REVIEW_ORIGIN')
            if not valid_origin(origin) or request.headers.get('Origin') != origin.rstrip('/') or request.headers.get('X-PolitiTrack-Review-Request') != '1':
                raise ReviewError('ORIGIN_DENIED', 'Record balances from the local PolitiTrack dashboard.', 403)
            if request.mimetype != 'application/json':
                raise ReviewError('JSON_REQUIRED', 'Submit the balance form as JSON.', 415)
            if request.content_length is not None and request.content_length > 16384:
                raise ReviewError('REQUEST_TOO_LARGE', 'The balance observation is too large.', 413)
            raw = request.stream.read(16385)
            if len(raw) > 16384:
                raise ReviewError('REQUEST_TOO_LARGE', 'The balance observation is too large.', 413)
            try:
                value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                if not isinstance(value, dict):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                raise ReviewError('INVALID_JSON', 'The balance observation is invalid.') from None
            if value.get('expected_account_id') != owner['account_id']:
                raise ReviewError('ACCOUNT_CHANGED', 'The signed-in account changed. Refresh before saving.', 409)
            g.billing_payload = value

    @blueprint.after_request
    def private(response):
        response.headers.update({'Cache-Control': 'private, no-store, max-age=0', 'Pragma': 'no-cache',
            'Vary': 'Cookie', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'})
        return response

    @blueprint.errorhandler(ReviewError)
    def known(error):
        return jsonify(code=error.code, message=error.message), error.status

    @blueprint.errorhandler(Exception)
    def unknown(error):
        if isinstance(error, HTTPException):
            return jsonify(code='REQUEST_REJECTED', message='The billing request was rejected.'), error.code
        current_app.logger.error('Billing metadata unavailable: %s', type(error).__name__)
        return jsonify(code='BILLING_UNAVAILABLE', message='Funding evidence is unavailable; no zero-balance claim is made.'), 503

    def render(state):
        now = store.clock()
        earliest = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        observation = state['latest'].get('openai_api')
        if observation:
            earliest = min(earliest, timestamp(observation['observed_at']))
        usage_path = Path(current_app.config['RUNTIME_BILLING_USAGE_PATH'])
        events, coverage = read_usage(usage_path, earliest)
        result = compose(state['latest'], events, coverage,
                         current_app.config.get('RUNTIME_OPENAI_BILLING_SCOPE'), now)
        result.update(authenticated=True, account_id=g.billing_owner['account_id'], revision=state['revision'],
                      history_count=len(state['events']), history_head_sha256=state['head_sha256'])
        return jsonify(result)

    @blueprint.get('/status')
    def status():
        return render(store.read(g.billing_owner['account_id']))

    @blueprint.post('/observations')
    def save():
        data = g.billing_payload
        if set(data) != {'expected_account_id', 'expected_revision', 'request_id', 'observation'}:
            raise ReviewError('INVALID_BILLING_REQUEST', 'Submit only the fields in the balance form.')
        state = store.save(g.billing_owner['account_id'], data['observation'], expected_revision=data['expected_revision'],
                           request_id=data['request_id'], scope=current_app.config.get('RUNTIME_OPENAI_BILLING_SCOPE'))
        return render(state)
    return blueprint
