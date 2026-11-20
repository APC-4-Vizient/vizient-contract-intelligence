"""Offline tests for scripts/verify-solution.py: a lagging metadata API must not read as missing objects, and
anything in the solution that the project does not declare must fail."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import schemalib  # noqa: E402

_spec = importlib.util.spec_from_file_location("verify_solution", SCRIPTS / "verify-solution.py")
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

# The entity set and name column that identify each kind of component in the Dataverse Web API.
NAME_COLUMNS = {
    verify.TABLE: ("EntityDefinitions", "LogicalName"),
    verify.CHOICE: ("GlobalOptionSetDefinitions", "Name"),
    verify.WORKFLOW: ("workflows", "name"),
    verify.CONNECTION_REFERENCE: ("connectionreferences", "connectionreferencelogicalname"),
    verify.ENV_DEFINITION: ("environmentvariabledefinitions", "schemaname"),
    verify.ENV_VALUE: ("environmentvariablevalues", "schemaname"),
    verify.CANVAS_APP: ("canvasapps", "displayname"),
}
MINE = "0b9f6a52-3c1e-4d7a-8f20-5a6b7c8d9e01"
THEIRS = "7d41c3e8-92ab-4f06-b1d5-3e8a0c6f2b17"


class FakeDataverse:
    """Serves the metadata a healthy environment holds for schema.json. The first `stale_reads`
    snapshots of each table are what a lagging node returns: the primary column and nothing else."""

    def __init__(self, schema: dict[str, Any], stale_reads: int = 0) -> None:
        self.schema = schema
        self.stale_reads = stale_reads
        self.snapshots: dict[str, int] = {}
        self.resets = 0

    def reset_affinity(self) -> None:
        self.resets += 1

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        schema = self.schema
        if path == "GlobalOptionSetDefinitions":
            return iter([{"Name": c["name"], "MetadataId": f"choice:{c['name']}"} for c in schema["global_choices"]])
        if path == "EntityDefinitions":
            return iter([{"LogicalName": t["name"], "MetadataId": f"table:{t['name']}"} for t in schema["tables"]])
        table_name = path.split("'")[1]
        kind = path.rsplit("/", 1)[1]
        if kind == "Attributes":
            self.snapshots[table_name] = self.snapshots.get(table_name, 0) + 1
        stale = self.snapshots[table_name] <= self.stale_reads
        table = next(t for t in schema["tables"] if t["name"] == table_name)
        if kind == "Attributes":
            names = [table["primary"]["name"]] if stale else schemalib.column_names(schema, table)
            return iter([{"LogicalName": n, "MetadataId": f"column:{table_name}.{n}",
                          "IsCustomAttribute": True, "AttributeOf": None} for n in names])
        if kind == "Keys":
            keys = [] if stale else [k for k in schema["keys"] if k["table"] == table_name]
            return iter([{"SchemaName": k["name"], "MetadataId": f"key:{k['name']}",
                          "EntityKeyIndexStatus": "Active"} for k in keys])
        rels = [] if stale else [r for r in schema["relationships"] if r["referencing"] == table_name]
        return iter([{"SchemaName": r["name"], "MetadataId": f"rel:{r['name']}"} for r in rels])


@pytest.fixture
def schema() -> dict[str, Any]:
    return schemalib.load_schema()


@pytest.fixture(autouse=True)
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "METADATA_PAUSE", 0)


def check(schema: dict[str, Any], stale_reads: int) -> tuple[FakeDataverse, Any]:
    components = [{"componenttype": verify.TABLE, "objectid": f"table:{t['name']}", "rootcomponentbehavior": 0}
                  for t in schema["tables"]]
    components += [{"componenttype": verify.CHOICE, "objectid": f"choice:{c['name']}", "rootcomponentbehavior": 0}
                   for c in schema["global_choices"]]
    dv = FakeDataverse(schema, stale_reads)
    report = verify.Report()
    verify.check_declared(dv, schema, verify.Coverage(components), report)
    return dv, report


def test_complete_answer_is_read_once(schema: dict[str, Any]) -> None:
    dv, report = check(schema, stale_reads=0)
    assert report.problems == []
    assert dv.resets == 0
    assert set(dv.snapshots.values()) == {1}


def test_lagging_answer_is_re_read_through_fresh_sessions_and_reported(
        schema: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    dv, report = check(schema, stale_reads=2)
    assert report.problems == []
    assert dv.resets == 2 * len(schema["tables"])
    assert "answered incompletely 2 time(s)" in capsys.readouterr().out


def test_objects_that_stay_unlisted_still_fail(schema: dict[str, Any]) -> None:
    dv, report = check(schema, stale_reads=10**6)
    missing = (sum(len(schemalib.column_names(schema, t)) - 1 for t in schema["tables"])
               + len(schema["keys"]) + len(schema["relationships"]))
    assert len(report.problems) == report.unlisted_count == missing
    assert set(dv.snapshots.values()) == {verify.METADATA_READS}
    assert f"column vz_finding.vz_presence is not listed by the metadata API after {verify.METADATA_READS} reads" \
        in report.problems


class FakeSolution:
    """Serves the names of solution components and no component definitions, so the fallback type numbers apply."""

    def __init__(self) -> None:
        self.components: list[dict[str, Any]] = []
        self.names: dict[str, dict[str, str]] = {}

    def add(self, ctype: int, name: str) -> None:
        entity_set, column = NAME_COLUMNS[ctype]
        object_id = f"{entity_set}:{name}"
        self.components.append({"componenttype": ctype, "objectid": object_id, "rootcomponentbehavior": 0})
        self.names[f"{entity_set}({object_id})"] = {column: name}

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        return iter([])

    def get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        return self.names.get(path)


def declared_solution(schema: dict[str, Any]) -> FakeSolution:
    solution = FakeSolution()
    for ctype, names in verify.declared_names(schema, {}).items():
        for name in sorted(names):
            solution.add(ctype, name)
    solution.add(verify.CANVAS_APP, "Contract Review")
    return solution


def contents(solution: FakeSolution, schema: dict[str, Any]) -> Any:
    report = verify.Report()
    verify.check_contents(solution, schema, solution.components, report)
    return report


def test_a_solution_holding_only_what_the_project_declares_is_clean(schema: dict[str, Any]) -> None:
    solution = declared_solution(schema)
    assert len(solution.components) == 23
    assert contents(solution, schema).problems == []


def test_a_component_the_project_does_not_declare_fails_by_name(schema: dict[str, Any]) -> None:
    solution = declared_solution(schema)
    solution.add(verify.CONNECTION_REFERENCE, "vz_other.cr.shared_x")
    assert contents(solution, schema).problems == [
        "Connection reference 'vz_other.cr.shared_x' is in the solution but this project does not declare it"]


def test_a_component_type_the_project_never_adds_fails(schema: dict[str, Any]) -> None:
    solution = declared_solution(schema)
    solution.components.append({"componenttype": 10233, "objectid": MINE, "rootcomponentbehavior": 0})
    assert contents(solution, schema).problems == [
        f"Component of type 10233 {MINE} is in the solution but this project does not declare it"]


def test_a_second_code_app_fails(schema: dict[str, Any]) -> None:
    solution = declared_solution(schema)
    solution.add(verify.CANVAS_APP, "Another app")
    problems = contents(solution, schema).problems
    assert len(problems) == 1 and problems[0].startswith("2 Code Apps are in the solution")


def test_ignore_list_holds_type_and_id_pairs() -> None:
    assert verify.parse_ignore(f" 10163:{THEIRS.upper()}, 300:{MINE},") == {(10163, THEIRS), (300, MINE)}
    assert verify.parse_ignore("") == frozenset()


@pytest.mark.parametrize("text", ["300", f"app:{MINE}", "300:not-a-guid"])
def test_a_malformed_ignore_entry_is_an_error_rather_than_a_silent_pass(text: str) -> None:
    with pytest.raises(ValueError):
        verify.parse_ignore(text)


def test_ignored_objects_are_skipped_aloud_and_the_rest_still_fail(capsys: pytest.CaptureFixture[str]) -> None:
    rows = {"canvasapps": [{"canvasappid": THEIRS, "displayname": "Someone else's app"},
                           {"canvasappid": MINE, "displayname": "Our stray"}]}

    class Sweep:
        def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
            return iter(rows.get(path, []))

    report = verify.Report()
    verify.sweep_strays(Sweep(), {"createdon": "2026-01-01T00:00:00Z"}, verify.Coverage([]), None, report,
                        {(verify.CANVAS_APP, THEIRS)})
    assert [object_id for _, object_id, _ in report.strays] == [MINE]
    out = capsys.readouterr().out
    assert "Someone else's app" in out and f"skipped because it is listed in {verify.IGNORE_VARIABLE}" in out
