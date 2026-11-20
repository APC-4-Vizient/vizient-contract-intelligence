import { describe, expect, it } from 'vitest';
import { parseRoute } from './useRoute';

describe('parseRoute', () => {
  it('reads a contract link', () => {
    expect(parseRoute('#/contract/abc-123')).toEqual({ name: 'contract', id: 'abc-123' });
    expect(parseRoute('#/contract/abc-123/')).toEqual({ name: 'contract', id: 'abc-123' });
  });

  it('reads the how-it-works and cost pages', () => {
    expect(parseRoute('#/how-it-works')).toEqual({ name: 'how-it-works' });
    expect(parseRoute('#/how-it-works/')).toEqual({ name: 'how-it-works' });
    expect(parseRoute('#/cost')).toEqual({ name: 'cost' });
    expect(parseRoute('#/cost/')).toEqual({ name: 'cost' });
  });

  it('treats anything else as the list', () => {
    for (const hash of [
      '',
      '#/',
      '#/contract/',
      '#/contract/a b',
      '#/contract/../x',
      '#/contract/abc/def',
      '#/other',
      '#/cost/extra',
      '#/how-it-works/extra',
    ]) {
      expect(parseRoute(hash)).toEqual({ name: 'list' });
    }
  });
});
