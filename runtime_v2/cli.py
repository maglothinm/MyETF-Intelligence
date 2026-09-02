"""Runtime v2 administration and job entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from .archive import extract_verified_zip
from .runner import JobRunner
from .store import NAMESPACES, PostgresSnapshotStore, StateStoreError


REPOSITORY_ID = 1349678672
PROTECTED_NAMESPACES = frozenset({"legislative", "executive", "ai"})
CANONICAL_REPOSITORY = "maglothinm/MyETF-Intelligence"
IMPORT_AUTHORITIES = {
    "legislative": {
        "workflow_path": ".github/workflows/legislative_trade_tracker_v2.yml",
        "artifact_name": "legislative-tracker-state",
        "job_name": "track",
    },
    "executive": {
        "workflow_path": ".github/workflows/executive_trade_tracker.yml",
        "artifact_name": "executive-tracker-state",
        "job_name": "track",
    },
    "ai": {
        "workflow_path": ".github/workflows/ai_filing_analyst.yml",
        "artifact_name": "ai-analysis-state",
        "job_name": "analyze",
    },
}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
GIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def _validated_provenance(path: Path, namespace: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateStoreError("migration provenance is unreadable") from exc
    required = {
        "repository_id",
        "repository_full_name",
        "workflow_path",
        "artifact_name",
        "artifact_id",
        "artifact_digest",
        "archive_sha256",
        "run_id",
        "run_attempt",
        "job_id",
        "job_name",
        "head_sha",
        "head_branch",
        "conclusion",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise StateStoreError("migration provenance is incomplete")
    expected = IMPORT_AUTHORITIES[namespace]
    if (
        value["repository_id"] != REPOSITORY_ID
        or value["repository_full_name"] != CANONICAL_REPOSITORY
        or value.get("namespace") not in {None, namespace}
        or value["workflow_path"] != expected["workflow_path"]
        or value["artifact_name"] != expected["artifact_name"]
        or value["job_name"] != expected["job_name"]
        or value["head_branch"] != "main"
        or value["conclusion"] != "success"
    ):
        raise StateStoreError("migration provenance does not identify canonical PolitiTrack state")
    if not all(
        isinstance(value[key], int) and value[key] > 0
        for key in ("artifact_id", "run_id", "run_attempt", "job_id")
    ):
        raise StateStoreError("migration provenance contains invalid GitHub identifiers")
    if not isinstance(value["head_sha"], str) or not GIT_SHA_PATTERN.fullmatch(value["head_sha"]):
        raise StateStoreError("migration provenance contains an invalid source revision")
    artifact_digest = str(value["artifact_digest"])
    archive_digest = str(value["archive_sha256"])
    if artifact_digest.startswith("sha256:"):
        artifact_digest = artifact_digest.removeprefix("sha256:")
    if not SHA256_PATTERN.fullmatch(artifact_digest) or not SHA256_PATTERN.fullmatch(archive_digest):
        raise StateStoreError("migration provenance contains an invalid artifact digest")
    if artifact_digest != archive_digest:
        raise StateStoreError("downloaded artifact does not match GitHub's artifact digest")
    value["artifact_digest"] = "sha256:" + artifact_digest
    value["archive_sha256"] = archive_digest
    return value


def _normalize_import(source: Path, destination: Path) -> dict:
    if not source.is_dir():
        raise StateStoreError("migration input is not a directory")
    if any(candidate.is_symlink() for candidate in source.resolve().rglob("*")):
        raise StateStoreError("migration input contains a symbolic link")
    states = list(source.resolve().rglob("state.json"))
    if len(states) != 1:
        raise StateStoreError("migration input must contain exactly one state.json")
    payload = json.loads(states[0].read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("last_success_utc"), str):
        raise StateStoreError("migration state has no successful-state marker")
    shutil.copytree(states[0].parent, destination)
    return payload


def _verify_import_archive(provenance: dict, archive: Path) -> None:
    candidate = archive.expanduser().resolve()
    if not candidate.is_file():
        raise StateStoreError("migration archive path is not readable")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if digest != provenance["archive_sha256"]:
        raise StateStoreError("migration archive changed after its receipt was created")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-db", help="Create additive Runtime v2 tables")
    init.add_argument("--with-vault", action="store_true", help="Also create the existing Filing Vault schema")
    run = commands.add_parser("run", help="Run one independently scheduled producer")
    run.add_argument("job", choices=("legislative", "executive", "ai", "dashboard"))
    status = commands.add_parser("status", help="Print current heads and latest job conclusions")
    status.add_argument("--pretty", action="store_true")
    ingest = commands.add_parser("import-directory", help="Import one provenance-verified GitHub artifact")
    ingest.add_argument("namespace", choices=tuple(sorted(PROTECTED_NAMESPACES)))
    ingest.add_argument("directory", type=Path)
    ingest.add_argument("--provenance", type=Path, required=True)
    ingest.add_argument("--archive", type=Path, required=True)
    cloud = commands.add_parser("import-gcs", help="Import one provenance-verified artifact from private GCS")
    cloud.add_argument("namespace", choices=tuple(sorted(PROTECTED_NAMESPACES)))
    cloud.add_argument("--bucket", required=True)
    cloud.add_argument("--archive-object", required=True)
    cloud.add_argument("--provenance-object", required=True)
    return parser


def _import_snapshot(store, namespace: str, source: Path, receipt: Path, archive: Path):
    provenance = _validated_provenance(receipt, namespace)
    _verify_import_archive(provenance, archive)
    with tempfile.TemporaryDirectory(prefix="polititrack-import-") as raw:
        normalized = Path(raw) / namespace
        state = _normalize_import(source, normalized)
        provenance = {
            **provenance,
            "last_success_utc": state["last_success_utc"],
            "authority": "github_actions_migration",
        }
        with store.locked(namespace) as locked:
            if locked.head() is not None:
                raise StateStoreError(f"{namespace} already has a durable head; refusing replacement")
            return locked.commit(
                normalized,
                expected_parent_sha256=None,
                source_revision=provenance["head_sha"],
                provenance=provenance,
                allow_initial=True,
            )


def _safe_gcs_object(value: str) -> str:
    path = value.strip()
    if not path.startswith("migration/") or "\\" in path or any(part in {"", ".", ".."} for part in path.split("/")):
        raise StateStoreError("migration object path is unsafe")
    return path


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = PostgresSnapshotStore()
    if args.command == "init-db":
        store.initialize_schema()
        if args.with_vault:
            from backend.filing_vault import configured_service
            from .database import sqlalchemy_engine

            import os

            config = {key: value for key, value in os.environ.items() if key.startswith("VAULT_")}
            if not config.get("VAULT_DATABASE_URL") and not os.environ.get("DATABASE_URL"):
                config["VAULT_ENGINE"] = sqlalchemy_engine()
            configured_service(config).init_schema()
        print(json.dumps({"result": "runtime_v2_schema_created", "protected_state_changed": False}))
        return 0
    if args.command == "status":
        print(json.dumps(store.status(), indent=2 if args.pretty else None, sort_keys=True))
        return 0
    if args.command == "run":
        head = JobRunner(store).run(args.job)
        print(json.dumps({
            "result": "success",
            "namespace": head.namespace,
            "generation": head.generation,
            "snapshot_sha256": head.snapshot_sha256,
        }, sort_keys=True))
        return 0
    if args.command == "import-directory":
        head = _import_snapshot(store, args.namespace, args.directory, args.provenance, args.archive)
    else:
        try:
            from google.cloud import storage
        except ImportError as exc:  # pragma: no cover - image dependency failure
            raise StateStoreError("Google Cloud Storage dependency is unavailable") from exc
        if not args.bucket or "/" in args.bucket or "\\" in args.bucket:
            raise StateStoreError("migration bucket name is unsafe")
        archive_object = _safe_gcs_object(args.archive_object)
        provenance_object = _safe_gcs_object(args.provenance_object)
        with tempfile.TemporaryDirectory(prefix="polititrack-gcs-import-") as raw:
            workspace = Path(raw)
            archive = workspace / "artifact.zip"
            receipt = workspace / "receipt.json"
            client = storage.Client()
            bucket = client.bucket(args.bucket)
            bucket.blob(archive_object).download_to_filename(archive)
            bucket.blob(provenance_object).download_to_filename(receipt)
            extracted = workspace / "extracted"
            provenance = _validated_provenance(receipt, args.namespace)
            _verify_import_archive(provenance, archive)
            extract_verified_zip(archive, extracted)
            head = _import_snapshot(store, args.namespace, extracted, receipt, archive)
    print(json.dumps({
        "result": "imported",
        "namespace": head.namespace,
        "generation": head.generation,
        "snapshot_sha256": head.snapshot_sha256,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StateStoreError, OSError, ValueError) as exc:
        print(f"Runtime v2 refused the operation: {exc}", file=sys.stderr)
        raise SystemExit(1)
