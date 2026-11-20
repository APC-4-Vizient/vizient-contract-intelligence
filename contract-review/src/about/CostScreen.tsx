import { useState } from 'react';
import { Money20Regular, Timer20Regular } from '@fluentui/react-icons';
import { Btn } from '../screens/Btn';
import { prefersMotion } from './motion';
import { CostBars, CostTable, CostTiles, ProcessingTable, ProcessingTiles, ProcessingTimeline } from './ProcessingCharts';
import { COST_TITLE, costExtras, costLead, costMethod } from './processingCost';
import { PROCESSING_TITLE, processingLead, processingMethod } from './processingTime';
import './about.css';

/** "Time and cost": how long one contract takes and what it costs to process, measured on synthetic samples. */
export default function CostScreen() {
  const [animate] = useState(prefersMotion);

  const jumpTo = (id: string) => {
    const target = document.getElementById(id);
    if (!target) return;
    target.scrollIntoView({ behavior: animate ? 'smooth' : 'auto', block: 'start' });
    target.focus({ preventScroll: true });
  };

  return (
    <article className="about cost">
      <section className="cost-hero" data-vz-theme="mulberry" aria-labelledby="cost-title">
        <p className="vz-eyebrow">Time and cost</p>
        <h1 id="cost-title" className="vz-heading vz-h1">
          What it takes to process one contract
        </h1>
        <p className="cost-hero__meta">
          Snapshots from three timed runs and three synthetic sample contracts, priced at public list prices. Not a benchmark and not an invoice.
        </p>
      </section>

      <div className="cost-jump" role="group" aria-label="Jump to a section of this page">
        <span className="cost-jump__label">On this page</span>
        <Btn variant="tint" small icon={<Timer20Regular />} onClick={() => jumpTo('cost-processing')}>
          {PROCESSING_TITLE}
        </Btn>
        <Btn variant="tint" small icon={<Money20Regular />} onClick={() => jumpTo('cost-per-document')}>
          {COST_TITLE}
        </Btn>
      </div>

      <section className="about__section" aria-labelledby="cost-processing">
        <h2 id="cost-processing" tabIndex={-1} className="vz-heading vz-h2">
          {PROCESSING_TITLE}
        </h2>
        <p className="about__note">{processingLead()}</p>
        <ProcessingTiles />
        <ProcessingTimeline />
        <ProcessingTable />
        <h3 className="about__subhead">How the times were measured</h3>
        <ul className="about__list">
          {processingMethod().map((note) => (
            <li key={note.term}>
              <strong>{note.term}</strong> {note.text}
            </li>
          ))}
        </ul>
      </section>

      <section className="about__section" aria-labelledby="cost-per-document">
        <h2 id="cost-per-document" tabIndex={-1} className="vz-heading vz-h2">
          {COST_TITLE}
        </h2>
        <p className="about__note">{costLead()}</p>
        <CostTiles />
        <CostBars />
        <CostTable />
        <h3 className="about__subhead">How the costs were worked out</h3>
        <ul className="about__list">
          {costMethod().map((note) => (
            <li key={note.term}>
              <strong>{note.term}</strong> {note.text}
            </li>
          ))}
        </ul>
        <h3 className="about__subhead">Left out of the totals</h3>
        <ul className="about__list">
          {costExtras().map((note) => (
            <li key={note.term}>
              <strong>{note.term}</strong> {note.text}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
