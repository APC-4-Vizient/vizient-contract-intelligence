import { describe, expect, it } from 'vitest';
import { DEFAULT_EVIDENCE_STYLE, parseEvidenceStyle } from './evidenceStyle';

describe('parseEvidenceStyle', () => {
  it('keeps a known style', () => {
    expect(parseEvidenceStyle('marker')).toBe('marker');
    expect(parseEvidenceStyle('box')).toBe('box');
    expect(parseEvidenceStyle('highlight')).toBe('highlight');
  });

  it('falls back to the highlight for anything else', () => {
    expect(DEFAULT_EVIDENCE_STYLE).toBe('highlight');
    expect(parseEvidenceStyle(null)).toBe('highlight');
    expect(parseEvidenceStyle(undefined)).toBe('highlight');
    expect(parseEvidenceStyle('neon')).toBe('highlight');
    expect(parseEvidenceStyle('Box')).toBe('highlight');
  });
});
