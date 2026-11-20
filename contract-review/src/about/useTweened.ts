import { useEffect, useRef, useState } from 'react';
import { easeOutCubic, lerp } from './scene/math';

/** Glides to `target` whenever it changes, from wherever it had got to. With `enabled` false it is the target at once. */
export function useTweened(target: number, enabled: boolean, durationMs = 700): number {
  const [value, setValue] = useState(target);
  const drawn = useRef(target);

  useEffect(() => {
    const from = drawn.current;
    const duration = enabled ? durationMs : 0;
    let frame = 0;
    let startedAt: number | null = null;
    const step = (now: number) => {
      startedAt ??= now;
      const progress = duration === 0 ? 1 : Math.min(1, (now - startedAt) / duration);
      drawn.current = lerp(from, target, easeOutCubic(progress));
      setValue(drawn.current);
      if (progress < 1) frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [target, enabled, durationMs]);

  return enabled ? value : target;
}
