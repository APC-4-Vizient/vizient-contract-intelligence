import { describe, expect, it } from 'vitest';
import type { Contract } from '../data/types';
import { referenceNumbers, suggestParent } from './parents';

function contract(fields: Partial<Contract> & Pick<Contract, 'id'>): Contract {
  return {
    name: `${fields.id}.pdf`,
    vendor: '',
    vizientEntity: '',
    documentType: null,
    identifier: '',
    effectiveDate: null,
    expirationDate: null,
    status: null,
    foundCount: null,
    totalCount: null,
    completeness: null,
    hasParentReference: false,
    processedOn: null,
    errorMessage: '',
    createdOn: null,
    sharePointUrl: '',
    parentContractId: null,
    ownerId: null,
    legalReviewerId: null,
    ...fields,
  };
}

describe('referenceNumbers', () => {
  it('keeps agreement numbers and drops dates and bare years', () => {
    expect(referenceNumbers('Statement of Work No. BP-SOW-2025-014 dated March 3, 2025 and opportunity 7654321')).toEqual([
      'BP-SOW-2025-014',
      '7654321',
    ]);
    expect(referenceNumbers('Master Agreement dated June 9, 2017, restated 03/04/2019 and 2019-05-06')).toEqual([]);
  });

  it('lists a repeated number once', () => {
    expect(referenceNumbers('No. 7654321 (the "SOW"), the SOW no. 7654321')).toEqual(['7654321']);
  });
});

describe('suggestParent', () => {
  const sow = contract({ id: 'sow', identifier: 'BP-SOW-2025-014', documentType: 'SOW' });
  const other = contract({ id: 'other', identifier: 'ZZ-100200' });
  const amendment = contract({ id: 'amend', identifier: 'BP-SOW-2025-014-A1', documentType: 'Amendment' });
  const reference = 'Statement of Work No. BP-SOW-2025-014 dated March 3, 2025';

  it('suggests the contract whose number is the one cited, never the contract itself', () => {
    expect(suggestParent(reference, amendment, [sow, other, amendment])).toEqual({ contract: sow, match: 'BP-SOW-2025-014' });
  });

  it('falls back to the file name, but prefers a matching contract number over it', () => {
    const named = contract({ id: 'named', name: 'Acme SOW Opp# 7654321_final.pdf' });
    const numbered = contract({ id: 'numbered', identifier: '7654321' });
    expect(suggestParent('Opportunity No. 7654321', amendment, [amendment, named, other])?.contract.id).toBe('named');
    expect(suggestParent('Opportunity No. 7654321', amendment, [amendment, named, numbered])?.contract.id).toBe('numbered');
  });

  it('stays quiet when the cited agreement is not uploaded or several match equally well', () => {
    expect(suggestParent('Master Services Agreement MSA-2019-0042 dated June 9, 2017', amendment, [sow, other, amendment])).toBeNull();
    const twin = contract({ id: 'twin', identifier: 'BP-SOW-2025-014', documentType: 'SOW' });
    expect(suggestParent(reference, amendment, [sow, twin, amendment])).toBeNull();
  });

  it('lets the kind of agreement the reference names break a tie between equal numbers', () => {
    const shared = 'BP-SOW-2025-014';
    const draft = contract({ id: 'draft', identifier: shared, documentType: 'Amendment' });
    const copy = contract({ id: 'copy', identifier: shared, documentType: 'Amendment' });
    expect(suggestParent(reference, draft, [sow, draft, copy])?.contract.id).toBe('sow');
    // Naming both kinds proves nothing, and a number that merely contains "SOW" names no kind at all.
    expect(suggestParent('Amendment No. 1 to the Statement of Work No. BP-SOW-2025-014', draft, [sow, draft, copy])).toBeNull();
    expect(suggestParent('Agreement No. BP-SOW-2025-014', draft, [sow, draft, copy])).toBeNull();
  });

  it('matches whole numbers only', () => {
    const longer = contract({ id: 'longer', identifier: '1234567' });
    expect(suggestParent('Opportunity No. 123456', amendment, [amendment, longer])).toBeNull();
  });

  it('never suggests a descendant, and says nothing once a parent is linked', () => {
    const child = contract({ id: 'child', identifier: 'BP-SOW-2025-014', parentContractId: 'amend' });
    const grandchild = contract({ id: 'grand', identifier: 'BP-SOW-2025-014', parentContractId: 'child' });
    expect(suggestParent(reference, amendment, [amendment, child, grandchild])).toBeNull();
    expect(suggestParent(reference, { ...amendment, parentContractId: 'sow' }, [sow, amendment])).toBeNull();
  });
});
