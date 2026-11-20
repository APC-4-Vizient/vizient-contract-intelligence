import { useEffect, useMemo, useRef, useState } from 'react';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
import { groupPassages, scaleRect } from '../domain/geometry';
import type { Passage, Rect } from '../domain/geometry';
import type { EvidenceStyle } from './evidenceStyle';

const MAX_CANVAS_PIXELS = 16_000_000;
const RENDER_MARGIN = '900px 0px';
/** How far left of the evidence its margin bar sits, in pixels, so it never touches the text. */
const BAR_GAP = 12;

interface PdfPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  /** Page size in points at scale 1. */
  width: number;
  height: number;
  scale: number;
  /** The scroll container. Only pages near its viewport are drawn, which keeps memory bounded on long contracts. */
  root: HTMLElement | null;
  /** Evidence line boxes on this page, in points at scale 1. */
  highlights: readonly Rect[];
  /** Changes on every finding click so the marks remount and their pulse restarts. */
  highlightKey: number;
  evidenceStyle: EvidenceStyle;
}

function isCancelled(error: unknown): boolean {
  return error instanceof Error && error.name === 'RenderingCancelledException';
}

/** Marks one passage of evidence. It never paints over the text: the marker and box sit beside it, the highlight blends into it. */
function EvidenceMark({ passage, scale, variant }: { passage: Passage; scale: number; variant: EvidenceStyle }) {
  const box = scaleRect(passage.bounds, scale);
  const barOffset = Math.min(BAR_GAP, Math.max(0, box.left - 2));
  return (
    <div
      className={`pdf-evidence pdf-evidence--${variant}`}
      style={{ left: box.left, top: box.top, width: box.width, height: box.height }}
      aria-hidden="true"
    >
      <span className="pdf-evidence__flash" />
      {variant === 'marker' ? <span className="pdf-evidence__bar" style={{ left: -barOffset }} /> : null}
      {variant === 'box'
        ? null
        : passage.lines.map((line, index) => {
            const at = scaleRect(line, scale);
            return (
              <span
                key={index}
                className="pdf-evidence__line"
                style={{ left: at.left - box.left, top: at.top - box.top, width: at.width, height: at.height }}
              />
            );
          })}
    </div>
  );
}

export function PdfPage({ doc, pageNumber, width, height, scale, root, highlights, highlightKey, evidenceStyle }: PdfPageProps) {
  const frame = useRef<HTMLDivElement>(null);
  const host = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  const [failed, setFailed] = useState(false);
  const passages = useMemo(() => groupPassages(highlights), [highlights]);

  useEffect(() => {
    const element = frame.current;
    if (!element || !root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) setNear(entry.isIntersecting);
      },
      { root, rootMargin: RENDER_MARGIN },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [root]);

  useEffect(() => {
    const target = host.current;
    if (!target) return;
    if (!near) {
      target.replaceChildren();
      return;
    }

    let cancelled = false;
    let task: RenderTask | null = null;
    doc
      .getPage(pageNumber)
      .then((page) => {
        if (cancelled) return undefined;
        const ratio = window.devicePixelRatio || 1;
        const full = page.getViewport({ scale: scale * ratio });
        const shrink = Math.min(1, Math.sqrt(MAX_CANVAS_PIXELS / (full.width * full.height)));
        const viewport = page.getViewport({ scale: scale * ratio * shrink });
        // Every render gets a fresh canvas that replaces the old one only once it is complete, so zooming never flashes blank.
        const canvas = document.createElement('canvas');
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        task = page.render({ canvas, viewport });
        return task.promise.then(() => {
          if (cancelled) return;
          target.replaceChildren(canvas);
          setFailed(false);
        });
      })
      .catch((error: unknown) => {
        if (!cancelled && !isCancelled(error)) setFailed(true);
      });

    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [doc, pageNumber, scale, near]);

  return (
    <div ref={frame} className="pdf-page" data-page={pageNumber} style={{ width: width * scale, height: height * scale }}>
      <div ref={host} className="pdf-page__canvas" />
      {passages.map((passage, index) => (
        <EvidenceMark key={`${highlightKey}-${index}`} passage={passage} scale={scale} variant={evidenceStyle} />
      ))}
      {failed ? (
        <p className="pdf-page__error" role="alert">
          Page {pageNumber} could not be drawn.
        </p>
      ) : null}
    </div>
  );
}
