import { describe, expect, it } from 'vitest';
import { STEPS } from './architecture';
import { initialJourney, journeyReducer } from './useJourney';
import type { JourneyState } from './useJourney';

const LAST = STEPS.length - 1;
const start: JourneyState = { step: null, playing: false, selected: null, hovered: null, motion: true };

describe('journeyReducer', () => {
  it('plays from the overview at the first step and advances on each tick', () => {
    const playing = journeyReducer(start, { type: 'play' });
    expect(playing).toMatchObject({ step: 0, playing: true });
    expect(journeyReducer(playing, { type: 'tick' }).step).toBe(1);
  });

  it('stops on the last step and replays from the first', () => {
    const atEnd = journeyReducer({ ...start, step: LAST, playing: true }, { type: 'tick' });
    expect(atEnd).toMatchObject({ step: LAST, playing: false });
    expect(journeyReducer(atEnd, { type: 'play' })).toMatchObject({ step: 0, playing: true });
  });

  it('resumes where it paused', () => {
    const paused = journeyReducer({ ...start, step: 3, playing: true }, { type: 'pause' });
    expect(journeyReducer(paused, { type: 'play' })).toMatchObject({ step: 3, playing: true });
  });

  it('ignores a tick that arrives after the story was paused', () => {
    const paused = { ...start, step: 2 };
    expect(journeyReducer(paused, { type: 'tick' })).toBe(paused);
  });

  it('pauses when the viewer picks a step, and keeps the step in range', () => {
    const playing = { ...start, step: 1, playing: true };
    expect(journeyReducer(playing, { type: 'goTo', index: 5 })).toMatchObject({ step: 5, playing: false });
    expect(journeyReducer(playing, { type: 'goTo', index: 99 }).step).toBe(LAST);
    expect(journeyReducer(playing, { type: 'goTo', index: -4 }).step).toBe(0);
    expect(journeyReducer(start, { type: 'next' }).step).toBe(0);
    expect(journeyReducer({ ...start, step: LAST }, { type: 'next' }).step).toBe(LAST);
    expect(journeyReducer({ ...start, step: 0 }, { type: 'prev' }).step).toBe(0);
    expect(journeyReducer(start, { type: 'prev' }).step).toBeNull();
  });

  it('selects a part, closes it when chosen again and pauses only when something is chosen', () => {
    const playing = { ...start, step: 2, playing: true };
    const chosen = journeyReducer(playing, { type: 'select', id: 'dataverse' });
    expect(chosen).toMatchObject({ selected: 'dataverse', playing: false });
    expect(journeyReducer(chosen, { type: 'select', id: 'dataverse' }).selected).toBeNull();
    expect(journeyReducer(playing, { type: 'select', id: null }).playing).toBe(true);
  });

  it('resets to the overview', () => {
    const busy: JourneyState = { step: 4, playing: true, selected: 'function', hovered: 'function', motion: false };
    expect(journeyReducer(busy, { type: 'reset' })).toEqual({ step: null, playing: false, selected: null, hovered: 'function', motion: false });
  });

  it('starts with motion on when the system does not ask for less', () => {
    expect(initialJourney().motion).toBe(true);
  });
});
