# Working in this repository

How to set up a workstation, check the code, follow the rules this repository enforces, and make the common changes. Deploying is
described in the [deployment runbook](deployment-runbook.md) and running the system day to day in the
[operations runbook](operations-runbook.md).

## Prerequisites

| You need | For |
|---|---|
| Python 3.12 and `python -m pip install -r requirements-dev.txt` | the scripts, the Function and the Python checks |
| Node 24 or later | the Code App in `contract-review/` |
| Azure CLI and the Azure Developer CLI (`azd`) | the Azure side |
| PAC CLI, the Dataverse CLI and the Power Apps CLI (`pa`) | the Power Platform side |

Only the first two are needed to run the checks, and the checks need no sign-in.

## Checks

```powershell
python -m pip install -r requirements-dev.txt
cd contract-review; npm ci; cd ..
python scripts/check.py            # everything below, in order; --python or --app runs half; --dry-run lists the commands
```

`scripts/check.py` runs every step even if an earlier one fails, then prints a summary and exits non-zero if any step failed.

| Step | Command | Where |
|---|---|---|
| Python lint | `ruff check scripts function analyzer eval tests` | repository root |
| Python types | `mypy` | repository root |
| Python tests | `python -m pytest -q --cov` (fails below the coverage floor in `pyproject.toml`) | repository root |
| App lint | `npm run lint` | `contract-review/` |
| App types | `npx tsc -b` | `contract-review/` |
| App tests | `npm test` | `contract-review/` |
| App build | `npm run build` | `contract-review/` |
| 3D page | `npm run build:standalone`, then fail if `docs/architecture-3d.html` changed | `contract-review/` |
| Leak scan | `python scripts/leak-scan.py`, only when a `.env` file exists | repository root |

The same steps run in continuous integration (see the end of this page). Two more checks need your own environment and a signed-in session:
`python scripts/verify-solution.py` (nothing sits outside the solution, nothing foreign inside it) and the live tests of the scripts you changed.

## Sign-ins and local configuration

Copy `.env.example` to `.env` and fill in your environment, tenant and subscription identifiers. Do not commit `.env`: it is git-ignored, and
`python scripts/leak-scan.py` checks what Git would commit against the identifiers in it. Authentication is each person's own interactive CLI
sign-in; no passwords or tokens belong in this repository.

The Azure CLI, PAC, the Dataverse CLI, the Power Apps CLI (`pa`) and the Power Automate tooling each keep a separate sign-in. Use the account named
in `AZURE_ACCOUNT` on all of them, and check each account and target before a script changes anything: do not rely on a global default or on
another tool's login.

- `python scripts/az.py ...` runs the Azure CLI and refuses to run as any account other than `AZURE_ACCOUNT`
  (`python scripts/az.py account show -o none` exits non-zero on a mismatch). Pass an explicit subscription to every other `az` call.
- Run azd with `AZD_CONFIG_DIR` set to the git-ignored `.azd-config` folder (create it first, as the deployment runbook shows), so azd's defaults
  do not leak in from other projects. Avoid `azd auth login`, `azd config set` and `az account set`, which change global defaults.
- `pa auth status` lists the cached accounts and marks the active one with `*`; switch with `pa auth switch`. Avoid `pa auth logout`, which
  clears every cached account.
- Dataverse and Content Understanding scripts need a silent credential. In an unattended shell set `CI=1` so a missing credential fails fast
  instead of waiting for a device-code prompt.

```powershell
dataverse auth who
pac org who
pa auth status
python .\scripts\auth.py --check
```

`scripts/auth.py` is vendored from Microsoft's Dataverse skills plugin (version 1.16.1). Keep it as it is.

## Rules this repository follows

- **Everything in the Power Platform lives in the solution `VizientContractPOC`:** tables, columns, choices, relationships, the Code App, cloud
  flows, connection references, environment variables, security roles and web resources. Never "move it in later". Create Dataverse metadata only
  through `scripts/dvweb.py` or `scripts/provision-dataverse.py`, which always send the solution header. `dataverse/schema.json` is the source of
  truth: change it there, then provision. Build flows in `scripts/flowlib.py`, not in the designer. Push the Code App only with the solution id.
  After any solution change run `python scripts/pull-solution.py` so `dataverse/solution/` matches.
- **The checklist has one source:** `checklist/checklist.json`. The copies in `function/` and `analyzer/` are generated, and tests fail while one
  is stale.
- **Evidence rules:** a Found result needs a verbatim clause, a source page and sufficient confidence. Silence is Not Addressed, not permission,
  and a right is never inferred from another document. AI results are immutable; reviewer changes go in separate reviewer fields. Extraction
  completeness, review completion and accuracy are three different measures and are never merged. Never invent confidence, evidence, extraction
  results or accuracy figures.
- **Synthetic contracts only in this repository.** Fixtures and gold labels use made-up contracts and numbers. Never commit a real contract or
  the labels for one.
- **Azure:** managed identities and Bicep. Validate, and obtain approval, before provisioning. Do not log document content, credentials or raw
  results.
- **The Code App:** React, Vite, strict TypeScript, Fluent UI v9 and pdf.js; the generated Power Apps data services, never browser-side tokens;
  the vizient.com theme in `design/vizient-theme/`. Orange `#f67318` is for fills only; use `#a24300` for orange text so contrast stays at or above
  4.5:1.
- **Check current documentation before copying a command:** the Code Apps CLI is `pa app`, not the legacy `pac code`. Content Understanding
  needs grounding and confidence enabled explicitly, and a long request should use the asynchronous operation, not a long synchronous call.

## Common tasks

### The Dataverse solution

Every Power Platform object lives in the unmanaged solution `VizientContractPOC`. `dataverse/schema.json` is the schema source of truth;
`dataverse/schema.md` explains it. The provisioner sends the solution header on every create, and the verifier proves nothing sits outside
the solution and nothing foreign sits inside it (declared schema, a real solution export, a sweep for flows, apps, connection references,
environment variables and other strays, and a check that every component is one this project declares).

```powershell
python .\scripts\provision-dataverse.py --dry-run   # plan only, read-only
python .\scripts\provision-dataverse.py             # create inside the solution (idempotent)
python .\scripts\verify-solution.py                 # exit 0 = everything is in the solution, and nothing else is
python .\scripts\verify-solution.py --fix           # repair strays and the preferred solution (never removes an object)
python .\scripts\verify-solution.py --self-test     # prove the guard works (creates and deletes one probe)
python .\scripts\pull-solution.py                   # refresh dataverse\solution\ and dataverse\VizientContractPOC_unmanaged.zip
python -m pytest tests -q                           # offline tests of the guard (no environment needed)
```

Right after provisioning, the Dataverse metadata API can briefly lag behind the export. The verifier re-reads through fresh sessions before it
reports an object missing, and when the export holds everything it says so; re-run in a few minutes. Wait for a clean run before seeding data.

### Azure

The resource group, Foundry account (the model deployments Content Understanding uses), Function app, managed identity and monitoring are Bicep
in `infra/`, deployed with azd (the reference deployment is in East US 2). The cost estimates are in appendix D of the
[deployment runbook](deployment-runbook.md). The region, the Search region, private networking, an optional storage exemption tag and the
real-contract switch are azd environment values; see section 3.2 of the same runbook.

```powershell
New-Item -ItemType Directory -Force .azd-config | Out-Null
$env:AZD_CONFIG_DIR = (Resolve-Path .azd-config).Path; $env:NO_COLOR = '1'
azd provision --no-prompt                       # infrastructure
azd deploy --no-prompt                          # publish function\ (about 25 seconds)
python .\analyzer\deploy_analyzer.py --status   # read-only: are the model defaults set, is the analyzer current?
python .\analyzer\deploy_analyzer.py --apply    # set the model defaults, then create or replace the analyzer
```

- Entra tokens only. Key authentication is off on the Foundry account (the reference tenant's policy forces it, and the design never needs a
  key), so the Function reaches Content Understanding with its user-assigned managed identity and a least-privilege role.
- A new Foundry resource answers `DefaultsNotSet` until its model defaults are patched; `--apply` does that first, which lets the analyzer use
  the model aliases (swap `gpt-5.5` for another model without redeploying it).
- Teardown: `azd down --force --purge` (the purge matters because Foundry accounts soft-delete).

### Analyze a contract locally

```powershell
python .\eval\generate_contracts.py                                   # synthetic PDFs into samples\ (git-ignored)
python .\scripts\run-local.py .\samples\bluepine-sow.pdf              # Content Understanding directly
python .\scripts\run-local.py .\samples\bluepine-sow.pdf --via function   # through the deployed API
python .\scripts\run-local.py --result .\samples\results\bluepine-sow.operation.json   # replay a saved result offline
```

Direct and function runs need the Azure CLI signed in as the account in `AZURE_ACCOUNT`. Results are saved to `samples\results\<name>.json`.
With `CONTRACT_DATA_MODE=synthetic` (the default), only PDFs carrying the `SYNTHETIC SAMPLE` marker are sent to the service, so a real contract
cannot go out through a mistyped path.

### Power Automate flows

Four cloud flows live in the solution. `scripts/flowlib.py` builds them and `scripts/provision-flow.py` creates them through the Dataverse
`workflows` API, so the definitions are reviewable and repeatable.

| Flow | Starts when | What it does |
|------|-------------|--------------|
| Vizient Contract Intake | A file arrives in the SharePoint intake folder | Creates the `vz_contract` row, copies the PDF into its file column, sets the status to Extracting |
| Vizient Contract Analysis | A contract's status becomes Extracting | Sends the PDF to the Function, polls until done, writes the findings, the found count and the completeness, and sets Ready for Review. It also queues the contract for indexing. On any error it sets Failed with the reason |
| Vizient Contract Indexing | A contract's `vz_indexstatus` becomes Queued | Indexes the contract's page text in Azure AI Search and records the index status, version and any error, independently of review status |
| Vizient Contract Questions | A `vz_contractquestion` row is created in the Queued status | Calls the Function in short polling steps and writes the cited answer back to the row |

Extracting is also a retry queue: set a Failed contract back to Extracting and the analysis flow runs again. The last two flows belong to
[Ask this contract](ask-this-contract.md).

```powershell
python .\scripts\provision-flow.py            # offline: build the flows and check them against dataverse\schema.json
python .\scripts\provision-flow.py --status   # read-only: compare Dataverse with what --apply would write
python .\scripts\provision-flow.py --apply    # create or update the rows, then turn the flows on
```

It needs the `SHAREPOINT_*` values and the two connection names in `.env` (`pa connection list` shows the names). Environment variables,
connection references and the flows are all created inside the solution. A flow is rewritten only when the `[definition ...]` tag in its
description changes, so reruns are safe.

- **Size limit:** the Dataverse connector reads file columns in 4 MiB ranges, so the flows analyze PDFs under 4 MiB (the Function itself accepts
  32 MiB). A file of 4 MiB or larger ends as Failed with a message that says so.
- **Function key:** the analysis flow calls the Function over HTTP with its function key. The provisioner reads the key from Azure into memory and
  stores it as the value of a text environment variable in the solution, so anyone who can read that variable can read the key. A Key Vault-backed
  secret variable would be better, but the reference tenant's policy keeps Key Vault unreachable from Power Platform (decision C3 in the
  [guide](handoff-guide.docx)). `pull-solution.py` strips environment variable values from the Git export. Rotate the key on a schedule you own,
  then run `provision-flow.py --apply` again to store the new one.

### Demo data

```powershell
python .\scripts\seed-demo.py            # offline: check the saved results and say what would be written
python .\scripts\seed-demo.py --status   # read-only: is the demo data in place?
python .\scripts\seed-demo.py --apply    # write the contracts that are missing; one that exists is not changed
python .\scripts\seed-demo.py --reset    # delete the demo contracts and their findings, then write them again
```

Seeds three synthetic contracts (60 findings) from their saved analysis results, with no Content Understanding call. `--reset` discards any
review work on those contracts, so confirm before running it.

### The Code App

`contract-review/` is a Power Apps Code App: React, Vite, strict TypeScript, Fluent UI v9 and pdf.js, styled with the vizient.com theme. Its
[README](../contract-review/README.md) covers the layout, mock mode and the review behavior.

```powershell
cd contract-review
npm ci
npm run dev:mock    # no Power Platform needed: serves the synthetic PDFs and saved results from ..\samples
npm run lint; npm test; npm run build
pa app push --solution-id <id of VizientContractPOC>   # dist\ must be built first; never push without the solution id
pa app share --principal <email>                       # give a person the right to open the app
```

A clean clone builds without `pa app init`, because the generated list of data sources
(`contract-review/.power/schemas/appschemas/dataSourcesInfo.ts`) is committed. Refresh it, and the generated services under
`contract-review/src/generated/`, with the Power Apps CLI whenever you add or change a table the app reads.

Two pages explain the project instead of reviewing a contract. **How it works** is an animated 3D diagram of the review pipeline, with a guided
"Follow a contract" tour (a clock under the diagram shows how far into the processing each step falls) and the explanation underneath. **Time and
cost** measures the pipeline itself: how long one contract takes from the PDF landing in SharePoint to Ready for Review (a person's review is not
counted), and what one contract costs to process (the pages read and the model tokens, at public list prices). The 3D scene is Three.js, loaded
only when that page opens, and it falls back to a flat diagram when WebGL is unavailable. Every figure is a dated snapshot; the app's README
explains how to refresh each one.

### Evaluation

```powershell
python .\eval\generate_contracts.py --check   # exit 1 if the gold labels differ from a fresh render
python .\eval\score.py                        # score samples\results against eval\gold
```

The last scored run (2026-10-22, synthetic set) matched 97% of the data-rights answers and 100% of the contract details. The one persistent
miss is the geographic right on the data use agreement. Three synthetic contracts are a small sample, and no real contract has been scored.

`eval/gold` holds only the synthetic sets. `.gitignore` ignores every other file there, so labels for a real contract (they quote it verbatim)
cannot be committed by accident; keep them outside the repository and pass that folder with `--gold`. To add a synthetic set, add an
`!eval/gold/<id>.json` line to `.gitignore`.

## Changing things

| To change | Do this |
|---|---|
| The checklist | Edit `checklist/checklist.json`, run `python analyzer/build_schema.py --write` and `Copy-Item checklist\checklist.json function\checklist.json`, then `python .\analyzer\deploy_analyzer.py --apply` and `azd deploy --no-prompt`. Tests fail while either copy is stale |
| The Dataverse schema | Edit `dataverse/schema.json`, run `provision-dataverse.py --dry-run`, then without `--dry-run`, then `verify-solution.py` and `pull-solution.py` |
| A flow | Edit `scripts/flowlib.py`, run `provision-flow.py --status`, then `--apply`. Do not edit flows in the designer |
| The 3D architecture page | It is built from the app's own source: `cd contract-review; npm run build:standalone`. The tests fail while `docs/architecture-3d.html` is older than its sources |
| A dependency of the Code App | Update `package.json` and the lockfile, then run `python scripts/gen-notices.py` to refresh `THIRD-PARTY-NOTICES.md`; the tests fail while it is stale |
| A number or a name that the documents repeat | The tests in `tests/test_doc_facts.py` compare the counts of tables and flows in the README, the documents and the app's own text with the schema and the flows; fix the words, not the test |

## Continuous integration and repository files

- `.github/workflows/ci.yml` runs `python scripts/check.py --python` and `--app` on every push and pull request, so a change is checked the way
  this page describes. It builds and tests; it does not deploy.
- `.github/workflows/codeql.yml` runs CodeQL code scanning when the repository variable `ENABLE_CODEQL` is `true`. Code scanning needs GitHub
  Advanced Security on a private repository, so it is off until you turn it on.
- `.github/dependabot.yml` proposes weekly updates for the app's npm packages, the Python requirements and the workflows.
- `.github/pull_request_template.md` is the checklist for a pull request. [CONTRIBUTING.md](../CONTRIBUTING.md) says how to propose a change and
  [SECURITY.md](../SECURITY.md) how to report a vulnerability and what to settle before production.
- Not included: a deployment pipeline that promotes the solution and the Azure resources between environments (decision C3 in the
  [guide](handoff-guide.docx)).
