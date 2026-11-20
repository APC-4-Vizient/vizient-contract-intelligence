"""Checklist helpers shared by analyzer/build_schema.py, scripts/seed-checklist.py and the tests.

checklist/checklist.json is the single source of truth. validate() is the offline guard that keeps it
consistent with dataverse/schema.json and the Content Understanding field limits.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import schemalib

ROOT = schemalib.ROOT
CHECKLIST_PATH = ROOT / "checklist" / "checklist.json"

FIELD_TYPES = {"string", "date", "number", "integer", "boolean"}
METHODS = {"extract", "generate", "classify"}
JUDGMENTS = ("Permitted", "Prohibited", "Conditional", "Not Addressed")
KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
FLAT_SUFFIXES = ("_Judgment", "_Conditions", "_Clause")
MAX_FIELD_NAME = 64
DETAIL_ONLY = {"type", "method", "enum", "enumDescriptions"}
MANUAL_FORBIDDEN = DETAIL_ONLY | {"hasJudgment", "judgments"}


def load_checklist(path: Path = CHECKLIST_PATH, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = validate(data, schema or schemalib.load_schema())
    if problems:
        raise ValueError("checklist.json is invalid:\n  " + "\n  ".join(problems))
    return data


def analyzer_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in data["items"] if item["source"] == "analyzer"]


def detail_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in analyzer_items(data) if item["group"] == "Contract Detail"]


def right_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in analyzer_items(data) if item["group"] == "Data Right"]


def manual_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in data["items"] if item["source"] == "manual"]


def judgments_for(data: dict[str, Any], item: dict[str, Any]) -> dict[str, str]:
    """The judgments a right may return, each with its meaning. An item can narrow the default set."""
    return dict(item.get("judgments") or data["defaultJudgments"])


def seed_rows(data: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
    """One vz_checklistitem row per checklist item, with the choice value of its group."""
    group_labels = _column(_table(schema, "vz_checklistitem"), "vz_group")["options"]
    group_values = {text: value for value, text in schemalib.options(schema, group_labels)}
    return [
        {
            "vz_key": item["key"],
            "vz_name": item["label"],
            "vz_group": group_values[item["group"]],
            "vz_definition": item["definition"],
            "vz_hasjudgment": bool(item.get("hasJudgment", False)),
            "vz_sortorder": item["sortOrder"],
            "vz_isactive": item["isActive"],
        }
        for item in data["items"]
    ]


def validate(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Return every problem found, so one run shows them all."""
    table = _table(schema, "vz_checklistitem")
    groups = _column(table, "vz_group")["options"]
    judgment_choice = next(c for c in schema["global_choices"] if c["name"] == "vz_judgment")["options"]
    lookups = {r["lookup"] for r in schema["relationships"] if r["referencing"] == "vz_contract"}
    limits = {
        "key": _column(table, "vz_key")["max_length"],
        "label": table["primary"]["max_length"],
        "definition": _column(table, "vz_definition")["max_length"],
    }
    sort_column = _column(table, "vz_sortorder")

    problems: list[str] = []
    if not isinstance(data.get("version"), int) or data["version"] < 1:
        problems.append("version must be an integer of 1 or more")
    if not str(data.get("rightSuffix", "")).strip():
        problems.append("rightSuffix must not be empty")
    defaults = data.get("defaultJudgments", {})
    if tuple(defaults) != JUDGMENTS or not all(isinstance(text, str) and text.strip() for text in defaults.values()):
        problems.append(f"defaultJudgments must describe {list(JUDGMENTS)} in that order")
    if not set(JUDGMENTS) <= set(judgment_choice):
        problems.append("schema choice vz_judgment lacks a judgment the checklist uses")

    seen: set[str] = set()
    previous_order = None
    for index, item in enumerate(data.get("items", [])):
        name = str(item.get("key", f"#{index}"))
        problems += [f"{name}: {text}" for text in _item_problems(item, groups, lookups, limits, set(defaults))]
        if name.lower() in seen:
            problems.append(f"{name}: duplicate key (the vz_key alternate key compares case-insensitively)")
        seen.add(name.lower())
        order = item.get("sortOrder")
        if not isinstance(order, int) or isinstance(order, bool) or not sort_column["min"] <= order <= sort_column["max"]:
            problems.append(f"{name}: sortOrder must be an integer from {sort_column['min']} to {sort_column['max']}")
        elif previous_order is not None and order <= previous_order:
            problems.append(f"{name}: sortOrder must increase down the list")
        else:
            previous_order = order
    if not data.get("items"):
        problems.append("items must not be empty")
    return problems


def _item_problems(item: dict[str, Any], groups: list[str], lookups: set[str],
                   limits: dict[str, int], judgment_names: set[str]) -> list[str]:
    out: list[str] = []
    key = item.get("key", "")
    longest_suffix = max(len(suffix) for suffix in FLAT_SUFFIXES)
    if (not isinstance(key, str) or not KEY_PATTERN.match(key) or len(key) > limits["key"]
            or len(key) + longest_suffix > MAX_FIELD_NAME):
        out.append("key must start with a letter, use letters, digits and underscores, "
                   "and leave room for the flat field suffixes")
    for field in ("label", "definition"):
        text = item.get(field)
        if not isinstance(text, str) or not text.strip() or len(text) > limits[field]:
            out.append(f"{field} must be 1 to {limits[field]} characters")
    if item.get("group") not in groups:
        out.append(f"group must be one of {groups}")
    if not isinstance(item.get("isActive"), bool):
        out.append("isActive must be true or false")

    source, group = item.get("source"), item.get("group")
    if source == "manual":
        if group != "Manual":
            out.append("manual items belong to the Manual group")
        if item.get("lookup") not in lookups:
            out.append(f"lookup must be a vz_contract lookup, one of {sorted(lookups)}")
        extra = MANUAL_FORBIDDEN & set(item)
        if extra:
            out.append(f"manual items cannot carry analyzer settings: {sorted(extra)}")
    elif source == "analyzer":
        if group == "Manual":
            out.append("the Manual group is for manual items")
        elif group == "Data Right":
            out += _right_problems(item, judgment_names)
        elif group == "Contract Detail":
            out += _detail_problems(item)
    else:
        out.append("source must be 'analyzer' or 'manual'")
    return out


def _right_problems(item: dict[str, Any], judgment_names: set[str]) -> list[str]:
    out: list[str] = []
    if item.get("hasJudgment") is not True:
        out.append("data rights must set hasJudgment to true")
    extra = DETAIL_ONLY & set(item)
    if extra:
        out.append(f"a data right always returns Judgment, Conditions and Clause, so remove {sorted(extra)}")
    custom = item.get("judgments")
    if custom is not None and (
            not set(custom) <= judgment_names or "Not Addressed" not in custom
            or not all(isinstance(text, str) and text.strip() for text in custom.values())):
        out.append("judgments must name known judgments, include 'Not Addressed' and describe each one")
    return out


def _detail_problems(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if item.get("hasJudgment") or "judgments" in item:
        out.append("only data rights carry a judgment")
    if item.get("type") not in FIELD_TYPES:
        out.append(f"type must be one of {sorted(FIELD_TYPES)}")
    if item.get("method") not in METHODS:
        out.append(f"method must be one of {sorted(METHODS)}")
    values = item.get("enum")
    if item.get("method") == "classify":
        if (not isinstance(values, list) or not values or len(set(values)) != len(values)
                or not all(isinstance(value, str) and value.strip() for value in values)):
            out.append("classify fields need a non-empty list of unique enum values")
        elif "enumDescriptions" in item and set(item["enumDescriptions"]) != set(values):
            out.append("enumDescriptions must describe exactly the enum values")
    elif values is not None or "enumDescriptions" in item:
        out.append("only classify fields take an enum")
    return out


def _table(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return next(table for table in schema["tables"] if table["name"] == name)


def _column(table: dict[str, Any], name: str) -> dict[str, Any]:
    return next(column for column in table["columns"] if column["name"] == name)
