import { describe, expect, it } from 'vitest';
import { makeFinding, makeRow } from '../test/factories';
import { canApprove, isConfidentPending, isFoundNow, needsAttention, summarize } from './completeness';

const right = { hasJudgment: true, group: 'Data Right' } as const;

describe('isFoundNow', () => {
  it('follows the AI while a finding is pending', () => {
    expect(isFoundNow(makeRow({ presence: 'Found' }))).toBe(true);
    expect(isFoundNow(makeRow({ presence: 'Not Found' }))).toBe(false);
    expect(isFoundNow(makeRow({ presence: 'Unclear' }))).toBe(false);
  });

  it('removes a rejected finding', () => {
    expect(isFoundNow(makeRow({ presence: 'Found', reviewStatus: 'Rejected' }))).toBe(false);
  });

  it('counts an unclear finding once the reviewer accepts an answer the AI gave', () => {
    expect(isFoundNow(makeRow({ presence: 'Unclear', reviewStatus: 'Accepted', aiValue: '30 days' }))).toBe(true);
    expect(isFoundNow(makeRow({ presence: 'Unclear', reviewStatus: 'Accepted', aiValue: '' }))).toBe(false);
    expect(isFoundNow(makeRow({ presence: 'Not Found', reviewStatus: 'Accepted' }))).toBe(false);
  });

  it('follows the reviewer after a correction', () => {
    expect(isFoundNow(makeRow({ presence: 'Not Found', reviewStatus: 'Corrected', reviewerValue: 'Acme' }))).toBe(true);
    expect(isFoundNow(makeRow({ presence: 'Found', reviewStatus: 'Corrected', reviewerValue: '  ' }))).toBe(false);
  });

  it('uses the judgment for rights and does not count Not Addressed', () => {
    expect(isFoundNow(makeRow({ presence: 'Unclear', reviewStatus: 'Accepted', aiJudgment: 'Prohibited' }, right))).toBe(true);
    expect(isFoundNow(makeRow({ presence: 'Unclear', reviewStatus: 'Accepted', aiJudgment: 'Not Addressed' }, right))).toBe(false);
    expect(isFoundNow(makeRow({ presence: 'Not Found', reviewStatus: 'Corrected', reviewerJudgment: 'Conditional' }, right))).toBe(true);
    expect(isFoundNow(makeRow({ presence: 'Found', reviewStatus: 'Corrected', reviewerJudgment: 'Not Addressed' }, right))).toBe(false);
  });
});

describe('needsAttention and isConfidentPending', () => {
  it('flags pending findings the AI did not find', () => {
    expect(needsAttention(makeFinding({ presence: 'Not Found' }))).toBe(true);
    expect(needsAttention(makeFinding({ presence: 'Unclear' }))).toBe(true);
    expect(needsAttention(makeFinding({ presence: 'Found' }))).toBe(false);
    expect(needsAttention(makeFinding({ presence: 'Unclear', reviewStatus: 'Accepted' }))).toBe(false);
  });

  it('marks only pending Found findings as confident', () => {
    expect(isConfidentPending(makeFinding({ presence: 'Found' }))).toBe(true);
    expect(isConfidentPending(makeFinding({ presence: 'Found', reviewStatus: 'Rejected' }))).toBe(false);
    expect(isConfidentPending(makeFinding({ presence: 'Unclear' }))).toBe(false);
  });
});

describe('summarize', () => {
  const rows = [
    makeRow({ presence: 'Found' }),
    makeRow({ presence: 'Found', reviewStatus: 'Rejected' }),
    makeRow({ presence: 'Not Found', reviewStatus: 'Corrected', reviewerValue: 'Acme' }),
    makeRow({ presence: 'Unclear' }),
    makeRow({ presence: 'Not Found', reviewStatus: 'Accepted' }),
    makeRow({ presence: 'Found', reviewStatus: 'Accepted' }),
  ];

  it('counts the current answers, not only the AI answers', () => {
    expect(summarize(rows)).toEqual({
      total: 6,
      found: 3,
      percent: 50,
      aiFound: 3,
      pending: 2,
      accepted: 2,
      corrected: 1,
      rejected: 1,
      attention: 1,
    });
  });

  it('rounds the percentage to one decimal and handles an empty list', () => {
    const twoOfThree = [makeRow({ presence: 'Found' }), makeRow({ presence: 'Found' }), makeRow({ presence: 'Not Found' })];
    expect(summarize(twoOfThree).percent).toBe(66.7);
    expect(summarize([]).percent).toBe(0);
  });
});

describe('canApprove', () => {
  it('needs findings and none left pending', () => {
    expect(canApprove([])).toBe(false);
    expect(canApprove([makeRow({ reviewStatus: 'Accepted' }), makeRow({ reviewStatus: 'Rejected' })])).toBe(true);
    expect(canApprove([makeRow({ reviewStatus: 'Accepted' }), makeRow({ reviewStatus: 'Pending' })])).toBe(false);
  });
});
