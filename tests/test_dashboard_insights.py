from __future__ import annotations

import copy
import json

import pytest

from scripts.dashboard_insights import (
    build_insights,
    optional_number,
    public_payload,
    review_category,
    review_rows,
    safe_url,
    source_filters,
)


def payload(**values):
    return {
        "summary": {"generated_utc": "2026-08-30T12:00:00Z", "repository_url": "https://github.com/example/PolitiTrack"},
        "filings": [], "transactions": [], "reviews": [], "analyses": [],
        "runs": [], "ai_runs": [], "portfolio": [], "simulation": {}, **values,
    }


def run(branch="legislative", *, key="42:1", success=True, **values):
    return {"branch": branch, "run_key": key, "success": success, "finished_utc": "2026-08-30T11:00:00Z",
            "run_url": "https://github.com/example/PolitiTrack/actions/runs/42", "errors": [],
            "new_filing_counts": {"house": 0, "senate": 0}, **values}


def signal(identifier="a:1", **values):
    return {"analysis_id": identifier, "trade_id": "t:" + identifier, "classification": "high_priority", "score": 84,
            "ticker": "EXM", "transaction_type": "Purchase", "transaction_date": "2026-08-20",
            "filed_date": "2026-08-25", "observed_at_utc": "2026-08-26T10:00:00Z", "analyzed_at_utc": "2026-08-27T09:00:00Z", **values}


def test_coverage_composition_and_review_categories_are_distinct_exact_populations(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    source = payload(
        filings=[
            {"filing_key": "f:1", "status": "cataloged", "source": "house", "report_id": "1"},
            {"filing_key": "f:2", "status": "processed", "source": "house", "report_id": "2"},
            {"filing_key": "f:3", "status": "review_required", "source": "oge", "report_id": "3", "access_mode": "request"},
            {"filing_key": "f:4", "status": "future_status"},
        ],
        transactions=[{"trade_id": str(index), "transaction_type": kind} for index, kind in enumerate(["Purchase", "Sale (Full)", "Sale (Partial)", "Exchange", "Other"])],
        reviews=[
            {"review_id": "r1", "source": "oge", "report_id": "3", "reason": "A filing needs review"},
            {"review_id": "r2", "source": "senate", "report_id": "2", "reason": "Paper filing requires manual review"},
            {"review_id": "r3", "reason": "Reason has not yet been categorized"},
        ],
        analyses=[signal(), signal("a:2", classification="archive")],
    )
    model = build_insights(source)
    assert model["build_sha"] == "a" * 40
    assert {key: model["coverage"][key] for key in ("cataloged_only", "processed", "review_required", "other_filings", "filings", "transactions", "analyses", "qualifying_signals")} == {
        "cataloged_only": 1, "processed": 1, "review_required": 1, "other_filings": 1, "filings": 4, "transactions": 5, "analyses": 2, "qualifying_signals": 1,
    }
    assert {key: model["composition"][key] for key in ("population", "purchases", "sales", "other")} == {"population": 5, "purchases": 1, "sales": 2, "other": 2}
    assert {key: model["reviews"][key] for key in ("access_required", "manual_exception", "other", "total")} == {"access_required": 1, "manual_exception": 1, "other": 1, "total": 3}
    assert model["reviews"]["latest"][0]["category"] == "manual_exception"
    assert "not a conversion funnel" in model["coverage"]["note"]
    assert "post-upgrade" in model["composition"]["note"]


@pytest.mark.parametrize(("row", "filing", "category"), [
    ({"reason": "OGE Form 278-T is listed, but access requires an OGE Form 201 request or no direct PDF was published"}, {}, "access_required"),
    ({"reason": "Manual review"}, {"access_mode": "request"}, "access_required"),
    ({"reason": "Unable to parse retained PDF"}, {}, "manual_exception"),
    ({"reason": "Manual review of paper filing"}, {}, "manual_exception"),
    ({"source": "senate", "reason": "Senate paper PTR is rendered as page images and exposes no direct PDF; manual review is required"}, {"access_mode": "direct"}, "manual_exception"),
    ({"reason": "Needs source clarification"}, {}, "other"),
    ({}, {}, "other"),
])
def test_real_review_reasons(row, filing, category):
    assert review_category(row, filing) == category


def test_complete_review_projection_inherits_metadata_and_preserves_retained_fields():
    source = payload(
        filings=[{"filing_key": "senate|senate:2026:exact-id", "source": "senate", "branch": "legislative",
                  "report_id": "senate:2026:exact-id", "status": "review_required", "filer": "Retained official",
                  "filed_date": "2026-08-29", "first_seen_utc": "2026-08-30T10:00:00Z",
                  "updated_at_utc": "2026-08-30T10:05:00Z", "access_mode": "direct",
                  "review_reason": "PDF parser requires manual review", "source_url": "https://example.test/official"}],
        reviews=[{"review_id": "review|senate:2026:exact-id", "source": "senate", "report_id": "senate:2026:exact-id",
                  "status": "pending", "review_status": "awaiting_operator", "observed_at_utc": "2026-08-30T10:01:00Z",
                  "title": "Original title", "extra_ledger_field": {"values": ["preserve"]}}],
    )
    before = copy.deepcopy(source)
    row = review_rows(source)[0]
    assert row["review_id"] == "review|senate:2026:exact-id"
    assert row["filing_key"] == "senate|senate:2026:exact-id"
    assert row["filing_available"] is True
    assert row["category"] == "manual_exception"
    assert row["filing_status"] == "review_required"
    assert row["status"] == "pending"
    assert row["review_status"] == "awaiting_operator"
    assert row["branch"] == "legislative"
    assert row["filer"] == "Retained official"
    assert row["title"] == "Original title"
    assert row["filed_date"] == "2026-08-29"
    assert row["observed_at_utc"] == "2026-08-30T10:01:00Z"
    assert row["first_seen_utc"] == "2026-08-30T10:00:00Z"
    assert row["updated_at_utc"] == "2026-08-30T10:05:00Z"
    assert row["reason"] == row["review_reason"] == "PDF parser requires manual review"
    assert row["source_url"] == "https://example.test/official"
    assert row["access_mode"] == "direct"
    assert row["is_synthetic_test"] is False
    assert row["extra_ledger_field"] == {"values": ["preserve"]}
    assert row is not source["reviews"][0]
    assert source == before
    assert review_rows({**source, "reviews": [row]}) == [row]


def test_review_projection_uses_exact_unique_identity_without_guessing_ids_or_timestamps():
    source = payload(
        filings=[
            {"filing_key": "different|encoding", "source": "senate", "report_id": "same-id", "review_reason": "manual parser error"},
            {"filing_key": "house|same-id", "source": "house", "report_id": "same-id", "access_mode": "request"},
            {"filing_key": "senate|same-id-near", "source": "senate", "report_id": "same-id-near", "review_reason": "manual parser error"},
            {"filing_key": "anonymous", "review_reason": "manual parser error"},
        ],
        reviews=[
            {"review_id": "exact", "source": "senate", "report_id": "same-id"},
            {"review_id": "key-only", "filing_key": "different|encoding"},
            {"review_id": "house", "source": "house", "report_id": "same-id"},
            {"review_id": "missing", "source": "senate", "report_id": "same"},
            {"review_id": "no-source", "report_id": "same-id"},
            {"review_id": "anonymous"},
            {"review_id": "contradiction", "filing_key": "different|encoding", "source": "house", "report_id": "same-id"},
            {"review_id": "unknown-key", "filing_key": "unretained-key", "source": "senate", "report_id": "same-id"},
        ],
    )
    rows = {row["review_id"]: row for row in review_rows(source)}
    assert rows["exact"]["filing_key"] == rows["key-only"]["filing_key"] == "different|encoding"
    assert rows["exact"]["category"] == rows["key-only"]["category"] == "manual_exception"
    assert rows["exact"]["filing_available"] is rows["key-only"]["filing_available"] is True
    assert rows["key-only"]["source"] == "senate"
    assert rows["key-only"]["report_id"] == "same-id"
    assert rows["house"]["category"] == "access_required"
    for name in ("missing", "no-source", "anonymous"):
        assert rows[name]["category"] == "other"
        assert rows[name]["filing_available"] is False
        assert "filing_key" not in rows[name]
    for name in ("contradiction", "unknown-key"):
        assert rows[name]["category"] == "other"
        assert rows[name]["filing_available"] is False
        assert "reason" not in rows[name]
    assert rows["contradiction"]["filing_key"] == "different|encoding"
    assert rows["unknown-key"]["filing_key"] == "unretained-key"
    for row in rows.values():
        assert "filing_status" not in row
        assert "observed_at_utc" not in row
        assert "filed_date" not in row


def test_ambiguous_review_filing_identity_requires_an_explicit_exact_key():
    source = payload(
        filings=[{"filing_key": "one", "source": "senate", "report_id": "same", "review_reason": "manual parser error"},
                 {"filing_key": "two", "source": "senate", "report_id": "same", "access_mode": "request"}],
        reviews=[{"review_id": "ambiguous", "source": "senate", "report_id": "same"},
                 {"review_id": "explicit", "filing_key": "one", "source": "senate", "report_id": "same"}],
    )
    ambiguous, explicit = review_rows(source)
    assert ambiguous["category"] == "other"
    assert ambiguous["filing_available"] is False
    assert "filing_key" not in ambiguous
    assert explicit["category"] == "manual_exception"
    assert explicit["filing_key"] == "one"
    assert explicit["filing_available"] is True


def test_review_projection_preserves_access_precedence_from_filing_and_own_review_reason():
    source = payload(
        filings=[{"filing_key": "oge:one", "source": "oge", "report_id": "one", "access_mode": "request",
                  "review_reason": "No direct PDF is available"}],
        reviews=[{"review_id": "request", "source": "oge", "report_id": "one", "reason": "Manual review requested"},
                 {"review_id": "own", "review_reason": "Unable to parse document"}],
    )
    request, own = review_rows(source)
    assert request["category"] == "access_required"
    assert request["reason"] == "Manual review requested"
    assert request["review_reason"] == "No direct PDF is available"
    assert own["category"] == "manual_exception"
    assert own["reason"] == "Unable to parse document"


@pytest.mark.parametrize("marker", [
    {"is_synthetic_test": True}, {"is_synthetic_test": "true"}, {"is_temporary": True},
    {"test_metadata": {"scenario": "acceptance"}}, {"filing_key": "TEST:fixture"},
])
def test_review_projection_inherits_synthetic_flags_and_overview_uses_same_exclusion(marker):
    filing = {"filing_key": "retained-test", "source": "senate", "report_id": "same",
              "review_reason": "Manual parser exception", **marker}
    source = payload(filings=[filing], reviews=[{"review_id": "linked", "source": "senate", "report_id": "same"},
                                              {"review_id": "keyed", "filing_key": filing["filing_key"]}])
    before = copy.deepcopy(source)
    rows = review_rows(source)
    model = build_insights(source)
    assert all(row["is_synthetic_test"] is True for row in rows)
    assert all(row["category"] == "manual_exception" for row in rows)
    assert model["reviews"]["manual_exception"] == model["reviews"]["total"] == 0
    assert model["reviews"]["latest"] == []
    assert model["synthetic"]["reviews"] == 2
    assert model["coverage"]["filings"] == 0
    assert source == before


def test_review_projection_reuses_trade_ancestry_and_false_flags_remain_production():
    source = payload(
        filings=[{"filing_key": "test", "source": "house", "report_id": "test", "is_synthetic_test": True}],
        transactions=[{"trade_id": "inherited-test", "source": "house", "report_id": "test"}],
        reviews=[{"review_id": "trade", "trade_id": "inherited-test", "reason": "Manual parser exception"},
                 {"review_id": "real", "is_synthetic_test": "false", "reason": "Manual parser exception"}],
    )
    rows = review_rows(source)
    assert [row["is_synthetic_test"] for row in rows] == [True, False]
    model = build_insights(source)
    assert model["synthetic"]["reviews"] == model["reviews"]["manual_exception"] == 1


def test_source_filters_include_supported_and_discovered_taxonomy_without_branch_inference():
    source = payload(
        filings=[{"source": "senate", "branch": "legislative"}, {"source": "oge", "branch": "executive"}],
        reviews=[{"source": "house", "branch": "legislative"}, {"source": "new_source", "branch": "judicial"}],
        transactions=[{"source": "transaction_source"}], analyses=[{"source": "analysis_source"}],
        portfolio=[{"source": "portfolio_source"}], runs=[{"source": "run_source"}], ai_runs=[{"branch": "ai"}],
        summary={"sources": {"catalog_source": {"source": "catalog_source"}}},
    )
    before = copy.deepcopy(source)
    choices = source_filters(source)
    by_value = {row["value"]: row for row in choices}
    assert by_value["branch:executive"] == {"value": "branch:executive", "label": "Executive", "field": "branch"}
    assert by_value["branch:legislative"] == {"value": "branch:legislative", "label": "Legislative", "field": "branch"}
    assert by_value["branch:judicial"]["field"] == "branch"
    assert "branch:ai" not in by_value
    assert by_value["oge"] == {"value": "oge", "label": "OGE", "field": "source"}
    assert by_value["house"]["label"] == "House"
    assert by_value["senate"]["label"] == "Senate"
    assert by_value["new_source"]["field"] == "source"
    assert {"transaction_source", "analysis_source", "portfolio_source", "run_source", "catalog_source"} <= by_value.keys()
    assert "executive" not in by_value and "legislative" not in by_value
    assert build_insights(source)["source_filters"] == choices
    assert source == before
    assert {row["value"] for row in source_filters(payload())} == {"branch:executive", "branch:legislative", "oge", "house", "senate"}


def test_synthetic_records_propagate_by_filing_and_trade_without_contaminating_production():
    source = payload(
        filings=[{"filing_key": "TEST:one", "source": "house", "report_id": "test1", "is_synthetic_test": True},
                 {"filing_key": "real", "source": "house", "report_id": "real", "is_synthetic_test": "false"}],
        transactions=[{"trade_id": "testtrade", "source": "house", "report_id": "test1"}, {"trade_id": "realtrade", "transaction_type": "Purchase"}],
        reviews=[{"review_id": "testreview", "source": "house", "report_id": "test1"}],
        analyses=[signal("a:test", trade_id="testtrade"), signal("a:real", trade_id="realtrade")],
        portfolio=[{"position_id": "testpos", "trade_id": "testtrade", "status": "open"}],
    )
    model = build_insights(source)
    assert model["synthetic"] == {"filings": 1, "transactions": 1, "reviews": 1, "analyses": 1}
    assert model["coverage"]["filings"] == model["coverage"]["transactions"] == model["coverage"]["analyses"] == 1
    assert [row["analysis_id"] for row in model["signals"]] == ["a:real"]
    assert len(model["notifications"]["trade_ids"]) == 1
    assert model["paper"]["open_positions"] == 0


def test_incomplete_synthetic_filing_does_not_mark_unrelated_anonymous_records_synthetic():
    model = build_insights(payload(filings=[{"is_synthetic_test": True}], analyses=[signal()]))
    assert model["coverage"]["qualifying_signals"] == 1


def test_only_qualifying_classifications_sorted_by_priority_score_then_analysis_date():
    model = build_insights(payload(analyses=[
        signal("archive", score=100, classification="archive", entry_plan={"entry_status": "review_now"}),
        signal("weak", score=100, classification="weak_signal"),
        signal("watch", score=99, classification="watchlist"),
        signal("old", score=80),
        signal("new", score=80, analyzed_at_utc="2026-08-28T09:00:00Z"),
        signal("first", score=90),
        signal("missing", score=None),
    ]))
    assert [row["analysis_id"] for row in model["signals"]] == ["first", "new", "old", "missing", "watch"]
    assert model["coverage"]["qualifying_signals"] == 5
    assert len(model["notifications"]["qualifying_signals"]) == 5


def test_dates_price_band_and_chase_ceiling_use_retained_evidence():
    result = build_insights(payload(analyses=[signal(
        market={"current_price": 101, "quote_timestamp_utc": "2026-08-27T08:30:00Z"},
        entry_plan={"entry_status": "review_now", "review_band_low": 99, "review_band_high": 102, "transaction_date_close": 100,
                    "maximum_chase_percent": 8, "signal_expires_utc": "2026-09-05T10:00:00Z"},
    )]))["signals"][0]
    assert result["transaction_date"] == "2026-08-20"
    assert result["filed_date"] == "2026-08-25"
    assert result["observed_at_utc"] == "2026-08-26T10:00:00Z"
    assert result["disclosure_lag_days"] == 6
    assert result["quote_timestamp_utc"] == "2026-08-27T08:30:00Z"
    assert result["chase_ceiling"] == 108
    assert result["price_band"] == {"low": 99, "high": 102, "current": 101, "chase_ceiling": 108, "minimum": 99, "maximum": 108}


@pytest.mark.parametrize("value", [None, "", "unavailable", "NaN", "Infinity", [], {}, True, False, float("nan"), float("inf")])
def test_malformed_optional_numbers_remain_unavailable(value):
    assert optional_number(value) is None
    model = build_insights(payload(analyses=[signal(score=value, market={"current_price": value}, entry_plan={"review_band_low": value, "review_band_high": value})]))
    row = model["signals"][0]
    assert row["score"] is row["final_score"] is row["current_price"] is row["price_band"] is None
    json.dumps(model, allow_nan=False)


def test_zero_is_a_valid_metric_but_never_a_valid_price_band():
    model = build_insights(payload(analyses=[signal(score=0, investor_edge_observation_count=0, market={"current_price": 0}, entry_plan={"review_band_low": 0, "review_band_high": 1})]))
    row = model["signals"][0]
    assert row["score"] == 0
    assert row["edge_observation_count"] == 0
    assert row["edge_score"] is None
    assert row["price_band"] is None


@pytest.mark.parametrize("entry", [
    {"review_band_low": 102, "review_band_high": 99},
    {"review_band_low": 99},
    {"review_band_low": 100, "review_band_high": 100},
])
def test_incomplete_reversed_or_zero_width_bands_are_not_drawn(entry):
    model = build_insights(payload(analyses=[signal(market={"current_price": 100}, entry_plan=entry)]))
    assert model["signals"][0]["price_band"] is None


def test_bearish_does_not_invent_a_bullish_chase_boundary():
    row = build_insights(payload(analyses=[signal(transaction_type="Sale (Full)", entry_plan={"transaction_date_close": 100, "maximum_chase_percent": 8})]))["signals"][0]
    assert row["direction"] == "bearish"
    assert row["chase_ceiling"] is None


def test_empty_missing_evidence_is_unknown_and_not_a_zero_valued_replay():
    model = build_insights(payload())
    assert model["health"]["status"] == "unknown"
    assert all(row["status"] == "unknown" and row["age_seconds"] is None for row in model["health"]["branches"])
    assert model["signals"] == []
    assert model["data_through_utc"] is None
    assert model["simulation"]["starting_value"] is None
    assert model["simulation"]["current_value"] is None
    assert model["simulation"]["change_usd"] is None
    assert model["paper"]["empty_note"] == "No open paper positions"


def test_run_health_uses_branch_evidence_with_failure_errors_age_and_no_invented_cadence():
    model = build_insights(payload(
        runs=[run(), run("executive", key="41:1", finished_utc="2026-08-29T10:00:00Z"),
              run("executive", success=False, errors=["Access failed"])],
        ai_runs=[run("ai", completed_count=0, errors=["Price provider failed"])],
    ))
    branches = {row["branch"]: row for row in model["health"]["branches"]}
    assert model["health"]["status"] == "failure"
    assert branches["legislative"]["status"] == "success"
    assert branches["legislative"]["new_record_count"] == 0
    assert branches["executive"]["last_success_utc"] == "2026-08-29T10:00:00Z"
    assert branches["ai"]["status"] == "failure"
    assert branches["ai"]["last_success_utc"] is None
    assert all(row["expected_cadence_seconds"] is None and row["age_seconds"] == 3600 for row in branches.values())
    assert {row["branch"] for row in model["notifications"]["current_incidents"]} == {"executive", "ai"}


def test_successful_later_run_preserves_failed_timeline_and_establishes_recovery_evidence():
    model = build_insights(payload(
        runs=[run(success=False, key="41:1", finished_utc="2026-08-30T10:00:00Z"), run(), run("executive")], ai_runs=[run("ai")],
    ))
    assert model["health"]["status"] == "success"
    assert model["notifications"]["current_incidents"] == []
    timeline = model["health"]["branches"][0]["timeline"]
    assert [row["status"] for row in timeline] == ["success", "failure"]
    assert timeline[0]["id"] != timeline[1]["id"]


def test_old_successful_run_is_old_not_unsupported_stale_failure():
    model = build_insights(payload(runs=[run(finished_utc="2024-01-01T00:00:00Z")]))
    branch = model["health"]["branches"][0]
    assert branch["age_seconds"] > 365 * 86400
    assert branch["status"] == "success"
    assert model["notifications"]["current_incidents"] == []


def test_replay_reports_investment_change_not_fraction_of_goal_and_no_persistent_history():
    model = build_insights(payload(simulation={
        "simulation_id": "sim:1", "status": "success", "as_of_utc": "2026-08-29T18:00:00Z",
        "objective": {"starting_capital_usd": 10000, "goal_value_usd": 20000, "goal_progress_percent": 51.25},
        "accounting": {"status": "priced", "portfolio_value_usd": 10250, "profit_loss_usd": 999, "return_percent": 99},
        "trade": {"ticker": "EXM"}, "analysis": {"score": 81, "classification": "high_priority"},
        "price_context": {"entry_price_timestamp_utc": "2026-08-28T10:00:00Z", "valuation_price_timestamp_utc": "2026-08-29T10:00:00Z"},
    }))
    replay = model["simulation"]
    assert replay["starting_value"] == 10000
    assert replay["current_value"] == 10250
    assert replay["change_usd"] == 250
    assert replay["change_percent"] == 2.5
    assert replay["remaining_to_goal"] == 9750
    assert "progress" not in json.dumps(replay)
    assert replay["persistent_history"] is False
    assert replay["history_note"] == "No persistent portfolio history yet."
    assert replay["entry_utc"] != replay["valuation_utc"]
    assert model["coverage"]["qualifying_signals"] == 0


def test_unpriced_replay_cash_does_not_claim_performance():
    replay = build_insights(payload(simulation={"status": "success", "accounting": {"status": "unpriced", "starting_cash_usd": 10000, "portfolio_value_usd": 10000, "profit_loss_usd": 0}}))["simulation"]
    assert replay["current_value"] == 10000
    assert replay["change_usd"] is None
    assert replay["change_percent"] is None
    assert replay["priced"] is False


def test_input_unchanged_in_memory_and_public_payload_removes_secrets_without_removing_benign_compatibility():
    source = payload(simulation={"notification": {"pushover": "not_requested", "email": "not_requested"}, "notification_status": "Pushover: not_requested; email: not_requested"})
    source["analyses"] = [signal(ai={"analysis_summary": "<script>alert('hello')</script>", "evidence_sources": [{"title": "<img onerror=attack()>", "url": "https://example.test/report"}]})]
    source["runs"] = [run(errors=["email person@example.test token=opaque-secret https://hc-ping.com/private-uuid sk-proj-123456789abcdefghijk"]) ]
    source["private_config"] = {"value": "cannot-publish"}
    source["summary"]["gmail_address"] = "private@example.test"
    before = copy.deepcopy(source)
    clean = public_payload(source)
    model = build_insights(clean)
    assert source == before
    serialized = json.dumps({"clean": clean, "model": model})
    for private in ("person@example.test", "private@example.test", "opaque-secret", "hc-ping.com", "private-uuid", "sk-proj-123456789abcdefghijk", "cannot-publish"):
        assert private not in serialized
    assert clean["simulation"] == source["simulation"]
    assert model["signals"][0]["why"] == "<script>alert('hello')</script>"
    assert model["signals"][0]["evidence"][0]["title"] == "<img onerror=attack()>"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,attack", "https://user:password@example.test/report", "https://example.test/?token=opaque", "https://hc-ping.com/abc", "https://healthchecks.io/ping/abc", "https://example.test/heartbeat/abc", "https://example.test/\nattack", "https://example.test/' onclick='attack"])
def test_unsafe_urls_are_never_public_links(url):
    assert safe_url(url) is None
    row = build_insights(payload(analyses=[signal(source_url=url, ai={"evidence_sources": [{"url": url}]})]))["signals"][0]
    assert row["source_url"] is None
    assert row["evidence"] == []


def test_notification_ids_are_complete_stable_and_signal_list_can_be_bounded():
    source = payload(filings=[{"filing_key": f"f:{index}"} for index in range(60)], analyses=[signal(f"a:{index}") for index in range(60)])
    first, second = build_insights(source), build_insights(source)
    assert first["notifications"] == second["notifications"]
    assert len(first["signals"]) == 48
    assert first["signals_truncated"] is True
    assert first["coverage"]["qualifying_signals"] == 60
    assert len(first["notifications"]["filing_ids"]) == 60
    assert len(first["notifications"]["analysis_ids"]) == 60
    assert len(first["notifications"]["qualifying_signals"]) == 60
    assert all(len(identifier) == 24 for identifier in first["notifications"]["filing_ids"])


def test_malformed_optional_nested_fields_do_not_break_model():
    model = build_insights(payload(
        analyses=[signal(market="missing", entry_plan=[], investor_edge="missing", ai={"evidence_sources": [None, "invalid"]}, analyzed_at_utc="wrong")],
        runs=[run(success="false", errors={"private": "unsupported"}, new_filing_counts={"house": "oops"})], simulation={"accounting": "missing"},
    ))
    assert model["signals"][0]["analyzed_at_utc"] is None
    assert model["signals"][0]["price_band"] is None
    assert model["health"]["branches"][0]["status"] == "failure"
    assert model["health"]["branches"][0]["new_record_count"] is None
    json.dumps(model, allow_nan=False)


def test_malformed_error_evidence_never_becomes_healthy():
    branch = build_insights(payload(runs=[run(errors=[{"message": "private provider response"}])]))["health"]["branches"][0]
    assert branch["status"] == "failure"
    assert branch["timeline"][0]["error_count"] == 1
    assert branch["errors"] == ["Retained run reports an error; details unavailable."]


def test_public_payload_never_exports_nested_notification_requests_or_opaque_credentials():
    source = payload(simulation={"notification": {"email": {"subject": "private subject", "body": "private body"}, "pushover": "not_requested", "request": {"message": "private message"}}})
    source["summary"]["customToken"] = "opaque-sensitive-value"
    source["summary"]["private_key"] = "opaque-private-value"
    clean = public_payload(source)
    assert clean["simulation"]["notification"] == {"pushover": "not_requested"}
    text = json.dumps(clean)
    assert "private subject" not in text
    assert "private body" not in text
    assert "private message" not in text
    assert "opaque-sensitive-value" not in text
    assert "opaque-private-value" not in text


def test_signal_preserves_existing_flattened_edge_evidence_and_exact_base_modifier():
    source = signal(
        base_score=82, final_score=87, investor_edge_modifier=5, investor_edge_status="scored",
        investor_edge_observation_count=8, investor_edge_relevant_alpha_label="20-session",
        investor_edge_relevant_followable_alpha=3.4, investor_edge_followable_alpha=2.7,
        investor_edge_hit_rate_percent=62.5, investor_edge_sector_alpha=-0.7,
    )
    before = copy.deepcopy(source)
    row = build_insights(payload(analyses=[source]))["signals"][0]
    assert row["base_score"] == 82
    assert row["final_score"] == 87
    assert row["edge_modifier"] == 5
    assert row["edge_relevant_alpha_label"] == "20-session"
    assert row["edge_followable_alpha"] == 3.4
    assert row["edge_hit_rate_percent"] == 62.5
    assert row["edge_sector_alpha"] == -0.7
    assert source == before


@pytest.mark.parametrize("status", [None, "", "insufficient_data", "insufficient_observations", "unavailable", "disabled", "error", "neutral", "missing"])
def test_missing_or_insufficient_edge_status_hides_numeric_outcomes_even_with_observations(status):
    row = build_insights(payload(analyses=[signal(
        investor_edge_status=status, investor_edge_observation_count=2, investor_edge_modifier=0,
        investor_edge_relevant_alpha_label="20-session", investor_edge_relevant_followable_alpha=8,
        investor_edge_followable_alpha=9, investor_edge_hit_rate_percent=100, investor_edge_sector_alpha=7,
    )]))["signals"][0]
    assert row["edge_observation_count"] == 2
    assert row["edge_modifier"] == 0
    assert row["edge_relevant_alpha_label"] == ""
    assert row["edge_followable_alpha"] is None
    assert row["edge_hit_rate_percent"] is None
    assert row["edge_sector_alpha"] is None


def test_missing_flattened_edge_outcomes_are_not_inferred_from_nested_profile_or_zero():
    row = build_insights(payload(analyses=[signal(
        investor_edge_status="scored", investor_edge_observation_count=8,
        investor_edge={"modifier": -3, "followable_alpha": 20, "weighted_followable_hit_rate_percent": 90},
    )]))["signals"][0]
    assert row["base_score"] is None
    assert row["edge_modifier"] == -3
    assert row["edge_followable_alpha"] is None
    assert row["edge_hit_rate_percent"] is None
    assert row["edge_sector_alpha"] is None


def test_flattened_weighted_alpha_fallback_never_borrows_a_different_horizon_label():
    row = build_insights(payload(analyses=[signal(
        investor_edge_status="scored", investor_edge_observation_count=8,
        investor_edge_relevant_alpha_label="20-session", investor_edge_relevant_followable_alpha="NaN",
        investor_edge_followable_alpha=0, investor_edge_hit_rate_percent=0, investor_edge_sector_alpha=0,
    )]))["signals"][0]
    assert row["edge_followable_alpha"] == 0
    assert row["edge_relevant_alpha_label"] == ""
    assert row["edge_hit_rate_percent"] == 0
    assert row["edge_sector_alpha"] == 0


def test_replay_notification_observation_time_stays_distinct_from_historical_cutoff():
    model = build_insights(payload(simulation={
        "simulation_id": "sim:historic", "status": "success", "as_of_utc": "2024-01-15T20:00:00Z",
    }))
    event = model["notifications"]["simulation_results"][0]
    assert event["timestamp"] == "2026-08-30T12:00:00Z"
    assert event["cutoff_utc"] == "2024-01-15T20:00:00Z"
    assert model["simulation"]["as_of_utc"] == "2024-01-15T20:00:00Z"
