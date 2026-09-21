"""Native Windows host for the existing Runtime v2 producers and dashboard.

The scheduler replaces Cloud Scheduler; it never creates a second state format.
Activation requires a private, explicit migration receipt. Database advisory
locks remain the producer authority. Missed intervals coalesce after restart.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

SCHEDULES = {"legislative": (15, 5), "executive": (30, 11),
             "ai": (30, 14), "dashboard": (15, 2)}
ORIGIN = "http://127.0.0.1:8765"
LOG = logging.getLogger("polititrack.local")


def latest_slot(now, period, offset):
    minute = int(now.timestamp()) // 60
    return (minute - offset) // period * period + offset


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    db = urlsplit(config["database_url"])
    if (config.get("schema_version") != 1 or db.scheme != "postgresql"
            or db.hostname != "127.0.0.1" or db.port != 54329
            or db.path != "/polititrack" or not db.username or not db.password):
        raise ValueError("Local configuration must use the dedicated loopback database")
    if set(config["environments"]) != {*SCHEDULES, "web"}:
        raise ValueError("Local configuration must contain exactly the existing runtime services")
    return config


def environment(config, job):
    # Never inherit cloud credentials, connectors, or secrets from the launcher.
    result = {key: value for key, value in os.environ.items()
              if key.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "PATH",
                                 "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA"}}
    result.update({key: str(value) for key, value in config["environments"][job].items()})
    for key in tuple(result):
        if key.startswith(("GOOGLE_", "CLOUDSDK_")) or key in {
            "INSTANCE_CONNECTION_NAME", "DB_USER", "DB_PASSWORD", "DB_IAM_USER", "PRIVATE_IP",
            "VAULT_GCS_BUCKET", "RUNTIME_OPERATIONS_PROJECT", "RUNTIME_OPERATIONS_REGION"}:
            result.pop(key, None)
    root = Path(config["root"])
    result.update(DATABASE_URL=config["database_url"], POLITITRACK_MODE="production",
                  RUNTIME_LOCAL_ONLY="true", RUNTIME_REVIEW_ORIGIN=ORIGIN,
                  DASHBOARD_URL=ORIGIN + "/#overview", RUNTIME_OPERATIONS_ENABLED="false",
                  VAULT_STORAGE_BACKEND="windows_local", VAULT_FILE_ROOT=str(root / "vault"),
                  VAULT_DATABASE_URL=config["database_url"], VAULT_ALLOWED_ORIGINS=ORIGIN,
                  PYTHONUTF8="1", PYTHONUNBUFFERED="1",
                  PLAYWRIGHT_BROWSERS_PATH=str(root / "tools" / "playwright"),
                  SOURCE_REVISION=config["source_revision"],
                  POLITITRACK_TRIGGER_SOURCE="external_scheduler",
                  ALLOW_STATE_INITIALIZATION="false", BOOTSTRAP_ALERTS="false")
    result["PATH"] = os.pathsep.join(config["tool_paths"] + [result.get("PATH", "")])
    result["TEMP"] = result["TMP"] = str(root / "temp")
    return result


def active(config):
    path = Path(config["root"]) / "config" / "local-authority.json"
    if not path.is_file():
        return False
    receipt = json.loads(path.read_text(encoding="utf-8"))
    return (receipt.get("repository_id") == 1349678672
            and receipt.get("authority") == "beast_local"
            and receipt.get("cloud_writers_drained") is True
            and receipt.get("database_verified") is True)


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def kill_tree(process):
    import psutil
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=10)
    except psutil.NoSuchProcess:
        pass


def windows_job():
    """Kill descendants if this service unexpectedly exits, including OCR tools."""
    if os.name != "nt":
        return None
    import win32api
    import win32job
    handle = win32job.CreateJobObject(None, "")
    limits = win32job.QueryInformationJobObject(handle, win32job.JobObjectExtendedLimitInformation)
    limits["BasicLimitInformation"]["LimitFlags"] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(handle, win32job.JobObjectExtendedLimitInformation, limits)
    win32job.AssignProcessToJobObject(handle, win32api.GetCurrentProcess())
    return handle


def backup(config):
    from .local_backup import BackupBusy, run_backup
    try:
        return run_backup(config)
    except BackupBusy:
        raise SystemExit(75)


def schedule(config):
    import psycopg2
    from .local_backup import BackupSupervisor
    root = Path(config["root"])
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda *_: stop.set())
    job_handle = windows_job()  # Kept alive for the full supervisor lifetime.
    state_path = root / "config" / "schedule-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    children = {}
    backup_worker = BackupSupervisor(config)
    lock = psycopg2.connect(config["database_url"], connect_timeout=15)
    lock.autocommit = True
    with lock.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(hashtext('polititrack-local-scheduler'))")
        if not cursor.fetchone()[0]:
            raise RuntimeError("Another local scheduler already owns the schedule")
    try:
        while not stop.is_set():
            with lock.cursor() as cursor:
                cursor.execute("SELECT 1")  # Fail closed if scheduler ownership connection dies.
            for name, (process, output, started) in list(children.items()):
                code = process.poll()
                if code is None and time.monotonic() - started > 3360:
                    kill_tree(process)
                    code = process.wait(timeout=15)
                if code is not None:
                    output.close()
                    children.pop(name)
                    LOG.info("%s exited with %s", name, code)
            if active(config):
                now = datetime.now(timezone.utc)
                for name, (period, offset) in SCHEDULES.items():
                    slot = latest_slot(now, period, offset)
                    if name in children or state.get(name, -1) >= slot:
                        continue
                    state[name] = slot
                    atomic_json(state_path, state)
                    output = (root / "logs" / (name + "-" + now.strftime("%Y%m%dT%H%M%SZ") + ".log")).open("ab")
                    child = subprocess.Popen([sys.executable, "-m", "runtime_v2", "run", name],
                        cwd=root / "app", env=environment(config, name), stdout=output, stderr=subprocess.STDOUT)
                    children[name] = (child, output, time.monotonic())
                    LOG.info("Started %s PID %s", name, child.pid)
                # Backup child is polled, never awaited by the production loop.
                backup_worker.tick()
            stop.wait(5)
    finally:
        try:
            backup_worker.stop()
        except Exception:
            LOG.exception("Backup shutdown cleanup failed")
        for process, output, _ in children.values():
            kill_tree(process)
            output.close()
        lock.close()
        # Keep the Windows handle alive until all workers have stopped.
        if job_handle is not None:
            job_handle.Detach()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("action", choices=("web", "schedule", "status", "backup", "check"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    root = Path(config["root"])
    (root / "temp").mkdir(exist_ok=True)
    if args.action == "schedule":
        return schedule(config)
    if args.action == "backup":
        print(json.dumps(backup(config)))
        return
    selected_environment = environment(config, "web")
    os.environ.clear()
    os.environ.update(selected_environment)
    if args.action == "web":
        from waitress import serve
        from .web import create_app
        serve(create_app(), host="127.0.0.1", port=8765, threads=8,
              max_request_body_size=21 * 1024 * 1024, clear_untrusted_proxy_headers=True)
    else:
        from .store import PostgresSnapshotStore
        status = PostgresSnapshotStore().status()
        print(json.dumps({"local_authority": active(config), "runtime": status}, sort_keys=True))


if __name__ == "__main__":
    main()
