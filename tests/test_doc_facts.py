"""The documents and the app's own wording must agree with the schema, the flows and the checklist on what the system consists of.

A count written into a sentence goes stale without anyone noticing: the README once said three tables and "both flows" after the system
had grown to four of each. These tests read the numbers out of the prose and compare them with the files they describe. When one fails,
fix the words, not the test.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import flowlib  # noqa: E402
import schemalib  # noqa: E402

NUMBER_WORDS = {word: number for number, word in enumerate("zero one two three four five six seven eight nine ten".split())}
DOCUMENTS = [ROOT / "README.md", ROOT / "contract-review" / "README.md", ROOT / "dataverse" / "schema.md", *sorted((ROOT / "docs").glob("*.md"))]
APP_WORDS = [path for path in sorted((ROOT / "contract-review" / "src" / "about").glob("*.ts")) if ".test." not in path.name]

NUMBER = r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
TABLES = re.compile(rf"\b{NUMBER}\s+(?:(?:Dataverse|review|solution|`vz_`)\s+)?tables\b", re.IGNORECASE)
# A count of every flow, not of some of them: "all four flows", "the four flows", "four cloud flows". "The last two flows" is not one.
ALL_FLOWS = re.compile(rf"\b(?:(?:all|the)\s+{NUMBER}\s+(?:(?:cloud|Power Automate)\s+)?flows|{NUMBER}\s+cloud\s+flows)\b", re.IGNORECASE)
FLOWS_ON = re.compile(r"\b(\d+) of (\d+) current and on\b")
CHECKLIST_SIZE = re.compile(r"\b(\d+)-item checklist\b|\b(\d+) extracted items\b")
TABLE_LIST = re.compile(r"VizientContractPOC:\s*((?:vz_\w+(?:,\s*)?)+)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def number(word: str) -> int:
    return int(word) if word.isdigit() else NUMBER_WORDS[word.lower()]


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return schemalib.load_schema()


def test_every_count_of_tables_is_the_schemas(schema: dict[str, Any]) -> None:
    claims = [(named(path), match) for path in [*DOCUMENTS, *APP_WORDS] for match in TABLES.finditer(read(path))]
    assert len(claims) >= 3, "the pattern no longer matches anything: if the wording changed, change this test with it"
    wrong = [f"{where}: {match.group(0)!r}" for where, match in claims if number(match.group(1)) != len(schema["tables"])]
    assert not wrong, f"the schema has {len(schema['tables'])} tables, but " + "; ".join(wrong)


def test_every_count_of_all_the_flows_is_the_flows(schema: dict[str, Any]) -> None:
    flows = len(flowlib.flow_specs(schema))
    claims = [(named(path), match) for path in DOCUMENTS for match in ALL_FLOWS.finditer(read(path))]
    assert len(claims) >= 3, "the pattern no longer matches anything: if the wording changed, change this test with it"
    wrong = [f"{where}: {match.group(0)!r}" for where, match in claims if number(match.group(match.lastindex or 1)) != flows]
    wrong += [
        f"{named(path)}: {match.group(0)!r}"
        for path in DOCUMENTS
        for match in FLOWS_ON.finditer(read(path))
        if {int(match.group(1)), int(match.group(2))} != {flows}
    ]
    assert not wrong, f"the solution has {flows} flows, but " + "; ".join(wrong)


def test_no_text_says_both_flows() -> None:
    offenders = [named(path) for path in [*DOCUMENTS, *APP_WORDS] if re.search(r"\bboth flows\b", read(path), re.IGNORECASE)]
    assert not offenders, "name the flows (Intake and Analysis) instead of saying both: there are four. " + ", ".join(offenders)


def test_the_lists_of_tables_are_the_schemas_tables(schema: dict[str, Any]) -> None:
    names = {table["name"] for table in schema["tables"]}
    lists = [(named(path), set(re.findall(r"vz_\w+", match.group(1)))) for path in DOCUMENTS for match in TABLE_LIST.finditer(read(path))]
    assert len(lists) >= 2, "no document lists the tables after 'VizientContractPOC:' any more: if the wording changed, change this test with it"
    assert [where for where, listed in lists if listed != names] == []


def test_every_checklist_size_is_the_number_of_questions_the_ai_answers() -> None:
    items = json.loads((ROOT / "checklist" / "checklist.json").read_text(encoding="utf-8-sig"))["items"]
    answered = sum(1 for item in items if item["source"] == "analyzer")
    claims = [(named(path), match) for path in [*DOCUMENTS, *APP_WORDS] for match in CHECKLIST_SIZE.finditer(read(path))]
    assert len(claims) >= 3, "the pattern no longer matches anything: if the wording changed, change this test with it"
    wrong = [f"{where}: {match.group(0)!r}" for where, match in claims if int(match.group(match.lastindex or 1)) != answered]
    assert not wrong, f"the AI answers {answered} items, but " + "; ".join(wrong)
