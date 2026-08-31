"""Validate complete discovery and send one classified terminal heartbeat.

Never forward tracker result JSON, exception text, source response bodies, or
credential-bearing URLs to logs or Healthchecks. The workflow owns start pings.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def read_result(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def complete_catalogs(result: dict) -> bool:
    counts = result.get("source_counts", {})
    statuses = result.get("source_statuses", {})
    return (
        result.get("discovery_complete") is True
        and isinstance(counts, dict)
        and isinstance(statuses, dict)
        and all(statuses.get(source) == "ok" for source in ("house", "senate"))
        and all(type(counts.get(source)) is int and counts[source] > 0
                for source in ("house", "senate"))
    )


def complete_result(result: dict) -> bool:
    return (result.get("success") is True and result.get("overall_status") == "ok"
            and complete_catalogs(result))


def terminal_classification(result: dict, job_status: str, tracker_outcome: str) -> str:
    if job_status == "success" and tracker_outcome == "success" and complete_result(result):
        return "legislative_complete"
    statuses = result.get("source_statuses", {})
    if isinstance(statuses, dict) and statuses.get("senate") == "blocked":
        return "senate_access_denied"
    if isinstance(statuses, dict) and statuses.get("senate") == "error":
        return "senate_source_error"
    if result.get("overall_status") == "degraded":
        return "legislative_discovery_incomplete"
    return "legislative_workflow_failed"


def signal_terminal(result: dict, *, base_url: str, job_status: str,
                    tracker_outcome: str, opener=None) -> bool:
    classification = terminal_classification(result, job_status, tracker_outcome)
    if not base_url:
        print("Healthchecks terminal ping: unconfigured")
        return False
    base_url = base_url.rstrip("/")
    for suffix in ("/start", "/fail"):
        if base_url.endswith(suffix):
            base_url = base_url[:-len(suffix)].rstrip("/")
    success = classification == "legislative_complete"
    try:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or any(ord(char) < 32 for char in base_url)):
            raise ValueError("invalid heartbeat URL")
        request = Request(base_url if success else base_url + "/fail",
                          data=classification.encode("ascii"), method="POST",
                          headers={"Content-Type": "text/plain"})
        opener = opener or build_opener(NoRedirect()).open
        # Exactly one terminal request; internal source retries have already ended.
        with opener(request, timeout=20) as response:
            accepted = 200 <= response.status < 300
            print(f"Healthchecks {'success' if success else 'failure'} ping: "
                  f"HTTP {response.status}; classification={classification}")
            return accepted
    except (URLError, OSError, ValueError):
        print(f"Healthchecks terminal delivery failed; classification={classification}")
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path, default=Path("legislative-result.json"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--discovery-only", action="store_true")
    args = parser.parse_args(argv)
    result = read_result(args.result)
    if args.discovery_only:
        return 0 if complete_catalogs(result) else 1
    if args.validate_only:
        valid = complete_result(result)
        print("Legislative complete-source validation: " + ("pass" if valid else "fail"))
        return 0 if valid else 1
    accepted = signal_terminal(result, base_url=os.environ.get("HEALTHCHECKS_PING_URL", ""),
                               job_status=os.environ.get("JOB_STATUS", "failure"),
                               tracker_outcome=os.environ.get("TRACKER_OUTCOME", "failure"))
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
