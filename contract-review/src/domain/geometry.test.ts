import { describe, expect, it } from 'vitest';
import { groupPassages, polygonToRect, scaleRect, topmost } from './geometry';

describe('polygonToRect', () => {
  it('converts a polygon in inches to a box in points', () => {
    expect(polygonToRect([1, 1, 3, 1, 3, 2, 1, 2])).toEqual({ left: 72, top: 72, width: 144, height: 72 });
  });

  it('uses the outer bounds of a skewed polygon', () => {
    expect(polygonToRect([1, 1.5, 3, 1, 3.5, 2, 1.25, 2.25])).toEqual({ left: 72, top: 72, width: 180, height: 90 });
  });

  it('rejects polygons it cannot draw', () => {
    expect(polygonToRect([])).toBeNull();
    expect(polygonToRect([1, 2, 3])).toBeNull();
    expect(polygonToRect([1, 2, 3, 4, 5])).toBeNull();
    expect(polygonToRect([1, 2, Number.NaN, 4])).toBeNull();
  });
});

describe('scaleRect', () => {
  it('scales to pixels and grows by the padding on every side', () => {
    expect(scaleRect({ left: 72, top: 72, width: 144, height: 72 }, 1.5, 2)).toEqual({ left: 106, top: 106, width: 220, height: 112 });
  });
});

describe('groupPassages', () => {
  const line = (top: number, left = 72, width = 400) => ({ left, top, width, height: 12 });

  it('joins wrapped lines into one passage with the box around all of them', () => {
    const lines = [line(100), line(113, 72, 250), line(126)];
    expect(groupPassages(lines)).toEqual([{ bounds: { left: 72, top: 100, width: 400, height: 38 }, lines }]);
  });

  it('keeps a clause together across a paragraph break but splits a quote further down the page', () => {
    const groups = groupPassages([line(100), line(113), line(135), line(400)]);
    expect(groups.map((group) => group.lines.length)).toEqual([3, 1]);
    expect(groups[1].bounds.top).toBe(400);
  });

  it('keeps two columns apart even though their lines sit at the same height', () => {
    const groups = groupPassages([line(100, 72, 200), line(100, 330, 200), line(113, 72, 200), line(113, 330, 200)]);
    expect(groups.map((group) => group.bounds.left)).toEqual([72, 330]);
    expect(groups.map((group) => group.lines.length)).toEqual([2, 2]);
  });

  it('does not depend on the order the lines arrive in, and drops boxes that have no size', () => {
    const groups = groupPassages([line(126), { left: 72, top: 50, width: 0, height: 12 }, line(100), line(113)]);
    expect(groups).toHaveLength(1);
    expect(groups[0].lines.map((entry) => entry.top)).toEqual([100, 113, 126]);
    expect(groupPassages([])).toEqual([]);
  });
});

describe('topmost', () => {
  it('returns the box highest on the page, or null for none', () => {
    const high = { left: 10, top: 5, width: 1, height: 1 };
    const low = { left: 0, top: 50, width: 1, height: 1 };
    expect(topmost([low, high])).toBe(high);
    expect(topmost([])).toBeNull();
  });
});
