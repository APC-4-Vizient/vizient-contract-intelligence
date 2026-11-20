"""Create the Vizient Contract POC Dataverse schema inside the VizientContractPOC solution.

Idempotent: existing objects are skipped and missing ones are created. Every metadata create
goes through Dataverse.create_metadata, which always sends the MSCRM.SolutionUniqueName header.
Prove membership afterwards with scripts/verify-solution.py.

    python scripts/provision-dataverse.py --dry-run   # read-only: show what would be created
    python scripts/provision-dataverse.py
"""

from __future__ import annotations

import argparse
import sys
import time
from functools import partial
from typing import Any

import schemalib
from dvweb import Dataverse, DataverseError, label, wait_for

NS = "Microsoft.Dynamics.CRM."
PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"


def cascade(kind: str) -> dict[str, str]:
    if kind == "parental":
        return {"Assign": "Cascade", "Delete": "Cascade", "Merge": "NoCascade", "Reparent": "Cascade",
                "Share": "Cascade", "Unshare": "Cascade", "RollupView": "NoCascade"}
    delete = {"removelink": "RemoveLink", "restrict": "Restrict"}[kind]
    return {"Assign": "NoCascade", "Delete": delete, "Merge": "NoCascade", "Reparent": "NoCascade",
            "Share": "NoCascade", "Unshare": "NoCascade", "RollupView": "NoCascade"}


class Provisioner:
    def __init__(self, dv: Dataverse, schema: dict[str, Any], dry_run: bool) -> None:
        self.dv = dv
        self.schema = schema
        self.dry_run = dry_run
        self.global_ids: dict[str, str] = {}
        self.created: list[str] = []
        self.existing = 0

    def log(self, verb: str, what: str) -> None:
        print(f"  {verb:<8} {what}")

    def skip(self, what: str) -> None:
        self.existing += 1
        self.log("exists", what)

    def create(self, path: str, body: dict[str, Any], what: str) -> None:
        if self.dry_run:
            self.created.append(what)
            self.log("would", f"create {what}")
            return
        for attempt in range(5):
            try:
                self.dv.create_metadata(path, body)
                break
            except DataverseError as exc:
                # A freshly created parent can take a few seconds to become visible to the next call.
                stale = exc.status == 404 or "does not exist" in exc.message.lower()
                if not stale or attempt == 4:
                    raise
                time.sleep(6)
        self.created.append(what)
        self.log("created", what)

    def names(self, path: str, field: str) -> set[str]:
        resp = self.dv.get(path, {"$select": field}, missing_ok=True)
        return {row[field] for row in resp["value"]} if resp else set()

    def column_payload(self, col: dict[str, Any]) -> dict[str, Any]:
        kind = col["type"]
        body: dict[str, Any] = {
            "SchemaName": col["name"],
            "DisplayName": label(col["display"]),
            "RequiredLevel": {"Value": "ApplicationRequired" if col.get("required") else "None"},
        }
        if col.get("description"):
            body["Description"] = label(col["description"])
        if kind == "string":
            body.update({"@odata.type": NS + "StringAttributeMetadata", "MaxLength": col["max_length"],
                         "FormatName": {"Value": "Text"}})
        elif kind == "url":
            body.update({"@odata.type": NS + "StringAttributeMetadata", "MaxLength": col.get("max_length", 2000),
                         "FormatName": {"Value": "Url"}})
        elif kind == "memo":
            body.update({"@odata.type": NS + "MemoAttributeMetadata", "Format": "TextArea",
                         "MaxLength": col["max_length"]})
        elif kind == "int":
            body.update({"@odata.type": NS + "IntegerAttributeMetadata", "Format": "None",
                         "MinValue": col.get("min", schemalib.INT32_MIN),
                         "MaxValue": col.get("max", schemalib.INT32_MAX)})
        elif kind == "decimal":
            body.update({"@odata.type": NS + "DecimalAttributeMetadata", "Precision": col["precision"],
                         "MinValue": col["min"], "MaxValue": col["max"]})
        elif kind == "bool":
            body.update({
                "@odata.type": NS + "BooleanAttributeMetadata",
                "DefaultValue": bool(col.get("default", False)),
                "OptionSet": {"@odata.type": NS + "BooleanOptionSetMetadata",
                              "TrueOption": {"Value": 1, "Label": label("Yes")},
                              "FalseOption": {"Value": 0, "Label": label("No")}},
            })
        elif kind == "date":
            # Explicit DateTimeBehavior: columns created without it break Filtered view generation.
            body.update({"@odata.type": NS + "DateTimeAttributeMetadata", "Format": "DateOnly",
                         "DateTimeBehavior": {"Value": "DateOnly"}})
        elif kind == "datetime":
            body.update({"@odata.type": NS + "DateTimeAttributeMetadata", "Format": "DateAndTime",
                         "DateTimeBehavior": {"Value": "UserLocal"}})
        elif kind == "file":
            body.update({"@odata.type": NS + "FileAttributeMetadata", "MaxSizeInKB": col.get("max_size_kb", 32768)})
        elif kind == "choice":
            opts = schemalib.options(self.schema, col["options"])
            body.update({
                "@odata.type": NS + "PicklistAttributeMetadata",
                "OptionSet": {"@odata.type": NS + "OptionSetMetadata", "IsGlobal": False, "OptionSetType": "Picklist",
                              "Options": [{"Value": value, "Label": label(text)} for value, text in opts]},
            })
            if "default" in col:
                body["DefaultFormValue"] = {text: value for value, text in opts}[col["default"]]
        elif kind == "globalchoice":
            global_id = self.global_ids.get(col["global"], PLACEHOLDER_ID)
            body.update({"@odata.type": NS + "PicklistAttributeMetadata",
                         "GlobalOptionSet@odata.bind": f"/GlobalOptionSetDefinitions({global_id})"})
        else:
            raise ValueError(f"{col['name']}: unsupported column type '{kind}'")
        return body

    def table_payload(self, table: dict[str, Any]) -> dict[str, Any]:
        primary = table["primary"]
        return {
            "@odata.type": NS + "EntityMetadata",
            "SchemaName": table["name"],
            "DisplayName": label(table["display"]),
            "DisplayCollectionName": label(table["plural"]),
            "Description": label(table["description"]),
            "OwnershipType": table["ownership"],
            "HasActivities": False,
            "HasNotes": False,
            "IsActivity": False,
            "Attributes": [{
                "@odata.type": NS + "StringAttributeMetadata",
                "AttributeType": "String",
                "AttributeTypeName": {"Value": "StringType"},
                "SchemaName": primary["name"],
                "DisplayName": label(primary["display"]),
                "Description": label(primary["description"]),
                "IsPrimaryName": True,
                "RequiredLevel": {"Value": "ApplicationRequired"},
                "MaxLength": primary["max_length"],
                "FormatName": {"Value": "Text"},
            }],
        }

    def relationship_payload(self, rel: dict[str, Any]) -> dict[str, Any]:
        return {
            "@odata.type": NS + "OneToManyRelationshipMetadata",
            "SchemaName": rel["name"],
            "ReferencedEntity": rel["referenced"],
            "ReferencedAttribute": rel["referenced"] + "id",
            "ReferencingEntity": rel["referencing"],
            "CascadeConfiguration": cascade(rel["cascade"]),
            "Lookup": {
                "@odata.type": NS + "LookupAttributeMetadata",
                "SchemaName": rel["lookup"],
                "DisplayName": label(rel["display"]),
                "Description": label(rel["description"]),
                "RequiredLevel": {"Value": "ApplicationRequired" if rel.get("required") else "None"},
            },
        }

    def global_choices(self) -> None:
        print("Global choices")
        for choice in self.schema["global_choices"]:
            name = choice["name"]
            path = f"GlobalOptionSetDefinitions(Name='{name}')"
            found = self.dv.get(path, {"$select": "MetadataId"}, missing_ok=True)
            if found:
                self.global_ids[name] = found["MetadataId"]
                self.skip(f"global choice {name}")
                continue
            body = {
                "@odata.type": NS + "OptionSetMetadata",
                "Name": name,
                "DisplayName": label(choice["display"]),
                "Description": label(choice["description"]),
                "IsGlobal": True,
                "OptionSetType": "Picklist",
                "Options": [{"Value": value, "Label": label(text)}
                            for value, text in schemalib.options(self.schema, choice["options"])],
            }
            self.create("GlobalOptionSetDefinitions", body, f"global choice {name}")
            if not self.dry_run:
                self.global_ids[name] = self.dv.get(path, {"$select": "MetadataId"})["MetadataId"]

    def tables(self) -> None:
        print("Tables")
        for table in self.schema["tables"]:
            name = table["name"]
            path = f"EntityDefinitions(LogicalName='{name}')"
            if self.dv.exists(path):
                self.skip(f"table {name}")
                continue
            self.create("EntityDefinitions", self.table_payload(table), f"table {name}")
            if not self.dry_run:
                wait_for(partial(self.dv.exists, path), f"table {name}")
                time.sleep(5)

    def columns(self) -> None:
        print("Columns")
        for table in self.schema["tables"]:
            name = table["name"]
            path = f"EntityDefinitions(LogicalName='{name}')/Attributes"
            present = self.names(path, "LogicalName")
            for col in table["columns"]:
                if col["name"] in present:
                    self.skip(f"column {name}.{col['name']}")
                else:
                    self.create(path, self.column_payload(col), f"column {name}.{col['name']}")

    def key_status(self, key: dict[str, Any]) -> str:
        path = f"EntityDefinitions(LogicalName='{key['table']}')/Keys"
        resp = self.dv.get(path, {"$select": "SchemaName,EntityKeyIndexStatus"})
        for row in resp["value"]:
            if row["SchemaName"] == key["name"]:
                return str(row["EntityKeyIndexStatus"])
        return "Missing"

    def key_active(self, key: dict[str, Any]) -> bool:
        status = self.key_status(key)
        if status == "Failed":
            raise RuntimeError(f"Alternate key {key['name']} index build failed")
        return status == "Active"

    def keys(self) -> None:
        print("Alternate keys")
        for key in self.schema["keys"]:
            path = f"EntityDefinitions(LogicalName='{key['table']}')/Keys"
            if key["name"] in self.names(path, "SchemaName"):
                self.skip(f"key {key['name']}")
            else:
                body = {"SchemaName": key["name"], "DisplayName": label(key["display"]),
                        "KeyAttributes": key["columns"]}
                self.create(path, body, f"key {key['name']}")
            if self.dry_run:
                continue
            wait_for(partial(self.key_active, key), f"alternate key {key['name']} index", timeout=300, interval=5)
            self.log("active", f"key {key['name']}")

    def relationships(self) -> None:
        print("Relationships and lookup columns")
        present: dict[str, set[str]] = {}
        for rel in self.schema["relationships"]:
            table = rel["referencing"]
            if table not in present:
                present[table] = self.names(f"EntityDefinitions(LogicalName='{table}')/ManyToOneRelationships",
                                            "SchemaName")
            if rel["name"] in present[table]:
                self.skip(f"relationship {rel['name']} ({table}.{rel['lookup']})")
            else:
                self.create("RelationshipDefinitions", self.relationship_payload(rel),
                            f"relationship {rel['name']} ({table}.{rel['lookup']})")

    def publish(self) -> None:
        if self.dry_run or not self.created:
            return
        print("Publish")
        entities = "".join(f"<entity>{table['name']}</entity>" for table in self.schema["tables"])
        optionsets = "".join(f"<optionset>{choice['name']}</optionset>" for choice in self.schema["global_choices"])
        xml = f"<importexportxml><entities>{entities}</entities><optionsets>{optionsets}</optionsets></importexportxml>"
        self.dv.action("PublishXml", {"ParameterXml": xml})
        self.log("done", "PublishXml for the declared tables and global choices")


def preflight(dv: Dataverse, schema: dict[str, Any], solution: str) -> dict[str, Any]:
    rows = list(dv.list("solutions", {"$filter": f"uniquename eq '{solution}'",
                                      "$select": "solutionid,ismanaged,version,_publisherid_value"}))
    if not rows:
        sys.exit(f"Solution '{solution}' does not exist. Create it first; refusing to build outside a solution.")
    sol = rows[0]
    if sol["ismanaged"]:
        sys.exit(f"Solution '{solution}' is managed; metadata can only be added to an unmanaged solution.")
    pub = dv.get(f"publishers({sol['_publisherid_value']})",
                 {"$select": "customizationprefix,customizationoptionvalueprefix"})
    if (pub["customizationprefix"], pub["customizationoptionvalueprefix"]) != (
            schema["publisher_prefix"], schema["option_value_prefix"]):
        sys.exit(f"Publisher mismatch: env has {pub['customizationprefix']}/{pub['customizationoptionvalueprefix']}, "
                 f"schema expects {schema['publisher_prefix']}/{schema['option_value_prefix']}")
    return sol


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="read-only: report what would be created")
    parser.add_argument("--solution", help="override the solution unique name from schema.json")
    args = parser.parse_args()

    schema = schemalib.load_schema()
    solution = args.solution or schema["solution"]
    dv = Dataverse("dv-metadata", solution=solution)
    sol = preflight(dv, schema, solution)
    print(f"Target {dv.base_url}  solution {solution} v{sol['version']} (unmanaged)"
          f"{'  [dry run]' if args.dry_run else ''}")

    work = Provisioner(dv, schema, args.dry_run)
    work.global_choices()
    work.tables()
    work.columns()
    work.keys()
    work.relationships()
    work.publish()

    verb = "would create" if args.dry_run else "created"
    print(f"\nDone: {verb} {len(work.created)}, already present {work.existing}.")
    print("Next: python scripts/verify-solution.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
