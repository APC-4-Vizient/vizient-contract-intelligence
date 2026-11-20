"""Analyze a contract PDF the way the review app will, and print what a reviewer would see.

    python scripts/run-local.py samples/contracts/bluepine-sow.pdf                  Content Understanding directly
    python scripts/run-local.py samples/contracts/bluepine-sow.pdf --via function   the deployed API
    python scripts/run-local.py --result samples/results/bluepine-sow.operation.json   a saved result, offline

Direct and function runs need the Azure CLI signed in as the project admin (AZURE_ACCOUNT in .env). A run saves what
the API returns, {contract, findings, raw}, to samples/results/<name>.json. A direct run also saves the full service
result as <name>.operation.json, so a change to the mapping can be re-run offline with --result. samples/ is
git-ignored. Progress goes to stderr and the findings table to stdout.

CONTRACT_DATA_MODE=synthetic (the default) sends only PDFs marked as synthetic samples, so a real contract cannot go to
the service by a mistyped path. The function key is read from Azure into memory; it is never printed or saved.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
for folder in ("scripts", "analyzer", "function"):
    sys.path.insert(0, str(ROOT / folder))

import cu_client  # noqa: E402
import mapping  # noqa: E402

RESULTS_DIR = ROOT / "samples" / "results"
SYNTHETIC_MARKER = "SYNTHETIC SAMPLE"
DEFAULT_ANALYZER = "vizientContractChecklist"
WAIT_SECONDS = 600.0
POLL_MIN, POLL_MAX = 2.0, 15.0
MAX_POLL_RETRIES = 5
API_SUFFIX = ".azurewebsites.net"
ARM_SCOPE = "https://management.azure.com/.default"
ARM_API_VERSION = "2023-12-01"

GUID = cu_client.OPERATION_ID
_RESOURCE_GROUP = re.compile(r"[\w.()-]{1,90}")
_APP_NAME = re.compile(r"[A-Za-z0-9-]{2,60}")
_AZD_ENV_NAME = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RunError(RuntimeError):
    """Something went wrong that deserves one clear line."""


def log(message: str) -> None:
    print(message, file=sys.stderr)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _now() -> float:
    return time.monotonic()


# --- settings -----------------------------------------------------------------------------------------------------

def azd_values(root: Path = ROOT) -> dict[str, str]:
    """The azd environment's outputs (function name, resource group, API address), or {} before azd has provisioned."""
    try:
        name = json.loads((root / ".azure" / "config.json").read_text(encoding="utf-8")).get("defaultEnvironment")
        if not isinstance(name, str) or not _AZD_ENV_NAME.fullmatch(name):
            return {}
        text = (root / ".azure" / name / ".env").read_text(encoding="utf-8")
    except (OSError, ValueError, AttributeError):
        return {}
    values = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() and not key.lstrip().startswith("#"):
            values[key.strip()] = value.strip().strip('"')
    return values


def load_settings(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """azd outputs, overridden by .env and the process environment."""
    if environ is None:
        import auth
        auth.load_env()
        environ = os.environ
    return {**azd_values(), **{key: value for key, value in environ.items() if value}}


# --- the synthetic-only guard --------------------------------------------------------------------------------------

def read_pdf(path: Path) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RunError(f"cannot read {path}: {exc.strerror or type(exc).__name__}") from exc
    if b"%PDF-" not in data[:1024]:
        raise RunError(f"{path.name} is not a PDF")
    return data


def confirm_synthetic(path: Path, mode: str) -> None:
    """In synthetic mode a PDF must carry the synthetic-sample marker, in its text or its document properties."""
    if mode == "real":
        log("CONTRACT_DATA_MODE=real: the synthetic-sample check is off")
        return
    if mode != "synthetic":
        raise RunError("CONTRACT_DATA_MODE must be synthetic or real")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RunError("pypdf is needed to confirm the PDF is a synthetic sample. Run: pip install pypdf") from exc
    try:
        reader = PdfReader(str(path))
        properties = " ".join(str(value) for value in (reader.metadata or {}).values())
        marked = SYNTHETIC_MARKER in properties or any(SYNTHETIC_MARKER in (page.extract_text() or "")
                                                       for page in reader.pages)
    except Exception as exc:  # pypdf raises many types for a damaged file
        raise RunError(f"cannot read {path.name} to confirm it is a synthetic sample ({type(exc).__name__})") from exc
    if not marked:
        raise RunError(f"{path.name} is not marked '{SYNTHETIC_MARKER}', so it was not sent. CONTRACT_DATA_MODE=synthetic "
                       "allows only the generated samples: python eval/generate_contracts.py")


# --- waiting --------------------------------------------------------------------------------------------------------

def transient(exc: cu_client.CuError) -> bool:
    """Throttling, an outage or no reply at all. A missing token or a bad setting will not fix itself."""
    if exc.status is None:
        return exc.code is None
    return exc.status == 429 or exc.status >= 500


def poll_until(read: Callable[[], tuple[Any, float | None]], what: str) -> Any:
    """Call read() until it returns (result, None). It returns (None, seconds) while the work is still running.
    Throttling and brief outages are retried a few times in a row; any other failure ends the wait."""
    deadline, failures = _now() + WAIT_SECONDS, 0
    while True:
        try:
            result, retry_after = read()
        except cu_client.CuError as exc:
            if not transient(exc) or failures >= MAX_POLL_RETRIES:
                raise
            failures, retry_after = failures + 1, exc.retry_after
        else:
            failures = 0
            if retry_after is None:
                return result
        if _now() >= deadline:
            raise RunError(f"{what} did not finish within {WAIT_SECONDS:.0f} s")
        _sleep(min(max(float(retry_after or cu_client.DEFAULT_RETRY_AFTER), POLL_MIN), POLL_MAX))


# --- direct: Content Understanding --------------------------------------------------------------------------------

def connect_direct(settings: Mapping[str, str]) -> cu_client.Client:
    import deploy_analyzer
    tenant = settings.get("TENANT_ID", "")
    if not tenant:
        raise RunError("TENANT_ID is not set in .env")
    token = deploy_analyzer.CliToken(tenant, settings.get("AZURE_ACCOUNT") or None)
    try:
        token()  # fail here, with the full reason, rather than as a bare NoToken on the first call
    except deploy_analyzer.DeployError as exc:
        raise RunError(str(exc)) from exc
    log(f"signed in as {token.account}")
    return cu_client.Client(settings.get("CU_ENDPOINT"), settings.get("CU_ANALYZER_ID") or DEFAULT_ANALYZER, token,
                            api_version=settings.get("CU_API_VERSION") or cu_client.API_VERSION)


def analyze_direct(client: cu_client.Client, pdf: bytes) -> cu_client.Operation:
    """Submit the PDF and wait for the operation to finish, in whatever state it finishes."""
    operation_id = client.submit(pdf)
    log(f"started {operation_id}")

    def read() -> tuple[cu_client.Operation | None, float | None]:
        operation = client.poll(operation_id)
        return (operation, None) if operation.done else (None, operation.retry_after)

    return poll_until(read, "the analysis")


def finish(operation: cu_client.Operation, items: Sequence[Mapping[str, Any]], high_conf: float) -> dict[str, Any]:
    if operation.status != "Succeeded":
        raise RunError(f"the analysis {operation.status.lower()}" + (f": {operation.error}" if operation.error else ""))
    return mapping.map_result(operation.body, items, high_conf)


# --- function: the deployed API ------------------------------------------------------------------------------------

def api_origin(base: str) -> str:
    parts = urlparse(base or "")
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host.endswith(API_SUFFIX):
        raise RunError(f"the API address must be an https {API_SUFFIX} address")
    return f"https://{host}"


def retry_after_of(reply: requests.Response) -> int | None:
    try:
        return min(max(int(float(reply.headers.get("Retry-After", ""))), 1), cu_client.MAX_RETRY_AFTER)
    except (TypeError, ValueError, OverflowError):
        return None


def api_failure(reply: requests.Response) -> cu_client.CuError:
    try:
        error = reply.json()["error"]
        code, message = str(error["code"]), str(error["message"])
    except (ValueError, KeyError, TypeError):
        code, message = "", reply.text
    message = clip(message, cu_client.MAX_MESSAGE)
    detail = f" {code}: {message}" if code else (f": {message}" if message else "")
    return cu_client.CuError(f"the API answered HTTP {reply.status_code}{detail}", status=reply.status_code,
                             code=code or None, retry_after=retry_after_of(reply))


class Api:
    """The deployed Function. The function key goes only to this host, and a redirect is an error, never followed."""

    def __init__(self, base: str, key: str, session: requests.Session | None = None,
                 timeout: tuple[float, float] = (10, 120)) -> None:
        self.base = api_origin(base)
        self._key = key
        self.session = session or requests.Session()
        self.timeout = timeout

    def submit(self, pdf: bytes) -> str:
        reply = self._send("POST", "/api/contracts/analyze", pdf)
        operation_id = self._json(reply).get("operationId") if reply.status_code == 202 else None
        if not isinstance(operation_id, str) or not GUID.fullmatch(operation_id):
            raise cu_client.CuError("the API did not accept the document with an operation id", code="UnexpectedReply")
        return operation_id

    def poll(self, operation_id: str) -> tuple[dict[str, Any] | None, float | None]:
        """(payload, None) when finished, else (None, seconds to wait)."""
        reply = self._send("GET", f"/api/contracts/analyze/{operation_id}")
        if reply.status_code == 202:
            return None, retry_after_of(reply) or cu_client.DEFAULT_RETRY_AFTER
        body = self._json(reply)
        if reply.status_code != 200 or not isinstance(body.get("findings"), list) or "contract" not in body:
            raise cu_client.CuError("the API returned a result without contract and findings", code="UnexpectedReply")
        return body, None

    def _send(self, method: str, path: str, pdf: bytes | None = None) -> requests.Response:
        headers = {"x-functions-key": self._key, "Accept": "application/json"}
        if pdf is not None:
            headers["Content-Type"] = "application/pdf"
        try:
            reply = self.session.request(method, self.base + path, headers=headers, data=pdf, timeout=self.timeout,
                                         allow_redirects=False)
        except requests.RequestException as exc:
            raise cu_client.CuError(f"no reply from the API ({type(exc).__name__})") from exc
        if not 200 <= reply.status_code < 300:
            raise api_failure(reply)
        return reply

    @staticmethod
    def _json(reply: requests.Response) -> dict[str, Any]:
        try:
            body = reply.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            raise cu_client.CuError("the API returned a reply that is not a JSON object", code="UnexpectedReply")
        return body


def function_key(settings: Mapping[str, str], *, credential: Any = None, session: Any = None) -> str:
    """The function app's default host key, read through Azure Resource Manager as the signed-in admin."""
    subscription = settings.get("AZURE_SUBSCRIPTION_ID", "")
    group, name, tenant = (settings.get(key, "") for key in ("AZURE_RESOURCE_GROUP", "AZURE_FUNCTION_NAME", "TENANT_ID"))
    if not (GUID.fullmatch(subscription) and _RESOURCE_GROUP.fullmatch(group) and _APP_NAME.fullmatch(name) and tenant):
        raise RunError("AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP, AZURE_FUNCTION_NAME and TENANT_ID must be set "
                       "(.env and the azd environment under .azure/)")
    import deploy_analyzer
    if credential is None:
        from azure.identity import AzureCliCredential
        credential = AzureCliCredential(tenant_id=tenant)
    try:
        token = credential.get_token(ARM_SCOPE).token
    except Exception as exc:  # azure-identity raises several types; the message is what helps
        reason = (str(exc).splitlines() or [type(exc).__name__])[0][:200]
        raise RunError(f"no Azure Resource Manager token from the Azure CLI ({reason}). Run: az login --tenant {tenant}") from exc
    try:
        account = deploy_analyzer.check_identity(deploy_analyzer.token_claims(token), tenant,
                                                 settings.get("AZURE_ACCOUNT") or None)
    except deploy_analyzer.DeployError as exc:
        raise RunError(str(exc)) from exc
    url = (f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{group}"
           f"/providers/Microsoft.Web/sites/{name}/host/default/listkeys")
    try:
        reply = (session or requests).post(url, params={"api-version": ARM_API_VERSION}, timeout=30,
                                           headers={"Authorization": f"Bearer {token}"}, allow_redirects=False)
    except requests.RequestException as exc:
        raise RunError(f"no reply from Azure Resource Manager ({type(exc).__name__})") from exc
    if reply.status_code != 200:
        raise RunError(f"Azure would not list the keys of {name} (HTTP {reply.status_code}). "
                       f"{account} needs Contributor on the function app")
    try:
        key = reply.json()["functionKeys"]["default"]
    except (ValueError, KeyError, TypeError):
        key = None
    if not isinstance(key, str) or not key:
        raise RunError(f"{name} has no default function key")
    log(f"read the function key of {name}; it is not shown or saved")
    return key


def connect_function(settings: Mapping[str, str]) -> Api:
    base = settings.get("SERVICE_API_URI", "")
    if not base:
        raise RunError("SERVICE_API_URI is not set. It is an output of azd provision, in .azure/<env>/.env")
    api_origin(base)
    return Api(base, function_key(settings))


def analyze_via_api(api: Api, pdf: bytes) -> dict[str, Any]:
    operation_id = api.submit(pdf)
    log(f"started {operation_id}")
    return poll_until(lambda: api.poll(operation_id), "the analysis")


# --- output ---------------------------------------------------------------------------------------------------------

def clip(text: str, width: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= width else text[:width - 3] + "..."


def render(payload: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> str:
    labels = {item["key"]: item["label"] for item in items}
    contract = payload.get("contract") or {}
    parent = "has a parent agreement" if contract.get("hasParentReference") else "no parent agreement"
    lines = [
        " | ".join(str(contract.get(key) or "-") for key in ("vendor", "documentType", "contractIdentifier"))
        + f" | effective {contract.get('effectiveDate') or '-'} | expires {contract.get('expirationDate') or '-'}",
        f"Found {contract.get('foundCount', 0)} of {contract.get('totalCount', 0)} ({contract.get('completeness', 0)}%)"
        f" | {parent}",
        "",
        f"{'Item':<34} {'Presence':<9} {'Judgment':<13} {'Page':>4} {'Regions':>7} {'Conf':>5}  Value or clause",
    ]
    for finding in payload.get("findings") or []:
        judgment = "" if finding.get("judgment") == mapping.NOT_APPLICABLE else finding.get("judgment") or ""
        confidence = finding.get("confidence")
        lines.append(
            f"{clip(labels.get(finding['key'], finding['key']), 34):<34} {finding.get('presence', ''):<9} {judgment:<13} "
            f"{finding.get('page') or '-':>4} {len(finding.get('sourceRegions') or []):>7} "
            f"{'-' if confidence is None else format(confidence, '.2f'):>5}  "
            f"{clip(finding.get('value') or finding.get('clause') or '', 60)}")
    usage = (payload.get("raw") or {}).get("usage")
    if usage:
        lines += ["", "usage: " + json.dumps(usage, sort_keys=True)]
    return "\n".join(lines)


def save(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def shown(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


# --- the command ------------------------------------------------------------------------------------------------------

def threshold(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = 0.0
    if not 0 < value <= 1:
        raise argparse.ArgumentTypeError("must be above 0 and at most 1")
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a contract PDF and print the checklist findings.")
    parser.add_argument("pdf", nargs="?", type=Path, help="the contract PDF to analyze")
    parser.add_argument("--result", type=Path, help="map a saved Content Understanding result instead; no network")
    parser.add_argument("--via", choices=("direct", "function"), help="call Content Understanding itself (the default) "
                        "or the deployed API")
    parser.add_argument("--out", type=Path, help="where to save the findings JSON (default samples/results/<name>.json)")
    parser.add_argument("--high-conf", type=threshold, help="the confidence a finding needs to count as Found "
                        "(default HIGH_CONF, else 0.8)")
    args = parser.parse_args(argv)
    if bool(args.pdf) == bool(args.result):
        parser.error("give a PDF to analyze, or --result with a saved result")
    if args.result and args.via:
        parser.error("--via applies to a PDF; --result maps a saved result without calling anything")
    if args.via == "function" and args.high_conf is not None:
        parser.error("the deployed API uses its own HIGH_CONF app setting; --high-conf applies to direct and --result runs")
    return args


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RunError(f"cannot read {path}: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise RunError(f"{path.name} is not a Content Understanding result")
    return data


def run_saved(args: argparse.Namespace, items: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[Path]]:
    operation = read_json(args.result)
    if "findings" in operation:
        raise RunError(f"{args.result.name} is already mapped. --result takes the full service result (<name>.operation.json)")
    payload = mapping.map_result(operation, items, args.high_conf or mapping.DEFAULT_HIGH_CONF)
    return payload, [save(args.out, payload)] if args.out else []


def run_pdf(args: argparse.Namespace, items: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[Path]]:
    settings = load_settings()
    pdf = read_pdf(args.pdf)
    confirm_synthetic(args.pdf, (settings.get("CONTRACT_DATA_MODE") or "synthetic").strip().lower())
    payload_path = args.out or RESULTS_DIR / f"{args.pdf.stem}.json"
    saved: list[Path] = []
    if args.via == "function":
        payload = analyze_via_api(connect_function(settings), pdf)
    else:
        operation = analyze_direct(connect_direct(settings), pdf)
        if operation.status == "Succeeded":  # keep the paid-for result even if the mapping then fails
            saved.append(save(payload_path.with_name(f"{payload_path.stem}.operation.json"), operation.body))
        payload = finish(operation, items, args.high_conf or mapping.parse_high_conf(settings.get("HIGH_CONF")))
    return payload, [*saved, save(payload_path, payload)]


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = parse_args(argv)
    try:
        items = mapping.load_checklist()
        payload, saved = run_saved(args, items) if args.result else run_pdf(args, items)
    except (RunError, cu_client.CuError, mapping.MappingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(render(payload, items))
    for path in saved:
        log(f"saved {shown(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
