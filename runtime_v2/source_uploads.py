"""Private, expiring source-upload inbox. It is not a second state writer.

Only the existing source producer may acknowledge processing after committing its
canonical snapshot. Raw bytes never enter protected snapshots or publications.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (Column, DateTime, Integer, LargeBinary, MetaData, String,
                        Table, Text, UniqueConstraint, func, insert, select, update)

from .database import sqlalchemy_engine
from .review_accounts import ReviewError, iso
from scripts.source_ocr import inspect_document

metadata = MetaData()
uploads = Table("runtime_source_uploads", metadata,
    Column("upload_id", String(36), primary_key=True),
    Column("account_id", String(36), nullable=False, index=True),
    Column("branch", String(16), nullable=False, index=True),
    Column("filing_key", String(500), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("format", String(16), nullable=False),
    Column("page_count", Integer, nullable=False),
    Column("payload", LargeBinary),
    Column("status", String(32), nullable=False),
    Column("result", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("snapshot_sha256", String(64)),
    UniqueConstraint("account_id", "filing_key", "sha256"))


class SourceUploadStore:
    def __init__(self, engine=None, clock=None):
        self._engine = engine
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def engine(self):
        if self._engine is None:
            self._engine = sqlalchemy_engine()
        return self._engine

    def initialize_schema(self):
        # Explicit additive migration, never initialize or touch canonical state.
        metadata.create_all(self.engine)

    def _fence(self, connection):
        # One narrowly scoped intake/expiry fence bounds concurrent total uploads.
        # PostgreSQL advisory lock is transaction-scoped; SQLite test transactions
        # use their single-writer serialization instead.
        if connection.dialect.name == "postgresql":
            from sqlalchemy import text
            connection.execute(text("SELECT pg_advisory_xact_lock(1349678672, 182)"))

    def _expire(self, connection):
        connection.execute(update(uploads).where(uploads.c.expires_at <= self.clock(), uploads.c.payload.is_not(None))
                           .values(payload=None, status="expired"))

    def submit(self, account_id, filing, data):
        from scripts.source_ocr import MAX_BYTES, OCRError
        if not data or len(data) > MAX_BYTES:
            raise OCRError("document_byte_limit")
        digest = hashlib.sha256(data).hexdigest()
        created = self.clock()
        with self.engine.begin() as connection:
            self._fence(connection)
            self._expire(connection)
            existing = connection.execute(select(uploads).where(
                uploads.c.account_id == account_id, uploads.c.filing_key == filing["filing_key"],
                uploads.c.sha256 == digest)).mappings().first()
            if existing and existing["status"] != "expired":
                return {"upload_id": existing["upload_id"], "sha256": digest, "status": existing["status"], "duplicate": True}
            pending = connection.execute(select(func.count()).select_from(uploads).where(uploads.c.payload.is_not(None))).scalar_one()
            recent = connection.execute(select(func.count()).select_from(uploads).where(
                uploads.c.account_id == account_id, uploads.c.submitted_at > created - timedelta(hours=1))).scalar_one()
            if pending >= 20 or recent >= 10:
                raise ReviewError("UPLOAD_LIMIT", "The source upload queue is full or its hourly limit has been reached. Try again later.", 429)
            from scripts.source_ocr_limits import inspect_bounded
            # The API authenticates and allowlists the owner before this inbox.
            # Manual source files are not subject to the automatic page cap.
            info = inspect_bounded(data, max_pages=None)
            if existing:
                connection.execute(update(uploads).where(uploads.c.upload_id == existing["upload_id"])
                                   .values(payload=data, status="pending", submitted_at=created, expires_at=created + timedelta(days=7)))
                return {"upload_id": existing["upload_id"], "sha256": digest, "status": "pending", "duplicate": True}
            upload_id = str(uuid.uuid4())
            connection.execute(insert(uploads).values(upload_id=upload_id, account_id=account_id,
                branch=filing["branch"], filing_key=filing["filing_key"], source_url=filing["source_url"],
                sha256=digest, format=info["format"], page_count=info["pages"], payload=data,
                status="pending", created_at=created, submitted_at=created, expires_at=created + timedelta(days=7)))
        return {"upload_id": upload_id, "sha256": digest, "status": "pending", "duplicate": False}

    def pending(self, branch, limit=5):
        # Source namespace lock, held by JobRunner, is the only consumer lease.
        # Do not drop bytes or mark done until snapshot receipt exists.
        with self.engine.begin() as connection:
            self._fence(connection)
            self._expire(connection)
            return [dict(row) for row in connection.execute(select(uploads).where(
                uploads.c.branch == branch, uploads.c.status.in_(["pending", "approved", "retry_delayed", "access_required"])).order_by(uploads.c.created_at, uploads.c.upload_id).limit(limit)).mappings()]

    def acknowledge(self, outcomes, snapshot_sha256):
        if len(snapshot_sha256) != 64:
            raise ValueError("invalid snapshot receipt")
        with self.engine.begin() as connection:
            for item in outcomes:
                connection.execute(update(uploads).where(uploads.c.upload_id == item["upload_id"],
                    uploads.c.sha256 == item["sha256"], uploads.c.status.in_(["pending", "approved", "retry_delayed", "access_required"])).values(
                    **({"payload": None} if item.get("has_evidence", item["status"] in {"complete", "needs_review"}) else {}),
                    status=item["status"], result=json.dumps(item.get("preview", {})), snapshot_sha256=snapshot_sha256))

    def read(self, account_id):
        with self.engine.begin() as connection:
            self._fence(connection)
            self._expire(connection)
            rows = connection.execute(select(uploads.c.upload_id, uploads.c.filing_key, uploads.c.sha256,
                uploads.c.status, uploads.c.page_count, uploads.c.created_at, uploads.c.expires_at,
                uploads.c.snapshot_sha256, uploads.c.result).where(uploads.c.account_id == account_id)
                .order_by(uploads.c.created_at.desc()).limit(50)).mappings()
            return [{**dict(row), "created_at": iso(row["created_at"]), "expires_at": iso(row["expires_at"]),
                     "result": json.loads(row["result"] or "{}")} for row in rows]

    def confirm(self, account_id, upload_id, digest, corrections):
        """Approve corrections to a complete extracted table, never arbitrary rows."""
        from scripts.source_ocr import AMOUNTS
        if not isinstance(corrections, list) or not 0 < len(corrections) <= 500:
            raise ReviewError("INVALID_ROWS", "Review the extracted transaction rows before confirming.")
        with self.engine.begin() as connection:
            self._fence(connection)
            row = connection.execute(select(uploads).where(uploads.c.upload_id == upload_id,
                uploads.c.account_id == account_id)).mappings().first()
            if not row or row["sha256"] != digest or row["status"] != "needs_review":
                raise ReviewError("EVIDENCE_CHANGED", "Reload the latest extraction before confirming.", 409)
            preview = json.loads(row["result"] or "{}")
            original = preview.get("rows", [])
            if preview.get("problems") or not preview.get("filer_matches") or len(corrections) != len(original):
                raise ReviewError("INCOMPLETE_EXTRACTION", "Missing rows/pages or a filer mismatch requires another source file.", 409)
            accepted = []
            for before, after in zip(original, corrections):
                if not isinstance(after, dict) or (after.get("page"), after.get("row")) != (before["page"], before["row"]):
                    raise ReviewError("ROW_IDENTITY_CHANGED", "Keep every extracted row in its original order.")
                asset = str(after.get("asset", "")).strip()
                if not 3 <= len(asset) <= 500 or any(ord(char) < 32 for char in asset):
                    raise ReviewError("INVALID_ASSET", "Each row needs a readable asset name.")
                kind, amount = after.get("transaction_type"), after.get("amount")
                owner = after.get("owner", "")
                if kind not in {"Purchase", "Sale", "Sale (Partial)", "Exchange"} or amount not in AMOUNTS or owner not in {"", "Self", "Spouse", "Joint", "Dependent Child"}:
                    raise ReviewError("INVALID_ROW_VALUE", "Select a disclosed transaction type, amount range and ownership.")
                if amount == AMOUNTS[-1] and owner not in {"Spouse", "Dependent Child"}:
                    raise ReviewError("SPECIAL_AMOUNT_OWNER", "Column K requires the disclosed spouse/dependent-child ownership; do not infer it.")
                dates = []
                for field in ("transaction_date", "notification_date"):
                    value = after.get(field, "")
                    try:
                        parsed = datetime.strptime(value, "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        raise ReviewError("INVALID_DATE", "Use valid transaction and notification dates.") from None
                    if parsed > self.clock().date():
                        raise ReviewError("FUTURE_DATE", "A disclosure transaction cannot be in the future.")
                    dates.append(parsed.isoformat())
                if dates[0] > dates[1]:
                    raise ReviewError("DATE_ORDER", "Notification cannot precede the disclosed transaction.")
                accepted.append({**before, "asset": asset, "transaction_type": kind, "amount": amount,
                    "owner": owner, "transaction_date": dates[0], "notification_date": dates[1], "issues": [],
                    "confirmation": "owner_reviewed"})
            connection.execute(update(uploads).where(uploads.c.upload_id == upload_id).values(
                status="approved", result=json.dumps({**preview, "approved_rows": accepted, "confirmed_at": self.clock().isoformat()})))
        return {"upload_id": upload_id, "status": "approved"}
