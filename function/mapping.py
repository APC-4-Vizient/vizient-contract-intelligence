"""Map a Content Understanding result to the checklist findings the review app shows.

The checklist analyzer returns one field per extracted checklist item. A detail is a scalar field. A Right_* item is
an object with Judgment, Conditions and Clause, and each of those carries its own confidence and source. A source is
"D(page,x1,y1,x2,y2,x3,y3,x4,y4)" in inches, with ";" between segments.

map_result() is pure: an operation in, findings out, no service calls. Presence follows section 3d of the brief, with
one addition: a finding is only Found when it has a page to highlight, because the review app proves every answer by
showing its source.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

CHECKLIST_PATH = Path(__file__).with_name("checklist.json")
DEFAULT_HIGH_CONF = 0.80
MAX_REGIONS = 40
MAX_TEXT = 9_500  # the Dataverse memo columns for value, conditions and clause hold 10,000 characters

FOUND, UNCLEAR, NOT_FOUND = "Found", "Unclear", "Not Found"
NOT_APPLICABLE = "N/A"
NOT_ADDRESSED = "Not Addressed"
RIGHT_GROUP = "Data Right"
JUDGMENTS = {name.lower(): name for name in ("Permitted", "Prohibited", "Conditional", NOT_ADDRESSED)}
VALUE_KEYS = ("valueString", "valueDate", "valueTime", "valueNumber", "valueInteger", "valueBoolean")

_SEGMENT = re.compile(r"D\((\d+),((?:-?\d+(?:\.\d+)?,){7}-?\d+(?:\.\d+)?)\)")
_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


class MappingError(ValueError):
    """The analyzer result does not have the shape this mapping expects."""


def load_checklist(path: Path = CHECKLIST_PATH) -> list[dict[str, Any]]:
    """The items the analyzer extracts, in checklist order. The manual items are not in an analyzer result."""
    data = json.loads(path.read_text(encoding="utf-8"))
    items = [item for item in data["items"] if item.get("source") == "analyzer"]
    if not items:
        raise MappingError(f"{path.name} lists no analyzer items")
    return items


def parse_high_conf(text: str | None) -> float:
    """HIGH_CONF from the environment: a number above 0 and up to 1, else the default."""
    try:
        value = float(text) if text else DEFAULT_HIGH_CONF
    except ValueError:
        return DEFAULT_HIGH_CONF
    return value if 0 < value <= 1 else DEFAULT_HIGH_CONF


def parse_source(source: str | None) -> list[dict[str, Any]]:
    """[{page, polygon}] from "D(1,x1,y1,...,x4,y4);D(2,...)". Segments in any other format are skipped."""
    regions = []
    for segment in (source or "").split(";"):
        match = _SEGMENT.fullmatch(segment.strip())
        if match:
            regions.append({"page": int(match.group(1)), "polygon": [float(n) for n in match.group(2).split(",")]})
    return regions[:MAX_REGIONS]


def map_result(operation: Mapping[str, Any], items: Sequence[Mapping[str, Any]],
               high_conf: float = DEFAULT_HIGH_CONF) -> dict[str, Any]:
    """The review payload for a Succeeded analyze operation: {contract, findings, raw}."""
    content = _content(operation)
    fields = content.get("fields")
    if not isinstance(fields, Mapping) or not fields:
        raise MappingError("the analyzer result has no fields. Is the analyzer the checklist analyzer?")
    markdown = content.get("markdown") if isinstance(content.get("markdown"), str) else ""
    findings = []
    for item in items:
        build = _right if item["group"] == RIGHT_GROUP else _detail
        findings.append(build(item["key"], fields.get(item["key"]), markdown, high_conf))
    return {"contract": _contract(findings), "findings": findings, "raw": _raw(operation, content)}


def _content(operation: Mapping[str, Any]) -> Mapping[str, Any]:
    result = operation.get("result")
    contents = result.get("contents") if isinstance(result, Mapping) else None
    if not contents or not isinstance(contents[0], Mapping):
        raise MappingError("the analyzer result has no content")
    return contents[0]


def _detail(key: str, field: Any, markdown: str, high_conf: float) -> dict[str, Any]:
    field = _field(key, field)
    value, confidence = _text(field), _confidence(field)
    if not value:
        return _finding(key, NOT_FOUND, confidence=confidence)
    regions = parse_source(field.get("source"))
    clause = _quote(field.get("spans"), markdown) or value
    presence = FOUND if _trusted(confidence, high_conf) and regions else UNCLEAR
    return _finding(key, presence, value=value, clause=clause, regions=regions, confidence=confidence)


def _right(key: str, field: Any, markdown: str, high_conf: float) -> dict[str, Any]:
    field = _field(key, field)
    if field and field.get("type") != "object":
        raise MappingError(f"{key} is a {field.get('type')} field, not an object. "
                           "Deploy the nested analyzer, vizientContractChecklist")
    parts = field.get("valueObject") if isinstance(field.get("valueObject"), Mapping) else {}
    judgment_field = _field(f"{key}.Judgment", parts.get("Judgment"))
    clause_field = _field(f"{key}.Clause", parts.get("Clause"))
    judgment = JUDGMENTS.get(_text(judgment_field).lower(), "")
    if judgment == NOT_ADDRESSED:
        # CU still returns a source for this judgment: the text it read before deciding the contract is silent.
        # That is not evidence, so no clause, page or region is kept.
        return _finding(key, NOT_FOUND, judgment=judgment, confidence=_confidence(judgment_field))
    clause = _text(clause_field)
    conditions = _text(_field(f"{key}.Conditions", parts.get("Conditions")))
    if not (judgment or clause or conditions):
        return _finding(key, NOT_FOUND, judgment="", confidence=_confidence(judgment_field))
    regions = parse_source(clause_field.get("source") if clause else None)
    if not regions and judgment:
        regions = parse_source(judgment_field.get("source"))
    confidences = [_confidence(judgment_field)] + ([_confidence(clause_field)] if clause else [])
    confidence = None if None in confidences else min(confidences)
    found = bool(judgment and clause and regions) and _trusted(confidence, high_conf)
    return _finding(key, FOUND if found else UNCLEAR, value=conditions, judgment=judgment, conditions=conditions,
                    clause=clause, regions=regions, confidence=confidence)


def _finding(key: str, presence: str, *, value: str = "", judgment: str = NOT_APPLICABLE, conditions: str = "",
             clause: str = "", regions: Sequence[dict[str, Any]] = (), confidence: float | None = None) -> dict[str, Any]:
    regions = list(regions)
    return {"key": key, "presence": presence, "value": _cap(value), "judgment": judgment,
            "conditions": _cap(conditions), "clause": _cap(clause),
            "page": regions[0]["page"] if regions else None, "sourceRegions": regions, "confidence": confidence}


def _cap(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 3].rstrip() + "..."


def _contract(findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_key = {finding["key"]: finding for finding in findings}

    def value(key: str) -> str | None:
        return (by_key.get(key) or {}).get("value") or None

    found = sum(1 for finding in findings if finding["presence"] == FOUND)
    total = len(findings)
    return {
        "vendor": value("Vendor"),
        "vizientEntity": value("VizientEntity"),
        "documentType": value("DocumentType"),
        "contractIdentifier": value("ContractIdentifier"),
        "effectiveDate": value("EffectiveDate"),
        "expirationDate": value("ExpirationDate"),
        "hasParentReference": bool(value("ParentAgreementReference")),
        "foundCount": found,
        "totalCount": total,
        "completeness": round(100 * found / total, 1) if total else 0.0,
    }


def _raw(operation: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    """What is worth keeping for debugging and re-scoring. The markdown, lines and words are left out: they are
    large, and the quotes the findings need are already in them."""
    result = operation["result"]
    return {
        "analyzerId": result.get("analyzerId"),
        "apiVersion": result.get("apiVersion"),
        "createdAt": result.get("createdAt"),
        "usage": operation.get("usage"),
        "unit": content.get("unit"),
        "pages": [{"pageNumber": page.get("pageNumber"), "width": page.get("width"), "height": page.get("height")}
                  for page in content.get("pages") or [] if isinstance(page, Mapping)],
        "fields": content.get("fields"),
        "warnings": result.get("warnings") or [],
    }


def _field(name: str, field: Any) -> Mapping[str, Any]:
    if field is None:
        return {}
    if not isinstance(field, Mapping):
        raise MappingError(f"{name} is not a field object")
    return field


def _text(field: Mapping[str, Any]) -> str:
    for name in VALUE_KEYS:
        value = field.get(name)
        if value is not None:
            return str(value).strip()
    return ""


def _confidence(field: Mapping[str, Any]) -> float | None:
    value = field.get("confidence")
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _trusted(confidence: float | None, high_conf: float) -> bool:
    return confidence is not None and confidence >= high_conf


def _quote(spans: Any, markdown: str) -> str:
    """The text a field's spans point at in the markdown, joined with " ... " when they are not adjacent."""
    parts = []
    for span in spans if isinstance(spans, list) else []:
        offset, length = (span.get("offset"), span.get("length")) if isinstance(span, Mapping) else (None, None)
        if isinstance(offset, int) and isinstance(length, int) and offset >= 0 and length > 0:
            text = " ".join(_ESCAPE.sub(r"\1", _COMMENT.sub(" ", markdown[offset:offset + length])).split())
            if text:
                parts.append(text)
    return " ... ".join(parts)
