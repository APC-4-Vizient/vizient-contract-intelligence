/*
  What it costs to process one contract, worked out from the usage the live system recorded rather than guessed.

  Every Content Understanding result carries a `usage` block: the pages it read, the tokens it prepared as context for
  the model, and the tokens the gpt-5.5 model took in and wrote out. The Analysis flow stores that block on the contract
  record. Each quantity times its published list price is the cost of one document. The three sample documents below
  are synthetic contracts from this repository, so anyone can run them again and compare.

  Prices are public list prices (the Azure Retail Prices API and Microsoft Learn), not what a tenant is invoiced. The
  Azure Function is measured on the three timed runs and priced, but kept out of the totals because it is a fraction of
  a percent of them. Power Automate is counted in actions, which draw on license allowances rather than a per-document
  charge, so it carries no dollar figure.

  To refresh: analyse a sample again, copy the numbers in its `usage` block into `SAMPLES`, and update `RATES` if a
  price has moved.
*/
import { formatDateOnly } from '../domain/format';
import { formatCount, formatUsd } from '../domain/format';
import { capitalize, countWord } from './processingTime';
import type { MethodNote } from './processingTime';

export type CostPartId = 'reading' | 'context' | 'input' | 'cached' | 'output';
export type CostGroupId = 'pages' | 'input' | 'output';

export interface CostGroup {
  id: CostGroupId;
  label: string;
}

/** The three colours of a bar: what the bill is made of. */
export const COST_GROUPS: readonly CostGroup[] = [
  { id: 'pages', label: 'Content Understanding' },
  { id: 'input', label: 'Model input' },
  { id: 'output', label: 'Model output' },
];

export interface CostRate {
  id: CostPartId;
  group: CostGroupId;
  label: string;
  /** Who bills it. */
  service: string;
  covers: string;
  /** List price in US dollars for `per` units. */
  usd: number;
  per: number;
  unit: 'pages' | 'tokens';
}

/** The day the list prices were read. */
export const PRICED_ON = '2026-10-22';

export const RATES: readonly CostRate[] = [
  { id: 'reading', group: 'pages', label: 'Reading each page', service: 'Content Understanding', covers: 'Turns every page into text and layout', usd: 5, per: 1_000, unit: 'pages' },
  { id: 'context', group: 'pages', label: 'Context for the model', service: 'Content Understanding', covers: 'Prepares each page for the model, counted as 1,000 tokens a page', usd: 1, per: 1_000_000, unit: 'tokens' },
  { id: 'input', group: 'input', label: 'Model input', service: 'gpt-5.5 model', covers: 'The contract text, the checklist and the instructions the model reads', usd: 5, per: 1_000_000, unit: 'tokens' },
  { id: 'cached', group: 'input', label: 'Model input, cached', service: 'gpt-5.5 model', covers: 'Input the model had already seen, billed at a tenth of the input price', usd: 0.5, per: 1_000_000, unit: 'tokens' },
  { id: 'output', group: 'output', label: 'Model output', service: 'gpt-5.5 model', covers: 'The answers and the evidence the model writes', usd: 30, per: 1_000_000, unit: 'tokens' },
];

export interface SampleDocument {
  id: string;
  label: string;
  pages: number;
  contextTokens: number;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
}

/** The usage block Content Understanding returned for each synthetic sample, as stored on its contract record. */
export const SAMPLES: readonly SampleDocument[] = [
  { id: 'amendment', label: 'Sample amendment', pages: 3, contextTokens: 3_000, inputTokens: 9_049, cachedInputTokens: 0, outputTokens: 2_396 },
  { id: 'dua', label: 'Sample data use agreement', pages: 13, contextTokens: 13_000, inputTokens: 25_669, cachedInputTokens: 7_680, outputTokens: 3_005 },
  { id: 'sow', label: 'Sample statement of work', pages: 14, contextTokens: 14_000, inputTokens: 38_282, cachedInputTokens: 0, outputTokens: 3_038 },
];

export interface Range {
  low: number;
  high: number;
}

const rangeOf = (values: readonly number[]): Range => ({ low: Math.min(...values), high: Math.max(...values) });

export interface DocumentCost {
  document: SampleDocument;
  /** US dollars for each part. */
  parts: Record<CostPartId, number>;
  groups: Record<CostGroupId, number>;
  total: number;
  perPage: number;
}

export function quantityOf(document: SampleDocument, id: CostPartId): number {
  switch (id) {
    case 'reading':
      return document.pages;
    case 'context':
      return document.contextTokens;
    case 'input':
      return document.inputTokens;
    case 'cached':
      return document.cachedInputTokens;
    case 'output':
      return document.outputTokens;
  }
}

export function costOf(document: SampleDocument, rates: readonly CostRate[] = RATES): DocumentCost {
  const parts = {} as Record<CostPartId, number>;
  const groups: Record<CostGroupId, number> = { pages: 0, input: 0, output: 0 };
  let total = 0;
  for (const rate of rates) {
    const usd = (quantityOf(document, rate.id) * rate.usd) / rate.per;
    parts[rate.id] = usd;
    groups[rate.group] += usd;
    total += usd;
  }
  return { document, parts, groups, total, perPage: total / document.pages };
}

export const SAMPLE_COSTS: readonly DocumentCost[] = SAMPLES.map((sample) => costOf(sample));

export function totalRange(costs: readonly DocumentCost[] = SAMPLE_COSTS): Range {
  return rangeOf(costs.map((cost) => cost.total));
}

export function perPageRange(costs: readonly DocumentCost[] = SAMPLE_COSTS): Range {
  return rangeOf(costs.map((cost) => cost.perPage));
}

export function pagesRange(costs: readonly DocumentCost[] = SAMPLE_COSTS): Range {
  return rangeOf(costs.map((cost) => cost.document.pages));
}

/** The document in the middle when they are put in order of cost. */
export function middleCost(costs: readonly DocumentCost[] = SAMPLE_COSTS): DocumentCost {
  const sorted = [...costs].sort((a, b) => a.total - b.total);
  return sorted[Math.floor((sorted.length - 1) / 2)];
}

export function averageTotal(costs: readonly DocumentCost[] = SAMPLE_COSTS): number {
  return costs.reduce((sum, cost) => sum + cost.total, 0) / costs.length;
}

/** The share of a document's cost that is the model, as a number between 0 and 1. */
export const modelShare = (cost: DocumentCost): number => (cost.groups.input + cost.groups.output) / cost.total;

export function modelShareRange(costs: readonly DocumentCost[] = SAMPLE_COSTS): Range {
  return rangeOf(costs.map(modelShare));
}

/**
  Content Understanding lists cached tokens apart from input tokens and does not say whether the input figure already
  includes them. Both are priced here, so if they overlap the estimate is high by the cached tokens at the input price.
*/
export function cachedOverlapUsd(document: SampleDocument, rates: readonly CostRate[] = RATES): number {
  const input = rates.find((rate) => rate.id === 'input');
  return input ? (document.cachedInputTokens * input.usd) / input.per : 0;
}

export function largestCachedOverlapUsd(samples: readonly SampleDocument[] = SAMPLES): number {
  return Math.max(...samples.map((sample) => cachedOverlapUsd(sample)));
}

/** What one document asked of the Azure Function on each of the three timed runs. */
export interface FunctionRun {
  calls: number;
  /** Gigabyte-seconds billed on a 2 GB instance, with each call rounded up to at least a second and then to a tenth. */
  gbSeconds: number;
}

export const FUNCTION_RUNS: readonly FunctionRun[] = [
  { calls: 3, gbSeconds: 7.2 },
  { calls: 14, gbSeconds: 29 },
  { calls: 4, gbSeconds: 8.4 },
];

export const FUNCTION_RATES = {
  usdPerGbSecond: 0.000026,
  usdPerCall: 0.0000004,
  freeGbSeconds: 100_000,
  freeCalls: 250_000,
} as const;

export const functionCostUsd = (run: FunctionRun): number =>
  run.gbSeconds * FUNCTION_RATES.usdPerGbSecond + run.calls * FUNCTION_RATES.usdPerCall;

export function functionCostRange(runs: readonly FunctionRun[] = FUNCTION_RUNS): Range {
  return rangeOf(runs.map(functionCostUsd));
}

export function functionCallRange(runs: readonly FunctionRun[] = FUNCTION_RUNS): Range {
  return rangeOf(runs.map((run) => run.calls));
}

/** Power Automate actions one document used on the timed runs, counting every pass through a loop. */
export interface FlowActions {
  intake: number;
  analysis: Range;
}

export const FLOW_ACTIONS: FlowActions = {
  intake: 7,
  analysis: { low: 44, high: 88 },
};

export function flowActionRange(actions: FlowActions = FLOW_ACTIONS): Range {
  return { low: actions.intake + actions.analysis.low, high: actions.intake + actions.analysis.high };
}

const FINE = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 3, maximumFractionDigits: 3 });
const TINY = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 4, maximumFractionDigits: 4 });

/** "$0.045": one part of a document's cost, to a tenth of a cent. */
export const formatUsdFine = (usd: number): string => FINE.format(usd);

/** "$0.0008": an amount under a tenth of a cent. */
export const formatUsdTiny = (usd: number): string => TINY.format(usd);

/** "$0.14–$0.37", or one amount when both ends read the same. */
export function formatUsdRange({ low, high }: Range): string {
  const first = formatUsd(low);
  const last = formatUsd(high);
  return first === last ? first : `${first}\u2013${last}`;
}

/** "2.3–4.5¢". */
export function formatCentsRange({ low, high }: Range): string {
  const first = (low * 100).toFixed(1);
  const last = (high * 100).toFixed(1);
  return first === last ? `${first}\u00A2` : `${first}\u2013${last}\u00A2`;
}

/** "74–87%". */
export function formatPercentRange({ low, high }: Range): string {
  const first = Math.round(low * 100);
  const last = Math.round(high * 100);
  return first === last ? `${first}%` : `${first}\u2013${last}%`;
}

/** "$5.00 per 1,000 pages". */
export function rateText(rate: CostRate): string {
  const per = rate.per === 1_000_000 ? 'million' : formatCount(rate.per);
  return `${formatUsd(rate.usd)} per ${per} ${rate.unit}`;
}

/** "9,049 tokens", or "not used" when the document did not use this part. */
export function usageText(document: SampleDocument, rate: CostRate): string {
  const quantity = quantityOf(document, rate.id);
  return quantity === 0 ? 'not used' : `${formatCount(quantity)} ${rate.unit}`;
}

/** The dollars for one part in the table: a dash when there is nothing to charge. */
export function partText(cost: DocumentCost, id: CostPartId): string {
  return cost.parts[id] === 0 ? '\u2013' : formatUsdFine(cost.parts[id]);
}

export const AXIS_STEP_USD = 0.1;
/** A segment shows its amount only when it is at least this share of the axis. */
const LABEL_MIN_SHARE = 0.1;

export interface CostSegment {
  id: CostGroupId;
  label: string;
  usd: number;
  showLabel: boolean;
}

export interface CostBarRow {
  cost: DocumentCost;
  /** The bar's length as a share of the axis. */
  widthPercent: number;
  segments: CostSegment[];
}

export interface CostTick {
  usd: number;
  percent: number;
  label: string;
}

export interface CostBars {
  axisMax: number;
  ticks: CostTick[];
  rows: CostBarRow[];
}

/** Every bar is drawn to the same scale, so a dearer document is a longer bar. */
export function costBars(costs: readonly DocumentCost[] = SAMPLE_COSTS): CostBars {
  const steps = Math.max(1, Math.ceil(Math.max(...costs.map((cost) => cost.total)) / AXIS_STEP_USD - 1e-9));
  const axisMax = steps * AXIS_STEP_USD;
  const ticks = Array.from({ length: steps + 1 }, (_, index) => {
    const usd = index * AXIS_STEP_USD;
    return { usd, percent: (usd / axisMax) * 100, label: formatUsd(usd) };
  });
  const rows = costs.map<CostBarRow>((cost) => ({
    cost,
    widthPercent: (cost.total / axisMax) * 100,
    segments: COST_GROUPS.map((group) => ({
      id: group.id,
      label: group.label,
      usd: cost.groups[group.id],
      showLabel: cost.groups[group.id] / axisMax >= LABEL_MIN_SHARE,
    })),
  }));
  return { axisMax, ticks, rows };
}

/** What a screen reader hears for one bar. */
export function describeCostRow(row: CostBarRow): string {
  const parts = row.segments.map((segment) => `${segment.label} ${formatUsdFine(segment.usd)}`);
  return `${row.cost.document.label}: ${formatUsd(row.cost.total)} in total. ${parts.join(', ')}.`;
}

export interface CostTile {
  label: string;
  value: string;
  note: string;
}

/** The four numbers at the top of the cost section. */
export function costTiles(costs: readonly DocumentCost[] = SAMPLE_COSTS): CostTile[] {
  const middle = middleCost(costs);
  const pages = pagesRange(costs);
  return [
    {
      label: 'Typical sample',
      value: formatUsd(middle.total),
      note: `The middle of ${countWord(costs.length)} synthetic contracts: ${middle.document.pages} pages`,
    },
    { label: 'Range', value: formatUsdRange(totalRange(costs)), note: `${pages.low} to ${pages.high} pages, all synthetic` },
    { label: 'Per page', value: formatCentsRange(perPageRange(costs)), note: 'Depends on the document, not just its length' },
    {
      label: 'Per 1,000 documents',
      value: formatUsd(averageTotal(costs) * 1000, false),
      note: 'Illustrative: the sample average times a thousand',
    },
  ];
}

export const COST_TITLE = 'Cost to process one contract';
export const COST_QUESTION = 'What does it cost?';

export function costLead(costs: readonly DocumentCost[] = SAMPLE_COSTS): string {
  return `Across the ${countWord(costs.length)} synthetic sample contracts, reading the pages and answering the 20-item checklist cost an estimated ${formatUsdRange(totalRange(costs))} a document at list prices, about ${formatCentsRange(perPageRange(costs))} a page. The AI model is ${formatPercentRange(modelShareRange(costs))} of that and reading the pages is the rest. Longer or denser contracts cost more.`;
}

/** The short version for the How it works page. */
export function costMention(costs: readonly DocumentCost[] = SAMPLE_COSTS): string {
  return `Processing one document costs an estimated ${formatUsdRange(totalRange(costs))} in the samples, most of it the AI model.`;
}

export function costMethod(costs: readonly DocumentCost[] = SAMPLE_COSTS, samples: readonly SampleDocument[] = SAMPLES): MethodNote[] {
  const pages = pagesRange(costs);
  return [
    {
      term: 'The documents.',
      text: `${capitalize(countWord(costs.length))} synthetic sample contracts of ${pages.low} to ${pages.high} pages. They live in the repository, so anyone can run them again and compare. Other documents will cost other amounts.`,
    },
    {
      term: 'The usage.',
      text: 'Every Content Understanding result carries a usage block: the pages it read, the tokens it prepared as context and the tokens the model took in and wrote out. The Analysis flow stores that block on the contract record, so these are the figures the live system reported, not our guesses.',
    },
    {
      term: 'The prices.',
      text: `Public list prices read on ${formatDateOnly(PRICED_ON)} from the Azure Retail Prices API and Microsoft Learn: Content Understanding at the Standard tier and the gpt-5.5 model on a Global Standard deployment. They are not an invoice, because discounts, commitments and taxes are not applied.`,
    },
    {
      term: 'Two bills.',
      text: 'Content Understanding bills the pages and the context. The model deployment bills the tokens. Both land on the same Azure subscription.',
    },
    {
      term: 'Cached input.',
      text: `Content Understanding reports cached tokens apart from input tokens and does not say whether the input figure already includes them. Each is priced at its own rate, so if they overlap the estimate runs high, by at most ${formatUsd(largestCachedOverlapUsd(samples))} a document.`,
    },
    { term: 'Rounding.', text: 'Parts are rounded to a tenth of a cent, so they can differ from a total by a tenth of a cent.' },
  ];
}

/** What the totals leave out, and why. */
export function costExtras(): MethodNote[] {
  const money = functionCostRange();
  const calls = functionCallRange();
  const actions = flowActionRange();
  return [
    {
      term: 'Azure Function.',
      text: `${formatUsdTiny(money.low)} to ${formatUsdTiny(money.high)} a document at list price: ${calls.low} to ${calls.high} short calls on a 2 GB instance, each billed for at least a second. Azure also takes the first ${formatCount(FUNCTION_RATES.freeGbSeconds)} gigabyte-seconds and ${formatCount(FUNCTION_RATES.freeCalls)} calls each month off the bill. It is left out of the totals because it is a fraction of a percent of them.`,
    },
    {
      term: 'Power Automate.',
      text: `${actions.low} to ${actions.high} flow actions a document: ${FLOW_ACTIONS.intake} in Intake and ${FLOW_ACTIONS.analysis.low} to ${FLOW_ACTIONS.analysis.high} in Analysis, depending on how many times the flow checks back for the AI\u2019s answer. Actions count against license allowances rather than being billed per document, so they carry no dollar figure here.`,
    },
    {
      term: 'Not included.',
      text: 'A person\u2019s review, Power Platform licenses, storage for the PDFs and results (priced by the month, not by the document), monitoring, discounts and taxes.',
    },
  ];
}

/** The cost line on a step card, or null for a step that has none. */
export function stepCost(stepId: string, costs: readonly DocumentCost[] = SAMPLE_COSTS): string | null {
  if (stepId === 'reads') return `Cost: ${formatUsdRange(totalRange(costs))} a sample document`;
  if (stepId === 'function') return 'Cost: under a tenth of a cent a document';
  return null;
}
