"""Authoritative, bounded filing retrieval; never a public URL proxy.

Adapters accept records from the server's approved catalog, not request URLs.
Source checks below establish the state of an exact document endpoint. They do
not pretend that HTTP headers discover separately published amendments. Those
relationships must arrive through an authoritative catalog reconciliation.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
import urllib3


DEFAULT_MAX_BYTES = 32 * 1024 * 1024
HOUSE_HOSTS = frozenset({"disclosures-clerk.house.gov"})
SENATE_HOSTS = frozenset({"efdsearch.senate.gov"})
OGE_HOSTS = frozenset({"oge.gov", "www.oge.gov", "www2.oge.gov", "extapps2.oge.gov"})
ACCESS_CLASSES = frozenset({"DIRECT_PUBLIC", "ACKNOWLEDGEMENT_REQUIRED", "REQUEST_REQUIRED", "UNAVAILABLE"})


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ProviderError(RuntimeError):
    """Safe, classified errors; never include response bodies or credentials."""

    def __init__(self, code: str, message: str, *, retryable: bool = False, status: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status = status


@dataclass(frozen=True)
class RetrievedDocument:
    body: bytes
    content_type: str
    document_url: str
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes
    url: str
    set_cookies: tuple[str, ...] = ()


def normalize_filing(record: Mapping[str, Any]) -> dict[str, Any]:
    """Keep canonical and source identities; never synthesize a document URL."""
    result = dict(record)
    filing_id = record.get("filing_key") or record.get("filing_id")
    if not isinstance(filing_id, str) or not filing_id.strip():
        raise ProviderError("INVALID_FILING", "A retained canonical filing ID is required.", status=400)
    source = str(record.get("source") or "").strip().lower()
    if source in {"executive", "agency", "executive-agency"}:
        source = "executive_agency"
    if source not in {"house", "senate", "oge", "executive_agency"}:
        raise ProviderError("UNSUPPORTED_SOURCE", "This source has no approved filing provider.", status=422)
    if any(value is not None and not isinstance(value, Mapping)
           for value in (record.get("metadata"), record.get("source_metadata"))):
        raise ProviderError("INVALID_FILING", "Source metadata must be a structured object.", status=400)
    metadata = dict(record.get("metadata") or {})
    metadata.update(dict(record.get("source_metadata") or {}))
    official = str(record.get("official_source_url") or record.get("source_url") or record.get("url") or "")
    mode = str(record.get("access_mode") or metadata.get("access_mode") or "").lower()
    access = str(record.get("access_class") or metadata.get("access_class") or "").strip().upper()
    method = str(record.get("access_method") or metadata.get("access_method") or "").strip().upper()
    requested_flags = (record.get("requires_request"), metadata.get("requires_request"))
    requested_markers = (record.get("access_mode"), metadata.get("access_mode"),
                         record.get("access_method"), metadata.get("access_method"),
                         record.get("access_class"), metadata.get("access_class"))
    requested = (any(value is True or (isinstance(value, str) and value.lower().strip() in {"true", "1", "yes"}) for value in requested_flags)
                 or any(str(value).strip().upper() in {"REQUEST", "REQUEST_REQUIRED", "OGE_FORM_201", "FORM_201", "AGENCY_REQUEST"}
                        for value in requested_markers))
    if requested or access == "REQUEST_REQUIRED":
        access = "REQUEST_REQUIRED"
    elif access not in ACCESS_CLASSES:
        if source in {"house", "senate"} or (source == "oge" and mode == "direct"):
            access = "ACKNOWLEDGEMENT_REQUIRED"
        elif source == "executive_agency" and mode == "direct":
            access = "DIRECT_PUBLIC"
        else:
            access = "UNAVAILABLE"
    document_url = str(record.get("document_url") or metadata.get("document_url") or "")
    if not document_url and (source in {"house", "senate"} or mode == "direct"):
        document_url = official
    if access == "REQUEST_REQUIRED":
        method = method or ("OGE_FORM_201" if source == "oge" else "AGENCY_REQUEST")
    elif source == "senate":
        method = method or "SENATE_EFD"
    else:
        method = method or ("DIRECT_PDF" if document_url else "UNAVAILABLE")
    result.update({
        "filing_id": filing_id,
        "external_filing_id": record.get("external_filing_id") or record.get("report_id") or metadata.get("document_id") or "",
        "filer_id": record.get("filer_id") or record.get("politician_id") or "",
        "filer_name": record.get("filer_name") or record.get("filer") or record.get("name") or "Unknown filer",
        "source": source,
        "filing_type": record.get("filing_type") or record.get("report_type") or metadata.get("report_type") or "Disclosure",
        "filing_date": record.get("filing_date") or record.get("filed_date") or "",
        "report_period": record.get("report_period") or metadata.get("filing_year") or "",
        "official_source_url": official,
        "document_url": document_url,
        "access_class": access,
        "access_method": method,
        "requires_request": access == "REQUEST_REQUIRED",
        "source_metadata": metadata,
        "is_amended": record.get("is_amended") is True,
        "supersedes_filing_id": record.get("supersedes_filing_id") or "",
        "superseded_by_filing_id": record.get("superseded_by_filing_id") or "",
    })
    return result


def validate_source_url(url: str, allowed_hosts: Iterable[str]) -> str:
    """Validate before DNS, including percent-encoded traversal and userinfo."""
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise ProviderError("UNSAFE_SOURCE_URL", "The source URL is not permitted.", status=422)
    if any(ord(char) <= 32 or ord(char) == 127 for char in url) or "\\" in url:
        raise ProviderError("UNSAFE_SOURCE_URL", "The source URL is not permitted.", status=422)
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        raise ProviderError("UNSAFE_SOURCE_URL", "The source URL is malformed.", status=422) from None
    allowed = {str(item).lower() for item in allowed_hosts}
    if (parsed.scheme != "https" or not host or host not in allowed or host.endswith(".")
            or parsed.username is not None or parsed.password is not None
            or port not in {None, 443} or parsed.fragment or "%" in parsed.netloc
            or not re.fullmatch(r"[a-z0-9.-]+", host)):
        raise ProviderError("UNSAFE_SOURCE_URL", "The URL is outside this source's approved HTTPS endpoints.", status=422)
    path = parsed.path or "/"
    decoded = path
    for _ in range(4):
        next_path = unquote(decoded)
        if next_path == decoded:
            break
        decoded = next_path
    if ("\\" in decoded or any(ord(char) <= 31 or ord(char) == 127 for char in decoded)
            or any(segment in {".", ".."} for segment in decoded.split("/")) or "%" in decoded):
        raise ProviderError("UNSAFE_SOURCE_URL", "The source URL contains an unsafe path.", status=422)
    return urlunsplit(("https", host, path, parsed.query, ""))


class SecureHTTPClient:
    """No proxies; validated public IP is the actual TLS connection destination.

    DNS is resolved again for every request/redirect, and all returned addresses
    must be public. Connecting to the selected literal IP while verifying TLS
    against the government hostname prevents DNS-rebinding between validation
    and connect. Injected pool/resolver functions are for deterministic tests.
    """

    def __init__(self, *, max_bytes: int = DEFAULT_MAX_BYTES, connect_timeout: float = 10,
                 read_timeout: float = 30, total_timeout: float = 60, retries: int = 2,
                 min_interval: float = 1.0, max_redirects: int = 3,
                 resolver: Callable[..., Any] | None = None,
                 pool_factory: Callable[..., Any] | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        if not 1 <= max_bytes <= 128 * 1024 * 1024 or not 0 <= retries <= 3 or not 0 <= max_redirects <= 5:
            raise ValueError("Invalid filing retrieval limits")
        if min(connect_timeout, read_timeout, total_timeout) <= 0 or min_interval < 0:
            raise ValueError("Invalid filing retrieval timeouts")
        self.max_bytes = max_bytes
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.total_timeout = total_timeout
        self.retries = retries
        self.min_interval = min_interval
        self.max_redirects = max_redirects
        self._resolver = resolver or socket.getaddrinfo
        self._pool_factory = pool_factory or urllib3.HTTPSConnectionPool
        self._clock = clock
        self._sleep = sleep
        self._rate_lock = threading.Lock()
        self._last: dict[str, float] = {}
        self._defer_until: dict[str, float] = {}

    def _address(self, host: str) -> str:
        try:
            answers = self._resolver(host, 443, type=socket.SOCK_STREAM)
            addresses = sorted({answer[4][0] for answer in answers})
        except (OSError, ValueError, TypeError):
            raise ProviderError("SOURCE_UNAVAILABLE", "The official source could not be resolved.", retryable=True) from None
        if not addresses:
            raise ProviderError("SOURCE_UNAVAILABLE", "The official source could not be resolved.", retryable=True)
        for value in addresses:
            try:
                address = ipaddress.ip_address(value)
            except ValueError:
                raise ProviderError("UNSAFE_SOURCE_ADDRESS", "The source resolved to an invalid address.", status=422) from None
            if (not address.is_global or address.is_multicast or address.is_unspecified
                    or getattr(address, "ipv4_mapped", None) or getattr(address, "sixtofour", None)
                    or getattr(address, "teredo", None) or "%" in value):
                raise ProviderError("UNSAFE_SOURCE_ADDRESS", "The source resolved to a non-public address.", status=422)
        return addresses[0]

    def _rate_limit(self, host: str) -> None:
        with self._rate_lock:
            now = self._clock()
            if self._defer_until.get(host, 0.0) > now:
                raise ProviderError("SOURCE_RATE_LIMITED", "The official source requested a retry delay. Try again later.", retryable=True, status=429)
            delay = max(0.0, self._last.get(host, now - self.min_interval) + self.min_interval - now)
            if delay:
                self._sleep(delay)
            self._last[host] = self._clock()

    def _retry_delay(self, response: SourceResponse) -> float:
        if response.status not in {429, 503}:
            return 0.0
        raw = response.headers.get("retry-after", "").strip()
        try:
            if re.fullmatch(r"\d{1,9}", raw):
                delay = float(raw)
            else:
                target = parsedate_to_datetime(raw)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                delay = max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0.0
        if delay:
            with self._rate_lock:
                host = urlsplit(response.url).hostname or ""
                self._defer_until[host] = self._clock() + delay
        return delay

    def _once(self, method: str, url: str, headers: Mapping[str, str], body: bytes | str | None) -> SourceResponse:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        address = self._address(host)
        self._rate_limit(host)
        pool = self._pool_factory(address, port=443, server_hostname=host,
                                  assert_hostname=host, cert_reqs="CERT_REQUIRED", maxsize=1, block=True)
        response = None
        started = self._clock()
        try:
            target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            request_headers = {"User-Agent": "PolitiTrack-FilingVault/1.0", **headers,
                               "Host": host, "Accept-Encoding": "identity"}
            response = pool.urlopen(method, target, body=body, headers=request_headers,
                                    redirect=False, retries=False, preload_content=False,
                                    timeout=urllib3.Timeout(connect=self.connect_timeout, read=self.read_timeout, total=self.total_timeout))
            response_headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            raw_length = response_headers.get("content-length")
            if raw_length is not None:
                if not raw_length.isdigit():
                    raise ProviderError("INVALID_DOCUMENT", "The source returned an invalid content length.")
                if int(raw_length) > self.max_bytes:
                    raise ProviderError("DOCUMENT_TOO_LARGE", "The official document exceeds the vault size limit.", status=413)
            if response_headers.get("content-encoding", "identity").lower() not in {"identity", ""}:
                raise ProviderError("INVALID_CONTENT_ENCODING", "Compressed source responses are not accepted.")
            chunks: list[bytes] = []
            size = 0
            if method != "HEAD":
                # read1 performs at most one underlying buffered read. A slow
                # peer cannot keep an accumulating read(64KiB) alive forever by
                # trickling bytes inside the socket's inactivity timeout.
                while True:
                    if self._clock() - started > self.total_timeout:
                        raise ProviderError("SOURCE_TIMEOUT", "The official source exceeded the retrieval time limit.", retryable=True)
                    chunk = response.read1(65536, decode_content=False)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise ProviderError("DOCUMENT_TOO_LARGE", "The official document exceeds the vault size limit.", status=413)
                    if self._clock() - started > self.total_timeout:
                        raise ProviderError("SOURCE_TIMEOUT", "The official source exceeded the retrieval time limit.", retryable=True)
                    chunks.append(chunk)
            cookie_headers = tuple(response.headers.getlist("Set-Cookie")) if hasattr(response.headers, "getlist") else ()
            return SourceResponse(response.status, response_headers, b"".join(chunks), url, cookie_headers)
        except (urllib3.exceptions.HTTPError, OSError):
            raise ProviderError("SOURCE_UNAVAILABLE", "The official source could not currently be reached.", retryable=True) from None
        finally:
            if response is not None:
                response.close()
                response.release_conn()
            pool.close()

    def request(self, method: str, url: str, *, allowed_hosts: Iterable[str],
                headers: Mapping[str, str] | None = None, body: bytes | str | None = None,
                follow_redirects: bool = True, allow_error_status: bool = False) -> SourceResponse:
        if method not in {"GET", "HEAD", "POST"}:
            raise ValueError("Unsupported source HTTP method")
        target = validate_source_url(url, allowed_hosts)
        active_headers = dict(headers or {})
        for redirect in range(self.max_redirects + 1):
            for attempt in range(self.retries + 1):
                try:
                    response = self._once(method, target, active_headers, body)
                except ProviderError as exc:
                    if not exc.retryable or exc.code == "SOURCE_RATE_LIMITED" or attempt == self.retries or method == "POST":
                        raise
                    self._sleep(min(4.0, 2.0 ** attempt))
                    continue
                retry_delay = self._retry_delay(response)
                if response.status in {408, 425, 429, 500, 502, 503, 504} and attempt < self.retries and method != "POST" and retry_delay <= 30:
                    delay = retry_delay or min(4.0, 2.0 ** attempt)
                    self._sleep(delay)
                    continue
                break
            if 300 <= response.status < 400 and follow_redirects:
                location = response.headers.get("location")
                if response.status not in {301, 302, 303, 307, 308} or not location or redirect == self.max_redirects:
                    raise ProviderError("UNSAFE_REDIRECT", "The source returned an invalid or excessive redirect chain.")
                next_target = validate_source_url(urljoin(target, location), allowed_hosts)
                if urlsplit(next_target).hostname != urlsplit(target).hostname:
                    active_headers = {key: value for key, value in active_headers.items() if key.lower() not in {"cookie", "authorization", "origin", "referer"}}
                target = next_target
                if response.status == 303:
                    method, body = "GET", None
                continue
            if not allow_error_status and response.status != 200:
                if response.status == 429 or retry_delay > 30:
                    raise ProviderError("SOURCE_RATE_LIMITED", "The official source requested a retry delay. Try again later.", retryable=True, status=429)
                if response.status in {401, 403}:
                    raise ProviderError("SOURCE_ACCESS_REQUIRED", "The official source requires its own access or acknowledgement process.", status=403)
                if response.status in {404, 410}:
                    raise ProviderError("SOURCE_NOT_FOUND", "This exact filing is no longer available at its recorded source.", status=404)
                raise ProviderError("SOURCE_UNAVAILABLE", "The official source returned an unsuccessful response.", retryable=response.status == 429 or response.status >= 500)
            return response
        raise ProviderError("UNSAFE_REDIRECT", "The source returned an excessive redirect chain.")


def _source_evidence(response: SourceResponse, scope: str) -> dict[str, Any]:
    evidence = {"checked_at": _utc(), "validation_scope": scope,
            "resolved_document_url": response.url,
            "etag": response.headers.get("etag", ""),
            "last_modified": response.headers.get("last-modified", ""),
            "source_http_status": response.status}
    if scope == "exact_document_content":
        evidence["validated_document_sha256"] = hashlib.sha256(response.body).hexdigest()
    return evidence


class FilingResourceProvider:
    source = ""
    allowed_hosts: frozenset[str] = frozenset()

    def __init__(self, *, http_client: SecureHTTPClient | None = None, acknowledged_sources: Iterable[str] = ()):
        self.http = http_client or SecureHTTPClient()
        self.acknowledged_sources = frozenset(acknowledged_sources)

    def resolve_filing(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = normalize_filing(record)
        if result["source"] != self.source:
            raise ProviderError("SOURCE_MISMATCH", "The record does not belong to this filing provider.", status=422)
        if result["official_source_url"]:
            validate_source_url(result["official_source_url"], self.allowed_hosts)
        if result["document_url"]:
            validate_source_url(result["document_url"], self.allowed_hosts)
        return result

    def _accessible(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = self.resolve_filing(record)
        if result["requires_request"]:
            raise ProviderError("REQUEST_REQUIRED", "This disclosure requires an OGE Form 201 or agency disclosure request; no document was retrieved.", status=403)
        if result["access_class"] == "UNAVAILABLE" or not result["document_url"]:
            raise ProviderError("SOURCE_UNAVAILABLE", "No approved direct document is available for this filing.", status=422)
        if self.source in {"oge", "executive_agency"} and result["access_class"] == "ACKNOWLEDGEMENT_REQUIRED" and self.source not in self.acknowledged_sources:
            raise ProviderError("SOURCE_ACKNOWLEDGEMENT_REQUIRED", "The source's acknowledgement must be reviewed and configured separately from the PolitiTrack notice.", status=403)
        return result

    def get_metadata(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = self._accessible(record)
        response = self.http.request("HEAD", result["document_url"], allowed_hosts=self.allowed_hosts,
                                     headers={"Accept": "application/pdf"}, allow_error_status=True)
        # Some official endpoints disallow HEAD. A fully checked GET establishes
        # source evidence; a method failure alone must never stamp validation.
        if response.status in {405, 501}:
            document = self.get_document(result)
            result["source_metadata"].update(document.source_metadata)
            return result
        self._check_status(response)
        self._check_document_identity(result, response.url)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/pdf":
            raise ProviderError("INVALID_CONTENT_TYPE", "The official source did not identify this endpoint as a PDF filing.")
        result["source_metadata"].update(_source_evidence(response, "document_headers_only"))
        return result

    @staticmethod
    def _check_status(response: SourceResponse) -> None:
        if response.status == 200:
            return
        if response.status in {401, 403}:
            raise ProviderError("SOURCE_ACCESS_REQUIRED", "The official source requires its own access process.", status=403)
        if response.status in {404, 410}:
            raise ProviderError("SOURCE_NOT_FOUND", "The exact filing is unavailable at its recorded source.", status=404)
        raise ProviderError("SOURCE_UNAVAILABLE", "The official source could not currently be reached.", retryable=response.status == 429 or response.status >= 500)

    def _check_document_identity(self, record: Mapping[str, Any], resolved_url: str) -> None:
        validate_source_url(resolved_url, self.allowed_hosts)
        expected, actual = urlsplit(record["document_url"]), urlsplit(resolved_url)
        if expected.path != actual.path or expected.query != actual.query:
            raise ProviderError("FILING_ID_MISMATCH", "The official source redirected to a different report; source metadata must be reconciled explicitly.", status=409)

    def get_document(self, record: Mapping[str, Any]) -> RetrievedDocument:
        result = self._accessible(record)
        response = self.http.request("GET", result["document_url"], allowed_hosts=self.allowed_hosts,
                                     headers={"Accept": "application/pdf"})
        self._check_status(response)
        self._check_document_identity(result, response.url)
        document = RetrievedDocument(response.body, response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
                                     result["document_url"], _source_evidence(response, "exact_document_content"))
        self.validate_document(document)
        return document

    def validate_document(self, document: RetrievedDocument) -> None:
        validate_source_url(document.document_url, self.allowed_hosts)
        if document.content_type != "application/pdf":
            raise ProviderError("INVALID_CONTENT_TYPE", "The official source returned a non-PDF response instead of a filing.")
        if not document.body.startswith(b"%PDF-") or b"%%EOF" not in document.body[-4096:]:
            raise ProviderError("INVALID_DOCUMENT", "The official source did not return a complete PDF document.")
        if len(document.body) > self.http.max_bytes:
            raise ProviderError("DOCUMENT_TOO_LARGE", "The filing exceeds the vault size limit.", status=413)

    def get_official_source_url(self, record: Mapping[str, Any]) -> str:
        return self.resolve_filing(record)["official_source_url"]

    def detect_revision(self, old: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
        # Relationships are supplied by the authoritative catalog; similar names
        # or dates are never sufficient to link two different filing IDs.
        if old.get("filing_id") != new.get("filing_id"):
            raise ProviderError("FILING_ID_MISMATCH", "Revision checks cannot substitute a different filing.", status=409)
        changes = [key for key in ("document_url", "document_version", "sha256", "is_amended",
                                   "supersedes_filing_id", "superseded_by_filing_id")
                   if key in new and old.get(key) != new.get(key)]
        return {"changed": bool(changes), "changed_fields": changes,
                "is_amended": new.get("is_amended") is True,
                "supersedes_filing_id": new.get("supersedes_filing_id") or "",
                "superseded_by_filing_id": new.get("superseded_by_filing_id") or ""}


class HouseFilingProvider(FilingResourceProvider):
    source = "house"
    allowed_hosts = HOUSE_HOSTS

    def resolve_filing(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = super().resolve_filing(record)
        url = result["document_url"]
        if url:
            match = re.fullmatch(r"/public_disc/(ptr-pdfs|financial-pdfs)/(\d{4})/(\d+)\.pdf", urlsplit(url).path, re.I)
            if not match or urlsplit(url).query:
                raise ProviderError("UNSUPPORTED_DOCUMENT_URL", "The House record has no recognized official report PDF endpoint.", status=422)
            metadata = result["source_metadata"]
            doc_id = metadata.get("document_id")
            if doc_id and str(doc_id) != match.group(3):
                raise ProviderError("FILING_ID_MISMATCH", "The House report ID and document URL disagree.", status=409)
            external = str(result["external_filing_id"])
            if external.startswith("house:") and external != f"house:{match.group(2)}:{match.group(3)}":
                raise ProviderError("FILING_ID_MISMATCH", "The House report ID and document URL disagree.", status=409)
            metadata.update({"document_id": match.group(3), "report_year": match.group(2)})
            result["report_period"] = result["report_period"] or match.group(2)
            if result["filing_type"] == "Disclosure":
                result["filing_type"] = "Periodic Transaction Report" if match.group(1).lower() == "ptr-pdfs" else "Financial Disclosure"
        return result


class OGEFilingProvider(FilingResourceProvider):
    source = "oge"
    allowed_hosts = OGE_HOSTS

    def resolve_filing(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = super().resolve_filing(record)
        url = result["document_url"]
        # A request landing page is not a document, even if a catalog incorrectly
        # marks it direct. No Form 201 submission is performed by this module.
        path = unquote(urlsplit(url).path).lower() if url else ""
        if url and (not path.endswith(".pdf") or re.search(r"oge[ _-]*form[ _-]*201", path)):
            result.update(access_class="REQUEST_REQUIRED", requires_request=True, access_method="OGE_FORM_201")
        return result


class ExecutiveAgencyFilingProvider(FilingResourceProvider):
    source = "executive_agency"

    def __init__(self, *, agency_hosts: Iterable[str] = (), **kwargs: Any):
        super().__init__(**kwargs)
        hosts = frozenset(str(host).lower().strip() for host in agency_hosts)
        if any(not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.gov", host) for host in hosts):
            raise ValueError("Agency hosts must be explicit government hostnames, without wildcards, paths or ports")
        self.allowed_hosts = hosts

    def resolve_filing(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = super().resolve_filing(record)
        # Structured endpoints may return PDFs, but this adapter never searches
        # an agency page for a plausible substitute or executes its JavaScript.
        if result["access_method"] in {"AGENCY_DISCLOSURE_PAGE", "STRUCTURED_ENDPOINT"} and not result["document_url"]:
            result.update(access_class="UNAVAILABLE", requires_request=False)
        return result


class _SecureSenateSession(requests.Session):
    """Requests-compatible session using only the pinned, bounded transport."""

    def __init__(self, http: SecureHTTPClient):
        super().__init__()
        self.http = http
        self.trust_env = False

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        if kwargs.pop("allow_redirects", False):
            raise ProviderError("UNSAFE_REDIRECT", "Senate redirects must be validated by the source adapter.")
        kwargs.pop("timeout", None)
        prepared = self.prepare_request(requests.Request(method, url, **kwargs))
        raw = self.http.request(method.upper(), prepared.url, allowed_hosts=SENATE_HOSTS,
                                headers=prepared.headers, body=prepared.body,
                                follow_redirects=False, allow_error_status=True)
        for header in raw.set_cookies:
            cookie = SimpleCookie()
            try:
                cookie.load(header)
            except Exception:
                continue
            for name, morsel in cookie.items():
                domain = morsel["domain"].lstrip(".") or "efdsearch.senate.gov"
                if domain != "efdsearch.senate.gov":
                    continue
                expires = None
                try:
                    if morsel["max-age"]:
                        expires = int(time.time()) + int(morsel["max-age"])
                    elif morsel["expires"]:
                        expires = int(parsedate_to_datetime(morsel["expires"]).timestamp())
                except (ValueError, TypeError, OverflowError):
                    continue
                self.cookies.set(name, morsel.value, domain=domain, path=morsel["path"] or "/",
                                 secure=bool(morsel["secure"]), expires=expires)
        response = requests.Response()
        response.status_code = raw.status
        response.url = raw.url
        response.headers.update(raw.headers)
        response._content = raw.body
        response.encoding = requests.utils.get_encoding_from_headers(response.headers) or "utf-8"
        response.request = prepared
        return response


class SenateFilingProvider(FilingResourceProvider):
    source = "senate"
    allowed_hosts = SENATE_HOSTS

    def __init__(self, *, senate_client: Any = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._client = senate_client
        self._lock = threading.RLock()

    def resolve_filing(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = super().resolve_filing(record)
        if result["document_url"]:
            parsed = urlsplit(result["document_url"])
            if not re.fullmatch(r"/search/view/(?:ptr|annual|paper|amendment|extension|blind|candidate|termination)/[A-Za-z0-9-]+/?", parsed.path) or parsed.query:
                raise ProviderError("UNSUPPORTED_DOCUMENT_URL", "The Senate record has no recognized exact report endpoint.", status=422)
            external = str(result["external_filing_id"])
            if external.startswith("senate:https://") and external[len("senate:"):] != result["document_url"]:
                raise ProviderError("FILING_ID_MISMATCH", "The Senate report ID and document URL disagree.", status=409)
            result["source_metadata"].setdefault("report_id", parsed.path.rstrip("/").rsplit("/", 1)[-1])
        return result

    def _fetch(self, result: Mapping[str, Any]) -> RetrievedDocument:
        if "senate" not in self.acknowledged_sources:
            raise ProviderError("SOURCE_ACKNOWLEDGEMENT_REQUIRED", "A truthful operator acknowledgement of the Senate source terms is required before establishing its official session.", status=403)
        client = self._client
        owned = client is None
        if owned:
            from scripts.monitor_disclosures import SenateClient
            # The existing client's bootstrap budget belongs to one collector
            # operation. Do not leave it indefinitely in a persistent server,
            # where successive normal session expirations would exhaust it.
            client = SenateClient(session_factory=lambda: _SecureSenateSession(self.http),
                                  sleep=self._source_retry_wait)
        try:
            response = client.get(result["document_url"])
        except ProviderError:
            raise
        except Exception:
            # Existing Senate diagnostics are classified and never expose tokens.
            raise ProviderError("SOURCE_ACCESS_UNAVAILABLE", "The Senate source session or exact report could not be validated.", retryable=True) from None
        finally:
            if owned:
                client.close()
        raw = SourceResponse(response.status_code, {key.lower(): value for key, value in response.headers.items()},
                             response.content, response.url)
        self._check_status(raw)
        self._check_document_identity(result, raw.url)
        content_type = raw.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        document = RetrievedDocument(raw.body, content_type, result["document_url"],
                                     _source_evidence(raw, "exact_document_content"))
        self.validate_document(document)
        return document

    @staticmethod
    def _source_retry_wait(delay: float) -> None:
        if delay > 30:
            raise ProviderError("SOURCE_RATE_LIMITED", "The Senate source requested a retry delay. Try again later.", retryable=True, status=429)
        time.sleep(max(0.0, delay))

    def get_metadata(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result = self._accessible(record)
        with self._lock:
            document = self._fetch(result)
        result["source_metadata"].update(document.source_metadata)
        return result

    def get_document(self, record: Mapping[str, Any]) -> RetrievedDocument:
        result = self._accessible(record)
        with self._lock:
            return self._fetch(result)

    def validate_document(self, document: RetrievedDocument) -> None:
        if document.content_type == "application/pdf":
            return super().validate_document(document)
        validate_source_url(document.document_url, self.allowed_hosts)
        if document.content_type not in {"text/html", "application/xhtml+xml"}:
            raise ProviderError("INVALID_CONTENT_TYPE", "The Senate source did not return a PDF or HTML report.")
        if not document.body or len(document.body) > self.http.max_bytes:
            raise ProviderError("INVALID_DOCUMENT", "The Senate report is empty or exceeds the vault size limit.")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(document.body, "html.parser")
        text = soup.get_text(" ", strip=True).lower()
        if (soup.find("html") is None or soup.find("form", id="agreement_form")
                or any(marker in text for marker in ("access denied", "request blocked", "captcha", "log in", "login"))
                or not (soup.find("table") or "filing document - print view" in text)):
            raise ProviderError("INVALID_DOCUMENT", "The Senate response is an access page, not a validated filing report.")
        # Raw HTML stays byte-for-byte immutable. The serving layer must supply
        # restrictive sandbox/CSP headers and never render it into the app DOM.


class ProviderRegistry:
    def __init__(self, *, http_client: SecureHTTPClient | None = None, agency_hosts: Iterable[str] = (),
                 acknowledged_sources: Iterable[str] = (), senate_client: Any = None):
        shared = {"http_client": http_client or SecureHTTPClient(), "acknowledged_sources": acknowledged_sources}
        self._providers = {
            "house": HouseFilingProvider(**shared),
            "senate": SenateFilingProvider(senate_client=senate_client, **shared),
            "oge": OGEFilingProvider(**shared),
            "executive_agency": ExecutiveAgencyFilingProvider(agency_hosts=agency_hosts, **shared),
        }

    def get(self, source: str) -> FilingResourceProvider:
        try:
            return self._providers[source]
        except KeyError:
            raise ProviderError("UNSUPPORTED_SOURCE", "This source has no approved filing provider.", status=422) from None


# Readable aliases for applications extending the adapter registry.
HouseProvider = HouseFilingProvider
SenateProvider = SenateFilingProvider
OGEProvider = OGEFilingProvider
ExecutiveAgencyProvider = ExecutiveAgencyFilingProvider
