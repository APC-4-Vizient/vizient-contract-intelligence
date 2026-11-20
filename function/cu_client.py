"""Content Understanding client for the Function: submit a PDF to the checklist analyzer, then poll the operation.

GA API 2025-11-01. The resource has local auth disabled, so each call carries an Entra bearer token from the token
provider: the Function's managed identity in Azure, the Azure CLI when run locally. The token is only ever sent to
the configured Azure AI endpoint. Operation URLs are rebuilt on that endpoint from the operation id, and redirects
are never followed, so the Operation-Location header cannot steer the token elsewhere.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import requests

API_VERSION = "2025-11-01"
ALLOWED_HOST_SUFFIXES = (".cognitiveservices.azure.com", ".services.ai.azure.com")
ACTIVE_STATES = ("NotStarted", "Running")
TERMINAL_STATES = ("Succeeded", "Failed", "Canceled")
OPERATION_ID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
DEFAULT_RETRY_AFTER = 5
MAX_RETRY_AFTER = 60
MAX_MESSAGE = 300

_OPERATION_PATH = re.compile(r"/contentunderstanding/analyzerResults/([0-9a-fA-F-]{36})/?")
_ANALYZER_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
_API_VERSION = re.compile(r"\d{4}-\d{2}-\d{2}")  # GA versions only: the preview APIs use a different operation path


class CuError(RuntimeError):
    """A failed call to Content Understanding. status is the HTTP status, or None when there was no reply."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None,
                 retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after = retry_after


@dataclass(frozen=True)
class Operation:
    id: str
    status: str
    body: Mapping[str, Any]
    retry_after: int
    error: str

    @property
    def done(self) -> bool:
        return self.status in TERMINAL_STATES


def normalize_endpoint(endpoint: str | None) -> str:
    """The https origin of the endpoint. The Entra token is only ever sent to Azure AI hosts."""
    parts = urlparse(endpoint or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host.endswith(ALLOWED_HOST_SUFFIXES):
        raise CuError("CU_ENDPOINT must be an https Azure AI endpoint, for example "
                      "https://<resource>.cognitiveservices.azure.com", code="Misconfigured")
    return f"https://{host}"


def operation_id_from(location: str | None) -> str:
    """The operation id in an Operation-Location header. Only the id is kept, never the URL."""
    match = _OPERATION_PATH.fullmatch(urlparse(location or "").path)
    if not match or not OPERATION_ID.fullmatch(match.group(1)):
        raise CuError("the service accepted the document but returned no usable Operation-Location",
                      code="UnexpectedReply")
    return match.group(1)


class Client:
    def __init__(self, endpoint: str | None, analyzer_id: str, token: Callable[[], str], *,
                 api_version: str = API_VERSION, session: requests.Session | None = None,
                 timeout: tuple[float, float] = (10, 60)) -> None:
        if not _ANALYZER_ID.fullmatch(analyzer_id or ""):
            raise CuError("CU_ANALYZER_ID must be 1 to 64 letters, digits, dots, dashes or underscores", code="Misconfigured")
        if not _API_VERSION.fullmatch(api_version or ""):
            raise CuError("CU_API_VERSION must look like 2025-11-01", code="Misconfigured")
        self.endpoint = normalize_endpoint(endpoint)
        self.analyzer_id = analyzer_id
        self.api_version = api_version
        self.token = token
        self.session = session or requests.Session()
        self.timeout = timeout

    def submit(self, pdf: bytes) -> str:
        """Start the analysis and return the operation id."""
        url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyzeBinary"
        reply = self._send("POST", url, "start the analysis", data=pdf, content_type="application/pdf")
        return operation_id_from(reply.headers.get("Operation-Location"))

    def poll(self, operation_id: str) -> Operation:
        """Read the operation once. The caller decides when to ask again."""
        if not OPERATION_ID.fullmatch(operation_id or ""):
            raise ValueError("operation_id must be a GUID")
        url = f"{self.endpoint}/contentunderstanding/analyzerResults/{operation_id}"
        reply = self._send("GET", url, "read the analysis")
        try:
            body = reply.json()
        except ValueError:
            body = None
        status = body.get("status") if isinstance(body, Mapping) else None
        if status not in ACTIVE_STATES + TERMINAL_STATES:
            raise CuError("the service returned an operation without a recognised status", status=reply.status_code,
                          code="UnexpectedReply")
        return Operation(operation_id, status, body, _retry_after(reply), _describe(body.get("error")))

    def _send(self, method: str, url: str, what: str, *, data: bytes | None = None,
              content_type: str | None = None) -> requests.Response:
        try:
            headers = {"Authorization": "Bearer " + self.token(), "Accept": "application/json"}
        except Exception as exc:  # azure-identity raises several types; the caller needs one
            raise CuError(f"could not {what}: no Entra token for Content Understanding ({type(exc).__name__})",
                          code="NoToken") from exc
        if content_type:
            headers["Content-Type"] = content_type
        try:
            reply = self.session.request(method, url, params={"api-version": self.api_version}, data=data,
                                         headers=headers, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException as exc:
            raise CuError(f"could not {what}: no reply from Content Understanding ({type(exc).__name__})") from exc
        if not 200 <= reply.status_code < 300:
            raise _failure(what, reply)
        return reply


def _failure(what: str, reply: requests.Response) -> CuError:
    try:
        body = reply.json()
    except ValueError:
        body = None
    error = body.get("error") if isinstance(body, Mapping) else None
    code = (error.get("code") if isinstance(error, Mapping) else None) or reply.headers.get("x-ms-error-code")
    detail = _describe(error)
    return CuError(f"could not {what}: HTTP {reply.status_code}{': ' + detail if detail else ''}",
                   status=reply.status_code, code=code, retry_after=_retry_after(reply))


def _describe(error: Any) -> str:
    if not isinstance(error, Mapping):
        return ""
    text = " - ".join(str(part) for part in (error.get("code"), error.get("message")) if part)
    return text[:MAX_MESSAGE]


def _retry_after(reply: requests.Response) -> int:
    try:
        seconds = int(float(reply.headers.get("Retry-After", DEFAULT_RETRY_AFTER)))
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_RETRY_AFTER
    return min(max(seconds, 1), MAX_RETRY_AFTER)
