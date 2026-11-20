import { useCallback, useEffect, useState } from 'react';
import { messageOf } from '../data/errors';
import { getRepo } from '../data/repo';
import type { Contract } from '../data/types';

export const CONTRACTS_REFRESH_MS = 10_000;

interface Snapshot {
  contracts: Contract[] | null;
  error: string | null;
  updatedAt: Date | null;
}

export interface ContractsState extends Snapshot {
  loading: boolean;
  refresh: () => void;
}

/** The contracts list, refreshed every 10 seconds while the tab is visible and straight away when it becomes visible. */
export function useContracts(): ContractsState {
  const [snapshot, setSnapshot] = useState<Snapshot>({ contracts: null, error: null, updatedAt: null });
  const [reloadKey, setReloadKey] = useState(0);
  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    function load(): Promise<void> {
      return getRepo()
        .then((repo) => repo.listContracts())
        .then((contracts) => {
          if (!cancelled) setSnapshot({ contracts, error: null, updatedAt: new Date() });
        })
        .catch((error: unknown) => {
          // The last good list stays on screen; the problem is shown next to it.
          if (!cancelled) setSnapshot((previous) => ({ ...previous, error: messageOf(error) }));
        });
    }

    function schedule(): void {
      if (cancelled) return;
      timer = window.setTimeout(() => {
        if (document.hidden) schedule();
        else void load().then(schedule);
      }, CONTRACTS_REFRESH_MS);
    }

    function onVisibility(): void {
      if (document.hidden || cancelled) return;
      window.clearTimeout(timer);
      void load().then(schedule);
    }

    void load().then(schedule);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [reloadKey]);

  return { ...snapshot, loading: snapshot.contracts === null && snapshot.error === null, refresh };
}
