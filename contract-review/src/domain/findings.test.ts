import { describe, expect, it } from 'vitest';
import { makeContract, makeFinding, makeItem, makeRow } from '../test/factories';
import { applyContractPatch, applyFindingPatch, groupRows, joinRows } from './findings';

describe('joinRows', () => {
  it('orders rows as the checklist does and labels an orphan from its finding', () => {
    const items = [makeItem({ id: 'i2', label: 'Second', sortOrder: 2 }), makeItem({ id: 'i1', label: 'First', sortOrder: 1 })];
    const rows = joinRows(
      [
        makeFinding({ id: 'f2', itemId: 'i2' }),
        makeFinding({ id: 'f9', itemId: 'gone', name: 'Orphan', aiJudgment: 'Prohibited' }),
        makeFinding({ id: 'f1', itemId: 'i1' }),
      ],
      items,
    );
    expect(rows.map((row) => row.finding.id)).toEqual(['f1', 'f2', 'f9']);
    expect(rows[2].item).toMatchObject({ label: 'Orphan', group: 'Data Right', hasJudgment: true });
  });
});

describe('groupRows', () => {
  it('lists details before rights and leaves out empty and manual groups', () => {
    const rows = [
      makeRow({ id: 'r' }, { group: 'Data Right' }),
      makeRow({ id: 'm' }, { group: 'Manual' }),
      makeRow({ id: 'd' }, { group: 'Contract Detail' }),
    ];
    const grouped = groupRows(rows).map((entry) => [entry.group, entry.rows.map((row) => row.finding.id)]);
    expect(grouped).toEqual([
      ['Contract Detail', ['d']],
      ['Data Right', ['r']],
    ]);
    expect(groupRows([])).toEqual([]);
  });
});

describe('patches', () => {
  it('changes only the finding fields in the patch, and lets an empty answer through', () => {
    const finding = makeFinding({ reviewStatus: 'Pending', reviewerValue: 'keep', reviewerNotes: 'note' });
    expect(applyFindingPatch(finding, { reviewStatus: 'Accepted' })).toMatchObject({
      reviewStatus: 'Accepted',
      reviewerValue: 'keep',
      reviewerNotes: 'note',
    });
    expect(applyFindingPatch(finding, { reviewerValue: '' }).reviewerValue).toBe('');
  });

  it('changes only the contract fields in the patch, and lets zero through', () => {
    const contract = makeContract({ status: 'Ready for Review', foundCount: 5, completeness: 25 });
    expect(applyContractPatch(contract, { status: 'In Review' })).toMatchObject({ status: 'In Review', foundCount: 5, completeness: 25 });
    expect(applyContractPatch(contract, { foundCount: 0, completeness: 0 })).toMatchObject({ foundCount: 0, completeness: 0 });
  });
});
