import { describe, expect, it } from 'vitest';
import { makeRow } from '../test/factories';
import { judgmentToShow, previewOf, safeHttpUrl } from './display';

const right = { hasJudgment: true, group: 'Data Right' } as const;

describe('previewOf', () => {
  it('shows the extracted value as is', () => {
    expect(previewOf(makeRow({ aiValue: ' Within 30 days ' }))).toEqual({ text: 'Within 30 days', muted: false });
  });

  it('shows the reviewer answer after a correction, even an emptied one', () => {
    const emptied = makeRow({ aiValue: 'Old value', reviewStatus: 'Corrected', reviewerValue: '' });
    expect(previewOf(emptied)).toEqual({ text: 'Reviewer found no value in the contract.', muted: true });
    const replaced = makeRow({ aiValue: 'Old value', reviewStatus: 'Corrected', reviewerValue: 'New value' });
    expect(previewOf(replaced)).toEqual({ text: 'New value', muted: false });
  });

  it('explains a right that has no text', () => {
    expect(previewOf(makeRow({ aiJudgment: 'Not Addressed', presence: 'Not Found' }, right)).text).toBe('The contract does not address this right.');
    expect(previewOf(makeRow({ aiJudgment: 'Permitted', presence: 'Found' }, right)).text).toBe('No conditions stated.');
  });

  it('explains a detail that has no value', () => {
    expect(previewOf(makeRow({ presence: 'Not Found' })).text).toBe('Not found in this contract.');
    expect(previewOf(makeRow({ presence: 'Unclear' })).text).toBe('Unclear. Needs a reviewer.');
    expect(previewOf(makeRow({ presence: 'Found' })).text).toBe('No value extracted.');
  });
});

describe('judgmentToShow', () => {
  it('hides the judgment for details and for N/A', () => {
    expect(judgmentToShow(makeRow({ aiJudgment: 'N/A' }))).toBeNull();
    expect(judgmentToShow(makeRow({ aiJudgment: 'N/A' }, right))).toBeNull();
    expect(judgmentToShow(makeRow({ aiJudgment: null }, right))).toBeNull();
    expect(judgmentToShow(makeRow({ aiJudgment: 'Permitted' }, right))).toBe('Permitted');
  });

  it('shows the reviewer judgment once corrected', () => {
    const corrected = makeRow({ aiJudgment: 'Permitted', reviewStatus: 'Corrected', reviewerJudgment: 'Prohibited' }, right);
    expect(judgmentToShow(corrected)).toBe('Prohibited');
  });
});

describe('safeHttpUrl', () => {
  it('only passes http and https links', () => {
    expect(safeHttpUrl('https://contoso.sharepoint.com/sites/contracts')).toBe('https://contoso.sharepoint.com/sites/contracts');
    expect(safeHttpUrl('javascript:alert(1)')).toBeNull();
    expect(safeHttpUrl('data:text/html,hello')).toBeNull();
    expect(safeHttpUrl('not a url')).toBeNull();
    expect(safeHttpUrl('')).toBeNull();
  });
});
