"""Small Dataverse Web API client for the provisioning and verification scripts.

Authentication comes from scripts/auth.py. Metadata creates always carry the
MSCRM.SolutionUniqueName header, and the client refuses to create metadata when no
solution is configured, so nothing can land in the Default solution by accident.
"""

from __future__ import annotations

import base64
import os
import sys
import time
from collections.abc import Callable, Iterator
from typing import Any, Literal, overload
from urllib.parse import quote

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATAVERSE_SUPPRESS_FALLBACK_HINT", "1")
import auth  # noqa: E402

API_VERSION = "v9.2"
TOKEN_TTL_SECONDS = 40 * 60
TRANSIENT_STATUS = {429, 500, 502, 503, 504}
LOCK_MARKERS = ("0x80040216", "0x80060891", "0x80048d0b", "cannot start the requested operation")
QUERY_SAFE = "(),'$=/:@*"

COMPONENT_TYPES: dict[int, str] = {
    1: "Table",
    2: "Column",
    9: "Choice",
    10: "Relationship",
    14: "Alternate key",
    20: "Security role",
    26: "View",
    29: "Cloud flow / process",
    60: "Form",
    61: "Web resource",
    62: "Site map",
    80: "Model-driven app",
    91: "Plug-in assembly",
    92: "Plug-in step",
    300: "Canvas / code app",
    372: "Connector",
    380: "Environment variable",
    381: "Environment variable value",
    10163: "Connection reference",
}


class DataverseError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, method: str, path: str) -> None:
        super().__init__(f"{method} {path} -> HTTP {status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def label(text: str, language_code: int = 1033) -> dict[str, Any]:
    return {
        "@odata.type": "Microsoft.Dynamics.CRM.Label",
        "LocalizedLabels": [
            {
                "@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel",
                "Label": text,
                "LanguageCode": language_code,
            }
        ],
    }


def _query(params: dict[str, Any] | None) -> str:
    if not params:
        return ""
    return "?" + "&".join(f"{key}={quote(str(value), safe=QUERY_SAFE)}" for key, value in params.items())


def _retryable(resp: requests.Response) -> bool:
    if resp.status_code in TRANSIENT_STATUS:
        return True
    text = resp.text.lower()
    return any(marker in text for marker in LOCK_MARKERS) or ("another" in text and "running" in text)


def _delay_seconds(resp: requests.Response, attempt: int) -> int:
    retry_after = resp.headers.get("Retry-After", "")
    if retry_after.isdigit():
        return min(int(retry_after), 120)
    return min(10 * (attempt + 1), 60)


def _as_error(resp: requests.Response, method: str, path: str) -> DataverseError:
    try:
        error = resp.json().get("error", {})
        code, message = str(error.get("code", "")), str(error.get("message", ""))
    except ValueError:
        code, message = "", resp.text[:500]
    return DataverseError(resp.status_code, code, message[:800], method, path)


def entity_id(resp: requests.Response) -> str:
    """Return the GUID from the OData-EntityId header of a create response."""
    header = resp.headers.get("OData-EntityId", "")
    return header.rsplit("(", 1)[1].rstrip(")") if "(" in header else ""


class Dataverse:
    def __init__(self, skill: str = "dv-metadata", solution: str | None = None) -> None:
        auth.load_env()
        self.base_url = os.environ["DATAVERSE_URL"].rstrip("/")
        self.api = f"{self.base_url}/api/data/{API_VERSION}"
        self.solution = solution
        self._token = ""
        self._token_at = 0.0
        self._http = requests.Session()
        self._headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "User-Agent": auth.get_plugin_headers(skill)["User-Agent"],
        }

    def _bearer(self, refresh: bool = False) -> str:
        if refresh or not self._token or time.time() - self._token_at > TOKEN_TTL_SECONDS:
            self._token = auth.get_token()
            self._token_at = time.time()
        return self._token

    def _require_solution(self) -> str:
        if not self.solution:
            raise ValueError("No solution configured: refusing to create metadata outside a solution.")
        return self.solution

    @overload
    def request(self, method: str, path: str, *, body: Any = ..., params: dict[str, Any] | None = ..., solution: bool = ...,
                headers: dict[str, str] | None = ..., ok: tuple[int, ...] = ..., missing_ok: Literal[False] = ...,
                retries: int = ..., data: bytes | None = ...) -> requests.Response: ...

    @overload
    def request(self, method: str, path: str, *, body: Any = ..., params: dict[str, Any] | None = ..., solution: bool = ...,
                headers: dict[str, str] | None = ..., ok: tuple[int, ...] = ..., missing_ok: bool,
                retries: int = ..., data: bytes | None = ...) -> requests.Response | None: ...

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        params: dict[str, Any] | None = None,
        solution: bool = False,
        headers: dict[str, str] | None = None,
        ok: tuple[int, ...] = (200, 201, 204),
        missing_ok: bool = False,
        retries: int = 6,
        data: bytes | None = None,
    ) -> requests.Response | None:
        url = path if path.startswith("http") else f"{self.api}/{path.lstrip('/')}"
        url += _query(params)
        refreshed = False
        for attempt in range(retries + 1):
            request_headers = {**self._headers, "Authorization": f"Bearer {self._bearer()}"}
            if solution:
                request_headers["MSCRM.SolutionUniqueName"] = self._require_solution()
            if headers:
                request_headers.update(headers)
            resp = self._http.request(method, url, json=body, data=data, headers=request_headers, timeout=(15, 240))
            if resp.status_code in ok:
                return resp
            if resp.status_code == 404 and missing_ok:
                return None
            if resp.status_code == 401 and not refreshed:
                refreshed = True
                self._bearer(refresh=True)
                continue
            if attempt < retries and _retryable(resp):
                delay = _delay_seconds(resp, attempt)
                print(f"  retry {attempt + 1}/{retries}: HTTP {resp.status_code}, waiting {delay}s", file=sys.stderr)
                time.sleep(delay)
                continue
            raise _as_error(resp, method, path)
        raise AssertionError("unreachable")

    @overload
    def get(self, path: str, params: dict[str, Any] | None = ..., *, missing_ok: Literal[False] = ...) -> dict[str, Any]: ...

    @overload
    def get(self, path: str, params: dict[str, Any] | None = ..., *, missing_ok: bool) -> dict[str, Any] | None: ...

    def get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        resp = self.request("GET", path, params=params, missing_ok=missing_ok)
        return None if resp is None else resp.json()

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        url: str | None = path
        query = params
        while url:
            data = self.request("GET", url, params=query).json()
            yield from data.get("value", [])
            url, query = data.get("@odata.nextLink"), None

    def exists(self, path: str) -> bool:
        return self.get(path, {"$select": "MetadataId"}, missing_ok=True) is not None

    def reset_affinity(self) -> None:
        """Forget the server-affinity cookies so the next request can be served by another node."""
        self._http.cookies.clear()

    def create_metadata(self, path: str, body: dict[str, Any]) -> str:
        resp = self.request("POST", path, body=body, solution=True)
        return entity_id(resp)

    def action(self, name: str, body: dict[str, Any] | None = None, *, solution: bool = False) -> dict[str, Any]:
        resp = self.request("POST", name, body=body or {}, solution=solution)
        return resp.json() if resp.content else {}

    def whoami(self) -> dict[str, Any]:
        return self.get("WhoAmI") or {}

    def upload_file(self, row: str, column: str, file_name: str, content: bytes) -> None:
        """Store content in a file column of one row, as in ("vz_contracts(<id>)", "vz_document"). One request, up to 128 MB."""
        self.request("PATCH", f"{row}/{column}", data=content,
                     headers={"Content-Type": "application/octet-stream", "x-ms-file-name": file_name})

    def export_solution(self, unique_name: str, managed: bool = False) -> bytes:
        payload = self.action("ExportSolution", {"SolutionName": unique_name, "Managed": managed})
        return base64.b64decode(payload["ExportSolutionFile"])


def wait_for(check: Callable[[], bool], what: str, timeout: int = 180, interval: int = 4) -> None:
    deadline = time.time() + timeout
    while not check():
        if time.time() > deadline:
            raise TimeoutError(f"Timed out after {timeout}s waiting for {what}")
        time.sleep(interval)


def signed_in_account(dv: Dataverse) -> str:
    """The name of the user the Dataverse token belongs to."""
    user = dv.get(f"systemusers({dv.whoami()['UserId']})", {"$select": "domainname,internalemailaddress"}) or {}
    return user.get("domainname") or user.get("internalemailaddress") or "an unknown account"
