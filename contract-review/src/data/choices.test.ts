import { describe, expect, it } from 'vitest';
import { aiJudgments, checklistGroups, contractStatuses, documentTypes, presences, reviewerJudgments, reviewStatuses } from './choices';
import type { Codec } from './choices';

function roundTrips<K extends number, L extends string>(codec: Codec<K, L>): boolean {
  return codec.labels.length > 0 && codec.labels.every((label) => codec.label(codec.code(label)) === label);
}

describe('choice codecs', () => {
  it('round-trips every label', () => {
    expect(roundTrips(documentTypes)).toBe(true);
    expect(roundTrips(contractStatuses)).toBe(true);
    expect(roundTrips(presences)).toBe(true);
    expect(roundTrips(aiJudgments)).toBe(true);
    expect(roundTrips(reviewerJudgments)).toBe(true);
    expect(roundTrips(reviewStatuses)).toBe(true);
    expect(roundTrips(checklistGroups)).toBe(true);
  });

  it('matches the Dataverse values', () => {
    expect(contractStatuses.code('Ready for Review')).toBe(651200002);
    expect(presences.code('Unclear')).toBe(651200002);
    expect(reviewStatuses.label(651200003)).toBe('Rejected');
  });

  it('gives no label for an empty or unknown value and refuses an unknown label', () => {
    expect(presences.label(null)).toBeNull();
    expect(presences.label(undefined)).toBeNull();
    expect(presences.label(1)).toBeNull();
    expect(() => {
      // @ts-expect-error "Maybe" is not a presence
      presences.code('Maybe');
    }).toThrow('Unknown choice label');
  });

  it('keeps the AI and reviewer judgment lists identical', () => {
    expect(reviewerJudgments.labels).toEqual(aiJudgments.labels);
  });
});
