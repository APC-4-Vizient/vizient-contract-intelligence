/*
  The words around the diagram on the "How it works" page. Kept as data, with the diagram's own copy in
  architecture.ts, so one test can check every string that reaches the screen for identifiers, hosts and accounts.
*/

export const HOW_IT_WORKS_TITLE = 'From a PDF in a folder to evidence you can click';

export const HOW_IT_WORKS_LEAD =
  'Contracts arrive as PDFs. This system reads each one against a 20-item checklist, shows every answer beside the exact passage it came from, and leaves the decision to a person. Follow a contract through it below, or click any part to see what it does.';

export const BIG_PICTURE: readonly string[] = [
  'Nine of the twenty questions are about the contract itself (who the parties are, the dates, the renewal and termination terms) and eleven are about data rights, such as whether the vendor may use the data for analytics, share it with third parties or move it offshore.',
  'For each question the AI returns an answer, a confidence and the proof: the quote, the page and the box on the page. The reviewer sees the answer and the evidence side by side, which turns reading a contract into checking one.',
  'The pieces are deliberately ordinary. A SharePoint folder, two Power Automate flows, three Dataverse tables, one small Azure Function, one Content Understanding analyzer and one Code App. None of them is clever on its own; the value is in how cleanly they hand work to each other.',
];

export interface DesignChoice {
  title: string;
  text: string;
}

export const DESIGN_CHOICES: readonly DesignChoice[] = [
  {
    title: 'Two small flows, not one big one',
    text: 'Intake only creates the record. Analysis only does the analysis. Each is easy to read, test and re-run, and the Extracting status doubles as the retry queue.',
  },
  {
    title: 'Every answer shows its proof',
    text: 'A finding carries the quote, the page and the box it came from, so a reviewer verifies it in a click instead of searching the PDF.',
  },
  {
    title: 'No AI keys anywhere',
    text: 'The Function reaches Content Understanding with a managed identity and a least-privilege role, and key access on the AI account is switched off.',
  },
  {
    title: 'One solution, one unit',
    text: 'The tables, both flows, their connection references, the environment variables and the Code App live in a single Dataverse solution, so they move between environments together.',
  },
  {
    title: 'Infrastructure as code',
    text: 'The Azure side is described in Bicep and deployed with azd, so the environment can be rebuilt from the repository.',
  },
  {
    title: 'The AI proposes, a person decides',
    text: 'Nothing is final until a reviewer approves it. Approving locks the findings, and every decision is time-stamped.',
  },
];

export interface Placement {
  piece: string;
  lives: string;
  builtWith: string;
}

export const WHERE_IT_LIVES: readonly Placement[] = [
  { piece: 'Intake folder', lives: 'SharePoint', builtWith: 'Microsoft 365' },
  { piece: 'Intake and Analysis flows', lives: 'The Dataverse solution', builtWith: 'Power Automate' },
  { piece: 'Contracts, findings and checklist', lives: 'The Dataverse solution (3 tables)', builtWith: 'Dataverse' },
  { piece: 'Review app', lives: 'The Dataverse solution', builtWith: 'Power Apps Code App (React and Fluent UI)' },
  { piece: 'Analysis API', lives: 'Azure', builtWith: 'Azure Functions, Flex Consumption, Python 3.12' },
  {
    piece: 'The reader',
    lives: 'Azure',
    builtWith: 'Content Understanding custom analyzer (GA API 2025-11-01) with a swappable gpt-5.5 alias',
  },
  { piece: 'Azure infrastructure', lives: 'Azure, East US 2', builtWith: 'Bicep and azd' },
];

export const GUARDRAILS: readonly string[] = [
  'Size: the flows analyze PDFs under 4 MiB, because the Dataverse connector reads files in 4 MiB ranges. The Function itself accepts up to 32 MiB. A file of 4 MiB or larger ends as Failed with a message that says so.',
  'Accuracy: on the made-up contracts used for testing, 97% of data-rights answers and 100% of contract details matched the labels. Answers can differ slightly between runs, which is why a person reviews every finding.',
  'Not tested yet: scanned, image-only PDFs.',
  'Access: a custom security role for reviewers is still to do. For now an admin grants access to the tables and shares the app.',
  'Anything dropped into the intake folder goes through the same pipeline, so choose what goes in on purpose.',
];

export const CHECKLIST_NOTE =
  'The AI answers the first two groups. The two manual fields are filled in by a reviewer.';
