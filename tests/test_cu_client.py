"""Offline tests for function/cu_client.py: a scripted session stands in for Content Understanding."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))

import cu_client  # noqa: E402

ENDPOINT = "https://vz.cognitiveservices.azure.com"
ANALYZER = "vizientContractChecklist"
OPERATION = "0f8fad5b-d9cb-469f-a165-70867728950e"
LOCATION = f"{ENDPOINT}/contentunderstanding/analyzerResults/{OPERATION}?api-version=2025-11-01"


class FakeSession:
    """Plays back scripted replies, and records each call like requests.Session.request would receive it."""

    def __init__(self, *replies: requests.Response | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def reply(status: int = 200, body: Any = None, **headers: str) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    response.headers.update({name.replace("_", "-"): value for name, value in headers.items()})
    return response


def client(*replies: requests.Response | Exception, token: Any = lambda: "tok", **kwargs: Any) -> tuple[cu_client.Client, FakeSession]:
    session = FakeSession(*replies)
    return cu_client.Client(ENDPOINT, ANALYZER, token, session=session, **kwargs), session


# --- submit ----------------------------------------------------------------------------------------------------

def test_submit_posts_the_pdf_to_the_analyzer_with_a_bearer_token() -> None:
    cu, session = client(reply(202, Operation_Location=LOCATION))

    assert cu.submit(b"%PDF-1.7 body") == OPERATION

    [call] = session.calls
    assert (call["method"], call["url"]) == ("POST", f"{ENDPOINT}/contentunderstanding/analyzers/{ANALYZER}:analyzeBinary")
    assert call["params"] == {"api-version": "2025-11-01"}
    assert call["data"] == b"%PDF-1.7 body"
    assert call["headers"]["Authorization"] == "Bearer tok"
    assert call["headers"]["Content-Type"] == "application/pdf"
    assert call["allow_redirects"] is False
    assert call["timeout"] == (10, 60)


def test_the_operation_location_host_is_never_trusted() -> None:
    hostile = f"https://evil.example/contentunderstanding/analyzerResults/{OPERATION}?api-version=2025-11-01"
    cu, session = client(reply(202, Operation_Location=hostile), reply(200, {"status": "Running"}))

    operation_id = cu.submit(b"%PDF-")
    cu.poll(operation_id)

    assert operation_id == OPERATION
    assert all(call["url"].startswith(ENDPOINT + "/") for call in session.calls)
    assert session.calls[1]["url"] == f"{ENDPOINT}/contentunderstanding/analyzerResults/{OPERATION}"


@pytest.mark.parametrize("location", [
    None,
    "",
    f"{ENDPOINT}/contentunderstanding/analyzers/{ANALYZER}",
    f"{ENDPOINT}/contentunderstanding/analyzerResults/not-a-guid",
    f"{ENDPOINT}/contentunderstanding/analyzerResults/{OPERATION}-extra",
])
def test_submit_rejects_a_reply_without_a_usable_operation_location(location: str | None) -> None:
    headers = {} if location is None else {"Operation_Location": location}
    cu, _ = client(reply(202, **headers))
    with pytest.raises(cu_client.CuError) as caught:
        cu.submit(b"%PDF-")
    assert caught.value.code == "UnexpectedReply"


# --- poll ------------------------------------------------------------------------------------------------------

def test_poll_reads_the_operation_on_the_configured_endpoint() -> None:
    cu, session = client(reply(200, {"status": "Running"}, Retry_After="7"))

    operation = cu.poll(OPERATION)

    assert (operation.id, operation.status, operation.retry_after, operation.done) == (OPERATION, "Running", 7, False)
    [call] = session.calls
    assert (call["method"], call["url"]) == ("GET", f"{ENDPOINT}/contentunderstanding/analyzerResults/{OPERATION}")
    assert call["params"] == {"api-version": "2025-11-01"}
    assert call["data"] is None and "Content-Type" not in call["headers"]


@pytest.mark.parametrize(("status", "done"), [("NotStarted", False), ("Running", False), ("Succeeded", True),
                                              ("Failed", True), ("Canceled", True)])
def test_poll_knows_which_states_are_final(status: str, done: bool) -> None:
    cu, _ = client(reply(200, {"status": status}))
    assert cu.poll(OPERATION).done is done


def test_a_succeeded_operation_carries_its_body() -> None:
    body = {"id": OPERATION, "status": "Succeeded", "result": {"contents": []}, "usage": {"documentPagesStandard": 2}}
    cu, _ = client(reply(200, body))
    assert cu.poll(OPERATION).body == body


def test_a_failed_operation_carries_a_bounded_error_description() -> None:
    body = {"status": "Failed", "error": {"code": "InvalidContent", "message": "bad pdf " + "x" * 2000}}
    cu, _ = client(reply(200, body))

    operation = cu.poll(OPERATION)

    assert operation.done and operation.error.startswith("InvalidContent - bad pdf")
    assert len(operation.error) == cu_client.MAX_MESSAGE


@pytest.mark.parametrize(("header", "expected"), [
    (None, 5), ("7", 7), ("7.9", 7), ("0", 1), ("-3", 1), ("999", 60), ("abc", 5), ("inf", 5), ("nan", 5),
    ("Wed, 21 Oct 2026 07:28:00 GMT", 5),
])
def test_retry_after_is_clamped_and_defaults_when_unreadable(header: str | None, expected: int) -> None:
    headers = {} if header is None else {"Retry_After": header}
    cu, _ = client(reply(200, {"status": "Running"}, **headers))
    assert cu.poll(OPERATION).retry_after == expected


@pytest.mark.parametrize("operation_id", ["", "abc", "../x", f"{OPERATION}/../x", f"{OPERATION}\n", OPERATION[:-1]])
def test_poll_refuses_ids_that_are_not_guids(operation_id: str) -> None:
    cu, session = client()
    with pytest.raises(ValueError, match="GUID"):
        cu.poll(operation_id)
    assert session.calls == []


@pytest.mark.parametrize("body", [{"status": "Weird"}, {"id": OPERATION}, [], "text", b"not json", None])
def test_poll_rejects_an_operation_without_a_recognised_status(body: Any) -> None:
    cu, _ = client(reply(200, body))
    with pytest.raises(cu_client.CuError) as caught:
        cu.poll(OPERATION)
    assert caught.value.code == "UnexpectedReply"


# --- failures --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("response", "status", "code", "retry_after"), [
    (reply(403, {"error": {"code": "AuthorizationFailed", "message": "no access"}}), 403, "AuthorizationFailed", 5),
    (reply(429, {"error": {"code": "TooManyRequests", "message": "slow down"}}, Retry_After="12"), 429, "TooManyRequests", 12),
    (reply(500, b"<html>boom</html>", x_ms_error_code="InternalServerError"), 500, "InternalServerError", 5),
    (reply(503, b"", Retry_After="900"), 503, None, 60),
    (reply(404, {"error": {"code": "ResourceNotFound", "message": "gone"}}), 404, "ResourceNotFound", 5),
    (reply(302, b"", Location="https://evil.example/"), 302, None, 5),
])
def test_http_failures_become_cu_errors_that_keep_the_status_code_and_retry_hint(
        response: requests.Response, status: int, code: str | None, retry_after: int) -> None:
    cu, session = client(response)

    with pytest.raises(cu_client.CuError) as caught:
        cu.poll(OPERATION)

    assert (caught.value.status, caught.value.code, caught.value.retry_after) == (status, code, retry_after)
    assert f"HTTP {status}" in str(caught.value)
    assert len(session.calls) == 1  # a redirect is an error, never followed


def test_an_upstream_error_message_is_bounded() -> None:
    cu, _ = client(reply(400, {"error": {"code": "InvalidRequest", "message": "m" * 5000}}))
    with pytest.raises(cu_client.CuError) as caught:
        cu.submit(b"%PDF-")
    assert len(str(caught.value)) < 500


def test_network_failures_become_cu_errors_without_a_status() -> None:
    cu, _ = client(requests.ConnectionError("https://secret.example/?sig=abc"))

    with pytest.raises(cu_client.CuError) as caught:
        cu.poll(OPERATION)

    assert caught.value.status is None
    assert "no reply" in str(caught.value) and "ConnectionError" in str(caught.value)
    assert "secret" not in str(caught.value)


def test_token_failures_become_cu_errors_and_nothing_is_sent() -> None:
    def broken() -> str:
        raise RuntimeError("managed identity said: secret detail")

    cu, session = client(token=broken)

    with pytest.raises(cu_client.CuError) as caught:
        cu.submit(b"%PDF-")

    assert caught.value.code == "NoToken"
    assert "secret detail" not in str(caught.value)
    assert session.calls == []


# --- configuration ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("endpoint", "origin"), [
    ("https://vz.cognitiveservices.azure.com", "https://vz.cognitiveservices.azure.com"),
    ("https://VZ.CognitiveServices.Azure.com/some/path/?x=1", "https://vz.cognitiveservices.azure.com"),
    ("https://vz.services.ai.azure.com/", "https://vz.services.ai.azure.com"),
])
def test_endpoints_are_reduced_to_their_https_origin(endpoint: str, origin: str) -> None:
    assert cu_client.normalize_endpoint(endpoint) == origin


@pytest.mark.parametrize("endpoint", [
    None,
    "",
    "vz.cognitiveservices.azure.com",
    "http://vz.cognitiveservices.azure.com",
    "https://evil.example",
    "https://cognitiveservices.azure.com",
    "https://evilcognitiveservices.azure.com",
    "https://cognitiveservices.azure.com.evil.example",
    "https://vz.cognitiveservices.azure.com@evil.example",
    "https://evil.example#.cognitiveservices.azure.com",
])
def test_endpoints_that_could_leak_the_token_are_rejected(endpoint: str | None) -> None:
    with pytest.raises(cu_client.CuError) as caught:
        cu_client.normalize_endpoint(endpoint)
    assert caught.value.code == "Misconfigured"


@pytest.mark.parametrize(("analyzer", "api_version"), [
    ("", "2025-11-01"), ("a/b", "2025-11-01"), ("a:analyzeBinary", "2025-11-01"), ("../x", "2025-11-01"),
    ("a b", "2025-11-01"), ("x" * 65, "2025-11-01"),
    (ANALYZER, ""), (ANALYZER, "v1"), (ANALYZER, "2025-11-01/../x"), (ANALYZER, "2025-11-01&x=1"),
    (ANALYZER, "2025-05-01-preview"),
])
def test_the_analyzer_id_and_api_version_cannot_reshape_the_url(analyzer: str, api_version: str) -> None:
    with pytest.raises(cu_client.CuError) as caught:
        cu_client.Client(ENDPOINT, analyzer, lambda: "tok", api_version=api_version)
    assert caught.value.code == "Misconfigured"


def test_a_ga_api_version_is_accepted() -> None:
    assert cu_client.Client(ENDPOINT, ANALYZER, lambda: "tok", api_version="2026-03-01").api_version == "2026-03-01"
