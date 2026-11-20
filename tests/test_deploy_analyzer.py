"""Offline tests for analyzer/deploy_analyzer.py: a scripted service stands in for Content Understanding."""

from __future__ import annotations

import base64
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "analyzer"))

import build_schema  # noqa: E402
import deploy_analyzer as deploy  # noqa: E402

HOST = "vz-cu.services.ai.azure.com"
ENDPOINT = f"https://{HOST}"
ANALYZER_ID = build_schema.ANALYZER_IDS["nested"]
DEFAULTS_PATH = "/contentunderstanding/defaults"
ANALYZER_PATH = f"/contentunderstanding/analyzers/{ANALYZER_ID}"
SETTINGS = deploy.Settings.from_env({"CU_COMPLETION_DEPLOYMENT": "chat-main", "CU_EMBEDDING_DEPLOYMENT": "embed-main"})


class FakeService:
    """Answers like the resource and records every call as (method, path, params, body, content type)."""

    def __init__(self, defaults: Mapping[str, str] | None = None,
                 polls: tuple[dict[str, Any], ...] = ({"status": "Running"}, {"status": "Succeeded"}),
                 operation_url: str | None = None) -> None:
        self.defaults: dict[str, str] | None = None if defaults is None else dict(defaults)
        self.polls = list(polls)
        self.operation_url = operation_url or f"{ENDPOINT}{ANALYZER_PATH}/operations/op1?api-version=2025-11-01"
        self.analyzer: dict[str, Any] | None = None
        self.calls: list[tuple[str, str, dict[str, str], Any, str | None]] = []

    def request(self, method: str, url: str, *, params: Mapping[str, str] | None = None,
                json_body: Any = None, content_type: str | None = None) -> deploy.Reply:
        path = urlparse(url).path
        self.calls.append((method, path, dict(params or {}), json_body, content_type))
        if path == DEFAULTS_PATH and method == "GET":
            if self.defaults is None:
                return deploy.Reply(400, {"x-ms-error-code": "InvalidRequest"}, {"error": {
                    "code": "InvalidRequest", "message": "Invalid request.",
                    "innererror": {"code": "DefaultsNotSet", "message": "Defaults have not yet been set."}}})
            return deploy.Reply(200, {}, {"modelDeployments": self.defaults})
        if path == DEFAULTS_PATH and method == "PATCH":
            self.defaults = {**(self.defaults or {}), **json_body["modelDeployments"]}
            return deploy.Reply(200, {}, {"modelDeployments": self.defaults})
        if path == ANALYZER_PATH and method == "PUT":
            self.analyzer = {**json_body, "status": "ready"}
            return deploy.Reply(201, {"operation-location": self.operation_url}, {})
        if "/operations/" in path:
            return deploy.Reply(200, {"retry-after": "1"}, self.polls.pop(0) if self.polls else {"status": "Running"})
        if path == ANALYZER_PATH and method == "GET":
            return deploy.Reply(200 if self.analyzer else 404, {}, self.analyzer or {"error": {"code": "NotFound"}})
        raise AssertionError(f"unexpected call {method} {path}")

    def sequence(self) -> list[tuple[str, str]]:
        return [(method, path.removeprefix("/contentunderstanding/")) for method, path, *_ in self.calls]


def client_for(service: FakeService, **kwargs: Any) -> deploy.Client:
    return deploy.Client(service, ENDPOINT, sleep=lambda _seconds: None, **kwargs)


def test_defaults_are_set_before_the_analyzer_is_created_and_polled_to_the_end() -> None:
    service, lines = FakeService(), []
    result = deploy.deploy(client_for(service), SETTINGS, "nested", log=lines.append)

    assert service.sequence() == [
        ("GET", "defaults"), ("PATCH", "defaults"), ("PUT", f"analyzers/{ANALYZER_ID}"),
        ("GET", f"analyzers/{ANALYZER_ID}/operations/op1"), ("GET", f"analyzers/{ANALYZER_ID}/operations/op1"),
        ("GET", f"analyzers/{ANALYZER_ID}")]
    patch = next(call for call in service.calls if call[0] == "PATCH")
    assert patch[4] == "application/merge-patch+json"
    assert patch[3]["modelDeployments"] == {
        "gpt-5.5": "chat-main", "prebuilt-analyzer-completion": "chat-main", "prebuilt-analyzer-completion-mini": "chat-main",
        "text-embedding-3-large": "embed-main", "prebuilt-analyzer-embedding": "embed-main"}
    put = next(call for call in service.calls if call[0] == "PUT")
    assert put[2] == {"api-version": "2025-11-01", "allowReplace": "true"}
    assert put[3] == json.loads(build_schema.OUTPUT_FILES["nested"].read_text(encoding="utf-8"))
    assert result["status"] == "ready"


def test_defaults_already_in_place_are_left_alone() -> None:
    service = FakeService(defaults=deploy.desired_defaults(SETTINGS))
    deploy.deploy(client_for(service), SETTINGS, "nested", log=lambda _line: None)
    assert "PATCH" not in [method for method, _ in service.sequence()]


def test_a_failed_operation_reports_the_service_error() -> None:
    service = FakeService(polls=({"status": "Failed", "error": {"code": "InvalidModelDeployment", "message": "No such deployment."}},))
    with pytest.raises(deploy.DeployError, match="failed: InvalidModelDeployment - No such deployment"):
        deploy.deploy(client_for(service), SETTINGS, "nested", log=lambda _line: None)


def test_polling_gives_up_after_the_timeout() -> None:
    ticks = iter(range(0, 10_000, 100))
    service = FakeService(polls=())
    client = client_for(service, clock=lambda: next(ticks), timeout=250)
    with pytest.raises(deploy.DeployError, match="still Running after 250 s"):
        client.wait(service.operation_url)


def test_the_token_is_not_sent_to_an_operation_url_on_another_host() -> None:
    service = FakeService(operation_url="https://attacker.example.com/operations/op1")
    with pytest.raises(deploy.DeployError, match="not on the resource host"):
        deploy.deploy(client_for(service), SETTINGS, "nested", log=lambda _line: None)
    assert service.sequence()[-1] == ("PUT", f"analyzers/{ANALYZER_ID}")


def test_a_new_resource_with_no_defaults_is_treated_as_having_none() -> None:
    assert client_for(FakeService()).get_defaults() == {}


def test_a_400_that_is_not_defaults_not_set_is_still_an_error() -> None:
    class Rejected:
        def request(self, *_args: Any, **_kwargs: Any) -> deploy.Reply:
            return deploy.Reply(400, {}, {"error": {"code": "InvalidRequest", "message": "Invalid request.",
                                                    "innererror": {"code": "InvalidApiVersion", "message": "Bad version."}}})

    with pytest.raises(deploy.DeployError, match=r"HTTP 400: InvalidRequest - Invalid request\. \(InvalidApiVersion: Bad version\.\)"):
        deploy.Client(Rejected(), ENDPOINT).get_defaults()


def test_a_403_says_which_role_is_missing() -> None:
    class Denied:
        def request(self, *_args: Any, **_kwargs: Any) -> deploy.Reply:
            return deploy.Reply(403, {"x-ms-error-code": "AuthorizationFailed"}, None)

    with pytest.raises(deploy.DeployError, match="HTTP 403: AuthorizationFailed.*Content Understanding Contributor"):
        deploy.Client(Denied(), ENDPOINT).get_defaults()


@pytest.mark.parametrize("endpoint", [
    "http://vz-cu.services.ai.azure.com", "https://example.com", f"https://{HOST}.attacker.example.com", "", "vz-cu"])
def test_only_azure_ai_endpoints_are_accepted(endpoint: str) -> None:
    with pytest.raises(deploy.DeployError, match="CU_ENDPOINT must be an https Azure AI endpoint"):
        deploy.normalize_endpoint(endpoint)


def test_an_endpoint_is_reduced_to_its_https_origin() -> None:
    assert deploy.normalize_endpoint(f"https://user:secret@{HOST.upper()}:8443/some/path?x=1") == ENDPOINT


def test_status_tells_a_current_analyzer_from_a_stale_one() -> None:
    service, lines = FakeService(), []
    deploy.deploy(client_for(service), SETTINGS, "nested", log=lambda _line: None)
    assert deploy.status(client_for(service), SETTINGS, "nested", log=lines.append) is True

    service.analyzer["tags"]["definitionHash"] = "000000000000"
    assert deploy.status(client_for(service), SETTINGS, "nested", log=lines.append) is False
    assert any("STALE" in line for line in lines)


def test_status_reports_a_missing_analyzer_without_changing_anything() -> None:
    service, lines = FakeService(defaults=deploy.desired_defaults(SETTINGS)), []
    assert deploy.status(client_for(service), SETTINGS, "nested", log=lines.append) is False
    assert {method for method, _ in service.sequence()} == {"GET"}
    assert any("not deployed" in line for line in lines)


def jwt(**claims: str) -> str:
    return "h." + base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode() + ".s"


class FakeCredential:
    def __init__(self, token: str) -> None:
        self.token, self.calls = token, 0

    def get_token(self, scope: str) -> Any:
        assert scope == deploy.SCOPE
        self.calls += 1
        return SimpleNamespace(token=self.token, expires_on=10_000)


def test_the_token_is_cached_and_the_account_is_reported() -> None:
    credential = FakeCredential(jwt(tid="tenant-1", upn="admin@demo.onmicrosoft.com"))
    token = deploy.CliToken("tenant-1", "ADMIN@demo.onmicrosoft.com", credential, clock=lambda: 0)
    assert token() == token() == credential.token
    assert credential.calls == 1
    assert token.account == "admin@demo.onmicrosoft.com"


@pytest.mark.parametrize(("claims", "expected"), [
    ({"tid": "corp-tenant", "upn": "someone@microsoft.com"}, "not in the project tenant"),
    ({"tid": "tenant-1", "upn": "other@demo.onmicrosoft.com"}, "AZURE_ACCOUNT expects"),
])
def test_the_wrong_account_is_refused_before_any_call(claims: dict[str, str], expected: str) -> None:
    token = deploy.CliToken("tenant-1", "admin@demo.onmicrosoft.com", FakeCredential(jwt(**claims)), clock=lambda: 0)
    with pytest.raises(deploy.DeployError, match=expected):
        token()


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command line with no .env, no CU settings, and no way to reach the network or sign in."""
    import auth

    monkeypatch.setattr(auth, "load_env", lambda: None)
    for name in ("CU_ENDPOINT", "CU_COMPLETION_MODEL", "CU_COMPLETION_DEPLOYMENT", "CU_EMBEDDING_MODEL",
                 "CU_EMBEDDING_DEPLOYMENT", "TENANT_ID", "AZURE_ACCOUNT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(requests.Session, "request", lambda *_a, **_k: pytest.fail("a network call was made"))
    monkeypatch.setattr(deploy.CliToken, "__call__", lambda *_a, **_k: pytest.fail("a sign-in was attempted"))


def test_running_with_no_flags_only_prints_the_plan(offline: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert deploy.main([]) == 0
    output = capsys.readouterr().out
    assert "Nothing was sent" in output and ANALYZER_ID in output and "PATCH" in output
    assert "CU_ENDPOINT is not set" in output


@pytest.mark.parametrize("flag", ["--status", "--apply"])
@pytest.mark.parametrize(("env", "expected"), [
    ({}, "CU_ENDPOINT is not set"),
    ({"CU_ENDPOINT": ENDPOINT}, "TENANT_ID is not set"),
    ({"CU_ENDPOINT": "https://example.com", "TENANT_ID": "t"}, "CU_ENDPOINT must be an https Azure AI endpoint"),
])
def test_a_live_run_stops_on_bad_settings_before_signing_in(offline: None, monkeypatch: pytest.MonkeyPatch,
                                                           capsys: pytest.CaptureFixture[str], flag: str,
                                                           env: dict[str, str], expected: str) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert deploy.main([flag]) == 1
    assert expected in capsys.readouterr().out
