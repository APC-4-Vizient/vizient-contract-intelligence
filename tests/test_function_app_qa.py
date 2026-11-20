"""Offline tests for the question and indexing routes and the client factories of function/function_app.py: what a caller is told when a
step is accepted, refused or fails, and that a failure never puts a prompt, a quote or an SDK message into the response or the log."""

from __future__ import annotations

import json
import logging
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

func = pytest.importorskip("azure.functions", reason="pip install -r function/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))

import contract_qa  # noqa: E402
import contract_search  # noqa: E402
import function_app  # noqa: E402

URL = "https://func-test.azurewebsites.net/api/contracts"
CLAUSE = "Example Supplier shall not disclose the Data to any third party."  # made up, as the text of a failure that must not be echoed


class Step:
    """Stands in for contract_qa.Client and contract_search.Client: a step answers with a status and a body, or raises."""

    def __init__(self, answer: tuple[int, dict[str, Any]] = (200, {"ok": True}), error: Exception | None = None) -> None:
        self.answer, self.error = answer, error
        self.payloads: list[Any] = []

    def step(self, payload: Any) -> tuple[int, dict[str, Any]]:
        self.payloads.append(payload)
        if self.error:
            raise self.error
        return self.answer


def call(route: str, body: Any) -> Any:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    request = func.HttpRequest("POST", f"{URL}/{route}", headers={"Content-Type": "application/json"}, body=raw)
    return getattr(function_app, {"questions": "ask_contract", "index": "index_contract"}[route]).build().get_user_function()(request)


def error_of(response: Any) -> tuple[int, str, str]:
    error = json.loads(response.get_body())["error"]
    return response.status_code, error["code"], error["message"]


@pytest.fixture
def qa(monkeypatch: pytest.MonkeyPatch) -> Step:
    client = Step()
    monkeypatch.setattr(function_app, "_qa_client", lambda: client)
    return client


@pytest.fixture
def search(monkeypatch: pytest.MonkeyPatch) -> Step:
    client = Step()
    monkeypatch.setattr(function_app, "_search_client", lambda: client)
    return client


# --- POST /api/contracts/questions ------------------------------------------------------------------------------

def test_a_question_step_is_answered_with_its_own_status_and_body(qa: Step) -> None:
    qa.answer = (202, {"operation": {"attempt": "1"}})

    response = call("questions", {"question": "May the Data be retained?"})

    assert response.status_code == 202 and json.loads(response.get_body()) == {"operation": {"attempt": "1"}}
    assert qa.payloads == [{"question": "May the Data be retained?"}]


@pytest.mark.parametrize("failure", [contract_qa.QaError("The question is too long."), ValueError("The history is not valid.")])
def test_a_refused_question_is_a_400_that_says_why(qa: Step, failure: Exception) -> None:
    qa.error = failure

    assert error_of(call("questions", {"question": "x"})) == (400, "QuestionRejected", str(failure))


def test_a_body_that_is_not_json_is_a_400_and_never_reaches_the_agent(qa: Step) -> None:
    status, code, _message = error_of(call("questions", b"not json"))

    assert (status, code) == (400, "QuestionRejected") and qa.payloads == []


def test_an_agent_failure_is_a_502_that_leaks_neither_the_message_nor_the_log(qa: Step, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    qa.error = RuntimeError(f"the model echoed: {CLAUSE}")

    response = call("questions", {"question": "x"})

    assert error_of(response)[:2] == (502, "AgentUnavailable")
    assert CLAUSE not in response.get_body().decode() and CLAUSE not in caplog.text
    assert "RuntimeError" in caplog.text


# --- POST /api/contracts/index ----------------------------------------------------------------------------------

def test_an_index_step_is_answered_with_its_own_status_and_body(search: Step) -> None:
    search.answer = (200, {"version": "abc", "chunks": 3})
    payload = {"contractId": "63abf974-20ea-472f-981a-8d42e67861cc", "context": "{}"}

    response = call("index", payload)

    assert response.status_code == 200 and json.loads(response.get_body()) == {"version": "abc", "chunks": 3}
    assert search.payloads == [payload]


@pytest.mark.parametrize("payload", [["not", "an", "object"], {"contractId": "x"}, {"context": 5}])
def test_a_request_without_the_document_text_is_a_400_and_never_reaches_the_index(search: Step, payload: Any) -> None:
    status, code, message = error_of(call("index", payload))

    assert (status, code) == (400, "IndexRejected") and "page-numbered document" in message
    assert search.payloads == []


@pytest.mark.parametrize("failure", [contract_qa.QaError(CLAUSE), KeyError(CLAUSE), TypeError(CLAUSE), ValueError(CLAUSE)])
def test_input_the_index_cannot_use_is_a_400_that_does_not_repeat_the_text(search: Step, caplog: pytest.LogCaptureFixture,
                                                                             failure: Exception) -> None:
    search.error = failure

    response = call("index", {"contractId": "x", "context": "{}"})

    assert error_of(response)[:2] == (400, "IndexRejected")
    assert CLAUSE not in response.get_body().decode() and CLAUSE not in caplog.text


def test_an_indexing_failure_is_a_502_that_leaks_neither_the_message_nor_the_log(search: Step, caplog: pytest.LogCaptureFixture) -> None:
    search.error = ConnectionError(f"upload failed for: {CLAUSE}")

    response = call("index", {"contractId": "x", "context": "{}"})

    assert error_of(response)[:2] == (502, "IndexUnavailable")
    assert CLAUSE not in response.get_body().decode() and CLAUSE not in caplog.text
    assert "ConnectionError" in caplog.text


# --- the clients the routes use ---------------------------------------------------------------------------------

TOKEN = object()


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Fakes for azure.identity, azure.ai.projects, azure.search.documents and openai that record how they were called. The factories import
    them when they run, and the real packages are large; they are never reached."""
    seen: dict[str, Any] = {}

    class Credential:
        def __init__(self, **kwargs: Any) -> None:
            seen["credential"] = kwargs
            self.client_id = kwargs.get("client_id")

    class Project:
        def __init__(self, **kwargs: Any) -> None:
            seen["project"] = kwargs

        def get_openai_client(self) -> Any:
            return SimpleNamespace(with_options=lambda **options: SimpleNamespace(options=options))

    class Search:
        def __init__(self, endpoint: str, index: str, credential: Any, **options: Any) -> None:
            seen["search"] = (endpoint, index, credential, options)

    class Embeddings:
        def __init__(self, **kwargs: Any) -> None:
            seen["embeddings"] = kwargs

    def token_provider(credential: Any, scope: str) -> object:
        seen["scope"] = scope
        return TOKEN

    modules = {"azure.identity": {"ManagedIdentityCredential": Credential, "get_bearer_token_provider": token_provider},
               "azure.ai.projects": {"AIProjectClient": Project},
               "azure.search.documents": {"SearchClient": Search},
               "openai": {"AzureOpenAI": Embeddings}}
    for name, attributes in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    return seen


@pytest.fixture
def fresh_clients(monkeypatch: pytest.MonkeyPatch, sdk: dict[str, Any]) -> Iterator[None]:
    cached = (function_app._qa_client, function_app._search_client)  # a test may replace the names; these are the caches
    for name in ("FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_QA_AGENT", "AZURE_CLIENT_ID", "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_INDEX",
                 "EMBEDDING_ENDPOINT", "EMBEDDING_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for client in cached:
        client.cache_clear()
    yield
    for client in cached:
        client.cache_clear()


def test_the_agent_client_is_not_built_until_the_agent_is_configured(fresh_clients: None) -> None:
    with pytest.raises(ValueError, match="agent has not been configured"):
        function_app._qa_client()


def test_the_agent_client_uses_the_functions_managed_identity_and_is_built_once(
        monkeypatch: pytest.MonkeyPatch, fresh_clients: None, sdk: dict[str, Any]) -> None:
    sentinel = Step()
    monkeypatch.setattr(function_app, "_search_client", lambda: sentinel)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://foundry.example.test/api/projects/p")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-1")

    client = function_app._qa_client()

    assert isinstance(client, contract_qa.Client) and client.agent == "contract-questions" and client.search is sentinel
    assert sdk["credential"] == {"client_id": "client-1"}
    assert sdk["project"]["endpoint"] == "https://foundry.example.test/api/projects/p"
    assert function_app._qa_client() is client


@pytest.mark.parametrize("missing", ["AZURE_SEARCH_ENDPOINT", "EMBEDDING_ENDPOINT"])
def test_the_search_client_needs_both_the_index_and_the_embedding_endpoint(monkeypatch: pytest.MonkeyPatch, fresh_clients: None,
                                                                          missing: str) -> None:
    settings = {"AZURE_SEARCH_ENDPOINT": "https://search.example.test", "EMBEDDING_ENDPOINT": "https://embed.example.test"}
    for name, value in settings.items():
        if name != missing:
            monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match="search has not been configured"):
        function_app._search_client()


def test_the_search_client_makes_short_calls_without_sdk_retries_and_is_built_once(
        monkeypatch: pytest.MonkeyPatch, fresh_clients: None, sdk: dict[str, Any]) -> None:
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://search.example.test")
    monkeypatch.setenv("EMBEDDING_ENDPOINT", "https://embed.example.test")

    client = function_app._search_client()

    assert isinstance(client, contract_search.Client) and client.model == "text-embedding-3-small"
    endpoint, index, credential, options = sdk["search"]
    assert (endpoint, index, credential.client_id) == ("https://search.example.test", "contract-chunks", None)
    assert options["retry_total"] == 0 and sdk["embeddings"]["max_retries"] == 0
    assert sdk["embeddings"]["azure_endpoint"] == "https://embed.example.test"
    assert sdk["embeddings"]["azure_ad_token_provider"] is TOKEN and sdk["scope"] == function_app.SCOPE
    assert function_app._search_client() is client
