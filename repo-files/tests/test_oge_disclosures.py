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
