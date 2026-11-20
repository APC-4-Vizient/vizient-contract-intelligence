import { formatUsd } from '../domain/format';
import {
  COST_GROUPS,
  RATES,
  SAMPLE_COSTS,
  costBars,
  costTiles,
  describeCostRow,
  formatCentsRange,
  formatUsdFine,
  partText,
  rateText,
  usageText,
} from './processingCost';
import {
  KINDS,
  KIND_LABELS,
  PROCESSING,
  STAGES,
  describeRow,
  formatSpan,
  processingTiles,
  runNote,
  timelineGeometry,
  totalSeconds,
} from './processingTime';
import type { StageId } from './processingTime';
import { cssVars } from './tone';

interface BarSegmentView {
  id: string;
  /** Picks the colour: see `data-kind` in about.css. */
  kind: string;
  label: string;
  value: string;
  /** This segment's share of its bar, as a percentage. */
  share: number;
  showLabel: boolean;
}

interface BarRowView {
  id: string;
  name: string;
  note: string;
  total: string;
  description: string;
  /** The bar's length as a share of the axis. */
  widthPercent: number;
  segments: BarSegmentView[];
}

interface BarTickView {
  label: string;
  percent: number;
}

interface LegendView {
  kind: string;
  label: string;
}

interface StackedBarsProps {
  title: string;
  rows: readonly BarRowView[];
  ticks: readonly BarTickView[];
  legend: readonly LegendView[];
  foot: string;
  /** Write each segment's name above its value. */
  showNames: boolean;
  /** The segment to bring forward while the rest fade back. */
  activeSegment?: string | null;
}

/** Rows of stacked bars on one shared scale: a longer bar is more time, or more money. */
function StackedBars({ title, rows, ticks, legend, foot, showNames, activeSegment = null }: StackedBarsProps) {
  const lastTick = ticks.length - 1;
  return (
    <figure className="ptl vz-card" aria-label={title} data-focus={activeSegment !== null} style={cssVars({ '--steps': lastTick })}>
      <ol className="ptl__rows">
        {rows.map((row, index) => (
          <li key={row.id} className="ptl__row" style={cssVars({ '--i': index, '--w': `${row.widthPercent}%` })}>
            <div className="ptl__name">
              <span className="ptl__title">{row.name}</span>
              <span className="ptl__note">{row.note}</span>
            </div>
            <div className="ptl__track" role="img" aria-label={row.description}>
              <div className="ptl__bar">
                {row.segments.map((segment) => (
                  <span
                    key={segment.id}
                    className="ptl__seg"
                    data-kind={segment.kind}
                    data-active={segment.id === activeSegment}
                    style={cssVars({ '--s': segment.share })}
                    title={`${segment.label}: ${segment.value}`}
                  >
                    {segment.showLabel ? (
                      <span className="ptl__seg-text">
                        {showNames ? <span className="ptl__seg-name">{segment.label}</span> : null}
                        <span className="ptl__seg-value">{segment.value}</span>
                      </span>
                    ) : null}
                  </span>
                ))}
              </div>
            </div>
            <p className="ptl__total">{row.total}</p>
          </li>
        ))}
      </ol>
      <div className="ptl__row ptl__row--axis" aria-hidden="true">
        <span />
        <div className="ptl__ticks">
          {ticks.map((tick, index) => (
            <span
              key={tick.label}
              className="ptl__tick"
              data-edge={index === 0 ? 'start' : index === lastTick ? 'end' : undefined}
              style={cssVars({ '--x': `${tick.percent}%` })}
            >
              {tick.label}
            </span>
          ))}
        </div>
        <span />
      </div>
      <ul className="ptl__legend">
        {legend.map((item) => (
          <li key={item.kind}>
            <span className="ptl__swatch" data-kind={item.kind} aria-hidden="true" />
            {item.label}
          </li>
        ))}
      </ul>
      <figcaption className="ptl__foot">{foot}</figcaption>
    </figure>
  );
}

const TIMELINE = timelineGeometry();

const TIME_ROWS: BarRowView[] = TIMELINE.rows.map((row) => ({
  id: row.run.id,
  name: row.run.label,
  note: runNote(row.run),
  total: formatSpan(row.total),
  description: describeRow(row),
  widthPercent: row.widthPercent,
  segments: row.segments.map((segment) => ({
    id: segment.id,
    kind: segment.kind,
    label: segment.label,
    value: formatSpan(segment.seconds),
    share: (segment.seconds / row.total) * 100,
    showLabel: segment.showLabel,
  })),
}));

const TIME_TICKS: BarTickView[] = TIMELINE.ticks.map((tick) => ({ label: tick.label, percent: tick.percent }));
const TIME_LEGEND: LegendView[] = KINDS.map((kind) => ({ kind, label: KIND_LABELS[kind] }));

/** One bar for each timed run, split into the six stages. The stage of the diagram step on show stands out. */
export function ProcessingTimeline({ activeStage = null }: { activeStage?: StageId | null }) {
  return (
    <StackedBars
      title="Time to process each timed contract, split into stages"
      rows={TIME_ROWS}
      ticks={TIME_TICKS}
      legend={TIME_LEGEND}
      foot="Minutes and seconds from the PDF being saved to Ready for Review. The bars share one scale, so a longer run is a longer bar."
      showNames
      activeSegment={activeStage}
    />
  );
}

const COSTS = costBars();

const COST_ROWS: BarRowView[] = COSTS.rows.map((row) => ({
  id: row.cost.document.id,
  name: row.cost.document.label,
  note: `${row.cost.document.pages} pages, ${formatCentsRange({ low: row.cost.perPage, high: row.cost.perPage })} a page`,
  total: formatUsd(row.cost.total),
  description: describeCostRow(row),
  widthPercent: row.widthPercent,
  segments: row.segments.map((segment) => ({
    id: segment.id,
    kind: segment.id,
    label: segment.label,
    value: formatUsdFine(segment.usd),
    share: (segment.usd / row.cost.total) * 100,
    showLabel: segment.showLabel,
  })),
}));

const COST_TICKS: BarTickView[] = COSTS.ticks.map((tick) => ({ label: tick.label, percent: tick.percent }));
const COST_LEGEND: LegendView[] = COST_GROUPS.map((group) => ({ kind: group.id, label: group.label }));

/** One bar for each synthetic sample, split into what the bill is made of. */
export function CostBars() {
  return (
    <StackedBars
      title="Estimated cost to process each sample contract, split into parts"
      rows={COST_ROWS}
      ticks={COST_TICKS}
      legend={COST_LEGEND}
      foot="Estimated at list prices, in US dollars. The bars share one scale, so a dearer document is a longer bar."
      showNames={false}
    />
  );
}

interface TileView {
  label: string;
  value: string;
  note: string;
}

function Tiles({ tiles }: { tiles: readonly TileView[] }) {
  return (
    <ul className="kpis">
      {tiles.map((tile) => (
        <li key={tile.label} className="kpi vz-card">
          <p className="kpi__label">{tile.label}</p>
          <p className="kpi__value">{tile.value}</p>
          <p className="kpi__note">{tile.note}</p>
        </li>
      ))}
    </ul>
  );
}

export function ProcessingTiles() {
  return <Tiles tiles={processingTiles()} />;
}

export function CostTiles() {
  return <Tiles tiles={costTiles()} />;
}

/** Every stage of every timed run, in seconds. */
export function ProcessingTable() {
  return (
    <div className="about__table-wrap">
      <table className="about__table about__table--numbers">
        <caption className="sr-only">Time spent in each stage, for each timed run</caption>
        <thead>
          <tr>
            <th scope="col">Stage</th>
            {PROCESSING.runs.map((run) => (
              <th key={run.id} scope="col">
                {run.label}
                <span className="about__table-sub">{runNote(run)}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {STAGES.map((stage) => (
            <tr key={stage.id}>
              <th scope="row">
                <span className="ptl__swatch" data-kind={stage.kind} aria-hidden="true" />
                {stage.label}
                <span className="about__table-sub">{stage.covers}</span>
              </th>
              {PROCESSING.runs.map((run) => (
                <td key={run.id}>{formatSpan(run.seconds[stage.id])}</td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Total</th>
            {PROCESSING.runs.map((run) => (
              <td key={run.id}>{formatSpan(totalSeconds(run))}</td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/** Quantity times price, part by part, for each synthetic sample. */
export function CostTable() {
  return (
    <div className="about__table-wrap">
      <table className="about__table about__table--numbers">
        <caption className="sr-only">Estimated cost of each part, for each sample contract</caption>
        <thead>
          <tr>
            <th scope="col">Part</th>
            <th scope="col">List price</th>
            {SAMPLE_COSTS.map((cost) => (
              <th key={cost.document.id} scope="col">
                {cost.document.label}
                <span className="about__table-sub">{cost.document.pages} pages, synthetic</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {RATES.map((rate) => (
            <tr key={rate.id}>
              <th scope="row">
                <span className="ptl__swatch" data-kind={rate.group} aria-hidden="true" />
                {rate.label}
                <span className="about__table-sub">{rate.covers}</span>
              </th>
              <td>
                {rateText(rate)}
                <span className="about__table-sub">{rate.service}</span>
              </td>
              {SAMPLE_COSTS.map((cost) => (
                <td key={cost.document.id}>
                  {partText(cost, rate.id)}
                  <span className="about__table-sub">{usageText(cost.document, rate)}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Total</th>
            <td />
            {SAMPLE_COSTS.map((cost) => (
              <td key={cost.document.id}>{formatUsd(cost.total)}</td>
            ))}
          </tr>
          <tr>
            <th scope="row">Per page</th>
            <td />
            {SAMPLE_COSTS.map((cost) => (
              <td key={cost.document.id}>{formatCentsRange({ low: cost.perPage, high: cost.perPage })}</td>
            ))}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
