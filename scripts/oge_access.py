"""Recognize published OGE PDF links without treating Form 201 as a download."""
from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import unquote, urlsplit


def is_direct_oge_pdf_url(value: str) -> bool:
    """Only an official HTTPS PDF path is evidence of a direct document link.

    A PDF filename in a request form's query string is not a document path.
    This classifies a link; callers must still validate the HTTP response/bytes.
    """
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        return bool(parsed.scheme == "https" and not parsed.username and not parsed.password
                    and parsed.port in {None, 443}
                    and (host == "oge.gov" or host.endswith(".oge.gov"))
                    and unquote(parsed.path).lower().endswith(".pdf"))
    except ValueError:
        return False


def normalize_oge_listing_access(listing: Mapping[str, Any]) -> dict[str, Any]:
    """Repair access metadata on retained listing exports, keeping their IDs."""
    result = dict(listing)
    for key in ("document_url", "request_url", "url"):
        url = str(listing.get(key) or "")
        if is_direct_oge_pdf_url(url):
            result.update(document_url=url, access_mode="direct")
            break
    return result
