import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import type { Plugin } from 'vite';
import { inlineAssets } from './src/standalone/inlineHtml';
import type { BuiltFile } from './src/standalone/inlineHtml';

/*
  Builds the "How it works" diagram as one HTML file with its code and styles inside, so it opens from a folder or an
  attachment with no server and no network:

    npm run build:standalone      writes ../docs/architecture-3d.html

  It needs neither the Power Platform sign-in nor `pa app init`: the page reads no data. The page carries a build-info
  block that lists every source file it was built from and each file's hash, and tests/test_architecture_page.py fails
  while any of them has changed, so a change to the diagram cannot ship without a rebuild.
*/

const projectRoot = fileURLToPath(new URL('.', import.meta.url));
const OUTPUT = resolve(projectRoot, '..', 'docs', 'architecture-3d.html');

// Files that shape the page without being part of its module graph.
const ALSO_HASHED = ['standalone.html', 'vite.standalone.config.ts', 'src/standalone/inlineHtml.ts'];

// Libraries whose versions end up inside the page.
const PACKAGES = ['react', 'react-dom', 'three', '@fluentui/react-icons', '@fluentui/react-components'];

const slashes = (path: string) => path.split(sep).join('/');

/** A file's SHA-256 with line endings normalized, so a Windows checkout and a Linux one agree. */
function fileHash(path: string): string {
  const text = readFileSync(path).toString('latin1').replace(/\r\n/g, '\n');
  return createHash('sha256').update(Buffer.from(text, 'latin1')).digest('hex');
}

function buildInfo(moduleIds: Iterable<string>): string {
  const base = slashes(projectRoot);
  const paths = new Set(ALSO_HASHED);
  for (const id of moduleIds) {
    const path = slashes(id.split('?')[0]);
    if (path.startsWith(`${base}src/`)) paths.add(path.slice(base.length));
  }
  const builtFrom = Object.fromEntries(
    [...paths].sort().map((path) => [path, fileHash(resolve(projectRoot, path))]),
  );
  const packages = Object.fromEntries(
    PACKAGES.map((name) => [name, (JSON.parse(readFileSync(resolve(projectRoot, 'node_modules', name, 'package.json'), 'utf8')) as { version: string }).version]),
  );
  return `<script type="application/json" id="build-info">\n${JSON.stringify({ builtFrom, packages }, null, 2)}\n</script>\n`;
}

function standalonePage(): Plugin {
  return {
    name: 'standalone-architecture-page',
    apply: 'build',
    enforce: 'post',
    generateBundle: {
      // Last of all: Vite's own generateBundle fills in the markers of its dynamic-import helper (__VITE_PRELOAD__), and
      // the code must be finished before it goes into the page.
      order: 'post',
      handler(_options, bundle) {
        const files: BuiltFile[] = [];
        let page: string | null = null;
        for (const [name, output] of Object.entries(bundle)) {
          if (output.type === 'chunk') {
            const marker = /__VITE_[A-Z_]+__/.exec(output.code);
            if (marker) this.error(`${name} still holds the Vite marker ${marker[0]}: the page was assembled before Vite finished the bundle.`);
            files.push({ name, content: output.code });
            continue;
          }
          const text = typeof output.source === 'string' ? output.source : Buffer.from(output.source).toString('utf8');
          if (name.endsWith('.html')) page = text;
          else files.push({ name, content: text });
        }
        if (page === null) this.error('The build produced no HTML page.');
        const html = inlineAssets(page, files).replace('</head>', () => `${buildInfo(this.getModuleIds())}</head>`);
        mkdirSync(dirname(OUTPUT), { recursive: true });
        writeFileSync(OUTPUT, html);
        this.info(`Wrote ${slashes(relative(resolve(projectRoot, '..'), OUTPUT))}: ${Buffer.byteLength(html).toLocaleString('en-US')} bytes.`);
        // Everything is inside the page, so there is nothing left for Vite to write.
        for (const name of Object.keys(bundle)) delete bundle[name];
      },
    },
  };
}

export default defineConfig({
  base: './',
  plugins: [react(), standalonePage()],
  build: {
    // Never written to: the plugin writes the page itself, and a stray `dist` here would be the Code App's deploy folder.
    outDir: 'node_modules/.tmp/standalone-page',
    write: false,
    cssCodeSplit: false,
    modulePreload: false,
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    reportCompressedSize: false,
    rollupOptions: {
      input: resolve(projectRoot, 'standalone.html'),
      // One file: the diagram's 3D engine is a dynamic import in the app and is folded in here.
      output: { inlineDynamicImports: true },
    },
  },
});
