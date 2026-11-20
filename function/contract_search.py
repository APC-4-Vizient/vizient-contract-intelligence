"""Ingestion-time, versioned Azure AI Search indexing and server-filtered retrieval."""
from __future__ import annotations

import hashlib
import time
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from contract_qa import QaError, source_pages

DIMENSIONS = 1536
CHUNK_SIZE = 2400
OVERLAP = 240
BATCH_SIZE = 8
THROTTLE_SECONDS = 10


def document_version(pages: Mapping[int, str]) -> str:
    document = "\n\n".join(f"PAGE {page}\n{text}" for page, text in pages.items())
    return hashlib.sha256(document.encode()).hexdigest()


def chunks(contract_id: str, pages: Mapping[int, str]) -> list[dict[str, Any]]:
    contract_id = str(UUID(contract_id))
    version = document_version(pages)
    documents = []
    for page, text in pages.items():
        for offset in range(0, len(text), CHUNK_SIZE - OVERLAP):
            part = text[offset:offset + CHUNK_SIZE]
            if part.strip():
                documents.append({
                    "id": f"{contract_id}-{version}-{page}-{offset}",
                    "kind": "chunk", "contractId": contract_id, "version": version,
                    "page": page, "content": part,
                })
            if offset + CHUNK_SIZE >= len(text):
                break
    if not documents:
        raise QaError("The contract has no searchable document text.")
    return documents


def index_schema(name: str) -> Any:
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration, SearchField, SearchFieldDataType, SearchIndex,
        SearchableField, SimpleField, VectorSearch, VectorSearchProfile,
    )

    return SearchIndex(name=name, fields=[
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        *[SimpleField(name=field, type=SearchFieldDataType.String, filterable=True)
          for field in ("kind", "contractId", "version")],
        SimpleField(name="page", type=SearchFieldDataType.Int32),
        SimpleField(name="chunkCount", type=SearchFieldDataType.Int32),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=DIMENSIONS, vector_search_profile_name="contracts"),
    ], vector_search=VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name="contracts", algorithm_configuration_name="hnsw")]))


class Client:
    def __init__(self, search: Any, embeddings: Any, model: str) -> None:
        self.search, self.embeddings, self.model = search, embeddings, model

    def _vectors(self, texts: list[str]) -> list[list[float]]:
        result = self.embeddings.embeddings.create(model=self.model, input=texts, dimensions=DIMENSIONS)
        ordered = sorted(result.data, key=lambda item: item.index)
        if [item.index for item in ordered] != list(range(len(texts))):
            raise QaError("The embedding service returned an incomplete batch.")
        vectors = [item.embedding for item in ordered]
        if any(len(vector) != DIMENSIONS for vector in vectors):
            raise QaError("The embedding dimensions do not match the contract index.")
        return vectors

    def _upload(self, documents: list[dict[str, Any]]) -> None:
        results = self.search.upload_documents(documents=documents)
        if len(results) != len(documents) or any(not result.succeeded for result in results):
            raise QaError("Azure AI Search did not accept every contract chunk. Retry indexing.")

    def ready(self, contract_id: str, version: str, expected: int) -> bool:
        contract_id = str(UUID(contract_id))
        if len(version) != 64 or any(char not in "0123456789abcdef" for char in version):
            raise QaError("Invalid contract index version.")
        bound = f"contractId eq '{contract_id}' and version eq '{version}'"
        manifests = list(self.search.search(
            search_text="*", filter=f"{bound} and kind eq 'manifest'",
            select=["chunkCount"], top=1))
        if not manifests or manifests[0]["chunkCount"] != expected:
            return False
        results = self.search.search(search_text="*", filter=f"{bound} and kind eq 'chunk'",
                                     include_total_count=True, select=["id"], top=1)
        return results.get_count() == expected

    def step(self, payload: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        contract_id = str(UUID(payload["contractId"]))
        pages = source_pages(payload["context"])
        version = document_version(pages)
        documents = chunks(contract_id, pages)
        operation = payload.get("operation") or {}
        if not isinstance(operation, dict):
            raise QaError("Invalid document indexing continuation.")
        cursor = operation.get("cursor", 0)
        if (type(cursor) is not int or not 0 <= cursor <= len(documents)
                or operation.get("version", version) != version):
            raise QaError("The indexing continuation does not match this document.")
        batch = documents[cursor:cursor + BATCH_SIZE]
        if batch:
            try:
                vectors = self._vectors([document["content"] for document in batch])
            except Exception as exc:
                # The embedding quota is per minute. Wait a little and let the caller poll again from the same cursor.
                if type(exc).__name__ != "RateLimitError":
                    raise
                time.sleep(THROTTLE_SECONDS)
                return 202, {"operation": {"cursor": cursor, "version": version}}
            self._upload([{**document, "embedding": vector} for document, vector in zip(batch, vectors, strict=True)])
            cursor += len(batch)
        state = {"cursor": cursor, "version": version}
        if cursor < len(documents):
            return 202, {"operation": state}
        self._upload([{"id": f"{contract_id}-{version}-manifest", "kind": "manifest",
                       "contractId": contract_id, "version": version, "chunkCount": len(documents)}])
        if not self.ready(contract_id, version, len(documents)):
            return 202, {"operation": state}
        return 200, {"version": version, "chunkCount": len(documents)}

    def retrieve(self, contract_id: str, pages: Mapping[int, str], query: str) -> dict[int, str]:
        from azure.search.documents.models import VectorizedQuery

        contract_id = str(UUID(contract_id))
        version = document_version(pages)
        if not self.ready(contract_id, version, len(chunks(contract_id, pages))):
            raise QaError("This document version is not indexed yet. Wait for Q&A indexing or retry ingestion.")
        vector = self._vectors([query])[0]
        results = self.search.search(
            search_text=query,
            vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=12, fields="embedding")],
            vector_filter_mode="preFilter",
            filter=f"contractId eq '{contract_id}' and version eq '{version}' and kind eq 'chunk'",
            select=["contractId", "version", "page", "content"], top=12)
        evidence: dict[int, list[str]] = {}
        for result in results:
            page, text = result["page"], result["content"]
            if (result["contractId"] != contract_id or result["version"] != version
                    or type(page) is not int or page not in pages
                    or not isinstance(text, str) or text not in pages[page]):
                raise QaError("Search returned evidence outside the authorized contract version.")
            evidence.setdefault(page, []).append(text)
        if not evidence:
            raise QaError("Search returned no passages for this question. Try a more specific question.")
        return {page: "\n\n".join(sorted(set(parts))) for page, parts in evidence.items()}
