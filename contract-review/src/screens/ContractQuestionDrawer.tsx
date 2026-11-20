import { useEffect, useRef, useState } from 'react';
import {
  DrawerBody, DrawerFooter, DrawerHeader, DrawerHeaderTitle, Field, OverlayDrawer, Spinner, Textarea,
} from '@fluentui/react-components';
import { Dismiss24Regular } from '@fluentui/react-icons';
import { readAnswer, submitQuestion } from '../data/contractQuestions';
import type { Answer, ChatTurn, Citation } from '../data/contractQuestions';
import { messageOf } from '../data/errors';
import { Btn } from './Btn';

interface Exchange { question: string; result?: Answer; error?: string }

export function ContractQuestionDrawer({ open, contractId, name, onClose, onEvidence }: {
  open: boolean; contractId: string; name: string; onClose: () => void; onEvidence: (citation: Citation) => void;
}) {
  const [question, setQuestion] = useState('');
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const alive = useRef(true);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcript = useRef<HTMLDivElement>(null);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
  useEffect(() => {
    transcript.current?.scrollTo({ top: transcript.current.scrollHeight });
  }, [exchanges, busy]);

  async function send(): Promise<void> {
    const text = question.trim();
    if (busy || !text || text.length > 4000) return;
    setBusy(true);
    setNotice('');
    const history: ChatTurn[] = exchanges.flatMap((entry) => entry.result ? [
      { role: 'user' as const, content: entry.question },
      { role: 'assistant' as const, content: entry.result.answer },
    ] : []).slice(-12);
    setExchanges((previous) => [...previous, { question: text }]);
    setQuestion('');
    const finish = (update: Partial<Exchange>) => {
      if (!alive.current) return;
      setExchanges((previous) => previous.map((entry, index) =>
        index === previous.length - 1 ? { ...entry, ...update } : entry));
      setBusy(false);
    };
    try {
      const id = await submitQuestion(contractId, text, history);
      const deadline = Date.now() + 16 * 60_000;
      async function poll(): Promise<void> {
        if (!alive.current) return;
        try {
          const result = await readAnswer(id, contractId);
          if (result) finish({ result });
          else if (Date.now() >= deadline) finish({ error: 'The question is taking too long. Close and reopen Ask this contract to try again.' });
          else timer.current = setTimeout(() => { void poll(); }, 3000);
        } catch (error) { finish({ error: messageOf(error) }); }
      }
      await poll();
    } catch (error) {
      finish({ error: messageOf(error) });
      if (alive.current) setNotice('The question was not answered. You can send it again.');
    }
  }

  return (
    <OverlayDrawer open={open} position="end" size="medium" onOpenChange={(_event, data) => { if (!data.open) onClose(); }}>
      <DrawerHeader>
        <DrawerHeaderTitle action={
          <button type="button" className="app-tool" aria-label="Close contract questions" onClick={onClose}>
            <Dismiss24Regular />
          </button>
        }>Ask this contract</DrawerHeaderTitle>
        <strong>{name}</strong>
        <p className="muted">Microsoft Foundry searches this contract only. No parent agreements or other records.
          Answers do not change the review and are not legal advice.</p>
      </DrawerHeader>
      <DrawerBody ref={transcript}>
        <div className="contract-chat" role="log" aria-label="Contract conversation" aria-live="polite">
          {exchanges.length === 0 ? <p>Ask about a term, a restriction, or an obligation.
            For example: What must happen to the data when this contract ends?</p> : null}
          {exchanges.map((entry, index) => (
            <article className="contract-chat__exchange" key={index}>
              <h3 className="contract-chat__question">{entry.question}</h3>
              {entry.error ? <p role="alert">{entry.error}</p> : null}
              {entry.result ? <>
                <p className="contract-chat__answer">{entry.result.answer}</p>
                {entry.result.citations.map((citation, citationIndex) => (
                  <div className="contract-chat__citation" key={citationIndex}>
                    <blockquote>{citation.quote}</blockquote>
                    <Btn small variant="outline" onClick={() => onEvidence(citation)}>View page {citation.page}</Btn>
                  </div>
                ))}
              </> : null}
            </article>
          ))}
          {busy ? <Spinner size="small" label="Searching this contract in Foundry..." /> : null}
          {notice ? <p role="status">{notice}</p> : null}
        </div>
      </DrawerBody>
      <DrawerFooter className="contract-chat__footer">
        <form onSubmit={(event) => { event.preventDefault(); void send(); }}>
          <Field label="Question about this contract">
            <Textarea value={question} maxLength={4000} rows={3} resize="vertical" disabled={busy}
              onChange={(_event, data) => setQuestion(data.value)} />
          </Field>
          <div className="contract-chat__actions">
            <span className="muted">Conversation resets when you leave this contract.</span>
            <Btn variant="cta" type="submit" disabled={busy || !question.trim()}>Ask</Btn>
          </div>
        </form>
      </DrawerFooter>
    </OverlayDrawer>
  );
}
