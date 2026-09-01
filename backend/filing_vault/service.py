"""Filing identity, immutable provenance, absolute TTL and lifecycle operations.

All retrieval starts with a registered ID. Catalog import is a trusted server
operation, deliberately absent from the HTTP API. This module never imports or
updates the Legislative, Executive, AI or simulation state stores.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import re
import threading
import time
import uuid

from sqlalchemy import and_, delete, func, insert, select, text, update
from sqlalchemy.exc import SQLAlchemyError

from . import schema
from .providers import ProviderError, normalize_filing
from .storage import StorageError, object_key

CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
LOG = logging.getLogger("polititrack.filing_vault")
RECORD_FIELDS = (
    "filing_id", "external_filing_id", "filer_id", "filer_name", "source",
    "filing_type", "filing_date", "report_period", "official_source_url",
    "document_url", "is_amended", "supersedes_filing_id", "superseded_by_filing_id",
    "access_class", "access_method", "requires_request", "source_metadata", "status",
)
PUBLIC_SOURCE_METADATA = frozenset({
    "access_mode", "access_method", "document_id", "report_id", "report_year", "filing_year",
    "report_type", "agency", "branch", "checked_at", "source_checked_at", "validation_scope",
    "metadata_validation_scope", "resolved_document_url", "etag", "last_modified", "source_http_status",
    "validated_document_sha256", "content_length", "document_version", "source_version",
})


def public_source_metadata(value):
    # Exact source provenance is preserved in the private database. Public API
    # responses must not accidentally expose internal paths, cookies or tokens
    # supplied by a future ingestion adapter.
    return {key: item for key, item in (value or {}).items()
            if key in PUBLIC_SOURCE_METADATA and isinstance(item, (str, int, float, bool, type(None)))}


def public_source_snapshot(value):
    projected = {key: value.get(key) for key in RECORD_FIELDS}
    projected["source_metadata"] = public_source_metadata(value.get("source_metadata"))
    projected["content_changed"] = value.get("content_changed")
    return projected


def is_synthetic(record):
    flags = (record.get("is_synthetic_test"), record.get("is_temporary"), record.get("is_simulation"))
    if any(value is True or str(value).lower() in {"true", "1", "yes"} for value in flags):
        return True
    if record.get("test_metadata"):
        return True
    return any(re.search(r"TEST[:_-]", str(record.get(key) or ""), re.I)
               for key in ("filing_key", "filing_id", "external_filing_id", "report_id"))


def _check_identity(previous, incoming):
    for key in ("filing_id", "source", "external_filing_id", "filer_id"):
        if previous.get(key) and incoming.get(key) and str(previous[key]) != str(incoming[key]):
            raise VaultError("IDENTITY_MISMATCH", "An existing filing cannot be reassigned to a different source report or filer.", status=409)


def utc_iso(value):
    if value is None:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


class VaultError(Exception):
    def __init__(self, code, message, *, status=503, filing=None):
        super().__init__(message)
        self.code, self.message, self.status, self.filing = code, message, status, filing


@dataclass(frozen=True)
class DocumentResult:
    body: bytes
    content_type: str
    filing: dict
    cache_hit: bool
    warning: str | None = None


class VaultService:
    def __init__(self, engine, store, providers, *, clock=time.time):
        self.engine, self.store, self.providers, self.clock = engine, store, providers, clock
        self._lock = threading.RLock()

    def init_schema(self):
        """Explicit additive migration; never silently recreates tracker state."""
        with self.engine.begin() as connection:
            schema.metadata.create_all(connection)
            schema.secure_postgresql_tables(connection)

    @contextmanager
    def _transaction(self, *, exclusive=False):
        # Postgres workers use shared lifecycle locks and per-filing row locks;
        # cleanup takes the exclusive lock so it cannot delete an in-flight
        # upload before its metadata commits. SQLite is explicit dev/test only.
        with self._lock, self.engine.connect() as conn:
            transaction = conn.begin()
            try:
                if self.engine.dialect.name == "sqlite":
                    conn.exec_driver_sql("BEGIN IMMEDIATE")
                elif self.engine.dialect.name == "postgresql":
                    conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                    lock = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
                    conn.execute(text(f"SELECT {lock}(1349678672, 30)"))
                yield conn
                transaction.commit()
            except BaseException:
                transaction.rollback()
                raise

    def _row(self, conn, filing_id, *, lock=False):
        query = select(schema.filings).where(schema.filings.c.filing_id == filing_id)
        if lock:
            query = query.with_for_update()
        row = conn.execute(query).mappings().first()
        if row is None:
            raise VaultError("FILING_NOT_FOUND", "This filing is not registered in the Filing Vault.", status=404)
        return dict(row)

    def _document(self, conn, row):
        if not row["current_document_id"]:
            return None
        found = conn.execute(select(schema.documents).where(
            schema.documents.c.document_id == row["current_document_id"])).mappings().first()
        return dict(found) if found else None

    @staticmethod
    def _status(record):
        if record.get("superseded_by_filing_id"):
            return "Superseded"
        status = str(record.get("status") or "").lower()
        if status in {"withdrawn", "invalid", "archived", "superseded"}:
            return status.title()
        return "Amended" if record.get("is_amended") else "Current"

    def _serialize(self, conn, row, *, include_versions=True):
        record = row["record"]
        public = {key: record.get(key) for key in RECORD_FIELDS}
        public["source_metadata"] = public_source_metadata(record.get("source_metadata"))
        public.update({"filing_id": row["filing_id"], "source": row["source"],
                       "status": self._status(record),
                       "cache_status": row["cache_status"],
                       "retrieval_status": row["retrieval_status"],
                       "retrieval_error": row["retrieval_error"],
                       "last_validated_at": utc_iso(row["last_validated_at"]),
                       "retrieved_at": None, "expires_at": None,
                       "content_type": None, "file_size": None, "sha256": None,
                       "document_version": None})
        current = self._document(conn, row)
        if current:
            for key in ("document_url", "official_source_url", "content_type", "file_size", "sha256"):
                public[key] = current[key]
            public["source_metadata"] = public_source_metadata(current["source_metadata"])
            public["retrieved_at"] = utc_iso(current["retrieved_at"])
            public["expires_at"] = utc_iso(current["expires_at"])
            if current["expires_at"] <= self.clock():
                public["cache_status"] = "EXPIRED"
            elif public["status"] in {"Superseded", "Withdrawn", "Invalid", "Archived"}:
                public["cache_status"] = "INVALID"
            public["document_version"] = conn.execute(select(schema.versions.c.document_version).where(
                schema.versions.c.document_id == current["document_id"])).scalar_one_or_none()
        if include_versions:
            history = conn.execute(select(schema.versions, schema.documents).join(
                schema.documents, schema.documents.c.document_id == schema.versions.c.document_id
            ).where(schema.versions.c.filing_id == row["filing_id"]).order_by(
                schema.versions.c.document_version.desc())).mappings()
            public["versions"] = [{
                "document_version": item["document_version"], "sha256": item["sha256"],
                "retrieved_at": utc_iso(item["retrieved_at"]), "expires_at": utc_iso(item["expires_at"]),
                "file_size": item["file_size"], "content_type": item["content_type"],
                "official_source_url": item["official_source_url"], "document_url": item["document_url"],
                "source_metadata": public_source_metadata(item["source_metadata"]),
                "source_snapshot": public_source_snapshot(item["source_snapshot"]),
                "cache_status": "EXPIRED" if item["expires_at"] <= self.clock() else item["cache_status"],
                "is_current": item["document_id"] == row["current_document_id"] and public["status"] in {"Current", "Amended"},
            } for item in history]
        return public

    def _normalize_record(self, record):
        if not isinstance(record, dict):
            raise VaultError("INVALID_FILING", "A filing catalog row must be an object.", status=400)
        if is_synthetic(record):
            raise VaultError("SIMULATION_NOT_PERMITTED", "TEST and simulation records cannot enter the persistent Filing Vault.", status=403)
        normalized = normalize_filing(record)
        filing_id = normalized.get("filing_id")
        if not isinstance(filing_id, str) or not filing_id or len(filing_id) > 512 or any(ord(c) < 32 for c in filing_id):
            raise VaultError("INVALID_FILING_ID", "The catalog filing ID is invalid.", status=400)
        provider = self.providers.get(normalized["source"])
        resolved = provider.resolve_filing(normalized)
        if resolved.get("filing_id") != filing_id or resolved.get("source") != normalized["source"]:
            raise VaultError("IDENTITY_MISMATCH", "Provider resolution changed the filing identity.", status=409)
        return {key: resolved.get(key) for key in RECORD_FIELDS}

    def register_filing(self, record):
        """Trusted single-record ingestion; never accepts an API-supplied URL.

        Existing exact IDs are preserved. Upserts change catalog metadata only;
        retrieval provenance and timestamps are never reconstructed from imports.
        Whole generated catalogs should use monotonic, atomic import_catalog.
        """
        normalized = self._normalize_record(record)
        now = self.clock()
        with self._transaction(exclusive=True) as conn:
            self._register_record(conn, normalized, now)
            return self._serialize(conn, self._row(conn, normalized["filing_id"]))

    def _register_record(self, conn, normalized, now):
        filing_id = normalized["filing_id"]
        existing = conn.execute(select(schema.filings).where(
            schema.filings.c.filing_id == filing_id).with_for_update()).mappings().first()
        if existing and existing["source"] != normalized["source"]:
            raise VaultError("IDENTITY_MISMATCH", "A filing ID cannot move between sources.", status=409)
        if existing:
            # A stale source projection must not undo known supersession,
            # withdrawal or amendment, including when its fields are missing.
            old = existing["record"]
            _check_identity(old, normalized)
            for key in ("external_filing_id", "filer_id"):
                normalized[key] = normalized.get(key) or old.get(key)
            for key in ("supersedes_filing_id", "superseded_by_filing_id"):
                normalized[key] = normalized.get(key) or old.get(key)
            normalized["is_amended"] = bool(normalized.get("is_amended") or old.get("is_amended"))
            normalized["source_metadata"] = {**(old.get("source_metadata") or {}), **(normalized.get("source_metadata") or {})}
            if self._status(old) in {"Withdrawn", "Invalid", "Archived", "Superseded"}:
                normalized["status"] = old.get("status")
            changed = any(normalized.get(key) != old.get(key) for key in (
                "document_url", "is_amended", "access_class", "requires_request",
                "superseded_by_filing_id", "status"))
            values = {"record": normalized, "updated_at": now}
            if changed:
                values["last_validated_at"] = None
                if existing["current_document_id"]:
                    values["cache_status"] = "INVALID"
            conn.execute(update(schema.filings).where(schema.filings.c.filing_id == filing_id).values(**values))
        else:
            conn.execute(insert(schema.filings).values(
                filing_id=filing_id, source=normalized["source"], record=normalized,
                cache_status="MISSING", retrieval_status="NOT_RETRIEVED", updated_at=now))
        self._relationships(conn, normalized, now)

    def import_catalog(self, catalog):
        """Validate then atomically import an operator-supplied trusted snapshot.

        The checkpoint prevents older exports, or different exports carrying the
        same timestamp, from regressing approved source metadata. It does not
        establish production artifact provenance; the operator must supply the
        existing publisher's trusted export, never an arbitrary downloaded JSON.
        """
        if (not isinstance(catalog, dict) or catalog.get("repository_id") != 1349678672
                or catalog.get("schema_version") != 1 or not isinstance(catalog.get("filings"), list)):
            raise VaultError("INVALID_CATALOG", "Expected a schema-version 1 catalog from canonical repository 1349678672.", status=400)
        try:
            generated = datetime.fromisoformat(catalog["generated_at"].replace("Z", "+00:00"))
            if generated.tzinfo is None:
                raise ValueError("timezone required")
            timestamp = generated.timestamp()
            if timestamp > self.clock() + 300:
                raise ValueError("future catalog")
        except (KeyError, TypeError, AttributeError, ValueError):
            raise VaultError("INVALID_CATALOG", "The catalog requires a valid UTC generation timestamp.", status=400) from None
        records = [self._normalize_record(record) for record in catalog["filings"]
                   if not isinstance(record, dict) or not is_synthetic(record)]
        skipped = len(catalog["filings"]) - len(records)
        if len({record["filing_id"] for record in records}) != len(records):
            raise VaultError("INVALID_CATALOG", "The catalog contains duplicate canonical filing IDs.", status=400)
        digest = hashlib.sha256(json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self._transaction(exclusive=True) as conn:
            checkpoint = conn.execute(select(schema.catalog_checkpoints).where(
                schema.catalog_checkpoints.c.catalog_id == "tracker_catalog").with_for_update()).mappings().first()
            if checkpoint:
                if timestamp < checkpoint["generated_at"] or (timestamp == checkpoint["generated_at"] and digest != checkpoint["sha256"]):
                    raise VaultError("STALE_CATALOG", "An older or conflicting catalog cannot replace the latest imported source metadata.", status=409)
                if digest == checkpoint["sha256"]:
                    return {"filings": len(records), "skipped_synthetic": skipped, "changed": False, "documents_retrieved": 0}
            for record in records:
                self._register_record(conn, record, self.clock())
            # A second pass makes exact relationships independent of row order.
            for record in records:
                self._relationships(conn, record, self.clock())
            values = {"generated_at": timestamp, "sha256": digest, "imported_at": self.clock()}
            if checkpoint:
                conn.execute(update(schema.catalog_checkpoints).where(
                    schema.catalog_checkpoints.c.catalog_id == "tracker_catalog").values(**values))
            else:
                conn.execute(insert(schema.catalog_checkpoints).values(catalog_id="tracker_catalog", **values))
        return {"filings": len(records), "skipped_synthetic": skipped, "changed": True, "documents_retrieved": 0}

    def _relationships(self, conn, record, now):
        """Link exact known IDs only; never infer an amendment from a person's name."""
        links = ((record.get("supersedes_filing_id"), "superseded_by_filing_id"),
                 (record.get("superseded_by_filing_id"), "supersedes_filing_id"))
        for other_id, field in links:
            if not other_id:
                continue
            if other_id == record["filing_id"]:
                raise VaultError("INVALID_REVISION", "A filing cannot supersede itself.", status=409)
            other = conn.execute(select(schema.filings).where(
                schema.filings.c.filing_id == other_id).with_for_update()).mappings().first()
            if other:
                if other["source"] != record["source"]:
                    raise VaultError("INVALID_REVISION", "An amendment cannot substitute a different source.", status=409)
                updated = dict(other["record"])
                previous = updated.get(field)
                if previous and previous != record["filing_id"]:
                    raise VaultError("REVISION_CONFLICT", "The catalog contains conflicting amendment links.", status=409)
                updated[field] = record["filing_id"]
                conn.execute(update(schema.filings).where(schema.filings.c.filing_id == other_id).values(
                    record=updated, updated_at=now))
                LOG.info("amendment_detected source=%s", record["source"])

    def get_filing(self, filing_id):
        with self.engine.connect() as conn:
            return self._serialize(conn, self._row(conn, filing_id))

    def list_filings(self, *, source=None, search=None, status=None, filing_type=None,
                     sort="newest_filing", limit=100, offset=0):
        # Catalogs are bounded/paginated. JSON fields stay portable to Postgres
        # and SQLite using SQLAlchemy JSON expressions, never SQL string input.
        query = select(schema.filings)
        filters = []
        if source:
            filters.append(schema.filings.c.source == source)
        if search:
            pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            filters.append(schema.filings.c.record["filer_name"].as_string().ilike(pattern, escape="\\") |
                           schema.filings.c.filing_id.ilike(pattern, escape="\\") |
                           schema.filings.c.record["external_filing_id"].as_string().ilike(pattern, escape="\\"))
        if filing_type:
            filters.append(schema.filings.c.record["filing_type"].as_string().ilike("%" + filing_type + "%"))
        if status == "amended":
            filters.append(schema.filings.c.record["is_amended"].as_boolean().is_(True))
        elif status == "superseded":
            filters.append(schema.filings.c.record["superseded_by_filing_id"].as_string() != "")
        if filters:
            query = query.where(and_(*filters))
        doc = schema.documents
        orders = {
            "newest_filing": schema.filings.c.record["filing_date"].as_string().desc(),
            "newest_retrieval": doc.c.retrieved_at.desc(),
            "cache_expiration": doc.c.expires_at.asc(),
            "source": schema.filings.c.source.asc(),
        }
        query = query.outerjoin(doc, doc.c.document_id == schema.filings.c.current_document_id)
        with self.engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(query.subquery())).scalar_one()
            rows = conn.execute(query.order_by(orders.get(sort, orders["newest_filing"]),
                                               schema.filings.c.filing_id).limit(min(200, max(1, limit))).offset(max(0, offset))).mappings()
            return {"filings": [self._serialize(conn, dict(row), include_versions=False) for row in rows],
                    "total": total, "limit": min(200, max(1, limit)), "offset": max(0, offset)}

    def _cached(self, conn, row, now):
        document = self._document(conn, row)
        if not document:
            return None, None
        if row["cache_status"] == "INVALID":
            # A prior source check proved a changed revision but could not
            # persist its replacement. Old bytes must not become current again.
            return document, None
        if document["expires_at"] <= now:
            LOG.info("cache_expired source=%s", row["source"])
            conn.execute(update(schema.documents).where(schema.documents.c.document_id == document["document_id"]).values(cache_status="EXPIRED"))
            row["cache_status"] = "EXPIRED"
            return document, None
        try:
            body = self.store.get(document["object_key"])
        except StorageError:
            body = None
            row["cache_status"] = "UNAVAILABLE"
        if body is not None and len(body) == document["file_size"] and hashlib.sha256(body).hexdigest() == document["sha256"]:
            row["cache_status"] = "VALID"
            conn.execute(update(schema.documents).where(schema.documents.c.document_id == document["document_id"]).values(cache_status="VALID"))
            conn.execute(update(schema.filings).where(schema.filings.c.filing_id == row["filing_id"]).values(cache_status="VALID"))
            return document, body
        if body is not None:
            LOG.warning("integrity_hash_mismatch source=%s", row["source"])
            status = "CORRUPT"
        else:
            status = row["cache_status"] if row["cache_status"] == "UNAVAILABLE" else "MISSING"
        row["cache_status"] = status
        conn.execute(update(schema.documents).where(schema.documents.c.document_id == document["document_id"]).values(cache_status=status))
        return document, None

    def _access_error(self, record):
        if record.get("requires_request") or record.get("access_class") == "REQUEST_REQUIRED":
            LOG.info("request_required_source_encountered source=%s", record["source"])
            return VaultError("REQUEST_REQUIRED", "This disclosure requires a request from OGE or the employing agency; it is not available for direct retrieval.", status=403)
        if record.get("access_class") == "UNAVAILABLE":
            return VaultError("SOURCE_UNAVAILABLE", "The official source does not provide this filing for direct retrieval.", status=409)
        if self._status(record) in {"Superseded", "Withdrawn", "Invalid", "Archived"}:
            return VaultError("FILING_NOT_CURRENT", "This filing is superseded, withdrawn or archived. Its provenance remains available; it is not served as the current filing.", status=409)
        return None

    def _metadata(self, conn, row, provider, now):
        previous = row["record"]
        incoming = provider.get_metadata(dict(previous))
        _check_identity(previous, incoming)
        if incoming.get("filing_id", row["filing_id"]) != row["filing_id"] or incoming.get("source", row["source"]) != row["source"]:
            raise VaultError("IDENTITY_MISMATCH", "The source returned a different filing identity.", status=409)
        merged = {**previous, **{key: value for key, value in incoming.items() if key in RECORD_FIELDS}}
        merged["source_metadata"] = {**(previous.get("source_metadata") or {}), **(incoming.get("source_metadata") or {})}
        changed = json.dumps(previous, sort_keys=True) != json.dumps(merged, sort_keys=True)
        conn.execute(insert(schema.source_metadata).values(metadata_id=str(uuid.uuid4()),
                    filing_id=row["filing_id"], validated_at=now, metadata_snapshot=merged, changed=changed))
        row.update(record=merged, last_validated_at=now)
        conn.execute(update(schema.filings).where(schema.filings.c.filing_id == row["filing_id"]).values(
            record=merged, last_validated_at=now, updated_at=now))
        self._relationships(conn, merged, now)
        return merged

    def document(self, filing_id, *, refresh=False):
        """Return exact immutable source bytes; validate SHA-256 on every cache hit.

        A refresh always contacts the source and compares content, including a
        same-URL replacement. Only a still-valid verified copy may survive an
        upstream outage. Expired, superseded or corrupt evidence never falls back.
        """
        result, error = None, None
        with self._transaction() as conn:
            row = self._row(conn, filing_id, lock=True)
            access_error = self._access_error(row["record"])
            if access_error:
                access_error.filing = self._serialize(conn, row)
                raise access_error
            now = self.clock()
            known_changed = row["cache_status"] == "INVALID"
            prior_record = dict(row["record"])
            previous_document, cached = self._cached(conn, row, now)
            if cached is not None and not refresh:
                LOG.info("cache_hit source=%s", row["source"])
                return DocumentResult(cached, previous_document["content_type"], self._serialize(conn, row), True)
            LOG.info("filing_retrieval_attempted source=%s", row["source"])
            if cached is None:
                LOG.info("cache_miss source=%s", row["source"])
            try:
                provider = self.providers.get(row["source"])
                record = self._metadata(conn, row, provider, now)
                if previous_document:
                    old_evidence = previous_document["source_metadata"] or {}
                    new_evidence = record.get("source_metadata") or {}
                    known_changed = known_changed or prior_record.get("document_url") != record.get("document_url")
                    for key in ("etag", "last_modified", "validated_document_sha256"):
                        if new_evidence.get(key) and old_evidence.get(key) and new_evidence[key] != old_evidence[key]:
                            known_changed = True
                denied = self._access_error(record)
                if denied:
                    raise denied
                fetched = provider.get_document(dict(record))
                provider.validate_document(fetched)
                body = fetched.body
                digest = hashlib.sha256(body).hexdigest()
                if previous_document and digest != previous_document["sha256"]:
                    known_changed = True
                retrieved = self.clock()
                # No sliding expiry: a successful validation with unchanged bytes
                # leaves the retained object and original retrieval timestamps.
                if (cached is not None and digest == previous_document["sha256"]
                        and previous_document["expires_at"] > retrieved):
                    conn.execute(update(schema.filings).where(schema.filings.c.filing_id == filing_id).values(
                        cache_status="VALID", retrieval_status="SUCCESS", retrieval_error=None,
                        last_validated_at=retrieved, updated_at=retrieved))
                    row.update(cache_status="VALID", retrieval_status="SUCCESS", retrieval_error=None,
                               last_validated_at=retrieved)
                    result = DocumentResult(cached, previous_document["content_type"], self._serialize(conn, row), True)
                else:
                    key = object_key(record, digest, fetched.content_type)
                    self.store.put(key, body, fetched.content_type)
                    stored = self.store.get(key)
                    if stored is None or hashlib.sha256(stored).hexdigest() != digest or stored != body:
                        raise StorageError("Evidence storage failed integrity verification")
                    document_id = str(uuid.uuid4())
                    version = (conn.execute(select(func.max(schema.versions.c.document_version)).where(
                        schema.versions.c.filing_id == filing_id)).scalar_one() or 0) + 1
                    provenance = {**(record.get("source_metadata") or {}), **(fetched.source_metadata or {})}
                    conn.execute(insert(schema.documents).values(
                        document_id=document_id, filing_id=filing_id, object_key=key, sha256=digest,
                        content_type=fetched.content_type, file_size=len(body), retrieved_at=retrieved,
                        expires_at=retrieved + CACHE_TTL_SECONDS, cache_status="VALID",
                        document_url=fetched.document_url, official_source_url=record["official_source_url"],
                        source_metadata=provenance))
                    snapshot = {**record, "document_url": fetched.document_url, "source_metadata": provenance,
                                "content_changed": previous_document is not None and previous_document["sha256"] != digest}
                    conn.execute(insert(schema.versions).values(
                        version_id=str(uuid.uuid4()), filing_id=filing_id, document_id=document_id,
                        document_version=version, source_snapshot=snapshot, created_at=retrieved))
                    row.update(current_document_id=document_id, cache_status="VALID", retrieval_status="SUCCESS",
                               retrieval_error=None, last_validated_at=retrieved)
                    conn.execute(update(schema.filings).where(schema.filings.c.filing_id == filing_id).values(
                        current_document_id=document_id, cache_status="VALID", retrieval_status="SUCCESS",
                        retrieval_error=None, last_validated_at=retrieved, updated_at=retrieved))
                    if previous_document and previous_document["sha256"] != digest:
                        LOG.info("source_changed source=%s", row["source"])
                    result = DocumentResult(body, fetched.content_type, self._serialize(conn, row), False)
                LOG.info("filing_retrieval_succeeded source=%s", row["source"])
            except (ProviderError, StorageError, VaultError) as exc:
                if isinstance(exc, StorageError):
                    code, message, status = "STORAGE_UNAVAILABLE", "The private filing cache is temporarily unavailable. Please retry or open the Official Source.", 503
                else:
                    code, message, status = exc.code, exc.message, exc.status
                LOG.warning("filing_retrieval_failed source=%s code=%s", row["source"], code)
                safe_error = {"code": code, "message": message}
                row.update(retrieval_status="FAILED", retrieval_error=safe_error)
                if known_changed or code in {"SOURCE_NOT_FOUND", "FILING_ID_MISMATCH", "IDENTITY_MISMATCH"}:
                    row["cache_status"] = "INVALID"
                conn.execute(update(schema.filings).where(schema.filings.c.filing_id == filing_id).values(
                    cache_status=row["cache_status"], retrieval_status="FAILED", retrieval_error=safe_error,
                    updated_at=self.clock()))
                # Only transient source/storage failure can fall back. A source
                # withdrawal, identity mismatch or security rejection must close.
                retryable = isinstance(exc, StorageError) or bool(getattr(exc, "retryable", False))
                if (retryable and not known_changed and cached is not None and previous_document["expires_at"] > self.clock()
                        and self._access_error(row["record"]) is None):
                    result = DocumentResult(cached, previous_document["content_type"], self._serialize(conn, row), True,
                        "Official source is temporarily unavailable. Showing the verified copy retrieved on " + utc_iso(previous_document["retrieved_at"]) + ".")
                else:
                    if known_changed and retryable:
                        code, message = "SOURCE_CHANGED_UNAVAILABLE", "The official source has changed. The older cached copy is not served as current; retry retrieval or open the Official Source."
                    if previous_document and previous_document["expires_at"] <= self.clock() and retryable:
                        code, message = "CACHE_EXPIRED_SOURCE_UNAVAILABLE", "This filing's cached copy has expired and the official source could not currently be reached. Retry or open the Official Source."
                    error = VaultError(code, message, status=status, filing=self._serialize(conn, row))
        if error:
            raise error
        return result

    def revalidate(self, filing_id):
        """Scheduled metadata check, separate from document retention/retrieval.

        Source adapters disclose validation scope (headers vs exact content).
        Catalog discovery/amendment links arrive through the existing ingestion
        catalog, not guessed from a HEAD response. This never extends the TTL.
        """
        # Tracked documents receive a complete content comparison. Headers alone
        # cannot detect a same-URL replacement and cannot keep it marked current.
        with self.engine.connect() as conn:
            existing = self._row(conn, filing_id)
            current = self._document(conn, existing)
        if current and current["expires_at"] > self.clock() and not self._access_error(existing["record"]):
            try:
                result = self.document(filing_id, refresh=True)
                return {"filing_id": filing_id, "result": "failed" if result.warning else "validated",
                        "error": "SOURCE_UNAVAILABLE" if result.warning else None}
            except VaultError as exc:
                return {"filing_id": filing_id, "result": "failed", "error": exc.code}
        error = None
        with self._transaction() as conn:
            row = self._row(conn, filing_id, lock=True)
            if self._access_error(row["record"]):
                return {"filing_id": filing_id, "result": "skipped_access_or_historical"}
            try:
                self._metadata(conn, row, self.providers.get(row["source"]), self.clock())
            except ProviderError as exc:
                conn.execute(update(schema.filings).where(schema.filings.c.filing_id == filing_id).values(
                    retrieval_error={"code": exc.code, "message": exc.message}, updated_at=self.clock()))
                error = exc.code
        return {"filing_id": filing_id, "result": "failed" if error else "validated", "error": error}

    def reconcile(self, *, revalidate=True, limit=10000):
        """Daily runtime task: expire objects, keep provenance, remove orphans.

        No production-state artifact, transaction, analysis or filing row is
        deleted. Failed deletions remain eligible for the next reconciliation.
        The database lock makes orphan cleanup safe against concurrent uploads.
        """
        counts = {"expired_documents": 0, "deleted_objects": 0, "orphaned_objects": 0,
                  "storage_failures": 0, "validated": 0, "validation_failed": 0, "skipped": 0}
        now = self.clock()
        with self._transaction(exclusive=True) as conn:
            expired = list(conn.execute(select(schema.documents).where(schema.documents.c.expires_at <= now)).mappings())
            live_keys = set(conn.execute(select(schema.documents.c.object_key).where(
                schema.documents.c.expires_at > now)).scalars())
            for document in expired:
                if document["cache_status"] != "EXPIRED":
                    counts["expired_documents"] += 1
                conn.execute(update(schema.documents).where(schema.documents.c.document_id == document["document_id"]).values(cache_status="EXPIRED"))
                conn.execute(update(schema.filings).where(schema.filings.c.current_document_id == document["document_id"]).values(cache_status="EXPIRED"))
            try:
                objects = list(self.store.list_objects())
                known_keys = {doc["object_key"] for doc in expired} | live_keys
                for key in objects:
                    if key not in live_keys:
                        try:
                            self.store.delete(key)
                            counts["deleted_objects"] += 1
                            if key not in known_keys:
                                counts["orphaned_objects"] += 1
                        except StorageError:
                            counts["storage_failures"] += 1
            except StorageError:
                counts["storage_failures"] += 1
            # Opaque acknowledgement receipts expire without retaining sessions
            # indefinitely. Historical filing provenance is never deleted.
            conn.execute(delete(schema.acknowledgements).where(schema.acknowledgements.c.expires_at <= now))
            due = list(conn.execute(select(schema.filings.c.filing_id).where(
                (schema.filings.c.last_validated_at.is_(None)) |
                (schema.filings.c.last_validated_at <= now - 86400)
            ).order_by(schema.filings.c.last_validated_at.asc(), schema.filings.c.filing_id).limit(limit)).scalars())
        if revalidate:
            for filing_id in due:
                result = self.revalidate(filing_id)
                counts[{"validated": "validated", "failed": "validation_failed"}.get(result["result"], "skipped")] += 1
        LOG.info("cache_reconciled %s", json.dumps(counts, sort_keys=True))
        return counts
