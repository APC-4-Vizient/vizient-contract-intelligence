"""Offline tests for scripts/provision-flow.py: the solution ends up holding the flows and what they need, and a rerun writes nothing."""

from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import flowlib  # noqa: E402
import schemalib  # noqa: E402
from dvweb import DataverseError  # noqa: E402

_spec = importlib.util.spec_from_file_location("provision_flow", SCRIPTS / "provision-flow.py")
provision = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = provision  # a dataclass resolves its string annotations through sys.modules
_spec.loader.exec_module(provision)

SECRET = "not-a-real-function-key"
ENV = {
    "SHAREPOINT_SITE_URL": "https://example.sharepoint.com/",
    "SHAREPOINT_LIBRARY_ID": "11111111-2222-3333-4444-555555555555",
    "SHAREPOINT_INTAKE_FOLDER": "/Shared Documents/Contract Intake",
    "SHAREPOINT_CONNECTION_NAME": "sharepoint-connection-1",
    "DATAVERSE_CONNECTION_NAME": "dataverse-connection-1",
}
ID_COLUMNS = {
    "environmentvariabledefinitions": "environmentvariabledefinitionid",
    "environmentvariablevalues": "environmentvariablevalueid",
    "connectionreferences": "connectionreferenceid",
    "workflows": "workflowid",
}
SPECS = flowlib.flow_specs(schemalib.load_schema())


class Write(NamedTuple):
    method: str
    path: str
    body: dict[str, Any]
    headers: dict[str, str]
    solution: bool


class Created:
    def __init__(self, entity_set: str, row_id: str) -> None:
        self.headers = {"OData-EntityId": f"https://example.crm.dynamics.test/api/data/v9.2/{entity_set}({row_id})"}


class FakeDataverse:
    """The four tables the script writes, in memory. It never deletes, and a create that is not in the solution fails."""

    def __init__(self, *, account: str = "admin@example.test", refuse_to_turn_on: str | None = None) -> None:
        self.base_url = "https://example.crm.dynamics.test"
        self.account = account
        self.refuse_to_turn_on = refuse_to_turn_on
        self.tables: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in ID_COLUMNS}
        self.writes: list[Write] = []

    def whoami(self) -> dict[str, Any]:
        return {"UserId": "user-1"}

    def get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        assert path == "systemusers(user-1)", f"unexpected GET {path}"
        return {"domainname": self.account, "internalemailaddress": self.account}

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        return iter([dict(row) for row in self.tables[path].values()])

    def request(self, method: str, path: str, *, body: dict[str, Any] | None = None, headers: dict[str, str] | None = None,
                solution: bool = False) -> Created | None:
        assert method in ("POST", "PATCH"), f"{method} {path}: this script never deletes"
        body = body or {}
        self.writes.append(Write(method, path, body, headers or {}, solution))
        if method == "POST":
            assert solution, f"POST {path} was not made inside the solution"
            row_id = f"{path}-{len(self.tables[path]) + 1}"
            stored = dict(body)
            bind = stored.pop("EnvironmentVariableDefinitionId@odata.bind", None)
            if bind:
                stored[provision.DEFINITION_OF_VALUE] = bind.removeprefix("/environmentvariabledefinitions(").removesuffix(")")
            self.tables[path][row_id] = {ID_COLUMNS[path]: row_id, **stored}
            return Created(path, row_id)
        assert (headers or {}).get("If-Match") == "*", "a PATCH must not be able to create a row"
        entity_set, _, row_id = path.partition("(")
        if body.get("statecode") == 1 and self.refuse_to_turn_on:
            raise DataverseError(400, "0x80060467", self.refuse_to_turn_on, method, path)
        self.tables[entity_set][row_id.removesuffix(")")].update(body)
        return None

    def reset_affinity(self) -> None:
        pass

    def rows(self, entity_set: str) -> list[dict[str, Any]]:
        return list(self.tables[entity_set].values())

    def flow(self, name: str) -> dict[str, Any]:
        return next(row for row in self.rows("workflows") if row["name"] == name)


def settings(**changes: str) -> Any:
    return provision.read_settings({**ENV, **changes}, "https://func-test.azurewebsites.net", SECRET)


def run(dv: FakeDataverse, apply: bool = True, **changes: str) -> tuple[bool, list[str]]:
    lines: list[str] = []
    return provision.reconcile(dv, settings(**changes), SPECS, apply=apply, log=lines.append), lines


def filled() -> FakeDataverse:
    dv = FakeDataverse()
    run(dv)
    dv.writes.clear()
    return dv


# --- what gets written ---------------------------------------------------------------------------------------------

def test_an_empty_environment_is_filled_inside_the_solution_and_a_second_run_writes_nothing() -> None:
    dv = FakeDataverse()
    in_sync, _lines = run(dv)
    assert in_sync
    created = [write for write in dv.writes if write.method == "POST"]
    assert Counter(write.path for write in created) == {"environmentvariabledefinitions": 5, "environmentvariablevalues": 5,
                                                        "connectionreferences": 2, "workflows": 4}
    assert all(write.solution for write in created)
    assert [row["statecode"] for row in dv.rows("workflows")] == [1] * len(SPECS)
    dv.writes.clear()
    assert run(dv)[0]
    assert dv.writes == []


def test_each_value_belongs_to_its_own_definition() -> None:
    dv = filled()
    definitions = {row["environmentvariabledefinitionid"]: row["schemaname"] for row in dv.rows("environmentvariabledefinitions")}
    values = {definitions[row[provision.DEFINITION_OF_VALUE]]: row["value"] for row in dv.rows("environmentvariablevalues")}
    assert values == settings().values
    assert {row["type"] for row in dv.rows("environmentvariabledefinitions")} == {flowlib.ENVIRONMENT_VARIABLE_TEXT}


def test_each_connection_reference_points_at_the_connection_named_in_env() -> None:
    held = {row["connectionreferencelogicalname"]: row for row in filled().rows("connectionreferences")}
    assert held["vz_sharepointonline"]["connectionid"] == ENV["SHAREPOINT_CONNECTION_NAME"]
    assert held["vz_dataverse"]["connectionid"] == ENV["DATAVERSE_CONNECTION_NAME"]
    assert {row["connectorid"] for row in held.values()} == {ref.connector_id for ref in flowlib.CONNECTION_REFS}


def test_nothing_that_is_printed_gives_away_a_value() -> None:
    _in_sync, lines = run(FakeDataverse())
    text = "\n".join(lines)
    assert text
    for value in settings().values.values():
        assert value not in text
    assert SECRET not in repr(settings())


# --- reruns --------------------------------------------------------------------------------------------------------

def test_a_rotated_key_rewrites_only_that_value() -> None:
    dv = filled()
    key_value = next(row for row in dv.rows("environmentvariablevalues") if row["schemaname"].startswith("vz_FunctionKey"))
    key_value["value"] = "an-older-key"
    run(dv)
    assert [(write.method, write.body) for write in dv.writes] == [("PATCH", {"value": SECRET})]


def test_a_changed_flow_is_switched_off_rewritten_and_switched_on_in_that_order() -> None:
    dv = filled()
    flow = dv.flow(flowlib.ANALYSIS_FLOW)
    flow["description"] = flow["description"].replace("[definition ", "[definition 0")
    assert run(dv)[0]
    assert [sorted(write.body) for write in dv.writes] == [["statecode", "statuscode"], ["clientdata", "description", "name"],
                                                           ["statecode", "statuscode"]]
    assert [write.body.get("statecode") for write in dv.writes] == [0, None, 1]
    assert dv.flow(flowlib.ANALYSIS_FLOW)["description"].endswith(next(s.tag for s in SPECS if s.name == flowlib.ANALYSIS_FLOW))


def test_a_flow_that_was_switched_off_is_only_switched_on() -> None:
    dv = filled()
    dv.flow(flowlib.INTAKE_FLOW)["statecode"] = 0
    assert run(dv)[0]
    assert [write.body for write in dv.writes] == [provision.ON]


def test_status_reports_a_difference_without_writing() -> None:
    dv = FakeDataverse()
    in_sync, lines = run(dv, apply=False)
    assert not in_sync and dv.writes == []
    assert any(line.startswith("  create") and "vz_FunctionKey" in line for line in lines)
    run(dv)
    assert run(dv, apply=False)[0]


# --- failures ------------------------------------------------------------------------------------------------------

def test_a_flow_that_will_not_turn_on_is_explained_and_stays_saved() -> None:
    dv = FakeDataverse(refuse_to_turn_on="The connection reference vz_dataverse is not bound to a connection.")
    with pytest.raises(provision.ProvisionError, match="saved in the solution but would not turn on.*vz_dataverse is not bound"):
        run(dv)
    assert [row["statecode"] for row in dv.rows("workflows")][:1] == [0]


def test_duplicate_rows_stop_the_run_before_any_write() -> None:
    dv = filled()
    duplicate = dict(dv.rows("environmentvariabledefinitions")[0], environmentvariabledefinitionid="another")
    dv.tables["environmentvariabledefinitions"]["another"] = duplicate
    with pytest.raises(provision.ProvisionError, match="more than one environment variable"):
        run(dv)
    assert dv.writes == []


def test_a_write_that_does_not_take_effect_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def never_settles(*_args: Any, **_kwargs: Any) -> None:
        raise TimeoutError("waited")

    monkeypatch.setattr(provision, "wait_for", never_settles)
    with pytest.raises(provision.ProvisionError, match="still differs"):
        run(FakeDataverse())


def test_only_the_account_named_in_env_may_write() -> None:
    dv = FakeDataverse(account="Admin@Example.test")
    assert provision.check_account(dv, "admin@example.test") == "Admin@Example.test"
    assert provision.check_account(dv, None) == "Admin@Example.test"
    with pytest.raises(provision.ProvisionError, match="signed in as Admin@Example.test"):
        provision.check_account(dv, "someone.else@example.test")


BAD_SETTINGS = {
    "a missing setting": ({"SHAREPOINT_LIBRARY_ID": ""}, "set SHAREPOINT_LIBRARY_ID"),
    "a site that is not SharePoint": ({"SHAREPOINT_SITE_URL": "https://example.com"}, "sharepoint.com"),
    "a site without https": ({"SHAREPOINT_SITE_URL": "http://example.sharepoint.com"}, "https"),
    "a library that is not a GUID": ({"SHAREPOINT_LIBRARY_ID": "Documents"}, "GUID"),
    "a folder without a leading slash": ({"SHAREPOINT_INTAKE_FOLDER": "Shared Documents/Contract Intake"}, "must start with /"),
    "a connection name with a path in it": ({"DATAVERSE_CONNECTION_NAME": "../other"}, "DATAVERSE_CONNECTION_NAME"),
}


@pytest.mark.parametrize("changes, expected", BAD_SETTINGS.values(), ids=BAD_SETTINGS.keys())
def test_a_setting_that_would_send_the_flows_to_the_wrong_place_is_refused(changes: dict[str, str], expected: str) -> None:
    with pytest.raises(provision.ProvisionError, match=expected) as caught:
        settings(**changes)
    assert SECRET not in str(caught.value)


def test_a_missing_function_key_is_refused() -> None:
    with pytest.raises(provision.ProvisionError, match="no key"):
        provision.read_settings(ENV, "https://func-test.azurewebsites.net", "")


def test_without_a_flag_nothing_is_sent(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("the offline run must not connect to Dataverse")

    monkeypatch.setattr(provision, "Dataverse", forbidden)
    assert provision.main([]) == 0
    out = capsys.readouterr().out
    assert all(f"{spec.name}: valid" in out for spec in SPECS)
