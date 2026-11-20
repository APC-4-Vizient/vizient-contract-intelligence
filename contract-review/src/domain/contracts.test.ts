import { describe, expect, it } from 'vitest';
import { makeContract } from '../test/factories';
import { contractTitle, matchesTab, tabCounts } from './contracts';

describe('tabs', () => {
  const contracts = [
    makeContract({ id: '1', status: 'Ready for Review', totalCount: 20, completeness: 80 }),
    makeContract({ id: '2', status: 'In Review', totalCount: 20, completeness: 40 }),
    makeContract({ id: '3', status: 'Extracting', totalCount: null, completeness: null }),
    makeContract({ id: '4', status: 'Approved', totalCount: 20, completeness: 59.9 }),
    makeContract({ id: '5', status: 'Failed', totalCount: 0, completeness: 0 }),
  ];

  it('counts each tab', () => {
    expect(tabCounts(contracts)).toEqual({ all: 5, ready: 2, low: 2 });
  });

  it('puts only analyzed contracts under 60 percent in Low completeness', () => {
    expect(matchesTab(makeContract({ totalCount: 20, completeness: 60 }), 'low')).toBe(false);
    expect(matchesTab(makeContract({ totalCount: 0, completeness: 0 }), 'low')).toBe(false);
    expect(matchesTab(makeContract({ totalCount: 20, completeness: 59 }), 'low')).toBe(true);
  });
});

describe('contractTitle', () => {
  it('uses the vendor, then the file name, then a placeholder', () => {
    expect(contractTitle(makeContract({ vendor: ' BluePine ', name: 'bluepine-sow.pdf' }))).toBe('BluePine');
    expect(contractTitle(makeContract({ vendor: '', name: 'bluepine-sow.pdf' }))).toBe('bluepine-sow.pdf');
    expect(contractTitle(makeContract({ vendor: ' ', name: '' }))).toBe('Untitled contract');
  });
});
