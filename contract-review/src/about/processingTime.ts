/*
  How long one contract takes to process, measured rather than guessed. A person's review is not part of it.

  The clock starts when a PDF is saved in the SharePoint intake folder and stops when the Analysis flow sets the
  contract's status to Ready for Review. Three documents went through the live system from start to finish on
  22 October 2026. Their times come from three places: the saved time of the file in SharePoint (to the second), the
  Power Automate run history of both flows and the Azure Function's own log. The six stages split each total at points
  those sources agree on, so every stage lines up with one step of the "How it works" diagram and the stages add up to
  the total. Nothing is simulated.

  To refresh: put another document through, read the same three sources and paste the new run into `PROCESSING`.
*/
import { formatDateOnly } from '../domain/format';

export type StageId = 'noticed' | 'record' | 'wakes' | 'function' | 'reads' | 'findings';
export type StageKind = 'wait' | 'work' | 'ai';

export interface ProcessingStage {
  /** The id of the diagram step this stage belongs to. */
  id: StageId;
  label: string;
  kind: StageKind;
  /** Where the stage starts and stops, in plain words. */
  covers: string;
}

/** In the order a contract goes through them. */
export const STAGES: readonly ProcessingStage[] = [
  { id: 'noticed', label: 'Pickup', kind: 'wait', covers: 'From the PDF being saved in the intake folder to the Intake flow starting' },
  { id: 'record', label: 'Intake flow', kind: 'work', covers: 'Creates the contract record, attaches the PDF and sets the status to Extracting' },
  { id: 'wakes', label: 'Hand-off', kind: 'wait', covers: 'From the status changing to the Analysis flow starting' },
  { id: 'function', label: 'Function', kind: 'work', covers: 'The Analysis flow prepares the PDF and the Azure Function hands it to the AI' },
  { id: 'reads', label: 'AI reading', kind: 'ai', covers: 'The AI reads the contract against the 20-item checklist while the flow checks back until it is done' },
  { id: 'findings', label: 'Write-back', kind: 'work', covers: 'Saves the 20 findings and sets the status to Ready for Review' },
];

export const KINDS: readonly StageKind[] = ['wait', 'work', 'ai'];

export const KIND_LABELS: Readonly<Record<StageKind, string>> = {
  wait: 'Waiting for the next step to start',
  work: 'A flow or the Function working',
  ai: 'The AI reading the contract',
};

export interface ProcessingRun {
  id: string;
  label: string;
  /** What kind of document it was, in a few words. */
  about: string;
  /** File size in KB, rounded. */
  sizeKb: number;
  /** Seconds spent in each stage. */
  seconds: Readonly<Record<StageId, number>>;
}

export interface ProcessingSnapshot {
  /** The day the runs were timed, as yyyy-mm-dd. */
  measuredOn: string;
  runs: readonly ProcessingRun[];
}

export const PROCESSING: ProcessingSnapshot = {
  measuredOn: '2026-10-22',
  runs: [
    {
      id: 'sow',
      label: 'Statement of work',
      about: 'larger contract',
      sizeKb: 900,
      seconds: { noticed: 32.26, record: 1.47, wakes: 7.75, function: 3.88, reads: 89.53, findings: 1.9 },
    },
    {
      id: 'amendment',
      label: 'Amendment',
      about: 'smaller contract',
      sizeKb: 500,
      seconds: { noticed: 32.26, record: 1.53, wakes: 7.83, function: 3.3, reads: 18.78, findings: 2.43 },
    },
    {
      id: 'test',
      label: 'Test document',
      about: 'tiny test file',
      sizeKb: 7,
      seconds: { noticed: 31.3, record: 0.58, wakes: 7.53, function: 1.76, reads: 22, findings: 2.51 },
    },
  ],
};

/** The diagram steps that are not stages: the clock starts at the first and stops before the last. */
export const START_STEP = 'arrives';
export const REVIEW_STEP = 'review';

export const STAGE_BY_ID: ReadonlyMap<StageId, ProcessingStage> = new Map(STAGES.map((stage) => [stage.id, stage]));

export function isStageId(value: string | null | undefined): value is StageId {
  return value !== null && value !== undefined && STAGE_BY_ID.has(value as StageId);
}

export function totalSeconds(run: ProcessingRun): number {
  return STAGES.reduce((sum, stage) => sum + run.seconds[stage.id], 0);
}

/** The time on the clock when each stage ends. */
export function stageEnds(run: ProcessingRun): Record<StageId, number> {
  const ends = {} as Record<StageId, number>;
  let elapsed = 0;
  for (const stage of STAGES) {
    elapsed += run.seconds[stage.id];
    ends[stage.id] = elapsed;
  }
  return ends;
}

export function kindSeconds(run: ProcessingRun, kind: StageKind): number {
  return STAGES.filter((stage) => stage.kind === kind).reduce((sum, stage) => sum + run.seconds[stage.id], 0);
}

export interface SpanRange {
  low: number;
  high: number;
}

const rangeOf = (values: readonly number[]): SpanRange => ({ low: Math.min(...values), high: Math.max(...values) });

export function stageRange(id: StageId, runs: readonly ProcessingRun[] = PROCESSING.runs): SpanRange {
  return rangeOf(runs.map((run) => run.seconds[id]));
}

export function totalRange(runs: readonly ProcessingRun[] = PROCESSING.runs): SpanRange {
  return rangeOf(runs.map(totalSeconds));
}

/** The range of the time a kind of stage takes per run. */
export function kindRange(kind: StageKind, runs: readonly ProcessingRun[] = PROCESSING.runs): SpanRange {
  return rangeOf(runs.map((run) => kindSeconds(run, kind)));
}

/** The run in the middle when they are put in order of total time. */
export function middleRun(runs: readonly ProcessingRun[] = PROCESSING.runs): ProcessingRun {
  const sorted = [...runs].sort((a, b) => totalSeconds(a) - totalSeconds(b));
  return sorted[Math.floor((sorted.length - 1) / 2)];
}

export function slowestRun(runs: readonly ProcessingRun[] = PROCESSING.runs): ProcessingRun {
  return runs.reduce((slowest, run) => (totalSeconds(run) > totalSeconds(slowest) ? run : slowest));
}

/** "7.8s" below ten seconds, then whole seconds: "32s", "1m 6s". */
export function formatSpan(seconds: number): string {
  const value = Math.max(0, seconds);
  if (value < 9.95) return `${value.toFixed(1)}s`;
  const rounded = Math.round(value);
  const minutes = Math.floor(rounded / 60);
  return minutes > 0 ? `${minutes}m ${rounded % 60}s` : `${rounded}s`;
}

/** "1 minute 6 seconds", for people who listen to the page. */
export function formatSpanWords(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(rounded / 60);
  const rest = rounded % 60;
  const parts: string[] = [];
  if (minutes > 0) parts.push(`${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`);
  if (rest > 0 || minutes === 0) parts.push(`${rest} ${rest === 1 ? 'second' : 'seconds'}`);
  return parts.join(' ');
}

/** "31–32s", "0.6–1.5s", "1m 6s to 2m 17s". One value when both ends read the same. */
export function formatSpanRange({ low, high }: SpanRange): string {
  const first = formatSpan(low);
  const last = formatSpan(high);
  if (first === last) return first;
  if (high < 9.95) return `${low.toFixed(1)}\u2013${last}`;
  if (high < 120) return `${Math.round(low)}\u2013${Math.round(high)}s`;
  return `${first} to ${last}`;
}

/** The clock face: "1:06". */
export function formatStopwatch(seconds: number): string {
  const rounded = Math.max(0, Math.round(seconds));
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, '0')}`;
}

/** "0.9 MB" or "7 KB". */
export function formatSize(kb: number): string {
  return kb >= 100 ? `${(kb / 1000).toFixed(1)} MB` : `${kb} KB`;
}

export function runNote(run: ProcessingRun): string {
  return `${run.about}, about ${formatSize(run.sizeKb)}`;
}

const COUNT_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
export const countWord = (count: number): string => COUNT_WORDS[count] ?? String(count);
export const capitalize = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

export interface ProcessingTile {
  label: string;
  value: string;
  note: string;
}

/** The four numbers at the top of the cost page. */
export function processingTiles(runs: readonly ProcessingRun[] = PROCESSING.runs): ProcessingTile[] {
  const slowest = slowestRun(runs);
  return [
    {
      label: 'Typical run',
      value: formatSpan(totalSeconds(middleRun(runs))),
      note: `The middle of ${countWord(runs.length)} runs, from saved PDF to Ready for Review`,
    },
    { label: 'Slowest run', value: formatSpan(totalSeconds(slowest)), note: `${slowest.label}: ${runNote(slowest)}` },
    {
      label: 'Waiting',
      value: formatSpanRange(rangeOf(runs.map((run) => kindSeconds(run, 'wait')))),
      note: 'Pickup and hand-off: the gaps before a flow starts',
    },
    { label: 'AI reading', value: formatSpanRange(kindRange('ai', runs)), note: 'Depends on the document, not just its size' },
  ];
}

export const PROCESSING_TITLE = 'Time to process one contract';
export const PROCESSING_QUESTION = 'How long does it take?';

export function processingLead(runs: readonly ProcessingRun[] = PROCESSING.runs): string {
  const timed = `${countWord(runs.length)} ${runs.length === 1 ? 'run' : 'runs'}`;
  return `From a saved PDF to Ready for Review took ${formatSpanRange(totalRange(runs))} in the ${timed} we timed. That is machine time only: a person\u2019s review comes after it and is not included.`;
}

/** What to notice in the numbers, written from the numbers so the two cannot drift apart. */
export function processingTakeaways(runs: readonly ProcessingRun[] = PROCESSING.runs): string[] {
  const waiting = formatSpanRange(rangeOf(runs.map((run) => kindSeconds(run, 'wait'))));
  return [
    `Waiting: ${waiting} of each run is the gap before a flow starts. The Intake flow has to notice the new file, and the Analysis flow has to start after the status changes.`,
    `AI reading is the part that changes with the document: ${formatSpanRange(kindRange('ai', runs))}.`,
    `The flows and the Function do their own work in ${formatSpanRange(kindRange('work', runs))} between them.`,
  ];
}

export interface MethodNote {
  term: string;
  text: string;
}

export function processingMethod(snapshot: ProcessingSnapshot = PROCESSING): MethodNote[] {
  const count = countWord(snapshot.runs.length);
  return [
    {
      term: 'The runs.',
      text: `${capitalize(count)} documents went through the live system from start to finish on ${formatDateOnly(snapshot.measuredOn)}. ${capitalize(count)} runs are a snapshot, not a benchmark, and other documents will take other times.`,
    },
    {
      term: 'The clock.',
      text: 'It starts when the PDF is saved in the intake folder, to the second, and stops when the Analysis flow sets the status to Ready for Review.',
    },
    {
      term: 'The sources.',
      text: 'The saved time of each file in SharePoint, the Power Automate run history of both flows and the Azure Function\u2019s own log. Nothing is estimated or simulated. Figures are rounded, so the stages can differ from the total by a second.',
    },
    {
      term: 'Waiting.',
      text: `Pickup and hand-off came out almost the same in all ${count} runs, but ${count} runs are too few to say how much they vary.`,
    },
    {
      term: 'AI reading.',
      text: 'This is the part that depends on the document, and file size did not predict it: the smallest file was not the fastest. It includes the few seconds the flow takes to notice that the AI has finished.',
    },
    { term: 'Not included.', text: 'A person\u2019s review, and the time it takes to save a PDF into the folder.' },
  ];
}

/** The line on a step card: what the step took, or why it is not timed. Null for a step that is not in the diagram. */
export function stepTiming(stepId: string, runs: readonly ProcessingRun[] = PROCESSING.runs): string | null {
  if (stepId === START_STEP) return 'Starts the clock';
  if (stepId === REVIEW_STEP) return 'Not timed: a person decides';
  if (!isStageId(stepId)) return null;
  const range = formatSpanRange(stageRange(stepId, runs));
  return STAGE_BY_ID.get(stepId)?.kind === 'ai' ? `Measured: ${range}, depending on the document` : `Measured: ${range}`;
}

export const CLOCK_NOTES = {
  total: 'From the PDF being saved to Ready for Review',
  start: 'The clock starts when the PDF is saved',
  running: 'Since the PDF was saved',
  stopped: 'Stopped at Ready for Review. A person\u2019s review is not timed',
} as const;

export interface ClockReading {
  seconds: number;
  note: string;
}

/** What the tour's clock shows when a step ends: null is the overview, which shows the whole run. */
export function clockAtStep(run: ProcessingRun, stepId: string | null): ClockReading {
  if (stepId === START_STEP) return { seconds: 0, note: CLOCK_NOTES.start };
  if (stepId === REVIEW_STEP) return { seconds: totalSeconds(run), note: CLOCK_NOTES.stopped };
  if (isStageId(stepId)) return { seconds: stageEnds(run)[stepId], note: CLOCK_NOTES.running };
  return { seconds: totalSeconds(run), note: CLOCK_NOTES.total };
}

export const AXIS_STEP_SECONDS = 30;
/** A segment shows its label only when it is at least this share of the axis. */
const LABEL_MIN_SHARE = 0.1;

export interface TimelineSegment {
  id: StageId;
  kind: StageKind;
  label: string;
  seconds: number;
  showLabel: boolean;
}

export interface TimelineRow {
  run: ProcessingRun;
  total: number;
  /** The bar's length as a share of the axis. */
  widthPercent: number;
  segments: TimelineSegment[];
}

export interface TimelineTick {
  seconds: number;
  percent: number;
  label: string;
}

export interface TimelineGeometry {
  axisMax: number;
  ticks: TimelineTick[];
  rows: TimelineRow[];
}

/** Every bar is drawn to the same scale, so a longer run is a longer bar. */
export function timelineGeometry(runs: readonly ProcessingRun[] = PROCESSING.runs): TimelineGeometry {
  const axisMax = Math.max(AXIS_STEP_SECONDS, Math.ceil(totalRange(runs).high / AXIS_STEP_SECONDS) * AXIS_STEP_SECONDS);
  const ticks: TimelineTick[] = [];
  for (let seconds = 0; seconds <= axisMax; seconds += AXIS_STEP_SECONDS) {
    ticks.push({ seconds, percent: (seconds / axisMax) * 100, label: formatStopwatch(seconds) });
  }
  const rows = runs.map<TimelineRow>((run) => {
    const total = totalSeconds(run);
    return {
      run,
      total,
      widthPercent: (total / axisMax) * 100,
      segments: STAGES.map((stage) => ({
        id: stage.id,
        kind: stage.kind,
        label: stage.label,
        seconds: run.seconds[stage.id],
        showLabel: run.seconds[stage.id] / axisMax >= LABEL_MIN_SHARE,
      })),
    };
  });
  return { axisMax, ticks, rows };
}

/** What a screen reader hears for one bar. */
export function describeRow(row: TimelineRow): string {
  const parts = row.segments.map((segment) => `${segment.label} ${formatSpan(segment.seconds)}`);
  return `${row.run.label}: ${formatSpanWords(row.total)} in total. ${parts.join(', ')}.`;
}
