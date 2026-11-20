import { describe, expect, it } from 'vitest';
import { parseRegions } from './regions';

const square = [1, 1, 2, 1, 2, 2, 1, 2];

describe('parseRegions', () => {
  it('reads the saved JSON', () => {
    expect(parseRegions(JSON.stringify([{ page: 3, polygon: square }]))).toEqual([{ page: 3, polygon: square }]);
  });

  it('returns nothing for empty or malformed input', () => {
    expect(parseRegions(null)).toEqual([]);
    expect(parseRegions('')).toEqual([]);
    expect(parseRegions('{not json')).toEqual([]);
    expect(parseRegions('{"page":1}')).toEqual([]);
  });

  it('drops entries that cannot be drawn and keeps the rest', () => {
    const raw = JSON.stringify([
      { page: 0, polygon: square },
      { page: 2.5, polygon: square },
      { page: 2, polygon: [1, 2, 3] },
      { page: 2, polygon: [1, 2, 3, 'x'] },
      'text',
      null,
      { page: 4, polygon: square },
    ]);
    expect(parseRegions(raw)).toEqual([{ page: 4, polygon: square }]);
  });

  it('caps the number of regions', () => {
    const many = Array.from({ length: 100 }, () => ({ page: 1, polygon: square }));
    expect(parseRegions(JSON.stringify(many))).toHaveLength(60);
  });
});
