import { useState } from 'react';
import { Tooltip } from '@fluentui/react-components';
import type { Summary } from '../domain/completeness';
import { isConfidentPending, isFoundNow } from '../domain/completeness';
import { groupTitle } from '../domain/display';
import { groupRows } from '../domain/findings';
import type { Finding, ReviewRow } from '../data/types';
import { Btn } from './Btn';
import { ConfirmDialog } from './ConfirmDialog';
import { FindingRow } from './FindingRow';
import type { Filter, RowHandlers } from './panelTypes';

interface FindingsPanelProps {
  /** Every finding, for the counts. */
  rows: readonly ReviewRow[];
  /** What the current filter shows, in display order. */
  visibleRows: readonly ReviewRow[];
  summary: Summary;
  filter: Filter;
  onFilter: (filter: Filter) => void;
  selectedId: string | null;
  editingId: string | null;
  locked: boolean;
  busy: boolean;
  handlers: RowHandlers;
  onSelect: (finding: Finding) => void;
  onAcceptConfident: () => void;
}

export function FindingsPanel({
  rows,
  visibleRows,
  summary,
  filter,
  onFilter,
  selectedId,
  editingId,
  locked,
  busy,
  handlers,
  onSelect,
  onAcceptConfident,
}: FindingsPanelProps) {
  const [confirmBulk, setConfirmBulk] = useState(false);
  const confident = rows.filter((row) => isConfidentPending(row.finding)).length;
  const allGroups = groupRows(rows);
  const shownGroups = groupRows(visibleRows);

  return (
    <aside className="findings" aria-label="Findings">
      <div className="findings__toolbar">
        <div className="seg" role="group" aria-label="Show findings">
          <button type="button" className="seg__btn" aria-pressed={filter === 'all'} onClick={() => onFilter('all')}>
            All {summary.total}
          </button>
          <Tooltip
            content="Findings nobody has reviewed yet that the AI marked Unclear or Not Found."
            relationship="description"
          >
            <button type="button" className="seg__btn" aria-pressed={filter === 'attention'} onClick={() => onFilter('attention')}>
              Needs attention {summary.attention}
            </button>
          </Tooltip>
        </div>
        {!locked ? (
          <Btn small variant="tint" disabled={confident === 0 || busy} onClick={() => setConfirmBulk(true)}>
            Accept all confident ({confident})
          </Btn>
        ) : null}
      </div>

      <div className="findings__scroll">
        {rows.length === 0 ? (
          <p className="findings__empty">No findings yet.</p>
        ) : visibleRows.length === 0 ? (
          <p className="findings__empty">Nothing needs attention. Every Unclear and Not Found item has been reviewed.</p>
        ) : (
          shownGroups.map(({ group, rows: groupRowsShown }) => {
            const full = allGroups.find((entry) => entry.group === group)?.rows ?? groupRowsShown;
            const found = full.filter(isFoundNow).length;
            return (
              <section key={group} className="findings__section">
                <h2 className="findings__heading">
                  {groupTitle(group)}
                  <span className="findings__count">
                    {found} of {full.length} found
                  </span>
                </h2>
                <ul className="findings__list">
                  {groupRowsShown.map((row) => (
                    <FindingRow
                      key={row.finding.id}
                      row={row}
                      selected={row.finding.id === selectedId}
                      editing={row.finding.id === editingId}
                      locked={locked}
                      onSelect={onSelect}
                      handlers={handlers}
                    />
                  ))}
                </ul>
              </section>
            );
          })
        )}
      </div>

      <ConfirmDialog
        open={confirmBulk}
        title={`Accept ${confident} confident findings?`}
        confirmLabel="Accept all"
        onCancel={() => setConfirmBulk(false)}
        onConfirm={() => {
          setConfirmBulk(false);
          onAcceptConfident();
        }}
      >
        <p>
          The AI marked these findings Found and nobody has reviewed them yet. Unclear and Not Found items stay Pending for your review.
          You can reset any accepted finding afterwards.
        </p>
      </ConfirmDialog>
    </aside>
  );
}
