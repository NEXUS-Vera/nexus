import { describe, expect, it, vi } from 'vitest';

import type { RendererRuntimeConfig } from '../shared/runtime-config.js';
import { SidecarStartError, SidecarTerminalError } from './sidecar-supervisor.js';
import type { SidecarHandshake } from './sidecar-supervisor.js';
import { RendererBundleError } from './renderer-entry.js';
import { createShutdownHandler, startShell } from './shell-session.js';

const HANDSHAKE = {
  schemaVersion: '1.0.0',
  host: '127.0.0.1',
  port: 54_321,
  pid: 4242,
} as const;

function refuse(what: string): never {
  throw new Error(`unexpected call to ${what}`);
}

describe('startShell', () => {
  it('arranges the sidecar shutdown before a window exists to close', async () => {
    const order: string[] = [];

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: () => ({
        start: async () => HANDSHAKE,
        stop: async () => undefined,
      }),
      host: {
        registerShutdown: () => {
          order.push('registerShutdown');
        },
        openWindow: async () => {
          order.push('openWindow');
        },
        updateRuntimeConfig: () => refuse('updateRuntimeConfig'),
        reportFatalError: () => refuse('reportFatalError'),
        quit: () => refuse('quit'),
      },
    });

    // A quit can arrive while the window is still loading: the user closing it,
    // or the renderer failing to come up. Arranging the shutdown only after the
    // window is up leaves a window of time in which quitting orphans a sidecar
    // that is already running.
    expect(order).toEqual(['registerShutdown', 'openWindow']);
  });

  it('gives the renderer the address the sidecar announced', async () => {
    const opened: RendererRuntimeConfig[] = [];

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: () => ({
        start: async () => HANDSHAKE,
        stop: async () => undefined,
      }),
      host: {
        registerShutdown: () => undefined,
        openWindow: async (config) => {
          opened.push(config);
        },
        updateRuntimeConfig: () => refuse('updateRuntimeConfig'),
        reportFatalError: () => refuse('reportFatalError'),
        quit: () => refuse('quit'),
      },
    });

    // The port is assigned by the operating system at spawn time, so the
    // address only exists once the sidecar has announced it. Anything the
    // renderer was told earlier would be a guess.
    expect(opened).toEqual([
      {
        baseUrl: 'http://127.0.0.1:54321',
        sessionToken: 'a-session-token',
        // A first launch is not a recovery, and saying so would put a notice
        // about a restart that never happened in front of the student.
        serviceRestarted: false,
      },
    ]);
  });

  it('explains a startup failure instead of opening a window onto nothing', async () => {
    const timeout = new SidecarStartError(
      'handshake-timeout',
      'Sidecar did not announce a listening port within 15000ms',
    );
    const reported: string[] = [];
    const startupTitles: string[] = [];
    let quits = 0;

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: () => ({
        start: () => Promise.reject(timeout),
        stop: async () => undefined,
      }),
      host: {
        registerShutdown: () => undefined,
        openWindow: async () => refuse('openWindow'),
        updateRuntimeConfig: () => refuse('updateRuntimeConfig'),
        reportFatalError: ({ title, message }) => {
          startupTitles.push(title);
          reported.push(message);
        },
        quit: () => {
          quits += 1;
        },
      },
    });

    expect(reported).toHaveLength(1);
    const [message] = reported;
    expect(startupTitles).toEqual(['Nexus cannot start']);
    // The detail has to survive, or a user reporting the fault has nothing to
    // report; and it has to be more than the raw detail, or the message is a
    // stack trace wearing a dialog.
    expect(message).toContain(timeout.message);
    expect(message).not.toBe(timeout.message);
    expect(quits).toBe(1);
  });

  it('explains a sidecar it could not even construct', async () => {
    const misconfigured = new Error('NEXUS_SIDECAR_COMMAND is not set');
    const reported: string[] = [];
    let quits = 0;

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: () => {
        throw misconfigured;
      },
      host: {
        registerShutdown: () => undefined,
        openWindow: async () => refuse('openWindow'),
        updateRuntimeConfig: () => refuse('updateRuntimeConfig'),
        reportFatalError: ({ message }) => {
          reported.push(message);
        },
        quit: () => {
          quits += 1;
        },
      },
    });

    // Failing before the spawn and failing during it look identical to the
    // user - the application does not open - so they have to reach the same
    // dialog rather than one reaching a dialog and the other a silent crash.
    expect(reported).toHaveLength(1);
    expect(reported[0]).toContain(misconfigured.message);
    expect(quits).toBe(1);
  });

  it('explains a window that could not be opened', async () => {
    const missingBundle = new RendererBundleError('/Applications/Nexus.app/index.html');
    const reported: string[] = [];
    let stops = 0;
    let quits = 0;

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: () => ({
        start: async () => HANDSHAKE,
        stop: async () => {
          stops += 1;
        },
      }),
      host: {
        registerShutdown: () => undefined,
        openWindow: () => Promise.reject(missingBundle),
        updateRuntimeConfig: () => refuse('updateRuntimeConfig'),
        reportFatalError: ({ message }) => {
          reported.push(message);
        },
        quit: () => {
          quits += 1;
        },
      },
    });

    // The sidecar is already running by this point, so failing here has to take
    // it down as well; otherwise the one path that ends in no window is also the
    // one path that leaves a process behind.
    expect(reported).toHaveLength(1);
    expect(reported[0]).toContain(missingBundle.message);
    // A missing interface is not a sidecar fault, and blaming the local service
    // for it sends the reader looking in the wrong place.
    expect(reported[0]).not.toContain('local service');
    expect(stops).toBe(1);
    expect(quits).toBe(1);
  });

  it('tells the user when the sidecar dies for good after the window is open', async () => {
    const terminal = new SidecarTerminalError(
      'restart-limit-exceeded',
      'Sidecar exited (code 1, signal null) after 1 restart attempt(s); not restarting again',
    );
    const reported: string[] = [];
    let notifyTerminalFailure: ((error: SidecarTerminalError) => void) | undefined;
    const titles: string[] = [];
    let quits = 0;

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: ({ onTerminalFailure }) => {
        notifyTerminalFailure = onTerminalFailure;
        return { start: async () => HANDSHAKE, stop: async () => undefined };
      },
      host: {
        registerShutdown: () => undefined,
        openWindow: async () => undefined,
        updateRuntimeConfig: () => refuse('updateRuntimeConfig'),
        reportFatalError: ({ title, message }) => {
          titles.push(title);
          reported.push(message);
        },
        quit: () => {
          quits += 1;
        },
      },
    });

    // A crash after startup cannot reject the start promise; it arrives on the
    // supervisor's callback instead. Ignoring it leaves the user looking at a
    // window whose every action will now fail, with nothing saying why.
    notifyTerminalFailure?.(terminal);

    expect(reported).toHaveLength(1);
    expect(reported[0]).toContain(terminal.message);
    // The window has been open by this point, so a dialog headed "cannot start"
    // would contradict the time the student has just spent in the application.
    expect(titles).toEqual(['Nexus has to close']);
    expect(quits).toBe(1);
  });

  it('re-points the renderer when a crashed sidecar is replaced on a new port', async () => {
    const republished: RendererRuntimeConfig[] = [];
    let announceRestart: ((handshake: SidecarHandshake) => void) | undefined;

    await startShell({
      sessionToken: 'a-session-token',
      createSidecar: ({ onRestart }) => {
        announceRestart = onRestart;
        return { start: async () => HANDSHAKE, stop: async () => undefined };
      },
      host: {
        registerShutdown: () => undefined,
        openWindow: async () => undefined,
        updateRuntimeConfig: (config) => {
          republished.push(config);
        },
        reportFatalError: () => refuse('reportFatalError'),
        quit: () => refuse('quit'),
      },
    });

    announceRestart?.({ ...HANDSHAKE, port: 61_234 });

    // The replacement is spawned with NEXUS_API_PORT=0 like the original, so it
    // binds somewhere else. A recovery nobody tells the renderer about leaves a
    // window that reads as healthy while every request goes to a dead port -
    // which is worse than the crash it recovered from, because nothing says so.
    expect(republished).toEqual([
      {
        baseUrl: 'http://127.0.0.1:61234',
        sessionToken: 'a-session-token',
        // The renderer is reloaded to pick this up, and a reload nobody asked
        // for reads as the application losing the student's place unless the
        // page is told it was a recovery.
        serviceRestarted: true,
      },
    ]);
  });

  it('holds a restart that lands while the first window is still loading', async () => {
    const republished: RendererRuntimeConfig[] = [];
    let announceRestart: ((handshake: SidecarHandshake) => void) | undefined;
    let finishLoad!: () => void;
    const loaded = new Promise<void>((resolve) => {
      finishLoad = resolve;
    });
    let startLoad!: () => void;
    const loading = new Promise<void>((resolve) => {
      startLoad = resolve;
    });

    const started = startShell({
      sessionToken: 'a-session-token',
      createSidecar: ({ onRestart }) => {
        announceRestart = onRestart;
        return { start: async () => HANDSHAKE, stop: async () => refuse('stop') };
      },
      host: {
        registerShutdown: () => undefined,
        openWindow: async () => {
          startLoad();
          return loaded;
        },
        updateRuntimeConfig: (config) => {
          republished.push(config);
        },
        reportFatalError: () => refuse('reportFatalError'),
        quit: () => refuse('quit'),
      },
    });

    await loading;
    announceRestart?.({ ...HANDSHAKE, port: 61_234 });

    // Re-pointing the window now would cancel the navigation that is still in
    // flight, and a cancelled first load is reported to the user as a shell
    // that could not start - out of a restart that in fact succeeded.
    expect(republished).toEqual([]);

    finishLoad();
    await started;

    // Held, not dropped: the window opened addressing the sidecar that died, so
    // without this it would be talking to a port nothing is listening on.
    expect(republished).toEqual([
      {
        baseUrl: 'http://127.0.0.1:61234',
        sessionToken: 'a-session-token',
        // The renderer announces a restart by telling the student that what
        // they had typed was not kept. Nothing was: this reload lands on a page
        // that has only just appeared, so the claim would be false and the
        // notice belongs to the crash-after-startup case instead.
        serviceRestarted: false,
      },
    ]);
  });
});

describe('createShutdownHandler', () => {
  it('holds the quit open until the sidecar has actually exited', async () => {
    let releaseStop!: () => void;
    const sidecarExited = new Promise<void>((resolve) => {
      releaseStop = resolve;
    });
    let prevented = 0;
    let quits = 0;

    const onBeforeQuit = createShutdownHandler(
      {
        stop: async () => {
          await sidecarExited;
        },
      },
      () => {
        quits += 1;
      },
    );

    onBeforeQuit({
      preventDefault: () => {
        prevented += 1;
      },
    });

    // Letting Electron tear the main process down while the sidecar is still
    // closing the local database is exactly how a quit leaves an orphan holding
    // the user's data. The quit is deferred, not cancelled.
    await vi.waitFor(() => {
      expect(prevented).toBe(1);
    });
    expect(quits).toBe(0);

    releaseStop();

    await vi.waitFor(() => {
      expect(quits).toBe(1);
    });
  });

  it('lets the quit it asked for through instead of deferring it again', async () => {
    let prevented = 0;
    let stops = 0;
    let quits = 0;

    const onBeforeQuit = createShutdownHandler(
      {
        stop: async () => {
          stops += 1;
        },
      },
      () => {
        quits += 1;
        // Electron re-runs `before-quit` for the quit the handler itself asked
        // for. A handler that defers that one too never lets the shell close.
        // Only the first re-entry is replayed here: replaying every one would
        // spin forever instead of reporting, which is the fault under test.
        if (quits === 1) {
          onBeforeQuit({
            preventDefault: () => {
              prevented += 1;
            },
          });
        }
      },
    );

    onBeforeQuit({
      preventDefault: () => {
        prevented += 1;
      },
    });

    await vi.waitFor(() => {
      expect(quits).toBe(1);
    });
    expect(prevented).toBe(1);
    expect(stops).toBe(1);
  });
});
