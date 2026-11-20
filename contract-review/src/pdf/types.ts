import type { SourceRegion } from '../data/types';
import type { Rect } from '../domain/geometry';

/** The evidence a click points at. `nonce` changes on every click so repeating a click scrolls and pulses again. */
export interface HighlightTarget {
  nonce: number;
  page: number | null;
  regions: SourceRegion[];
  quote: string;
}

/** How the highlight was placed: by the AI's regions, by searching the page text, or only down to the page. */
export type LocateMethod = 'regions' | 'text' | 'page' | 'none';

/** A run of text from the PDF, in points at scale 1 with the origin at the top left of the page. */
export interface TextRun {
  text: string;
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface TextMatch {
  nonce: number;
  page: number;
  rects: Rect[];
}

export interface Resolved {
  method: LocateMethod;
  /** Highlight rects per page, in points at scale 1. */
  byPage: Map<number, Rect[]>;
  anchorPage: number | null;
  anchorRect: Rect | null;
}
