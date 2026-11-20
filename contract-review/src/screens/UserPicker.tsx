import { useEffect, useState } from 'react';
import { Combobox, Field, Option } from '@fluentui/react-components';
import { getRepo } from '../data/repo';
import type { UserRef } from '../data/types';

const SEARCH_DELAY_MS = 250;

interface UserPickerProps {
  label: string;
  hint: string;
  /** The person already assigned. Shown until someone else is picked. */
  current: UserRef | null;
  disabled?: boolean;
  onPick: (userId: string) => void;
}

/** Searches the people who can sign in, as the user types. */
export function UserPicker({ label, hint, current, disabled = false, onPick }: UserPickerProps) {
  const [text, setText] = useState(current?.name ?? '');
  const [query, setQuery] = useState('');
  const [found, setFound] = useState<UserRef[]>([]);
  const [failed, setFailed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(current?.id ?? null);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(
      () => {
        getRepo()
          .then((repo) => repo.searchUsers(query))
          .then((users) => {
            if (cancelled) return;
            setFound(users);
            setFailed(false);
          })
          .catch(() => {
            if (!cancelled) setFailed(true);
          });
      },
      query === '' ? 0 : SEARCH_DELAY_MS,
    );
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const options = current !== null && !found.some((user) => user.id === current.id) ? [current, ...found] : found;

  return (
    <Field label={label} hint={hint} validationState={failed ? 'error' : 'none'} validationMessage={failed ? 'Could not search people.' : undefined}>
      <Combobox
        freeform
        disabled={disabled}
        placeholder="Search by name or email"
        value={text}
        selectedOptions={selectedId ? [selectedId] : []}
        onChange={(event) => {
          setText(event.target.value);
          setQuery(event.target.value.trim());
        }}
        onOptionSelect={(_event, data) => {
          if (!data.optionValue) return;
          setSelectedId(data.optionValue);
          setText(data.optionText ?? '');
          onPick(data.optionValue);
        }}
      >
        {options.map((user) => (
          <Option key={user.id} value={user.id} text={user.name}>
            <span className="user-option">
              <span>{user.name}</span>
              <span className="user-option__email">{user.email}</span>
            </span>
          </Option>
        ))}
      </Combobox>
    </Field>
  );
}
