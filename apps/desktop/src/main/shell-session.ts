import type { RendererRuntimeConfig } from '../shared/runtime-config.js';
import { RendererBundleError } from './renderer-entry.js';
import { SidecarStartError } from './sidecar-supervisor.js';
import type { SidecarHandshake } from './sidecar-supervisor.js';

/**
 * Bringing the shell up, expressed without Electron.
 *
 * The order matters and is the whole point of this module: the local API has to
 * be listening before the window exists, because the address it listens on is
 * assigned by the operating system at spawn time and is one of the two things
 * the renderer needs to talk to it. A window opened first would have nothing to
 * connect to and no way to learn the answer later.
 */

/** The part of {@link SidecarSupervisor} this module drives. */
export interface SidecarLifecycle {
  start(): Promise<SidecarHandshake>;
  stop(): Promise<void>;
}

/** What the supervisor reports back once `start()` has already resolved. */
export interface SidecarCallbacks {
  readonly onTerminalFailure: (error: Error) => void;
  readonly onRestart: (handshake: SidecarHandshake) => void;
}

/** The Electron-shaped effects, injected so this module stays plain Node. */
export interface ShellHost {
  /**
   * Arrange for this sidecar to be stopped whenever the application quits.
   *
   * Called before any window exists, because a quit can arrive while the window
   * is still loading and a shutdown arranged after that point would miss it.
   */
  registerShutdown(sidecar: SidecarLifecycle): void;
  openWindow(config: RendererRuntimeConfig): Promise<void>;
  /**
   * Re-point an already-open window at a new runtime configuration.
   *
   * Called when a crashed sidecar has been replaced. The replacement binds a
   * different port, so the address the window was opened with names nothing;
   * without this the shell reads as healthy while every request fails, which is
   * a worse outcome than a visible failure.
   */
  updateRuntimeConfig(config: RendererRuntimeConfig): void;
  reportFatalError(error: FatalError): void;
  quit(): void;
}

/**
 * What the user is told when the shell cannot go on.
 *
 * The title travels with the message because the same channel carries two
 * different events: a shell that never came up, and one that has been open for
 * an hour and just lost the service under it. Telling a student who has been
 * working all afternoon that Nexus "cannot start" contradicts the afternoon.
 */
export interface FatalError {
  readonly title: string;
  readonly message: string;
}

export interface StartShellOptions {
  readonly sessionToken: string;
  /**
   * Build the sidecar, wiring the supervisor's post-startup callbacks to the
   * handlers passed in. Both are the only way anything that happens after the
   * start promise settles can reach the shell: a crash it could not recover
   * from, and a recovery that moved the service to a new address.
   */
  readonly createSidecar: (callbacks: SidecarCallbacks) => SidecarLifecycle;
  readonly host: ShellHost;
}

/**
 * Start the local API and, once it answers, the window that talks to it.
 *
 * Resolves once the shell is up, or once the user has been told why it is not.
 */
export async function startShell(options: StartShellOptions): Promise<void> {
  let sidecar: SidecarLifecycle;
  let handshake: SidecarHandshake;

  try {
    // Constructing the sidecar can fail on its own - an unconfigured command,
    // a path that is not there - and to the user that is indistinguishable from
    // a sidecar that failed to start. Both belong on the same path out.
    sidecar = options.createSidecar({
      onTerminalFailure: (error) => {
        options.host.reportFatalError(describeTerminalFailure(error));
        options.host.quit();
      },
      // A replacement sidecar is only a recovery once the window knows where it
      // went. This covers a crash after the window is open, and only that: the
      // supervisor does not restart a sidecar that died before `start()`
      // resolved, so a shell that cannot come up reaches the user as the
      // startup failure below rather than as a silent retry.
      onRestart: (replacement) => {
        options.host.updateRuntimeConfig(
          runtimeConfigFor(replacement, options.sessionToken, true),
        );
      },
    });
    handshake = await sidecar.start();
  } catch (error) {
    // A window is worse than no window here. Without the local API the shell
    // can render nothing but an empty frame, and an empty frame tells the user
    // neither what went wrong nor what to do about it.
    options.host.reportFatalError(describeStartupFailure(error));
    options.host.quit();
    return;
  }

  options.host.registerShutdown(sidecar);

  try {
    await options.host.openWindow(runtimeConfigFor(handshake, options.sessionToken, false));
  } catch (error) {
    // The sidecar is running by now, so this is the one failure that can leave
    // a process behind: no window will ever close to trigger the shutdown.
    options.host.reportFatalError(describeStartupFailure(error));
    await sidecar.stop();
    options.host.quit();
  }
}

/** Shown when the shell never came up, as against one that has to close. */
const STARTUP_FAILURE_TITLE = 'Nexus cannot start';

/**
 * What the renderer is told about a sidecar, derived in one place.
 *
 * The initial window and every replacement after a restart have to agree on
 * how an announcement becomes an address, or a recovery quietly points the
 * page somewhere the original never was.
 */
function runtimeConfigFor(
  handshake: SidecarHandshake,
  sessionToken: string,
  serviceRestarted: boolean,
): RendererRuntimeConfig {
  return {
    baseUrl: `http://${handshake.host}:${String(handshake.port)}`,
    // The supervisor spawns a replacement with the same credential, so this is
    // still the token the service expects.
    sessionToken,
    serviceRestarted,
  };
}

/**
 * Turn a startup failure into something a user can act on.
 *
 * The supervisor distinguishes its failures by reason precisely so this can
 * say different things about them: a runtime that never came up and a runtime
 * that came up speaking the wrong protocol call for different remedies. The
 * underlying message is always appended, because the person who eventually
 * reads a bug report needs the detail the person reading the dialog does not.
 */
function describeStartupFailure(error: unknown): FatalError {
  // A missing interface already explains itself, including what to run. Wrapping
  // it in the local-service preamble would send the reader after the wrong fault.
  if (error instanceof RendererBundleError) {
    return { title: STARTUP_FAILURE_TITLE, message: error.message };
  }

  const detail = error instanceof Error ? error.message : String(error);

  if (error instanceof SidecarStartError) {
    switch (error.reason) {
      case 'handshake-timeout':
        return {
          title: STARTUP_FAILURE_TITLE,
          message:
            'Nexus could not start its local service.\n\n' +
            'The service was launched but never reported that it was ready. That ' +
            'usually means its runtime is missing from the installation, or ' +
            'security software on this machine blocked it from starting.\n\n' +
            `Details: ${detail}`,
        };
      case 'unsupported-schema-version':
        return {
          title: STARTUP_FAILURE_TITLE,
          message:
            'Nexus could not start its local service.\n\n' +
            'The service announced a startup protocol this version of Nexus does ' +
            'not understand, which means the two halves of the installation do ' +
            'not match. Reinstalling Nexus should resolve it.\n\n' +
            `Details: ${detail}`,
        };
    }
  }

  return {
    title: STARTUP_FAILURE_TITLE,
    message: `Nexus could not start its local service.\n\nDetails: ${detail}`,
  };
}

/**
 * Explain a sidecar that died after the window was already open.
 *
 * The supervisor has already retried and given up by the time this is reached,
 * so there is nothing left to offer but an accurate account: the window is
 * still on screen, but everything in it would now fail.
 */
function describeTerminalFailure(error: Error): FatalError {
  return {
    title: 'Nexus has to close',
    message:
      'The local service Nexus depends on stopped running and could not be ' +
      'restarted, so Nexus has to close.\n\n' +
      `Details: ${error.message}`,
  };
}

/** Build the `before-quit` listener that shuts the sidecar down first. */
export function createShutdownHandler(
  sidecar: Pick<SidecarLifecycle, 'stop'>,
  quit: () => void,
): (event: { preventDefault: () => void }) => void {
  let shuttingDown = false;

  return (event) => {
    // The quit this handler asks for arrives back here as another `before-quit`.
    // Deferring that one as well would leave the shell asking itself to close
    // forever, so the second pass is let through untouched.
    if (shuttingDown) {
      return;
    }

    shuttingDown = true;
    event.preventDefault();
    void sidecar.stop().finally(quit);
  };
}
