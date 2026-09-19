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


def _page_state(start=0, total=2, length=1):
    end = min(start + length, total)
    return dict(start=start, end=end, total=total, length=length,
                rows=end-start, response_rows=end-start, response_total=total)


@pytest.mark.parametrize("change", [
    {"rows": 0}, {"response_rows": 0}, {"response_total": 3},
    {"start": -1}, {"end": 2}, {"length": 0}, {"total": True},
    {"total": "2"}, {"error": "upstream error"},
])
def test_rejects_partial_or_malformed_page_counts(change):
    from scripts.oge_disclosures import _validate_table_page, SourceChangedError
    with pytest.raises(SourceChangedError):
        _validate_table_page({**_page_state(), **change})


@pytest.mark.parametrize("state", [_page_state(), _page_state(1), _page_state(total=0)])
def test_accepts_complete_page_counts_including_empty_search(state):
    from scripts.oge_disclosures import _validate_table_page
    assert _validate_table_page(state) == state


@pytest.mark.parametrize("timeouts", [1, 2])
def test_loading_timeout_reloads_only_once_and_never_returns_partial(monkeypatch, tmp_path, timeouts):
    from types import SimpleNamespace
    from playwright.sync_api import TimeoutError
    from scripts import oge_disclosures as oge
    calls = []
    page = SimpleNamespace(goto=lambda *a, **kw: calls.append("goto"),
                           reload=lambda **kw: calls.append("reload"))
    monkeypatch.setattr(oge, "_affirm_terms", lambda p: calls.append("affirm"))
    monkeypatch.setattr(oge, "_dismiss_terms_overlay", lambda p: calls.append("dismiss"))
    monkeypatch.setattr(oge, "_save_diagnostics", lambda p, d, label: calls.append(label))
    waits = 0
    def wait(*a, **kw):
        nonlocal waits
        waits += 1
        if waits <= timeouts:
            raise TimeoutError("upstream still loading")
    monkeypatch.setattr(oge, "_wait_for_rendered_table", wait)
    if timeouts == 2:
        with pytest.raises(oge.SourceChangedError, match="two bounded attempts"):
            oge._load_collection(page, oge.OGE_COLLECTION_URL, 100, tmp_path)
    else:
        oge._load_collection(page, oge.OGE_COLLECTION_URL, 100, tmp_path)
    assert calls.count("goto") == calls.count("reload") == 1
    assert calls.count("affirm") == 2
    assert calls.count("dismiss") == (timeouts == 1)
    assert "oge-loading-timeout-1" in calls
    assert waits == 2


def test_invalid_source_does_not_trigger_loading_retry(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from scripts import oge_disclosures as oge
    def fail(*a, **kw):
        raise oge.SourceChangedError("unrecognized acknowledgement")
    page = SimpleNamespace(goto=lambda *a, **kw: None,
                           reload=lambda **kw: pytest.fail("must not retry validation failure"))
    monkeypatch.setattr(oge, "_affirm_terms", fail)
    with pytest.raises(oge.SourceChangedError, match="unrecognized acknowledgement"):
        oge._load_collection(page, oge.OGE_COLLECTION_URL, 100, tmp_path)


def _listing_html(name):
    return f'''<table><tr><th>Date</th><th>Type</th><th>Name</th><th>Title</th><th>Agency</th><th>Level</th></tr>
    <tr><td>08/06/2026</td><td><a href="{PDF_URL}">OGE Form 278-T</a></td>
    <td>{name}</td><td>Director</td><td>Department A</td><td>PAS</td></tr></table>'''


def _fake_collection(monkeypatch, pages, *, next_control=True):
    from types import SimpleNamespace
    from scripts import oge_disclosures as oge
    import playwright.sync_api
    calls = []
    position = 0
    def click(**kw):
        nonlocal position
        position += 1
    search = SimpleNamespace(fill=lambda value: calls.append(("search", value)))
    page = SimpleNamespace(
        url=oge.OGE_COLLECTION_URL, set_default_timeout=lambda v: None,
        on=lambda *a: None, content=lambda: pages[position][1],
        wait_for_timeout=lambda *a: pytest.fail("fixed sleeps must not drive discovery"),
    )
    context = SimpleNamespace(new_page=lambda: page, close=lambda: calls.append("context_closed"))
    browser = SimpleNamespace(new_context=lambda **kw: context, close=lambda: calls.append("browser_closed"))
    class Playwright:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kw: browser))
        def __exit__(self, *a):
            return False
    monkeypatch.setattr(playwright.sync_api, "sync_playwright", Playwright)
    monkeypatch.setattr(oge, "_load_collection", lambda *a: None)
    def wait(p, timeout_ms, **expected):
        calls.append(expected)
        assert expected == {"search_term": "278-T", "start": pages[position][0]["start"]}
        return oge._validate_table_page(pages[position][0])
    monkeypatch.setattr(oge, "_wait_for_rendered_table", wait)
    monkeypatch.setattr(oge, "_find_search_input", lambda p: search)
    monkeypatch.setattr(oge, "_dismiss_terms_overlay", lambda p: False)
    monkeypatch.setattr(oge, "_next_locator", lambda p: SimpleNamespace(click=click) if next_control else None)
    monkeypatch.setattr(oge, "_save_diagnostics", lambda *a: calls.append("diagnostic"))
    return calls


def test_complete_collection_waits_for_matching_search_and_every_page(monkeypatch, tmp_path):
    from scripts import oge_disclosures as oge
    calls = _fake_collection(monkeypatch, [(_page_state(), _listing_html("A")),
                                         (_page_state(1), _listing_html("B"))])
    rows = oge.scrape_oge_listings(collection_url=oge.OGE_COLLECTION_URL, timeout_ms=100,
                                  max_pages=2, diagnostics_dir=tmp_path)
    assert {r.name for r in rows} == {"A", "B"}
    assert len({r.listing_id for r in rows}) == 2
    assert calls[-2:] == ["context_closed", "browser_closed"]
    assert "diagnostic" not in calls


@pytest.mark.parametrize("failure", ["repeated", "changed_total", "page_limit", "missing_next", "changed_headers"])
def test_incomplete_collection_fails_after_first_valid_page(monkeypatch, tmp_path, failure):
    from scripts import oge_disclosures as oge
    pages = [(_page_state(), _listing_html("A")), (_page_state(1), _listing_html("B"))]
    if failure == "repeated":
        pages[1] = (_page_state(1), _listing_html("A"))
    elif failure == "changed_total":
        pages[1] = (_page_state(1, total=3), _listing_html("B"))
    elif failure == "changed_headers":
        pages[1] = (_page_state(1), "<table><tr><td>Unknown source layout</td></tr></table>")
    calls = _fake_collection(monkeypatch, pages, next_control=failure != "missing_next")
    with pytest.raises(oge.SourceChangedError):
        oge.scrape_oge_listings(collection_url=oge.OGE_COLLECTION_URL, timeout_ms=100,
                               max_pages=1 if failure == "page_limit" else 2, diagnostics_dir=tmp_path)
    assert calls[-3:] == ["diagnostic", "context_closed", "browser_closed"]


def test_network_diagnostics_exclude_query_credentials_and_headers(caplog):
    from types import SimpleNamespace
    from scripts.oge_disclosures import _log_request_failure
    _log_request_failure(SimpleNamespace(url="https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v2/rest?secret=value",
                                        resource_type="xhr", failure="net::ERR_TIMED_OUT"))
    assert "API.xsp/v2/rest" in caplog.text
    assert "net::ERR_TIMED_OUT" in caplog.text
    assert "secret" not in caplog.text and "value" not in caplog.text


def test_draw_readiness_correlates_public_datatables_response():
    """Execute the actual wait predicate against asynchronous draw states."""
    import json
    import subprocess
    from types import SimpleNamespace
    from scripts.oge_disclosures import _wait_for_rendered_table
    captured = {}
    class Handle:
        def json_value(self):
            return _page_state()
        def dispose(self):
            captured["disposed"] = True
    def wait(script, **kwargs):
        captured.update(script=script, **kwargs)
        return Handle()
    _wait_for_rendered_table(SimpleNamespace(wait_for_function=wait), 123,
                             search_term="278-T", start=0)
    assert captured["disposed"] and captured["timeout"] == 123
    assert json.loads(captured["arg"]) == {"search": "278-T", "start": 0}
    harness = r'''
const assert = require('node:assert/strict');
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const predicate = eval('(' + input.script + ')');
const table = {innerText: 'Date Type Name Report'};
const request = {draw: 2, start: 0, search: {value: '278-T'}};
const response = {draw: 1, data: [{}], recordsFiltered: 2};
const info = {serverSide: true, start: 0, end: 1, recordsDisplay: 2, length: 1};
const api = {page: {info: () => info}, ajax: {params: () => request, json: () => response},
             rows: () => ({count: () => 1})};
global.document = {querySelectorAll: () => [table]};
const jq = () => ({DataTable: () => api});
jq.fn = {dataTable: {isDataTable: () => true}};
global.window = {jQuery: jq};
assert.equal(predicate(input.arg), false, 'old response must wait');
response.draw = 2;
assert.equal(predicate(input.arg).rows, 1, 'completed matching draw is ready');
request.search.value = '';
assert.equal(predicate(input.arg), false, 'old search must wait');
request.search.value = '278-T';
request.start = 1;
assert.equal(predicate(input.arg), false, 'pending page must wait');
request.start = 0;
info.start = 1;
assert.equal(predicate(input.arg), false, 'wrong rendered offset must wait');
info.start = 0;
table.innerText = 'Date Type Name Loading Loading';
assert.equal(predicate(input.arg), false, 'placeholder must wait');
table.innerText = 'Date Type Name Report';
delete request.draw; delete response.draw;
assert.equal(predicate(input.arg), false, 'missing counters cannot prove a completed draw');
'''
    subprocess.run(["node", "-e", harness], input=json.dumps(captured), text=True, check=True)


def test_browser_readiness_preserves_initial_nulls_and_rejects_stale_draws():
    """Exercise the actual Playwright polling transport, not just the predicate."""
    import os
    from playwright.sync_api import Error, TimeoutError, sync_playwright
    from scripts.oge_disclosures import _wait_for_rendered_table

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Error as exc:
            if "Executable doesn't exist" in str(exc) and not os.environ.get("CI"):
                pytest.skip("local Chromium is not installed; canonical CI requires it")
            raise
        try:
            page = browser.new_page()
            page.set_content("<table><tr><th>Date Type Name</th></tr><tr><td>Report</td></tr></table>")
            page.evaluate("""() => {
                window.request = {draw: 1, start: 0, search: {value: ''}};
                window.response = {draw: 1, data: [{}], recordsFiltered: 2};
                window.info = {serverSide: true, start: 0, end: 1, recordsDisplay: 2, length: 1};
                const api = {page: {info: () => info},
                    ajax: {params: () => request, json: () => response},
                    rows: () => ({count: () => 1})};
                window.jQuery = () => ({DataTable: () => api});
                jQuery.fn = {dataTable: {isDataTable: () => true}};
            }""")
            assert _wait_for_rendered_table(page, 1000) == _page_state()
            page.evaluate("() => {request.draw=2; request.search.value='278-T'}")
            with pytest.raises(TimeoutError):
                _wait_for_rendered_table(page, 150, search_term="278-T", start=0)
            page.evaluate("() => {response.draw=2}")
            assert _wait_for_rendered_table(page, 1000, search_term="278-T", start=0) == _page_state()
            page.evaluate("() => {request.draw=3; request.start=1}")
            with pytest.raises(TimeoutError):
                _wait_for_rendered_table(page, 150, search_term="278-T", start=1)
            page.evaluate("() => {response.draw=3; info.start=1; info.end=2}")
            assert _wait_for_rendered_table(page, 1000, search_term="278-T", start=1) == _page_state(1)
        finally:
            browser.close()
