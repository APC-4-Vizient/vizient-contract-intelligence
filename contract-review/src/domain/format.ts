const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})/;
const EMPTY = '\u2014';

/** Formats a date-only value without shifting it through UTC. */
export function formatDateOnly(value: string | null | undefined): string {
  if (!value) return EMPTY;
  const match = DATE_ONLY.exec(value);
  if (!match) return value;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return EMPTY;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export function formatClock(date: Date): string {
  return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', second: '2-digit' });
}

/** "70%" for whole numbers, "66.7%" otherwise. */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY;
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

/** Keeps a date-only column as yyyy-mm-dd. */
export function toDateOnly(value: string | null | undefined): string | null {
  if (!value) return null;
  const match = DATE_ONLY.exec(value);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : null;
}

/** "$1,234.50", or "$1,234" when cents are left out. */
export function formatUsd(value: number, cents = true): string {
  const digits = cents ? 2 : 0;
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/** A whole number with thousands separators: "1,235". */
export function formatCount(value: number): string {
  return Math.round(value).toLocaleString('en-US');
}
