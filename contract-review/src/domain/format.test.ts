import { describe, expect, it } from 'vitest';
import { formatCount, formatUsd } from './format';

describe('formatUsd', () => {
  it('writes dollars with cents, or without them when asked', () => {
    expect(formatUsd(1234.5)).toBe('$1,234.50');
    expect(formatUsd(1234.4, false)).toBe('$1,234');
  });
});

describe('formatCount', () => {
  it('rounds to a whole number with thousands separators', () => {
    expect(formatCount(1234.6)).toBe('1,235');
    expect(formatCount(193241136)).toBe('193,241,136');
  });
});
