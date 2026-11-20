from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("purge_contract_index", SCRIPTS / "purge-contract-index.py")
purge = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = purge
_spec.loader.exec_module(purge)

A = "63abf974-20ea-472f-981a-8d42e67861cc"
B = "b1f22340-71ae-49ea-a426-ea463870a771"
GONE = "0a61bb38-ef8b-f111-8076-7ced8d3c0da2"
DOCS = [
    {"id": "a-new-1", "contractId": A, "version": "new"},
    {"id": "a-new-manifest", "contractId": A, "version": "new"},
    {"id": "a-old-1", "contractId": A, "version": "old"},
    {"id": "b-1", "contractId": B, "version": "v"},
    {"id": "gone-1", "contractId": GONE, "version": "v"},
]
LIVE = {A: "new", B: "v"}


def test_nothing_is_selected_without_a_selector() -> None:
    assert purge.plan(DOCS, LIVE, stale=False, orphans=False) == []


def test_stale_removes_only_older_versions_of_live_contracts() -> None:
    assert purge.plan(DOCS, LIVE, stale=True, orphans=False) == ["a-old-1"]


def test_orphans_remove_only_chunks_whose_contract_row_is_gone() -> None:
    assert purge.plan(DOCS, LIVE, stale=False, orphans=True) == ["gone-1"]


def test_contract_removes_every_version_of_that_contract_only() -> None:
    assert purge.plan(DOCS, LIVE, stale=False, orphans=False, contracts=[A]) == ["a-new-1", "a-new-manifest", "a-old-1"]


def test_a_contract_still_indexing_is_never_treated_as_stale_or_orphaned() -> None:
    assert purge.plan([{"id": "x", "contractId": B, "version": "v"}], {B: ""}, stale=True, orphans=True) == []


def test_contract_must_be_a_guid() -> None:
    with pytest.raises(ValueError):
        purge.plan(DOCS, LIVE, stale=False, orphans=False, contracts=["not-a-guid"])


def test_summary_counts_current_other_and_orphans() -> None:
    summary = purge.summarize(DOCS, LIVE)
    assert summary[A] == {"current": 2, "other": 1, "exists": 1}
    assert summary[GONE]["exists"] == 0
