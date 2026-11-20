import type { ChecklistItem, Contract, Finding, ReviewRow } from '../data/types';

export function makeItem(overrides: Partial<ChecklistItem> = {}): ChecklistItem {
  return {
    id: 'item:Test',
    key: 'Test',
    label: 'Test item',
    group: 'Contract Detail',
    definition: '',
    hasJudgment: false,
    isActive: true,
    sortOrder: 1,
    ...overrides,
  };
}

export function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'finding-1',
    contractId: 'contract-1',
    itemId: 'item:Test',
    name: 'Test item',
    aiValue: '',
    aiJudgment: null,
    aiConditions: '',
    clause: '',
    page: null,
    regions: [],
    confidence: null,
    presence: 'Found',
    reviewStatus: 'Pending',
    reviewerValue: '',
    reviewerJudgment: null,
    reviewerNotes: '',
    reviewedOn: null,
    reviewedById: null,
    ...overrides,
  };
}

export function makeRow(finding: Partial<Finding> = {}, item: Partial<ChecklistItem> = {}): ReviewRow {
  return { finding: makeFinding(finding), item: makeItem(item) };
}

export function makeContract(overrides: Partial<Contract> = {}): Contract {
  return {
    id: 'contract-1',
    name: 'contract.pdf',
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
    ...overrides,
  };
}
