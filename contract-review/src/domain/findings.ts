import type { ChecklistGroup } from '../data/choices';
import type { ChecklistItem, Contract, ContractPatch, Finding, FindingPatch, ReviewRow } from '../data/types';

const UNLISTED_SORT = 10_000;

/** A finding whose checklist item is missing still shows up, labelled from the finding itself. */
function placeholderItem(finding: Finding): ChecklistItem {
  const judged = finding.aiJudgment !== null && finding.aiJudgment !== 'N/A';
  return {
    id: finding.itemId ?? finding.id,
    key: finding.id,
    label: finding.name || 'Unlisted item',
    group: judged ? 'Data Right' : 'Contract Detail',
    definition: '',
    hasJudgment: judged,
    isActive: true,
    sortOrder: UNLISTED_SORT,
  };
}

/** Joins findings to their checklist items and orders them as the checklist does. */
export function joinRows(findings: readonly Finding[], items: readonly ChecklistItem[]): ReviewRow[] {
  const byId = new Map(items.map((item) => [item.id, item]));
  return findings
    .map((finding): ReviewRow => ({
      finding,
      item: (finding.itemId ? byId.get(finding.itemId) : undefined) ?? placeholderItem(finding),
    }))
    .sort((a, b) => a.item.sortOrder - b.item.sortOrder || a.item.label.localeCompare(b.item.label));
}

export interface RowGroup {
  group: ChecklistGroup;
  rows: ReviewRow[];
}

const GROUP_ORDER: readonly ChecklistGroup[] = ['Contract Detail', 'Data Right'];

/** Groups rows for display. The Manual group is never analyzed, so it has no findings to show. */
export function groupRows(rows: readonly ReviewRow[]): RowGroup[] {
  return GROUP_ORDER.map((group) => ({ group, rows: rows.filter((row) => row.item.group === group) })).filter(
    (entry) => entry.rows.length > 0,
  );
}

export function applyFindingPatch(finding: Finding, patch: FindingPatch): Finding {
  return {
    ...finding,
    reviewStatus: patch.reviewStatus ?? finding.reviewStatus,
    reviewerValue: patch.reviewerValue ?? finding.reviewerValue,
    reviewerJudgment: patch.reviewerJudgment ?? finding.reviewerJudgment,
    reviewerNotes: patch.reviewerNotes ?? finding.reviewerNotes,
    reviewedOn: patch.reviewedOn ?? finding.reviewedOn,
    reviewedById: patch.reviewedById ?? finding.reviewedById,
  };
}

export function applyContractPatch(contract: Contract, patch: ContractPatch): Contract {
  return {
    ...contract,
    status: patch.status ?? contract.status,
    foundCount: patch.foundCount ?? contract.foundCount,
    completeness: patch.completeness ?? contract.completeness,
    parentContractId: patch.parentContractId ?? contract.parentContractId,
    ownerId: patch.ownerId ?? contract.ownerId,
    legalReviewerId: patch.legalReviewerId ?? contract.legalReviewerId,
  };
}
