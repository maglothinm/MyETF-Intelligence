"""Deterministic, hash-verified archives for immutable runtime snapshots."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


MAX_FILES = 100_000
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


class SnapshotArchiveError(RuntimeError):
    """The snapshot archive is unsafe, malformed, or fails integrity checks."""


@dataclass(frozen=True)
class PackedSnapshot:
    payload: bytes
    sha256: str
    manifest: dict[str, Any]


def _safe_name(name: str) -> str:
    if not name or "\\" in name or name.startswith("/"):
        raise SnapshotArchiveError("snapshot contains an unsafe path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SnapshotArchiveError("snapshot contains an unsafe path")
    return path.as_posix()


def _directory_files(root: Path) -> list[tuple[str, Path]]:
    root = root.resolve()
    if not root.is_dir():
        raise SnapshotArchiveError("snapshot source is not a directory")
    files: list[tuple[str, Path]] = []
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise SnapshotArchiveError("snapshot source contains a symbolic link")
        if candidate.is_file():
            name = _safe_name(candidate.relative_to(root).as_posix())
            files.append((name, candidate))
    files.sort(key=lambda item: item[0])
    if not files:
        raise SnapshotArchiveError("snapshot source is empty")
    if len(files) > MAX_FILES:
        raise SnapshotArchiveError("snapshot contains too many files")
    return files


def pack_directory(root: Path) -> PackedSnapshot:
    """Pack a directory with stable ordering, metadata, and content hashes."""
    entries: list[dict[str, Any]] = []
    total = 0
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, candidate in _directory_files(root):
            data = candidate.read_bytes()
            total += len(data)
            if total > MAX_UNCOMPRESSED_BYTES:
                raise SnapshotArchiveError("snapshot exceeds the uncompressed size limit")
            digest = hashlib.sha256(data).hexdigest()
            entries.append({"path": name, "size": len(data), "sha256": digest})
            info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    payload = stream.getvalue()
    manifest = {
        "schema_version": 1,
        "file_count": len(entries),
        "uncompressed_bytes": total,
        "files": entries,
    }
    manifest["content_sha256"] = hashlib.sha256(
        json.dumps(entries, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return PackedSnapshot(payload, hashlib.sha256(payload).hexdigest(), manifest)


def _normalized_manifest(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    files = value.get("files")
    if value.get("schema_version") != 1 or not isinstance(files, list):
        raise SnapshotArchiveError("snapshot manifest has an unsupported schema")
    result: dict[str, dict[str, Any]] = {}
    for entry in files:
        if not isinstance(entry, Mapping):
            raise SnapshotArchiveError("snapshot manifest contains a malformed entry")
        name = _safe_name(str(entry.get("path") or ""))
        if name in result:
            raise SnapshotArchiveError("snapshot manifest contains a duplicate path")
        size = entry.get("size")
        digest = entry.get("sha256")
        if not isinstance(size, int) or size < 0 or not isinstance(digest, str) or len(digest) != 64:
            raise SnapshotArchiveError("snapshot manifest contains invalid integrity data")
        result[name] = {"path": name, "size": size, "sha256": digest}
    if len(result) > MAX_FILES or sum(item["size"] for item in result.values()) > MAX_UNCOMPRESSED_BYTES:
        raise SnapshotArchiveError("snapshot manifest exceeds safety limits")
    return result


def unpack_directory(
    payload: bytes,
    destination: Path,
    *,
    expected_sha256: str,
    expected_manifest: Mapping[str, Any],
) -> None:
    """Verify and extract a snapshot without trusting archive paths or metadata."""
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise SnapshotArchiveError("snapshot payload hash does not match its head")
    manifest = _normalized_manifest(expected_manifest)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload), "r")
    except zipfile.BadZipFile as exc:
        raise SnapshotArchiveError("snapshot payload is not a valid ZIP archive") from exc
    with archive:
        members = archive.infolist()
        if len(members) != len(manifest):
            raise SnapshotArchiveError("snapshot archive and manifest file counts differ")
        for member in members:
            name = _safe_name(member.filename)
            if name in seen or member.is_dir():
                raise SnapshotArchiveError("snapshot archive contains a duplicate or directory entry")
            seen.add(name)
            expected = manifest.get(name)
            if expected is None or member.file_size != expected["size"]:
                raise SnapshotArchiveError("snapshot archive does not match its manifest")
            if member.file_size > MAX_UNCOMPRESSED_BYTES:
                raise SnapshotArchiveError("snapshot member exceeds the safety limit")
            data = archive.read(member)
            if hashlib.sha256(data).hexdigest() != expected["sha256"]:
                raise SnapshotArchiveError("snapshot file hash does not match its manifest")
            target = (destination / Path(*PurePosixPath(name).parts)).resolve()
            if os.path.commonpath((str(destination), str(target))) != str(destination):
                raise SnapshotArchiveError("snapshot extraction escaped its destination")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    if seen != set(manifest):
        raise SnapshotArchiveError("snapshot archive is incomplete")


def extract_verified_zip(path: Path, destination: Path) -> None:
    """Extract a digest-verified external ZIP without trusting member paths."""
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise SnapshotArchiveError("migration artifact is not a readable ZIP archive") from exc
    with archive:
        members = archive.infolist()
        files = [member for member in members if not member.is_dir()]
        if not files or len(files) > MAX_FILES:
            raise SnapshotArchiveError("migration artifact has an invalid file count")
        if sum(member.file_size for member in files) > MAX_UNCOMPRESSED_BYTES:
            raise SnapshotArchiveError("migration artifact exceeds the uncompressed size limit")
        seen: set[str] = set()
        for member in members:
            name = _safe_name(member.filename.rstrip("/"))
            if name in seen:
                raise SnapshotArchiveError("migration artifact contains a duplicate path")
            seen.add(name)
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise SnapshotArchiveError("migration artifact contains a symbolic link")
            target = (destination / Path(*PurePosixPath(name).parts)).resolve()
            if os.path.commonpath((str(destination), str(target))) != str(destination):
                raise SnapshotArchiveError("migration extraction escaped its destination")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(member)
            if len(data) != member.file_size:
                raise SnapshotArchiveError("migration artifact member is incomplete")
            target.write_bytes(data)
