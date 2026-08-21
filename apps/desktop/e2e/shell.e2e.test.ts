import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { _electron as electron, expect, test } from '@playwright/test';
import type { ElectronApplication } from '@playwright/test';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fakeSidecar = path.join(packageRoot, 'e2e', 'fixtures', 'fake-sidecar.mjs');

/**
 * Launch the built shell against a sidecar these suites control.
 *
 * The fixture speaks the real handshake over a real loopback socket, so the
 * shell does the same work it does in production - spawn, wait for the
 * announcement, resolve the address - without the suite needing a Python
 * runtime installed on the machine that runs it.
 *
 * `ELECTRON_RUN_AS_NODE` is stripped from the inherited environment because it
 * turns the Electron binary into a plain Node interpreter, and an environment
 * that exports it (some agent and CI harnesses do) would start the shell with
 * no `app` and no window at all.
 */
async function launchShell(): Promise<ElectronApplication> {
  const environment: Record<string, string> = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (key !== 'ELECTRON_RUN_AS_NODE' && value !== undefined) {
      environment[key] = value;
    }
  }

  environment.NEXUS_SIDECAR_COMMAND = process.execPath;
  environment.NEXUS_SIDECAR_ARGS = JSON.stringify([fakeSidecar]);

  return electron.launch({ args: [packageRoot], env: environment });
}

/**
 * Close the shell and wait until its process is really gone.
 *
 * Safe to call on a shell that has already exited, so a test that closes the
 * application as part of what it is asserting can still close it again from a
 * `finally` block. Waiting on an `exit` that has already fired would otherwise
 * hang the run for the sake of tidying up.
 */
async function closeShell(app: ElectronApplication): Promise<void> {
  const shell = app.process();
  if (shell.exitCode !== null || shell.signalCode !== null) {
    return;
  }

  const exited = new Promise<void>((resolve) => {
    shell.once('exit', () => {
      resolve();
    });
  });

  await app.close();
  await exited;
}

test('opens the renderer on the home route without rewriting its file URL', async () => {
  const app = await launchShell();

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
    await closeShell(app);
  }
});

test('exposes nothing to the renderer beyond the allowlisted bridge', async () => {
  const app = await launchShell();

  try {
    const page = await app.firstWindow();

    const exposure = await page.evaluate(() => {
      const scope = window as unknown as Record<string, unknown>;
      const bridge = scope.nexus as Record<string, unknown> | undefined;
      const api = bridge?.api as Record<string, unknown> | undefined;
      const shell = bridge?.shell as Record<string, unknown> | undefined;

      return {
        require: typeof scope.require,
        process: typeof scope.process,
        ipcRenderer: typeof scope.ipcRenderer,
        bridgeKeys: bridge === undefined ? null : Object.keys(bridge).sort(),
        apiKeys: api === undefined ? null : Object.keys(api).sort(),
        shellKeys: shell === undefined ? null : Object.keys(shell).sort(),
        serviceRestarted: shell?.serviceRestarted,
        nonAllowlistedChannel: typeof bridge?.['nexus:write-file'],
      };
    });

    // Vera writes files and spawns shells on the user's machine. Any Node handle
    // reachable from the page turns a cross-site script or a hostile model
    // output into arbitrary local code execution, so the renderer must see
    // exactly the surface the shell chose to hand it and nothing else.
    expect(exposure).toEqual({
      require: 'undefined',
      process: 'undefined',
      ipcRenderer: 'undefined',
      bridgeKeys: ['api', 'shell'],
      apiKeys: ['baseUrl', 'sessionToken'],
      shellKeys: ['serviceRestarted'],
      // A first launch is not a recovery from anything.
      serviceRestarted: false,
      nonAllowlistedChannel: 'undefined',
    });
  } finally {
    await closeShell(app);
  }
});

test('keeps the student’s projects in a named directory, on the sqlite backend', async () => {
  const app = await launchShell();

  try {
    const page = await app.firstWindow();

    const storage = await page.evaluate<{
      storageBackend: string | null;
      databaseUrl: string | null;
    }>(async () => {
      const api = (window as unknown as { nexus: { api: Record<string, string> } }).nexus.api;
      const response = await fetch(`${api.baseUrl}/healthz`, {
        headers: { Authorization: `Bearer ${api.sessionToken}` },
      });

      return (await response.json()) as {
        storageBackend: string | null;
        databaseUrl: string | null;
      };
    });

    // The API's own default backend is in-memory, so a shell that says nothing
    // loses every project on quit. Read back from the spawned process, because
    // what matters is what it was actually started with.
    expect(storage.storageBackend).toBe('sqlite');

    const databaseFile = (storage.databaseUrl ?? '').replace(/^sqlite:\/\/\//, '');
    expect(path.basename(databaseFile)).toBe('nexus.sqlite3');
    // Electron derives `userData` from the application's name, which without an
    // explicit `productName` is the npm package name - putting a scope segment
    // into the directory a student's projects live in permanently. Moving it
    // after a release orphans their data, so it is pinned here.
    expect(path.basename(path.dirname(databaseFile))).toBe('Nexus');
  } finally {
    await closeShell(app);
  }
});

test('hands the renderer a live address and the sidecar’s own credential', async () => {
  const app = await launchShell();

  try {
    const page = await app.firstWindow();

    const probe = await page.evaluate<{
      baseUrl: string;
      authorization: string | null;
      expectedToken: string;
    }>(async () => {
      const api = (window as unknown as { nexus: { api: Record<string, string> } }).nexus.api;
      const response = await fetch(`${api.baseUrl}/healthz`, {
        headers: { Authorization: `Bearer ${api.sessionToken}` },
      });
      const body = (await response.json()) as {
        authorization: string | null;
        expectedToken: string;
      };

      return { baseUrl: api.baseUrl, ...body };
    });

    // The port is whatever the operating system handed the sidecar, so the only
    // way the renderer can hold a working address is if the shell read it from
    // the handshake; and the only way the header matches is if the token the
    // renderer was given is the token the service was started with.
    expect(probe.baseUrl).toMatch(/^http:\/\/127\.0\.0\.1:\d+$/);
    expect(probe.expectedToken).toMatch(/^[0-9a-f]{64}$/);
    expect(probe.authorization).toBe(`Bearer ${probe.expectedToken}`);
  } finally {
    await closeShell(app);
  }
});

test('takes the sidecar with it when the shell closes', async () => {
  const app = await launchShell();

  try {
    const page = await app.firstWindow();

    const sidecarPid = await page.evaluate(async () => {
      const api = (window as unknown as { nexus: { api: Record<string, string> } }).nexus.api;
      // Authenticated like every other probe here. The real service exempts no
      // route, so a probe that omits the credential would read an error envelope
      // as a health report the day the fixture starts enforcing it too.
      const response = await fetch(`${api.baseUrl}/healthz`, {
        headers: { Authorization: `Bearer ${api.sessionToken}` },
      });
      const body = (await response.json()) as { pid?: number };
      return Number(body.pid);
    });

    // `process.kill` throws both for a process that has gone and for a pid that
    // is not a number, so the liveness check below distinguishes the two only
    // once this pid is known to name a process that was really running.
    expect(Number.isInteger(sidecarPid)).toBe(true);
    expect(sidecarPid).toBeGreaterThan(0);
    expect(() => {
      process.kill(sidecarPid, 0);
    }).not.toThrow();

    await closeShell(app);

    // A sidecar that survives the shell keeps holding the user's local database
    // and its loopback port, and nothing on screen says it is there. Closing the
    // application has to end it.
    expect(() => {
      process.kill(sidecarPid, 0);
    }).toThrow();
  } finally {
    await closeShell(app);
  }
});
