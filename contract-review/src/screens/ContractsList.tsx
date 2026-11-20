import { useState } from 'react';
import {
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  MessageBarTitle,
  Spinner,
  Tab,
  TabList,
  Table,
  TableBody,
  TableCell,
  TableCellLayout,
  TableHeader,
  TableHeaderCell,
  TableRow,
  Tooltip,
} from '@fluentui/react-components';
import { ArrowSync20Regular } from '@fluentui/react-icons';
import type { Contract } from '../data/types';
import { CONTRACTS_REFRESH_MS, useContracts } from '../hooks/useContracts';
import { LOW_COMPLETENESS_BELOW, contractTitle, isContractTab, matchesTab, tabCounts } from '../domain/contracts';
import type { ContractTab } from '../domain/contracts';
import { formatClock, formatDateTime, formatPercent } from '../domain/format';
import { openContract } from '../hooks/useRoute';
import { Btn } from './Btn';
import { Chip } from './Chips';

const DASH = '\u2014';

function StatusCell({ contract }: { contract: Contract }) {
  const { status } = contract;
  if (!status) return <span className="muted">{DASH}</span>;
  return (
    <div className="contracts__status">
      <div className="contracts__status-line">
        <Chip label={status} />
        {status === 'Extracting' ? <Spinner size="tiny" aria-label="Extraction in progress" /> : null}
        {contract.hasParentReference && !contract.parentContractId ? (
          <span className="vz-chip vz-chip--warning" title="This contract refers to a parent agreement that is not linked yet.">
            Parent not linked
          </span>
        ) : null}
      </div>
      {status === 'Failed' && contract.errorMessage ? (
        <span className="contracts__error" title={contract.errorMessage}>
          {contract.errorMessage}
        </span>
      ) : null}
    </div>
  );
}

function CompletenessCell({ contract }: { contract: Contract }) {
  const total = contract.totalCount ?? 0;
  if (total === 0 || contract.completeness === null) return <span className="muted">{DASH}</span>;
  const percent = Math.max(0, Math.min(100, contract.completeness));
  return (
    <div className="contracts__completeness">
      <div
        className="vz-progress"
        role="progressbar"
        aria-label="Completeness"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <span className="contracts__fraction">
        {contract.foundCount ?? 0} of {total} {'\u00B7'} {formatPercent(contract.completeness)}
      </span>
    </div>
  );
}

function openLabel(contract: Contract): string {
  switch (contract.status) {
    case 'Ready for Review':
    case 'In Review':
      return 'Review';
    case 'Approved':
      return 'View';
    default:
      return 'Open';
  }
}

function ContractRow({ contract }: { contract: Contract }) {
  const href = `#/contract/${contract.id}`;
  const detail = [contract.identifier, contract.vendor.trim() ? contract.name : ''].filter((part) => part !== '').join(' \u00B7 ');
  return (
    <TableRow
      className="contracts__row"
      onClick={(event) => {
        if (!(event.target instanceof Element && event.target.closest('a'))) openContract(contract.id);
      }}
    >
      <TableCell>
        <TableCellLayout description={detail}>
          <a className="vz-link contracts__title" href={href}>
            {contractTitle(contract)}
          </a>
        </TableCellLayout>
      </TableCell>
      <TableCell>{contract.documentType ?? DASH}</TableCell>
      <TableCell>
        <StatusCell contract={contract} />
      </TableCell>
      <TableCell>
        <CompletenessCell contract={contract} />
      </TableCell>
      <TableCell>{formatDateTime(contract.processedOn)}</TableCell>
      <TableCell>
        <a className="vz-btn vz-btn--sm vz-btn--outline" href={href}>
          {openLabel(contract)}
        </a>
      </TableCell>
    </TableRow>
  );
}

export function ContractsList() {
  const { contracts, error, updatedAt, loading, refresh } = useContracts();
  const [tab, setTab] = useState<ContractTab>('all');

  const counts = tabCounts(contracts ?? []);
  const shown = (contracts ?? []).filter((contract) => matchesTab(contract, tab));

  return (
    <div className="contracts">
      <div className="contracts__head">
        <h1 className="vz-h1">Contracts</h1>
        <div className="contracts__refresh">
          <span className="muted" role="status">
            {updatedAt ? `Updated ${formatClock(updatedAt)} \u00B7 auto-refresh ${CONTRACTS_REFRESH_MS / 1000} s` : ''}
          </span>
          <Btn variant="outline" small icon={<ArrowSync20Regular />} onClick={refresh}>
            Refresh
          </Btn>
        </div>
      </div>

      {error ? (
        <MessageBar intent={contracts ? 'warning' : 'error'}>
          <MessageBarBody>
            <MessageBarTitle>{contracts ? 'Could not refresh the list' : 'Could not load contracts'}</MessageBarTitle>
            {error}
            {contracts ? ' Showing the last result.' : ''}
          </MessageBarBody>
          <MessageBarActions>
            <Btn small variant="outline" onClick={refresh}>
              Try again
            </Btn>
          </MessageBarActions>
        </MessageBar>
      ) : null}

      {loading ? (
        <div className="screen-state">
          <Spinner label={'Loading contracts\u2026'} />
        </div>
      ) : null}

      {contracts ? (
        <>
          <TabList
            className="contracts__tabs"
            selectedValue={tab}
            onTabSelect={(_event, data) => {
              if (isContractTab(data.value)) setTab(data.value);
            }}
          >
            <Tab value="all">All ({counts.all})</Tab>
            <Tooltip content="Includes contracts a reviewer has already started." relationship="description">
              <Tab value="ready">Ready for Review ({counts.ready})</Tab>
            </Tooltip>
            <Tooltip content={`Fewer than ${LOW_COMPLETENESS_BELOW}% of the checklist found.`} relationship="description">
              <Tab value="low">Low completeness ({counts.low})</Tab>
            </Tooltip>
          </TabList>

          {contracts.length === 0 ? (
            <p className="contracts__empty">No contracts yet. New contracts appear here as soon as they are uploaded.</p>
          ) : shown.length === 0 ? (
            <p className="contracts__empty">No contracts match this view.</p>
          ) : (
            <Table className="contracts__table" aria-label="Contracts">
              <TableHeader>
                <TableRow>
                  <TableHeaderCell>Contract</TableHeaderCell>
                  <TableHeaderCell>Type</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                  <TableHeaderCell>Completeness</TableHeaderCell>
                  <TableHeaderCell>Processed</TableHeaderCell>
                  <TableHeaderCell>
                    <span className="sr-only">Open</span>
                  </TableHeaderCell>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((contract) => (
                  <ContractRow key={contract.id} contract={contract} />
                ))}
              </TableBody>
            </Table>
          )}
        </>
      ) : null}
    </div>
  );
}
