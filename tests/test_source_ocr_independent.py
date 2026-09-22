"""Manual recovery shares one lease and cannot falsify collection freshness."""
from contextlib import contextmanager
from copy import deepcopy
import json
from types import SimpleNamespace
import pytest

from runtime_v2.runner import JobRunner
from runtime_v2.store import SnapshotHead
from runtime_v2 import source_uploads,source_ocr_worker
from test_source_ocr_runtime import source_state, FILING, evidence, ENV


def test_manual_only_pass_never_downloads_or_changes_automatic_backoff(tmp_path):
    from scripts import government_trade_tracker as tracker
    import hashlib
    directory=source_state(tmp_path)
    other={**FILING,'filing_key':'house:untouched','report_id':'untouched'}
    tracker.append_jsonl(directory/'filings.jsonl',[other])
    receipt={'filing_key':other['filing_key'],'source_url':other['source_url'],'status':'retry_delayed','attempts':3,'next_attempt_at':'2099-01-01T00:00:00Z'}
    tracker.append_jsonl(directory/'source-ocr.jsonl',[receipt])
    prefix=(directory/'source-ocr.jsonl').read_bytes()
    upload={'upload_id':'TEST-upload','filing_key':FILING['filing_key'],'source_url':FILING['source_url'],'status':'pending','payload':b'test','sha256':hashlib.sha256(b'test').hexdigest()}
    outcomes=source_ocr_worker.run_pass(directory,'legislative',ENV,[upload],manual_only=True,
        loader=lambda *_:pytest.fail('manual recovery downloaded an automatic source'),extractor=lambda b,**k:evidence(b))
    assert outcomes[0]['status']=='needs_review'
    assert (directory/'source-ocr.jsonl').read_bytes().startswith(prefix)
    assert not (directory/'transactions.jsonl').exists()
    assert tracker.latest_records(directory/'source-ocr.jsonl','filing_key')[other['filing_key']]==receipt


@pytest.mark.parametrize('failure',['collection','commit','cleanup','none'])
def test_manual_commit_survives_collection_outage_and_ack_is_after_commit(monkeypatch,failure):
    events=[]; committed=[]; current=['b'*64]
    class Lock:
        def restore(self,path):
            path.mkdir();(path/'state.json').write_text('{"last_success_utc":"2026-09-01T00:00:00Z"}')
            return SnapshotHead('executive',1,'before',current[0],'2026-09-01T00:00:00Z','a'*40,{})
        def start_run(self,job,*a):events.append(job);return job
        def record_ocr_health(self,run,metrics):pass
        def finish_run(self,run,**kw):events.append((run,kw['status']))
        def commit(self,path,**kw):
            assert kw['expected_parent_sha256']==current[0]
            if failure=='commit':raise RuntimeError('TEST commit failure')
            events.append('commit');committed.append((kw, json.loads((path/'state.json').read_text())))
            current[0]='c'*64 if len(committed)==1 else 'd'*64
            return SnapshotHead('executive',1+len(committed),'next',current[0],'2026-09-22T00:00:00Z','a'*40,{})
    class Store:
        @contextmanager
        def locked(self,namespace):
            assert namespace=='executive';events.append('lock');yield Lock();events.append('unlock')
    def ack(*a):
        events.append('ack')
        if failure=='cleanup':raise RuntimeError('TEST cleanup')
    uploads=SimpleNamespace(pending=lambda _: [{'TEST':'upload'}],acknowledge=ack)
    monkeypatch.setattr(source_uploads,'SourceUploadStore',lambda:uploads)
    def manual_pass(path,*a,**kw):
        if kw.get('manual_only'):
            events.append('manual');(path/'manual-proof.json').write_text('{"TEST":true}')
            return [{'TEST':'outcome'}]
        return []
    monkeypatch.setattr(source_ocr_worker,'run_pass',manual_pass)
    runner=JobRunner(Store(),source_revision='a'*40,environment={**ENV,'RUNTIME_SOURCE_OCR_ENABLED':'true'})
    def execute(args):
        events.append('collect')
        if failure=='collection':raise RuntimeError('TEST OGE outage')
    monkeypatch.setattr(runner,'_execute',execute)
    monkeypatch.setattr(runner,'_prepare_notifications',lambda *a:None)
    monkeypatch.setattr(runner,'_notification_commit_options',lambda *a:({},{}))
    monkeypatch.setattr(runner,'_dispatch_notifications',lambda *a:None)
    if failure in ('collection','commit'):
        with pytest.raises(RuntimeError):runner.run('executive')
    else:runner.run('executive')
    if failure=='commit':
        assert not committed and 'ack' not in events and 'collect' not in events
    else:
        assert events.index('manual') < events.index('commit') < events.index('ack') < events.index('collect')
        assert committed[0][0]['provenance']['job']=='executive_manual_ocr'
        assert committed[0][0]['provenance']['collection_performed'] is False
        assert committed[0][1]['last_success_utc']=='2026-09-01T00:00:00Z'
        if failure=='collection':
            assert len(committed)==1 and ('executive','failure') in events
        else:assert len(committed)==2
    assert events.count('lock')==1


def test_postgres_manual_receipt_is_not_collector_success_and_replay_is_unique(tmp_path,monkeypatch):
    import uuid,hashlib
    from pathlib import Path
    from runtime_v2.store import LockedNamespace,PostgresSnapshotStore
    from test_runtime_v2_mode_quarantine import _postgres_connection
    from scripts import government_trade_tracker as tracker
    connection=_postgres_connection();cursor=connection.cursor()
    schema='manual_ocr_'+uuid.uuid4().hex
    try:
        cursor.execute('CREATE SCHEMA "'+schema+'"');cursor.execute('SET search_path TO "'+schema+'"')
        cursor.execute((Path(__file__).resolve().parents[1]/'migrations/20260904_runtime_v2_mode_quarantine.sql').read_text())
        locked=LockedNamespace(connection,'executive')
        directory=source_state(tmp_path)
        filing={**FILING,'branch':'executive','source':'oge'}
        tracker.append_jsonl(directory/'filings.jsonl',[filing])
        seed=locked.start_run('executive','external_scheduler','a'*40,'production')
        baseline=locked.commit(directory,expected_parent_sha256=None,allow_initial=True,successful_run_id=seed,source_revision='a'*40,
            provenance={'authority':'runtime_v2','job':'executive','mode':'production','trigger_source':'external_scheduler'})
        upload={'upload_id':str(uuid.uuid4()),'filing_key':filing['filing_key'],'source_url':filing['source_url'],'status':'pending','payload':b'test','sha256':hashlib.sha256(b'test').hexdigest()}
        ack=[]
        monkeypatch.setattr(source_uploads,'SourceUploadStore',lambda:SimpleNamespace(pending=lambda _:[upload],acknowledge=lambda *a:ack.append(a)))
        original=source_ocr_worker.run_pass
        monkeypatch.setattr(source_ocr_worker,'run_pass',lambda *a,**kw:original(*a,**kw,extractor=lambda b,**_:evidence(b)))
        runner=JobRunner(object(),source_revision='b'*40,environment={**ENV,'RUNTIME_SOURCE_OCR_ENABLED':'true'})
        first=runner._manual_upload_pass(locked,'executive',directory,baseline,'external_scheduler')
        second=runner._manual_upload_pass(locked,'executive',directory,first,'external_scheduler')
        assert second.generation==first.generation+1 and second.snapshot_sha256!=first.snapshot_sha256
        assert len(ack)==2
        assert len(tracker.read_jsonl(directory/'source-ocr.jsonl'))==1
        assert not (directory/'transactions.jsonl').exists()
        failed=locked.start_run('executive','external_scheduler','b'*40,'production')
        locked.finish_run(failed,status='failure',error_code='CalledProcessError')
        history=PostgresSnapshotStore._successful_history(cursor,'executive')
        assert len(history)==1 and history[0]['run_id']==seed
        class ConnectionProxy:
            def __getattr__(self,key):return getattr(connection,key)
            def close(self):pass
        store=object.__new__(PostgresSnapshotStore)
        monkeypatch.setattr(store,'_connect',lambda:ConnectionProxy())
        branch=store.workflow_evidence()['branches']['executive']
        assert branch['attempts'][0]['run_id']==failed
        assert len(branch['manual_upload_attempts'])==2
        assert all(a['conclusion']=='success' for a in branch['manual_upload_attempts'])
        from scripts.dashboard_insights import _health
        from datetime import datetime,timezone
        health,_=_health([],[],datetime.now(timezone.utc),{'available':True,'branches':{'executive':branch}})
        executive=next(b for b in health['branches'] if b['branch']=='executive')
        assert executive['status']=='failure'
        assert executive['source_ocr']['manual_uploads']['committed_pass'] is True
    finally:
        cursor.execute('SET search_path TO public');cursor.execute('DROP SCHEMA IF EXISTS "'+schema+'" CASCADE')
        cursor.close();connection.close()
