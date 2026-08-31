"""Additive SQLAlchemy schema for the evidence vault, separate from tracker state.

No table here is an ingestion baseline or production tracker-state authority.
Original document bytes live only in a private runtime object store.
"""

from sqlalchemy import (
    JSON, Boolean, Column, Float, ForeignKey, Integer, MetaData, String, Table,
    Text, UniqueConstraint, text,
)

metadata = MetaData()

catalog_checkpoints = Table(
    "vault_catalog_checkpoints", metadata,
    Column("catalog_id", String(64), primary_key=True),
    Column("generated_at", Float, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("imported_at", Float, nullable=False),
)

filings = Table(
    "vault_filings", metadata,
    Column("filing_id", String(512), primary_key=True),
    Column("source", String(32), nullable=False, index=True),
    # Canonical catalog metadata; version snapshots below are immutable.
    Column("record", JSON, nullable=False),
    Column("current_document_id", String(36)),
    Column("last_validated_at", Float),
    Column("cache_status", String(32), nullable=False, default="MISSING"),
    Column("retrieval_status", String(32), nullable=False, default="NOT_RETRIEVED"),
    Column("retrieval_error", JSON),
    Column("updated_at", Float, nullable=False),
)

documents = Table(
    "vault_filing_documents", metadata,
    Column("document_id", String(36), primary_key=True),
    Column("filing_id", String(512), ForeignKey("vault_filings.filing_id"), nullable=False, index=True),
    Column("object_key", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("file_size", Integer, nullable=False),
    Column("retrieved_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False, index=True),
    Column("cache_status", String(32), nullable=False),
    Column("document_url", Text, nullable=False),
    Column("official_source_url", Text, nullable=False),
    Column("source_metadata", JSON, nullable=False),
)

versions = Table(
    "vault_filing_versions", metadata,
    Column("version_id", String(36), primary_key=True),
    Column("filing_id", String(512), ForeignKey("vault_filings.filing_id"), nullable=False, index=True),
    Column("document_id", String(36), ForeignKey("vault_filing_documents.document_id"), nullable=False),
    Column("document_version", Integer, nullable=False),
    Column("source_snapshot", JSON, nullable=False),
    Column("created_at", Float, nullable=False),
    UniqueConstraint("filing_id", "document_version"),
)

source_metadata = Table(
    "vault_filing_source_metadata", metadata,
    Column("metadata_id", String(36), primary_key=True),
    Column("filing_id", String(512), ForeignKey("vault_filings.filing_id"), nullable=False, index=True),
    Column("validated_at", Float, nullable=False),
    Column("metadata_snapshot", JSON, nullable=False),
    Column("changed", Boolean, nullable=False),
)

acknowledgements = Table(
    "vault_filing_acknowledgements", metadata,
    Column("session_hash", String(64), primary_key=True),
    Column("acknowledgement_type", String(64), nullable=False),
    Column("version", String(64), nullable=False),
    Column("policy_version", String(128), nullable=False),
    Column("accepted_at", Float, nullable=False),
    Column("expires_at", Float, nullable=False, index=True),
)


def secure_postgresql_tables(connection):
    """Deny direct browser-role access to private Vault tables on PostgreSQL.

    Supabase's exposed schema can give newly created tables default grants. The
    HTTP API's projection is not a security boundary if PostgREST can read these
    tables directly. Only the six explicitly owned tables are touched. RLS has
    no browser policy; the table owner or a server-only BYPASSRLS role continues
    to operate. Do not FORCE RLS and inadvertently deny the owning service.

    Run in the same transaction as create_all so new tables are never committed
    with default browser grants. Errors deliberately propagate and roll back the
    migration instead of leaving a partially secured schema.
    """
    if connection.dialect.name != "postgresql":
        return
    roles = set(connection.execute(text(
        "SELECT rolname FROM pg_catalog.pg_roles WHERE rolname IN ('anon', 'authenticated')"
    )).scalars())
    preparer = connection.dialect.identifier_preparer
    for table in metadata.sorted_tables:
        qualified = preparer.format_table(table)
        connection.execute(text(f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"REVOKE ALL PRIVILEGES ON TABLE {qualified} FROM PUBLIC"))
        for role in sorted(roles & {"anon", "authenticated"}):
            connection.execute(text(
                f"REVOKE ALL PRIVILEGES ON TABLE {qualified} FROM {preparer.quote(role)}"
            ))
