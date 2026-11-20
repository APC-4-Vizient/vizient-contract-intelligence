import { useState } from 'react';
import { Timer20Regular } from '@fluentui/react-icons';
import { Btn } from '../screens/Btn';
import { PROCESSING, clockAtStep, formatSpanWords, formatStopwatch, middleRun, runNote } from './processingTime';
import { useTweened } from './useTweened';

/**
  A stopwatch that follows the tour: at each step it shows how long a real run had taken by the end of that step.
  The buttons switch between the runs we timed.
*/
export function TourClock({ stepId, motion }: { stepId: string | null; motion: boolean }) {
  const [runId, setRunId] = useState(() => middleRun().id);
  const run = PROCESSING.runs.find((entry) => entry.id === runId) ?? middleRun();
  const reading = clockAtStep(run, stepId);
  const shown = useTweened(reading.seconds, motion);

  return (
    <div className="arch__clock">
      <p className="sr-only">
        {formatSpanWords(reading.seconds)} on the clock. {reading.note}.
      </p>
      <div className="arch__clock-face" aria-hidden="true">
        <Timer20Regular />
        <span className="arch__clock-time">{formatStopwatch(shown)}</span>
      </div>
      <p className="arch__clock-note" aria-hidden="true">
        {reading.note}
      </p>
      <div className="arch__runs" role="group" aria-label="Which timed run to show">
        {PROCESSING.runs.map((entry) => (
          <Btn key={entry.id} small variant="outline" aria-pressed={entry.id === run.id} title={runNote(entry)} onClick={() => setRunId(entry.id)}>
            {entry.label}
          </Btn>
        ))}
      </div>
    </div>
  );
}
