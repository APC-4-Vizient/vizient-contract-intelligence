/** How the evidence for a finding is marked on the page. */
export type EvidenceStyle = 'marker' | 'box' | 'highlight';

export const EVIDENCE_STYLES: ReadonlyArray<{ id: EvidenceStyle; label: string; title: string }> = [
  { id: 'marker', label: 'Marker', title: 'A bar in the margin and an underline. The text itself is left untouched.' },
  { id: 'box', label: 'Box', title: 'A thin outline around the passage.' },
  { id: 'highlight', label: 'Highlight', title: 'A soft highlighter over the text.' },
];

export const DEFAULT_EVIDENCE_STYLE: EvidenceStyle = 'highlight';

const STORAGE_KEY = 'vz-evidence-style';

/** Anything that is not one of the known styles falls back to the default, so a stale or hand-edited value never breaks the viewer. */
export function parseEvidenceStyle(value: unknown): EvidenceStyle {
  const known = EVIDENCE_STYLES.find((style) => style.id === value);
  return known ? known.id : DEFAULT_EVIDENCE_STYLE;
}

/** The host can block storage, in which case the choice simply is not remembered. */
export function loadEvidenceStyle(): EvidenceStyle {
  try {
    return parseEvidenceStyle(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return DEFAULT_EVIDENCE_STYLE;
  }
}

export function saveEvidenceStyle(style: EvidenceStyle): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, style);
  } catch {
    // Storage is blocked; the choice lasts until the page is reloaded.
  }
}
