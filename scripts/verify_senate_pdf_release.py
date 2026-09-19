"""Independent read-only #182 acceptance; BASELINE is the frozen audit's heads.

Run as an explicit existing admin execution after release acceptance. Snapshot
bytes, document text and private upload contents never leave the process.
"""
import hashlib
import io
import json
import os
import zipfile

from runtime_v2.database import connect

SOURCE = "df5bb5a850942ff54f6b73a4936fc9ec18d8e548"
SENATE_KEYS = ["senate|senate:https://efdsearch.senate.gov/search/view/paper/" + identifier + "/"
               for identifier in ("929216d5-5dbd-429c-858c-1e9332924627", "ec20cd93-6702-4a29-b3a6-983f4b17f365")]


def require(value, code):
    if not value:
        raise RuntimeError(code)


def archive(payload, digest):
    payload = bytes(payload)
    require(hashlib.sha256(payload).hexdigest() == digest, "snapshot_hash_mismatch")
    return zipfile.ZipFile(io.BytesIO(payload))


def latest(z, basename):
    names = [n for n in z.namelist() if n.rsplit("/", 1)[-1] == basename]
    require(len(names) == 1, "ledger_identity_ambiguous")
    rows = [json.loads(line) for line in z.read(names[0]).splitlines() if line.strip()]
    return {row["filing_key"]: row for row in rows}


def verify(baseline):
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SET LOCAL statement_timeout = '120s'")
        report = {"probe": "polititrack_senate_pdf_acceptance_v1", "read_only": True,
                  "execution": os.environ.get("CLOUD_RUN_EXECUTION", ""), "source": SOURCE,
                  "namespaces": {}, "senate": []}
        for namespace in ("legislative", "executive"):
            cursor.execute("SELECT payload,snapshot_sha256 FROM runtime_state_snapshots WHERE namespace=%s AND snapshot_id=%s::uuid",
                           (namespace, baseline[namespace]["snapshot_id"]))
            before = cursor.fetchone()
            require(before is not None and before[1] == baseline[namespace]["payload_sha256"], "baseline_identity_mismatch")
            cursor.execute("SELECT s.payload,s.snapshot_sha256,s.source_revision,s.generation,s.snapshot_id::text "
                           "FROM runtime_state_heads h JOIN runtime_state_snapshots s ON s.snapshot_id=h.snapshot_id WHERE h.namespace=%s", (namespace,))
            current = cursor.fetchone()
            require(current is not None and current[2] == SOURCE and current[3] > baseline[namespace]["generation"], "release_head_missing")
            with archive(*before) as old, archive(current[0], current[1]) as new:
                old_names, new_names = set(old.namelist()), set(new.namelist())
                require(old_names.issubset(new_names), "prior_file_removed")
                receipts = [n for n in old_names if n.rsplit("/", 1)[-1] == "source-ocr.jsonl"]
                require(len(receipts) == 1, "prior_ocr_ledger_missing")
                require(new.read(receipts[0]).startswith(old.read(receipts[0])), "prior_ocr_receipts_changed")
                old_evidence = [n for n in old_names if "ocr-evidence/" in n and n.endswith(".json")]
                new_evidence = [n for n in new_names if "ocr-evidence/" in n and n.endswith(".json")]
                require(all(old.read(n) == new.read(n) for n in old_evidence), "prior_extraction_evidence_changed")
                report["namespaces"][namespace] = {
                    "generation": current[3], "snapshot_id": current[4], "snapshot_sha256": current[1],
                    "prior_ocr_receipts_preserved": True, "prior_extraction_files_preserved": len(old_evidence),
                    "new_extraction_files": len(new_evidence) - len(old_evidence)}
                if namespace == "legislative":
                    prior, updated = latest(old, "source-ocr.jsonl"), latest(new, "source-ocr.jsonl")
                    for key in SENATE_KEYS:
                        a, b = prior[key], updated[key]
                        require(a.get("status") == "retry_delayed" and b.get("status") == "needs_review", "senate_classification_not_corrected")
                        require(not b.get("next_attempt_at"), "senate_retry_timer_retained")
                        require(all(a.get(k) == b.get(k) for k in ("attempts", "attempted_at", "source_url", "error_code", "version")), "senate_history_changed")
                        report["senate"].append({"filing_key": key, "status": b["status"], "error_code": b["error_code"],
                            "attempts_preserved": b["attempts"], "next_attempt_at": None})
        require(sum(x["new_extraction_files"] for x in report["namespaces"].values()) > 0, "no_new_real_extraction_evidence")
        cursor.execute("SELECT sha256,status,page_count,payload IS NULL,result FROM runtime_source_uploads WHERE account_id=%s AND filing_key=%s",
                       ("432b3395-e059-45e8-acf6-0d031d92f41d", "house|house:2026:9116331"))
        rows = cursor.fetchall()
        require(len(rows) == 1, "owner_upload_identity_changed")
        digest, status, pages, cleared, preview = rows[0]
        preview = json.loads(preview) if isinstance(preview, str) else preview
        require(digest == "58cefce89a3fe84a5d4893337e79b4bc9add769d02fac1869403456afd5a4343"
                and status == "needs_review" and pages == 2 and cleared and len(preview.get("rows", [])) == 5,
                "owner_upload_review_or_cleanup_changed")
        report["owner_upload"] = {"status": status, "pages": pages, "review_rows": 5, "raw_payload_is_null": cleared}
        connection.rollback()
        report["result"] = "PASS"
        print(json.dumps(report), flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    verify(BASELINE)  # supplied from this release's immutable baseline receipt
