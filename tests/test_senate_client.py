"""Deterministic official-source contract fixtures; never contact eFD in tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
import requests
from requests import Response
from requests.cookies import RequestsCookieJar

import scripts.monitor_disclosures as monitor


FORM_TOKEN = "A" * 64
COOKIE_TOKEN = "B" * 32
SEARCH_TOKEN = "C" * 64
SEARCH_COOKIE = "D" * 32
SESSION_TOKEN = "S" * 32
REPORT_URL = monitor.SENATE_ROOT + "/search/view/ptr/example/"
LANDING = f'''<html><form id="agreement_form" method="post">
<input name="csrfmiddlewaretoken" type="hidden" value="{FORM_TOKEN}">
<input name="prohibition_agreement" type="checkbox"></form></html>'''
SEARCH = f'''<html><h1>Find Reports</h1><form id="searchForm" method="post">
<input name="csrfmiddlewaretoken" type="hidden" value="{SEARCH_TOKEN}">
<input name="first_name"><input name="last_name">
<input name="report_type"><input name="filer_type"></form></html>'''
REPORT = "<html><table><tr>" + "<td>valid report</td>" * 8 + "</tr></table></html>"
ROW = ["Alex", "Example", "PTR", '<a href="/search/view/ptr/example/">View</a>', "08/30/2026"]
NOW = datetime(2026, 8, 31, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("unit test attempted live network")
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


def response(status=200, text="", *, content_type="text/html", **headers):
    result = Response()
    result.status_code = status
    result._content = text.encode() if isinstance(text, str) else text
    result.headers.update({"Content-Type": content_type, **headers})
    return result


def json_response(body=None):
    if body is None:
        body = {"draw": 1, "recordsTotal": 1, "recordsFiltered": 1, "data": [ROW], "result": "fixture"}
    return response(text=json.dumps(body), content_type="application/json")


class FakeSession:
    def __init__(self, steps):
        self.steps = list(steps)
        self.calls = []
        self.cookies = RequestsCookieJar()
        self.headers = {}
        self.closes = 0

    def close(self):
        self.closes += 1

    def get(self, url, **kwargs):
        return self._request("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, kwargs)

    def _request(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        expected_method, expected_url, result, cookies = self.steps.pop(0)
        assert (method, url) == (expected_method, expected_url)
        assert kwargs["allow_redirects"] is False
        for key, value in cookies.items():
            self.cookies.set(key, value, domain="efdsearch.senate.gov", path="/")
        if isinstance(result, Exception):
            raise result
        result.url = url
        return result


def step(method, url, result, **cookies):
    return method, url, result, cookies


def bootstrap(*, landing=LANDING, terms_status=302, terms_cookies=True, search=SEARCH):
    return [
        step("GET", monitor.SENATE_HOME_URL, response(text=landing), csrftoken=COOKIE_TOKEN),
        step("POST", monitor.SENATE_HOME_URL, response(terms_status, Location="/search/"), **({"sessionid": SESSION_TOKEN} if terms_cookies else {})),
        step("GET", monitor.SENATE_SEARCH_URL, response(text=search), csrftoken=SEARCH_COOKIE),
    ]


def client_for(*sessions):
    made, delays = [], []
    pending = iter(sessions)

    def factory():
        item = next(pending)
        made.append(item)
        return item

    client = monitor.SenateClient(session_factory=factory, sleep=delays.append, random=lambda: 0.25)
    return client, made, delays


def fetch(client):
    return monitor.fetch_senate_reports(client, 120, now=NOW)


def test_initial_403_discards_session_then_succeeds_with_distinct_tokens():
    denied = FakeSession([step("GET", monitor.SENATE_HOME_URL, response(403, "Forbidden"))])
    good = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response())])
    client, made, delays = client_for(denied, good)
    assert len(fetch(client)) == 1
    assert made == [denied, good] and denied.closes == 1 and good.closes == 0
    assert delays == [1.25]
    assert good.headers["User-Agent"] == monitor.SENATE_USER_AGENT
    terms = good.calls[1][2]
    assert terms["data"] == {"csrfmiddlewaretoken": FORM_TOKEN, "prohibition_agreement": "1"}
    assert terms["headers"] == {"Origin": monitor.SENATE_ROOT, "Referer": monitor.SENATE_HOME_URL}
    search = good.calls[3][2]
    assert search["data"]["csrfmiddlewaretoken"] == SEARCH_TOKEN
    assert search["headers"]["X-CSRFToken"] == SEARCH_COOKIE
    assert search["headers"]["X-Requested-With"] == "XMLHttpRequest"
    assert search["headers"]["Origin"] == monitor.SENATE_ROOT
    assert search["headers"]["Referer"] == monitor.SENATE_SEARCH_URL
    client.close()
    assert good.closes == 1


def test_three_landing_403s_are_exact_limit_and_typed_failure():
    sessions = [FakeSession([step("GET", monitor.SENATE_HOME_URL, response(403))]) for _ in range(3)]
    client, made, delays = client_for(*sessions)
    with pytest.raises(monitor.SenateAccessDenied) as caught:
        fetch(client)
    assert caught.value.attempt == 3
    assert made == sessions and [s.closes for s in sessions] == [1, 1, 1]
    assert delays == [1.25, 2.25]
    assert all(len(s.calls) == 1 for s in sessions)
    assert client.session is None
    with pytest.raises(monitor.SenateAccessDenied, match="retry_budget_exhausted"):
        client.bootstrap()
    assert made == sessions


@pytest.mark.parametrize("status", [302, 303])
def test_terms_redirect_and_session_cookie_are_required(status):
    session = FakeSession(bootstrap(terms_status=status))
    client, _, _ = client_for(session)
    assert client.bootstrap() == SEARCH_TOKEN
    assert session.calls[1][2]["allow_redirects"] is False


def test_signed_cookie_session_backend_is_accepted_without_database_key_assumption():
    steps = bootstrap()
    steps[1][3]["sessionid"] = "." + "signedPayload" * 30 + ":1abcDE:" + "signature" * 6
    session = FakeSession(steps)
    client, _, _ = client_for(session)
    assert client.bootstrap() == SEARCH_TOKEN


@pytest.mark.parametrize("session_cookie", ["", "invalid;cookie", "invalid\ncookie", "x" * 4097])
def test_invalid_opaque_session_cookie_is_rejected(session_cookie):
    steps = bootstrap()
    steps[1][3]["sessionid"] = session_cookie
    session = FakeSession(steps)
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse, match="session_cookie"):
        client.bootstrap()


@pytest.mark.parametrize("change", ["cookie", "redirect", "status"])
def test_terms_fail_closed_for_missing_cookie_or_wrong_redirect(change):
    steps = bootstrap(terms_cookies=change != "cookie")
    if change == "redirect":
        steps[1][2].headers["Location"] = "/search/home/"
    if change == "status":
        steps[1][2].status_code = 200
    session = FakeSession(steps)
    client, made, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse):
        client.bootstrap()
    assert len(made) == 1 and session.closes == 1
    assert len(session.calls) == 2


def test_terms_csrf_403_restarts_complete_handshake_with_new_cookie_jar():
    first_steps = bootstrap()
    first_steps[1][2].status_code = 403
    first_steps[1][2]._content = b"Forbidden: CSRF verification failed"
    first = FakeSession(first_steps[:2])
    second = FakeSession(bootstrap())
    client, made, _ = client_for(first, second)
    client.bootstrap()
    assert made == [first, second]
    assert len(first.calls) == 2 and len(second.calls) == 3
    assert first.closes == 1


@pytest.mark.parametrize("mode", ["csrf", "redirect", "redirect_query"])
def test_search_expiry_replays_once_after_complete_bootstrap(mode):
    expired = response(403, "CSRF verification failed. Request aborted.") if mode == "csrf" else response(302, Location="/search/home/?next=search" if mode == "redirect_query" else "/search/home/")
    first = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, expired)])
    second = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response())])
    client, made, _ = client_for(first, second)
    assert len(fetch(client)) == 1
    assert made == [first, second] and first.closes == 1


def test_report_expiry_and_pdf_share_retained_session():
    first = FakeSession(bootstrap() + [
        step("POST", monitor.SENATE_REPORTS_URL, json_response()),
        step("GET", REPORT_URL, response(302, Location="/search/home/")),
    ])
    second = FakeSession(bootstrap() + [
        step("GET", REPORT_URL, response(text=REPORT)),
        step("GET", monitor.SENATE_ROOT + "/document.pdf", response(text=b"%PDF-example", content_type="application/pdf")),
    ])
    client, made, _ = client_for(first, second)
    reports = fetch(client)
    assert monitor._senate_page_response(client, reports[0]).text == REPORT
    assert client.get(monitor.SENATE_ROOT + "/document.pdf").content == b"%PDF-example"
    assert made == [first, second] and len(second.calls) == 5


def test_second_expiry_is_terminal_even_with_one_bootstrap_attempt_remaining():
    sessions = [FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, response(302, Location="/search/home/"))]) for _ in range(2)]
    client, made, delays = client_for(*sessions)
    with pytest.raises(monitor.SenateAccessDenied, match="session_expired"):
        fetch(client)
    assert len(made) == 2 and len(delays) == 1


def test_bootstrap_budget_is_shared_across_search_and_report_operations():
    first = FakeSession([step("GET", monitor.SENATE_HOME_URL, response(403))])
    second = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, response(503))])
    third = FakeSession(bootstrap() + [
        step("POST", monitor.SENATE_REPORTS_URL, json_response()),
        step("GET", REPORT_URL, response(403)),
    ])
    client, made, delays = client_for(first, second, third)
    client.bootstrap()
    assert len(fetch(client)) == 1
    with pytest.raises(monitor.SenateAccessDenied) as caught:
        client.get(REPORT_URL)
    assert caught.value.attempt == 3 and len(made) == 3 and len(delays) == 2


@pytest.mark.parametrize("body", ["", "Access denied", "<html>WAF access denied</html>", SEARCH, "<form id='agreement_form'></form>", LANDING.replace('type="hidden"', 'type="text"'), LANDING.replace(FORM_TOKEN, "short")])
def test_invalid_landing_200_is_not_zero_filings_or_retryable(body):
    session = FakeSession([step("GET", monitor.SENATE_HOME_URL, response(text=body), csrftoken=COOKIE_TOKEN)])
    client, made, delays = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse):
        fetch(client)
    assert len(made) == 1 and not delays


@pytest.mark.parametrize("body", ["", "<html>Access denied</html>", LANDING, "<html>Login</html>", SEARCH.replace('id="searchForm"', 'id="unknown"')])
def test_invalid_find_reports_page_fails_closed(body):
    session = FakeSession(bootstrap(search=body))
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse):
        fetch(client)


@pytest.mark.parametrize("body", ["", LANDING, "<html>Access denied</html>", "<html>Login</html>", "<html>broken</html>"])
def test_invalid_report_200_is_a_typed_sanitized_error(body):
    session = FakeSession(bootstrap() + [step("GET", REPORT_URL, response(text=body))])
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse):
        client.get(REPORT_URL)


@pytest.mark.parametrize("body", [{}, {"data": {}}, [], {"draw": 1, "recordsTotal": 91, "recordsFiltered": 91, "data": [ROW], "result": "fixture"}, {"draw": 1, "recordsTotal": 91, "recordsFiltered": 91, "data": [], "result": "fixture"}, {"draw": True, "recordsTotal": 1, "recordsFiltered": 1, "data": [ROW], "result": "fixture"}, {"draw": 1, "recordsTotal": 1, "recordsFiltered": 1, "data": [["malformed"]], "result": "fixture"}])
def test_malformed_json_schema_or_incomplete_catalog_fails_closed(body):
    session = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response(body))])
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse):
        fetch(client)


@pytest.mark.parametrize("content_type,text", [("application/json", "{broken"), ("text/html", LANDING), ("text/html", "<html>WAF</html>"), ("text/html", "")])
def test_non_json_and_malformed_json_do_not_become_empty_results(content_type, text):
    session = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, response(text=text, content_type=content_type))])
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse):
        fetch(client)


def test_explicit_empty_catalog_is_valid_json_not_unavailable_source():
    session = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response({"draw": 1, "recordsTotal": 0, "recordsFiltered": 0, "data": [], "result": "fixture"}))])
    client, _, _ = client_for(session)
    assert fetch(client) == []  # Tracker independently disallows empty required sources.


@pytest.mark.parametrize("retry_after,expected", [("45", 45.0), ("999999", 120.0), ("nonsense-cookie=secret", 1.25)])
def test_retry_after_is_honored_and_capped_without_waiting(retry_after, expected):
    first = FakeSession([step("GET", monitor.SENATE_HOME_URL, response(429, **{"Retry-After": retry_after}))])
    second = FakeSession(bootstrap())
    client, _, delays = client_for(first, second)
    client.bootstrap()
    assert delays == [expected]


def test_retry_after_http_date_and_transport_exception_are_safe(monkeypatch, caplog):
    monkeypatch.setattr(monitor, "utc_now", lambda: NOW)
    first = FakeSession([step("GET", monitor.SENATE_HOME_URL, requests.Timeout("SECRET-CSRF-sessionid"))])
    second = FakeSession([step("GET", monitor.SENATE_HOME_URL, response(503, **{"Retry-After": "Mon, 31 Aug 2026 00:01:00 GMT"}))])
    third = FakeSession(bootstrap())
    client, _, delays = client_for(first, second, third)
    client.bootstrap()
    assert delays == [1.25, 60.0]
    assert "SECRET-CSRF-sessionid" not in caplog.text


@pytest.mark.parametrize("status", [408, 425, 429, 500, 502, 503, 504, 599])
def test_retryable_statuses_restart_session(status):
    first = FakeSession([step("GET", monitor.SENATE_HOME_URL, response(status))])
    second = FakeSession(bootstrap())
    client, made, _ = client_for(first, second)
    client.bootstrap()
    assert len(made) == 2 and first.closes == 1


def test_diagnostics_redact_all_body_headers_tokens_and_url_queries(caplog, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "33342768435")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    sensitive = "UNKNOWN-SENSITIVE-COOKIE"
    denied = response(403, f"Forbidden csrfmiddlewaretoken={FORM_TOKEN} sessionid={SESSION_TOKEN} Cookie: {sensitive}", **{
        "Set-Cookie": f"sessionid={SESSION_TOKEN}", "Server": f"nginx {sensitive}",
        "X-Request-ID": f"{COOKIE_TOKEN}", "X-Amzn-RequestId": sensitive,
        "Location": f"/search/home/?csrfmiddlewaretoken={SEARCH_TOKEN}",
        "Retry-After": sensitive,
    })
    session = FakeSession([step("GET", monitor.SENATE_HOME_URL, denied, csrftoken=COOKIE_TOKEN)])
    client, _, _ = client_for(session)
    client.MAX_ATTEMPTS = 1
    with pytest.raises(monitor.SenateAccessDenied) as caught:
        fetch(client)
    output = caplog.text + json.dumps({"errors": [str(caught.value)]})
    for secret in (FORM_TOKEN, COOKIE_TOKEN, SEARCH_TOKEN, SESSION_TOKEN, sensitive, "Set-Cookie"):
        assert secret not in output
    assert '"github_run_id": "33342768435"' in output
    assert '"body_fingerprint"' in output and '"body_excerpt": "page markers:' in output
    assert '"stage": "landing"' in output and '"attempt": 1' in output
    assert '"status": 403' in output and '"elapsed_seconds"' in output


@pytest.mark.parametrize("url", ["https://evil.example/report.pdf", "http://efdsearch.senate.gov/report.pdf", "https://efdsearch.senate.gov@evil.example/report.pdf", "https://efdsearch.senate.gov:443/report.pdf"])
def test_untrusted_report_url_is_rejected_before_network(url):
    client, made, _ = client_for()
    with pytest.raises(monitor.SenateInvalidResponse):
        client.get(url)
    with pytest.raises(monitor.SenateInvalidResponse):
        monitor.extract_report_link(f'<a href="{url}">View</a>')
    assert made == []


def test_external_report_redirect_is_not_followed():
    session = FakeSession(bootstrap() + [step("GET", REPORT_URL, response(302, Location="https://evil.example/secret"))])
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse, match="untrusted_report_redirect"):
        client.get(REPORT_URL)
    assert len(session.calls) == 4


def test_duplicate_report_rows_cannot_hide_missing_filings():
    body = {"draw": 1, "recordsTotal": 2, "recordsFiltered": 2, "data": [ROW, ROW], "result": "fixture"}
    session = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response(body))])
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse, match="duplicate_catalog"):
        fetch(client)


def test_pagination_preserves_complete_catalog_and_report_identity():
    rows = [ROW[:3] + [f'<a href="/search/view/ptr/report-{index}/">View</a>', ROW[4]] for index in range(101)]
    bodies = [
        {"draw": 1, "recordsTotal": 101, "recordsFiltered": 101, "data": rows[:100], "result": "fixture"},
        {"draw": 2, "recordsTotal": 101, "recordsFiltered": 101, "data": rows[100:], "result": "fixture"},
    ]
    session = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response(body)) for body in bodies])
    client, made, _ = client_for(session)
    reports = fetch(client)
    assert len(reports) == 101 and len(made) == 1
    assert {report.report_id for report in reports} == {f"senate:{monitor.SENATE_ROOT}/search/view/ptr/report-{index}/" for index in range(101)}
    assert [call[2]["data"]["start"] for call in session.calls if call[1] == monitor.SENATE_REPORTS_URL] == ["0", "100"]


def test_pagination_changed_total_emits_safe_diagnostics(caplog):
    rows = [ROW[:3] + [f'<a href="/search/view/ptr/report-{index}/">View</a>', ROW[4]] for index in range(100)]
    bodies = [
        {"draw": 1, "recordsTotal": 101, "recordsFiltered": 101, "data": rows, "result": "fixture"},
        {"draw": 2, "recordsTotal": 100, "recordsFiltered": 100, "data": [], "result": "fixture"},
    ]
    session = FakeSession(bootstrap() + [step("POST", monitor.SENATE_REPORTS_URL, json_response(body)) for body in bodies])
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse, match="catalog_total_changed"):
        fetch(client)
    assert '"stage": "search"' in caplog.text
    assert '"status": 200' in caplog.text


@pytest.mark.parametrize("cookie_name", ["csrftoken", "sessionid"])
def test_cookie_scoped_to_different_origin_cannot_authenticate(cookie_name):
    steps = bootstrap()
    cookie_step = 0 if cookie_name == "csrftoken" else 1
    steps[cookie_step][3].pop(cookie_name)
    session = FakeSession(steps)
    session.cookies.set(cookie_name, COOKIE_TOKEN if cookie_name == "csrftoken" else SESSION_TOKEN, domain="evil.example", path="/")
    client, _, _ = client_for(session)
    with pytest.raises(monitor.SenateInvalidResponse, match="cookie"):
        client.bootstrap()


def test_pdf_parser_warning_can_be_sanitized(monkeypatch, caplog):
    def bad_pdf(*_args, **_kwargs):
        raise ValueError("SECRET-PDF-CSRF-cookie")
    monkeypatch.setattr(monitor.pdfplumber, "open", bad_pdf)
    monkeypatch.setattr(monitor, "pytesseract", None)
    with pytest.raises(monitor.MonitorError, match="OCR dependencies"):
        monitor.extract_pdf_text(b"%PDF-corrupt", 3, safe_diagnostics=True)
    assert "SECRET-PDF-CSRF-cookie" not in caplog.text
    assert "parser failure" in caplog.text
