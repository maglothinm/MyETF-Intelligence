"""Production runs require an owner session and a durable single-dispatch receipt."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from flask import Flask
from sqlalchemy import select

from runtime_v2.operations import (CloudRunJobs, JOBS, OperationStore, REQUEST_ENV, TRIGGER,
    execution_state, receipts)
from runtime_v2.operations_api import create_blueprint
from runtime_v2.review_accounts import ReviewError
from runtime_v2.review_api import COOKIE
from tests.test_personal_reviews import store, member, ORIGIN


def execution(job, request_id=None, state="starting"):
    value = {"name": f"projects/project-test/locations/us-central1/jobs/{JOBS[job]}/executions/test-1",
        "taskCount": 1, "template": {"containers": [{"env": [{"name": REQUEST_ENV, "value": request_id}]}]}}
    if state in {"running", "succeeded", "failed"}:
        value["startTime"] = "2026-09-09T13:00:00Z"
    if state in {"succeeded", "failed"}:
        value.update(completionTime="2026-09-09T13:10:00Z", succeededCount=int(state == "succeeded"),
            conditions=[{"type": "Completed", "state": "CONDITION_SUCCEEDED" if state == "succeeded" else "CONDITION_FAILED"}])
    return value


class Cloud:
    def __init__(self):
        self.items = {job: [] for job in JOBS}
        self.calls = []
        self.lose_response = False
        self.rejected = False
    def executions(self, job):
        return deepcopy(self.items[job])
    def execution(self, job, name):
        return deepcopy(next(item for item in self.items[job] if item["name"] == name))
    def prepare(self, job):
        return {"etag": "verified", "container": ""}
    def start(self, job, request_id, prepared):
        self.calls.append((job, request_id))
        if self.rejected:
            return {"rejected": True}
        self.items[job].append(execution(job, request_id))
        if self.lose_response:
            raise TimeoutError("private cloud details")
        return {"name": "operation/accepted"}


@pytest.fixture
def control(store):
    result = OperationStore(store.engine, clock=lambda: datetime(2026, 9, 9, 13, tzinfo=timezone.utc).timestamp())
    result.initialize_schema()
    return result


def test_dispatch_replay_restart_and_completion(control):
    cloud = Cloud(); request = str(uuid.uuid4())
    assert control.start("ai", "owner", request, cloud)["state"] == "starting"
    assert control.start("ai", "owner", request, cloud)["state"] == "starting"
    restarted = OperationStore(control.engine, clock=control.clock)
    assert restarted.status("ai", cloud)["busy"] is True
    cloud.items["ai"] = [execution("ai", request, "succeeded")]
    assert restarted.status("ai", cloud)["latest_request"]["state"] == "succeeded"
    assert restarted.start("ai", "owner", request, cloud)["state"] == "succeeded"
    assert len(cloud.calls) == 1


def test_timeout_reconciles_exact_execution_without_redispatch(control):
    cloud = Cloud(); cloud.lose_response = True; request = str(uuid.uuid4())
    assert control.start("legislative", "owner", request, cloud)["state"] == "unconfirmed"
    cloud.items["legislative"].insert(0, execution("legislative", "scheduled", "succeeded"))
    assert control.status("legislative", cloud)["latest_request"]["state"] == "starting"
    assert len(cloud.calls) == 1


def test_worker_loss_before_start_response_does_not_look_like_normal_startup_forever(control):
    cloud = Cloud(); request = str(uuid.uuid4())
    control.start("ai", "owner", request, cloud)
    cloud.items["ai"] = []
    now = control.clock()
    restarted = OperationStore(control.engine, clock=lambda: now + 121)
    value = restarted.status("ai", cloud)
    assert value["busy"] and value["latest_request"]["state"] == "unconfirmed"
    cloud.items["ai"] = [execution("ai", request, "succeeded")]
    assert restarted.status("ai", cloud)["latest_request"]["state"] == "succeeded"
    assert len(cloud.calls) == 1


def test_failure_can_be_retried_and_old_receipt_remains(control):
    cloud = Cloud(); request = str(uuid.uuid4())
    control.start("executive", "owner", request, cloud)
    cloud.items["executive"] = [execution("executive", request, "failed")]
    assert control.status("executive", cloud)["latest_request"]["state"] == "failed"
    now = control.clock(); control.clock = lambda: now + 61
    control.start("executive", "owner", str(uuid.uuid4()), cloud)
    with control.engine.connect() as conn:
        assert len(conn.execute(select(receipts)).all()) == 2
    assert len(cloud.calls) == 2


def test_existing_scheduled_run_and_durable_reservation_prevent_duplicates(control):
    cloud = Cloud(); cloud.items["ai"] = [execution("ai")]
    with pytest.raises(ReviewError, match="already"):
        control.start("ai", "owner", str(uuid.uuid4()), cloud)
    assert not cloud.calls
    cloud.items["ai"] = []
    control.start("ai", "owner", str(uuid.uuid4()), cloud)
    cloud.items["ai"] = []  # Receipt remains authoritative if Cloud Run has not listed it yet.
    with pytest.raises(ReviewError, match="already"):
        control.start("ai", "owner", str(uuid.uuid4()), cloud)
    assert len(cloud.calls) == 1


def test_parallel_requests_across_web_instances_dispatch_once(control):
    if control.engine.dialect.name != "postgresql":
        pytest.skip("Row locking requires PostgreSQL")
    cloud = Cloud()
    def attempt(_):
        try:
            return OperationStore(control.engine, clock=control.clock).start("ai", "owner", str(uuid.uuid4()), cloud)
        except ReviewError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert len(cloud.calls) == 1
    assert results.count("RUN_ALREADY_ACTIVE") == 3


def test_no_success_without_completed_execution_evidence():
    item = execution("ai", "request")
    item.update(succeededCount=1, conditions=[{"type": "Completed", "state": "CONDITION_SUCCEEDED"}])
    assert execution_state(item) == "starting"
    item["completionTime"] = "2026-09-09T13:10:00Z"
    item["failedCount"] = 1
    assert execution_state(item) == "failed"
    item.pop("failedCount"); item["succeededCount"] = 0
    assert execution_state(item) == "failed"


@pytest.fixture
def api(store, control):
    owner, token = member(store)
    other, other_token = member(store, "bob")
    cloud = Cloud(); app = Flask(__name__)
    app.config.update(RUNTIME_PERSONAL_REVIEWS_ENABLED="true", RUNTIME_OPERATIONS_ENABLED="true",
        RUNTIME_REVIEW_ORIGIN=ORIGIN, RUNTIME_OPERATIONS_ACCOUNT_IDS=owner["account_id"])
    app.register_blueprint(create_blueprint(store, control, cloud))
    client = app.test_client(); client.set_cookie(COOKIE, token, domain="dashboard.test")
    return SimpleNamespace(app=app, client=client, cloud=cloud, owner=owner, other=other, other_token=other_token)


def post(api, job="ai", headers=None, **changes):
    body = dict(expected_account_id=api.owner["account_id"], request_id=str(uuid.uuid4())); body.update(changes)
    return api.client.post(f"/api/operations/{job}/runs", base_url=ORIGIN, json=body,
        headers=headers if headers is not None else {"Origin": ORIGIN, "X-PolitiTrack-Operation-Request": "1"})


def test_api_owner_only_origin_identity_allowlist_and_private_responses(api):
    assert post(api, headers={}).status_code == 403
    assert post(api, expected_account_id=api.other["account_id"]).status_code == 409
    for job in ("dashboard", "admin", "simulation"):
        assert post(api, job=job).status_code == 404
    assert post(api, overrides={"args": ["init-db"]}).status_code == 400
    assert post(api, request_id="bad").status_code == 400
    assert not api.cloud.calls
    response = post(api)
    assert response.status_code == 202
    assert response.json["latest_request"]["state"] == "starting"
    assert "no-store" in response.headers["Cache-Control"]
    assert "account_id" not in response.json["latest_request"]
    api.client.set_cookie(COOKIE, api.other_token, domain="dashboard.test")
    assert post(api).status_code == 403
    api.client.delete_cookie(COOKIE, domain="dashboard.test")
    assert post(api).status_code == 401
    assert len(api.cloud.calls) == 1


def test_disabled_feature_and_cloud_errors_fail_closed(api):
    api.app.config["RUNTIME_OPERATIONS_ENABLED"] = "false"
    assert post(api).status_code == 503
    api.app.config["RUNTIME_OPERATIONS_ENABLED"] = "true"
    def fail(_):
        raise RuntimeError("secret provider details")
    api.cloud.executions = fail
    response = post(api)
    assert response.status_code == 503 and "secret" not in response.get_data(as_text=True)
    assert not api.cloud.calls


def test_cloud_adapter_fixed_resource_overrides_and_no_status_shortcuts():
    calls = []
    class Session:
        def get(self, url, **kw):
            value = {"etag": "pinned", "template": {"taskCount": 1, "template": {"containers": [
                {"command": ["python"], "args": ["-m", "runtime_v2", "run", "ai"],
                 "env": [{"name": "POLITITRACK_MODE", "value": "production"}]}]}}}
            return SimpleNamespace(json=lambda: value, raise_for_status=lambda: None)
        def post(self, url, **kw):
            calls.append((url, kw))
            return SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"name": "accepted"})
    cloud = CloudRunJobs("project-test", "us-central1", Session()); request = str(uuid.uuid4())
    cloud.start("ai", request, cloud.prepare("ai"))
    url, kw = calls[0]
    assert url.endswith("/jobs/polititrack-ai:run")
    assert kw["json"] == {"etag": "pinned", "overrides": {"containerOverrides": [{"env": [
        {"name": "POLITITRACK_TRIGGER_SOURCE", "value": TRIGGER}, {"name": REQUEST_ENV, "value": request}]}]}}
    with pytest.raises(ReviewError):
        cloud.execution("ai", "https://attacker.test/credentials")
    with pytest.raises(ReviewError):
        cloud.prepare("legislative")


def test_manual_scheduled_collision_is_not_reported_as_success(monkeypatch):
    from runtime_v2 import cli
    from runtime_v2.mode import RuntimeMode
    from runtime_v2.store import NamespaceBusy
    def busy(_):
        raise NamespaceBusy("another writer owns this namespace")
    monkeypatch.setenv("POLITITRACK_TRIGGER_SOURCE", TRIGGER)
    monkeypatch.setattr(cli, "resolve_runtime_mode", lambda: RuntimeMode.PRODUCTION)
    monkeypatch.setattr(cli, "PostgresSnapshotStore", lambda: object())
    monkeypatch.setattr(cli, "JobRunner", lambda *_a, **_kw: SimpleNamespace(run=busy))
    with pytest.raises(NamespaceBusy):
        cli.main(["run", "ai"])


def test_manual_trigger_and_actual_ai_cadence_survive_publication():
    from scripts.collector_freshness import FRESHNESS_POLICY, trigger_source
    assert trigger_source({"trigger_source": TRIGGER}) == TRIGGER
    assert FRESHNESS_POLICY["ai"]["expected_interval_minutes"] == 30
    assert "14 and 44" in FRESHNESS_POLICY["ai"]["trigger_relationship"]


def test_cloud_pagination_checks_later_active_executions_and_refuses_truncation():
    cloud = CloudRunJobs("project-test", "us-central1", object())
    calls = []
    def page(_resource, **params):
        calls.append(params)
        if params.get("pageToken") == "next":
            return {"executions": [execution("ai")]}
        return {"executions": [execution("ai", "old", "succeeded")], "nextPageToken": "next"}
    cloud.read = page
    assert len(cloud.executions("ai")) == 2 and len(calls) == 2
    cloud.read = lambda *_a, **_kw: {"nextPageToken": "forever"}
    with pytest.raises(ReviewError):
        cloud.executions("ai")
