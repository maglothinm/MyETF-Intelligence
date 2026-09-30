"""Private append-only owner funding observations in existing PostgreSQL backups."""
from __future__ import annotations
import json
import re
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, UniqueConstraint, insert, select
from .review_accounts import accounts, ReviewError, utc_now
from .database import sqlalchemy_engine
from scripts.opportunity_common import canonical, digest, timestamp, utc
from scripts.billing_status import validate_observation

metadata = MetaData()
observations = Table('runtime_billing_observations', metadata,
    Column('account_id', String(36), primary_key=True),
    Column('revision', Integer, primary_key=True),
    Column('request_id', String(36), nullable=False),
    Column('fingerprint', String(64), nullable=False),
    Column('payload', Text, nullable=False),
    Column('sha256', String(64), nullable=False),
    UniqueConstraint('account_id', 'request_id'))


class BillingStore:
    def __init__(self, engine=None, *, clock=utc_now):
        self._engine, self.clock = engine, clock

    @property
    def engine(self):
        if self._engine is None:
            self._engine = sqlalchemy_engine()
        return self._engine

    def initialize_schema(self):
        metadata.create_all(self.engine)  # Operator metadata only; no producer baseline.

    def _read(self, connection, account_id):
        rows = connection.execute(select(observations).where(observations.c.account_id == account_id)
                                  .order_by(observations.c.revision).limit(10001)).mappings().all()
        if len(rows) > 10000:
            raise ReviewError('BILLING_HISTORY_LIMIT', 'Billing history requires maintenance; nothing was discarded.', 503)
        previous, latest, history = None, {}, []
        for revision, row in enumerate(rows, 1):
            value = json.loads(row['payload'])
            if (row['revision'] != revision or value['revision'] != revision or value['account_id'] != account_id
                    or value['previous'] != previous or digest(value) != row['sha256']
                    or value['request_id'] != row['request_id'] or value['fingerprint'] != row['fingerprint']):
                raise ReviewError('BILLING_HISTORY_INVALID', 'Billing history integrity check failed.', 503)
            recorded = timestamp(value['recorded_at'])
            if not recorded:
                raise ReviewError('BILLING_HISTORY_INVALID', 'Invalid billing history timestamp.', 503)
            clean = validate_observation(value['data'], recorded)
            if clean != value['data']:
                raise ReviewError('BILLING_HISTORY_INVALID', 'Invalid billing history payload.', 503)
            latest[clean['provider']] = {**clean, 'scope': value['scope'], 'recorded_at': value['recorded_at']}
            history.append(value)
            previous = row['sha256']
        return {'revision': len(rows), 'latest': latest, 'events': history, 'head_sha256': previous}

    def read(self, account_id):
        with self.engine.connect() as connection:
            return self._read(connection, account_id)

    def save(self, account_id, data, *, expected_revision, request_id, scope):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ReviewError('REVISION_REQUIRED', 'Refresh the funding panel before saving.', 409)
        if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9-]{36}', request_id):
            raise ReviewError('REQUEST_ID_REQUIRED', 'Use the funding form to record a balance.')
        try:
            clean = validate_observation(data, self.clock())
        except (ValueError, TypeError) as exc:
            raise ReviewError('INVALID_BILLING_OBSERVATION', str(exc)) from None
        selected_scope = scope if clean['provider'] == 'openai_api' else None
        if clean['provider'] == 'openai_api' and (not isinstance(selected_scope, str) or not re.fullmatch(r'[0-9a-f]{64}', selected_scope)):
            raise ReviewError('API_CONFIGURATION_UNKNOWN', 'The configured API account scope is unavailable.', 409)
        fingerprint = digest({'data': clean, 'scope': selected_scope})
        with self.engine.begin() as connection:
            owner = connection.execute(select(accounts.c.account_id).where(accounts.c.account_id == account_id,
                accounts.c.enabled.is_(True)).with_for_update()).first()
            if not owner:
                raise ReviewError('SIGN_IN_REQUIRED', 'Sign in again before saving a balance.', 401)
            state = self._read(connection, account_id)
            existing = next((e for e in state['events'] if e['request_id'] == request_id), None)
            if existing:
                if existing['fingerprint'] != fingerprint:
                    raise ReviewError('REQUEST_CHANGED', 'This request ID already recorded a different observation.', 409)
                return state
            if expected_revision != state['revision']:
                raise ReviewError('BILLING_CHANGED', 'A newer funding observation exists. Refresh before saving.', 409)
            if state['revision'] >= 10000:
                raise ReviewError('BILLING_HISTORY_LIMIT', 'Billing history requires maintenance; nothing was discarded.', 503)
            value = {'version': 1, 'account_id': account_id, 'revision': state['revision'] + 1,
                     'request_id': request_id, 'fingerprint': fingerprint, 'data': clean,
                     'scope': selected_scope, 'recorded_at': utc(self.clock()), 'previous': state['head_sha256']}
            connection.execute(insert(observations).values(account_id=account_id, revision=value['revision'],
                request_id=request_id, fingerprint=fingerprint, payload=canonical(value), sha256=digest(value)))
            return self._read(connection, account_id)
