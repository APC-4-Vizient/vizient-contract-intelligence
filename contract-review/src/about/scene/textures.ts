import { CanvasTexture, SRGBColorSpace } from 'three';

/*
  Every texture in the 3D view is drawn here with the 2D canvas. Nothing is fetched and no image is embedded, which
  keeps the view working under the Power Apps host's content security policy.
*/

function makeCanvas(width: number, height: number): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('The 2D canvas is not available.');
  return [canvas, context];
}

function finish(canvas: HTMLCanvasElement): CanvasTexture {
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

function roundedRect(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, radius: number): void {
  context.beginPath();
  context.moveTo(x + radius, y);
  context.arcTo(x + width, y, x + width, y + height, radius);
  context.arcTo(x + width, y + height, x, y + height, radius);
  context.arcTo(x, y + height, x, y, radius);
  context.arcTo(x, y, x + width, y, radius);
  context.closePath();
}

/** A soft round glow, white in the middle. Tinted by whatever uses it. */
export function createGlowTexture(): CanvasTexture {
  const [canvas, context] = makeCanvas(128, 128);
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.25, 'rgba(255,255,255,0.55)');
  gradient.addColorStop(0.6, 'rgba(255,255,255,0.12)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  return finish(canvas);
}

const LINE_WIDTHS = [0.92, 0.84, 0.95, 0.7, 0.88, 0.9, 0.62, 0.86, 0.93, 0.78, 0.5];

/** One page of a contract: a title band, lines of text, a highlighted passage and a boxed one. */
function drawPage(context: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, accent: boolean): void {
  context.fillStyle = '#fefcf8';
  context.fillRect(x, y, width, height);
  context.fillStyle = '#4a1029';
  context.fillRect(x, y, width, height * 0.1);
  context.fillStyle = '#6e3a52';
  context.fillRect(x + width * 0.08, y + height * 0.14, width * 0.5, height * 0.035);

  const top = y + height * 0.23;
  const step = (height * 0.72) / LINE_WIDTHS.length;
  LINE_WIDTHS.forEach((fraction, index) => {
    const lineY = top + index * step;
    if (accent && index === 4) {
      context.fillStyle = 'rgba(255,204,18,0.75)';
      context.fillRect(x + width * 0.05, lineY - step * 0.22, width * 0.9, step * 0.62);
    }
    context.fillStyle = accent && index === 4 ? '#2c0a19' : '#cfc0c8';
    context.fillRect(x + width * 0.08, lineY, width * 0.84 * fraction, step * 0.26);
    if (accent && index === 8) {
      context.strokeStyle = '#f67318';
      context.lineWidth = Math.max(2, width * 0.012);
      context.strokeRect(x + width * 0.05, lineY - step * 0.2, width * 0.9, step * 0.6);
    }
  });
}

/** The contract that travels through the pipeline. */
export function createPaperTexture(): CanvasTexture {
  const [canvas, context] = makeCanvas(256, 332);
  drawPage(context, 0, 0, 256, 332, true);
  context.strokeStyle = 'rgba(74,16,41,0.35)';
  context.lineWidth = 3;
  context.strokeRect(1.5, 1.5, 253, 329);
  return finish(canvas);
}

const FINDING_ROWS: readonly { dot: string; width: number; pill: number }[] = [
  { dot: '#1a9a59', width: 0.62, pill: 0.9 },
  { dot: '#1a9a59', width: 0.5, pill: 0.84 },
  { dot: '#f67318', width: 0.7, pill: 0.95 },
  { dot: '#ffcc12', width: 0.44, pill: 0.62 },
  { dot: '#1a9a59', width: 0.58, pill: 0.88 },
  { dot: '#ffcc12', width: 0.66, pill: 0.7 },
  { dot: '#1a9a59', width: 0.4, pill: 0.92 },
];

/** A miniature of the Code App: the PDF with its evidence marked on the left, the findings on the right. */
export function createScreenTexture(): CanvasTexture {
  const [canvas, context] = makeCanvas(640, 400);
  context.fillStyle = '#eee8ec';
  context.fillRect(0, 0, 640, 400);

  context.fillStyle = '#2c0a19';
  context.fillRect(0, 0, 640, 46);
  context.fillStyle = '#f67318';
  roundedRect(context, 16, 11, 26, 24, 7);
  context.fill();
  context.fillStyle = '#fefcf8';
  context.font = '600 17px "Segoe UI", system-ui, sans-serif';
  context.textBaseline = 'middle';
  context.fillText('Contract Review', 54, 24);
  context.fillStyle = '#6e3a52';
  roundedRect(context, 560, 12, 64, 22, 11);
  context.fill();

  context.fillStyle = 'rgba(15,3,8,0.18)';
  context.fillRect(30, 66, 268, 322);
  drawPage(context, 24, 60, 268, 322, true);

  const rowTop = 62;
  const rowHeight = 41;
  FINDING_ROWS.forEach((row, index) => {
    const y = rowTop + index * rowHeight;
    context.fillStyle = '#fefcf8';
    roundedRect(context, 318, y, 306, rowHeight - 7, 9);
    context.fill();
    if (index === 2) {
      context.strokeStyle = '#f67318';
      context.lineWidth = 3;
      roundedRect(context, 318, y, 306, rowHeight - 7, 9);
      context.stroke();
    }
    context.fillStyle = row.dot;
    context.beginPath();
    context.arc(338, y + (rowHeight - 7) / 2, 7, 0, Math.PI * 2);
    context.fill();
    context.fillStyle = '#4a1029';
    roundedRect(context, 356, y + 11, 150 * row.width * 1.4, 7, 3.5);
    context.fill();
    context.fillStyle = '#cfc0c8';
    roundedRect(context, 356, y + 22, 110 * row.width * 1.4, 5, 2.5);
    context.fill();
    context.fillStyle = '#e2d8dc';
    roundedRect(context, 548, y + 9, 60 * row.pill, 16, 8);
    context.fill();
  });

  context.fillStyle = '#f67318';
  roundedRect(context, 470, 352, 154, 36, 18);
  context.fill();
  context.fillStyle = '#1d160a';
  context.font = '700 16px "Segoe UI", system-ui, sans-serif';
  context.textAlign = 'center';
  context.fillText('Approve', 547, 371);
  return finish(canvas);
}
