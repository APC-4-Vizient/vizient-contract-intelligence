import { useMemo, useSyncExternalStore } from 'react';

export type Route = { name: 'list' } | { name: 'contract'; id: string } | { name: 'how-it-works' } | { name: 'cost' };

const CONTRACT_ROUTE = /^#\/contract\/([A-Za-z0-9_-]{1,64})\/?$/;
const HOW_IT_WORKS_ROUTE = /^#\/how-it-works\/?$/;
const COST_ROUTE = /^#\/cost\/?$/;

/** Anything that is not a known link is the list, so a stray or hand-edited hash never breaks the app. */
export function parseRoute(hash: string): Route {
  const match = CONTRACT_ROUTE.exec(hash);
  if (match) return { name: 'contract', id: match[1] };
  if (HOW_IT_WORKS_ROUTE.test(hash)) return { name: 'how-it-works' };
  if (COST_ROUTE.test(hash)) return { name: 'cost' };
  return { name: 'list' };
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

function currentHash(): string {
  return window.location.hash;
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, currentHash, () => '');
  return useMemo(() => parseRoute(hash), [hash]);
}

export function openContract(id: string): void {
  window.location.hash = `#/contract/${id}`;
}

export function openList(): void {
  window.location.hash = '#/';
}
