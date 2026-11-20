from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))
import contract_search as search
from contract_qa import QaError, source_pages

CONTRACT = "63abf974-20ea-472f-981a-8d42e67861cc"
RAW = (ROOT / "tests" / "fixtures" / "cu_result_sow.json").read_text()


def client() -> search.Client:
    sdk, embeddings = Mock(), Mock()
    sdk.upload_documents.side_effect = lambda documents: [NS(succeeded=True) for _ in documents]
    embeddings.embeddings.create.side_effect = lambda **kw: NS(data=[
        NS(index=index, embedding=[0.1] * search.DIMENSIONS) for index, _ in enumerate(kw["input"])])
    return search.Client(sdk, embeddings, "text-embedding-3-small")


def test_chunks_are_page_local_versioned_and_cover_the_full_document() -> None:
    pages = {1: "SYNTHETIC SAMPLE " + "x" * 9000, 2: "Made-up contract ends after seven years."}
    docs = search.chunks(CONTRACT, pages)
    assert len(docs) > 4
    for doc in docs:
        assert doc["content"] in pages[doc["page"]]
        assert doc["version"] == search.document_version(pages)
    assert docs[-1]["content"] == pages[2]
    assert docs == search.chunks(CONTRACT, pages)
    changed = search.chunks(CONTRACT, {**pages, 2: "Changed synthetic term."})
    assert changed[0]["id"] != docs[0]["id"]


def test_schema_vector_dimensions_and_contract_filters() -> None:
    schema = search.index_schema("test-contracts")
    fields = {field.name: field for field in schema.fields}
    assert fields["contractId"].filterable and fields["version"].filterable
    assert fields["embedding"].vector_search_dimensions == search.DIMENSIONS


def test_ingestion_uploads_complete_document_before_marking_ready() -> None:
    api = client()
    api.ready = Mock(return_value=True)
    status, result = api.step({"contractId": CONTRACT, "context": RAW})
    assert status == 200
    uploaded = api.search.upload_documents.call_args_list
    assert uploaded[-1].kwargs["documents"][0]["kind"] == "manifest"
    assert uploaded[-1].kwargs["documents"][0]["chunkCount"] == result["chunkCount"]
    assert api.ready.call_args.args == (CONTRACT, result["version"], result["chunkCount"])


def test_partial_batch_failure_never_publishes_manifest_or_readiness() -> None:
    api = client()
    api.search.upload_documents.side_effect = lambda documents: [NS(succeeded=False) for _ in documents]
    with pytest.raises(QaError, match="every contract chunk"):
        api.step({"contractId": CONTRACT, "context": RAW})
    assert api.search.upload_documents.call_count == 1


def test_large_document_is_batched_and_resumes_without_reembedding_completed_chunks() -> None:
    api = client()
    raw = json.loads(RAW)
    raw["result"]["contents"][0]["markdown"] = "SYNTHETIC SAMPLE " + "word " * 6000 + "<!-- PageBreak -->End."
    request = {"contractId": CONTRACT, "context": json.dumps(raw)}
    status, result = api.step(request)
    assert status == 202 and result["operation"]["cursor"] == search.BATCH_SIZE
    assert len(api.search.upload_documents.call_args.kwargs["documents"]) == search.BATCH_SIZE
    request["operation"] = {**result["operation"], "version": "wrong"}
    with pytest.raises(QaError, match="continuation"):
        api.step(request)


def test_search_visibility_must_be_confirmed_before_ready() -> None:
    api = client()
    api.ready = Mock(return_value=False)
    status, result = api.step({"contractId": CONTRACT, "context": RAW})
    assert status == 202 and result["operation"]["cursor"] > 0


def test_partial_manifest_never_passes_readiness() -> None:
    api = client()
    api.search.search.return_value = []
    assert not api.ready(CONTRACT, "a" * 64, 2)
    with pytest.raises(QaError):
        api.ready(CONTRACT, "' or true", 2)


def test_retrieval_filters_before_ranking_and_rejects_other_contracts() -> None:
    api = client()
    api.ready = Mock(return_value=True)
    pages = source_pages(RAW)
    api.search.search.return_value = [{
        "contractId": CONTRACT, "version": search.document_version(pages), "page": 1, "content": pages[1],
    }]
    assert api.retrieve(CONTRACT, pages, "How many years?") == {1: pages[1]}
    sent = api.search.search.call_args.kwargs
    assert sent["vector_filter_mode"] == "preFilter"
    assert CONTRACT in sent["filter"] and search.document_version(pages) in sent["filter"]
    api.search.search.return_value[0]["contractId"] = "another-contract"
    with pytest.raises(QaError, match="outside"):
        api.retrieve(CONTRACT, pages, "How many years?")


def test_ready_manifest_requires_exact_chunk_count() -> None:
    api = client()
    results = Mock()
    results.get_count.return_value = 1
    api.search.search.side_effect = [[{"chunkCount": 2}], results]
    assert not api.ready(CONTRACT, "a" * 64, 2)


def test_embedding_throttling_pauses_and_resumes_from_the_same_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    class RateLimitError(Exception):
        pass

    pauses: list[int] = []
    monkeypatch.setattr(search.time, "sleep", pauses.append)
    api = client()
    api.embeddings.embeddings.create.side_effect = RateLimitError("429")
    status, body = api.step({"contractId": CONTRACT, "context": RAW})
    assert status == 202 and body["operation"]["cursor"] == 0
    assert pauses == [search.THROTTLE_SECONDS]
    api.search.upload_documents.assert_not_called()
    api.embeddings.embeddings.create.side_effect = ValueError("not a throttle")
    with pytest.raises(ValueError):
        api.step({"contractId": CONTRACT, "context": RAW})


def test_indexing_rejects_non_synthetic_source_before_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_REAL_CONTRACTS", raising=False)
    api = client()
    with pytest.raises(QaError, match="synthetic"):
        api.step({"contractId": CONTRACT, "context": RAW.replace("SYNTHETIC SAMPLE", "EXAMPLE")})
    api.embeddings.embeddings.create.assert_not_called()
