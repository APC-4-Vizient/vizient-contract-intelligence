export interface Rect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export const POINTS_PER_INCH = 72;

/**
 * Bounding box of a Content Understanding polygon, in PDF points at scale 1 (origin top-left).
 * The polygon is in inches, so one inch is 72 points regardless of the page size.
 */
export function polygonToRect(polygon: readonly number[]): Rect | null {
  if (polygon.length < 4 || polygon.length % 2 !== 0) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (let i = 0; i < polygon.length; i += 2) {
    const x = polygon[i];
    const y = polygon[i + 1];
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  return {
    left: minX * POINTS_PER_INCH,
    top: minY * POINTS_PER_INCH,
    width: (maxX - minX) * POINTS_PER_INCH,
    height: (maxY - minY) * POINTS_PER_INCH,
  };
}

/** Converts a rect in points to CSS pixels at a scale, growing it by `pad` pixels on every side. */
export function scaleRect(rect: Rect, scale: number, pad = 0): Rect {
  return {
    left: rect.left * scale - pad,
    top: rect.top * scale - pad,
    width: rect.width * scale + pad * 2,
    height: rect.height * scale + pad * 2,
  };
}

/** Evidence that reads as one piece: the box around it and the line boxes inside it, in the same units as the input. */
export interface Passage {
  bounds: Rect;
  lines: Rect[];
}

/** How far below a passage the next line may start, in line heights, and still belong to it. */
const PASSAGE_GAP = 1.25;

const rightOf = (rect: Rect): number => rect.left + rect.width;
const bottomOf = (rect: Rect): number => rect.top + rect.height;

/**
 * Groups line boxes into passages. A line joins a passage when it overlaps it sideways and starts within about a
 * line of where it ends, so a clause that wraps over several lines or paragraphs is one passage, while a second
 * column or a quote further down the page is another.
 */
export function groupPassages(rects: readonly Rect[]): Passage[] {
  const sorted = rects.filter((rect) => rect.width > 0 && rect.height > 0).sort((a, b) => a.top - b.top || a.left - b.left);
  const groups: Array<Passage & { tallest: number }> = [];

  for (const rect of sorted) {
    const home = groups.find(
      (group) =>
        rect.left < rightOf(group.bounds) &&
        rightOf(rect) > group.bounds.left &&
        rect.top - bottomOf(group.bounds) <= Math.max(rect.height, group.tallest) * PASSAGE_GAP,
    );
    if (!home) {
      groups.push({ bounds: rect, lines: [rect], tallest: rect.height });
      continue;
    }
    const left = Math.min(home.bounds.left, rect.left);
    const top = Math.min(home.bounds.top, rect.top);
    home.bounds = {
      left,
      top,
      width: Math.max(rightOf(home.bounds), rightOf(rect)) - left,
      height: Math.max(bottomOf(home.bounds), bottomOf(rect)) - top,
    };
    home.lines.push(rect);
    home.tallest = Math.max(home.tallest, rect.height);
  }

  return groups.map(({ bounds, lines }) => ({ bounds, lines }));
}

/** The rect that sits highest on the page, used as the scroll anchor. */
export function topmost(rects: readonly Rect[]): Rect | null {
  let best: Rect | null = null;
  for (const rect of rects) {
    if (best === null || rect.top < best.top) best = rect;
  }
  return best;
}
