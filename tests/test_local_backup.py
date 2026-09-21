from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from runtime_v2 import local_backup as backup
from runtime_v2 import local_host


@pytest.fixture
def cfg(tmp_path):
    for name in ['config', 'app', 'logs', 'backups', 'temp']:
        (tmp_path / name).mkdir()
    value = {'root': str(tmp_path), 'database_url': 'postgresql://runtime:secret@127.0.0.1:54329/polititrack',
             'source_revision': 'a' * 40}
    backup.atomic_json(tmp_path / 'config' / 'backup-private.json', {
        'username': backup.ROLE, 'host': '127.0.0.1', 'port': 54329, 'password': 'test-only'})
    return value


def completed(root, name, day='2026-09-20'):
    path = root / 'backups' / name
    path.mkdir()
    (path / 'backup_manifest').write_bytes(b'known manifest')
    receipt = {'repository_id': 1349678672, 'directory': name, 'pg_verifybackup': 'passed',
               'manifest_sha256': hashlib.sha256(b'known manifest').hexdigest(),
               'completed_at': day + 'T12:00:00+00:00'}
    backup.atomic_json(path / 'verified.json', receipt)
    return receipt


def fake_database(monkeypatch, acquired=True, tablespaces=None):
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    cursor.fetchone.side_effect = [(acquired,), (1,)]
    cursor.fetchall.return_value = tablespaces or []
    connection = Mock()
    connection.cursor.return_value = cursor
    import psycopg2
    monkeypatch.setattr(psycopg2, 'connect', Mock(return_value=connection))
    monkeypatch.setattr(local_host, 'active', lambda _: True)
    return connection


def test_success_requires_full_manifest_verification(cfg, monkeypatch):
    connection = fake_database(monkeypatch)
    calls = []
    def run(command, **kwargs):
        calls.append((command, dict(kwargs['env'])))
        if 'pg_basebackup' in command[0]:
            target = Path(next(x.split('=', 1)[1] for x in command if x.startswith('--pgdata=')))
            target.mkdir()
            (target / 'backup_manifest').write_bytes(b'full manifest')
            (target / 'data').write_bytes(b'full database')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(backup.subprocess, 'run', run)
    result = backup.run_backup(cfg)
    assert result['pg_verifybackup'] == 'passed'
    assert len(calls) == 2 and 'pg_verifybackup' in calls[1][0][0]
    assert '--username=polititrack_backup' in calls[0][0]
    assert calls[0][1]['PGPASSWORD'] == 'test-only'
    assert 'PGPASSWORD' not in calls[1][1]
    assert all('test-only' not in arg for args, _ in calls for arg in args)
    root = Path(cfg['root'])
    assert backup.read_status(root)['status'] == 'success'
    assert backup.verified_receipt(root / 'backups' / result['directory']) == result
    assert not list((root / 'backups').glob('routine-*.partial'))
    connection.close.assert_called_once()


def test_verification_failure_preserves_prior_backup_and_sets_backoff(cfg, monkeypatch):
    fake_database(monkeypatch)
    root = Path(cfg['root'])
    prior = completed(root, 'routine-20260920T120000Z-11111111.base')
    backup.status(root, 'success', last_success=prior)
    def run(command, **kwargs):
        if 'pg_basebackup' in command[0]:
            target = Path(next(x.split('=', 1)[1] for x in command if x.startswith('--pgdata=')))
            target.mkdir()
            (target / 'backup_manifest').write_bytes(b'bad manifest')
        else:
            raise backup.subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(backup.subprocess, 'run', run)
    with pytest.raises(backup.subprocess.CalledProcessError):
        backup.run_backup(cfg)
    value = backup.read_status(root)
    assert value['status'] == 'failed' and value['last_success'] == prior
    assert datetime.fromisoformat(value['next_retry_at']) > backup.now_utc()
    assert len(list((root / 'backups').glob('routine-*.base'))) == 1
    assert not list((root / 'backups').glob('routine-*.partial'))


def test_duplicate_backup_cannot_start_or_modify_health(cfg, monkeypatch):
    fake_database(monkeypatch, acquired=False)
    root = Path(cfg['root'])
    before = backup.status(root, 'running', started_at=backup.now_utc().isoformat())
    runner = Mock()
    monkeypatch.setattr(backup.subprocess, 'run', runner)
    with pytest.raises(RuntimeError, match='Another local backup'):
        backup.run_backup(cfg)
    assert backup.read_status(root) == before
    runner.assert_not_called()


def test_external_tablespaces_fail_closed(cfg, monkeypatch):
    fake_database(monkeypatch, tablespaces=[('external',)])
    with pytest.raises(RuntimeError, match='tablespaces'):
        backup.run_backup(cfg)


def test_application_role_cannot_be_reused_as_backup_role(cfg, monkeypatch):
    fake_database(monkeypatch)
    root = Path(cfg['root'])
    path = root / 'config' / 'backup-private.json'
    value = json.loads(path.read_text())
    value['username'] = 'polititrack_runtime'
    backup.atomic_json(path, value)
    with pytest.raises(ValueError, match='Dedicated loopback'):
        backup.run_backup(cfg)


def test_retention_keeps_two_verified_backups_and_migration_evidence(cfg):
    root = Path(cfg['root'])
    for day in ['18', '19', '20']:
        completed(root, 'routine-202609' + day + 'T120000Z-11111111.base')
    protected = root / 'backups' / 'local-cutover-basebackup'
    protected.mkdir()
    export = root / 'backups' / 'polititrack-final.sql.gz'
    export.write_bytes(b'protected export')
    backup.rotate(root / 'backups')
    assert len(list((root / 'backups').glob('routine-*.base'))) == 2
    assert protected.is_dir() and export.read_bytes() == b'protected export'


def test_invalid_receipt_stops_retention(cfg):
    root = Path(cfg['root'])
    receipt = completed(root, 'routine-20260920T120000Z-11111111.base')
    (root / 'backups' / receipt['directory'] / 'backup_manifest').write_bytes(b'changed')
    with pytest.raises(ValueError, match='does not match'):
        backup.rotate(root / 'backups')
    assert (root / 'backups' / receipt['directory']).exists()


def test_backup_process_is_not_awaited_by_scheduler(cfg, monkeypatch):
    child = Mock(pid=1234)
    child.poll.return_value = None
    spawn = Mock(return_value=child)
    monkeypatch.setattr(backup.subprocess, 'Popen', spawn)
    supervisor = backup.BackupSupervisor(cfg)
    supervisor.tick()
    for _ in range(10):
        supervisor.tick()
    spawn.assert_called_once()
    child.wait.assert_not_called()
    supervisor.output.close()


def test_worker_failure_is_contained_and_not_retried_immediately(cfg, monkeypatch):
    child = Mock(pid=1234)
    child.poll.return_value = 1
    spawn = Mock(return_value=child)
    monkeypatch.setattr(backup.subprocess, 'Popen', spawn)
    supervisor = backup.BackupSupervisor(cfg)
    supervisor.tick()
    supervisor.tick()
    supervisor.tick()
    assert backup.read_status(cfg['root'])['status'] == 'failed'
    spawn.assert_called_once()


def test_spawn_error_does_not_escape_to_producer_scheduler(cfg, monkeypatch):
    monkeypatch.setattr(backup.subprocess, 'Popen', Mock(side_effect=OSError('test')))
    supervisor = backup.BackupSupervisor(cfg)
    supervisor.tick()
    assert backup.read_status(cfg['root'])['status'] == 'failed'
    assert supervisor.output is None


def test_success_today_prevents_another_daily_backup(cfg, monkeypatch):
    root = Path(cfg['root'])
    backup.status(root, 'success', last_success={'completed_at': backup.now_utc().isoformat()})
    spawn = Mock()
    monkeypatch.setattr(backup.subprocess, 'Popen', spawn)
    backup.BackupSupervisor(cfg).tick()
    spawn.assert_not_called()


def test_persisted_backoff_survives_supervisor_restart(cfg, monkeypatch):
    backup.failure(cfg['root'], 'test failure')
    spawn = Mock()
    monkeypatch.setattr(backup.subprocess, 'Popen', spawn)
    backup.BackupSupervisor(cfg).tick()
    spawn.assert_not_called()


def test_backup_children_do_not_inherit_application_or_cloud_secrets(cfg, monkeypatch):
    for key in ['PGPASSWORD', 'DATABASE_URL', 'OPENAI_API_KEY', 'GOOGLE_APPLICATION_CREDENTIALS']:
        monkeypatch.setenv(key, 'never-inherit')
    environment = backup.clean_environment(cfg['root'])
    assert 'never-inherit' not in environment.values()
