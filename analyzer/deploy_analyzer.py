"""Deploy the checklist analyzer to the Content Understanding resource (GA API 2025-11-01).

    python analyzer/deploy_analyzer.py            show the plan; no network call and no sign-in
    python analyzer/deploy_analyzer.py --status   read-only: are the model defaults set, is the analyzer current?
    python analyzer/deploy_analyzer.py --apply    set the model defaults, then create or replace the analyzer

--layout nested|flat picks the analyzer. nested is the default; flat is the grounding fallback.

Settings come from the environment or .env (see .env.example). The resource has local auth disabled, so every
call carries the Azure CLI's Entra token and there are no keys. The signed-in account must belong to TENANT_ID
(and equal AZURE_ACCOUNT when that is set) and hold the Cognitive Services Content Understanding Contributor
role on the resource.

Order matters: the model defaults are a prerequisite of creating an analyzer, so they are set first.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import requests

import build_schema  # puts scripts/ on sys.path
import checklistlib

API_VERSION = "2025-11-01"
SCOPE = "https://cognitiveservices.azure.com/.default"
ALLOWED_HOST_SUFFIXES = (".cognitiveservices.azure.com", ".services.ai.azure.com")
MERGE_PATCH = "application/merge-patch+json"
DEFAULT_COMPLETION_MODEL = "gpt-5.5"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
POLL_TIMEOUT_SECONDS = 300.0
TOKEN_REFRESH_SECONDS = 300


class DeployError(RuntimeError):
    """A failure worth one clear line, not a stack trace."""


@dataclass(frozen=True)
class Reply:
    status: int
    headers: Mapping[str, str]
    body: Any


class Transport(Protocol):
    def request(self, method: str, url: str, *, params: Mapping[str, str] | None = None,
                json_body: Any = None, content_type: str | None = None) -> Reply: ...


@dataclass(frozen=True)
class Settings:
    endpoint: str
    completion_model: str
    completion_deployment: str
    embedding_model: str
    embedding_deployment: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Settings:
        completion = env.get("CU_COMPLETION_MODEL") or DEFAULT_COMPLETION_MODEL
        embedding = env.get("CU_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
        return cls(
            endpoint=(env.get("CU_ENDPOINT") or "").strip(),
            completion_model=completion,
            completion_deployment=env.get("CU_COMPLETION_DEPLOYMENT") or completion,
            embedding_model=embedding,
            embedding_deployment=env.get("CU_EMBEDDING_DEPLOYMENT") or embedding,
        )


def desired_defaults(settings: Settings) -> dict[str, str]:
    """Each model name and alias mapped to a Foundry deployment. The mini alias shares the completion
    deployment, so a prebuilt analyzer that uses it works instead of failing for want of a mapping."""
    return {
        settings.completion_model: settings.completion_deployment,
        settings.embedding_model: settings.embedding_deployment,
        "prebuilt-analyzer-completion": settings.completion_deployment,
        "prebuilt-analyzer-completion-mini": settings.completion_deployment,
        "prebuilt-analyzer-embedding": settings.embedding_deployment,
    }


def normalize_endpoint(endpoint: str) -> str:
    """The https origin of the endpoint. The Entra token is only ever sent to Azure AI hosts."""
    parts = urlparse(endpoint)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host.endswith(ALLOWED_HOST_SUFFIXES):
        raise DeployError("CU_ENDPOINT must be an https Azure AI endpoint ending in "
                          f"{' or '.join(ALLOWED_HOST_SUFFIXES)}, for example https://<resource>.services.ai.azure.com")
    return f"https://{host}"


def load_analyzer(layout: str) -> tuple[str, dict[str, Any]]:
    """The committed analyzer file, after proving it matches checklist.json and the service limits."""
    analyzer_id, path = build_schema.ANALYZER_IDS[layout], build_schema.OUTPUT_FILES[layout]
    if not path.exists():
        raise DeployError(f"{path.name} is missing. Run: python analyzer/build_schema.py --write")
    committed = json.loads(path.read_text(encoding="utf-8"))
    if committed != build_schema.build_analyzer(checklistlib.load_checklist(), layout):
        raise DeployError(f"{path.name} is out of date with checklist.json. Run: python analyzer/build_schema.py --write")
    problems = build_schema.validate_analyzer(committed, analyzer_id)
    if problems:
        raise DeployError(f"{path.name} is invalid: " + "; ".join(problems))
    return analyzer_id, committed


def token_claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def check_identity(claims: Mapping[str, Any], tenant_id: str, expected_account: str | None) -> str:
    """The signed-in account, after proving it is the right tenant and, when named, the right account."""
    account = claims.get("upn") or claims.get("preferred_username") or claims.get("unique_name") or "an unknown account"
    if claims.get("tid") != tenant_id:
        raise DeployError(f"signed in as {account}, which is not in the project tenant. "
                          f"Run: az login --tenant {tenant_id}, and use the admin account")
    if expected_account and account.lower() != expected_account.lower():
        raise DeployError(f"signed in as {account}, but AZURE_ACCOUNT expects {expected_account}")
    return account


class CliToken:
    """Entra token from the signed-in Azure CLI, checked once for tenant and account."""

    def __init__(self, tenant_id: str, expected_account: str | None = None, credential: Any = None,
                 clock: Callable[[], float] = time.time) -> None:
        self.tenant_id = tenant_id
        self.expected_account = expected_account
        self.account: str | None = None
        self._credential = credential
        self._clock = clock
        self._token: Any = None

    def __call__(self) -> str:
        if self._token is None or self._token.expires_on - self._clock() < TOKEN_REFRESH_SECONDS:
            if self._credential is None:
                from azure.identity import AzureCliCredential
                self._credential = AzureCliCredential(tenant_id=self.tenant_id)
            try:
                self._token = self._credential.get_token(SCOPE)
            except Exception as exc:  # azure-identity raises several types; the message is what helps
                reason = (str(exc).splitlines() or [type(exc).__name__])[0][:200]
                raise DeployError(f"no token from the Azure CLI ({reason}). Run: az login --tenant {self.tenant_id}") from exc
            if self.account is None:
                self.account = check_identity(token_claims(self._token.token), self.tenant_id, self.expected_account)
        return self._token.token


class Http:
    """The real transport: requests, with the bearer token, no redirects and no retries."""

    def __init__(self, token: Callable[[], str], timeout: float = 60.0, session: requests.Session | None = None) -> None:
        self.token = token
        self.timeout = timeout
        self.session = session or requests.Session()

    def request(self, method: str, url: str, *, params: Mapping[str, str] | None = None,
                json_body: Any = None, content_type: str | None = None) -> Reply:
        headers = {"Authorization": "Bearer " + self.token(), "Accept": "application/json"}
        data = None
        if json_body is not None:
            headers["Content-Type"] = content_type or "application/json"
            data = json.dumps(json_body)
        try:
            response = self.session.request(method, url, params=params, data=data, headers=headers,
                                            timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            raise DeployError(f"{method} {urlparse(url).path} could not reach the service ({type(exc).__name__})") from exc
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = None
        return Reply(response.status_code, response.headers, body)


class Client:
    """The few Content Understanding calls a deployment needs."""

    def __init__(self, http: Transport, endpoint: str, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, timeout: float = POLL_TIMEOUT_SECONDS) -> None:
        self.http = http
        self.endpoint = endpoint
        self.sleep = sleep
        self.clock = clock
        self.timeout = timeout

    def get_defaults(self) -> dict[str, str]:
        reply = self._call("read the model defaults", "GET", self._url("defaults"), allow=(400,))
        if reply.status == 400:
            # A new resource answers 400 DefaultsNotSet until the first PATCH; any other 400 is a real error.
            if _inner_code(reply.body) != "DefaultsNotSet":
                raise _failure("read the model defaults", reply)
            return {}
        return dict((reply.body or {}).get("modelDeployments") or {})

    def set_defaults(self, deployments: Mapping[str, str]) -> None:
        self._call("set the model defaults", "PATCH", self._url("defaults"),
                   json_body={"modelDeployments": dict(deployments)}, content_type=MERGE_PATCH)

    def get_analyzer(self, analyzer_id: str) -> dict[str, Any] | None:
        reply = self._call(f"read analyzer {analyzer_id}", "GET", self._url(f"analyzers/{analyzer_id}"), allow=(404,))
        return None if reply.status == 404 else reply.body

    def put_analyzer(self, analyzer_id: str, body: dict[str, Any]) -> str:
        """Create or replace; returns the URL to poll."""
        reply = self._call(f"create analyzer {analyzer_id}", "PUT", self._url(f"analyzers/{analyzer_id}"),
                           params={"allowReplace": "true"}, json_body=body)
        location = reply.headers.get("operation-location")
        if not location:
            raise DeployError("the service accepted the analyzer but returned no Operation-Location to poll")
        return location

    def wait(self, operation_url: str) -> dict[str, Any]:
        target, home = urlparse(operation_url), urlparse(self.endpoint)
        if target.scheme != "https" or target.hostname != home.hostname:
            raise DeployError("the operation URL is not on the resource host, so the token is not sent to it")
        deadline = self.clock() + self.timeout
        versioned = "api-version=" not in operation_url
        while True:
            reply = self._call("poll the analyzer operation", "GET", operation_url, versioned=versioned)
            body = reply.body if isinstance(reply.body, dict) else {}
            state = body.get("status")
            if state == "Succeeded":
                return body
            if state in ("Failed", "Canceled"):
                raise DeployError(f"the analyzer operation {state.lower()}{_describe(body.get('error'))}")
            if self.clock() >= deadline:
                raise DeployError(f"the analyzer operation was still {state or 'pending'} after {self.timeout:.0f} s")
            self.sleep(_retry_after(reply))

    def _url(self, path: str) -> str:
        return f"{self.endpoint}/contentunderstanding/{path}"

    def _call(self, what: str, method: str, url: str, *, params: Mapping[str, str] | None = None,
              json_body: Any = None, content_type: str | None = None, allow: tuple[int, ...] = (),
              versioned: bool = True) -> Reply:
        query = {"api-version": API_VERSION, **(params or {})} if versioned else params
        reply = self.http.request(method, url, params=query, json_body=json_body, content_type=content_type)
        if 200 <= reply.status < 300 or reply.status in allow:
            return reply
        raise _failure(what, reply)


def _failure(what: str, reply: Reply) -> DeployError:
    error = reply.body.get("error") if isinstance(reply.body, dict) else None
    detail = _describe(error or {"code": reply.headers.get("x-ms-error-code")})
    hint = (" Sign in as the admin account, which needs the Cognitive Services Content Understanding "
            "Contributor role on the resource.") if reply.status in (401, 403) else ""
    return DeployError(f"could not {what}: HTTP {reply.status}{detail}.{hint}")


def _inner_code(body: Any) -> str | None:
    error = body.get("error") if isinstance(body, dict) else None
    inner = error.get("innererror") if isinstance(error, dict) else None
    return inner.get("code") if isinstance(inner, dict) else None


def _describe(error: Any) -> str:
    if not isinstance(error, Mapping):
        return ""
    text = " - ".join(str(part) for part in (error.get("code"), error.get("message")) if part)
    inner = error.get("innererror")
    if isinstance(inner, Mapping):
        cause = ": ".join(str(part) for part in (inner.get("code"), inner.get("message")) if part)
        if cause:
            text += f" ({cause})"
    return f": {text[:500]}" if text else ""


def _retry_after(reply: Reply) -> float:
    try:
        return min(max(float(reply.headers.get("retry-after", 2)), 1.0), 10.0)
    except (TypeError, ValueError):
        return 2.0


def defaults_gap(current: Mapping[str, str], settings: Settings) -> list[str]:
    """The model names and aliases whose deployment is missing or different."""
    return sorted(name for name, deployment in desired_defaults(settings).items() if current.get(name) != deployment)


def deploy(client: Client, settings: Settings, layout: str, log: Callable[[str], None] = print) -> dict[str, Any]:
    analyzer_id, body = load_analyzer(layout)
    gap = defaults_gap(client.get_defaults(), settings)
    if gap:
        client.set_defaults(desired_defaults(settings))
        log(f"model defaults: set {', '.join(gap)}")
    else:
        log("model defaults: already in place")
    log(f"analyzer {analyzer_id}: submitting {build_schema.field_counts(body)['total']} fields")
    client.wait(client.put_analyzer(analyzer_id, body))
    return verify(client.get_analyzer(analyzer_id), body, settings, log)


def verify(analyzer: dict[str, Any] | None, body: dict[str, Any], settings: Settings,
           log: Callable[[str], None] = print) -> dict[str, Any]:
    if analyzer is None:
        raise DeployError("the analyzer cannot be read back although the operation succeeded")
    if analyzer.get("status") != "ready":
        raise DeployError(f"the analyzer is {analyzer.get('status')!r}, expected 'ready'")
    wanted, deployed = body["tags"]["definitionHash"], (analyzer.get("tags") or {}).get("definitionHash")
    if deployed is None:
        log("WARNING: the service returned no tags, so the deployed definition cannot be compared")
    elif deployed != wanted:
        raise DeployError(f"the deployed definition ({deployed}) is not the one submitted ({wanted})")
    supported = (analyzer.get("supportedModels") or {}).get("completion")
    if supported is not None and settings.completion_model not in supported:
        log(f"WARNING: {settings.completion_model} is not among the analyzer's supported completion models {supported}")
    log(f"analyzer is ready, definition {deployed or 'unknown'}, supported completion models {supported or 'not reported'}")
    return {"status": "ready", "definitionHash": deployed, "supportedCompletion": supported}


def status(client: Client, settings: Settings, layout: str, log: Callable[[str], None] = print) -> bool:
    """Print where the resource stands; True when nothing needs deploying."""
    analyzer_id, body = load_analyzer(layout)
    gap = defaults_gap(client.get_defaults(), settings)
    log("model defaults: in place" if not gap else f"model defaults: missing or different for {', '.join(gap)}")
    analyzer = client.get_analyzer(analyzer_id)
    if analyzer is None:
        log(f"analyzer {analyzer_id}: not deployed")
        return False
    wanted, deployed = body["tags"]["definitionHash"], (analyzer.get("tags") or {}).get("definitionHash")
    current = deployed == wanted and analyzer.get("status") == "ready"
    log(f"analyzer {analyzer_id}: {analyzer.get('status')}, " + ("current" if current else
        f"STALE (deployed {deployed}, file {wanted})"))
    return current and not gap


def print_plan(settings: Settings, layout: str, log: Callable[[str], None] = print) -> None:
    analyzer_id, body = load_analyzer(layout)
    log(f"Plan for the '{layout}' layout. Nothing was sent: no network call, no sign-in.")
    log(f"  analyzer  {analyzer_id}: {build_schema.field_counts(body)['total']} fields, "
        f"definition {body['tags']['definitionHash']}")
    log(f"  endpoint  {settings.endpoint or 'CU_ENDPOINT is not set (it exists once the Foundry resource does)'}")
    log("  1. GET    /contentunderstanding/defaults")
    log("  2. PATCH  /contentunderstanding/defaults, only if a mapping is missing:")
    for name, deployment in desired_defaults(settings).items():
        log(f"       {name} -> deployment {deployment}")
    log(f"  3. PUT    /contentunderstanding/analyzers/{analyzer_id}?allowReplace=true, then poll the operation")
    log("  4. GET    the analyzer and check it is ready and matches this definition")
    log("Run with --status to read the resource, or --apply to deploy.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy the checklist analyzer to Content Understanding.")
    parser.add_argument("--layout", choices=build_schema.LAYOUTS, default="nested")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="read-only check of the defaults and the analyzer")
    mode.add_argument("--apply", action="store_true", help="set the model defaults and create or replace the analyzer")
    args = parser.parse_args(argv)

    try:
        import auth
        auth.load_env()
        settings = Settings.from_env(os.environ)
        if not (args.status or args.apply):
            print_plan(settings, args.layout)
            return 0
        if not settings.endpoint:
            raise DeployError("CU_ENDPOINT is not set. It exists once the Foundry resource is deployed")
        if not os.environ.get("TENANT_ID"):
            raise DeployError("TENANT_ID is not set in .env")
        endpoint = normalize_endpoint(settings.endpoint)
        token = CliToken(os.environ["TENANT_ID"], os.environ.get("AZURE_ACCOUNT") or None)
        token()
        print(f"Signed in as {token.account}; resource {urlparse(endpoint).hostname}")
        client = Client(Http(token), endpoint)
        if args.status:
            return 0 if status(client, settings, args.layout) else 1
        deploy(client, settings, args.layout)
        return 0
    except DeployError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
