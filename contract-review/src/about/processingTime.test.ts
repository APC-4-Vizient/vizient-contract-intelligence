import { describe, expect, it } from 'vitest';
import { STEPS } from './architecture';
import {
  CLOCK_NOTES,
  KIND_LABELS,
  KINDS,
  PROCESSING,
  PROCESSING_QUESTION,
  PROCESSING_TITLE,
  REVIEW_STEP,
  STAGES,
  START_STEP,
  clockAtStep,
  describeRow,
  formatSize,
  formatSpan,
  formatSpanRange,
  formatSpanWords,
  formatStopwatch,
  isStageId,
  kindRange,
  middleRun,
  processingLead,
  processingMethod,
  processingTakeaways,
  processingTiles,
  runNote,
  slowestRun,
  stageEnds,
  stageRange,
  stepTiming,
  timelineGeometry,
  totalRange,
  totalSeconds,
} from './processingTime';
import type { ProcessingRun, StageId } from './processingTime';

const RUNS = PROCESSING.runs;
const [SOW, AMENDMENT, TEST_DOC] = RUNS;

function collectStrings(value: unknown, into: string[] = []): string[] {
  if (typeof value === 'string') into.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectStrings(item, into));
  else if (value && typeof value === 'object') Object.values(value).forEach((item) => collectStrings(item, into));
  return into;
}

describe('the measured runs', () => {
  it('has a unique id per run and a positive, finite time in every stage', () => {
    expect(new Set(RUNS.map((run) => run.id)).size).toBe(RUNS.length);
    for (const run of RUNS) {
      for (const stage of STAGES) {
        expect(Number.isFinite(run.seconds[stage.id]), `${run.id} ${stage.id}`).toBe(true);
        expect(run.seconds[stage.id], `${run.id} ${stage.id}`).toBeGreaterThan(0);
      }
    }
  });

  it('adds the stages up to the time from saved PDF to Ready for Review', () => {
    expect(totalSeconds(SOW)).toBeCloseTo(136.79, 2);
    expect(totalSeconds(AMENDMENT)).toBeCloseTo(66.13, 2);
    expect(totalSeconds(TEST_DOC)).toBeCloseTo(65.68, 2);
  });

  it('marks the clock at the end of each stage, in order, finishing at the total', () => {
    for (const run of RUNS) {
      const ends = stageEnds(run);
      let last = 0;
      for (const stage of STAGES) {
        expect(ends[stage.id]).toBeGreaterThan(last);
        last = ends[stage.id];
      }
      expect(last).toBeCloseTo(totalSeconds(run), 9);
    }
  });
});

describe('the stages and the diagram', () => {
  it('has one stage for each step between the first and the last, in the same order', () => {
    expect(STEPS[0].id).toBe(START_STEP);
    expect(STEPS.at(-1)?.id).toBe(REVIEW_STEP);
    expect(STEPS.slice(1, -1).map((step) => step.id)).toEqual(STAGES.map((stage) => stage.id));
  });

  it('gives every stage a kind that has a legend entry', () => {
    for (const stage of STAGES) expect(KINDS).toContain(stage.kind);
    for (const kind of KINDS) expect(KIND_LABELS[kind].length).toBeGreaterThan(0);
  });

  it('recognizes stage ids and nothing else', () => {
    expect(isStageId('reads')).toBe(true);
    expect(isStageId(START_STEP)).toBe(false);
    expect(isStageId(null)).toBe(false);
  });
});

describe('the summary', () => {
  it('finds the middle and the slowest run', () => {
    expect(middleRun(RUNS).id).toBe('amendment');
    expect(slowestRun(RUNS).id).toBe('sow');
    expect(totalRange(RUNS).low).toBeCloseTo(65.68, 2);
    expect(totalRange(RUNS).high).toBeCloseTo(136.79, 2);
  });

  it('ranges over the runs for one stage and for one kind of stage', () => {
    expect(stageRange('reads', RUNS)).toEqual({ low: 18.78, high: 89.53 });
    expect(kindRange('ai', RUNS)).toEqual({ low: 18.78, high: 89.53 });
    expect(kindRange('wait', RUNS).high).toBeCloseTo(40.09, 2);
  });

  it('puts four tiles together from the numbers', () => {
    const tiles = processingTiles(RUNS);
    expect(tiles.map((tile) => tile.label)).toEqual(['Typical run', 'Slowest run', 'Waiting', 'AI reading']);
    expect(tiles[0].value).toBe('1m 6s');
    expect(tiles[1].value).toBe('2m 17s');
    expect(tiles[2].value).toBe('39\u201340s');
    expect(tiles[3].value).toBe('19\u201390s');
  });

  it('works from the runs it is given', () => {
    const only: ProcessingRun[] = [AMENDMENT];
    expect(processingLead(only)).toContain('took 1m 6s in the one run we timed');
    expect(processingTiles(only)[2].value).toBe('40s');
  });
});

describe('claims the copy makes about the numbers', () => {
  it('says the AI reading is the part that changes with the document', () => {
    const spread = (id: StageId) => stageRange(id, RUNS).high - stageRange(id, RUNS).low;
    for (const stage of STAGES) {
      if (stage.kind !== 'ai') expect(spread('reads')).toBeGreaterThan(spread(stage.id) * 5);
    }
  });

  it('says file size did not predict the AI reading', () => {
    const bySize = [...RUNS].sort((a, b) => a.sizeKb - b.sizeKb).map((run) => run.id);
    const byReading = [...RUNS].sort((a, b) => a.seconds.reads - b.seconds.reads).map((run) => run.id);
    expect(byReading).not.toEqual(bySize);
  });

  it('says pickup and hand-off came out almost the same every time', () => {
    for (const id of ['noticed', 'wakes'] as const) {
      const { low, high } = stageRange(id, RUNS);
      expect(high - low, id).toBeLessThan(2);
    }
  });
});

describe('formatting', () => {
  it('writes short spans with a decimal and long spans in whole seconds', () => {
    expect(formatSpan(0.58)).toBe('0.6s');
    expect(formatSpan(7.75)).toBe('7.8s');
    expect(formatSpan(9.97)).toBe('10s');
    expect(formatSpan(32.26)).toBe('32s');
    expect(formatSpan(66.13)).toBe('1m 6s');
    expect(formatSpan(136.79)).toBe('2m 17s');
    expect(formatSpan(-5)).toBe('0.0s');
  });

  it('writes a range once the two ends read differently', () => {
    expect(formatSpanRange({ low: 31.3, high: 32.26 })).toBe('31\u201332s');
    expect(formatSpanRange({ low: 0.58, high: 1.53 })).toBe('0.6\u20131.5s');
    expect(formatSpanRange({ low: 18.78, high: 89.53 })).toBe('19\u201390s');
    expect(formatSpanRange({ low: 65.68, high: 136.79 })).toBe('1m 6s to 2m 17s');
    expect(formatSpanRange({ low: 66.13, high: 66.4 })).toBe('1m 6s');
  });

  it('writes the clock face and the spoken form', () => {
    expect(formatStopwatch(0)).toBe('0:00');
    expect(formatStopwatch(66.13)).toBe('1:06');
    expect(formatStopwatch(136.79)).toBe('2:17');
    expect(formatSpanWords(66)).toBe('1 minute 6 seconds');
    expect(formatSpanWords(60)).toBe('1 minute');
    expect(formatSpanWords(137)).toBe('2 minutes 17 seconds');
    expect(formatSpanWords(1)).toBe('1 second');
    expect(formatSpanWords(0)).toBe('0 seconds');
  });

  it('rounds file sizes the way the notes do', () => {
    expect(formatSize(900)).toBe('0.9 MB');
    expect(formatSize(7)).toBe('7 KB');
    expect(runNote(SOW)).toBe('larger contract, about 0.9 MB');
  });
});

describe('the clock on the tour', () => {
  it('reads zero when the PDF arrives and the whole run in the overview', () => {
    expect(clockAtStep(AMENDMENT, START_STEP)).toEqual({ seconds: 0, note: CLOCK_NOTES.start });
    expect(clockAtStep(AMENDMENT, null)).toEqual({ seconds: totalSeconds(AMENDMENT), note: CLOCK_NOTES.total });
  });

  it('reads the end of the stage on a stage step, and stops at Ready for Review on the last step', () => {
    expect(clockAtStep(AMENDMENT, 'wakes')).toEqual({ seconds: stageEnds(AMENDMENT).wakes, note: CLOCK_NOTES.running });
    expect(clockAtStep(AMENDMENT, 'findings').seconds).toBeCloseTo(totalSeconds(AMENDMENT), 9);
    expect(clockAtStep(AMENDMENT, REVIEW_STEP)).toEqual({ seconds: totalSeconds(AMENDMENT), note: CLOCK_NOTES.stopped });
  });

  it('never runs backwards from one step to the next', () => {
    for (const run of RUNS) {
      let last = -1;
      for (const step of STEPS) {
        const { seconds } = clockAtStep(run, step.id);
        expect(seconds, `${run.id} ${step.id}`).toBeGreaterThanOrEqual(last);
        last = seconds;
      }
    }
  });
});

describe('the lines on the step cards', () => {
  it('has a line for every step, and none for a step that is not in the diagram', () => {
    for (const step of STEPS) expect(stepTiming(step.id, RUNS), step.id).not.toBeNull();
    expect(stepTiming('nothing', RUNS)).toBeNull();
  });

  it('shows what was measured, and says when the time depends on the document', () => {
    expect(stepTiming('noticed', RUNS)).toBe('Measured: 31\u201332s');
    expect(stepTiming('record', RUNS)).toBe('Measured: 0.6\u20131.5s');
    expect(stepTiming('reads', RUNS)).toBe('Measured: 19\u201390s, depending on the document');
    expect(stepTiming(START_STEP, RUNS)).toBe('Starts the clock');
    expect(stepTiming(REVIEW_STEP, RUNS)).toMatch(/not timed/i);
  });
});

describe('the timeline', () => {
  const geometry = timelineGeometry(RUNS);

  it('draws every bar to one scale that fits the longest run', () => {
    expect(geometry.axisMax % 30).toBe(0);
    expect(geometry.axisMax).toBeGreaterThanOrEqual(totalRange(RUNS).high);
    expect(geometry.axisMax).toBeLessThan(totalRange(RUNS).high + 30);
    for (const row of geometry.rows) {
      expect(row.widthPercent).toBeGreaterThan(0);
      expect(row.widthPercent).toBeLessThanOrEqual(100);
      expect(row.segments.reduce((sum, segment) => sum + segment.seconds, 0)).toBeCloseTo(row.total, 9);
    }
    expect(Math.max(...geometry.rows.map((row) => row.widthPercent))).toBeGreaterThan(80);
  });

  it('marks the axis from zero to the end every half minute', () => {
    expect(geometry.ticks[0]).toEqual({ seconds: 0, percent: 0, label: '0:00' });
    expect(geometry.ticks.at(-1)?.percent).toBe(100);
    expect(geometry.ticks.map((tick) => tick.seconds)).toEqual([0, 30, 60, 90, 120, 150]);
  });

  it('labels a segment only when there is room for the label', () => {
    for (const row of geometry.rows) {
      for (const segment of row.segments) expect(segment.showLabel).toBe(segment.seconds / geometry.axisMax >= 0.1);
    }
    expect(geometry.rows[0].segments.find((segment) => segment.id === 'reads')?.showLabel).toBe(true);
    expect(geometry.rows[0].segments.find((segment) => segment.id === 'record')?.showLabel).toBe(false);
  });

  it('describes a bar in words', () => {
    expect(describeRow(geometry.rows[1])).toBe(
      'Amendment: 1 minute 6 seconds in total. Pickup 32s, Intake flow 1.5s, Hand-off 7.8s, Function 3.3s, AI reading 19s, Write-back 2.4s.',
    );
  });
});

describe('everything the pages say about processing time', () => {
  const all = collectStrings([
    STAGES,
    KIND_LABELS,
    RUNS.map((run) => [run.label, runNote(run)]),
    processingTiles(RUNS),
    processingLead(RUNS),
    processingTakeaways(RUNS),
    processingMethod(PROCESSING),
    CLOCK_NOTES,
    STEPS.map((step) => stepTiming(step.id, RUNS)),
    PROCESSING_TITLE,
    PROCESSING_QUESTION,
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

  it('says plainly that a person\u2019s review is not included', () => {
    expect(processingLead(RUNS)).toMatch(/not included/);
    expect(CLOCK_NOTES.stopped).toMatch(/not timed/);
  });
});
