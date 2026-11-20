"""Cloud flow definitions for the contract pipeline, built from dataverse/schema.json.

Two flows move a contract from SharePoint to a set of findings a person can review:

  Intake    A PDF lands in the SharePoint folder -> a vz_contract row, with the PDF in its vz_document
            file column -> vz_status becomes Extracting.
  Analysis  vz_status becomes Extracting -> the Function API analyzes the PDF -> the contract's promoted fields
            and one vz_finding row per checklist item are written -> vz_status becomes Ready for Review
            (or Failed, with the reason in vz_errormessage).

Setting vz_status to Extracting is also the retry: a Failed contract is re-queued by setting it again, and a
contract row created through the API can be analyzed without SharePoint.

Nothing environment-specific is written into a definition. The site, library, folder, Function address and
Function key are environment variables and the two connectors are connection references, so
scripts/provision-flow.py can set them per environment. The builders here are pure: no network, no secrets.
problems() checks a definition against the schema, so a renamed column cannot silently break a flow.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import schemalib

SHAREPOINT = "shared_sharepointonline"
DATAVERSE = "shared_commondataserviceforapps"
DEFINITION_SCHEMA = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
AUTH = "@parameters('$authentication')"

INTAKE_FLOW = "Vizient Contract Intake"
ANALYSIS_FLOW = "Vizient Contract Analysis"
QUESTION_FLOW = "Vizient Contract Questions"
INDEX_FLOW = "Vizient Contract Indexing"

# The Dataverse connector's file download returns at most the first 4 MiB. As base64 text that is 5,592,405 characters.
DOWNLOAD_LIMIT_BASE64 = 5_592_405
TEXT_MARGIN = 500  # Dataverse stores line breaks as CRLF, so long text is kept this far under its column's limit
POLL_SECONDS = 5
POLL_LIMIT = 180  # about 15 minutes at one poll every 5 seconds plus the call itself
FINDING_WORKERS = 10

ENVIRONMENT_VARIABLE_TEXT = 100000000


@dataclass(frozen=True)
class EnvVar:
    schema_name: str
    display_name: str
    description: str

    @property
    def parameter(self) -> str:
        """The name a flow definition uses to read the variable."""
        return f"{self.display_name} ({self.schema_name})"

    @property
    def expression(self) -> str:
        return f"@parameters('{self.parameter}')"


FUNCTION_URL = EnvVar("vz_FunctionBaseUrl", "Function Base URL",
                      "Address of the contract analysis Function app, such as https://<app>.azurewebsites.net, with no trailing slash.")
FUNCTION_KEY = EnvVar("vz_FunctionKey", "Function Key", "Host key of the contract analysis Function app, sent as x-functions-key.")
SITE_URL = EnvVar("vz_SharePointSiteUrl", "SharePoint Site URL", "Address of the SharePoint site that holds the intake library.")
LIBRARY_ID = EnvVar("vz_SharePointLibraryId", "SharePoint Library ID", "GUID of the document library that holds the intake folder.")
INTAKE_FOLDER = EnvVar("vz_IntakeFolderPath", "Intake Folder Path",
                       "Folder that is watched for new contracts, such as /Shared Documents/Contract Intake.")
ENV_VARS = (FUNCTION_URL, FUNCTION_KEY, SITE_URL, LIBRARY_ID, INTAKE_FOLDER)


@dataclass(frozen=True)
class ConnectionRef:
    connector: str
    logical_name: str
    display_name: str

    @property
    def connector_id(self) -> str:
        return f"/providers/Microsoft.PowerApps/apis/{self.connector}"


SHAREPOINT_REF = ConnectionRef(SHAREPOINT, "vz_sharepointonline", "Vizient Contract SharePoint")
DATAVERSE_REF = ConnectionRef(DATAVERSE, "vz_dataverse", "Vizient Contract Dataverse")
CONNECTION_REFS = (SHAREPOINT_REF, DATAVERSE_REF)


# --- schema lookups ------------------------------------------------------------------------------------------------

def _table(schema: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    for table in schema["tables"]:
        if table["name"] == name:
            return table
    raise KeyError(f"{name} is not a table in the schema")


def choice_values(schema: Mapping[str, Any], table: str, column: str) -> dict[str, int]:
    """Label -> stored value of a local choice column."""
    for col in _table(schema, table)["columns"]:
        if col["name"] == column and col["type"] == "choice":
            return {label: value for value, label in schemalib.options(dict(schema), col["options"])}
    raise KeyError(f"{table}.{column} is not a choice column in the schema")


def global_choice_values(schema: Mapping[str, Any], name: str) -> dict[str, int]:
    for choice in schema["global_choices"]:
        if choice["name"] == name:
            return {label: value for value, label in schemalib.options(dict(schema), choice["options"])}
    raise KeyError(f"{name} is not a global choice in the schema")


def entity_set(table: str) -> str:
    """Entity set name of a table. Every table here is named vz_<singular> and pluralised with an s."""
    return f"{table}s"


def max_length(schema: Mapping[str, Any], table: str, column: str) -> int:
    """The longest text a string, memo or primary name column holds."""
    spec = _table(schema, table)
    for col in (spec["primary"], *spec["columns"]):
        if col["name"] == column and "max_length" in col:
            return col["max_length"]
    raise KeyError(f"{table}.{column} has no maximum length in the schema")


def text_limit(schema: Mapping[str, Any], table: str, column: str) -> int:
    """How much of a long text to write: the column's limit less a margin for the CRLF line breaks Dataverse adds."""
    return max_length(schema, table, column) - TEXT_MARGIN


# --- expression helpers --------------------------------------------------------------------------------------------

def trigger_field(name: str) -> str:
    return "triggerOutputs()?['body/" + name + "']"


def clipped(expression: str, limit: int) -> str:
    """Text cut to a column's length, or null when there is none."""
    return f"if(empty({expression}), null, substring(string({expression}), 0, min(length(string({expression})), {limit})))"


def iso_date(expression: str) -> str:
    """The text when it looks like yyyy-MM-dd, else null: a date column rejects anything else."""
    text = f"string({expression})"
    shaped = f"and(equals(substring({text}, 4, 1), '-'), equals(substring({text}, 7, 1), '-'))"
    return f"if(equals(length({text}), 10), if({shaped}, {text}, null), null)"


def cut(expression: str, limit: int) -> str:
    return f"substring({expression}, 0, min(length({expression}), {limit}))"


# --- action builders -----------------------------------------------------------------------------------------------

def after(*names: str, on: tuple[str, ...] = ("Succeeded",)) -> dict[str, list[str]]:
    return {name: list(on) for name in names}


def connector_action(connector: str, operation: str, parameters: Mapping[str, Any], run_after: Mapping[str, Any] | None = None,
                     **extra: Any) -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": "OpenApiConnection",
        "inputs": {
            "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{connector}", "connectionName": connector,
                     "operationId": operation},
            "parameters": dict(parameters),
            "authentication": AUTH,
        },
        "runAfter": dict(run_after or {}),
    }
    action.update(extra)
    return action


def dataverse(operation: str, parameters: Mapping[str, Any], run_after: Mapping[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    return connector_action(DATAVERSE, operation, parameters, run_after, **extra)


def compose(value: Any, run_after: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "Compose", "inputs": value, "runAfter": dict(run_after or {})}


def terminate(code: str, message: str, run_after: Mapping[str, Any]) -> dict[str, Any]:
    return {"type": "Terminate", "inputs": {"runStatus": "Failed", "runError": {"code": code, "message": message}},
            "runAfter": dict(run_after)}


def scope(actions: Mapping[str, Any], run_after: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "Scope", "actions": dict(actions), "runAfter": dict(run_after or {})}


def mark_failed(contract_id: str, failed: int, message: str, run_after: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return dataverse("UpdateOnlyRecord", {"entityName": entity_set("vz_contract"), "recordId": contract_id,
                                          "item/vz_status": failed, "item/vz_errormessage": message}, run_after)


def failure_actions(try_scope: str, contract_id: str, failed: int, headline: str, limit: int) -> dict[str, Any]:
    """What a failure handler does: say which step failed, record it on the contract, and fail the run."""
    first = "first(body('Failed_steps'))"
    detail = ("@concat('" + headline + " Step: ', coalesce(" + first + "?['name'], 'unknown'), '. ', "
              "coalesce(" + first + "?['error']?['message'], ''), ' ', string(coalesce(" + first + "?['outputs'], '')), "
              "' (flow run ', workflow()?['run']?['name'], ')')")
    return {
        "Failed_steps": {"type": "Query", "inputs": {"from": f"@result('{try_scope}')",
                                                      "where": "@equals(item()?['status'], 'Failed')"}, "runAfter": {}},
        "Failure_detail": compose(detail, after("Failed_steps")),
        "Failure_text": compose("@" + cut("outputs('Failure_detail')", limit), after("Failure_detail")),
        "Mark_contract_failed": mark_failed(contract_id, failed, "@outputs('Failure_text')", after("Failure_text")),
        "Fail_the_run": terminate("ContractFlowFailed", "@outputs('Failure_text')",
                                  after("Mark_contract_failed", on=("Succeeded", "Failed", "TimedOut"))),
    }


def definition(parameters: Mapping[str, Any], triggers: Mapping[str, Any], actions: Mapping[str, Any]) -> dict[str, Any]:
    declared: dict[str, Any] = {
        "$connections": {"defaultValue": {}, "type": "Object"},
        "$authentication": {"defaultValue": {}, "type": "SecureObject"},
    }
    declared.update(parameters)
    return {"$schema": DEFINITION_SCHEMA, "contentVersion": "1.0.0.0", "parameters": declared,
            "triggers": dict(triggers), "actions": dict(actions), "outputs": {}}


def env_parameters(*variables: EnvVar) -> dict[str, Any]:
    return {var.parameter: {"defaultValue": "", "type": "String", "metadata": {"schemaName": var.schema_name}}
            for var in variables}


# --- the intake flow -----------------------------------------------------------------------------------------------

def intake_definition(schema: Mapping[str, Any]) -> dict[str, Any]:
    status = choice_values(schema, "vz_contract", "vz_status")
    contracts = entity_set("vz_contract")
    error_limit = text_limit(schema, "vz_contract", "vz_errormessage")
    file_name = trigger_field("{FilenameWithExtension}")
    link = trigger_field("{Link}")
    contract_id = "@outputs('Add_contract')?['body/vz_contractid']"

    trigger = {
        "When_a_file_is_added_to_Contract_Intake": {
            "type": "OpenApiConnection",
            "recurrence": {"frequency": "Minute", "interval": 1},
            "splitOn": "@triggerOutputs()?['body/value']",
            "inputs": {
                "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{SHAREPOINT}", "connectionName": SHAREPOINT,
                         "operationId": "GetOnNewFileItems"},
                "parameters": {"dataset": SITE_URL.expression, "table": LIBRARY_ID.expression,
                               "folderPath": INTAKE_FOLDER.expression},
                "authentication": AUTH,
            },
        }
    }
    attach = {
        "Upload_document": dataverse("UpdateEntityFileImageFieldContent", {
            "entityName": contracts, "recordId": contract_id, "fileImageFieldName": "vz_document",
            "item": "@body('Get_file_content')", "x-ms-file-name": "@" + file_name}),
        "Queue_analysis": dataverse("UpdateOnlyRecord", {
            "entityName": contracts, "recordId": contract_id, "item/vz_status": status["Extracting"]},
            after("Upload_document")),
    }
    handled = {
        "Get_file_content": connector_action(SHAREPOINT, "GetFileContent", {
            "dataset": SITE_URL.expression, "id": "@" + trigger_field("{Identifier}"), "inferContentType": True}),
        "Add_contract": dataverse("CreateRecord", {
            "entityName": contracts,
            "item/vz_name": "@" + file_name,
            "item/vz_sharepointurl": "@if(startsWith(toLower(string(" + link + ")), 'http'), "
                                     "replace(string(" + link + "), ' ', '%20'), null)",
            "item/vz_sharepointitemid": "@string(" + trigger_field("ID") + ")"}, after("Get_file_content")),
        "Attach_and_queue": scope(attach, after("Add_contract")),
        "Handle_failure": scope(failure_actions("Attach_and_queue", contract_id, status["Failed"],
                                                "The document could not be attached or queued for analysis.",
                                                error_limit),
                                after("Attach_and_queue", on=("Failed", "TimedOut"))),
    }
    actions = {
        "Is_a_PDF": {"type": "If", "expression": {"and": [{"endsWith": ["@toLower(" + file_name + ")", ".pdf"]}]},
                     "actions": handled, "else": {"actions": {}}, "runAfter": {}},
    }
    return definition(env_parameters(SITE_URL, LIBRARY_ID, INTAKE_FOLDER), trigger, actions)


# --- the analysis flow ---------------------------------------------------------------------------------------------

def _http(method: str, uri: str, headers: Mapping[str, str], run_after: Mapping[str, Any], *, body: Any = None,
          retry: Mapping[str, Any]) -> dict[str, Any]:
    inputs: dict[str, Any] = {"method": method, "uri": uri, "headers": dict(headers), "retryPolicy": dict(retry)}
    if body is not None:
        inputs["body"] = body
    # The async pattern would follow the 202 Location without the function key, so each call is made by hand.
    return {"type": "Http", "inputs": inputs, "runAfter": dict(run_after), "operationOptions": "DisableAsyncPattern",
            "runtimeConfiguration": {"secureData": {"properties": ["inputs"]}}}


def analysis_definition(schema: Mapping[str, Any]) -> dict[str, Any]:
    status = choice_values(schema, "vz_contract", "vz_status")
    index_status = choice_values(schema, "vz_contract", "vz_indexstatus")
    kinds = choice_values(schema, "vz_contract", "vz_documenttype")
    presence = choice_values(schema, "vz_finding", "vz_presence")
    contracts, findings = entity_set("vz_contract"), entity_set("vz_finding")
    error_limit = text_limit(schema, "vz_contract", "vz_errormessage")
    raw_limit = text_limit(schema, "vz_contract", "vz_rawresult")
    text_length = {column: max_length(schema, "vz_contract", column)
                   for column in ("vz_vendor", "vz_viziententity", "vz_contractidentifier")}
    finding_name_length = max_length(schema, "vz_finding", "vz_name")
    contract_id = "@" + trigger_field("vz_contractid")
    base = FUNCTION_URL.expression.removeprefix("@")
    key = FUNCTION_KEY.expression
    parsed = "outputs('Parsed_result')"

    def contract(field: str) -> str:
        return f"{parsed}?['contract']?['{field}']"

    def finding(field: str) -> str:
        return f"items('Add_findings')?['{field}']"

    trigger = {
        "When_a_contract_is_queued": {
            "type": "OpenApiConnectionWebhook",
            "inputs": {
                "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE}", "connectionName": DATAVERSE,
                         "operationId": "SubscribeWebhookTrigger"},
                "parameters": {
                    "subscriptionRequest/message": 3,  # Update
                    "subscriptionRequest/entityname": "vz_contract",
                    "subscriptionRequest/scope": 4,  # Organization
                    "subscriptionRequest/filteringattributes": "vz_status",
                    "subscriptionRequest/filterexpression": f"vz_status eq {status['Extracting']}",
                },
                "authentication": AUTH,
            },
        }
    }

    too_large = ("The document is 4 MB or larger. This version of the flow reads at most the first 4 MB of the "
                 "document column, so it was not analyzed.")
    add_finding = dataverse("CreateRecord", {
        "entityName": findings,
        "item/vz_name": "@" + cut("concat(" + trigger_field("vz_name") + ", ' - ', " + finding("key") + ")",
                                  finding_name_length),
        "item/vz_presence": "@coalesce(outputs('Maps')?['presence']?[string(" + finding("presence") + ")], "
                            + str(presence["Unclear"]) + ")",
        "item/vz_aivalue": "@" + finding("value"),
        "item/vz_aiconditions": "@" + finding("conditions"),
        "item/vz_clause": "@" + finding("clause"),
        "item/vz_aijudgment": "@if(empty(" + finding("judgment") + "), null, "
                              "outputs('Maps')?['judgment']?[string(" + finding("judgment") + ")])",
        "item/vz_page": "@" + finding("page"),
        "item/vz_sourceregions": "@string(coalesce(" + finding("sourceRegions") + ", json('[]')))",
        "item/vz_confidence": "@" + finding("confidence"),
        "item/vz_contract@odata.bind": "@{concat('" + contracts + "(', " + trigger_field("vz_contractid") + ", ')')}",
        "item/vz_checklistitem@odata.bind": "vz_checklistitems(vz_key='@{" + finding("key") + "}')",
    })
    raw = f"{parsed}?['raw']"
    on_success = {
        "Parsed_result": compose("@json(variables('pollText'))"),
        "Update_contract": dataverse("UpdateOnlyRecord", {
            "entityName": contracts, "recordId": contract_id,
            "item/vz_vendor": "@" + clipped(contract("vendor"), text_length["vz_vendor"]),
            "item/vz_viziententity": "@" + clipped(contract("vizientEntity"), text_length["vz_viziententity"]),
            "item/vz_contractidentifier": "@" + clipped(contract("contractIdentifier"),
                                                        text_length["vz_contractidentifier"]),
            "item/vz_documenttype": "@coalesce(outputs('Maps')?['documentType']?[string(coalesce("
                                    + contract("documentType") + ", 'Other'))], " + str(kinds["Other"]) + ")",
            "item/vz_effectivedate": "@" + iso_date(contract("effectiveDate")),
            "item/vz_expirationdate": "@" + iso_date(contract("expirationDate")),
            "item/vz_hasparentreference": "@equals(" + contract("hasParentReference") + ", true)",
            "item/vz_foundcount": "@" + contract("foundCount"),
            "item/vz_totalcount": "@" + contract("totalCount"),
            "item/vz_completeness": "@" + contract("completeness"),
            "item/vz_processedon": "@utcNow()",
            "item/vz_rawresult": f"@if(less(length(string({raw})), {raw_limit}), string({raw}), null)",
            "item/vz_documenttext": f"@{parsed}?['indexing']?['documentText']",
            "item/vz_indexstatus": f"@if(equals({parsed}?['indexing']?['status'], 'Queued'), {index_status['Queued']}, {index_status['Failed']})",
            "item/vz_indexversion": "",
            "item/vz_indexerror": f"@{parsed}?['indexing']?['error']",
        }, after("Parsed_result")),
        "Add_findings": {"type": "Foreach", "foreach": f"@{parsed}?['findings']",
                         "actions": {"Add_finding": add_finding}, "runAfter": after("Update_contract"),
                         "runtimeConfiguration": {"concurrency": {"repetitions": FINDING_WORKERS}}},
        "Mark_ready": dataverse("UpdateOnlyRecord", {
            "entityName": contracts, "recordId": contract_id, "item/vz_status": status["Ready for Review"]},
            after("Add_findings")),
    }
    run_name = "workflow()?['run']?['name']"
    on_failure = {
        "Describe_analysis_failure": compose(
            "@if(equals(variables('pollStatus'), 202), 'Timed out waiting for the analysis to finish.', "
            "concat('The analysis failed with HTTP ', string(variables('pollStatus')), ': ', "
            + cut("variables('pollText')", 2000) + "))"),
        "Mark_analysis_failed": mark_failed(
            contract_id, status["Failed"],
            f"@concat(outputs('Describe_analysis_failure'), ' (flow run ', {run_name}, ')')",
            after("Describe_analysis_failure")),
        "Fail_after_analysis": terminate("AnalysisFailed", "@outputs('Describe_analysis_failure')",
                                         after("Mark_analysis_failed", on=("Succeeded", "Failed", "TimedOut"))),
    }
    poll_done = ("@or(equals(variables('pollStatus'), 200), and(greaterOrEquals(variables('pollStatus'), 400), "
                 "not(contains(createArray(429, 503, 504), variables('pollStatus')))))")
    poll_loop = {
        "Wait_before_polling": {"type": "Wait", "inputs": {"interval": {"count": POLL_SECONDS, "unit": "Second"}},
                                "runAfter": {}},
        "Poll_analysis": _http(
            "GET", f"@{{{base}}}/api/contracts/analyze/@{{body('Submit_analysis')?['operationId']}}",
            {"x-functions-key": key, "Accept": "application/json"}, after("Wait_before_polling"), retry={"type": "none"}),
        "Record_poll_status": {"type": "SetVariable", "inputs": {
            "name": "pollStatus", "value": "@int(coalesce(actions('Poll_analysis')?['outputs']?['statusCode'], 503))"},
            "runAfter": after("Poll_analysis", on=("Succeeded", "Failed", "TimedOut"))},
        "Record_poll_body": {"type": "SetVariable", "inputs": {
            "name": "pollText", "value": "@string(coalesce(actions('Poll_analysis')?['outputs']?['body'], ''))"},
            "runAfter": after("Record_poll_status")},
    }
    attempt = {
        "Find_old_findings": dataverse("ListRecords", {
            "entityName": findings, "$select": "vz_findingid",
            "$filter": "_vz_contract_value eq @{" + trigger_field("vz_contractid") + "}"}),
        "Delete_old_findings": {"type": "Foreach", "foreach": "@outputs('Find_old_findings')?['body/value']",
                                "actions": {"Delete_old_finding": dataverse("DeleteRecord", {
                                    "entityName": findings, "recordId": "@items('Delete_old_findings')?['vz_findingid']"})},
                                "runAfter": after("Find_old_findings"),
                                "runtimeConfiguration": {"concurrency": {"repetitions": FINDING_WORKERS}}},
        "Download_document": dataverse("GetEntityFileImageFieldContent", {
            "entityName": contracts, "recordId": contract_id, "fileImageFieldName": "vz_document"},
            after("Delete_old_findings")),
        "Check_document_size": {
            "type": "If",
            "expression": {"and": [{"less": ["@length(coalesce(body('Download_document')?['$content'], ''))",
                                             DOWNLOAD_LIMIT_BASE64]}]},
            "actions": {},
            "else": {"actions": {
                "Mark_document_too_large": mark_failed(contract_id, status["Failed"], too_large),
                "Fail_document_too_large": terminate("DocumentTooLarge", too_large,
                                                     after("Mark_document_too_large", on=("Succeeded", "Failed", "TimedOut"))),
            }},
            "runAfter": after("Download_document"),
        },
        "Submit_analysis": _http(
            "POST", f"@{{{base}}}/api/contracts/analyze",
            {"x-functions-key": key, "Content-Type": "application/json", "Accept": "application/json"},
            after("Check_document_size"),
            body={"contractId": contract_id, "fileName": "@" + trigger_field("vz_name"),
                  "fileBase64": "@{body('Download_document')?['$content']}"},
            retry={"type": "fixed", "count": 3, "interval": "PT15S"}),
        "Wait_for_the_analysis": {"type": "Until", "expression": poll_done,
                                  "limit": {"count": POLL_LIMIT, "timeout": "PT25M"}, "actions": poll_loop,
                                  "runAfter": after("Submit_analysis")},
        "Check_analysis": {"type": "If", "expression": {"and": [{"equals": ["@variables('pollStatus')", 200]}]},
                           "actions": on_success, "else": {"actions": on_failure},
                           "runAfter": after("Wait_for_the_analysis", on=("Succeeded", "Failed", "TimedOut"))},
    }
    maps = {"presence": presence, "judgment": global_choice_values(schema, "vz_judgment"), "documentType": kinds}
    actions = {
        "Init_pollStatus": {"type": "InitializeVariable", "inputs": {"variables": [
            {"name": "pollStatus", "type": "integer", "value": 0}]}, "runAfter": {}},
        "Init_pollText": {"type": "InitializeVariable", "inputs": {"variables": [
            {"name": "pollText", "type": "string", "value": ""}]}, "runAfter": after("Init_pollStatus")},
        "Maps": compose(maps, after("Init_pollText")),
        "Try": scope(attempt, after("Maps")),
        "Catch": scope(failure_actions("Try", contract_id, status["Failed"], "The analysis flow failed.", error_limit),
                       after("Try", on=("Failed", "TimedOut"))),
    }
    return definition(env_parameters(FUNCTION_URL, FUNCTION_KEY), trigger, actions)


def indexing_definition(schema: Mapping[str, Any]) -> dict[str, Any]:
    """A separate flow: indexing failures never change review status or findings."""
    status = choice_values(schema, "vz_contract", "vz_indexstatus")
    contract_id = "@" + trigger_field("vz_contractid")
    trigger = {
        "When_document_indexing_is_queued": {
            "type": "OpenApiConnectionWebhook",
            "inputs": {
                "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE}",
                         "connectionName": DATAVERSE, "operationId": "SubscribeWebhookTrigger"},
                "parameters": {
                    "subscriptionRequest/message": 3, "subscriptionRequest/entityname": "vz_contract",
                    "subscriptionRequest/scope": 4, "subscriptionRequest/filteringattributes": "vz_indexstatus",
                    "subscriptionRequest/filterexpression": f"vz_indexstatus eq {status['Queued']}",
                }, "authentication": AUTH,
            }, "runtimeConfiguration": {"secureData": {"properties": ["inputs", "outputs"]}},
        }
    }
    call = _http(
        "POST", "@{" + FUNCTION_URL.expression[1:] + "}/api/contracts/index",
        {"x-functions-key": FUNCTION_KEY.expression, "Content-Type": "application/json"}, {},
        body={"contractId": contract_id, "context": "@" + trigger_field("vz_documenttext"),
              "operation": "@variables('indexOperation')"}, retry={"type": "none"})
    call["runtimeConfiguration"]["secureData"]["properties"].append("outputs")
    loop = {
        "Index_document": call,
        "Record_index_status": {"type": "SetVariable", "inputs": {
            "name": "indexHttp", "value": "@int(coalesce(actions('Index_document')?['outputs']?['statusCode'], 502))"},
            "runAfter": after("Index_document", on=("Succeeded", "Failed", "TimedOut"))},
        "Record_index_operation": {"type": "SetVariable", "inputs": {
            "name": "indexOperation", "value": "@coalesce(body('Index_document')?['operation'], json('{}'))"},
            "runAfter": after("Record_index_status")},
        "Index_pause": {"type": "Wait", "inputs": {"interval": {"count": 3, "unit": "Second"}},
                        "runAfter": after("Record_index_operation")},
    }
    ready = dataverse("UpdateOnlyRecord", {
        "entityName": "vz_contracts", "recordId": contract_id,
        "item/vz_indexstatus": status["Ready"],
        "item/vz_indexversion": "@body('Index_document')?['version']", "item/vz_indexerror": ""})
    failed = dataverse("UpdateOnlyRecord", {
        "entityName": "vz_contracts", "recordId": contract_id,
        "item/vz_indexstatus": status["Failed"], "item/vz_indexversion": "",
        "item/vz_indexerror": "@coalesce(body('Index_document')?['error']?['message'], 'Document indexing timed out or failed. Retry Q&A indexing.')"})
    actions = {
        "Init_index_http": {"type": "InitializeVariable", "inputs": {"variables": [
            {"name": "indexHttp", "type": "integer", "value": 0}]}, "runAfter": {}},
        "Init_index_operation": {"type": "InitializeVariable", "inputs": {"variables": [
            {"name": "indexOperation", "type": "object", "value": {}}]}, "runAfter": after("Init_index_http")},
        "Index_until_complete": {"type": "Until", "expression": "@not(equals(variables('indexHttp'), 202))",
            "limit": {"count": 180, "timeout": "PT25M"}, "actions": loop, "runAfter": after("Init_index_operation")},
        "Read_current_document_version": dataverse("GetItem", {
            "entityName": "vz_contracts", "recordId": contract_id, "$select": "vz_documenttext"},
            after("Index_until_complete", on=("Succeeded", "Failed", "TimedOut")),
            runtimeConfiguration={"secureData": {"properties": ["inputs", "outputs"]}}),
        "Only_update_the_indexed_document": {
            "type": "If", "expression": {"and": [{"equals": [
                "@body('Read_current_document_version')?['vz_documenttext']",
                "@" + trigger_field("vz_documenttext")]}]},
            "actions": {
                "Record_index_outcome": {
                    "type": "If", "expression": {"and": [{"equals": ["@variables('indexHttp')", 200]}]},
                    "actions": {"Mark_index_ready": ready}, "else": {"actions": {"Mark_index_failed": failed}},
                    "runAfter": {},
                },
            },
            "else": {"actions": {}}, "runAfter": after("Read_current_document_version"),
        },
    }
    for action in (ready, failed):
        action["runtimeConfiguration"] = {"secureData": {"properties": ["inputs", "outputs"]}}
    return definition(env_parameters(FUNCTION_URL, FUNCTION_KEY), trigger, actions)


def question_definition(schema: Mapping[str, Any]) -> dict[str, Any]:
    status = choice_values(schema, "vz_contractquestion", "vz_status")
    questions = entity_set("vz_contractquestion")
    question_id = "@" + trigger_field("vz_contractquestionid")
    trigger = {
        "When_a_question_is_created": {
            "type": "OpenApiConnectionWebhook",
            "inputs": {
                "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE}",
                         "connectionName": DATAVERSE, "operationId": "SubscribeWebhookTrigger"},
                "parameters": {
                    "subscriptionRequest/message": 1,
                    "subscriptionRequest/entityname": "vz_contractquestion",
                    "subscriptionRequest/scope": 4,
                    "subscriptionRequest/filterexpression": f"vz_status eq {status['Queued']}",
                },
                "authentication": AUTH,
            },
            "runtimeConfiguration": {"secureData": {"properties": ["inputs", "outputs"]}},
        }
    }
    call = _http(
        "POST", "@{" + FUNCTION_URL.expression[1:] + "}/api/contracts/questions",
        {"x-functions-key": FUNCTION_KEY.expression, "Content-Type": "application/json"}, {},
        body={"questionId": question_id, "contractId": "@" + trigger_field("_vz_contract_value"),
              "question": "@" + trigger_field("vz_question"), "context": "@" + trigger_field("vz_context"),
              "history": "@coalesce(" + trigger_field("vz_history") + ", '[]')",
              "operation": "@variables('qaOperation')"},
        retry={"type": "none"})
    call["runtimeConfiguration"]["secureData"]["properties"].append("outputs")
    loop = {
        "Ask_Foundry": call,
        "Record_question_status": {"type": "SetVariable", "inputs": {
            "name": "qaStatus", "value": "@int(coalesce(actions('Ask_Foundry')?['outputs']?['statusCode'], 502))"},
            "runAfter": after("Ask_Foundry", on=("Succeeded", "Failed", "TimedOut"))},
        "Record_question_operation": {"type": "SetVariable", "inputs": {
            "name": "qaOperation", "value": "@coalesce(body('Ask_Foundry')?['operation'], json('{}'))"},
            "runAfter": after("Record_question_status")},
        "Pause_question_poll": {"type": "Wait", "inputs": {"interval": {"count": 5, "unit": "Second"}},
                                "runAfter": after("Record_question_operation")},
    }
    answered = dataverse("UpdateOnlyRecord", {
        "entityName": questions, "recordId": question_id,
        "item/vz_status": status["Answered"], "item/vz_answer": "@string(body('Ask_Foundry'))",
        "item/vz_context": "", "item/vz_history": "",
    })
    failed = dataverse("UpdateOnlyRecord", {
        "entityName": questions, "recordId": question_id, "item/vz_status": status["Failed"],
        "item/vz_context": "", "item/vz_history": "",
        "item/vz_error": "@coalesce(body('Ask_Foundry')?['error']?['message'], 'The contract agent timed out. Try a new question.')",
    })
    attempt = {
        "Poll_contract_question": {
            "type": "Until", "expression": "@not(equals(variables('qaStatus'), 202))",
            "limit": {"count": 120, "timeout": "PT15M"}, "actions": loop, "runAfter": {},
        },
        "Finish_question": {
            "type": "If", "expression": {"and": [{"equals": ["@variables('qaStatus')", 200]}]},
            "actions": {"Save_grounded_answer": answered},
            "else": {"actions": {"Save_question_failure": failed}},
            "runAfter": after("Poll_contract_question", on=("Succeeded", "Failed", "TimedOut")),
        },
    }
    catch = dataverse("UpdateOnlyRecord", {
        "entityName": questions, "recordId": question_id, "item/vz_status": status["Failed"],
        "item/vz_context": "", "item/vz_history": "",
        "item/vz_error": "The question flow failed. Try a new question.",
    })
    actions = {
        "Init_qaStatus": {"type": "InitializeVariable", "inputs": {"variables": [
            {"name": "qaStatus", "type": "integer", "value": 202}]}, "runAfter": {}},
        "Init_qaOperation": {"type": "InitializeVariable", "inputs": {"variables": [
            {"name": "qaOperation", "type": "object", "value": {}}]}, "runAfter": after("Init_qaStatus")},
        "Try_question": scope(attempt, after("Init_qaOperation")),
        "Catch_question": scope({"Fail_question_flow": catch}, after("Try_question", on=("Failed", "TimedOut"))),
    }
    for _siblings, _name, action in walk_actions(actions):
        if action["type"] == "OpenApiConnection":
            action["runtimeConfiguration"] = {"secureData": {"properties": ["inputs", "outputs"]}}
    return definition(env_parameters(FUNCTION_URL, FUNCTION_KEY), trigger, actions)


# --- packaging -----------------------------------------------------------------------------------------------------

def connectors_used(flow: Mapping[str, Any]) -> list[str]:
    """Connector names (the connectionName of each connector action or trigger), in a stable order."""
    names: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            if isinstance(node.get("connectionName"), str):
                names.add(node["connectionName"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(flow["triggers"])
    visit(flow["actions"])
    return sorted(names)


def client_data(flow: Mapping[str, Any]) -> str:
    """The clientdata text of a workflow row: the definition plus a connection reference for each connector it uses."""
    by_connector = {ref.connector: ref for ref in CONNECTION_REFS}
    references = {}
    for connector in connectors_used(flow):
        ref = by_connector[connector]
        references[connector] = {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": ref.logical_name},
                                 "api": {"name": connector}, "impersonation": {}}
    payload = {"properties": {"connectionReferences": references, "definition": flow}, "schemaVersion": "1.0.0.0"}
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class FlowSpec:
    name: str
    summary: str
    definition: Mapping[str, Any]

    @property
    def client_data(self) -> str:
        return client_data(self.definition)

    @property
    def tag(self) -> str:
        """Kept at the end of the flow's description, so a later run can tell whether the stored flow is current."""
        return f"[definition {fingerprint(self.client_data)}]"

    @property
    def description(self) -> str:
        return f"{self.summary} Built by scripts/provision-flow.py; do not edit by hand. {self.tag}"

    @property
    def row(self) -> dict[str, Any]:
        return {"category": 5, "type": 1, "statecode": 0, "statuscode": 1, "name": self.name, "description": self.description,
                "primaryentity": "none", "clientdata": self.client_data}


def flow_specs(schema: Mapping[str, Any] | None = None) -> list[FlowSpec]:
    schema = schema or schemalib.load_schema()
    return [
        FlowSpec(INTAKE_FLOW, "Adds a contract row and its PDF when a file arrives in the SharePoint intake folder, then queues the analysis.",
                 intake_definition(schema)),
        FlowSpec(ANALYSIS_FLOW, "Analyzes a queued contract with the Function API and writes its findings for review.",
                 analysis_definition(schema)),
        FlowSpec(QUESTION_FLOW, "Answers a user's question from only the authorized text of the open contract using Foundry.",
                 question_definition(schema)),
        FlowSpec(INDEX_FLOW, "Indexes complete synthetic contract documents for Q&A independently of review readiness.",
                 indexing_definition(schema)),
    ]


# --- checks --------------------------------------------------------------------------------------------------------

_REFERENCE = re.compile(r"\b(outputs|body|actions|result|items|variables|parameters)\('([^']+)'\)")
_GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_EMBEDDED = re.compile(r"https?://|\.sharepoint\.com|azurewebsites|windows\.net", re.IGNORECASE)
_LOOKUP_FILTER = re.compile(r"\b(_\w+_value)\b")
RUN_AFTER_OUTCOMES = frozenset({"Succeeded", "Failed", "Skipped", "TimedOut"})


def walk_actions(actions: Mapping[str, Any]) -> Iterator[tuple[Mapping[str, Any], str, dict[str, Any]]]:
    """(the dict that holds the action, its name, the action) for every action, nested ones included."""
    for name, action in actions.items():
        yield actions, name, action
        yield from walk_actions(action.get("actions") or {})
        yield from walk_actions((action.get("else") or {}).get("actions") or {})


def _strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, Mapping):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


def _closing_brace(text: str, start: int) -> int:
    """Index of the } that closes an @{ whose contents begin at start."""
    depth, quoted = 1, False
    for index in range(start, len(text)):
        char = text[index]
        if char == "'":
            quoted = not quoted  # an escaped quote ('') toggles twice
        elif not quoted and char == "{":
            depth += 1
        elif not quoted and char == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("an @{ is never closed")


def _expressions(text: str) -> Iterator[str]:
    """The expressions in one definition string: all of it after a leading @, or each @{...} piece."""
    if text.startswith("@@"):
        return
    if text.startswith("@") and not text.startswith("@{"):
        yield text[1:]
        return
    position = text.find("@{")
    while position >= 0:
        end = _closing_brace(text, position + 2)
        yield text[position + 2:end]
        position = text.find("@{", end + 1)


def _balanced(expression: str) -> bool:
    opening = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    quoted = False
    for char in expression:
        if char == "'":
            quoted = not quoted
        elif not quoted and char in "([{":
            stack.append(char)
        elif not quoted and char in opening:
            if not stack or stack.pop() != opening[char]:
                return False
    return not stack and not quoted


def _expression_problems(piece: str, known: Mapping[str, set[str]], actions: set[str]) -> list[str]:
    try:
        expressions = list(_expressions(piece))
    except ValueError:
        return [f"an @{{ is never closed in {piece[:60]!r}"]
    found = []
    for expression in expressions:
        if not _balanced(expression):
            found.append(f"unbalanced brackets or quotes in {expression[:70]!r}")
        for kind, target in _REFERENCE.findall(expression):
            if target not in known.get(kind, actions):
                found.append(f"{kind}('{target}') names something the flow does not have")
    return found


def _dataverse_problems(schema: Mapping[str, Any], name: str, action: Mapping[str, Any]) -> list[str]:
    inputs = action["inputs"]
    if inputs["host"]["connectionName"] != DATAVERSE:
        return []
    params = inputs["parameters"]
    tables = {entity_set(table["name"]): table for table in schema["tables"]}
    table = tables.get(params.get("entityName"))
    if table is None:
        return [f"{name}: entityName {params.get('entityName')!r} is not a table of the schema"]
    columns = set(schemalib.column_names(dict(schema), dict(table))) | {f"{table['name']}id"}
    lookups = {rel["lookup"] for rel in schema["relationships"] if rel["referencing"] == table["name"]}
    files = {col["name"] for col in table["columns"] if col["type"] == "file"}
    found = []
    for key in params:
        if key.startswith("item/"):
            column = key.removeprefix("item/")
            if column.endswith("@odata.bind"):
                if column.removesuffix("@odata.bind") not in lookups:
                    found.append(f"{name}: {key} is not a lookup of {table['name']}")
            elif column not in columns:
                found.append(f"{name}: {key} is not a column of {table['name']}")
    if "fileImageFieldName" in params and params["fileImageFieldName"] not in files:
        found.append(f"{name}: {params['fileImageFieldName']} is not a file column of {table['name']}")
    for column in str(params.get("$select", "")).split(","):
        if column and column not in columns:
            found.append(f"{name}: $select names {column}, which {table['name']} does not have")
    for lookup in _LOOKUP_FILTER.findall(str(params.get("$filter", ""))):
        if lookup.removeprefix("_").removesuffix("_value") not in lookups:
            found.append(f"{name}: $filter names {lookup}, which is not a lookup of {table['name']}")
    return found


def problems(flow: Mapping[str, Any], schema: Mapping[str, Any]) -> list[str]:
    """Everything wrong with a flow definition that can be found without running it. Empty when it is sound."""
    found: list[str] = []
    if len(flow["triggers"]) != 1:
        found.append("a flow needs exactly one trigger")
    walked = list(walk_actions(flow["actions"]))
    names = [name for _siblings, name, _action in walked]
    for name in sorted({name for name in names if names.count(name) > 1}):
        found.append(f"{name}: the action name is used more than once")
    by_name = {name: action for _siblings, name, action in walked}
    loops = {name for name, action in by_name.items() if action["type"] == "Foreach"}
    variables = {item["name"] for action in by_name.values() if action["type"] == "InitializeVariable"
                 for item in action["inputs"]["variables"]}
    known = {"items": loops, "variables": variables, "parameters": set(flow["parameters"])}
    for siblings, name, action in walked:
        for target, outcomes in action.get("runAfter", {}).items():
            if target not in siblings:
                found.append(f"{name}: runAfter {target} is not an action next to it")
            if not outcomes or not set(outcomes) <= RUN_AFTER_OUTCOMES:
                found.append(f"{name}: runAfter {target} names an outcome that does not exist")
        if action["type"] == "InitializeVariable" and siblings is not flow["actions"]:
            found.append(f"{name}: a variable can only be initialized at the top level of the flow")
        if action["type"] == "SetVariable" and action["inputs"]["name"] not in variables:
            found.append(f"{name}: sets {action['inputs']['name']}, which is never initialized")
        if action["type"] == "OpenApiConnection":
            found.extend(_dataverse_problems(schema, name, action))
    for piece in list(_strings(flow["triggers"])) + list(_strings(flow["actions"])):
        found.extend(_expression_problems(piece, known, set(by_name)))
        if _GUID.search(piece) or _EMBEDDED.search(piece):
            found.append(f"an environment-specific value is written into the flow: {piece[:60]!r}")
    for name, action in by_name.items():
        if action["type"] == "Http" and "inputs" not in action.get("runtimeConfiguration", {}).get("secureData", {}).get("properties", []):
            found.append(f"{name}: the HTTP call carries the function key, so its inputs must be secured")
        if action["type"] == "Http" and action.get("operationOptions") != "DisableAsyncPattern":
            found.append(f"{name}: the asynchronous pattern must be off, or the poll is made without the key")
    for trigger in flow["triggers"].values():
        params = trigger["inputs"]["parameters"]
        if "subscriptionRequest/entityname" in params:
            table = _table(schema, params["subscriptionRequest/entityname"])
            filtering = params.get("subscriptionRequest/filteringattributes")
            if filtering and filtering not in schemalib.column_names(dict(schema), dict(table)):
                found.append("the trigger filters on a column the table does not have")
    return found
