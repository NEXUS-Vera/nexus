import { expect, it, vi } from 'vitest';

import type { StartShellOptions } from './shell-session.js';

const { app, startShell } = vi.hoisted(() => ({
  app: {
    whenReady: vi.fn().mockResolvedValue(undefined),
    on: vi.fn(),
    quit: vi.fn(),
    exit: vi.fn(),
  },
  startShell: vi.fn<(options: StartShellOptions) => Promise<void>>().mockResolvedValue(undefined),
}));

vi.mock('electron', () => ({ app, BrowserWindow: {}, dialog: {}, ipcMain: {} }));
vi.mock('./shell-session.js', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./shell-session.js')>()),
  startShell,
}));

it('exits Electron only after the sidecar has stopped, without requesting another quit', async () => {
  app.whenReady.mockResolvedValue(undefined);
  startShell.mockResolvedValue(undefined);
  await import('./index.js');
  await vi.waitFor(() => expect(startShell).toHaveBeenCalledOnce());

  let finishStop!: () => void;
  const stopped = new Promise<void>((resolve) => {
    finishStop = resolve;
  });
  const stop = vi.fn(() => stopped);
  startShell.mock.calls[0]![0].host.registerShutdown({
    start: vi.fn(),
    stop,
  });

  expect(app.on).toHaveBeenCalledWith('before-quit', expect.any(Function));
  const onBeforeQuit = app.on.mock.calls[0]![1] as (event: {
    preventDefault: () => void;
  }) => void;
  const preventDefault = vi.fn();
  onBeforeQuit({ preventDefault });

  expect(preventDefault).toHaveBeenCalledOnce();
  expect(stop).toHaveBeenCalledOnce();
  expect(app.exit).not.toHaveBeenCalled();

  finishStop();
  await vi.waitFor(() => expect(app.exit).toHaveBeenCalledExactlyOnceWith(0));
  expect(app.quit).not.toHaveBeenCalled();
});
