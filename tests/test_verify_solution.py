"""Offline tests for scripts/verify-solution.py: a lagging metadata API must not read as missing objects, and
anything in the solution that the project does not declare must fail."""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from collections.abc import Collection, Iterator
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


# --- the whole check, the export proof and the repairs ---------------------------------------------------------------

SOLUTION = "VizientContractPOC"
SOLUTION_ID = "bbbbbbbb-0000-0000-0000-000000000002"
USER = "cccccccc-0000-0000-0000-000000000003"
INTAKE_FLOW_ID = "dddddddd-0000-0000-0000-000000000004"


class Environment:
    """An environment where everything declared is built and inside the solution, and nothing else is. A test breaks one thing."""

    base_url = "https://example.crm.dynamics.test"

    def __init__(self, schema: dict[str, Any], *, exists: bool = True, managed: bool = False, prefix: str | None = None,
                 preferred: bool = True) -> None:
        self.schema = schema
        self.exists, self.managed, self.prefix, self.preferred = exists, managed, prefix or schema["publisher_prefix"], preferred
        self.tables = FakeDataverse(schema)
        self.solution = FakeSolution()
        for ctype, names in verify.declared_names(schema, {}).items():
            for name in sorted(names):
                if ctype in (verify.TABLE, verify.CHOICE):
                    self.add_metadata(ctype, name)
                else:
                    self.solution.add(ctype, name)
        self.solution.add(verify.CANVAS_APP, "Contract Review")
        self.outside: dict[str, list[dict[str, Any]]] = {}  # objects made since the solution that are not in it, by entity set
        self.actions: list[tuple[str, dict[str, Any]]] = []

    def add_metadata(self, ctype: int, name: str) -> None:
        entity_set, column = NAME_COLUMNS[ctype]
        object_id = f"{'table' if ctype == verify.TABLE else 'choice'}:{name}"  # the ids FakeDataverse gives them
        self.solution.components.append({"componenttype": ctype, "objectid": object_id, "rootcomponentbehavior": 0})
        self.solution.names[f"{entity_set}({object_id})"] = {column: name}

    def reset_affinity(self) -> None:
        pass

    def whoami(self) -> dict[str, Any]:
        return {"UserId": USER}

    def list(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        if path == "solutions":
            return iter([{"solutionid": SOLUTION_ID, "version": "1.0.0.0", "ismanaged": self.managed, "createdon": "2026-01-01T00:00:00Z",
                          "_publisherid_value": "publisher-1"}] if self.exists else [])
        if path == "solutioncomponents":
            return iter(self.solution.components)
        if path == "solutioncomponentdefinitions":
            return iter([])
        if path in {sweep[0] for sweep in verify.SWEEPS}:
            return iter(self.outside.get(path, []))
        return self.tables.list(path, params)

    def get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        if path.startswith("publishers("):
            return {"uniquename": "vizient", "customizationprefix": self.prefix}
        if path == "GetPreferredSolution()":
            return {"solutionid": SOLUTION_ID if self.preferred else "another-solution", "friendlyname": "Default Solution"}
        return self.solution.get(path, params, missing_ok=missing_ok)

    def action(self, name: str, body: dict[str, Any] | None = None, *, solution: bool = False) -> dict[str, Any]:
        body = body or {}
        self.actions.append((name, body))
        if name == "SetPreferredSolution":
            self.preferred = True
        elif name == "AddSolutionComponent":
            self.solution.components.append({"componenttype": body["ComponentType"], "objectid": body["ComponentId"],
                                             "rootcomponentbehavior": None})
            for entity_set, _primary, id_column, label_column, *_rest in verify.SWEEPS:
                for row in self.outside.get(entity_set, []):
                    if row[id_column] == body["ComponentId"]:
                        self.solution.names[f"{entity_set}({row[id_column]})"] = {label_column: row[label_column]}
        return {}

    def export_solution(self, unique_name: str, managed: bool = False) -> bytes:
        return build_export(self.schema)


def build_export(schema: dict[str, Any], skip: Collection[str] = ()) -> bytes:
    """A solution export that holds every declared object except the ones named in skip: "table T", "column T.C", "key K",
    "relationship R" or "choice C"."""
    tables = [table for table in schema["tables"] if f"table {table['name']}" not in skip]
    choices = [choice for choice in schema["global_choices"] if f"choice {choice['name']}" not in skip]
    entities = "".join(
        f"<Entity><Name>{table['name']}</Name><EntityInfo><entity><attributes>"
        + "".join(f'<attribute PhysicalName="{column}"/>' for column in schemalib.column_names(schema, table)
                  if f"column {table['name']}.{column}" not in skip)
        + "</attributes></entity></EntityInfo>"
        + "".join(f"<EntityKeys><EntityKey><Name>{key['name']}</Name></EntityKey></EntityKeys>"
                  for key in schema["keys"] if key["table"] == table["name"] and f"key {key['name']}" not in skip)
        + "</Entity>" for table in tables)
    manifest = ("<ImportExportXml><SolutionManifest><RootComponents>"
                + "".join(f'<RootComponent type="{verify.CHOICE}" schemaName="{choice["name"]}"/>' for choice in choices)
                + "".join(f'<RootComponent type="{verify.TABLE}" schemaName="{table["name"]}"/>' for table in tables)
                + "</RootComponents></SolutionManifest></ImportExportXml>")
    customizations = (f"<ImportExportXml><Entities>{entities}</Entities><optionsets>"
                      + "".join(f'<optionset Name="{choice["name"]}"/>' for choice in choices)
                      + "</optionsets><EntityRelationships>"
                      + "".join(f'<EntityRelationship Name="{rel["name"]}"/>' for rel in schema["relationships"]
                                if f"relationship {rel['name']}" not in skip)
                      + "</EntityRelationships></ImportExportXml>")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("solution.xml", manifest)
        bundle.writestr("customizations.xml", customizations)
    return buffer.getvalue()


@pytest.fixture
def verify_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> Any:
    """Runs main() as `python scripts/verify-solution.py <flags>` would, against an environment. Returns the exit code and what it printed."""

    def run(env: Environment, *flags: str) -> tuple[int, str]:
        monkeypatch.setattr(verify, "Dataverse", lambda skill, solution: env)
        monkeypatch.setattr(sys, "argv", ["verify-solution.py", *flags])
        code = verify.main()
        return code, capsys.readouterr().out

    return run


def test_an_environment_where_everything_is_inside_the_solution_verifies(verify_main: Any, schema: dict[str, Any]) -> None:
    code, out = verify_main(Environment(schema))

    assert code == 0 and f"VERIFIED: everything checked is inside {SOLUTION}, and nothing else is." in out
    assert f"export of {SOLUTION} contains all {len(schema['tables'])} tables" in out and "FAIL" not in out


def test_a_solution_that_does_not_exist_fails_at_the_first_step_and_checks_nothing_else(verify_main: Any, schema: dict[str, Any]) -> None:
    code, out = verify_main(Environment(schema, exists=False))

    assert code == 1 and f"FAIL  solution {SOLUTION} does not exist" in out and "2. Declared schema" not in out


@pytest.mark.parametrize("changes, message", [
    ({"managed": True}, "is managed; this project builds in an unmanaged solution"),
    ({"prefix": "xx"}, "solution publisher prefix is xx, expected vz"),
])
def test_a_managed_solution_or_another_publisher_fails(verify_main: Any, schema: dict[str, Any], changes: dict[str, Any], message: str) -> None:
    code, out = verify_main(Environment(schema, **changes))

    assert code == 1 and message in out


def test_a_preferred_solution_that_is_not_this_one_fails_and_fix_sets_it(verify_main: Any, schema: dict[str, Any]) -> None:
    env = Environment(schema, preferred=False)

    code, out = verify_main(env)
    assert code == 1 and "preferred solution is 'Default Solution', so portal-made objects would land outside" in out
    assert env.actions == []

    code, out = verify_main(env, "--fix")
    assert code == 0 and env.actions == [("SetPreferredSolution", {"SolutionId": SOLUTION_ID})]
    assert f"set   preferred solution -> {SOLUTION}" in out


def test_a_flow_made_outside_the_solution_fails_and_fix_adds_it_with_that_component_type_and_id(verify_main: Any, schema: dict[str, Any]) -> None:
    env = Environment(schema)
    env.outside["workflows"] = [{"workflowid": INTAKE_FLOW_ID, "name": "Vizient Contract Intake"}]

    code, out = verify_main(env)
    assert code == 1 and "Cloud flow / process 'Vizient Contract Intake' (workflows) is not in the solution" in out
    assert "Run with --fix to repair what can be repaired; it adds objects and never removes one." in out
    assert env.actions == []

    code, out = verify_main(env, "--fix")
    assert code == 0 and "VERIFIED" in out
    assert env.actions == [("AddSolutionComponent", {"ComponentId": INTAKE_FLOW_ID, "ComponentType": verify.WORKFLOW,
                                                     "SolutionUniqueName": SOLUTION, "AddRequiredComponents": False})]


def test_a_table_is_added_with_its_subcomponents_and_nothing_else_is_given_that_flag() -> None:
    env = Environment(schemalib.load_schema())
    report = verify.Report()
    report.strays += [(verify.TABLE, "table-1", "table vz_x"), (verify.CHOICE, "choice-1", "global choice vz_y")]

    verify.apply_fixes(env, SOLUTION, SOLUTION_ID, report)

    assert [(body["ComponentType"], body.get("DoNotIncludeSubcomponents")) for _name, body in env.actions] == [
        (verify.TABLE, False), (verify.CHOICE, None)]


def test_an_export_that_holds_every_declared_object_passes(schema: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    report = verify.Report()

    verify.inspect_export(build_export(schema), schema, SOLUTION, report)

    columns = sum(len(schemalib.column_names(schema, table)) for table in schema["tables"])
    assert report.problems == [] and report.export_complete
    assert (f"contains all {len(schema['tables'])} tables, {columns} columns, {len(schema['keys'])} keys, "
            f"{len(schema['relationships'])} relationships and {len(schema['global_choices'])} global choices") in capsys.readouterr().out


def test_an_export_that_lacks_declared_objects_names_each_of_them(schema: dict[str, Any]) -> None:
    report = verify.Report()
    skip = {"choice vz_judgment", "column vz_finding.vz_clause", "key vz_checklistitem_key", "relationship vz_finding_contract"}

    verify.inspect_export(build_export(schema, skip), schema, SOLUTION, report)

    assert report.problems == [f"export of {SOLUTION} is missing {item}" for item in (
        "global choice vz_judgment", "column vz_finding.vz_clause", "key vz_checklistitem_key", "relationship vz_finding_contract")]
    assert not report.export_complete


def test_a_table_the_export_lacks_is_reported_once_and_not_column_by_column(schema: dict[str, Any]) -> None:
    report = verify.Report()

    verify.inspect_export(build_export(schema, {"table vz_finding"}), schema, SOLUTION, report)

    assert [problem for problem in report.problems if "vz_finding." in problem and problem.startswith("export")] == []
    assert f"export of {SOLUTION} is missing table vz_finding" in report.problems


def test_a_malformed_ignore_list_stops_the_run_before_the_environment_is_read(
        verify_main: Any, schema: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(verify.IGNORE_VARIABLE, "300")
    env = Environment(schema)

    code, out = verify_main(env)

    assert code == 1 and f"{verify.IGNORE_VARIABLE}: '300' is not TYPE:ID" in out and env.actions == []
