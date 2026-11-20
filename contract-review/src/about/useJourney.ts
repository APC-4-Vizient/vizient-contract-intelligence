import { useEffect, useMemo, useReducer } from 'react';
import { STEPS } from './architecture';
import type { NodeId } from './architecture';
import { prefersMotion } from './motion';

/** How long the story rests on each step while it plays on its own. */
export const STEP_MS = 5500;

const LAST_STEP = STEPS.length - 1;

export interface JourneyState {
  /** The step being shown, or null for the overview. */
  step: number | null;
  playing: boolean;
  selected: NodeId | null;
  hovered: NodeId | null;
  /** Animation on or off. Starts off for people who ask their system for reduced motion. */
  motion: boolean;
}

export type JourneyAction =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'tick' }
  | { type: 'goTo'; index: number }
  | { type: 'next' }
  | { type: 'prev' }
  | { type: 'reset' }
  | { type: 'select'; id: NodeId | null }
  | { type: 'hover'; id: NodeId | null }
  | { type: 'toggleMotion' };

export function journeyReducer(state: JourneyState, action: JourneyAction): JourneyState {
  switch (action.type) {
    case 'play':
      // Playing from the overview, or again after the last step, starts from the first step.
      return { ...state, playing: true, step: state.step === null || state.step >= LAST_STEP ? 0 : state.step };
    case 'pause':
      return state.playing ? { ...state, playing: false } : state;
    case 'tick':
      if (!state.playing) return state;
      if (state.step === null) return { ...state, step: 0 };
      return state.step >= LAST_STEP ? { ...state, playing: false } : { ...state, step: state.step + 1 };
    case 'goTo':
      return { ...state, playing: false, step: Math.min(LAST_STEP, Math.max(0, Math.trunc(action.index))) };
    case 'next':
      return { ...state, playing: false, step: state.step === null ? 0 : Math.min(LAST_STEP, state.step + 1) };
    case 'prev':
      return { ...state, playing: false, step: state.step === null ? null : Math.max(0, state.step - 1) };
    case 'reset':
      return { ...state, step: null, playing: false, selected: null };
    case 'select':
      // Choosing the same part again closes it. Choosing a part pauses the story so it can be read.
      return { ...state, selected: action.id === state.selected ? null : action.id, playing: action.id === null ? state.playing : false };
    case 'hover':
      return state.hovered === action.id ? state : { ...state, hovered: action.id };
    case 'toggleMotion':
      return { ...state, motion: !state.motion };
  }
}

export function initialJourney(): JourneyState {
  return { step: null, playing: false, selected: null, hovered: null, motion: prefersMotion() };
}

export interface JourneyActions {
  play(): void;
  pause(): void;
  goTo(index: number): void;
  next(): void;
  prev(): void;
  reset(): void;
  select(id: NodeId | null): void;
  hover(id: NodeId | null): void;
  toggleMotion(): void;
}

export interface Journey extends JourneyActions {
  state: JourneyState;
}

export function useJourney(): Journey {
  const [state, dispatch] = useReducer(journeyReducer, undefined, initialJourney);

  useEffect(() => {
    if (!state.playing) return;
    const timer = window.setTimeout(() => dispatch({ type: 'tick' }), STEP_MS);
    return () => window.clearTimeout(timer);
  }, [state.playing, state.step]);

  const actions = useMemo<JourneyActions>(
    () => ({
      play: () => dispatch({ type: 'play' }),
      pause: () => dispatch({ type: 'pause' }),
      goTo: (index) => dispatch({ type: 'goTo', index }),
      next: () => dispatch({ type: 'next' }),
      prev: () => dispatch({ type: 'prev' }),
      reset: () => dispatch({ type: 'reset' }),
      select: (id) => dispatch({ type: 'select', id }),
      hover: (id) => dispatch({ type: 'hover', id }),
      toggleMotion: () => dispatch({ type: 'toggleMotion' }),
    }),
    [],
  );

  return { state, ...actions };
}
