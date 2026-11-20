import { describe, expect, it } from 'vitest';
import { EDGES, EDGE_BY_ID, NODES, NODE_BY_ID, STEPS, ZONES, ZONE_BY_ID, resolveRoute } from './architecture';
import {
  BIG_PICTURE,
  CHECKLIST_NOTE,
  DESIGN_CHOICES,
  GUARDRAILS,
  HOW_IT_WORKS_LEAD,
  HOW_IT_WORKS_TITLE,
  WHERE_IT_LIVES,
} from './howItWorksCopy';
import {
  ABOUT_THIS_PAGE,
  EYEBROW,
  PAGE_KIND,
  PRODUCT_NAME,
  SCOPE_NOTE,
  STEPS_TITLE,
} from '../standalone/standaloneCopy';

function collectStrings(value: unknown, into: string[] = []): string[] {
  if (typeof value === 'string') into.push(value);
  else if (Array.isArray(value)) value.forEach((item) => collectStrings(item, into));
  else if (value && typeof value === 'object') Object.values(value).forEach((item) => collectStrings(item, into));
  return into;
}

const unique = (values: readonly string[]) => new Set(values).size === values.length;

describe('the architecture map', () => {
  it('has unique ids, and every node sits in a zone that exists', () => {
    expect(unique(NODES.map((node) => node.id))).toBe(true);
    expect(unique(EDGES.map((edge) => edge.id))).toBe(true);
    expect(unique(STEPS.map((step) => step.id))).toBe(true);
    expect(unique(ZONES.map((zone) => zone.id))).toBe(true);
    for (const node of NODES) expect(ZONE_BY_ID.has(node.zone)).toBe(true);
  });

  it('puts every node on the slab of its own zone, and keeps nodes apart', () => {
    for (const node of NODES) {
      const zone = ZONE_BY_ID.get(node.zone);
      const [x, , z] = node.position;
      const inside = zone?.slabs.some(
        (slab) => Math.abs(x - slab.x) <= slab.width / 2 && Math.abs(z - slab.z) <= slab.depth / 2,
      );
      expect(inside, `${node.id} should stand on the ${node.zone} slab`).toBe(true);
    }
    for (const [index, a] of NODES.entries()) {
      for (const b of NODES.slice(index + 1)) {
        const distance = Math.hypot(a.position[0] - b.position[0], a.position[2] - b.position[2]);
        expect(distance, `${a.id} and ${b.id}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it('routes every edge between its own two nodes through points that exist', () => {
    for (const edge of EDGES) {
      expect(NODE_BY_ID.has(edge.from)).toBe(true);
      expect(NODE_BY_ID.has(edge.to)).toBe(true);
      expect(edge.route.length).toBeGreaterThanOrEqual(2);
      expect(edge.route[0].at).toBe(edge.from);
      expect(edge.route.at(-1)?.at).toBe(edge.to);
      for (const point of resolveRoute(edge)) {
        expect(point.every(Number.isFinite)).toBe(true);
        expect(point[1]).toBeGreaterThan(0);
      }
    }
  });
});

describe('the journey', () => {
  it('numbers eight steps and refers only to nodes and edges that exist', () => {
    expect(STEPS).toHaveLength(8);
    for (const step of STEPS) {
      expect(step.focus.length).toBeGreaterThan(0);
      for (const id of step.focus) expect(NODE_BY_ID.has(id)).toBe(true);
      for (const id of step.edges) expect(EDGE_BY_ID.has(id)).toBe(true);
      for (const hop of step.travel) expect(step.edges).toContain(hop.edge);
      if (step.enter) expect(step.focus).toContain(step.enter);
    }
  });

  it('shows every node and every edge in at least one step', () => {
    for (const node of NODES) expect(STEPS.some((step) => step.focus.includes(node.id)), node.id).toBe(true);
    for (const edge of EDGES) expect(STEPS.some((step) => step.edges.includes(edge.id)), edge.id).toBe(true);
  });

  it('moves the contract status forward and never back to nothing', () => {
    const order = ['Extracting', 'Ready for Review', 'Approved'];
    let last = -1;
    for (const step of STEPS) {
      if (!step.status) {
        expect(last, `step "${step.id}" has no status after one was set`).toBe(-1);
        continue;
      }
      const position = order.indexOf(step.status);
      expect(position).toBeGreaterThanOrEqual(last);
      last = position;
    }
    expect(last).toBe(order.length - 1);
  });
});

describe('everything on the screen', () => {
  const all = collectStrings([
    NODES,
    EDGES.map((edge) => edge.caption),
    STEPS,
    ZONES.map((zone) => zone.label),
    HOW_IT_WORKS_TITLE,
    HOW_IT_WORKS_LEAD,
    BIG_PICTURE,
    DESIGN_CHOICES,
    WHERE_IT_LIVES,
    GUARDRAILS,
    CHECKLIST_NOTE,
    [PRODUCT_NAME, PAGE_KIND, EYEBROW, SCOPE_NOTE, STEPS_TITLE, ABOUT_THIS_PAGE],
  ]);

  it('is never empty', () => {
    for (const text of all) expect(text.trim().length).toBeGreaterThan(0);
  });

  it('carries no identifiers, hosts or accounts', () => {
    const forbidden = [
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
      /\.(dynamics|sharepoint|onmicrosoft)\.com/i,
      /\.azurewebsites\.net/i,
      /\.(cognitiveservices|openai|services\.ai)\.azure\.com/i,
      /[\w.-]+@[\w-]+\.[a-z]{2,}/i,
    ];
    for (const text of all) for (const pattern of forbidden) expect(text, `"${text}" matches ${pattern}`).not.toMatch(pattern);
  });

  it('makes no claim the project cannot back up', () => {
    const unsupported = [/\bonly\b[^.]*\b(synthetic|made-up)\b/i, /reviewed by/i, /\bwho (reviewed|approved)\b/i];
    for (const text of all) for (const pattern of unsupported) expect(text, `"${text}" matches ${pattern}`).not.toMatch(pattern);
  });
});
