"""Offline tests for function/routes.py and function/function_app.py: the HTTP API in front of Content Understanding."""

from __future__ import annotations

import base64
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

func = pytest.importorskip("azure.functions", reason="pip install -r function/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))

import cu_client  # noqa: E402
import function_app  # noqa: E402
import mapping  # noqa: E402
import routes  # noqa: E402

BASE = "https://func-test.azurewebsites.net/api/contracts/analyze"
OPERATION = "0f8fad5b-d9cb-469f-a165-70867728950e"
CONTRACT = "5c1b3b0e-6f43-4f4c-9d0a-2f0d6a1d9a11"
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
DOCX = b"PK\x03\x04 a word document"
FIXTURE = ROOT / "tests" / "fixtures" / "cu_result_sow.json"


class FakeClient:
    """Stands in for cu_client.Client: records what the handlers pass on and answers as the test scripts."""

    def __init__(self, operation: cu_client.Operation | None = None, error: Exception | None = None) -> None:
        self.operation, self.error = operation, error
        self.submitted: list[bytes] = []
        self.polled: list[str] = []

    def submit(self, pdf: bytes) -> str:
        self.submitted.append(pdf)
        if self.error:
            raise self.error
        return OPERATION

    def poll(self, operation_id: str) -> cu_client.Operation:
        self.polled.append(operation_id)
        if self.error:
            raise self.error
        assert self.operation is not None
        return self.operation


def context(client: FakeClient) -> routes.Context:
    return routes.Context(client, mapping.load_checklist(), mapping.DEFAULT_HIGH_CONF)  # type: ignore[arg-type]


def post(body: bytes, content_type: str | None = "application/pdf", **params: str) -> func.HttpRequest:
    headers = {"Content-Type": content_type} if content_type else {}
    return func.HttpRequest("POST", BASE, headers=headers, params=params, body=body)


def post_json(payload: Any) -> func.HttpRequest:
    return post(json.dumps(payload).encode(), "application/json")


def get(operation_id: str) -> func.HttpRequest:
    return func.HttpRequest("GET", f"{BASE}/{operation_id}", route_params={"operationId": operation_id}, body=b"")


def body_of(response: func.HttpResponse) -> Any:
    return json.loads(response.get_body())


def error_of(response: func.HttpResponse) -> tuple[int, str]:
    return response.status_code, body_of(response)["error"]["code"]


def operation(status: str, body: dict[str, Any] | None = None, retry_after: int = 5, error: str = "") -> cu_client.Operation:
    return cu_client.Operation(OPERATION, status, {"status": status} if body is None else body, retry_after, error)


def encode(pdf: bytes) -> str:
    return base64.b64encode(pdf).decode()


# --- POST /api/contracts/analyze --------------------------------------------------------------------------------

def test_a_pdf_body_starts_an_analysis() -> None:
    client = FakeClient()

    response = routes.submit(post(PDF), context(client))

    assert response.status_code == 202 and response.mimetype == "application/json"
    assert response.headers["Location"] == f"{BASE}/{OPERATION}"
    assert response.headers["Retry-After"] == "5"
    assert body_of(response) == {"operationId": OPERATION, "status": "Running"}
    assert client.submitted == [PDF]


@pytest.mark.parametrize("content_type", ["Application/PDF", "application/pdf; charset=binary"])
def test_the_pdf_content_type_is_matched_loosely(content_type: str) -> None:
    client = FakeClient()
    assert routes.submit(post(PDF, content_type), context(client)).status_code == 202
    assert client.submitted == [PDF]


@pytest.mark.parametrize("content_type", ["application/json", None])
def test_a_json_body_with_line_wrapped_base64_starts_an_analysis(content_type: str | None) -> None:
    encoded = encode(PDF)
    wrapped = "\r\n".join(encoded[i:i + 10] for i in range(0, len(encoded), 10))
    payload = json.dumps({"contractId": CONTRACT, "fileName": "sow.pdf", "fileBase64": wrapped}).encode()
    client = FakeClient()

    response = routes.submit(post(payload, content_type), context(client))

    assert response.status_code == 202
    assert client.submitted == [PDF]


@pytest.mark.parametrize(("build", "status", "code"), [
    (lambda: post(b""), 400, "EmptyFile"),
    (lambda: post(b"", "application/json"), 400, "InvalidJson"),
    (lambda: post(b"{not json", "application/json"), 400, "InvalidJson"),
    (lambda: post(b"\xff\xfe", "application/json"), 400, "InvalidJson"),
    (lambda: post_json({"fileName": "x.pdf"}), 400, "MissingFile"),
    (lambda: post_json({"fileBase64": ""}), 400, "MissingFile"),
    (lambda: post_json({"fileBase64": "   "}), 400, "MissingFile"),
    (lambda: post_json({"fileBase64": 42}), 400, "MissingFile"),
    (lambda: post_json(["fileBase64"]), 400, "MissingFile"),
    (lambda: post_json({"fileBase64": "***not base64***"}), 400, "InvalidBase64"),
    (lambda: post(DOCX), 415, "NotAPdf"),
    (lambda: post_json({"fileBase64": encode(DOCX)}), 415, "NotAPdf"),
    (lambda: post(PDF, "text/plain"), 415, "UnsupportedMediaType"),
    (lambda: post(PDF, "multipart/form-data; boundary=x"), 415, "UnsupportedMediaType"),
])
def test_bad_requests_are_rejected_before_content_understanding_is_called(build: Any, status: int, code: str) -> None:
    client = FakeClient()

    response = routes.submit(build(), context(client))

    assert error_of(response) == (status, code)
    assert client.submitted == []


def test_oversized_documents_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(routes, "MAX_PDF_BYTES", 64)
    monkeypatch.setattr(routes, "MAX_BASE64_CHARS", 88)
    over = PDF + b"0" * 64
    client = FakeClient()

    for request in (post(over), post_json({"fileBase64": encode(over)})):
        assert error_of(routes.submit(request, context(client))) == (413, "FileTooLarge")
    assert client.submitted == []

    assert routes.submit(post(over[:64]), context(client)).status_code == 202  # exactly at the limit


def test_only_ids_and_sizes_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    request = post_json({"contractId": CONTRACT, "fileName": "Confidential Pricing.pdf", "fileBase64": encode(PDF)})

    routes.submit(request, context(FakeClient()))

    assert CONTRACT in caplog.text and OPERATION in caplog.text and f"bytes={len(PDF)}" in caplog.text
    assert "Confidential" not in caplog.text


def test_a_contract_id_that_is_not_a_guid_never_reaches_the_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    routes.submit(post(PDF, contractId="x\nERROR forged log line"), context(FakeClient()))

    assert "forged" not in caplog.text and "contract=-" in caplog.text


UPSTREAM_FAILURES = [
    (cu_client.CuError("busy", status=429, retry_after=17), 429, "Throttled", "17"),
    (cu_client.CuError("down", status=503), 503, "UpstreamUnavailable", "5"),
    (cu_client.CuError("no reply"), 503, "UpstreamUnavailable", "5"),
    (cu_client.CuError("denied", status=403), 502, "UpstreamForbidden", None),
    (cu_client.CuError("denied", status=401), 502, "UpstreamForbidden", None),
    (cu_client.CuError("rejected", status=400, code="InvalidRequest"), 502, "UpstreamRejected", None),
    (cu_client.CuError("bad config", code="Misconfigured"), 500, "Misconfigured", None),
    (cu_client.CuError("token", code="NoToken"), 502, "NoToken", None),
]


@pytest.mark.parametrize(("failure", "status", "code", "retry_after"), UPSTREAM_FAILURES)
def test_content_understanding_failures_map_to_clean_http_errors(failure: cu_client.CuError, status: int, code: str,
                                                                 retry_after: str | None) -> None:
    for handler, request in ((routes.submit, post(PDF)), (routes.poll, get(OPERATION))):
        response = handler(request, context(FakeClient(error=failure)))

        assert error_of(response) == (status, code)
        assert response.headers.get("Retry-After") == retry_after
        assert set(body_of(response)) == {"error"} and set(body_of(response)["error"]) == {"code", "message"}


# --- GET /api/contracts/analyze/{operationId} -------------------------------------------------------------------

@pytest.mark.parametrize("status", ["Running", "NotStarted"])
def test_an_analysis_in_progress_returns_202_with_the_poll_location(status: str) -> None:
    client = FakeClient(operation(status, retry_after=9))

    response = routes.poll(get(OPERATION), context(client))

    assert response.status_code == 202
    assert response.headers["Location"] == f"{BASE}/{OPERATION}" and response.headers["Retry-After"] == "9"
    assert body_of(response) == {"operationId": OPERATION, "status": status}
    assert client.polled == [OPERATION]


def test_a_finished_analysis_returns_the_review_payload() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    response = routes.poll(get(OPERATION), context(FakeClient(operation("Succeeded", fixture))))

    payload = body_of(response)
    assert response.status_code == 200 and response.mimetype == "application/json"
    assert set(payload) == {"contract", "findings", "raw", "indexing"}
    assert len(payload["findings"]) == 20 and payload["contract"]["foundCount"] == 13
    assert payload["indexing"]["status"] == "Queued"
    assert "Artificial Intelligence" in payload["indexing"]["documentText"]


def test_a_dense_extraction_is_bounded_by_its_page_text_not_its_raw_size() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture["result"]["contents"][0]["words"] = [{"content": "word", "span": {"offset": 0, "length": 4}}] * 60_000
    assert len(json.dumps(fixture)) > routes.contract_qa.MAX_CONTEXT
    payload = body_of(routes.poll(get(OPERATION), context(FakeClient(operation("Succeeded", fixture)))))
    assert payload["indexing"]["status"] == "Queued"
    assert len(payload["indexing"]["documentText"]) < routes.contract_qa.MAX_CONTEXT


def test_missing_full_text_fails_indexing_without_failing_review() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del fixture["result"]["contents"][0]["markdown"]
    response = routes.poll(get(OPERATION), context(FakeClient(operation("Succeeded", fixture))))
    payload = body_of(response)
    assert response.status_code == 200 and len(payload["findings"]) == 20
    assert payload["indexing"]["status"] == "Failed"
    assert payload["indexing"]["documentText"] == ""


@pytest.mark.parametrize(("status", "code"), [("Failed", "AnalysisFailed"), ("Canceled", "AnalysisCanceled")])
def test_a_failed_or_canceled_analysis_is_a_502_that_says_why(status: str, code: str) -> None:
    detailed = routes.poll(get(OPERATION), context(FakeClient(operation(status, error="InvalidContent - not a PDF"))))
    plain = routes.poll(get(OPERATION), context(FakeClient(operation(status))))

    assert error_of(detailed) == (502, code) and error_of(plain) == (502, code)
    assert body_of(detailed)["error"]["message"] == "InvalidContent - not a PDF"
    assert body_of(plain)["error"]["message"] == f"The analysis {status.lower()}."


def test_a_result_that_is_not_a_checklist_result_is_a_502() -> None:
    broken = {"status": "Succeeded", "result": {"contents": [{"fields": {}}]}}

    response = routes.poll(get(OPERATION), context(FakeClient(operation("Succeeded", broken))))

    assert error_of(response) == (502, "UnexpectedResult")


def test_an_unknown_operation_is_a_404() -> None:
    response = routes.poll(get(OPERATION), context(FakeClient(error=cu_client.CuError("gone", status=404))))
    assert error_of(response) == (404, "OperationNotFound")


@pytest.mark.parametrize("operation_id", ["", "not-a-guid", "..%2Fx", OPERATION + "x", OPERATION[:-1]])
def test_an_operation_id_that_is_not_a_guid_is_a_400_and_never_reaches_the_service(operation_id: str) -> None:
    client = FakeClient()

    response = routes.poll(get(operation_id), context(client))

    assert error_of(response) == (400, "InvalidOperationId")
    assert client.polled == []


# --- the Function app -------------------------------------------------------------------------------------------

def test_the_app_registers_the_health_probe_and_the_two_analysis_routes() -> None:
    def describe(trigger: Any) -> tuple[str, set[str], Any]:
        return trigger.route, {getattr(m, "value", m) for m in trigger.methods}, trigger.auth_level

    registered = {fn.get_function_name(): describe(fn.get_trigger()) for fn in function_app.app.get_functions()}

    assert registered == {
        "health": ("health", {"GET"}, func.AuthLevel.ANONYMOUS),
        "start_analysis": ("contracts/analyze", {"POST"}, func.AuthLevel.FUNCTION),
        "get_analysis": ("contracts/analyze/{operationId}", {"GET"}, func.AuthLevel.FUNCTION),
        "ask_contract": ("contracts/questions", {"POST"}, func.AuthLevel.FUNCTION),
        "index_contract": ("contracts/index", {"POST"}, func.AuthLevel.FUNCTION),
    }


def test_health_needs_no_key_and_discloses_nothing() -> None:
    health = function_app.health.build().get_user_function()

    response = health(func.HttpRequest("GET", "https://func-test.azurewebsites.net/api/health", body=b""))

    assert response.status_code == 200
    assert body_of(response) == {"status": "ok", "service": "vizient-contract-api"}


@pytest.fixture
def credential(monkeypatch: pytest.MonkeyPatch) -> Any:
    seen: dict[str, Any] = {}

    class FakeCredential:
        def __init__(self, **kwargs: Any) -> None:
            seen["init"] = kwargs

        def get_token(self, scope: str) -> SimpleNamespace:
            seen["scope"] = scope
            return SimpleNamespace(token="tok")

    monkeypatch.setattr("azure.identity.DefaultAzureCredential", FakeCredential)
    function_app._context.cache_clear()
    yield seen
    function_app._context.cache_clear()


def test_the_context_is_built_from_the_app_settings(monkeypatch: pytest.MonkeyPatch, credential: Any) -> None:
    settings = {"CU_ENDPOINT": "https://vz.cognitiveservices.azure.com/", "CU_ANALYZER_ID": "myAnalyzer",
                "CU_API_VERSION": "2026-03-01", "AZURE_CLIENT_ID": "client-1", "HIGH_CONF": "0.9"}
    for name, value in settings.items():
        monkeypatch.setenv(name, value)

    ctx = function_app._context()

    assert (ctx.client.endpoint, ctx.client.analyzer_id, ctx.client.api_version) == (
        "https://vz.cognitiveservices.azure.com", "myAnalyzer", "2026-03-01")
    assert ctx.high_conf == 0.9 and len(ctx.items) == 20
    assert credential["init"] == {"managed_identity_client_id": "client-1"}
    assert ctx.client.token() == "tok" and credential["scope"] == "https://cognitiveservices.azure.com/.default"
    assert function_app._context() is ctx


def test_the_optional_settings_have_defaults(monkeypatch: pytest.MonkeyPatch, credential: Any) -> None:
    for name in ("CU_ANALYZER_ID", "CU_API_VERSION", "AZURE_CLIENT_ID", "HIGH_CONF"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CU_ENDPOINT", "https://vz.services.ai.azure.com")

    ctx = function_app._context()

    assert (ctx.client.analyzer_id, ctx.client.api_version, ctx.high_conf) == ("vizientContractChecklist", "2025-11-01", 0.8)
    assert credential["init"] == {"managed_identity_client_id": None}


def test_a_missing_endpoint_is_a_clean_500_not_a_crash(monkeypatch: pytest.MonkeyPatch, credential: Any) -> None:
    monkeypatch.delenv("CU_ENDPOINT", raising=False)

    response = function_app._handle(routes.submit, post(PDF))

    assert error_of(response) == (500, "Misconfigured")


def test_an_unreadable_checklist_is_a_clean_500_that_hides_the_path(monkeypatch: pytest.MonkeyPatch,
                                                                    credential: Any) -> None:
    monkeypatch.setenv("CU_ENDPOINT", "https://vz.cognitiveservices.azure.com")

    def missing(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("D:\\home\\site\\wwwroot\\checklist.json")

    monkeypatch.setattr(mapping, "load_checklist", missing)

    response = function_app._handle(routes.submit, post(PDF))

    assert error_of(response) == (500, "Misconfigured")
    assert "wwwroot" not in response.get_body().decode()
