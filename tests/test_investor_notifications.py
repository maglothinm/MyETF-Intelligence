from datetime import datetime, timezone
from dataclasses import replace
import json

import pytest

from scripts import investor_notifications as alerts
from scripts import runtime_notifications as outbox
from runtime_v2.notifications import configured_channels, send_notification


@pytest.fixture
def staged(monkeypatch, tmp_path):
    monkeypatch.setenv(outbox.MODE_KEY, outbox.CONTRACT)
    monkeypatch.setenv(outbox.NAMESPACE_KEY, "ai")
    path = tmp_path / "notification-intents.jsonl"
    monkeypatch.setenv(outbox.PATH_KEY, str(path))
    return path


def profile(score=61, **values):
    return {"edge_score": score, "filer": "Example Filer", "owner": "Spouse", "sample_count": 8,
            "minimum_sample_met": True, "profile_status": "complete", "as_of_date": "2026-09-10", **values}


def stage(tmp_path, profiles, **kwargs):
    return alerts.stage_profile_alerts(tmp_path, profiles, dashboard_url="https://dashboard.test", suppress_alerts=False,
                                      now=datetime(2026, 9, 10, 12, tzinfo=timezone.utc), **kwargs)


@pytest.mark.parametrize("score,expected", [(59.9, 0), (60.0, 0), (60.01, 1), (100, 1), (101, 0), (-1, 0), (None, 0), (float("nan"), 0), (True, 0)])
def test_strict_edge_threshold(staged, tmp_path, score, expected):
    assert stage(tmp_path, {"profile-1": profile(score)}) == expected
    rows = outbox.read_intents(staged, "ai")
    assert len(rows) == expected
    if rows:
        assert rows[0]["payload"]["recipient"] == "maglothinm@gmail.com"
        assert rows[0]["available_on"] == "2026-09-10"
        assert rows[0]["channel"] == "gmail"


def test_restart_crossing_and_missing_evidence_do_not_replay(staged, tmp_path):
    assert stage(tmp_path, {"person": profile(61)}) == 1
    first = outbox.read_intents(staged, "ai")[0]
    assert stage(tmp_path, {"person": profile(72)}) == 0
    assert stage(tmp_path, {}) == 0
    assert stage(tmp_path, {"person": profile(50, profile_status="stale_last_good")}) == 0
    assert stage(tmp_path, {"person": profile(72)}) == 0
    assert stage(tmp_path, {"person": profile(60)}) == 0
    assert stage(tmp_path, {"person": profile(60.1)}) == 1
    rows = outbox.read_intents(staged, "ai")
    assert len(rows) == 2 and rows[1]["delivery_id"] != first["delivery_id"]


def test_independent_owner_profiles_and_unusable_evidence(staged, tmp_path):
    assert stage(tmp_path, {"filer-self": profile(), "filer-spouse": profile(owner="Self"),
                            "insufficient": profile(99, minimum_sample_met=False),
                            "test:synthetic": profile(99), "synthetic": profile(99, is_synthetic_test=True)}) == 2


def test_missing_credentials_queues_and_suppressed_modes_do_not_write(staged, tmp_path, monkeypatch):
    assert configured_channels({}) == []
    assert stage(tmp_path, {"person": profile()}) == 1
    previous = (tmp_path / alerts.JOURNAL_FILE).read_bytes()
    monkeypatch.setenv(outbox.MODE_KEY, "disabled")
    assert stage(tmp_path, {"new": profile()}) == 0
    assert (tmp_path / alerts.JOURNAL_FILE).read_bytes() == previous
    assert alerts.stage_profile_alerts(tmp_path, {"new": profile()}, dashboard_url="", suppress_alerts=True) == 0


def test_invalid_history_is_not_reinitialized(staged, tmp_path):
    (tmp_path / alerts.JOURNAL_FILE).write_text('{"version":1,"profiles":{"person":{}}}')
    with pytest.raises(ValueError, match="history"):
        stage(tmp_path, {"person": profile()})
    assert not staged.exists()


def test_gmail_uses_intended_recipient_without_changing_sender(monkeypatch):
    messages = []
    class SMTP:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def login(self, sender, password): assert sender == "sender@example.test" and password == "test-only"
        def send_message(self, message): messages.append(message); return {}
    monkeypatch.setattr("runtime_v2.notifications.smtplib.SMTP_SSL", SMTP)
    payload = {"title": "Example", "message": "Research", "url": "", "url_title": "", "recipient": "maglothinm@gmail.com"}
    assert send_notification("gmail", payload, {"GMAIL_ADDRESS": "sender@example.test", "GMAIL_APP_PASSWORD": "test-only"})
    assert messages[0]["To"] == "maglothinm@gmail.com"
    assert messages[0]["From"] == "sender@example.test"
    with pytest.raises(ValueError):
        send_notification("gmail", {**payload, "recipient": "bad\nBcc: stolen@example.test"}, {"GMAIL_ADDRESS": "sender@example.test"})


def test_candidate_email_is_requested_without_credentials_and_stays_queued(staged, tmp_path):
    from test_ai_filing_analyst_hardened import _config
    from scripts import ai_filing_analyst_hardened as ai
    cfg = replace(_config(tmp_path), suppress_alerts=False, require_pushover=False, gmail_address="", gmail_app_password="")
    assert "gmail" in ai.legacy._requested_candidate_channels(cfg)
    delivery = {"analysis_id": "a", "trade_id": "t", "analysis_revision": 1, "filed_date": "2026-09-10",
                "requested_channels": ["gmail"], "alert": {"title": "Watchlist", "message": "Example"}}
    state = ai.legacy.AIState(candidate_alert_deliveries={"id": delivery})
    cfg.ai_dir.mkdir(parents=True)
    result = ai.AnalystRunResult(started_utc="2026-09-10T12:00:00Z")
    ai._deliver_pending_candidate_alerts(cfg, result, state, cfg.ai_dir / "state.json")
    rows = outbox.read_intents(staged, "ai")
    assert rows[0]["payload"]["recipient"] == "maglothinm@gmail.com"
    assert not delivery.get("delivered_channels")
    ai._deliver_pending_candidate_alerts(cfg, result, state, cfg.ai_dir / "state.json")
    assert outbox.read_intents(staged, "ai") == rows
