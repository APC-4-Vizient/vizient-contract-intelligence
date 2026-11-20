"""Offline tests for scripts/flowlib.py: the two cloud flows agree with dataverse/schema.json and with the Function API.

Nothing is sent anywhere. Whether Power Automate accepts the definitions is proven by provision-flow.py --apply.
"""

from __future__ import annotations

import copy
import json
import math
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "function"))

import checklistlib  # noqa: E402
import flowlib  # noqa: E402
import mapping  # noqa: E402
import schemalib  # noqa: E402

SCHEMA = schemalib.load_schema()
SPECS = flowlib.flow_specs(SCHEMA)
INTAKE_SPEC = next(spec for spec in SPECS if spec.name == flowlib.INTAKE_FLOW)
INTAKE = INTAKE_SPEC.definition
ANALYSIS = next(spec for spec in SPECS if spec.name == flowlib.ANALYSIS_FLOW).definition
STATUS = flowlib.choice_values(SCHEMA, "vz_contract", "vz_status")
SOW_RESULT = ROOT / "tests" / "fixtures" / "cu_result_sow.json"
PARAMETER_BUILTINS = {"$connections", "$authentication"}


def actions_of(flow: dict[str, Any], kind: str | None = None) -> dict[str, dict[str, Any]]:
    return {name: action for _siblings, name, action in flowlib.walk_actions(flow["actions"])
            if kind is None or action["type"] == kind}


def edited(flow: dict[str, Any], change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    clone = copy.deepcopy(flow)
    change(clone)
    return clone


def written_statuses(flow: dict[str, Any]) -> set[int]:
    """Every vz_status value a flow writes to a contract."""
    return {action["inputs"]["parameters"]["item/vz_status"] for action in actions_of(flow, "OpenApiConnection").values()
            if "item/vz_status" in action["inputs"]["parameters"]}


# --- the definitions agree with the schema ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_a_definition_has_nothing_the_schema_or_the_flow_language_rejects(spec: flowlib.FlowSpec) -> None:
    assert flowlib.problems(spec.definition, SCHEMA) == []


def _drop_secure_inputs(flow: dict[str, Any]) -> None:
    del actions_of(flow)["Submit_analysis"]["runtimeConfiguration"]


def _async_pattern_on(flow: dict[str, Any]) -> None:
    del actions_of(flow)["Poll_analysis"]["operationOptions"]


def _hard_coded_function(flow: dict[str, Any]) -> None:
    actions_of(flow)["Poll_analysis"]["inputs"]["uri"] = "https://func-test.azurewebsites.net/api/contracts/analyze"


def _reference_to_nothing(flow: dict[str, Any]) -> None:
    actions_of(flow)["Maps"]["inputs"]["x"] = "@outputs('Nowhere')"


def _unbalanced_expression(flow: dict[str, Any]) -> None:
    actions_of(flow)["Maps"]["inputs"]["x"] = "@concat('a', outputs('Maps')"


def _unknown_column(flow: dict[str, Any]) -> None:
    actions_of(flow)["Update_contract"]["inputs"]["parameters"]["item/vz_nope"] = "x"


def _unknown_lookup(flow: dict[str, Any]) -> None:
    actions_of(flow)["Add_finding"]["inputs"]["parameters"]["item/vz_nope@odata.bind"] = "x"


def _unknown_filter_column(flow: dict[str, Any]) -> None:
    next(iter(flow["triggers"].values()))["inputs"]["parameters"]["subscriptionRequest/filteringattributes"] = "vz_nope"


def _run_after_nothing(flow: dict[str, Any]) -> None:
    actions_of(flow)["Maps"]["runAfter"] = {"Nowhere": ["Succeeded"]}


def _set_unknown_variable(flow: dict[str, Any]) -> None:
    actions_of(flow)["Record_poll_status"]["inputs"]["name"] = "nope"


PROBLEMS = {
    "secure inputs dropped": (_drop_secure_inputs, "must be secured"),
    "async pattern on": (_async_pattern_on, "asynchronous pattern must be off"),
    "function address written in": (_hard_coded_function, "environment-specific value"),
    "reference to an action that is not there": (_reference_to_nothing, "names something the flow does not have"),
    "unbalanced expression": (_unbalanced_expression, "unbalanced"),
    "column that is not in the schema": (_unknown_column, "item/vz_nope is not a column of vz_contract"),
    "lookup that is not in the schema": (_unknown_lookup, "is not a lookup of vz_finding"),
    "trigger column that is not in the schema": (_unknown_filter_column, "filters on a column the table does not have"),
    "runAfter an action that is not there": (_run_after_nothing, "is not an action next to it"),
    "variable that is never initialized": (_set_unknown_variable, "never initialized"),
}


@pytest.mark.parametrize("change, expected", PROBLEMS.values(), ids=PROBLEMS.keys())
def test_a_broken_definition_is_reported(change: Callable[[dict[str, Any]], None], expected: str) -> None:
    assert any(expected in line for line in flowlib.problems(edited(ANALYSIS, change), SCHEMA))


# --- the flows fit together ------------------------------------------------------------------------------------------

def test_the_analysis_flow_cannot_queue_itself_again() -> None:
    """Setting vz_status to Extracting is what starts an analysis, so the flow that analyzes never sets it."""
    (trigger,) = ANALYSIS["triggers"].values()
    parameters = trigger["inputs"]["parameters"]
    assert parameters["subscriptionRequest/filteringattributes"] == "vz_status"
    assert parameters["subscriptionRequest/filterexpression"] == f"vz_status eq {STATUS['Extracting']}"
    assert written_statuses(ANALYSIS) == {STATUS["Ready for Review"], STATUS["Failed"]}
    assert written_statuses(INTAKE) == {STATUS["Extracting"], STATUS["Failed"]}


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_each_connector_has_a_connection_reference(spec: flowlib.FlowSpec) -> None:
    references = json.loads(spec.client_data)["properties"]["connectionReferences"]
    used = flowlib.connectors_used(spec.definition)
    logical = {ref.connector: ref.logical_name for ref in flowlib.CONNECTION_REFS}
    assert sorted(references) == used
    assert {key: ref["connection"]["connectionReferenceLogicalName"] for key, ref in references.items()} == \
           {connector: logical[connector] for connector in used}


def test_every_environment_variable_is_read_by_a_flow_and_every_other_parameter_is_one() -> None:
    declared = {variable.parameter for variable in flowlib.ENV_VARS}
    read: set[str] = set()
    for flow in (INTAKE, ANALYSIS):
        parameters = set(flow["parameters"]) - PARAMETER_BUILTINS
        assert parameters <= declared
        read |= parameters
    assert read == declared


def test_the_size_guard_rejects_what_the_download_may_have_cut_short() -> None:
    """The Dataverse connector returns the first 4 MiB of a file column. Base64 text is 4 characters per 3 bytes."""
    four_mib = 4 * 1024 * 1024
    base64_length = lambda size: 4 * math.ceil(size / 3)  # noqa: E731
    assert base64_length(four_mib - 1) < flowlib.DOWNLOAD_LIMIT_BASE64 <= base64_length(four_mib)
    (guard,) = actions_of(ANALYSIS)["Check_document_size"]["expression"]["and"]
    assert guard["less"][1] == flowlib.DOWNLOAD_LIMIT_BASE64


# --- the flow reads what the Function returns ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def payload() -> dict[str, Any]:
    return mapping.map_result(json.loads(SOW_RESULT.read_text(encoding="utf-8")), mapping.load_checklist())


def test_the_flow_reads_only_fields_the_function_returns(payload: dict[str, Any]) -> None:
    text = json.dumps(ANALYSIS)
    contract_fields = set(re.findall(r"outputs\('Parsed_result'\)\?\['contract'\]\?\['(\w+)'\]", text))
    finding_fields = set(re.findall(r"items\('Add_findings'\)\?\['(\w+)'\]", text))
    assert contract_fields and finding_fields
    assert contract_fields <= set(payload["contract"])
    assert finding_fields <= set(payload["findings"][0])


def test_the_maps_cover_every_answer_the_function_can_give() -> None:
    maps = actions_of(ANALYSIS)["Maps"]["inputs"]
    document_types = next(item for item in mapping.load_checklist() if item["key"] == "DocumentType")["enum"]
    assert {mapping.FOUND, mapping.UNCLEAR, mapping.NOT_FOUND} <= set(maps["presence"])
    assert {*mapping.JUDGMENTS.values(), mapping.NOT_APPLICABLE} <= set(maps["judgment"])
    assert set(document_types) <= set(maps["documentType"])


def test_every_finding_binds_to_a_checklist_row_that_is_seeded() -> None:
    seeded = {row["vz_key"] for row in checklistlib.seed_rows(checklistlib.load_checklist(schema=SCHEMA), SCHEMA)}
    assert {item["key"] for item in mapping.load_checklist()} <= seeded


# --- what is stored in Dataverse -------------------------------------------------------------------------------------

def test_the_description_tells_a_changed_definition_from_a_current_one() -> None:
    def queue_as_received(flow: dict[str, Any]) -> None:
        actions_of(flow)["Queue_analysis"]["inputs"]["parameters"]["item/vz_status"] = STATUS["Received"]

    changed = flowlib.FlowSpec(INTAKE_SPEC.name, INTAKE_SPEC.summary, edited(INTAKE, queue_as_received))
    rebuilt = next(spec for spec in flowlib.flow_specs(SCHEMA) if spec.name == INTAKE_SPEC.name)
    assert rebuilt.tag == INTAKE_SPEC.tag
    assert changed.tag != INTAKE_SPEC.tag
    assert INTAKE_SPEC.row["description"].endswith(INTAKE_SPEC.tag)


@pytest.mark.parametrize("spec", SPECS, ids=lambda spec: spec.name)
def test_the_workflow_row_is_a_modern_cloud_flow_holding_the_definition(spec: flowlib.FlowSpec) -> None:
    row = spec.row
    assert (row["category"], row["type"], row["primaryentity"]) == (5, 1, "none")
    assert json.loads(row["clientdata"])["properties"]["definition"] == json.loads(json.dumps(spec.definition))
