"""Provision the additive Foundry Q&A infrastructure and prompt agent. No documents are read.

--status reads the configured agent. --apply validates/deploys infra/qa.bicep, then creates the agent.
Authentication and all deployment identifiers come from ignored local configuration.
The Search region is AZURE_SEARCH_LOCATION (azd environment or .env) and defaults to the deployment region.
ALLOW_REAL_CONTRACTS is an infrastructure setting owned by infra/main.bicep; this script never changes it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import az
from loadscript import load_script

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))
import contract_qa  # noqa: E402


def deployment_parameters(function_principal_id: str, deployer_id: str, search_location: str | None) -> tuple[str, ...]:
    """The qa.bicep parameters for az deployment; the Search region is passed only when one is configured."""
    values = [f"functionPrincipalId={function_principal_id}", f"deployerPrincipalId={deployer_id}"]
    if search_location:
        values.append(f"searchLocation={search_location}")
    return ("--parameters", *values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--validate", action="store_true", help="validate infrastructure only; create nothing")
    mode.add_argument("--agent-only", action="store_true", help="publish agent definition without changing infrastructure")
    args = parser.parse_args()
    module = load_script("run-local.py", "run_local")
    env = module.load_settings()
    sub, tenant = env["AZURE_SUBSCRIPTION_ID"], env["TENANT_ID"]

    def cli(*words: str) -> Any:
        target = [] if words[:1] == ("ad",) else ["--subscription", sub]
        result = subprocess.run([*az.az_command(), *words, *target, "--only-show-errors", "-o", "json"],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            # ARM errors contain resource ids, but never document text or credentials.
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout) if result.stdout.strip() else None

    account = cli("account", "show")
    az.check_signed_in(account, tenant, env["AZURE_ACCOUNT"])
    print("Azure account, tenant and subscription verified.")
    group, function = env["AZURE_RESOURCE_GROUP"], env["AZURE_FUNCTION_NAME"]
    if args.apply or args.validate:
        user = cli("ad", "signed-in-user", "show", "--query", "id")
        identities = cli("functionapp", "identity", "show", "-g", group, "-n", function)
        assigned = list((identities.get("userAssignedIdentities") or {}).values())
        if len(assigned) != 1:
            raise RuntimeError("Expected the Function's single configured user-assigned managed identity.")
        models = cli("cognitiveservices", "model", "list", "-l", env.get("AZURE_LOCATION", "eastus2"))
        if not any(item.get("model", {}).get("name") == "gpt-4.1-mini"
                   and item["model"].get("version") == "2025-04-14" for item in models):
            raise RuntimeError("The pinned Q&A model is not available in this region.")
        if not any(item.get("model", {}).get("name") == "text-embedding-3-small"
                   and item["model"].get("version") == "1" for item in models):
            raise RuntimeError("The pinned embedding model is not available in this region.")
        parameters = deployment_parameters(assigned[0]["principalId"], user, env.get("AZURE_SEARCH_LOCATION"))
        for command in (("validate",) if args.validate else ("validate", "create")):
            deployed = cli("deployment", "group", command, "-g", group, "-n", "contract-questions",
                           "--template-file", str(ROOT / "infra" / "qa.bicep"), *parameters)
            print(f"Q&A infrastructure {command}: complete.")
        if args.validate:
            preview = cli("deployment", "group", "what-if", "-g", group, "-n", "contract-questions",
                          "--template-file", str(ROOT / "infra" / "qa.bicep"),
                          "--no-pretty-print", *parameters)
            changes = preview.get("changes") or preview.get("properties", {}).get("changes", [])
            for change in changes:
                print(f"What-if: {change['changeType']} {change['resourceId'].rsplit('/', 1)[-1]}")
            if any(change["changeType"] == "Delete" for change in changes):
                raise RuntimeError("The Q&A deployment would delete resources. Review the template before applying.")
            return 0
        endpoint = deployed["properties"]["outputs"]["projectEndpoint"]["value"]
        search_endpoint = deployed["properties"]["outputs"]["searchEndpoint"]["value"]
        embedding_endpoint = deployed["properties"]["outputs"]["embeddingEndpoint"]["value"]
        cli("functionapp", "config", "appsettings", "set", "-g", group, "-n", function, "--settings",
            f"FOUNDRY_PROJECT_ENDPOINT={endpoint}", "FOUNDRY_QA_AGENT=contract-questions",
            "FOUNDRY_QA_MODEL=gpt-4.1-mini", f"AZURE_SEARCH_ENDPOINT={search_endpoint}",
            "AZURE_SEARCH_INDEX=contract-chunks", f"EMBEDDING_ENDPOINT={embedding_endpoint}",
            "EMBEDDING_MODEL=text-embedding-3-small")
    settings = cli("functionapp", "config", "appsettings", "list", "-g", group, "-n", function)
    values = {item["name"]: item["value"] for item in settings}
    endpoint = values.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("Q&A is not provisioned. Use --apply.")
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.identity import AzureCliCredential

    client = AIProjectClient(endpoint=endpoint, credential=AzureCliCredential(tenant_id=tenant))
    name = values["FOUNDRY_QA_AGENT"]
    if not args.status:
        from azure.search.documents.indexes import SearchIndexClient

        import contract_search

        if not values.get("AZURE_SEARCH_ENDPOINT"):
            raise RuntimeError("Azure AI Search is not provisioned. Validate and obtain approval before --apply.")
        indexes = SearchIndexClient(values["AZURE_SEARCH_ENDPOINT"], AzureCliCredential(tenant_id=tenant))
        indexes.create_or_update_index(contract_search.index_schema(values.get("AZURE_SEARCH_INDEX", "contract-chunks")))
        print("Contract chunk index schema: ready.")
        created = client.agents.create_version(
            agent_name=name, definition=PromptAgentDefinition(
                model=values["FOUNDRY_QA_MODEL"], instructions=contract_qa.INSTRUCTIONS),
            description="Answers from server-filtered Azure AI Search passages for the authorized contract version.")
        print(f"Foundry agent {created.name}, version {created.version}: created.")
    else:
        present = client.agents.get(name)
        print(f"Foundry agent {present.name}: present.")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("CI", "1")
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        sys.exit(1)
