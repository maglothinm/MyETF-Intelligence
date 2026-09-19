"""Offline recovery/continuation checks: no GCP, credentials or production data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    'ocr_controller', Path(__file__).parents[1] / 'scripts/ocr_release_controller.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def snapshot(folder):
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in folder.rglob('*') if p.is_file()}


@pytest.fixture
def recovered(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('An offline recovery check attempted a cloud action')
    monkeypatch.setattr(c.subprocess, 'run', forbidden)
    monkeypatch.setattr(c.urllib.request, 'urlopen', forbidden)
    state = {
        'release_id': 'a' * 32, 'source': c.SOURCE, 'image': c.IMAGE,
        'status': 'recovered_original_configuration', 'steps': {},
        'producer_submission_started': False, 'schedules_restored': True,
        'recovery_reason': 'execution_inventory_unavailable_before_any_deployment_submission',
        'recovered_at': '2026-09-18T15:44:14+00:00',
        'paused': ['polititrack-' + p for p in c.PRODUCERS],
        'last_schedule_observation': {'states': {
            **{'polititrack-' + p: 'ENABLED' for p in c.PRODUCERS},
            'polititrack-vault-lifecycle': 'PAUSED'}},
        'last_wait': 'retained original failure',
    }
    folder = tmp_path / 'ocr-deployment'
    folder.mkdir()
    c.save(folder / 'journal.json', state)
    c.save(folder / 'journal-before-controller-v2.json', {'original': True})
    c.save(folder / 'cloud' / 'restored-schedules.json', state['last_schedule_observation'])
    for name in c.RESOURCES:
        c.save(tmp_path / (name + '.json'), {'name': name})
    c.save(tmp_path / 'schedules.json', [])
    return tmp_path


def digest(workspace):
    return hashlib.sha256((workspace / 'ocr-deployment/journal.json').read_bytes()).hexdigest()


def mutate(workspace, key, value):
    path = workspace / 'ocr-deployment/journal.json'
    state = c.load(path)
    state[key] = value
    c.save(path, state)


def test_review_is_read_only_and_retains_failure(recovered):
    before = snapshot(recovered)
    review = c.recovery_review(recovered, digest(recovered))
    assert review['files']['journal.json'] == digest(recovered)
    assert len(review['files']) == 3
    assert snapshot(recovered) == before


@pytest.mark.parametrize(('key', 'value'), [
    ('status', 'maintenance'), ('status', 'recovered_new_image_ocr_disabled'),
    ('source', 'different'), ('image', 'different'),
    ('steps', {'migration': {'requested': True}}), ('steps', None),
    ('producer_submission_started', True), ('producer_submission_started', None),
    ('schedules_restored', False), ('schedules_restored', 1),
    ('recovery_reason', 'different'), ('recovered_at', ''),
    ('installation_verified', True), ('activation_verified', True),
    ('acceptance_verified', True), ('recovery_error', 'unresolved'),
    ('last_schedule_observation', {'states': {}}), ('paused', []),
    ('release_id', '../escape'),
])
def test_uncertain_or_different_recovery_is_rejected(recovered, key, value):
    mutate(recovered, key, value)
    before = snapshot(recovered)
    with pytest.raises(c.Stop):
        c.recovery_review(recovered)
    assert snapshot(recovered) == before


def test_previous_baseline_requires_separate_review(recovered):
    c.save(recovered / 'ocr-deployment/baseline-receipt.json', {})
    with pytest.raises(c.Stop, match='baseline'):
        c.recovery_review(recovered)


@pytest.mark.parametrize('expected', ['0' * 64, '../wrong', 'A' * 64, ''])
def test_exact_review_hash_required(recovered, expected):
    with pytest.raises(c.Stop):
        c.continuation_location(recovered, expected)
    assert not (recovered / 'ocr-continuations').exists()


def test_successor_is_fresh_and_resumes_one_identity(recovered):
    before = snapshot(recovered / 'ocr-deployment')
    predecessor = c.recovery_review(recovered)
    first = c.Release(recovered, None, predecessor=predecessor)
    assert first.folder == recovered / 'ocr-continuations' / ('a' * 32)
    assert first.state['status'] == 'preparing'
    assert first.state['paused'] == [] and first.state['steps'] == {}
    assert first.state['producer_submission_started'] is False
    assert 'last_wait' not in first.state and 'roles' not in first.state
    first.state['steps']['observe-only'] = {'execution': 'retained'}
    first.persist()
    second = c.Release(recovered, None, predecessor=predecessor)
    assert second.state['release_id'] == first.state['release_id']
    assert second.state['steps'] == first.state['steps']
    assert snapshot(recovered / 'ocr-deployment') == before


def test_successor_must_pass_fresh_preflight_before_pause(recovered, monkeypatch):
    release = c.Release(recovered, None, predecessor=c.recovery_review(recovered))
    actions = []
    def preflight():
        actions.append('preflight')
        raise c.Stop('fresh check failed')
    monkeypatch.setattr(release, 'preflight', preflight)
    monkeypatch.setattr(release, 'pause', lambda: actions.append('pause'))
    with pytest.raises(c.Stop, match='fresh check'):
        release.run()
    assert actions == ['preflight']


@pytest.mark.parametrize('change', ['journal', 'receipt', 'new_receipt'])
def test_predecessor_drift_blocks_successor_writes(recovered, change):
    release = c.Release(recovered, None, predecessor=c.recovery_review(recovered))
    before = release.path.read_bytes()
    if change == 'journal':
        mutate(recovered, 'last_wait', 'changed')
    elif change == 'receipt':
        (recovered / 'ocr-deployment/cloud/restored-schedules.json').write_text('{}')
    else:
        (recovered / 'ocr-deployment/new-evidence.json').write_text('{}')
    release.state['status'] = 'ready'
    with pytest.raises(c.Stop):
        release.persist()
    assert release.path.read_bytes() == before


def test_closed_successor_cannot_start_another_attempt(recovered):
    predecessor = c.recovery_review(recovered)
    release = c.Release(recovered, None, predecessor=predecessor)
    release.state['status'] = 'stopped_before_maintenance'
    release.persist()
    before = snapshot(recovered)
    with pytest.raises(c.Stop, match='closed'):
        c.Release(recovered, None, predecessor=predecessor)
    assert snapshot(recovered) == before


def test_orphaned_successor_evidence_is_not_reinitialized(recovered):
    folder, predecessor = c.continuation_location(recovered, digest(recovered))
    folder.mkdir(parents=True)
    (folder / 'receipt.json').write_text('{}')
    with pytest.raises(c.Stop, match='missing'):
        c.Release(recovered, None, predecessor=predecessor)
    assert not (folder / 'journal.json').exists()


@pytest.mark.parametrize('target', ['ocr-continuations', 'ocr-deployment/linked-receipt'])
def test_symlink_paths_are_rejected(recovered, target, tmp_path_factory):
    (recovered / target).symlink_to(tmp_path_factory.mktemp('outside'), target_is_directory=True)
    with pytest.raises(c.Stop, match='[Ll]inked'):
        c.continuation_location(recovered, digest(recovered))


@pytest.mark.parametrize('mode', ['--deploy', '--recover', '--status', '--review-recovered'])
def test_closed_cli_cannot_load_audit_mutate_journal_or_recover(recovered, monkeypatch, mode):
    before = snapshot(recovered / 'ocr-deployment')
    monkeypatch.setattr(sys, 'argv', ['controller', '--workspace', str(recovered), mode])
    monkeypatch.setattr(c, 'load_audit_module', lambda: pytest.fail('loaded deployment machinery'))
    monkeypatch.setattr(c.Release, 'recover', lambda self: pytest.fail('recovered a closed attempt'))
    if mode in ('--deploy', '--recover'):
        with pytest.raises(c.Stop, match='closed'):
            c.main()
    else:
        assert c.main() == 0
    assert snapshot(recovered / 'ocr-deployment') == before


def test_new_attempt_uses_existing_workspace_lock(recovered, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['controller', '--workspace', str(recovered), '--deploy',
                                    '--continue-recovered', digest(recovered)])
    with (recovered / '.ocr-deployment.lock').open('a') as lock:
        c.fcntl.flock(lock, c.fcntl.LOCK_EX | c.fcntl.LOCK_NB)
        with pytest.raises(c.Stop, match='lock'):
            c.main()
    assert not (recovered / 'ocr-continuations').exists()


@pytest.mark.parametrize('mode', ['--status', '--recover'])
def test_observation_and_recovery_cannot_create_a_successor(recovered, monkeypatch, mode):
    monkeypatch.setattr(sys, 'argv', ['controller', '--workspace', str(recovered), mode,
                                    '--continue-recovered', digest(recovered)])
    with pytest.raises(c.Stop, match='will not create'):
        c.main()
    assert not (recovered / 'ocr-continuations').exists()


def test_fresh_inventory_pause_drain_and_baseline_order(recovered, monkeypatch):
    release = c.Release(recovered, None, predecessor=c.recovery_review(recovered))
    actions = []
    def preflight():
        actions.append('preflight')
        release.state['status'] = 'ready'
    def audit(key, **kwargs):
        actions.append((key, kwargs))
        raise c.Stop('test stops at fresh frozen baseline')
    monkeypatch.setattr(release, 'preflight', preflight)
    monkeypatch.setattr(release, 'active', lambda **kwargs: actions.append(('inventory', kwargs)))
    monkeypatch.setattr(release, 'pause', lambda: actions.append('pause'))
    monkeypatch.setattr(release, 'drain', lambda: actions.append('drain'))
    monkeypatch.setattr(release, 'audit', audit)
    with pytest.raises(c.Stop, match='test stops'):
        release.run()
    assert actions == ['preflight', ('inventory', {'include_admin': True}), 'pause', 'drain',
                       ('baseline', {'old_image': True})]
