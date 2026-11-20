import { defineConfig } from 'vitest/config';

// Kept apart from vite.config.ts so the Power Apps plugin is not loaded for unit tests.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
