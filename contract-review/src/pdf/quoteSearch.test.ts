import { describe, expect, it } from 'vitest';
import { locateQuote } from './quoteSearch';
import type { TextRun } from './types';

function run(text: string, left: number, top: number, width: number, height = 10): TextRun {
  return { text, left, top, width, height };
}

describe('locateQuote', () => {
  it('finds a quote that spans several runs on one line and returns one box', () => {
    const runs = [
      run('The Vendor shall ', 72, 100, 85),
      run('destroy all Customer Data ', 157, 100, 130),
      run('within 30 days.', 287, 100, 75),
    ];
    expect(locateQuote(runs, 'destroy all customer data within 30 days')).toEqual([{ left: 157, top: 100, width: 200, height: 10 }]);
  });

  it('ignores case, curly quotes, dashes and non-breaking spaces', () => {
    const runs = [run('Customer\u2019s Data \u2014 retained for\u00A0seven\u00A0years', 10, 20, 400)];
    expect(locateQuote(runs, "customer's data - retained for seven years")).toEqual([{ left: 10, top: 20, width: 400, height: 10 }]);
  });

  it('keeps separate boxes for text on different lines', () => {
    const runs = [run('The Vendor shall destroy all', 72, 100, 200), run('Customer Data within thirty days.', 72, 114, 230)];
    const found = locateQuote(runs, 'shall destroy all Customer Data within thirty days');
    expect(found?.map((rect) => rect.top)).toEqual([100, 114]);
  });

  it('falls back to a shorter start of the quote when its end drifts from the page', () => {
    const runs = [run('Vendor shall securely destroy all Customer Data within thirty (30) days of termination.', 72, 200, 600)];
    const quote = 'Vendor shall securely destroy all Customer Data within thirty (30) calendar days after termination of the Agreement.';
    const found = locateQuote(runs, quote);
    expect(found).toHaveLength(1);
    expect(found?.[0].left).toBe(72);
    expect(found?.[0].width).toBeGreaterThan(0);
    expect(found?.[0].width).toBeLessThan(600);
  });

  it('returns null when the text is not on the page or the quote is too short to trust', () => {
    const runs = [run('Payment is due within forty-five days.', 72, 100, 300)];
    expect(locateQuote(runs, 'The Vendor may use Customer Data for analytics.')).toBeNull();
    expect(locateQuote(runs, 'Payment is')).toBeNull();
    expect(locateQuote(runs, '   ')).toBeNull();
  });
});
