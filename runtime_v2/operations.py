"""Owner-authorized dispatch receipts, separate from all producer state.

Reservations commit before the network call. An ambiguous response is reconciled
using an execution-scoped UUID; it is never automatically submitted again.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, Float, MetaData, String, Table, insert, select, update

from .review_accounts import ReviewError

JOBS = {"legislative": "polititrack-legislative", "executive": "polititrack-executive", "ai": "polititrack-ai"}
TERMINAL = {"succeeded", "failed", "rejected"}
REQUEST_ENV = "POLITITRACK_MANUAL_REQUEST_ID"
TRIGGER = "dashboard_manual"
metadata = MetaData()
gates = Table("runtime_operation_gates", metadata,
    Column("job", String(32), primary_key=True), Column("request_id", String(36)))
receipts = Table("runtime_operation_requests", metadata,
    Column("request_id", String(36), primary_key=True),
    Column("job", String(32), nullable=False), Column("account_id", String(36), nullable=False),
    Column("created_at", Float, nullable=False), Column("state", String(32), nullable=False),
    Column("execution", String(512)), Column("finished_at", String(64)))


def unavailable():
    return ReviewError("RUN_CONTROL_UNAVAILABLE", "Run controls are temporarily unavailable. Check again shortly.", 503)


def request_uuid(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise ReviewError("INVALID_REQUEST", "Refresh PolitiTrack before starting a run.") from None
    return value


def execution_state(execution):
    conditions = {item.get("type"): item.get("state") for item in execution.get("conditions", [])}
    if execution.get("completionTime"):
        if (conditions.get("Completed") == "CONDITION_SUCCEEDED"
            and execution.get("succeededCount", 0) == execution.get("taskCount", 1)
            and not execution.get("failedCount") and not execution.get("cancelledCount")):
            return "succeeded"
        return "failed"
    return "running" if execution.get("startTime") else "starting"


def execution_request(execution):
    values = [env.get("value") for container in execution.get("template", {}).get("containers", [])
              for env in container.get("env", []) if env.get("name") == REQUEST_ENV]
    return values[0] if len(values) == 1 else None


class CloudRunJobs:
    """Fixed resources and fixed overrides. No client-supplied URL/command/env."""
    def __init__(self, project, region, session=None):
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project or "") or not re.fullmatch(r"[a-z]+-[a-z]+[0-9]", region or ""):
            raise unavailable()
        self.prefix = f"projects/{project}/locations/{region}"
        self._session = session

    @property
    def session(self):
        if self._session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            # Token refresh must not replay a POST whose outcome is uncertain.
            self._session = AuthorizedSession(credentials, max_refresh_attempts=0)
        return self._session

    def name(self, job):
        return f"{self.prefix}/jobs/{JOBS[job]}"

    def read(self, resource, **params):
        response = self.session.get("https://run.googleapis.com/v2/" + resource, params=params, timeout=(3, 10))
        response.raise_for_status()
        return response.json()

    def executions(self, job):
        # Read every retained page; a truncated busy check must never permit a run.
        result, token, started = [], None, time.monotonic()
        for _ in range(12):
            if time.monotonic() - started > 15:
                raise unavailable()
            page = self.read(self.name(job) + "/executions", pageSize=100, **({"pageToken": token} if token else {}))
            result.extend(page.get("executions", []))
            token = page.get("nextPageToken")
            if not token:
                return result
        raise unavailable()

    def execution(self, job, name):
        if not name.startswith(self.name(job) + "/executions/") or not re.fullmatch(r"[a-z0-9-]+", name.rsplit("/", 1)[-1]):
            raise unavailable()
        return self.read(name)

    def prepare(self, job):
        config = self.read(self.name(job))
        template = config.get("template", {}).get("template", {})
        containers = template.get("containers", [])
        # Refuse a changed entry point or multiple tasks: a successful process must
        # mean that this producer ran, including its strict manual busy failure.
        if (len(containers) != 1 or containers[0].get("command") != ["python"]
            or containers[0].get("args") != ["-m", "runtime_v2", "run", job]
            or config.get("template", {}).get("taskCount", 1) != 1
            or template.get("maxRetries", 0) != 0
            or not any(env.get("name") == "POLITITRACK_MODE" and env.get("value") == "production"
                       for env in containers[0].get("env", []))):
            raise unavailable()
        return {"etag": config["etag"], "container": containers[0].get("name", "")}

    def start(self, job, request_id, prepared):
        override = {"env": [{"name": "POLITITRACK_TRIGGER_SOURCE", "value": TRIGGER},
                            {"name": REQUEST_ENV, "value": request_id}]}
        if prepared["container"]:
            override["name"] = prepared["container"]
        # requests/AuthorizedSession do not retry this write.
        response = self.session.post("https://run.googleapis.com/v2/" + self.name(job) + ":run",
            json={"etag": prepared["etag"], "overrides": {"containerOverrides": [override]}}, timeout=(3, 20))
        if response.status_code in {400, 401, 403, 404, 409, 412, 429}:
            return {"rejected": True}
        response.raise_for_status()
        return response.json()


class OperationStore:
    def __init__(self, engine=None, clock=None):
        self._engine = engine
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())

    @property
    def engine(self):
        if self._engine is None:
            from .database import sqlalchemy_engine
            self._engine = sqlalchemy_engine()
        return self._engine

    def initialize_schema(self):
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            for job in JOBS:
                if not conn.execute(select(gates.c.job).where(gates.c.job == job)).first():
                    conn.execute(insert(gates).values(job=job))

    @staticmethod
    def public(row):
        return {key: row.get(key) for key in ("request_id", "state", "created_at", "finished_at")}

    def _latest(self, conn, job):
        gate = conn.execute(select(gates).where(gates.c.job == job).with_for_update()).mappings().one()
        return conn.execute(select(receipts).where(receipts.c.request_id == gate["request_id"])).mappings().first()

    def _reconcile(self, conn, row, cloud, executions=None):
        if not row or row["state"] in TERMINAL:
            return row
        execution = None
        if row["execution"]:
            execution = cloud.execution(row["job"], row["execution"])
        else:
            matches = [item for item in (executions if executions is not None else cloud.executions(row["job"]))
                       if execution_request(item) == row["request_id"]]
            if len(matches) > 1:
                raise unavailable()
            if matches:
                execution = matches[0]
        if execution:
            if execution_request(execution) != row["request_id"]:
                raise unavailable()
            changes = {"state": execution_state(execution), "execution": execution["name"],
                       "finished_at": execution.get("completionTime")}
            conn.execute(update(receipts).where(receipts.c.request_id == row["request_id"]).values(**changes))
            return {**row, **changes}
        return row

    def status(self, job, cloud):
        with self.engine.begin() as conn:
            row = self._latest(conn, job)
            executions = cloud.executions(job)
            row = self._reconcile(conn, row, cloud, executions)
            busy = any(execution_state(item) not in TERMINAL for item in executions)
            return {"job": job, "busy": busy or bool(row and row["state"] not in TERMINAL),
                    "latest_request": self.public(row) if row else None}

    def start(self, job, account_id, request_id, cloud):
        request_uuid(request_id)
        with self.engine.begin() as conn:
            latest = self._latest(conn, job)
            prior = conn.execute(select(receipts).where(receipts.c.request_id == request_id)).mappings().first()
            if prior:
                if prior["job"] != job or prior["account_id"] != account_id:
                    raise ReviewError("REQUEST_CONFLICT", "Refresh before starting another run.", 409)
                return self.public(self._reconcile(conn, prior, cloud))
            executions = cloud.executions(job)
            latest = self._reconcile(conn, latest, cloud, executions)
            if (latest and latest["state"] not in TERMINAL) or any(execution_state(item) not in TERMINAL for item in executions):
                raise ReviewError("RUN_ALREADY_ACTIVE", "A run is already starting or running. Its progress will appear here.", 409)
            if latest and self.clock() - latest["created_at"] < 60:
                raise ReviewError("RUN_COOLDOWN", "Wait a minute between manual runs.", 429)
            prepared = cloud.prepare(job)
            row = dict(request_id=request_id, job=job, account_id=account_id, created_at=self.clock(),
                       state="starting", execution=None, finished_at=None)
            conn.execute(insert(receipts).values(**row))
            conn.execute(update(gates).where(gates.c.job == job).values(request_id=request_id))
        try:
            result = cloud.start(job, request_id, prepared)
            state = "rejected" if result.get("rejected") else "starting"
        except Exception:
            # Commit the uncertainty and reconcile by UUID on subsequent reads.
            state = "unconfirmed"
        with self.engine.begin() as conn:
            current = self._latest(conn, job)
            if current and current["request_id"] == request_id and current["state"] in {"starting", "unconfirmed"}:
                conn.execute(update(receipts).where(receipts.c.request_id == request_id).values(state=state))
                row = {**current, "state": state}
            elif current:
                row = current
        return self.public(row)
