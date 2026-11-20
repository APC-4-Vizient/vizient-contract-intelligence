import { useCallback, useEffect, useMemo, useState } from 'react';
import { MessageBar, MessageBarActions, MessageBarBody, MessageBarTitle, Spinner } from '@fluentui/react-components';
import { ArrowLeft20Regular } from '@fluentui/react-icons';
import { getRepo } from '../data/repo';
import type { Finding } from '../data/types';
import { needsAttention } from '../domain/completeness';
import { contractTitle } from '../domain/contracts';
import { effectiveValue } from '../domain/display';
import { groupRows } from '../domain/findings';
import { formatPercent } from '../domain/format';
import { useResource } from '../hooks/useResource';
import { useReview } from '../hooks/useReview';
import { useContractIndex } from '../hooks/useContractIndex';
import { PdfViewer } from '../pdf/PdfViewer';
import type { HighlightTarget } from '../pdf/types';
import { Btn } from './Btn';
import { Chip } from './Chips';
import { ConfirmDialog } from './ConfirmDialog';
import { DetailsDrawer } from './DetailsDrawer';
import { FindingsPanel } from './FindingsPanel';
import { ContractQuestionDrawer } from './ContractQuestionDrawer';
import type { Filter, RowHandlers } from './panelTypes';

interface Selection {
  id: string;
  target: HighlightTarget;
  editing: boolean;
}

/** Keys look like "<attempt>:<contractId>" so a retry reloads the same PDF. */
async function loadPdf(key: string): Promise<Uint8Array> {
  const repo = await getRepo();
  return repo.downloadPdf(key.slice(key.indexOf(':') + 1));
}

/** Arrow keys belong to these elements, so the findings list must leave them alone. */
const OWN_ARROW_KEYS = 'input, textarea, select, [contenteditable="true"], [role="dialog"], [role="listbox"], [role="combobox"], .pdf-scroller';

export function ReviewScreen({ contractId }: { contractId: string }) {
  const review = useReview(contractId);
  const { contract, rows, summary, actions, locked, busy } = review;
  const documentIndex = useContractIndex(contractId, contract?.processedOn ?? undefined);

  const [filter, setFilter] = useState<Filter>('all');
  const [selection, setSelection] = useState<Selection | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [questionsOpen, setQuestionsOpen] = useState(false);
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [pdfAttempt, setPdfAttempt] = useState(0);
  const pdf = useResource(contract ? `${pdfAttempt}:${contractId}` : null, loadPdf);

  const visibleRows = useMemo(() => {
    const filtered = filter === 'attention' ? rows.filter((row) => needsAttention(row.finding)) : rows;
    return groupRows(filtered).flatMap((entry) => entry.rows);
  }, [filter, rows]);

  const selectedId = selection?.id ?? null;

  /** Each click gets a new nonce, so clicking the same finding again scrolls and pulses again. */
  const select = useCallback((finding: Finding) => {
    setSelection((previous) => ({
      id: finding.id,
      editing: false,
      target: { nonce: (previous?.target.nonce ?? 0) + 1, page: finding.page, regions: finding.regions, quote: finding.clause },
    }));
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent): void {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      if (event.target instanceof Element && event.target.closest(OWN_ARROW_KEYS)) return;
      if (visibleRows.length === 0) return;
      const index = visibleRows.findIndex((row) => row.finding.id === selectedId);
      const step = event.key === 'ArrowDown' ? 1 : -1;
      const next = index < 0 ? 0 : Math.min(visibleRows.length - 1, Math.max(0, index + step));
      if (next === index) return;
      event.preventDefault();
      select(visibleRows[next].finding);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [visibleRows, selectedId, select]);

  /** In the attention list a decided finding drops out, so move on to the next one that still needs a look. */
  function advanceFrom(finding: Finding): void {
    if (filter !== 'attention') return;
    const index = visibleRows.findIndex((row) => row.finding.id === finding.id);
    if (index < 0) return;
    const neighbor = visibleRows[index + 1] ?? visibleRows[index - 1];
    if (neighbor) select(neighbor.finding);
    else setSelection(null);
  }

  const handlers: RowHandlers = {
    accept: (finding) => {
      advanceFrom(finding);
      actions.accept(finding.id);
    },
    reject: (finding) => {
      advanceFrom(finding);
      actions.reject(finding.id);
    },
    correct: (finding, correction) => {
      setSelection((previous) => (previous ? { ...previous, editing: false } : previous));
      advanceFrom(finding);
      actions.correct(finding.id, correction);
    },
    reset: (finding) => actions.reset(finding.id),
    startEdit: (finding) => setSelection((previous) => (previous && previous.id === finding.id ? { ...previous, editing: true } : previous)),
    cancelEdit: () => setSelection((previous) => (previous ? { ...previous, editing: false } : previous)),
  };

  if (review.fatalError) {
    return (
      <div className="screen-state">
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Could not open this contract</MessageBarTitle>
            {review.fatalError}
          </MessageBarBody>
        </MessageBar>
        <div className="screen-state__actions">
          <Btn onClick={actions.reload}>Try again</Btn>
          <a className="vz-btn vz-btn--outline" href="#/">
            Back to contracts
          </a>
        </div>
      </div>
    );
  }
  if (!contract) {
    return (
      <div className="screen-state">
        <Spinner label={'Loading contract\u2026'} />
      </div>
    );
  }

  const parentRow = rows.find((row) => row.item.key === 'ParentAgreementReference');
  // A rejected answer is wrong by the reviewer's own call, so it must not drive a suggested link.
  const parentReference = parentRow && parentRow.finding.reviewStatus !== 'Rejected' ? effectiveValue(parentRow) : '';
  const waiting = contract.status === 'Received' || contract.status === 'Extracting';
  const reviewed = summary.total - summary.pending;
  const approveHint =
    summary.total === 0
      ? 'There are no findings to approve yet.'
      : summary.pending > 0
        ? `${summary.pending} ${summary.pending === 1 ? 'finding is' : 'findings are'} still pending. Review every finding before approving.`
        : '';
  const caption = [
    `AI found ${summary.aiFound}`,
    `Reviewed ${reviewed} of ${summary.total}`,
    summary.corrected > 0 ? `${summary.corrected} corrected` : '',
    summary.rejected > 0 ? `${summary.rejected} rejected` : '',
  ]
    .filter((part) => part !== '')
    .join(' \u00B7 ');
  const subtitle = [contract.documentType, contract.identifier, contract.vendor.trim() ? contract.name : '']
    .filter((part): part is string => typeof part === 'string' && part !== '')
    .join(' \u00B7 ');

  return (
    <div className="review">
      <header className="review__header">
        <a className="vz-link review__back" href="#/">
          <ArrowLeft20Regular />
          Contracts
        </a>
        <div className="review__title">
          <h1 className="vz-h2">{contractTitle(contract)}</h1>
          {subtitle ? <p className="muted">{subtitle}</p> : null}
        </div>
        {contract.status ? <Chip label={contract.status} /> : null}

        {summary.total > 0 ? (
          <div className="review__completeness">
            <div className="review__completeness-line">
              <strong>
                {summary.found} of {summary.total} found
              </strong>
              <span>{formatPercent(summary.percent)}</span>
            </div>
            <div
              className="vz-progress"
              role="progressbar"
              aria-label="Completeness"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(summary.percent)}
            >
              <span style={{ width: `${summary.percent}%` }} />
            </div>
            <p className="review__caption muted">{caption}</p>
          </div>
        ) : null}

        <div className="review__tools">
          {contract.hasParentReference ? (
            contract.parentContractId ? (
              <span className="vz-chip vz-chip--success">Parent agreement linked</span>
            ) : (
              <button
                type="button"
                className="vz-chip vz-chip--warning vz-chip--action"
                title="This contract refers to a parent agreement that is not linked yet. Open the details to link it."
                onClick={() => setDetailsOpen(true)}
              >
                Parent agreement not linked
              </button>
            )
          ) : null}
          {busy ? (
            <span className="review__saving muted" role="status">
              Saving{'\u2026'}
            </span>
          ) : null}
          <Btn variant="outline" onClick={() => setDetailsOpen(true)}>
            Details
          </Btn>
          <Btn variant="outline" onClick={() => setQuestionsOpen(true)}
            disabled={!documentIndex.ready || contract.status === 'Received' || contract.status === 'Extracting' || contract.status === 'Failed'}>
            Ask this contract
          </Btn>
          <span className="muted" role="status">{documentIndex.message}</span>
          {locked ? (
            <Btn variant="outline" disabled={busy} onClick={actions.reopen}>
              Reopen review
            </Btn>
          ) : (
            <span title={approveHint}>
              <Btn variant="cta" disabled={!review.approvable || busy} onClick={() => setConfirmApprove(true)}>
                Approve
              </Btn>
            </span>
          )}
        </div>
      </header>

      {waiting ? (
        <MessageBar intent="info">
          <MessageBarBody>
            <MessageBarTitle>Extraction in progress</MessageBarTitle>
            The findings appear here as soon as the analysis finishes. This page refreshes on its own.
          </MessageBarBody>
        </MessageBar>
      ) : null}
      {contract.status === 'Failed' ? (
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Extraction failed</MessageBarTitle>
            {contract.errorMessage || 'No details were recorded.'}
          </MessageBarBody>
        </MessageBar>
      ) : null}
      {locked ? (
        <MessageBar intent="success">
          <MessageBarBody>
            <MessageBarTitle>Approved</MessageBarTitle>
            The findings are read-only. Reopen the review to change them.
          </MessageBarBody>
        </MessageBar>
      ) : null}
      {review.notice ? (
        <MessageBar intent="error">
          <MessageBarBody>
            <MessageBarTitle>Something went wrong</MessageBarTitle>
            {review.notice}
          </MessageBarBody>
          <MessageBarActions>
            <Btn small variant="outline" onClick={actions.reload}>
              Reload
            </Btn>
            <Btn small variant="outline" onClick={actions.dismissNotice}>
              Dismiss
            </Btn>
          </MessageBarActions>
        </MessageBar>
      ) : null}

      <div className="review__body">
        <section className="review__pdf" aria-label="Contract document">
          {pdf.loading ? (
            <div className="pdf-message">
              <Spinner label={'Loading the contract PDF\u2026'} />
            </div>
          ) : pdf.error ? (
            <div className="pdf-message" role="alert">
              <p>Could not load the PDF: {pdf.error}</p>
              <Btn small variant="outline" onClick={() => setPdfAttempt((attempt) => attempt + 1)}>
                Try again
              </Btn>
            </div>
          ) : pdf.data ? (
            <PdfViewer key={contractId} data={pdf.data} target={selection?.target ?? null} />
          ) : null}
        </section>

        <FindingsPanel
          rows={rows}
          visibleRows={visibleRows}
          summary={summary}
          filter={filter}
          onFilter={setFilter}
          selectedId={selectedId}
          editingId={selection?.editing ? selection.id : null}
          locked={locked}
          busy={busy}
          handlers={handlers}
          onSelect={select}
          onAcceptConfident={actions.acceptConfident}
        />
      </div>

        <ContractQuestionDrawer key={`${contractId}:${contract.processedOn}`} open={questionsOpen}
          contractId={contractId} name={contractTitle(contract)}
          onClose={() => setQuestionsOpen(false)}
          onEvidence={(citation) => {
            setSelection((previous) => ({
              id: '', editing: false,
              target: { nonce: (previous?.target.nonce ?? 0) + 1, page: citation.page, regions: [], quote: citation.quote },
            }));
            setQuestionsOpen(false);
          }}
        />

      {detailsOpen ? (
        <DetailsDrawer
          contract={contract}
          parentReference={parentReference}
          locked={locked}
          onClose={() => setDetailsOpen(false)}
          onSave={actions.saveDetails}
        />
      ) : null}

      <ConfirmDialog
        open={confirmApprove}
        title="Approve this contract?"
        confirmLabel="Approve"
        onCancel={() => setConfirmApprove(false)}
        onConfirm={() => {
          setConfirmApprove(false);
          actions.approve();
        }}
      >
        <p>
          Approving marks the review complete and locks the findings. {summary.found} of {summary.total} checklist items are found (
          {formatPercent(summary.percent)}). You can reopen the review later.
        </p>
      </ConfirmDialog>
    </div>
  );
}
