import { polygonToRect, topmost } from '../domain/geometry';
import type { Rect } from '../domain/geometry';
import type { HighlightTarget, Resolved, TextMatch } from './types';

const NOTHING: Resolved = { method: 'none', byPage: new Map(), anchorPage: null, anchorRect: null };

/**
 * Decides where the evidence goes. The AI's regions win; without them a text match found for this same click is used;
 * without that the viewer can only jump to the page.
 */
export function resolveHighlight(target: HighlightTarget | null, textMatch: TextMatch | null): Resolved {
  if (!target) return NOTHING;

  const byPage = new Map<number, Rect[]>();
  for (const region of target.regions) {
    const rect = polygonToRect(region.polygon);
    if (!rect) continue;
    const list = byPage.get(region.page);
    if (list) list.push(rect);
    else byPage.set(region.page, [rect]);
  }
  if (byPage.size > 0) {
    const anchorPage = Math.min(...byPage.keys());
    return { method: 'regions', byPage, anchorPage, anchorRect: topmost(byPage.get(anchorPage) ?? []) };
  }

  if (textMatch && textMatch.nonce === target.nonce && textMatch.rects.length > 0) {
    byPage.set(textMatch.page, textMatch.rects);
    return { method: 'text', byPage, anchorPage: textMatch.page, anchorRect: topmost(textMatch.rects) };
  }

  if (target.page !== null) return { method: 'page', byPage, anchorPage: target.page, anchorRect: null };
  return NOTHING;
}
