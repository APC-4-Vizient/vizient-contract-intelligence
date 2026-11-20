"""Find and delete Azure AI Search chunks that no longer belong to a live contract version.

    python scripts/purge-contract-index.py --status                       # what is in the index, nothing changes
    python scripts/purge-contract-index.py --stale --orphans              # dry run of what would be deleted
    python scripts/purge-contract-index.py --stale --orphans --apply      # delete
    python scripts/purge-contract-index.py --contract <guid> --apply      # delete every version of one contract

--stale    chunks of an older version than the contract's current vz_indexversion
--orphans  chunks whose contract row no longer exists in Dataverse
--contract chunks of every version of one contract (use before re-extracting it)

Nothing is deleted without --apply. No document text is read or printed: only ids, versions and counts.
Run it after deleting contracts, and before any real contract is indexed, because Search chunks are not removed
when a Dataverse row is deleted. Sign-in comes from the verified Azure CLI account; targets come from ignored .env.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

import az
from dvweb import Dataverse, signed_in_account
from loadscript import load_script

BATCH = 500


def plan(documents: Iterable[Mapping[str, Any]], live: Mapping[str, str], *, stale: bool, orphans: bool,
         contracts: Iterable[str] = ()) -> list[str]:
    """Ids of the index documents to delete. live maps each existing contract id to its current index version."""
    targets = {str(UUID(contract)) for contract in contracts}
    doomed = []
    for document in documents:
        contract, version = document["contractId"], document["version"]
        if contract in targets:
            doomed.append(document["id"])
        elif orphans and contract not in live:
            doomed.append(document["id"])
        elif stale and live.get(contract) and version != live[contract]:
            doomed.append(document["id"])
    return doomed


def summarize(documents: Iterable[Mapping[str, Any]], live: Mapping[str, str]) -> dict[str, dict[str, int]]:
    """Per contract id: documents in the current version, in other versions, and whether the contract still exists."""
    result: dict[str, dict[str, int]] = defaultdict(lambda: {"current": 0, "other": 0, "exists": 0})
    for document in documents:
        contract = document["contractId"]
        entry = result[contract]
        entry["exists"] = int(contract in live)
        entry["current" if document["version"] == live.get(contract) else "other"] += 1
    return dict(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stale", action="store_true")
    parser.add_argument("--orphans", action="store_true")
    parser.add_argument("--contract", action="append", default=[], metavar="GUID")
    parser.add_argument("--apply", action="store_true", help="actually delete; otherwise only report")
    args = parser.parse_args(argv)
    if not (args.status or args.stale or args.orphans or args.contract):
        parser.error("choose --status, --stale, --orphans or --contract")
    try:
        for contract in args.contract:
            UUID(contract)
    except ValueError:
        parser.error("--contract needs a GUID")

    module = load_script("run-local.py", "run_local")
    env = module.load_settings()

    def cli(*words: str) -> Any:
        result = subprocess.run([*az.az_command(), *words, "--subscription", env["AZURE_SUBSCRIPTION_ID"],
                                 "--only-show-errors", "-o", "json"], capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout) if result.stdout.strip() else None

    az.check_signed_in(cli("account", "show"), env["TENANT_ID"], env["AZURE_ACCOUNT"])
    dv = Dataverse("dv-data", solution="VizientContractPOC")
    if signed_in_account(dv).lower() != env["AZURE_ACCOUNT"].lower():
        raise RuntimeError("Dataverse account mismatch.")
    settings = {item["name"]: item["value"] for item in cli(
        "functionapp", "config", "appsettings", "list", "-g", env["AZURE_RESOURCE_GROUP"],
        "-n", env["AZURE_FUNCTION_NAME"])}

    from azure.identity import AzureCliCredential
    from azure.search.documents import SearchClient

    search = SearchClient(settings["AZURE_SEARCH_ENDPOINT"], settings["AZURE_SEARCH_INDEX"],
                          AzureCliCredential(tenant_id=env["TENANT_ID"]))
    live = {row["vz_contractid"]: row.get("vz_indexversion") or ""
            for row in dv.list("vz_contracts", {"$select": "vz_contractid,vz_indexversion"})}
    documents = [{"id": item["id"], "contractId": item["contractId"], "version": item["version"]}
                 for item in search.search(search_text="*", select=["id", "contractId", "version"])]
    print(f"Index holds {len(documents)} documents for {len({d['contractId'] for d in documents})} contracts; "
          f"Dataverse holds {len(live)} contracts.")
    for contract, counts in sorted(summarize(documents, live).items()):
        state = "contract exists" if counts["exists"] else "ORPHAN (no contract row)"
        print(f"  {contract}: {counts['current']} current, {counts['other']} other-version; {state}")
    doomed = plan(documents, live, stale=args.stale, orphans=args.orphans, contracts=args.contract)
    if args.status and not (args.stale or args.orphans or args.contract):
        return 0
    print(f"{len(doomed)} documents match the purge selection.")
    if not args.apply:
        print("Dry run: nothing deleted. Add --apply to delete.")
        return 0
    deleted = 0
    for start in range(0, len(doomed), BATCH):
        batch = [{"id": item} for item in doomed[start:start + BATCH]]
        results = search.delete_documents(documents=batch)
        if len(results) != len(batch) or any(not result.succeeded for result in results):
            raise RuntimeError("Azure AI Search did not delete every selected document.")
        deleted += len(batch)
    print(f"Deleted {deleted} documents.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("CI", "1")
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
