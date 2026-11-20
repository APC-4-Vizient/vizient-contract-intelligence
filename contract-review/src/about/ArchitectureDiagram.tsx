import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowRepeatAll20Regular,
  ArrowReset20Regular,
  ChevronLeft20Regular,
  ChevronRight20Regular,
  Pause20Regular,
  Play20Regular,
  ZoomIn20Regular,
  ZoomOut20Regular,
} from '@fluentui/react-icons';
import { Btn } from '../screens/Btn';
import { Chip } from '../screens/Chips';
import { EDGES, NODES, NODE_BY_ID, STEPS, ZONES } from './architecture';
import { FlatDiagram } from './FlatDiagram';
import type { Engine } from './scene/engine';
import { TourClock } from './TourClock';
import { toneStyle } from './tone';
import type { Journey } from './useJourney';

type Status = 'loading' | 'ready' | 'unsupported';

const LAST_STEP = STEPS.length - 1;

function NodeDetail({ journey }: { journey: Journey }) {
  const node = journey.state.selected === null ? null : NODE_BY_ID.get(journey.state.selected);
  if (!node) {
    return (
      <div className="arch__detail" data-empty="true">
        <p className="arch__detail-hint">Click any part of the diagram to see what it does.</p>
      </div>
    );
  }
  return (
    <div className="arch__detail" style={toneStyle(node.color)}>
      <div className="arch__detail-head">
        <h3 className="arch__detail-title">{node.title}</h3>
        <button type="button" className="vz-icon-btn" aria-label="Close details" onClick={() => journey.select(node.id)}>
          {'\u00D7'}
        </button>
      </div>
      <p>{node.summary}</p>
      <ul className="arch__bullets">
        {node.bullets.map((bullet) => (
          <li key={bullet}>{bullet}</li>
        ))}
      </ul>
    </div>
  );
}

/** The interactive diagram: a 3D scene when the browser can draw one, a plain grouped list when it cannot. */
export function ArchitectureDiagram({ journey }: { journey: Journey }) {
  const { state, hover, select } = journey;
  const cardRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<Engine | null>(null);
  const initialMotion = useRef(state.motion);
  const motionRef = useRef(state.motion);
  const [status, setStatus] = useState<Status>('loading');

  // On a short screen the caption and the detail panel sit under the fold: bring the whole card into view, and do
  // nothing when it already is.
  const reveal = useCallback(() => {
    cardRef.current?.scrollIntoView({ behavior: motionRef.current ? 'smooth' : 'auto', block: 'nearest' });
  }, []);

  // three.js is a separate chunk: it downloads only when this page is opened.
  useEffect(() => {
    const container = stageRef.current;
    const labels = labelsRef.current;
    if (!container || !labels) return;
    let cancelled = false;
    let engine: Engine | null = null;
    import('./scene/engine')
      .then(({ createEngine }) => {
        if (cancelled) return;
        engine = createEngine({
          container,
          labels,
          motion: initialMotion.current,
          onHover: hover,
          onSelect: (id) => {
            select(id);
            if (id) reveal();
          },
        });
        engineRef.current = engine;
        setStatus('ready');
      })
      .catch(() => {
        if (!cancelled) setStatus('unsupported');
      });
    return () => {
      cancelled = true;
      engine?.dispose();
      engineRef.current = null;
    };
  }, [hover, select, reveal]);

  const { step, selected, hovered, motion } = state;
  useEffect(() => {
    motionRef.current = motion;
    engineRef.current?.setMotion(motion);
  }, [motion, status]);
  useEffect(() => {
    engineRef.current?.setStep(step);
  }, [step, status]);
  useEffect(() => {
    engineRef.current?.setSelected(selected);
  }, [selected, status]);
  useEffect(() => {
    engineRef.current?.setHovered(hovered);
  }, [hovered, status]);

  const current = step === null ? null : STEPS[step];
  const flat = status === 'unsupported';
  const finished = step === LAST_STEP && !state.playing;
  const playLabel = state.playing ? 'Pause' : step === null ? 'Follow a contract' : finished ? 'Replay' : 'Resume';
  const PlayIcon = state.playing ? Pause20Regular : finished ? ArrowRepeatAll20Regular : Play20Regular;
  const togglePlay = () => {
    if (state.playing) {
      journey.pause();
      return;
    }
    journey.play();
    reveal();
  };

  return (
    <section ref={cardRef} className="arch vz-card" aria-label="Interactive diagram of how a contract moves through the system">
      <div className="arch__toolbar">
        <Btn variant="cta" small icon={<PlayIcon />} onClick={togglePlay}>
          {playLabel}
        </Btn>
        <span className="arch__toolbar-spacer" />
        {flat ? null : (
          <>
            <Btn
              variant="outline"
              small
              icon={<ArrowReset20Regular />}
              onClick={() => {
                journey.reset();
                engineRef.current?.resetView();
              }}
            >
              Overview
            </Btn>
            <span className="arch__zoom" role="group" aria-label="Zoom">
              <button type="button" className="vz-icon-btn" aria-label="Zoom out" onClick={() => engineRef.current?.zoomBy(1.2)}>
                <ZoomOut20Regular />
              </button>
              <button type="button" className="vz-icon-btn" aria-label="Zoom in" onClick={() => engineRef.current?.zoomBy(1 / 1.2)}>
                <ZoomIn20Regular />
              </button>
            </span>
            <Btn variant="outline" small aria-pressed={motion} onClick={journey.toggleMotion}>
              Motion: {motion ? 'on' : 'off'}
            </Btn>
          </>
        )}
      </div>

      {flat ? (
        <FlatDiagram journey={journey} />
      ) : (
        <div
          ref={stageRef}
          className="arch__stage"
          data-state={status}
          role="group"
          aria-label="3D diagram. Drag to rotate, hold Ctrl and scroll to zoom, or use the buttons. Each part is also a button, and the same story is written out in the steps below."
        >
          <div ref={labelsRef} className="arch__labels">
            {ZONES.map((zone) => (
              <span key={zone.id} className="arch__zone" style={toneStyle(zone.color)} data-anchor="zone" data-id={zone.id} aria-hidden="true">
                {zone.label}
              </span>
            ))}
            {EDGES.filter((edge) => current?.edges.includes(edge.id)).map((edge) => (
              <span key={edge.id} className="arch__edge" data-anchor="edge" data-id={edge.id} aria-hidden="true">
                {edge.caption}
              </span>
            ))}
            {current?.status ? (
              <span className="arch__status" data-anchor="status" aria-hidden="true">
                <span className="arch__status-label">Contract status</span>
                <Chip label={current.status} />
              </span>
            ) : null}
            {NODES.map((node) => {
              const lit = (current?.focus.includes(node.id) ?? false) || selected === node.id || hovered === node.id;
              return (
                <button
                  key={node.id}
                  type="button"
                  className="arch__label"
                  style={toneStyle(node.color)}
                  data-anchor="node"
                  data-id={node.id}
                  data-lit={lit}
                  aria-pressed={selected === node.id}
                  onClick={() => {
                    select(node.id);
                    reveal();
                  }}
                  onMouseEnter={() => hover(node.id)}
                  onMouseLeave={() => hover(null)}
                  onFocus={() => hover(node.id)}
                  onBlur={() => hover(null)}
                >
                  <span className="arch__label-name">{node.label}</span>
                  <span className="arch__label-kicker">{node.kicker}</span>
                </button>
              );
            })}
          </div>
          {status === 'loading' ? (
            <p className="arch__note" role="status">
              Loading the 3D view…
            </p>
          ) : null}
        </div>
      )}

      <div className="arch__info">
        <div className="arch__caption" aria-live={state.playing ? 'off' : 'polite'}>
          {current ? (
            <>
              <p className="vz-eyebrow">
                Step {(step ?? 0) + 1} of {STEPS.length}
              </p>
              <h3 className="arch__caption-title">{current.title}</h3>
              <p className="arch__caption-text">{current.text}</p>
            </>
          ) : (
            <>
              <p className="vz-eyebrow">Overview</p>
              <h3 className="arch__caption-title">Eight parts, three homes and one person</h3>
              <p className="arch__caption-text">
                Press <strong>Follow a contract</strong> to watch one contract travel through the system, or click any part to see what it does.
              </p>
            </>
          )}
          <TourClock stepId={current?.id ?? null} motion={motion} />
          <div className="arch__steps">
            <button type="button" className="vz-icon-btn" aria-label="Previous step" disabled={step === null || step === 0} onClick={journey.prev}>
              <ChevronLeft20Regular />
            </button>
            <ol className="arch__dots">
              {STEPS.map((item, index) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="arch__dot"
                    aria-label={`Step ${index + 1}: ${item.title}`}
                    aria-current={step === index ? 'step' : undefined}
                    data-done={step !== null && index < step}
                    onClick={() => journey.goTo(index)}
                  />
                </li>
              ))}
            </ol>
            <button type="button" className="vz-icon-btn" aria-label="Next step" disabled={step === LAST_STEP} onClick={journey.next}>
              <ChevronRight20Regular />
            </button>
          </div>
        </div>
        <div className="arch__side">
          <NodeDetail journey={journey} />
          <ul className="arch__legend" aria-label="Where each part lives">
            {ZONES.map((zone) => (
              <li key={zone.id} style={toneStyle(zone.color)}>
                <span className="arch__swatch" aria-hidden="true" />
                {zone.label}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
