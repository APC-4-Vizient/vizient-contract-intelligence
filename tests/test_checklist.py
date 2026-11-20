"""Offline tests for scripts/checklistlib.py: checklist.json must stay consistent with dataverse/schema.json."""

from __future__ import annotations

import copy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import checklistlib  # noqa: E402
import schemalib  # noqa: E402


@pytest.fixture
def schema() -> dict[str, Any]:
    return schemalib.load_schema()


@pytest.fixture
def data(schema: dict[str, Any]) -> dict[str, Any]:
    return checklistlib.load_checklist(schema=schema)


def test_checklist_has_twenty_analyzer_items_and_two_manual(data: dict[str, Any]) -> None:
    assert len(checklistlib.detail_items(data)) == 9
    assert len(checklistlib.right_items(data)) == 11
    assert len(checklistlib.manual_items(data)) == 2


def test_seed_rows_carry_the_choice_value_of_their_group(data: dict[str, Any], schema: dict[str, Any]) -> None:
    rows = {row["vz_key"]: row for row in checklistlib.seed_rows(data, schema)}
    assert len(rows) == 22
    assert rows["Vendor"]["vz_group"] == 651200000
    assert rows["Right_AIML"]["vz_group"] == 651200001
    assert rows["ContractOwner"]["vz_group"] == 651200002
    assert {key for key, row in rows.items() if row["vz_hasjudgment"]} == {
        item["key"] for item in checklistlib.right_items(data)}


@pytest.mark.parametrize(("mutate", "expected"), [
    (lambda d: d["items"][1].update(key="vendor"), "duplicate key"),
    (lambda d: d["items"][0].update(group="Details"), "group must be one of"),
    (lambda d: d["items"][1].update(sortOrder=1), "sortOrder must increase"),
    (lambda d: d["items"][0].update(key="A" * 60), "leave room for the flat field suffixes"),
    (lambda d: d["items"][-1].update(type="string"), "manual items cannot carry analyzer settings"),
    (lambda d: d["items"][9].update(enum=["Yes"]), "always returns Judgment, Conditions and Clause"),
    (lambda d: d["items"][12].update(judgments={"Conditional": "Needs a BAA."}), "include 'Not Addressed'"),
    (lambda d: d["items"][2].pop("enum"), "classify fields need"),
])
def test_validation_reports_what_is_wrong(data: dict[str, Any], schema: dict[str, Any],
                                          mutate: Callable[[dict[str, Any]], Any], expected: str) -> None:
    broken = copy.deepcopy(data)
    mutate(broken)
    assert any(expected in problem for problem in checklistlib.validate(broken, schema))
