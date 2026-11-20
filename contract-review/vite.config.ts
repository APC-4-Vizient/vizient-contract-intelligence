import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { powerApps } from '@microsoft/power-apps-vite/plugin';
import { defineConfig } from 'vite';
import { mockFixtures } from './vite.fixtures';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));

// `vite --mode mock` serves the saved sample contracts instead of connecting to Power Platform.
export default defineConfig(({ mode }) => ({
  plugins: [react(), mode === 'mock' ? mockFixtures(repoRoot) : powerApps()],
  build: {
    // The three chunks over 500 kB are the libraries themselves: the PDF worker (1.2 MB, a prebuilt file), the React and Fluent UI
    // bundle, and the 3D engine, which loads only when the How it works page opens. The limit sits just above the largest of them,
    // so a new heavy chunk still warns.
    chunkSizeWarningLimit: 1250,
  },
}));
