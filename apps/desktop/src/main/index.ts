import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { app, BrowserWindow, dialog, ipcMain } from 'electron';

import { serveRuntimeConfig } from '../shared/runtime-config.js';
import type { RendererRuntimeConfig } from '../shared/runtime-config.js';
import { resolveRendererEntry } from './renderer-entry.js';
import { createSessionToken } from './session-token.js';
import { createShutdownHandler, startShell } from './shell-session.js';
import { resolveSidecarLaunch } from './sidecar-launch.js';
import { SidecarSupervisor } from './sidecar-supervisor.js';

/**
 * Electron main-process entry point.
 *
 * This is the composition root, and the only module in this package allowed to
 * import `electron` directly. Everything it composes takes the Electron APIs it
 * needs as arguments so those modules stay unit-testable in plain Node.
 */

function preloadEntryPath(): string {
  return path.join(app.getAppPath(), 'dist', 'preload', 'index.cjs');
}

/**
 * Where the sidecar keeps the user's projects.
 *
 * `userData` is the per-user application data directory the operating system
 * set aside for exactly this - `~/Library/Application Support` on macOS,
 * `%APPDATA%` on Windows - so the database survives an application update and
 * belongs to the user rather than to the installation. The directory is created
 * here because the sidecar is handed a path, not a chance to make one.
 */
function databaseFilePath(): string {
  const directory = app.getPath('userData');
  mkdirSync(directory, { recursive: true });
  return path.join(directory, 'nexus.sqlite3');
}

/**
 * The configuration the preload bridge is currently serving.
 *
 * Held here rather than captured by the channel handler because a replacement
 * sidecar binds a new port: the answer has to be re-readable, not fixed at the
 * moment the first window opened.
 */
let rendererRuntimeConfig: RendererRuntimeConfig | undefined;

function currentRuntimeConfig(): RendererRuntimeConfig {
  if (rendererRuntimeConfig === undefined) {
    // Unreachable through `startShell`, which opens a window only after the
    // handshake. Stated rather than defaulted, because a placeholder address
    // here would reach the renderer as a real one.
    throw new Error('The renderer asked for its runtime configuration before the shell had one.');
  }
  return rendererRuntimeConfig;
}

/**
 * Point every open window at a replacement sidecar.
 *
 * The bridge deliberately exposes named values rather than anything the page
 * can call, so there is no channel to push a new address down. Reloading is
 * therefore how the renderer learns: the preload runs again and asks for the
 * configuration above, which by then names the replacement. The alternative -
 * leaving the page addressing a port nothing is listening on - looks healthy
 * and fails on every request.
 */
function republishRuntimeConfig(config: RendererRuntimeConfig): void {
  rendererRuntimeConfig = config;
  for (const window of BrowserWindow.getAllWindows()) {
    window.webContents.reload();
  }
}

async function openMainWindow(config: RendererRuntimeConfig): Promise<void> {
  // Checked before a window exists, so a missing interface is reported as one
  // sentence rather than as an empty frame that failed to load a file URL.
  // `app.getAppPath()` is the application root in both shapes the shell runs
  // in: the built package directory during development, and the archive root
  // once packaged.
  const rendererEntry = resolveRendererEntry(app.getAppPath());

  // Answering is arranged before the window exists: the preload asks for this
  // during its own load, which happens before the page's first script runs.
  rendererRuntimeConfig = config;
  serveRuntimeConfig(ipcMain, currentRuntimeConfig);

  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: preloadEntryPath(),
      // Stated rather than inherited. These are Electron's defaults today, but
      // they are the whole security posture of the shell, and a default is a
      // decision someone else gets to change. Read together: the page runs in
      // its own isolated world, in an OS sandbox, with no Node built-ins and no
      // way to reach the main process except the bridge the preload exposes.
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  try {
    await window.loadFile(rendererEntry);
  } catch (error) {
    // A load that stops because the window went away is a quit arriving during
    // startup, not a failure to start. Treating it as one would raise a dialog
    // about an application the user has already closed.
    if (!window.isDestroyed()) {
      throw error;
    }
  }
}

async function bootstrap(): Promise<void> {
  // Minted per run and held only in memory. Writing it anywhere on disk would
  // turn a credential that dies with this process into one that outlives it.
  const sessionToken = createSessionToken();

  await startShell({
    sessionToken,
    createSidecar: ({ onTerminalFailure, onRestart }) =>
      new SidecarSupervisor({
        ...resolveSidecarLaunch(process.env),
        sessionToken,
        databaseFile: databaseFilePath(),
        onTerminalFailure,
        onRestart,
      }),
    host: {
      // Every route out of the application passes through `before-quit`: the
      // menu item, the keyboard shortcut, and the implicit quit Electron
      // performs when the last window closes. Hanging the sidecar's shutdown
      // here covers all of them, so no exit leaves the local service running.
      //
      // No `window-all-closed` listener accompanies this on purpose.
      // Subscribing to that event takes ownership of whether the application
      // quits, and the only thing this shell would do with that ownership is
      // quit - which is already what Electron does when nobody subscribes.
      registerShutdown: (sidecar) => {
        app.on(
          'before-quit',
          createShutdownHandler(sidecar, () => {
            app.quit();
          }),
        );
      },
      openWindow: openMainWindow,
      updateRuntimeConfig: republishRuntimeConfig,
      reportFatalError: (message) => {
        dialog.showErrorBox('Nexus cannot start', message);
      },
      quit: () => {
        app.quit();
      },
    },
  });
}

void app.whenReady().then(async () => {
  try {
    await bootstrap();
  } catch (error) {
    // Nothing above may become an unhandled rejection. An unhandled rejection
    // in the main process leaves the shell in a state nobody chose: no window,
    // no message, and a sidecar that may still be running.
    dialog.showErrorBox(
      'Nexus cannot start',
      `Nexus stopped while starting up.\n\nDetails: ${
        error instanceof Error ? error.message : String(error)
      }`,
    );
    app.quit();
  }
});
