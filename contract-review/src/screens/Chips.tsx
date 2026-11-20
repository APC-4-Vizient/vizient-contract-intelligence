import { chipClass } from '../theme/vizient-fluent-theme';

export function Chip({ label, title }: { label: string; title?: string }) {
  return (
    <span className={chipClass(label)} title={title}>
      {label}
    </span>
  );
}

export function ConfidencePill({ value }: { value: number | null }) {
  if (value === null) return null;
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <span className="vz-confidence" title="How sure the AI is of this answer">
      <span className="sr-only">AI confidence </span>
      {percent}%
    </span>
  );
}
