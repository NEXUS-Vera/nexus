import path from 'node:path';
import { app, BrowserWindow } from 'electron';

/**
 * Electron main-process entry point.
 *
 * This is the composition root, and the only module in this package allowed to
 * import `electron` directly. Everything it composes takes the Electron APIs it
 * needs as arguments so those modules stay unit-testable in plain Node.
 */

/**
 * The renderer is loaded from disk, not from a development server.
 *
 * `app.getAppPath()` is the application root in both shapes the shell runs in:
 * the built package directory during development, and the archive root once
 * packaged. Resolving from it keeps one path expression correct for both.
 */
function rendererEntryPath(): string {
  return path.join(app.getAppPath(), 'dist', 'renderer', 'index.html');
}

async function openMainWindow(): Promise<void> {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
  });

  await window.loadFile(rendererEntryPath());
}

void app.whenReady().then(openMainWindow);

// The shell hosts exactly one window and owns local processes on the user's
// machine. Outliving its last window would leave those running invisibly.
app.on('window-all-closed', () => {
  app.quit();
});
