"""Seed the demo contracts into Dataverse, already analyzed.

The Contract Intake flow turns a PDF dropped into SharePoint into a contract row and its findings. This script writes the
same rows from the saved results of the three synthetic contracts (samples/results/<name>.json, made by
scripts/run-local.py) and attaches the PDFs, so the review screens have data for a rehearsal or when a live analysis is not
worth the wait.

    python scripts/seed-demo.py           # offline: check the saved results and say what would be written
    python scripts/seed-demo.py --status  # read-only: compare Dataverse with them; exit 1 if the demo data is not in place
    python scripts/seed-demo.py --apply   # write the contracts that are missing; one that is there is not changed
    python scripts/seed-demo.py --reset   # delete the demo contracts and their findings, then write them again

A demo contract is a contract named like its file (bluepine-sow.pdf) that did not come from SharePoint; a contract that did
is never touched. The row goes in as Received and becomes Ready for Review only after the document and every finding are
written, as in the analysis flow, so a run that stops half way leaves a Received row that the next --apply finishes. A demo
contract in any other state that is not complete (being analyzed, failed, or short of findings) is reported and left alone;
--reset replaces it. --reset also discards any review work done on the demo contracts.
Only the synthetic PDFs go to Dataverse: a PDF without the SYNTHETIC SAMPLE marker stops the script. Dataverse must be
signed in as AZURE_ACCOUNT from .env, or the script stops before it reads anything else.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import checklistlib
import flowlib
import schemalib
from dvweb import Dataverse, DataverseError, entity_id, signed_in_account
from loadscript import load_script

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
DEFAULT_SAMPLES = ROOT / "samples"
# In the order the reviewer sees them. The app lists the newest contract first, so they are written last to first.
DEMO_CONTRACTS = ("bluepine-sow", "bluepine-amendment", "tessera-dua")
CONTRACTS, FINDINGS, CHECKLIST = "vz_contracts", "vz_findings", "vz_checklistitems"
IF_MATCH = {"If-Match": "*"}  # without it a PATCH to a missing row would create one
FINISHED = ("Ready for Review", "In Review", "Approved")
WRITES = ("create", "resume", "replace")


class SeedError(RuntimeError):
    """A failure worth one clear line, not a stack trace."""


@dataclass(frozen=True)
class Rules:
    """What the analysis flow knows about the schema: the choice values and the length of each text column."""
    status: Mapping[str, int]
    kinds: Mapping[str, int]
    presence: Mapping[str, int]
    judgment: Mapping[str, int]
    text_length: Mapping[str, int]
    name_length: int
    raw_limit: int

    def status_label(self, value: int | None) -> str:
        return next((label for label, stored in self.status.items() if stored == value), "no status")


def rules_from(schema: Mapping[str, Any]) -> Rules:
    return Rules(
        status=flowlib.choice_values(schema, "vz_contract", "vz_status"),
        kinds=flowlib.choice_values(schema, "vz_contract", "vz_documenttype"),
        presence=flowlib.choice_values(schema, "vz_finding", "vz_presence"),
        judgment=flowlib.global_choice_values(schema, "vz_judgment"),
        text_length={column: flowlib.max_length(schema, "vz_contract", column)
                     for column in ("vz_vendor", "vz_viziententity", "vz_contractidentifier")},
        name_length=flowlib.max_length(schema, "vz_finding", "vz_name"),
        raw_limit=flowlib.text_limit(schema, "vz_contract", "vz_rawresult"),
    )


@dataclass(frozen=True)
class Sample:
    name: str                          # the contract's name: its file name
    pdf: bytes
    created: dict[str, Any]            # the row that starts the contract
    finished: dict[str, Any]           # what the analysis fills in; written last, with the Ready for Review status
    findings: dict[str, dict[str, Any]]  # checklist key -> finding row, without the link to its contract


@dataclass(frozen=True)
class Held:
    """A demo contract as Dataverse holds it."""
    id: str
    status: int | None
    has_document: bool
    keys: frozenset[str]               # checklist keys of its findings


@dataclass(frozen=True)
class State:
    held: Mapping[str, tuple[Held, ...]]  # contract name -> the demo contracts with that name
    checklist: frozenset[str]


@dataclass(frozen=True)
class Step:
    sample: Sample
    action: str                        # create, resume, replace, keep or blocked
    held: tuple[Held, ...] = ()
    note: str = ""


# --- mapping: the same values the analysis flow writes ---------------------------------------------------------------

def clip(value: Any, limit: int) -> str | None:
    """Text cut to a column's length, or None when there is none."""
    return None if value in (None, "") else str(value)[:limit]


def iso_date(value: Any) -> str | None:
    """The text when it looks like yyyy-MM-dd, else None: a date column rejects anything else."""
    text = "" if value is None else str(value)
    return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else None


def compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def finding_row(contract_name: str, finding: Mapping[str, Any], rules: Rules) -> dict[str, Any]:
    key, judgment, presence = finding["key"], finding.get("judgment"), finding.get("presence")
    return {
        "vz_name": f"{contract_name} - {key}"[:rules.name_length],
        "vz_presence": rules.presence["Unclear"] if presence is None else rules.presence.get(presence, rules.presence["Unclear"]),
        "vz_aivalue": finding.get("value"),
        "vz_aiconditions": finding.get("conditions"),
        "vz_clause": finding.get("clause"),
        "vz_aijudgment": rules.judgment.get(judgment) if judgment else None,
        "vz_page": finding.get("page"),
        "vz_sourceregions": compact(finding.get("sourceRegions") or []),
        "vz_confidence": finding.get("confidence"),
        "vz_checklistitem@odata.bind": f"{CHECKLIST}(vz_key='{key}')",
    }


def build_sample(name: str, pdf: bytes, saved: Any, keys: Sequence[str], rules: Rules, processed_on: str) -> Sample:
    """The rows for one contract from the result run-local.py saved. Refuses a result that does not cover the checklist."""
    if not (isinstance(saved, Mapping) and isinstance(saved.get("contract"), Mapping)
            and isinstance(saved.get("findings"), list) and isinstance(saved.get("raw"), Mapping)):
        raise SeedError(f"{name}: the saved result must hold contract, findings and raw, as run-local.py saves them")
    contract, findings, raw = saved["contract"], saved["findings"], saved["raw"]
    seen = [finding.get("key") if isinstance(finding, Mapping) else None for finding in findings]
    problems = []
    if len(set(map(str, seen))) != len(seen):
        problems.append("a key appears twice")
    if lacking := sorted(set(keys) - set(seen)):
        problems.append(f"lacks {', '.join(lacking)}")
    if unknown := sorted(set(map(str, seen)) - set(keys)):
        problems.append(f"has unknown {', '.join(unknown)}")
    if problems:
        raise SeedError(f"{name}: the findings do not match the checklist ({'; '.join(problems)}). "
                        f"Analyze it again: python scripts/run-local.py samples/{name} --via function")
    raw_text = compact(raw)
    length = rules.text_length
    finished = {
        "vz_vendor": clip(contract.get("vendor"), length["vz_vendor"]),
        "vz_viziententity": clip(contract.get("vizientEntity"), length["vz_viziententity"]),
        "vz_contractidentifier": clip(contract.get("contractIdentifier"), length["vz_contractidentifier"]),
        "vz_documenttype": rules.kinds.get(contract.get("documentType") or "Other", rules.kinds["Other"]),
        "vz_effectivedate": iso_date(contract.get("effectiveDate")),
        "vz_expirationdate": iso_date(contract.get("expirationDate")),
        "vz_hasparentreference": contract.get("hasParentReference") is True,
        "vz_foundcount": contract.get("foundCount"),
        "vz_totalcount": contract.get("totalCount"),
        "vz_completeness": contract.get("completeness"),
        "vz_processedon": processed_on,
        "vz_rawresult": raw_text if len(raw_text) < rules.raw_limit else None,
        "vz_status": rules.status["Ready for Review"],
    }
    return Sample(name, pdf, {"vz_name": name, "vz_status": rules.status["Received"]}, finished,
                  {finding["key"]: finding_row(name, finding, rules) for finding in findings})


# --- the files -------------------------------------------------------------------------------------------------------

def load_run_local() -> Any:
    return load_script("run-local.py", "run_local")


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_samples(directory: Path, keys: Sequence[str], rules: Rules, processed_on: str) -> list[Sample]:
    """The demo contracts, in display order. Every PDF must carry the synthetic-sample marker."""
    run_local = load_run_local()
    samples = []
    for stem in DEMO_CONTRACTS:
        pdf_path, saved_path = directory / f"{stem}.pdf", directory / "results" / f"{stem}.json"
        try:
            pdf = run_local.read_pdf(pdf_path)
            run_local.confirm_synthetic(pdf_path, "synthetic")
        except run_local.RunError as exc:
            raise SeedError(f"{exc}. The samples are made by: python eval/generate_contracts.py") from exc
        try:
            saved = json.loads(saved_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SeedError(f"{saved_path.name} is missing. Make it with: "
                            f"python scripts/run-local.py samples/{stem}.pdf --via function") from exc
        except (OSError, ValueError) as exc:
            raise SeedError(f"cannot read {saved_path.name} ({type(exc).__name__})") from exc
        samples.append(build_sample(f"{stem}.pdf", pdf, saved, keys, rules, processed_on))
    return samples


# --- Dataverse -------------------------------------------------------------------------------------------------------

def check_account(dv: Dataverse, expected: str | None) -> str:
    """The signed-in account, after proving it is the one named in .env (when one is named)."""
    account = signed_in_account(dv)
    if expected and account.lower() != expected.lower():
        raise SeedError(f"Dataverse is signed in as {account}, but AZURE_ACCOUNT expects {expected}")
    return account


def survey(dv: Dataverse) -> State:
    """The checklist keys, and the demo contracts: those that did not come through SharePoint."""
    keys = {row["vz_checklistitemid"]: row["vz_key"]
            for row in dv.list(CHECKLIST, {"$select": "vz_checklistitemid,vz_key"})}
    written: dict[str, set[str]] = {}
    for row in dv.list(FINDINGS, {"$select": "_vz_contract_value,_vz_checklistitem_value"}):
        if key := keys.get(row["_vz_checklistitem_value"]):
            written.setdefault(row["_vz_contract_value"], set()).add(key)
    held: dict[str, list[Held]] = {}
    columns = "vz_contractid,vz_name,vz_status,vz_document_name,vz_sharepointitemid"
    for row in dv.list(CONTRACTS, {"$select": columns}):
        if row.get("vz_sharepointitemid"):
            continue
        held.setdefault(row["vz_name"], []).append(Held(
            row["vz_contractid"], row.get("vz_status"), bool(row.get("vz_document_name")),
            frozenset(written.get(row["vz_contractid"], ()))))
    return State({name: tuple(rows) for name, rows in held.items()}, frozenset(keys.values()))


def decide(sample: Sample, held: tuple[Held, ...], rules: Rules, *, reset: bool) -> Step:
    if reset:
        replaced = f"replaces {len(held)} existing contract(s)" if held else f"{len(sample.findings)} findings"
        return Step(sample, "replace" if held else "create", tuple(held), replaced)
    if not held:
        return Step(sample, "create", note=f"{len(sample.findings)} findings, {len(sample.pdf) / 1024:.1f} KB document")
    if len(held) > 1:
        raise SeedError(f"Dataverse holds {len(held)} contracts named {sample.name}; delete the extras by hand, "
                        "or run --reset")
    row = held[0]
    absent = len(set(sample.findings) - row.keys)
    label = rules.status_label(row.status)
    if row.status == rules.status["Received"]:
        todo = [f"{absent} finding(s) to add"] if absent else []
        return Step(sample, "resume", held, ", ".join(todo + ([] if row.has_document else ["document to attach"]))
                    or "to finish")
    if label in FINISHED and row.has_document and not absent:
        return Step(sample, "keep", held, f"{label}, {len(row.keys)} findings")
    problems = ([] if row.has_document else ["no document"]) + ([f"{absent} finding(s) missing"] if absent else [])
    return Step(sample, "blocked", held, f"{label}{'; ' if problems else ''}{', '.join(problems)}"
                " - left alone; --reset replaces it")


def make_plan(samples: Sequence[Sample], state: State, rules: Rules, *, reset: bool = False) -> list[Step]:
    return [decide(sample, state.held.get(sample.name, ()), rules, reset=reset) for sample in samples]


def describe(steps: Sequence[Step], log: Callable[[str], None] = print) -> None:
    width = max(len(step.sample.name) for step in steps)
    for step in steps:
        log(f"  {step.action:<8} {step.sample.name:<{width}}  {step.note}")
    writing = sum(step.action in WRITES for step in steps)
    kept = sum(step.action == "keep" for step in steps)
    log(f"{writing} to write, {kept} in place, {len(steps) - writing - kept} left alone")


def write(dv: Dataverse, step: Step, rules: Rules, log: Callable[[str], None] = print) -> None:
    sample = step.sample
    if step.action == "resume":
        row = step.held[0]
        contract, has_document, written = f"{CONTRACTS}({row.id})", row.has_document, row.keys
    else:
        for old in step.held:
            dv.request("DELETE", f"{CONTRACTS}({old.id})")  # its findings go with it
        contract = f"{CONTRACTS}({entity_id(dv.request('POST', CONTRACTS, body=sample.created))})"
        has_document, written = False, frozenset()
    if not has_document:
        dv.upload_file(contract, "vz_document", sample.name, sample.pdf)
    for key, finding in sample.findings.items():
        if key not in written:
            dv.request("POST", FINDINGS, body={**finding, "vz_contract@odata.bind": contract})
    dv.request("PATCH", contract, body=sample.finished, headers=IF_MATCH)
    log(f"  wrote {sample.name}: {len(sample.findings)} findings, {rules.status_label(sample.finished['vz_status'])}")


def sync(dv: Dataverse, samples: Sequence[Sample], rules: Rules, *, apply: bool, reset: bool = False,
         log: Callable[[str], None] = print) -> list[Step]:
    """Compare Dataverse with the saved results and, when asked, write the difference. Returns the plan that now holds."""
    state = survey(dv)
    if lacking := sorted({key for sample in samples for key in sample.findings} - state.checklist):
        raise SeedError(f"the checklist table has no row for {', '.join(lacking)}. "
                        "Run: python scripts/seed-checklist.py --apply")
    steps = make_plan(samples, state, rules, reset=reset)
    describe(steps, log)
    todo = [step for step in steps if step.action in WRITES]
    if not apply or not todo:
        return steps
    for step in reversed(todo):
        write(dv, step, rules, log)
    dv.reset_affinity()
    after = make_plan(samples, survey(dv), rules)
    wrote = {step.sample.name for step in todo}
    if unfinished := [step.sample.name for step in after if step.sample.name in wrote and step.action != "keep"]:
        raise SeedError(f"{', '.join(unfinished)} still differ from the saved results after the write; "
                        "run --status to see how")
    log(f"wrote {len(todo)} contract(s); Dataverse now holds the demo data")
    return after


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="read-only comparison with Dataverse; exit 1 if it differs")
    mode.add_argument("--apply", action="store_true", help="write the demo contracts that are missing")
    mode.add_argument("--reset", action="store_true", help="delete the demo contracts, then write them again")
    args = parser.parse_args(argv)

    try:
        schema = schemalib.load_schema()
        rules = rules_from(schema)
        keys = [item["key"] for item in checklistlib.analyzer_items(checklistlib.load_checklist(schema=schema))]
        samples = load_samples(DEFAULT_SAMPLES, keys, rules, utc_now())
        if not (args.status or args.apply or args.reset):
            for sample in samples:
                print(f"  {sample.name}: {len(sample.findings)} findings, {len(sample.pdf) / 1024:.1f} KB document")
            print("The saved results and PDFs are valid. Nothing was sent. "
                  "Run with --status to compare with Dataverse, or --apply to write.")
            return 0
        dv = Dataverse("dv-data")
        account = check_account(dv, os.environ.get("AZURE_ACCOUNT") or None)
        print(f"Signed in as {account}; environment {urlparse(dv.base_url).hostname}")
        steps = sync(dv, samples, rules, apply=args.apply or args.reset, reset=args.reset)
        return 0 if all(step.action == "keep" for step in steps) else 1
    except (SeedError, DataverseError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
