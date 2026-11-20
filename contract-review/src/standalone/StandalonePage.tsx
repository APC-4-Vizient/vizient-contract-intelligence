import { useRef } from 'react';
import { ArchitectureDiagram } from '../about/ArchitectureDiagram';
import { STEPS } from '../about/architecture';
import { HOW_IT_WORKS_LEAD, HOW_IT_WORKS_TITLE } from '../about/howItWorksCopy';
import { useJourney } from '../about/useJourney';
import { ABOUT_THIS_PAGE, EYEBROW, PAGE_KIND, PRODUCT_NAME, SCOPE_NOTE, STEPS_TITLE } from './standaloneCopy';

/**
  The "How it works" diagram of the Contract Review app as a page of its own: the same interactive 3D view and the
  same step list, with none of the app around them. It reads no data and calls nothing, so it runs from a file.
*/
export function StandalonePage() {
  const journey = useJourney();
  const diagramRef = useRef<HTMLDivElement>(null);

  const showStep = (index: number) => {
    journey.goTo(index);
    diagramRef.current?.scrollIntoView({ behavior: journey.state.motion ? 'smooth' : 'auto', block: 'start' });
  };

  return (
    <div className="standalone">
      <div className="standalone__top">
        <header className="vz-appbar">
          <span className="vz-appbar__title">{PRODUCT_NAME}</span>
          <span className="vz-appbar__spacer" />
          <span className="standalone__kind">{PAGE_KIND}</span>
        </header>
      </div>
      <main>
        <article className="about">
          <header className="about__intro">
            <p className="vz-eyebrow">{EYEBROW}</p>
            <h1 className="vz-heading vz-h1">{HOW_IT_WORKS_TITLE}</h1>
            <p className="about__lead">{HOW_IT_WORKS_LEAD}</p>
            <p className="about__note">{SCOPE_NOTE}</p>
          </header>

          <div ref={diagramRef} className="about__diagram">
            <ArchitectureDiagram journey={journey} />
          </div>

          <section className="about__section" aria-labelledby="standalone-steps">
            <h2 id="standalone-steps" className="vz-heading vz-h2">
              {STEPS_TITLE}
            </h2>
            <ol className="steps">
              {STEPS.map((step, index) => (
                <li key={step.id} className="step" data-active={journey.state.step === index}>
                  <button type="button" className="step__head" onClick={() => showStep(index)} aria-label={`Show step ${index + 1} in the diagram: ${step.title}`}>
                    <span className="step__number" aria-hidden="true">
                      {index + 1}
                    </span>
                    <span className="step__title">{step.title}</span>
                  </button>
                  <p className="step__text">{step.text}</p>
                  <p className="step__detail">{step.detail}</p>
                </li>
              ))}
            </ol>
          </section>

          <footer>
            <p className="about__note">{ABOUT_THIS_PAGE}</p>
          </footer>
        </article>
      </main>
    </div>
  );
}
