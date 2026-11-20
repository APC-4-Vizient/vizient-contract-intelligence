/*
  The map behind the "How it works" page: what the parts are, how a contract moves through them and where each part
  sits in the 3D view. The 3D scene, the labels, the step cards and the flat fallback all read this one file, so they
  cannot drift apart. Everything here is shown on screen, so it holds no identifiers, hosts or accounts.

  Coordinates are world units: x runs left to right, y up and z toward the viewer.
*/

export type Vec3 = readonly [x: number, y: number, z: number];

export type ZoneId = 'm365' | 'power-platform' | 'azure' | 'people';

export type NodeId =
  | 'sharepoint'
  | 'flow-intake'
  | 'dataverse'
  | 'flow-analysis'
  | 'function'
  | 'analyzer'
  | 'code-app'
  | 'reviewer';

export type EdgeId = 'intake' | 'record' | 'trigger' | 'submit' | 'read' | 'results' | 'review' | 'decide';

export type NodeKind = 'library' | 'flow' | 'flow-double' | 'tables' | 'bolt' | 'analyzer' | 'monitor' | 'person';

export interface ZoneSlab {
  x: number;
  z: number;
  width: number;
  depth: number;
}

export interface ArchZone {
  id: ZoneId;
  label: string;
  color: string;
  slabs: readonly ZoneSlab[];
  /** Where the zone's name is printed on the floor: [x, z]. */
  labelAt: readonly [x: number, z: number];
}

export interface ArchNode {
  id: NodeId;
  kind: NodeKind;
  zone: ZoneId;
  /** Short name used on the label. */
  label: string;
  /** The second line of the label. */
  kicker: string;
  /** Full name, used in the detail panel. */
  title: string;
  color: string;
  position: Vec3;
  /** Height of the label's anchor above the floor. */
  labelY: number;
  summary: string;
  bullets: readonly string[];
}

/** A point on an edge's route, given relative to a node so that moving a node carries its edges with it. */
export interface Waypoint {
  at: NodeId;
  offset: Vec3;
}

export type EdgeTone = 'forward' | 'return' | 'review';

export interface ArchEdge {
  id: EdgeId;
  from: NodeId;
  to: NodeId;
  tone: EdgeTone;
  /** The pill shown on the edge while it is lit. */
  caption: string;
  /** Slides the pill off the line, in world units, when a node's label would otherwise sit on it. */
  captionOffset?: Vec3;
  bidirectional: boolean;
  route: readonly Waypoint[];
}

export interface Hop {
  edge: EdgeId;
  reverse?: boolean;
}

export interface ArchStep {
  id: string;
  title: string;
  /** One or two sentences: shown on the diagram and on the step card. */
  text: string;
  /** What is really happening: shown on the step card. */
  detail: string;
  focus: readonly NodeId[];
  /** Edges that light up during the step. */
  edges: readonly EdgeId[];
  /** The path the contract token follows, in order. */
  travel: readonly Hop[];
  /** The token drops into this node from above instead of travelling. */
  enter?: NodeId;
  /** The contract's status at this point; the chip over Dataverse shows it. */
  status?: string;
  effect?: 'scan' | 'findings';
}

export const ZONES: readonly ArchZone[] = [
  { id: 'm365', label: 'Microsoft 365', color: '#5c9bd0', slabs: [{ x: -12.6, z: 0, width: 5.4, depth: 7 }], labelAt: [-15.1, 3.15] },
  {
    id: 'power-platform',
    label: 'Power Platform',
    color: '#f67318',
    slabs: [
      { x: -2.5, z: 0, width: 14.6, depth: 7 },
      { x: -2.5, z: 7.5, width: 5.4, depth: 4.6 },
    ],
    labelAt: [-9.6, 3.15],
  },
  { id: 'azure', label: 'Azure', color: '#2fb585', slabs: [{ x: 10.1, z: 0, width: 10.4, depth: 7 }], labelAt: [13.7, 3.15] },
  { id: 'people', label: 'People', color: '#ffcc12', slabs: [{ x: 2.5, z: 7.5, width: 3.9, depth: 4.6 }], labelAt: [0.7, 9.45] },
];

export const NODES: readonly ArchNode[] = [
  {
    id: 'sharepoint',
    kind: 'library',
    zone: 'm365',
    label: 'SharePoint',
    kicker: 'Contract Intake folder',
    title: 'SharePoint: the Contract Intake folder',
    color: '#7fb6e0',
    position: [-12.5, 0, 0],
    labelY: 2.9,
    summary: 'Where a contract starts. A PDF placed in the Contract Intake folder is the only step a person has to take.',
    bullets: [
      'The folder is the front door: any PDF dropped in goes through the same pipeline.',
      'Nothing is copied by hand. The Intake flow does the rest.',
    ],
  },
  {
    id: 'flow-intake',
    kind: 'flow',
    zone: 'power-platform',
    label: 'Intake flow',
    kicker: 'Power Automate',
    title: 'Contract Intake (cloud flow)',
    color: '#f67318',
    position: [-7.5, 0, 0],
    labelY: 2.9,
    summary: 'Notices the new file, creates the contract in Dataverse and hands it on by setting its status to Extracting.',
    bullets: [
      'Starts by itself with a polling trigger on the folder.',
      'Creates the contract row and copies the PDF into its document column.',
      '12 actions. Setting the status to Extracting is the hand-off to the next flow.',
    ],
  },
  {
    id: 'dataverse',
    kind: 'tables',
    zone: 'power-platform',
    label: 'Dataverse',
    kicker: '4 tables',
    title: 'Dataverse: the system of record',
    color: '#fefcf8',
    position: [-2.5, 0, 0],
    labelY: 3.0,
    summary: 'Holds the contracts, the checklist and every answer the AI finds, each with its evidence and its review status.',
    bullets: [
      'Four tables: contracts, findings, checklist items and the questions asked of a contract (57 columns in all).',
      'The contract status moves Received, Extracting, Ready for Review, In Review, Approved, or Failed.',
      'Everything lives in one solution, so it travels between environments as a unit.',
    ],
  },
  {
    id: 'flow-analysis',
    kind: 'flow-double',
    zone: 'power-platform',
    label: 'Analysis flow',
    kicker: 'Power Automate',
    title: 'Contract Analysis (cloud flow)',
    color: '#f67318',
    position: [2.5, 0, 0],
    labelY: 2.9,
    summary: 'Wakes when a contract becomes Extracting, sends the PDF to the Azure Function and writes the answers back.',
    bullets: [
      'Triggered by Dataverse the moment the status becomes Extracting.',
      'Calls the Function over HTTP, then polls until the analysis finishes.',
      '32 actions with Try and Catch scopes: a failure ends as Failed, with the reason recorded.',
    ],
  },
  {
    id: 'function',
    kind: 'bolt',
    zone: 'azure',
    label: 'Azure Function',
    kicker: 'Python 3.12',
    title: 'Azure Function: the analysis API',
    color: '#ffcc12',
    position: [7.5, 0, 0],
    labelY: 3.2,
    summary: 'A small API that keeps the AI plumbing out of Power Platform: it takes a PDF and gives back structured answers.',
    bullets: [
      'Flex Consumption plan. POST starts an analysis and returns 202 with an operation id; GET returns 200 when it is done.',
      'Reaches the analyzer with a managed identity. There are no AI keys to store or rotate.',
      'Accepts PDFs up to 32 MiB. The flows send files under 4 MiB.',
    ],
  },
  {
    id: 'analyzer',
    kind: 'analyzer',
    zone: 'azure',
    label: 'Content Understanding',
    kicker: 'Azure AI',
    title: 'Azure Content Understanding: the reader',
    color: '#58d6a8',
    position: [12.5, 0, 0],
    labelY: 3.9,
    summary: 'A custom analyzer reads the whole PDF against the 20-item checklist and returns each answer with its proof.',
    bullets: [
      'Every answer carries the exact quote, the page and the box on the page, which powers click-to-highlight.',
      'Uses a gpt-5.5 model through an alias, so the model can be swapped without touching the pipeline.',
      'Key access on the AI account is switched off: it accepts Microsoft Entra sign-in only.',
    ],
  },
  {
    id: 'code-app',
    kind: 'monitor',
    zone: 'power-platform',
    label: 'Code App',
    kicker: 'Power Apps',
    title: 'Contract Review (Power Apps Code App)',
    color: '#ff8a3d',
    position: [-2.5, 0, 7.5],
    labelY: 3.35,
    summary: 'Where a person reviews. Findings sit beside the PDF, and clicking one lights up its evidence on the page.',
    bullets: [
      'Accept, correct, reject or reopen each finding. Approve locks them and sets the status to Approved.',
      'A Needs attention tab, and one click to accept everything the AI is confident about.',
      'Suggests a contract’s parent agreement and links it in one click.',
    ],
  },
  {
    id: 'reviewer',
    kind: 'person',
    zone: 'people',
    label: 'Reviewer',
    kicker: 'Human decision',
    title: 'The reviewer: a person in the loop',
    color: '#ffcc12',
    position: [2.5, 0, 7.5],
    labelY: 3.0,
    summary: 'The AI proposes and a person decides. Nothing is final until someone approves it.',
    bullets: [
      'Reads the evidence, not just the answer.',
      'Each review decision is time-stamped on the finding.',
    ],
  },
];

export const EDGES: readonly ArchEdge[] = [
  {
    id: 'intake',
    from: 'sharepoint',
    to: 'flow-intake',
    tone: 'forward',
    caption: 'new file',
    bidirectional: false,
    route: [
      { at: 'sharepoint', offset: [1.7, 1.1, 0] },
      { at: 'flow-intake', offset: [-1.25, 1.1, 0] },
    ],
  },
  {
    id: 'record',
    from: 'flow-intake',
    to: 'dataverse',
    tone: 'forward',
    caption: 'creates the contract',
    bidirectional: false,
    route: [
      { at: 'flow-intake', offset: [1.25, 1.1, 0] },
      { at: 'dataverse', offset: [-1.85, 1.1, 0] },
    ],
  },
  {
    id: 'trigger',
    from: 'dataverse',
    to: 'flow-analysis',
    tone: 'forward',
    caption: 'status = Extracting',
    bidirectional: false,
    route: [
      { at: 'dataverse', offset: [1.85, 1.1, 0] },
      { at: 'flow-analysis', offset: [-1.25, 1.1, 0] },
    ],
  },
  {
    id: 'submit',
    from: 'flow-analysis',
    to: 'function',
    tone: 'forward',
    caption: 'POST, then poll',
    bidirectional: false,
    route: [
      { at: 'flow-analysis', offset: [1.25, 1.1, 0] },
      { at: 'function', offset: [-1.45, 1.3, 0] },
    ],
  },
  {
    id: 'read',
    from: 'function',
    to: 'analyzer',
    tone: 'forward',
    caption: 'PDF + checklist',
    bidirectional: false,
    route: [
      { at: 'function', offset: [1.45, 1.3, 0] },
      { at: 'analyzer', offset: [-1.35, 1.7, 0] },
    ],
  },
  {
    id: 'results',
    from: 'analyzer',
    to: 'dataverse',
    tone: 'return',
    caption: '20 answers with proof',
    bidirectional: false,
    route: [
      { at: 'analyzer', offset: [-0.9, 3.1, 0] },
      { at: 'function', offset: [0, 5.3, 0] },
      { at: 'flow-analysis', offset: [0, 5.5, 0] },
      { at: 'dataverse', offset: [0, 2.4, 0] },
    ],
  },
  {
    id: 'review',
    from: 'dataverse',
    to: 'code-app',
    tone: 'review',
    caption: 'findings and decisions',
    captionOffset: [-2.6, 0, 0],
    bidirectional: true,
    route: [
      { at: 'dataverse', offset: [0, 1.0, 1.85] },
      { at: 'code-app', offset: [0, 1.0, -1.5] },
    ],
  },
  {
    id: 'decide',
    from: 'code-app',
    to: 'reviewer',
    tone: 'review',
    caption: 'review',
    bidirectional: true,
    route: [
      { at: 'code-app', offset: [1.9, 1.2, 0] },
      { at: 'reviewer', offset: [-0.95, 1.2, 0] },
    ],
  },
];

export const STEPS: readonly ArchStep[] = [
  {
    id: 'arrives',
    title: 'A contract arrives',
    text: 'Someone drops a PDF into the Contract Intake folder in SharePoint.',
    detail:
      'The folder is the front door. There is nothing to install and no form to fill in: any PDF placed there goes through the same pipeline.',
    focus: ['sharepoint'],
    edges: [],
    travel: [],
    enter: 'sharepoint',
  },
  {
    id: 'noticed',
    title: 'The Intake flow picks it up',
    text: 'A Power Automate flow watches the folder and starts when a new file appears.',
    detail:
      'The Intake flow has 12 actions. It uses a polling trigger on the folder, so it starts by itself.',
    focus: ['sharepoint', 'flow-intake'],
    edges: ['intake'],
    travel: [{ edge: 'intake' }],
  },
  {
    id: 'record',
    title: 'A contract record is created',
    text: 'The flow creates the contract in Dataverse, attaches the PDF and sets the status to Extracting.',
    detail:
      'One row in the contracts table holds the document, its type and its status. Setting the status to Extracting is the hand-off to the next flow.',
    focus: ['flow-intake', 'dataverse'],
    edges: ['record'],
    travel: [{ edge: 'record' }],
    status: 'Extracting',
  },
  {
    id: 'wakes',
    title: 'The Analysis flow wakes up',
    text: 'A second flow starts the moment a contract’s status becomes Extracting.',
    detail:
      'It is a Dataverse trigger, so Extracting works as a queue: set a contract back to Extracting and it is analyzed again. The Analysis flow has 32 actions inside Try and Catch scopes, so a failure ends as Failed with a reason and never leaves a contract stuck.',
    focus: ['dataverse', 'flow-analysis'],
    edges: ['trigger'],
    travel: [{ edge: 'trigger' }],
    status: 'Extracting',
  },
  {
    id: 'function',
    title: 'The Function takes the PDF',
    text: 'The flow hands the PDF to an Azure Function, then checks back until the answer is ready.',
    detail:
      'POST /api/contracts/analyze returns 202 and an operation id straight away. The flow then polls GET /api/contracts/analyze/{operationId} until it returns 200, so slow AI work never blocks a flow.',
    focus: ['flow-analysis', 'function'],
    edges: ['submit'],
    travel: [{ edge: 'submit' }],
    status: 'Extracting',
  },
  {
    id: 'reads',
    title: 'The AI reads the whole contract',
    text: 'Content Understanding reads the PDF against the 20-item checklist.',
    detail:
      'A custom analyzer answers every checklist item and returns, for each one, the quote it relied on, the page and the box on that page. The Function reaches it with a managed identity, so there are no AI keys to leak.',
    focus: ['function', 'analyzer'],
    edges: ['read'],
    travel: [{ edge: 'read' }],
    status: 'Extracting',
    effect: 'scan',
  },
  {
    id: 'findings',
    title: 'The findings come home',
    text: 'Twenty answers, each with its proof, are written back to Dataverse.',
    detail:
      'The flow saves one finding per checklist item, plus the found count and a completeness score, then sets the status to Ready for Review. If anything goes wrong the status becomes Failed and the reason is recorded on the contract.',
    focus: ['analyzer', 'function', 'flow-analysis', 'dataverse'],
    edges: ['results'],
    travel: [],
    status: 'Ready for Review',
    effect: 'findings',
  },
  {
    id: 'review',
    title: 'A person reviews and decides',
    text: 'In the Code App the findings sit beside the PDF. Click one and its evidence lights up on the page.',
    detail:
      'A reviewer accepts, corrects or rejects each finding, can reopen a decision and approves the contract when satisfied. Approving locks the findings and sets the status to Approved. The AI proposes and a person decides.',
    focus: ['dataverse', 'code-app', 'reviewer'],
    edges: ['review', 'decide'],
    travel: [{ edge: 'review' }, { edge: 'decide' }],
    status: 'Approved',
  },
];

export const NODE_BY_ID: ReadonlyMap<NodeId, ArchNode> = new Map(NODES.map((node) => [node.id, node]));
export const EDGE_BY_ID: ReadonlyMap<EdgeId, ArchEdge> = new Map(EDGES.map((edge) => [edge.id, edge]));
export const ZONE_BY_ID: ReadonlyMap<ZoneId, ArchZone> = new Map(ZONES.map((zone) => [zone.id, zone]));

/** A waypoint in world coordinates. */
export function resolveWaypoint(waypoint: Waypoint): Vec3 {
  const node = NODE_BY_ID.get(waypoint.at);
  if (!node) throw new Error(`Unknown node ${waypoint.at}`);
  return [node.position[0] + waypoint.offset[0], node.position[1] + waypoint.offset[1], node.position[2] + waypoint.offset[2]];
}

export function resolveRoute(edge: ArchEdge): Vec3[] {
  return edge.route.map(resolveWaypoint);
}
