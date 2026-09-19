from __future__ import annotations

import hashlib
import pytest

from scripts.oge_disclosures import parse_oge_table_html


PDF_URL = "https://extapps2.oge.gov/201/Presiden.nsf/PAS+Index/ABC/$FILE/Test-278T.pdf"
REQUEST_URL = "https://extapps2.oge.gov/201/Presiden.nsf/201%20Request?OpenForm&Filer=Example"


@pytest.mark.parametrize("prefix,extra,identity_document,identity_request", [
    ("", "", "", PDF_URL),
    ('<a href="https://www.oge.gov/official">Official</a>', "", "https://www.oge.gov/official", PDF_URL),
    ('<a href="'+REQUEST_URL+'">Form 201 request</a>', "", "", REQUEST_URL),
    ("", '<a href="'+REQUEST_URL+'">Form 201 request</a>', "", PDF_URL),
])
def test_extapps_pdf_classification_preserves_pre_repair_listing_identity(prefix, extra, identity_document, identity_request):
    html = f'''<table><tr><th>Date</th><th>Type</th><th>Name</th><th>Title</th><th>Agency</th><th>Level</th></tr>
        <tr><td>08/06/2026</td><td>{prefix}<a href="{PDF_URL}">OGE Form 278-T</a>{extra}</td>
        <td>Example Official</td><td>Director</td><td>Department A</td><td>PAS</td></tr></table>'''
    listing, = parse_oge_table_html(html)
    # The pre-repair identity used the old document/request slots, even when the
    # first request-slot URL was a PDF. Keep this independently calculated key.
    old_material = "\x1f".join(("08/06/2026", " ".join(filter(None, [
        "Official" if "Official</a>" in prefix else "Form 201 request" if prefix else "",
        "OGE Form 278-T", "Form 201 request" if extra else ""])),
        "Example Official", "Director", "Department A", "PAS", identity_document, identity_request))
    assert listing.listing_id == "oge:" + hashlib.sha256(old_material.encode()).hexdigest()[:32]
    assert listing.access_mode == "direct" and listing.document_url == PDF_URL


@pytest.mark.parametrize("url,expected", [
    (PDF_URL, True), (PDF_URL + "?OpenElement", True), (PDF_URL + "#page=2", True),
    (REQUEST_URL + "&Document=Report.pdf", False),
    ("https://extapps2.oge.gov/request/201?download=Report.pdf", False),
    ("https://extapps2.oge.gov.evil.test/file.pdf", False),
    ("http://extapps2.oge.gov/file.pdf", False),
    ("https://user:pass@extapps2.oge.gov/file.pdf", False),
    ("https://extapps2.oge.gov:8443/file.pdf", False),
    ("https://extapps2.oge.gov:bad/file.pdf", False),
])
def test_only_official_pdf_paths_can_reclassify_request_metadata(url, expected):
    from scripts.oge_access import is_direct_oge_pdf_url, normalize_oge_listing_access
    old = {"listing_id": "keep-this-id", "request_url": url, "access_mode": "request"}
    normalized = normalize_oge_listing_access(old)
    assert is_direct_oge_pdf_url(url) is expected
    assert normalized["listing_id"] == old["listing_id"]
    assert old["access_mode"] == "request"
    assert normalized["access_mode"] == ("direct" if expected else "request")


def test_parse_oge_table_direct_and_request_rows() -> None:
    html = """
    <html><body><table id="officials">
      <thead><tr><th>Date</th><th>Type</th><th>Name</th><th>Title</th><th>Agency</th><th>Level</th></tr></thead>
      <tbody>
        <tr>
          <td>08/20/2026</td><td><a href="/files/example-278t.pdf">OGE Form 278-T</a></td>
          <td>Direct Official</td><td>Secretary</td><td>Department A</td><td>Level I</td>
        </tr>
        <tr>
          <td>08/19/2026</td><td><a href="https://extapps2.oge.gov/request/201">Periodic Transaction Report (278-T)</a></td>
          <td>Request Official</td><td>Assistant Secretary</td><td>Department B</td><td>PAS</td>
        </tr>
        <tr><td>08/18/2026</td><td>Annual 278e</td><td>Other Official</td><td></td><td></td><td></td></tr>
      </tbody>
    </table></body></html>
    """
    listings = parse_oge_table_html(html, base_url="https://www.oge.gov/collection")
    assert len(listings) == 2
    direct = next(item for item in listings if item.name == "Direct Official")
    request = next(item for item in listings if item.name == "Request Official")
    assert direct.access_mode == "direct"
    assert direct.document_url == "https://www.oge.gov/files/example-278t.pdf"
    assert request.access_mode == "request"
    assert request.request_url == "https://extapps2.oge.gov/request/201"
    assert direct.listing_id != request.listing_id


def test_parse_oge_table_ignores_loading_row() -> None:
    html = """
    <table><thead><tr><th>Date</th><th>Type</th><th>Name</th><th>Title</th><th>Agency</th><th>Level</th></tr></thead>
    <tbody><tr><td>Loading</td><td>Loading</td><td>Loading</td><td>Loading</td><td>Loading</td><td>Loading</td></tr></tbody></table>
    """
    assert parse_oge_table_html(html) == []


class _FakeOverlay:
    def __init__(self, *, blocking: bool = True) -> None:
        self.blocking = blocking
        self.clicked = False

    @property
    def first(self):
        return self

    def wait_for(self, **_kwargs) -> None:
        return None

    def count(self) -> int:
        return 1

    def evaluate(self, script: str):
        if "element.click()" in script:
            self.clicked = True
            self.blocking = False
            return None
        return self.blocking

    def text_content(self) -> str:
        return "By clicking this banner, I affirm: I am aware of these prohibitions and wish to proceed."

    def is_visible(self) -> bool:
        return self.blocking


class _FakePage:
    def __init__(self, overlay: _FakeOverlay) -> None:
        self.overlay = overlay

    def locator(self, selector: str):
        assert selector == "#overlay"
        return self.overlay

    def wait_for_function(self, _script: str, **_kwargs) -> None:
        assert not self.overlay.blocking


def test_dismiss_terms_overlay_invokes_oge_click_handler() -> None:
    from scripts.oge_disclosures import _dismiss_terms_overlay

    overlay = _FakeOverlay()
    page = _FakePage(overlay)
    assert _dismiss_terms_overlay(page, wait_ms=1_000) is True
    assert overlay.clicked is True
    assert overlay.blocking is False


def test_dismiss_terms_overlay_ignores_inactive_overlay() -> None:
    from scripts.oge_disclosures import _dismiss_terms_overlay

    overlay = _FakeOverlay(blocking=False)
    page = _FakePage(overlay)
    assert _dismiss_terms_overlay(page) is False
    assert overlay.clicked is False
