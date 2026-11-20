import { Vz_contractsService } from '../generated/services/Vz_contractsService';
import { Vz_contractquestionsService } from '../generated/services/Vz_contractquestionsService';
import { messageOf } from './errors';
import { MOCK_MODE } from './repo';

export interface Citation { page: number; quote: string }
export interface Answer { answer: string; citations: Citation[] }
export interface ChatTurn { role: 'user' | 'assistant'; content: string }
export interface IndexReadiness { ready: boolean; message: string }
const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function readIndexReadiness(contractId: string): Promise<IndexReadiness> {
  if (MOCK_MODE) return { ready: false, message: 'Document Q&A is unavailable in mock mode.' };
  if (!GUID.test(contractId)) throw new Error('The contract id is invalid.');
  const result = await Vz_contractsService.get(contractId, { select: ['vz_indexstatus', 'vz_indexerror'] });
  if (!result.success) throw new Error(`Could not read Q&A indexing status: ${messageOf(result.error)}`);
  const row = result.data;
  const status = 'vz_indexstatus' in row ? row.vz_indexstatus : undefined;
  if (status === 651200002) return { ready: true, message: 'Document indexed for Q&A.' };
  if (status === 651200001) return { ready: false, message: 'Document indexing for Q&A is in progress. Review is available.' };
  if (status === 651200003) {
    const error = 'vz_indexerror' in row && typeof row.vz_indexerror === 'string' ? row.vz_indexerror : '';
    return { ready: false, message: error || 'Document indexing failed. Retry Q&A indexing; review is still available.' };
  }
  return { ready: false, message: 'Document is not indexed for Q&A. Synthetic contracts need ingestion with document indexing enabled.' };
}

export function parseAnswer(text: string): Answer {
  const data: unknown = JSON.parse(text);
  if (typeof data !== 'object' || data === null || !('answer' in data) || typeof data.answer !== 'string' ||
      !('citations' in data) || !Array.isArray(data.citations)) throw new Error('The agent returned an invalid answer.');
  const citations: Citation[] = data.citations.map((value: unknown) => {
    if (typeof value !== 'object' || value === null || !('page' in value) ||
        typeof value.page !== 'number' || !Number.isInteger(value.page) || value.page < 1 ||
        !('quote' in value) || typeof value.quote !== 'string' || !value.quote.trim()) {
      throw new Error('The agent returned an invalid page reference.');
    }
    return { page: value.page, quote: value.quote };
  });
  return { answer: data.answer, citations };
}

export async function submitQuestion(contractId: string, question: string, history: ChatTurn[]): Promise<string> {
  if (MOCK_MODE) throw new Error('Foundry Q&A is available in the deployed app only. Mock mode never fabricates AI answers.');
  if (!GUID.test(contractId)) throw new Error('The contract id is invalid.');
  // Read as the user, not as the flow's administrative connection.
  const source = await Vz_contractsService.get(contractId, {
    select: ['vz_documenttext', 'vz_indexstatus', 'vz_indexversion', 'vz_status'],
  });
  if (!source.success) throw new Error(`Could not read this contract: ${messageOf(source.error)}`);
  if (![651200002, 651200003, 651200004].includes(source.data.vz_status ?? -1)) {
    throw new Error('Wait for this contract to finish extracting before asking questions.');
  }
  if (!('vz_indexstatus' in source.data) || source.data.vz_indexstatus !== 651200002) {
    throw new Error('This document is not ready for Q&A. Wait for document indexing or retry indexing.');
  }
  const context = 'vz_documenttext' in source.data && typeof source.data.vz_documenttext === 'string'
    ? source.data.vz_documenttext : '';
  if (!context || context.length > 1_048_000) throw new Error('Full contract text is unavailable. Re-extract this contract first.');
  const created = await Vz_contractquestionsService.create({
    statecode: 0,
    vz_name: question.slice(0, 200),
    vz_question: question,
    vz_context: context,
    vz_history: JSON.stringify(history.slice(-12)),
    'vz_contract@odata.bind': `/vz_contracts(${contractId})`,
  });
  if (!created.success) throw new Error(`Could not send the question: ${messageOf(created.error)}`);
  return created.data.vz_contractquestionid;
}

export async function readAnswer(id: string, contractId: string): Promise<Answer | null> {
  if (!GUID.test(id) || !GUID.test(contractId)) throw new Error('The question record id is invalid.');
  const result = await Vz_contractquestionsService.get(id, {
    select: ['vz_status', 'vz_answer', 'vz_error', '_vz_contract_value'],
  });
  if (!result.success) throw new Error(`Could not read the answer: ${messageOf(result.error)}`);
  const row = result.data;
  if (row._vz_contract_value?.toLowerCase() !== contractId.toLowerCase()) {
    throw new Error('This answer belongs to a different contract.');
  }
  if (row.vz_status === 651200002) throw new Error(row.vz_error || 'The contract agent could not answer. Try again.');
  if (row.vz_status !== 651200001) return null;
  return parseAnswer(row.vz_answer || '');
}
