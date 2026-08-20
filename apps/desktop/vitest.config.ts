import { defineConfig } from 'vitest/config';

/**
 * Vitest configuration for Electron MAIN-PROCESS code.
 *
 * Main-process modules are plain Node modules. They are unit tested by running
 * them directly in Node, never by launching Electron, so the runner is
 * configured for a Node environment with no DOM and no browser globals.
 *
 * Renderer/UI testing is not in scope for this package; it lives in `@nexus/web`.
 */
export default defineConfig({
  test: {
    // Node, not jsdom: main-process code must never depend on DOM globals.
    environment: 'node',
    // Only main-process suites. Preload code runs in the renderer's context and
    // is covered by renderer-side tooling, not this runner.
    include: ['src/main/**/*.test.ts'],
    exclude: ['**/node_modules/**', '**/dist/**'],
    // A real child Node process per test file, so modules that manage child
    // processes, signals, and process-level state get an isolated, disposable
    // host rather than a shared worker thread.
    pool: 'forks',
    restoreMocks: true,
  },
});
