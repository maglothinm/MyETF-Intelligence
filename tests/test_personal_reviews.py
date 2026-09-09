"""Personal state persists independently of browsers and producer publications."""
import json
import os
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import create_engine, event, select, text

from runtime_v2.review_accounts import (PersonalReviewStore, ReviewError, accounts,
    acknowledgements, digest, events, metadata, sessions)
from runtime_v2.review_api import COOKIE, create_blueprint

PASSWORD = "test-only long review passphrase"
REVIEW = "review:retained-one"
IDENTITY = "review-logical-v1:" + "a" * 32
SECOND_IDENTITY = "review-logical-v1:" + "b" * 32
NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
ORIGIN = "https://dashboard.test"
HEADERS = {"Origin": ORIGIN, "X-PolitiTrack-Review-Request": "1"}


@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path):
    cleanup = lambda: None
    if request.param == "postgres":
        if os.environ.get("RUNTIME_V2_TEST_POSTGRES") != "1":
            pytest.skip("PostgreSQL integration service is not enabled")
        url = "postgresql+pg8000://postgres:runtime-v2-test@127.0.0.1:5432/postgres"
        admin = create_engine(url)
        schema = "personal_reviews_test_" + uuid.uuid4().hex
        with admin.begin() as conn:
            conn.execute(text('CREATE SCHEMA "' + schema + '"'))
        engine = create_engine(url)
        @event.listens_for(engine, "connect")
        def search_path(conn, _):
            cursor = conn.cursor()
            cursor.execute('SET search_path TO "' + schema + '"')
            cursor.close()
            conn.commit()
        def cleanup():
            with admin.begin() as conn:
                conn.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
            admin.dispose()
    else:
        engine = create_engine("sqlite:///" + str(tmp_path / "review-test.db"))
    result = PersonalReviewStore(engine, clock=lambda: NOW)
    result.initialize_schema()
    yield result
    engine.dispose()
    cleanup()


def invited(store, name="alice"):
    token = secrets.token_urlsafe(32)
    account = store.invite(name, digest(token))
    return account, token


def member(store, name="alice"):
    account, activation = invited(store, name)
    session = store.activate(activation, PASSWORD)
    return account, session


def save(store, account, acknowledged=True, revision=0, identity=IDENTITY, request_id=None):
    return store.set_acknowledged(account["account_id"], REVIEW, identity, acknowledged,
                                  revision, request_id or str(uuid.uuid4()))


def test_personal_state_survives_session_loss_restart_and_another_account(store):
    alice, token = member(store)
    bob, _ = member(store, "bob")
    save(store, alice)
    store.logout(token)
    assert store.account_for_session(token) is None
    restarted = PersonalReviewStore(store.engine, clock=lambda: NOW)
    signed_in = restarted.account_for_session(restarted.login("ALICE", PASSWORD))
    assert signed_in["account_id"] == alice["account_id"]
    assert restarted.read(alice["account_id"])["acknowledged"][0]["logical_review_id"] == IDENTITY
    assert restarted.read(bob["account_id"])["acknowledged"] == []


def test_recovery_preserves_timestamps_aliases_and_restore_tombstones(store):
    alice, _ = member(store)
    original = [{"id": REVIEW, "logical_review_id": IDENTITY, "acknowledged_at_utc": "2026-09-08T16:06:48.338Z"}]
    result = store.import_legacy(alice["account_id"], original, {REVIEW: IDENTITY}, source="owner_recovery")
    assert result["imported"] == 1
    assert result["acknowledged"][0]["acknowledged_at_utc"] == original[0]["acknowledged_at_utc"]
    assert store.import_legacy(alice["account_id"], original, {REVIEW: IDENTITY})["imported"] == 0
    restored = save(store, alice, False, result["revision"])
    assert restored["acknowledged"] == []
    original[0]["id"] = "new-evidence-alias"
    again = store.import_legacy(alice["account_id"], original, {"new-evidence-alias": IDENTITY})
    assert again["imported"] == 0
    assert again["acknowledged"] == []
    with store.engine.connect() as conn:
        retained = conn.execute(select(acknowledgements)).mappings().one()
        assert retained["acknowledged"] is False
        assert len(conn.execute(select(events)).all()) == 2


def test_missing_publication_does_not_mutate_saved_state_and_new_identity_is_distinct(store):
    alice, _ = member(store)
    first = save(store, alice)
    assert store.import_legacy(alice["account_id"], [], {})["acknowledged"] == first["acknowledged"]
    assert store.read(alice["account_id"])["acknowledged"] == first["acknowledged"]
    second = save(store, alice, revision=1, identity=SECOND_IDENTITY)
    assert {r["logical_review_id"] for r in second["acknowledged"]} == {IDENTITY, SECOND_IDENTITY}


def test_idempotency_and_stale_tabs_do_not_overwrite_other_changes(store):
    alice, _ = member(store)
    request_id = str(uuid.uuid4())
    first = save(store, alice, request_id=request_id)
    assert save(store, alice, request_id=request_id) == first
    with pytest.raises(ReviewError, match="another session"):
        save(store, alice, False, revision=0)
    with pytest.raises(ReviewError, match="different action"):
        save(store, alice, False, revision=1, request_id=request_id)
    assert store.read(alice["account_id"])["revision"] == 1


def test_failed_audit_insert_rolls_back_state_and_revision(store):
    alice, _ = member(store)
    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO runtime_review_events"):
            raise RuntimeError("injected audit failure")
    event.listen(store.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            save(store, alice)
    finally:
        event.remove(store.engine, "before_cursor_execute", fail)
    assert store.read(alice["account_id"])["revision"] == 0
    assert store.read(alice["account_id"])["acknowledged"] == []


def test_activation_is_single_use_and_credentials_are_not_stored_in_plaintext(store):
    alice, activation = invited(store)
    token = store.activate(activation, PASSWORD)
    with pytest.raises(ReviewError, match="invalid or expired"):
        store.activate(activation, PASSWORD)
    with store.engine.connect() as conn:
        account = conn.execute(select(accounts)).mappings().one()
        session = conn.execute(select(sessions)).mappings().one()
    assert account["password_hash"].startswith("scrypt:")
    assert PASSWORD not in account["password_hash"]
    assert account["invitation_hash"] is None
    assert session["token_hash"] == digest(token)
    assert token not in str(session)


def test_expired_sessions_invitations_and_disabled_accounts_fail_closed(store):
    alice, token = member(store)
    _, invitation = invited(store, "bob")
    store.clock = lambda: NOW + timedelta(days=31)
    assert store.account_for_session(token) is None
    with pytest.raises(ReviewError):
        store.activate(invitation, PASSWORD)
    store.clock = lambda: NOW
    store.disable("alice")
    assert store.account_for_session(token) is None
    with pytest.raises(ReviewError):
        store.login("alice", PASSWORD)


def test_recovery_rejects_wrong_identity_and_future_time(store):
    alice, _ = member(store)
    original = [{"id": REVIEW, "logical_review_id": SECOND_IDENTITY, "acknowledged_at_utc": "2026-09-08T00:00:00Z"}]
    with pytest.raises(ReviewError, match="does not match"):
        store.import_legacy(alice["account_id"], original, {REVIEW: IDENTITY})
    original[0].update(logical_review_id=IDENTITY, acknowledged_at_utc="2099-01-01T00:00:00Z")
    with pytest.raises(ReviewError, match="timestamp"):
        store.import_legacy(alice["account_id"], original, {REVIEW: IDENTITY})
    assert store.read(alice["account_id"])["revision"] == 0


def test_password_recovery_preserves_identity_and_reviews_and_revokes_old_sessions(store):
    alice, old_session = member(store)
    saved = save(store, alice)
    invitation = secrets.token_urlsafe(32)
    store.reset_invitation("alice", alice["account_id"], digest(invitation))
    new_session = store.activate(invitation, PASSWORD + " new")
    assert store.account_for_session(old_session) is None
    assert store.account_for_session(new_session)["account_id"] == alice["account_id"]
    assert store.read(alice["account_id"]) == saved
    with pytest.raises(ReviewError):
        store.login("alice", PASSWORD)


def app_for(store, tmp_path):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/dashboard-insights.json").write_text(json.dumps({"reviews": {
        "manual_exception": 1, "manual_exception_ids": [REVIEW], "manual_exception_identities": {REVIEW: IDENTITY}}}))
    app = Flask(__name__)
    app.config.update(TESTING=True, RUNTIME_PERSONAL_REVIEWS_ENABLED=True, RUNTIME_REVIEW_ORIGIN=ORIGIN)
    app.register_blueprint(create_blueprint(store, SimpleNamespace(refresh=lambda: tmp_path)))
    return app


def post(client, path, payload):
    return client.post("/api/reviews/" + path, json=payload, headers=HEADERS, base_url=ORIGIN)


def test_browser_clear_then_login_recovers_only_the_signed_in_person(store, tmp_path):
    alice, _ = member(store)
    bob, _ = member(store, "bob")
    save(store, alice)
    app = app_for(store, tmp_path)
    browser = app.test_client()
    assert browser.get("/api/reviews/session", base_url=ORIGIN).json == {"authenticated": False}
    signed_in = post(browser, "login", {"username": "alice", "password": PASSWORD})
    assert signed_in.status_code == 200
    assert len(signed_in.json["acknowledged"]) == 1
    cookie = signed_in.headers["Set-Cookie"]
    for flag in ("Secure", "HttpOnly", "SameSite=Strict", "Path=/"):
        assert flag in cookie
    assert "Domain=" not in cookie
    browser.delete_cookie(COOKIE, domain="dashboard.test")
    assert browser.get("/api/reviews/state", base_url=ORIGIN).status_code == 401
    fresh_browser = app_for(PersonalReviewStore(store.engine, clock=lambda: NOW), tmp_path).test_client()
    assert len(post(fresh_browser, "login", {"username": "alice", "password": PASSWORD}).json["acknowledged"]) == 1
    post(fresh_browser, "logout", {})
    other = post(fresh_browser, "login", {"username": "bob", "password": PASSWORD})
    assert other.json["account"]["id"] == bob["account_id"]
    assert other.json["acknowledged"] == []


def test_api_rejects_unauthorized_cross_origin_and_wrong_review_identity(store, tmp_path):
    alice, _ = member(store)
    client = app_for(store, tmp_path).test_client()
    payload = {"review_id": REVIEW, "logical_review_id": IDENTITY, "acknowledged": True,
               "expected_revision": 0, "request_id": str(uuid.uuid4()), "expected_account_id":alice["account_id"]}
    assert post(client, "acknowledgements", payload).status_code == 401
    assert client.post("/api/reviews/login", json={"username":"alice","password":PASSWORD}, base_url=ORIGIN).status_code == 403
    post(client, "login", {"username": "alice", "password": PASSWORD})
    wrong = client.post("/api/reviews/acknowledgements", json=payload,
        headers={**HEADERS,"Origin":"https://other.test"}, base_url=ORIGIN)
    assert wrong.status_code == 403
    assert post(client, "acknowledgements", {**payload,"logical_review_id":SECOND_IDENTITY}).status_code == 409
    assert post(client, "acknowledgements", {**payload,"expected_account_id":str(uuid.uuid4())}).json["code"] == "ACCOUNT_CHANGED"
    result = post(client, "acknowledgements", payload)
    assert result.status_code == 200
    assert result.headers["Cache-Control"].startswith("private, no-store")
    assert result.headers["Vary"] == "Cookie"
    assert store.read(alice["account_id"])["revision"] == 1


def test_schema_is_additive_and_no_producer_tables_are_initialized(store):
    from sqlalchemy import inspect
    names = set(inspect(store.engine).get_table_names())
    assert names == set(metadata.tables)
    assert not names.intersection({"runtime_state_heads", "runtime_state_snapshots", "runtime_job_runs"})
    store.initialize_schema()
    assert set(inspect(store.engine).get_table_names()) == names


def test_postgres_serializes_two_concurrent_saves(store):
    if store.engine.dialect.name != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL")
    alice, _ = member(store)
    def attempt(identity):
        try:
            return save(store, alice, identity=identity)["revision"]
        except ReviewError as error:
            return error.code
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(attempt, [IDENTITY, SECOND_IDENTITY]))
    assert sorted(str(x) for x in results) == ["1", "REVIEW_CHANGED"]
    assert len(store.read(alice["account_id"])["acknowledged"]) == 1


def test_sign_in_limits_persist_across_instances_then_expire(store):
    member(store)
    restarted = PersonalReviewStore(store.engine, clock=lambda: NOW)
    for _ in range(12):
        with pytest.raises(ReviewError) as error:
            restarted.login("alice", "wrong password", remote="test-client")
        assert error.value.code == "SIGN_IN_FAILED"
    with pytest.raises(ReviewError) as error:
        store.login("alice", PASSWORD, remote="test-client")
    assert error.value.code == "SIGN_IN_LIMIT"
    store.clock = lambda: NOW + timedelta(minutes=16)
    assert store.account_for_session(store.login("alice", PASSWORD, remote="test-client"))


def test_api_limits_and_failures_never_expose_private_state(store, tmp_path):
    alice, _ = member(store)
    app = app_for(store, tmp_path)
    client = app.test_client()
    assert client.post("/api/reviews/login", data="{}", headers=HEADERS, base_url=ORIGIN).status_code == 415
    assert client.post("/api/reviews/login", data="{", content_type="application/json", headers=HEADERS, base_url=ORIGIN).status_code == 400
    assert post(client, "login", {"password":"x" * 17000}).status_code == 413
    app.config["RUNTIME_PERSONAL_REVIEWS_ENABLED"] = False
    disabled = client.get("/api/reviews/session", base_url=ORIGIN)
    assert disabled.status_code == 503
    assert "no-store" in disabled.headers["Cache-Control"]
    app.config["RUNTIME_PERSONAL_REVIEWS_ENABLED"] = True
    post(client, "login", {"username":"alice", "password":PASSWORD})
    def fail_read(_):
        raise RuntimeError("private database address and credentials")
    store.read = fail_read
    failed = client.get("/api/reviews/state", base_url=ORIGIN)
    assert failed.status_code == 503
    assert "private database" not in failed.text
    assert alice["account_id"] not in failed.text
    assert "no-store" in failed.headers["Cache-Control"]
