"""Prove that every Power Platform object of this project lives in the VizientContractPOC solution.

  1. The solution exists, is unmanaged and uses the project publisher; the signed-in user's
     preferred solution is this solution, so portal-made objects land in it.
  2. Everything declared in dataverse/schema.json exists and is covered by the solution.
  3. A real solution export contains every declared object (ground truth).
  4. Nothing created by the signed-in user since the solution was created sits outside it:
     flows, apps, connection references, environment variables, roles, web resources, and so on.
  5. Nothing else is in the solution: every component is one this project declares (schema.json and
     scripts/flowlib.py) or the Code App, because an export carries anything else into the next environment.

    python scripts/verify-solution.py             # read-only; exit code 1 on any problem
    python scripts/verify-solution.py --fix       # set the preferred solution, add strays, re-verify
    python scripts/verify-solution.py --no-export # skip the export proof (faster)
    python scripts/verify-solution.py --all-users # sweep objects created by anyone, not just you
    python scripts/verify-solution.py --self-test # prove the guard itself works (creates and deletes one probe)

A table counts as covered when the solution holds it with rootcomponentbehavior 0 (include all
subcomponents), which is how the provisioner adds it; its columns, keys, relationships, forms and
views then travel with it and have no rows of their own.

A metadata answer that lacks something declared is re-read through fresh sessions before it is
reported missing, because a lagging server node can serve an older snapshot.

In an environment shared with other work, step 4 also sees that work's objects when the same account created them.
List them in .env as SOLUTION_GUARD_IGNORE=TYPE:ID,TYPE:ID (for example 300:<app id>); step 4 then skips them and
says so. The list never excuses anything inside the solution: step 5 has no exceptions.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Collection
from typing import Any, TypeVar

import flowlib
import schemalib
from dvweb import COMPONENT_TYPES, Dataverse, entity_id

TABLE, COLUMN, CHOICE, RELATIONSHIP, KEY = 1, 2, 9, 10, 14
WORKFLOW, CANVAS_APP, ENV_DEFINITION, ENV_VALUE, CONNECTION_REFERENCE = 29, 300, 380, 381, 10163

IGNORE_VARIABLE = "SOLUTION_GUARD_IGNORE"
GUID = re.compile(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
PROBE = "vz_zzGuardProbe"  # the throwaway environment variable that --self-test creates

# Once, columns, keys and relationships were missing from the metadata API while the solution
# export held them. A short answer is therefore re-read, with growing pauses, before it counts.
METADATA_READS = 4
METADATA_PAUSE = 2.0  # seconds; doubled after every short answer

T = TypeVar("T")

# entity set, primary entity (for the dynamic component type lookup), id column, label column,
# created-on column, creator column, fallback component type
SWEEPS = [
    ("canvasapps", "canvasapp", "canvasappid", "displayname", "createdtime", "_ownerid_value", 300),
    ("workflows", "workflow", "workflowid", "name", "createdon", "_createdby_value", 29),
    ("connectionreferences", "connectionreference", "connectionreferenceid", "connectionreferencelogicalname",
     "createdon", "_createdby_value", 10163),
    ("environmentvariabledefinitions", "environmentvariabledefinition", "environmentvariabledefinitionid",
     "schemaname", "createdon", "_createdby_value", 380),
    ("environmentvariablevalues", "environmentvariablevalue", "environmentvariablevalueid", "schemaname",
     "createdon", "_createdby_value", 381),
    ("appmodules", "appmodule", "appmoduleid", "uniquename", "createdon", "_createdby_value", 80),
    ("roles", "role", "roleid", "name", "createdon", "_createdby_value", 20),
    ("webresourceset", "webresource", "webresourceid", "name", "createdon", "_createdby_value", 61),
    ("pluginassemblies", "pluginassembly", "pluginassemblyid", "name", "createdon", "_createdby_value", 91),
    ("customapis", "customapi", "customapiid", "uniquename", "createdon", "_createdby_value", 10038),
    ("connectors", "connector", "connectorid", "name", "createdon", "_createdby_value", 372),
]

Stray = tuple[int, str, str]  # component type, object id, description


class Report:
    def __init__(self) -> None:
        self.problems: list[str] = []
        self.strays: list[Stray] = []
        self.fix_preferred = False
        self.unlisted_count = 0
        self.export_complete = False

    def ok(self, text: str) -> None:
        print(f"  ok    {text}")

    def warn(self, text: str) -> None:
        print(f"  warn  {text}")

    def fail(self, text: str) -> None:
        self.problems.append(text)
        print(f"  FAIL  {text}")

    def stray(self, ctype: int, object_id: str, text: str) -> None:
        self.strays.append((ctype, object_id, text))
        self.fail(f"{text} is not in the solution")

    def unlisted(self, text: str) -> None:
        self.unlisted_count += 1
        self.fail(f"{text} is not listed by the metadata API after {METADATA_READS} reads")


class Coverage:
    """What the solution holds, keyed by (component type, object id)."""

    def __init__(self, components: list[dict[str, Any]]) -> None:
        self.rows = {(c["componenttype"], c["objectid"].lower()): c.get("rootcomponentbehavior")
                     for c in components}

    def has(self, ctype: int, object_id: str) -> bool:
        return (ctype, object_id.lower()) in self.rows

    def covered(self, ctype: int, object_id: str, table_id: str) -> bool:
        return self.has(ctype, object_id) or self.rows.get((TABLE, table_id.lower())) == 0


def check_solution(dv: Dataverse, name: str, schema: dict[str, Any], report: Report) -> dict[str, Any] | None:
    rows = list(dv.list("solutions", {"$filter": f"uniquename eq '{name}'",
                                      "$select": "solutionid,version,ismanaged,createdon,_publisherid_value"}))
    if not rows:
        report.fail(f"solution {name} does not exist")
        return None
    sol = rows[0]
    pub = dv.get(f"publishers({sol['_publisherid_value']})", {"$select": "uniquename,customizationprefix"})
    if sol["ismanaged"]:
        report.fail(f"solution {name} is managed; this project builds in an unmanaged solution")
    elif pub["customizationprefix"] != schema["publisher_prefix"]:
        report.fail(f"solution publisher prefix is {pub['customizationprefix']}, expected {schema['publisher_prefix']}")
    else:
        report.ok(f"{name} v{sol['version']} is unmanaged; publisher {pub['uniquename']} ({pub['customizationprefix']})")

    preferred = dv.get("GetPreferredSolution()", missing_ok=True) or {}
    if str(preferred.get("solutionid", "")).lower() == sol["solutionid"].lower():
        report.ok(f"preferred solution of the signed-in user is {name}")
    else:
        report.fix_preferred = True
        report.fail(f"preferred solution is '{preferred.get('friendlyname', 'none')}', so portal-made objects "
                    f"would land outside {name}")
    return sol


def read_metadata(dv: Dataverse, report: Report, what: str, read: Callable[[], T], complete: Callable[[T], bool]) -> T:
    """Read metadata; while the answer lacks something expected, re-read it through a fresh session."""
    result = read()
    rereads = 0
    while not complete(result) and rereads < METADATA_READS - 1:
        time.sleep(METADATA_PAUSE * 2 ** rereads)
        rereads += 1
        dv.reset_affinity()
        result = read()
    if rereads and complete(result):
        report.warn(f"{what}: the metadata API answered incompletely {rereads} time(s) before a full answer "
                    "(lagging server node)")
    return result


def read_table_metadata(dv: Dataverse, table: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """One snapshot of a table: its attributes, keys and many-to-one relationships by name."""
    base = f"EntityDefinitions(LogicalName='{table}')"
    attrs = {a["LogicalName"]: a for a in dv.list(
        f"{base}/Attributes", {"$select": "LogicalName,MetadataId,AttributeOf,IsCustomAttribute"})}
    keys = {k["SchemaName"]: k for k in dv.list(
        f"{base}/Keys", {"$select": "SchemaName,MetadataId,EntityKeyIndexStatus"})}
    rels = {r["SchemaName"]: r["MetadataId"] for r in dv.list(
        f"{base}/ManyToOneRelationships", {"$select": "SchemaName,MetadataId"})}
    return attrs, keys, rels


def table_complete(snapshot: tuple[dict[str, Any], dict[str, Any], dict[str, str]],
                   columns: list[str], keys: list[dict[str, Any]], rels: list[dict[str, Any]]) -> bool:
    attrs_found, keys_found, rels_found = snapshot
    return (all(c in attrs_found for c in columns) and all(k["name"] in keys_found for k in keys)
            and all(r["name"] in rels_found for r in rels))


def check_declared(dv: Dataverse, schema: dict[str, Any], cov: Coverage, report: Report) -> None:
    prefix = schema["publisher_prefix"] + "_"
    declared_choices = {c["name"] for c in schema["global_choices"]}
    declared_tables = {t["name"] for t in schema["tables"]}

    choices = read_metadata(
        dv, report, "global choices",
        lambda: {c["Name"]: c["MetadataId"]
                 for c in dv.list("GlobalOptionSetDefinitions", {"$select": "Name,MetadataId"})},
        lambda found: declared_choices <= found.keys())
    for choice in schema["global_choices"]:
        name = choice["name"]
        if name not in choices:
            report.unlisted(f"global choice {name}")
        elif cov.has(CHOICE, choices[name]):
            report.ok(f"global choice {name}")
        else:
            report.stray(CHOICE, choices[name], f"global choice {name}")
    for name, object_id in choices.items():
        if name.startswith(prefix) and name not in declared_choices and not cov.has(CHOICE, object_id):
            report.stray(CHOICE, object_id, f"global choice {name}")

    entities = read_metadata(
        dv, report, "tables",
        lambda: {e["LogicalName"]: e["MetadataId"]
                 for e in dv.list("EntityDefinitions", {"$select": "LogicalName,MetadataId"})
                 if e["LogicalName"].startswith(prefix)},
        lambda found: declared_tables <= found.keys())
    for name, table_id in entities.items():
        if name not in declared_tables:
            if cov.has(TABLE, table_id):
                report.warn(f"table {name} is in the solution but not declared in schema.json")
            else:
                report.stray(TABLE, table_id, f"table {name}")

    for table in schema["tables"]:
        name = table["name"]
        if name not in entities:
            report.unlisted(f"table {name}")
            continue
        table_id = entities[name]
        if not cov.has(TABLE, table_id):
            report.stray(TABLE, table_id, f"table {name}")
            continue
        wanted = schemalib.column_names(schema, table)
        wanted_keys = [k for k in schema["keys"] if k["table"] == name]
        wanted_rels = [r for r in schema["relationships"] if r["referencing"] == name]
        attrs, keys, rels = read_metadata(
            dv, report, name, lambda: read_table_metadata(dv, name),
            lambda found: table_complete(found, wanted, wanted_keys, wanted_rels))
        problems = 0
        for column in wanted:
            if column not in attrs:
                report.unlisted(f"column {name}.{column}")
                problems += 1
            elif not cov.covered(COLUMN, attrs[column]["MetadataId"], table_id):
                report.stray(COLUMN, attrs[column]["MetadataId"], f"column {name}.{column}")
                problems += 1
        extra = sorted(c for c, a in attrs.items() if a.get("IsCustomAttribute") and not a.get("AttributeOf")
                       and c.startswith(prefix) and c not in wanted)
        if extra:
            report.warn(f"{name} has columns that schema.json does not declare: {', '.join(extra)}")

        for key in wanted_keys:
            row = keys.get(key["name"])
            if row is None:
                report.unlisted(f"key {key['name']}")
                problems += 1
            elif str(row["EntityKeyIndexStatus"]) != "Active":
                report.fail(f"key {key['name']} index is {row['EntityKeyIndexStatus']}, not Active")
                problems += 1
            elif not cov.covered(KEY, row["MetadataId"], table_id):
                report.stray(KEY, row["MetadataId"], f"key {key['name']}")
                problems += 1

        for rel in wanted_rels:
            if rel["name"] not in rels:
                report.unlisted(f"relationship {rel['name']}")
                problems += 1
            elif not cov.covered(RELATIONSHIP, rels[rel["name"]], table_id):
                report.stray(RELATIONSHIP, rels[rel["name"]], f"relationship {rel['name']}")
                problems += 1
        if not problems:
            report.ok(f"{name}: table, {len(wanted)} columns, {len(wanted_keys)} keys, "
                      f"{len(wanted_rels)} relationships")


def check_export(dv: Dataverse, schema: dict[str, Any], name: str, report: Report) -> None:
    inspect_export(dv.export_solution(name), schema, name, report)


def inspect_export(data: bytes, schema: dict[str, Any], name: str, report: Report) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        manifest = ET.fromstring(bundle.read("solution.xml"))
        custom = ET.fromstring(bundle.read("customizations.xml"))
    roots = {(rc.get("type"), (rc.get("schemaName") or "").lower()) for rc in manifest.iter("RootComponent")}
    tables: dict[str, tuple[set[str], set[str]]] = {}
    for entity in custom.findall("./Entities/Entity"):
        info = entity.find("./EntityInfo/entity")
        attributes = {a.get("PhysicalName", "").lower() for a in info.iter("attribute")} if info is not None else set()
        keys = {(k.findtext("Name") or "").lower() for k in entity.iter("EntityKey")}
        tables[(entity.findtext("Name") or "").lower()] = (attributes, keys)
    choices = {(o.get("Name") or "").lower() for o in custom.findall("./optionsets/optionset")}
    relationships = {(r.get("Name") or "").lower() for r in custom.findall("./EntityRelationships/EntityRelationship")}

    missing: list[str] = []
    counts = {"tables": 0, "columns": 0, "keys": 0, "relationships": 0, "choices": 0}
    for choice in schema["global_choices"]:
        counts["choices"] += 1
        if choice["name"] not in choices or (str(CHOICE), choice["name"]) not in roots:
            missing.append(f"global choice {choice['name']}")
    for table in schema["tables"]:
        counts["tables"] += 1
        attributes = tables.get(table["name"], (set(), set()))[0]
        if table["name"] not in tables or (str(TABLE), table["name"]) not in roots:
            missing.append(f"table {table['name']}")
            continue
        for column in schemalib.column_names(schema, table):
            counts["columns"] += 1
            if column not in attributes:
                missing.append(f"column {table['name']}.{column}")
    for key in schema["keys"]:
        counts["keys"] += 1
        if key["name"] not in tables.get(key["table"], (set(), set()))[1]:
            missing.append(f"key {key['name']}")
    for rel in schema["relationships"]:
        counts["relationships"] += 1
        if rel["name"] not in relationships:
            missing.append(f"relationship {rel['name']}")

    report.export_complete = not missing
    if missing:
        for item in missing:
            report.fail(f"export of {name} is missing {item}")
    else:
        report.ok(f"export of {name} contains all {counts['tables']} tables, {counts['columns']} columns, "
                  f"{counts['keys']} keys, {counts['relationships']} relationships and {counts['choices']} global choices")


def parse_ignore(text: str) -> frozenset[tuple[int, str]]:
    """The TYPE:ID pairs in a SOLUTION_GUARD_IGNORE value. A malformed entry is an error, so a typo cannot
    quietly switch a check off."""
    pairs: set[tuple[int, str]] = set()
    for entry in (part.strip() for part in text.split(",")):
        if not entry:
            continue
        ctype, _, object_id = entry.partition(":")
        if not ctype.strip().isdigit() or not GUID.fullmatch(object_id.strip()):
            raise ValueError(f"'{entry}' is not TYPE:ID, such as 300:<app id>")
        pairs.add((int(ctype), object_id.strip().lower()))
    return frozenset(pairs)


def component_types(dv: Dataverse) -> dict[str, int]:
    """Component type numbers by primary table name; some differ from one environment to the next."""
    return {d["primaryentityname"]: d["solutioncomponenttype"]
            for d in dv.list("solutioncomponentdefinitions", {"$select": "primaryentityname,solutioncomponenttype"})}


def sweep_strays(dv: Dataverse, sol: dict[str, Any], cov: Coverage, user_id: str | None, report: Report,
                 ignore: Collection[tuple[int, str]] = frozenset()) -> None:
    types = component_types(dv)
    since = sol["createdon"]
    for entity_set, primary, id_col, label_col, created_col, creator_col, fallback in SWEEPS:
        ctype = types.get(primary, fallback)
        flt = f"{created_col} ge {since}" + (f" and {creator_col} eq {user_id}" if user_id else "")
        rows = list(dv.list(entity_set, {"$select": f"{id_col},{label_col}", "$filter": flt}))
        outside = [r for r in rows if not cov.has(ctype, r[id_col])]
        reported = 0
        for row in outside:
            text = f"{COMPONENT_TYPES.get(ctype, entity_set)} '{row.get(label_col)}' ({entity_set})"
            if (ctype, row[id_col].lower()) in ignore:
                report.warn(f"{text} is outside the solution; skipped because it is listed in {IGNORE_VARIABLE}")
            else:
                report.stray(ctype, row[id_col], text)
                reported += 1
        if not reported:
            outcome = "none outside it" if not outside else f"{len(outside)} outside it, all listed in {IGNORE_VARIABLE}"
            report.ok(f"{entity_set}: {len(rows)} created since the solution, {outcome}")


def declared_names(schema: dict[str, Any], types: dict[str, int]) -> dict[int, set[str]]:
    """The lower-case name of every component this project puts in the solution, by component type. The Code App
    has no declared name, so check_contents counts it instead. A relationship's target table, such as the user
    table, is in the solution as a reference."""
    return {
        TABLE: {t["name"] for t in schema["tables"]} | {r["referenced"] for r in schema["relationships"]},
        CHOICE: {c["name"] for c in schema["global_choices"]},
        types.get("workflow", WORKFLOW): {spec.name for spec in flowlib.flow_specs(schema)},
        types.get("connectionreference", CONNECTION_REFERENCE): {ref.logical_name for ref in flowlib.CONNECTION_REFS},
        types.get("environmentvariabledefinition", ENV_DEFINITION): {var.schema_name for var in flowlib.ENV_VARS},
        types.get("environmentvariablevalue", ENV_VALUE): {var.schema_name for var in flowlib.ENV_VARS},
    }


def check_contents(dv: Dataverse, schema: dict[str, Any], components: list[dict[str, Any]], report: Report,
                   allow: Collection[str] = ()) -> None:
    """Fail on anything in the solution that this project does not declare. Nothing is removed for you: taking an
    object out of a solution is a decision, and it stays in the environment either way."""
    types = component_types(dv)
    where = {types.get(primary, fallback): (entity_set, label_col)
             for entity_set, primary, _, label_col, _, _, fallback in SWEEPS}
    where[TABLE] = ("EntityDefinitions", "LogicalName")
    where[CHOICE] = ("GlobalOptionSetDefinitions", "Name")
    declared = {ctype: {n.lower() for n in names} for ctype, names in declared_names(schema, types).items()}
    app_type = types.get("canvasapp", CANVAS_APP)
    allowed = {name.lower() for name in allow}

    apps: list[str] = []
    extras = 0
    for component in components:
        ctype, object_id = component["componenttype"], component["objectid"]
        entity_set, label_col = where.get(ctype, (None, None))
        row = dv.get(f"{entity_set}({object_id})", {"$select": label_col}, missing_ok=True) if entity_set else None
        name = (row or {}).get(label_col) if label_col else None
        label = COMPONENT_TYPES.get(ctype, f"Component of type {ctype}")
        shown = f"{label} '{name}'" if name else f"{label} {object_id}"
        if ctype == app_type:
            apps.append(shown)
        elif ctype in declared and name and name.lower() in declared[ctype] | allowed:
            continue
        else:
            extras += 1
            report.fail(f"{shown} is in the solution but this project does not declare it")
    if len(apps) > 1:
        extras += 1
        report.fail(f"{len(apps)} Code Apps are in the solution ({'; '.join(apps)}); this project ships one")
    if extras:
        report.warn("to take an object out: maker portal > Solutions > the solution > the object > Remove > "
                    "Remove from this solution (the object stays in the environment), then pull-solution.py")
    else:
        report.ok(f"{len(components)} components, every one declared by this project")


def run_checks(dv: Dataverse, schema: dict[str, Any], name: str, user_id: str | None, export: bool,
               ignore: Collection[tuple[int, str]] = frozenset(), allow: Collection[str] = ()) -> Report:
    report = Report()
    print("1. Solution")
    sol = check_solution(dv, name, schema, report)
    if sol is None:
        return report
    components = list(dv.list("solutioncomponents", {"$filter": f"_solutionid_value eq {sol['solutionid']}",
                                                     "$select": "componenttype,objectid,rootcomponentbehavior"}))
    cov = Coverage(components)
    print("2. Declared schema is in the solution")
    check_declared(dv, schema, cov, report)
    if export:
        print("3. Export proof")
        check_export(dv, schema, name, report)
        if report.unlisted_count and report.export_complete:
            print(f"  note  the export holds every declared object, so the {report.unlisted_count} the metadata API "
                  "did not list are in the solution; the API is lagging")
    print("4. Objects created since the solution that could sit outside it")
    sweep_strays(dv, sol, cov, user_id, report, ignore)
    print("5. Nothing else is in the solution")
    check_contents(dv, schema, components, report, allow)
    return report


def apply_fixes(dv: Dataverse, name: str, solution_id: str, report: Report) -> None:
    if report.fix_preferred:
        dv.action("SetPreferredSolution", {"SolutionId": solution_id})
        print(f"  set   preferred solution -> {name}")
    for ctype, object_id, text in report.strays:
        body: dict[str, Any] = {"ComponentId": object_id, "ComponentType": ctype, "SolutionUniqueName": name,
                                "AddRequiredComponents": False}
        if ctype == TABLE:
            body["DoNotIncludeSubcomponents"] = False
        dv.action("AddSolutionComponent", body)
        print(f"  added {text}")


def quietly(func: Any, *args: Any, **kwargs: Any) -> tuple[Any, list[str]]:
    """Run a check silently; return its result and only the lines that report a failure or a repair."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = func(*args, **kwargs)
    return result, [line for line in buffer.getvalue().splitlines() if line.startswith(("  FAIL", "  set", "  added"))]


def self_test(dv: Dataverse, schema: dict[str, Any], name: str, user_id: str | None,
              ignore: Collection[tuple[int, str]] = frozenset()) -> int:
    """Prove the guard works: create a throwaway environment variable, take it out of the solution,
    expect a failure, let --fix put it back, expect a pass, then delete it."""
    solution_id = next(dv.list("solutions", {"$filter": f"uniquename eq '{name}'", "$select": "solutionid"}))["solutionid"]

    def run(allow: Collection[str] = ()) -> tuple[Report, list[str]]:
        return quietly(run_checks, dv, schema, name, user_id, False, ignore, allow)

    baseline, _ = run()
    if baseline.problems:
        print("SELF-TEST ABORTED: the solution is not clean to start with; run verify-solution.py --fix first.")
        return 1

    probe = None
    results: dict[str, bool] = {}
    try:
        print("Self-test: create a throwaway environment variable with no solution header, then take it out of the solution")
        probe = entity_id(dv.request("POST", "environmentvariabledefinitions", body={
            "schemaname": PROBE, "displayname": "zz guard probe (temporary)", "type": 100000000}))
        row = next(dv.list("solutioncomponents", {"$filter": f"_solutionid_value eq {solution_id} and objectid eq {probe}",
                                                  "$select": "objectid"}), None)
        results["a plain create lands in the solution (preferred solution works)"] = row is not None
        if row:
            # the API reads the component's own id from this slot, not the membership row id
            dv.action("RemoveSolutionComponent", {
                "SolutionComponent": {"@odata.type": "Microsoft.Dynamics.CRM.solutioncomponent",
                                      "solutioncomponentid": probe},
                "ComponentType": 380, "SolutionUniqueName": name})

        broken, lines = run()
        print("  guard output while the object is outside the solution (this failure is expected):")
        for line in lines:
            print("   " + line.strip())
        results["the guard fails on an object outside the solution"] = any(
            object_id.lower() == probe.lower() for _, object_id, _ in broken.strays)

        _, lines = quietly(apply_fixes, dv, name, solution_id, broken)
        for line in lines:
            print("   " + line.strip())
        # back in the solution, the probe is an object the project does not declare, so step 5 must be told about it
        fixed, _ = run(allow=[PROBE])
        results["--fix adds it back and the guard passes"] = not fixed.problems
        results["the guard fails on an object the project does not declare"] = bool(run()[0].problems)
    finally:
        if probe:
            dv.request("DELETE", f"environmentvariabledefinitions({probe})")
    clean, _ = run()
    results["probe deleted and the solution is clean again"] = not clean.problems

    for text, passed in results.items():
        print(f"  {'ok  ' if passed else 'FAIL'}  {text}")
    if all(results.values()):
        print("SELF-TEST PASSED: the guard catches a stray object, an undeclared one, and --fix repairs the stray.")
        return 0
    print("SELF-TEST FAILED.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="set the preferred solution and add strays, then re-verify")
    parser.add_argument("--no-export", action="store_true", help="skip the export proof")
    parser.add_argument("--all-users", action="store_true", help="sweep objects created by anyone, not just you")
    parser.add_argument("--self-test", action="store_true", help="prove the guard catches a violation (creates and deletes one probe)")
    parser.add_argument("--solution", help="override the solution unique name from schema.json")
    args = parser.parse_args()

    schema = schemalib.load_schema()
    name = args.solution or schema["solution"]
    dv = Dataverse("dv-solution", solution=name)
    try:
        ignore = parse_ignore(os.environ.get(IGNORE_VARIABLE, ""))
    except ValueError as error:
        print(f"{IGNORE_VARIABLE}: {error}")
        return 1
    user_id = None if args.all_users else dv.whoami()["UserId"]
    print(f"Verifying {name} on {dv.base_url}" + (f" as user {user_id}" if user_id else " (all users)"))
    if args.self_test:
        return self_test(dv, schema, name, user_id, ignore)

    report = run_checks(dv, schema, name, user_id, not args.no_export, ignore)
    if args.fix and (report.strays or report.fix_preferred):
        sol = next(dv.list("solutions", {"$filter": f"uniquename eq '{name}'", "$select": "solutionid"}))
        print("\nApplying fixes")
        apply_fixes(dv, name, sol["solutionid"], report)
        print("\nRe-verifying")
        report = run_checks(dv, schema, name, user_id, not args.no_export, ignore)

    print()
    if report.problems:
        lagging = report.unlisted_count == len(report.problems) and report.export_complete
        hint = ("The export holds everything, so the metadata API is lagging: re-run in a few minutes."
                if lagging else "Run with --fix to repair what can be repaired; it adds objects and never removes one.")
        print(f"FAILED: {len(report.problems)} problem(s). {hint}")
        return 1
    print(f"VERIFIED: everything checked is inside {name}, and nothing else is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
