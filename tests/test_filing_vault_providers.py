"""Provider/security tests use synthetic bytes and mocked government responses."""
from __future__ import annotations

import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from urllib3._collections import HTTPHeaderDict

from backend.filing_vault.providers import (
    ExecutiveAgencyProvider, HouseProvider, OGEProvider, ProviderError,
    ProviderRegistry, RetrievedDocument, SecureHTTPClient, SenateProvider,
    SourceResponse, normalize_filing, validate_source_url,
)


PDF = b"%PDF-1.7\nTEST synthetic official-response fixture\n%%EOF\n"
HOUSE_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/12345.pdf"
SENATE_URL = "https://efdsearch.senate.gov/search/view/ptr/12345678-abcd/"
OGE_URL = "https://www.oge.gov/web/OGE.nsf/0/ABC/$FILE/TEST.pdf"
HTML = b"<html><body><h1>TEST Periodic Transaction Report</h1><table><tr><td>TEST</td></tr></table></body></html>"


def record(source="house", url=HOUSE_URL, **kwargs):
    return {"filing_key": "retained:key", "source": source, "filer": "TEST Filer",
            "source_url": url, "report_id": "source-report-id", "filed_date": "2026-08-01", **kwargs}


def raw_response(url=HOUSE_URL, body=PDF, content_type="application/pdf", status=200, **headers):
    return SourceResponse(status, {"content-type": content_type, **headers}, body, url)


def mock_http(*responses):
    client = Mock(spec=SecureHTTPClient)
    client.max_bytes = 1024 * 1024
    client.request.side_effect = list(responses)
    return client


class PoolResponse:
    def __init__(self, status=200, body=PDF, headers=None, chunks=None):
        self.status = status
        self.headers = HTTPHeaderDict(headers or {"Content-Type": "application/pdf"})
        self.body = body
        self.chunks = chunks
        self._reads = iter(chunks if chunks is not None else [body])
        self.closed = False
        self.released = False

    def stream(self, *_args, **_kwargs):
        yield from (self.chunks if self.chunks is not None else [self.body])

    def read1(self, *_args, **_kwargs):
        return next(self._reads, b"")

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


def transport(*responses, **kwargs):
    pools = []
    pending = list(responses)

    def pool_factory(*args, **pool_kwargs):
        pool = Mock()
        pool.urlopen.return_value = pending.pop(0)
        pools.append((args, pool_kwargs, pool))
        return pool

    resolver = kwargs.pop("resolver", Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]))
    client = SecureHTTPClient(resolver=resolver, pool_factory=pool_factory,
                              min_interval=0, retries=0, **kwargs)
    return client, pools, resolver


def test_normalization_preserves_retained_ids_source_dates_and_exact_url():
    raw = record(report_id="house:2026:12345", metadata={"document_id": "12345", "filing_year": "2026"})
    normalized = normalize_filing(raw)
    assert normalized["filing_id"] == "retained:key"
    assert normalized["external_filing_id"] == "house:2026:12345"
    assert normalized["filer_name"] == "TEST Filer"
    assert normalized["filing_date"] == "2026-08-01"
    assert normalized["document_url"] == normalized["official_source_url"] == HOUSE_URL
    assert normalized["report_period"] == "2026"
    assert "checked_at" not in normalized["source_metadata"]
    assert "retrieved_at" not in normalized
    assert raw["metadata"] == {"document_id": "12345", "filing_year": "2026"}


@pytest.mark.parametrize("unsafe", [
    "http://disclosures-clerk.house.gov/a.pdf", "https://127.0.0.1/a.pdf",
    "https://disclosures-clerk.house.gov.evil.example/a.pdf",
    "https://user@disclosures-clerk.house.gov/a.pdf", "https://disclosures-clerk.house.gov:444/a.pdf",
    "https://disclosures-clerk.house.gov./a.pdf", "https://disclosures-clerk.house.gov/a.pdf#x",
    "https://disclosures-clerk.house.gov/a/../b.pdf", "https://disclosures-clerk.house.gov/a/%2e%2e/b.pdf",
    "https://disclosures-clerk.house.gov/a/%252e%252e/b.pdf", "https://disclosures-clerk.house.gov/a%5cb.pdf",
    "https://disclosures-clerk.house.gov/a%00.pdf", "https://disclosures-clerk.house.gov/\na.pdf",
    "https://disclosures-clerk.house.gov%2e.evil.example/a.pdf",
])
def test_url_validation_rejects_unsafe_addresses_without_network(unsafe):
    client, pools, resolver = transport()
    with pytest.raises(ProviderError) as exc:
        client.request("GET", unsafe, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "UNSAFE_SOURCE_URL"
    assert not pools
    resolver.assert_not_called()


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.5", "::1", "fc00::1", "::ffff:93.184.216.34", "224.0.0.1", "2002:7f00:1::", "2001:0000:4136:e378:8000:63bf:3fff:fdd2"])
def test_nonpublic_dns_never_connects(address):
    resolver = Mock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    client, pools, _ = transport(resolver=resolver)
    with pytest.raises(ProviderError) as exc:
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "UNSAFE_SOURCE_ADDRESS"
    assert not pools


def test_dns_public_private_mixture_fails_closed():
    resolver = Mock(return_value=[(socket.AF_INET, 1, 6, "", (address, 443)) for address in ("93.184.216.34", "127.0.0.1")])
    client, pools, _ = transport(resolver=resolver)
    with pytest.raises(ProviderError):
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert not pools


def test_tls_connects_to_pinned_ip_but_verifies_government_name():
    response = PoolResponse()
    client, pools, resolver = transport(response)
    received = client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert received.body == PDF
    assert pools[0][0] == ("93.184.216.34",)
    assert pools[0][1]["server_hostname"] == pools[0][1]["assert_hostname"] == "disclosures-clerk.house.gov"
    assert pools[0][1]["cert_reqs"] == "CERT_REQUIRED"
    sent = pools[0][2].urlopen.call_args
    assert sent.kwargs["headers"]["Host"] == "disclosures-clerk.house.gov"
    assert sent.kwargs["preload_content"] is False
    assert sent.kwargs["redirect"] is False
    assert sent.kwargs["retries"] is False
    assert response.closed and response.released
    resolver.assert_called_once()


def test_cross_host_redirect_is_revalidated_before_connection():
    client, pools, resolver = transport(PoolResponse(status=302, headers={"Location": "http://169.254.169.254/latest/meta-data"}))
    with pytest.raises(ProviderError) as exc:
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "UNSAFE_SOURCE_URL"
    assert len(pools) == 1
    resolver.assert_called_once()


def test_redirect_dns_rebinding_to_private_ip_never_connects_again():
    resolver = Mock(side_effect=[[(socket.AF_INET, 1, 6, "", ("93.184.216.34", 443))],
                                 [(socket.AF_INET, 1, 6, "", ("127.0.0.1", 443))]])
    client, pools, _ = transport(PoolResponse(status=302, headers={"Location": "/next.pdf"}), resolver=resolver)
    with pytest.raises(ProviderError) as exc:
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "UNSAFE_SOURCE_ADDRESS"
    assert len(pools) == 1


def test_cross_origin_allowed_redirect_drops_credentials():
    client, pools, _ = transport(PoolResponse(status=302, headers={"Location": "https://oge.gov/report.pdf"}), PoolResponse())
    client.request("GET", OGE_URL, allowed_hosts={"www.oge.gov", "oge.gov"},
                   headers={"Cookie": "private=secret", "Authorization": "secret", "Referer": OGE_URL})
    sent = pools[1][2].urlopen.call_args.kwargs["headers"]
    assert not {"Cookie", "Authorization", "Referer"} & sent.keys()


@pytest.mark.parametrize("response", [PoolResponse(headers={"Content-Length": "200"}),
                                      PoolResponse(chunks=[b"x" * 60, b"y" * 60])])
def test_excessive_content_length_or_stream_is_rejected(response):
    client, pools, _ = transport(response, max_bytes=100)
    with pytest.raises(ProviderError) as exc:
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "DOCUMENT_TOO_LARGE"
    assert response.closed and response.released
    pools[0][2].close.assert_called_once()


def test_encoded_content_is_not_decompressed():
    client, _, _ = transport(PoolResponse(headers={"Content-Encoding": "gzip"}))
    with pytest.raises(ProviderError) as exc:
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "INVALID_CONTENT_ENCODING"


def test_slow_trickle_cannot_reset_total_retrieval_deadline():
    now = [0.0]
    response = PoolResponse(chunks=[b"x"] * 1000)
    original_read = response.read1

    def trickle(*args, **kwargs):
        now[0] += 1
        return original_read(*args, **kwargs)

    response.read1 = trickle
    client, _, _ = transport(response, total_timeout=3, clock=lambda: now[0])
    with pytest.raises(ProviderError) as exc:
        client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
    assert exc.value.code == "SOURCE_TIMEOUT"
    assert now[0] == 4
    assert response.closed and response.released


def test_retry_budget_and_retry_after_are_bounded():
    now = [0.0]
    client, pools, _ = transport(PoolResponse(status=429, headers={"Retry-After": "2"}), PoolResponse(status=503), PoolResponse(), clock=lambda: now[0])
    client.retries = 2
    client._sleep = Mock(side_effect=lambda delay: now.__setitem__(0, now[0] + delay))
    assert client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"}).status == 200
    assert len(pools) == 3
    assert [call.args[0] for call in client._sleep.call_args_list] == [2.0, 2.0]


def test_long_source_retry_after_is_not_shortened_or_bypassed_by_new_request():
    client, pools, _ = transport(PoolResponse(status=429, headers={"Retry-After": "9999"}))
    client.retries = 2
    client._sleep = Mock()
    for _ in range(2):
        with pytest.raises(ProviderError) as exc:
            client.request("GET", HOUSE_URL, allowed_hosts={"disclosures-clerk.house.gov"})
        assert exc.value.code == "SOURCE_RATE_LIMITED"
    assert len(pools) == 1
    client._sleep.assert_not_called()


def test_house_pdf_metadata_and_document_are_separate_source_checks():
    http = mock_http(raw_response(body=b"", etag='"source-version"'), raw_response())
    provider = HouseProvider(http_client=http)
    normalized = provider.get_metadata(record(report_id="house:2026:12345"))
    metadata = normalized["source_metadata"]
    assert metadata["validation_scope"] == "document_headers_only"
    assert metadata["etag"] == '"source-version"'
    assert metadata["checked_at"].endswith("Z")
    assert metadata["report_year"] == "2026"
    document = provider.get_document(normalized)
    assert document.body == PDF
    assert document.source_metadata["validation_scope"] == "exact_document_content"
    assert [call.args[0] for call in http.request.call_args_list] == ["HEAD", "GET"]


def test_house_annual_reports_use_same_provider_without_ptr_reclassification():
    url = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2026/12345.pdf"
    provider = HouseProvider(http_client=mock_http(raw_response(url=url)))
    normalized = provider.resolve_filing(record(url=url, report_type="Annual"))
    assert normalized["filing_type"] == "Annual"
    assert provider.get_document(normalized).document_url == url


def test_house_report_identity_mismatch_never_fetches():
    http = mock_http()
    provider = HouseProvider(http_client=http)
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record(report_id="house:2026:99999"))
    assert exc.value.code == "FILING_ID_MISMATCH"
    http.request.assert_not_called()


@pytest.mark.parametrize("content_type,body,code", [
    ("text/html", b"<html>agreement</html>", "INVALID_CONTENT_TYPE"),
    ("application/octet-stream", PDF, "INVALID_CONTENT_TYPE"),
    ("application/pdf", b"MZ executable", "INVALID_DOCUMENT"),
    ("application/pdf", b"%PDF-1.7 truncated", "INVALID_DOCUMENT"),
])
def test_invalid_mime_or_pdf_signature_rejected(content_type, body, code):
    provider = HouseProvider(http_client=mock_http(raw_response(body=body, content_type=content_type)))
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record())
    assert exc.value.code == code


def test_oge_direct_filing_preserves_exact_bytes_and_access_method():
    provider = OGEProvider(http_client=mock_http(raw_response(url=OGE_URL)), acknowledged_sources={"oge"})
    normalized = provider.resolve_filing(record("oge", OGE_URL, access_mode="direct"))
    assert normalized["access_class"] == "ACKNOWLEDGEMENT_REQUIRED"
    assert provider.get_document(normalized).body == PDF
    assert provider.get_official_source_url(normalized) == OGE_URL


@pytest.mark.parametrize("extra", [{"access_mode": "request"}, {"access_class": "REQUEST_REQUIRED"},
                                    {"requires_request": True}, {"requires_request": "true"},
                                    {"access_method": "OGE_FORM_201", "access_class": "DIRECT_PUBLIC"},
                                    {"access_class": "DIRECT_PUBLIC", "source_metadata": {"access_class": "REQUEST_REQUIRED"}},
                                    {"access_mode": "unknown"}])
def test_oge_request_or_unknown_never_fetches_even_with_document_url(extra):
    http = mock_http()
    provider = OGEProvider(http_client=http, acknowledged_sources={"oge"})
    with pytest.raises(ProviderError):
        provider.get_document(record("oge", OGE_URL, document_url=OGE_URL, **extra))
    http.request.assert_not_called()


def test_oge_request_landing_page_cannot_be_mislabeled_as_pdf():
    http = mock_http()
    provider = OGEProvider(http_client=http, acknowledged_sources={"oge"})
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record("oge", "https://extapps2.oge.gov/201/Presiden.nsf/201%20Request", access_mode="direct"))
    assert exc.value.code == "REQUEST_REQUIRED"
    http.request.assert_not_called()


def test_blank_oge_form201_pdf_is_not_the_requested_official_filing():
    http = mock_http()
    provider = OGEProvider(http_client=http, acknowledged_sources={"oge"})
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record("oge", "https://www.oge.gov/web/OGE.nsf/0/ABC/$FILE/OGE%20Form%20201.pdf", access_mode="direct"))
    assert exc.value.code == "REQUEST_REQUIRED"
    http.request.assert_not_called()


def test_executive_agency_is_explicitly_configured_and_request_boundary_is_preserved():
    url = "https://ethics.example.gov/reports/TEST.pdf"
    http = mock_http(raw_response(url=url))
    provider = ExecutiveAgencyProvider(agency_hosts={"ethics.example.gov"}, http_client=http)
    normalized = provider.resolve_filing(record("executive", url, document_url=url, access_class="DIRECT_PUBLIC", access_method="DIRECT_PDF", agency="TEST agency"))
    assert normalized["source"] == "executive_agency"
    assert normalized["agency"] == "TEST agency"
    assert provider.get_document(normalized).body == PDF
    with pytest.raises(ProviderError) as exc:
        provider.get_metadata({**normalized, "requires_request": True})
    assert exc.value.code == "REQUEST_REQUIRED"
    assert http.request.call_count == 1


def test_executive_provider_does_not_fetch_unconfigured_or_wildcard_hosts():
    http = mock_http()
    provider = ExecutiveAgencyProvider(http_client=http)
    with pytest.raises(ProviderError):
        provider.get_document(record("executive_agency", "https://ethics.example.gov/TEST.pdf", access_mode="direct"))
    http.request.assert_not_called()
    with pytest.raises(ValueError):
        ExecutiveAgencyProvider(agency_hosts={"*.gov"})


def test_senate_requires_truthful_source_ack_before_get():
    senate = Mock()
    provider = SenateProvider(senate_client=senate)
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record("senate", SENATE_URL))
    assert exc.value.code == "SOURCE_ACKNOWLEDGEMENT_REQUIRED"
    senate.get.assert_not_called()


def test_senate_retains_original_html_and_does_not_reuse_stale_metadata_fetch():
    senate = Mock()
    senate.get.return_value = SimpleNamespace(status_code=200, content=HTML, url=SENATE_URL,
                                              headers={"Content-Type": "text/html; charset=utf-8"})
    provider = SenateProvider(senate_client=senate, acknowledged_sources={"senate"})
    metadata = provider.get_metadata(record("senate", SENATE_URL, report_type="Periodic Transaction Report"))
    document = provider.get_document(metadata)
    assert document.body == HTML
    assert document.content_type == "text/html"
    assert metadata["source_metadata"]["validation_scope"] == "exact_document_content"
    assert metadata["filing_type"] == "Periodic Transaction Report"
    assert metadata["source_metadata"]["report_id"] == "12345678-abcd"
    assert senate.get.call_count == 2
    assert all(call.args == (SENATE_URL,) for call in senate.get.call_args_list)


def test_senate_adapter_does_not_mistake_agreement_page_for_a_report():
    senate = Mock()
    senate.get.return_value = SimpleNamespace(status_code=200, content=b'<html><form id="agreement_form"></form><table></table></html>',
                                              url=SENATE_URL, headers={"Content-Type": "text/html"})
    provider = SenateProvider(senate_client=senate, acknowledged_sources={"senate"})
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record("senate", SENATE_URL))
    assert exc.value.code == "INVALID_DOCUMENT"


def test_existing_senate_client_truthful_handshake_repeats_safely_in_persistent_provider():
    token = "a" * 32
    landing = f'<html><form id="agreement_form"><input type="hidden" name="csrfmiddlewaretoken" value="{token}"><input type="checkbox" name="prohibition_agreement"></form></html>'.encode()
    search = (f'<html>Find Reports<form id="searchForm" method="post"><input type="hidden" name="csrfmiddlewaretoken" value="{token}">'
              '<input name="first_name"><input name="last_name"><input name="report_type"><input name="filer_type"></form></html>').encode()
    home_url = "https://efdsearch.senate.gov/search/home/"
    search_url = "https://efdsearch.senate.gov/search/"
    replies = [SourceResponse(200, {"content-type": "text/html"}, landing, home_url,
                                    (f"csrftoken={token}; Path=/; Secure",)),
                     SourceResponse(302, {"location": search_url}, b"", home_url,
                                    ("sessionid=truthful-official-session; Path=/; Secure; HttpOnly",)),
                     SourceResponse(200, {"content-type": "text/html"}, search, search_url),
                     SourceResponse(200, {"content-type": "text/html"}, HTML, SENATE_URL)]
    http = mock_http(*(replies * 4))
    provider = SenateProvider(http_client=http, acknowledged_sources={"senate"})
    for _ in range(4):
        document = provider.get_document(record("senate", SENATE_URL))
        assert document.body == HTML
    calls = http.request.call_args_list
    assert [call.args[0] for call in calls] == ["GET", "POST", "GET", "GET"] * 4
    assert "prohibition_agreement=1" in calls[1].kwargs["body"]
    assert all(call.kwargs["follow_redirects"] is False for call in calls)
    assert "sessionid=truthful-official-session" in calls[-1].kwargs["headers"]["Cookie"]


def test_source_failures_do_not_fabricate_validation_timestamps():
    original = record()
    http = mock_http(raw_response(status=503))
    with pytest.raises(ProviderError):
        HouseProvider(http_client=http).get_metadata(original)
    assert "source_metadata" not in original
    assert "last_validated_at" not in original


def test_revision_detection_does_not_infer_relationships_from_same_filer():
    provider = HouseProvider()
    old = {"filing_id": "one", "sha256": "old", "filer": "Same Filer"}
    changed = provider.detect_revision(old, {**old, "sha256": "new"})
    assert changed["changed_fields"] == ["sha256"]
    assert not changed["is_amended"]
    assert changed["supersedes_filing_id"] == ""
    with pytest.raises(ProviderError):
        provider.detect_revision(old, {**old, "filing_id": "two"})


def test_registry_keeps_all_four_adapters_distinct():
    registry = ProviderRegistry()
    assert isinstance(registry.get("house"), HouseProvider)
    assert isinstance(registry.get("senate"), SenateProvider)
    assert isinstance(registry.get("oge"), OGEProvider)
    assert isinstance(registry.get("executive_agency"), ExecutiveAgencyProvider)
    with pytest.raises(ProviderError):
        registry.get("https://attacker.example")


def test_malformed_source_metadata_is_a_classified_record_error():
    with pytest.raises(ProviderError) as exc:
        normalize_filing(record(source_metadata="not a JSON object"))
    assert exc.value.code == "INVALID_FILING"
    assert exc.value.status == 400


@pytest.mark.parametrize("method", ["get_metadata", "get_document"])
def test_house_redirect_cannot_silently_substitute_another_report(method):
    provider = HouseProvider(http_client=mock_http(raw_response(url=HOUSE_URL.replace("12345", "99999"))))
    with pytest.raises(ProviderError) as exc:
        getattr(provider, method)(record())
    assert exc.value.code == "FILING_ID_MISMATCH"


def test_senate_redirect_cannot_silently_substitute_another_report():
    senate = Mock()
    senate.get.return_value = SimpleNamespace(status_code=200, content=HTML, url=SENATE_URL.replace("12345678", "87654321"),
                                              headers={"Content-Type": "text/html"})
    provider = SenateProvider(senate_client=senate, acknowledged_sources={"senate"})
    with pytest.raises(ProviderError) as exc:
        provider.get_document(record("senate", SENATE_URL))
    assert exc.value.code == "FILING_ID_MISMATCH"


def test_explicit_direct_agency_metadata_enables_known_document_only():
    url = "https://ethics.example.gov/reports/TEST.pdf"
    provider = ExecutiveAgencyProvider(agency_hosts={"ethics.example.gov"}, http_client=mock_http(raw_response(url=url)))
    normalized = provider.resolve_filing(record("executive_agency", url, access_mode="direct"))
    assert normalized["access_class"] == "DIRECT_PUBLIC"
    assert normalized["document_url"] == url
    assert provider.get_document(normalized).body == PDF


@pytest.mark.parametrize("source", ["oge", "executive_agency"])
@pytest.mark.parametrize("method", ["get_metadata", "get_document"])
def test_oge_and_agency_redirects_cannot_substitute_another_filing(source, method):
    url = OGE_URL if source == "oge" else "https://ethics.example.gov/reports/TEST.pdf"
    http = mock_http(raw_response(url=url.replace("TEST.pdf", "OTHER.pdf")))
    provider = (OGEProvider(http_client=http, acknowledged_sources={"oge"}) if source == "oge"
                else ExecutiveAgencyProvider(agency_hosts={"ethics.example.gov"}, http_client=http))
    with pytest.raises(ProviderError) as exc:
        getattr(provider, method)(record(source, url, access_mode="direct"))
    assert exc.value.code == "FILING_ID_MISMATCH"


def test_oge_alias_redirect_may_preserve_exact_document_identity():
    provider = OGEProvider(http_client=mock_http(raw_response(url=OGE_URL.replace("www.oge.gov", "oge.gov"))), acknowledged_sources={"oge"})
    doc = provider.get_document(record("oge", OGE_URL, access_mode="direct"))
    assert doc.document_url == OGE_URL
    assert doc.source_metadata["resolved_document_url"] == OGE_URL.replace("www.oge.gov", "oge.gov")
