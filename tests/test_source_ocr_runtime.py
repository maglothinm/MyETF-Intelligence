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
from scripts.source_ocr import VERSION, DOCUMENT_POLICY_VERSION, OCRError, AMOUNTS

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


@pytest.mark.parametrize("future", [False, True])
def test_due_technical_retry_precedes_untouched_history_without_bypassing_backoff(tmp_path, future):
    directory = source_state(tmp_path)
    untouched = {**FILING, "filing_key": "house:untouched", "report_id": "untouched"}
    tracker.append_jsonl(directory / "filings.jsonl", [untouched])
    prior = {"filing_key": FILING["filing_key"], "source_url": FILING["source_url"], "version": VERSION,
             "status": "retry_delayed", "error_code": "incomplete_page_ocr", "attempts": 1,
             "attempted_at": "2026-09-19T00:00:00Z",
             "next_attempt_at": "2099-01-01T00:00:00Z" if future else "2020-01-01T00:00:00Z"}
    tracker.append_jsonl(directory / "source-ocr.jsonl", [prior])
    prefix = (directory / "source-ocr.jsonl").read_bytes()
    loaded = []
    def loader(row, config):
        loaded.append(row["filing_key"])
        return b"test"
    run_pass(directory, "legislative", {**ENV, "RUNTIME_SOURCE_OCR_FILES_PER_RUN": "1"},
             loader=loader, extractor=lambda *a, **k: evidence())
    assert loaded == [untouched["filing_key"] if future else FILING["filing_key"]]
    assert (directory / "source-ocr.jsonl").read_bytes().startswith(prefix)


def test_new_filing_precedes_due_retry_then_oldest_due_retry_leads(tmp_path):
    directory = source_state(tmp_path)
    new = {**FILING, "filing_key": "house:new", "report_id": "new",
           "first_seen_utc": datetime.now(timezone.utc).isoformat()}
    newer_retry = {**FILING, "filing_key": "house:newer-retry", "report_id": "newer-retry"}
    tracker.append_jsonl(directory / "filings.jsonl", [new, newer_retry])
    for filing, stamp in [(FILING, "2020-01-01T00:00:00Z"), (newer_retry, "2020-01-02T00:00:00Z")]:
        tracker.append_jsonl(directory / "source-ocr.jsonl", [{"filing_key": filing["filing_key"],
            "source_url": filing["source_url"], "version": VERSION, "status": "retry_delayed",
            "attempted_at": stamp, "next_attempt_at": "2020-01-03T00:00:00Z"}])
    loaded = []
    def loader(row, config):
        loaded.append(row["filing_key"])
        return row["filing_key"].encode()
    run_pass(directory, "legislative", {**ENV, "RUNTIME_SOURCE_OCR_FILES_PER_RUN": "2"},
             loader=loader, extractor=lambda data, **k: evidence(data))
    assert loaded == [new["filing_key"], FILING["filing_key"]]


def test_completed_no_text_page_is_review_not_retry_or_partial_import(tmp_path):
    directory = source_state(tmp_path)
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    health = {}
    partial = {**evidence(), "page_count": 2, "completed_pages": [1, 2], "empty_ocr_pages": [2]}
    run_pass(directory, "legislative", ENV, loader=lambda *_: b"test",
             extractor=lambda *a, **k: partial, health=health)
    receipt = tracker.read_jsonl(directory / "source-ocr.jsonl")[-1]
    assert receipt["status"] == "needs_review"
    assert receipt["error_code"] == "unreadable_page_needs_review"
    assert "next_attempt_at" not in receipt
    assert health["documents_completed"] == 1 and health["pages_completed"] == 2
    assert health["retry_remaining"] == 0 and health["review_remaining"] == 1
    assert not (directory / "transactions.jsonl").exists()
    for name, content in before.items():
        assert (directory / name).read_bytes() == content
    from runtime_v2.source_ocr_worker import _parse
    with pytest.raises(OCRError, match="unreadable_page_needs_review"):
        _parse(FILING, partial, [ROW])


def test_old_pdf_rejection_retries_once_without_invalidating_successful_evidence(tmp_path):
    directory = source_state(tmp_path)
    rejected = {"filing_key": FILING["filing_key"], "source_url": FILING["source_url"], "version": VERSION,
                "origin": "official_download", "status": "needs_review", "error_code": "invalid_or_encrypted_pdf",
                "attempts": 1, "next_attempt_at": "2099-01-01T00:00:00Z", "revalidate_after": "2099-01-01T00:00:00Z"}
    tracker.append_jsonl(directory / "source-ocr.jsonl", [rejected])
    old_ledger = (directory / "source-ocr.jsonl").read_bytes()
    calls = []
    def engine(data, **kwargs):
        calls.append(1)
        return evidence(data)
    run_pass(directory, "legislative", ENV, loader=lambda *_: b"test", extractor=engine)
    receipt = tracker.latest_records(directory / "source-ocr.jsonl", "filing_key")[FILING["filing_key"]]
    assert receipt["status"] == "complete" and receipt["document_policy_version"] == DOCUMENT_POLICY_VERSION
    assert receipt["attempts"] == 2
    assert (directory / "source-ocr.jsonl").read_bytes().startswith(old_ledger)
    run_pass(directory, "legislative", ENV, loader=lambda *_: pytest.fail("successful document repeated"), extractor=engine)
    assert calls == [1]


def test_current_policy_pdf_rejection_and_unrelated_reviews_keep_backoff(tmp_path):
    directory = source_state(tmp_path)
    for code, policy in [("invalid_or_encrypted_pdf", DOCUMENT_POLICY_VERSION), ("table_needs_review", None)]:
        tracker.append_jsonl(directory / "source-ocr.jsonl", [{"filing_key": FILING["filing_key"],
            "source_url": FILING["source_url"], "version": VERSION, "document_policy_version": policy,
            "status": "needs_review", "error_code": code, "revalidate_after": "2099-01-01T00:00:00Z"}])
        run_pass(directory, "legislative", ENV, loader=lambda *_: pytest.fail("unaffected review requeued"))


def test_executive_direct_pdf_retries_past_old_backoff_ahead_of_gated_requests(tmp_path):
    directory = source_state(tmp_path)
    pdf = {**FILING, "branch": "executive", "source": "oge", "filing_key": "oge|retained-pdf",
           "report_id": "retained-pdf", "access_mode": "request", "source_url": "https://extapps2.oge.gov/201/$FILE/test.pdf"}
    gated = {**pdf, "filing_key": "oge|gated", "report_id": "gated", "source_url": "https://extapps2.oge.gov/201%20Request?OpenForm"}
    tracker.append_jsonl(directory / "filings.jsonl", [gated, pdf])
    prior = {"filing_key": pdf["filing_key"], "source_url": pdf["source_url"], "version": VERSION,
             "status": "access_required", "error_code": "access_required", "next_attempt_at": "2099-01-01T00:00:00Z"}
    tracker.append_jsonl(directory / "source-ocr.jsonl", [prior])
    state_before = (directory / "state.json").read_bytes()
    filing_prefix = (directory / "filings.jsonl").read_bytes()
    loaded = []
    def loader(row, config):
        loaded.append(row)
        return b"test"
    # An unrecognized scanned layout remains reviewable; this test accepts the
    # download/queue repair, not an invented OGE transaction import.
    run_pass(directory, "executive", {**ENV, "RUNTIME_SOURCE_OCR_FILES_PER_RUN": "1"}, loader=loader, extractor=lambda *a, **k: evidence())
    assert [row["filing_key"] for row in loaded] == [pdf["filing_key"]]
    assert loaded[0]["access_mode"] == "direct"
    assert loaded[0]["first_seen_utc"] == pdf["first_seen_utc"]
    assert (directory / "state.json").read_bytes() == state_before
    assert (directory / "filings.jsonl").read_bytes().startswith(filing_prefix)
    receipts = tracker.read_jsonl(directory / "source-ocr.jsonl")
    assert receipts[0] == prior and len(receipts) == 2
    assert receipts[-1]["document_policy_version"] == DOCUMENT_POLICY_VERSION
    assert receipts[-1]["error_code"] == "unsupported_scanned_layout"


def test_ocr_download_reclassifies_only_official_pdf_not_form201(tmp_path, monkeypatch):
    from runtime_v2 import source_ocr_worker as worker
    from unittest.mock import Mock
    pdf = {**FILING, "source": "oge", "branch": "executive", "access_mode": "request",
           "source_url": "https://extapps2.oge.gov/201/$FILE/test.pdf"}
    resolve = Mock(return_value=b"%PDF-test")
    monkeypatch.setattr(tracker, "resolve_oge_pdf", resolve)
    config = worker._configuration(tmp_path, "executive", ENV)
    assert worker.download(pdf, config) == b"%PDF-test"
    assert resolve.call_args.args[1]["access_mode"] == "direct"
    resolve.reset_mock()
    with pytest.raises(OCRError, match="access_required"):
        worker.download({**pdf, "source_url": "https://extapps2.oge.gov/201%20Request?Document=test.pdf"}, config)
    resolve.assert_not_called()


def test_shadow_cannot_read_uploads_or_download_sources(tmp_path):
    directory=source_state(tmp_path)
    with pytest.raises(OCRError,match="shadow"):
        run_pass(directory,"legislative",{**ENV,"POLITITRACK_MODE":"shadow"},loader=lambda *_:pytest.fail("network called"))


@pytest.mark.parametrize("format,html", [
    ("pdf", b"<h1>Filing Document - Print View</h1><p>Page 1 of 2</p><img src='page1.png'>"),
    ("html", b"<h1>Paper filing</h1><img src='page1.png'>"),
])
def test_senate_image_viewer_is_review_required_without_retry(tmp_path, monkeypatch, format, html):
    from runtime_v2 import source_ocr_worker as worker
    from unittest.mock import MagicMock
    directory = source_state(tmp_path)
    filing = {**FILING, "source": "senate", "document_format": format,
              "source_url": "https://efdsearch.senate.gov/search/view/paper/TEST/"}
    tracker.append_jsonl(directory / "filings.jsonl", [filing])
    client = MagicMock()
    monkeypatch.setattr(tracker, "SenateClient", lambda: client)
    response = SimpleNamespace(headers={"Content-Type": "text/html"}, url=filing["source_url"])
    monkeypatch.setattr(tracker, "_senate_page_response", lambda *_: response)
    monkeypatch.setattr(tracker, "response_bytes", lambda *a, **k: html)
    health = {}
    before = (directory / "state.json").read_bytes()
    worker.run_pass(directory, "legislative", ENV, health=health,
                    extractor=lambda *a, **k: pytest.fail("unsupported viewer entered PDF extraction"))
    receipt = tracker.read_jsonl(directory / "source-ocr.jsonl")[-1]
    assert receipt["error_code"] == "page_image_download_requires_review"
    assert receipt["status"] == "needs_review" and "next_attempt_at" not in receipt
    assert health["review_remaining"] == 1 and health["retry_remaining"] == 0
    assert health["documents_completed"] == 0
    assert (directory / "state.json").read_bytes() == before
    assert not (directory / "transactions.jsonl").exists()
    worker.run_pass(directory, "legislative", ENV,
                    loader=lambda *_: pytest.fail("review retried before source revalidation"))


@pytest.mark.parametrize("code", ["PaperFilingError", "page_image_download_requires_review"])
def test_retained_senate_retry_is_corrected_once_with_no_new_attempt(tmp_path, code):
    directory = source_state(tmp_path)
    filing = {**FILING, "source": "senate", "source_url": "https://efdsearch.senate.gov/search/view/paper/TEST/"}
    tracker.append_jsonl(directory / "filings.jsonl", [filing])
    prior = {"filing_key": filing["filing_key"], "source_url": filing["source_url"], "version": VERSION,
             "status": "retry_delayed", "error_code": code, "origin": "official_download", "attempts": 8,
             "attempted_at": "2026-09-19T07:40:07Z", "next_attempt_at": "2099-01-01T00:00:00Z"}
    tracker.append_jsonl(directory / "source-ocr.jsonl", [prior])
    preserved = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    health = {}
    for _ in range(2):
        run_pass(directory, "legislative", ENV, health=health,
                 loader=lambda *_: pytest.fail("classification repair performed a download"))
    rows = tracker.read_jsonl(directory / "source-ocr.jsonl")
    assert len(rows) == 2 and rows[0] == prior
    assert rows[-1]["status"] == "needs_review" and "next_attempt_at" not in rows[-1]
    assert all(rows[-1][k] == v for k, v in prior.items() if k not in {"status", "next_attempt_at"})
    assert health["documents_attempted"] == 0 and health["retry_remaining"] == 0 and health["review_remaining"] == 1
    assert set(p.name for p in directory.iterdir()) == set(preserved)
    for name, data in preserved.items():
        current = (directory / name).read_bytes()
        assert current.startswith(data) if name == "source-ocr.jsonl" else current == data


@pytest.mark.parametrize("change", [
    {"source_url": "https://efdsearch.senate.gov/changed"},
    {"version": "older-version"}, {"origin": "user_upload"}, {"error_code": "Timeout"},
])
def test_retained_retry_without_matching_source_evidence_is_not_reclassified(tmp_path, change):
    directory = source_state(tmp_path)
    filing = {**FILING, "source": "senate"}
    tracker.append_jsonl(directory / "filings.jsonl", [filing])
    prior = {"filing_key": filing["filing_key"], "source_url": filing["source_url"], "version": VERSION,
             "status": "retry_delayed", "error_code": "PaperFilingError", "origin": "official_download",
             "next_attempt_at": "2099-01-01T00:00:00Z", **change}
    tracker.append_jsonl(directory / "source-ocr.jsonl", [prior])
    run_pass(directory, "legislative", ENV, loader=lambda *_: pytest.fail("existing backoff ignored"))
    assert tracker.read_jsonl(directory / "source-ocr.jsonl") == [prior]


@pytest.mark.parametrize("error,status", [
    (tracker.PaperFilingError("private source text"), "needs_review"),
    (OCRError("unsupported_scanned_layout"), "needs_review"),
    (OCRError("access_required"), "access_required"),
    (TimeoutError("private URL"), "retry_delayed"),
])
def test_layout_review_does_not_mask_access_or_transport_failures(tmp_path, error, status):
    directory = source_state(tmp_path)
    def loader(*_):
        raise error
    run_pass(directory, "legislative", ENV, loader=loader)
    receipt = tracker.read_jsonl(directory / "source-ocr.jsonl")[-1]
    assert receipt["status"] == status
    assert ("next_attempt_at" in receipt) == (status != "needs_review")
    assert "private" not in json.dumps(receipt)


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
    from test_source_ocr import multipage_source
    response=client.post(url,data=multipage_source(37),headers=headers)
    assert response.status_code==202
    assert response.headers["Cache-Control"]=="private, no-store"
    assert intake.pending("legislative")[0]["page_count"] == 37
    app.config["RUNTIME_SOURCE_OCR_ACCOUNT_IDS"] = "different-owner"
    assert client.post(url, data=multipage_source(37), headers=headers).status_code == 403


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
    monkeypatch.setattr(source_ocr_worker,"run_pass",lambda *a,**k:[{"TEST":"outcome"}])
    monkeypatch.setattr(store.lock,"record_ocr_health",lambda *a:None,raising=False)
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


@pytest.mark.parametrize("branch", ["legislative", "executive"])
@pytest.mark.parametrize("manual", [False, True])
def test_only_durable_manual_uploads_bypass_automatic_page_cap(tmp_path, branch, manual):
    directory = source_state(tmp_path)
    filing = {**FILING, "branch": branch, "manual_upload": True, "max_pages": None}
    if branch == "executive":
        filing.update(source="oge", source_url="https://extapps2.oge.gov/201/$FILE/TEST.pdf", access_mode="direct")
    tracker.append_jsonl(directory / "filings.jsonl", [filing])
    data = b"test"
    upload = {"upload_id": str(uuid.uuid4()), "source_url": filing["source_url"], "filing_key": filing["filing_key"],
              "payload": data, "sha256": hashlib.sha256(data).hexdigest(), "status": "pending"}
    calls = []
    def engine(blob, **kwargs):
        calls.append(kwargs)
        return evidence(blob)
    run_pass(directory, branch, ENV, [upload] if manual else (), loader=lambda *_: data, extractor=engine)
    assert len(calls) == 1
    assert (calls[0]["max_pages"] is None) if manual else calls[0]["max_pages"] == 30
    if manual:
        assert calls[0]["timeout"] == 120
        assert not (directory / "transactions.jsonl").exists()
        assert tracker.read_jsonl(directory / "source-ocr.jsonl")[-1]["error_code"] == "upload_confirmation_required"


def test_long_manual_upload_reaches_private_inbox_and_keeps_coverage(intake):
    from test_source_ocr import multipage_source
    data = multipage_source(75)
    first = intake.submit("owner", FILING, data)
    pending = intake.pending("legislative")
    assert len(pending) == 1 and pending[0]["page_count"] == 75
    assert pending[0]["payload"] == data
    assert intake.submit("owner", FILING, data)["duplicate"]
    assert intake.read("other") == []
    intake.acknowledge([{**first, "status": "needs_review", "has_evidence": True}], "a" * 64)
    with intake.engine.begin() as conn:
        row = conn.execute(select(uploads)).mappings().one()
    assert row["page_count"] == 75 and row["payload"] is None
