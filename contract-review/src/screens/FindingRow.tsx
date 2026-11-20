import { useEffect, useRef } from 'react';
import { Tooltip } from '@fluentui/react-components';
import type { Finding, ReviewRow } from '../data/types';
import { effectiveValue, judgmentToShow, previewOf } from '../domain/display';
import { formatDateTime } from '../domain/format';
import { Btn } from './Btn';
import { Chip, ConfidencePill } from './Chips';
import { CorrectEditor } from './CorrectEditor';
import type { RowHandlers } from './panelTypes';

interface FindingRowProps {
  row: ReviewRow;
  selected: boolean;
  editing: boolean;
  locked: boolean;
  onSelect: (finding: Finding) => void;
  handlers: RowHandlers;
}

function Facts({ row }: { row: ReviewRow }) {
  const { finding, item } = row;
  const corrected = finding.reviewStatus === 'Corrected';
  const judgment = judgmentToShow(row);
  const aiConditions = finding.aiConditions.trim();
  const aiValue = finding.aiValue.trim();

  return (
    <div className="finding__facts">
      {corrected ? (
        <div className="finding__fact">
          <span className="vz-eyebrow">Reviewer&rsquo;s answer</span>
          {judgment ? <Chip label={judgment} /> : null}
          <p>{effectiveValue(row).trim() || <span className="muted">No value stated.</span>}</p>
          {finding.reviewerNotes.trim() ? <p className="muted">Notes: {finding.reviewerNotes}</p> : null}
        </div>
      ) : null}

      <div className={corrected ? 'finding__fact finding__fact--ai' : 'finding__fact'}>
        <span className="vz-eyebrow">AI&rsquo;s answer</span>
        {corrected && item.hasJudgment && finding.aiJudgment && finding.aiJudgment !== 'N/A' ? <Chip label={finding.aiJudgment} /> : null}
        <p>{aiValue || <span className="muted">Nothing extracted.</span>}</p>
        {aiConditions && aiConditions !== aiValue ? <p className="muted">Conditions: {aiConditions}</p> : null}
      </div>

      <div className="finding__fact">
        <span className="vz-eyebrow">Contract text{finding.page ? ` \u00B7 page ${finding.page}` : ''}</span>
        {finding.clause.trim() ? (
          <blockquote className="finding__clause">{finding.clause}</blockquote>
        ) : (
          <p className="muted">No supporting text was found.</p>
        )}
      </div>

      {item.definition ? (
        <p className="finding__definition">
          <strong>What we look for:</strong> {item.definition}
        </p>
      ) : null}
      {finding.reviewStatus !== 'Pending' && finding.reviewedOn ? (
        <p className="finding__stamp muted">Reviewed {formatDateTime(finding.reviewedOn)}</p>
      ) : null}
    </div>
  );
}

export function FindingRow({ row, selected, editing, locked, onSelect, handlers }: FindingRowProps) {
  const { finding, item } = row;
  const element = useRef<HTMLLIElement>(null);
  const judgment = judgmentToShow(row);
  const preview = previewOf(row);
  const status = finding.reviewStatus;
  // An open row shows the whole answer below, so its one-line summary would only repeat it.
  const showPreview = !selected || preview.muted;

  useEffect(() => {
    if (selected) element.current?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  const label = item.definition ? (
    <Tooltip content={item.definition} relationship="description">
      <span className="finding__label">{item.label}</span>
    </Tooltip>
  ) : (
    <span className="finding__label">{item.label}</span>
  );

  return (
    <li ref={element} className={`vz-row finding${status === 'Rejected' ? ' finding--rejected' : ''}`} aria-current={selected ? 'true' : undefined}>
      <button type="button" className="finding__head" aria-expanded={selected} onClick={() => onSelect(finding)}>
        <span className="finding__top">
          {label}
          <span className="finding__meta">
            <ConfidencePill value={finding.confidence} />
            <span className="finding__page">{finding.page ? `p. ${finding.page}` : 'no page'}</span>
          </span>
        </span>
        <span className="finding__chips">
          {finding.presence ? <Chip label={finding.presence} /> : null}
          {judgment ? <Chip label={judgment} /> : null}
          {status !== 'Pending' ? <Chip label={status} /> : null}
        </span>
        {showPreview ? (
          <span className={preview.muted ? 'finding__preview finding__preview--muted' : 'finding__preview'}>{preview.text}</span>
        ) : null}
      </button>

      {selected ? (
        <div className="finding__body">
          {editing ? (
            <CorrectEditor row={row} onSave={(correction) => handlers.correct(finding, correction)} onCancel={handlers.cancelEdit} />
          ) : (
            <>
              <Facts row={row} />
              {!locked ? (
                <div className="finding__actions">
                  <Btn small disabled={status === 'Accepted'} onClick={() => handlers.accept(finding)}>
                    {finding.presence === 'Not Found' ? 'Confirm not found' : 'Accept'}
                  </Btn>
                  <Btn small variant="outline" onClick={() => handlers.startEdit(finding)}>
                    Correct
                  </Btn>
                  <Btn small variant="outline" disabled={status === 'Rejected'} onClick={() => handlers.reject(finding)}>
                    Reject
                  </Btn>
                  {status !== 'Pending' ? (
                    <button type="button" className="finding__reset vz-link" onClick={() => handlers.reset(finding)}>
                      Reset to Pending
                    </button>
                  ) : null}
                </div>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </li>
  );
}
