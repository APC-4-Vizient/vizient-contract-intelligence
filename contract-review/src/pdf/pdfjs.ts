import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist';
import type { TextRun } from './types';

type Pdfjs = typeof import('pdfjs-dist');

let loading: Promise<Pdfjs> | null = null;

async function load(): Promise<Pdfjs> {
  // Importing the worker bundle registers globalThis.pdfjsWorker, which makes pdf.js run its worker code on the
  // main thread. Code Apps do not allow Web Workers or fetches, so the usual separate worker file cannot be used.
  await import('pdfjs-dist/build/pdf.worker.min.mjs');
  return import('pdfjs-dist');
}

/** Loads pdf.js on first use so the contracts list does not pay for it. */
export function loadPdfjs(): Promise<Pdfjs> {
  loading ??= load().catch((error: unknown) => {
    loading = null;
    throw error;
  });
  return loading;
}

export async function openPdf(data: Uint8Array): Promise<PDFDocumentProxy> {
  const pdfjs = await loadPdfjs();
  // pdf.js takes ownership of the bytes it is given, so it gets a copy. WASM decoders are fetched, which Code Apps block.
  return pdfjs.getDocument({ data: data.slice(), useWasm: false }).promise;
}

export interface PageSize {
  /** Points at scale 1. */
  width: number;
  height: number;
}

export function readPageSizes(doc: PDFDocumentProxy): Promise<PageSize[]> {
  return Promise.all(
    Array.from({ length: doc.numPages }, async (_, index) => {
      const page = await doc.getPage(index + 1);
      const { width, height } = page.getViewport({ scale: 1 });
      page.cleanup();
      return { width, height };
    }),
  );
}

/** The page's text as runs placed in points at scale 1, top-left origin. */
export async function pageTextRuns(page: PDFPageProxy): Promise<TextRun[]> {
  const viewport = page.getViewport({ scale: 1 });
  const content = await page.getTextContent();
  const runs: TextRun[] = [];
  for (const item of content.items) {
    if (!('str' in item) || item.str.trim() === '') continue;
    const [x, y] = viewport.convertToViewportPoint(item.transform[4], item.transform[5]);
    runs.push({ text: item.str, left: x, top: y - item.height, width: item.width, height: item.height });
  }
  return runs;
}
