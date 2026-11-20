import { useEffect, useState } from 'react';
import { messageOf } from '../data/errors';

interface Slot<T> {
  key: string;
  data: T | null;
  error: string | null;
}

export interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Loads `load(key)` whenever `key` changes. The result is stored with the key it belongs to, so a slow response for an
 * old key can never show up for the current one. `load` must be a stable function (declare it at module level).
 */
export function useResource<T>(key: string | null, load: (key: string) => Promise<T>): Resource<T> {
  const [slot, setSlot] = useState<Slot<T> | null>(null);

  useEffect(() => {
    if (key === null) return;
    let cancelled = false;
    load(key)
      .then((data) => {
        if (!cancelled) setSlot({ key, data, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setSlot({ key, data: null, error: messageOf(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [key, load]);

  const current = slot !== null && slot.key === key ? slot : null;
  return { data: current?.data ?? null, error: current?.error ?? null, loading: key !== null && current === null };
}
