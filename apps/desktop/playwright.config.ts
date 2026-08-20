import { defineConfig } from '@playwright/test';

/**
 * Playwright configuration for the Electron shell smoke suite.
 *
 * These suites launch a real Electron process against the built shell and the
 * built renderer, which is the only way to observe things that exist solely at
 * runtime: how the renderer routes over `file://`, and what the preload bridge
 * actually exposes to the page. They are deliberately separate from the Vitest
 * suite in `src/main`, which stays Node-only and needs no display.
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.test.ts',
  timeout: 60_000,
  // One Electron application at a time: each launch owns a real window, a real
  // sidecar, and real loopback ports, none of which parallelise for free.
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  reporter: 'list',
});
