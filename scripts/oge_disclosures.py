#!/usr/bin/env python3
"""Discover OGE Form 278-T listings from OGE's dynamic disclosure collection.

OGE's collection is rendered client-side. This utility uses a real browser, affirms the
statutory-use banner only after explicit operator acknowledgement, filters the collection
to periodic transaction reports, and exports normalized listing metadata for the main
tracker. It does not bypass the OGE Form 201 request process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from .monitor_disclosures import MonitorError, SourceChangedError, normalize_text, parse_bool
except ImportError:  # pragma: no cover - direct execution path
    from monitor_disclosures import MonitorError, SourceChangedError, normalize_text, parse_bool  # type: ignore

LOGGER = logging.getLogger("oge-disclosure-discovery")

OGE_COLLECTION_URL = (
    "https://www.oge.gov/web/oge.nsf/Officials%20Individual%20Disclosures%20Search%20Collection?OpenForm="
)
DEFAULT_OUTPUT = Path("oge-listings.json")
DEFAULT_DIAGNOSTICS_DIR = Path("oge-diagnostics")
DEFAULT_TIMEOUT_MS = 120_000
DEFAULT_MAX_PAGES = 250


@dataclass(frozen=True)
class OgeListing:
    listing_id: str
    date: str
    document_type: str
    name: str
    title: str
    agency: str
    level: str
    document_url: str
    request_url: str
    access_mode: str
    row_text: str


def iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_listing_id(values: Iterable[str]) -> str:
    material = "\x1f".join(normalize_text(value) for value in values)
    return "oge:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _canonical(value: str) -> str:
    value = normalize_text(value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _header_map(table: Any) -> dict[str, int]:
    headers = [_canonical(cell.get_text(" ", strip=True)) for cell in table.find_all("th")]
    aliases = {
        "date": ("date",),
        "document_type": ("type", "document type"),
        "name": ("name",),
        "title": ("title", "position title"),
        "agency": ("agency",),
        "level": ("level", "pay level"),
    }
    result: dict[str, int] = {}
    for key, candidates in aliases.items():
        for candidate in candidates:
            candidate_key = _canonical(candidate)
            exact = next((i for i, header in enumerate(headers) if header == candidate_key), None)
            if exact is not None:
                result[key] = exact
                break
        if key in result:
            continue
        for candidate in candidates:
            candidate_key = _canonical(candidate)
            partial = next((i for i, header in enumerate(headers) if candidate_key in header), None)
            if partial is not None:
                result[key] = partial
                break
    return result


def _cell(cells: Sequence[Any], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return normalize_text(cells[index].get_text(" ", strip=True))


def _classify_links(cells: Sequence[Any], base_url: str) -> tuple[str, str, str]:
    links: list[tuple[str, str]] = []
    for cell in cells:
        for anchor in cell.find_all("a", href=True):
            href = urljoin(base_url, str(anchor["href"]))
            text = normalize_text(anchor.get_text(" ", strip=True))
            links.append((href, text))

    direct: list[str] = []
    request: list[str] = []
    landing: list[str] = []
    for href, text in links:
        combined = f"{href} {text}".casefold()
        if "form 201" in combined or "request" in combined or "extapps2.oge.gov" in combined:
            request.append(href)
        elif re.search(r"\.pdf(?:$|\?)", href, re.IGNORECASE) or any(
            term in combined for term in ("download", "view document", "view report")
        ):
            direct.append(href)
        else:
            landing.append(href)

    if direct:
        return direct[0], request[0] if request else "", "direct"
    if request:
        return landing[0] if landing else "", request[0], "request"
    if landing:
        return landing[0], "", "unknown"
    return "", "", "request"


def parse_oge_table_html(html: str, base_url: str = OGE_COLLECTION_URL) -> list[OgeListing]:
    """Parse one rendered OGE table page into normalized 278-T listing rows."""
    soup = BeautifulSoup(html, "html.parser")
    listings: list[OgeListing] = []
    candidate_table_seen = False

    for table in soup.find_all("table"):
        mapping = _header_map(table)
        if not {"date", "document_type", "name"}.issubset(mapping):
            continue
        candidate_table_seen = True
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            row_text = normalize_text(row.get_text(" ", strip=True))
            lowered = row_text.casefold()
            if not row_text or "loading" in lowered:
                continue
            document_type = _cell(cells, mapping.get("document_type"))
            if not re.search(r"(?:278\s*[-–—]?\s*t|periodic\s+transaction)", document_type, re.I):
                # Some renderers place the document type in link text rather than the cell text.
                if not re.search(r"(?:278\s*[-–—]?\s*t|periodic\s+transaction)", row_text, re.I):
                    continue
            date = _cell(cells, mapping.get("date"))
            name = _cell(cells, mapping.get("name")) or "Unknown filer"
            title = _cell(cells, mapping.get("title"))
            agency = _cell(cells, mapping.get("agency"))
            level = _cell(cells, mapping.get("level"))
            document_url, request_url, access_mode = _classify_links(cells, base_url)
            listing_id = _stable_listing_id(
                (date, document_type, name, title, agency, level, document_url, request_url)
            )
            listings.append(
                OgeListing(
                    listing_id=listing_id,
                    date=date,
                    document_type=document_type,
                    name=name,
                    title=title,
                    agency=agency,
                    level=level,
                    document_url=document_url,
                    request_url=request_url,
                    access_mode=access_mode,
                    row_text=row_text,
                )
            )

    if not candidate_table_seen:
        raise SourceChangedError(
            "OGE page contains no table with Date, Type, and Name columns"
        )
    deduped = {listing.listing_id: listing for listing in listings}
    return sorted(deduped.values(), key=lambda item: (item.date, item.listing_id))


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(encoded)
        temp_name = handle.name
    Path(temp_name).replace(path)


def _save_diagnostics(page: Any, directory: Path, label: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", label).strip("-") or "diagnostic"
    try:
        page.screenshot(path=str(directory / f"{safe}.png"), full_page=True)
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.warning("Could not save OGE screenshot: %s", exc)
    try:
        (directory / f"{safe}.html").write_text(page.content(), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best effort
        LOGGER.warning("Could not save OGE HTML diagnostic: %s", exc)


def _visible(locator: Any) -> bool:
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False


def _overlay_is_blocking(overlay: Any) -> bool:
    """Return True when OGE's acknowledgement overlay can intercept pointer events."""
    try:
        return bool(
            overlay.evaluate(
                """element => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && style.pointerEvents !== 'none'
                        && rect.width > 0
                        && rect.height > 0;
                }"""
            )
        )
    except Exception:
        try:
            return overlay.is_visible()
        except Exception:
            return False


def _dismiss_terms_overlay(page: Any, *, wait_ms: int = 0) -> bool:
    """Affirm OGE's statutory-use banner through the page's own click handler."""
    overlay = page.locator("#overlay").first
    if wait_ms > 0:
        try:
            overlay.wait_for(state="attached", timeout=wait_ms)
        except Exception:
            return False
    try:
        if overlay.count() == 0 or not _overlay_is_blocking(overlay):
            return False
        text = normalize_text(overlay.text_content() or "")
    except Exception:
        return False

    if not re.search(
        r"(?:By clicking this banner.*I affirm|I am aware of these prohibitions|"
        r"unlawful for any person to obtain or use a report)",
        text,
        re.IGNORECASE,
    ):
        raise SourceChangedError(
            "A visible OGE overlay is blocking the collection, but it does not match the statutory-use acknowledgement"
        )

    # OGE currently implements the acknowledgement as <div id="overlay" onclick="off()">.
    # DOM click invokes that first-party handler without trying to click controls hidden beneath it.
    overlay.evaluate("element => element.click()")
    try:
        page.wait_for_function(
            """() => {
                const element = document.querySelector('#overlay');
                if (!element) return true;
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display === 'none'
                    || style.visibility === 'hidden'
                    || style.pointerEvents === 'none'
                    || rect.width === 0
                    || rect.height === 0;
            }""",
            timeout=10_000,
        )
    except Exception as exc:
        raise SourceChangedError(
            "OGE statutory-use acknowledgement was activated, but its overlay remained active"
        ) from exc
    LOGGER.info("Accepted OGE statutory-use acknowledgement overlay")
    return True


def _affirm_terms(page: Any) -> None:
    """Click OGE's acknowledgement banner without guessing a hidden endpoint."""
    # The overlay may be present before it is considered visible by accessibility locators.
    # Address its stable DOM id first, and wait briefly because OGE initializes it client-side.
    if _dismiss_terms_overlay(page, wait_ms=10_000):
        return

    candidates = [
        page.get_by_role("button", name=re.compile(r"affirm|proceed|agree|accept|continue", re.I)),
        page.get_by_text(re.compile(r"By clicking this banner.*I affirm", re.I)),
        page.get_by_text(re.compile(r"I am aware of these prohibitions", re.I)),
        page.locator("[role='dialog'] button"),
        page.locator(".modal button"),
        page.locator(".alert").filter(has_text=re.compile(r"wish to proceed", re.I)),
    ]
    for locator in candidates:
        try:
            count = locator.count()
        except Exception:
            continue
        for index in range(min(count, 10)):
            try:
                node = locator.nth(index)
                if not node.is_visible():
                    continue
                node.click(timeout=10_000)
                page.wait_for_timeout(1_000)
                _dismiss_terms_overlay(page)
                return
            except Exception:
                continue

    # The banner may already have been accepted or may not be active for this session.
    # Do not treat a generic Loading row as proof: that allowed a delayed overlay to survive.
    body_text = normalize_text(page.locator("body").inner_text())
    if re.search(r"Officials[’']? Individual Disclosures", body_text, re.IGNORECASE):
        LOGGER.info("OGE acknowledgement overlay is not active; continuing with rendered collection")
        return
    raise SourceChangedError("Could not locate or confirm the OGE statutory-use acknowledgement banner")


def _find_search_input(page: Any) -> Any | None:
    candidates = [
        page.locator("input[type='search']:visible"),
        page.locator(".dataTables_filter input:visible"),
        page.locator("input[placeholder*='Search' i]:visible"),
        page.get_by_role("searchbox"),
    ]
    for locator in candidates:
        try:
            if locator.count() > 0 and locator.first.is_visible():
                return locator.first
        except Exception:
            continue
    return None


def _next_locator(page: Any) -> Any | None:
    candidates = [
        page.locator("a.paginate_button.next:not(.disabled):visible"),
        page.locator("button.paginate_button.next:not(.disabled):visible"),
        page.locator("[aria-label='Next']:not([aria-disabled='true']):visible"),
        page.get_by_role("button", name=re.compile(r"^Next$", re.I)),
        page.get_by_role("link", name=re.compile(r"^Next$", re.I)),
    ]
    for locator in candidates:
        try:
            if locator.count() > 0 and locator.first.is_visible():
                node = locator.first
                classes = (node.get_attribute("class") or "").casefold()
                aria_disabled = (node.get_attribute("aria-disabled") or "").casefold()
                disabled = node.get_attribute("disabled")
                if "disabled" not in classes and aria_disabled != "true" and disabled is None:
                    return node
        except Exception:
            continue
    return None


def _wait_for_rendered_table(page: Any, timeout_ms: int) -> None:
    page.wait_for_function(
        """() => {
            const tables = Array.from(document.querySelectorAll('table'));
            return tables.some((table) => {
              const text = (table.innerText || '').replace(/\\s+/g, ' ');
              return /Date/i.test(text) && /Type/i.test(text) && /Name/i.test(text) && !/Loading\\s+Loading/i.test(text);
            });
        }""",
        timeout=timeout_ms,
    )


def scrape_oge_listings(
    *,
    collection_url: str,
    timeout_ms: int,
    max_pages: int,
    diagnostics_dir: Path,
) -> list[OgeListing]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise MonitorError("playwright is not installed") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128 Safari/537.36 "
                "MyETFGovernmentTradeTracker/1.0"
            ),
            viewport={"width": 1440, "height": 1200},
        )
        page = context.new_page()
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(collection_url, wait_until="domcontentloaded", timeout=timeout_ms)
            _affirm_terms(page)
            _wait_for_rendered_table(page, timeout_ms)
            # OGE can activate the acknowledgement overlay after DOMContentLoaded.
            _dismiss_terms_overlay(page)

            search_input = _find_search_input(page)
            search_terms = ("278-T", "Periodic Transaction") if search_input is not None else ("",)
            all_listings: dict[str, OgeListing] = {}

            for search_term in search_terms:
                if search_input is not None:
                    _dismiss_terms_overlay(page)
                    search_input.fill(search_term)
                    page.wait_for_timeout(1_500)
                page_number = 0
                seen_signatures: set[str] = set()
                term_found = False
                while page_number < max_pages:
                    page_number += 1
                    html = page.content()
                    signature = hashlib.sha256(html.encode("utf-8")).hexdigest()
                    if signature in seen_signatures:
                        break
                    seen_signatures.add(signature)
                    try:
                        listings = parse_oge_table_html(html, base_url=page.url)
                    except SourceChangedError:
                        listings = []
                    if listings:
                        term_found = True
                        all_listings.update({item.listing_id: item for item in listings})
                    next_button = _next_locator(page)
                    if next_button is None:
                        break
                    before = normalize_text(page.locator("table").first.inner_text())
                    _dismiss_terms_overlay(page)
                    try:
                        next_button.click(timeout=min(timeout_ms, 15_000))
                    except PlaywrightTimeoutError:
                        # A late OGE acknowledgement overlay can appear between discovery and click.
                        if not _dismiss_terms_overlay(page):
                            raise
                        next_button.click(timeout=min(timeout_ms, 15_000))
                    try:
                        page.wait_for_function(
                            "before => document.querySelector('table') && "
                            "(document.querySelector('table').innerText || '').replace(/\\s+/g, ' ').trim() !== before",
                            arg=before,
                            timeout=min(timeout_ms, 30_000),
                        )
                    except PlaywrightTimeoutError:
                        page.wait_for_timeout(1_500)
                if term_found:
                    break

            if not all_listings:
                _save_diagnostics(page, diagnostics_dir, "no-278t-listings")
                raise SourceChangedError(
                    "OGE collection rendered successfully but yielded zero Form 278-T listings"
                )
            return sorted(all_listings.values(), key=lambda item: (item.date, item.listing_id))
        except Exception:
            _save_diagnostics(page, diagnostics_dir, "oge-discovery-failure")
            raise
        finally:
            context.close()
            browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--collection-url", default=OGE_COLLECTION_URL)
    parser.add_argument("--diagnostics-dir", default=str(DEFAULT_DIAGNOSTICS_DIR))
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--acknowledge-terms", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    acknowledged = args.acknowledge_terms or parse_bool(
        os.environ.get("DISCLOSURE_TERMS_ACKNOWLEDGED"), default=False
    )
    if not acknowledged:
        LOGGER.error(
            "DISCLOSURE_TERMS_ACKNOWLEDGED is false. Review and explicitly acknowledge the statutory-use restrictions first."
        )
        return 1
    try:
        listings = scrape_oge_listings(
            collection_url=args.collection_url,
            timeout_ms=args.timeout_ms,
            max_pages=args.max_pages,
            diagnostics_dir=Path(args.diagnostics_dir),
        )
        payload = {
            "success": True,
            "scraped_at_utc": iso_utc(),
            "collection_url": args.collection_url,
            "count": len(listings),
            "listings": [asdict(item) for item in listings],
        }
        atomic_write_json(Path(args.output), payload)
        LOGGER.info("Discovered %s OGE Form 278-T listings", len(listings))
        return 0
    except (MonitorError, ValueError) as exc:
        LOGGER.error("OGE discovery failed: %s", exc)
        atomic_write_json(
            Path(args.output),
            {
                "success": False,
                "scraped_at_utc": iso_utc(),
                "collection_url": args.collection_url,
                "count": 0,
                "listings": [],
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        return 1
    except Exception as exc:
        LOGGER.exception("Unexpected OGE discovery failure")
        atomic_write_json(
            Path(args.output),
            {
                "success": False,
                "scraped_at_utc": iso_utc(),
                "collection_url": args.collection_url,
                "count": 0,
                "listings": [],
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
