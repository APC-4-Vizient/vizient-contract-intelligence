"""HTTP handlers for the contract analysis API.

    POST /api/contracts/analyze            start an analysis. 202 with Location and Retry-After.
    GET  /api/contracts/analyze/{id}       202 while it runs. 200 with {contract, findings, raw} when it is done.

The body of the POST is application/pdf, or JSON {"contractId", "fileName", "fileBase64"}. The handlers keep no state
and write contract content nowhere: the PDF goes to Content Understanding and the findings go back to the caller.
Only operation ids, statuses and counts are logged.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import azure.functions as func

import cu_client
import mapping
import contract_qa

MAX_PDF_BYTES = 32 * 1024 * 1024
MAX_BASE64_CHARS = -(-MAX_PDF_BYTES // 3) * 4
RETRY_AFTER_SECONDS = 5


@dataclass(frozen=True)
class Context:
    client: cu_client.Client
    items: list[dict[str, Any]]
    high_conf: float


class _Rejected(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def submit(req: func.HttpRequest, ctx: Context) -> func.HttpResponse:
    try:
        pdf, contract_id = _read_pdf(req)
    except _Rejected as rejected:
        return error(rejected.status, rejected.code, str(rejected))
    try:
        operation_id = ctx.client.submit(pdf)
    except cu_client.CuError as exc:
        return _upstream(exc)
    logging.info("analysis started: operation=%s contract=%s bytes=%d", operation_id, contract_id or "-", len(pdf))
    return _accepted(req, operation_id, "Running", RETRY_AFTER_SECONDS)


def poll(req: func.HttpRequest, ctx: Context) -> func.HttpResponse:
    operation_id = req.route_params.get("operationId") or ""
    if not cu_client.OPERATION_ID.fullmatch(operation_id):
        return error(400, "InvalidOperationId", "The operation id must be a GUID.")
    try:
        operation = ctx.client.poll(operation_id)
    except cu_client.CuError as exc:
        if exc.status == 404:
            return error(404, "OperationNotFound", "There is no such analysis. It may have expired.")
        return _upstream(exc)
    if not operation.done:
        return _accepted(req, operation_id, operation.status, operation.retry_after)
    if operation.status != "Succeeded":
        logging.warning("analysis %s: operation=%s", operation.status.lower(), operation_id)
        return error(502, f"Analysis{operation.status}", operation.error or f"The analysis {operation.status.lower()}.")
    try:
        payload = mapping.map_result(operation.body, ctx.items, ctx.high_conf)
    except mapping.MappingError as exc:
        logging.error("unexpected analyzer result: operation=%s %s", operation_id, exc)
        return error(502, "UnexpectedResult", str(exc))
    summary = payload["contract"]
    try:
        pages = contract_qa.pages_from_extraction(operation.body)
        content = {
            "markdown": "<!-- PageBreak -->".join(pages.values()),
            "pages": [{"pageNumber": page} for page in pages],
            "startPageNumber": 1, "endPageNumber": len(pages),
        }
        document = json.dumps({"result": {"contents": [content]}})
        if len(document) > contract_qa.MAX_CONTEXT:
            raise contract_qa.QaError("Full document text exceeds the indexing handoff limit.")
        payload["indexing"] = {"status": "Queued", "documentText": document, "error": ""}
    except contract_qa.QaError as exc:
        logging.warning("document indexing preparation rejected: operation=%s", operation_id)
        payload["indexing"] = {"status": "Failed", "documentText": "", "error": str(exc)}
    logging.info("analysis done: operation=%s found=%d of %d", operation_id, summary["foundCount"], summary["totalCount"])
    return _json(200, payload)


def error(status: int, code: str, message: str, headers: Mapping[str, str] | None = None) -> func.HttpResponse:
    return _json(status, {"error": {"code": code, "message": message}}, headers)


def _json(status: int, body: Any, headers: Mapping[str, str] | None = None) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status, mimetype="application/json",
                             headers=dict(headers or {}))


def _accepted(req: func.HttpRequest, operation_id: str, status: str, wait: int) -> func.HttpResponse:
    origin = urlsplit(req.url)
    location = f"{origin.scheme}://{origin.netloc}/api/contracts/analyze/{operation_id}"
    return _json(202, {"operationId": operation_id, "status": status},
                 {"Location": location, "Retry-After": str(wait)})


def _upstream(exc: cu_client.CuError) -> func.HttpResponse:
    logging.warning("Content Understanding call failed: status=%s code=%s", exc.status, exc.code)
    wait = {"Retry-After": str(exc.retry_after or cu_client.DEFAULT_RETRY_AFTER)}
    if exc.code == "Misconfigured":
        return error(500, "Misconfigured", str(exc))
    if exc.code == "NoToken":
        return error(502, "NoToken", "The Function could not get a token for Content Understanding.")
    if exc.status == 429:
        return error(429, "Throttled", "Content Understanding is busy. Try again shortly.", wait)
    if exc.status is None or exc.status >= 500:
        return error(503, "UpstreamUnavailable", "Content Understanding is unavailable. Try again shortly.", wait)
    if exc.status in (401, 403):
        return error(502, "UpstreamForbidden", f"Content Understanding rejected the Function's identity (HTTP {exc.status}).")
    return error(502, "UpstreamRejected", str(exc))


def _read_pdf(req: func.HttpRequest) -> tuple[bytes, str | None]:
    content_type = (req.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type == "application/pdf":
        pdf, contract_id = req.get_body(), req.params.get("contractId")
    elif content_type in ("", "application/json"):
        pdf, contract_id = _decode_json(req)
    else:
        raise _Rejected(415, "UnsupportedMediaType", "Send application/pdf, or application/json with fileBase64.")
    if not pdf:
        raise _Rejected(400, "EmptyFile", "The document is empty.")
    if len(pdf) > MAX_PDF_BYTES:
        raise _Rejected(413, "FileTooLarge", f"The document is over {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    if b"%PDF-" not in pdf[:1024]:
        raise _Rejected(415, "NotAPdf", "Only PDF documents are supported.")
    return pdf, contract_id if contract_id and cu_client.OPERATION_ID.fullmatch(contract_id) else None


def _decode_json(req: func.HttpRequest) -> tuple[bytes, str | None]:
    try:
        payload = req.get_json()
    except ValueError:
        raise _Rejected(400, "InvalidJson", "The body is not valid JSON.") from None
    encoded = payload.get("fileBase64") if isinstance(payload, dict) else None
    if not isinstance(encoded, str) or not encoded.strip():
        raise _Rejected(400, "MissingFile", "fileBase64 is required.")
    if len(encoded) > MAX_BASE64_CHARS:
        raise _Rejected(413, "FileTooLarge", f"The document is over {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    try:
        pdf = base64.b64decode("".join(encoded.split()), validate=True)
    except (binascii.Error, ValueError):
        raise _Rejected(400, "InvalidBase64", "fileBase64 is not valid base64.") from None
    contract_id = payload.get("contractId")
    return pdf, contract_id if isinstance(contract_id, str) else None
