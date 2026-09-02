"""Private evidence storage extending the application's Supabase architecture.

Objects are content-addressed. The dev filesystem backend must be explicitly
selected and must be outside every repository checkout. Public bucket URLs and
storage paths are never returned to API clients.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import quote, urlsplit

import requests


class StorageError(Exception):
    """Safe, classified error; never include credentials, paths or response text."""


def validate_key(key: str) -> str:
    if (
        not isinstance(key, str)
        or not key.startswith("filings/")
        or "\\" in key
        or len(key) > 700
        or any(part in ("", ".", "..") for part in key.split("/"))
        or not re.fullmatch(r"[a-zA-Z0-9/_\-.]+", key)
    ):
        raise StorageError("Invalid evidence object key")
    return key


def object_key(record: dict, digest: str, content_type: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise StorageError("Invalid evidence digest")
    source = record["source"]
    if source not in {"house", "senate", "oge", "executive_agency"}:
        raise StorageError("Invalid evidence source")
    # Stable opaque path components avoid exposing names and reject traversal.
    filer = hashlib.sha256(
        str(record.get("filer_id") or "unknown").encode()
    ).hexdigest()[:24]
    filing = hashlib.sha256(record["filing_id"].encode()).hexdigest()
    suffix = "pdf" if content_type == "application/pdf" else "html"
    return validate_key(f"filings/{source}/{filer}/{filing}/{digest}.{suffix}")


class FileObjectStore:
    """Atomic dev/test storage; never use a checkout as a PDF cache."""

    def __init__(self, root, *, repository_root=None, max_bytes=25 * 1024 * 1024):
        self.root = Path(root).expanduser().resolve()
        if repository_root:
            repo = Path(repository_root).resolve()
            if self.root == repo or repo in self.root.parents:
                raise ValueError("VAULT_FILE_ROOT must be outside the repository")
        # Detect the primary checkout too when this code runs from a worktree.
        if any((parent / ".git").exists() for parent in (self.root, *self.root.parents)):
            raise ValueError("VAULT_FILE_ROOT must be outside all Git checkouts")
        self.max_bytes = max_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        path = self.root.joinpath(*PurePosixPath(validate_key(key)).parts)
        resolved = path.resolve()
        if self.root not in resolved.parents:
            raise StorageError("Evidence object path rejected")
        if any(
            parent.is_symlink()
            for parent in (path, *path.parents)
            if parent != self.root.parent
        ):
            raise StorageError("Evidence object symlink rejected")
        return path

    def put(self, key, body, content_type):
        if len(body) > self.max_bytes:
            raise StorageError("Evidence object exceeds maximum size")
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Same key always means the same bytes; a corrupted object can be
            # repaired atomically after authoritative retrieval.
            descriptor, temporary = tempfile.mkstemp(prefix=".upload-", dir=path.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        except OSError as exc:
            raise StorageError("Evidence storage write unavailable") from exc

    def get(self, key):
        path = self._path(key)
        try:
            if not path.exists():
                return None
            if path.stat().st_size > self.max_bytes:
                raise StorageError("Evidence object exceeds maximum size")
            with path.open("rb") as stream:
                body = stream.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise StorageError("Evidence object exceeds maximum size")
            return body
        except OSError as exc:
            raise StorageError("Evidence storage read unavailable") from exc

    def delete(self, key):
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Evidence storage deletion unavailable") from exc

    def list_objects(self):
        try:
            for path in self.root.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    key = path.relative_to(self.root).as_posix()
                    if key.startswith("filings/"):
                        yield validate_key(key)
        except OSError as exc:
            raise StorageError("Evidence storage listing unavailable") from exc


class GoogleCloudObjectStore:
    """Private GCS evidence store with fail-closed bucket-policy checks."""

    def __init__(
        self,
        bucket,
        *,
        client=None,
        max_bytes=25 * 1024 * 1024,
    ):
        if not isinstance(bucket, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", bucket
        ):
            raise ValueError("VAULT_GCS_BUCKET must be a valid private bucket name")
        if max_bytes < 1024 or max_bytes > 50 * 1024 * 1024:
            raise ValueError("Evidence object size limit is invalid")
        if client is None:
            try:
                from google.cloud import storage
            except ImportError as exc:  # pragma: no cover - runtime dependency failure
                raise StorageError("Google Cloud evidence storage is unavailable") from exc
            client = storage.Client()
        self.client = client
        self.bucket = client.bucket(bucket)
        self.max_bytes = max_bytes
        try:
            self.bucket.reload()
            policy = self.bucket.iam_configuration
            if not bool(policy.uniform_bucket_level_access_enabled):
                raise StorageError(
                    "Evidence bucket requires uniform bucket-level access"
                )
            if str(policy.public_access_prevention).strip().lower() != "enforced":
                raise StorageError(
                    "Evidence bucket requires public access prevention enforcement"
                )
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Unable to verify private evidence bucket") from exc

    def _blob(self, key):
        return self.bucket.blob(validate_key(key))

    def put(self, key, body, content_type):
        if not isinstance(body, (bytes, bytearray)):
            raise StorageError("Evidence object body must be bytes")
        body = bytes(body)
        if len(body) > self.max_bytes:
            raise StorageError("Evidence object exceeds maximum size")
        blob = self._blob(key)
        try:
            if blob.exists():
                existing = self.get(key)
                if existing != body:
                    raise StorageError("Evidence object key already contains different bytes")
                return
            blob.upload_from_string(
                body,
                content_type=content_type,
                if_generation_match=0,
            )
        except StorageError:
            raise
        except Exception as exc:
            # A same-key race is safe only when the retained bytes are identical.
            try:
                if self.get(key) == body:
                    return
            except StorageError:
                pass
            raise StorageError("Evidence storage write unavailable") from exc

    def get(self, key):
        blob = self._blob(key)
        try:
            if not blob.exists():
                return None
            blob.reload()
            if blob.size is None or int(blob.size) > self.max_bytes:
                raise StorageError("Evidence object exceeds maximum size")
            body = blob.download_as_bytes(if_generation_match=blob.generation)
            if len(body) > self.max_bytes:
                raise StorageError("Evidence object exceeds maximum size")
            return body
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Evidence storage read unavailable") from exc

    def delete(self, key):
        blob = self._blob(key)
        try:
            if not blob.exists():
                return
            blob.reload()
            blob.delete(if_generation_match=blob.generation)
        except Exception as exc:
            raise StorageError("Evidence storage deletion unavailable") from exc

    def list_objects(self):
        try:
            for blob in self.client.list_blobs(self.bucket, prefix="filings/"):
                yield validate_key(str(blob.name))
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("Evidence storage listing unavailable") from exc


class SupabaseObjectStore:
    """Bounded REST client to the existing Supabase private object store.

    A service role credential belongs only on the server. Bucket privacy is
    verified during construction; the adapter cannot operate on a public bucket.
    No bucket or permission is silently created or changed.
    """

    def __init__(
        self,
        url,
        key,
        bucket,
        *,
        session=None,
        max_bytes=25 * 1024 * 1024,
    ):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError("VAULT_SUPABASE_URL must be an HTTPS Supabase project origin")
        if not key or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", bucket or ""):
            raise ValueError("Private storage credentials and bucket are required")
        self.base = url.rstrip("/") + "/storage/v1"
        self.bucket = bucket
        self.max_bytes = max_bytes
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.headers = {"Authorization": "Bearer " + key, "apikey": key}
        response = self._request("GET", "/bucket/" + quote(bucket, safe=""))
        try:
            info = response.json()
        except ValueError as exc:
            raise StorageError("Unable to verify private evidence bucket") from exc
        finally:
            response.close()
        if info.get("public") is not False:
            raise StorageError("Evidence bucket must be private")

    def _request(self, method, path, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        try:
            response = self.session.request(
                method,
                self.base + path,
                headers=headers,
                timeout=(5, 25),
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise StorageError("Private evidence store is temporarily unavailable") from exc
        if response.status_code not in {200, 201, 204}:
            if (
                response.status_code == 404
                and method == "GET"
                and path.startswith("/object/")
            ):
                return response
            response.close()
            raise StorageError("Private evidence store rejected the operation")
        return response

    def _object_path(self, key):
        return (
            "/object/"
            + quote(self.bucket, safe="")
            + "/"
            + quote(validate_key(key), safe="/")
        )

    def put(self, key, body, content_type):
        if len(body) > self.max_bytes:
            raise StorageError("Evidence object exceeds maximum size")
        response = self._request(
            "POST",
            self._object_path(key),
            data=body,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        response.close()

    def get(self, key):
        response = self._request("GET", self._object_path(key), stream=True)
        try:
            if response.status_code == 404:
                return None
            chunks, size = [], 0
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > self.max_bytes:
                    raise StorageError("Evidence object exceeds maximum size")
                chunks.append(chunk)
            return b"".join(chunks)
        except requests.RequestException as exc:
            raise StorageError("Private evidence store read unavailable") from exc
        finally:
            response.close()

    def delete(self, key):
        response = self._request(
            "DELETE",
            "/object/" + quote(self.bucket, safe=""),
            json={"prefixes": [validate_key(key)]},
        )
        response.close()

    def list_objects(self):
        # Storage listing is prefix-based and paginated. A finite limit prevents
        # a malformed provider response from creating an unbounded traversal.
        pending, visited, entries = ["filings"], set(), 0
        while pending:
            prefix = pending.pop()
            if prefix in visited:
                continue
            visited.add(prefix)
            offset = 0
            while True:
                response = self._request(
                    "POST",
                    "/object/list/" + quote(self.bucket, safe=""),
                    json={
                        "prefix": prefix,
                        "limit": 1000,
                        "offset": offset,
                        "sortBy": {"column": "name", "order": "asc"},
                    },
                )
                try:
                    rows = response.json()
                except ValueError as exc:
                    raise StorageError("Invalid evidence storage inventory") from exc
                finally:
                    response.close()
                if not isinstance(rows, list):
                    raise StorageError("Invalid evidence storage inventory")
                for row in rows:
                    entries += 1
                    if entries > 1_000_000:
                        raise StorageError("Evidence inventory safety limit reached")
                    name = row.get("name", "")
                    if not isinstance(name, str) or "/" in name:
                        raise StorageError("Invalid evidence storage inventory")
                    key = validate_key(prefix + "/" + name)
                    if row.get("id") is None:
                        pending.append(key)
                    else:
                        yield key
                if len(rows) < 1000:
                    break
                offset += len(rows)
