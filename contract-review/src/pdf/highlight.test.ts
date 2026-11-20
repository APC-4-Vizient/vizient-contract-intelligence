import { describe, expect, it } from 'vitest';
import { resolveHighlight } from './highlight';
import type { HighlightTarget, TextMatch } from './types';

const square = [1, 1, 2, 1, 2, 2, 1, 2];
const match: TextMatch = { nonce: 1, page: 5, rects: [{ left: 1, top: 2, width: 3, height: 4 }] };

function target(overrides: Partial<HighlightTarget> = {}): HighlightTarget {
  return { nonce: 1, page: 4, regions: [], quote: 'quoted clause', ...overrides };
}

describe('resolveHighlight', () => {
  it('places nothing without a target', () => {
    expect(resolveHighlight(null, match).method).toBe('none');
  });

  it('prefers the AI regions and anchors on the earliest page', () => {
    const regions = [
      { page: 7, polygon: square },
      { page: 6, polygon: square },
    ];
    const resolved = resolveHighlight(target({ regions }), match);
    expect(resolved.method).toBe('regions');
    expect(resolved.anchorPage).toBe(6);
    expect([...resolved.byPage.keys()].sort((a, b) => a - b)).toEqual([6, 7]);
    expect(resolved.anchorRect).toEqual({ left: 72, top: 72, width: 72, height: 72 });
  });

  it('skips regions that cannot be drawn', () => {
    expect(resolveHighlight(target({ regions: [{ page: 2, polygon: [1, 2, 3] }] }), null).method).toBe('page');
  });

  it('uses a text match only when it belongs to the same click', () => {
    expect(resolveHighlight(target(), match)).toMatchObject({ method: 'text', anchorPage: 5 });
    expect(resolveHighlight(target({ nonce: 2 }), match).method).toBe('page');
  });

  it('falls back to the page, then to nothing', () => {
    expect(resolveHighlight(target(), null)).toMatchObject({ method: 'page', anchorPage: 4 });
    expect(resolveHighlight(target({ page: null }), null).method).toBe('none');
  });
});
