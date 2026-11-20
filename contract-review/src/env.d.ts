// Importing the pdf.js worker bundle registers globalThis.pdfjsWorker, which makes pdf.js run its
// worker code on the main thread. Code Apps block Worker creation (CSP worker-src 'none').
declare module 'pdfjs-dist/build/pdf.worker.min.mjs';
