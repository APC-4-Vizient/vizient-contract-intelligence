import { useEffect, useState } from 'react';
import { readIndexReadiness } from '../data/contractQuestions';
import type { IndexReadiness } from '../data/contractQuestions';
import { messageOf } from '../data/errors';

export function useContractIndex(contractId: string, processedOn: string | undefined): IndexReadiness {
  const [state, setState] = useState<IndexReadiness & { id: string; version?: string }>({
    id: '', ready: false, message: 'Checking document indexing...',
  });
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll(): Promise<void> {
      try {
        const result = await readIndexReadiness(contractId);
        if (alive) setState({ id: contractId, version: processedOn, ...result });
      } catch (error) {
        if (alive) setState({ id: contractId, version: processedOn, ready: false, message: messageOf(error) });
      }
      if (alive) timer = setTimeout(() => { void poll(); }, 10_000);
    }
    void poll();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [contractId, processedOn]);
  return state.id === contractId && state.version === processedOn
    ? state : { ready: false, message: 'Checking document indexing...' };
}
