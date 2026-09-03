import json

import pytest

from runtime_v2 import acceptance
from runtime_v2.store import StateStoreError


class _Store:
    def status(self):
        return {
            "heads": [
                {
                    "namespace": "legislative",
                    "generation": 1,
                    "snapshot_sha256": "a" * 64,
                }
            ],
            "latest_runs": [],
        }


def test_acceptance_receipt_contains_runtime_status(monkeypatch):
    monkeypatch.setattr(acceptance, "_utc_now", lambda: "2026-09-03T12:00:00Z")
    receipt = acceptance.build_receipt(_Store())
    assert receipt["schema_version"] == 1
    assert receipt["generated_at_utc"] == "2026-09-03T12:00:00Z"
    assert receipt["runtime"]["heads"][0]["namespace"] == "legislative"
    assert receipt["runtime"]["latest_runs"] == []
    json.dumps(receipt)


@pytest.mark.parametrize("value", ["", "bucket/name", "bucket\\name"])
def test_acceptance_bucket_rejects_unsafe_names(value):
    with pytest.raises(StateStoreError, match="bucket"):
        acceptance._safe_bucket(value)


@pytest.mark.parametrize(
    "value",
    [
        "status.json",
        "phase3/status.json",
        "phase3/acceptance/../status.json",
        "phase3/acceptance\\status.json",
    ],
)
def test_acceptance_object_rejects_unsafe_paths(value):
    with pytest.raises(StateStoreError, match="object"):
        acceptance._safe_object(value)


def test_acceptance_object_accepts_phase3_namespace():
    assert acceptance._safe_object("phase3/acceptance/status.json") == "phase3/acceptance/status.json"
