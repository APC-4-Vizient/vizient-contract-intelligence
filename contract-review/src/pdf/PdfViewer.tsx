import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Spinner } from '@fluentui/react-components';
import {
  ArrowMaximize20Regular,
  ChevronDown20Regular,
  ChevronUp20Regular,
  ZoomIn20Regular,
  ZoomOut20Regular,
} from '@fluentui/react-icons';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { messageOf } from '../data/errors';
import type { Rect } from '../domain/geometry';
import { PdfPage } from './PdfPage';
import { EVIDENCE_STYLES, loadEvidenceStyle, saveEvidenceStyle } from './evidenceStyle';
import type { EvidenceStyle } from './evidenceStyle';
import { resolveHighlight } from './highlight';
import { openPdf, pageTextRuns, readPageSizes } from './pdfjs';
import type { PageSize } from './pdfjs';
import { locateQuote } from './quoteSearch';
import type { HighlightTarget, LocateMethod, TextMatch } from './types';

const ZOOM_STEP = 0.25;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.5;
const NO_RECTS: readonly Rect[] = [];

interface Opened {
  source: Uint8Array;
  doc: PDFDocumentProxy | null;
  sizes: PageSize[];
  error: string | null;
}

interface PdfViewerProps {
  data: Uint8Array;
  target: HighlightTarget | null;
}

function locateLabel(method: LocateMethod, searching: boolean, page: number | null): string {
  if (searching) return 'Locating by text\u2026';
  switch (method) {
    case 'regions':
      return `Located by AI region \u00B7 p. ${page}`;
    case 'text':
      return `Located by text match \u00B7 p. ${page}`;
    case 'page':
      return `Page only \u00B7 p. ${page}`;
    default:
      return '';
  }
}

export function PdfViewer({ data, target }: PdfViewerProps) {
  const [opened, setOpened] = useState<Opened | null>(null);
  const [scroller, setScroller] = useState<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [match, setMatch] = useState<TextMatch | null>(null);
  const [evidenceStyle, setEvidenceStyle] = useState<EvidenceStyle>(loadEvidenceStyle);
  const frameRequest = useRef<number | null>(null);
  const scrolledFor = useRef('');

  useEffect(() => {
    let cancelled = false;
    let holding: PDFDocumentProxy | null = null;
    openPdf(data)
      .then(async (pdf) => {
        if (cancelled) {
          void pdf.loadingTask.destroy();
          return;
        }
        holding = pdf;
        const sizes = await readPageSizes(pdf);
        if (!cancelled) setOpened({ source: data, doc: pdf, sizes, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setOpened({ source: data, doc: null, sizes: [], error: messageOf(error) });
      });
    return () => {
      cancelled = true;
      if (holding) void holding.loadingTask.destroy();
    };
  }, [data]);

  useEffect(() => {
    if (!scroller) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(scroller);
    return () => observer.disconnect();
  }, [scroller]);

  useEffect(
    () => () => {
      if (frameRequest.current !== null) cancelAnimationFrame(frameRequest.current);
    },
    [],
  );

  const slot = opened !== null && opened.source === data ? opened : null;
  const doc = slot?.doc ?? null;
  const sizes = slot?.sizes ?? [];
  const error = slot?.error ?? null;
  const widest = sizes.reduce((max, size) => Math.max(max, size.width), 0);
  const scale = widest > 0 && width > 0 ? (width / widest) * zoom : 0;
  const ready = doc !== null && scale > 0;

  const searchNonce =
    target !== null && target.regions.length === 0 && target.page !== null && target.quote.trim() !== '' ? target.nonce : null;
  const searching = searchNonce !== null && match?.nonce !== searchNonce;
  const resolved = useMemo(() => resolveHighlight(target, match), [target, match]);

  // With no AI region, look the clause quote up in the page's own text.
  useEffect(() => {
    if (!doc || !target || searchNonce === null || target.page === null) return;
    const { nonce, page, quote } = target;
    let cancelled = false;
    doc
      .getPage(page)
      .then(pageTextRuns)
      .then((runs) => locateQuote(runs, quote) ?? [])
      .catch((): Rect[] => [])
      .then((rects) => {
        if (!cancelled) setMatch({ nonce, page, rects });
      });
    return () => {
      cancelled = true;
    };
  }, [doc, target, searchNonce]);

  useEffect(() => {
    if (!ready || !scroller || !target || resolved.anchorPage === null || searching) return;
    const key = `${target.nonce}:${resolved.method}`;
    if (scrolledFor.current === key) return;
    scrolledFor.current = key;
    const frame = scroller.querySelector<HTMLElement>(`[data-page="${resolved.anchorPage}"]`);
    if (!frame) return;
    const frameTop = frame.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop;
    const anchor = resolved.anchorRect ? resolved.anchorRect.top * scale : 0;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller.scrollTo({
      top: Math.max(0, frameTop + anchor - scroller.clientHeight / 3),
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }, [ready, scroller, target, resolved, searching, scale]);

  const updateCurrentPage = useCallback(() => {
    if (!scroller) return;
    const line = scroller.getBoundingClientRect().top + scroller.clientHeight / 3;
    let best = 1;
    for (const frame of scroller.querySelectorAll<HTMLElement>('[data-page]')) {
      if (frame.getBoundingClientRect().top > line) break;
      best = Number(frame.dataset.page);
    }
    setCurrentPage(best);
  }, [scroller]);

  const onScroll = useCallback(() => {
    if (frameRequest.current !== null) return;
    frameRequest.current = requestAnimationFrame(() => {
      frameRequest.current = null;
      updateCurrentPage();
    });
  }, [updateCurrentPage]);

  function goToPage(pageNumber: number): void {
    const frame = scroller?.querySelector<HTMLElement>(`[data-page="${pageNumber}"]`);
    if (!scroller || !frame) return;
    const top = frame.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 8;
    scroller.scrollTo({ top, behavior: 'smooth' });
  }

  function chooseEvidenceStyle(style: EvidenceStyle): void {
    setEvidenceStyle(style);
    saveEvidenceStyle(style);
  }

  const pageCount = sizes.length;
  const label = locateLabel(resolved.method, searching, resolved.anchorPage);
  const highlightKey = target?.nonce ?? 0;

  return (
    <div className="pdf-viewer">
      <div className="pdf-toolbar" role="toolbar" aria-label="Document controls">
        <div className="pdf-toolbar__group">
          <button
            type="button"
            className="app-tool"
            aria-label="Previous page"
            disabled={!ready || currentPage <= 1}
            onClick={() => goToPage(currentPage - 1)}
          >
            <ChevronUp20Regular />
          </button>
          <span className="pdf-toolbar__page">{ready ? `Page ${currentPage} / ${pageCount}` : 'Page \u2013'}</span>
          <button
            type="button"
            className="app-tool"
            aria-label="Next page"
            disabled={!ready || currentPage >= pageCount}
            onClick={() => goToPage(currentPage + 1)}
          >
            <ChevronDown20Regular />
          </button>
        </div>
        <div className="pdf-toolbar__group">
          <button
            type="button"
            className="app-tool"
            aria-label="Zoom out"
            disabled={!ready || zoom <= MIN_ZOOM}
            onClick={() => setZoom((value) => Math.max(MIN_ZOOM, Math.round((value - ZOOM_STEP) * 100) / 100))}
          >
            <ZoomOut20Regular />
          </button>
          <span className="pdf-toolbar__zoom">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            className="app-tool"
            aria-label="Zoom in"
            disabled={!ready || zoom >= MAX_ZOOM}
            onClick={() => setZoom((value) => Math.min(MAX_ZOOM, Math.round((value + ZOOM_STEP) * 100) / 100))}
          >
            <ZoomIn20Regular />
          </button>
          <button type="button" className="app-tool" aria-label="Fit to width" disabled={!ready || zoom === 1} onClick={() => setZoom(1)}>
            <ArrowMaximize20Regular />
          </button>
        </div>
        <div className="pdf-toolbar__group">
          <span className="pdf-toolbar__label">Evidence</span>
          <div className="seg seg--compact" role="group" aria-label="Evidence style">
            {EVIDENCE_STYLES.map((option) => (
              <button
                key={option.id}
                type="button"
                className="seg__btn"
                title={option.title}
                aria-pressed={evidenceStyle === option.id}
                onClick={() => chooseEvidenceStyle(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <span className="pdf-toolbar__locate" role="status">
          {label}
        </span>
      </div>

      {!searching && resolved.method === 'page' && target && target.quote.trim() !== '' ? (
        <div className="pdf-quote">
          <span className="vz-eyebrow">Evidence quote (not found in the page text)</span>
          <p>{target.quote}</p>
        </div>
      ) : null}

      <div ref={setScroller} className="vz-viewer pdf-scroller" tabIndex={0} role="region" aria-label="Contract document" onScroll={onScroll}>
        {error ? (
          <p className="pdf-message" role="alert">
            Could not open this PDF: {error}
          </p>
        ) : doc === null ? (
          <div className="pdf-message">
            <Spinner label={'Opening document\u2026'} />
          </div>
        ) : ready ? (
          <div className="pdf-pages">
            {sizes.map((size, index) => (
              <PdfPage
                key={index + 1}
                doc={doc}
                pageNumber={index + 1}
                width={size.width}
                height={size.height}
                scale={scale}
                root={scroller}
                highlights={resolved.byPage.get(index + 1) ?? NO_RECTS}
                highlightKey={highlightKey}
                evidenceStyle={evidenceStyle}
              />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
