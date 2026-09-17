"""Private intake, source producer reconciliation and crash/replay invariants."""
import copy
import hashlib
import io
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine, event, select, text

from runtime_v2.source_uploads import SourceUploadStore, uploads
from runtime_v2.review_accounts import ReviewError
from runtime_v2.source_ocr_worker import run_pass, OfficialSession
from scripts import government_trade_tracker as tracker
from scripts.source_ocr import VERSION, OCRError, AMOUNTS

NOW=datetime(2026,9,17,14,tzinfo=timezone.utc)
ENV={"DISCLOSURE_TERMS_ACKNOWLEDGED":"true","POLITITRACK_MODE":"production"}
FILING={"filing_key":"house:source-ocr-test", "branch":"legislative","source":"house","report_id":"source-ocr-test",
        "filer":"Diana Harshbarger","filed_date":"2026-09-11","first_seen_utc":"2026-09-11T14:00:00Z",
        "status":"review_required","source_url":"https://disclosures-clerk.house.gov/test.pdf", "document_format":"pdf"}
ROW={"page":1,"row":1,"asset":"School district bond", "owner":"","ticker":"","transaction_type":"Sale",
     "transaction_date":"2026-07-30","notification_date":"2026-08-19","amount":AMOUNTS[1],"issues":[]}


def evidence(data=b"test"):
    return {"sha256":hashlib.sha256(data).hexdigest(),"version":VERSION,"format":"pdf","page_count":1,
        "completed_pages":[1],"ocr_completed_at":"2026-09-17T14:00:00Z","native_pages":[""],
        "ocr_text":"Diana Harshbarger HOUSE OF REPRESENTATIVES TRANSACTION", "words":[],
        "house_table":{"recognized":True,"rows":[ROW, {**ROW,"row":2}],"problems":[]}, "ocr_status":"complete"}


def source_state(tmp_path):
    directory=tmp_path/"state";directory.mkdir()
    state=tracker.TrackerState(last_success_utc="2026-09-17T13:00:00Z")
    state.seen_filings["house"][FILING["report_id"]]=FILING["first_seen_utc"]
    state.seen_reviews["original-review-id"]="2026-09-11T15:00:00Z"
    tracker.save_state(directory/"state.json",state)
    tracker.append_jsonl(directory/"filings.jsonl",[FILING])
    tracker.append_jsonl(directory/"pending-review.jsonl",[{"review_id":"original-review-id","source":"house","report_id":FILING["report_id"]}])
    return directory


def test_seen_review_filing_gets_ocr_backfill_no_duplicates_no_seen_timestamp_rewrite(tmp_path):
    directory=source_state(tmp_path)
    before=(directory/"pending-review.jsonl").read_bytes()
    calls=[]
    def engine(data,**_):calls.append(1);return evidence(data)
    run_pass(directory,"legislative",ENV,loader=lambda *_:b"test",extractor=engine)
    rows=tracker.read_jsonl(directory/"transactions.jsonl")
    assert len(rows)==2 and rows[0]["trade_id"]!=rows[1]["trade_id"]
    assert all(row["historical_bootstrap"] and row["owner"]=="" and not row["equity_like"] for row in rows)
    state,_=tracker.load_state(directory/"state.json")
    assert state.seen_filings["house"][FILING["report_id"]]==FILING["first_seen_utc"]
    assert state.seen_reviews["original-review-id"]=="2026-09-11T15:00:00Z"
    assert (directory/"pending-review.jsonl").read_bytes()==before
    run_pass(directory,"legislative",ENV,loader=lambda *_:pytest.fail("unchanged completed document polled too early"),extractor=engine)
    assert calls==[1]
    assert len(tracker.read_jsonl(directory/"transactions.jsonl"))==2


def test_upload_requires_owner_confirmation_and_replays_postcommit_ack(tmp_path):
    directory=source_state(tmp_path)
    upload={"upload_id":str(uuid.uuid4()),"source_url":FILING["source_url"],"filing_key":FILING["filing_key"],
            "payload":b"test","sha256":hashlib.sha256(b"test").hexdigest(),"status":"pending"}
    engine=lambda data,**_:evidence(data)
    outcome=run_pass(directory,"legislative",ENV,[upload],extractor=engine)
    assert outcome[0]["status"]=="needs_review"
    assert not (directory/"transactions.jsonl").exists()
    replay=run_pass(directory,"legislative",ENV,[upload],extractor=lambda *_args,**_kwargs:pytest.fail("OCR repeated after committed receipt"))
    assert replay==outcome
    approved={**upload,"payload":None,"status":"approved","result":json.dumps({"approved_rows":evidence()["house_table"]["rows"]})}
    outcome=run_pass(directory,"legislative",ENV,[approved],extractor=engine)
    assert outcome[0]["status"]=="complete"
    assert len(tracker.read_jsonl(directory/"transactions.jsonl"))==2
    assert run_pass(directory,"legislative",ENV,[approved],extractor=engine)==outcome


def test_blocked_access_retries_with_backoff_without_rewriting_history(tmp_path):
    directory=source_state(tmp_path)
    def blocked(*_):raise OCRError("access_required")
    before=(directory/"state.json").read_bytes()
    run_pass(directory,"legislative",ENV,loader=blocked)
    assert (directory/"state.json").read_bytes()==before
    receipts=tracker.read_jsonl(directory/"source-ocr.jsonl")
    assert receipts[-1]["status"]=="access_required" and receipts[-1]["next_attempt_at"]
    run_pass(directory,"legislative",ENV,loader=lambda *_:pytest.fail("retry backoff ignored"))


def test_shadow_cannot_read_uploads_or_download_sources(tmp_path):
    directory=source_state(tmp_path)
    with pytest.raises(OCRError,match="shadow"):
        run_pass(directory,"legislative",{**ENV,"POLITITRACK_MODE":"shadow"},loader=lambda *_:pytest.fail("network called"))


def test_official_transport_rejects_nonofficial_hosts_before_network():
    with OfficialSession("house") as session:
        for url in ["http://disclosures-clerk.house.gov/file.pdf","https://127.0.0.1/file.pdf", "https://house.gov.evil.test/file.pdf", "https://user:pass@house.gov/file.pdf", "https://house.gov:8443/file.pdf"]:
            with pytest.raises(OCRError):session.get(url)


@pytest.fixture(params=["sqlite","postgres"])
def intake(request,tmp_path):
    cleanup=lambda:None
    if request.param=="postgres":
        if os.environ.get("RUNTIME_V2_TEST_POSTGRES")!="1":pytest.skip("PostgreSQL integration service not enabled")
        url="postgresql+pg8000://postgres:runtime-v2-test@127.0.0.1:5432/postgres"
        admin=create_engine(url);schema="source_ocr_test_"+uuid.uuid4().hex
        with admin.begin() as conn:conn.execute(text('CREATE SCHEMA "'+schema+'"'))
        engine=create_engine(url)
        @event.listens_for(engine,"connect")
        def search_path(conn,_):
            cursor=conn.cursor();cursor.execute('SET search_path TO "'+schema+'"');cursor.close();conn.commit()
        def cleanup():
            engine.dispose()
            with admin.begin() as conn:conn.execute(text('DROP SCHEMA "'+schema+'" CASCADE'))
            admin.dispose()
    else:engine=create_engine("sqlite://")
    store=SourceUploadStore(engine,clock=lambda:NOW);store.initialize_schema()
    yield store
    cleanup();engine.dispose()


def image_bytes():
    stream=io.BytesIO();Image.new("L",(100,100),255).save(stream,format="PNG");return stream.getvalue()


def test_private_upload_deduplicates_and_expiry_deletes_raw_bytes_only(intake):
    first=intake.submit("owner",FILING,image_bytes())
    assert intake.submit("owner",FILING,image_bytes())["duplicate"]
    assert len(intake.pending("legislative"))==1
    assert intake.read("other")==[]
    intake.clock=lambda:NOW+timedelta(days=8)
    assert intake.pending("legislative")==[]
    with intake.engine.begin() as conn:row=conn.execute(select(uploads)).mappings().one()
    assert row["payload"] is None and row["status"]=="expired" and row["sha256"]==first["sha256"]


def test_approval_preserves_rows_and_cannot_cross_accounts(intake):
    first=intake.submit("owner",FILING,image_bytes())
    preview={"rows":[ROW,{**ROW,"row":2}],"problems":[],"filer_matches":True}
    intake.acknowledge([{**first,"status":"needs_review","preview":preview}],"a"*64)
    with pytest.raises(ReviewError):intake.confirm("other",first["upload_id"],first["sha256"],preview["rows"])
    with pytest.raises(ReviewError):intake.confirm("owner",first["upload_id"],first["sha256"],preview["rows"][:1])
    assert intake.confirm("owner",first["upload_id"],first["sha256"],preview["rows"])["status"]=="approved"
    queued=intake.pending("legislative")
    assert len(queued)==1 and queued[0]["payload"] is None
    intake.acknowledge([{**first,"status":"complete","preview":preview}],"b"*64)
    assert intake.pending("legislative")==[]


def test_upload_api_requires_owner_origin_account_and_existing_filing(intake,tmp_path):
    from flask import Flask
    from runtime_v2.source_ocr_api import create_blueprint
    from runtime_v2.review_api import COOKIE
    root=tmp_path/"site";(root/"data").mkdir(parents=True)
    (root/"data/filings.json").write_text(json.dumps([FILING]))
    account={"account_id":"owner"}
    app=Flask(__name__);app.config.update(RUNTIME_SOURCE_OCR_ENABLED=True,RUNTIME_SOURCE_OCR_ACCOUNT_IDS="owner",RUNTIME_REVIEW_ORIGIN="https://dashboard.test")
    app.register_blueprint(create_blueprint(SimpleNamespace(account_for_session=lambda token:account if token=="valid" else None),SimpleNamespace(refresh=lambda:root),intake))
    client=app.test_client()
    assert client.get("/api/source-ocr/status").status_code==401
    client.set_cookie(COOKIE,"valid")
    headers={"Origin":"https://dashboard.test","X-PolitiTrack-Source-Request":"1","X-PolitiTrack-Account":"owner"}
    url="/api/source-ocr/upload?filing_key="+FILING["filing_key"]
    assert client.post(url,data=image_bytes()).status_code==403
    assert client.post(url,data=image_bytes(),headers={**headers,"X-PolitiTrack-Account":"other"}).status_code==409
    assert client.post("/api/source-ocr/upload?filing_key=missing",data=image_bytes(),headers=headers).status_code==400
    response=client.post(url,data=image_bytes(),headers=headers)
    assert response.status_code==202
    assert response.headers["Cache-Control"]=="private, no-store"


def test_evidence_disk_failure_aborts_instead_of_acknowledging(tmp_path,monkeypatch):
    from pathlib import Path
    directory=source_state(tmp_path)
    original=Path.write_text
    def fail(path,*args,**kwargs):
        if path.parent.name=="ocr-evidence":raise OSError("TEST disk unavailable")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,"write_text",fail)
    with pytest.raises(OSError):
        run_pass(directory,"legislative",ENV,loader=lambda *_:b"test",extractor=lambda *a,**k:evidence())
    assert not (directory/"source-ocr.jsonl").exists()
    assert not (directory/"transactions.jsonl").exists()


def test_expired_resubmission_obeys_queue_limits_and_keeps_original_date(intake):
    first=intake.submit("owner",FILING,image_bytes())
    intake.clock=lambda:NOW+timedelta(days=8)
    assert intake.pending("legislative")==[]
    # Ten other current uploads fill this owner's hourly allowance.
    for index in range(10):
        intake.submit("owner",{**FILING,"filing_key":f"house:limit-{index}"},image_bytes())
    with pytest.raises(ReviewError) as caught:intake.submit("owner",FILING,image_bytes())
    assert caught.value.code=="UPLOAD_LIMIT"
    intake.clock=lambda:NOW+timedelta(days=8,hours=2)
    resumed=intake.submit("owner",FILING,image_bytes())
    assert resumed["upload_id"]==first["upload_id"] and resumed["status"]=="pending"
    with intake.engine.begin() as conn:
        row=conn.execute(select(uploads).where(uploads.c.upload_id==first["upload_id"])).mappings().one()
    assert row["created_at"].replace(tzinfo=timezone.utc)==NOW


@pytest.mark.parametrize("fail_commit",[False,True])
def test_runner_acknowledges_only_after_successful_canonical_commit(monkeypatch,fail_commit):
    import test_runtime_v2_shadow_mode as fixtures
    from runtime_v2.runner import JobRunner
    from runtime_v2 import source_uploads,source_ocr_worker
    store=fixtures._RunStore();order=[]
    runner=JobRunner(store,source_revision="a"*40,environment={**ENV,"RUNTIME_SOURCE_OCR_ENABLED":"true"})
    monkeypatch.setattr(runner,"_execute",lambda *a:None)
    monkeypatch.setattr(runner,"_prepare_notifications",lambda *a:None)
    monkeypatch.setattr(runner,"_notification_commit_options",lambda *a:({},{}))
    monkeypatch.setattr(runner,"_dispatch_notifications",lambda *a:None)
    monkeypatch.setattr(source_uploads,"SourceUploadStore",lambda:SimpleNamespace(pending=lambda branch:[],acknowledge=lambda *a:order.append("ack")))
    monkeypatch.setattr(source_ocr_worker,"run_pass",lambda *a:[{"TEST":"outcome"}])
    commit=store.lock.commit
    def wrapped(*args,**kwargs):
        order.append("commit")
        if fail_commit:raise RuntimeError("TEST snapshot failure")
        return commit(*args,**kwargs)
    monkeypatch.setattr(store.lock,"commit",wrapped)
    if fail_commit:
        with pytest.raises(RuntimeError,match="TEST snapshot"):runner.run("legislative")
        assert order==["commit"]
    else:
        runner.run("legislative")
        assert order==["commit","ack"]
