from __future__ import annotations

from scripts.oge_disclosures import parse_oge_table_html


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
