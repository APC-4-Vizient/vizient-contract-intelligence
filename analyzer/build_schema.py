"""Generate the Content Understanding analyzer definitions from checklist/checklist.json.

    python analyzer/build_schema.py --write    regenerate both committed files
    python analyzer/build_schema.py --check    exit 1 if a committed file is missing or stale

Both layouts carry the same 20 checklist items and differ only in how a data right is shaped:
  nested  Right_X is an object with Judgment, Conditions and Clause (the brief's default).
  flat    Right_X_Judgment, Right_X_Conditions and Right_X_Clause are top-level fields. This is the
          fallback if nested objects do not return reliable grounding (brief section 4b).

The analyzer refers to the model aliases below, not to a model. PATCH /contentunderstanding/defaults
maps those aliases to deployments, so changing the model never needs a new analyzer. If the service
rejects the aliases for a custom analyzer, put model names in MODELS and run --write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import checklistlib  # noqa: E402

LAYOUTS = ("nested", "flat")
# Letters, digits, dots and underscores: the stricter of the analyzer reference and the REST schema.
ANALYZER_IDS = {"nested": "vizientContractChecklist", "flat": "vizientContractChecklistFlat"}
OUTPUT_FILES = {
    "nested": ROOT / "analyzer" / "vizient-contract-checklist.json",
    "flat": ROOT / "analyzer" / "vizient-contract-checklist.flat.json",
}
DESCRIPTION = "Vizient third-party data contract checklist (POC Lite)"
SCHEMA_NAME = "VizientContractChecklist"
BASE_ANALYZER = "prebuilt-document"
MODELS = {"completion": "prebuilt-analyzer-completion", "embedding": "prebuilt-analyzer-embedding"}
CONFIG = {
    "returnDetails": True,
    "estimateFieldSourceAndConfidence": True,
    "enableOcr": True,
    "enableLayout": True,
    "enableFormula": False,
}

ANALYZER_ID_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,64}$")
FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
LEAF_TYPES = {"string", "date", "number", "integer", "boolean"}
METHODS = {"extract", "generate", "classify"}
MAX_FIELDS, MAX_DESCRIPTION, MAX_CATEGORIES = 1000, 4096, 300


def build_analyzer(data: dict[str, Any], layout: str = "nested") -> dict[str, Any]:
    """The analyzer body for a validated checklist. analyzerId is not in the body: it is in the URL."""
    if layout not in LAYOUTS:
        raise ValueError(f"layout must be one of {LAYOUTS}")
    fields: dict[str, Any] = {}
    for item in checklistlib.detail_items(data):
        fields[item["key"]] = _leaf(item["type"], item["method"], item["definition"],
                                    item.get("enum"), item.get("enumDescriptions"))
    for item in checklistlib.right_items(data):
        parts = _right_parts(data, item)
        if layout == "nested":
            fields[item["key"]] = {
                "type": "object",
                "description": f"{item['label']}: {item['definition']} {data['rightSuffix']}",
                "properties": parts,
            }
        else:
            fields.update({f"{item['key']}_{name}": leaf for name, leaf in parts.items()})
    body: dict[str, Any] = {
        "description": DESCRIPTION,
        "baseAnalyzerId": BASE_ANALYZER,
        "models": dict(MODELS),
        "config": dict(CONFIG),
        "fieldSchema": {"name": SCHEMA_NAME, "fields": fields},
    }
    body["tags"] = {
        "checklistVersion": str(data["version"]),
        "layout": layout,
        "definitionHash": definition_hash(body),
    }
    return body


def definition_hash(body: dict[str, Any]) -> str:
    """Short fingerprint of everything but the tags, so a deployed analyzer can be compared with the file."""
    canonical = {key: value for key, value in body.items() if key != "tags"}
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:12]


def validate_analyzer(body: dict[str, Any], analyzer_id: str) -> list[str]:
    """Every problem found against the Content Understanding limits and what the app relies on."""
    problems: list[str] = []
    if not ANALYZER_ID_PATTERN.match(analyzer_id):
        problems.append(f"analyzer id {analyzer_id!r} must be 1-64 letters, digits, dots or underscores")
    if "analyzerId" in body:
        problems.append("analyzerId belongs in the URL, not the body")
    if not (body.get("config", {}).get("returnDetails") and body["config"].get("estimateFieldSourceAndConfidence")):
        problems.append("config must set returnDetails and estimateFieldSourceAndConfidence: the viewer needs them")
    if not all(isinstance(value, str) for value in body.get("tags", {}).values()):
        problems.append("tag values must be strings")

    entries = list(_walk(body.get("fieldSchema", {}).get("fields", {})))
    if not entries:
        problems.append("fieldSchema has no fields")
    if len(entries) > MAX_FIELDS:
        problems.append(f"{len(entries)} fields exceed the limit of {MAX_FIELDS}")
    for path, name, field in entries:
        problems += [f"{path}: {text}" for text in _field_problems(name, field)]
    return problems


def field_counts(body: dict[str, Any]) -> dict[str, int]:
    fields = body["fieldSchema"]["fields"]
    nested = sum(len(field.get("properties", {})) for field in fields.values())
    return {"top_level": len(fields), "nested": nested, "total": len(fields) + nested}


def render(body: dict[str, Any]) -> str:
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def _leaf(type_: str, method: str, description: str, enum: list[str] | None = None,
          enum_descriptions: dict[str, str] | None = None) -> dict[str, Any]:
    leaf: dict[str, Any] = {"type": type_, "method": method, "description": description}
    if enum is not None:
        leaf["enum"] = list(enum)
    if enum_descriptions is not None:
        leaf["enumDescriptions"] = dict(enum_descriptions)
    # Set on every leaf: for extract fields the field-level flag decides grounding, whatever the config says.
    leaf["estimateSourceAndConfidence"] = True
    return leaf


def _right_parts(data: dict[str, Any], item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    label = item["label"]
    judgments = checklistlib.judgments_for(data, item)
    return {
        "Judgment": _leaf("string", "classify", f"Judgment for '{label}': {item['definition']} {data['rightSuffix']}",
                          list(judgments), judgments),
        "Conditions": _leaf("string", "generate",
                            f"Conditions, limits or approvals that apply to '{label}'. Empty if none."),
        "Clause": _leaf("string", "extract",
                        f"Verbatim text of the clause that governs '{label}'. Prefer the clause that states the rule "
                        "over a sentence that only refers to it. Empty if Not Addressed."),
    }


def _walk(fields: dict[str, Any], parent: str = "") -> Iterator[tuple[str, str, dict[str, Any]]]:
    for name, field in fields.items():
        path = f"{parent}.{name}" if parent else name
        yield path, name, field
        if field.get("type") == "object":
            yield from _walk(field.get("properties", {}), path)


def _field_problems(name: str, field: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if not FIELD_NAME_PATTERN.match(name):
        out.append("field names start with a letter, use letters, digits and underscores, and fit in 64 characters")
    description = field.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION:
        out.append(f"description must be 1 to {MAX_DESCRIPTION} characters")
    if field.get("type") == "object":
        if not field.get("properties"):
            out.append("an object field needs properties")
        return out
    if field.get("type") not in LEAF_TYPES:
        out.append(f"type must be one of {sorted(LEAF_TYPES)} or object")
    if field.get("method") not in METHODS:
        out.append(f"method must be one of {sorted(METHODS)}")
    if field.get("estimateSourceAndConfidence") is not True:
        out.append("estimateSourceAndConfidence must be true so the field returns source and confidence")
    values = field.get("enum")
    if field.get("method") == "classify":
        if not values or len(set(values)) != len(values) or len(values) > MAX_CATEGORIES:
            out.append(f"classify needs 1 to {MAX_CATEGORIES} unique enum values")
        elif "enumDescriptions" in field and set(field["enumDescriptions"]) != set(values):
            out.append("enumDescriptions must describe exactly the enum values")
        elif (name == "Judgment" or name.endswith("_Judgment")) and "Not Addressed" not in values:
            out.append("a judgment must allow 'Not Addressed': silence is never inferred")
    elif values is not None:
        out.append("only classify fields take an enum")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the analyzer definitions from checklist.json.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="regenerate the committed analyzer files")
    mode.add_argument("--check", action="store_true", help="exit 1 if a committed analyzer file is stale")
    args = parser.parse_args(argv)

    data = checklistlib.load_checklist()
    stale: list[str] = []
    for layout in LAYOUTS:
        body = build_analyzer(data, layout)
        problems = validate_analyzer(body, ANALYZER_IDS[layout])
        if problems:
            print(f"{layout}: the generated analyzer is invalid:\n  " + "\n  ".join(problems))
            return 1
        path, counts = OUTPUT_FILES[layout], field_counts(body)
        if args.write:
            path.write_text(render(body), encoding="utf-8", newline="\r\n")
            state = "written"
        elif path.exists() and json.loads(path.read_text(encoding="utf-8")) == body:
            state = "current"
        else:
            state = "STALE"
            stale.append(path.name)
        print(f"{layout:<6} {path.name}  {counts['top_level']} top-level + {counts['nested']} nested fields  "
              f"hash {body['tags']['definitionHash']}  {state}")
    if stale:
        print("Run: python analyzer/build_schema.py --write")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
