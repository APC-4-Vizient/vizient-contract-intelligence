import { useState } from 'react';
import type { ReactNode } from 'react';
import {
  DrawerBody,
  DrawerFooter,
  DrawerHeader,
  DrawerHeaderTitle,
  Field,
  MessageBar,
  MessageBarBody,
  OverlayDrawer,
  Select,
  Spinner,
} from '@fluentui/react-components';
import { Dismiss24Regular } from '@fluentui/react-icons';
import { getRepo } from '../data/repo';
import type { Contract, ContractPatch, UserRef } from '../data/types';
import { contractTitle } from '../domain/contracts';
import { safeHttpUrl } from '../domain/display';
import { formatDateOnly, formatDateTime } from '../domain/format';
import { suggestParent } from '../domain/parents';
import { useResource } from '../hooks/useResource';
import { Btn } from './Btn';
import { Chip } from './Chips';
import { UserPicker } from './UserPicker';

interface Lookups {
  contracts: Contract[];
  owner: UserRef | null;
  legalReviewer: UserRef | null;
}

async function loadLookups(contractId: string): Promise<Lookups> {
  const repo = await getRepo();
  const [contracts, current] = await Promise.all([repo.listContracts(), repo.getContract(contractId)]);
  const ids = [current.ownerId, current.legalReviewerId].filter((id): id is string => id !== null);
  const users = ids.length > 0 ? await repo.getUsers(ids) : [];
  const byId = new Map(users.map((user) => [user.id, user]));
  return {
    contracts,
    owner: current.ownerId ? (byId.get(current.ownerId) ?? null) : null,
    legalReviewer: current.legalReviewerId ? (byId.get(current.legalReviewerId) ?? null) : null,
  };
}

function Info({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

function parentOptionLabel(candidate: Contract): string {
  const parts = [contractTitle(candidate), candidate.documentType, candidate.identifier].filter(
    (part): part is string => typeof part === 'string' && part !== '',
  );
  return parts.join(' \u00B7 ');
}

interface DetailsFormProps {
  contract: Contract;
  lookups: Lookups;
  parentReference: string;
  locked: boolean;
  onClose: () => void;
  onSave: (patch: ContractPatch) => void;
}

function DetailsForm({ contract, lookups, parentReference, locked, onClose, onSave }: DetailsFormProps) {
  const [parentId, setParentId] = useState(contract.parentContractId ?? '');
  const [ownerId, setOwnerId] = useState<string | null>(null);
  const [legalId, setLegalId] = useState<string | null>(null);

  const candidates = lookups.contracts
    .filter((candidate) => candidate.id !== contract.id)
    .sort((a, b) => {
      const sameA = a.vendor !== '' && a.vendor === contract.vendor ? 0 : 1;
      const sameB = b.vendor !== '' && b.vendor === contract.vendor ? 0 : 1;
      return sameA - sameB || contractTitle(a).localeCompare(contractTitle(b));
    });

  const patch: ContractPatch = {};
  if (parentId !== '' && parentId !== (contract.parentContractId ?? '')) patch.parentContractId = parentId;
  if (ownerId !== null && ownerId !== contract.ownerId) patch.ownerId = ownerId;
  if (legalId !== null && legalId !== contract.legalReviewerId) patch.legalReviewerId = legalId;
  const changed = Object.keys(patch).length > 0;
  const link = safeHttpUrl(contract.sharePointUrl);
  const parent = lookups.contracts.find((candidate) => candidate.id === contract.parentContractId) ?? null;
  const linkedDocuments = lookups.contracts.filter((candidate) => candidate.parentContractId === contract.id);
  const suggestion = suggestParent(parentReference, contract, lookups.contracts);

  return (
    <>
      <DrawerBody>
        <dl className="details__list">
          <Info label="Status">{contract.status ? <Chip label={contract.status} /> : '\u2014'}</Info>
          <Info label="Document type">{contract.documentType ?? '\u2014'}</Info>
          <Info label="Contract number">{contract.identifier || '\u2014'}</Info>
          <Info label="Contracting entity">{contract.vizientEntity || '\u2014'}</Info>
          <Info label="Effective">{formatDateOnly(contract.effectiveDate)}</Info>
          <Info label="Expires">{formatDateOnly(contract.expirationDate)}</Info>
          <Info label="Processed">{formatDateTime(contract.processedOn)}</Info>
          <Info label="Source file">
            {link ? (
              <a className="vz-link" href={link} target="_blank" rel="noreferrer">
                Open in SharePoint
              </a>
            ) : (
              contract.sharePointUrl || '\u2014'
            )}
          </Info>
          <Info label="Linked documents">
            {linkedDocuments.length > 0 ? (
              <ul className="details__links">
                {linkedDocuments.map((document) => (
                  <li key={document.id}>
                    <a className="vz-link" href={`#/contract/${document.id}`}>
                      {parentOptionLabel(document)}
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              '\u2014'
            )}
          </Info>
        </dl>

        {contract.errorMessage ? (
          <MessageBar intent="error">
            <MessageBarBody>{contract.errorMessage}</MessageBarBody>
          </MessageBar>
        ) : null}

        <div className="details__form">
          <Field
            label="Parent contract"
            hint={
              contract.parentContractId ? (
                <>
                  The agreement this one amends or extends.
                  {parent ? (
                    <>
                      {' '}
                      <a className="vz-link" href={`#/contract/${parent.id}`}>
                        Open it
                      </a>
                    </>
                  ) : null}
                </>
              ) : (
                'Link this to the agreement it amends or extends. A link cannot be removed here yet.'
              )
            }
          >
            <Select disabled={locked} value={parentId} onChange={(_event, data) => setParentId(data.value)}>
              {contract.parentContractId ? null : <option value="">Not linked</option>}
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {parentOptionLabel(candidate)}
                </option>
              ))}
            </Select>
          </Field>
          {contract.hasParentReference && parentReference.trim() ? (
            <p className="details__reference">
              <span className="vz-eyebrow">The contract says</span>
              {parentReference}
            </p>
          ) : null}
          {suggestion ? (
            <div className="details__suggest" role="group" aria-label="Suggested parent contract">
              <span className="vz-eyebrow">Suggested parent</span>
              <strong>{parentOptionLabel(suggestion.contract)}</strong>
              <span className="muted">Carries &ldquo;{suggestion.match}&rdquo;, the number this contract cites.</span>
              <Btn small disabled={locked} onClick={() => onSave({ ...patch, parentContractId: suggestion.contract.id })}>
                Link to this contract
              </Btn>
            </div>
          ) : null}

          <UserPicker
            label="Contract owner"
            hint="Pick a person to change it. Clearing the owner is not supported yet."
            current={lookups.owner}
            disabled={locked}
            onPick={setOwnerId}
          />
          <UserPicker
            label="Legal reviewer"
            hint="Pick a person to change it. Clearing the reviewer is not supported yet."
            current={lookups.legalReviewer}
            disabled={locked}
            onPick={setLegalId}
          />
        </div>
      </DrawerBody>
      <DrawerFooter>
        <Btn disabled={!changed || locked} onClick={() => onSave(patch)}>
          Save changes
        </Btn>
        <Btn variant="outline" onClick={onClose}>
          Cancel
        </Btn>
      </DrawerFooter>
    </>
  );
}

interface DetailsDrawerProps {
  contract: Contract;
  /** What the contract says about its parent agreement, as the reviewer left it. Empty when there is none. */
  parentReference: string;
  locked: boolean;
  onClose: () => void;
  onSave: (patch: ContractPatch) => void;
}

/** Mounted only while open, so every opening starts from the saved contract. */
export function DetailsDrawer({ contract, parentReference, locked, onClose, onSave }: DetailsDrawerProps) {
  const lookups = useResource(contract.id, loadLookups);

  return (
    <OverlayDrawer
      open
      position="end"
      size="medium"
      onOpenChange={(_event, data) => {
        if (!data.open) onClose();
      }}
    >
      <DrawerHeader>
        <DrawerHeaderTitle
          action={
            <button type="button" className="app-tool" aria-label="Close details" onClick={onClose}>
              <Dismiss24Regular />
            </button>
          }
        >
          Contract details
        </DrawerHeaderTitle>
      </DrawerHeader>
      {lookups.data ? (
        <DetailsForm
          contract={contract}
          lookups={lookups.data}
          parentReference={parentReference}
          locked={locked}
          onClose={onClose}
          onSave={(patch) => {
            onSave(patch);
            onClose();
          }}
        />
      ) : (
        <DrawerBody>
          {lookups.error ? (
            <MessageBar intent="error">
              <MessageBarBody>Could not load the details: {lookups.error}</MessageBarBody>
            </MessageBar>
          ) : (
            <Spinner label={'Loading details\u2026'} />
          )}
        </DrawerBody>
      )}
    </OverlayDrawer>
  );
}
