import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { powerApps } from '@microsoft/power-apps-vite/plugin';
import { defineConfig } from 'vite';
import { mockFixtures } from './vite.fixtures';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));

// `vite --mode mock` serves the saved sample contracts instead of connecting to Power Platform.
export default defineConfig(({ mode }) => ({
  plugins: [react(), mode === 'mock' ? mockFixtures(repoRoot) : powerApps()],
}));
