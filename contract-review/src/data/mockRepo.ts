// Dev-only data source for `npm run dev:mock`. It never ships: repo.ts only imports it when MOCK_MODE is true,
// which is a compile-time false in production builds.
import { applyContractPatch, applyFindingPatch } from '../domain/findings';
import { toDateOnly } from '../domain/format';
import { parseRegions } from '../domain/regions';
import { aiJudgments, checklistGroups, documentTypes, presences } from './choices';
import type { ContractStatus } from './choices';
import type { Repo } from './repo';
import type { ChecklistItem, Contract, ContractPatch, Finding, FindingPatch, UserRef } from './types';

const LATENCY_MS = 40;
const FIXTURES = '/__fixtures__';
const FAIL_FLAG = 'vz-mock-fail-writes';

interface FixtureFinding {
  key: string;
  presence?: string | null;
  value?: string | null;
  judgment?: string | null;
  conditions?: string | null;
  clause?: string | null;
  page?: number | null;
  sourceRegions?: unknown;
  confidence?: number | null;
}

interface FixtureResult {
  contract: {
    vendor?: string | null;
    vizientEntity?: string | null;
    documentType?: string | null;
    contractIdentifier?: string | null;
    effectiveDate?: string | null;
    expirationDate?: string | null;
    hasParentReference?: boolean | null;
    foundCount?: number | null;
    totalCount?: number | null;
    completeness?: number | null;
  };
  findings: FixtureFinding[];
}

interface FixtureChecklistItem {
  key: string;
  label: string;
  group: string;
  definition?: string;
  hasJudgment?: boolean;
  sortOrder: number;
  isActive?: boolean;
}

interface State {
  contracts: Contract[];
  items: ChecklistItem[];
  findings: Map<string, Finding[]>;
  pdfIds: Set<string>;
}

const USERS: UserRef[] = [
  { id: 'mock-user', name: 'Demo Reviewer', email: 'demo.reviewer@example.com' },
  { id: 'user-ana', name: 'Ana Whitfield', email: 'ana.whitfield@example.com' },
  { id: 'user-marcus', name: 'Marcus Oyelaran', email: 'marcus.oyelaran@example.com' },
  { id: 'user-priya', name: 'Priya Raman', email: 'priya.raman@example.com' },
  { id: 'user-dana', name: 'Dana Kowalski', email: 'dana.kowalski@example.com' },
];

function pause(): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, LATENCY_MS);
  });
}

async function fetchFixture(path: string): Promise<Response> {
  const response = await fetch(`${FIXTURES}/${path}`);
  if (!response.ok) {
    throw new Error(`Mock fixture "${path}" could not be loaded (${response.status}). Run the dev server inside the repo that holds samples/results.`);
  }
  return response;
}

async function fetchJson<T>(path: string): Promise<T> {
  return (await (await fetchFixture(path)).json()) as T;
}

function findingFrom(contractId: string, fixture: FixtureFinding, item: ChecklistItem): Finding {
  return {
    id: `${contractId}:${fixture.key}`,
    contractId,
    itemId: item.id,
    name: item.label,
    aiValue: fixture.value ?? '',
    aiJudgment: aiJudgments.labels.find((label) => label === fixture.judgment) ?? null,
    aiConditions: fixture.conditions ?? '',
    clause: fixture.clause ?? '',
    page: fixture.page ?? null,
    regions: parseRegions(JSON.stringify(fixture.sourceRegions ?? [])),
    confidence: fixture.confidence ?? null,
    presence: presences.labels.find((label) => label === fixture.presence) ?? null,
    reviewStatus: 'Pending',
    reviewerValue: '',
    reviewerJudgment: null,
    reviewerNotes: '',
    reviewedOn: null,
    reviewedById: null,
  };
}

function stub(id: string, status: ContractStatus, ageMs: number, errorMessage = ''): Contract {
  return {
    id,
    name: `${id}.pdf`,
    vendor: '',
    vizientEntity: '',
    documentType: null,
    identifier: '',
    effectiveDate: null,
    expirationDate: null,
    status,
    foundCount: null,
    totalCount: null,
    completeness: null,
    hasParentReference: false,
    processedOn: null,
    errorMessage,
    createdOn: new Date(Date.now() - ageMs).toISOString(),
    sharePointUrl: '',
    parentContractId: null,
    ownerId: null,
    legalReviewerId: null,
  };
}

async function buildState(): Promise<State> {
  const [ids, checklist] = await Promise.all([
    fetchJson<string[]>('index.json'),
    fetchJson<{ items: FixtureChecklistItem[] }>('checklist.json'),
  ]);
  const results = await Promise.all(ids.map(async (id) => ({ id, result: await fetchJson<FixtureResult>(`${id}.json`) })));

  const items: ChecklistItem[] = checklist.items.map((entry) => ({
    id: `item:${entry.key}`,
    key: entry.key,
    label: entry.label,
    group: checklistGroups.labels.find((label) => label === entry.group) ?? 'Contract Detail',
    definition: entry.definition ?? '',
    hasJudgment: entry.hasJudgment === true,
    isActive: entry.isActive !== false,
    sortOrder: entry.sortOrder,
  }));
  const itemByKey = new Map(items.map((item) => [item.key, item]));

  const now = Date.now();
  const contracts: Contract[] = [];
  const findings = new Map<string, Finding[]>();
  results.forEach(({ id, result }, index) => {
    const detail = result.contract;
    const created = now - (index + 2) * 3_600_000;
    contracts.push({
      id,
      name: `${id}.pdf`,
      vendor: detail.vendor ?? '',
      vizientEntity: detail.vizientEntity ?? '',
      documentType: documentTypes.labels.find((label) => label === detail.documentType) ?? null,
      identifier: detail.contractIdentifier ?? '',
      effectiveDate: toDateOnly(detail.effectiveDate),
      expirationDate: toDateOnly(detail.expirationDate),
      status: 'Ready for Review',
      foundCount: detail.foundCount ?? null,
      totalCount: detail.totalCount ?? null,
      completeness: detail.completeness ?? null,
      hasParentReference: detail.hasParentReference === true,
      processedOn: new Date(created + 120_000).toISOString(),
      errorMessage: '',
      createdOn: new Date(created).toISOString(),
      sharePointUrl: '',
      parentContractId: null,
      ownerId: null,
      legalReviewerId: null,
    });
    findings.set(
      id,
      result.findings.flatMap((fixture) => {
        const item = itemByKey.get(fixture.key);
        return item ? [findingFrom(id, fixture, item)] : [];
      }),
    );
  });

  contracts.push(
    stub('northwind-msa', 'Extracting', 90_000),
    stub('harborview-baa', 'Received', 20_000),
    stub('summit-nda', 'Failed', 86_400_000, 'Content Understanding could not read this file: the PDF is password protected.'),
  );

  return { contracts, items, findings, pdfIds: new Set(ids) };
}

function newestFirst(a: Contract, b: Contract): number {
  return (b.createdOn ?? '').localeCompare(a.createdOn ?? '');
}

export function createMockRepo(): Repo {
  const ready = buildState();

  // `sessionStorage.setItem('vz-mock-fail-writes', '1')` makes writes fail, to exercise the error and rollback path.
  function guardWrite(): void {
    if (sessionStorage.getItem(FAIL_FLAG) === '1') throw new Error('Mock write failure (vz-mock-fail-writes is set).');
  }

  return {
    mode: 'mock',

    async listContracts() {
      const state = await ready;
      await pause();
      return [...state.contracts].sort(newestFirst);
    },

    async getContract(id) {
      const state = await ready;
      await pause();
      const contract = state.contracts.find((entry) => entry.id === id);
      if (!contract) throw new Error('Contract not found.');
      return contract;
    },

    async listChecklist() {
      const state = await ready;
      await pause();
      return [...state.items];
    },

    async listFindings(contractId) {
      const state = await ready;
      await pause();
      return [...(state.findings.get(contractId) ?? [])];
    },

    async downloadPdf(contractId) {
      const state = await ready;
      if (!state.pdfIds.has(contractId)) throw new Error('This contract has no PDF attached.');
      const response = await fetchFixture(`${contractId}.pdf`);
      return new Uint8Array(await response.arrayBuffer());
    },

    async updateFinding(id, patch: FindingPatch) {
      const state = await ready;
      await pause();
      guardWrite();
      for (const [contractId, list] of state.findings) {
        const index = list.findIndex((entry) => entry.id === id);
        if (index >= 0) {
          state.findings.set(
            contractId,
            list.map((entry, position) => (position === index ? applyFindingPatch(entry, patch) : entry)),
          );
          return;
        }
      }
      throw new Error('Finding not found.');
    },

    async updateContract(id, patch: ContractPatch) {
      const state = await ready;
      await pause();
      guardWrite();
      if (!state.contracts.some((entry) => entry.id === id)) throw new Error('Contract not found.');
      state.contracts = state.contracts.map((entry) => (entry.id === id ? applyContractPatch(entry, patch) : entry));
    },

    async searchUsers(query) {
      await pause();
      const needle = query.trim().toLowerCase();
      return USERS.filter((user) => !needle || user.name.toLowerCase().includes(needle) || user.email.toLowerCase().includes(needle));
    },

    async getUsers(ids) {
      await pause();
      return USERS.filter((user) => ids.includes(user.id));
    },

    currentUserId: () => Promise.resolve('mock-user'),
  };
}
