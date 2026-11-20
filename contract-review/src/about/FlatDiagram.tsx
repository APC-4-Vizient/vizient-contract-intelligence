import { NODES, STEPS, ZONES } from './architecture';
import { toneStyle } from './tone';
import type { Journey } from './useJourney';

/** The diagram without 3D: the same parts, grouped by where they live. Shown when the browser cannot draw the 3D view. */
export function FlatDiagram({ journey }: { journey: Journey }) {
  const { state } = journey;
  const focus = state.step === null ? [] : STEPS[state.step].focus;
  return (
    <div className="arch-flat" role="group" aria-label="The parts of the system, grouped by where they live">
      {ZONES.map((zone) => (
        <section key={zone.id} className="arch-flat__zone" style={toneStyle(zone.color)}>
          <h3 className="arch-flat__zone-name">{zone.label}</h3>
          <ul className="arch-flat__parts">
            {NODES.filter((node) => node.zone === zone.id).map((node) => (
              <li key={node.id}>
                <button
                  type="button"
                  className="arch-flat__part"
                  style={toneStyle(node.color)}
                  data-lit={focus.includes(node.id) || state.selected === node.id}
                  aria-pressed={state.selected === node.id}
                  onClick={() => journey.select(node.id)}
                >
                  <span className="arch__label-name">{node.label}</span>
                  <span className="arch__label-kicker">{node.kicker}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
