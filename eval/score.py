"""Score review payloads against gold labels: success criteria 2 to 6 of the brief (section 9).

    python eval/score.py                      every eval/gold/<id>.json that has a samples/results/<id>.json
    python eval/score.py bluepine-sow         only the named contracts
    python eval/score.py --json report.json   also write the numbers as JSON

A result is the payload scripts/run-local.py saves: {contract, findings, raw}. A gold file holds one entry per
checklist item: {"value", "page", "quote"} for a detail ("" when the contract is silent) and {"judgment", "page",
"quote", "alsoAcceptable"} for a right. Text matches at a token-set ratio of 85 or more; dates, document types and
judgments match exactly. Presence is scored as saved, so save the result at the confidence you mean to judge
(run-local.py --high-conf).

Criterion 6 is a proxy: a Found item counts when its page is the gold page and its clause matches the gold quote. The
click test in the review app still decides it.

Exit code: 0 when every measured criterion is met, 1 when one is missed, 2 when nothing could be scored.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import checklistlib  # noqa: E402

TEXT_THRESHOLD = 85.0
DEFAULT_GOLD_DIR = HERE / "gold"
DEFAULT_RESULTS_DIR = ROOT / "samples" / "results"
RIGHT_GROUP = "Data Right"
FOUND = "Found"
NOT_ADDRESSED = "Not Addressed"
PROHIBITED = "Prohibited"
CHECKS = ("detail", "right", "prohibited", "found", "silent", "highlight")
SUMMARY_LABELS = {"detail": "details", "right": "rights", "prohibited": "prohibited", "found": "found with evidence",
                  "silent": "silent not asserted", "highlight": "evidence"}
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_WORD = re.compile(r"\w+")


class ScoreError(ValueError):
    """A gold file or a result that cannot be scored."""


@dataclass(frozen=True)
class Miss:
    contract: str
    check: str
    key: str
    detail: str


@dataclass
class Result:
    """What one contract scored. Every check is a count of items examined and a count of those that missed."""

    contract: str
    totals: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CHECKS, 0))
    missed: dict[str, int] = field(default_factory=lambda: dict.fromkeys(CHECKS, 0))
    misses: list[Miss] = field(default_factory=list)

    def count(self, check: str, ok: bool, key: str, detail: str, *, listed: bool = True) -> None:
        self.totals[check] += 1
        if not ok:
            self.missed[check] += 1
            if listed:
                self.misses.append(Miss(self.contract, check, key, detail))

    def hits(self, check: str) -> int:
        return self.totals[check] - self.missed[check]


@dataclass(frozen=True)
class Criterion:
    number: int
    name: str
    measured: str
    target: str
    met: bool | None  # None when the gold set holds nothing to measure


# --- matching ----------------------------------------------------------------------------------------------------

def words(text: str) -> list[str]:
    return _WORD.findall(text.casefold())


def lcs_length(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = [0] * (len(b) + 1)
    for char in a:
        current = [0]
        for index, other in enumerate(b, 1):
            current.append(previous[index - 1] + 1 if char == other else max(previous[index], current[index - 1]))
        previous = current
    return previous[-1]


def ratio(a: str, b: str) -> float:
    """Similarity of two strings from 0 to 100: twice the longest common subsequence over the total length."""
    total = len(a) + len(b)
    return 100.0 if not total else 200.0 * lcs_length(a, b) / total


def token_set_ratio(a: str, b: str) -> float:
    """Ratio of the words the two texts share, ignoring case, punctuation and order. A text whose words are all in
    the other scores 100, so a value that is a faithful part of the gold value still matches."""
    left, right = set(words(a)), set(words(b))
    if not left or not right:
        return 0.0
    shared = " ".join(sorted(left & right))
    with_left = f"{shared} {' '.join(sorted(left - right))}".strip()
    with_right = f"{shared} {' '.join(sorted(right - left))}".strip()
    return max(ratio(shared, with_left), ratio(shared, with_right), ratio(with_left, with_right))


def kind_of(item: Mapping[str, Any]) -> str:
    if item.get("type") == "date":
        return "date"
    return "enum" if item.get("method") == "classify" or item.get("enum") else "text"


def detail_matches(kind: str, expected: str, actual: str) -> bool:
    expected, actual = expected.strip(), actual.strip()
    if not expected or not actual:
        return expected == actual
    if kind == "date":
        return expected == actual
    if kind == "enum":
        return expected.casefold() == actual.casefold()
    return token_set_ratio(expected, actual) >= TEXT_THRESHOLD


def text_of(value: Any) -> str:
    return value if isinstance(value, str) else ""


def is_page(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def has_evidence(finding: Mapping[str, Any]) -> bool:
    return bool(text_of(finding.get("clause")).strip()) and is_page(finding.get("page"))


def evidence_problem(finding: Mapping[str, Any], expected: Mapping[str, Any]) -> str:
    """Why a Found item's evidence is not the gold clause, or "" when it is."""
    problems = []
    page = finding.get("page")
    if page != expected["page"]:
        problems.append(f"page {page if is_page(page) else 'missing'}, gold page {expected['page']}")
    if token_set_ratio(text_of(finding.get("clause")), expected["quote"]) < TEXT_THRESHOLD:
        problems.append("clause differs from the gold quote")
    return "; ".join(problems)


def clip(text: str, width: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 3] + "..."


def quoted(text: str) -> str:
    return f'"{clip(text)}"' if text else "nothing"


# --- scoring -----------------------------------------------------------------------------------------------------

def score_contract(contract: str, gold: Mapping[str, Mapping[str, Any]], findings: Mapping[str, Mapping[str, Any]],
                   items: Sequence[Mapping[str, Any]]) -> Result:
    """Score one contract's findings (by key) against its gold, for every checklist item."""
    result = Result(contract)
    for item in items:
        key, expected = item["key"], gold[item["key"]]
        finding = findings.get(key) or {}
        found = finding.get("presence") == FOUND
        if item["group"] == RIGHT_GROUP:
            wanted, actual = expected["judgment"], text_of(finding.get("judgment"))
            accepted = {name.casefold() for name in (wanted, *expected.get("alsoAcceptable", ()))}
            agreed = actual.casefold() in accepted
            note = f"expected {wanted}, got {actual or 'nothing'}"
            result.count("right", agreed, key, note)
            if wanted == PROHIBITED:
                result.count("prohibited", agreed, key, note, listed=False)
            silent = wanted == NOT_ADDRESSED
        else:
            wanted, actual = text_of(expected["value"]).strip(), text_of(finding.get("value")).strip()
            result.count("detail", detail_matches(kind_of(item), wanted, actual), key,
                         f"expected {quoted(wanted)}, got {quoted(actual)}")
            silent = not wanted
        if found:
            result.count("found", has_evidence(finding), key, "Found without a clause and a page")
        if silent:
            result.count("silent", not found, key, "Found, but the contract is silent")
        elif found and is_page(expected.get("page")) and text_of(expected.get("quote")).strip():
            problem = evidence_problem(finding, expected)
            result.count("highlight", not problem, key, problem)
    return result


def combine(results: Sequence[Result]) -> Result:
    total = Result("all")
    for result in results:
        for check in CHECKS:
            total.totals[check] += result.totals[check]
            total.missed[check] += result.missed[check]
        total.misses.extend(result.misses)
    return total


def criteria(total: Result) -> list[Criterion]:
    """The brief's measurable success criteria over every scored contract together."""

    def at_least(number: int, name: str, check: str, percent: int) -> Criterion:
        hits, count = total.hits(check), total.totals[check]
        measured = "n/a" if not count else f"{hits}/{count} ({100 * hits / count:.1f}%)"
        met = None if not count else hits * 100 >= percent * count
        return Criterion(number, name, measured, "100%" if percent == 100 else f">= {percent}%", met)

    silent, asserted = total.totals["silent"], total.missed["silent"]
    return [
        at_least(2, "Contract-detail accuracy", "detail", 90),
        at_least(3, "Rights judgment agreement", "right", 85),
        at_least(3, "Rights judgment agreement, Prohibited only", "prohibited", 95),
        at_least(4, "Found items with a clause and a page", "found", 100),
        Criterion(5, "Found where the contract is silent", f"{asserted} of {silent}", "0",
                  None if not silent else asserted == 0),
        at_least(6, "Evidence on the gold clause (proxy)", "highlight", 90),
    ]


# --- files -------------------------------------------------------------------------------------------------------

def read_object(path: Path, what: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ScoreError(f"cannot read the {what} file {path.name}: {exc.strerror or exc}") from exc
    except ValueError as exc:
        raise ScoreError(f"the {what} file {path.name} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ScoreError(f"the {what} file {path.name} must hold a JSON object")
    return data


def entry_problems(item: Mapping[str, Any], entry: Any) -> list[str]:
    key = item["key"]
    if not isinstance(entry, dict):
        return [f"{key}: must be an object"]
    problems = []
    if item["group"] == RIGHT_GROUP:
        if entry.get("judgment") not in checklistlib.JUDGMENTS:
            problems.append(f"{key}: judgment must be one of {', '.join(checklistlib.JUDGMENTS)}")
        also = entry.get("alsoAcceptable", [])
        if not isinstance(also, list) or any(name not in checklistlib.JUDGMENTS for name in also):
            problems.append(f"{key}: alsoAcceptable must list judgments")
    elif not isinstance(entry.get("value"), str):
        problems.append(f"{key}: value must be a string, empty when the contract is silent")
    if "page" in entry and not is_page(entry["page"]):
        problems.append(f"{key}: page must be a positive integer")
    if "quote" in entry and not isinstance(entry["quote"], str):
        problems.append(f"{key}: quote must be a string")
    return problems


def load_gold(path: Path, items: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    data = read_object(path, "gold")
    entries = {key: entry for key, entry in data.items() if key != "_meta"}
    known = {item["key"] for item in items}
    problems = [f"{key}: not a checklist item" for key in entries if key not in known]
    for item in items:
        if item["key"] in entries:
            problems.extend(entry_problems(item, entries[item["key"]]))
        else:
            problems.append(f"{item['key']}: missing")
    if problems:
        more = "; ..." if len(problems) > 6 else ""
        raise ScoreError(f"the gold file {path.name} is not valid: {'; '.join(problems[:6])}{more}")
    return entries


def load_findings(path: Path) -> dict[str, dict[str, Any]]:
    data = read_object(path, "result")
    findings = data.get("findings")
    if not isinstance(findings, list) or not all(isinstance(f, dict) and isinstance(f.get("key"), str)
                                                 for f in findings):
        raise ScoreError(f"the result file {path.name} is not a review payload: it has no findings list. "
                         "Save one with scripts/run-local.py.")
    return {finding["key"]: finding for finding in findings}


def gold_ids(directory: Path) -> list[str]:
    if not directory.is_dir():
        raise ScoreError(f"there is no gold directory at {directory}")
    ids = sorted(path.stem for path in directory.glob("*.json"))
    if not ids:
        raise ScoreError(f"there are no gold files in {directory}")
    return ids


def score_all(ids: Sequence[str], gold_dir: Path, results_dir: Path,
              items: Sequence[Mapping[str, Any]]) -> tuple[list[Result], list[str]]:
    """The scored contracts, and the ids that have gold but no saved result yet."""
    results, skipped = [], []
    for contract in ids:
        gold = load_gold(gold_dir / f"{contract}.json", items)
        path = results_dir / f"{contract}.json"
        if path.is_file():
            results.append(score_contract(contract, gold, load_findings(path), items))
        else:
            skipped.append(contract)
    return results, skipped


# --- report ------------------------------------------------------------------------------------------------------

def fraction(result: Result, check: str) -> str:
    return f"{result.hits(check)}/{result.totals[check]}" if result.totals[check] else "-"


def render(results: Sequence[Result], skipped: Sequence[str]) -> str:
    total = combine(results)
    rows = criteria(total)
    width = max(len(row.name) for row in rows)
    lines = [f"{result.contract}: " + "  ".join(f"{SUMMARY_LABELS[check]} {fraction(result, check)}"
                                                for check in CHECKS) for result in results]
    lines += ["", f"{'#':<3}{'Criterion':<{width}}  {'Result':<16}{'Target':<8}Verdict"]
    for row in rows:
        verdict = "n/a" if row.met is None else "PASS" if row.met else "FAIL"
        lines.append(f"{row.number:<3}{row.name:<{width}}  {row.measured:<16}{row.target:<8}{verdict}")
    if total.misses:
        lines += ["", f"Misses ({len(total.misses)})"]
        lines += [f"  {miss.contract:<20} {miss.check:<10} {miss.key:<26} {miss.detail}" for miss in total.misses]
    lines += ["", "Not measured here: 1 (scanned PDF through the flow), 6 (the click test in the app), "
                  "7 (reviewer time), 8 (processing time)."]
    if skipped:
        lines.append("Skipped, no saved result yet: " + ", ".join(skipped))
    return "\n".join(lines)


def report(results: Sequence[Result]) -> dict[str, Any]:
    return {
        "criteria": [asdict(row) for row in criteria(combine(results))],
        "contracts": {result.contract: {"totals": result.totals, "missed": result.missed,
                                         "misses": [asdict(miss) for miss in result.misses]}
                      for result in results},
    }


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="score.py", description="Score saved review payloads against gold labels.")
    parser.add_argument("ids", nargs="*", metavar="id",
                        help="contracts to score (default: every gold file that has a saved result)")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD_DIR, help="gold directory (default eval/gold)")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS_DIR,
                        help="saved payloads (default samples/results)")
    parser.add_argument("--json", type=Path, metavar="PATH", help="also write the numbers to this JSON file")
    args = parser.parse_args(argv)
    for contract in args.ids:
        if not ID_PATTERN.fullmatch(contract):
            parser.error(f"{contract!r} is not a contract id: use the gold file name without .json")
    args.ids = list(dict.fromkeys(args.ids))
    return args


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(errors="replace")
    args = parse_args(argv)
    try:
        items = checklistlib.analyzer_items(checklistlib.load_checklist())
        results, skipped = score_all(args.ids or gold_ids(args.gold), args.gold, args.results, items)
    except (ValueError, OSError) as exc:
        print(f"score: {exc}", file=sys.stderr)
        return 2
    if not results:
        hints = "".join(f"\n  python scripts/run-local.py samples/{contract}.pdf" for contract in skipped)
        print(f"score: nothing to score. Save a result for a gold file first:{hints}", file=sys.stderr)
        return 2
    print(render(results, skipped))
    if args.json:
        try:
            args.json.write_text(json.dumps(report(results), indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"score: cannot write {args.json}: {exc.strerror or exc}", file=sys.stderr)
            return 2
    return 1 if any(row.met is False for row in criteria(combine(results))) else 0


if __name__ == "__main__":
    sys.exit(main())
