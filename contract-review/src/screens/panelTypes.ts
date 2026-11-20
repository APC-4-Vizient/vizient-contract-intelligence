import type { Finding } from '../data/types';
import type { Correction } from '../hooks/useReview';

export type Filter = 'all' | 'attention';

/** What a finding row can do. The review screen supplies these so selection and editing stay in one place. */
export interface RowHandlers {
  accept(finding: Finding): void;
  reject(finding: Finding): void;
  correct(finding: Finding, correction: Correction): void;
  reset(finding: Finding): void;
  startEdit(finding: Finding): void;
  cancelEdit(): void;
}
