import hashlib
import io
import json
import zipfile

import pytest

from scripts import verify_ocr_page_retry_release as audit

BEFORE = dict(filing_key="house|case", attempts=1, attempted_at="2026-09-20T09:00:00Z",
              next_attempt_at="2026-09-20T10:00:00Z", status="retry_delayed", error_code="incomplete_page_ocr")
AFTER = {**BEFORE, "attempts":2, "attempted_at":"2026-09-20T12:00:00Z", "status":"needs_review",
         "error_code":"unsupported_scanned_layout", "next_attempt_at":None}


def archive(rows, evidence=b"original"):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("source-ocr.jsonl", b"".join(json.dumps(r).encode()+b"\n" for r in rows))
        z.writestr("ocr-evidence/original.json", evidence)
    raw = data.getvalue()
    return audit.archive(raw, hashlib.sha256(raw).hexdigest())


def test_review_is_real_progress_and_preserves_original_attempt_and_evidence():
    with archive([BEFORE]) as old, archive([BEFORE, AFTER]) as new:
        report = audit.compare(old, new, "2026-09-20T11:00:00Z")
    assert report["baseline_retries_attempted"] == report["baseline_retries_resolved"] == 1
    assert report["current_total_technical_retries"] == 0


@pytest.mark.parametrize("rows,evidence,error", [
    ([AFTER], b"original", "prior_ocr_receipts_changed"),
    ([BEFORE, AFTER], b"changed", "prior_extraction_evidence_changed"),
    ([BEFORE], b"original", "no_actual_due_retry_progress"),
    ([BEFORE, {**AFTER, "attempted_at":BEFORE["attempted_at"]}], b"original", "retry_time_not_advanced"),
])
def test_false_acceptance_rejected(rows, evidence, error):
    with archive([BEFORE]) as old, archive(rows, evidence) as new:
        with pytest.raises(RuntimeError, match=error):
            audit.compare(old, new, "2026-09-20T11:00:00Z")


def test_retry_that_still_fails_is_not_reported_resolved():
    retry = {**AFTER, "status":"retry_delayed", "error_code":"ReadTimeout"}
    with archive([BEFORE]) as old, archive([BEFORE, retry]) as new:
        report = audit.compare(old, new, "2026-09-20T11:00:00Z")
    assert report["baseline_retries_attempted"] == 1 and report["baseline_retries_resolved"] == 0
    assert report["current_total_technical_retries"] == 1


def test_future_backoff_is_not_counted_as_due():
    with archive([BEFORE]) as old, archive([BEFORE]) as new:
        report = audit.compare(old, new, "2026-09-20T09:30:00Z")
    assert report["baseline_due_retries"] == 0 and report["current_total_technical_retries"] == 1


def test_unverified_snapshot_bytes_rejected():
    with pytest.raises(RuntimeError, match="snapshot_hash_mismatch"):
        audit.archive(b"changed", "0"*64)
