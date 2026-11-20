import type { ChecklistItem, Contract, ContractPatch, Finding, FindingPatch, UserRef } from './types';

export interface Repo {
  readonly mode: 'dataverse' | 'mock';
  listContracts(): Promise<Contract[]>;
  getContract(id: string): Promise<Contract>;
  listChecklist(): Promise<ChecklistItem[]>;
  listFindings(contractId: string): Promise<Finding[]>;
  /** The contract PDF from its vz_document file column. */
  downloadPdf(contractId: string): Promise<Uint8Array>;
  updateFinding(id: string, patch: FindingPatch): Promise<void>;
  updateContract(id: string, patch: ContractPatch): Promise<void>;
  searchUsers(query: string): Promise<UserRef[]>;
  getUsers(ids: readonly string[]): Promise<UserRef[]>;
  /** The signed-in user's systemuserid, or null when the host does not provide it. */
  currentUserId(): Promise<string | null>;
}

let cached: Promise<Repo> | null = null;

/** True only on the dev server started with `vite --mode mock`; production builds drop the mock entirely. */
export const MOCK_MODE: boolean = import.meta.env.DEV && import.meta.env.MODE === 'mock';

/** Loads the Dataverse repo, or the in-memory mock under `vite --mode mock`. */
export function getRepo(): Promise<Repo> {
  cached ??= load();
  return cached;
}

async function load(): Promise<Repo> {
  if (MOCK_MODE) {
    const { createMockRepo } = await import('./mockRepo');
    return createMockRepo();
  }
  const { createDataverseRepo } = await import('./dataverseRepo');
  return createDataverseRepo();
}
