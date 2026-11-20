import type { Rect } from '../domain/geometry';
import type { TextRun } from './types';

const MIN_NEEDLE = 12;
const PREFIX_LENGTHS = [80, 50, 30, 20];

const SINGLE_QUOTES = /[\u2018\u2019\u201A\u201B\u2032]/;
const DOUBLE_QUOTES = /[\u201C\u201D\u201E\u201F\u2033]/;
const DASHES = /[\u2010-\u2015\u2212]/;
const WHITESPACE = /\s/;

/** Folds one UTF-16 unit to what the search compares: case, quotes, dashes, spaces and ligatures are all flattened. */
function fold(unit: string): string {
  if (unit === '\u00AD' || unit === '\u200B') return '';
  if (SINGLE_QUOTES.test(unit)) return "'";
  if (DOUBLE_QUOTES.test(unit)) return '"';
  if (DASHES.test(unit)) return '-';
  if (WHITESPACE.test(unit)) return ' ';
  return unit.normalize('NFKC').toLowerCase();
}

interface Haystack {
  text: string;
  /** Source run index of each character, or -1 for a space added between runs. */
  run: number[];
  /** Index of each character within its source run's text. */
  offset: number[];
}

function buildHaystack(runs: readonly TextRun[]): Haystack {
  const chars: string[] = [];
  const run: number[] = [];
  const offset: number[] = [];

  const push = (folded: string, runIndex: number, at: number): void => {
    for (let i = 0; i < folded.length; i += 1) {
      const char = folded[i];
      if (char === ' ' && (chars.length === 0 || chars[chars.length - 1] === ' ')) continue;
      chars.push(char);
      run.push(runIndex);
      offset.push(at);
    }
  };

  runs.forEach((entry, index) => {
    push(' ', -1, 0);
    for (let i = 0; i < entry.text.length; i += 1) push(fold(entry.text[i]), index, i);
  });
  return { text: chars.join(''), run, offset };
}

function foldNeedle(quote: string): string {
  const chars: string[] = [];
  for (let i = 0; i < quote.length; i += 1) {
    const folded = fold(quote[i]);
    for (let j = 0; j < folded.length; j += 1) {
      const char = folded[j];
      if (char === ' ' && (chars.length === 0 || chars[chars.length - 1] === ' ')) continue;
      chars.push(char);
    }
  }
  return chars.join('').trim();
}

/** Joins boxes that sit on the same line and nearly touch, so a sentence reads as one highlight per line. */
function mergeLines(rects: readonly Rect[]): Rect[] {
  const merged: Rect[] = [];
  for (const rect of rects) {
    const last = merged.at(-1);
    if (last) {
      const tall = Math.max(last.height, rect.height);
      const sameLine = Math.abs(last.top - rect.top) < tall * 0.5;
      const gap = rect.left - (last.left + last.width);
      if (sameLine && gap < tall) {
        const left = Math.min(last.left, rect.left);
        const top = Math.min(last.top, rect.top);
        const right = Math.max(last.left + last.width, rect.left + rect.width);
        const bottom = Math.max(last.top + last.height, rect.top + rect.height);
        merged[merged.length - 1] = { left, top, width: right - left, height: bottom - top };
        continue;
      }
    }
    merged.push(rect);
  }
  return merged;
}

function rectsFor(runs: readonly TextRun[], haystack: Haystack, start: number, length: number): Rect[] {
  const spans = new Map<number, { first: number; last: number }>();
  for (let i = start; i < start + length; i += 1) {
    const runIndex = haystack.run[i];
    if (runIndex < 0) continue;
    const at = haystack.offset[i];
    const span = spans.get(runIndex);
    if (span) span.last = at;
    else spans.set(runIndex, { first: at, last: at });
  }

  const rects: Rect[] = [];
  for (const [runIndex, span] of spans) {
    const entry = runs[runIndex];
    const count = Math.max(entry.text.length, 1);
    rects.push({
      left: entry.left + (entry.width * span.first) / count,
      top: entry.top,
      width: (entry.width * (span.last - span.first + 1)) / count,
      height: entry.height,
    });
  }
  return mergeLines(rects);
}

/**
 * Finds a clause quote in a page's text and returns its boxes in points, or null when it is not there.
 * Tries the whole quote first, then shorter prefixes, because the AI quote can drift from the page text near its end.
 */
export function locateQuote(runs: readonly TextRun[], quote: string): Rect[] | null {
  const needle = foldNeedle(quote);
  if (needle.length < MIN_NEEDLE) return null;

  const haystack = buildHaystack(runs);
  const candidates = [needle, ...PREFIX_LENGTHS.filter((size) => size < needle.length).map((size) => needle.slice(0, size).trimEnd())];
  for (const candidate of candidates) {
    if (candidate.length < MIN_NEEDLE) continue;
    const start = haystack.text.indexOf(candidate);
    if (start >= 0) return rectsFor(runs, haystack, start, candidate.length);
  }
  return null;
}
