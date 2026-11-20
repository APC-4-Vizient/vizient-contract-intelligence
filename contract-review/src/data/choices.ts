import {
  Vz_contractsvz_documenttype as DocumentTypeMap,
  Vz_contractsvz_status as ContractStatusMap,
} from '../generated/models/Vz_contractsModel';
import {
  Vz_findingsvz_aijudgment as AiJudgmentMap,
  Vz_findingsvz_presence as PresenceMap,
  Vz_findingsvz_reviewerjudgment as ReviewerJudgmentMap,
  Vz_findingsvz_reviewstatus as ReviewStatusMap,
} from '../generated/models/Vz_findingsModel';
import { Vz_checklistitemsvz_group as GroupMap } from '../generated/models/Vz_checklistitemsModel';

export type DocumentType = (typeof DocumentTypeMap)[keyof typeof DocumentTypeMap];
export type ContractStatus = (typeof ContractStatusMap)[keyof typeof ContractStatusMap];
export type Presence = (typeof PresenceMap)[keyof typeof PresenceMap];
// The AI and reviewer judgment choices are the same list; choices.test.ts guards against drift.
export type Judgment = (typeof AiJudgmentMap)[keyof typeof AiJudgmentMap];
export type ReviewStatus = (typeof ReviewStatusMap)[keyof typeof ReviewStatusMap];
export type ChecklistGroup = (typeof GroupMap)[keyof typeof GroupMap];

export interface Codec<K extends number, L extends string> {
  readonly labels: readonly L[];
  /** Label for a Dataverse choice value, or null when the value is empty or unknown. */
  label(code: number | null | undefined): L | null;
  /** Dataverse choice value for a label. */
  code(label: L): K;
}

function codec<K extends number, L extends string>(map: Record<K, L>): Codec<K, L> {
  const pairs = Object.entries(map as unknown as Record<string, L>).map(([key, label]) => [Number(key) as K, label] as const);
  const byCode = new Map<number, L>(pairs);
  const byLabel = new Map<L, K>(pairs.map(([key, label]) => [label, key]));
  return {
    labels: pairs.map(([, label]) => label),
    label: (code) => (code === null || code === undefined ? null : (byCode.get(code) ?? null)),
    code: (label) => {
      const code = byLabel.get(label);
      if (code === undefined) throw new Error(`Unknown choice label "${label}"`);
      return code;
    },
  };
}

export const documentTypes = codec(DocumentTypeMap);
export const contractStatuses = codec(ContractStatusMap);
export const presences = codec(PresenceMap);
export const aiJudgments = codec(AiJudgmentMap);
export const reviewerJudgments = codec(ReviewerJudgmentMap);
export const reviewStatuses = codec(ReviewStatusMap);
export const checklistGroups = codec(GroupMap);
