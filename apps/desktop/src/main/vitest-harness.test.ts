import { describe, expect, it } from 'vitest';

/**
 * HARNESS SMOKE CHECK — not a test of product behavior.
 *
 * This asserts the one property the main-process test runner exists to
 * guarantee: main-process suites execute in plain Node, with no DOM and no
 * Electron runtime attached. It fails if `vitest.config.ts` is switched to a
 * browser-like environment or if the runner is ever made to boot Electron,
 * which is exactly when main-process unit tests would stop being runnable
 * without a display.
 */
describe('main-process test harness', () => {
  it('runs in plain Node without a DOM', () => {
    expect(process.versions.node).toBeDefined();
    expect(globalThis).not.toHaveProperty('window');
    expect(globalThis).not.toHaveProperty('document');
  });

  it('runs without an Electron runtime', () => {
    expect(process.versions.electron).toBeUndefined();
  });
});
