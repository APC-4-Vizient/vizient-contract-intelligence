import type { DocumentType } from '../data/choices';
import type { Contract } from '../data/types';

export interface ParentSuggestion {
  contract: Contract;
  /** The number the contract cites that the suggested parent carries. */
  match: string;
}

/** An agreement number is a run of letters and digits with hyphens allowed inside, such as 4150832 or MSA-2023-014. */
const WORD = /[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*/g;
const BARE_YEAR = /^(?:19|20)\d{2}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The numbers a reference such as "Statement of Work No. 4150832 dated March 3, 2025" uses to name the agreement. Dates and bare years are skipped. */
export function referenceNumbers(reference: string): string[] {
  const found = new Map<string, string>();
  for (const word of reference.match(WORD) ?? []) {
    const digits = word.replace(/\D/g, '').length;
    if (digits < 4 || BARE_YEAR.test(word) || ISO_DATE.test(word)) continue;
    const key = word.toLowerCase();
    if (!found.has(key)) found.set(key, word);
  }
  return [...found.values()];
}

/** Whole words only, with spaces standing in for every separator, so "4150832" never matches inside "41508320". */
function words(text: string): string {
  return ` ${text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()} `;
}

/** 3: the contract number is the cited number. 2: the contract number contains it. 1: only the file name does. */
function score(candidate: Contract, number: string): number {
  const needle = words(number);
  const identifier = words(candidate.identifier);
  if (identifier === needle) return 3;
  if (identifier.includes(needle)) return 2;
  return words(candidate.name).includes(needle) ? 1 : 0;
}

interface Hit {
  contract: Contract;
  score: number;
  match: string;
}

function bestHit(candidate: Contract, numbers: readonly string[]): Hit | null {
  let best: Hit | null = null;
  for (const number of numbers) {
    const value = score(candidate, number);
    if (value > 0 && (best === null || value > best.score)) best = { contract: candidate, score: value, match: number };
  }
  return best;
}

/** How a reference words each kind of agreement, so "Statement of Work No. X" can pick the SOW over an amendment that carries the same number. */
const TYPE_WORDS: Readonly<Partial<Record<DocumentType, RegExp>>> = {
  SOW: /\b(?:statement of work|sow)\b/i,
  MSA: /\b(?:master|msa)\b/i,
  Amendment: /\bamendment\b/i,
  'Order Form': /\border form\b/i,
  DUA: /\b(?:data use agreement|dua)\b/i,
  BAA: /\b(?:business associate|baa)\b/i,
  NDA: /\b(?:non-?disclosure|nda)\b/i,
};

/** `prose` is the reference without its numbers, because a number can contain a type word (BP-SOW-2025-014). */
function namesType(prose: string, type: DocumentType | null): boolean {
  const pattern = type === null ? undefined : TYPE_WORDS[type];
  return pattern !== undefined && pattern.test(prose);
}

/** A link from this contract down to the candidate would make a loop. */
function descendsFrom(candidate: Contract, ancestorId: string, byId: ReadonlyMap<string, Contract>): boolean {
  const seen = new Set<string>();
  let parentId = candidate.parentContractId;
  while (parentId !== null && !seen.has(parentId)) {
    if (parentId === ancestorId) return true;
    seen.add(parentId);
    parentId = byId.get(parentId)?.parentContractId ?? null;
  }
  return false;
}

/**
 * The one contract that carries a number this contract cites as its parent agreement.
 * Equal numbers are common (an amendment often carries its SOW's number), so among equal matches the kind of agreement the reference names wins.
 * Nothing is suggested when none matches (the parent may not be uploaded) or when several still match equally well, and a person always confirms the link.
 */
export function suggestParent(reference: string, contract: Contract, contracts: readonly Contract[]): ParentSuggestion | null {
  if (contract.parentContractId !== null) return null;
  const numbers = referenceNumbers(reference);
  if (numbers.length === 0) return null;

  const byId = new Map(contracts.map((candidate) => [candidate.id, candidate]));
  const hits = contracts
    .filter((candidate) => candidate.id !== contract.id && !descendsFrom(candidate, contract.id, byId))
    .map((candidate) => bestHit(candidate, numbers))
    .filter((hit): hit is Hit => hit !== null);
  const top = Math.max(0, ...hits.map((hit) => hit.score));
  const leaders = hits.filter((hit) => hit.score === top);
  const prose = reference.replace(/\S*\d\S*/g, ' ');
  const named = leaders.filter((hit) => namesType(prose, hit.contract.documentType));
  const pool = named.length > 0 ? named : leaders;
  return pool.length === 1 ? { contract: pool[0].contract, match: pool[0].match } : null;
}
