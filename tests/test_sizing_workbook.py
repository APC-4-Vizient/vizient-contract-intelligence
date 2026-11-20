"""docs/capacity-sizing-workbook.xlsx: its inputs that copy a constant in the code or the pricing module stay equal to it,
and its saved results carry no formula errors. The workbook is read as a zip of XML, so no spreadsheet library is needed."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "function"))

import contract_search  # noqa: E402
import flowlib  # noqa: E402

BOOK = ROOT / "docs" / "capacity-sizing-workbook.xlsx"
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
SAMPLES = ("Amendment", "Data use agreement", "Statement of work")


class Book:
    def __init__(self, path: Path) -> None:
        self.sheets: dict[str, dict[str, object]] = {}
        self.errors: list[str] = []
        with zipfile.ZipFile(path) as package:
            workbook = ET.fromstring(package.read("xl/workbook.xml"))
            targets = {rel.get("Id"): rel.get("Target") for rel in ET.fromstring(package.read("xl/_rels/workbook.xml.rels"))}
            shared = ["".join(text.text or "" for text in item.iter(MAIN + "t")) for item in ET.fromstring(package.read("xl/sharedStrings.xml"))]
            for sheet in workbook.find(MAIN + "sheets"):
                target = targets[sheet.get(REL + "id")].lstrip("/")
                tree = ET.fromstring(package.read(target if target.startswith("xl/") else "xl/" + target))
                cells: dict[str, object] = {}
                for cell in tree.iter(MAIN + "c"):
                    raw = cell.find(MAIN + "v")
                    if raw is None:
                        continue
                    kind = cell.get("t")
                    if kind == "e":
                        self.errors.append(f"{sheet.get('name')}!{cell.get('r')}")
                    cells[cell.get("r")] = shared[int(raw.text)] if kind == "s" else raw.text if kind in ("str", "e") else float(raw.text)
                self.sheets[sheet.get("name")] = cells
            self.names = {item.get("name"): item.text for item in workbook.find(MAIN + "definedNames")}

    def value(self, name: str) -> object:
        sheet, ref = self.names[name].split("!")
        return self.sheets[sheet.strip("'")][ref.replace("$", "")]


@pytest.fixture(scope="module")
def book() -> Book:
    assert BOOK.is_file(), f"{BOOK.relative_to(ROOT)} is missing"
    return Book(BOOK)


def number(text: str) -> float:
    return float(text.replace("_", ""))


def test_no_saved_result_is_a_formula_error(book: Book) -> None:
    assert book.errors == []
    assert book.value("c_cost_total") > 0


def test_inputs_that_copy_code_constants_match_the_code(book: Book) -> None:
    main = (ROOT / "infra" / "main.bicep").read_text(encoding="utf-8")
    qa = (ROOT / "infra" / "qa.bicep").read_text(encoding="utf-8")
    expected = {
        "in_poll_s": flowlib.POLL_SECONDS,
        "in_chunk_chars": contract_search.CHUNK_SIZE,
        "in_chunk_overlap": contract_search.OVERLAP,
        "in_batch_chunks": contract_search.BATCH_SIZE,
        "in_embed_dims": contract_search.DIMENSIONS,
        "in_q_ext_tpm": int(re.search(r"name: 'gpt-5\.5'.*?capacity: (\d+)", main, re.S).group(1)),
        "in_q_emb_tpm": int(re.search(r"name: 'text-embedding-3-small'\s+sku: \{[^}]*capacity: (\d+)", qa).group(1)),
        "in_search_partitions": int(re.search(r"partitionCount: (\d+)", qa).group(1)),
    }

    assert {name: book.value(name) for name in expected} == expected
    assert book.value("in_search_tier") == re.search(r"searchServices.*?sku: \{ name: '(\w+)' \}", qa, re.S).group(1).capitalize()


def test_prices_and_measured_samples_match_the_pricing_module(book: Book) -> None:
    costs = (ROOT / "contract-review" / "src" / "about" / "processingCost.ts").read_text(encoding="utf-8")
    rates = {key: (float(usd), number(per)) for key, usd, per in re.findall(r"id: '(reading|context|input|cached|output)'.*?usd: ([\d.]+), per: ([\d_]+)", costs)}
    names = {"reading": "in_p_read", "context": "in_p_ctx", "input": "in_p_in", "cached": "in_p_cached", "output": "in_p_out"}

    assert {key: usd for key, (usd, _) in rates.items()} == {key: book.value(name) for key, name in names.items()}
    assert {key: per for key, (_, per) in rates.items()} == {"reading": 1_000, "context": 1_000_000, "input": 1_000_000, "cached": 1_000_000, "output": 1_000_000}
    assert book.value("in_actions_intake") == number(re.search(r"intake: (\d+)", costs).group(1))

    cells = book.sheets["Per contract"]
    rows: dict[str, str] = {}
    for ref, text in cells.items():
        if ref.startswith("A") and text in SAMPLES:
            rows.setdefault(text, ref[1:])
    measured = re.findall(r"pages: (\d+), contextTokens: [\d_]+, inputTokens: ([\d_]+), cachedInputTokens: ([\d_]+), outputTokens: ([\d_]+)", costs)
    assert len(measured) == len(SAMPLES)
    for label, sample in zip(SAMPLES, measured):
        assert [cells[f"{col}{rows[label]}"] for col in "BCDE"] == [number(value) for value in sample]
