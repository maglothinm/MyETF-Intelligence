from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from scripts.collector_freshness import FRESHNESS_POLICY, overall_status
from scripts.dashboard_insights import build_insights, source_data_through


AS_OF = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def stamp(minutes_ago=0):
    return (AS_OF - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")


def run(branch="legislative", minutes_ago=10, **values):
    return {
        "branch": branch, "run_key": f"{branch}-{minutes_ago}:1",
        "started_utc": stamp(minutes_ago + 2), "finished_utc": stamp(minutes_ago),
        "success": True, "errors": [], "event_name": "schedule",
        "run_url": "https://github.com/example/PolitiTrack/actions/runs/42", **values,
    }


def payload(**values):
    return {"summary": {"generated_utc": stamp()}, "runs": [], "ai_runs": [], **values}


def branches(model):
    return {row["branch"]: row for row in model["health"]["branches"]}


@pytest.fixture(autouse=True)
def avoid_git_lookup(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)


@pytest.mark.parametrize(("branch", "age", "expected"), [
    ("legislative", 10, "success"), ("legislative", 29, "success"),
    ("legislative", 30, "success"), ("legislative", 30.01, "stale"),
    ("legislative", 70, "stale"), ("executive", 45, "success"),
    ("executive", 60, "success"), ("executive", 60.01, "stale"),
    ("ai", 75, "success"), ("ai", 75.01, "stale"),
])
def test_fixed_completion_age_enforces_each_branch_policy(branch, age, expected):
    source = payload(**{("ai_runs" if branch == "ai" else "runs"): [run(branch, age)]})
    before = copy.deepcopy(source)
    model = build_insights(source, as_of=AS_OF)
    row = branches(model)[branch]
    assert row["status"] == expected
    assert row["latest_run_success"] is True
    assert row["fresh"] is (expected == "success")
    assert row["age_minutes"] == age
    assert row["expected_interval_minutes"] == FRESHNESS_POLICY[branch]["expected_interval_minutes"]
    assert row["stale_after_minutes"] == FRESHNESS_POLICY[branch]["stale_after_minutes"]
    assert row["timeline"][0]["status"] == "success"  # No fake failed/missed run.
    assert source == before


def test_elapsed_fields_use_collector_start_and_successful_completion_in_utc():
    model = build_insights(payload(runs=[run(minutes_ago=70, trigger_source="external_scheduler")]), as_of=AS_OF)
    row = branches(model)["legislative"]
    assert row["last_attempt_utc"] == "2026-08-31T10:48:00Z"
    assert row["last_attempt_timestamp_kind"] == "collector_start"
    assert row["last_success_utc"] == "2026-08-31T10:50:00Z"
    assert row["next_expected_utc"] == "2026-08-31T11:05:00Z"
    assert row["overdue_minutes"] == 55
    assert row["age_minutes"] == 70
    assert row["estimated_missed_intervals"] == 3
    assert row["trigger_source"] == "external_scheduler"
    assert model["health"]["as_of_utc"] == stamp()


@pytest.mark.parametrize("recent_success", [False, True])
def test_latest_failure_outranks_even_a_recent_previous_success(recent_success):
    history = [run(minutes_ago=5, success=False, errors=["Source unavailable"])]
    if recent_success:
        history.append(run(minutes_ago=10))
    row = branches(build_insights(payload(runs=history), as_of=AS_OF))["legislative"]
    assert row["status"] == "failure"
    assert row["latest_run_success"] is False
    assert row["last_attempt_utc"] == stamp(7)
    assert row["last_success_utc"] == (stamp(10) if recent_success else None)
    assert row["fresh"] is (True if recent_success else None)
    assert row["error_count"] == 1
    assert row["latest_conclusion"] == "failure"


def test_qualifying_errors_override_success_boolean_and_no_previous_success_is_invented():
    row = branches(build_insights(payload(runs=[run(errors=["Discovery incomplete"])]), as_of=AS_OF))["legislative"]
    assert row["status"] == "failure"
    assert row["last_success_utc"] is None


def test_missing_evidence_is_unknown_with_policy_but_no_invented_timestamps():
    model = build_insights(payload(), as_of=AS_OF)
    assert model["health"]["status"] == "unknown"
    for row in model["health"]["branches"]:
        assert row["status"] == "unknown"
        for key in ("last_attempt_utc", "last_success_utc", "age_minutes", "next_expected_utc", "overdue_minutes", "latest_run_success", "fresh", "estimated_missed_intervals"):
            assert row[key] is None


@pytest.mark.parametrize(("legislative", "executive", "ai", "expected"), [
    (run(), run("executive", 70), run("ai"), "stale"),
    (run(), run("executive"), run("ai"), "success"),
    (run(success=False), run("executive", 70), run("ai"), "failure"),
    (run(minutes_ago=70), run("executive"), run("ai", 1), "stale"),
])
def test_overall_precedence_and_fresh_ai_cannot_mask_old_inputs(legislative, executive, ai, expected):
    model = build_insights(payload(runs=[legislative, executive], ai_runs=[ai]), as_of=AS_OF)
    assert model["health"]["status"] == expected


def test_republication_and_ai_updates_do_not_refresh_sources_or_collector_health():
    source = payload(runs=[run(minutes_ago=70)], ai_runs=[run("ai", 1)],
                     analyses=[{"analyzed_at_utc": stamp(1)}], portfolio=[{"last_updated_utc": stamp()}])
    old = build_insights(source, as_of=AS_OF)
    source["summary"]["generated_utc"] = stamp(-60)
    new = build_insights(source, as_of=AS_OF + timedelta(hours=1))
    assert old["health"]["status"] == new["health"]["status"] == "stale"
    assert old["data_through_utc"] == new["data_through_utc"] == stamp(70)
    assert old["generated_utc"] != new["generated_utc"]


@pytest.mark.parametrize("marker", [
    {"is_synthetic_test": True}, {"test_metadata": {"scenario": "acceptance"}},
    {"run_key": "TEST:fixture"}, {"is_temporary": True}, {"is_simulation": True},
    {"simulation_id": "sim:one"}, {"mode": "simulation"}, {"event_name": "manual_test"},
    {"trigger_source": "manual_test"}, {"workflow_file": "manual_test.yml"},
    {"workflow_file": "filing_simulation.yml"}, {"workflow_name": "Run Simulation"},
    {"workflow_file": "publish_trade_dashboard.yml"}, {"workflow_name": "Publish trade dashboard"},
    {"event_name": "publication"}, {"event_name": "local"},
])
def test_nonproduction_and_publication_success_cannot_refresh_production(marker):
    source = payload(runs=[run(minutes_ago=70), run(minutes_ago=1, **marker)])
    model = build_insights(source, as_of=AS_OF)
    row = branches(model)["legislative"]
    assert row["status"] == "stale"
    assert row["last_success_utc"] == model["data_through_utc"] == stamp(70)
    assert len(row["timeline"]) == 1


def test_synthetic_source_ancestry_and_future_times_do_not_move_source_currency():
    source = payload(
        filings=[{"filing_key": "real", "updated_at_utc": stamp(70)},
                 {"filing_key": "TEST:one", "source": "house", "report_id": "one", "updated_at_utc": stamp(2)},
                 {"filing_key": "future", "updated_at_utc": stamp(-1)}],
        transactions=[{"filing_key": "TEST:one", "observed_at_utc": stamp(1)}],
        reviews=[{"source": "house", "report_id": "one", "observed_at_utc": stamp()}],
        simulation={"as_of_utc": stamp()},
    )
    assert source_data_through(source, as_of=AS_OF) == stamp(70)
    assert source_data_through(payload(), as_of=AS_OF) is None


@pytest.mark.parametrize("values", [
    {"finished_utc": None}, {"finished_utc": "invalid"}, {"finished_utc": stamp(-5)},
    {"enabled": False},
])
def test_missing_future_or_disabled_completion_never_proves_current_success(values):
    row = branches(build_insights(payload(ai_runs=[run("ai", **values)]), as_of=AS_OF))["ai"]
    assert row["status"] == "unknown"
    assert row["last_success_utc"] is None


def observation(*attempts, available=True):
    return {"schema_version": 1, "observed_at_utc": stamp(), "available": available,
            "branches": {"legislative": {"available": available, "attempts": list(attempts)}}}


def action_attempt(**values):
    return {**run(minutes_ago=5), "started_utc": None, "workflow_started_utc": stamp(7),
            "evidence_source": "github_actions", "conclusion": "failure", "success": False,
            "error_count": 1, **values}


def test_failed_actions_attempt_is_visible_without_mutating_successful_artifact_history():
    source = payload(runs=[run()], workflow_evidence=observation(action_attempt()))
    before = copy.deepcopy(source)
    row = branches(build_insights(source, as_of=AS_OF))["legislative"]
    assert row["status"] == "failure"
    assert row["last_success_utc"] == stamp(10)
    assert row["last_attempt_utc"] == stamp(7)
    assert row["last_attempt_timestamp_kind"] == "workflow_start"
    assert row["error_count"] == 1
    assert len(row["timeline"]) == 2
    assert source == before


def test_actions_success_without_retained_state_never_advances_source_or_success_time():
    source = payload(runs=[run(minutes_ago=70)], workflow_evidence=observation(
        action_attempt(success=True, conclusion="success", error_count=0)))
    model = build_insights(source, as_of=AS_OF)
    row = branches(model)["legislative"]
    assert row["status"] == "stale"
    assert row["latest_run_success"] is None
    assert row["last_success_utc"] == model["data_through_utc"] == stamp(70)


def test_same_actions_attempt_keeps_collector_timestamp_and_coarse_external_trigger():
    retained = run(trigger_source="external_scheduler")
    source = payload(runs=[retained], workflow_evidence=observation(action_attempt(
        run_key=retained["run_key"], success=True, conclusion="success", error_count=0)))
    row = branches(build_insights(source, as_of=AS_OF))["legislative"]
    assert row["status"] == "success"
    assert row["last_success_utc"] == stamp(10)
    assert row["trigger_source"] == "external_scheduler"
    assert len(row["timeline"]) == 1


def test_in_progress_attempt_reports_attempt_without_cancelling_recent_success():
    row = branches(build_insights(payload(runs=[run()], workflow_evidence=observation(action_attempt(
        success=None, conclusion="in_progress", error_count=0, finished_utc=None))), as_of=AS_OF))["legislative"]
    assert row["status"] == "success"
    assert row["attempt_conclusion"] == "in_progress"
    assert row["last_attempt_utc"] == stamp(7)


def test_active_attempt_does_not_move_existing_failure_incident_to_wrong_run():
    failed = run(minutes_ago=10, success=False)
    active = action_attempt(success=None, conclusion="in_progress", error_count=0, finished_utc=None,
                            run_url="https://github.com/example/PolitiTrack/actions/runs/43")
    model = build_insights(payload(runs=[failed], workflow_evidence=observation(active)), as_of=AS_OF)
    incident = model["notifications"]["current_incidents"][0]
    assert incident["id"] == "failure:legislative:" + failed["run_key"]
    assert incident["url"] == failed["run_url"]
    assert incident["since"] == failed["finished_utc"]


@pytest.mark.parametrize(("age", "success", "expected"), [(10, True, "unknown"), (70, True, "stale"), (10, False, "failure")])
def test_actions_observation_outage_does_not_claim_green_or_hide_stronger_evidence(age, success, expected):
    row = branches(build_insights(payload(runs=[run(minutes_ago=age, success=success)],
                                         workflow_evidence=observation(available=False)), as_of=AS_OF))["legislative"]
    assert row["status"] == expected
    assert row["workflow_evidence_available"] is False


def test_utc_offsets_and_fractional_seconds_order_attempts_by_real_time():
    rows = [run(minutes_ago=10, run_key="later:1", started_utc="2026-08-31T07:48:00.5-04:00", finished_utc="2026-08-31T07:50:00.5-04:00"),
            run(minutes_ago=10, run_key="earlier:1", started_utc="2026-08-31T11:48:00Z", finished_utc="2026-08-31T11:50:00Z", success=False)]
    row = branches(build_insights(payload(runs=rows), as_of=AS_OF))["legislative"]
    assert row["status"] == "success"
    assert row["last_success_utc"] == "2026-08-31T11:50:00.500000Z"
    assert row["timeline"][0]["id"] == "legislative:later:1"


@pytest.mark.parametrize("values", [
    {"conclusion": "unrecognized"}, {"conclusion": "cancelled"},
    {"finished_utc": stamp(-1)}, {"finished_utc": None}, {"enabled": False},
])
def test_unknown_or_invalid_newest_completion_cannot_borrow_previous_green_success(values):
    source = payload(ai_runs=[run("ai", 5, **values), run("ai", 10)])
    row = branches(build_insights(source, as_of=AS_OF))["ai"]
    assert row["status"] == "unknown"
    assert row["fresh"] is True
    assert row["evidence_incomplete"] is True
    assert row["last_success_utc"] == stamp(10)


def test_overall_helper_requires_all_required_workers():
    assert overall_status([{"branch": "legislative", "status": "success"}]) == "unknown"
    assert overall_status([{"branch": "executive", "status": "stale"}]) == "stale"


def test_queued_workflow_is_visible_but_does_not_fabricate_attempt_start():
    source = payload(runs=[run()], workflow_evidence=observation(action_attempt(
        success=None, conclusion="queued", error_count=0, finished_utc=None,
        workflow_started_utc=None, workflow_created_utc=stamp(1))))
    row = branches(build_insights(source, as_of=AS_OF))["legislative"]
    assert row["status"] == "success"
    assert row["attempt_conclusion"] == "queued"
    assert row["last_attempt_utc"] == stamp(12)
    assert row["last_attempt_timestamp_kind"] == "collector_start"
    assert row["timeline"][0]["workflow_started_utc"] is None


def test_builder_summary_and_insights_share_source_time_without_generation_fallback(monkeypatch):
    from scripts.build_trade_dashboard import build_payload

    monkeypatch.setattr("scripts.build_trade_dashboard.utc_now_iso", lambda: stamp())
    empty = {"filings": [], "transactions": [], "reviews": [], "runs": [], "state": {}}
    empty_payload = build_payload(empty, empty, repository_url="https://github.com/example/PolitiTrack")
    assert empty_payload["summary"]["data_through_utc"] is None
    assert build_insights(empty_payload, as_of=AS_OF)["data_through_utc"] is None
    filled = {**empty, "runs": [run(minutes_ago=70), run(minutes_ago=1, is_synthetic_test=True)]}
    built = build_payload(filled, empty, repository_url="https://github.com/example/PolitiTrack",
                          ai={"runs": [run("ai", 1)], "state": {}, "analyses": [], "portfolio": []})
    assert built["summary"]["data_through_utc"] == stamp(70)
    assert build_insights(built, as_of=AS_OF)["data_through_utc"] == stamp(70)
