import { useRef } from 'react';
import { Money20Regular, Timer20Regular } from '@fluentui/react-icons';
import { getRepo } from '../data/repo';
import type { ChecklistItem } from '../data/types';
import { useResource } from '../hooks/useResource';
import { ArchitectureDiagram } from './ArchitectureDiagram';
import { STEPS } from './architecture';
import {
  BIG_PICTURE,
  CHECKLIST_NOTE,
  DESIGN_CHOICES,
  GUARDRAILS,
  HOW_IT_WORKS_LEAD,
  HOW_IT_WORKS_TITLE,
  WHERE_IT_LIVES,
} from './howItWorksCopy';
import { ProcessingTimeline } from './ProcessingCharts';
import { COST_QUESTION, costMention, stepCost } from './processingCost';
import { PROCESSING_QUESTION, isStageId, processingLead, processingTakeaways, stepTiming } from './processingTime';
import { useJourney } from './useJourney';
import './about.css';

const loadChecklist = () => getRepo().then((repo) => repo.listChecklist());

interface ChecklistGroupView {
  group: string;
  items: ChecklistItem[];
}

function groupChecklist(items: readonly ChecklistItem[]): ChecklistGroupView[] {
  const groups = new Map<string, ChecklistItem[]>();
  for (const item of [...items].filter((entry) => entry.isActive).sort((a, b) => a.sortOrder - b.sortOrder)) {
    const list = groups.get(item.group) ?? [];
    list.push(item);
    groups.set(item.group, list);
  }
  return [...groups].map(([group, list]) => ({ group, items: list }));
}

/** "How it works": an interactive 3D diagram of the pipeline, then the story written out in plain words. */
export default function HowItWorksScreen() {
  const journey = useJourney();
  const diagramRef = useRef<HTMLDivElement>(null);
  const checklist = useResource<ChecklistItem[]>('checklist', loadChecklist);
  const groups = checklist.data ? groupChecklist(checklist.data) : [];
  const shownStep = journey.state.step === null ? null : STEPS[journey.state.step];
  const activeStage = shownStep && isStageId(shownStep.id) ? shownStep.id : null;

  const showStep = (index: number) => {
    journey.goTo(index);
    diagramRef.current?.scrollIntoView({ behavior: journey.state.motion ? 'smooth' : 'auto', block: 'start' });
  };

  return (
    <article className="about">
      <header className="about__intro">
        <p className="vz-eyebrow">How it works</p>
        <h1 className="vz-heading vz-h1">{HOW_IT_WORKS_TITLE}</h1>
        <p className="about__lead">{HOW_IT_WORKS_LEAD}</p>
      </header>

      <div ref={diagramRef} className="about__diagram">
        <ArchitectureDiagram journey={journey} />
      </div>

      <section className="about__section" aria-labelledby="about-steps">
        <h2 id="about-steps" className="vz-heading vz-h2">
          The journey, step by step
        </h2>
        <ol className="steps">
          {STEPS.map((step, index) => {
            const timing = stepTiming(step.id);
            const cost = stepCost(step.id);
            return (
              <li key={step.id} className="step" data-active={journey.state.step === index}>
                <button type="button" className="step__head" onClick={() => showStep(index)} aria-label={`Show step ${index + 1} in the diagram: ${step.title}`}>
                  <span className="step__number" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span className="step__title">{step.title}</span>
                </button>
                <p className="step__text">{step.text}</p>
                <p className="step__detail">{step.detail}</p>
                {timing || cost ? (
                  <ul className="step__takes">
                    {timing ? (
                      <li>
                        <Timer20Regular aria-hidden="true" />
                        {timing}
                      </li>
                    ) : null}
                    {cost ? (
                      <li>
                        <Money20Regular aria-hidden="true" />
                        {cost}
                      </li>
                    ) : null}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="about__section" aria-labelledby="about-time">
        <h2 id="about-time" className="vz-heading vz-h2">
          {PROCESSING_QUESTION}
        </h2>
        <p className="about__note">{processingLead()}</p>
        <ProcessingTimeline activeStage={activeStage} />
        <ul className="about__list">
          {processingTakeaways().map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      <section className="about__section" aria-labelledby="about-cost">
        <h2 id="about-cost" className="vz-heading vz-h2">
          {COST_QUESTION}
        </h2>
        <p className="about__note">
          {costMention()}{' '}
          <a className="vz-link" href="#/cost">
            See the breakdown on the Time and cost page
          </a>
          .
        </p>
      </section>

      <section className="about__section about__prose" aria-labelledby="about-big-picture">
        <h2 id="about-big-picture" className="vz-heading vz-h2">
          The big picture
        </h2>
        {BIG_PICTURE.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
      </section>

      <section className="about__section" aria-labelledby="about-design">
        <h2 id="about-design" className="vz-heading vz-h2">
          Why it is built this way
        </h2>
        <ul className="choices">
          {DESIGN_CHOICES.map((choice) => (
            <li key={choice.title} className="choice vz-card">
              <h3 className="choice__title">{choice.title}</h3>
              <p>{choice.text}</p>
            </li>
          ))}
        </ul>
      </section>

      {groups.length > 0 ? (
        <section className="about__section" aria-labelledby="about-checklist">
          <h2 id="about-checklist" className="vz-heading vz-h2">
            What the AI is asked
          </h2>
          <p className="about__note">{CHECKLIST_NOTE}</p>
          <div className="checklist">
            {groups.map((entry) => (
              <div key={entry.group} className="checklist__group">
                <h3 className="checklist__name">
                  {entry.group} <span className="muted">({entry.items.length})</span>
                </h3>
                <ul className="checklist__items">
                  {entry.items.map((item) => (
                    <li key={item.id} className="vz-chip vz-chip--outline" title={item.definition || undefined}>
                      {item.label}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="about__section" aria-labelledby="about-where">
        <h2 id="about-where" className="vz-heading vz-h2">
          Where everything lives
        </h2>
        <div className="about__table-wrap">
          <table className="about__table">
            <thead>
              <tr>
                <th scope="col">Piece</th>
                <th scope="col">Lives in</th>
                <th scope="col">Built with</th>
              </tr>
            </thead>
            <tbody>
              {WHERE_IT_LIVES.map((row) => (
                <tr key={row.piece}>
                  <th scope="row">{row.piece}</th>
                  <td>{row.lives}</td>
                  <td>{row.builtWith}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="about__section" aria-labelledby="about-limits">
        <h2 id="about-limits" className="vz-heading vz-h2">
          Guardrails and limits
        </h2>
        <ul className="about__list">
          {GUARDRAILS.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>
    </article>
  );
}
