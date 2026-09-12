"""Offline progress, restart, publication and no-scoring-change regressions."""
from __future__ import annotations
import copy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import os
import shutil
import subprocess

import pytest
from bs4 import BeautifulSoup
from scripts import investor_edge as edge
from scripts import investor_edge_progress as progress

AS_OF = date(2026, 9, 11)
NOW = datetime(2026, 9, 11, 20, tzinfo=timezone.utc)


def rows(start=date(2026, 8, 1), end=AS_OF):
    result=[]
    while start <= end:
        if start.weekday() < 5:
            result.append({"date":start.isoformat(),"close":100.0})
        start += timedelta(days=1)
    return result


def trade(**changes):
    return {"trade_id":"one", "observation_key":"obs:one", "ticker":"AAA", "benchmark":"SPY", "eligible":True,
            "transaction_date":"2026-08-03", "followable_anchor_date":"2026-08-05",
            "picker_outcomes":{}, "followable_outcomes":{}, **changes}


def classify(item=None, cached=None, prices=None, **kwargs):
    prices = rows() if prices is None else prices
    def compute(t, field, h, stock, bench):
        anchor=progress.day(t["transaction_date" if field=="picker_outcomes" else "followable_anchor_date"])
        return edge._outcome_for_horizon(stock,bench,anchor,h,as_of=AS_OF) is not None
    return progress.inventory([{"filer":"TEST Investor", "owner":"Spouse", "trade_results":[item or trade()]}],
                              {"obs:one":cached or {}}, horizons=[5],as_of=AS_OF,
                              rows_for=lambda _:prices,computable=compute,**kwargs)


def category(work):
    return next(iter(work.values()))["category"]


def test_ready_requires_actual_computable_cached_prices():
    assert category(classify()) == "ready"
    assert category(classify(prices=[])) == "queued"
    assert category(classify(prices=[],market_configured=False)) == "blocked"


def test_daily_attempt_limit_is_not_mislabeled_running_or_ready():
    work=classify(cached={"last_attempted_as_of":"2026-09-11"})
    assert category(work)=="awaiting_retry"
    row=next(iter(work.values()))
    assert row["reason_code"]=="daily_attempt_limit"
    assert row["next_retry_at"]=="2026-09-12T00:00:00Z"


def test_provider_retry_backoff_keeps_its_real_date():
    work=classify(cached={"last_attempted_as_of":"2026-09-10","retry_after_as_of":"2026-09-14"})
    assert category(work)=="awaiting_retry"
    assert next(iter(work.values()))["next_retry_at"]=="2026-09-14T00:00:00Z"


def test_recent_purchase_waits_for_sessions_without_fake_finish_date():
    work=classify(trade(transaction_date="2026-09-10",followable_anchor_date="2026-09-12"),cached={"last_attempted_as_of":"2026-09-11"})
    assert category(work)=="awaiting_maturity"
    assert next(iter(work.values()))["next_retry_at"] is None


def test_old_trade_with_new_public_observation_still_has_immature_followable_outcome():
    picker=edge._outcome_for_horizon(rows(),rows(),date(2026,8,3),5,as_of=AS_OF)
    work=classify(trade(followable_anchor_date="2026-09-12",picker_outcomes={"5":picker}))
    assert category(work)=="awaiting_maturity"
    assert len(next(iter(work.values()))["completed_outcomes"])==1


def test_complete_and_future_outcome_visibility_are_distinct():
    item=trade(picker_outcomes={"5":{"exit_date":"2026-08-10"}},followable_outcomes={"5":{"exit_date":"2026-08-12"}})
    assert category(classify(item))=="completed"
    item["followable_outcomes"]["5"]["exit_date"]="2026-10-01"
    assert category(classify(item))=="ready"


def test_missing_or_stale_prices_are_not_called_immature():
    work=classify(trade(transaction_date="2026-09-10",followable_anchor_date="2026-09-11"),cached={"last_attempted_as_of":"2026-09-01"},prices=rows(end=date(2026,9,4)))
    assert category(work)=="missing_data"


def test_invalid_observation_remains_unknown():
    assert category(classify(trade(observation_key="")))=="unknown"


def work_fixture(ready=10,done=0,waiting=0):
    result={}
    for i in range(ready+done+waiting):
        state="completed" if i<done else "ready" if i<done+ready else "awaiting_maturity"
        result[str(i)]={"category":state,"reason_code":"complete" if state=="completed" else "cached_work_ready" if state=="ready" else "outcome_not_mature", "completed_outcomes":["picker_outcomes:5"] if state=="completed" else [],
                        "investor":"TEST", "owner":"Self", "ticker":"AAA", "trade_id":str(i),"profile_index":0,"next_retry_at":None,"missing_outcome_count":0 if state=="completed" else 1}
    return result


def publish(work,journal,now=NOW):
    return progress.report(work,journal,now=now,as_of=AS_OF,enabled=True,limit=30,stale_after_minutes=75)


def test_repeated_save_or_same_run_is_not_new_progress():
    w=work_fixture()
    a=progress.record_success({},w,w,method_hash="m",run_id="one",now=NOW,attempted=0)
    b=progress.record_success(a,w,w,method_hash="m",run_id="one",now=NOW+timedelta(minutes=30),attempted=0)
    assert a==b and len(b["events"])==1


def test_stalled_requires_ready_work_across_distinct_successful_passes():
    w=work_fixture(); journal={}
    for i in range(3):
        journal=progress.record_success(journal,w,w,method_hash="m",run_id=str(i),now=NOW+timedelta(minutes=30*i),attempted=0)
    report=publish(w,journal,NOW+timedelta(hours=1))
    assert report["status"]=="stalled" and report["eta"] is None
    wait=work_fixture(ready=0,waiting=10)
    journal=progress.record_success(journal,wait,wait,method_hash="m",run_id="wait",now=NOW+timedelta(hours=2),attempted=0)
    assert publish(wait,journal,NOW+timedelta(hours=2))["status"]=="awaiting_maturity"
    assert journal["events"][-1]["stalled_streak"]==0


def test_eta_uses_measured_ready_completions_not_attempts_or_future_horizons():
    journal={}; before=work_fixture(ready=100)
    for i in range(4):
        after=work_fixture(ready=100-10*i,done=10*i)
        journal=progress.record_success(journal,before,after,method_hash="m",run_id=str(i),now=NOW+timedelta(minutes=30*i),attempted=30)
        before=after
    result=publish(after,journal,NOW+timedelta(minutes=90))
    assert result["eta"]["lower_seconds"]==12600
    assert result["eta"]["upper_seconds"]==12600
    assert result["completed_in_last_run"]==10
    assert result["attempted_in_last_run"]==30
    assert publish(after,journal,NOW+timedelta(hours=4))["eta"] is None
    # No new outcomes; a recent zero-progress interval invalidates the estimate.
    journal=progress.record_success(journal,after,after,method_hash="m",run_id="idle",now=NOW+timedelta(hours=2),attempted=30)
    assert publish(after,journal,NOW+timedelta(hours=2))["eta"] is None


def test_population_pruning_or_method_change_is_not_completion():
    before=work_fixture(ready=10)
    journal=progress.record_success({},before,before,method_hash="m",run_id="one",now=NOW,attempted=0)
    after={k:v for k,v in before.items() if int(k)<5}
    journal=progress.record_success(journal,before,after,method_hash="m2",run_id="two",now=NOW+timedelta(minutes=30),attempted=0)
    assert len(journal["events"])==1
    assert journal["events"][-1]["completed_observations"]==0
    assert journal["last_advancement_at"] is None
    assert publish(after,journal,NOW+timedelta(minutes=30))["eta"] is None


def test_journal_is_bounded_and_clock_regression_cannot_advance_it():
    w=work_fixture(); journal={}
    for i in range(40):
        journal=progress.record_success(journal,w,w,method_hash="m",run_id=str(i),now=NOW+timedelta(minutes=i),attempted=0)
    assert len(journal["events"])==24
    assert progress.record_success(journal,w,w,method_hash="m",run_id="old",now=NOW,attempted=0)==journal


def test_unknown_legacy_telemetry_and_private_fields_never_become_completion():
    assert progress.public_report(None) is None
    assert progress.public_report({"schema_version":1,"counts":{"ready":0}}) is None
    payload=publish(work_fixture(),{})
    payload.update(api_key="never-export",private_details="private")
    clean=progress.public_report(payload)
    assert "api_key" not in clean and "private_details" not in clean
    payload["counts"]["ready"]=True
    assert progress.public_report(payload) is None


def test_zero_population_is_not_a_100_percent_success_claim():
    result=publish({}, {})
    assert result["status"]=="empty" and result["eta"] is None
    assert result["last_successful_run_at"] is None


class Provider:
    errors=[]
    network_requests=0
    def sector(self,ticker):
        return {"benchmark":"SPY"}
    def daily(self,ticker,**kwargs):
        return rows()


def purchase():
    return {"trade_id":"old", "filer":"TEST Representative", "owner":"Self", "ticker":"AAA", "transaction_type":"Purchase", "equity_like":True,"parse_confidence":"high", "transaction_date":"2026-08-03", "filed_date":"2026-08-04", "amount":"$1,001 - $15,000"}


def test_runtime_restart_and_final_refresh_do_not_double_count(tmp_path,monkeypatch):
    monkeypatch.setattr(edge,"_utc_now",lambda:NOW)
    config={"enabled":True,"horizons":[5],"horizon_weights":{"5":1},"backfill_analysis_limit_per_run":30}
    runtime=edge.InvestorEdgeRuntime(config,tmp_path,Provider(),{})
    profile=runtime.refresh_leaderboard([purchase()],as_of=AS_OF)
    first=json.loads((tmp_path/edge.OBSERVATION_FILE).read_text())["backfill"]["progress_journal"]
    runtime.refresh_leaderboard([purchase()],as_of=AS_OF,allow_backfill=False)
    final=json.loads((tmp_path/edge.OBSERVATION_FILE).read_text())["backfill"]["progress_journal"]
    assert first==final and len(final["events"])==1
    assert profile[0]["sample_count"]==1
    assert runtime.population_metadata["backfill_progress"]["counts"]["completed"]==1
    # Restore through the real constructor without requiring a live provider.
    import requests
    config_path=tmp_path/'edge.yml'; config_path.write_text('enabled: true\nhorizons: [5]\nhorizon_weights: {"5": 1}\n')
    restored=edge.InvestorEdgeRuntime.create(ai_dir=tmp_path,session=requests.Session(),alphavantage_api_key="",finnhub_api_key="",alphavantage_entitlement="",request_timeout=(1,1),config_path=config_path)
    assert restored.progress_journal==final


def test_progress_failure_does_not_change_scoring_or_erase_history(tmp_path,monkeypatch):
    monkeypatch.setattr(edge,"_utc_now",lambda:NOW)
    runtime=edge.InvestorEdgeRuntime({"enabled":True,"horizons":[5]},tmp_path,Provider(),{})
    runtime.progress_journal={"retained":"history"}
    monkeypatch.setattr(runtime,"_progress_inventory_unchecked",lambda *a,**k:(_ for _ in ()).throw(ValueError("private token")))
    result=runtime.refresh_leaderboard([purchase()],as_of=AS_OF)
    assert result[0]["sample_count"]==1
    assert runtime.population_metadata["backfill_progress"] is None
    assert runtime.progress_journal=={"retained":"history"}
    assert "private token" not in (tmp_path/edge.OBSERVATION_FILE).read_text()


def test_publication_is_read_only_and_inert_json_is_escaped(tmp_path):
    ai=tmp_path/'ai';ai.mkdir()
    work=work_fixture(); next(iter(work.values()))["investor"]='</script><script id="injected">bad()</script>'
    report=publish(work,{})
    payload={"investors":[],"backfill_progress":report,"api_key":"secret"}
    source=ai/edge.LEADERBOARD_FILE;source.write_text(json.dumps(payload)); before=source.read_bytes()
    out=tmp_path/'site'; edge.build_dashboard_addon(ai,out)
    assert source.read_bytes()==before
    soup=BeautifulSoup((out/'investor-edge.html').read_text(),'html.parser')
    assert soup.select_one('#injected') is None
    assert soup.select_one('#edge-backfill-data') is not None
    public=json.loads((out/'data/investor-edge.json').read_text())
    assert 'api_key' not in public and public['backfill_progress']['counts']['ready']==10
    assert 'PTBackfill.attachStandalone' in (out/'investor-edge.js').read_text()


def test_backfill_component_dom_when_node_tools_are_available():
    root=Path(__file__).resolve().parents[1]
    node=os.environ.get('POLITITRACK_TEST_NODE') or shutil.which('node')
    modules=Path(os.environ.get('POLITITRACK_TEST_NODE_MODULES',root/'.remediation/ui-test-tools/node_modules'))
    if not node or not (modules/'jsdom/package.json').exists():
        pytest.skip('Node/jsdom DOM checks run in canonical CI')
    env=dict(os.environ,POLITITRACK_TEST_NODE_MODULES=str(modules))
    result=subprocess.run([node,'--test','tests/backfill_progress_dom.test.cjs'],cwd=root,env=env,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('failure_site',['record_success','report'])
def test_broken_progress_accounting_is_nonfatal_and_explicitly_unknown(tmp_path,monkeypatch,failure_site):
    monkeypatch.setattr(edge,'_utc_now',lambda:NOW)
    runtime=edge.InvestorEdgeRuntime({'enabled':True,'horizons':[5]},tmp_path,Provider(),{})
    monkeypatch.setattr(progress,failure_site,lambda *a,**k:(_ for _ in ()).throw(ValueError('private token')))
    profiles=runtime.refresh_leaderboard([purchase()],as_of=AS_OF)
    assert profiles[0]['sample_count']==1
    assert runtime.population_metadata['backfill_progress'] is None
    assert 'private token' not in (tmp_path/edge.OBSERVATION_FILE).read_text()
