import type { ChecklistGroup, ContractStatus, DocumentType, Judgment, Presence, ReviewStatus } from './choices';

/** A source region from Content Understanding. Polygon is 4 or more x,y pairs in inches, origin top-left. */
export interface SourceRegion {
  page: number;
  polygon: number[];
}

export interface UserRef {
  id: string;
  name: string;
  email: string;
}

export interface Contract {
  id: string;
  name: string;
  vendor: string;
  vizientEntity: string;
  documentType: DocumentType | null;
  identifier: string;
  effectiveDate: string | null;
  expirationDate: string | null;
  status: ContractStatus | null;
  foundCount: number | null;
  totalCount: number | null;
  /** Percent, 0 to 100. */
  completeness: number | null;
  hasParentReference: boolean;
  processedOn: string | null;
  errorMessage: string;
  createdOn: string | null;
  sharePointUrl: string;
  parentContractId: string | null;
  ownerId: string | null;
  legalReviewerId: string | null;
}

export interface ChecklistItem {
  id: string;
  key: string;
  label: string;
  group: ChecklistGroup;
  definition: string;
  hasJudgment: boolean;
  isActive: boolean;
  sortOrder: number;
}

export interface Finding {
  id: string;
  contractId: string;
  itemId: string | null;
  name: string;
  aiValue: string;
  aiJudgment: Judgment | null;
  aiConditions: string;
  clause: string;
  page: number | null;
  regions: SourceRegion[];
  /** 0 to 1. */
  confidence: number | null;
  presence: Presence | null;
  reviewStatus: ReviewStatus;
  reviewerValue: string;
  reviewerJudgment: Judgment | null;
  reviewerNotes: string;
  reviewedOn: string | null;
  reviewedById: string | null;
}

export interface ReviewRow {
  finding: Finding;
  item: ChecklistItem;
}

export interface FindingPatch {
  reviewStatus?: ReviewStatus;
  reviewerValue?: string;
  reviewerJudgment?: Judgment;
  reviewerNotes?: string;
  reviewedOn?: string;
  reviewedById?: string;
}

export interface ContractPatch {
  status?: ContractStatus;
  foundCount?: number;
  completeness?: number;
  parentContractId?: string;
  ownerId?: string;
  legalReviewerId?: string;
}
