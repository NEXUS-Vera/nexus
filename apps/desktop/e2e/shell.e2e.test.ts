import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { _electron as electron, expect, test } from '@playwright/test';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/**
 * Inherit the caller's environment minus `ELECTRON_RUN_AS_NODE`.
 *
 * That variable turns the Electron binary into a plain Node interpreter, so an
 * environment that exports it (some agent and CI harnesses do) would start the
 * shell with no `app` and no window at all. Stripping it keeps the suite
 * measuring the product rather than the harness it happens to run in.
 */
function launchEnvironment(): Record<string, string> {
  const environment: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (key !== 'ELECTRON_RUN_AS_NODE' && value !== undefined) {
      environment[key] = value;
    }
  }
  return environment;
}

test('opens the renderer on the home route without rewriting its file URL', async () => {
  const app = await electron.launch({ args: [packageRoot], env: launchEnvironment() });

  try {
    const window = await app.firstWindow();

    await expect(
      window.getByRole('heading', { name: 'Start a new embedded project' }),
    ).toBeVisible();

    // Landing on home is not enough: over `file://` there is no server to map a
    // path back onto the bundle, so a router that addresses routes through the
    // pathname replaces the document's own URL with something that no longer
    // exists on disk. The window then cannot be reloaded or restored, and every
    // relative asset resolves against the wrong directory.
    expect(window.url()).toContain('dist/renderer/index.html');
  } finally {
    await app.close();
  }
});
