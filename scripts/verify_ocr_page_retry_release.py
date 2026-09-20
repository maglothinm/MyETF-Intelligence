"""Independent read-only verification of #203 retry progress and OCR preservation.

BASELINE is supplied from this release's immutable frozen-baseline receipt.
Only counts, filing identities and status evidence are reported; no raw documents
or snapshot payloads leave the existing admin execution. PASS proves preservation
and actual retry progress, not that every technical retry has cleared.
"""
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime

SOURCE = "aba0285689d649d94e3e11444b582c748927bbc4"


def require(value, code):
    if not value:
        raise RuntimeError(code)


def archive(payload, digest):
    payload = bytes(payload)
    require(hashlib.sha256(payload).hexdigest() == digest, "snapshot_hash_mismatch")
    return zipfile.ZipFile(io.BytesIO(payload))


def latest(z):
    names = [n for n in z.namelist() if n.rsplit("/", 1)[-1] == "source-ocr.jsonl"]
    require(len(names) == 1, "ocr_ledger_identity_ambiguous")
    rows = [json.loads(line) for line in z.read(names[0]).splitlines() if line.strip()]
    return names[0], {row["filing_key"]:row for row in rows}


def instant(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "timestamp_timezone_missing")
    return result


def compare(old, new, observed_at):
    old_names, new_names = set(old.namelist()), set(new.namelist())
    require(old_names.issubset(new_names), "prior_file_removed")
    ledger, before = latest(old)
    new_ledger, after = latest(new)
    require(ledger == new_ledger and new.read(ledger).startswith(old.read(ledger)), "prior_ocr_receipts_changed")
    old_evidence = [n for n in old_names if "ocr-evidence/" in n and n.endswith(".json")]
    new_evidence = [n for n in new_names if "ocr-evidence/" in n and n.endswith(".json")]
    require(all(old.read(n) == new.read(n) for n in old_evidence), "prior_extraction_evidence_changed")
    due = {k:r for k,r in before.items() if r.get("status") == "retry_delayed"
           and (not r.get("next_attempt_at") or instant(r["next_attempt_at"]) <= instant(observed_at))}
    outcomes = []
    for key, prior in sorted(due.items()):
        current = after[key]
        advanced = int(current.get("attempts", 0)) > int(prior.get("attempts", 0))
        if advanced:
            require(instant(current["attempted_at"]) > instant(prior["attempted_at"]), "retry_time_not_advanced")
        outcomes.append({"filing_key":key, "before_error":prior.get("error_code"),
            "attempts_before":prior.get("attempts"), "attempts_after":current.get("attempts"),
            "retried":advanced, "status":current.get("status"), "error_code":current.get("error_code"),
            "next_attempt_at":current.get("next_attempt_at")})
    require(not due or any(r["retried"] for r in outcomes), "no_actual_due_retry_progress")
    return {"prior_ocr_receipts_preserved":True, "prior_extraction_files_preserved":len(old_evidence),
        "new_extraction_files":len(new_evidence)-len(old_evidence), "baseline_due_retries":len(due),
        "baseline_retries_attempted":sum(r["retried"] for r in outcomes),
        "baseline_retries_resolved":sum(r["retried"] and r["status"] != "retry_delayed" for r in outcomes),
        "current_total_technical_retries":sum(r.get("status") == "retry_delayed" for r in after.values()),
        "outcomes":outcomes}


def verify(baseline):
    from runtime_v2.database import connect
    connection = connect()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SET LOCAL statement_timeout = '120s'")
        report = {"probe":"polititrack_ocr_page_retry_acceptance_v1", "read_only":True,
            "execution":os.environ.get("CLOUD_RUN_EXECUTION", ""), "source":SOURCE, "namespaces":{}}
        for namespace in ("legislative", "executive"):
            old_head = baseline["heads"][namespace]
            cursor.execute("SELECT payload,snapshot_sha256 FROM runtime_state_snapshots WHERE namespace=%s AND snapshot_id=%s::uuid",
                           (namespace, old_head["snapshot_id"]))
            before = cursor.fetchone()
            require(before is not None and before[1] == old_head["payload_sha256"], "baseline_identity_mismatch")
            cursor.execute("SELECT s.payload,s.snapshot_sha256,s.source_revision,s.generation,s.snapshot_id::text "
                "FROM runtime_state_heads h JOIN runtime_state_snapshots s ON s.snapshot_id=h.snapshot_id WHERE h.namespace=%s", (namespace,))
            current = cursor.fetchone()
            require(current is not None and current[2] == SOURCE and current[3] > old_head["generation"], "release_head_missing")
            with archive(*before) as old, archive(current[0], current[1]) as new:
                evidence = compare(old, new, baseline["observed_at"])
            report["namespaces"][namespace] = {**evidence, "generation":current[3], "snapshot_id":current[4],
                                               "snapshot_sha256":current[1]}
        cursor.execute("SELECT sha256,status,page_count,payload IS NULL,result FROM runtime_source_uploads WHERE account_id=%s AND filing_key=%s",
            ("432b3395-e059-45e8-acf6-0d031d92f41d", "house|house:2026:9116331"))
        rows = cursor.fetchall()
        require(len(rows) == 1, "owner_upload_identity_changed")
        digest, status, pages, cleared, preview = rows[0]
        preview = json.loads(preview) if isinstance(preview, str) else preview
        require(digest == "58cefce89a3fe84a5d4893337e79b4bc9add769d02fac1869403456afd5a4343"
            and status == "needs_review" and pages == 2 and cleared and len(preview.get("rows", [])) == 5,
            "owner_upload_review_or_cleanup_changed")
        report["owner_upload"] = {"status":status, "pages":pages, "review_rows":5, "raw_payload_is_null":cleared}
        connection.rollback()
        report["result"] = "PASS"
        print(json.dumps(report), flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    verify(BASELINE)  # injected from the immutable baseline, never manufactured
