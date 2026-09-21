from datetime import datetime, timezone
import json

import pytest
from flask import Flask

from runtime_v2.local_host import ORIGIN, SCHEDULES, active, environment, latest_slot, load_config
from runtime_v2.local_origin import session_cookie, valid_origin
from runtime_v2.web import create_app
from tests.test_personal_reviews import store, member, app_for, PASSWORD


def config(tmp_path):
    return {"schema_version": 1, "root": str(tmp_path),
            "database_url": "postgresql://runtime:secret@127.0.0.1:54329/polititrack",
            "source_revision": "a" * 40, "tool_paths": [str(tmp_path / "tools")],
            "environments": {name: {} for name in [*SCHEDULES, "web"]}}


def test_schedule_coalesces_missed_intervals_without_replay():
    now = datetime(2026, 9, 21, 14, 36, tzinfo=timezone.utc)
    slot = latest_slot(now, *SCHEDULES["legislative"])
    assert datetime.fromtimestamp(slot * 60, timezone.utc).minute == 35
    assert latest_slot(now.replace(second=59), *SCHEDULES["legislative"]) == slot
    assert latest_slot(now.replace(hour=18), *SCHEDULES["legislative"]) - slot == 240


def test_local_runtime_refuses_cloud_database_and_inherited_secrets(tmp_path, monkeypatch):
    value = config(tmp_path)
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(value))
    assert load_config(path) == value
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "never-copy")
    monkeypatch.setenv("OPENAI_API_KEY", "never-inherit")
    monkeypatch.setenv("SYSTEMROOT", "windows-required")
    env = environment(value, "web")
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["SYSTEMROOT"] == "windows-required"
    assert env["ALLOW_STATE_INITIALIZATION"] == "false"
    value["database_url"] = value["database_url"].replace("127.0.0.1", "cloud.example")
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        load_config(path)


def test_no_writer_without_verified_cutover_receipt(tmp_path):
    value = config(tmp_path)
    assert not active(value)
    (tmp_path / "config").mkdir()
    receipt = tmp_path / "config/local-authority.json"
    data = {"repository_id": 1349678672, "authority": "beast_local",
            "cloud_writers_drained": True, "database_verified": False}
    receipt.write_text(json.dumps(data))
    assert not active(value)
    data["database_verified"] = True
    receipt.write_text(json.dumps(data))
    assert active(value)


@pytest.mark.parametrize("origin,host,remote,allowed", [
    (ORIGIN, ORIGIN, "127.0.0.1", True),
    (ORIGIN, "http://attacker.example:8765", "127.0.0.1", False),
    (ORIGIN, ORIGIN, "192.168.1.12", False),
    ("http://127.0.0.1:80", ORIGIN, "127.0.0.1", False),
    ("http://127.0.0.1:8765@attacker.example", ORIGIN, "127.0.0.1", False),
])
def test_local_origin_requires_exact_loopback(origin, host, remote, allowed):
    app = Flask(__name__)
    app.config["RUNTIME_LOCAL_ONLY"] = "true"
    with app.test_request_context(base_url=host, environ_overrides={"REMOTE_ADDR": remote}):
        assert valid_origin(origin) is allowed
        assert session_cookie() == "polititrack_local_session"


def test_cloud_origin_remains_https_only():
    app = Flask(__name__)
    with app.test_request_context(base_url="https://dashboard.test"):
        assert valid_origin("https://dashboard.test")
        assert not valid_origin(ORIGIN)
        assert session_cookie() == "__Host-polititrack-review-session"


def test_web_rejects_remote_clients_and_dns_rebinding_before_database_use():
    app = create_app({"TESTING": True, "RUNTIME_LOCAL_ONLY": "true"}, store=object())
    client = app.test_client()
    assert client.get("/healthz", base_url=ORIGIN).status_code == 200
    assert client.get("/healthz", base_url="http://attacker.example:8765").status_code == 403
    assert client.get("/healthz", base_url=ORIGIN,
                      environ_overrides={"REMOTE_ADDR": "10.0.0.1"}).status_code == 403


def test_local_login_and_logout_retain_account_identity(store, tmp_path):
    alice, _ = member(store)
    app = app_for(store, tmp_path)
    app.config.update(RUNTIME_LOCAL_ONLY="true", RUNTIME_REVIEW_ORIGIN=ORIGIN)
    client = app.test_client()
    headers = {"Origin": ORIGIN, "X-PolitiTrack-Review-Request": "1"}
    response = client.post("/api/reviews/login", base_url=ORIGIN, headers=headers,
                           json={"username": "alice", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json["account"]["id"] == alice["account_id"]
    assert "polititrack_local_session=" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Strict" in response.headers["Set-Cookie"]
    assert client.get("/api/reviews/session", base_url=ORIGIN).json["authenticated"]
    assert client.post("/api/reviews/logout", base_url=ORIGIN, headers=headers, json={}).status_code == 200
    assert not client.get("/api/reviews/session", base_url=ORIGIN).json["authenticated"]
