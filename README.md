# Vizient Contract Intelligence

POC Lite: a contract dropped into SharePoint is read by Azure Content Understanding against a
20-item checklist (9 contract details and 11 data rights). The answers land in Dataverse, and a
Power Apps Code App shows each answer beside its source evidence in the PDF so a reviewer can
accept, correct or reject it.

The requirements are in `vizient-contract-poc-lite-plan.md` (a redacted copy of the brief). Start with the
[handoff and decision guide](docs/handoff-guide.docx): what this is, where it stands and the decisions to make.

| To | Read |
|---|---|
| Understand the design | [Architecture](docs/architecture.md), with its [diagram](docs/architecture/contract-intelligence-architecture.png) |
| See a contract move through the system, in 3D | [Interactive 3D architecture](docs/architecture-3d.html): one web page that opens in any browser with no sign-in or network. Download the file and open it (GitHub shows its source, not the page). It is not part of the Power Platform solution |
| Deploy Azure, the Power Platform solution, the flows and the app | [Deployment runbook](docs/deployment-runbook.md). The Power Platform side can also be imported from [the solution file](dataverse/VizientContractPOC_unmanaged.zip) (deployment runbook 5.10) |
| Run it day to day, and fix it | [Operations runbook](docs/operations-runbook.md) |
| Staff it | [Team and roles](docs/team-and-roles.md): who to involve, the access each person needs, and when |
| Size a backfill and a steady stream | [Capacity and sizing workbook](docs/capacity-sizing-workbook.xlsx) |
| See every table, column and choice | [Dataverse schema notes](dataverse/schema.md) and `dataverse/schema.json` |
| Change the code | This file, and the README in [contract-review/](contract-review/README.md) for the app |

## How it works

```text
SharePoint "Contract Intake" folder
  -> flow "Vizient Contract Intake": creates the contract row, attaches the PDF, queues it as Extracting
  -> flow "Vizient Contract Analysis": calls the Function, writes 20 findings, sets Ready for Review
     (or Failed, with the reason)
  -> Azure Function (Flex Consumption, Python 3.12)
     POST /api/contracts/analyze, then GET /api/contracts/analyze/{operationId} until it returns 200
  -> Content Understanding analyzer "vizientContractChecklist" (gpt-5.5, GA API 2025-11-01)

Dataverse, solution VizientContractPOC: vz_contract, vz_finding, vz_checklistitem
Code App "Vizient Contract Review" (contract-review/): contract list, findings beside the PDF,
click-to-highlight evidence, accept / correct / reject, approve; plus a "How it works" page (an
interactive 3D walk through this pipeline) and a "Time and cost" page (how long it takes and what it costs to
process one contract)
```

| Path | What it holds |
|------|---------------|
| `checklist/checklist.json` | The checklist: single source of truth (20 extracted items plus 2 manual fields). `function/checklist.json` is the copy the Function ships; a test fails when they differ |
| `analyzer/` | Builds the Content Understanding analyzer from the checklist and deploys it |
| `function/` | The async analysis API (`routes.py`), the Content Understanding client and the mapping to findings |
| `infra/`, `azure.yaml` | Bicep and azd for the Azure side |
| `dataverse/` | `schema.json` (source of truth), `schema.md`, `solution/` (the unpacked solution, for review in Git) and `VizientContractPOC_unmanaged.zip` (the same solution as an importable file, with the Code App package) |
| `docs/` | The guide, architecture (with its diagram and the interactive 3D page), the two runbooks, team and roles, and the sizing workbook |
| `scripts/` | Provisioning, seeding, flows, solution guard, local analysis and the leak scan |
| `eval/` | Synthetic contract generator, gold labels and the scorer |
| `tests/` | Offline pytest suites for the Python code |
| `contract-review/` | The Code App (React, Vite, strict TypeScript, Fluent UI v9, pdf.js). See its own README |
| `design/vizient-theme/` | The vizient.com theme (CSS and a preview page) |

## Data handling

**Synthetic contracts only in this repository.** The supplied signed PDFs sit in the project
root, are excluded from Git (`*.pdf`), and are never read by the tooling, committed or used as
test data. Fixtures, gold labels and documentation use made-up contracts and numbers (`eval/`).
The brief is committed in a redacted form; the original stays local as
`vizient-contract-poc-lite-plan.original.md` (ignored). A document a person drops into the
SharePoint intake folder goes through the same pipeline as any upload, so choose on purpose
which documents appear in a demo.

`python scripts/leak-scan.py` checks what Git would commit against the project's identifiers
(environment, tenant, subscription, hosts and the sign-in account) and must be clean before
every commit. The checklist contains **20** extracted items, not 18; two additional reviewer
fields are manual.

## Local configuration

Copy `.env.example` to `.env` and populate the confirmed environment, tenant and
subscription identifiers. Do not commit `.env`. Authentication is the user's own
interactive CLI sign-in; no passwords or tokens belong in this project.

Azure CLI, PAC, Dataverse CLI, the Power Apps CLI (`pa`) and the Power Automate tooling each keep
a separate sign-in. Use the tenant admin account (`AZURE_ACCOUNT` in `.env`) on all of them, never a
corporate one, and verify each account and environment, not just the active subscription.
Current Code Apps documentation uses `pa app`, rather than the brief's legacy `pac code` commands.

- `python scripts/az.py ...` runs the Azure CLI and refuses to run as the wrong account
  (`python scripts/az.py account show -o none` exits non-zero on a mismatch). Pass an explicit
  subscription to every other `az` call.
- Run azd with `AZD_CONFIG_DIR` set to the git-ignored `.azd-config` folder (its config makes azd reuse
  the Azure CLI sign-in). Never run `azd auth login`, `azd config set` or `az account set`: the global
  defaults point at other subscriptions.
- `pa auth status` lists the cached accounts and marks the active one with `*`. Switch with
  `pa auth switch`. Never run `pa auth logout`: it clears every cached account.
- Dataverse and Content Understanding scripts need a silent credential. In an unattended shell set `CI=1`
  so a missing credential fails fast instead of waiting for a device-code prompt.
- The Azure MCP server and the FlowAgent tool in this workspace are signed in to other tenants and
  cannot see this environment. Use the scripts here instead.

PowerShell examples, run from the project root:

```powershell
dataverse auth who
pac org who
pa auth status
python .\scripts\auth.py --check
```

The authentication helpers in `scripts` come from the installed Microsoft
Dataverse-skills plugin (version 1.16.1). Python setup dependencies are declared in
`requirements-tools.txt`; restore them only if missing:

```powershell
python -m pip install -r .\requirements-tools.txt
```

## Dataverse solution

Every Power Platform object lives in the unmanaged solution `VizientContractPOC`.
`dataverse/schema.json` is the schema source of truth; `dataverse/schema.md` explains it.
The provisioner sends the solution header on every create, and the verifier proves nothing
sits outside the solution and nothing foreign sits inside it (declared schema, a real solution export, a sweep for flows,
apps, connection references, environment variables and other strays, and a check that every component is one this project
declares).

```powershell
python .\scripts\provision-dataverse.py --dry-run   # plan only, read-only
python .\scripts\provision-dataverse.py             # create inside the solution (idempotent)
python .\scripts\verify-solution.py                 # exit 0 = everything is in the solution, and nothing else is
python .\scripts\verify-solution.py --fix           # repair strays and the preferred solution (never removes an object)
python .\scripts\verify-solution.py --self-test     # prove the guard works (creates and deletes one probe)
python .\scripts\pull-solution.py                   # refresh dataverse\solution\ and dataverse\VizientContractPOC_unmanaged.zip
python -m pytest tests -q                           # offline tests of the guard (no environment needed)
```

Right after provisioning, the Dataverse metadata API can briefly lag behind the export. The verifier
re-reads through fresh sessions before it reports an object missing, and when the export holds
everything it says so; re-run in a few minutes. Wait for a clean run before seeding data.

## Azure

The resource group, Foundry account (the model deployments Content Understanding uses), Function app,
managed identity and monitoring are Bicep in `infra/`, deployed with azd (the demonstration environment is in East US 2).
The cost estimates are in appendix D of the [deployment runbook](docs/deployment-runbook.md). The region, the Search region,
private networking, an optional storage exemption tag and the real-contract switch are azd environment values; see section
3.2 of the same runbook.

```powershell
$env:AZD_CONFIG_DIR = (Resolve-Path .azd-config).Path; $env:NO_COLOR = '1'
azd provision --no-prompt                       # infrastructure
azd deploy --no-prompt                          # publish function\ (about 25 seconds)
python .\analyzer\deploy_analyzer.py --status   # read-only: are the model defaults set, is the analyzer current?
python .\analyzer\deploy_analyzer.py --apply    # set the model defaults, then create or replace the analyzer
```

- Entra tokens only. Policy forces key authentication off on the Foundry account, so the Function reaches
  Content Understanding with its user-assigned managed identity and a least-privilege role.
- A new Foundry resource answers `DefaultsNotSet` until its model defaults are patched; `--apply` does that
  first, which lets the analyzer use the model aliases (swap `gpt-5.5` for another model without redeploying it).
- To change the checklist, edit `checklist/checklist.json`, run `python analyzer/build_schema.py --write` and
  `Copy-Item checklist\checklist.json function\checklist.json`, then `--apply` and `azd deploy --no-prompt`.
  Tests fail while either copy is stale.
- Teardown: `azd down --force --purge` (the purge matters because Foundry accounts soft-delete).

## Analyze a contract locally

```powershell
python .\eval\generate_contracts.py                                   # synthetic PDFs into samples\ (git-ignored)
python .\scripts\run-local.py .\samples\bluepine-sow.pdf              # Content Understanding directly
python .\scripts\run-local.py .\samples\bluepine-sow.pdf --via function   # through the deployed API
python .\scripts\run-local.py --result .\samples\results\bluepine-sow.operation.json   # replay a saved result offline
```

Direct and function runs need the Azure CLI signed in as the admin account. Results are saved to
`samples\results\<name>.json`. With `CONTRACT_DATA_MODE=synthetic` (the default), only PDFs carrying the
`SYNTHETIC SAMPLE` marker are sent to the service, so a real contract cannot go out through a mistyped path.

## Power Automate flows

Two cloud flows live in the solution. `scripts/flowlib.py` builds them and `scripts/provision-flow.py` creates
them through the Dataverse `workflows` API, so the definitions are reviewable and repeatable.

| Flow | Starts when | What it does |
|------|-------------|--------------|
| Vizient Contract Intake | A file arrives in the SharePoint intake folder | Creates the `vz_contract` row, copies the PDF into its file column, sets the status to Extracting |
| Vizient Contract Analysis | A contract's status becomes Extracting | Sends the PDF to the Function, polls until done, writes the findings, the found count and the completeness, and sets Ready for Review. On any error it sets Failed with the reason |

Extracting is also a retry queue: set a Failed contract back to Extracting and the analysis flow runs again.

```powershell
python .\scripts\provision-flow.py            # offline: build both flows and check them against dataverse\schema.json
python .\scripts\provision-flow.py --status   # read-only: compare Dataverse with what --apply would write
python .\scripts\provision-flow.py --apply    # create or update the rows, then turn both flows on
```

It needs the `SHAREPOINT_*` values and the two connection names in `.env` (`pa connection list` shows the
names). Environment variables, connection references and both flows are all created inside the solution.
A flow is rewritten only when the `[definition ...]` tag in its description changes, so reruns are safe.

- **Size limit:** the Dataverse connector reads file columns in 4 MiB ranges, so the flows analyze PDFs up to
  4 MB (the Function itself accepts 32 MiB). A larger file ends as Failed with a message that says so.
- **Function key:** the analysis flow calls the Function over HTTP with its function key. The provisioner reads
  the key from Azure into memory and stores it as the value of a text environment variable in the solution, so
  anyone who can read that variable can read the key. A Key Vault-backed secret variable would be better, but
  tenant policy keeps Key Vault unreachable from Power Platform. `pull-solution.py` strips environment variable
  values from the Git export. Rotate the key after the demo, then run `provision-flow.py --apply` again to store
  the new one.

## Demo data

```powershell
python .\scripts\seed-demo.py            # offline: check the saved results and say what would be written
python .\scripts\seed-demo.py --status   # read-only: is the demo data in place?
python .\scripts\seed-demo.py --apply    # write the contracts that are missing; one that exists is not changed
python .\scripts\seed-demo.py --reset    # delete the demo contracts and their findings, then write them again
```

Seeds three synthetic contracts (60 findings) from their saved analysis results, with no Content
Understanding call. `--reset` discards any review work on those contracts, so confirm before running it.

## Code App

`contract-review/` is a Power Apps Code App: React, Vite, strict TypeScript, Fluent UI v9 and pdf.js, styled with
the vizient.com theme. Its README covers the layout, mock mode and the review behavior.

```powershell
cd contract-review
npm ci
npm run dev:mock    # no Power Platform needed: serves the synthetic PDFs and saved results from ..\samples
npm run lint; npm test; npm run build
pa app push --solution-id <id of VizientContractPOC>   # dist\ must be built first; never push without the solution id
pa app share --principal <email>                       # give a person the right to open the app
```

Two pages explain the project instead of reviewing a contract. **How it works** is an animated 3D diagram of the
pipeline above, with a guided "Follow a contract" tour (a clock under the diagram shows how far into the processing
each step falls) and the explanation underneath. **Time and cost** measures the pipeline itself: how long one contract
takes from the PDF landing in SharePoint to Ready for Review (a person's review is not counted), and what one contract
costs to process (the pages read and the model tokens, at public list prices). The 3D scene is Three.js, loaded only when
that page opens, and it falls back to a flat diagram when WebGL is unavailable. Every figure is a dated snapshot;
`contract-review/README.md` explains how to refresh each one.

## Ask this contract (Foundry)

Open an indexed contract in the existing review app and select **Ask this contract**. The additive drawer searches
only that record's full extracted text, not just its checklist findings, and never follows parent links.
**View page** opens verified quote evidence in the existing PDF viewer; reopening the drawer preserves the
conversation while you stay on that record. Navigating away or re-extracting resets it. Review behavior is unchanged.
This POC accepts real and synthetic contracts while the Function setting `ALLOW_REAL_CONTRACTS=true` is on (see below).

Ingestion preserves complete page-grounded text in `vz_documenttext`, separately from the deliberately reduced
`vz_rawresult` debugging snapshot. The analysis result supplies an explicit `indexing` handoff. Missing page text
or a document that is not marked synthetic (only while `ALLOW_REAL_CONTRACTS` is off) fails only that handoff;
checklist review continues unchanged.
The separate solution-owned **Vizient Contract Indexing** flow indexes page-local overlapping chunks in a shared
Azure AI Search index. It records `vz_indexstatus`, `vz_indexversion` and `vz_indexerror` independently of review status.
Indexing uses bounded embedding/upload batches and short polling requests, checks every upload result, and verifies
manifest/chunk visibility before declaring Ready. Requeue `vz_indexstatus` to Queued to retry indexing without
discarding reviewer work. Records ingested before full-text indexing have no document text: use
`reextract-contracts.py` (below), which discards their findings; nothing backfills automatically.

The app reads `vz_documenttext` with the signed-in user's generated Dataverse service, creates a user-owned
`vz_contractquestion`, and polls for the answer. The solution-owned **Vizient Contract Questions** flow calls the Function
in short polling steps; it never fetches document text as its connection owner. It clears context/history after either
success or failure. The backend performs hybrid keyword/vector retrieval with mandatory contract ID and content-version
prefilters, verifies returned chunks against the authorized document, and passes only retrieved evidence to Foundry's
`contract-questions` prompt agent. Questions never create indexes or upload files. Quotes must match both retrieved
passages and their original source pages. Tables are shown to the model one row per line (cells joined by ` | `), and a
quote matches on its letters and digits across cell and tag boundaries, so a quote may span table markup but cannot
invent words. If the first answer's quotes fail, one automatic retry is made before the user sees an error.
Insufficient retrieval is reported as Not Addressed in the retrieved passages,
not proof of absence throughout the whole document. Answers are plain text, not executed HTML.
The app shows Q&A readiness and disables **Ask this contract** until indexing is Ready.

`infra/qa.bicep` adds a separate Foundry account/project and a GlobalStandard `gpt-4.1-mini` deployment, with managed
identity access for the existing Function, one Basic Azure AI Search unit and `text-embedding-3-small`.
Search uses Entra authentication only; the Function has index-data access and the deployer manages the schema.
The extraction flow gains the indexing handoff; intake and checklist/reviewer semantics are unchanged.
Basic Search is continuously billed: the public retail quote checked on 2026-10-23 was USD 0.101/hour
(about USD 73.73 at 730 hours), plus usage-based embeddings and answer tokens. This single-replica POC is not
an HA deployment. Validate and obtain provisioning approval before `--apply`.
East US 2 rejected new Search capacity during the demonstration build, so its Search service runs in East US while Foundry
and the Function stay in East US 2. The Search region is the azd value `AZURE_SEARCH_LOCATION` (the infra parameter
`searchLocation`, default the primary region) and `provision-qa.py` passes it to `infra/qa.bicep`.
Search versions have no automatic expiry. Old versions are excluded from retrieval but remain stored; deleting
a Dataverse record does not delete its Search chunks. Run `purge-contract-index.py` after deleting contracts or
re-extracting them (see below). Existing Foundry File Search uploads/vector stores are not migrated or deleted.
Real, non-synthetic contracts are indexed in the demonstration environment because its azd value
`ALLOW_REAL_CONTRACTS=true` sets the Function setting of the same name (the infra parameter `allowRealContracts`,
default `false`, which restricts Q&A indexing to synthetic samples and does not gate extraction). Run
`azd env set ALLOW_REAL_CONTRACTS false` and `azd provision --no-prompt` to return to synthetic-only. `provision-qa.py`
never changes it. This was an explicit owner decision (2026-10-23). Real contract text is then stored in the Search
index, so a retention policy, a legal and security review, and non-admin permission testing remain open before wider
use. Give reviewers only own-row access to questions.

```powershell
python .\scripts\provision-qa.py --validate    # ARM validation/model availability only; creates nothing
python .\scripts\provision-qa.py --apply       # after approval: provision Search/embeddings, create index, publish agent
python .\scripts\provision-qa.py --agent-only  # publish instructions/tool schema without reprovisioning
python .\scripts\provision-qa.py --status
python .\scripts\provision-dataverse.py        # new question table/columns/relationship, always inside the solution
python .\scripts\provision-flow.py --status
python .\scripts\provision-flow.py --apply
python .\scripts\test-contract-qa.py --direct --index-fixture # explicit synthetic fixture -> Search -> Foundry
python .\scripts\test-contract-qa.py --index-fixture # queue synthetic indexing flow, then question flow
python .\scripts\test-contract-qa.py --ingest-fixture --question "How many years is this contract for?" --expect-answer-text "seven years"
```

`--ingest-fixture` generates a made-up PDF in memory, creates a new synthetic record, and waits for extraction,
review readiness, Search readiness and a cited answer. It does not reset existing reviews or read uploaded PDFs.
The synthetic record is retained for inspection. `--expect-answer-text` makes an unexpected answer fail the smoke test.

Existing contracts ingested before full-text indexing have no document text. Re-queue them through extraction, and
purge Search chunks that no longer belong to a live contract version:

```powershell
python .\scripts\reextract-contracts.py                     # dry run; lists contracts and findings that would be discarded
python .\scripts\reextract-contracts.py --apply --wait      # DISCARDS findings and review work, then re-extracts and indexes
python .\scripts\reextract-contracts.py --apply --name "file.pdf"   # one contract only
python .\scripts\purge-contract-index.py --status           # what the index holds; changes nothing
python .\scripts\purge-contract-index.py --stale --orphans --apply  # delete old versions and chunks of deleted contracts
python .\scripts\purge-contract-index.py --contract <guid> --apply  # delete every version of one contract
```

Re-extraction keeps the contract row, its PDF, parent link and the manual Owner/Reviewer fields. Both tools print only
names, ids and counts, never document text. `--stale` ignores a contract that is still indexing.

Refresh the generated Code App data services for `vz_contract` and `vz_contractquestion` in the verified environment before building.
Deploy the Function with the project's isolated azd configuration, run all Code App gates before pushing the app
with the solution id, then run `verify-solution.py` and `pull-solution.py`. All target identifiers remain in ignored local
configuration. Existing extraction results, findings and review decisions are never overwritten by Q&A.

## Evaluation

```powershell
python .\eval\generate_contracts.py --check   # exit 1 if the gold labels differ from a fresh render
python .\eval\score.py                        # score samples\results against eval\gold
```

The last scored run (2026-10-22, synthetic set) matched 97% of the data-rights answers and 100% of the contract
details. The one persistent miss is the geographic right on the data use agreement.

`eval/gold` holds only the synthetic sets. `.gitignore` ignores every other file there, so labels for a real contract
(they quote it verbatim) cannot be committed by accident; keep them outside the repository and pass that folder with
`--gold`. To add a synthetic set, add an `!eval/gold/<id>.json` line to `.gitignore`.

## Before every commit

```powershell
python .\scripts\leak-scan.py          # exit 0 = clean
python .\scripts\verify-solution.py    # exit 0 = nothing outside the solution, nothing foreign inside it
python -m pytest tests -q              # offline Python suites
cd contract-review; npm run lint; npm test; npm run build
```

## Known limits

- **Ask this contract:**
  - Each answer comes from the top 12 retrieved passages, so "Not Addressed in the retrieved passages" does not prove
    the contract is silent. Ask Legal when it matters.
  - Answers are checked for verbatim quotes, not for legal correctness; answer accuracy on real contracts has not been
    measured. Quote verification is by letters and digits, so it can match across table cells.
  - Real contract text is stored in Dataverse (`vz_documenttext`) and in Azure AI Search. No retention policy,
    legal/security review or non-admin permission test has been done. Chunks are not deleted with their contract:
    run `purge-contract-index.py`.
  - A contract has one index version at a time; re-extracting replaces it. A document over about 1 MB of page text
    fails indexing only (review is unaffected), and the embedding quota can slow indexing of long contracts.
  - Old Foundry File Search resources from the first build still exist and are unused.
  - The Search index costs about USD 74 a month while it exists, even idle.
- Scanned (image-only) PDFs have not been tried. The synthetic contracts all have a text layer.
- Content Understanding answers can differ slightly between runs of the same contract.
- The project defines no Dataverse security role of its own yet. A person who is not a system administrator
  needs a role with access to the three `vz_` tables, a Power Apps license that covers Dataverse, and the app
  shared with them.
- A SOW or amendment is linked to its parent only when that parent contract is in the repository. A parent
  that was never uploaded leaves the "Parent agreement not linked" chip on.
- The **Time and cost** page does not update itself. Its processing time and cost per contract are dated snapshots, not a
  benchmark: three timed end-to-end runs, and the recorded usage of three synthetic samples priced at public list prices
  (a tenant's own agreement may differ). Both depend on the document. The cost leaves out a person's review, Power
  Platform licenses, storage, monitoring, discounts and tax. For other volumes use the
  [capacity and sizing workbook](docs/capacity-sizing-workbook.xlsx).
