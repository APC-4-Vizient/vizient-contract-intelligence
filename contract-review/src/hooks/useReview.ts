import { useEffect, useMemo, useState } from 'react';
import type { Judgment } from '../data/choices';
import { messageOf } from '../data/errors';
import { getRepo } from '../data/repo';
import type { ChecklistItem, Contract, ContractPatch, Finding, FindingPatch, ReviewRow } from '../data/types';
import { canApprove, isConfidentPending, summarize } from '../domain/completeness';
import type { Summary } from '../domain/completeness';
import { applyContractPatch, applyFindingPatch, joinRows } from '../domain/findings';

const EXTRACTION_REFRESH_MS = 5_000;
const WRITE_BATCH = 4;

interface ReviewData {
  contract: Contract;
  items: ChecklistItem[];
  findings: Finding[];
}

interface Slot {
  key: string;
  data: ReviewData | null;
  error: string | null;
}

interface FindingChange {
  id: string;
  patch: FindingPatch;
}

export interface Correction {
  value: string;
  /** Required for items that carry a judgment, ignored for the rest. */
  judgment: Judgment | null;
  notes: string;
}

export interface ReviewActions {
  accept(id: string): void;
  reject(id: string): void;
  correct(id: string, correction: Correction): void;
  /** Puts a finding back to Pending. The earlier reviewer entries stay on record but no longer count. */
  reset(id: string): void;
  acceptConfident(): void;
  approve(): void;
  reopen(): void;
  saveDetails(patch: ContractPatch): void;
  dismissNotice(): void;
  reload(): void;
}

export interface ReviewState {
  contract: Contract | null;
  rows: ReviewRow[];
  summary: Summary;
  loading: boolean;
  /** Set only when there is nothing to show. */
  fatalError: string | null;
  /** A failed refresh or write. The last good data stays on screen. */
  notice: string | null;
  busy: boolean;
  /** Approved contracts are read-only until reopened. */
  locked: boolean;
  approvable: boolean;
  actions: ReviewActions;
}

async function loadReview(contractId: string): Promise<ReviewData> {
  const repo = await getRepo();
  const [contract, items, findings] = await Promise.all([
    repo.getContract(contractId),
    repo.listChecklist(),
    repo.listFindings(contractId),
  ]);
  return { contract, items, findings };
}

function applyChanges(findings: readonly Finding[], changes: readonly FindingChange[]): Finding[] {
  const byId = new Map(changes.map((change) => [change.id, change.patch]));
  return findings.map((finding) => {
    const patch = byId.get(finding.id);
    return patch ? applyFindingPatch(finding, patch) : finding;
  });
}

function stamp(userId: string | null): Pick<FindingPatch, 'reviewedOn' | 'reviewedById'> {
  const reviewedOn = new Date().toISOString();
  return userId ? { reviewedOn, reviewedById: userId } : { reviewedOn };
}

export function useReview(contractId: string): ReviewState {
  const [slot, setSlot] = useState<Slot | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pending, setPending] = useState(0);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    function load(): void {
      loadReview(contractId)
        .then((data) => {
          if (cancelled) return;
          setSlot({ key: contractId, data, error: null });
          const status = data.contract.status;
          if (status === 'Received' || status === 'Extracting') timer = window.setTimeout(load, EXTRACTION_REFRESH_MS);
        })
        .catch((error: unknown) => {
          if (cancelled) return;
          const message = messageOf(error);
          setSlot((previous) =>
            previous !== null && previous.key === contractId
              ? { ...previous, error: message }
              : { key: contractId, data: null, error: message },
          );
        });
    }

    load();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [contractId, reloadKey]);

  useEffect(() => {
    let cancelled = false;
    getRepo()
      .then((repo) => repo.currentUserId())
      .then((id) => {
        if (!cancelled) setUserId(id);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const current = slot !== null && slot.key === contractId ? slot : null;
  const data = current?.data ?? null;
  const loadError = current?.error ?? null;
  const contract = data?.contract ?? null;
  const rows = useMemo(() => (data ? joinRows(data.findings, data.items) : []), [data]);
  const summary = useMemo(() => summarize(rows), [rows]);
  const locked = contract?.status === 'Approved';
  const reviewable = contract?.status === 'Ready for Review' || contract?.status === 'In Review';
  const approvable = reviewable && canApprove(rows);

  /** Shows the change at once, then saves it. A failed save is reported and the page reloads the saved state. */
  function write(changes: readonly FindingChange[], contractPatch: ContractPatch): void {
    setActionError(null);
    setPending((count) => count + 1);
    setSlot((previous) =>
      previous !== null && previous.key === contractId && previous.data
        ? {
            ...previous,
            data: {
              ...previous.data,
              contract: applyContractPatch(previous.data.contract, contractPatch),
              findings: applyChanges(previous.data.findings, changes),
            },
          }
        : previous,
    );

    getRepo()
      .then(async (repo) => {
        for (let i = 0; i < changes.length; i += WRITE_BATCH) {
          await Promise.all(changes.slice(i, i + WRITE_BATCH).map((change) => repo.updateFinding(change.id, change.patch)));
        }
        await repo.updateContract(contractId, contractPatch);
      })
      .catch((error: unknown) => {
        setActionError(messageOf(error));
        setReloadKey((key) => key + 1);
      })
      .finally(() => setPending((count) => Math.max(0, count - 1)));
  }

  /** A finding decision. The contract's found count and completeness follow it, and the first decision starts the review. */
  function commit(changes: readonly FindingChange[]): void {
    if (!data || locked || changes.length === 0) return;
    const next = summarize(joinRows(applyChanges(data.findings, changes), data.items));
    const contractPatch: ContractPatch = { foundCount: next.found, completeness: next.percent };
    if (data.contract.status === 'Ready for Review') contractPatch.status = 'In Review';
    write(changes, contractPatch);
  }

  const actions: ReviewActions = {
    accept: (id) => commit([{ id, patch: { reviewStatus: 'Accepted', ...stamp(userId) } }]),
    reject: (id) => commit([{ id, patch: { reviewStatus: 'Rejected', ...stamp(userId) } }]),
    correct: (id, correction) =>
      commit([
        {
          id,
          patch: {
            reviewStatus: 'Corrected',
            reviewerValue: correction.value,
            reviewerNotes: correction.notes,
            ...(correction.judgment ? { reviewerJudgment: correction.judgment } : {}),
            ...stamp(userId),
          },
        },
      ]),
    reset: (id) => commit([{ id, patch: { reviewStatus: 'Pending' } }]),
    acceptConfident: () =>
      commit(
        rows
          .filter((row) => isConfidentPending(row.finding))
          .map((row): FindingChange => ({ id: row.finding.id, patch: { reviewStatus: 'Accepted', ...stamp(userId) } })),
      ),
    approve: () => {
      if (approvable) write([], { status: 'Approved' });
    },
    reopen: () => {
      if (contract && locked) write([], { status: 'In Review' });
    },
    saveDetails: (patch) => {
      if (contract) write([], patch);
    },
    dismissNotice: () => setActionError(null),
    reload: () => setReloadKey((key) => key + 1),
  };

  return {
    contract,
    rows,
    summary,
    loading: current === null,
    fatalError: data === null ? loadError : null,
    notice: actionError ?? (data !== null ? loadError : null),
    busy: pending > 0,
    locked,
    approvable,
    actions,
  };
}
