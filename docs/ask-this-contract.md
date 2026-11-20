# Ask this contract

A reviewer can put a question to one contract and get an answer that quotes the passages it came from. This page describes how the
feature behaves, what it adds to Azure and how to operate it. The review pipeline it sits beside is described in the
[architecture](architecture.md).

Ask this contract is deployed with the rest of the system: `provision-flow.py` always creates all four flows, and Azure AI Search is billed
by the hour whether or not anyone asks a question. Making it optional is a code change (decision A6 in the [guide](handoff-guide.docx)).

## What a reviewer sees

Open an indexed contract in the review app and select **Ask this contract**. The additive drawer searches only that record's full
extracted text, not just its checklist findings, and never follows parent links. **View page** opens verified quote evidence in the existing
PDF viewer; reopening the drawer preserves the conversation while you stay on that record. Navigating away or re-extracting resets it. Review
behavior is unchanged. The app shows Q&A readiness and disables **Ask this contract** until indexing is Ready.

## How it works

Ingestion preserves complete page-grounded text in `vz_documenttext`, separately from the deliberately reduced `vz_rawresult` debugging
snapshot. The analysis result supplies an explicit `indexing` handoff. Missing page text or a document that is not marked synthetic (only
while `ALLOW_REAL_CONTRACTS` is off) fails only that handoff; checklist review continues unchanged.

The separate solution-owned **Vizient Contract Indexing** flow indexes page-local overlapping chunks in a shared Azure AI Search index. It
records `vz_indexstatus`, `vz_indexversion` and `vz_indexerror` independently of review status. Indexing uses bounded embedding and upload
batches and short polling requests, checks every upload result, and verifies manifest and chunk visibility before declaring Ready. Requeue
`vz_indexstatus` to Queued to retry indexing without discarding reviewer work. A contract whose row holds no document text (for example one
created by an older build) cannot be indexed: use `reextract-contracts.py` (below), which discards its findings. Nothing backfills automatically.

The app reads `vz_documenttext` with the signed-in user's generated Dataverse service, creates a user-owned `vz_contractquestion`, and polls
for the answer. The solution-owned **Vizient Contract Questions** flow calls the Function in short polling steps; it never fetches document
text as its connection owner. It clears context and history after either success or failure.

The backend performs hybrid keyword and vector retrieval with mandatory contract ID and content-version prefilters, verifies returned chunks
against the authorized document, and passes only retrieved evidence to Foundry's `contract-questions` prompt agent. Questions never create
indexes or upload files. Quotes must match both the retrieved passages and their original source pages. Tables are shown to the model one row
per line (cells joined by ` | `), and a quote matches on its letters and digits across cell and tag boundaries, so a quote may span table markup
but cannot invent words. If the first answer's quotes fail, one automatic retry is made before the user sees an error. Insufficient retrieval
is reported as Not Addressed in the retrieved passages, not as proof of absence throughout the whole document. Answers are plain text, not
executed HTML.

## What it adds to Azure

`infra/qa.bicep` adds a separate Foundry account and project and a GlobalStandard `gpt-4.1-mini` deployment, with managed identity access for
the existing Function, one Basic Azure AI Search unit and `text-embedding-3-small`. Search uses Entra authentication only; the Function has
index-data access and the deployer manages the schema. Basic Search is continuously billed: the public retail quote checked on 2026-10-23 was
USD 0.101 an hour (about USD 73.73 at 730 hours), plus usage-based embeddings and answer tokens. This single-replica pilot is not a
high-availability deployment. Validate and obtain provisioning approval before `--apply`.

In the reference deployment East US 2 rejected new Search capacity, so its Search service runs in East US while Foundry and the Function stay
in East US 2. The Search region is the azd value `AZURE_SEARCH_LOCATION` (the infra parameter `searchLocation`, default the primary region)
and `provision-qa.py` passes it to `infra/qa.bicep`.

## Real contracts

The Function setting `ALLOW_REAL_CONTRACTS` (azd value of the same name, infra parameter `allowRealContracts`) defaults to `false`. While it
is off, Q&A indexing is restricted to documents carrying the `SYNTHETIC SAMPLE` marker; it does not gate extraction. `provision-qa.py` never
changes it.

Turn it on only after decision A1 in the [guide](handoff-guide.docx): `azd env set ALLOW_REAL_CONTRACTS true`, then `azd provision --no-prompt`.
Real contract text is then stored in Dataverse (`vz_documenttext`) and in the Search index, so a retention policy, a legal and security
review, and a non-administrator permission test come first. Give reviewers only own-row access to questions. Return to synthetic-only with
`azd env set ALLOW_REAL_CONTRACTS false` and `azd provision --no-prompt`.

## Commands

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

`--ingest-fixture` generates a made-up PDF in memory, creates a new synthetic record, and waits for extraction, review readiness, Search
readiness and a cited answer. It does not reset existing reviews or read uploaded PDFs. The synthetic record is retained for inspection.
`--expect-answer-text` makes an unexpected answer fail the smoke test.

Search versions have no automatic expiry. Old versions are excluded from retrieval but remain stored, and deleting a Dataverse record does not
delete its Search chunks. Re-extract contracts that have no document text, and purge Search chunks that no longer belong to a live contract
version:

```powershell
python .\scripts\reextract-contracts.py                     # dry run; lists contracts and findings that would be discarded
python .\scripts\reextract-contracts.py --apply --wait      # DISCARDS findings and review work, then re-extracts and indexes
python .\scripts\reextract-contracts.py --apply --name "file.pdf"   # one contract only
python .\scripts\purge-contract-index.py --status           # what the index holds; changes nothing
python .\scripts\purge-contract-index.py --stale --orphans --apply  # delete old versions and chunks of deleted contracts
python .\scripts\purge-contract-index.py --contract <guid> --apply  # delete every version of one contract
```

Re-extraction keeps the contract row, its PDF, its parent link and the manual Contract Owner and Legal Reviewer fields. Both tools print only
names, ids and counts, never document text. `--stale` ignores a contract that is still indexing.

## Changing the feature

Refresh the generated Code App data services for `vz_contract` and `vz_contractquestion` in your environment before building. Deploy the
Function with the project's isolated azd configuration, run all Code App checks before pushing the app with the solution id, then run
`verify-solution.py` and `pull-solution.py` (see [Working in this repository](development.md)). All target identifiers stay in ignored local
configuration. Existing extraction results, findings and review decisions are never overwritten by Q&A.

The limits that matter when you rely on it are under "Known limits" in the [README](../README.md).
