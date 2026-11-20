# Deployment runbook

How to deploy Vizient Contract Intelligence into a new Azure subscription, Power Platform environment and SharePoint
site, and prove it works. Day-2 procedures (retries, key rotation, monitoring, troubleshooting) are in the
[operations runbook](./operations-runbook.md).

> **Validation status.** This runbook follows the source code and the record of the demonstration deployment. It has
> **not** been run from a clean start in a second tenant. Steps marked **Unverified** were never exercised from nothing
> (the demonstration environment was built up piece by piece). Run it first in a development subscription and
> environment, and correct this file where reality differs. That run is the acceptance test for this document.

## 1. What you are deploying

```text
SharePoint "Contract Intake" folder
  -> flow "Vizient Contract Intake"      creates the contract row, attaches the PDF, sets status Extracting
  -> flow "Vizient Contract Analysis"    sends the PDF to the Function, writes 20 findings, sets Ready for Review (or Failed)
  -> Azure Function  /api/contracts/analyze  ->  Content Understanding analyzer "vizientContractChecklist"
  -> flow "Vizient Contract Indexing"    indexes the full page text in Azure AI Search (for Ask this contract)
  -> flow "Vizient Contract Questions"   answers a question about one contract through a Foundry prompt agent
Dataverse solution VizientContractPOC: vz_contract, vz_finding, vz_checklistitem, vz_contractquestion
Code App "Vizient Contract Review": the reviewer's screen
```

| Layer | Deployed by | What it creates |
|---|---|---|
| Azure | `azd provision` and `azd deploy` ([infra/](../infra/)) | Resource group, Function app, Foundry account with the extraction models, Q&A Foundry account and project, Azure AI Search, storage, monitoring, managed identity, role assignments |
| Content Understanding | `analyzer/deploy_analyzer.py` | Model defaults and the `vizientContractChecklist` analyzer, generated from [checklist.json](../checklist/checklist.json) |
| Q&A agent | `scripts/provision-qa.py` | The Search index schema and the Foundry prompt agent `contract-questions` |
| Dataverse | `scripts/provision-dataverse.py`, `scripts/seed-checklist.py` | Four tables, columns, choices and relationships inside the unmanaged solution. The 22 checklist rows are data, not solution components, so seed each environment |
| Power Automate | `scripts/provision-flow.py` | Four cloud flows, two connection references and five environment variables, all inside the solution |
| Code App | `pa app push` | The review app, added to the solution |

Q&A cannot be left out today. `azd provision` always deploys it (a second Foundry account and a Basic Azure AI Search
service), and `provision-flow.py` always creates all four flows. Search is billed hourly whether or not it is used.

## 2. Before you start

### 2.1 People and permissions

| Who | Needs | Why |
|---|---|---|
| Azure deployer | **Owner** on the target subscription, or Contributor plus User Access Administrator | The template deploys at subscription scope (it creates the resource group) and creates role assignments. The same account later reads the Function key from Azure |
| Power Platform administrator | **System Administrator** in the target environment | `provision-dataverse.py` creates tables and publishes customizations |
| Power Platform tenant or environment administrator | Turn on **Enable code apps** for the environment | See 5.1 |
| SharePoint site owner | Edit rights on the intake library | The Intake flow reads it through a connection |
| Reviewers | A role on the `vz_` tables, a license that can run code apps, and the app shared with them | See 5.9 |

The full list of roles, what each needs and when, is in [team and roles](./team-and-roles.md). The Power Platform
administrator role does not give System Administrator inside an environment by itself: add the person to that role through
the environment's membership (team and roles, 4.2).

The deployer account is the one named in `AZURE_ACCOUNT` in `.env`. Most scripts that read or change Azure or Dataverse
(`az.py`, `deploy_analyzer.py`, `provision-flow.py`, `provision-qa.py`, `seed-checklist.py`, `reextract-contracts.py`,
`purge-contract-index.py` and others) check the signed-in account against it and stop on a mismatch.
`provision-dataverse.py`, `verify-solution.py` and `pull-solution.py` do not: they use whichever identity the sign-in chain
in 2.3 yields, so confirm it first (5.3).

### 2.2 Licenses, quota and providers

- **Code apps** need, per user, one of: Power Apps Premium, pay-as-you-go, an App Pass, or auto-claim
  ([Microsoft Learn](https://learn.microsoft.com/power-apps/developer/code-apps/overview#prerequisites)).
- **Cloud flows** use the built-in HTTP action to call the Function. Confirm with your licensing contact that the flow
  owner's license covers it.
- **Model quota** (GlobalStandard, thousands of tokens per minute) must be available in the region:

  | Deployment | Template default | Purpose |
  |---|---|---|
  | `gpt-5.5` | 250 | Checklist extraction |
  | `gpt-5.4` | 100 | Fallback for extraction |
  | `text-embedding-3-large` | 50 | Required by Content Understanding |
  | `gpt-4.1-mini` | 30 | Q&A answers |
  | `text-embedding-3-small` | 30 | Search embeddings |

- **Resource providers** registered on the subscription: `Microsoft.CognitiveServices`, `Microsoft.Web`,
  `Microsoft.Search`, `Microsoft.Storage`, `Microsoft.Insights`, `Microsoft.OperationalInsights`,
  `Microsoft.ManagedIdentity`, and, with private networking (2.4), `Microsoft.Network` and `Microsoft.App`. In the
  demonstration subscription the original deployment needed only the first two registered by hand.

### 2.3 Tools

Versions are the ones the demonstration build used.

| Tool | Version | Install and use |
|---|---|---|
| Python | 3.12 | Everything under `scripts/`, `analyzer/`, `eval/`, `tests/`. `python -m pip install -r requirements-tools.txt` |
| Node.js and npm | Node LTS (built with 26.13, npm 11.12) | The Code App |
| Azure CLI | 2.92 | `az`, with Bicep (`az bicep install`) |
| Azure Developer CLI | 1.37 | `azd` |
| Power Apps CLI | 1.0.2 | `npm install --global @microsoft/power-apps-cli`. Command group `pa` |
| Power Platform CLI | 2.12 | Only `scripts/pull-solution.py` (offline unpack): `dotnet tool install --global Microsoft.PowerApps.CLI.Tool` |
| Azure Functions Core Tools | 4.12 | Optional, for running the Function locally |

Dataverse scripts authenticate through Azure Identity in this order: service principal (`CLIENT_ID` and
`CLIENT_SECRET`, or a certificate, in `.env`), the Dataverse CLI token cache, then your Azure CLI sign-in. Signing in
with `az login --tenant <tenant-id>` is enough. Each CLI keeps its own sign-in, so check them one by one (5.3).

### 2.4 Decisions to make first

| Decision | Default in this repository | What to know |
|---|---|---|
| Azure region | `eastus2` | The only region this was deployed in. Content Understanding, Flex Consumption and every pinned model version and capacity must exist in the region you pick. Validate in 4.3 before provisioning. The template no longer restricts the region |
| Search region | Same as the primary region | New Search capacity was unavailable in East US 2 during the demonstration build, so that service runs in East US. Set `AZURE_SEARCH_LOCATION` if you hit the same limit. A Search service cannot be moved |
| Model processing location | `GlobalStandard` | That SKU may process prompts in any Azure region. If Vizient requires processing inside a data zone, the `sku.name` in `infra/main.bicep` and `infra/qa.bicep` must change, and Content Understanding support for it must be confirmed first. Not tested |
| Real contracts | Q&A indexes synthetic samples only | `ALLOW_REAL_CONTRACTS=true` lets Q&A index and answer questions about real contracts. The check only looks for the text `SYNTHETIC SAMPLE` in the extracted document, so it is not a control on what people upload. It does **not** gate extraction: any PDF that reaches the analysis flow is processed, and its text is stored in Dataverse. Turning it off later does not remove content already indexed (operations runbook 3.4). A contract whose indexing was rejected while it was off stored no document text, so re-extract it after turning the setting on (operations runbook 3.3). No retention policy, legal or security review, or non-admin permission test has been done |
| Storage network access | Public, no exemption tag | The Function's storage account is the resource tenant policy most often locks down: a policy that sets its public network access to Disabled breaks a Flex Consumption app that is not on a virtual network. `ENABLE_PRIVATE_NETWORKING=true` is the durable answer and the recommended one where such a policy exists or your standards require private storage: the app joins a VNet and the account gets a private endpoint with public access off (Appendix E). An exemption tag (`STORAGE_EXEMPTION_TAG_NAME` and `STORAGE_EXEMPTION_TAG_VALUE`, the tag your governance team prescribes, after they approve it) is not durable: in the demonstration tenant the tag was gone about two weeks after deployment, an Azure Policy Modify effect then ran against the account, and its public network access is now Disabled. Repeat the check in 4.6 after any governance change |
| Who owns the flow connections | The account that creates them | Flows run as the connection owner. See the operations runbook before choosing a person's account |

## 3. Configure

### 3.1 Local configuration (`.env`)

Copy [.env.example](../.env.example) to `.env`. It is git-ignored and must never be committed.

| Variable | Used by | Where to get it |
|---|---|---|
| `TENANT_ID` | Every script | Microsoft Entra tenant id |
| `AZURE_SUBSCRIPTION_ID` | Azure scripts | Target subscription |
| `AZURE_ACCOUNT` | Identity guard | Sign-in name of the deployer. The CLIs must be signed in as exactly this account |
| `AZURE_LOCATION` | Azure scripts | The primary region |
| `DATAVERSE_URL` | Dataverse scripts | Environment URL, from the Power Platform admin center |
| `PA_CLI_ENVIRONMENT_ID` | Nobody | No script reads it, and `.env` is not read by `pa`. Keep the environment id (a GUID from the Power Platform admin center) as a note and pass it to `pa` with `--environment-id` |
| `SHAREPOINT_SITE_URL`, `SHAREPOINT_LIBRARY_ID`, `SHAREPOINT_INTAKE_FOLDER` | `provision-flow.py` | See 5.6 |
| `SHAREPOINT_CONNECTION_NAME`, `DATAVERSE_CONNECTION_NAME` | `provision-flow.py` | Names of existing, connected connections you own. See 5.5 |
| `CONTRACT_DATA_MODE` | `run-local.py` | Leave `synthetic`. It only guards the local analysis script |
| `CU_*` | `deploy_analyzer.py` | `CU_ENDPOINT` is **not** read from the azd environment by this script: after `azd provision`, copy the value of `azd env get-value CU_ENDPOINT` into `.env` (4.8). The model settings are usually blank. See the model swap in the operations runbook |
| `SOLUTION_NAME`, `PUBLISHER_*`, `MCP_CLIENT_ID`, `DATAVERSE_PLUGIN_*` | Dataverse tooling | Leave as in `.env.example` |

### 3.2 Azure environment values (azd)

Infrastructure inputs are azd environment values, mapped to Bicep parameters by
[main.parameters.json](../infra/main.parameters.json). A value that is not set is left out of the deployment, so the
template default applies; `azd env unset <name>` returns a value to its default (add `--force` in a script).

The two switches, `ENABLE_PRIVATE_NETWORKING` and `ALLOW_REAL_CONTRACTS`, accept only the lowercase values `true` and
`false`. Anything else, such as `True`, fails the deployment instead of quietly choosing a mode. azd also falls back to a
process environment variable of the same name when its own environment has none, so a stray variable in your shell can
still feed a parameter after `azd env unset`. This should print nothing unless you meant to set them:

```powershell
Get-ChildItem Env: | Where-Object Name -in 'ENABLE_PRIVATE_NETWORKING','ALLOW_REAL_CONTRACTS','AZURE_SEARCH_LOCATION','STORAGE_EXEMPTION_TAG_NAME','STORAGE_EXEMPTION_TAG_VALUE'
```

| azd value | Bicep parameter | Default | Effect |
|---|---|---|---|
| `AZURE_ENV_NAME` | `environmentName` | Set by `azd env new` | Names the resource group `rg-<name>` and seeds the resource names |
| `AZURE_LOCATION` | `location` | Set by `azd env new` | Region of every resource except Search when it is overridden |
| `AZURE_PRINCIPAL_ID` | `principalId` | Set by azd at provision | The deployer. Receives the Content Understanding Contributor role. Q&A is deployed only when it is set, and azd always sets it |
| `AZURE_SEARCH_LOCATION` | `searchLocation` | Primary region | Region of the Search service |
| `ENABLE_PRIVATE_NETWORKING` | `enablePrivateNetworking` | `false` | `true` creates the VNet, private endpoint and private DNS zone in Appendix E and turns public network access off on the Function storage account |
| `STORAGE_EXEMPTION_TAG_NAME`, `STORAGE_EXEMPTION_TAG_VALUE` | `storageExemptionTagName`, `storageExemptionTagValue` | Empty | Tag on the Function storage account and nothing else |
| `ALLOW_REAL_CONTRACTS` | `allowRealContracts` | `false` | Sets the Function setting of the same name |

The model deployments, instance cap and Python version are Bicep parameters (`modelDeployments`,
`maximumInstanceCount`, `pythonVersion`) with no azd value. Change their defaults in [main.bicep](../infra/main.bicep).
The private network's address ranges (`vnetAddressPrefix` `10.20.0.0/24`, `functionSubnetPrefix` `10.20.0.0/27` and
`privateEndpointSubnetPrefix` `10.20.0.32/28`) are Bicep parameters too: change them if the range overlaps a network you
will connect it to.

## 4. Deploy Azure

Run everything from the repository root.

### 4.1 Sign in and verify

```powershell
az login --tenant <tenant-id>
python scripts\az.py account show -o none     # exit 0 and "az: <account>, subscription <name>" when the guard passes
```

`scripts\az.py` adds the subscription to every call and stops when the CLI is signed in as a different account. Use it for
every other `az` command below. Sign azd in with `azd auth login --tenant-id <tenant-id>`, or let it reuse the Azure CLI
sign-in. On a machine that also works with other tenants, keep azd's settings in a project-local folder so the change does
not affect them (the folder is git-ignored):

```powershell
New-Item -ItemType Directory -Force .azd-config | Out-Null
$env:AZD_CONFIG_DIR = (Resolve-Path .azd-config).Path     # set this in every shell that runs azd
azd config set auth.useAzCliAuth true
```

azd takes its account from the Azure CLI's **active subscription**, not from `AZURE_ACCOUNT`. If an azd command fails with
"failed to resolve user ... access to subscription", the CLI's active account is not the deployer. Make the deployer's
subscription the active one yourself (`az account set --subscription <subscription-id>`; `scripts\az.py` refuses to do it
for you), or sign azd in separately with `azd auth login --tenant-id <tenant-id>`.

### 4.2 Register providers

```powershell
python scripts\az.py provider show --namespace Microsoft.Web --query registrationState -o tsv
python scripts\az.py provider register --namespace Microsoft.Web     # repeat for each namespace in 2.2 that is not Registered
```

Registration can take several minutes. Wait until every namespace reports `Registered`.

### 4.3 Check the region and quota

```powershell
python scripts\az.py cognitiveservices model list -l <region> -o json
python scripts\az.py cognitiveservices usage list -l <region> -o table
```

Confirm that each model in 2.2 is listed with the `GlobalStandard` SKU at the version in
[main.bicep](../infra/main.bicep) and [qa.bicep](../infra/qa.bicep), and that quota covers the capacities in 2.2.
Also confirm that Content Understanding and Flex Consumption are available in the region (Microsoft Learn service
availability pages). **Unverified for any region except `eastus2`.**

### 4.4 Create the azd environment

```powershell
azd env new <environment-name> --subscription <subscription-id> --location <region> --no-prompt
# Only when needed (see 2.4):
azd env set AZURE_SEARCH_LOCATION <region>
azd env set ENABLE_PRIVATE_NETWORKING true
azd env set STORAGE_EXEMPTION_TAG_NAME <tag-name>
azd env set STORAGE_EXEMPTION_TAG_VALUE <tag-value>
azd env set ALLOW_REAL_CONTRACTS true
azd provision --preview --no-prompt            # read-only what-if; review it before the next step
```

### 4.5 Provision

```powershell
azd provision --no-prompt
```

The core resources took under two minutes in the demonstration; the Q&A account and Search add more. If Search fails
with `InsufficientResourcesAvailable`, set `AZURE_SEARCH_LOCATION` to another region and run it again.

If the Bicep compile prints warning `BCP036` for `hostingMode` in `infra/qa.bicep`, it is expected: the type library lists
`Default` and the template sets `default`. The reference environment's Search service was deployed with that value, and the
warning does not block provisioning.

### 4.6 Check what policy may have changed

Tenant policy can rewrite properties after creation. Confirm the template's intent held:

```powershell
python scripts\az.py storage account show -g <resource-group> -n <storage-account> --query "{publicNetworkAccess:publicNetworkAccess,allowSharedKeyAccess:allowSharedKeyAccess,allowBlobPublicAccess:allowBlobPublicAccess,minimumTlsVersion:minimumTlsVersion,defaultAction:networkRuleSet.defaultAction,bypass:networkRuleSet.bypass}"
python scripts\az.py cognitiveservices account show -g <resource-group> -n <foundry-account> --query properties.disableLocalAuth
```

| Design | `publicNetworkAccess` | `defaultAction` | `bypass` |
|---|---|---|---|
| Default (public) | `Enabled` | `Allow` | `AzureServices` |
| `ENABLE_PRIVATE_NETWORKING=true` | `Disabled` | `Deny` | `None` |

In both designs expect `allowSharedKeyAccess` and `allowBlobPublicAccess` `false`, `minimumTlsVersion` `TLS1_2`, and
`disableLocalAuth` `true`. If `publicNetworkAccess` is `Disabled` and you did not enable private networking, the Function
host cannot reach its storage: see "Storage network access" in 2.4 and Appendix E. With private networking, also confirm the
endpoint connection is approved:

```powershell
python scripts\az.py storage account show -g <resource-group> -n <storage-account> --query "privateEndpointConnections[].{name:name, state:privateLinkServiceConnectionState.status}" -o table
```

Repeat these checks after any governance change, because policy can revert a setting long after deployment. Resource names
are in appendix A.

### 4.7 Deploy the Function

```powershell
azd deploy --no-prompt                          # about 25 seconds in the demonstration
Invoke-RestMethod "$(azd env get-value SERVICE_API_URI)/api/health"     # {"status": "ok", "service": "vizient-contract-api"}
```

`/api/health` is the only anonymous route. Every other route needs the function key.

### 4.8 Deploy the analyzer

`deploy_analyzer.py` reads `CU_ENDPOINT` from `.env` or the process environment, not from the azd environment. Copy it
across once:

```powershell
azd env get-value CU_ENDPOINT                   # copy the value into CU_ENDPOINT in .env
```

```powershell
python analyzer\deploy_analyzer.py --status     # a new resource reports no model defaults yet. That is expected
python analyzer\deploy_analyzer.py --apply      # sets the model defaults, then creates or replaces the analyzer
python analyzer\deploy_analyzer.py --status     # expect: ready, current (exit 0)
```

The deployer needs the Content Understanding Contributor role, which the template assigns. A new role assignment can take
a few minutes to apply; retry on a 403.

### 4.9 Publish the Q&A agent and index

```powershell
python scripts\provision-qa.py --validate       # ARM validation, model availability and what-if. Creates nothing
python scripts\provision-qa.py --agent-only     # creates the Search index schema and publishes the Foundry agent
python scripts\provision-qa.py --status         # expect: Foundry agent contract-questions: present
```

`azd provision` already created the Q&A infrastructure and the Function settings that point at it, so `--apply` is not
needed here. **Unverified:** `--agent-only` straight after `azd provision` in a clean subscription. In the demonstration
the infrastructure and the agent were created by `--apply` in a separate step.

## 5. Deploy Power Platform

### 5.1 Prepare the environment

Use a Dataverse-enabled environment. In the Power Platform admin center: **Manage > Environments >** your environment
**> Settings > Product > Features > Power Apps code apps**, turn on **Enable code apps**, and save
([Microsoft Learn](https://learn.microsoft.com/power-platform/admin/settings-features#power-apps-code-apps)).

### 5.2 Create the publisher and the solution

`provision-dataverse.py` stops unless both exist, and nothing in this repository creates them. **Unverified:** no script or
document here records how the demonstration's publisher and solution were created, so create them in the maker portal
(**Solutions > New solution**, with a new publisher) and check them with 5.4.

| Object | Setting |
|---|---|
| Publisher unique name | `VizientContractIntelligence` |
| Publisher prefix | `vz` |
| Publisher choice value prefix | `65120` |
| Solution unique name | `VizientContractPOC` (unmanaged) |

The script checks the prefix pair and that the solution is unmanaged, and refuses to continue otherwise. Do not change
these values: the choice values stored in rows are derived from the prefix.

### 5.3 Sign in and check each tool

```powershell
pa auth login                       # opens a browser
pa auth status                      # the active account is marked with *
dataverse auth who                  # only if you use the Dataverse CLI
python scripts\auth.py --check      # makes a real call to Dataverse; proves it is reachable
```

Set `DATAVERSE_URL` and `TENANT_ID` in `.env` first. `provision-dataverse.py` and `verify-solution.py` do not check
`AZURE_ACCOUNT`, so make sure the identity the sign-in chain will use (2.3) is the one you intend, for example by signing
in with `az login` as that account and having no Dataverse CLI profile for another. `pa auth switch` changes the active
`pa` account; do not use `pa auth logout`, which clears every cached account.

### 5.4 Create the schema and seed the checklist

```powershell
python scripts\provision-dataverse.py --dry-run     # read-only
python scripts\provision-dataverse.py               # idempotent; every create carries the solution header
python scripts\verify-solution.py --fix             # sets your preferred solution, then verifies
python scripts\verify-solution.py                   # exit 0 = everything is in the solution
python scripts\seed-checklist.py --status
python scripts\seed-checklist.py --apply            # 22 rows: 9 contract details, 11 data rights, 2 manual fields
```

`verify-solution.py` fails until the signed-in user's preferred solution is `VizientContractPOC`, which is why the first run
uses `--fix`; that setting makes objects created in the portal land in the solution. It is per user: repeat it for every
account that builds here. It also fails if the solution holds anything this project does not declare, because an export
would carry that into the next environment; `--fix` never removes an object, so take such an object out of the solution
in the maker portal (**Remove > Remove from this solution**; it stays in the environment). In an environment shared with
other work, the same account may have made objects that sit outside the solution on purpose: list them as `TYPE:ID` pairs in
`SOLUTION_GUARD_IGNORE` in `.env` (see `.env.example`), and the check skips them and says so. Right after provisioning the
Dataverse metadata API can briefly answer incompletely. If
`verify-solution.py` reports an object as "not listed by the metadata API", wait a few minutes and run it again, and seed
only after a clean run.

### 5.5 Create the connections

The flows need a connected **SharePoint** connection and a connected **Microsoft Dataverse** connection, owned by the
account that runs the scripts. Create them in the maker portal (**Power Automate > Connections > New connection**), or
with `pa connection create --connector <connector-id>`, then list them:

```powershell
pa connection list
```

Put the two connection names in `.env` (`SHAREPOINT_CONNECTION_NAME`, `DATAVERSE_CONNECTION_NAME`). **Unverified** from a
clean start.

### 5.6 Prepare the SharePoint intake location

Create a folder in a document library (the default `.env.example` value is `/Shared Documents/Contract Intake`). Set
`SHAREPOINT_SITE_URL` to the site address, `SHAREPOINT_INTAKE_FOLDER` to the folder path, and `SHAREPOINT_LIBRARY_ID` to
the library's GUID (it appears as `List=%7B<guid>%7D` in the address of the library's settings page).

### 5.7 Create the flows

```powershell
python scripts\provision-flow.py                # offline: builds the four flows and checks them against dataverse\schema.json
python scripts\provision-flow.py --status       # read-only comparison with Dataverse
python scripts\provision-flow.py --apply        # creates the rows inside the solution and turns the flows on
python scripts\provision-flow.py --status       # expect: flows: 4 of 4 current and on (exit 0)
```

`--apply` reads the Function address from the azd environment and the Function key from Azure, and stores them as two
text environment variables in the solution. Anyone who can read those variables can read the key, and tenant policy in
the demonstration kept Key Vault unreachable from Power Platform. Restrict who can read environment variable values in the
environment. Never edit the flows in the designer: change [flowlib.py](../scripts/flowlib.py) and run `--status` and
`--apply` again. The flows analyze PDFs up to 4 MB (a Dataverse connector limit); a larger file ends as Failed with a
message that says so.

### 5.8 Build and publish the Code App

```powershell
Push-Location contract-review
npm ci
pa app init --environment-id <environment-id> --display-name "Vizient Contract Review"
pa app add data-source --connector dataverse --table vz_contract
pa app add data-source --connector dataverse --table vz_finding
pa app add data-source --connector dataverse --table vz_checklistitem
pa app add data-source --connector dataverse --table vz_contractquestion
pa app add data-source --connector dataverse --table systemuser
npx tsc -b
npm run lint
npm test
npm run build                                     # run each gate on its own and stop at the first failure
pa solution list                                  # copy the id of VizientContractPOC
pa app push --solution-id <solution-id>           # never push without the solution id
Pop-Location
```

`pa app init` writes `power.config.json`, which holds the environment and the app's id and is git-ignored; it stops if one already
exists in the folder. The data-source commands write the rest of `.power/` (also git-ignored) and the typed Dataverse services in
`src/generated/`, which are committed. One file under `.power/` is committed on purpose:
`.power/schemas/appschemas/dataSourcesInfo.ts`. It lists the data sources the app reads (the four project tables and the system user table) and holds no identifiers, so `npx tsc -b` and `npm run build`
pass on a fresh clone before any of these commands has run. After any schema change run `pa app refresh data-source`. The unpacked folder
`dataverse/solution/` leaves out the app package (it is git-ignored), so it
cannot be packed back into an importable solution, and `pa app push` deploys the app. The solution file in 5.10 does contain the
app package. Microsoft Learn says a code app that is in a solution moves with an exported and imported solution
([Microsoft Learn](https://learn.microsoft.com/power-apps/developer/code-apps/how-to/alm)); that route was not tested here.
**Unverified:** `pa app init` and the data-source commands against a fresh environment from this existing source tree. The Power Apps CLI
(1.0.2) is written to merge into an existing `dataSourcesInfo.ts` rather than refuse, but that was read from its code and not run.

### 5.9 Give people access

The solution defines no security role of its own yet. Each reviewer needs a role with access to `vz_contract`,
`vz_finding` and `vz_checklistitem`, and **own-row** access to `vz_contractquestion` (the app creates a question row per
question), plus a license from 2.2. Share the app. `pa app share` acts on the code app in the current folder, so run it from
the app directory:

```powershell
Push-Location contract-review
pa app share --principal <email-or-object-id>
Pop-Location
```

Non-admin access has not been tested. Test with a user who is not a system administrator before wider use.

### 5.10 Alternative: import the solution file

`dataverse/VizientContractPOC_unmanaged.zip` is an export of the demonstration's unmanaged solution, written by
`scripts/pull-solution.py`. It carries the publisher, the four tables with their columns, keys, relationships, forms and
views, the global choice, the four flows, the two connection references, the five environment variable definitions and the
Code App with its package. It carries **no environment variable values**: the Function key and the tenant addresses were
removed before it was committed. The connection references carry no connection, so the import asks for one. It does not
carry the 22 checklist rows, which are data (5.4 seeds them).

It was exported on 18 November 2026 from the demonstration environment, after `verify-solution.py` showed that the solution
holds exactly what this project declares. The export lists one missing dependency: the built-in user table (`systemuser`),
which the source environment supplies through a Microsoft-installed solution (`OmnichannelTelephony`). Every Dataverse
environment has that table, so it should not stop an import, but that was not tried. The file unpacks with
`pac solution unpack` into exactly the folder `dataverse/solution/`.

**Unverified.** This file has not been imported into a second environment. Do the first import in a development environment.

Use it instead of 5.2, 5.4, 5.7 and 5.8, after Azure is deployed (section 4), because the environment variables need the
Function's address and key:

1. Complete 5.1 (enable code apps) and 5.5 (create the SharePoint and Dataverse connections) first.
2. In the maker portal, **Solutions > Import solution**, and choose the file. Bind each connection reference to the connection
   you created, and supply the five environment variable values: the Function address (`vz_FunctionBaseUrl`), the Function key
   (`vz_FunctionKey`, from `azd env get-value` or the portal), and the SharePoint site address, library id and intake folder
   (`vz_SharePointSiteUrl`, `vz_SharePointLibraryId`, `vz_IntakeFolderPath`). Restrict who can read those values (5.7).
3. Seed the checklist rows: `python scripts\seed-checklist.py --apply`. Set `DATAVERSE_URL` and `TENANT_ID` in `.env` first (3.1).
4. Turn the four flows on, then check them: `python scripts\provision-flow.py --status` should report 4 of 4 current and on. If
   it reports a difference, the imported definition differs from `scripts\flowlib.py`: run `--apply` so the script's version
   wins, because the script is the source of truth.
5. Share the app and give reviewers a role (5.9). Run the checks in section 6.

Things to settle on the first import, because they have not been tried:

- Whether the imported flows start on, or need turning on once their connection references are bound.
- Whether `python scripts\verify-solution.py` passes against an imported solution. It was written against one built by the
  scripts; the first run will say.
- How the imported app and `pa app init` interact. `pa app init` registers a new app, so pushing from `contract-review/`
  after an import may add a second app to the solution rather than update the imported one. Run `pa app list` and decide
  which to keep before you push.
- The app in the file is the build that existed when the file was exported. Rebuild and push it (5.8) if you change the source.

To refresh the file after a change in the source environment, run `python scripts\pull-solution.py`: it rewrites both the
unpacked folder and the zip.

## 6. Verify end to end

Run these in order. Every one must pass before you call the deployment done.

| # | Check | Expected |
|---|---|---|
| 1 | `python scripts\verify-solution.py` | Exit 0 |
| 2 | `python scripts\provision-flow.py --status` | Exit 0, `flows: 4 of 4 current and on` |
| 3 | `python analyzer\deploy_analyzer.py --status` | Exit 0, ready and current |
| 4 | `python scripts\provision-qa.py --status` | The agent `contract-questions` is present |
| 5 | `python scripts\test-contract-qa.py --ingest-fixture --question "How many years is this contract for?" --expect-answer-text "seven years"` | Passes: the script creates a synthetic record, waits for extraction, review readiness and Search readiness, and checks a cited answer |
| 6 | `python eval\generate_contracts.py`, then drop `samples\bluepine-sow.pdf` into the SharePoint intake folder | The contract appears in the app and reaches Ready for Review with 20 findings. The project target is three minutes or less from drop to ready |
| 7 | In the app, open that contract, click a finding | The PDF jumps to the page and marks the passage. Accept, correct and reject each save. **Approve** locks the findings |
| 8 | `python -m pytest tests -q` and, in `contract-review`, `npm test` | All pass |

Check 6 exercises the SharePoint trigger, which check 5 skips. For an accuracy baseline on the synthetic set, run
`python scripts\run-local.py` on the generated PDFs and then `python eval\score.py`; the demonstration scored 97% on data
rights and 100% on contract details.

Use synthetic contracts only until the open items in the operations runbook (retention, legal and security review,
least-privilege roles) are closed.

## 7. Tear down

**`azd down` deletes the whole resource group, including anything added to it by hand** (for example an alert or an action
group created in the portal). It acts on the **selected azd environment**, which is not necessarily the subscription and
group in your `.env`. Confirm they are the same, then inventory the group and keep what you need:

```powershell
azd env list                                                   # the selected environment is marked as default
azd env get-values | Select-String 'AZURE_SUBSCRIPTION_ID|AZURE_RESOURCE_GROUP'   # must match .env and the group below
python scripts\az.py resource list -g <resource-group> --query "[].{name:name, type:type}" -o table
azd down --purge                                               # asks for confirmation; read the group it names
```

Use `--force` only in automation, and only after the checks above.

`--purge` matters because Foundry accounts soft-delete and keep their names. If a redeployment is blocked by a
soft-deleted account, find and purge it:

```powershell
python scripts\az.py cognitiveservices account list-deleted
python scripts\az.py cognitiveservices account purge --location <region> --resource-group <resource-group> --name <account>
```

Then delete the solution (or the environment) in Power Platform, the Code App, the two connections and the SharePoint
folder. Search chunks and Dataverse rows hold contract text, so delete them deliberately when the project ends.

## Appendix A: Azure resources

`<token>` is a 13-character hash of the subscription, environment name and region. `<qa-token>` is a hash of the
resource group id.

| Resource | Name | Notes |
|---|---|---|
| Resource group | `rg-<environment-name>` | |
| User-assigned managed identity | `id-api-<token>` | The Function runs as this identity |
| App Service plan | `plan-<token>` | Flex Consumption (FC1), Linux |
| Function app | `func-api-<token>` | Python 3.12, 2,048 MB instances, at most 10, no always-ready instances |
| Storage account | `st<token>` | Standard LRS. Shared-key and anonymous blob access off, TLS 1.2. Holds the code package and host state only |
| Log Analytics workspace | `log-<token>` | 30-day retention |
| Application Insights | `appi-<token>` | Workspace-based. Local auth off, so telemetry uses Entra |
| Foundry account (extraction) | `aif-vz-<token>` | AIServices S0, local auth off, public network on. Hosts Content Understanding and the three extraction models |
| Foundry account (Q&A) | `aif-qa-<qa-token>` | Project `contract-questions`, models `gpt-4.1-mini` and `text-embedding-3-small` |
| Azure AI Search | `srch-contract-<qa-token>` | Basic, one replica, one partition, Entra auth only. Index `contract-chunks` |

## Appendix B: Role assignments

Every role is scoped to a single resource, never the resource group or subscription.

| Principal | Role | Scope |
|---|---|---|
| Function identity | Cognitive Services Content Understanding Reader | Extraction Foundry account |
| Function identity | Storage Blob Data Owner | Function storage |
| Function identity | Monitoring Metrics Publisher | Application Insights |
| Function identity | Search Index Data Contributor | Search |
| Function identity | Cognitive Services OpenAI User and Foundry User (formerly Azure AI User) | Q&A Foundry account |
| Deployer | Cognitive Services Content Understanding Contributor | Extraction Foundry account |
| Deployer | Search Index Data Contributor and Search Service Contributor | Search |
| Deployer | Cognitive Services OpenAI User and Foundry User (formerly Azure AI User) | Q&A Foundry account |

The template assigns the deployer's roles to one user, the account whose object id is `AZURE_PRINCIPAL_ID` (the one that ran
`azd provision`). Any other developer who runs `deploy_analyzer.py` or `provision-qa.py`, or `run-local.py` directly against
Content Understanding, needs the same roles, and you must assign them yourself. Assigning them to a group is **Unverified**.
## Appendix C: Function app settings

Set by the template. Change them in [main.bicep](../infra/main.bicep), not by hand, or the next provision reverts them.

| Setting | Value |
|---|---|
| `CU_ENDPOINT`, `CU_ANALYZER_ID`, `CU_API_VERSION` | The Foundry endpoint, `vizientContractChecklist`, `2025-11-01` |
| `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_QA_AGENT`, `FOUNDRY_QA_MODEL` | The Q&A project, `contract-questions`, `gpt-4.1-mini` |
| `AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_INDEX` | The Search service, `contract-chunks` |
| `EMBEDDING_ENDPOINT`, `EMBEDDING_MODEL` | The Q&A account, `text-embedding-3-small` |
| `ALLOW_REAL_CONTRACTS` | `true` or `false` (see 2.4) |
| `AZURE_CLIENT_ID` | The managed identity's client id |
| `HIGH_CONF` | Optional. The minimum Content Understanding confidence for a finding to be marked Found. Below it, or without a source region, the finding is Unclear and a reviewer decides. A number above 0 and up to 1; default 0.80 |
| `AzureWebJobsStorage__*`, `APPLICATIONINSIGHTS_*` | Identity-based storage and telemetry. Do not change |

## Appendix D: Estimated cost

List-price estimates from the project's deployment record (October 2026), not an invoice. Check them against your own
agreement.

| Item | Estimate |
|---|---|
| Extraction of one 29-page contract with `gpt-5.5` | About USD 0.57 to 0.81 (Content Understanding, contextualization and model tokens). About 0.37 to 0.49 with `gpt-5.4` |
| Azure AI Search, Basic, one unit | About USD 74 a month (USD 0.101 an hour) while it exists, even idle |
| Function (Flex, no always-ready instances), storage, Log Analytics, Application Insights | Pennies at pilot volume |
| Q&A embeddings and answers | Usage-based tokens |
| Defender for Cloud plans | Charged by the subscription's own plans, not by this template |
| Private networking (Appendix E) | About USD 7.30 a month for the private endpoint and USD 0.50 for the private DNS zone at list price, plus data processed |

The app's **Time and cost** page shows measured per-contract time and cost for three synthetic samples. For other volumes (a
backfill, a steady stream, a reviewer pool) use the [capacity and sizing workbook](capacity-sizing-workbook.xlsx).

## Appendix E: Private networking (`ENABLE_PRIVATE_NETWORKING`)

With `ENABLE_PRIVATE_NETWORKING=true`, [network.bicep](../infra/app/network.bicep) is deployed, the Function app joins its
VNet, and the Function storage account gets a private endpoint and has public network access turned off. Use it where a
tenant policy disables public network access on storage accounts, or where your standards require private storage. All
resources carry the template's tags.

| Component | Configuration |
|---|---|
| Virtual network | `vnet-<token>`, address space `10.20.0.0/24` (`vnetAddressPrefix`) |
| Function subnet | `snet-func`, `10.20.0.0/27`, delegated to `Microsoft.App/environments`, with a network security group that has no custom rules. The Function app is VNet-integrated into it |
| Private endpoint subnet | `snet-private-endpoints`, `10.20.0.32/28`, with a network security group that has no custom rules |
| Private endpoint | `pe-st<token>-blob`, for the storage account's `blob` sub-resource. The app has HTTP triggers and uses blob storage only, so there is no queue or table endpoint |
| Private DNS | Zone `privatelink.blob.core.windows.net`, linked to the VNet without auto-registration. A zone group on the endpoint registers its address |
| Storage account | Public network access Disabled, default network action Deny, bypass None |

It isolates the Function's storage and nothing else. In the demonstration environment the Function app keeps its public
inbound endpoint, and the Foundry accounts and Search stay on public endpoints that accept Entra tokens only. Flex
Consumption routes all of the app's outbound traffic through the integrated subnet ([Microsoft
Learn](https://learn.microsoft.com/azure/azure-functions/functions-networking-options)), so the network security group and any
route table on `snet-func` apply to its calls to Foundry and Search; the group created here has no custom rules. The subnet
cannot be shared with a Container Apps environment. The option needs the `Microsoft.Network` and `Microsoft.App` resource
providers (2.2).

**How it was checked, and what was not.** The option reproduces the demonstration environment, which was first deployed
with the exemption tag and then rebuilt by hand on 6 November 2026, after the tag was gone and a policy Modify effect had
disabled public access. A what-if of these templates with the option on, run against that environment, reports no
difference in any network resource, in the storage account's network settings or in the Function app's VNet integration.
The one network entry that is not "no change" is the private endpoint's DNS zone group, which differs only by
server-populated fields (`etag`, `id`, `provisioningState`, `type`). The what-if also still lists differences on other
resources, the same ones it listed before this option existed: read-only properties that the templates do not set. **The
option has not been deployed from scratch.** Treat the first deployment into a new subscription as the test, and read
`azd provision --preview --no-prompt` first.

**Changing an existing environment.** Switching one from public to private updates the storage account first and the Function
app last, so the app has no route to its storage between the two. If a run fails partway, the host stays offline until you
fix the cause and run it again (the deployment can be repeated safely). Do it in a maintenance window, with a preview in
hand. Setting the value back to `false` only helps where policy still allows public network access on the account.

**Defender for Storage.** If Microsoft Defender for Storage malware scanning is on, Defender adds a `StorageDataScanner`
entry to the account's network rules (**Networking > Resource instances**) so that scanning can reach a restricted account
([Microsoft Learn](https://learn.microsoft.com/azure/defender-for-cloud/introduction-malware-scanning#access-and-data-privacy)).
The template does not declare that entry and the what-if does not report it as a change, but a deployment that replaces
the account's network rules could remove it. After `azd provision`, check that the entry is still there. If scanning has
stopped, Defender's guidance is to disable and re-enable malware scanning.

**Checks.** The commands in 4.6, then `GET <function>/api/health`. A host that cannot reach its storage logs
`Process reporting unhealthy` (operations runbook, section 5).
