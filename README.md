# Contract Intelligence

A pilot that reads a contract PDF against a 20-item checklist (9 contract details and 11 data rights), stores each answer in Dataverse beside
the quote and page it came from, and gives a reviewer a Power Apps Code App to accept, correct or reject every answer. A reviewer can also ask
a question of one contract and get a cited answer.

> **Status: pilot-grade.** It was built and demonstrated on synthetic contracts. It has not been deployed from a clean start, scored on real
> contracts or hardened for production. The [handoff and decision guide](docs/handoff-guide.docx) says what is proven, what is not, and which
> decisions to make first.

The requirements are in `vizient-contract-poc-lite-plan.md` (a redacted copy of the brief).

## Start here

| To | Read |
|---|---|
| Decide what to do first | The [handoff and decision guide](docs/handoff-guide.docx): what this is, where it stands and the decisions to make |
| Understand the design | [Architecture](docs/architecture.md), with its [diagram](docs/architecture/contract-intelligence-architecture.png) |
| See a contract move through the system, in 3D | [Interactive 3D architecture](docs/architecture-3d.html): one web page that opens in any browser with no sign-in or network. Download the file and open it (GitHub shows its source, not the page). It is not part of the Power Platform solution |
| Deploy Azure, the Power Platform solution, the flows and the app | [Deployment runbook](docs/deployment-runbook.md). The Power Platform side can also be imported from [the solution file](dataverse/VizientContractPOC_unmanaged.zip) (deployment runbook 5.10) |
| Run it day to day, and fix it | [Operations runbook](docs/operations-runbook.md) |
| Staff it | [Team and roles](docs/team-and-roles.md): who to involve, the access each person needs, and when |
| Size a backfill and a steady stream | [Capacity and sizing workbook](docs/capacity-sizing-workbook.xlsx) |
| See every table, column and choice | [Dataverse schema notes](dataverse/schema.md) and `dataverse/schema.json` |
| Understand the question feature | [Ask this contract](docs/ask-this-contract.md) |
| Change the code | [Working in this repository](docs/development.md), and the README in [contract-review/](contract-review/README.md) for the app |

## How it works

```text
SharePoint "Contract Intake" folder
  -> flow "Vizient Contract Intake": creates the contract row, attaches the PDF, queues it as Extracting
  -> flow "Vizient Contract Analysis": calls the Function, writes 20 findings, sets Ready for Review
     (or Failed, with the reason) and queues the contract for indexing
  -> Azure Function (Flex Consumption, Python 3.12)
     POST /api/contracts/analyze, then GET /api/contracts/analyze/{operationId} until it returns 200
  -> Content Understanding analyzer "vizientContractChecklist" (gpt-5.5, GA API 2025-11-01)

Ask this contract (docs/ask-this-contract.md)
  flow "Vizient Contract Indexing": indexes the contract's page text in Azure AI Search
  flow "Vizient Contract Questions": answers a reviewer's question through the Function and a Foundry agent

Dataverse, solution VizientContractPOC: vz_contract, vz_finding, vz_checklistitem, vz_contractquestion
Code App "Vizient Contract Review" (contract-review/): contract list, findings beside the PDF,
click-to-highlight evidence, accept / correct / reject, approve, Ask this contract; plus a "How it works" page
(an interactive 3D walk through the review pipeline) and a "Time and cost" page (how long it takes and what it
costs to process one contract)
```

| Path | What it holds |
|------|---------------|
| `checklist/checklist.json` | The checklist: single source of truth (20 extracted items plus 2 manual fields). `function/checklist.json` is the copy the Function ships; a test fails when they differ |
| `analyzer/` | Builds the Content Understanding analyzer from the checklist and deploys it |
| `function/` | The async analysis API (`routes.py`), the Content Understanding client and the mapping to findings |
| `infra/`, `azure.yaml` | Bicep and azd for the Azure side |
| `dataverse/` | `schema.json` (source of truth), `schema.md`, `solution/` (the unpacked solution, for review in Git) and `VizientContractPOC_unmanaged.zip` (the same solution as an importable file, with the Code App package) |
| `docs/` | The guide, the architecture (with its diagram and the interactive 3D page), the runbooks, team and roles, Ask this contract, working in this repository, and the sizing workbook |
| `scripts/` | Provisioning, seeding, flows, the solution guard, local analysis, the leak scan and `check.py` |
| `eval/` | Synthetic contract generator, gold labels and the scorer |
| `tests/` | Offline pytest suites for the Python code |
| `contract-review/` | The Code App (React, Vite, strict TypeScript, Fluent UI v9, pdf.js). See its own README |
| `design/vizient-theme/` | The vizient.com theme (CSS and a preview page) |
| `.github/` | Continuous integration, code scanning and dependency updates |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, `THIRD-PARTY-NOTICES.md` | What changed between releases, how to propose a change, how to report a vulnerability and what to settle before production, and the licenses of the packages the app is built from |

## Check that it builds

You need Python 3.12 and Node 24 or later. No sign-in is needed.

```powershell
python -m pip install -r requirements-dev.txt
cd contract-review; npm ci; cd ..
python scripts/check.py        # Python lint, types and tests, then the app's lint, types, tests and build
```

Deploying is a separate, signed-in job with its own order: follow the [deployment runbook](docs/deployment-runbook.md), which says what each step
needs. Copy `.env.example` to `.env` first (see [Working in this repository](docs/development.md)).

## Data handling

**Synthetic contracts only in this repository.** Fixtures, gold labels and documentation use made-up contracts and numbers (`eval/`). `*.pdf` is
git-ignored, so a real contract cannot be committed by mistake, and `eval/gold` accepts only the synthetic sets. A document that someone drops
into the SharePoint intake folder goes through the same pipeline as any upload, so choose on purpose which documents appear in a demonstration.

`python scripts/leak-scan.py` checks what Git would commit against the identifiers in your `.env` (environment, tenant, subscription, hosts and
the sign-in account) and must be clean before every commit. The checklist contains **20** extracted items; two additional reviewer fields
(Contract Owner and Legal Reviewer) are filled in by hand and sit outside the accuracy figures.

## Known limits

- **Ask this contract:**
  - Each answer comes from the top 12 retrieved passages, so "Not Addressed in the retrieved passages" does not prove the contract is silent.
    Ask Legal when it matters.
  - Answers are checked for verbatim quotes, not for legal correctness; answer accuracy on real contracts has not been measured. Quote
    verification is by letters and digits, so it can match across table cells.
  - Once real contracts are allowed (see [Ask this contract](docs/ask-this-contract.md)), their text is stored in Dataverse (`vz_documenttext`)
    and in Azure AI Search. No retention policy, legal and security review or non-administrator permission test has been done. Chunks are not
    deleted with their contract: run `purge-contract-index.py`.
  - A contract has one index version at a time; re-extracting replaces it. A document over about 1 MB of page text fails indexing only (review is
    unaffected), and the embedding quota can slow indexing of long contracts.
  - The Search index costs about USD 74 a month while it exists, even idle.
- Scanned (image-only) PDFs have not been tried. The synthetic contracts all have a text layer.
- Content Understanding answers can differ slightly between runs of the same contract.
- The project defines no Dataverse security role of its own yet. A person who is not a system administrator needs a role with access to the
  four `vz_` tables (own-row access is enough for questions), a Power Apps license that covers Dataverse, and the app shared with them.
- A SOW or amendment is linked to its parent only when that parent contract has been uploaded too. A parent that was never uploaded leaves the
  "Parent agreement not linked" chip on.
- The **Time and cost** page does not update itself. Its processing time and cost per contract are dated snapshots, not a benchmark: three timed
  end-to-end runs, and the recorded usage of three synthetic samples priced at public list prices (a tenant's own agreement may differ). Both
  depend on the document. The cost leaves out a person's review, Power Platform licenses, storage, monitoring, discounts and tax. For other
  volumes use the [capacity and sizing workbook](docs/capacity-sizing-workbook.xlsx).

## License and notices

This source was delivered for Vizient's evaluation of the pilot. The terms on which it may be used are those of the agreement under which it
was delivered; this repository does not add to or change them.

Third-party components keep their own licenses. [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) lists the packages the Code App and the 3D
page are built from, and [infra/LICENSE-functions-quickstart.txt](infra/LICENSE-functions-quickstart.txt) covers the Bicep adapted from an Azure
sample. The Python packages are installed from PyPI when you deploy and are not redistributed here.
