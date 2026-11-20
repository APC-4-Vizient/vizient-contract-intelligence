import type { ChecklistGroup, Judgment } from '../data/choices';
import type { ReviewRow } from '../data/types';
import { isAddressed } from './completeness';

/** The judgment to show: the reviewer's once the finding is corrected, otherwise the AI's. */
export function effectiveJudgment({ finding }: ReviewRow): Judgment | null {
  return finding.reviewStatus === 'Corrected' && finding.reviewerJudgment ? finding.reviewerJudgment : finding.aiJudgment;
}

/** The value to show: the reviewer's answer once corrected (even when emptied on purpose), otherwise the AI's. */
export function effectiveValue({ finding }: ReviewRow): string {
  return finding.reviewStatus === 'Corrected' ? finding.reviewerValue : finding.aiValue;
}

/** Only items that carry a judgment show one, and N/A says nothing worth a chip. */
export function judgmentToShow(row: ReviewRow): Judgment | null {
  if (!row.item.hasJudgment) return null;
  const judgment = effectiveJudgment(row);
  return judgment === null || judgment === 'N/A' ? null : judgment;
}

export interface Preview {
  text: string;
  /** True for the stand-in sentences, which are shown quieter than a real answer. */
  muted: boolean;
}

/** The one-line summary under a finding's label. */
export function previewOf(row: ReviewRow): Preview {
  const { finding, item } = row;
  const value = effectiveValue(row).trim();
  if (value !== '') return { text: value, muted: false };

  const judgment = effectiveJudgment(row);
  if (item.hasJudgment && judgment === 'Not Addressed') {
    return { text: 'The contract does not address this right.', muted: true };
  }
  if (item.hasJudgment && isAddressed(judgment)) return { text: 'No conditions stated.', muted: true };
  if (finding.reviewStatus === 'Corrected') return { text: 'Reviewer found no value in the contract.', muted: true };
  if (finding.presence === 'Not Found') return { text: 'Not found in this contract.', muted: true };
  if (finding.presence === 'Unclear') return { text: 'Unclear. Needs a reviewer.', muted: true };
  return { text: 'No value extracted.', muted: true };
}

export function groupTitle(group: ChecklistGroup): string {
  switch (group) {
    case 'Contract Detail':
      return 'Contract details';
    case 'Data Right':
      return 'Data rights';
    default:
      return group;
  }
}

/** Stored links are only rendered as links when they are http(s); anything else is shown as plain text. */
export function safeHttpUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
  } catch {
    return null;
  }
}
