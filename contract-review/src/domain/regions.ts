import type { SourceRegion } from '../data/types';

const MAX_REGIONS = 60;

/** Parses the vz_sourceregions JSON column. Malformed entries are dropped, never thrown on. */
export function parseRegions(raw: string | null | undefined): SourceRegion[] {
  if (!raw) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];

  const regions: SourceRegion[] = [];
  for (const entry of parsed) {
    if (regions.length >= MAX_REGIONS) break;
    if (typeof entry !== 'object' || entry === null) continue;
    const { page, polygon } = entry as { page?: unknown; polygon?: unknown };
    if (typeof page !== 'number' || !Number.isInteger(page) || page < 1) continue;
    if (!Array.isArray(polygon) || polygon.length < 4 || polygon.length % 2 !== 0) continue;
    if (!polygon.every((n) => typeof n === 'number' && Number.isFinite(n))) continue;
    regions.push({ page, polygon: polygon as number[] });
  }
  return regions;
}
