# Vizient Contract Review

The reviewer's screen for the contract pipeline. A Power Apps Code App (React 19, Vite, strict TypeScript,
Fluent UI v9, pdf.js) that reads and writes the `vz_contract`, `vz_finding` and `vz_checklistitem` tables in
Dataverse. It is desktop-first and uses the vizient.com theme (`src/theme/`).

## What a reviewer does

- **Contracts:** every contract, newest first, with its status (Received, Extracting, Ready for Review,
  In Review, Approved or Failed), vendor, document type and how many of the 20 answers were found.
- **Review:** the PDF on one side and the 20 checklist answers on the other (9 contract details, 11 data
  rights). Selecting an answer scrolls the PDF to its source and marks the passage.
- **Per answer:** Accept, Correct (type the right value) or Reject. A "Not found" answer is confirmed with
  **Confirm not found**. A reviewed answer can be reset to Pending.
- **Needs attention:** the answers nobody has reviewed that the AI marked Unclear or Not Found. **Accept all
  confident** accepts every pending answer the AI found with high confidence, after a confirmation.
- **Approve:** locks the findings (read-only) and sets the contract to Approved. **Reopen review** undoes it.
- **Details:** the contract's number, type, Vizient entity, dates and source file, plus the editable parent
  contract, contract owner and legal reviewer. See "Parent agreements" below.
- **Ask this contract:** an additive Foundry chat drawer for ready contracts. It searches only the open contract's
  full extracted text, cites verified page quotes, and can open them in the existing PDF viewer. It never changes
  findings or reviewer decisions. Conversation stays with the open record and resets on navigation/re-extraction.
  Real contracts are accepted while the Function setting `ALLOW_REAL_CONTRACTS=true` is on; mock mode explicitly refuses to simulate answers.
  See the root README for the agent, indexing, solution-owned question flow and deployment commands.
  Q&A readiness is separate from review readiness. Ingestion indexes full page-grounded document text in Azure AI
  Search; the button stays disabled while Not Indexed/Queued/Failed, with an explicit indexing status/error.
  Questions use `vz_documenttext`, never the reduced `vz_rawresult` debugging snapshot.

The review writes the status, the found count and the completeness back to the contract as the reviewer works.

### About pages

Two read-only pages sit beside the review screens in the header (`src/about/`, routes `#/how-it-works` and `#/cost`).

- **How it works:** an animated 3D diagram of the pipeline (SharePoint, the two flows, Dataverse, the Azure Function,
  Content Understanding, this app and the reviewer). **Follow a contract** plays a document through the eight steps;
  the step cards, the dots and the arrows jump to one step; clicking a part opens what it does. A clock under the
  caption shows how far into the processing the current step falls (the chips choose which timed run it follows), and
  the step cards carry a "Measured" line and a "Cost" line where one applies. The explanation sits under the diagram,
  with **How long does it take?** and **What does it cost?** sections. The zones, parts, links and steps all come from
  one file, `architecture.ts`, so the 3D scene, the flat fallback and the written steps cannot drift apart.
- **Time and cost:** two sections measure the pipeline itself: **Time to process one contract** (three timed
  end-to-end runs; a person's review is not counted) and **Cost to process one contract** (recorded usage times public
  list prices, for three synthetic samples). See "Refreshing the time and per-document figures" below.

The scene is plain Three.js (`src/about/scene/`). It loads only when the page opens, as its own chunk (about 600 kB,
157 kB gzipped), so the contract list does not pay for it. Where WebGL is unavailable, the page shows a flat diagram
with the same steps and details. Parts are real buttons with a visible focus ring. The camera moves, pulses and
particles start off for people who ask their system for reduced motion; the **Motion** button turns them on. The scene
draws everything in code (no images, fetches or workers), so it runs under the Code App content security policy.

The same diagram is also built as a page of its own, `..\docs\architecture-3d.html`; see "The standalone 3D page" below.

### Evidence marking

The service returns one box per line of text, so the viewer groups neighbouring lines into passages and marks
each as one unit. The **Marker** (margin bar and underline), **Box** (outline) and **Highlight** (soft
highlighter, the default) choices sit in the PDF toolbar and are remembered in the browser
(`vz-evidence-style`). Every style flashes the passage briefly when it is selected; the flash is off for people
who ask their system for reduced motion.

### Parent agreements

A SOW or amendment cites the agreement it belongs to. The **Details** drawer shows what the contract says, and
when exactly one contract in the repository matches the cited number it offers **Link to this contract**. The match
(`src/domain/parents.ts`) scores an identifier equal to the number above an identifier that contains it above a file
name that contains it, ignores the contract itself and its descendants, and uses the kind of agreement the
reference names (SOW, MSA, Amendment...) to break a tie between equal numbers. Nothing is linked without a click. A SOW
shows its amendments under **Linked documents**.

## Run it

```powershell
npm ci
npm run dev:mock    # in-memory data plus the synthetic PDFs and saved results from ..\samples; needs no Power Platform
npm run dev         # real data source; needs the Power Apps host (see `pa app run`)
npm run lint
npm test            # Vitest, pure functions only
npm run build       # tsc -b && vite build, into dist\
npm run build:standalone   # writes ..\docs\architecture-3d.html, the 3D diagram as one page; needs no Power Platform
```

`dev:mock` is available only on the dev server. A production build contains none of the mock code. Generate
the synthetic contracts first with `python ..\eval\generate_contracts.py`, then analyze them with
`python ..\scripts\run-local.py` (see the root README).

## Layout

| Path | What it holds |
|------|---------------|
| `src/data/` | The repository the screens use: `dataverseRepo.ts` (real), `mockRepo.ts` (dev only), `mappers.ts`, `choices.ts` |
| `src/domain/` | Pure rules: completeness, findings, display values, parent matching, region geometry. Unit tested |
| `src/hooks/` | Data loading, review actions and the hash router |
| `src/pdf/` | pdf.js wrapper, page rendering, quote search, the evidence marks |
| `src/screens/` | The contract list, the review screen, the findings panel, the details drawer |
| `src/about/` | The "How it works" and "Time and cost" pages: `architecture.ts` (the single source for the diagram), `scene/` (Three.js engine), `processingTime.ts` and `processingCost.ts` (time and cost per contract), `howItWorksCopy.ts` (the explanation) |
| `src/theme/` | The Fluent theme and the vizient.com CSS variables |
| `src/standalone/` | The page around the diagram in the standalone 3D page (`StandalonePage.tsx`, its copy and styles), and `inlineHtml.ts`, which puts the built script and styles inside that page |
| `src/generated/` | Typed Dataverse services written by the Power Apps CLI. Do not edit |
| `standalone.html`, `vite.standalone.config.ts` | The entry and the build of the standalone 3D page |
| `vite.fixtures.ts` | Dev-server middleware that serves `..\samples` in mock mode |

## Data source and deployment

`src/generated/` comes from `pa app add data-source --connector dataverse --table <table>`. After a schema
change, run `pa app refresh data-source`. `power.config.json` and `.power/` are written by `pa app init`. They hold
the environment, so they are git-ignored.

```powershell
npm run build
pa app push --solution-id <id of VizientContractPOC>   # never push without the solution id
pa app share --principal <email>                       # give a person the right to open the app
```

The push adds the app to the solution. The unpacked folder `..\dataverse\solution\` leaves out the app package (it is
git-ignored), so it cannot be packed back into a solution. The importable file `..\dataverse\VizientContractPOC_unmanaged.zip`
does carry the package, but importing it into a second environment has not been tried, so publish the app with
`pa app push` (deployment runbook 5.8 and 5.10).

Code Apps run under a strict content security policy, so the viewer does not use Web Workers or fetches: pdf.js runs
its worker on the main thread (`src/pdf/pdfjs.ts`) and the PDF is read through the Dataverse data source.

## The standalone 3D page

`..\docs\architecture-3d.html` is the "How it works" diagram as a page of its own: the same interactive 3D view and step
list, in one HTML file with its code and styles inside. It opens from a folder, a download or an attachment, needs no server,
sign-in or network, and is not part of the Power Platform solution. It covers the review path only, as the app's page does;
the Ask this contract path is in `..\docs\architecture.md`. SharePoint Online downloads an HTML file from a document library
instead of showing it ([Microsoft Learn](https://learn.microsoft.com/sharepointmigration/migration-assessment-scan-browser-file-handling)),
so share the file itself, or put it on a static web host such as an Azure Storage static website.

```powershell
npm ci
npm run build:standalone    # writes ..\docs\architecture-3d.html (about 0.9 MB)
```

- The page reads no data, so the build needs neither `pa app init` nor a sign-in, and it never writes to `dist\`.
- `standalone.html` and `src/standalone/` hold the page around the diagram. The diagram, the step list and the scene are the
  app's own files in `src/about/`, so the page and the app show the same thing. `vite.standalone.config.ts` bundles it, and
  `src/standalone/inlineHtml.ts` puts the script and styles inside the page; the build stops if anything is left to fetch.
- The page records every source it was built from, with each file's hash, in a `build-info` block. After a change to the
  diagram's text, parts or scene, rebuild and commit the page: `tests/test_architecture_page.py` fails while it is stale. The
  same test checks that the numbers the diagram states (tables, columns, flow actions, size limits, the checklist and the
  statuses) still match `dataverse/schema.json`, `scripts/flowlib.py` and the Function.
- Where WebGL is unavailable, the page shows the flat diagram, as the app does.

## Refreshing the time and per-document figures

`processingTime.ts` and `processingCost.ts` are snapshots of the live system. Nothing in them is simulated, and the
pages say where each number came from. The dollar figures are estimates at public list prices, not an invoice.

**Time to process one contract** (`PROCESSING`). The clock starts when the PDF is saved in the SharePoint intake folder
and stops when the Analysis flow sets the status to Ready for Review; a person's review is not counted. To add a run,
put a document through and read three sources:

- the file's saved time in SharePoint, which is the start (to the second),
- the run history of both flows, through the Power Automate flow API (when each run started and ended),
- the Azure Function's own log in Application Insights (when it took the document and when the result was read).

Pair the Intake run with its Analysis run by the contract's id, not by time. Split the total into the six stages at the
points those sources agree on and paste the seconds into `PROCESSING`. `npm test` checks that the stages add up and that
the copy claims nothing the measurements cannot back up (for example, how often a flow looks for a new file).

**Cost per document** (`SAMPLES`, `RATES`). Every Content Understanding result has a `usage` block: the pages read, the
context tokens, and the model's input, cached-input and output tokens. The Analysis flow stores the result on the
contract record (`vz_rawresult`), so analyse a sample and copy its numbers into `SAMPLES`. Each quantity times its list
price is the document's cost; re-read the prices (the Azure Retail Prices API and Microsoft Learn) into `RATES` and
`PRICED_ON`. Pages and context tokens are billed by Content Understanding, the model tokens by the model deployment.
Only synthetic samples belong in `SAMPLES`. The Azure Function (Application Insights calls and GB-seconds) and the flows
(actions) are measured on the page but kept out of the dollar total: the Function is under 1% of it, and flow actions
draw on a license allowance rather than a per-document charge.

Left out of every figure: a person's review, Power Platform licenses, storage of the PDF and the results, monitoring,
discounts and tax. Content Understanding lists cached input separately without saying whether it is already inside the
input count, so each is priced at its own rate and the estimate may run a few cents high.

## Lockfile

`.npmrc` sets `omit-lockfile-registry-resolved=true`, so `package-lock.json` keeps its integrity hashes but no
registry host. It then installs from whichever registry the machine uses: public npm or an internal mirror.
Configure a mirror in your user-level npm configuration, not in this repository.
