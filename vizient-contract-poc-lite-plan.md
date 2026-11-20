# Vizient Contract Intelligence — POC Lite Build Plan

> **Purpose:** Build plan for an AI-first build in VS Code + GitHub Copilot (Agent mode). Drop this file at the repo root as `plan.md` and work it phase by phase.
> **Owner:** walkthenose75 · **Target:** Working demo by **Friday 2026-10-23 AM** (built 100% with GitHub Copilot) · **Environment:** Microsoft demo tenant (DEV)
> **Status:** v0.2 — 2026-10-21 (Friday autopilot edition — see §0 and §8)

---

## 0. Build tooling (GitHub Copilot does everything)

| Piece | Built by | Notes |
|---|---|---|
| Azure infra (Foundry, Function App, storage, RBAC) | Copilot Agent mode → Bicep + `azd up` (Azure MCP Server to inspect) | |
| Content Understanding analyzer | Copilot → `build_schema.py` + `deploy_analyzer.py` | **Microsoft Learn MCP Server** connected so Copilot reads the *current* CU API, not guesses |
| Azure Function (analyze + map) | Copilot → Python | Unit-tested with saved JSON fixtures |
| Dataverse tables + seed | Copilot → Dataverse Web API script / PAC CLI (Dataverse MCP to verify) | |
| App user for Function → Dataverse | `pac admin create-service-principal` | |
| Power Automate intake flow | Copilot → **Agent Flow MCP server** | Confirm SharePoint *file created* trigger is available in the flow type the MCP builds; else cloud flow |
| **Contract Review app + Evidence Viewer** | Copilot → **Power Apps Code App** (React + Vite + TypeScript + Fluent UI v9 + pdf.js) · `pac code init` / `pac code add-data-source` / `pac code push` | ✅ **Decision 2026-10-21: Code App route.** One app = contract list + side-by-side viewer + click-to-highlight + Accept/Correct. Model-driven app optional later for admin/MVP. |

**Autopilot rules:** one phase per Agent-mode session · each phase ends with its *Done when* test · Copilot must not start the next phase until the test passes · `checklist/checklist.json` is the single source of truth.

---

## 1. The POC in one sentence

**Drop a contract in SharePoint → AI reads it against Vizient's checklist → a reviewer sees the PDF side by side with every finding, clicks an item, and the exact clause lights up.**

### What it proves
1. **Find it:** For each checklist item, is it in the contract? (Found / Not Found / Unclear)
2. **Show it:** If found, what does it say, and where (verbatim clause + page + highlight)?
3. **Judge it (suggested):** For data-rights items, the AI *suggests* Permitted / Prohibited / Conditional / Not Addressed. **A human always confirms.**
4. **Measure it:** Every reviewer Accept/Correct is recorded, so accuracy is measured, not claimed.

### What it does NOT do (MVP scope)
- Merge terms across MSA → SOW → Amendment (we only **flag** references and allow a manual Parent link)
- Multi-step governance workflow (Legal → DG → Business Owner)
- Databricks/Unity Catalog/Purview integration (record-scoped Foundry Q&A added by the approved phase below)
- Production ALM, HA/DR, Vizient client contracts

---

## 2. Flow

```
 ┌──────────────┐   ┌────────────────────┐   ┌──────────────────────────┐   ┌─────────────────────────┐
 │ 1. SharePoint│──▶│ 2. Power Automate   │──▶│ 3. Azure Function         │──▶│ 4. Dataverse             │
 │ "Contract    │   │ - Create Contract   │   │ - Call Content            │   │ - Contract (status,      │
 │  Intake" lib │   │   row (Received)    │   │   Understanding analyzer  │   │   completeness, PDF)     │
 │ (drop PDF)   │   │ - Copy PDF to file  │   │ - Normalize to 18         │   │ - 18 Findings rows       │
 └──────────────┘   │   column            │   │   findings + grounding    │   │   (value, clause, page,  │
                    │ - Call Function     │   └──────────────────────────┘   │   polygon, confidence)   │
                    │ - Write findings    │                                  └────────────┬────────────┘
                    │ - Status = Ready    │                                               │
                    └────────────────────┘                                               ▼
                                                                  ┌─────────────────────────────────────┐
                                                                  │ 5. Code App "Contract Review"        │
                                                                  │  Evidence Viewer: PDF ◀▶ Checklist   │
                                                                  │  click item → scroll + highlight     │
                                                                  │  Accept / Correct per item           │
                                                                  └─────────────────────────────────────┘
```

**Design rules**
- **Evidence or it didn't happen:** no clause = no "Found". The AI never fills a gap with a guess.
- **Not Found ≠ Not Permitted.** "Not Addressed" is a valid, important answer (often means "check the MSA / ask Legal").
- **Checklist is data, not code.** Items live in a Dataverse table; the analyzer schema is generated from it.
- **One document = one Contract record.** Amendments are separate records linked by a manual *Parent Contract* lookup.

---

## 3. The checklist (18 extracted + 2 manual)

Source: Vizient *Enterprise Contract Intelligence Platform* proposal — "Contract Information" repository elements and the Phase 1 taxonomy example table.

### 3a. Contract details (extract)

| # | Key (analyzer field) | Label | Type | Definition for the AI |
|---|---|---|---|---|
| 1 | `Vendor` | Client / Vendor | string | Legal name of the counterparty providing data or services to Vizient or its affiliate. |
| 2 | `VizientEntity` | Vizient contracting entity | string | The Vizient entity or affiliate that is a party (e.g., Vizient Inc., Sg2, LLC). |
| 3 | `DocumentType` | Document type | enum | One of: MSA, SOW, Amendment, Order Form, DUA, BAA, NDA, Other. |
| 4 | `ContractIdentifier` | Contract identifier | string | Agreement, SOW, opportunity, or contract number of THIS document. |
| 5 | `EffectiveDate` | Effective date | date | Date this document takes effect. |
| 6 | `ExpirationDate` | Expiration / end date | date | Date the term or license period ends. Empty if evergreen or not stated. |
| 7 | `RenewalTermination` | Renewal & termination terms | string | Summary of renewal, notice periods, and termination-for-convenience rights. |
| 8 | `Signatories` | Signatories | string | Names, titles, and signature dates of all signers. |
| 9 | `ParentAgreementReference` | Parent / related agreement | string | Any other agreement this document incorporates, amends, or is governed by (number + date). |

> *Count note:* items 1–9 above are 9 detail fields; items 2–3 are POC helpers. If you need exactly 7, drop `VizientEntity` and `DocumentType` — but keep them: they're cheap and make the demo smarter.

### 3b. Data rights (extract + suggested judgment)

Each right returns: **Judgment** (Permitted / Prohibited / Conditional / Not Addressed), **Conditions** (text), **Clause** (verbatim quote — grounded).

| # | Key | Category | Question the AI answers |
|---|---|---|---|
| 10 | `Right_InternalAnalytics` | Internal Analytics | May the data be used for internal reporting and analysis? |
| 11 | `Right_AIML` | AI / Machine Learning | May the data be used for AI/ML model training or inference? |
| 12 | `Right_ProductDevelopment` | Product Development | May the data be used in commercial products, solutions, or derivative works? |
| 13 | `Right_BAARequired` | BAA Required | Does the contract require or reference a Business Associate Agreement? (Judgment: Yes→Conditional, No→Not Addressed) |
| 14 | `Right_Retention` | Retention Requirements | How long may data be retained? What retention obligations apply? |
| 15 | `Right_AffiliateSharing` | Affiliate Sharing | May data be shared with corporate affiliates? |
| 16 | `Right_ThirdPartySharing` | Third-Party Sharing | May data be distributed or disclosed to external parties/clients? |
| 17 | `Right_DataLinking` | Data Linking | May data be combined/linked with other datasets? Any limits on identifiers/linkages? |
| 18 | `Right_DeIdentification` | De-Identification Rights | May data be anonymized, aggregated, or de-identified, and used afterward? |
| 19 | `Right_Destruction` | Destruction Requirements | What must happen to the data at termination/expiration (return, destroy, archive)? |
| 20 | `Right_Geographic` | Geographic / Offshore | Are there data residency or offshore access restrictions? |

> That's 11 rights + 9 details = **20 extracted** (the "18" in conversation + the 2 helper fields). Fine for POC.

### 3c. Manual (reviewer enters — not in the contract)
- **Contract Owner** (Vizient business owner) — lookup to User
- **Legal Reviewer** — lookup to User

### 3d. Presence logic (computed in the Function)

| Presence | Rule |
|---|---|
| **Found** | Value/clause present AND confidence ≥ `HIGH_CONF` (default 0.80) AND (for rights) Judgment ≠ Not Addressed |
| **Unclear** | Value present but confidence < `HIGH_CONF`, OR clause missing for a non-empty value |
| **Not Found** | Empty value, or rights Judgment = Not Addressed |

**Completeness score** = Found ÷ total extracted items (shown as "14 of 20").

---

## 4. Azure: Content Understanding analyzer

### 4a. Resources (demo tenant)
- **Azure AI Foundry resource** (AI Services) in a US region that supports Content Understanding
- Model deployments required by Content Understanding (per current docs — e.g., a GPT-4.1-class chat model + text embedding model) set as the resource defaults
- **Function App** — Python 3.11, Flex Consumption, system-assigned managed identity
- Auth: managed identity → *Cognitive Services User* on the Foundry resource (API key in app settings acceptable for day 1)

> ⚠️ **Verify first (Day 1, hour 1):** current GA API version, the `:analyze` / `:analyzeBinary` request shape, and that field results include **`source`** (page + polygon) and **`confidence`** when `estimateFieldSourceAndConfidence` is enabled. The highlight viewer depends on this.

### 4b. Analyzer definition (starter — generate from the checklist table)

`analyzer/vizient-contract-checklist.json`
```json
{
  "description": "Vizient third-party data contract checklist (POC Lite)",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "returnDetails": true,
    "estimateFieldSourceAndConfidence": true,
    "enableOcr": true,
    "enableLayout": true
  },
  "fieldSchema": {
    "name": "VizientContractChecklist",
    "fields": {
      "Vendor":               { "type": "string", "method": "extract",  "description": "Legal name of the counterparty providing data or services to Vizient or its affiliate." },
      "VizientEntity":        { "type": "string", "method": "extract",  "description": "The Vizient entity or affiliate that is a party, e.g. Vizient Inc. or Sg2, LLC." },
      "DocumentType":         { "type": "string", "method": "classify", "enum": ["MSA","SOW","Amendment","Order Form","DUA","BAA","NDA","Other"], "description": "Type of this document." },
      "ContractIdentifier":   { "type": "string", "method": "extract",  "description": "Agreement, SOW, opportunity or contract number of THIS document." },
      "EffectiveDate":        { "type": "date",   "method": "extract",  "description": "Date this document takes effect." },
      "ExpirationDate":       { "type": "date",   "method": "extract",  "description": "Date the term or license period ends. Leave empty if not stated." },
      "RenewalTermination":   { "type": "string", "method": "generate", "description": "Summary of renewal terms, notice periods and termination-for-convenience rights. Empty if not stated." },
      "Signatories":          { "type": "string", "method": "extract",  "description": "Names, titles and signature dates of all signers." },
      "ParentAgreementReference": { "type": "string", "method": "extract", "description": "Any other agreement this document incorporates by reference, amends or is governed by, with number and date. Empty if none." },

      "Right_AIML": {
        "type": "object",
        "description": "Whether the licensed data may be used for AI or machine learning model training or inference.",
        "properties": {
          "Judgment":   { "type": "string", "method": "classify", "enum": ["Permitted","Prohibited","Conditional","Not Addressed"], "description": "Use 'Not Addressed' if the document does not explicitly address this. Never infer from silence." },
          "Conditions": { "type": "string", "method": "generate", "description": "Conditions or limits that apply. Empty if none." },
          "Clause":     { "type": "string", "method": "extract",  "description": "Verbatim text of the governing clause. Empty if Not Addressed." }
        }
      }
      /* Repeat the Right_* object for the other 10 rights categories — generate from checklist.json */
    }
  }
}
```

**Rules for Copilot when generating the schema**
- Generate all `Right_*` objects from `checklist/checklist.json` (single source of truth).
- Every rights description ends with: *"Use 'Not Addressed' if the document does not explicitly address this. Never infer from silence."*
- If nested `object` fields don't return reliable grounding, **flatten** to `Right_AIML_Judgment`, `Right_AIML_Clause`, `Right_AIML_Conditions`.

---

## 5. Dataverse data model

Publisher prefix: **`vz_`** · Solution: **`VizientContractPOC`** (unmanaged in DEV)

### `vz_contract` — Contract
| Column | Type | Notes |
|---|---|---|
| `vz_name` | Text (primary) | File name |
| `vz_vendor`, `vz_viziententity`, `vz_contractidentifier` | Text | Promoted from findings for views |
| `vz_documenttype` | Choice | MSA, SOW, Amendment, Order Form, DUA, BAA, NDA, Other |
| `vz_effectivedate`, `vz_expirationdate` | Date only | |
| `vz_status` | Choice | Received · Extracting · Ready for Review · In Review · Approved · Failed |
| `vz_document` | **File** (max 32 MB) | Copy of the PDF — viewer reads this |
| `vz_sharepointurl` | URL | Link to source |
| `vz_sharepointitemid` | Text | SharePoint item/file id — Code App reads the PDF via the SharePoint connector |
| `vz_parentcontract` | Lookup → vz_contract | Manual link (amendment → SOW → MSA) |
| `vz_hasparentreference` | Yes/No | True if AI found a parent/related agreement reference |
| `vz_foundcount`, `vz_totalcount` | Whole number | |
| `vz_completeness` | Decimal (0–100) | found/total × 100 |
| `vz_contractowner`, `vz_legalreviewer` | Lookup → User | Manual |
| `vz_rawresult` | Multiline text (1M) | Raw analyzer JSON (debug + re-processing) |
| `vz_errormessage` | Multiline text | |
| `vz_processedon` | Date/time | |

### `vz_checklistitem` — Checklist Item (config)
| Column | Type | Notes |
|---|---|---|
| `vz_name` | Text | Label |
| `vz_key` | Text (unique) | Matches analyzer field, e.g. `Right_AIML` |
| `vz_group` | Choice | Contract Detail · Data Right · Manual |
| `vz_definition` | Multiline | Shown as tooltip in the viewer |
| `vz_hasjudgment` | Yes/No | True for Data Rights |
| `vz_sortorder` | Whole number | |
| `vz_isactive` | Yes/No | |

### `vz_finding` — Finding (one per contract × checklist item)
| Column | Type | Notes |
|---|---|---|
| `vz_name` | Text | `{Contract} – {Item}` |
| `vz_contract` | Lookup → vz_contract | Parental (cascade delete) |
| `vz_checklistitem` | Lookup → vz_checklistitem | |
| `vz_presence` | Choice | Found · Not Found · Unclear |
| `vz_aivalue` | Multiline | Extracted value / summary |
| `vz_aijudgment` | Choice | Permitted · Prohibited · Conditional · Not Addressed · N/A |
| `vz_aiconditions` | Multiline | |
| `vz_clause` | Multiline | Verbatim quote |
| `vz_page` | Whole number | First page of the source |
| `vz_sourceregions` | Multiline | JSON array: `[{page, polygon:[x1,y1..x4,y4]}]` (units as returned — inches for PDF) |
| `vz_confidence` | Decimal (0–1) | |
| `vz_reviewstatus` | Choice | Pending · Accepted · Corrected · Rejected |
| `vz_reviewervalue`, `vz_reviewerjudgment`, `vz_reviewernotes` | as above | Original AI value is **never overwritten** |
| `vz_reviewedby` / `vz_reviewedon` | Lookup User / Date-time | |

**Seed data:** `checklist/checklist.json` → imported into `vz_checklistitem` by `scripts/seed-checklist.py` (Dataverse Web API) or a PAC CLI data import.

---

## 6. Components to build

### 6a. Azure Function — `ExtractContract` (Python)
- **Input** (HTTP POST, function key): `{ "contractId": "<guid>", "fileName": "...", "fileBase64": "..." }`
- **Steps:** call analyzer (`analyzeBinary`) → poll operation until `Succeeded` (timeout 5 min) → map fields to findings using `checklist.json` → parse `source` strings to `{page, polygon}` → compute presence + completeness
- **Output:**
```json
{
  "contract": { "vendor": "...", "vizientEntity": "...", "documentType": "SOW", "contractIdentifier": "...",
                "effectiveDate": "2025-03-01", "expirationDate": "2028-02-29", "hasParentReference": true,
                "foundCount": 14, "totalCount": 20, "completeness": 70.0 },
  "findings": [
    { "key": "Right_AIML", "presence": "Not Found", "value": "", "judgment": "Not Addressed",
      "conditions": "", "clause": "", "page": null, "sourceRegions": [], "confidence": 0.91 }
  ],
  "raw": { }
}
```
- Unit tests: `tests/test_mapping.py` using saved analyzer JSON fixtures (no live calls).

> **Lite alternative (no Function):** Power Automate HTTP action → `analyzeBinary`, *Do until* poll, Parse JSON, and map. Works, but mapping/grounding parsing is painful in expressions. Use only if a Function App is blocked.

### 6b. Power Automate — `Contract Intake – Extract`
1. Trigger: SharePoint *When a file is created in a folder* — library **Contract Intake**
2. Dataverse: **Add a row** `vz_contract` (name, SharePoint URL, status = Received)
3. Dataverse: **Upload a file** → `vz_document`
4. Update status = Extracting
5. HTTP → Function `ExtractContract`
6. Update contract with promoted fields + counts + `vz_rawresult`
7. *Apply to each* finding → **Add a row** `vz_finding` (lookup checklist item by `vz_key`)
8. Status = **Ready for Review**
9. Scope *catch* → status = Failed + `vz_errormessage`

### 6c. Power Apps Code App — **Contract Review** ⭐ the wow

**Setup (Copilot runs these)**
```bash
npm create vite@latest contract-review -- --template react-ts
cd contract-review && npm i @fluentui/react-components pdfjs-dist
pac auth create --environment <DEV env id>
pac code init --displayName "Contract Review"
pac code add-data-source -a dataverse -t vz_contract
pac code add-data-source -a dataverse -t vz_finding
pac code add-data-source -a dataverse -t vz_checklistitem
pac code add-data-source -a sharedsharepointonline -c <connection id>   # read the PDF
npm run build && pac code push
```
> ⚠️ Verify against current Code Apps docs (Learn MCP) — command flags and generated service names change. Code Apps must be enabled on the environment; users need Power Apps Premium (or trial).

**Screens**
1. **Contracts** (home) — card/table list: Vendor · Doc type · Status chip · Completeness bar · Processed on. Filters: *Ready for Review* · *All* · *Low completeness (< 60%)*. Auto-refresh every 10 s so a SharePoint drop *appears live* in the demo.
2. **Review** (per contract) — the Evidence Viewer below + a *Details* drawer (Parent Contract, Contract Owner, Legal Reviewer, Status) + **Approve Contract** button (enabled only when no findings are Pending).

**PDF source (pick whichever works first, Wed night):**
- **A (preferred):** SharePoint connector *Get file content* using `vz_sharepointitemid` → bytes → pdf.js
- **B:** Dataverse file column `vz_document` (if supported by the Code App Dataverse data source)
- **C (last resort):** Function writes a copy to Blob and returns a short-lived SAS URL stored on the contract

### 6d. Evidence Viewer component (inside the Code App)
React component `EvidenceViewer` (`src/components/EvidenceViewer.tsx`) using the generated Dataverse services for `vz_finding` / `vz_contract`.

**Layout**
```
┌───────────────────────────── Header ───────────────────────────────┐
│ Bluepine Co. · SOW · BP-0417           Completeness ███████░░ 14/20 │
├───────────────────────────────┬────────────────────────────────────┤
│                               │ ▾ CONTRACT DETAILS                 │
│     PDF (pdf.js)              │   ● Vendor  Bluepine Co. 0.97  ✓ ✎ │
│                               │   ● Effective  2025-03-01     ✓ ✎ │
│   ┌───────────────────────┐   │ ▾ DATA RIGHTS                      │
│   │ ▓▓▓ highlighted ▓▓▓▓▓ │   │   ● AI / ML   Not Addressed  ⚠    │
│   │ ▓▓▓ clause ▓▓▓▓▓▓▓▓▓▓ │   │   ● Destruction  Conditional  p.2 │
│   └───────────────────────┘   │     "Licensee shall delete any…"  │
│        page 2 / 12            │     [Accept] [Correct] [Reject]   │
└───────────────────────────────┴────────────────────────────────────┘
```

**Behavior**
- Loads PDF bytes (source A/B/C above); renders with **pdf.js** (canvas + text layer)
- Loads findings for the contract via the generated `vz_finding` service (filter on contract id; join checklist item for label, group, definition, sort order)
- **Click a finding** → scroll to page → draw translucent highlight over each polygon (convert inches × 72 → PDF points → viewport scale) → brief pulse animation
- Chips: Found (green) · Unclear (amber) · Not Found (grey) · Prohibited (red) · Conditional (amber) · Permitted (green)
- Confidence pill; hover tooltip shows checklist **definition**
- **Accept / Correct / Reject** → update the finding via the generated service (Correct opens inline editor for value + judgment + notes); completeness bar updates live
- Filter toggle: *All · Needs attention (Unclear + Not Found + Pending)*
- Keyboard: ↑/↓ moves between findings (demo flex)

**Tech:** React + Vite + TypeScript strict, Fluent UI v9, `pdfjs-dist` (set `GlobalWorkerOptions.workerSrc` via Vite `?url` import).
**Highlight fallbacks:** (1) no polygons from CU → search the quote in the pdf.js text layer and highlight matches; (2) still slipping → jump-to-page + quote panel.

---

## 7. Repo structure

```
vizient-contract-poc/
├── plan.md                              ← this file
├── checklist/checklist.json             ← single source of truth (20 items)
├── analyzer/
│   ├── build_schema.py                  ← checklist.json → analyzer JSON
│   ├── vizient-contract-checklist.json  ← generated
│   └── deploy_analyzer.py               ← PUT analyzer
├── function/                            ← Azure Function (Python)
│   ├── function_app.py
│   ├── cu_client.py                     ← analyze + poll
│   ├── mapping.py                       ← fields → findings, source parsing, presence
│   └── requirements.txt
├── dataverse/
│   ├── schema.md                        ← tables above
│   └── solution/                        ← pac solution clone/unpack output
├── contract-review/                     ← Power Apps Code App (React + Vite)
├── scripts/
│   ├── seed-checklist.py
│   └── run-local.py                     ← analyze a local PDF → print findings table
├── eval/
│   ├── gold/bluepine-sow.json           ← synthetic (Appendix B)
│   ├── gold/bluepine-amendment.json
│   └── score.py                         ← compares results vs gold → accuracy report
├── infra/main.bicep                     ← Foundry, Function App, RBAC
├── samples/                             ← test PDFs (do NOT commit real contracts)
└── tests/
```

---

## 8. Build phases (with done criteria)

### Friday schedule (Wed 2026-10-21 evening → Fri 2026-10-23 AM)

| When | Phase | Done when… | Go / no-go |
|---|---|---|---|
| **Wed eve** | **0 · Setup** — repo, MCP servers (Learn, Azure, Dataverse, Agent Flow), `infra/main.bicep`, `azd up`, Power Platform solution `VizientContractPOC` | Resources deployed; solution exists | **Code Apps enabled** + Premium/trial; `pac code` works |
| **Wed eve** | **1 · Analyzer** — `checklist.json`, `build_schema.py`, deploy, `run-local.py` on the SOW (contract pages only) | Table of 20 items with value, page, **polygon**, confidence | **No polygons → highlight via quote search in pdf.js** |
| **Wed late** | **3 · Dataverse** — 3 tables, seed 20 checklist rows, app user | Tables + seed visible in maker portal | |
| **Thu AM** | **2 · Function** — analyze → map → presence → write Contract + 20 Findings | Function call creates rows for the SOW | |
| **Thu AM** | **4 · Flow** (Agent Flow MCP) — SharePoint drop → create Contract + upload PDF to file column → call Function → status Ready | Drop SOW → 20 findings, < 3 min | |
| **Wed late** | **5a · Code App skeleton** — `pac code init`, data sources, list screen, `pac code push`; prove PDF bytes load (source A/B/C) | App opens in Power Apps and lists contracts; a PDF renders | **PDF won't load by Thu 10:00 → source C (Blob SAS)** |
| **Thu PM** | **5b · Evidence Viewer** — PDF ◀▶ findings, click-to-highlight, Accept/Correct, completeness, Approve | Click *Destruction Requirements* → clause lights up | **No highlight by 16:00 → quote-search / jump-to-page fallback** |
| **Thu night** | **6 · Polish + demo** — Amendment + Parent link, chips/colors, `score.py` quick run vs Appendix B, **record backup video** | Two clean dry runs | |
| **Fri AM** | Final dry run | | |

> Keep the demo PDFs to the contract pages only (a signed copy can include e-signature certificate and disclosure pages).

---

## 9. POC Lite success criteria

### Added phase 7: record-scoped Foundry Q&A (requested 2026-10-23)

Add an **Ask this contract** entry point without changing the existing review screen's behavior.
A Foundry prompt agent searches only the full extracted text of the open synthetic contract, in an isolated,
content-versioned file-search index. No parent or cross-contract retrieval. Switching contracts starts a fresh chat.
Transport uses a user-owned question table and a separate cloud flow inside VizientContractPOC, with generated
Code App data services. The browser reads extraction with the user's permissions; the flow never fetches document
text as its connection owner. Original findings and reviewer values are never written by Q&A.

**Done when:** a synthetic question completes through the deployed question flow; answers include verified verbatim
quotes and page links, silence produces Not Addressed, wrong-contract index/response reuse is rejected, the existing
Code App gates pass, and verify-solution.py exits 0. No signed/user-uploaded contract is read or indexed by this build.

### Added phase 8: ingestion-time Azure AI Search (requested 2026-10-23)

Supersedes phase 7's on-demand File Search indexing. Preserve complete synthetic document text separately from
the reduced raw debugging output. Queue a separate solution-owned indexing flow during ingestion. Use a shared
Basic Azure AI Search index, page-local chunks, embeddings and hybrid retrieval with mandatory server-side
contract/content-version filters. Foundry answers only from the retrieved document passages; citations must match
both those passages and the original page. Never derive document answers from checklist fields.

Keep Q&A indexing readiness/errors separate from review readiness. Disable questions until indexing completes;
retrying indexing must not reset review work. Superseded 2026-10-23: the owner later approved re-extracting existing
contracts and indexing real documents (see the follow-up below).
Versioned Search chunks persist until explicit purge; automated deletion/retention and non-admin permission
testing are prerequisites before expanding beyond this synthetic POC.

**Done when:** ARM validation and all app/Python gates pass; user approves continuously billed Search provisioning;
complete synthetic extraction reaches Search during ingestion; a duration question returns verified page evidence;
missing text fails Q&A indexing without failing review; version/contract isolation is tested; solution verification
and export refresh pass. No phase completion claim until live synthetic ingestion and Q&A pass.

**Phase 8 follow-up (2026-10-23, owner decision):** the synthetic-only restriction on Q&A was lifted with the Function
setting `ALLOW_REAL_CONTRACTS=true`. All 7 existing contracts had their findings discarded and were re-extracted; each
now has 20 findings, a recorded index version and Search readiness (141 chunks, no stale or orphaned chunks). The run
found and fixed three defects: a size cap applied to the raw extraction instead of the stored page text, page markers
that disagree with the page count (now split by page spans), and embedding rate limits (now a bounded retry). Added
`scripts/reextract-contracts.py` and `scripts/purge-contract-index.py`. Answers on real contracts were not read or
evaluated here. Retention policy, legal/security review and non-admin permission tests remain open.

**Phase 8 follow-up 2 (2026-10-23):** a real signed contract returned "did not return verifiable page evidence".
Cause: on table-heavy pages the model stitched table cells into a quote that is not in the document. Fixed by giving
the model a plain-text rendering (one table row per line, cells separated by ` | `), matching quotes on letters and
digits across cell/tag boundaries (still requiring the passage in both the retrieved evidence and the original page),
stricter quoting instructions (agent version 5), and one bound automatic retry per question. Verified 12 of 12
replays on two real contracts (counts only; no answer text read). Invented quotes are still rejected.

**Phase 8 verified (2026-10-23):** approved Search provisioning completed in East US after the East US 2 capacity
failure. A freshly generated synthetic PDF passed deployed extraction, independent indexing and a seven-year
duration answer with a verbatim page-1 citation. Agent version 4 returned conservative Not Addressed for an
unsupported subject. All 520 Python tests and 181 frontend tests passed, along with TypeScript, lint and build.
The readiness-aware Code App was published inside VizientContractPOC; solution verification, export refresh and
leak/whitespace checks passed. Existing user-uploaded documents were not read or backfilled. Browser interaction,
real-contract accuracy and non-admin permission tests are not claimed.

| # | Criterion | Target |
|---|---|---|
| 1 | Contracts processed end-to-end from SharePoint drop (incl. 1 scanned PDF) | 100% |
| 2 | Contract-detail accuracy vs. gold | ≥ 90% |
| 3 | Rights judgment agreement vs. gold | ≥ 85% (≥ 95% on Prohibited) |
| 4 | Every "Found" item has a clause + page | 100% |
| 5 | "Found" asserted where the contract is silent | 0 |
| 6 | Click-to-highlight lands on the correct clause | ≥ 90% of Found items |
| 7 | Reviewer time to verify one contract | ≤ 10 min |
| 8 | Drop-to-ready processing time | ≤ 3 min |

---

## 10. Demo script (the wow moments)

1. **"Here's how it works today"** — open a long contract PDF. *"Is AI/ML use allowed? Somebody reads this for an hour."*
2. **Drop it** into SharePoint Contract Intake. Talk for ~90 seconds about the architecture.
3. **Watch the Code App** — the contract appears on its own (auto-refresh), flips to *Ready for Review*, **Completeness 14/20**.
4. **Click "Destruction Requirements"** → PDF jumps to page 2, clause **lights up**: destroy proprietary identifiers, linkages and appended data. ✨
5. **Click "AI / Machine Learning"** → **Not Addressed**. *"It didn't guess. It's telling Legal: this SOW is silent — check the MSA."*
6. Point to the **Parent Agreement** flag: *"It found the reference to the master agreement — which isn't in the repository. That's a gap Vizient didn't know it had."*
7. **Correct** one value → completeness updates; *"every correction is measured — that's your accuracy number."*
8. Drop the **amendment**, link it to the SOW with Parent Contract. Close with the MVP path.

---

## 11. Prereqs checklist

- [ ] Azure subscription in demo tenant; Foundry resource in a Content Understanding-supported US region; default model deployments configured
- [ ] Function App (Python 3.11) + managed identity with *Cognitive Services User*
- [ ] Power Platform DEV environment with Dataverse; Power Apps Premium/trial for reviewers
- [x] SharePoint site + **Contract Intake** document library
- [ ] VS Code: GitHub Copilot (Agent mode), Azure Functions ext., Power Platform Tools ext., PAC CLI, Node LTS (Code App), Python 3.11; Power Apps **Code Apps enabled** on the DEV environment
- [ ] **Data handling:** confirm real Vizient contracts may be processed in the Microsoft demo tenant. If not → build on **synthetic contracts** modeled on a real SOW and run real ones later in Vizient's tenant
- [ ] `samples/` is git-ignored

---

## Appendix A — Working agreement for the coding assistant (starter)

```markdown
# Copilot instructions — Vizient Contract POC Lite

## Context
POC that extracts a 20-item checklist from contract PDFs with Azure AI Content Understanding,
stores findings in Dataverse, and reviews them in a Power Apps Code App (React + Vite + pdf.js) with a side-by-side evidence viewer.
Read plan.md before any task. Work one phase at a time; stop at each phase's "done when" and report.

## Non-negotiables
- checklist/checklist.json is the single source of truth. Never hard-code checklist items elsewhere.
- A finding is "Found" only if it has a clause/value AND grounding. Never infer rights from silence.
- Never overwrite AI values; reviewer edits go to vz_reviewer* columns.
- Do not commit contracts, keys, or tenant IDs. Use env vars / local.settings.json (git-ignored).
- Dataverse prefix: vz_. Solution: VizientContractPOC.

## Stack & style
- Python 3.11, type hints, small pure functions; mapping logic unit-tested with saved JSON fixtures.
- Azure: managed identity (DefaultAzureCredential) preferred; Bicep for infra.
- Code App: React + Vite + TypeScript strict, Fluent UI v9, pdfjs-dist. Use only the services generated by
  `pac code add-data-source` for Dataverse/SharePoint; never call Dataverse with hand-rolled tokens from the browser.
- Before calling any Azure API, check the current Content Understanding REST docs for the GA api-version
  and request/response shape; do not guess field names.

## Definition of done for any change
- Tests pass (pytest / npm test). eval/score.py does not regress.
- README section updated if a command or setting changed.
```

---

## Appendix B — Gold labels (starter, to be confirmed by Vizient Data Governance)

The starter labels were taken from two signed contracts, a Statement of Work and its Amendment. Those values are real contract data, so they are **not kept in this repository**: they stay in the local, git-ignored `vizient-contract-poc-lite-plan.original.md`. The committed gold labels cover three synthetic contracts (`eval/gold/bluepine-sow.json`, `bluepine-amendment.json`, `tessera-dua.json`), written by `eval/generate_contracts.py` next to the PDFs.

### Label shape
One entry per checklist item (20 in all):

| Group | Keys | Expected label |
|---|---|---|
| Contract details (9) | Vendor, VizientEntity, DocumentType, ContractIdentifier, EffectiveDate, ExpirationDate, RenewalTermination, Signatories, ParentAgreementReference | `value` (empty when the contract is silent), plus the supporting `page` and `quote` |
| Data rights (11) | Right_InternalAnalytics, Right_AIML, Right_ProductDevelopment, Right_BAARequired, Right_Retention, Right_AffiliateSharing, Right_ThirdPartySharing, Right_DataLinking, Right_DeIdentification, Right_Destruction, Right_Geographic | `judgment` (Permitted, Prohibited, Conditional or Not Addressed), plus `page`, `quote` and an optional `alsoAcceptable` list |

> Gold files in `eval/gold/*.json` use `{ "key": { "value": "...", "page": 1, "quote": "..." } }` for a detail and `{ "key": { "judgment": "...", "page": 1, "quote": "..." } }` for a right. `score.py` uses fuzzy match for text (token-set ratio ≥ 85), exact match for dates/enums/judgments.

---

## Appendix C — Open items
- [x] Confirm Content Understanding grounding (page + polygon) for nested object fields (Day 1) — resolved
- [ ] Vizient to validate checklist definitions + gold labels (send `checklist/checklist.json` and the labels in `eval/gold/` to Data Governance)
- [ ] Obtain the master agreement the SOW cites (optional — enables a 3-document hierarchy demo)
- [ ] Decide: demo on real vs. synthetic contracts in Microsoft tenant
