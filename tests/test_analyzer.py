"""Offline tests for analyzer/build_schema.py: the committed analyzer files must match checklist.json."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "analyzer"))

import build_schema  # noqa: E402
import checklistlib  # noqa: E402

ANALYZER_ID = build_schema.ANALYZER_IDS["nested"]


@pytest.fixture
def data() -> dict[str, Any]:
    return checklistlib.load_checklist()


@pytest.mark.parametrize("layout", build_schema.LAYOUTS)
def test_committed_file_matches_the_checklist(data: dict[str, Any], layout: str) -> None:
    committed = json.loads(build_schema.OUTPUT_FILES[layout].read_text(encoding="utf-8"))
    assert committed == build_schema.build_analyzer(data, layout), "run: python analyzer/build_schema.py --write"


@pytest.mark.parametrize("layout", build_schema.LAYOUTS)
def test_generated_analyzer_is_valid(data: dict[str, Any], layout: str) -> None:
    body = build_schema.build_analyzer(data, layout)
    assert build_schema.validate_analyzer(body, build_schema.ANALYZER_IDS[layout]) == []


def test_both_layouts_carry_every_right(data: dict[str, Any]) -> None:
    details, rights = len(checklistlib.detail_items(data)), len(checklistlib.right_items(data))
    nested = build_schema.field_counts(build_schema.build_analyzer(data, "nested"))
    flat = build_schema.field_counts(build_schema.build_analyzer(data, "flat"))
    assert nested == {"top_level": details + rights, "nested": 3 * rights, "total": details + 4 * rights}
    assert flat == {"top_level": details + 3 * rights, "nested": 0, "total": details + 3 * rights}


def test_every_right_refuses_to_infer_from_silence(data: dict[str, Any]) -> None:
    suffix = data["rightSuffix"]
    nested = build_schema.build_analyzer(data, "nested")["fieldSchema"]["fields"]
    flat = build_schema.build_analyzer(data, "flat")["fieldSchema"]["fields"]
    for item in checklistlib.right_items(data):
        judgment = nested[item["key"]]["properties"]["Judgment"]
        assert nested[item["key"]]["description"].endswith(suffix)
        assert judgment["description"].endswith(suffix)
        assert "Not Addressed" in judgment["enum"]
        assert flat[f"{item['key']}_Judgment"] == judgment


def test_baa_judgment_is_limited_to_what_the_brief_maps(data: dict[str, Any]) -> None:
    fields = build_schema.build_analyzer(data)["fieldSchema"]["fields"]
    assert fields["Right_BAARequired"]["properties"]["Judgment"]["enum"] == ["Conditional", "Not Addressed"]
    assert fields["Right_AIML"]["properties"]["Judgment"]["enum"] == [
        "Permitted", "Prohibited", "Conditional", "Not Addressed"]


def test_definition_hash_tracks_the_definition_and_ignores_tags(data: dict[str, Any]) -> None:
    body = build_schema.build_analyzer(data)
    assert build_schema.definition_hash(body) == body["tags"]["definitionHash"]
    body["fieldSchema"]["fields"]["Vendor"]["description"] += " changed"
    assert build_schema.definition_hash(body) != body["tags"]["definitionHash"]


@pytest.mark.parametrize(("mutate", "expected"), [
    (lambda f: f["Vendor"].update(estimateSourceAndConfidence=False), "estimateSourceAndConfidence must be true"),
    (lambda f: f.update({"Bad-Name": copy.deepcopy(f["Vendor"])}), "field names start with a letter"),
    (lambda f: f["Vendor"].update(description="x" * 4097), "description must be 1 to 4096"),
    (lambda f: f["DocumentType"].pop("enum"), "classify needs"),
    (lambda f: f["Right_AIML"]["properties"]["Judgment"].update(
        enum=["Permitted"], enumDescriptions={"Permitted": "Allowed."}), "must allow 'Not Addressed'"),
    (lambda f: f["Right_AIML"].update(properties={}), "an object field needs properties"),
])
def test_validator_rejects(data: dict[str, Any], mutate: Callable[[dict[str, Any]], Any], expected: str) -> None:
    body = build_schema.build_analyzer(data)
    mutate(body["fieldSchema"]["fields"])
    assert any(expected in problem for problem in build_schema.validate_analyzer(body, ANALYZER_ID))


def test_validator_rejects_an_analyzer_id_with_a_hyphen(data: dict[str, Any]) -> None:
    problems = build_schema.validate_analyzer(build_schema.build_analyzer(data), "vizient-contract")
    assert any("letters, digits, dots or underscores" in problem for problem in problems)
