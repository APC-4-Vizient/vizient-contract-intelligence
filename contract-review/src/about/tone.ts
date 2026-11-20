import type { CSSProperties } from 'react';

/** A style object made of CSS custom properties, which React's CSSProperties type does not describe. */
export function cssVars(vars: Record<string, string | number>): CSSProperties {
  return vars as unknown as CSSProperties;
}

/** Passes a part's or zone's color to the stylesheet as `--tone`. */
export function toneStyle(color: string): CSSProperties {
  return cssVars({ '--tone': color });
}
