"""Filing Vault projections and isolated generated-page acceptance.

Every record is TEST data. DOM/CSS checks are not claims of PDF rendering,
physical mobile acceptance, browser CSP enforcement or a deployed backend.
"""
from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from scripts.build_trade_dashboard import build_payload, build_site, load_branch
from scripts.filing_resources import api_origin, attach_filing_ids, filing_catalog


def _row(key: str = "TEST-house-42", **changes) -> dict:
    return {
        "filing_key": key,
        "source": "house",
        "report_id": "TEST-report-42",
        "filer": "TEST Fixture Filer",
        "source_url": "https://official.example.test/TEST-42.pdf",
        "filed_date": "2026-08-01",
        "status": "cataloged",
        **changes,
    }


@pytest.mark.parametrize(("value", "expected"), [
    ("", ""),
    ("https://vault.example.test", "https://vault.example.test"),
    ("https://vault.example.test/", "https://vault.example.test"),
    ("https://vault.example.test:8443", "https://vault.example.test:8443"),
    ("http://localhost:8000", "http://localhost:8000"),
    ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
    ("http://[::1]:8000", "http://[::1]:8000"),
])
def test_filing_api_origin_accepts_only_explicit_origin(value: str, expected: str) -> None:
    assert api_origin(value) == expected


@pytest.mark.parametrize("value", [
    "http://vault.example.test", "https://vault.example.test/api",
    "https://user:secret@vault.example.test", "https://vault.example.test?token=TEST",
    "https://vault.example.test#fragment", "//vault.example.test",
    "javascript:alert(1)", "file:///C:/TEST/report.pdf", "https://",
    "https://vault.example.test:bad", "https://vault.example.test:99999",
    'https://vault.example.test" onload="TEST',
    "https://vault.example.test;script-src *",
    "https://vault.example.test\n",
    "https://<TEST>.example.test",
])
def test_filing_api_origin_rejects_unsafe_or_malformed_configuration(value: str) -> None:
    with pytest.raises(ValueError):
        api_origin(value)


def test_catalog_projects_stable_ids_without_mutating_source_or_claiming_cache() -> None:
    payload = {
        "summary": {"generated_utc": "2026-08-31T12:00:00Z"},
        "filings": [
            _row(),
            _row("TEST-oge-access", source="oge", access_required=True),
            _row("TEST-synthetic", is_synthetic_test=True),
            {"filer": "TEST Missing Identity"},
        ],
    }
    before = deepcopy(payload)
    catalog = filing_catalog(payload)
    assert payload == before
    assert catalog["repository_id"] == 1349678672
    assert catalog["generated_at"] == "2026-08-31T12:00:00Z"
    assert [r["filing_id"] for r in catalog["filings"]] == [
        "TEST-house-42", "TEST-oge-access", "TEST-synthetic",
    ]
    assert catalog["filings"][1]["access_required"] is True
    assert catalog["filings"][2]["is_synthetic_test"] is True
    assert all("retrieved_at" not in row and "cache_status" not in row for row in catalog["filings"])


def test_attach_filing_ids_is_read_only_recursive_and_requires_retained_evidence() -> None:
    catalog = filing_catalog({"filings": [_row()]})
    records = {"nested": [
        {"filing_key": "TEST-house-42", "source": "house"},
        {"source": "house", "report_id": "TEST-report-42"},
        {"source_url": "https://official.example.test/TEST-42.pdf"},
        {"ticker": "TEST", "filer": "TEST Fixture Filer"},
        "TEST scalar",
    ]}
    before = deepcopy(records)
    attached = attach_filing_ids(records, catalog)
    assert records == before
    assert attached is not records
    assert [item.get("filing_id") if isinstance(item, dict) else item for item in attached["nested"]] == [
        "TEST-house-42", "TEST-house-42", "TEST-house-42", None, "TEST scalar",
    ]


def test_catalog_omits_nested_private_paths_credentials_and_storage_details() -> None:
    record = _row(
        access_required=True,
        local_pdf_path="C:/SECRET_PRIVATE/TEST.pdf",
        object_key="filings/SECRET_PRIVATE/TEST.pdf",
        agency={"internal_path": "C:/SECRET_PRIVATE/inside-allowed-field"},
        title=[{"private_path": "C:/SECRET_PRIVATE/inside-allowed-list"}],
        metadata={
            "document_id": "TEST-report-42",
            "local_pdf_path": "C:/SECRET_PRIVATE/TEST.pdf",
            "session": {"cookie": "SECRET_PRIVATE_cookie"},
            "report_type": {"internal_path": "C:/SECRET_PRIVATE/nested"},
        },
        source_metadata={
            "validation_scope": "document_headers_only",
            "resolved_document_url": "https://official.example.test/TEST-42.pdf",
            "storage": {"key": "SECRET_PRIVATE_key"},
            "authorization": "Bearer SECRET_PRIVATE_receipt",
            "checked_at": {"private_path": "C:/SECRET_PRIVATE/nested-date"},
        },
    )
    before = deepcopy(record)
    catalog = filing_catalog({"filings": [record]})
    assert record == before, "private input provenance must remain untouched"
    exported = catalog["filings"][0]
    assert exported["access_required"] is True
    assert exported["metadata"] == {"document_id": "TEST-report-42"}
    assert exported["source_metadata"] == {
        "validation_scope": "document_headers_only",
        "resolved_document_url": "https://official.example.test/TEST-42.pdf",
    }
    assert "SECRET_PRIVATE" not in json.dumps(catalog)


@pytest.mark.parametrize("contradiction", [
    {"source": "senate"},
    {"report_id": "TEST-wrong-report"},
    {"source_url": "https://official.example.test/TEST-other.pdf"},
    {"official_source_url": "https://official.example.test/TEST-other.pdf"},
])
def test_attach_rejects_source_report_or_url_substitution(contradiction: dict) -> None:
    catalog = filing_catalog({"filings": [_row()]})
    item = {"filing_key": "TEST-house-42", **contradiction}
    result = attach_filing_ids(item, catalog)
    assert "filing_id" not in result
    assert result == {**item, "filing_resolution": "conflict"}


def test_attach_does_not_replace_an_explicit_unknown_filing_identity() -> None:
    catalog = filing_catalog({"filings": [_row()]})
    record = {"filing_id": "TEST-unknown", "source": "house", "report_id": "TEST-report-42"}
    assert attach_filing_ids(record, catalog) == {**record, "filing_resolution": "unresolved"}
    keyed = {"filing_key": "TEST-unknown", "source": "house", "report_id": "TEST-report-42"}
    assert attach_filing_ids(keyed, catalog) == {**keyed, "filing_resolution": "unresolved"}


def test_ambiguous_retained_urls_never_pick_a_filing_by_order() -> None:
    catalog = filing_catalog({"filings": [
        _row(),
        _row("TEST-senate-42", source="senate"),
    ]})
    original = {"source_url": "https://official.example.test/TEST-42.pdf"}
    assert attach_filing_ids(original, catalog) == {**original, "filing_resolution": "ambiguous"}
    exact = {"source": "senate", "report_id": "TEST-report-42"}
    assert attach_filing_ids(exact, catalog)["filing_id"] == "TEST-senate-42"


@pytest.mark.parametrize("item", [
    {"filing_id": "TEST-house-42", "source_url": "https://official.example.test/OTHER.pdf"},
    {"filing_key": "TEST-house-42", "filing_id": "TEST-other"},
    {"filing_key": "TEST-other", "filing_id": "TEST-house-42"},
])
def test_conflicting_explicit_ids_remain_provenance_but_are_not_viewable(item: dict) -> None:
    before = deepcopy(item)
    result = attach_filing_ids(item, filing_catalog({"filings": [_row()]}))
    assert result == {**before, "filing_resolution": "conflict"}
    assert item == before


@pytest.mark.parametrize("resolution", ["conflict", "ambiguous", "unresolved"])
def test_failed_resolution_survives_compact_insights_and_second_attachment(resolution: str) -> None:
    from scripts.dashboard_insights import _filing, _review, _signal
    catalog = filing_catalog({"filings": [_row()]})
    original = {"filing_key": "TEST-house-42", "filing_id": "TEST-house-42",
                "source_url": "https://official.example.test/TEST-42.pdf",
                "filing_resolution": resolution}
    for projection in (_filing, lambda row: _review(row, "manual_exception"), _signal):
        compact = projection(original)
        result = attach_filing_ids(compact, catalog)
        assert result["filing_resolution"] == resolution
        assert result["filing_key"] == original["filing_key"]
        assert result["filing_id"] == original["filing_id"]


def test_duplicate_catalog_identity_is_ambiguous_instead_of_last_row_wins() -> None:
    catalog = filing_catalog({"filings": [_row(), _row(source_url="https://official.example.test/OTHER.pdf")]})
    original = {"filing_key": "TEST-house-42"}
    assert attach_filing_ids(original, catalog) == {**original, "filing_resolution": "ambiguous"}


def test_approved_official_url_alias_can_resolve_without_rewriting_source() -> None:
    original = {"official_source_url": "https://official.example.test/TEST-42.pdf"}
    result = attach_filing_ids(original, filing_catalog({"filings": [_row()]}))
    assert result == {**original, "filing_id": "TEST-house-42", "filing_resolution": "matched"}


def _generated_fixture(tmp_path: Path) -> Path:
    payload = build_payload(
        load_branch(None, "legislative"), load_branch(None, "executive"),
        repository_url="https://github.com/maglothinm/MyETF-Intelligence",
    )
    output = tmp_path / "TEST-filing-vault-site"
    build_site(payload, output)
    return output


def test_generator_packages_vault_assets_catalog_and_mobile_document_contract(tmp_path: Path) -> None:
    output = _generated_fixture(tmp_path)
    for relative in (
        "filing-vault.html", "filing-vault.js", "filing-vault.css",
        "filing-pdf.js", "filing-pdf.css",
        "vendor/pdfjs/pdf.mjs", "vendor/pdfjs/pdf.worker.mjs",
        "vendor/pdfjs/LICENSE", "vendor/pdfjs/MANIFEST.json",
        "data/filing-vault-config.json", "data/filing-resources.json",
    ):
        assert (output / relative).is_file(), f"Generated site omits {relative}"
    html = (output / "filing-vault.html").read_text(encoding="utf-8")
    code = (output / "filing-vault.js").read_text(encoding="utf-8")
    css = (output / "filing-vault.css").read_text(encoding="utf-8")
    assert 'width=device-width' in html
    assert 'aria-labelledby="filing-title"' in html
    assert 'aria-live="polite"' in html
    assert 'id="filing-official"' in html
    assert 'id="filing-download"' in html
    assert 'id="filing-retry"' in html
    assert 'filing-vault.js' in html
    assert 'filing-pdf.js' in html
    assert 'filing-pdf.css' in html
    assert 'window.PT' in code, "Standalone vault must package its shared utilities"
    assert re.search(r"@media\s*\(\s*max-width\s*:\s*600px\s*\)", css)
    assert re.search(r"\.vault-list\s*\{[^}]*grid-template-columns\s*:\s*1fr", css)
    assert re.search(r"#filing-document\s+pre\s*\{[^}]*overflow-wrap\s*:\s*anywhere", css)
    catalog = json.loads((output / "data/filing-resources.json").read_text(encoding="utf-8"))
    assert catalog["repository_id"] == 1349678672
    assert isinstance(catalog["filings"], list)
    vendor = output / "vendor/pdfjs"
    manifest = json.loads((vendor / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["package"] == "pdfjs-dist"
    assert {"pdf.mjs", "pdf.worker.mjs", "LICENSE"} <= {entry["path"] for entry in manifest["files"]}
    for entry in manifest["files"]:
        asset = (vendor / entry["path"]).resolve()
        assert vendor.resolve() in asset.parents, "Vendored manifest must stay within local PDF assets"
        assert asset.is_file(), f"Generated viewer asset missing: {entry['path']}"
        content = asset.read_bytes()
        assert len(content) == entry["bytes"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
    assert not list(vendor.rglob("*.pdf")), "Source filings must never ship as static vendor assets"


def test_generated_filing_vault_dom(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    node = os.environ.get("POLITITRACK_TEST_NODE") or shutil.which("node")
    modules = Path(os.environ.get(
        "POLITITRACK_TEST_NODE_MODULES", repository / ".remediation/ui-test-tools/node_modules",
    ))
    if not node or not (modules / "jsdom/package.json").exists() or not (modules / "axe-core/package.json").exists():
        pytest.skip("Optional TEST DOM fixtures require Node, jsdom and axe-core")
    output = _generated_fixture(tmp_path)
    env = dict(
        os.environ,
        POLITITRACK_TEST_BUILD=str(output),
        POLITITRACK_TEST_NODE_MODULES=str(modules),
    )
    result = subprocess.run(
        [node, "--test", "tests/filing_vault_dom.test.cjs"],
        cwd=repository, env=env, capture_output=True, text=True,
        check=False, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_filing_pdf_renderer_dom() -> None:
    """Exercise local helper lifecycle with a deterministic PDF engine, not live decoding."""
    repository = Path(__file__).resolve().parents[1]
    node = os.environ.get("POLITITRACK_TEST_NODE") or shutil.which("node")
    modules = Path(os.environ.get(
        "POLITITRACK_TEST_NODE_MODULES", repository / ".remediation/ui-test-tools/node_modules",
    ))
    if not node or not (modules / "jsdom/package.json").exists():
        pytest.skip("Optional TEST PDF helper fixtures require Node and jsdom")
    env = dict(os.environ, POLITITRACK_TEST_NODE_MODULES=str(modules))
    result = subprocess.run(
        [node, "--test", "tests/filing_pdf_dom.test.cjs"],
        cwd=repository, env=env, capture_output=True, text=True,
        check=False, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_configured_api_origin_is_the_same_explicit_origin_in_config_and_csp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FILING_VAULT_API_ORIGIN", "https://vault-api.example.test:8443/")
    output = _generated_fixture(tmp_path)
    config = json.loads((output / "data/filing-vault-config.json").read_text(encoding="utf-8"))
    assert config == {"api_origin": "https://vault-api.example.test:8443"}

    class MetaParser(HTMLParser):
        csp = None

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "meta" and values.get("http-equiv") == "Content-Security-Policy":
                self.csp = values["content"]

    parser = MetaParser()
    parser.feed((output / "filing-vault.html").read_text(encoding="utf-8"))
    assert parser.csp
    assert "connect-src 'self' https://vault-api.example.test:8443;" in parser.csp
    directives = {
        parts[0]: set(parts[1:])
        for directive in parser.csp.split(";")
        if (parts := directive.strip().split())
    }
    assert directives["script-src"] == {"'self'", "'wasm-unsafe-eval'"}
    assert directives["worker-src"] == {"'self'"}
    assert "'unsafe-eval'" not in parser.csp
    assert "object-src 'none'" in parser.csp
    assert "unsafe-inline" not in parser.csp
