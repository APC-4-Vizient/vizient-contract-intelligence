import { describe, expect, it } from 'vitest';
import { STEPS } from './architecture';
import {
  AXIS_STEP_USD,
  COST_GROUPS,
  COST_QUESTION,
  COST_TITLE,
  FLOW_ACTIONS,
  FUNCTION_RUNS,
  RATES,
  SAMPLES,
  SAMPLE_COSTS,
  averageTotal,
  cachedOverlapUsd,
  costBars,
  costExtras,
  costLead,
  costMention,
  costMethod,
  costOf,
  costTiles,
  describeCostRow,
  flowActionRange,
  formatCentsRange,
  formatPercentRange,
  formatUsdFine,
  formatUsdRange,
  formatUsdTiny,
  functionCostRange,
  functionCostUsd,
  largestCachedOverlapUsd,
  middleCost,
  modelShareRange,
  partText,
  perPageRange,
  quantityOf,
  rateText,
  stepCost,
  totalRange,
  usageText,
} from './processingCost';
import type { CostPartId, SampleDocument } from './processingCost';

const [AMENDMENT, DUA, SOW] = SAMPLE_COSTS;

function collectStrings(value: unknown, into: string[] = []): string[] {
  if (typeof value === 'string') into.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectStrings(item, into));
  else if (value && typeof value === 'object') Object.values(value).forEach((item) => collectStrings(item, into));
  return into;
}

describe('the cost of one document', () => {
  it('multiplies each quantity by its list price', () => {
    const expected: Record<string, Record<CostPartId, number>> = {
      amendment: { reading: 0.015, context: 0.003, input: 0.045245, cached: 0, output: 0.07188 },
      dua: { reading: 0.065, context: 0.013, input: 0.128345, cached: 0.00384, output: 0.09015 },
      sow: { reading: 0.07, context: 0.014, input: 0.19141, cached: 0, output: 0.09114 },
    };
    for (const cost of SAMPLE_COSTS) {
      for (const rate of RATES) expect(cost.parts[rate.id], `${cost.document.id} ${rate.id}`).toBeCloseTo(expected[cost.document.id][rate.id], 9);
    }
    expect(AMENDMENT.total).toBeCloseTo(0.135125, 9);
    expect(DUA.total).toBeCloseTo(0.300335, 9);
    expect(SOW.total).toBeCloseTo(0.36655, 9);
  });

  it('adds the parts up to the total, and the colours of the bar up to the same total', () => {
    for (const cost of SAMPLE_COSTS) {
      const parts = RATES.reduce((sum, rate) => sum + cost.parts[rate.id], 0);
      const groups = COST_GROUPS.reduce((sum, group) => sum + cost.groups[group.id], 0);
      expect(parts).toBeCloseTo(cost.total, 12);
      expect(groups).toBeCloseTo(cost.total, 12);
      expect(cost.perPage).toBeCloseTo(cost.total / cost.document.pages, 12);
    }
  });

  it('prices only what the document used', () => {
    expect(AMENDMENT.parts.cached).toBe(0);
    const unused: SampleDocument = { id: 'blank', label: 'Blank', pages: 1, contextTokens: 0, inputTokens: 0, cachedInputTokens: 0, outputTokens: 0 };
    expect(costOf(unused).total).toBeCloseTo(0.005, 9);
    expect(quantityOf(DUA.document, 'cached')).toBe(7680);
  });

  it('has one rate for each part, in a group the bar knows', () => {
    expect(new Set(RATES.map((rate) => rate.id)).size).toBe(RATES.length);
    for (const rate of RATES) expect(COST_GROUPS.map((group) => group.id)).toContain(rate.group);
  });
});

describe('the summary', () => {
  it('finds the range, the middle and the average', () => {
    expect(totalRange(SAMPLE_COSTS).low).toBeCloseTo(0.135125, 9);
    expect(totalRange(SAMPLE_COSTS).high).toBeCloseTo(0.36655, 9);
    expect(middleCost(SAMPLE_COSTS).document.id).toBe('dua');
    expect(averageTotal(SAMPLE_COSTS)).toBeCloseTo(0.267337, 6);
  });

  it('puts four tiles together from the numbers', () => {
    const tiles = costTiles(SAMPLE_COSTS);
    expect(tiles.map((tile) => tile.label)).toEqual(['Typical sample', 'Range', 'Per page', 'Per 1,000 documents']);
    expect(tiles.map((tile) => tile.value)).toEqual(['$0.30', '$0.14\u2013$0.37', '2.3\u20134.5\u00A2', '$267']);
  });

  it('works from the documents it is given', () => {
    expect(costLead([AMENDMENT, DUA])).toContain('Across the two synthetic sample contracts');
    expect(costLead([AMENDMENT, DUA])).toContain('an estimated $0.14\u2013$0.30 a document');
    expect(costTiles([DUA])[1].value).toBe('$0.30');
  });
});

describe('claims the copy makes about the numbers', () => {
  it('says longer documents cost more', () => {
    const byPages = [...SAMPLE_COSTS].sort((a, b) => a.document.pages - b.document.pages).map((cost) => cost.total);
    expect(byPages).toEqual([...byPages].sort((a, b) => a - b));
  });

  it('says the cost per page depends on the document, not just its length', () => {
    const { low, high } = perPageRange(SAMPLE_COSTS);
    expect(high).toBeGreaterThan(low * 1.5);
  });

  it('says the model is most of the cost', () => {
    expect(modelShareRange(SAMPLE_COSTS).low).toBeGreaterThan(0.5);
    expect(formatPercentRange(modelShareRange(SAMPLE_COSTS))).toBe('74\u201387%');
  });

  it('says a context token is counted 1,000 to a page', () => {
    for (const sample of SAMPLES) expect(sample.contextTokens).toBe(sample.pages * 1000);
  });

  it('says cached tokens might overlap the input tokens, so the estimate can only run high', () => {
    for (const sample of SAMPLES) expect(sample.cachedInputTokens).toBeLessThanOrEqual(sample.inputTokens);
    expect(cachedOverlapUsd(DUA.document)).toBeCloseTo(0.0384, 9);
    expect(cachedOverlapUsd(AMENDMENT.document)).toBe(0);
    expect(largestCachedOverlapUsd(SAMPLES)).toBeCloseTo(0.0384, 9);
  });

  it('says the Azure Function is a fraction of a percent of the cost and under a tenth of a cent', () => {
    const { high } = functionCostRange(FUNCTION_RUNS);
    expect(high).toBeLessThan(0.001);
    expect(high / totalRange(SAMPLE_COSTS).low).toBeLessThan(0.01);
    expect(functionCostUsd({ calls: 3, gbSeconds: 7.2 })).toBeCloseTo(0.0001884, 9);
  });

  it('counts the flow actions of one document from the two flows', () => {
    expect(flowActionRange(FLOW_ACTIONS)).toEqual({ low: 51, high: 95 });
    expect(flowActionRange({ intake: 7, analysis: { low: 1, high: 2 } })).toEqual({ low: 8, high: 9 });
  });
});

describe('formatting', () => {
  it('writes a part to a tenth of a cent and a tiny amount to a hundredth', () => {
    expect(formatUsdFine(0.045245)).toBe('$0.045');
    expect(formatUsdFine(0.00384)).toBe('$0.004');
    expect(formatUsdTiny(0.0007596)).toBe('$0.0008');
  });

  it('writes a range once the two ends read differently', () => {
    expect(formatUsdRange({ low: 0.135, high: 0.3666 })).toBe('$0.14\u2013$0.37');
    expect(formatUsdRange({ low: 0.301, high: 0.304 })).toBe('$0.30');
    expect(formatCentsRange({ low: 0.0231, high: 0.045 })).toBe('2.3\u20134.5\u00A2');
    expect(formatCentsRange({ low: 0.0231, high: 0.0232 })).toBe('2.3\u00A2');
    expect(formatPercentRange({ low: 0.74, high: 0.867 })).toBe('74\u201387%');
  });

  it('writes the price, the usage and the cell of the table', () => {
    expect(RATES.map(rateText)).toEqual([
      '$5.00 per 1,000 pages',
      '$1.00 per million tokens',
      '$5.00 per million tokens',
      '$0.50 per million tokens',
      '$30.00 per million tokens',
    ]);
    const [reading, , input, cached] = RATES;
    expect(usageText(AMENDMENT.document, reading)).toBe('3 pages');
    expect(usageText(AMENDMENT.document, input)).toBe('9,049 tokens');
    expect(usageText(AMENDMENT.document, cached)).toBe('not used');
    expect(partText(AMENDMENT, 'cached')).toBe('\u2013');
    expect(partText(DUA, 'cached')).toBe('$0.004');
    expect(partText(SOW, 'output')).toBe('$0.091');
  });
});

describe('the bars', () => {
  const bars = costBars(SAMPLE_COSTS);

  it('draws every bar to one scale that fits the dearest document', () => {
    expect(bars.axisMax).toBeCloseTo(0.4, 9);
    expect(bars.axisMax).toBeGreaterThanOrEqual(totalRange(SAMPLE_COSTS).high);
    expect(bars.axisMax).toBeLessThan(totalRange(SAMPLE_COSTS).high + AXIS_STEP_USD);
    for (const row of bars.rows) {
      expect(row.widthPercent).toBeGreaterThan(0);
      expect(row.widthPercent).toBeLessThanOrEqual(100);
      expect(row.segments.reduce((sum, segment) => sum + segment.usd, 0)).toBeCloseTo(row.cost.total, 12);
    }
  });

  it('marks the axis from zero to the end every ten cents', () => {
    expect(bars.ticks.map((tick) => tick.label)).toEqual(['$0.00', '$0.10', '$0.20', '$0.30', '$0.40']);
    expect(bars.ticks[0].percent).toBe(0);
    expect(bars.ticks.at(-1)?.percent).toBeCloseTo(100, 9);
  });

  it('labels a segment only when there is room for its amount', () => {
    for (const row of bars.rows) {
      for (const segment of row.segments) expect(segment.showLabel).toBe(segment.usd / bars.axisMax >= 0.1);
    }
    expect(bars.rows[0].segments.map((segment) => segment.showLabel)).toEqual([false, true, true]);
  });

  it('describes a bar in words', () => {
    expect(describeCostRow(bars.rows[0])).toBe('Sample amendment: $0.14 in total. Content Understanding $0.018, Model input $0.045, Model output $0.072.');
  });
});

describe('the lines on the step cards', () => {
  it('puts a cost on the two steps that have one, and on no other', () => {
    expect(stepCost('reads', SAMPLE_COSTS)).toBe('Cost: $0.14\u2013$0.37 a sample document');
    expect(stepCost('function', SAMPLE_COSTS)).toBe('Cost: under a tenth of a cent a document');
    for (const step of STEPS) if (step.id !== 'reads' && step.id !== 'function') expect(stepCost(step.id, SAMPLE_COSTS), step.id).toBeNull();
    for (const id of ['reads', 'function']) expect(STEPS.map((step) => step.id)).toContain(id);
  });
});

describe('everything the pages say about cost', () => {
  const all = collectStrings([
    RATES,
    COST_GROUPS,
    SAMPLES.map((sample) => sample.label),
    costTiles(SAMPLE_COSTS),
    costLead(SAMPLE_COSTS),
    costMention(SAMPLE_COSTS),
    costMethod(SAMPLE_COSTS, SAMPLES),
    costExtras(),
    STEPS.map((step) => stepCost(step.id, SAMPLE_COSTS)),
    COST_TITLE,
    COST_QUESTION,
  ]);

  it('is never empty', () => {
    expect(all.length).toBeGreaterThan(40);
    for (const text of all) expect(text.trim().length).toBeGreaterThan(0);
  });

  it('carries no identifiers, hosts or accounts', () => {
    const forbidden = [
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
      /\.(dynamics|sharepoint|onmicrosoft)\.com/i,
      /\.azurewebsites\.net/i,
      /\.(cognitiveservices|openai|services\.ai)\.azure\.com/i,
      /[\w.-]+@[\w-]+\.[a-z]{2,}/i,
    ];
    for (const text of all) for (const pattern of forbidden) expect(text, `"${text}" matches ${pattern}`).not.toMatch(pattern);
  });

  it('claims nothing the measurements cannot back up', () => {
    const unsupported = [
      /\bpoll/i,
      /\binterval\b/i,
      /\brecurrence\b/i,
      /\bevery\s+(\d+|few|other)\b/i,
      /\bonly\b[^.]*\b(synthetic|made-up)\b/i,
      /reviewed by/i,
      /\bwho (reviewed|approved)\b/i,
    ];
    for (const text of all) for (const pattern of unsupported) expect(text, `"${text}" matches ${pattern}`).not.toMatch(pattern);
  });

  it('says plainly that these are estimates at list prices and what is left out', () => {
    expect(costLead(SAMPLE_COSTS)).toMatch(/estimated/);
    expect(costLead(SAMPLE_COSTS)).toMatch(/list prices/);
    const leftOut = costExtras().map((note) => note.text).join(' ');
    expect(leftOut).toMatch(/review/);
    expect(leftOut).toMatch(/licen[cs]e/);
    expect(leftOut).toMatch(/storage/);
  });
});
