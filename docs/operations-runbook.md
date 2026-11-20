# Operations runbook

Day-2 procedures for a deployed Vizient Contract Intelligence. To deploy it first, use the
[deployment runbook](./deployment-runbook.md). All commands run from the repository root in PowerShell, signed in as the
account named by `AZURE_ACCOUNT` in `.env`.

> **Validation status.** Procedures marked **Unverified** have not been run against a live system. Everything else follows
> the scripts and templates in this repository, and most of it was exercised in the demonstration environment.

## 1. Ownership

Fill this in before go-live. A pipeline with no named owners stops quietly when a credential or license changes. Suggested
owners for each row are in [team and roles](./team-and-roles.md), section 6.

| Responsibility | Owner | Notes |
|---|---|---|
| Azure subscription, budget and cost alerts | | Search is billed hourly even when idle |
| Azure resources and model quota | | Region, capacity, `azd provision` |
| Function key rotation | | 3.5 |
| Dataverse environment and the solution | | System Administrator |
| Owner of the flow connections | | 4.1 |
| Reviewer access and licenses | | 3.9 |
| Code App releases | | `pa app push` |
| Incident triage | | Section 4 |
| Contract data retention and deletion | | No policy exists yet, see section 6 |

## 2. Routine checks

Look at these on a schedule your team sets. Nothing alerts automatically yet.

| Check | Where | Healthy |
|---|---|---|
| Contracts waiting in **Extracting** | The contract list, or the `vz_contract` table | Each one moves to Ready for Review within a few minutes |
| Contracts in **Failed** | Same. The reason is in `vz_errormessage` | None unexplained |
| Contracts whose `vz_indexstatus` is **Failed** | The `vz_contract` table. The reason is in `vz_indexerror` | None. A failure here never blocks review |
| Flow run failures | Power Automate, solution `VizientContractPOC`, each flow's run history | No failed runs. A failed analysis run also marks the contract Failed |
| Function errors and slow calls | Application Insights (section 5) | Few failures, none repeating |
| Storage account networking and tags | Run the property check in the deployment runbook, 4.6 | Unchanged. Policy and governance automation can revert settings weeks after deployment |
| Model throttling | The Foundry accounts' metrics in Azure Monitor, and failed flow runs | No sustained throttling |
| Cost | Azure Cost Management on the resource group | Matches the estimate in the deployment runbook, appendix D |

## 3. Procedures

### 3.1 Retry a failed contract

Set the contract's **Status** back to **Extracting** (for example in the maker portal's table data view, or any Dataverse
client). The Analysis flow runs again. Extracting is the retry queue.

**The flow deletes every existing finding for the contract first, including reviewer decisions, before it calls the
Function.** If the new analysis then fails, the contract is left Failed with no findings. Retry only contracts whose review
work you can lose, and copy any decisions you need out of `vz_finding` beforehand.

### 3.2 Retry indexing

Set `vz_indexstatus` to **Queued**. The Indexing flow runs again. Reviewer work is untouched. This only works when the
contract has stored document text (`vz_documenttext`). If indexing was rejected before it started (for example the
synthetic-sample check in 4.2, or a document over the size limit), no text was stored: re-extract the contract instead (3.3).

### 3.3 Re-extract existing contracts

Use this for contracts ingested before full-text indexing existed, or after changing the checklist. **It discards the
findings and the review work of the contracts it touches.** It keeps the contract row, the PDF, the parent link and the
manual Owner and Reviewer fields.

```powershell
python scripts\reextract-contracts.py                          # dry run: lists what would be discarded
python scripts\reextract-contracts.py --apply --wait           # re-queue everything
python scripts\reextract-contracts.py --apply --name "file.pdf"   # one contract
```

### 3.4 Clean the Search index

Search chunks are versioned and never expire, and deleting a contract does not delete its chunks.

```powershell
python scripts\purge-contract-index.py --status                      # what the index holds; changes nothing
python scripts\purge-contract-index.py --stale --orphans --apply     # old versions and chunks of deleted contracts
python scripts\purge-contract-index.py --contract <guid> --apply     # every version of one contract
```

Run the second command after deleting or re-extracting contracts. `--stale` only considers contracts that have a current
index version. A contract that is still indexing, or whose indexing failed, has none, so its old chunks stay until it
indexes successfully or you purge it with `--contract`. Review the dry run (omit `--apply`) before deleting.

### 3.5 Rotate the Function key

The flows send the Function's default host key. It is stored as the text environment variable `vz_FunctionKey` in the
solution.

```powershell
python scripts\az.py functionapp keys set -g <resource-group> -n <function-app> --key-type functionKeys --key-name default
python scripts\provision-flow.py --status       # expect: update environment variable value vz_FunctionKey (value). Exit 1
python scripts\provision-flow.py --apply        # writes the new key; it is never printed
python scripts\provision-flow.py --status       # expect exit 0
```

Do the steps back to back. Between the first and the third, flow calls to the Function fail with 401, and any analysis
that was in flight ends as Failed: re-queue those with 3.1. **Unverified:** that `keys set` without `--key-value`
replaces an existing key's value. The first `--status` is the check: if it reports no change, the key did not change.

### 3.6 Change the checklist

`checklist/checklist.json` is the single source of truth. The analyzer definition, the Function's copy and the Dataverse
rows are all derived from it.

```powershell
python analyzer\build_schema.py --write
Copy-Item checklist\checklist.json function\checklist.json
python -m pytest tests -q                       # fails while either copy is stale
python scripts\seed-checklist.py --status
python scripts\seed-checklist.py --apply        # first: creates or updates the vz_checklistitem rows; nothing is ever deleted
python analyzer\deploy_analyzer.py --status
python analyzer\deploy_analyzer.py --apply
azd deploy --no-prompt                          # last: publishes the Function with its copy of the checklist
```

Seed the Dataverse rows **before** deploying the analyzer and the Function. The Analysis flow binds each finding to its
checklist row by key, so a finding for a key that has no row yet fails the run. Do the change when no contract is being
processed. Contracts that already have findings keep them. Re-extract (3.3) to apply the change to them. Keep each item's
evidence requirement: a Found result needs a verbatim clause, a source page and enough confidence.

### 3.7 Swap the extraction model

The analyzer refers to model aliases, and the Content Understanding defaults map those aliases to deployment names.

1. Make sure the model is deployed on the extraction Foundry account. Add it to `modelDeployments` in
   [main.bicep](../infra/main.bicep) and run `azd provision --no-prompt` (the template already deploys `gpt-5.4` as a
   fallback).
2. Set `CU_COMPLETION_MODEL=<model>` in `.env`, and `CU_COMPLETION_DEPLOYMENT=<deployment-name>` if the deployment name
   differs from the model name.
3. `python analyzer\deploy_analyzer.py --status`, then `--apply`.
4. Re-score on the synthetic set (`python scripts\run-local.py` on the generated PDFs, then `python eval\score.py`)
   before trusting it. Content Understanding answers can also differ slightly between runs of the same contract.

### 3.8 Change capacity, scale or the Python version

Model capacities, the instance cap (`maximumInstanceCount`, default 10; each instance is 2,048 MB and counts against the
regional Flex quota) and `pythonVersion` are defaults in [main.bicep](../infra/main.bicep). Change them there and run
`azd provision --preview --no-prompt`, review it, then `azd provision --no-prompt`. Q&A capacities are in
[qa.bicep](../infra/qa.bicep). Long contracts can be slow to index when the embedding quota is small.

Every procedure that runs `azd provision` assumes the environment still matches the templates. Run
`azd provision --preview --no-prompt` first and read it: it lists what would change. It does not show everything: it cannot
tell you, for example, whether a rule that a platform service added to the storage firewall would be removed (deployment
runbook, Appendix E), so check critical settings after provisioning (deployment runbook, 4.6). If anyone has changed the
environment by hand (in the portal, say), the preview shows what a provision would undo; do not run it until you have
decided that is what you want. The preview also lists differences on several resources that are not real changes
(read-only properties the templates do not set); compare it with a preview taken before your edit.

### 3.9 Give a reviewer access

Give them a security role with access to `vz_contract`, `vz_finding` and `vz_checklistitem` and **own-row** access to
`vz_contractquestion`, a license that can run code apps, and share the app. `pa app share` acts on the code app in the
current folder:

```powershell
Push-Location contract-review
pa app share --principal <email-or-object-id>
Pop-Location
```

### 3.10 Release changes

| Change | Edit | Then |
|---|---|---|
| Screens, filters, review behavior | [contract-review/src/](../contract-review/src/) | In `contract-review`, run each of `npx tsc -b`, `npm run lint`, `npm test` and `npm run build` and stop at the first failure, then `pa app push --solution-id <solution-id>` |
| Extraction mapping or Q&A logic | [function/](../function/) | `python -m pytest tests -q`, then `azd deploy --no-prompt`. Republish the agent with `python scripts\provision-qa.py --agent-only` when its instructions or tool schema change |
| Tables, columns, relationships | [schema.json](../dataverse/schema.json) | `python scripts\provision-dataverse.py` creates what is missing and skips what already exists, so it never changes an existing column, option or relationship: make such a change as an explicit metadata update and record it in `schema.json`. Then `python scripts\verify-solution.py`, `pa app refresh data-source`, rebuild and `pa app push --solution-id <solution-id>`. Only ever append choice options |
| Flows | [flowlib.py](../scripts/flowlib.py) | `python scripts\provision-flow.py --status`, then `--apply`. Do not edit flows in the designer |
| Azure resources | [infra/](../infra/) | `azd provision --preview --no-prompt`, review, then `azd provision --no-prompt` (see the warning in 3.8) |

After any solution change run `python scripts\pull-solution.py` so `dataverse/solution/` matches. Before every commit run
`python scripts\leak-scan.py` (exit 0), `python scripts\verify-solution.py` and the test suites. There is no automated
promotion between environments yet: repeat the steps in each one.

## 4. Troubleshooting

### 4.1 Pipeline

| Symptom | Likely cause | What to do |
|---|---|---|
| A contract stays in Extracting | The Analysis flow is off, failed, or cannot reach the Function | `python scripts\provision-flow.py --status`. Check the flow's run history. Check `GET <function>/api/health` returns 200 |
| Every flow run fails at once | The connection owner's sign-in, license or consent changed. Flows run as the owner of their connections | Reconnect the SharePoint and Dataverse connections in the maker portal, then `provision-flow.py --status`. Consider a dedicated service account as the owner. **Unverified** |
| `provision-flow.py --apply` says a flow "would not turn on" | A connection reference points at a connection that is not connected | Fix the connection, check its name in `.env`, run `--apply` again |
| Contract Failed, the message mentions the size | The PDF is over 4 MB. The Dataverse connector reads file columns in 4 MiB ranges | Reduce the file. The Function itself accepts up to 32 MiB |
| Contract Failed for another reason | Read `vz_errormessage`, then the flow run and the Function traces | Fix the cause, then 3.1 (which deletes any existing findings first) |
| Flow run fails with 401 from the Function | The key in `vz_FunctionKey` no longer matches the Function's key | 3.5 |
| Function answers 500 `Misconfigured` | A required setting or the checklist file is missing | Compare the app settings with the deployment runbook, appendix C. Redeploy with `azd deploy --no-prompt` |
| Content Understanding answers 400 `DefaultsNotSet` | The model defaults were never set on this resource | `python analyzer\deploy_analyzer.py --apply` |
| Content Understanding answers 403 | The Function identity or the deployer lacks the role, or a new assignment has not propagated | Check the roles in the deployment runbook, appendix B. Wait a few minutes after a change |
| Many 429 responses | Model quota is too small for the load | Raise the capacity (3.8) or request more quota |
| Scanned (image-only) PDF gives poor results | Never tested. The synthetic contracts all have a text layer | Treat as unsupported until tested |

### 4.2 Ask this contract

| Symptom | Likely cause | What to do |
|---|---|---|
| The button is disabled | `vz_indexstatus` is not **Ready** | Read `vz_indexstatus` and `vz_indexerror`. Requeue with 3.2 |
| Indexing Failed, "synthetic sample contracts only". Questions fail with the same message | `ALLOW_REAL_CONTRACTS` is not `true`, and the extracted text does not contain `SYNTHETIC SAMPLE`. The same check applies when a question is answered, so it affects contracts indexed earlier | Decide deliberately (deployment runbook 2.4), then `azd env set ALLOW_REAL_CONTRACTS true` and `azd provision --no-prompt` (see the warning in 3.8). Contracts whose indexing was rejected stored no text: re-extract them (3.3) |
| Indexing Failed, "no complete page-grounded extraction" | The contract was ingested before full-text indexing | Re-extract it (3.3) |
| Indexing Failed on a very long contract | About 1 MB of page text is the limit. Review is unaffected | None for review. Q&A is unavailable for that contract |
| "Did not return verifiable page evidence" | The model's quote could not be found in the retrieved passages and the original page. One automatic retry already happened | Rephrase the question. Invented quotes are rejected by design |
| "Not Addressed in the retrieved passages" | Only the top 12 passages are searched. Silence here is not proof the contract is silent | Ask Legal when it matters |
| Answers come from a deleted or changed contract | Chunks outlive their contract | 3.4 |

### 4.3 Azure and tooling

| Symptom | Likely cause | What to do |
|---|---|---|
| `azd provision` fails for Search with `InsufficientResourcesAvailable` | No new Search capacity in that region | `azd env set AZURE_SEARCH_LOCATION <other-region>` and provision again |
| The Function host will not start, storage errors, or `Process reporting unhealthy` traces | A tenant policy set the storage account's public network access to Disabled, or removed the exemption tag that was preventing it | Run the checks in the deployment runbook, 4.6. The durable fix is private networking: `azd env set ENABLE_PRIVATE_NETWORKING true`, then preview and provision (deployment runbook, Appendix E). A new exemption tag is not durable |
| An azd command fails with "failed to resolve user ... access to subscription" | azd uses the Azure CLI's active subscription, and the active account is not the deployer | Deployment runbook, 4.1 |
| `scripts\az.py` or a Dataverse script says it is signed in as someone else | The CLI's active account is not `AZURE_ACCOUNT` | Sign in as the right account. Never use `az account set` or `pa auth logout` as a shortcut |
| `verify-solution.py`: "not listed by the metadata API" | The Dataverse metadata API lagging right after provisioning | Wait a few minutes and run it again |
| A reviewer cannot open the app | No license, no security role, or the app is not shared | 3.9 |
| A redeployment is blocked by a deleted account | Foundry accounts soft-delete | Deployment runbook, section 7 |

## 5. Monitoring

Application Insights (`appi-<token>`) holds the Function's requests, traces and exceptions. The Function logs the type of an
exception and a short reason, never document text or credentials. In **Logs**:

```kusto
// failures by route and status, last 24 hours
requests
| where timestamp > ago(24h)
| summarize requests = count(), failures = countif(success == false) by name, resultCode
| order by failures desc
```

```kusto
// warnings and errors the Function logged
traces
| where timestamp > ago(24h) and severityLevel >= 2
| summarize count() by message
| order by count_ desc
| take 20
```

```kusto
// exceptions by type
exceptions
| where timestamp > ago(24h)
| summarize count() by type, outerMessage
| order by count_ desc
```

```kusto
// the Functions host reporting itself unhealthy (for example, it cannot reach its storage)
traces
| where timestamp > ago(24h) and message has "Process reporting unhealthy"
| summarize count() by bin(timestamp, 1h)
```

No alerts or action groups are created by this repository's templates. The demonstration environment has one log-search alert
added by hand: every 10 minutes it looks for an Application Insights trace containing `Process reporting unhealthy` (the
Functions host reporting itself unhealthy, for example when it cannot reach its storage) and notifies an action group. Add
equivalent alerts for your own environment, and consider an alert on failed Function requests and a scheduled check for
contracts that sit in Extracting for more than 15 minutes. Recommended, not built.

## 6. Data handling and open items

What is stored, and where:

| Data | Where |
|---|---|
| The original PDF | SharePoint, the intake library. Nothing in this project deletes it |
| The PDF copy | Dataverse, `vz_contract.vz_document` |
| Complete page text | Dataverse, `vz_contract.vz_documenttext`, and chunks in Azure AI Search (`contract-chunks`) |
| A reduced extraction result | Dataverse, `vz_contract.vz_rawresult` (debugging only) |
| Findings and reviewer decisions | Dataverse, `vz_finding`. AI results are immutable. Reviewer changes go in separate reviewer fields |
| Questions and answers | Dataverse, `vz_contractquestion`. Context and history are cleared after an answer or failure |
| Action inputs and outputs | Power Automate run history, for the platform's retention period. The flows secure the HTTP inputs (which carry the function key and the PDF) and both the inputs and outputs of the indexing and question actions, but not every output in the Intake and Analysis flows, so document content can appear in run history |
| Documents in analysis | Content Understanding keeps input documents, intermediate results and results in Microsoft-managed storage, in the resource's region, for up to 24 hours, then deletes them (Microsoft Learn: "Data, privacy, and security for Content Understanding") |
| Question responses | Foundry. The Function calls the agent in the background (`background=True`), which the Responses API only allows with `store=true`, so each question, its retrieved passages and the answer are stored in the Q&A Foundry resource, 30 days by default (Microsoft Learn: "Use the Azure OpenAI Responses API"). Nothing in this repository deletes them. A stored response can be deleted by id |

There are no stored keys except the Function key (3.5). Azure services use managed identities and Entra tokens; local
authentication is turned off on the Foundry accounts, Search and Application Insights.

Open before wider use or real contracts. These are not implemented:

| Item | Status |
|---|---|
| Least-privilege reviewer roles, and testing as a non-administrator | Open |
| Retention and deletion policy for Dataverse and Search content | Open. Search chunks are not deleted with their contract |
| Deleting stored Q&A responses in Foundry | Open. They are kept 30 days by default, and nothing here deletes them. If that period is too long, delete each response by id after the answer is saved, or ask Microsoft whether a different retention is available for the resource |
| Where models may process prompts | Open. Both Foundry accounts use GlobalStandard deployments, which may process prompts in any Azure geography (guide decision A2). A data-zone SKU is untested with Content Understanding |
| Who can open flow run history, and which action outputs are secured | Open. Restrict access, or secure the remaining outputs in `flowlib.py` |
| Production secret handling for the Function key | Open. Key Vault was unreachable from Power Platform under the demonstration tenant's policy |
| Monitoring, alerting, recovery and environment promotion | Open |
| Legal and security review of storing real contract text | Open |
| Regional availability, capacity and licensing in the customer's tenant | Open |
| Accuracy on real contracts | Not measured. The synthetic set scored 97% on data rights and 100% on contract details |

More limits are listed under "Known limits" in the [README](../README.md).
