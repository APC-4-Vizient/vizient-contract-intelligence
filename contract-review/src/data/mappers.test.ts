import { describe, expect, it } from 'vitest';
import type { Systemusers } from '../generated/models/SystemusersModel';
import type { Vz_checklistitems } from '../generated/models/Vz_checklistitemsModel';
import type { Vz_contracts } from '../generated/models/Vz_contractsModel';
import type { Vz_findings } from '../generated/models/Vz_findingsModel';
import { toChecklistItem, toContract, toFinding, toUserRef } from './mappers';

// Dataverse omits or nulls columns, so the rows below carry only what a response would.
const asFinding = (row: Record<string, unknown>) => row as unknown as Vz_findings;
const asContract = (row: Record<string, unknown>) => row as unknown as Vz_contracts;
const asItem = (row: Record<string, unknown>) => row as unknown as Vz_checklistitems;
const asUser = (row: Record<string, unknown>) => row as unknown as Systemusers;

describe('toFinding', () => {
  it('maps a saved finding and normalizes line endings', () => {
    const finding = toFinding(
      asFinding({
        vz_findingid: 'f-1',
        _vz_contract_value: 'c-1',
        _vz_checklistitem_value: 'i-1',
        vz_name: 'Destruction',
        vz_aivalue: 'Within 30 days',
        vz_aijudgment: 651200000,
        vz_clause: 'Line one\r\nLine two',
        vz_page: 7,
        vz_sourceregions: JSON.stringify([{ page: 7, polygon: [1, 1, 2, 1, 2, 2, 1, 2] }]),
        vz_confidence: 0.92,
        vz_presence: 651200000,
        vz_reviewstatus: 651200002,
        vz_reviewervalue: 'Within 45 days',
        vz_reviewerjudgment: 651200002,
      }),
    );
    expect(finding).toMatchObject({
      id: 'f-1',
      contractId: 'c-1',
      itemId: 'i-1',
      aiValue: 'Within 30 days',
      aiJudgment: 'Permitted',
      clause: 'Line one\nLine two',
      page: 7,
      confidence: 0.92,
      presence: 'Found',
      reviewStatus: 'Corrected',
      reviewerValue: 'Within 45 days',
      reviewerJudgment: 'Conditional',
    });
    expect(finding.regions).toHaveLength(1);
  });

  it('treats the nulls Dataverse sends as empty', () => {
    const finding = toFinding(
      asFinding({
        vz_findingid: 'f-2',
        _vz_checklistitem_value: null,
        vz_aivalue: null,
        vz_clause: null,
        vz_page: null,
        vz_confidence: null,
        vz_presence: null,
        vz_reviewstatus: null,
        vz_sourceregions: null,
      }),
    );
    expect(finding).toMatchObject({
      itemId: null,
      aiValue: '',
      clause: '',
      page: null,
      confidence: null,
      presence: null,
      reviewStatus: 'Pending',
      regions: [],
    });
  });
});

describe('toContract', () => {
  it('maps a contract and keeps a date-only value as a date', () => {
    const contract = toContract(
      asContract({
        vz_contractid: 'c-1',
        vz_name: 'bluepine-sow.pdf',
        vz_vendor: 'BluePine',
        vz_documenttype: 651200001,
        vz_effectivedate: '2025-03-01T00:00:00Z',
        vz_status: 651200002,
        vz_foundcount: 16,
        vz_totalcount: 20,
        vz_completeness: 80,
        vz_hasparentreference: true,
        _vz_parentcontract_value: 'c-0',
      }),
    );
    expect(contract).toMatchObject({
      id: 'c-1',
      vendor: 'BluePine',
      documentType: 'SOW',
      effectiveDate: '2025-03-01',
      status: 'Ready for Review',
      foundCount: 16,
      totalCount: 20,
      completeness: 80,
      hasParentReference: true,
      parentContractId: 'c-0',
      ownerId: null,
    });
  });
});

describe('toChecklistItem', () => {
  it('falls back to the key for the label and sorts an unsorted item last', () => {
    const item = toChecklistItem(
      asItem({ vz_checklistitemid: 'i-1', vz_key: 'Right_Destruction', vz_name: null, vz_group: 651200001, vz_hasjudgment: true }),
    );
    expect(item).toMatchObject({ label: 'Right_Destruction', group: 'Data Right', hasJudgment: true, isActive: true, sortOrder: 9000 });
  });
});

describe('toUserRef', () => {
  it('uses the email when the user has no name', () => {
    const user = toUserRef(asUser({ systemuserid: 'u-1', fullname: null, internalemailaddress: 'ada@example.com' }));
    expect(user).toEqual({ id: 'u-1', name: 'ada@example.com', email: 'ada@example.com' });
  });
});
