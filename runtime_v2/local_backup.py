"""Verified local physical backups, isolated from the production schedule.

The backup role has REPLICATION, not SQL superuser/BYPASSRLS privileges. Routine
backups never overwrite live data or the separately retained migration evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

LOG = logging.getLogger("polititrack.backup")
ROLE = "polititrack_backup"
RETRY_SECONDS = 3600
MAX_SECONDS = 10800
ROUTINE = re.compile(r"routine-\d{8}T\d{6}Z-[0-9a-f]{8}\.(base|partial)\Z")


def now_utc():
    return datetime.now(timezone.utc)


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_status(root):
    path = Path(root) / "config" / "backup-status.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def status(root, phase, **fields):
    value = read_status(root)
    value.update(schema_version=1, status=phase, updated_at=now_utc().isoformat(), **fields)
    atomic_json(Path(root) / "config" / "backup-status.json", value)
    return value


def failure(root, reason):
    return status(root, "failed", error=reason,
                  next_retry_at=(now_utc() + timedelta(seconds=RETRY_SECONDS)).isoformat())


def clean_environment(root):
    allowed = {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATH", "USERPROFILE", "APPDATA",
               "LOCALAPPDATA", "PROGRAMDATA"}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    env.update(TEMP=str(Path(root) / "temp"), TMP=str(Path(root) / "temp"),
               PYTHONUTF8="1", PYTHONUNBUFFERED="1")
    return env


def safe_routine(path, parent):
    return (path.parent == parent and ROUTINE.fullmatch(path.name)
            and path.is_dir() and not path.is_symlink()
            and not getattr(path, "is_junction", lambda: False)())


def verified_receipt(path):
    receipt = json.loads((path / "verified.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((path / "backup_manifest").read_bytes()).hexdigest()
    if (receipt.get("repository_id") != 1349678672 or receipt.get("pg_verifybackup") != "passed"
            or receipt.get("manifest_sha256") != digest or receipt.get("directory") != path.name):
        raise ValueError("Routine backup verification receipt does not match its manifest")
    return receipt


def rotate(parent):
    """Only this module's verified directories; never the cutover backup/export."""
    completed = []
    for path in parent.glob("routine-*.base"):
        if safe_routine(path, parent):
            verified_receipt(path)  # Fail closed rather than delete unverifiable evidence.
            completed.append(path)
    for path in sorted(completed, reverse=True)[2:]:
        shutil.rmtree(path)


def run_backup(config):
    import psycopg2
    from .local_host import active

    root = Path(config["root"])
    if not active(config):
        raise RuntimeError("Verified Beast authority is required for a routine backup")
    lock = psycopg2.connect(config["database_url"], connect_timeout=15)
    lock.autocommit = True
    staging = None
    acquired = False
    try:
        with lock.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(hashtext('polititrack-local-backup'))")
            acquired = cursor.fetchone()[0]
            if not acquired:
                raise RuntimeError("Another local backup owns the backup lock")
            cursor.execute("SELECT spcname FROM pg_tablespace WHERE spcname NOT IN ('pg_default','pg_global')")
            if cursor.fetchall():
                raise RuntimeError("External tablespaces require an explicit backup mapping")
            cursor.execute("SELECT sum(pg_database_size(oid)) FROM pg_database")
            required = int(cursor.fetchone()[0]) * 1.2 + 1024 ** 3
        credentials = json.loads((root / "config" / "backup-private.json").read_text(encoding="utf-8"))
        if (credentials.get("username") != ROLE or credentials.get("host") != "127.0.0.1"
                or credentials.get("port") != 54329 or not credentials.get("password")):
            raise ValueError("Dedicated loopback backup credentials are required")
        parent = root / "backups"
        if shutil.disk_usage(parent).free < required:
            raise RuntimeError("Insufficient free space for a new full physical backup")
        # The advisory lock excludes all new backup workers, including manual runs.
        for abandoned in parent.glob("routine-*.partial"):
            if safe_routine(abandoned, parent):
                shutil.rmtree(abandoned)
        stamp = now_utc().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        staging = parent / ("routine-" + stamp + ".partial")
        destination = staging.with_suffix(".base")
        started = now_utc().isoformat()
        status(root, "running", started_at=started, error=None, next_retry_at=None,
               partial_directory=staging.name)
        env = clean_environment(root)
        env["PGPASSWORD"] = credentials["password"]
        tools = root / "tools" / "postgresql16" / "pgsql" / "bin"
        command = [str(tools / "pg_basebackup.exe"), "--host=127.0.0.1", "--port=54329",
                   "--username=" + ROLE, "--no-password", "--pgdata=" + str(staging),
                   "--format=plain", "--wal-method=stream", "--checkpoint=fast",
                   "--manifest-checksums=SHA256"]
        subprocess.run(command, env=env, check=True, timeout=7200)
        env.pop("PGPASSWORD", None)
        status(root, "verifying")
        subprocess.run([str(tools / "pg_verifybackup.exe"), "--exit-on-error", str(staging)],
                       env=env, check=True, timeout=3600)
        with lock.cursor() as cursor:
            cursor.execute("SELECT 1")  # Do not publish after losing backup ownership.
        manifest = staging / "backup_manifest"
        receipt = {"repository_id": 1349678672, "kind": "postgresql16_physical",
                   "directory": destination.name, "started_at": started,
                   "completed_at": now_utc().isoformat(), "pg_verifybackup": "passed",
                   "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                   "bytes": sum(p.stat().st_size for p in staging.rglob("*") if p.is_file()),
                   "source_revision": config["source_revision"]}
        atomic_json(staging / "verified.json", receipt)
        os.replace(staging, destination)
        staging = None
        status(root, "success", last_success=receipt, error=None, next_retry_at=None,
               partial_directory=None)
        try:
            rotate(parent)
        except Exception as exc:
            # Retention failure cannot undo a verified backup or stop producers.
            status(root, "success", retention_error=type(exc).__name__)
            LOG.error("Routine backup retention failed: %s", type(exc).__name__)
        return receipt
    except Exception as exc:
        if acquired:
            if staging is not None and safe_routine(staging, root / "backups"):
                try:
                    shutil.rmtree(staging)
                except OSError:
                    LOG.error("Incomplete backup cleanup deferred")
            failure(root, type(exc).__name__)
        raise
    finally:
        lock.close()


class BackupSupervisor:
    """Poll one separate backup child; never wait for a backup in the job loop."""

    def __init__(self, config):
        self.config = config
        self.root = Path(config["root"])
        self.process = None
        self.output = None
        self.started = 0.0
        self.retry_after = 0.0

    def _finish(self, code):
        self.output.close()
        self.output = None
        self.process = None
        value = read_status(self.root)
        if code != 0 or value.get("status") != "success":
            failure(self.root, "backup_worker_exit_" + str(code))
            self.retry_after = time.monotonic() + RETRY_SECONDS
            LOG.error("Backup worker failed; producer scheduling continues")
        else:
            LOG.info("Verified backup completed: %s", value["last_success"]["directory"])

    def tick(self):
        try:
            self._tick()
        except Exception as exc:
            self.retry_after = time.monotonic() + RETRY_SECONDS
            LOG.error("Backup supervision error (%s); producer scheduling continues", type(exc).__name__)

    def _tick(self):
        if self.process is not None:
            code = self.process.poll()
            if code is None and time.monotonic() - self.started > MAX_SECONDS:
                from .local_host import kill_tree
                kill_tree(self.process)
                code = self.process.wait(timeout=15)
            if code is not None:
                self._finish(code)
            return
        if time.monotonic() < self.retry_after:
            return
        value = read_status(self.root)
        now = now_utc()
        if value.get("last_success", {}).get("completed_at", "")[:10] == now.date().isoformat():
            return
        not_before = value.get("next_retry_at")
        if not_before and datetime.fromisoformat(not_before) > now:
            return
        # Persist backoff before spawn, covering interruption before worker startup.
        status(self.root, "queued", next_retry_at=(now + timedelta(seconds=RETRY_SECONDS)).isoformat())
        self.output = (self.root / "logs" / "routine-backup.log").open("ab")
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "runtime_v2.local_host", "--config",
                 str(self.root / "config" / "runtime.json"), "backup"],
                cwd=self.root / "app", env=clean_environment(self.root),
                stdin=subprocess.DEVNULL, stdout=self.output, stderr=subprocess.STDOUT)
        except Exception:
            self.output.close()
            self.output = None
            failure(self.root, "backup_worker_start_failed")
            raise
        self.started = time.monotonic()
        LOG.info("Started independent backup PID %s", self.process.pid)

    def stop(self):
        if self.process is not None:
            from .local_host import kill_tree
            kill_tree(self.process)
            try:
                self.process.wait(timeout=15)
                failure(self.root, "backup_interrupted_by_service_stop")
            finally:
                self.output.close()
                self.output = None
                self.process = None
