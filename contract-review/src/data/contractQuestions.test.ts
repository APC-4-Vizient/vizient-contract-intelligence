import { beforeEach, describe, expect, it, vi } from 'vitest';
const services = vi.hoisted(() => ({ get: vi.fn(), create: vi.fn() }));
vi.mock('../generated/services/Vz_contractsService', () => ({ Vz_contractsService: { get: services.get } }));
vi.mock('../generated/services/Vz_contractquestionsService', () => ({ Vz_contractquestionsService: { create: services.create } }));
vi.mock('./repo', () => ({ MOCK_MODE: false }));
import { parseAnswer, readIndexReadiness, submitQuestion } from './contractQuestions';

const id = '63abf974-20ea-472f-981a-8d42e67861cc';
beforeEach(() => { vi.clearAllMocks(); });

describe('contract answers', () => {
  it('preserves verbatim evidence and page numbers without interpreting markup', () => {
    const answer = { answer: '<script>not executed</script>', citations: [{ page: 2, quote: 'A verbatim clause.' }] };
    expect(parseAnswer(JSON.stringify(answer))).toEqual(answer);
  });

  describe('document indexing readiness', () => {
    it.each([undefined, 651200000, 651200001, 651200003])('blocks questions while not indexed: %s', async (status) => {
      services.get.mockResolvedValue({ success: true, data: { vz_indexstatus: status, vz_status: 651200002 } });
      expect((await readIndexReadiness(id)).ready).toBe(false);
      await expect(submitQuestion(id, 'How many years?', [])).rejects.toThrow('not ready');
      expect(services.create).not.toHaveBeenCalled();
    });
    it('shows the indexing failure independently of review', async () => {
      services.get.mockResolvedValue({ success: true, data: { vz_indexstatus: 651200003, vz_indexerror: 'Index unavailable.' } });
      expect(await readIndexReadiness(id)).toEqual({ ready: false, message: 'Index unavailable.' });
    });
    it('sends full document text rather than the reduced debugging result', async () => {
      services.get.mockResolvedValue({ success: true, data: {
        vz_status: 651200002, vz_indexstatus: 651200002,
        vz_documenttext: 'Full page-grounded synthetic text', vz_rawresult: 'Reduced checklist debug output',
      } });
      services.create.mockResolvedValue({ success: true, data: { vz_contractquestionid: id } });
      expect((await readIndexReadiness(id)).ready).toBe(true);
      await submitQuestion(id, 'How many years?', []);
      expect(services.create.mock.calls[0][0].vz_context).toBe('Full page-grounded synthetic text');
    });
    it('surfaces permission or connection errors rather than claiming indexing is pending', async () => {
      services.get.mockResolvedValue({ success: false, error: new Error('Access denied') });
      await expect(readIndexReadiness(id)).rejects.toThrow('Could not read Q&A indexing status');
    });
  });
  it('accepts a not-addressed answer without inventing a citation', () => {
    expect(parseAnswer('{"answer":"Not addressed.","citations":[]}').citations).toEqual([]);
  });
  it.each([0, -1, 1.5, '2', null])('rejects an invalid source page: %s', (page) => {
    expect(() => parseAnswer(JSON.stringify({ answer: 'A term.', citations: [{ page, quote: 'Clause' }] }))).toThrow();
  });
});
