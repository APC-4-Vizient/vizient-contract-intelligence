"""Create the cloud flows of the contract pipeline, and what they need, inside the VizientContractPOC solution.

    python scripts/provision-flow.py           # offline: build both flows and check them against dataverse/schema.json
    python scripts/provision-flow.py --status  # read-only: compare Dataverse with what --apply would write; exit 1 if it differs
    python scripts/provision-flow.py --apply   # create or update the rows below, then turn both flows on

Every row is created with the solution header, so nothing lands outside the solution:
  environment variables   the Function address and key, and the SharePoint site, library and intake folder
  connection references   one for SharePoint and one for Dataverse, bound to the existing connections named in .env
  cloud flows             Vizient Contract Intake and Vizient Contract Analysis (built by scripts/flowlib.py)

Settings come from .env (see .env.example): the SHAREPOINT_* values and the two connection names. The Function address
comes from the azd environment, and the Function key is read from Azure into memory. The key is written only to its
environment variable's value in Dataverse and is never printed. A flow is rewritten only when the [definition ...] tag at
the end of its description is not the current one, so a rerun that changes nothing writes nothing.
Dataverse must be signed in as AZURE_ACCOUNT from .env, or the script stops before it reads anything else.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import flowlib
import schemalib
from dvweb import Dataverse, DataverseError, entity_id, signed_in_account, wait_for
from loadscript import load_script

GUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
CONNECTION_NAME = re.compile(r"[A-Za-z0-9-]{8,80}")
REQUIRED = ("SHAREPOINT_SITE_URL", "SHAREPOINT_LIBRARY_ID", "SHAREPOINT_INTAKE_FOLDER",
            "SHAREPOINT_CONNECTION_NAME", "DATAVERSE_CONNECTION_NAME")
ON = {"statecode": 1, "statuscode": 2}
OFF = {"statecode": 0, "statuscode": 1}
IF_MATCH = {"If-Match": "*"}  # without it a PATCH to a missing row would create one

DEFINITIONS, DEFINITION_ID = "environmentvariabledefinitions", "environmentvariabledefinitionid"
VALUES, VALUE_ID = "environmentvariablevalues", "environmentvariablevalueid"
REFERENCES, REFERENCE_ID = "connectionreferences", "connectionreferenceid"
FLOWS, FLOW_ID = "workflows", "workflowid"
DEFINITION_OF_VALUE = "_environmentvariabledefinitionid_value"


class ProvisionError(RuntimeError):
    """A failure worth one clear line, not a stack trace."""


@dataclass(frozen=True)
class Settings:
    values: Mapping[str, str] = field(repr=False)  # environment variable schema name -> value; one of them is the Function key
    connections: Mapping[str, str]                 # connector name -> name of the existing connection it uses


def read_settings(env: Mapping[str, str], function_url: str, function_key: str) -> Settings:
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        raise ProvisionError(f"set {', '.join(missing)} in .env (see .env.example)")
    site = env["SHAREPOINT_SITE_URL"].rstrip("/")
    if urlparse(site).scheme != "https" or not (urlparse(site).hostname or "").lower().endswith(".sharepoint.com"):
        raise ProvisionError("SHAREPOINT_SITE_URL must be an https address on sharepoint.com")
    library = env["SHAREPOINT_LIBRARY_ID"]
    if not GUID.fullmatch(library):
        raise ProvisionError("SHAREPOINT_LIBRARY_ID must be the GUID of the document library")
    folder = env["SHAREPOINT_INTAKE_FOLDER"]
    if not folder.startswith("/"):
        raise ProvisionError("SHAREPOINT_INTAKE_FOLDER must start with /, as in /Shared Documents/Contract Intake")
    connections = {flowlib.SHAREPOINT: env["SHAREPOINT_CONNECTION_NAME"], flowlib.DATAVERSE: env["DATAVERSE_CONNECTION_NAME"]}
    for setting, name in (("SHAREPOINT_CONNECTION_NAME", connections[flowlib.SHAREPOINT]),
                          ("DATAVERSE_CONNECTION_NAME", connections[flowlib.DATAVERSE])):
        if not CONNECTION_NAME.fullmatch(name):
            raise ProvisionError(f"{setting} must be the name of an existing connection (letters, digits and hyphens)")
    if not function_key:
        raise ProvisionError("the Function app has no key to give the flows")
    values = {flowlib.FUNCTION_URL.schema_name: function_url, flowlib.FUNCTION_KEY.schema_name: function_key,
              flowlib.SITE_URL.schema_name: site, flowlib.LIBRARY_ID.schema_name: library,
              flowlib.INTAKE_FOLDER.schema_name: folder}
    return Settings(values, connections)


# --- comparing rows ------------------------------------------------------------------------------------------------

@dataclass
class Plan:
    what: str
    create: list[tuple[str, dict[str, Any]]] = field(default_factory=list, repr=False)  # key, wanted row
    update: list[tuple[str, str, dict[str, Any], list[str]]] = field(default_factory=list, repr=False)  # key, row id, wanted row, changed
    unchanged: int = 0

    @property
    def in_sync(self) -> bool:
        return not self.create and not self.update


def _text(value: Any) -> Any:
    """Dataverse hands multi-line text back with CRLF, whatever was written."""
    return value.replace("\r\n", "\n") if isinstance(value, str) else value


def hold(rows: Iterable[dict[str, Any]], key: Callable[[dict[str, Any]], str], what: str) -> dict[str, dict[str, Any]]:
    held: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = key(row)
        if name in held:
            raise ProvisionError(f"Dataverse holds more than one {what} named {name}; remove the duplicate by hand")
        held[name] = row
    return held


def diff(what: str, wanted: list[tuple[str, dict[str, Any]]], held: Mapping[str, dict[str, Any]],
         columns: tuple[str, ...], id_column: str) -> Plan:
    plan = Plan(what)
    for key, row in wanted:
        current = held.get(key)
        if current is None:
            plan.create.append((key, row))
            continue
        changed = [column for column in columns if _text(current.get(column)) != _text(row[column])]
        if changed:
            plan.update.append((key, current[id_column], row, changed))
        else:
            plan.unchanged += 1
    return plan


def any_of(column: str, values: Iterable[str], quote: str = "'") -> str:
    return " or ".join(f"{column} eq {quote}{value}{quote}" for value in values)


def plan_definitions(dv: Dataverse) -> tuple[Plan, dict[str, dict[str, Any]]]:
    columns = ("displayname", "description", "type")
    held = hold(dv.list(DEFINITIONS, {"$select": ",".join((DEFINITION_ID, "schemaname", *columns)),
                                      "$filter": any_of("schemaname", (var.schema_name for var in flowlib.ENV_VARS))}),
                lambda row: row["schemaname"], "environment variable")
    wanted = [(var.schema_name, {"schemaname": var.schema_name, "displayname": var.display_name,
                                 "description": var.description, "type": flowlib.ENVIRONMENT_VARIABLE_TEXT})
              for var in flowlib.ENV_VARS]
    return diff("environment variable", wanted, held, columns, DEFINITION_ID), held


def plan_values(dv: Dataverse, settings: Settings, definition_ids: Mapping[str, str]) -> Plan:
    """A value row belongs to a definition, so the rows are matched through the definition's id."""
    by_id = {row_id: name for name, row_id in definition_ids.items()}
    rows = dv.list(VALUES, {"$select": ",".join((VALUE_ID, "schemaname", "value", DEFINITION_OF_VALUE)),
                            "$filter": any_of(DEFINITION_OF_VALUE, by_id.keys(), quote="")}) if by_id else []
    held = hold(rows, lambda row: by_id[row[DEFINITION_OF_VALUE]], "value")
    wanted = [(var.schema_name, {"schemaname": f"{var.schema_name}_value", "value": settings.values[var.schema_name]})
              for var in flowlib.ENV_VARS]
    return diff("environment variable value", wanted, held, ("value",), VALUE_ID)


def plan_references(dv: Dataverse, settings: Settings) -> Plan:
    columns = ("connectionreferencedisplayname", "connectorid", "connectionid")
    held = hold(dv.list(REFERENCES, {"$select": ",".join((REFERENCE_ID, "connectionreferencelogicalname", *columns)),
                                     "$filter": any_of("connectionreferencelogicalname",
                                                       (ref.logical_name for ref in flowlib.CONNECTION_REFS))}),
                lambda row: row["connectionreferencelogicalname"], "connection reference")
    wanted = [(ref.logical_name, {"connectionreferencelogicalname": ref.logical_name,
                                  "connectionreferencedisplayname": ref.display_name, "connectorid": ref.connector_id,
                                  "connectionid": settings.connections[ref.connector]})
              for ref in flowlib.CONNECTION_REFS]
    return diff("connection reference", wanted, held, columns, REFERENCE_ID)


def flow_state(spec: flowlib.FlowSpec, current: Mapping[str, Any] | None) -> str:
    """create, update (the stored flow is not this definition), start (current but off) or ok."""
    if current is None:
        return "create"
    if spec.tag not in (current.get("description") or ""):
        return "update"
    return "ok" if current.get("statecode") == 1 else "start"


def plan_flows(dv: Dataverse, specs: list[flowlib.FlowSpec]) -> list[tuple[flowlib.FlowSpec, str, dict[str, Any] | None]]:
    held = hold(dv.list(FLOWS, {"$select": f"{FLOW_ID},name,description,statecode",
                                "$filter": f"category eq 5 and ({any_of('name', (spec.name for spec in specs))})"}),
                lambda row: row["name"], "flow")
    return [(spec, flow_state(spec, held.get(spec.name)), held.get(spec.name)) for spec in specs]


@dataclass
class Survey:
    definitions: Plan
    definition_ids: dict[str, str]
    values: Plan
    references: Plan
    flows: list[tuple[flowlib.FlowSpec, str, dict[str, Any] | None]]

    @property
    def in_sync(self) -> bool:
        return (self.definitions.in_sync and self.values.in_sync and self.references.in_sync
                and all(state == "ok" for _spec, state, _row in self.flows))


def survey(dv: Dataverse, settings: Settings, specs: list[flowlib.FlowSpec]) -> Survey:
    definitions, held = plan_definitions(dv)
    ids = {name: row[DEFINITION_ID] for name, row in held.items()}
    return Survey(definitions, ids, plan_values(dv, settings, ids), plan_references(dv, settings), plan_flows(dv, specs))


def describe(found: Survey, log: Callable[[str], None] = print) -> None:
    """What differs, by name and column. Values are never shown: one of them is a key."""
    for plan in (found.definitions, found.values, found.references):
        for key, _row in plan.create:
            log(f"  create  {plan.what} {key}")
        for key, _row_id, _row, changed in plan.update:
            log(f"  update  {plan.what} {key}  ({', '.join(changed)})")
        log(f"{plan.what}: {len(plan.create)} to create, {len(plan.update)} to update, {plan.unchanged} unchanged")
    for spec, state, _current in found.flows:
        if state != "ok":
            log(f"  {state:<7} flow {spec.name}")
    log(f"flows: {sum(state == 'ok' for _spec, state, _row in found.flows)} of {len(found.flows)} current and on")


# --- writing -------------------------------------------------------------------------------------------------------

def write(dv: Dataverse, entity_set: str, plan: Plan,
          decorate: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, str]:
    """Create and update the rows of a plan. Returns the id of each row that was created."""
    created: dict[str, str] = {}
    for key, row in plan.create:
        body = decorate(key, row) if decorate else row
        created[key] = entity_id(dv.request("POST", entity_set, body=body, solution=True))
    for _key, row_id, row, changed in plan.update:
        dv.request("PATCH", f"{entity_set}({row_id})", body={column: row[column] for column in changed}, headers=IF_MATCH)
    return created


def clip(text: str, width: int = 600) -> str:
    return " ".join(str(text).split())[:width]


def write_flow(dv: Dataverse, spec: flowlib.FlowSpec, state: str, current: Mapping[str, Any] | None,
               log: Callable[[str], None] = print) -> None:
    if state == "create":
        flow_id = entity_id(dv.request("POST", FLOWS, body=spec.row, solution=True))
    else:
        assert current is not None, "flow_state reports create for a flow that has no row, and nothing else"
        flow_id = current[FLOW_ID]
        if state == "update":
            if current.get("statecode") == 1:  # a flow that is on cannot be rewritten
                dv.request("PATCH", f"{FLOWS}({flow_id})", body=OFF, headers=IF_MATCH)
            dv.request("PATCH", f"{FLOWS}({flow_id})", headers=IF_MATCH,
                       body={"name": spec.name, "description": spec.description, "clientdata": spec.client_data})
    try:
        dv.request("PATCH", f"{FLOWS}({flow_id})", body=ON, headers=IF_MATCH)
    except DataverseError as exc:
        raise ProvisionError(f"{spec.name} is saved in the solution but would not turn on. "
                             f"Dataverse said: {clip(exc.message)}") from exc
    log(f"  on      flow {spec.name}")


def write_all(dv: Dataverse, found: Survey, log: Callable[[str], None] = print) -> None:
    ids = {**found.definition_ids, **write(dv, DEFINITIONS, found.definitions)}
    write(dv, VALUES, found.values,
          lambda key, row: {**row, "EnvironmentVariableDefinitionId@odata.bind": f"/{DEFINITIONS}({ids[key]})"})
    write(dv, REFERENCES, found.references)
    for spec, state, current in found.flows:
        if state != "ok":
            write_flow(dv, spec, state, current, log)


def reconcile(dv: Dataverse, settings: Settings, specs: list[flowlib.FlowSpec], apply: bool,
              log: Callable[[str], None] = print) -> bool:
    """Compare Dataverse with what the flows need and, when asked, write the difference. True when nothing differs."""
    found = survey(dv, settings, specs)
    describe(found, log)
    if not apply or found.in_sync:
        return found.in_sync
    write_all(dv, found, log)
    dv.reset_affinity()
    try:
        wait_for(lambda: survey(dv, settings, specs).in_sync, "the flows to be current and on", timeout=60, interval=3)
    except TimeoutError as exc:
        raise ProvisionError("Dataverse still differs after the write. Run --status to see how") from exc
    log(f"Dataverse now holds the environment variables, connection references and flows; all {len(specs)} flows are on.")
    return True


# --- running it ----------------------------------------------------------------------------------------------------

def check_account(dv: Dataverse, expected: str | None) -> str:
    """The signed-in account, after proving it is the one named in .env (when one is named)."""
    account = signed_in_account(dv)
    if expected and account.lower() != expected.lower():
        raise ProvisionError(f"Dataverse is signed in as {account}, but AZURE_ACCOUNT expects {expected}")
    return account


def checked_specs(schema: Mapping[str, Any]) -> list[flowlib.FlowSpec]:
    specs = flowlib.flow_specs(schema)
    for spec in specs:
        issues = flowlib.problems(spec.definition, schema)
        if issues:
            raise ProvisionError(f"{spec.name} does not match the schema:\n  " + "\n  ".join(issues))
    return specs


def load_run_local() -> Any:
    """scripts/run-local.py, which already knows how to find the Function and read its key."""
    return load_script("run-local.py", "run_local")


def connect_settings() -> Settings:
    run_local = load_run_local()
    try:
        env = run_local.load_settings()
        function_url = run_local.api_origin(env.get("SERVICE_API_URI", ""))
        key = run_local.function_key(env)
    except run_local.RunError as exc:
        raise ProvisionError(str(exc)) from exc
    return read_settings(env, function_url, key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="read-only comparison with Dataverse; exit 1 if it differs")
    mode.add_argument("--apply", action="store_true", help="create or update the rows, then turn both flows on")
    args = parser.parse_args(argv)

    try:
        schema = schemalib.load_schema()
        specs = checked_specs(schema)
        if not (args.status or args.apply):
            for spec in specs:
                actions = sum(1 for _ in flowlib.walk_actions(spec.definition["actions"]))
                print(f"{spec.name}: valid ({actions} actions, {len(spec.client_data)} bytes, {spec.tag})")
            print("Nothing was sent. Run with --status to compare with Dataverse, or --apply to write.")
            return 0
        dv = Dataverse("dv-solution", solution=schema["solution"])
        account = check_account(dv, os.environ.get("AZURE_ACCOUNT") or None)
        print(f"Signed in as {account}; environment {urlparse(dv.base_url).hostname}; solution {schema['solution']}")
        return 0 if reconcile(dv, connect_settings(), specs, apply=args.apply) else 1
    except (ProvisionError, DataverseError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
