"""Vizient Contract Intelligence API (Azure Functions, Python v2 programming model).

    GET  /api/health                       anonymous liveness probe
    POST /api/contracts/analyze            start an analysis of one PDF (function key)
    GET  /api/contracts/analyze/{id}       poll it; 200 carries {contract, findings, raw} (function key)

Settings: CU_ENDPOINT, CU_ANALYZER_ID, CU_API_VERSION and AZURE_CLIENT_ID come from the infrastructure. HIGH_CONF
(default 0.80) is optional. The API keeps no state: it never calls Dataverse and never stores contract content.
"""
from __future__ import annotations

import functools
import json
import logging
import os
from collections.abc import Callable

import azure.functions as func

import cu_client
import mapping
import routes
import contract_qa
import contract_search

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

SCOPE = "https://cognitiveservices.azure.com/.default"


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe. Static body, so it discloses nothing and needs no key."""
    return func.HttpResponse(
        json.dumps({"status": "ok", "service": "vizient-contract-api"}),
        mimetype="application/json",
    )


@app.route(route="contracts/analyze", methods=["POST"])
def start_analysis(req: func.HttpRequest) -> func.HttpResponse:
    return _handle(routes.submit, req)


@app.route(route="contracts/analyze/{operationId}", methods=["GET"])
def get_analysis(req: func.HttpRequest) -> func.HttpResponse:
    return _handle(routes.poll, req)


@app.route(route="contracts/questions", methods=["POST"])
def ask_contract(req: func.HttpRequest) -> func.HttpResponse:
    try:
        status, body = _qa_client().step(req.get_json())
        return routes._json(status, body)
    except (ValueError, contract_qa.QaError) as exc:
        return routes.error(400, "QuestionRejected", str(exc))
    except Exception as exc:
        # SDK errors may contain prompts or document snippets; log only the exception class.
        logging.warning("contract question failed: %s", type(exc).__name__)
        return routes.error(502, "AgentUnavailable", "The contract agent is unavailable. Try again shortly.")


@app.route(route="contracts/index", methods=["POST"])
def index_contract(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = req.get_json()
        if not isinstance(payload, dict) or not isinstance(payload.get("context"), str):
            raise contract_qa.QaError("A contract id and full document extraction are required.")
        status, body = _search_client().step(payload)
        return routes._json(status, body)
    except (ValueError, KeyError, TypeError) as exc:
        logging.warning("contract indexing input rejected: %s", type(exc).__name__)
        return routes.error(400, "IndexRejected", "The indexing request is invalid or is not a complete, page-numbered document.")
    except Exception as exc:
        logging.warning("contract indexing failed: %s", type(exc).__name__)
        return routes.error(502, "IndexUnavailable", "Document indexing is unavailable. Retry indexing shortly.")


@functools.lru_cache(maxsize=1)
def _search_client() -> contract_search.Client:
    from azure.identity import ManagedIdentityCredential, get_bearer_token_provider
    from azure.search.documents import SearchClient
    from openai import AzureOpenAI

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    embedding_endpoint = os.environ.get("EMBEDDING_ENDPOINT")
    if not endpoint or not embedding_endpoint:
        raise ValueError("Contract document search has not been configured.")
    credential = ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID") or None)
    search = SearchClient(endpoint, os.environ.get("AZURE_SEARCH_INDEX") or "contract-chunks", credential,
                          connection_timeout=10, read_timeout=15, retry_total=0)
    embeddings = AzureOpenAI(
        azure_endpoint=embedding_endpoint, api_version="2024-10-21",
        azure_ad_token_provider=get_bearer_token_provider(credential, SCOPE), timeout=30, max_retries=0)
    return contract_search.Client(search, embeddings, os.environ.get("EMBEDDING_MODEL") or "text-embedding-3-small")

@functools.lru_cache(maxsize=1)
def _qa_client() -> contract_qa.Client:
    from azure.ai.projects import AIProjectClient
    from azure.identity import ManagedIdentityCredential

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise ValueError("The contract agent has not been configured.")
    credential = ManagedIdentityCredential(client_id=os.environ.get("AZURE_CLIENT_ID") or None)
    project = AIProjectClient(endpoint=endpoint, credential=credential)
    return contract_qa.Client(project, os.environ.get("FOUNDRY_QA_AGENT") or "contract-questions", _search_client())


def _handle(handler: Callable[[func.HttpRequest, routes.Context], func.HttpResponse],
            req: func.HttpRequest) -> func.HttpResponse:
    try:
        context = _context()
    except cu_client.CuError as exc:
        logging.error("the API is not configured: %s", exc)
        return routes.error(500, "Misconfigured", str(exc))
    except (OSError, ValueError):  # the checklist is missing or unreadable; its path stays out of the response
        logging.exception("the API could not load its checklist")
        return routes.error(500, "Misconfigured", "The API could not load its checklist.")
    return handler(req, context)


@functools.lru_cache(maxsize=1)
def _context() -> routes.Context:
    from azure.identity import DefaultAzureCredential  # imported here so /api/health stays fast to start

    credential = DefaultAzureCredential(managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID") or None)
    client = cu_client.Client(
        os.environ.get("CU_ENDPOINT"),
        os.environ.get("CU_ANALYZER_ID") or "vizientContractChecklist",
        lambda: credential.get_token(SCOPE).token,
        api_version=os.environ.get("CU_API_VERSION") or cu_client.API_VERSION,
    )
    return routes.Context(client, mapping.load_checklist(), mapping.parse_high_conf(os.environ.get("HIGH_CONF")))
