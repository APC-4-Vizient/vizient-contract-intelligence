"""Schema spec helpers shared by provision-dataverse.py and verify-solution.py."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "dataverse" / "schema.json"
INT32_MIN, INT32_MAX = -2147483648, 2147483647


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    validate(schema)
    return schema


def validate(schema: dict[str, Any]) -> None:
    prefix = f"{schema['publisher_prefix']}_"
    names = [choice["name"] for choice in schema["global_choices"]]
    for table in schema["tables"]:
        names += [table["name"], table["primary"]["name"]] + [col["name"] for col in table["columns"]]
    names += [key["name"] for key in schema["keys"]]
    for rel in schema["relationships"]:
        names += [rel["name"], rel["lookup"]]
    wrong = [name for name in names if not name.startswith(prefix)]
    if wrong:
        raise ValueError(f"Names outside the '{prefix}' publisher prefix: {wrong}")
    declared_tables = {table["name"] for table in schema["tables"]}
    for rel in schema["relationships"]:
        if rel["referencing"] not in declared_tables:
            raise ValueError(f"{rel['name']}: referencing table {rel['referencing']} is not declared")


def option_value(schema: dict[str, Any], position: int) -> int:
    return schema["option_value_prefix"] * 10000 + position


def options(schema: dict[str, Any], labels: list[str]) -> list[tuple[int, str]]:
    return [(option_value(schema, index), text) for index, text in enumerate(labels)]


def column_names(schema: dict[str, Any], table: dict[str, Any]) -> list[str]:
    """Every column the schema declares for a table: primary name, plain columns and lookups."""
    names = [table["primary"]["name"]] + [col["name"] for col in table["columns"]]
    names += [rel["lookup"] for rel in schema["relationships"] if rel["referencing"] == table["name"]]
    return names
