from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("reextract_contracts", SCRIPTS / "reextract-contracts.py")
reextract = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = reextract
_spec.loader.exec_module(reextract)

ROWS = [
    {"vz_name": "a.pdf", "vz_status": 651200002, "vz_document_name": "a.pdf"},
    {"vz_name": "b.pdf", "vz_status": 651200001, "vz_document_name": "b.pdf"},
    {"vz_name": "c.pdf", "vz_status": 651200003, "vz_document_name": None},
    {"vz_name": "d.pdf", "vz_status": 651200005, "vz_document_name": "d.pdf"},
]


def test_only_contracts_with_a_pdf_that_are_not_already_extracting_are_requeued() -> None:
    chosen, skipped = reextract.select(ROWS)
    assert [row["vz_name"] for row in chosen] == ["a.pdf", "d.pdf"]
    assert skipped == ["b.pdf: already extracting", "c.pdf: no PDF is attached"]


def test_names_limit_the_selection_case_insensitively() -> None:
    chosen, skipped = reextract.select(ROWS, ["A.PDF"])
    assert [row["vz_name"] for row in chosen] == ["a.pdf"]
    assert skipped == []


def test_clearing_resets_index_fields_but_not_review_fields() -> None:
    assert set(reextract.CLEAR) == {"vz_documenttext", "vz_indexstatus", "vz_indexversion", "vz_indexerror"}
