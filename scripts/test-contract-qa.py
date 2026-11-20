"""Smoke-test contract Q&A with committed synthetic text or a newly generated synthetic PDF.

--direct exercises Foundry; otherwise creates a solution question row and waits for the deployed flow.
Never downloads a PDF or reads existing user-uploaded contract text.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import az
from dvweb import Dataverse, entity_id, signed_in_account

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "function"))
import contract_qa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--index-fixture", action="store_true",
                        help="queue only the committed synthetic fixture for ingestion-time indexing")
    parser.add_argument("--ingest-fixture", action="store_true",
                        help="generate a new synthetic PDF in memory and exercise extraction, indexing and Q&A")
    parser.add_argument("--expect-answer-text", help="fail if the synthetic answer does not contain this text")
    parser.add_argument("--question", default="May Vizient use the Data to train an AI model?")
    args = parser.parse_args()
    if args.ingest_fixture and (args.direct or args.index_fixture):
        parser.error("--ingest-fixture cannot be combined with --direct or --index-fixture")
    spec = importlib.util.spec_from_file_location("run_local", ROOT / "scripts" / "run-local.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    env = module.load_settings()
    raw = (ROOT / "tests" / "fixtures" / "cu_result_sow.json").read_text()
    contract_qa.source_pages(raw)
    request = {"contractId": "63abf974-20ea-472f-981a-8d42e67861cc", "questionId": str(uuid4()),
               "context": raw, "history": [], "question": args.question}
    if args.direct:
        from azure.ai.projects import AIProjectClient
        from azure.identity import AzureCliCredential
        from azure.identity import get_bearer_token_provider
        from azure.search.documents import SearchClient
        from openai import AzureOpenAI
        import contract_search

        base = [*az.az_command()]
        target = ["--subscription", env["AZURE_SUBSCRIPTION_ID"], "--only-show-errors", "-o", "json"]
        shown = subprocess.run([*base, "account", "show", *target], capture_output=True, text=True, check=True)
        az.check_signed_in(json.loads(shown.stdout), env["TENANT_ID"], env["AZURE_ACCOUNT"])
        shown = subprocess.run([*base, "functionapp", "config", "appsettings", "list",
                                "-g", env["AZURE_RESOURCE_GROUP"], "-n", env["AZURE_FUNCTION_NAME"], *target],
                               capture_output=True, text=True, check=True)
        settings = {item["name"]: item["value"] for item in json.loads(shown.stdout)}
        credential = AzureCliCredential(tenant_id=env["TENANT_ID"])
        project = AIProjectClient(endpoint=settings["FOUNDRY_PROJECT_ENDPOINT"], credential=credential)
        search = contract_search.Client(
            SearchClient(settings["AZURE_SEARCH_ENDPOINT"], settings["AZURE_SEARCH_INDEX"], credential),
            AzureOpenAI(azure_endpoint=settings["EMBEDDING_ENDPOINT"], api_version="2024-10-21",
                        azure_ad_token_provider=get_bearer_token_provider(
                            credential, "https://cognitiveservices.azure.com/.default"), timeout=30, max_retries=0),
            settings["EMBEDDING_MODEL"])
        client = contract_qa.Client(project, settings["FOUNDRY_QA_AGENT"], search)
        if args.index_fixture:
            indexing = {"contractId": request["contractId"], "context": raw}
            for _ in range(180):
                status, result = search.step(indexing)
                if status == 200:
                    break
                indexing["operation"] = result["operation"]
                time.sleep(3)
            else:
                raise RuntimeError("Direct synthetic indexing timed out.")
        for _ in range(90):
            status, answer = client.step(request)
            if status == 200:
                if args.expect_answer_text and args.expect_answer_text.lower() not in answer["answer"].lower():
                    raise RuntimeError("The synthetic answer did not contain the expected text.")
                print(json.dumps(answer))
                return 0
            request["operation"] = answer["operation"]
            time.sleep(5)
        raise RuntimeError("Foundry smoke test timed out.")
    dv = Dataverse("dv-data", solution="VizientContractPOC")
    if signed_in_account(dv).lower() != env["AZURE_ACCOUNT"].lower():
        raise RuntimeError("Dataverse account mismatch.")
    if args.ingest_fixture:
        from reportlab.pdfgen import canvas

        content = BytesIO()
        pdf = canvas.Canvas(content)
        lines = [
            "SYNTHETIC SAMPLE - MADE-UP CONTRACT FOR TESTING ONLY",
            "Contract between Vizient and Example Synthetic Supplier.",
            "1. Term. This agreement runs for seven years from its effective date.",
            "2. Data. Vizient shall not use the Data to train any AI model.",
            "3. Retention. The Data must be deleted when the agreement ends.",
        ]
        for line, y in zip(lines, range(760, 610, -30), strict=True):
            pdf.drawString(40, y, line)
        pdf.save()
        file_name = f"synthetic-search-proof-{uuid4().hex[:8]}.pdf"
        contract_id = entity_id(dv.request("POST", "vz_contracts", body={
            "vz_name": file_name, "vz_status": 651200000,
        }))
        row_path = f"vz_contracts({contract_id})"
        dv.upload_file(row_path, "vz_document", file_name, content.getvalue())
        dv.request("PATCH", row_path, body={"vz_status": 651200001}, headers={"If-Match": "*"})
        print("New generated synthetic document queued for extraction and indexing.", flush=True)
        for _ in range(240):
            row = dv.get(row_path, {"$select": "vz_status,vz_indexstatus,vz_documenttext,vz_indexerror,vz_errormessage"})
            if row["vz_status"] == 651200005:
                raise RuntimeError(row.get("vz_errormessage") or "Synthetic ingestion failed.")
            if row.get("vz_indexstatus") == 651200003:
                raise RuntimeError(row.get("vz_indexerror") or "Synthetic ingestion indexing failed.")
            if row.get("vz_indexstatus") == 651200002 and row["vz_status"] in (651200002, 651200003, 651200004):
                raw = row["vz_documenttext"]
                contract_qa.source_pages(raw)
                print("Synthetic ingestion reached both Review Ready and Q&A Ready.", flush=True)
                break
            time.sleep(5)
        else:
            raise RuntimeError("Synthetic ingestion timed out.")
    else:
        rows = list(dv.list("vz_contracts", {
            "$select": "vz_contractid", "$filter": "vz_name eq 'bluepine-sow.pdf' and vz_sharepointitemid eq null"}))
        if len(rows) != 1:
            raise RuntimeError("Expected exactly one seeded synthetic bluepine-sow.pdf contract.")
        contract_id = rows[0]["vz_contractid"]
    if args.index_fixture:
        dv.request("PATCH", f"vz_contracts({contract_id})", body={
            "vz_documenttext": raw, "vz_indexstatus": 651200001, "vz_indexversion": "", "vz_indexerror": "",
        }, headers={"If-Match": "*"})
        for _ in range(180):
            indexed = dv.get(f"vz_contracts({contract_id})", {"$select": "vz_indexstatus,vz_indexversion,vz_indexerror"})
            if indexed["vz_indexstatus"] == 651200002:
                print("Committed synthetic document indexed; version recorded.", flush=True)
                break
            if indexed["vz_indexstatus"] == 651200003:
                raise RuntimeError(indexed.get("vz_indexerror") or "Synthetic fixture indexing failed.")
            time.sleep(5)
        else:
            raise RuntimeError("Synthetic fixture indexing timed out.")
    question_id = entity_id(dv.request("POST", "vz_contractquestions", body={
        "vz_name": "Synthetic Q&A smoke test", "vz_question": args.question,
        "vz_context": raw, "vz_history": "[]", "vz_contract@odata.bind": f"/vz_contracts({contract_id})"}))
    print(f"Synthetic question queued: {question_id}", flush=True)
    for _ in range(120):
        row = dv.get(f"vz_contractquestions({question_id})", {"$select": "vz_status,vz_answer,vz_error,vz_context"})
        if row["vz_status"] == 651200001:
            answer = json.loads(row["vz_answer"])
            contract_qa.grounded_answer(json.dumps({**answer, "notAddressed": not answer["citations"]}),
                                        contract_qa.source_pages(raw))
            if row.get("vz_context"):
                raise RuntimeError("Question flow did not clear its transient context.")
            if args.expect_answer_text and args.expect_answer_text.lower() not in answer["answer"].lower():
                raise RuntimeError("The synthetic answer did not contain the expected text.")
            print(json.dumps(answer))
            return 0
        if row["vz_status"] == 651200002:
            raise RuntimeError(row.get("vz_error") or "Question flow failed.")
        time.sleep(5)
    raise RuntimeError("Question flow timed out.")


if __name__ == "__main__":
    os.environ.setdefault("CI", "1")
    sys.exit(main())
