"""OCR manual review is a versioned projection, never source approval/import."""

import copy
from contextlib import nullcontext
import csv
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import uuid

from flask import Flask
import pytest
from sqlalchemy import create_engine

from runtime_v2.review_accounts import LOGICAL_ID, PersonalReviewStore, digest
from runtime_v2.review_api import COOKIE, create_blueprint, publication_identities
from scripts.build_trade_dashboard import build_payload, build_site, load_branch
from scripts.dashboard_insights import build_insights, review_rows
from scripts.source_ocr_reviews import project_source_ocr_reviews


FILING = {"filing_key": "oge|fixture:one", "source": "oge", "branch": "executive",
          "report_id": "fixture:one", "filer": "Fixture Executive Official",
          "source_url": "https://example.test/fixture-one.pdf", "access_mode": "direct",
          "status": "cataloged", "filed_date": "2026-10-01", "first_seen_utc": "2026-10-01T12:00:00Z"}
RECEIPT = {"filing_key": FILING["filing_key"], "source_url": FILING["source_url"],
           "version": "source-ocr-v2", "status": "needs_review", "error_code": "native_ocr_disagreement",
           "origin": "official_download", "attempts": 1, "attempted_at": "2026-10-02T12:00:00Z",
           "sha256": "a" * 64, "evidence": {"sha256": "a" * 64, "version": "source-ocr-v2",
               "page_count": 2, "completed_pages": [1, 2], "private_text": "PRIVATE OCR TEXT"}}
ORIGIN = "https://dashboard.test"
HEADERS = {"Origin": ORIGIN, "X-PolitiTrack-Review-Request": "1"}


def projected(receipt=None, filing=None):
    filing = copy.deepcopy(FILING if filing is None else filing)
    receipt = copy.deepcopy(RECEIPT if receipt is None else receipt)
    return project_source_ocr_reviews([filing], {filing["filing_key"]: receipt}, filing["branch"])[0]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def source_fixture(path, receipts=None, *, legacy=True, synthetic=False):
    filing = {**FILING, **({"is_synthetic_test": True} if synthetic else {})}
    write_jsonl(path / "filings.jsonl", [filing])
    write_jsonl(path / "source-ocr.jsonl", [RECEIPT] if receipts is None else receipts)
    if legacy:
        write_jsonl(path / "pending-review.jsonl", [{"review_id": "legacy-retained-review",
            "source": "oge", "report_id": FILING["report_id"], "reason": "Paper filing needs manual review",
            "observed_at_utc": "2026-10-01T12:01:00Z"}])
    return path


def payload_from(source):
    return build_payload(load_branch(None, "legislative"), load_branch(source, "executive"),
                         repository_url="https://github.com/maglothinm/MyETF-Intelligence")


def test_same_document_and_error_survive_rechecks_parser_changes_and_display_changes():
    first = projected()
    changed = {**RECEIPT, "attempts": 9, "attempted_at": "2026-10-12T12:00:00Z",
               "source_checked_at": "2026-10-12T12:01:00Z", "revalidate_after": "2026-10-19T12:00:00Z",
               "parser_version": "new-parser", "version": "source-ocr-v3", "reason": "Different display wording"}
    second = projected(changed, {**FILING, "filer": "Different display name"})
    assert second["review_id"] == first["review_id"]
    assert second["logical_review_id"] == first["logical_review_id"]
    assert LOGICAL_ID.fullmatch(first["logical_review_id"])
    assert first["ocr_review_version_kind"] == "sha256"


def test_changed_document_or_error_gets_a_distinct_identity():
    first = projected()
    new_bytes = {**RECEIPT, "sha256": "b" * 64, "evidence": {**RECEIPT["evidence"], "sha256": "b" * 64}}
    changed_error = {**RECEIPT, "error_code": "existing_transaction_conflict"}
    assert len({row["logical_review_id"] for row in [first, projected(new_bytes), projected(changed_error)]}) == 3


def test_unknown_document_is_acknowledgeable_only_for_its_exact_recorded_attempt():
    unknown = {key: value for key, value in RECEIPT.items() if key not in {"sha256", "evidence"}}
    unknown["error_code"] = "document_byte_limit"
    first = projected(unknown)
    assert first["review_identity_status"] == "available"
    assert first["ocr_review_version_kind"] == "receipt-v1"
    assert "bytes are unverified" in first["reason"]
    assert "ocr_document_sha256" not in first
    refreshed = {**unknown, "revalidate_after": "2026-11-01T12:00:00Z", "source_checked_at": "2026-10-12T12:00:00Z"}
    assert projected(refreshed)["logical_review_id"] == first["logical_review_id"]
    new_attempt = {**unknown, "attempted_at": "2026-10-12T12:00:00Z", "attempts": 2}
    assert projected(new_attempt)["logical_review_id"] != first["logical_review_id"]
    assert projected()["logical_review_id"] != first["logical_review_id"]


@pytest.mark.parametrize("mutations", [
    {"sha256": "b" * 64},
    {"sha256": "invalid"},
    {"source_url": "https://example.test/different-document.pdf"},
    {"filing_key": "different-key"},
    {"error_code": ""},
    {"sha256": None, "evidence": None, "attempted_at": None},
    {"sha256": None, "evidence": None, "attempts": True},
    {"sha256": None, "evidence": None, "version": ""},
    {"sha256": None, "evidence": None, "origin": "unknown"},
])
def test_incomplete_or_conflicting_identity_is_visible_but_cannot_be_acknowledged(mutations):
    row = projected({**RECEIPT, **mutations})
    assert row["review_identity_status"] == "unavailable"
    source = {"filings": [FILING], "reviews": [row]}
    model = build_insights(source)
    assert review_rows(source)[0]["category"] == "other"
    assert model["reviews"]["manual_exception_ids"] == []
    assert model["reviews"]["manual_exception_identities"] == {}
    assert model["reviews"]["other"] == 1


def test_committed_manual_upload_hash_is_bound_to_its_upload_receipt():
    receipt = {**RECEIPT, "sha256": None, "evidence": None, "origin": "user_upload",
               "upload_id": "fixture-upload", "error_code": "upload_confirmation_required",
               "upload_outcome": {"upload_id": "fixture-upload", "sha256": "a" * 64}}
    row = projected(receipt)
    assert row["review_identity_status"] == "available" and row["ocr_document_sha256"] == "a" * 64
    invalid = {**receipt, "upload_outcome": {"upload_id": "another-upload", "sha256": "a" * 64}}
    assert projected(invalid)["review_identity_status"] == "unavailable"
    for invalid_id in (42, {}, ""):
        invalid = {**receipt, "upload_id": invalid_id, "upload_outcome": {"upload_id": invalid_id, "sha256": "a" * 64}}
        assert projected(invalid)["review_identity_status"] == "unavailable"
    unknown = {**receipt, "upload_outcome": None, "upload_id": ""}
    assert projected(unknown)["review_identity_status"] == "unavailable"
    assert not {"upload_id", "upload_outcome", "approved_rows", "evidence"}.intersection(row)


@pytest.mark.parametrize(("mutations", "identity_status"), [
    ({"evidence": None, "sha256": None}, "available"),
    ({"evidence": {**RECEIPT["evidence"], "completed_pages": None}}, "available"),
    ({"evidence": []}, "unavailable"),
    ({"evidence": "invalid"}, "unavailable"),
    ({"evidence": None, "sha256": None, "origin": []}, "unavailable"),
    ({"upload_outcome": []}, "unavailable"),
])
def test_malformed_receipt_display_fields_do_not_crash_the_whole_dashboard(tmp_path, mutations, identity_status):
    source = source_fixture(tmp_path / "source", [{**RECEIPT, **mutations}], legacy=False)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    payload = payload_from(source)
    assert payload["reviews"][0]["review_identity_status"] == identity_status
    build_site(payload, tmp_path / "site")
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before


def test_nonstrings_cannot_form_an_acknowledgeable_source_identity():
    assert project_source_ocr_reviews([{**FILING, "source": []}], {FILING["filing_key"]: RECEIPT}, "executive") == []
    row = projected({**RECEIPT, "source_url": ["invalid"]}, {**FILING, "source_url": ["invalid"]})
    assert row["review_identity_status"] == "unavailable"


@pytest.mark.parametrize("status", ["complete", "access_required", "retry_delayed", "not_applicable"])
def test_only_latest_needs_review_receipts_enter_the_current_review_inventory(tmp_path, status):
    source = source_fixture(tmp_path / "source", [RECEIPT, {**RECEIPT, "status": status}], legacy=False)
    assert load_branch(source, "executive")["reviews"] == []


def test_exact_join_and_synthetic_ancestry_are_required(tmp_path):
    assert project_source_ocr_reviews([FILING, FILING], {FILING["filing_key"]: RECEIPT}, "executive") == []
    assert project_source_ocr_reviews([FILING], {FILING["filing_key"]: RECEIPT}, "legislative") == []
    source = source_fixture(tmp_path / "source", legacy=False, synthetic=True)
    model = build_insights(payload_from(source))
    assert model["reviews"]["manual_exception"] == model["reviews"]["total"] == 0


def test_projection_preserves_source_bytes_and_existing_ids_and_exports_consistent_inventory(tmp_path):
    source = source_fixture(tmp_path / "source")
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    payload = payload_from(source)
    rows = review_rows(payload)
    assert len(rows) == 2
    legacy = next(row for row in rows if row["review_id"] == "legacy-retained-review")
    ocr = next(row for row in rows if row.get("review_kind") == "source_ocr")
    assert legacy["logical_review_id"] != ocr["logical_review_id"]
    original = copy.deepcopy(payload)
    output = tmp_path / "site"
    for _ in range(2):
        build_site(payload, output)
        assert payload == original
        published = json.loads((output / "data/pending-reviews.json").read_text())
        insights = json.loads((output / "data/dashboard-insights.json").read_text())
        assert len(published) == insights["reviews"]["manual_exception"] == 2
        assert publication_identities(output) == {row["review_id"]: row["logical_review_id"] for row in published}
        with (output / "data/pending-reviews.csv").open(newline="") as handle:
            exported = list(csv.DictReader(handle))
        assert {row["logical_review_id"] for row in exported} == {row["logical_review_id"] for row in published}
        assert "PRIVATE OCR TEXT" not in (output / "data/pending-reviews.json").read_text()
    assert {path.name: path.read_bytes() for path in source.iterdir()} == before


def test_ocr_projection_uses_existing_authenticated_api_without_approving_or_altering_sources(tmp_path):
    source = source_fixture(tmp_path / "source", legacy=False)
    output = tmp_path / "site"
    build_site(payload_from(source), output)
    review = json.loads((output / "data/pending-reviews.json").read_text())[0]
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    engine = create_engine("sqlite:///" + str(tmp_path / "personal-review-fixture.db"))
    try:
        store = PersonalReviewStore(engine, clock=lambda: datetime(2026, 10, 12, tzinfo=timezone.utc))
        store.initialize_schema()
        invitation = "fixture-activation-only-not-for-production"
        account = store.invite("fixture-reviewer", digest(invitation))
        session = store.activate(invitation, "fixture-only long review passphrase")
        app = Flask(__name__)
        app.config.update(TESTING=True, RUNTIME_PERSONAL_REVIEWS_ENABLED=True, RUNTIME_REVIEW_ORIGIN=ORIGIN)
        app.register_blueprint(create_blueprint(store, SimpleNamespace(read=lambda: nullcontext(SimpleNamespace(root=output)))))
        client = app.test_client()
        client.set_cookie(COOKIE, session, domain="dashboard.test")
        body = {"review_id": review["review_id"], "logical_review_id": review["logical_review_id"],
                "acknowledged": True, "expected_revision": 0, "expected_account_id": account["account_id"],
                "request_id": str(uuid.uuid4())}
        response = client.post("/api/reviews/acknowledgements", json=body, headers=HEADERS, base_url=ORIGIN)
        assert response.status_code == 200
        saved = response.json["acknowledged"]
        assert saved[0]["logical_review_id"] == review["logical_review_id"]
        assert {path.name: path.read_bytes() for path in source.iterdir()} == before
        assert json.loads((source / "source-ocr.jsonl").read_text())["status"] == "needs_review"
        # A genuinely new content version is not acknowledged by the saved row.
        next_receipt = {**RECEIPT, "sha256": "b" * 64, "evidence": {**RECEIPT["evidence"], "sha256": "b" * 64}}
        write_jsonl(source / "source-ocr.jsonl", [RECEIPT, next_receipt])
        build_site(payload_from(source), output)
        assert review["review_id"] not in publication_identities(output)
        assert store.read(account["account_id"])["acknowledged"] == saved
        stale = {**body, "expected_revision": 1, "request_id": str(uuid.uuid4())}
        assert client.post("/api/reviews/acknowledgements", json=stale, headers=HEADERS, base_url=ORIGIN).status_code == 409
    finally:
        engine.dispose()
