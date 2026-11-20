"""Re-queue existing contracts through extraction so they get full document text and Search indexing.

    python scripts/reextract-contracts.py            # dry run: list what would change
    python scripts/reextract-contracts.py --apply    # discard findings, clear index fields, set Extracting
    python scripts/reextract-contracts.py --apply --wait

Re-extraction replaces a contract's 20 findings (the analysis flow creates findings, so keeping the old ones would
duplicate them). THIS DISCARDS REVIEW WORK on the selected contracts, including Accept/Correct/Reject decisions.
Contract rows, their attached PDFs, parent links and the manual Owner/Reviewer fields are kept. The PDFs are processed
by the deployed flows, as at first upload; this script never reads a PDF or any clause text.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from dvweb import Dataverse, signed_in_account

ROOT = Path(__file__).resolve().parent.parent
EXTRACTING, NOT_INDEXED = 651200001, 651200000
CLEAR = {"vz_documenttext": "", "vz_indexstatus": NOT_INDEXED, "vz_indexversion": "", "vz_indexerror": ""}


def select(rows: Iterable[Mapping[str, Any]], names: Iterable[str] = ()) -> tuple[list[Mapping[str, Any]], list[str]]:
    """Contracts to re-queue, and the reasons any were skipped. A row with no PDF or already extracting is skipped."""
    wanted = {name.lower() for name in names}
    chosen, skipped = [], []
    for row in rows:
        if wanted and row["vz_name"].lower() not in wanted:
            continue
        if not row.get("vz_document_name"):
            skipped.append(f"{row['vz_name']}: no PDF is attached")
        elif row["vz_status"] == EXTRACTING:
            skipped.append(f"{row['vz_name']}: already extracting")
        else:
            chosen.append(row)
    return chosen, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="discard findings and re-queue; otherwise only report")
    parser.add_argument("--wait", action="store_true", help="wait until no selected contract is extracting")
    parser.add_argument("--name", action="append", default=[], help="limit to a contract file name (repeatable)")
    args = parser.parse_args(argv)
    spec = importlib.util.spec_from_file_location("run_local", ROOT / "scripts" / "run-local.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    env = module.load_settings()
    dv = Dataverse("dv-data", solution="VizientContractPOC")
    if signed_in_account(dv).lower() != env["AZURE_ACCOUNT"].lower():
        raise RuntimeError("Dataverse account mismatch.")
    rows = list(dv.list("vz_contracts", {"$select": "vz_contractid,vz_name,vz_status,vz_document_name"}))
    chosen, skipped = select(rows, args.name)
    for reason in skipped:
        print(f"Skipped {reason}")
    for row in chosen:
        findings = list(dv.list("vz_findings", {"$select": "vz_findingid",
                                                 "$filter": f"_vz_contract_value eq {row['vz_contractid']}"}))
        print(f"{'Re-queue' if args.apply else 'Would re-queue'} {row['vz_name']}: discard {len(findings)} findings")
        if not args.apply:
            continue
        for finding in findings:
            dv.request("DELETE", f"vz_findings({finding['vz_findingid']})")
        dv.request("PATCH", f"vz_contracts({row['vz_contractid']})",
                   body={**CLEAR, "vz_status": EXTRACTING}, headers={"If-Match": "*"})
    if not args.apply:
        print("Dry run: nothing changed. Add --apply to discard review work and re-extract.")
        return 0
    if args.wait and chosen:
        ids = {row["vz_contractid"] for row in chosen}
        for _ in range(240):
            now = [dv.get(f"vz_contracts({item})", {"$select": "vz_name,vz_status,vz_indexstatus,vz_errormessage,vz_indexerror"})
                   for item in ids]
            if all(item["vz_status"] != EXTRACTING and item.get("vz_indexstatus") in (651200002, 651200003) for item in now):
                for item in now:
                    print(f"{item['vz_name']}: review status {item['vz_status']}, index status {item['vz_indexstatus']}"
                          + (f", error: {item.get('vz_indexerror') or item.get('vz_errormessage')}"
                             if item["vz_indexstatus"] == 651200003 or item["vz_status"] == 651200005 else ""))
                return 0
            time.sleep(10)
        raise RuntimeError("Timed out waiting for re-extraction; the flows may still be running.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
