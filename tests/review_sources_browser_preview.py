"""Isolated TEST browser acceptance for direct source-review acknowledgements.

Every browser request is fulfilled from generated local files or a Python-memory
TEST account. No real account, collector, upload, database, or network is used.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_trade_dashboard import build_payload, build_site, load_branch


ORIGIN = "https://dashboard.test"
ACCOUNT = {"id": "test-browser-review-owner", "username": "TEST reviewer"}
STAMP = "2026-10-12T11:00:00Z"


def fingerprint(directory: Path) -> dict[str, str]:
    return {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(directory.rglob("*")) if path.is_file()}


def build_preview(work: Path) -> tuple[Path, dict]:
    source = work / "TEST-executive"
    source.mkdir(parents=True)
    # Production-shaped inventory is necessary to exercise this control: the
    # application's explicitly synthetic inventory intentionally has no personal
    # acknowledgement action. Display fields mark this isolated fixture as TEST.
    filing = {
        "filing_key": "oge:fixture-source-review", "report_id": "fixture-source-review",
        "source": "oge", "branch": "executive", "filer": "TEST Source Review Official",
        "title": "TEST browser acceptance only", "agency": "TEST Fixture Agency",
        "status": "review_required", "access_mode": "public_download", "document_format": "PDF",
        "filed_date": "2026-10-11", "first_seen_utc": STAMP,
        "source_url": ORIGIN + "/fixtures/TEST-source.pdf",
    }
    digest = hashlib.sha256(b"TEST retained OCR document version for isolated browser acceptance").hexdigest()
    receipt = {
        "filing_key": filing["filing_key"], "source_url": filing["source_url"],
        "status": "needs_review", "error_code": "unsupported_oge_278t_layout",
        "sha256": digest, "origin": "official_download", "version": "source-ocr-v2",
        "attempts": 1, "attempted_at": STAMP,
        "evidence": {"sha256": digest, "page_count": 1, "completed_pages": [1], "ocr_completed_at": STAMP},
    }
    (source / "filings.jsonl").write_text(json.dumps(filing) + "\n", encoding="utf-8")
    (source / "source-ocr.jsonl").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    (source / "state.json").write_text(json.dumps({"last_success_utc": STAMP}) + "\n", encoding="utf-8")
    before = fingerprint(source)
    payload = build_payload(
        load_branch(None, "legislative"), load_branch(source, "executive"),
        repository_url=ORIGIN + "/TEST-fixture",
    )
    site = work / "TEST-site"
    build_site(payload, site)
    rows = json.loads((site / "data/pending-reviews.json").read_text(encoding="utf-8"))
    model = json.loads((site / "data/dashboard-insights.json").read_text(encoding="utf-8"))
    assert len(rows) == 1 and rows[0]["category"] == "manual_exception"
    row = rows[0]
    assert row["review_kind"] == "source_ocr" and row["review_identity_status"] == "available"
    assert row["is_synthetic_test"] is False and row["filer"].startswith("TEST ")
    assert model["reviews"]["manual_exception_identities"] == {row["review_id"]: row["logical_review_id"]}
    assert fingerprint(source) == before, "Generating the preview changed retained source evidence"
    return site, row


class ReviewFixture:
    def __init__(self, site: Path, review: dict):
        self.site, self.review = site, review
        self.revision = 0
        self.acknowledged = []
        self.mutations = []
        self.request_ids = {}
        self.unexpected = []
        self.session_reads = 0

    def state(self):
        return {"authenticated": True, "version": 1, "account": ACCOUNT,
                "revision": self.revision, "acknowledged": deepcopy(self.acknowledged)}

    @staticmethod
    def reply(route, value, status=200):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(value),
                      headers={"Cache-Control": "private, no-store"})

    def reject(self, route, code, status=409):
        self.reply(route, {"code": code, "message": "TEST review fixture rejected an invalid change."}, status)

    def handle(self, route):
        request = route.request
        url = urlsplit(request.url)
        if url.scheme != "https" or url.netloc != "dashboard.test":
            self.unexpected.append({"method": request.method, "url": request.url})
            route.abort()
            return
        path = unquote(url.path)
        if path in {"/api/reviews/session", "/api/reviews/state"} and request.method == "GET":
            self.session_reads += 1
            self.reply(route, self.state())
            return
        if path == "/api/reviews/acknowledgements" and request.method == "POST":
            headers = request.headers
            if (headers.get("origin") != ORIGIN or headers.get("x-polititrack-review-request") != "1"
                    or headers.get("content-type") != "application/json"):
                self.reject(route, "ORIGIN_DENIED", 403)
                return
            try:
                body = json.loads(request.post_data or "")
                expected = {"review_id", "logical_review_id", "acknowledged", "expected_account_id",
                            "expected_revision", "request_id"}
                if not isinstance(body, dict) or set(body) != expected or type(body["acknowledged"]) is not bool:
                    raise ValueError
                uuid.UUID(body["request_id"])
            except (ValueError, TypeError, KeyError, AttributeError):
                self.reject(route, "INVALID_REQUEST", 400)
                return
            if body["expected_account_id"] != ACCOUNT["id"]:
                self.reject(route, "ACCOUNT_CHANGED")
                return
            if (body["review_id"] != self.review["review_id"]
                    or body["logical_review_id"] != self.review["logical_review_id"]):
                self.reject(route, "REVIEW_CHANGED")
                return
            prior = self.request_ids.get(body["request_id"])
            if prior:
                if prior[0] != body:
                    self.reject(route, "REQUEST_CONFLICT")
                else:
                    self.reply(route, prior[1])
                return
            if type(body["expected_revision"]) is not int or body["expected_revision"] != self.revision:
                self.reject(route, "REVIEW_CHANGED")
                return
            self.revision += 1
            self.acknowledged = ([{"id": body["review_id"], "logical_review_id": body["logical_review_id"],
                                   "acknowledged_at_utc": STAMP}] if body["acknowledged"] else [])
            self.mutations.append(deepcopy(body))
            result = self.state()
            self.request_ids[body["request_id"]] = (deepcopy(body), deepcopy(result))
            self.reply(route, result)
            return
        if path == "/api/billing/status" and request.method == "GET":
            # The generated shell also renders a funding summary; this unrelated
            # private service is explicitly unavailable in the browser fixture.
            self.reply(route, {"code": "LOCAL_BILLING_ONLY", "message": "TEST fixture: funding unavailable."}, 503)
            return
        target = (self.site / path.lstrip("/")).resolve() if path != "/" else self.site / "index.html"
        if (request.method not in {"GET", "HEAD"} or path.startswith("/api/")
                or not target.is_relative_to(self.site) or not target.is_file()):
            self.unexpected.append({"method": request.method, "url": request.url})
            route.abort()
            return
        route.fulfill(status=200, content_type=mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                      body=b"" if request.method == "HEAD" else target.read_bytes(),
                      headers={"Cache-Control": "no-store"})


def capture(site: Path, review: dict, output: Path) -> None:
    from playwright.sync_api import expect, sync_playwright

    fixture = ReviewFixture(site, review)
    before = fingerprint(site)
    errors, checks = [], []
    selector = '#reviews-body button[data-review-ack="' + review["review_id"] + '"][data-review-ack-surface="list"]'

    def evidence(page, width, stage):
        button = page.locator(selector)
        button.scroll_into_view_if_needed()
        metrics = page.evaluate("""selector => {
          const bounds=document.querySelector(selector).getBoundingClientRect();
          return {viewport:innerWidth,document:document.documentElement.scrollWidth,
                  body:document.body.scrollWidth,button_left:bounds.left,button_right:bounds.right,
                  button_height:bounds.height};
        }""", selector)
        assert metrics["document"] <= width + 1 and metrics["body"] <= width + 1, metrics
        assert metrics["button_left"] >= -1 and metrics["button_right"] <= width + 1, metrics
        assert metrics["button_height"] >= 30, metrics
        screenshot = f"review-sources-{width}-{stage}.png"
        page.screenshot(path=str(output / screenshot), full_page=True)
        return {"stage": stage, "screenshot": screenshot, "layout": metrics}

    with sync_playwright() as tool:
        executable = os.environ.get("POLITITRACK_TEST_CHROMIUM")
        if not executable and Path("/usr/bin/chromium").is_file():
            executable = "/usr/bin/chromium"
        browser = tool.chromium.launch(executable_path=executable or None, headless=True, args=["--no-sandbox"])
        try:
            for width, height in ((1280, 900), (390, 844)):
                context = browser.new_context(viewport={"width": width, "height": height},
                                              reduced_motion="reduce", service_workers="block")
                context.route("**/*", fixture.handle)
                page = context.new_page()
                page.set_default_timeout(15000)
                page.on("pageerror", lambda error, viewport=width: errors.append({"width": viewport, "error": str(error)}))
                try:
                    starting_revision, starting_mutations = fixture.revision, len(fixture.mutations)
                    page.goto(ORIGIN + "/#records/reviews", wait_until="domcontentloaded")
                    button = page.locator(selector)
                    expect(page.locator("#review-account-button")).to_have_text(ACCOUNT["username"])
                    expect(button).to_have_text("Acknowledge manual review")
                    expect(button).to_be_enabled()
                    expect(page.locator("#error-banner")).to_be_hidden()
                    original_url = page.url
                    assert page.locator(".record-details").count() == 0
                    stages = [evidence(page, width, "active")]
                    button.click()
                    expect(button).to_have_text("Restore to active review")
                    expect(button).to_have_attribute("data-acknowledged", "true")
                    expect(page.locator("#review-save-note")).to_contain_text("acknowledged and saved to your account")
                    expect(page.locator("#reviews-body small.success")).to_contain_text("Acknowledged by you")
                    assert page.url == original_url and page.locator(".record-details").count() == 0
                    assert fixture.revision == starting_revision + 1 and len(fixture.mutations) == starting_mutations + 1
                    assert len(fixture.acknowledged) == 1
                    page.evaluate("localStorage.clear(); sessionStorage.clear();")
                    page.reload(wait_until="domcontentloaded")
                    expect(button).to_have_attribute("data-acknowledged", "true")
                    expect(button).to_have_text("Restore to active review")
                    expect(page.locator("#reviews-body small.success")).to_contain_text("Acknowledged by you")
                    assert fixture.revision == starting_revision + 1 and len(fixture.mutations) == starting_mutations + 1
                    stages.append(evidence(page, width, "saved-after-reload"))
                    button.click()
                    expect(button).to_have_text("Acknowledge manual review")
                    expect(button).to_have_attribute("data-acknowledged", "false")
                    expect(page.locator("#review-save-note")).to_contain_text("Restored to your active manual reviews")
                    assert page.url == original_url and page.locator(".record-details").count() == 0
                    assert fixture.revision == starting_revision + 2 and len(fixture.mutations) == starting_mutations + 2
                    assert fixture.acknowledged == []
                    stages.append(evidence(page, width, "restored"))
                    checks.append({"width": width, "direct_table_acknowledgement": True,
                                   "reload_after_clearing_browser_storage": True, "restore": True,
                                   "detail_navigation_required": False, "stages": stages})
                finally:
                    context.close()
        finally:
            browser.close()
    assert not errors, errors
    assert not fixture.unexpected, fixture.unexpected
    assert fingerprint(site) == before, "Review actions changed generated filing/source evidence"
    (output / "review-sources-browser-result.json").write_text(json.dumps({
        "result": "passed", "fixture": "TEST only; generated local publication and in-memory account",
        "network_requests_forwarded": 0, "real_accounts_or_state_used": False,
        "review_id": review["review_id"], "logical_review_id": review["logical_review_id"],
        "checks": checks, "saved_changes": len(fixture.mutations), "final_revision": fixture.revision,
        "session_reads": fixture.session_reads, "source_evidence_unchanged": True,
        "browser_errors": errors, "unexpected_requests": fixture.unexpected,
    }, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="polititrack-review-browser-TEST-") as directory:
        site, review = build_preview(Path(directory))
        capture(site, review, args.output)


if __name__ == "__main__":
    main()
