"""Offline tests for scripts/provision-dataverse.py. The provisioner runs through the real client (scripts/dvweb.py) against an in-memory
Dataverse that answers as the Web API does: a metadata create needs a parent that exists and is visible, a duplicate is refused, and the
solution a create lands in is whatever its MSCRM.SolutionUniqueName header says. Nothing is sent to a network."""

from __future__ import annotations

import copy
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dvweb  # noqa: E402
import schemalib  # noqa: E402
from loadscript import load_script  # noqa: E402

provision = load_script("provision-dataverse.py", "provision_dataverse")

BASE = "https://example.crm.dynamics.test"
API = f"{BASE}/api/data/v9.2"
SOLUTION = "VizientContractPOC"
PUBLISHER_ID = "aaaaaaaa-0000-0000-0000-000000000001"
ENTITY_PATH = re.compile(r"EntityDefinitions\(LogicalName='(.+?)'\)(?:/(\w+))?")


class Clock:
    """Stands in for the time module in the client and the provisioner. It moves only when the code sleeps, so waiting costs nothing."""

    def __init__(self) -> None:
        self.now = 1_000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class Reply:
    """The parts of a requests.Response that the client reads."""

    def __init__(self, status: int = 204, body: Any = None, headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.text = "" if body is None else json.dumps(body)
        self.content = self.text.encode()

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("the response has no JSON body")
        return self._body


def refused(status: int, message: str) -> Reply:
    return Reply(status, {"error": {"code": "0x80060888", "message": message}})


@dataclass
class Attempt:
    label: str
    solution: str | None  # what the MSCRM.SolutionUniqueName header said, or None when there was none


class Table:
    def __init__(self, table_id: str, hidden_reads: int = 0) -> None:
        self.id = table_id
        self.hidden_reads = hidden_reads  # reads that still answer "not found" after the table was created
        self.attributes: dict[str, dict[str, Any]] = {}
        self.keys: dict[str, list[str]] = {}  # key -> the index statuses it reports, the last one for good
        self.relationships: set[str] = set()


class Environment:
    """The metadata of one Dataverse environment, and the HTTP session the client sends its requests through."""

    def __init__(self, *, solution: str | None = SOLUTION, managed: bool = False, publisher: tuple[str, int] = ("vz", 65120),
                 hidden_reads: int = 0, key_statuses: dict[str, list[str]] | None = None) -> None:
        self.solutions = ([{"solutionid": "bbbbbbbb-0000-0000-0000-000000000002", "uniquename": solution, "ismanaged": managed,
                            "version": "1.0.0.0", "_publisherid_value": PUBLISHER_ID}] if solution else [])
        self.publisher = {"customizationprefix": publisher[0], "customizationoptionvalueprefix": publisher[1]}
        self.hidden_reads = hidden_reads
        self.key_statuses = key_statuses or {}
        self.refusals: dict[str, list[Reply]] = {}  # label of a create -> the replies it gets before it is accepted
        self.counter = 0
        self.choices: dict[str, str] = {}
        self.tables: dict[str, Table] = {"systemuser": Table(self.next_id())}
        self.requests: list[tuple[str, str]] = []
        self.attempts: list[Attempt] = []
        self.created: list[str] = []
        self.published: list[str] = []
        self.status_reads: dict[str, int] = {}

    def next_id(self) -> str:
        self.counter += 1
        return f"00000000-0000-0000-0000-{self.counter:012d}"

    @property
    def writes(self) -> list[tuple[str, str]]:
        return [request for request in self.requests if request[0] != "GET"]

    # --- the part of requests.Session that scripts/dvweb.py uses ---

    def request(self, method: str, url: str, *, json: Any = None, data: Any = None, headers: dict[str, str] | None = None,
                timeout: Any = None) -> Reply:
        path, _, query = url.removeprefix(API + "/").partition("?")
        self.requests.append((method, path))
        if method == "GET":
            return self.read(path, {key: values[0] for key, values in parse_qs(query).items()})
        return self.write(path, json or {}, headers or {})

    # --- reads ---

    def visible(self, name: str) -> Table | None:
        table = self.tables.get(name)
        return table if table is not None and table.hidden_reads == 0 else None

    def read(self, path: str, params: dict[str, str]) -> Reply:
        if path == "solutions":
            match = re.search(r"uniquename eq '([^']+)'", params["$filter"])
            assert match, f"unexpected solution filter {params['$filter']}"
            return Reply(200, {"value": [row for row in self.solutions if row["uniquename"] == match.group(1)]})
        if re.fullmatch(r"publishers\(.+\)", path):
            return Reply(200, self.publisher)
        if choice := re.fullmatch(r"GlobalOptionSetDefinitions\(Name='(.+)'\)", path):
            found = self.choices.get(choice.group(1))
            return Reply(200, {"MetadataId": found}) if found else refused(404, f"The global option set {choice.group(1)} does not exist.")
        match = ENTITY_PATH.fullmatch(path)
        assert match, f"unexpected GET {path}"
        name, part = match.groups()
        table = self.tables.get(name)
        if table is None:
            return refused(404, f"The entity {name} does not exist.")
        if part is None:
            if table.hidden_reads > 0:
                table.hidden_reads -= 1
                return refused(404, f"The entity {name} does not exist.")
            return Reply(200, {"MetadataId": table.id})
        if part == "Attributes":
            return Reply(200, {"value": [{"LogicalName": attribute} for attribute in table.attributes]})
        if part == "ManyToOneRelationships":
            return Reply(200, {"value": [{"SchemaName": relationship} for relationship in sorted(table.relationships)]})
        assert part == "Keys", f"unexpected GET {path}"
        reports_status = "EntityKeyIndexStatus" in params["$select"]
        self.status_reads[name] = self.status_reads.get(name, 0) + reports_status
        rows = []
        for key, statuses in table.keys.items():
            row = {"SchemaName": key}
            if reports_status:
                status = statuses.pop(0) if len(statuses) > 1 else statuses[0]
                if status == "Missing":  # the key is not listed yet
                    continue
                row["EntityKeyIndexStatus"] = status
            rows.append(row)
        return Reply(200, {"value": rows})

    # --- writes: every one that is not a publish is a metadata create ---

    def write(self, path: str, body: dict[str, Any], headers: dict[str, str]) -> Reply:
        if path == "PublishXml":
            self.published.append(body["ParameterXml"])
            return Reply(204)
        label = self.label(path, body)
        self.attempts.append(Attempt(label, headers.get("MSCRM.SolutionUniqueName")))
        reply = self.refusals[label].pop(0) if self.refusals.get(label) else self.accept(path, body)
        if reply.status_code == 204:
            self.created.append(label)
        return reply

    @staticmethod
    def label(path: str, body: dict[str, Any]) -> str:
        if path == "GlobalOptionSetDefinitions":
            return f"choice {body['Name']}"
        if path == "EntityDefinitions":
            return f"table {body['SchemaName']}"
        if path == "RelationshipDefinitions":
            return f"relationship {body['SchemaName']}"
        match = ENTITY_PATH.fullmatch(path)
        assert match and match.group(2) in ("Attributes", "Keys"), f"unexpected POST {path}"
        if match.group(2) == "Attributes":
            return f"column {match.group(1)}.{body['SchemaName'].lower()}"
        return f"key {body['SchemaName']}"

    def entity_id(self) -> Reply:
        return Reply(204, headers={"OData-EntityId": f"{API}/Anything({self.next_id()})"})

    def accept(self, path: str, body: dict[str, Any]) -> Reply:
        if path == "GlobalOptionSetDefinitions":
            if body["Name"] in self.choices:
                return refused(400, f"A global option set named {body['Name']} already exists.")
            self.choices[body["Name"]] = self.next_id()
            return self.entity_id()
        if path == "EntityDefinitions":
            logical = body["SchemaName"].lower()
            if logical in self.tables:
                return refused(400, f"An entity named {logical} already exists.")
            table = self.tables[logical] = Table(self.next_id(), self.hidden_reads)
            for attribute in body["Attributes"]:
                table.attributes[attribute["SchemaName"].lower()] = attribute
            table.attributes[logical + "id"] = {}
            return self.entity_id()
        if path == "RelationshipDefinitions":
            for name in (body["ReferencedEntity"], body["ReferencingEntity"]):
                if self.visible(name) is None:
                    return refused(404, f"The entity {name} does not exist.")
            child, lookup = self.tables[body["ReferencingEntity"]], body["Lookup"]["SchemaName"].lower()
            if body["SchemaName"] in child.relationships or lookup in child.attributes:
                return refused(400, f"The relationship {body['SchemaName']} already exists.")
            child.relationships.add(body["SchemaName"])
            child.attributes[lookup] = body["Lookup"]
            return self.entity_id()
        match = ENTITY_PATH.fullmatch(path)
        assert match
        table = self.visible(match.group(1))
        if table is None:
            return refused(404, f"The entity {match.group(1)} does not exist.")
        if match.group(2) == "Attributes":
            name = body["SchemaName"].lower()
            bound = (body.get("GlobalOptionSet@odata.bind") or "").removeprefix("/GlobalOptionSetDefinitions(").removesuffix(")")
            if name in table.attributes:
                return refused(400, f"An attribute named {name} already exists.")
            if "GlobalOptionSet@odata.bind" in body and bound not in self.choices.values():
                return refused(404, f"The global option set {bound} does not exist.")
            table.attributes[name] = body
        else:
            missing = [column for column in body["KeyAttributes"] if column not in table.attributes]
            if missing or body["SchemaName"] in table.keys:
                return refused(400, f"The key {body['SchemaName']} is not valid: missing {missing}.")
            table.keys[body["SchemaName"]] = list(self.key_statuses.get(body["SchemaName"], ["Active"]))
        return self.entity_id()


@pytest.fixture
def schema() -> dict[str, Any]:
    return schemalib.load_schema()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(dvweb, "time", clock)
    monkeypatch.setattr(provision, "time", clock)
    return clock


@pytest.fixture
def connect(monkeypatch: pytest.MonkeyPatch, clock: Clock) -> Callable[..., dvweb.Dataverse]:
    monkeypatch.setenv("DATAVERSE_URL", BASE + "/")
    monkeypatch.setattr(dvweb.auth, "load_env", lambda: None)
    monkeypatch.setattr(dvweb.auth, "get_token", lambda: "token")
    monkeypatch.setattr(dvweb.auth, "get_plugin_headers", lambda _skill: {"User-Agent": "test"})

    def make(env: Environment, solution: str | None = SOLUTION) -> dvweb.Dataverse:
        client = dvweb.Dataverse("dv-metadata", solution=solution)
        client._http = env
        return client

    return make


@pytest.fixture
def run_script(monkeypatch: pytest.MonkeyPatch, connect: Callable[..., dvweb.Dataverse],
               capsys: pytest.CaptureFixture[str]) -> Callable[..., str]:
    """Runs the script's main() against an environment, as `python scripts/provision-dataverse.py <flags>` would. Returns what it printed."""

    def run(env: Environment, *flags: str) -> str:
        monkeypatch.setattr(provision, "Dataverse", lambda skill, solution: connect(env, solution))
        monkeypatch.setattr(sys, "argv", ["provision-dataverse.py", *flags])
        assert provision.main() == 0
        return capsys.readouterr().out

    return run


def declared(schema: dict[str, Any]) -> int:
    """How many objects schema.json asks for: global choices, tables, plain columns, keys and relationships."""
    return (len(schema["global_choices"]) + len(schema["tables"]) + sum(len(table["columns"]) for table in schema["tables"])
            + len(schema["keys"]) + len(schema["relationships"]))


# --- what a run builds -------------------------------------------------------------------------------------------

def test_an_empty_environment_is_filled_and_every_create_names_the_solution(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()

    out = run_script(env)

    assert f"Done: created {declared(schema)}, already present 0." in out
    assert len(env.attempts) == len(env.created) == declared(schema)
    assert {attempt.solution for attempt in env.attempts} == {SOLUTION}


def test_everything_the_schema_declares_exists_afterwards(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()

    run_script(env)

    assert set(env.choices) == {choice["name"] for choice in schema["global_choices"]}
    for table in schema["tables"]:
        built = env.tables[table["name"]]
        assert {table["primary"]["name"], *(column["name"] for column in table["columns"])} <= set(built.attributes)
        assert {key["name"] for key in schema["keys"] if key["table"] == table["name"]} == set(built.keys)
    for rel in schema["relationships"]:
        child = env.tables[rel["referencing"]]
        assert rel["name"] in child.relationships and rel["lookup"] in child.attributes


def test_a_rerun_creates_and_publishes_nothing(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()
    run_script(env)
    writes_before = len(env.writes)

    out = run_script(env)

    assert f"Done: created 0, already present {declared(schema)}." in out
    assert len(env.writes) == writes_before
    assert len(env.published) == 1
    assert "  created" not in out and out.count("  exists") == declared(schema)


def test_a_run_that_stopped_part_way_is_finished_by_the_next_run(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()
    env.refusals["column vz_contract.vz_status"] = [refused(400, "The attribute definition is not valid.")]

    with pytest.raises(dvweb.DataverseError, match="not valid"):
        run_script(env)
    first = len(env.created)
    assert 0 < first < declared(schema)

    out = run_script(env)

    assert f"Done: created {declared(schema) - first}, already present {first}." in out
    assert len(env.created) == declared(schema)
    assert len(set(env.created)) == len(env.created), "something was created twice"


def test_dependencies_are_created_before_what_needs_them(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()

    run_script(env)

    position = {label: index for index, label in enumerate(env.created)}
    for table in schema["tables"]:
        for column in table["columns"]:
            assert position[f"table {table['name']}"] < position[f"column {table['name']}.{column['name']}"]
            if column["type"] == "globalchoice":
                assert position[f"choice {column['global']}"] < position[f"column {table['name']}.{column['name']}"]
    for key in schema["keys"]:
        assert all(position[f"column {key['table']}.{column}"] < position[f"key {key['name']}"] for column in key["columns"])
    for rel in schema["relationships"]:
        assert position[f"table {rel['referencing']}"] < position[f"relationship {rel['name']}"]
        if rel["referenced"] in {table["name"] for table in schema["tables"]}:
            assert position[f"table {rel['referenced']}"] < position[f"relationship {rel['name']}"]


def test_what_was_created_is_published_once_at_the_end_for_every_declared_table_and_choice(
        run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()

    run_script(env)

    (xml,) = env.published
    assert env.requests[-1] == ("POST", "PublishXml")
    assert re.findall(r"<entity>(.+?)</entity>", xml) == [table["name"] for table in schema["tables"]]
    assert re.findall(r"<optionset>(.+?)</optionset>", xml) == [choice["name"] for choice in schema["global_choices"]]


def test_a_dry_run_reads_but_writes_nothing(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()

    out = run_script(env, "--dry-run")

    assert env.writes == [] and env.published == [] and env.tables.keys() == {"systemuser"}
    assert "[dry run]" in out and f"Done: would create {declared(schema)}, already present 0." in out
    assert out.count("  would") == declared(schema)


def test_a_dry_run_after_a_real_run_has_nothing_left_to_create(run_script: Callable[..., str], schema: dict[str, Any]) -> None:
    env = Environment()
    run_script(env)

    out = run_script(env, "--dry-run")

    assert f"Done: would create 0, already present {declared(schema)}." in out


def test_the_solution_option_sends_that_solution_with_every_create(run_script: Callable[..., str]) -> None:
    env = Environment(solution="AnotherSolution")

    run_script(env, "--solution", "AnotherSolution")

    assert env.attempts and {attempt.solution for attempt in env.attempts} == {"AnotherSolution"}


# --- refusing to build outside the solution ----------------------------------------------------------------------

def test_the_client_refuses_to_create_metadata_without_a_solution(connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any]) -> None:
    env = Environment()
    work = provision.Provisioner(connect(env, solution=None), schema, dry_run=False)

    with pytest.raises(ValueError, match="refusing to create metadata outside a solution"):
        work.global_choices()

    assert env.writes == [] and env.attempts == [] and work.created == []


REFUSED = {
    "a solution that does not exist": (dict(solution=None), "does not exist.*refusing to build outside a solution"),
    "a managed solution": (dict(managed=True), "is managed"),
    "another publisher prefix": (dict(publisher=("xx", 65120)), "Publisher mismatch: env has xx/65120, schema expects vz/65120"),
    "another option value prefix": (dict(publisher=("vz", 10000)), "Publisher mismatch: env has vz/10000, schema expects vz/65120"),
}


@pytest.mark.parametrize("environment, message", REFUSED.values(), ids=REFUSED.keys())
def test_the_run_stops_before_it_reads_or_writes_anything_else_when_the_solution_is_not_fit_to_build_in(
        environment: dict[str, Any], message: str, run_script: Callable[..., str]) -> None:
    env = Environment(**environment)

    with pytest.raises(SystemExit, match=message):
        run_script(env)

    assert env.writes == [] and {path for _method, path in env.requests} <= {"solutions", f"publishers({PUBLISHER_ID})"}


def test_preflight_returns_the_solution_row_when_it_is_fit(connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any]) -> None:
    row = provision.preflight(connect(Environment()), schema, SOLUTION)

    assert row["uniquename"] == SOLUTION and row["ismanaged"] is False


# --- waiting for Dataverse ---------------------------------------------------------------------------------------

def test_a_table_is_waited_for_until_it_can_be_read_before_its_columns_are_added(
        run_script: Callable[..., str], schema: dict[str, Any], clock: Clock) -> None:
    env = Environment(hidden_reads=2)

    run_script(env)

    # a table that cannot be read yet refuses new columns, so a single attempt per object means nothing was added too early
    assert len(env.attempts) == len(env.created) == declared(schema)
    assert clock.slept


def test_a_create_that_races_its_parent_is_retried_after_a_pause(
        connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any], clock: Clock) -> None:
    env = Environment()
    work = provision.Provisioner(connect(env), schema, dry_run=False)
    work.global_choices()
    work.tables()
    clock.slept.clear()
    column = schema["tables"][0]["columns"][0]
    table = schema["tables"][0]["name"]
    env.refusals[f"column {table}.{column['name']}"] = [refused(404, f"The entity {table} does not exist.")] * 2

    work.create(f"EntityDefinitions(LogicalName='{table}')/Attributes", work.column_payload(column), "the racing column")

    assert clock.slept == [6, 6]
    assert work.created[-1] == "the racing column"
    assert [attempt.label for attempt in env.attempts][-3:] == [f"column {table}.{column['name']}"] * 3


def test_a_create_that_keeps_missing_its_parent_gives_up_after_five_tries(
        connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any], clock: Clock) -> None:
    env = Environment()
    work = provision.Provisioner(connect(env), schema, dry_run=False)
    env.refusals["choice vz_judgment"] = [refused(404, "The entity does not exist.")] * 9

    with pytest.raises(dvweb.DataverseError, match="does not exist"):
        work.global_choices()

    assert len(env.attempts) == 5 and clock.slept == [6, 6, 6, 6]
    assert work.created == []


def test_any_other_refusal_is_raised_at_once_without_a_retry(
        connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any], clock: Clock) -> None:
    env = Environment()
    work = provision.Provisioner(connect(env), schema, dry_run=False)
    env.refusals["choice vz_judgment"] = [refused(400, "The display name is not valid.")]

    with pytest.raises(dvweb.DataverseError, match="display name is not valid"):
        work.global_choices()

    assert len(env.attempts) == 1 and clock.slept == []


def test_each_alternate_key_is_waited_for_on_its_own_index(
        connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any], clock: Clock, capsys: pytest.CaptureFixture[str]) -> None:
    two_keys = copy.deepcopy(schema)
    two_keys["keys"].append({"table": "vz_contract", "name": "vz_contract_identifier_key", "display": "Contract identifier key",
                             "columns": ["vz_contractidentifier"]})
    env = Environment(key_statuses={"vz_checklistitem_key": ["Pending", "InProgress", "Active"],
                                    "vz_contract_identifier_key": ["Active"]})
    work = provision.Provisioner(connect(env), two_keys, dry_run=False)
    work.global_choices()
    work.tables()
    work.columns()
    clock.slept.clear()

    work.keys()

    assert env.status_reads == {"vz_checklistitem": 3, "vz_contract": 1}
    assert clock.slept == [5, 5]
    out = capsys.readouterr().out
    assert out.index("active   key vz_checklistitem_key") < out.index("active   key vz_contract_identifier_key")


def test_a_key_that_is_not_listed_yet_is_waited_for_like_one_that_is_still_building(
        connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any], clock: Clock) -> None:
    env = Environment(key_statuses={"vz_checklistitem_key": ["Missing", "Missing", "Active"]})
    work = provision.Provisioner(connect(env), schema, dry_run=False)
    work.global_choices()
    work.tables()
    work.columns()
    clock.slept.clear()

    work.keys()

    assert env.status_reads == {"vz_checklistitem": 3} and clock.slept == [5, 5]


def test_an_index_that_fails_to_build_stops_the_run(
        connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any], clock: Clock) -> None:
    env = Environment(key_statuses={"vz_checklistitem_key": ["Pending", "Failed"]})
    work = provision.Provisioner(connect(env), schema, dry_run=False)
    work.global_choices()
    work.tables()
    work.columns()

    with pytest.raises(RuntimeError, match="vz_checklistitem_key index build failed"):
        work.keys()


# --- what is sent for each kind of column ------------------------------------------------------------------------

COLUMNS = [pytest.param(column, id=f"{table['name']}.{column['name']}")
           for table in schemalib.load_schema()["tables"] for column in table["columns"]]


@pytest.fixture
def builder(connect: Callable[..., dvweb.Dataverse], schema: dict[str, Any]) -> Any:
    """A provisioner that only builds request bodies: its client is never asked to send one."""
    return provision.Provisioner(connect(Environment()), schema, dry_run=True)


@pytest.mark.parametrize("column", COLUMNS)
def test_every_declared_column_has_a_payload_with_its_name_and_requirement(builder: Any, column: dict[str, Any]) -> None:
    body = builder.column_payload(column)

    assert body["SchemaName"] == column["name"]
    assert body["RequiredLevel"]["Value"] == ("ApplicationRequired" if column.get("required") else "None")
    assert body["@odata.type"].startswith("Microsoft.Dynamics.CRM.") and body["@odata.type"].endswith("AttributeMetadata")
    assert ("Description" in body) == bool(column.get("description"))


def test_a_choice_default_is_one_of_the_options_it_lists(builder: Any, schema: dict[str, Any]) -> None:
    choices = [column for table in schema["tables"] for column in table["columns"] if column["type"] == "choice" and "default" in column]
    assert choices

    for column in choices:
        body = builder.column_payload(column)
        options = {option["Label"]["LocalizedLabels"][0]["Label"]: option["Value"] for option in body["OptionSet"]["Options"]}
        assert body["DefaultFormValue"] == options[column["default"]]
        assert list(options.values()) == [schemalib.option_value(schema, index) for index in range(len(options))]


def test_dates_say_how_they_behave_because_a_column_without_it_breaks_filtered_views(builder: Any) -> None:
    date = builder.column_payload({"name": "vz_when", "display": "When", "type": "date"})
    moment = builder.column_payload({"name": "vz_at", "display": "At", "type": "datetime"})

    assert (date["Format"], date["DateTimeBehavior"]) == ("DateOnly", {"Value": "DateOnly"})
    assert (moment["Format"], moment["DateTimeBehavior"]) == ("DateAndTime", {"Value": "UserLocal"})


def test_a_column_bound_to_a_global_choice_points_at_the_choice_that_was_created(builder: Any) -> None:
    column = {"name": "vz_judged", "display": "Judged", "type": "globalchoice", "global": "vz_judgment"}
    builder.global_ids["vz_judgment"] = "11111111-1111-1111-1111-111111111111"

    assert builder.column_payload(column)["GlobalOptionSet@odata.bind"] == "/GlobalOptionSetDefinitions(11111111-1111-1111-1111-111111111111)"


def test_a_column_type_the_provisioner_does_not_know_is_refused_by_name(builder: Any) -> None:
    with pytest.raises(ValueError, match="vz_odd: unsupported column type 'money'"):
        builder.column_payload({"name": "vz_odd", "display": "Odd", "type": "money"})


def test_a_relationship_that_owns_its_children_cascades_and_one_that_does_not_never_does(schema: dict[str, Any]) -> None:
    kinds = {rel["cascade"] for rel in schema["relationships"]}
    assert kinds == {"parental", "removelink", "restrict"}

    parental, removelink, restrict = (provision.cascade(kind) for kind in ("parental", "removelink", "restrict"))

    assert (parental["Delete"], parental["Share"], parental["Reparent"]) == ("Cascade", "Cascade", "Cascade")
    assert removelink["Delete"] == "RemoveLink" and restrict["Delete"] == "Restrict"
    assert all(value == "NoCascade" for body in (removelink, restrict) for name, value in body.items() if name != "Delete")
