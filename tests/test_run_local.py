"""Offline tests for scripts/run-local.py: fakes stand in for Content Understanding, the deployed API and Azure."""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
for folder in ("function", "analyzer"):
    sys.path.insert(0, str(ROOT / folder))

import cu_client  # noqa: E402
import deploy_analyzer  # noqa: E402
import mapping  # noqa: E402

_spec = importlib.util.spec_from_file_location("run_local", SCRIPTS / "run-local.py")
run_local = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = run_local
_spec.loader.exec_module(run_local)

FIXTURE = ROOT / "tests" / "fixtures" / "cu_result_sow.json"
OPERATION = "0f8fad5b-d9cb-469f-a165-70867728950e"
TENANT = "11111111-2222-3333-4444-555555555555"
SUBSCRIPTION = "66666666-7777-8888-9999-000000000000"
BASE = "https://func-test.azurewebsites.net"
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
KEY = "s3cr3t-function-key"
FOUND_AT_DEFAULT = 13


@pytest.fixture(scope="module")
def operation_body() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def pauses(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Polling never really sleeps. The list holds each pause it asked for."""
    asked: list[float] = []
    monkeypatch.setattr(run_local, "_sleep", asked.append)
    return asked


def use_settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    values = {"CONTRACT_DATA_MODE": "real", **extra}
    monkeypatch.setattr(run_local, "load_settings", lambda environ=None: values)


def write_pdf(path: Path) -> Path:
    path.write_bytes(PDF)
    return path


def reply(status: int = 200, body: Any = None, **headers: str) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    response.headers.update({name.replace("_", "-"): value for name, value in headers.items()})
    return response


def operation(status: str, body: dict[str, Any] | None = None, retry_after: int = 5, error: str = "") -> cu_client.Operation:
    return cu_client.Operation(OPERATION, status, {"status": status} if body is None else body, retry_after, error)


class FakeClient:
    """cu_client.Client with scripted polls: each step is an Operation, or an exception to raise."""

    def __init__(self, *polls: cu_client.Operation | Exception) -> None:
        self.polls = list(polls)
        self.submitted: list[bytes] = []
        self.polled = 0

    def submit(self, pdf: bytes) -> str:
        self.submitted.append(pdf)
        return OPERATION

    def poll(self, operation_id: str) -> cu_client.Operation:
        assert operation_id == OPERATION
        self.polled += 1
        step = self.polls.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class FakeSession:
    def __init__(self, *replies: requests.Response | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        return self._answer({"method": method, "url": url, **kwargs})

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self._answer({"method": "POST", "url": url, **kwargs})

    def _answer(self, call: dict[str, Any]) -> requests.Response:
        self.calls.append(call)
        answer = self.replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


# --- a saved result, offline --------------------------------------------------------------------------------------

def test_a_saved_result_is_mapped_and_shown_without_any_service(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                                operation_body: dict[str, Any]) -> None:
    out = tmp_path / "findings.json"

    assert run_local.main(["--result", str(FIXTURE), "--out", str(out)]) == 0

    assert json.loads(out.read_text(encoding="utf-8")) == mapping.map_result(operation_body, mapping.load_checklist())
    shown = capsys.readouterr().out
    assert f"Found {FOUND_AT_DEFAULT} of 20 (65.0%)" in shown
    assert "Bluepine Health Data, Inc." in shown and "effective 2025-01-15" in shown and "expires 2028-01-14" in shown
    assert "Prohibited" in shown and "usage:" in shown


def test_a_stricter_threshold_changes_the_outcome(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_local.main(["--result", str(FIXTURE), "--high-conf", "0.95"]) == 0
    assert "Found 4 of 20 (20.0%)" in capsys.readouterr().out


@pytest.mark.parametrize(("content", "message"), [
    (None, "cannot read"),
    ("[]", "not a Content Understanding result"),
    ("{not json", "cannot read"),
    ('{"status": "Succeeded", "result": {"contents": [{"fields": {}}]}}', "no fields"),
    ('{"contract": {}, "findings": [], "raw": {}}', "already mapped"),
])
def test_a_result_that_cannot_be_mapped_is_one_clear_line(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                                         content: str | None, message: str) -> None:
    path = tmp_path / "result.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")

    assert run_local.main(["--result", str(path)]) == 1

    captured = capsys.readouterr()
    assert captured.out == "" and message in captured.err and "Traceback" not in captured.err


@pytest.mark.parametrize("argv", [
    [],
    ["a.pdf", "--result", "b.json"],
    ["--result", "b.json", "--via", "direct"],
    ["a.pdf", "--via", "function", "--high-conf", "0.9"],
    ["a.pdf", "--high-conf", "0"],
    ["a.pdf", "--high-conf", "1.5"],
    ["a.pdf", "--high-conf", "nan"],
    ["a.pdf", "--high-conf", "abc"],
    ["a.pdf", "--via", "carrier-pigeon"],
])
def test_bad_arguments_are_a_usage_error(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as stop:
        run_local.parse_args(argv)
    assert stop.value.code == 2


def test_text_is_collapsed_and_clipped() -> None:
    assert run_local.clip("a  b\n c", 10) == "a b c"
    assert run_local.clip("x" * 100, 10) == "x" * 7 + "..."
    assert run_local.clip(None, 10) == ""


# --- direct: Content Understanding ------------------------------------------------------------------------------------

def test_a_direct_run_waits_for_the_result_and_saves_both_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                capsys: pytest.CaptureFixture[str],
                                                                operation_body: dict[str, Any], pauses: list[float]) -> None:
    use_settings(monkeypatch)
    client = FakeClient(operation("Running", retry_after=1), operation("Running", retry_after=30),
                        operation("Succeeded", operation_body))
    monkeypatch.setattr(run_local, "connect_direct", lambda _settings: client)
    out = tmp_path / "results" / "bluepine.json"

    assert run_local.main([str(write_pdf(tmp_path / "bluepine.pdf")), "--out", str(out)]) == 0

    assert client.submitted == [PDF] and pauses == [2.0, 15.0]  # Retry-After is kept between the floor and ceiling
    assert json.loads(out.with_name("bluepine.operation.json").read_text(encoding="utf-8")) == operation_body
    assert json.loads(out.read_text(encoding="utf-8"))["contract"]["foundCount"] == FOUND_AT_DEFAULT
    captured = capsys.readouterr()
    assert f"Found {FOUND_AT_DEFAULT} of 20" in captured.out
    assert f"started {OPERATION}" in captured.err and "bluepine.operation.json" in captured.err


def test_a_failed_analysis_says_why_and_saves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    use_settings(monkeypatch)
    monkeypatch.setattr(run_local, "connect_direct",
                        lambda _settings: FakeClient(operation("Failed", error="InvalidContent - not a valid document")))
    out = tmp_path / "failed.json"

    assert run_local.main([str(write_pdf(tmp_path / "x.pdf")), "--out", str(out)]) == 1

    assert "the analysis failed: InvalidContent - not a valid document" in capsys.readouterr().err
    assert not list(tmp_path.glob("failed*"))


def test_the_service_result_is_kept_when_the_mapping_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                           capsys: pytest.CaptureFixture[str]) -> None:
    use_settings(monkeypatch)
    broken = {"status": "Succeeded", "result": {"contents": [{"fields": {}}]}}
    monkeypatch.setattr(run_local, "connect_direct", lambda _settings: FakeClient(operation("Succeeded", broken)))
    out = tmp_path / "broken.json"

    assert run_local.main([str(write_pdf(tmp_path / "x.pdf")), "--out", str(out)]) == 1

    assert json.loads(out.with_name("broken.operation.json").read_text(encoding="utf-8")) == broken
    assert not out.exists() and "no fields" in capsys.readouterr().err


def test_throttling_is_retried_a_few_times_then_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str], pauses: list[float],
                                                         operation_body: dict[str, Any]) -> None:
    use_settings(monkeypatch)
    once = FakeClient(cu_client.CuError("busy", status=429, retry_after=7), operation("Succeeded", operation_body))
    monkeypatch.setattr(run_local, "connect_direct", lambda _settings: once)
    assert run_local.main([str(write_pdf(tmp_path / "a.pdf")), "--out", str(tmp_path / "a.json")]) == 0
    assert pauses == [7.0]

    pauses.clear()
    always = FakeClient(*[cu_client.CuError("down", status=503)] * 6)
    monkeypatch.setattr(run_local, "connect_direct", lambda _settings: always)
    assert run_local.main([str(write_pdf(tmp_path / "b.pdf")), "--out", str(tmp_path / "b.json")]) == 1
    assert len(pauses) == run_local.MAX_POLL_RETRIES and always.polled == run_local.MAX_POLL_RETRIES + 1
    assert "down" in capsys.readouterr().err


@pytest.mark.parametrize("failure", [
    cu_client.CuError("denied", status=403),
    cu_client.CuError("no token", code="NoToken"),
    cu_client.CuError("bad setting", code="Misconfigured"),
])
def test_other_failures_are_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pauses: list[float],
                                        capsys: pytest.CaptureFixture[str], failure: cu_client.CuError) -> None:
    use_settings(monkeypatch)
    client = FakeClient(failure)
    monkeypatch.setattr(run_local, "connect_direct", lambda _settings: client)

    assert run_local.main([str(write_pdf(tmp_path / "x.pdf")), "--out", str(tmp_path / "x.json")]) == 1

    assert client.polled == 1 and pauses == [] and str(failure) in capsys.readouterr().err


def test_it_gives_up_when_the_analysis_never_finishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    use_settings(monkeypatch)
    clock = iter([0.0, 1.0, run_local.WAIT_SECONDS + 100])
    monkeypatch.setattr(run_local, "_now", lambda: next(clock))
    monkeypatch.setattr(run_local, "connect_direct",
                        lambda _settings: FakeClient(operation("Running"), operation("Running")))

    assert run_local.main([str(write_pdf(tmp_path / "x.pdf")), "--out", str(tmp_path / "x.json")]) == 1

    assert "did not finish within 600 s" in capsys.readouterr().err


def test_the_direct_client_is_built_from_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    class Signed:
        account = "admin@contoso.example"

        def __init__(self, tenant: str, account: str | None) -> None:
            self.args = (tenant, account)

        def __call__(self) -> str:
            return "tok"

    monkeypatch.setattr(deploy_analyzer, "CliToken", Signed)

    client = run_local.connect_direct({"TENANT_ID": TENANT, "CU_ENDPOINT": "https://vz.services.ai.azure.com/",
                                       "CU_ANALYZER_ID": "other", "CU_API_VERSION": "2026-01-01"})

    assert (client.endpoint, client.analyzer_id, client.api_version) == ("https://vz.services.ai.azure.com", "other", "2026-01-01")
    assert client.token.args == (TENANT, None) and client.token() == "tok"


def test_a_wrong_sign_in_is_reported_with_its_full_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    class Wrong:
        def __init__(self, *_args: Any) -> None:
            pass

        def __call__(self) -> str:
            raise deploy_analyzer.DeployError("signed in as corp@example.com, which is not in the project tenant")

    monkeypatch.setattr(deploy_analyzer, "CliToken", Wrong)

    with pytest.raises(run_local.RunError, match="not in the project tenant"):
        run_local.connect_direct({"TENANT_ID": TENANT})
    with pytest.raises(run_local.RunError, match="TENANT_ID"):
        run_local.connect_direct({})


# --- function: the deployed API ---------------------------------------------------------------------------------------

def test_the_api_is_called_with_the_key_and_polled_by_operation_id(pauses: list[float],
                                                                   operation_body: dict[str, Any]) -> None:
    payload = mapping.map_result(operation_body, mapping.load_checklist())
    session = FakeSession(
        reply(202, {"operationId": OPERATION, "status": "Running"}, Location="https://evil.example/steal"),
        reply(202, {"operationId": OPERATION, "status": "Running"}, Retry_After="3"),
        reply(200, payload),
    )

    assert run_local.analyze_via_api(run_local.Api(BASE, KEY, session), PDF) == payload

    assert [(call["method"], call["url"]) for call in session.calls] == [
        ("POST", f"{BASE}/api/contracts/analyze"),
        ("GET", f"{BASE}/api/contracts/analyze/{OPERATION}"),
        ("GET", f"{BASE}/api/contracts/analyze/{OPERATION}"),
    ]
    assert all(call["headers"]["x-functions-key"] == KEY and call["allow_redirects"] is False for call in session.calls)
    assert {urlparse(call["url"]).hostname for call in session.calls} == {"func-test.azurewebsites.net"}
    assert session.calls[0]["data"] == PDF and session.calls[0]["headers"]["Content-Type"] == "application/pdf"
    assert pauses == [3.0]


def test_a_function_run_saves_the_payload_and_never_shows_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                  capsys: pytest.CaptureFixture[str],
                                                                  operation_body: dict[str, Any]) -> None:
    use_settings(monkeypatch)
    payload = mapping.map_result(operation_body, mapping.load_checklist())
    api = run_local.Api(BASE, KEY, FakeSession(reply(202, {"operationId": OPERATION}), reply(200, payload)))
    monkeypatch.setattr(run_local, "connect_function", lambda _settings: api)
    out = tmp_path / "api.json"

    assert run_local.main([str(write_pdf(tmp_path / "x.pdf")), "--via", "function", "--out", str(out)]) == 0

    assert json.loads(out.read_text(encoding="utf-8")) == payload
    assert not out.with_name("api.operation.json").exists()
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err + out.read_text(encoding="utf-8")


def test_a_poll_that_hits_a_brief_outage_is_retried(pauses: list[float], operation_body: dict[str, Any]) -> None:
    payload = mapping.map_result(operation_body, mapping.load_checklist())
    session = FakeSession(reply(202, {"operationId": OPERATION}), reply(503, Retry_After="4"), reply(200, payload))

    assert run_local.analyze_via_api(run_local.Api(BASE, KEY, session), PDF) == payload
    assert pauses == [4.0]


@pytest.mark.parametrize(("answer", "message"), [
    (reply(401), "HTTP 401"),
    (reply(413, {"error": {"code": "FileTooLarge", "message": "The PDF is over 32 MB."}}),
     "HTTP 413 FileTooLarge: The PDF is over 32 MB."),
    (reply(502, {"error": {"code": "UpstreamForbidden", "message": "Content Understanding refused the call."}}),
     "UpstreamForbidden: Content Understanding refused the call."),
    (reply(500, b"<html>" + b"boom " * 500), "HTTP 500: <html>"),
    (reply(302, Location="https://evil.example/"), "HTTP 302"),
])
def test_api_failures_are_one_bounded_line(answer: requests.Response, message: str) -> None:
    session = FakeSession(answer)

    with pytest.raises(cu_client.CuError) as caught:
        run_local.Api(BASE, KEY, session).submit(PDF)

    assert message in str(caught.value) and len(str(caught.value)) < 400
    assert len(session.calls) == 1  # a redirect is never followed


def test_a_network_failure_does_not_leak_the_url_or_key() -> None:
    session = FakeSession(requests.ConnectionError(f"HTTPSConnectionPool(host='func-test'): {KEY}"))

    with pytest.raises(cu_client.CuError) as caught:
        run_local.Api(BASE, KEY, session).submit(PDF)

    assert str(caught.value) == "no reply from the API (ConnectionError)" and caught.value.status is None


@pytest.mark.parametrize("reply_", [reply(200, {"operationId": OPERATION}), reply(202, {"operationId": "../x"}),
                                    reply(202, {"status": "Running"}), reply(202, b"not json"), reply(202, ["x"])])
def test_a_submit_reply_without_an_operation_id_is_rejected(reply_: requests.Response) -> None:
    with pytest.raises(cu_client.CuError, match="UnexpectedReply|operation id|not a JSON object") as caught:
        run_local.Api(BASE, KEY, FakeSession(reply_)).submit(PDF)
    assert caught.value.code == "UnexpectedReply"


def test_a_finished_poll_without_findings_is_rejected() -> None:
    with pytest.raises(cu_client.CuError) as caught:
        run_local.Api(BASE, KEY, FakeSession(reply(200, {"contract": {}}))).poll(OPERATION)
    assert caught.value.code == "UnexpectedReply"


@pytest.mark.parametrize("base", ["http://f.azurewebsites.net", "https://evil.example.com",
                                  "https://f.azurewebsites.net.evil.com", "f.azurewebsites.net", ""])
def test_the_key_is_only_ever_sent_to_an_azurewebsites_host(base: str) -> None:
    with pytest.raises(run_local.RunError, match="azurewebsites.net"):
        run_local.Api(base, KEY)


def test_connect_function_checks_the_address_before_reading_any_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_local, "function_key", lambda *_a, **_k: pytest.fail("the key was read"))

    with pytest.raises(run_local.RunError, match="azurewebsites.net"):
        run_local.connect_function({"SERVICE_API_URI": "https://evil.example.com"})
    with pytest.raises(run_local.RunError, match="SERVICE_API_URI"):
        run_local.connect_function({})


# --- the function key ---------------------------------------------------------------------------------------------------

SETTINGS = {"TENANT_ID": TENANT, "AZURE_ACCOUNT": "admin@contoso.example", "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
            "AZURE_RESOURCE_GROUP": "rg-test", "AZURE_FUNCTION_NAME": "func-test"}


def jwt(**claims: str) -> str:
    def part(data: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none'})}.{part(claims)}.signature"


class FakeCredential:
    def __init__(self, token: str | Exception) -> None:
        self.token, self.scopes = token, []

    def get_token(self, scope: str) -> SimpleNamespace:
        self.scopes.append(scope)
        if isinstance(self.token, Exception):
            raise self.token
        return SimpleNamespace(token=self.token)


def admin_token() -> str:
    return jwt(tid=TENANT, upn="Admin@Contoso.example")


def test_the_function_key_is_read_through_arm_as_the_expected_admin() -> None:
    credential = FakeCredential(admin_token())
    arm = FakeSession(reply(200, {"functionKeys": {"default": KEY}, "masterKey": "master-secret"}))

    assert run_local.function_key(SETTINGS, credential=credential, session=arm) == KEY

    [call] = arm.calls
    assert call["url"] == (f"https://management.azure.com/subscriptions/{SUBSCRIPTION}/resourceGroups/rg-test"
                           "/providers/Microsoft.Web/sites/func-test/host/default/listkeys")
    assert call["params"] == {"api-version": "2023-12-01"} and call["allow_redirects"] is False
    assert call["headers"]["Authorization"].startswith("Bearer ") and credential.scopes == [run_local.ARM_SCOPE]


@pytest.mark.parametrize(("token", "message"), [
    (jwt(tid="99999999-9999-9999-9999-999999999999", upn="admin@contoso.example"), "not in the project tenant"),
    (jwt(tid=TENANT, upn="corp@example.com"), "AZURE_ACCOUNT expects admin@contoso.example"),
    (RuntimeError("Please run 'az login' to set up an account."), "no Azure Resource Manager token"),
])
def test_the_wrong_sign_in_never_reaches_arm(token: str | Exception, message: str) -> None:
    arm = FakeSession()

    with pytest.raises(run_local.RunError, match=message):
        run_local.function_key(SETTINGS, credential=FakeCredential(token), session=arm)

    assert arm.calls == []


@pytest.mark.parametrize(("answer", "message"), [
    (reply(403), r"HTTP 403\). admin@contoso.example needs Contributor"),
    (reply(200, {"functionKeys": {}}), "no default function key"),
    (reply(200, {"masterKey": "m"}), "no default function key"),
    (reply(200, b"not json"), "no default function key"),
    (requests.ConnectionError("down"), "no reply from Azure Resource Manager"),
])
def test_a_key_that_cannot_be_read_says_what_to_fix(answer: requests.Response | Exception, message: str) -> None:
    arm = FakeSession(answer)
    credential = FakeCredential(jwt(tid=TENANT, upn="admin@contoso.example"))

    with pytest.raises(run_local.RunError, match=message):
        run_local.function_key(SETTINGS, credential=credential, session=arm)


@pytest.mark.parametrize("change", [
    {"AZURE_RESOURCE_GROUP": ""}, {"AZURE_RESOURCE_GROUP": "rg/../other"}, {"AZURE_FUNCTION_NAME": "func/../x"},
    {"AZURE_FUNCTION_NAME": ""}, {"AZURE_SUBSCRIPTION_ID": "not-a-guid"}, {"TENANT_ID": ""},
])
def test_the_names_in_the_arm_url_are_validated(change: dict[str, str]) -> None:
    arm = FakeSession()

    with pytest.raises(run_local.RunError, match="must be set"):
        run_local.function_key({**SETTINGS, **change}, credential=FakeCredential(admin_token()), session=arm)

    assert arm.calls == []


# --- settings ---------------------------------------------------------------------------------------------------------

def test_azd_values_come_from_the_default_environment(tmp_path: Path) -> None:
    azure = tmp_path / ".azure"
    (azure / "dev").mkdir(parents=True)
    (azure / "config.json").write_text('{"defaultEnvironment": "dev"}', encoding="utf-8")
    (azure / "dev" / ".env").write_text('A="1"\nB=two\n# C=3\n\nnot a pair\n', encoding="utf-8")

    assert run_local.azd_values(tmp_path) == {"A": "1", "B": "two"}


@pytest.mark.parametrize("config", [None, "{not json", '{"defaultEnvironment": 7}', '{"defaultEnvironment": "../x"}',
                                    '{"defaultEnvironment": "missing"}', "[]"])
def test_azd_values_are_empty_when_azd_has_not_provisioned(tmp_path: Path, config: str | None) -> None:
    (tmp_path / ".azure").mkdir()
    if config is not None:
        (tmp_path / ".azure" / "config.json").write_text(config, encoding="utf-8")

    assert run_local.azd_values(tmp_path) == {}


def test_the_environment_overrides_azd_and_blank_values_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_local, "azd_values", lambda: {"A": "azd", "B": "azd"})

    assert run_local.load_settings({"B": "env", "C": "", "D": "new"}) == {"A": "azd", "B": "env", "D": "new"}


# --- the synthetic-only guard --------------------------------------------------------------------------------------------

def make_pdf(path: Path, text: str, subject: str | None = None) -> Path:
    canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    pytest.importorskip("pypdf")
    page = canvas.Canvas(str(path))
    if subject:
        page.setSubject(subject)
    page.drawString(72, 720, text)
    page.save()
    return path


@pytest.mark.parametrize(("text", "subject"), [
    ("SYNTHETIC SAMPLE - FICTIONAL PARTIES - NOT A REAL AGREEMENT", None),
    ("a scan with no text layer", "SYNTHETIC SAMPLE - FICTIONAL PARTIES"),
])
def test_a_marked_pdf_is_accepted_in_synthetic_mode(tmp_path: Path, text: str, subject: str | None) -> None:
    run_local.confirm_synthetic(make_pdf(tmp_path / "ok.pdf", text, subject), "synthetic")


def test_an_unmarked_pdf_is_refused_before_anything_is_sent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                            capsys: pytest.CaptureFixture[str]) -> None:
    use_settings(monkeypatch, CONTRACT_DATA_MODE="synthetic")
    monkeypatch.setattr(run_local, "connect_direct", lambda _settings: pytest.fail("signed in for an unmarked PDF"))
    monkeypatch.setattr(run_local, "connect_function", lambda _settings: pytest.fail("signed in for an unmarked PDF"))
    pdf = make_pdf(tmp_path / "real.pdf", "MASTER SERVICES AGREEMENT between two real companies")

    for via in ("direct", "function"):
        assert run_local.main([str(pdf), "--via", via]) == 1

    assert "not marked 'SYNTHETIC SAMPLE', so it was not sent" in capsys.readouterr().err


def test_real_mode_turns_the_check_off_and_says_so(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_local.confirm_synthetic(make_pdf(tmp_path / "real.pdf", "any contract"), "real")

    assert "check is off" in capsys.readouterr().err


def test_an_unknown_mode_and_a_damaged_pdf_are_refused(tmp_path: Path) -> None:
    pytest.importorskip("pypdf")
    damaged = tmp_path / "damaged.pdf"
    damaged.write_bytes(b"%PDF-1.7 this is not a pdf")

    with pytest.raises(run_local.RunError, match="synthetic or real"):
        run_local.confirm_synthetic(damaged, "maybe")
    with pytest.raises(run_local.RunError, match="cannot read damaged.pdf"):
        run_local.confirm_synthetic(damaged, "synthetic")


def test_only_a_pdf_is_read(tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(run_local.RunError, match="is not a PDF"):
        run_local.read_pdf(other)
    with pytest.raises(run_local.RunError, match="cannot read"):
        run_local.read_pdf(tmp_path / "missing.pdf")
