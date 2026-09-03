import json
from datetime import datetime
from pathlib import Path

import pytest

from runtime_v2.cli import _validated_provenance


ROOT = Path("docs/runtime-v2/phase3")
EXPECTED = {
    "legislative": {
        "archive_sha256": "a1a45416b4e6467e06493e8723f264aa11b9a20b8c3b1081d49b08b8de538394",
        "snapshot_sha256": "f33c72c058d1cb6f4bd8e240c20614bae9c6a3b121fa351b9ac3031f84e6858e",
        "artifact_id": 9881049089,
        "job_id": 100546743583,
        "run_id": 33723283663,
        "file_count": 7,
    },
    "executive": {
        "archive_sha256": "9be04931374289cf51afd2cb0b1670564b006dad21105025d77c9c2e95c04c8d",
        "snapshot_sha256": "73ec5a75b4f5b01dead5af2d8e36be26f3a41db06c3810e4cd60697d6d2a5a14",
        "artifact_id": 9881124215,
        "job_id": 100547268592,
        "run_id": 33723462162,
        "file_count": 4,
    },
    "ai": {
        "archive_sha256": "30ebd04c7418d64846dc53c84610d2a22abfe1d7a9e48121f4faa74468abab36",
        "snapshot_sha256": "80d4729e941e33443b905e8f208ad5db4361f10e59ffb28658b9d6631ceee931",
        "artifact_id": 9827727750,
        "job_id": 100089268533,
        "run_id": 33579058808,
        "file_count": 163,
    },
}


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.mark.parametrize("namespace", sorted(EXPECTED))
def test_phase3_migration_receipt_is_import_compatible(namespace: str) -> None:
    path = ROOT / f"{namespace}-receipt.json"
    receipt = _validated_provenance(path, namespace)
    expected = EXPECTED[namespace]

    assert receipt["archive_sha256"] == expected["archive_sha256"]
    assert receipt["artifact_digest"] == "sha256:" + expected["archive_sha256"]
    assert receipt["artifact_id"] == expected["artifact_id"]
    assert receipt["job_id"] == expected["job_id"]
    assert receipt["run_id"] == expected["run_id"]


@pytest.mark.parametrize("namespace", sorted(EXPECTED))
def test_phase3_receipt_records_success_and_inventory_evidence(namespace: str) -> None:
    receipt = json.loads((ROOT / f"{namespace}-receipt.json").read_text(encoding="utf-8"))
    expected = EXPECTED[namespace]

    assert receipt["archive_hash_matches_github_digest"] is True
    assert receipt["artifact_created_within_job_window"] is True
    assert receipt["complete_required_inventory_verified"] is True
    assert receipt["producer_head_is_ancestor_of_phase3_main"] is True
    assert receipt["state_marker_verified"] is True
    assert receipt["archive_file_count"] == expected["file_count"]
    assert len(receipt["archive_inventory_sha256"]) == 64
    assert receipt["expected_runtime_v2_generation"] == 1
    assert receipt["expected_runtime_v2_snapshot_sha256"] == expected["snapshot_sha256"]
    assert receipt["head_branch"] == "main"
    assert receipt["conclusion"] == "success"
    assert _time(receipt["job_started_at"]) <= _time(receipt["artifact_created_at"]) <= _time(receipt["job_completed_at"])


def test_phase3_required_state_files_are_recorded() -> None:
    legislative = json.loads((ROOT / "legislative-receipt.json").read_text(encoding="utf-8"))
    executive = json.loads((ROOT / "executive-receipt.json").read_text(encoding="utf-8"))
    ai = json.loads((ROOT / "ai-receipt.json").read_text(encoding="utf-8"))

    assert set(legislative["required_files"]) == {
        "filings.jsonl",
        "historical-backfill.jsonl",
        "pending-review.jsonl",
        "purchases.jsonl",
        "runs.jsonl",
        "state.json",
        "transactions.jsonl",
    }
    assert set(executive["required_files"]) == {
        "filings.jsonl",
        "pending-review.jsonl",
        "runs.jsonl",
        "state.json",
    }
    assert set(ai["required_top_level_files"]) == {
        "analyses.jsonl",
        "investor-edge-leaderboard.json",
        "investor-edge-observations.json",
        "investor-edge-profiles.json",
        "runs.jsonl",
        "state.json",
    }
    assert ai["nested_archive_file_count"] == 157
