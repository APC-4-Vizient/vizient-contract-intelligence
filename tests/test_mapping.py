"""Offline tests for function/mapping.py: a Content Understanding result becomes the checklist findings the app shows.

The base case is a real analysis of a 2-page synthetic SOW (tests/fixtures/cu_result_sow.json). Edge cases edit a copy of it.
"""

from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))

import mapping  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "cu_result_sow.json"
DETAIL = {"key": "Vendor", "group": "Contract Detail"}
RIGHT = {"key": "Right_AIML", "group": "Data Right"}
NOT_ADDRESSED_KEYS = ["Right_ProductDevelopment", "Right_BAARequired", "Right_AffiliateSharing", "Right_DataLinking",
                      "Right_DeIdentification", "Right_Geographic"]


@pytest.fixture(scope="module")
def items() -> list[dict[str, Any]]:
    return mapping.load_checklist()


@pytest.fixture
def operation() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fields_of(operation: dict[str, Any]) -> dict[str, Any]:
    return operation["result"]["contents"][0]["fields"]


def parts_of(operation: dict[str, Any], key: str = "Right_AIML") -> dict[str, Any]:
    return fields_of(operation)[key]["valueObject"]


def finding(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in payload["findings"] if item["key"] == key)


def segment(page: int, x: float = 0.0) -> str:
    return f"D({page},{x},0,{x + 1},0,{x + 1},1,{x},1)"


def minimal(fields: dict[str, Any], markdown: str = "") -> dict[str, Any]:
    return {"result": {"contents": [{"fields": fields, "markdown": markdown, "pages": []}]}}


def string_field(value: str, confidence: float = 0.9, **extra: Any) -> dict[str, Any]:
    return {"type": "string", "valueString": value, "confidence": confidence, "source": segment(1), **extra}


# --- a real result -----------------------------------------------------------------------------------------------

def test_a_real_result_maps_every_checklist_item_in_order(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    payload = mapping.map_result(operation, items)

    assert [item["key"] for item in payload["findings"]] == [item["key"] for item in items]
    assert Counter(item["presence"] for item in payload["findings"]) == {"Found": 13, "Unclear": 1, "Not Found": 6}
    assert payload["contract"] == {
        "vendor": "Bluepine Health Data, Inc.",
        "vizientEntity": "Vizient, Inc.",
        "documentType": "SOW",
        "contractIdentifier": "BP-2025-0417",
        "effectiveDate": "2025-01-15",
        "expirationDate": "2028-01-14",
        "hasParentReference": True,
        "foundCount": 13,
        "totalCount": 20,
        "completeness": 65.0,
    }
    assert json.loads(json.dumps(payload)) == payload


def test_mapping_leaves_the_operation_untouched(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    before = copy.deepcopy(operation)
    mapping.map_result(operation, items)
    assert operation == before


def test_details_carry_value_quote_page_and_region(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    vendor = finding(mapping.map_result(operation, items), "Vendor")

    assert vendor["presence"] == "Found"
    assert (vendor["value"], vendor["clause"]) == ("Bluepine Health Data, Inc.", "Bluepine Health Data, Inc.")
    assert (vendor["judgment"], vendor["conditions"]) == ("N/A", "")
    assert (vendor["page"], vendor["confidence"]) == (1, 0.953)
    [region] = vendor["sourceRegions"]
    assert region["page"] == 1
    assert region["polygon"][:2] == [2.5612, 1.5368] and len(region["polygon"]) == 8


def test_a_date_keeps_the_iso_value_and_quotes_the_wording(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    effective = finding(mapping.map_result(operation, items), "EffectiveDate")
    assert (effective["value"], effective["clause"]) == ("2025-01-15", "January 15, 2025")


def test_a_detail_with_several_source_segments_keeps_each_region(operation: dict[str, Any],
                                                                 items: list[dict[str, Any]]) -> None:
    signatories = finding(mapping.map_result(operation, items), "Signatories")
    assert [region["page"] for region in signatories["sourceRegions"]] == [2, 2]
    assert signatories["page"] == 2


def test_low_confidence_is_unclear_and_keeps_the_answer(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    signatories = finding(mapping.map_result(operation, items), "Signatories")
    assert signatories["presence"] == "Unclear"
    assert signatories["confidence"] == 0.705
    assert "Maren Okafor" in signatories["value"] and signatories["sourceRegions"]


@pytest.mark.parametrize(("high_conf", "found"), [(0.5, 14), (0.8, 13), (0.95, 4), (0.96, 2), (1.0, 0)])
def test_the_threshold_decides_found_or_unclear(operation: dict[str, Any], items: list[dict[str, Any]],
                                                high_conf: float, found: int) -> None:
    payload = mapping.map_result(operation, items, high_conf)
    assert payload["contract"]["foundCount"] == found
    assert Counter(item["presence"] for item in payload["findings"])["Not Found"] == 6


def test_a_confidence_exactly_at_the_threshold_is_found() -> None:
    for confidence, presence in ((0.79, "Unclear"), (0.8, "Found")):
        payload = mapping.map_result(minimal({"Vendor": string_field("Acme", confidence)}), [DETAIL])
        assert payload["findings"][0]["presence"] == presence


def test_a_confident_detail_without_a_source_is_unclear() -> None:
    field = string_field("Acme", 0.99)
    del field["source"]
    result = finding(mapping.map_result(minimal({"Vendor": field}), [DETAIL]), "Vendor")
    assert (result["presence"], result["value"], result["page"], result["sourceRegions"]) == ("Unclear", "Acme", None, [])


@pytest.mark.parametrize(("field", "confidence"), [
    ({"type": "string", "confidence": 0.61}, 0.61),
    ({"type": "string", "valueString": "   ", "confidence": 0.9}, 0.9),
    (None, None),
])
def test_a_missing_value_is_not_found(field: dict[str, Any] | None, confidence: float | None) -> None:
    result = finding(mapping.map_result(minimal({"Vendor": field} if field else {"Other": {}}), [DETAIL]), "Vendor")
    assert (result["presence"], result["value"], result["clause"], result["page"]) == ("Not Found", "", "", None)
    assert result["confidence"] == confidence


# --- rights -----------------------------------------------------------------------------------------------------

def test_a_right_takes_judgment_clause_conditions_and_regions_from_its_parts(operation: dict[str, Any],
                                                                             items: list[dict[str, Any]]) -> None:
    aiml = finding(mapping.map_result(operation, items), "Right_AIML")
    parts = parts_of(operation)

    assert (aiml["presence"], aiml["judgment"]) == ("Found", "Prohibited")
    assert aiml["clause"] == parts["Clause"]["valueString"]
    assert aiml["conditions"] == aiml["value"] == parts["Conditions"]["valueString"]
    assert aiml["confidence"] == min(parts["Judgment"]["confidence"], parts["Clause"]["confidence"])
    assert aiml["sourceRegions"] == mapping.parse_source(parts["Clause"]["source"])
    assert aiml["page"] == 1


@pytest.mark.parametrize(("key", "judgment", "page"), [
    ("Right_InternalAnalytics", "Permitted", 1),
    ("Right_AIML", "Prohibited", 1),
    ("Right_Retention", "Conditional", 2),
    ("Right_ThirdPartySharing", "Prohibited", 2),
    ("Right_Destruction", "Conditional", 2),
])
def test_the_rights_the_contract_addresses_are_found_with_a_page(operation: dict[str, Any], items: list[dict[str, Any]],
                                                                 key: str, judgment: str, page: int) -> None:
    result = finding(mapping.map_result(operation, items), key)
    assert (result["presence"], result["judgment"], result["page"]) == ("Found", judgment, page)
    assert result["clause"] and result["sourceRegions"]


@pytest.mark.parametrize("key", NOT_ADDRESSED_KEYS)
def test_not_addressed_rights_keep_no_evidence(operation: dict[str, Any], items: list[dict[str, Any]], key: str) -> None:
    # CU still returns a title-region source and whole-document spans for this judgment; they are not evidence.
    judgment = parts_of(operation, key)["Judgment"]
    assert judgment["valueString"] == "Not Addressed" and judgment.get("source") and judgment.get("spans")

    result = finding(mapping.map_result(operation, items), key)

    assert (result["presence"], result["judgment"]) == ("Not Found", "Not Addressed")
    assert (result["clause"], result["value"], result["conditions"]) == ("", "", "")
    assert (result["page"], result["sourceRegions"]) == (None, [])
    assert result["confidence"] == judgment["confidence"]


def test_a_not_addressed_judgment_drops_a_contradicting_clause(operation: dict[str, Any],
                                                                items: list[dict[str, Any]]) -> None:
    parts_of(operation)["Judgment"]["valueString"] = "Not Addressed"
    result = finding(mapping.map_result(operation, items), "Right_AIML")
    assert (result["presence"], result["clause"], result["conditions"], result["sourceRegions"]) == ("Not Found", "", "", [])


@pytest.mark.parametrize(("text", "expected"), [
    ("prohibited", "Prohibited"), (" PERMITTED ", "Permitted"), ("Conditional", "Conditional"),
])
def test_judgments_are_normalised(operation: dict[str, Any], items: list[dict[str, Any]], text: str, expected: str) -> None:
    parts_of(operation)["Judgment"]["valueString"] = text
    result = finding(mapping.map_result(operation, items), "Right_AIML")
    assert (result["judgment"], result["presence"]) == (expected, "Found")


def test_an_unknown_judgment_is_unclear_and_blank(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    parts_of(operation)["Judgment"]["valueString"] = "Maybe"
    result = finding(mapping.map_result(operation, items), "Right_AIML")
    assert (result["presence"], result["judgment"]) == ("Unclear", "")
    assert result["clause"] and result["sourceRegions"]


def test_a_right_without_a_clause_is_unclear_and_points_at_the_judgments_source(operation: dict[str, Any],
                                                                                items: list[dict[str, Any]]) -> None:
    parts = parts_of(operation)
    del parts["Clause"]
    result = finding(mapping.map_result(operation, items), "Right_AIML")

    assert (result["presence"], result["judgment"], result["clause"]) == ("Unclear", "Prohibited", "")
    assert result["sourceRegions"] == mapping.parse_source(parts["Judgment"]["source"]) != []


def test_the_weakest_part_sets_a_rights_confidence(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    parts_of(operation)["Clause"]["confidence"] = 0.5
    result = finding(mapping.map_result(operation, items), "Right_AIML")
    assert (result["presence"], result["confidence"]) == ("Unclear", 0.5)


def test_a_part_without_confidence_leaves_the_right_unclear(operation: dict[str, Any], items: list[dict[str, Any]]) -> None:
    del parts_of(operation)["Judgment"]["confidence"]
    result = finding(mapping.map_result(operation, items), "Right_AIML")
    assert (result["presence"], result["confidence"]) == ("Unclear", None)


@pytest.mark.parametrize("edit", [
    lambda fields: fields.update(Right_AIML={"type": "object", "valueObject": {}}),
    lambda fields: fields.update(Right_AIML={"type": "object"}),
    lambda fields: fields.pop("Right_AIML"),
], ids=["empty parts", "no parts", "no field"])
def test_a_right_with_nothing_returned_is_not_found_with_a_blank_judgment(operation: dict[str, Any],
                                                                          items: list[dict[str, Any]], edit: Any) -> None:
    edit(fields_of(operation))
    result = finding(mapping.map_result(operation, items), "Right_AIML")
    assert (result["presence"], result["judgment"], result["clause"], result["page"]) == ("Not Found", "", "", None)


def test_a_scalar_right_means_the_flat_analyzer_is_deployed() -> None:
    flat = {"Right_AIML": string_field("Prohibited")}
    with pytest.raises(mapping.MappingError, match="nested analyzer"):
        mapping.map_result(minimal(flat), [RIGHT])


# --- results that are not from the checklist analyzer ----------------------------------------------------------

@pytest.mark.parametrize(("edit", "message"), [
    (lambda op: op.clear(), "no content"),
    (lambda op: op["result"].update(contents=[]), "no content"),
    (lambda op: op["result"]["contents"].__setitem__(0, "text"), "no content"),
    (lambda op: op["result"]["contents"][0].update(fields={}), "no fields"),
    (lambda op: op["result"]["contents"][0].pop("fields"), "no fields"),
    (lambda op: op["result"]["contents"][0]["fields"].update(Vendor="Acme"), "not a field object"),
])
def test_results_that_are_not_checklist_results_are_rejected(operation: dict[str, Any], items: list[dict[str, Any]],
                                                             edit: Any, message: str) -> None:
    edit(operation)
    with pytest.raises(mapping.MappingError, match=message):
        mapping.map_result(operation, items)


# --- source parsing and quotes ----------------------------------------------------------------------------------

def test_parse_source_reads_every_segment() -> None:
    regions = mapping.parse_source(f"{segment(1)}; {segment(2, 3)}")
    assert [region["page"] for region in regions] == [1, 2]
    assert regions[1]["polygon"] == [3.0, 0.0, 4.0, 0.0, 4.0, 1.0, 3.0, 1.0]


def test_parse_source_reads_negative_and_fractional_numbers() -> None:
    [region] = mapping.parse_source("D(3,-0.5,1.25,2,1,2,2,1,2)")
    assert (region["page"], region["polygon"][:2]) == (3, [-0.5, 1.25])


@pytest.mark.parametrize("source", [
    None, "", "junk", "D(1,1,2,3)", "D(1,1,1,2,1,2,2,1,2,9)", "D(x,0,0,1,0,1,1,0,1)", f"{segment(1)} trailing",
])
def test_parse_source_skips_what_it_cannot_read(source: str | None) -> None:
    assert mapping.parse_source(source) == []


def test_parse_source_skips_junk_between_good_segments() -> None:
    assert [region["page"] for region in mapping.parse_source(f"junk;{segment(1)};D(9);{segment(4)}")] == [1, 4]


def test_parse_source_caps_the_regions() -> None:
    regions = mapping.parse_source(";".join(segment(1) for _ in range(mapping.MAX_REGIONS + 10)))
    assert len(regions) == mapping.MAX_REGIONS


def test_quotes_are_unescaped_and_stripped_of_markup() -> None:
    first = "1\\. Term\\. This SOW <!-- PageBreak -->   expires."
    second = "Later text here."
    markdown = f"{first}\n\n{second}"
    spans = [{"offset": 0, "length": len(first)}, {"offset": markdown.index(second), "length": len(second)}]
    field = string_field("x", spans=spans)

    result = finding(mapping.map_result(minimal({"Vendor": field}, markdown), [DETAIL]), "Vendor")

    assert result["clause"] == "1. Term. This SOW expires. ... Later text here."


@pytest.mark.parametrize("spans", [None, [], [{"offset": -1, "length": 5}], [{"offset": 0, "length": 0}], ["x"],
                                   [{"offset": 500, "length": 5}]])
def test_a_clause_falls_back_to_the_value_when_no_span_resolves(spans: Any) -> None:
    field = string_field("Acme", spans=spans) if spans is not None else string_field("Acme")
    result = finding(mapping.map_result(minimal({"Vendor": field}, "short"), [DETAIL]), "Vendor")
    assert result["clause"] == "Acme"


def test_long_text_is_capped_to_fit_the_dataverse_columns() -> None:
    long_text = "x" * (mapping.MAX_TEXT + 500)
    result = finding(mapping.map_result(minimal({"Vendor": string_field(long_text)}), [DETAIL]), "Vendor")
    assert len(result["value"]) == len(result["clause"]) == mapping.MAX_TEXT
    assert result["value"].endswith("...")


def test_the_text_cap_stays_under_every_column_it_protects() -> None:
    schema = json.loads((ROOT / "dataverse" / "schema.json").read_text(encoding="utf-8"))
    limits: dict[str, int] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("name") in ("vz_aivalue", "vz_aiconditions", "vz_clause") and "max_length" in node:
                limits[node["name"]] = node["max_length"]
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(schema)
    assert set(limits) == {"vz_aivalue", "vz_aiconditions", "vz_clause"}
    assert mapping.MAX_TEXT < min(limits.values())


# --- raw, completeness, settings, checklist ---------------------------------------------------------------------

def test_raw_keeps_fields_usage_and_geometry_but_not_the_document_text(operation: dict[str, Any],
                                                                       items: list[dict[str, Any]]) -> None:
    raw = mapping.map_result(operation, items)["raw"]

    assert (raw["analyzerId"], raw["apiVersion"], raw["unit"]) == ("vizientContractChecklist", "2025-11-01", "inch")
    assert raw["usage"] == operation["usage"] and raw["usage"]["documentPagesStandard"] == 2
    assert raw["pages"] == [{"pageNumber": 1, "width": 8.5, "height": 11}, {"pageNumber": 2, "width": 8.5, "height": 11}]
    assert raw["fields"] == fields_of(operation)
    assert raw["warnings"] == []
    assert "markdown" not in raw and "IN WITNESS WHEREOF" not in json.dumps(raw)


def test_completeness_counts_only_the_analyzer_items(items: list[dict[str, Any]]) -> None:
    assert len(items) == 20 and {item["source"] for item in items} == {"analyzer"}
    assert items[0]["key"] == "Vendor"


def test_a_checklist_without_analyzer_items_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "checklist.json"
    path.write_text(json.dumps({"items": [{"key": "ContractOwner", "source": "manual"}]}), encoding="utf-8")
    with pytest.raises(mapping.MappingError, match="no analyzer items"):
        mapping.load_checklist(path)


@pytest.mark.parametrize(("text", "expected"), [
    (None, 0.8), ("", 0.8), ("0.9", 0.9), ("1", 1.0), ("0.01", 0.01),
    ("0", 0.8), ("-1", 0.8), ("1.5", 0.8), ("abc", 0.8), ("nan", 0.8), ("inf", 0.8),
])
def test_high_conf_comes_from_a_sane_number_or_the_default(text: str | None, expected: float) -> None:
    assert mapping.parse_high_conf(text) == expected


def test_the_function_ships_the_checklist_the_repository_defines() -> None:
    source = json.loads((ROOT / "checklist" / "checklist.json").read_text(encoding="utf-8"))
    shipped = json.loads((ROOT / "function" / "checklist.json").read_text(encoding="utf-8"))
    assert shipped == source, "function\\checklist.json is stale. Run: Copy-Item checklist\\checklist.json function\\checklist.json"
