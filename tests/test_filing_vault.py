"""Offline vault acceptance: exact identities, provenance, retention and API gates."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import time

import pytest
from sqlalchemy import create_engine, func, select

from backend.filing_vault import create_vault_app
from backend.filing_vault import schema
from backend.filing_vault.api import ACK_POLICY_VERSION, ACK_VERSION
from backend.filing_vault.providers import ProviderError, RetrievedDocument, normalize_filing
from backend.filing_vault.service import CACHE_TTL_SECONDS, VaultError, VaultService, utc_iso
from backend.filing_vault.storage import FileObjectStore, StorageError, SupabaseObjectStore, object_key

PDF_A = b"%PDF-1.4\nimmutable first filing\n%%EOF\n"
PDF_B = b"%PDF-1.4\nimmutable corrected filing\n%%EOF\n"
URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/12345.pdf"


def record(filing_id="house:2026:12345", **changes):
    return {"filing_id": filing_id, "external_filing_id": "house:2026:12345", "filer_id": "official-42",
            "filer_name": "TEST Official", "source": "house", "filing_type": "PTR",
            "filing_date": "2026-08-27", "report_period": "2026", "official_source_url": URL,
            "document_url": URL, "access_class": "ACKNOWLEDGEMENT_REQUIRED", **changes}


class Clock:
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeProvider:
    def __init__(self):
        self.body, self.content_type = PDF_A, "application/pdf"
        self.metadata_calls = self.document_calls = 0
        self.failure = self.document_failure = None
        self.overlay = {}

    def resolve_filing(self, row):
        return normalize_filing(row)

    def get_metadata(self, row):
        self.metadata_calls += 1
        if self.failure:
            raise self.failure
        return {**deepcopy(row), **deepcopy(self.overlay)}

    def get_document(self, row):
        self.document_calls += 1
        if self.document_failure:
            raise self.document_failure
        return RetrievedDocument(self.body, self.content_type, row["document_url"],
                                 {"validation_scope": "exact_document_content", "upstream_request_id": "test-receipt"})

    def validate_document(self, document):
        if document.content_type != "application/pdf" or not document.body.startswith(b"%PDF-"):
            raise ProviderError("INVALID_DOCUMENT", "The source did not return a PDF.")


class FakeRegistry:
    def __init__(self):
        self.provider = FakeProvider()

    def get(self, source):
        return self.provider


@pytest.fixture
def vault(tmp_path):
    clock = Clock()
    engine = create_engine("sqlite:///" + str(tmp_path / "vault.sqlite"),
                           connect_args={"check_same_thread": False, "timeout": 5})
    providers = FakeRegistry()
    store = FileObjectStore(tmp_path / "private-evidence")
    service = VaultService(engine, store, providers, clock=clock)
    service.init_schema()
    service.register_filing(record())
    yield service, providers.provider, clock, store
    engine.dispose()


def count(service, table):
    with service.engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def outage():
    return ProviderError("SOURCE_UNAVAILABLE", "The official source is temporarily unavailable.", retryable=True)


def test_cache_hit_is_exact_local_bytes_without_upstream(vault):
    service, provider, _, _ = vault
    first = service.document(record()["filing_id"])
    second = service.document(record()["filing_id"])
    assert first.body == second.body == PDF_A
    assert first.cache_hit is False and second.cache_hit is True
    assert provider.document_calls == provider.metadata_calls == 1
    assert count(service, schema.documents) == 1
    assert second.filing["sha256"] == hashlib.sha256(PDF_A).hexdigest()


def test_existing_flask_factory_embeds_vault_without_legacy_connection(vault):
    from backend.api import create_app
    service, _, _, _ = vault
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://",
                      "VAULT_ENABLED": True, "VAULT_SERVICE": service,
                      "VAULT_SECRET_KEY": "TEST-only-key-with-at-least-thirty-two-characters"})
    client = app.test_client()
    response = client.get("/api/filings")
    assert response.status_code == 200
    assert response.json["filings"][0]["filing_id"] == record()["filing_id"]
    response = client.post("/api/filing-acknowledgements", json={"payload": "x" * 17000},
                           headers={"Origin": "http://localhost"})
    assert response.status_code == 413


def test_ttl_is_exact_30_days_and_boundary_refetches(vault):
    service, provider, clock, _ = vault
    first = service.document(record()["filing_id"])
    assert first.filing["expires_at"] == utc_iso(clock() + 30 * 86400)
    clock.advance(CACHE_TTL_SECONDS - 1)
    assert service.document(record()["filing_id"]).cache_hit
    clock.advance(1)
    assert service.get_filing(record()["filing_id"])["cache_status"] == "EXPIRED"
    second = service.document(record()["filing_id"])
    assert not second.cache_hit
    assert provider.document_calls == 2
    assert second.filing["retrieved_at"] != first.filing["retrieved_at"]
    assert count(service, schema.documents) == 2


def test_expired_outage_never_serves_old_bytes(vault):
    service, provider, clock, _ = vault
    first = service.document(record()["filing_id"])
    clock.advance(CACHE_TTL_SECONDS)
    provider.failure = outage()
    with pytest.raises(VaultError) as exc:
        service.document(record()["filing_id"])
    assert exc.value.code == "CACHE_EXPIRED_SOURCE_UNAVAILABLE"
    assert exc.value.filing["retrieved_at"] == first.filing["retrieved_at"]
    assert exc.value.filing["cache_status"] == "EXPIRED"


def test_valid_cached_document_survives_transient_source_outage(vault):
    service, provider, clock, _ = vault
    first = service.document(record()["filing_id"])
    clock.advance(3600)
    provider.failure = outage()
    refreshed = service.document(record()["filing_id"], refresh=True)
    assert refreshed.body == PDF_A and refreshed.cache_hit
    assert "temporarily unavailable" in refreshed.warning
    assert refreshed.filing["retrieved_at"] == first.filing["retrieved_at"]
    assert refreshed.filing["last_validated_at"] == first.filing["last_validated_at"]
    assert service.document(record()["filing_id"]).body == PDF_A


@pytest.mark.parametrize("corruption", [b"%PDF-1.4\nchanged\n%%EOF", b"not a pdf", None])
def test_missing_or_corrupt_cache_refetches_without_serving_bad_bytes(vault, corruption):
    service, provider, _, store = vault
    first = service.document(record()["filing_id"])
    key = object_key(record(), first.filing["sha256"], "application/pdf")
    if corruption is None:
        store.delete(key)
    else:
        store.put(key, corruption, "application/pdf")
    assert service.document(record()["filing_id"]).body == PDF_A
    assert provider.document_calls == 2
    assert store.get(key) == PDF_A


def test_corrupt_cached_bytes_cannot_fallback_during_outage(vault):
    service, provider, _, store = vault
    first = service.document(record()["filing_id"])
    store.put(object_key(record(), first.filing["sha256"], "application/pdf"), b"bad", "application/pdf")
    provider.failure = outage()
    with pytest.raises(VaultError):
        service.document(record()["filing_id"])
    assert service.get_filing(record()["filing_id"])["cache_status"] == "CORRUPT"


def test_unchanged_refresh_preserves_object_and_original_timestamps(vault):
    service, provider, clock, store = vault
    first = service.document(record()["filing_id"])
    objects = list(store.list_objects())
    clock.advance(86400)
    refreshed = service.document(record()["filing_id"], refresh=True)
    assert provider.document_calls == 2
    assert refreshed.filing["retrieved_at"] == first.filing["retrieved_at"]
    assert refreshed.filing["expires_at"] == first.filing["expires_at"]
    assert refreshed.filing["last_validated_at"] == utc_iso(clock())
    assert refreshed.filing["document_version"] == 1
    assert list(store.list_objects()) == objects
    assert count(service, schema.versions) == 1


def test_changed_same_url_hash_creates_version_and_keeps_provenance(vault):
    service, provider, clock, store = vault
    first = service.document(record()["filing_id"])
    provider.body = PDF_B
    clock.advance(3600)
    second = service.document(record()["filing_id"], refresh=True)
    assert second.body == PDF_B and second.filing["document_version"] == 2
    assert len(second.filing["versions"]) == 2
    assert second.filing["versions"][1]["sha256"] == first.filing["sha256"]
    assert second.filing["versions"][1]["official_source_url"] == URL
    assert store.get(object_key(record(), first.filing["sha256"], "application/pdf")) == PDF_A


def test_changed_source_url_same_bytes_preserves_retrieval_provenance(vault):
    service, provider, clock, _ = vault
    first = service.document(record()["filing_id"])
    clock.advance(86400)
    provider.overlay = {"document_url": URL + "?revision=verified"}
    second = service.document(record()["filing_id"], refresh=True)
    assert second.filing["document_url"] == URL
    assert second.filing["retrieved_at"] == first.filing["retrieved_at"]
    assert count(service, schema.source_metadata) == 2


def test_changed_source_then_failed_fetch_invalidates_previous_copy(vault):
    service, provider, _, _ = vault
    service.document(record()["filing_id"])
    provider.overlay = {"document_url": URL + "?new=1"}
    provider.document_failure = outage()
    with pytest.raises(VaultError) as exc:
        service.document(record()["filing_id"], refresh=True)
    assert exc.value.code == "SOURCE_CHANGED_UNAVAILABLE"
    assert service.get_filing(record()["filing_id"])["cache_status"] == "INVALID"
    with pytest.raises(VaultError):
        service.document(record()["filing_id"])


def test_source_404_does_not_allow_next_get_to_hit_old_cache(vault):
    service, provider, _, _ = vault
    service.document(record()["filing_id"])
    provider.failure = ProviderError("SOURCE_NOT_FOUND", "The source removed the report.", status=404)
    with pytest.raises(VaultError):
        service.document(record()["filing_id"], refresh=True)
    assert service.get_filing(record()["filing_id"])["cache_status"] == "INVALID"
    with pytest.raises(VaultError):
        service.document(record()["filing_id"])
    provider.failure = None
    assert service.document(record()["filing_id"]).body == PDF_A


def test_request_required_never_calls_source_and_metadata_remains_available(vault):
    service, provider, _, _ = vault
    service.register_filing(record("oge:request", source="oge", access_class="REQUEST_REQUIRED", requires_request=True,
                                    access_method="OGE_FORM_201", document_url=""))
    with pytest.raises(VaultError) as exc:
        service.document("oge:request")
    assert exc.value.code == "REQUEST_REQUIRED"
    assert provider.metadata_calls == provider.document_calls == 0
    assert service.get_filing("oge:request")["access_method"] == "OGE_FORM_201"


def test_exact_amendment_links_superseded_not_served_current(vault):
    service, provider, _, _ = vault
    service.document(record()["filing_id"])
    service.register_filing(record("house:amended", is_amended=True, supersedes_filing_id=record()["filing_id"]))
    old = service.get_filing(record()["filing_id"])
    assert old["status"] == "Superseded" and old["superseded_by_filing_id"] == "house:amended"
    assert service.get_filing("house:amended")["status"] == "Amended"
    with pytest.raises(VaultError) as exc:
        service.document(record()["filing_id"])
    assert exc.value.code == "FILING_NOT_CURRENT"
    assert provider.document_calls == 1
    assert len(old["versions"]) == 1 and not old["versions"][0]["is_current"]
    service.register_filing(record())
    assert service.get_filing(record()["filing_id"])["status"] == "Superseded"
    assert service.list_filings(status="superseded")["total"] == 1


def test_wrong_identity_from_source_is_never_substituted(vault):
    service, provider, _, _ = vault
    provider.overlay = {"filing_id": "house:some-other-filing"}
    with pytest.raises(VaultError) as exc:
        service.document(record()["filing_id"])
    assert exc.value.code == "IDENTITY_MISMATCH"
    assert provider.document_calls == 0


def test_cleanup_retains_metadata_removes_expired_objects_and_orphans(vault):
    service, provider, clock, store = vault
    first = service.document(record()["filing_id"])
    orphan = object_key(record("orphan"), "a" * 64, "application/pdf")
    store.put(orphan, PDF_A, "application/pdf")
    clock.advance(CACHE_TTL_SECONDS)
    report = service.reconcile()
    assert report["expired_documents"] == 1 and report["orphaned_objects"] == 1
    assert report["deleted_objects"] == 2 and list(store.list_objects()) == []
    assert provider.document_calls == 1  # Daily cleanup must not refetch expired bytes.
    retained = service.get_filing(record()["filing_id"])
    assert retained["cache_status"] == "EXPIRED" and retained["sha256"] == first.filing["sha256"]
    assert count(service, schema.versions) == 1


def test_cleanup_preserves_shared_key_with_unexpired_retrieval(vault):
    service, _, clock, store = vault
    service.document(record()["filing_id"])
    clock.advance(CACHE_TTL_SECONDS)
    latest = service.document(record()["filing_id"])
    service.reconcile(revalidate=False)
    assert store.get(object_key(record(), latest.filing["sha256"], "application/pdf")) == PDF_A


def test_cleanup_removes_abandoned_atomic_upload(vault):
    service, _, _, store = vault
    orphan = store.root / "filings" / "house" / ".upload-abandoned"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"interrupted partial upload")
    report = service.reconcile(revalidate=False)
    assert report["orphaned_objects"] == 1
    assert not orphan.exists()


def test_daily_check_compares_content_without_sliding_expiry(vault):
    service, provider, clock, _ = vault
    first = service.document(record()["filing_id"])
    clock.advance(86400)
    assert service.reconcile()["validated"] == 1
    assert service.get_filing(record()["filing_id"])["expires_at"] == first.filing["expires_at"]
    assert provider.document_calls == 2
    provider.body = PDF_B
    clock.advance(86400)
    assert service.reconcile()["validated"] == 1
    assert service.get_filing(record()["filing_id"])["document_version"] == 2


def test_concurrent_requests_create_one_document(vault):
    service, provider, _, _ = vault
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(workers.map(lambda _: service.document(record()["filing_id"]), range(8)))
    assert all(result.body == PDF_A for result in results)
    assert provider.document_calls == 1
    assert count(service, schema.documents) == 1


def test_storage_failure_does_not_commit_false_success(vault, monkeypatch):
    service, _, _, store = vault
    def unavailable(*_):
        raise StorageError("test unavailable")
    monkeypatch.setattr(store, "put", unavailable)
    with pytest.raises(VaultError) as exc:
        service.document(record()["filing_id"])
    assert exc.value.code == "STORAGE_UNAVAILABLE"
    assert count(service, schema.documents) == 0
    assert service.get_filing(record()["filing_id"])["retrieval_status"] == "FAILED"


def catalog(clock, rows):
    return {"schema_version": 1, "repository_id": 1349678672, "generated_at": utc_iso(clock()), "filings": rows}


def test_catalog_import_is_monotonic_idempotent_and_never_fetches(vault):
    service, provider, clock, _ = vault
    old = catalog(clock, [record(), record("house:second")])
    assert service.import_catalog(old)["changed"]
    assert not service.import_catalog(old)["changed"]
    clock.advance(60)
    service.import_catalog(catalog(clock, [record("house:second", is_amended=True)]))
    with pytest.raises(VaultError) as exc:
        service.import_catalog(old)
    assert exc.value.code == "STALE_CATALOG"
    assert service.list_filings()["total"] == 2  # Omission never deletes a filing.
    assert provider.document_calls == provider.metadata_calls == 0


def test_catalog_validation_is_atomic(vault):
    service, _, clock, _ = vault
    with pytest.raises(ProviderError):
        service.import_catalog(catalog(clock, [record("house:new"), record("invalid", source="attacker")]))
    assert service.list_filings()["total"] == 1
    conflict = [record("house:new", supersedes_filing_id="house:new")]
    with pytest.raises(VaultError):
        service.import_catalog(catalog(clock, conflict))
    assert service.list_filings()["total"] == 1


def test_catalog_changed_url_invalidates_cache_before_next_open(vault):
    service, provider, clock, _ = vault
    service.document(record()["filing_id"])
    service.import_catalog(catalog(clock, [record(document_url=URL + "?replacement=1")]))
    assert service.get_filing(record()["filing_id"])["cache_status"] == "INVALID"
    service.document(record()["filing_id"])
    assert provider.document_calls == 2


@pytest.mark.parametrize("changes", [{"is_synthetic_test": True}, {"is_temporary": "true"},
                                    {"test_metadata": {"run_id": "123"}}, {"filing_id": "TEST:house:123"}])
def test_synthetic_records_are_never_retrievable_or_imported(vault, changes):
    service, provider, clock, _ = vault
    row = record("house:synthetic", **changes) if "filing_id" not in changes else record(changes["filing_id"])
    with pytest.raises(VaultError) as exc:
        service.register_filing(row)
    assert exc.value.code == "SIMULATION_NOT_PERMITTED"
    result = service.import_catalog(catalog(clock, [row]))
    assert result["skipped_synthetic"] == 1 and result["filings"] == 0
    assert service.list_filings()["total"] == 1
    assert provider.metadata_calls == provider.document_calls == 0


@pytest.mark.parametrize("field", ["external_filing_id", "filer_id"])
def test_existing_id_cannot_be_reassigned_by_import_or_source(vault, field):
    service, provider, clock, _ = vault
    with pytest.raises(VaultError) as exc:
        service.register_filing(record(**{field: "different-report-or-person"}))
    assert exc.value.code == "IDENTITY_MISMATCH"
    with pytest.raises(VaultError):
        service.import_catalog(catalog(clock, [record(**{field: "different-report-or-person"})]))
    provider.overlay = {field: "different-report-or-person"}
    with pytest.raises(VaultError) as exc:
        service.document(record()["filing_id"])
    assert exc.value.code == "IDENTITY_MISMATCH" and provider.document_calls == 0


def test_public_metadata_omits_paths_credentials_and_private_snapshots(vault):
    service, _, _, _ = vault
    service.register_filing(record(source_metadata={"object_key": "SECRET/object", "internal_path": "SECRET/path",
                                                     "token": "SECRET/token", "report_year": 2026}))
    before = service.get_filing(record()["filing_id"])
    after = service.document(record()["filing_id"]).filing
    assert "SECRET" not in str(before) and "SECRET" not in str(after)
    assert after["source_metadata"]["report_year"] == 2026
    with service.engine.connect() as conn:
        private = conn.execute(select(schema.versions.c.source_snapshot)).scalar_one()
    assert private["source_metadata"]["token"] == "SECRET/token"


@pytest.fixture
def client(vault):
    service, _, _, _ = vault
    app = create_vault_app({"TESTING": True, "VAULT_SERVICE": service,
                            "VAULT_SECRET_KEY": "test-secret-" * 8,
                            "VAULT_ALLOWED_ORIGINS": ["https://dashboard.example"]})
    return app.test_client()


def acknowledge(client):
    notice = client.get("/api/filing-acknowledgements").get_json()
    response = client.post("/api/filing-acknowledgements", json={"accepted": True,
                           "version": notice["version"], "policy_version": notice["policy_version"]},
                           headers={"Origin": "https://dashboard.example"})
    assert response.status_code == 201
    return {"Authorization": "Bearer " + response.get_json()["token"], "Origin": "https://dashboard.example"}


def test_document_requires_ack_and_cached_opens_reuse_receipt(client, vault):
    url = "/api/filings/" + record()["filing_id"] + "/document"
    assert client.get(url).get_json()["code"] == "ACKNOWLEDGEMENT_REQUIRED"
    headers = acknowledge(client)
    assert client.get("/api/filing-acknowledgements", headers=headers).get_json()["acknowledged"]
    first, second = client.get(url, headers=headers), client.get(url, headers=headers)
    assert first.data == second.data == PDF_A
    assert second.headers["X-Filing-Cache"] == "HIT"
    assert count(vault[0], schema.acknowledgements) == 1
    assert "no-store" in second.headers["Cache-Control"]
    assert "sandbox" in second.headers["Content-Security-Policy"]
    assert "script-src 'none'" in second.headers["Content-Security-Policy"]
    assert second.headers["X-Content-Type-Options"] == "nosniff"
    assert "filings/house/" not in str(second.headers)


def test_ack_is_versioned_private_and_expires(client, vault):
    headers = acknowledge(client)
    service, _, clock, _ = vault
    with service.engine.connect() as conn:
        ack = conn.execute(select(schema.acknowledgements)).mappings().one()
    assert ack["version"] == ACK_VERSION and ack["policy_version"] == ACK_POLICY_VERSION
    assert len(ack["session_hash"]) == 64
    assert "session" not in ack
    clock.advance(CACHE_TTL_SECONDS)
    assert not client.get("/api/filing-acknowledgements", headers=headers).get_json()["acknowledged"]
    assert client.get("/api/filings/" + record()["filing_id"] + "/document", headers=headers).status_code == 403


def test_ack_forgery_and_old_version_are_rejected(client):
    forged = {"Authorization": "Bearer fabricated", "Origin": "https://dashboard.example"}
    assert client.get("/api/filings/" + record()["filing_id"] + "/document", headers=forged).status_code == 403
    assert client.post("/api/filing-acknowledgements", json={"accepted": True, "version": "0", "policy_version": ACK_POLICY_VERSION},
                       headers={"Origin": "https://dashboard.example"}).status_code == 400


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "https://dashboard.example.evil.test", None])
def test_post_origin_boundary_rejects_csrf(client, origin):
    response = client.post("/api/filing-acknowledgements", json={"accepted": True, "version": ACK_VERSION, "policy_version": ACK_POLICY_VERSION},
                           headers={"Origin": origin} if origin else {})
    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response.headers


def test_cors_preflight_and_json_boundary(client):
    response = client.options("/api/filings/house:1/refresh", headers={"Origin": "https://dashboard.example"})
    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "https://dashboard.example"
    assert "Authorization" in response.headers["Access-Control-Allow-Headers"]
    assert "Access-Control-Allow-Credentials" not in response.headers
    assert client.post("/api/filing-acknowledgements", data="accepted=true", headers={"Origin": "https://dashboard.example"}).status_code == 415


def test_existing_flask_integration_has_bounded_request_body(vault):
    from flask import Flask, request
    from backend.filing_vault import init_app
    app = Flask("existing-app")
    app.config.update(TESTING=True, VAULT_SERVICE=vault[0], VAULT_SECRET_KEY="test-secret" * 8)
    init_app(app)
    @app.post("/existing-upload")
    def existing_upload():
        return str(len(request.get_data()))
    response = app.test_client().post("/api/filing-acknowledgements", json={"data": "x" * 20000},
                                      headers={"Origin": "http://localhost"})
    assert response.status_code == 413
    assert response.is_json
    assert app.config["MAX_CONTENT_LENGTH"] is None
    assert app.test_client().post("/existing-upload", data=b"x" * 20000).status_code == 200


def test_vault_bounds_chunked_body_without_declared_length(client):
    import io
    response = client.open("/api/filing-acknowledgements", method="POST",
                           content_type="application/json", headers={"Origin": "https://dashboard.example"},
                           environ_overrides={"wsgi.input": io.BytesIO(b'{"data":"' + b"x" * 20000 + b'"}'),
                                              "wsgi.input_terminated": True, "CONTENT_LENGTH": ""})
    assert response.status_code == 413


def test_vault_keeps_stricter_existing_body_limit(vault):
    from flask import Flask
    from backend.filing_vault import init_app
    app = Flask("limited-existing-app")
    app.config.update(TESTING=True, MAX_CONTENT_LENGTH=1024, VAULT_SERVICE=vault[0], VAULT_SECRET_KEY="test-secret" * 8)
    init_app(app)
    response = app.test_client().post("/api/filing-acknowledgements", json={"data": "x" * 2000},
                                      headers={"Origin": "http://localhost"})
    assert response.status_code == 413 and app.config["MAX_CONTENT_LENGTH"] == 1024


@pytest.mark.parametrize("roles", [[], ["anon"], ["authenticated"], ["anon", "authenticated"]])
def test_postgres_security_migration_covers_only_vault_tables_and_existing_roles(roles):
    from sqlalchemy.dialects import postgresql
    statements = []
    class Result:
        def scalars(self):
            return roles
    class Connection:
        dialect = postgresql.dialect()
        def execute(self, statement):
            statements.append(str(statement))
            return Result()
    schema.secure_postgresql_tables(Connection())
    assert statements[0] == "SELECT rolname FROM pg_catalog.pg_roles WHERE rolname IN ('anon', 'authenticated')"
    expected = set()
    for table in schema.metadata.tables.values():
        expected.add(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY")
        expected.add(f"REVOKE ALL PRIVILEGES ON TABLE {table.name} FROM PUBLIC")
        for role in roles:
            expected.add(f"REVOKE ALL PRIVILEGES ON TABLE {table.name} FROM {role}")
    assert set(statements[1:]) == expected
    assert len(statements) == 1 + 6 * (2 + len(roles))
    assert not any("FORCE ROW" in command or "GRANT " in command or "ALTER DEFAULT PRIVILEGES" in command
                   for command in statements)


def test_schema_and_security_migrate_in_one_transaction_and_fail_closed(monkeypatch):
    events = []
    class Transaction:
        def __enter__(self):
            events.append("begin")
            return "connection"
        def __exit__(self, kind, *_):
            events.append("rollback" if kind else "commit")
    class Engine:
        def begin(self):
            return Transaction()
    monkeypatch.setattr(schema.metadata, "create_all", lambda conn: events.append("create:" + conn))
    def deny_security(conn):
        events.append("secure:" + conn)
        raise RuntimeError("cannot revoke browser grants")
    monkeypatch.setattr(schema, "secure_postgresql_tables", deny_security)
    service = VaultService(Engine(), None, None)
    with pytest.raises(RuntimeError, match="revoke"):
        service.init_schema()
    assert events == ["begin", "create:connection", "secure:connection", "rollback"]


def test_unknown_id_arbitrary_url_and_public_registration_cannot_fetch(client, vault):
    headers = acknowledge(client)
    assert client.get("/api/filings/https://127.0.0.1/secret/document", headers=headers).status_code == 404
    assert client.post("/api/filings", json={"document_url": "https://127.0.0.1/"}, headers=headers).status_code == 405
    assert vault[1].metadata_calls == vault[1].document_calls == 0


def test_exact_id_with_slashes_is_supported_without_path_storage(client, vault):
    service, _, _, _ = vault
    filing_id = "house:https://source.example/report/id"
    service.register_filing(record(filing_id))
    headers = acknowledge(client)
    response = client.get("/api/filings/house:https:%2F%2Fsource.example%2Freport%2Fid/document", headers=headers)
    assert response.status_code == 200 and response.data == PDF_A


def test_api_metadata_official_source_filters_pagination_and_refresh(client, vault):
    service, provider, _, _ = vault
    service.register_filing(record("house:second", filer_name="Second TEST Official"))
    response = client.get("/api/filings?limit=1&search=TEST").get_json()
    assert response["total"] == 2 and len(response["filings"]) == 1
    assert client.get("/api/filings?limit=not-a-number").status_code == 400
    assert client.get("/api/filings/" + record()["filing_id"] + "/official-source").get_json()["official_source_url"] == URL
    headers = acknowledge(client)
    response = client.post("/api/filings/" + record()["filing_id"] + "/refresh", json={}, headers=headers)
    assert response.status_code == 200 and response.get_json()["filing"]["sha256"]
    provider.failure = outage()
    response = client.post("/api/filings/" + record()["filing_id"] + "/refresh", json={}, headers=headers)
    assert response.status_code == 200 and "temporarily unavailable" in response.get_json()["warning"]


def test_refresh_rate_is_bounded(client):
    headers = acknowledge(client)
    path = "/api/filings/" + record()["filing_id"] + "/refresh"
    for _ in range(6):
        assert client.post(path, json={}, headers=headers).status_code == 200
    response = client.post(path, json={}, headers=headers)
    assert response.status_code == 429 and response.get_json()["code"] == "RATE_LIMITED"


@pytest.mark.parametrize("key", ["../secret", "filings/../secret.pdf", "filings/a/../../x", "filings/a\\x.pdf", "/filings/x.pdf", "filings/a//x.pdf"])
def test_storage_paths_reject_traversal(vault, key):
    with pytest.raises(StorageError):
        vault[3].put(key, PDF_A, "application/pdf")


def test_filesystem_backend_rejects_repository_storage(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    (root / ".git").mkdir()
    with pytest.raises(ValueError, match="Git checkouts"):
        FileObjectStore(root / "cache")


def test_factory_refuses_insecure_or_unconfigured_runtime():
    with pytest.raises(ValueError, match="VAULT_DATABASE_URL"):
        create_vault_app({"VAULT_SECRET_KEY": "x" * 32})
    with pytest.raises(ValueError, match="SQLite"):
        create_vault_app({"VAULT_DATABASE_URL": "sqlite://", "VAULT_SECRET_KEY": "x" * 32})


def test_supabase_store_refuses_public_bucket():
    class Response:
        status_code = 200
        def json(self):
            return {"public": True}
        def close(self):
            pass
    class Session:
        def request(self, *_, **kwargs):
            assert kwargs["allow_redirects"] is False
            return Response()
    with pytest.raises(StorageError, match="private"):
        SupabaseObjectStore("https://project.supabase.co", "server-test-key", "vault", session=Session())
