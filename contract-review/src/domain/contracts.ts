import type { Contract } from '../data/types';

export type ContractTab = 'all' | 'ready' | 'low';

/** Contracts below this completeness (percent) show under the Low completeness tab. */
export const LOW_COMPLETENESS_BELOW = 60;

const TABS: readonly string[] = ['all', 'ready', 'low'];

export function isContractTab(value: unknown): value is ContractTab {
  return typeof value === 'string' && TABS.includes(value);
}

export function matchesTab(contract: Contract, tab: ContractTab): boolean {
  switch (tab) {
    case 'ready':
      return contract.status === 'Ready for Review' || contract.status === 'In Review';
    case 'low':
      return (contract.totalCount ?? 0) > 0 && (contract.completeness ?? 0) < LOW_COMPLETENESS_BELOW;
    default:
      return true;
  }
}

export function tabCounts(contracts: readonly Contract[]): Record<ContractTab, number> {
  return {
    all: contracts.length,
    ready: contracts.filter((contract) => matchesTab(contract, 'ready')).length,
    low: contracts.filter((contract) => matchesTab(contract, 'low')).length,
  };
}

/** The vendor once it has been extracted, otherwise the file name. */
export function contractTitle(contract: Contract): string {
  return contract.vendor.trim() || contract.name.trim() || 'Untitled contract';
}
