import type { Judgment } from '../data/choices';
import type { Finding, ReviewRow } from '../data/types';

/** Judgments that mean the contract speaks to the right. Not Addressed and N/A do not. */
const ADDRESSED: ReadonlySet<Judgment> = new Set<Judgment>(['Permitted', 'Prohibited', 'Conditional']);

export const EDITABLE_JUDGMENTS: readonly Judgment[] = ['Permitted', 'Prohibited', 'Conditional', 'Not Addressed'];

export function isAddressed(judgment: Judgment | null): boolean {
  return judgment !== null && ADDRESSED.has(judgment);
}

function aiHasContent({ finding, item }: ReviewRow): boolean {
  return item.hasJudgment ? isAddressed(finding.aiJudgment) : finding.aiValue.trim() !== '';
}

/**
 * Whether the item counts as found right now, after any reviewer decision.
 * Pending follows the AI, Accepted confirms the AI, Corrected follows the reviewer's answer, Rejected removes it.
 */
export function isFoundNow(row: ReviewRow): boolean {
  const { finding, item } = row;
  switch (finding.reviewStatus) {
    case 'Rejected':
      return false;
    case 'Corrected':
      return item.hasJudgment ? isAddressed(finding.reviewerJudgment) : finding.reviewerValue.trim() !== '';
    case 'Accepted':
      return finding.presence === 'Found' || (finding.presence === 'Unclear' && aiHasContent(row));
    default:
      return finding.presence === 'Found';
  }
}

/** Unclear and Not Found items nobody has looked at yet. */
export function needsAttention(finding: Finding): boolean {
  return finding.reviewStatus === 'Pending' && finding.presence !== 'Found';
}

/** Found by the AI and not yet reviewed, so safe to confirm in bulk. */
export function isConfidentPending(finding: Finding): boolean {
  return finding.reviewStatus === 'Pending' && finding.presence === 'Found';
}

export interface Summary {
  total: number;
  found: number;
  /** Percent, one decimal. */
  percent: number;
  aiFound: number;
  pending: number;
  accepted: number;
  corrected: number;
  rejected: number;
  attention: number;
}

export function summarize(rows: readonly ReviewRow[]): Summary {
  const summary: Summary = {
    total: rows.length,
    found: 0,
    percent: 0,
    aiFound: 0,
    pending: 0,
    accepted: 0,
    corrected: 0,
    rejected: 0,
    attention: 0,
  };
  for (const row of rows) {
    const { finding } = row;
    if (isFoundNow(row)) summary.found += 1;
    if (finding.presence === 'Found') summary.aiFound += 1;
    if (needsAttention(finding)) summary.attention += 1;
    switch (finding.reviewStatus) {
      case 'Accepted':
        summary.accepted += 1;
        break;
      case 'Corrected':
        summary.corrected += 1;
        break;
      case 'Rejected':
        summary.rejected += 1;
        break;
      default:
        summary.pending += 1;
    }
  }
  summary.percent = summary.total === 0 ? 0 : Math.round((summary.found / summary.total) * 1000) / 10;
  return summary;
}

/** Approval needs at least one finding and no finding left Pending. */
export function canApprove(rows: readonly ReviewRow[]): boolean {
  return rows.length > 0 && rows.every((row) => row.finding.reviewStatus !== 'Pending');
}
