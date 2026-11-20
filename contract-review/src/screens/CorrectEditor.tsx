import { useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Field, Input, Select, Textarea } from '@fluentui/react-components';
import type { Judgment } from '../data/choices';
import type { ReviewRow } from '../data/types';
import { EDITABLE_JUDGMENTS } from '../domain/completeness';
import type { Correction } from '../hooks/useReview';
import { Btn } from './Btn';

/** Reviewer memo columns hold 10,000 characters; stay well inside. */
const MAX_TEXT = 9000;

interface CorrectEditorProps {
  row: ReviewRow;
  onSave: (correction: Correction) => void;
  onCancel: () => void;
}

function toJudgment(value: string): Judgment {
  return EDITABLE_JUDGMENTS.find((judgment) => judgment === value) ?? 'Not Addressed';
}

/** Starts from the reviewer's last answer when there is one, otherwise from what the AI found. */
function initialValue({ finding }: ReviewRow): string {
  return finding.reviewStatus === 'Corrected' ? finding.reviewerValue : finding.aiValue;
}

function initialJudgment({ finding }: ReviewRow): Judgment {
  const start = finding.reviewStatus === 'Corrected' ? finding.reviewerJudgment : finding.aiJudgment;
  return start === null ? 'Not Addressed' : toJudgment(start);
}

export function CorrectEditor({ row, onSave, onCancel }: CorrectEditorProps) {
  const { finding, item } = row;
  const [value, setValue] = useState(() => initialValue(row));
  const [judgment, setJudgment] = useState<Judgment>(() => initialJudgment(row));
  const [notes, setNotes] = useState(finding.reviewerNotes);

  function submit(event: FormEvent): void {
    event.preventDefault();
    onSave({ value: value.trim(), judgment: item.hasJudgment ? judgment : null, notes: notes.trim() });
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onCancel();
    }
  }

  return (
    <form className="correct" onSubmit={submit} onKeyDown={onKeyDown} aria-label={`Correct ${item.label}`}>
      {item.hasJudgment ? (
        <>
          <Field label="What the contract says about this right">
            <Select autoFocus value={judgment} onChange={(_event, data) => setJudgment(toJudgment(data.value))}>
              {EDITABLE_JUDGMENTS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Conditions" hint="The limits the contract puts on it. Leave empty if there are none.">
            <Textarea
              resize="vertical"
              rows={3}
              maxLength={MAX_TEXT}
              value={value}
              onChange={(_event, data) => setValue(data.value)}
            />
          </Field>
        </>
      ) : (
        <Field label="Correct value" hint="Leave empty if the contract does not state this.">
          <Input autoFocus maxLength={MAX_TEXT} value={value} onChange={(_event, data) => setValue(data.value)} />
        </Field>
      )}
      <Field label="Notes (optional)">
        <Textarea resize="vertical" rows={2} maxLength={MAX_TEXT} value={notes} onChange={(_event, data) => setNotes(data.value)} />
      </Field>
      <div className="correct__actions">
        <Btn type="submit" small>
          Save correction
        </Btn>
        <Btn small variant="outline" onClick={onCancel}>
          Cancel
        </Btn>
      </div>
    </form>
  );
}
