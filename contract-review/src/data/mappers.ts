import type { Systemusers } from '../generated/models/SystemusersModel';
import type { Vz_checklistitems } from '../generated/models/Vz_checklistitemsModel';
import type { Vz_contracts } from '../generated/models/Vz_contractsModel';
import type { Vz_findings } from '../generated/models/Vz_findingsModel';
import { parseRegions } from '../domain/regions';
import { toDateOnly } from '../domain/format';
import {
  aiJudgments,
  checklistGroups,
  contractStatuses,
  documentTypes,
  presences,
  reviewerJudgments,
  reviewStatuses,
} from './choices';
import type { ChecklistItem, Contract, Finding, UserRef } from './types';

const UNSORTED = 9_000;

// Dataverse sends null for empty columns although the generated types say undefined, and memo columns come back with CRLF.
function text(value: string | null | undefined): string {
  return (value ?? '').replace(/\r\n?/g, '\n');
}

function num(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function toContract(row: Vz_contracts): Contract {
  return {
    id: row.vz_contractid,
    name: text(row.vz_name),
    vendor: text(row.vz_vendor),
    vizientEntity: text(row.vz_viziententity),
    documentType: documentTypes.label(row.vz_documenttype),
    identifier: text(row.vz_contractidentifier),
    effectiveDate: toDateOnly(row.vz_effectivedate),
    expirationDate: toDateOnly(row.vz_expirationdate),
    status: contractStatuses.label(row.vz_status),
    foundCount: num(row.vz_foundcount),
    totalCount: num(row.vz_totalcount),
    completeness: num(row.vz_completeness),
    hasParentReference: row.vz_hasparentreference === true,
    processedOn: row.vz_processedon ?? null,
    errorMessage: text(row.vz_errormessage),
    createdOn: row.createdon ?? null,
    sharePointUrl: text(row.vz_sharepointurl),
    parentContractId: row._vz_parentcontract_value ?? null,
    ownerId: row._vz_contractowner_value ?? null,
    legalReviewerId: row._vz_legalreviewer_value ?? null,
  };
}

export function toChecklistItem(row: Vz_checklistitems): ChecklistItem {
  return {
    id: row.vz_checklistitemid,
    key: row.vz_key,
    label: text(row.vz_name) || row.vz_key,
    group: checklistGroups.label(row.vz_group) ?? 'Contract Detail',
    definition: text(row.vz_definition),
    hasJudgment: row.vz_hasjudgment === true,
    isActive: row.vz_isactive !== false,
    sortOrder: num(row.vz_sortorder) ?? UNSORTED,
  };
}

export function toFinding(row: Vz_findings): Finding {
  return {
    id: row.vz_findingid,
    contractId: row._vz_contract_value ?? '',
    itemId: row._vz_checklistitem_value ?? null,
    name: text(row.vz_name),
    aiValue: text(row.vz_aivalue),
    aiJudgment: aiJudgments.label(row.vz_aijudgment),
    aiConditions: text(row.vz_aiconditions),
    clause: text(row.vz_clause),
    page: num(row.vz_page),
    regions: parseRegions(row.vz_sourceregions),
    confidence: num(row.vz_confidence),
    presence: presences.label(row.vz_presence),
    reviewStatus: reviewStatuses.label(row.vz_reviewstatus) ?? 'Pending',
    reviewerValue: text(row.vz_reviewervalue),
    reviewerJudgment: reviewerJudgments.label(row.vz_reviewerjudgment),
    reviewerNotes: text(row.vz_reviewernotes),
    reviewedOn: row.vz_reviewedon ?? null,
    reviewedById: row._vz_reviewedby_value ?? null,
  };
}

export function toUserRef(row: Systemusers): UserRef {
  const email = text(row.internalemailaddress);
  return { id: row.systemuserid, name: text(row.fullname) || email || 'Unknown user', email };
}
