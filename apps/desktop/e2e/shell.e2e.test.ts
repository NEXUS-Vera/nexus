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
    const page = await app.firstWindow();

    await expect(
      page.getByRole('heading', { name: 'Start a new embedded project' }),
    ).toBeVisible();

    // Landing on home is not enough: over `file://` there is no server to map a
    // path back onto the bundle, so a router that addresses routes through the
    // pathname replaces the document's own URL with something that no longer
    // exists on disk. The window then cannot be reloaded or restored, and every
    // relative asset resolves against the wrong directory.
    expect(page.url()).toContain('dist/renderer/index.html');
  } finally {
    await app.close();
  }
});

test('exposes nothing to the renderer beyond the allowlisted bridge', async () => {
  const app = await electron.launch({ args: [packageRoot], env: launchEnvironment() });

  try {
    const page = await app.firstWindow();

    const exposure = await page.evaluate(() => {
      const scope = window as unknown as Record<string, unknown>;
      const bridge = scope.nexus as Record<string, unknown> | undefined;

      return {
        require: typeof scope.require,
        process: typeof scope.process,
        ipcRenderer: typeof scope.ipcRenderer,
        bridgeKeys: bridge === undefined ? null : Object.keys(bridge).sort(),
        nonAllowlistedChannel: typeof bridge?.['nexus:write-file'],
      };
    });

    // Vera writes files and spawns shells on the user's machine. Any Node handle
    // reachable from the page turns a cross-site script or a malicious model
    // output into arbitrary local code execution, so the renderer must see
    // exactly the surface the shell chose to hand it and nothing else.
    expect(exposure).toEqual({
      require: 'undefined',
      process: 'undefined',
      ipcRenderer: 'undefined',
      bridgeKeys: ['api'],
      nonAllowlistedChannel: 'undefined',
    });
  } finally {
    await app.close();
  }
});
