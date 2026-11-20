# Dataverse schema

Publisher `VizientContractIntelligence` (prefix `vz`, option prefix `65120`) in the unmanaged solution
**`VizientContractPOC`**. Plan section 5 is the design; `schema.json` is the implemented source of truth
and holds every column, type, length and default. This file records what is decided and why.

## Change the schema

1. Edit `dataverse/schema.json`.
2. `python scripts/provision-dataverse.py --dry-run`, then without `--dry-run`. It is idempotent and
   sends the solution header on every create, so nothing can land outside the solution.
3. `python scripts/verify-solution.py` must exit 0.
4. `python scripts/pull-solution.py` refreshes `dataverse/solution/` (generated, never hand-edited).

## Tables

| Table | Ownership | Purpose |
|---|---|---|
| `vz_contract` | User | One analyzed contract document, its promoted header fields, status and the stored PDF (`vz_document` file column). |
| `vz_checklistitem` | Organization | Configuration: one row per checklist item. Alternate key `vz_checklistitem_key` on `vz_key`, so seeding upserts. |
| `vz_finding` | User | One row per contract and checklist item: what the AI found (`vz_ai*`) and what the reviewer decided (`vz_reviewer*`). |
| `vz_contractquestion` | User | One asynchronous question about a single contract. Holds question/history, transient authorized extraction, status, and a JSON answer with verified page quotes. Context/history are cleared after success/failure; no findings are changed. |

## Relationships

| Name | From | To | Delete behavior |
|---|---|---|---|
| `vz_finding_contract` | `vz_finding` | `vz_contract` | Parental: deleting a contract deletes its findings |
| `vz_finding_checklistitem` | `vz_finding` | `vz_checklistitem` | Restrict |
| `vz_finding_reviewedby` | `vz_finding` | `systemuser` | Remove link |
| `vz_contract_parentcontract` | `vz_contract` | `vz_contract` | Remove link (amendment to SOW to MSA) |
| `vz_contract_contractowner` | `vz_contract` | `systemuser` | Remove link |
| `vz_contract_legalreviewer` | `vz_contract` | `systemuser` | Remove link |
| `vz_contractquestion_contract` | `vz_contractquestion` | `vz_contract` | Parental: deleting a contract deletes its questions |

## Choices

Option values are `651200000 + position` in the order listed in `schema.json`.
**Only ever append options. Never reorder or delete**, because stored rows hold the numbers.

- Global `vz_judgment`: Permitted `651200000`, Prohibited `…01`, Conditional `…02`, Not Addressed `…03`, N/A `…04`.
  Shared by `vz_aijudgment` and `vz_reviewerjudgment`.
- Local choices: `vz_documenttype`, `vz_status`, `vz_group`, `vz_presence`, `vz_reviewstatus`.
- Question `vz_status`: Queued `651200000`, Answered `651200001`, Failed `651200002`. Reviewer roles should
  have own-row question privileges only, with read/append-to on contracts they are authorized to ask about.
- Contract `vz_indexstatus`: Not Indexed `651200000`, Queued `651200001`, Ready `651200002`, Failed `651200003`.
  This is independent of review `vz_status`. `vz_indexversion` is the SHA-256 document version; `vz_indexerror`
  explains indexing failures. `vz_documenttext` holds complete synthetic page text; `vz_rawresult` remains a
  reduced debugging result and must never be treated as the whole document.

## Decisions to know

- **Display names start with "Vizient".** The system `contract` table already owns the display name
  "Contract", so a plain name collides in the maker portal. Logical names keep the plan's `vz_` form.
- **`vz` is separate from the `viz_` tables** that already exist in this environment. There is no technical
  collision. It is the prefix that was chosen for this project.
- **A `systemuser` root component appears in the solution** (`rootcomponentbehavior` 1, no subcomponents).
  Dataverse adds it as a dependency shell for the three user lookups. The export also reports one
  `MissingDependency` on `systemuser` from `OmnichannelTelephony`. Both are expected and harmless.
- **Columns are not separate solution rows.** Each table is a root component with "include all
  subcomponents", so its columns, key, relationships, forms and views travel with it.
  `verify-solution.py` accounts for this and confirms against a real export.
- **Date and datetime columns** are created through the Web API with an explicit `DateTimeBehavior`.
  The SDK's default breaks Filtered view generation.
- **The metadata API can answer incompletely right after provisioning.** Seen once, not reproduced: a table
  listed with only its primary column while the export and the data plane were complete. `verify-solution.py`
  re-reads such answers through fresh sessions. If an object is still unlisted it fails with "not listed by the
  metadata API" and says to re-run in a few minutes. The cause on the platform side is unproven, so wait for a
  clean run before seeding data.
