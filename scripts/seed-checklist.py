"""Seed the Vizient checklist items into Dataverse.

checklist/checklist.json is the single source of truth. This script makes the vz_checklistitem table
match it: one row per item, matched on the alternate key vz_key.

    python scripts/seed-checklist.py           # offline: validate the file and say what it holds
    python scripts/seed-checklist.py --status  # read-only: compare Dataverse with the file; exit 1 if they differ
    python scripts/seed-checklist.py --apply   # create the missing rows and update the ones that differ

The rows are data, so they are not solution components; the table that holds them is already in the
solution. A row in Dataverse that is not in the file is reported and left alone: nothing is deleted.
Dataverse must be signed in as AZURE_ACCOUNT from .env, or the script stops before it reads anything else.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import checklistlib
import schemalib
from dvweb import Dataverse, DataverseError, signed_in_account

TABLE = "vz_checklistitem"
ID_COLUMN = "vz_checklistitemid"
KEY = "vz_key"
COLUMNS = ("vz_name", "vz_group", "vz_definition", "vz_hasjudgment", "vz_sortorder", "vz_isactive")


class SeedError(RuntimeError):
    """A failure worth one clear line, not a stack trace."""


@dataclass
class Plan:
    create: list[dict[str, Any]] = field(default_factory=list)
    update: list[tuple[str, dict[str, Any], list[str]]] = field(default_factory=list)  # row id, wanted row, changed columns
    unchanged: int = 0
    extra: list[str] = field(default_factory=list)  # keys Dataverse holds and the file does not

    @property
    def in_sync(self) -> bool:
        return not self.create and not self.update


def _text(value: Any) -> Any:
    """Dataverse hands multi-line text back with CRLF, whatever was written."""
    return value.replace("\r\n", "\n") if isinstance(value, str) else value


def make_plan(wanted: list[dict[str, Any]], existing: list[dict[str, Any]]) -> Plan:
    counts = Counter(row[KEY] for row in existing)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise SeedError(f"Dataverse holds more than one row for {', '.join(duplicates)}; remove the duplicates by hand")
    held = {row[KEY]: row for row in existing}
    plan = Plan()
    for row in wanted:
        current = held.pop(row[KEY], None)
        if current is None:
            plan.create.append(row)
            continue
        changed = [column for column in COLUMNS if _text(current.get(column)) != _text(row[column])]
        if changed:
            plan.update.append((current[ID_COLUMN], row, changed))
        else:
            plan.unchanged += 1
    plan.extra = sorted(held)
    return plan


def entity_set_name(dv: Dataverse) -> str:
    meta = dv.get(f"EntityDefinitions(LogicalName='{TABLE}')", {"$select": "EntitySetName"}, missing_ok=True)
    if not meta:
        raise SeedError(f"the table {TABLE} does not exist. Run: python scripts/provision-dataverse.py")
    return meta["EntitySetName"]


def read_rows(dv: Dataverse, entity_set: str) -> list[dict[str, Any]]:
    return list(dv.list(entity_set, {"$select": ",".join((ID_COLUMN, KEY, *COLUMNS))}))


def check_account(dv: Dataverse, expected: str | None) -> str:
    """The signed-in account, after proving it is the one named in .env (when one is named)."""
    account = signed_in_account(dv)
    if expected and account.lower() != expected.lower():
        raise SeedError(f"Dataverse is signed in as {account}, but AZURE_ACCOUNT expects {expected}")
    return account


def describe(plan: Plan, log: Callable[[str], None] = print) -> None:
    for row in plan.create:
        log(f"  create  {row[KEY]}")
    for _row_id, row, changed in plan.update:
        log(f"  update  {row[KEY]}  ({', '.join(changed)})")
    for key in plan.extra:
        log(f"  extra   {key}  (in Dataverse, not in checklist.json; left alone)")
    log(f"{len(plan.create)} to create, {len(plan.update)} to update, {plan.unchanged} unchanged, {len(plan.extra)} extra")


def sync(dv: Dataverse, wanted: list[dict[str, Any]], apply: bool, log: Callable[[str], None] = print) -> Plan:
    """Compare the table with the file and, when asked, write the difference. Returns the plan that now holds."""
    entity_set = entity_set_name(dv)
    plan = make_plan(wanted, read_rows(dv, entity_set))
    describe(plan, log)
    if not apply or plan.in_sync:
        return plan
    for row in plan.create:
        dv.request("POST", entity_set, body=row)
    for row_id, row, changed in plan.update:
        dv.request("PATCH", f"{entity_set}({row_id})", body={column: row[column] for column in changed},
                   headers={"If-Match": "*"})
    dv.reset_affinity()
    after = make_plan(wanted, read_rows(dv, entity_set))
    if not after.in_sync:
        raise SeedError("the table still differs from checklist.json after the write; run --status to see how")
    log(f"wrote {len(plan.create) + len(plan.update)} row(s); Dataverse now matches checklist.json")
    return after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="read-only comparison with Dataverse; exit 1 if it differs")
    mode.add_argument("--apply", action="store_true", help="create the missing rows and update the ones that differ")
    args = parser.parse_args(argv)

    try:
        schema = schemalib.load_schema()
        data = checklistlib.load_checklist(schema=schema)
        wanted = sorted(checklistlib.seed_rows(data, schema), key=lambda row: row["vz_sortorder"])
        if not (args.status or args.apply):
            groups = Counter(item["group"] for item in data["items"])
            print(f"checklist.json is valid: {len(wanted)} rows ({', '.join(f'{n} {group}' for group, n in groups.items())}).")
            print("Nothing was sent. Run with --status to compare with Dataverse, or --apply to write.")
            return 0
        dv = Dataverse("dv-data")
        account = check_account(dv, os.environ.get("AZURE_ACCOUNT") or None)
        print(f"Signed in as {account}; environment {urlparse(dv.base_url).hostname}")
        return 0 if sync(dv, wanted, apply=args.apply).in_sync else 1
    except (SeedError, DataverseError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
