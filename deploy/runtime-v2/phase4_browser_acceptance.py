"""Authenticated headless-browser acceptance for the private Runtime v2 dashboard."""

from __future__ import annotations

import argparse
import asyncio
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def _run(args: argparse.Namespace) -> dict:
    from playwright.async_api import async_playwright

    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_responses: list[dict] = []
    routes: list[dict] = []
    headers = {"Authorization": f"Bearer {args.token}"}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            extra_http_headers=headers,
            viewport={"width": 1440, "height": 1000},
        )
        page = await context.new_page()
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "response",
            lambda response: failed_responses.append(
                {"url": response.url, "status": response.status}
            )
            if response.status >= 400
            else None,
        )

        for relative in ("/", "/filing-vault.html"):
            url = urljoin(args.url.rstrip("/") + "/", relative.lstrip("/"))
            response = await page.goto(url, wait_until="networkidle", timeout=120_000)
            if response is None:
                raise RuntimeError(f"no browser response for {relative}")
            snapshot = response.headers.get("x-polititrack-snapshot", "")
            body = (await page.locator("body").inner_text()).strip()
            route = {
                "route": relative,
                "status": response.status,
                "snapshot_sha256": snapshot,
                "title": await page.title(),
                "body_has_polititrack": "polititrack" in body.casefold(),
                "body_length": len(body),
            }
            routes.append(route)
            if response.status != 200:
                raise RuntimeError(f"{relative} returned {response.status}")
            if snapshot != args.expected_snapshot:
                raise RuntimeError(f"{relative} served unexpected dashboard snapshot")
            if not route["body_has_polititrack"] or route["body_length"] < 100:
                raise RuntimeError(f"{relative} did not render the expected application shell")
            if relative == "/":
                await page.screenshot(path=str(args.screenshot), full_page=True)

        summary_url = urljoin(args.url.rstrip("/") + "/", "data/summary.json")
        summary_response = await context.request.get(summary_url, headers=headers, timeout=120_000)
        summary_status = summary_response.status
        summary_snapshot = summary_response.headers.get("x-polititrack-snapshot", "")
        if summary_status != 200 or summary_snapshot != args.expected_snapshot:
            raise RuntimeError("summary JSON did not match the accepted dashboard snapshot")
        summary = await summary_response.json()
        if not isinstance(summary, dict) or not summary:
            raise RuntimeError("summary JSON was empty or malformed")

        await context.close()
        await browser.close()

    relevant_failures = [
        item
        for item in failed_responses
        if not item["url"].startswith("data:")
        and not item["url"].startswith("chrome-extension:")
    ]
    if console_errors or page_errors or relevant_failures:
        raise RuntimeError(
            "browser reported errors: "
            + json.dumps(
                {
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "failed_responses": relevant_failures,
                },
                sort_keys=True,
            )
        )

    return {
        "schema_version": 1,
        "result": "phase4_private_dashboard_browser_accepted",
        "observed_at_utc": _utc_now(),
        "service_url": args.url,
        "expected_snapshot_sha256": args.expected_snapshot,
        "routes": routes,
        "summary_status": summary_status,
        "summary_snapshot_sha256": summary_snapshot,
        "summary_top_level_keys": sorted(summary),
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_responses": relevant_failures,
        "authenticated": True,
        "public_access_required": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--expected-snapshot", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    args = parser.parse_args()

    receipt = {
        "schema_version": 1,
        "result": "phase4_private_dashboard_browser_failed",
        "observed_at_utc": _utc_now(),
        "service_url": args.url,
        "expected_snapshot_sha256": args.expected_snapshot,
    }
    try:
        receipt = asyncio.run(_run(args))
        return_code = 0
    except BaseException as exc:
        receipt.update(
            {
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:2000],
                "traceback_tail": traceback.format_exc().splitlines()[-25:],
            }
        )
        return_code = 1
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
