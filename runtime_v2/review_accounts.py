"""Durable personal review state, separate from producer snapshots.

Every review mutation locks its account row, commits state and an audit event
together, and retains Restore tombstones so old browser imports cannot undo them.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey, Integer,
                        MetaData, String, Table, Text, UniqueConstraint, insert,
                        select, update)
from werkzeug.security import check_password_hash, generate_password_hash

from .database import sqlalchemy_engine

metadata = MetaData()
accounts = Table("runtime_review_accounts", metadata,
    Column("account_id", String(36), primary_key=True),
    Column("username", String(64), unique=True, nullable=False),
    Column("password_hash", Text),
    Column("invitation_hash", String(64), unique=True),
    Column("invitation_expires", DateTime(timezone=True)),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("revision", BigInteger, nullable=False, default=0),
    Column("created_at", DateTime(timezone=True), nullable=False))
sessions = Table("runtime_review_sessions", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("account_id", ForeignKey(accounts.c.account_id), nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)))
acknowledgements = Table("runtime_review_acknowledgements", metadata,
    Column("account_id", ForeignKey(accounts.c.account_id), primary_key=True),
    Column("logical_review_id", String(500), primary_key=True),
    Column("review_id", String(500), nullable=False),
    Column("acknowledged", Boolean, nullable=False),
    Column("acknowledged_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("revision", BigInteger, nullable=False))
events = Table("runtime_review_events", metadata,
    Column("account_id", ForeignKey(accounts.c.account_id), primary_key=True),
    Column("revision", BigInteger, primary_key=True),
    Column("request_id", String(36), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("logical_review_id", String(500), nullable=False),
    Column("review_id", String(500), nullable=False),
    Column("operation", String(16), nullable=False),
    Column("source", String(32), nullable=False),
    Column("effective_at", DateTime(timezone=True), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("account_id", "request_id"))
auth_limits = Table("runtime_review_auth_limits", metadata,
    Column("bucket", String(64), primary_key=True),
    Column("window_start", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False))

SESSION_SECONDS = 30 * 24 * 3600
USERNAME = re.compile(r"[a-z0-9][a-z0-9_.-]{2,63}\Z")
LOGICAL_ID = re.compile(r"review-logical-v1:[0-9a-f]{32}\Z")
_DUMMY_PASSWORD_HASH = generate_password_hash("Not an account credential: timing equalizer", method="scrypt:32768:8:1")


class ReviewError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def utc_now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value):
    if not value:
        return None
    rendered = utc(value).isoformat().replace("+00:00", "Z")
    return re.sub(r"(\.\d*?[1-9])0+Z$", r"\1Z", rendered).replace(".000000Z", "Z")


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def username(value):
    result = value.strip().casefold() if isinstance(value, str) else ""
    if not USERNAME.fullmatch(result):
        raise ReviewError("INVALID_USERNAME", "Use 3–64 letters, numbers, dots, underscores or hyphens for the username.")
    return result


def validate_password(value):
    if not isinstance(value, str) or not 14 <= len(value) <= 256:
        raise ReviewError("INVALID_PASSWORD", "Use a password or passphrase with 14–256 characters.")
    return value


class PersonalReviewStore:
    def __init__(self, engine=None, *, clock=utc_now):
        self._engine, self.clock = engine, clock

    @property
    def engine(self):
        if self._engine is None:
            self._engine = sqlalchemy_engine()
        return self._engine

    def initialize_schema(self):
        # Only these new account/review tables. Never initialize producer state.
        metadata.create_all(self.engine)

    def invite(self, name, invitation_hash):
        name = username(name)
        if not re.fullmatch(r"[0-9a-f]{64}", invitation_hash or ""):
            raise ReviewError("INVALID_INVITATION", "Provide the SHA-256 hash of a random activation token.")
        with self.engine.begin() as conn:
            existing = conn.execute(select(accounts).where(accounts.c.username == name)).mappings().first()
            if existing:
                if existing["invitation_hash"] == invitation_hash and existing["password_hash"] is None:
                    return {"account_id": existing["account_id"], "username": name}
                raise ReviewError("ACCOUNT_EXISTS", "This account already exists; it was not replaced.", 409)
            account_id = str(uuid.uuid4())
            conn.execute(insert(accounts).values(account_id=account_id, username=name,
                invitation_hash=invitation_hash, invitation_expires=self.clock() + timedelta(days=7),
                enabled=True, revision=0, created_at=self.clock()))
        return {"account_id": account_id, "username": name}

    def _new_session(self, conn, account_id):
        token = secrets.token_urlsafe(32)
        conn.execute(insert(sessions).values(token_hash=digest(token), account_id=account_id,
            expires_at=self.clock() + timedelta(seconds=SESSION_SECONDS)))
        return token

    def reset_invitation(self, name, account_id, invitation_hash):
        """IAM-protected administrator recovery preserves the stable account ID."""
        name = username(name)
        if not re.fullmatch(r"[0-9a-f]{64}", invitation_hash or ""):
            raise ReviewError("INVALID_INVITATION", "Provide an activation token hash.")
        with self.engine.begin() as conn:
            row = conn.execute(select(accounts).where(accounts.c.username == name,
                accounts.c.account_id == account_id, accounts.c.enabled.is_(True)).with_for_update()).mappings().first()
            if not row:
                raise ReviewError("ACCOUNT_UNAVAILABLE", "The account identity does not match an enabled account.", 404)
            conn.execute(update(accounts).where(accounts.c.account_id == account_id).values(
                invitation_hash=invitation_hash, invitation_expires=self.clock() + timedelta(days=7)))
        return {"account_id": account_id, "username": name, "history_preserved": True}

    def _limit(self, bucket, limit=12, seconds=900):
        # The atomic upsert works across web instances; no browser/IP identifier
        # is used as account identity. Buckets contain only one-way hashes.
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        now = self.clock()
        with self.engine.begin() as conn:
            upsert = pg_insert if conn.dialect.name == "postgresql" else sqlite_insert
            conn.execute(upsert(auth_limits).values(bucket=digest(bucket), window_start=now, attempts=0)
                         .on_conflict_do_nothing(index_elements=[auth_limits.c.bucket]))
            row = conn.execute(select(auth_limits).where(auth_limits.c.bucket == digest(bucket))
                               .with_for_update()).mappings().one()
            expired = utc(row["window_start"]) <= now - timedelta(seconds=seconds)
            attempts = 1 if expired else row["attempts"] + 1
            conn.execute(update(auth_limits).where(auth_limits.c.bucket == digest(bucket))
                         .values(attempts=min(attempts, limit + 1), window_start=now if expired else row["window_start"]))
        if attempts > limit:
            raise ReviewError("SIGN_IN_LIMIT", "Too many sign-in attempts. Try again in 15 minutes.", 429)

    def activate(self, invitation, password, *, remote=""):
        if not isinstance(invitation, str) or not 32 <= len(invitation) <= 128:
            raise ReviewError("INVALID_INVITATION", "This activation link is invalid or expired.", 401)
        self._limit("activate:" + remote, limit=30)
        password_hash = generate_password_hash(validate_password(password), method="scrypt:32768:8:1")
        with self.engine.begin() as conn:
            account = conn.execute(select(accounts).where(accounts.c.invitation_hash == digest(invitation))
                                   .with_for_update()).mappings().first()
            if not account or not account["enabled"] or utc(account["invitation_expires"]) <= self.clock():
                raise ReviewError("INVALID_INVITATION", "This activation link is invalid or expired.", 401)
            conn.execute(update(accounts).where(accounts.c.account_id == account["account_id"])
                         .values(password_hash=password_hash, invitation_hash=None, invitation_expires=None))
            conn.execute(update(sessions).where(sessions.c.account_id == account["account_id"], sessions.c.revoked_at.is_(None))
                         .values(revoked_at=self.clock()))
            return self._new_session(conn, account["account_id"])

    def login(self, name, password, *, remote=""):
        normalized = name.strip().casefold() if isinstance(name, str) else ""
        self._limit("login-ip:" + remote, limit=60)
        self._limit("login-name:" + normalized)
        if not isinstance(password, str) or len(password) > 256 or not USERNAME.fullmatch(normalized):
            raise ReviewError("SIGN_IN_FAILED", "The username or password was not recognized.", 401)
        with self.engine.begin() as conn:
            row = conn.execute(select(accounts).where(accounts.c.username == normalized)
                               .with_for_update()).mappings().first()
            valid_password = check_password_hash(row["password_hash"] if row and row["password_hash"] else _DUMMY_PASSWORD_HASH, password)
            if not row or not row["enabled"] or not row["password_hash"] or not valid_password:
                raise ReviewError("SIGN_IN_FAILED", "The username or password was not recognized.", 401)
            return self._new_session(conn, row["account_id"])

    def account_for_session(self, token):
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(select(accounts.c.account_id, accounts.c.username).join(sessions)
                .where(sessions.c.token_hash == digest(token), sessions.c.revoked_at.is_(None),
                       sessions.c.expires_at > self.clock(), accounts.c.enabled.is_(True))).mappings().first()
            return dict(row) if row else None

    def logout(self, token):
        if token:
            with self.engine.begin() as conn:
                conn.execute(update(sessions).where(sessions.c.token_hash == digest(token), sessions.c.revoked_at.is_(None))
                             .values(revoked_at=self.clock()))

    def disable(self, name):
        with self.engine.begin() as conn:
            row = conn.execute(select(accounts).where(accounts.c.username == username(name)).with_for_update()).mappings().one()
            conn.execute(update(accounts).where(accounts.c.account_id == row["account_id"]).values(enabled=False))
            conn.execute(update(sessions).where(sessions.c.account_id == row["account_id"], sessions.c.revoked_at.is_(None)).values(revoked_at=self.clock()))

    def _state(self, conn, account):
        rows = conn.execute(select(acknowledgements).where(
            acknowledgements.c.account_id == account["account_id"], acknowledgements.c.acknowledged.is_(True))
            .order_by(acknowledgements.c.logical_review_id)).mappings()
        return {"version": 1, "account": {"id": account["account_id"], "username": account["username"]},
            "revision": account["revision"], "acknowledged": [{"id": r["review_id"],
                "logical_review_id": r["logical_review_id"], "acknowledged_at_utc": iso(r["acknowledged_at"])} for r in rows]}

    def read(self, account_id):
        with self.engine.begin() as conn:
            # Lock pairs the account revision with its rows, even during a write.
            account = conn.execute(select(accounts).where(accounts.c.account_id == account_id,
                accounts.c.enabled.is_(True)).with_for_update()).mappings().first()
            if not account:
                raise ReviewError("SIGN_IN_REQUIRED", "Sign in to load your saved reviews.", 401)
            return self._state(conn, account)

    def _change(self, conn, account, review_id, logical_id, acknowledged, request_id, source, effective_at, fingerprint):
        revision = account["revision"] + 1
        existing = conn.execute(select(acknowledgements).where(acknowledgements.c.account_id == account["account_id"],
            acknowledgements.c.logical_review_id == logical_id)).mappings().first()
        stamp = existing["acknowledged_at"] if existing and existing["acknowledged"] and acknowledged else effective_at if acknowledged else None
        values = dict(review_id=review_id, acknowledged=acknowledged, acknowledged_at=stamp,
                      updated_at=self.clock(), revision=revision)
        if existing:
            conn.execute(update(acknowledgements).where(acknowledgements.c.account_id == account["account_id"],
                acknowledgements.c.logical_review_id == logical_id).values(**values))
        else:
            conn.execute(insert(acknowledgements).values(account_id=account["account_id"], logical_review_id=logical_id, **values))
        conn.execute(insert(events).values(account_id=account["account_id"], revision=revision,
            request_id=request_id, fingerprint=fingerprint, logical_review_id=logical_id, review_id=review_id,
            operation="acknowledge" if acknowledged else "restore", source=source,
            effective_at=effective_at, recorded_at=self.clock()))
        conn.execute(update(accounts).where(accounts.c.account_id == account["account_id"]).values(revision=revision))
        return {**account, "revision": revision}

    def set_acknowledged(self, account_id, review_id, logical_id, acknowledged, expected_revision, request_id):
        if (not isinstance(review_id, str) or not 1 <= len(review_id) <= 500
            or not isinstance(logical_id, str) or not LOGICAL_ID.fullmatch(logical_id)
            or type(acknowledged) is not bool or type(expected_revision) is not int or expected_revision < 0):
            raise ReviewError("INVALID_REVIEW", "The review request is invalid. Refresh and try again.")
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise ReviewError("INVALID_REQUEST_ID", "The save request needs a unique identifier.") from None
        fingerprint = digest(json.dumps([review_id, logical_id, acknowledged], separators=(",", ":")))
        with self.engine.begin() as conn:
            account = conn.execute(select(accounts).where(accounts.c.account_id == account_id, accounts.c.enabled.is_(True))
                                   .with_for_update()).mappings().first()
            if not account:
                raise ReviewError("SIGN_IN_REQUIRED", "Sign in to save your reviews.", 401)
            prior = conn.execute(select(events.c.fingerprint).where(events.c.account_id == account_id,
                                 events.c.request_id == request_id)).scalar_one_or_none()
            if prior:
                if prior != fingerprint:
                    raise ReviewError("REQUEST_CONFLICT", "This save identifier was already used for a different action.", 409)
                return self._state(conn, account)
            if account["revision"] != expected_revision:
                raise ReviewError("REVIEW_CHANGED", "Your saved reviews changed in another session. Refresh and try again.", 409)
            account = self._change(conn, account, review_id, logical_id, acknowledged, request_id,
                                   "user", self.clock(), fingerprint)
            return self._state(conn, account)

    def import_legacy(self, account_id, records, identities, *, source="browser_migration"):
        if not isinstance(records, list) or len(records) > 500:
            raise ReviewError("INVALID_IMPORT", "Import at most 500 saved acknowledgements at a time.")
        validated = []
        for record in records:
            if not isinstance(record, dict):
                raise ReviewError("INVALID_IMPORT", "The saved acknowledgement data is invalid.")
            review_id = record.get("id")
            logical_id = identities.get(review_id) if isinstance(review_id, str) else None
            # Unknown legacy IDs remain in the browser backup for later import;
            # never guess identity from client-supplied display text.
            if logical_id is None:
                continue
            if not LOGICAL_ID.fullmatch(logical_id) or record.get("logical_review_id") not in (None, "", logical_id):
                raise ReviewError("IMPORT_IDENTITY_MISMATCH", "A saved acknowledgement does not match the retained review.", 409)
            try:
                stamp = datetime.fromisoformat(record["acknowledged_at_utc"].replace("Z", "+00:00"))
                if stamp.tzinfo is None or not datetime(2000, 1, 1, tzinfo=timezone.utc) <= stamp <= self.clock() + timedelta(minutes=5):
                    raise ValueError
            except (KeyError, ValueError, TypeError, AttributeError):
                raise ReviewError("INVALID_IMPORT_TIME", "A saved acknowledgement has an invalid timestamp.") from None
            validated.append((review_id, logical_id, stamp))
        with self.engine.begin() as conn:
            account = conn.execute(select(accounts).where(accounts.c.account_id == account_id, accounts.c.enabled.is_(True))
                                   .with_for_update()).mappings().first()
            if not account:
                raise ReviewError("ACCOUNT_UNAVAILABLE", "This review account is unavailable.", 404)
            imported = 0
            for review_id, logical_id, stamp in validated:
                exists = conn.execute(select(acknowledgements.c.logical_review_id).where(
                    acknowledgements.c.account_id == account_id, acknowledgements.c.logical_review_id == logical_id)).first()
                if exists:
                    continue  # Includes Restore tombstones and prior successful imports.
                request_id = str(uuid.uuid5(uuid.UUID(account_id), "legacy:" + logical_id))
                fingerprint = digest(json.dumps([review_id, logical_id, iso(stamp)], separators=(",", ":")))
                account = self._change(conn, account, review_id, logical_id, True, request_id, source, stamp, fingerprint)
                imported += 1
            return {**self._state(conn, account), "imported": imported, "unmatched": len(records) - len(validated)}
