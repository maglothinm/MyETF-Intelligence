from __future__ import annotations

import copy
import json
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from runtime_v2 import legislative_recovery as recovery
from runtime_v2.notifications import DeliveryRejected, NotificationDispatcher, _known_no_delivery
from runtime_v2.runner import JobRunner
from runtime_v2.store import LockedNamespace, PostgresSnapshotStore, SnapshotHead, NamespaceBusy, StateStoreError
from scripts import runtime_notifications as intents

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f' * 40
CREDENTIALS = {'PUSHOVER_API_TOKEN': 'test-token', 'PUSHOVER_USER_KEY': 'test-user'}
PAYLOAD = {'title': 'Test filing', 'message': 'A new filing', 'url': '', 'url_title': ''}


def intent(key, day='2026-09-09', namespace='legislative', channel='pushover'):
    return {'schema_version': 1, 'namespace': namespace, 'channel': channel,
            'record_key': key, 'delivery_id': intents.delivery_id(namespace, channel, key),
            'available_on': day, 'payload': dict(PAYLOAD)}


def staging(monkeypatch, tmp_path, namespace='legislative'):
    path = tmp_path / 'notification-intents.jsonl'
    monkeypatch.setenv(intents.MODE_KEY, intents.CONTRACT)
    monkeypatch.setenv(intents.PATH_KEY, str(path))
    monkeypatch.setenv(intents.NAMESPACE_KEY, namespace)
    return path


def test_exact_incident_evidence_is_optional_for_collection_but_required_for_exemption(monkeypatch, tmp_path):
    receipt = recovery.load_receipt(recovery.CASE)
    original = copy.deepcopy(receipt['failed_run'])
    assert original['side_effects_possible'] is True
    assert receipt['accepted_parent']['generation'] == 232
    assert _known_no_delivery(original)['receipt_sha256'] == recovery.RECEIPT_SHA256
    assert receipt['failed_run'] == original
    for field in ('run_id', 'source_revision', 'runtime_mode_evidence', 'finished_at'):
        changed = {**original, field: 'changed'}
        assert _known_no_delivery(changed) is None
    path = tmp_path / 'tampered.json'
    path.write_text('{"approved":true}')
    monkeypatch.setattr(recovery, 'RECEIPT_PATH', path)
    assert _known_no_delivery(original) is None
    with pytest.raises(StateStoreError, match='digest mismatch'):
        recovery.load_receipt(recovery.CASE)


@pytest.mark.parametrize('namespace', ['legislative', 'executive'])
def test_actual_tracker_stages_without_external_delivery(monkeypatch, tmp_path, namespace):
    from scripts import government_trade_tracker_core as tracker
    from test_government_trade_tracker import _tracker_config
    path = staging(monkeypatch, tmp_path, namespace)
    cfg = replace(_tracker_config(tmp_path, initialize=False), no_notify=False,
                  pushover_api_token='token', pushover_user_key='user')
    class NoNetwork:
        def post(self, *args, **kwargs):
            raise AssertionError('collection attempted external notification')
    accepted = tracker._pushover_post(NoNetwork(), cfg, **PAYLOAD, notification_key='filing-1', filed_date='09/09/2026')
    assert accepted is False
    assert intents.read_intents(path, namespace) == [intent('filing-1', namespace=namespace)]
    cfg = replace(cfg, pushover_api_token='', pushover_user_key='')
    assert tracker._pushover_post(NoNetwork(), cfg, **PAYLOAD, notification_key='without-credentials') is False
    assert len(intents.read_intents(path, namespace)) == 1


@pytest.mark.parametrize('with_credentials', [True, False])
def test_ai_queues_channels_without_claiming_delivery_and_has_stable_retry_identity(monkeypatch, tmp_path, with_credentials):
    from scripts import ai_filing_analyst as entrypoint
    from scripts import ai_filing_analyst_hardened as ai
    assert entrypoint.run_analyst is ai.run_analyst
    from test_ai_filing_analyst_hardened import _config
    path = staging(monkeypatch, tmp_path, 'ai')
    cfg = replace(_config(tmp_path), suppress_alerts=False, require_pushover=True,
                  pushover_api_token='token' if with_credentials else '',
                  pushover_user_key='user' if with_credentials else '')
    delivery = {'trade_id': 'trade', 'analysis_id': 'analysis', 'analysis_revision': 1,
                'filed_date': '2026-09-09', 'requested_channels': ['pushover', 'gmail'],
                'delivered_channels': {}, 'alert': dict(PAYLOAD)}
    state = ai.legacy.AIState(candidate_alert_deliveries={'local-attempt-1': copy.deepcopy(delivery)})
    state_path = cfg.ai_dir / 'state.json'
    state_path.parent.mkdir(parents=True)
    def no_send(*args, **kwargs):
        raise AssertionError('AI collection attempted external delivery')
    monkeypatch.setattr(ai.legacy, '_notification_post', no_send)
    monkeypatch.setattr(ai, '_send_candidate_email_with_evidence', no_send)
    result = ai.AnalystRunResult(started_utc=ai.legacy.iso_utc())
    ai._deliver_pending_candidate_alerts(cfg, result, state, state_path)
    rows = intents.read_intents(path, 'ai')
    assert {r['channel'] for r in rows} == {'gmail', 'pushover'}
    assert state.candidate_alert_deliveries['local-attempt-1']['delivered_channels'] == {}
    assert not result.delivery_phase_started
    ai._deliver_pending_candidate_alerts(cfg, result, state, state_path)
    assert intents.read_intents(path, 'ai') == rows
    # A retry with a different local attempt/timestamp is the same durable send.
    state.candidate_alert_deliveries['local-attempt-2'] = copy.deepcopy(delivery)
    ai._deliver_pending_candidate_alerts(cfg, result, state, state_path)
    repeated = intents.read_intents(path, 'ai')[2:]
    assert {r['delivery_id'] for r in repeated} == {r['delivery_id'] for r in rows}
    state.candidate_alert_deliveries['new-revision'] = {**copy.deepcopy(delivery), 'analysis_revision': 2}
    ai._deliver_pending_candidate_alerts(cfg, result, state, state_path)
    assert len({r['delivery_id'] for r in intents.read_intents(path, 'ai')}) == 4


@pytest.mark.parametrize('runtime_mode', [True, False])
def test_required_notification_credentials_do_not_gate_runtime_collection(monkeypatch, tmp_path, runtime_mode):
    from scripts import government_trade_tracker_core as tracker
    from test_government_trade_tracker import _tracker_config
    cfg=replace(_tracker_config(tmp_path,initialize=False),no_notify=False,require_pushover=True)
    tracker.save_state(cfg.state_path,tracker.TrackerState())
    if runtime_mode:
        path=staging(monkeypatch,tmp_path,'executive')
    else:
        monkeypatch.delenv(intents.MODE_KEY,raising=False)
    collected=[]
    class NoNetwork:
        def post(self,*args,**kwargs):
            pytest.fail('missing credentials must never reach provider')
    def collect(config,state,result,session,filing_index):
        collected.append(True)
        assert tracker._pushover_post(session,config,**PAYLOAD,notification_key='new-filing',filed_date='2026-09-09') is False
    monkeypatch.setattr(tracker,'run_executive',collect)
    if runtime_mode:
        result=tracker.run_tracker(cfg,session=NoNetwork())
        assert result.success and collected==[True]
        assert intents.read_intents(path,'executive') == [intent('new-filing',namespace='executive')]
    else:
        with pytest.raises(tracker.NotificationError,match='REQUIRE_PUSHOVER'):
            tracker.run_tracker(cfg,session=NoNetwork())
        assert not collected


@pytest.mark.parametrize('field,value', [('namespace','ai'), ('delivery_id','bad'), ('available_on','yesterday'), ('payload',{'token':'secret'})])
def test_staged_identity_or_payload_corruption_is_rejected(field, value):
    with pytest.raises(ValueError):
        intents.validate_intent({**intent('filing'), field: value}, 'legislative')


class RunLock:
    def __init__(self, namespace):
        self.namespace = namespace
        self.prepared = 0
        self.started, self.finished, self.committed = [], [], []

    def prepare_notification_delivery(self):
        self.prepared += 1

    def restore(self, path):
        path.mkdir(parents=True)
        (path / 'state.json').write_text('{"last_success_utc":"2026-09-08T10:25:04Z"}')
        return SnapshotHead(self.namespace, 232, 'parent', 'a'*64, '', REVISION, {})

    def start_run(self, *args):
        self.started.append(args)
        return str(uuid.uuid4())

    def finish_run(self, run_id, **kwargs):
        self.finished.append((run_id, kwargs))

    def commit(self, source, **kwargs):
        self.committed.append(kwargs)
        return SnapshotHead(self.namespace, 233, 'successor', 'b'*64, '', REVISION, kwargs['provenance'])


class RunStore:
    def __init__(self, namespace):
        self.lock = RunLock(namespace)

    @contextmanager
    def locked(self, namespace):
        yield self.lock

    def restore_latest(self, namespace, path):
        return RunLock(namespace).restore(path)


@pytest.mark.parametrize('namespace', ['legislative', 'executive', 'ai'])
@pytest.mark.parametrize('failures', [1, 3])
@pytest.mark.parametrize('credentials', [{}, CREDENTIALS])
def test_failures_do_not_latch_later_scheduled_collection(monkeypatch, namespace, failures, credentials):
    store = RunStore(namespace)
    def runner():
        return JobRunner(store, source_revision=REVISION, environment={'POLITITRACK_MODE':'production', **credentials})
    for _ in range(failures):
        failed = runner()
        def fail(command):
            assert failed._env()[intents.MODE_KEY] == intents.CONTRACT
            raise RuntimeError('collection unavailable')
        monkeypatch.setattr(failed, '_execute', fail)
        with pytest.raises(RuntimeError, match='collection unavailable'):
            failed.run(namespace)
    assert not store.lock.committed
    assert len(store.lock.finished) == failures
    assert all(row[1]['side_effects_possible'] is False for row in store.lock.finished)
    successful = runner()  # New process equivalent: no in-memory retry permission.
    commands = []
    monkeypatch.setattr(successful, '_execute', lambda command: commands.append(command))
    monkeypatch.setattr(successful, '_dispatch_notifications', lambda *args: None)
    head = successful.run(namespace)
    assert head.generation == 233
    assert store.lock.prepared == failures + 1
    assert store.lock.committed[0]['expected_parent_sha256'] == 'a'*64
    assert store.lock.committed[0]['notification_intents'] == []
    if namespace == 'legislative':
        assert '--source' in commands[0] and 'all' in commands[0]
        assert '--validate-only' in commands[1]


def test_complete_source_failure_never_publishes_staged_intents(monkeypatch):
    store = RunStore('legislative')
    runner = JobRunner(store, source_revision=REVISION, environment={'POLITITRACK_MODE':'production', **CREDENTIALS})
    def execute(command):
        if '--validate-only' in command:
            raise RuntimeError('Senate source incomplete')
        path = Path(runner._env()[intents.PATH_KEY])
        path.write_text(json.dumps(intent('would-have-sent')) + '\n')
    monkeypatch.setattr(runner, '_execute', execute)
    with pytest.raises(RuntimeError, match='source incomplete'):
        runner.run('legislative')
    assert store.lock.committed == []
    assert store.lock.finished[0][1]['side_effects_possible'] is False


def test_delivery_infrastructure_failure_cannot_reclassify_success(monkeypatch, capsys):
    store = RunStore('legislative')
    store.lock.connection = object()
    runner = JobRunner(store, source_revision=REVISION, environment={'POLITITRACK_MODE':'production', **CREDENTIALS})
    monkeypatch.setattr(runner, '_execute', lambda command: None)
    monkeypatch.setattr(NotificationDispatcher, 'dispatch', lambda self: (_ for _ in ()).throw(RuntimeError('database disconnected')))
    assert runner.run('legislative').generation == 233
    assert len(store.lock.committed) == 1 and store.lock.finished == []
    assert 'notification_delivery_deferred' in capsys.readouterr().out


@pytest.fixture
def pg():
    from test_runtime_v2_mode_quarantine import _postgres_connection
    connection = _postgres_connection()
    schema = 'notification_liveness_' + uuid.uuid4().hex
    def configure(conn):
        conn.cursor().execute(f'SET search_path TO "{schema}"')
        return conn
    connection.cursor().execute(f'CREATE SCHEMA "{schema}"')
    configure(connection)
    for name in ('20260904_runtime_v2_mode_quarantine.sql', '20260909_runtime_notification_outbox.sql'):
        connection.cursor().execute((ROOT / 'migrations' / name).read_text())
    try:
        yield connection, lambda: configure(_postgres_connection())
    finally:
        connection.rollback()
        connection.autocommit = True
        connection.cursor().execute(f'DROP SCHEMA "{schema}" CASCADE')
        connection.close()


def query(conn, sql, params=()):
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def seed_original(conn):
    receipt = recovery.load_receipt(recovery.CASE)
    parent = receipt['accepted_parent']
    cursor = conn.cursor()
    cursor.execute("INSERT INTO runtime_state_snapshots (snapshot_id,namespace,generation,snapshot_sha256,source_revision,manifest,payload,created_at) VALUES (%s::uuid,'legislative',232,%s,%s,'{}'::jsonb,%s,'2026-09-08T10:25:04Z')", (parent['snapshot_id'],parent['snapshot_sha256'],REVISION,b'original synthetic test payload'))
    cursor.execute("INSERT INTO runtime_state_heads VALUES ('legislative',232,%s::uuid,%s,'2026-09-08T10:25:04Z')",(parent['snapshot_id'],parent['snapshot_sha256']))
    cursor.execute('INSERT INTO runtime_job_runs SELECT * FROM jsonb_populate_record(NULL::runtime_job_runs,%s::jsonb)', (json.dumps(receipt['failed_run']),))
    cursor.close()
    return receipt


def publish(conn, tmp_path, namespace, rows):
    source = tmp_path / uuid.uuid4().hex
    source.mkdir()
    (source / 'state.json').write_text(json.dumps({'last_success_utc':'2026-09-09T15:00:00Z','revision':source.name}))
    locked = LockedNamespace(conn, namespace)
    locked.prepare_notification_delivery()
    parent = locked.head()
    run_id = locked.start_run(namespace, 'external_scheduler', REVISION, 'production')
    head = locked.commit(source, expected_parent_sha256=parent.snapshot_sha256 if parent else None,
                         source_revision=REVISION, allow_initial=parent is None,
                         provenance={'authority':'runtime_v2','job':namespace,'mode':'production','trigger_source':'external_scheduler'},
                         successful_run_id=run_id, notification_intents=rows)
    return head, run_id


def test_postgres_original_evidence_preserved_and_ambiguous_records_isolated(pg, tmp_path):
    conn, reconnect = pg
    receipt = seed_original(conn)
    original_runs = query(conn, 'SELECT to_jsonb(r) FROM runtime_job_runs r')
    original_snapshot = query(conn, 'SELECT to_jsonb(s) FROM runtime_state_snapshots s')
    # A second legacy run really is ambiguous; it must hold only its possible records.
    ambiguous = {**copy.deepcopy(receipt['failed_run']), 'run_id':str(uuid.uuid4()),
                 'started_at':'2026-09-08T11:00:00+00:00', 'finished_at':'2026-09-08T11:05:00+00:00'}
    conn.cursor().execute('INSERT INTO runtime_job_runs SELECT * FROM jsonb_populate_record(NULL::runtime_job_runs,%s::jsonb)',(json.dumps(ambiguous),))
    rows = [intent('old','2026-09-07'), intent('same-day','2026-09-08'), intent('unknown',None), intent('new','2026-09-09')]
    head, run_id = publish(conn, tmp_path, 'legislative', rows)
    assert head.generation == 233
    states = dict(query(conn,'SELECT record_key,status FROM runtime_notification_deliveries'))
    assert states == {'old':'legacy_held','same-day':'legacy_held','unknown':'legacy_held','new':'pending'}
    sent = []
    NotificationDispatcher(conn,'legislative',CREDENTIALS,send=lambda *a: sent.append(a) or True).dispatch()
    assert len(sent) == 1
    # Head has moved, process restarted: persistent legacy fence still scopes old records.
    restarted = reconnect()
    try:
        next_head, _ = publish(restarted,tmp_path,'legislative',rows + [intent('later','2026-09-10'), intent('late-old','2026-09-07')])
        assert next_head.generation == 234
        NotificationDispatcher(restarted,'legislative',CREDENTIALS,send=lambda *a: sent.append(a) or True).dispatch()
    finally:
        restarted.close()
    assert len(sent) == 2
    assert query(conn,'SELECT to_jsonb(r) FROM runtime_job_runs r WHERE run_id=%s::uuid',(receipt['failed_run']['run_id'],)) == original_runs
    assert query(conn,'SELECT to_jsonb(s) FROM runtime_state_snapshots s WHERE generation=232') == original_snapshot
    assert dict(query(conn,'SELECT failed_run_id::text,finding FROM runtime_notification_legacy_fences')) == {receipt['failed_run']['run_id']:'no_delivery',ambiguous['run_id']:'unresolved'}


@pytest.mark.parametrize('namespace',['legislative','executive','ai'])
def test_postgres_claim_crash_restart_new_alert_and_no_credentials(pg,tmp_path,namespace):
    conn,reconnect = pg
    first = intent('first',namespace=namespace)
    head, run_id = publish(conn,tmp_path,namespace,[first])
    sent=[]
    NotificationDispatcher(conn,namespace,{},send=lambda *a: sent.append(a)).dispatch()
    assert not sent
    assert query(conn,'SELECT status FROM runtime_notification_deliveries')[0][0] == 'pending'
    class ProcessDeath(BaseException):
        pass
    def die_after_acceptance(*args):
        # A separate connection sees the committed claim BEFORE the side effect.
        observer = reconnect()
        try:
            assert query(observer,'SELECT status FROM runtime_notification_deliveries')[0][0] == 'sending'
        finally:
            observer.close()
        sent.append(args)
        raise ProcessDeath()
    with pytest.raises(ProcessDeath):
        NotificationDispatcher(conn,namespace,CREDENTIALS,send=die_after_acceptance).dispatch()
    assert query(conn,'SELECT status FROM runtime_job_runs WHERE run_id=%s::uuid',(run_id,))[0][0] == 'success'
    restarted = reconnect()
    try:
        successor,_ = publish(restarted,tmp_path,namespace,[first,intent('fresh',namespace=namespace)])
        assert successor.generation == head.generation+1
        NotificationDispatcher(restarted,namespace,CREDENTIALS,send=lambda *a: sent.append(a) or True).dispatch()
        NotificationDispatcher(restarted,namespace,CREDENTIALS,send=lambda *a: sent.append(a) or True).dispatch()
    finally:
        restarted.close()
    assert len(sent) == 2
    assert dict(query(conn,'SELECT record_key,status FROM runtime_notification_deliveries')) == {'first':'uncertain','fresh':'accepted'}
    events=query(conn,'SELECT event_type FROM runtime_notification_events WHERE delivery_id=%s ORDER BY observed_at',(first['delivery_id'],))
    assert [r[0] for r in events] == ['pending','sending','uncertain']


def test_postgres_invalid_intent_rolls_back_snapshot_head_and_queue(pg,tmp_path):
    conn,_ = pg
    head,_ = publish(conn,tmp_path,'legislative',[])
    before = query(conn,'SELECT to_jsonb(h) FROM runtime_state_heads h')
    with pytest.raises(ValueError):
        publish(conn,tmp_path,'legislative',[intent('valid'),{**intent('corrupt'),'delivery_id':'bad'}])
    assert query(conn,'SELECT to_jsonb(h) FROM runtime_state_heads h') == before
    assert not query(conn,'SELECT * FROM runtime_notification_deliveries')
    assert query(conn,'SELECT count(*) FROM runtime_state_snapshots')[0][0] == 1


def test_postgres_writer_lock_excludes_concurrent_collection_and_claims(pg,tmp_path,monkeypatch):
    conn,reconnect = pg
    store = object.__new__(PostgresSnapshotStore)
    monkeypatch.setattr(store,'_connect',reconnect)
    with store.locked('legislative') as first:
        publish(first.connection,tmp_path,'legislative',[intent('one')])
        with pytest.raises(NamespaceBusy):
            with store.locked('legislative'):
                pytest.fail('second writer acquired same namespace')
        assert NotificationDispatcher(first.connection,'legislative',CREDENTIALS,send=lambda *a: True).dispatch()['accepted'] == 1
    with store.locked('legislative') as later:
        assert NotificationDispatcher(later.connection,'legislative',CREDENTIALS,send=lambda *a: pytest.fail('duplicate send')).dispatch()['accepted'] == 0


@pytest.mark.parametrize('namespace',['legislative','executive','ai'])
def test_postgres_multiple_failed_runs_preserved_across_success_and_restart(pg,tmp_path,namespace):
    conn,reconnect = pg
    parent,_ = publish(conn,tmp_path,namespace,[])
    locked = LockedNamespace(conn,namespace)
    ids = []
    for _ in range(3):
        run_id = locked.start_run(namespace,'external_scheduler',REVISION,'production')
        locked.finish_run(run_id,status='failure',error_code='SourceUnavailable',side_effects_possible=False)
        ids.append(run_id)
    failures = query(conn,"SELECT to_jsonb(r) FROM runtime_job_runs r WHERE status='failure' ORDER BY started_at")
    restarted = reconnect()
    try:
        head,_ = publish(restarted,tmp_path,namespace,[intent('fresh',namespace=namespace)])
        assert head.generation == parent.generation + 1
        assert NotificationDispatcher(restarted,namespace,CREDENTIALS,send=lambda *a: True).dispatch()['accepted'] == 1
    finally:
        restarted.close()
    assert query(conn,"SELECT to_jsonb(r) FROM runtime_job_runs r WHERE status='failure' ORDER BY started_at") == failures
    assert not query(conn,'SELECT * FROM runtime_notification_legacy_fences')
    assert query(conn,'SELECT count(*) FROM runtime_state_snapshots WHERE snapshot_id=%s::uuid',(parent.snapshot_id,))[0][0] == 1


def test_postgres_transport_failures_are_individual_and_new_records_deliver(pg,tmp_path):
    conn,_ = pg
    publish(conn,tmp_path,'legislative',[intent('rejection'),intent('timeout'),intent('accepted')])
    seen=[]
    def send(channel,payload,environment):
        seen.append(payload['message'])
        if len(seen) == 1:
            raise DeliveryRejected('provider says no')
        if len(seen) == 2:
            raise TimeoutError('could have accepted')
        return True
    counts=NotificationDispatcher(conn,'legislative',CREDENTIALS,send=send).dispatch()
    assert counts == {'accepted':1,'uncertain':1,'rejected':1}
    publish(conn,tmp_path,'legislative',[intent('fresh')])
    assert NotificationDispatcher(conn,'legislative',CREDENTIALS,send=lambda *a: True).dispatch()['accepted'] == 1
    assert query(conn,"SELECT count(*) FROM runtime_job_runs WHERE status='success'")[0][0] == 2
