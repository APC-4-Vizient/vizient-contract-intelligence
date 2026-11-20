import { getContext } from '@microsoft/power-apps/app';
import type { IOperationResult } from '@microsoft/power-apps/data';
import type { Vz_contractsBase } from '../generated/models/Vz_contractsModel';
import type { Vz_findingsBase } from '../generated/models/Vz_findingsModel';
import { SystemusersService } from '../generated/services/SystemusersService';
import { Vz_checklistitemsService } from '../generated/services/Vz_checklistitemsService';
import { Vz_contractsService } from '../generated/services/Vz_contractsService';
import { Vz_findingsService } from '../generated/services/Vz_findingsService';
import { contractStatuses, reviewerJudgments, reviewStatuses } from './choices';
import { messageOf } from './errors';
import { toChecklistItem, toContract, toFinding, toUserRef } from './mappers';
import type { Repo } from './repo';
import type { ContractPatch, FindingPatch } from './types';

// vz_document, vz_document_name and vz_rawresult are left out on purpose: they are large and the UI never shows them.
const CONTRACT_COLUMNS = [
  'vz_contractid',
  'vz_name',
  'vz_vendor',
  'vz_viziententity',
  'vz_contractidentifier',
  'vz_documenttype',
  'vz_effectivedate',
  'vz_expirationdate',
  'vz_status',
  'vz_foundcount',
  'vz_totalcount',
  'vz_completeness',
  'vz_hasparentreference',
  'vz_processedon',
  'vz_errormessage',
  'vz_sharepointurl',
  'createdon',
  '_vz_parentcontract_value',
  '_vz_contractowner_value',
  '_vz_legalreviewer_value',
];

const CHECKLIST_COLUMNS = [
  'vz_checklistitemid',
  'vz_key',
  'vz_name',
  'vz_group',
  'vz_definition',
  'vz_hasjudgment',
  'vz_isactive',
  'vz_sortorder',
];

const FINDING_COLUMNS = [
  'vz_findingid',
  'vz_name',
  'vz_aivalue',
  'vz_aijudgment',
  'vz_aiconditions',
  'vz_clause',
  'vz_page',
  'vz_sourceregions',
  'vz_confidence',
  'vz_presence',
  'vz_reviewstatus',
  'vz_reviewervalue',
  'vz_reviewerjudgment',
  'vz_reviewernotes',
  'vz_reviewedon',
  '_vz_contract_value',
  '_vz_checklistitem_value',
  '_vz_reviewedby_value',
];

const USER_COLUMNS = ['systemuserid', 'fullname', 'internalemailaddress'];

const MAX_CONTRACTS = 200;
const MAX_CHECKLIST = 100;
const MAX_FINDINGS = 100;
const MAX_USERS = 20;

const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Ids end up inside OData filters and bind paths, so only well-formed GUIDs get through. */
function guid(id: string): string {
  if (!GUID.test(id)) throw new Error('That record id is not valid.');
  return id;
}

function unwrap<T>(result: IOperationResult<T>, action: string): T {
  if (!result.success) {
    throw new Error(`Could not ${action}${result.error ? `: ${messageOf(result.error)}` : '.'}`);
  }
  return result.data;
}

function toBytes(data: unknown): Uint8Array {
  if (data instanceof Uint8Array && data.length > 0) return data;
  if (data instanceof ArrayBuffer && data.byteLength > 0) return new Uint8Array(data);
  if (typeof data === 'string' && data.length > 0) {
    const binary = atob(data);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }
  throw new Error('This contract has no PDF attached.');
}

/** Keeps letters, digits and a few name characters, then escapes quotes for OData. */
function searchText(query: string): string {
  return query
    .trim()
    .replace(/[^\p{L}\p{N} .@_'-]/gu, '')
    .replace(/'/g, "''");
}

export function createDataverseRepo(): Repo {
  let userId: Promise<string | null> | null = null;

  return {
    mode: 'dataverse',

    async listContracts() {
      const result = await Vz_contractsService.getAll({
        select: CONTRACT_COLUMNS,
        orderBy: ['createdon desc'],
        top: MAX_CONTRACTS,
      });
      return unwrap(result, 'load the contracts').map(toContract);
    },

    async getContract(id) {
      const result = await Vz_contractsService.get(guid(id), { select: CONTRACT_COLUMNS });
      return toContract(unwrap(result, 'load the contract'));
    },

    async listChecklist() {
      const result = await Vz_checklistitemsService.getAll({
        select: CHECKLIST_COLUMNS,
        orderBy: ['vz_sortorder asc'],
        top: MAX_CHECKLIST,
      });
      return unwrap(result, 'load the checklist').map(toChecklistItem);
    },

    async listFindings(contractId) {
      const result = await Vz_findingsService.getAll({
        select: FINDING_COLUMNS,
        filter: `_vz_contract_value eq ${guid(contractId)}`,
        top: MAX_FINDINGS,
      });
      return unwrap(result, 'load the findings').map(toFinding);
    },

    async downloadPdf(contractId) {
      const result = await Vz_contractsService.downloadFile(guid(contractId), 'vz_document');
      return toBytes(unwrap(result, 'download the contract PDF'));
    },

    async updateFinding(id, patch: FindingPatch) {
      const fields: Partial<Omit<Vz_findingsBase, 'vz_findingid'>> = {};
      if (patch.reviewStatus !== undefined) fields.vz_reviewstatus = reviewStatuses.code(patch.reviewStatus);
      if (patch.reviewerValue !== undefined) fields.vz_reviewervalue = patch.reviewerValue;
      if (patch.reviewerJudgment !== undefined) fields.vz_reviewerjudgment = reviewerJudgments.code(patch.reviewerJudgment);
      if (patch.reviewerNotes !== undefined) fields.vz_reviewernotes = patch.reviewerNotes;
      if (patch.reviewedOn !== undefined) fields.vz_reviewedon = patch.reviewedOn;
      if (patch.reviewedById !== undefined) fields['vz_reviewedby@odata.bind'] = `/systemusers(${guid(patch.reviewedById)})`;
      unwrap(await Vz_findingsService.update(guid(id), fields), 'save the review');
    },

    async updateContract(id, patch: ContractPatch) {
      const fields: Partial<Omit<Vz_contractsBase, 'vz_contractid'>> = {};
      if (patch.status !== undefined) fields.vz_status = contractStatuses.code(patch.status);
      if (patch.foundCount !== undefined) fields.vz_foundcount = patch.foundCount;
      if (patch.completeness !== undefined) fields.vz_completeness = patch.completeness;
      if (patch.parentContractId !== undefined) {
        fields['vz_parentcontract@odata.bind'] = `/vz_contracts(${guid(patch.parentContractId)})`;
      }
      if (patch.ownerId !== undefined) fields['vz_contractowner@odata.bind'] = `/systemusers(${guid(patch.ownerId)})`;
      if (patch.legalReviewerId !== undefined) {
        fields['vz_legalreviewer@odata.bind'] = `/systemusers(${guid(patch.legalReviewerId)})`;
      }
      unwrap(await Vz_contractsService.update(guid(id), fields), 'save the contract');
    },

    async searchUsers(query) {
      // Read-write, administrative and read-only seats. Support, non-interactive (application) and delegated users are left out.
      const clauses = ['isdisabled eq false', 'accessmode lt 3'];
      const text = searchText(query);
      if (text) clauses.push(`(contains(fullname,'${text}') or contains(internalemailaddress,'${text}'))`);
      const result = await SystemusersService.getAll({
        select: USER_COLUMNS,
        filter: clauses.join(' and '),
        orderBy: ['fullname asc'],
        top: MAX_USERS,
      });
      return unwrap(result, 'search users').map(toUserRef);
    },

    async getUsers(ids) {
      const unique = [...new Set(ids)].map(guid);
      if (unique.length === 0) return [];
      const result = await SystemusersService.getAll({
        select: USER_COLUMNS,
        filter: unique.map((id) => `systemuserid eq ${id}`).join(' or '),
        top: unique.length,
      });
      return unwrap(result, 'load users').map(toUserRef);
    },

    currentUserId() {
      userId ??= getContext()
        .then((context) => {
          const id = (context.user.systemUserId ?? '').replace(/[{}]/g, '').trim();
          return GUID.test(id) ? id : null;
        })
        .catch(() => null);
      return userId;
    },
  };
}
